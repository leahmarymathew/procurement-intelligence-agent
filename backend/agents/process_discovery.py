from __future__ import annotations
import json
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, func

from .base import BaseAgent
from ..database import AsyncSessionLocal
from ..models import ApprovalDecision, AuditLog, SupplierScore, ProcessBacklog, StakeholderFeedback
from ..schemas import AuditLogEntry, ProcessFinding

PROMPT_VERSION = "process-discovery-v1.0"

IMPACT_WEIGHT = {"high": 3, "medium": 2, "low": 1}
EFFORT_INVERSE = {"low": 3, "medium": 2, "high": 1}


class ProcessDiscoveryAgent(BaseAgent):
    agent_name = "process-discovery"

    async def discover(
        self,
        pilot_team: Optional[str] = None,
    ) -> list[ProcessFinding]:
        self._reset_retrieval()

        # ── Step 1: Mandatory data retrieval from SQLite logs ────────────────
        workflow_data = await _collect_workflow_data(pilot_team)
        self._mark_retrieval_done()

        context_payload = {
            "pilot_team": pilot_team,
            "data_snapshot": {k: str(v)[:100] for k, v in workflow_data.items()},
        }
        input_hash = self.payload_hash(context_payload)

        # ── Step 2: LLM analysis ─────────────────────────────────────────────
        self._require_retrieval()
        prompt = self.get_versioned_prompt(PROMPT_VERSION)
        user_message = f"Workflow Performance Data:\n{json.dumps(workflow_data, indent=2, default=str)}"

        try:
            raw = await self._llm_call(prompt, user_message)
            raw_findings = raw if isinstance(raw, list) else raw.get("findings", [raw])
        except Exception as exc:
            print(f"[process-discovery] LLM unavailable ({exc}), using heuristic findings")
            raw_findings = _heuristic_findings(workflow_data)

        # ── Step 3: Score, validate, and persist findings ────────────────────
        findings: list[ProcessFinding] = []
        async with AsyncSessionLocal() as db:
            for item in raw_findings[:10]:
                effort = item.get("effort", "medium").lower()
                impact = item.get("impact", "medium").lower()
                score = IMPACT_WEIGHT.get(impact, 2) * EFFORT_INVERSE.get(effort, 2)
                finding_id = f"PF-{uuid.uuid4().hex[:8].upper()}"
                today = date.today().isoformat()

                finding = ProcessFinding(
                    finding_id=finding_id,
                    workflow=item.get("workflow", "approval"),
                    bottleneck=item.get("bottleneck", "Unknown bottleneck"),
                    root_cause_hypothesis=item.get("root_cause_hypothesis"),
                    effort=effort,
                    impact=impact,
                    score=score,
                    recommended_action=item.get("recommended_action"),
                    status="backlog",
                    discovered_date=today,
                )
                findings.append(finding)

                record = ProcessBacklog(
                    finding_id=finding_id,
                    workflow=finding.workflow,
                    bottleneck=finding.bottleneck,
                    root_cause_hypothesis=finding.root_cause_hypothesis,
                    effort=effort,
                    impact=impact,
                    score=score,
                    recommended_action=finding.recommended_action,
                    status="backlog",
                    discovered_date=today,
                    pilot_team=pilot_team,
                )
                db.add(record)
            await db.commit()

        # ── Step 4: Audit log ────────────────────────────────────────────────
        await self.emit_audit_log(AuditLogEntry(
            timestamp=self._utcnow(),
            agent=self.agent_name,
            action="process_discovery_run",
            confidence=0.85,
            prompt_version=PROMPT_VERSION,
            pilot_team=pilot_team,
            slack_channel="#ops-process",
            status=f"{len(findings)}_findings",
            context_payload_hash=input_hash,
        ))

        return findings


async def _collect_workflow_data(pilot_team: Optional[str]) -> dict:
    async with AsyncSessionLocal() as db:
        # Approval cycle times from audit log
        audit_q = select(AuditLog).where(AuditLog.agent == "approval-routing").limit(200)
        audit_result = await db.execute(audit_q)
        audit_rows = audit_result.scalars().all()

        # Supplier scoring stats
        score_q = select(SupplierScore).limit(100)
        score_result = await db.execute(score_q)
        scores = score_result.scalars().all()

        # Approval decisions: policy gaps and escalations
        decision_q = select(ApprovalDecision).limit(200)
        decision_result = await db.execute(decision_q)
        decisions = decision_result.scalars().all()

        # Stakeholder feedback
        fb_q = select(StakeholderFeedback)
        if pilot_team:
            fb_q = fb_q.where(StakeholderFeedback.pilot_team == pilot_team)
        fb_result = await db.execute(fb_q)
        feedback_rows = fb_result.scalars().all()

        policy_gaps = sum(1 for d in decisions if d.is_policy_gap)
        escalations = sum(1 for d in decisions if d.escalation_condition)
        avg_confidence = (
            sum(s.confidence or 0 for s in scores) / len(scores) if scores else 0
        )
        avg_rating = (
            sum(f.rating or 0 for f in feedback_rows) / len(feedback_rows)
            if feedback_rows else None
        )

        return {
            "total_audit_events": len(audit_rows),
            "total_approval_decisions": len(decisions),
            "policy_gap_count": policy_gaps,
            "escalation_count": escalations,
            "escalation_rate_pct": round(100 * escalations / max(len(decisions), 1), 1),
            "total_supplier_scores": len(scores),
            "avg_supplier_confidence": round(avg_confidence, 3),
            "low_confidence_scores": sum(1 for s in scores if (s.confidence or 1) < 0.5),
            "watch_list_or_disqualified": sum(
                1 for s in scores if s.status in ("watch-list", "disqualified")
            ),
            "stakeholder_feedback_count": len(feedback_rows),
            "avg_stakeholder_rating": round(avg_rating, 2) if avg_rating else None,
        }


def _heuristic_findings(data: dict) -> list[dict]:
    findings = []
    if data.get("policy_gap_count", 0) > 0:
        findings.append({
            "workflow": "approval",
            "bottleneck": f"{data['policy_gap_count']} purchase requests found no matching policy rule",
            "root_cause_hypothesis": "Policy table has gaps for emerging spend categories or new value thresholds",
            "effort": "medium",
            "impact": "high",
            "recommended_action": "Conduct a policy-gap analysis session with procurement policy owner; add missing rules within 2 weeks",
        })
    if data.get("low_confidence_scores", 0) > 0:
        findings.append({
            "workflow": "sourcing",
            "bottleneck": f"{data['low_confidence_scores']} supplier scores had confidence below 50%",
            "root_cause_hypothesis": "Knowledge base is sparse for those supplier categories",
            "effort": "low",
            "impact": "medium",
            "recommended_action": "Enrich knowledge base with performance records and audit outcomes for low-confidence suppliers",
        })
    if data.get("escalation_rate_pct", 0) > 15:
        findings.append({
            "workflow": "approval",
            "bottleneck": f"Escalation rate of {data['escalation_rate_pct']}% exceeds 15% threshold",
            "root_cause_hypothesis": "Approval thresholds or delegated authority matrix may be misaligned with actual spend patterns",
            "effort": "medium",
            "impact": "high",
            "recommended_action": "Review delegated authority matrix against last 6 months of spend data; adjust thresholds",
        })
    if not findings:
        findings.append({
            "workflow": "approval",
            "bottleneck": "Insufficient data volume for meaningful pattern detection",
            "root_cause_hypothesis": "System is new; baseline metrics not yet established",
            "effort": "low",
            "impact": "low",
            "recommended_action": "Increase data collection period to 30 days before running process discovery",
        })
    return findings
