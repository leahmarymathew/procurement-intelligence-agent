from __future__ import annotations
import json
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select

from .base import BaseAgent
from ..database import AsyncSessionLocal
from ..models import (
    MetricsAggregate, PilotMetrics, SupplierScore, ApprovalDecision,
    AuditLog, ProcessBacklog, StakeholderFeedback,
)
from ..schemas import AuditLogEntry

PROMPT_VERSION = "metrics-report-v1.0"


class MetricsReportingAgent(BaseAgent):
    agent_name = "metrics-reporting"

    async def update_metrics(
        self,
        event: str,
        agent_type: Optional[str] = None,
        pilot_team: Optional[str] = None,
        confidence: Optional[float] = None,
        is_escalation: bool = False,
        is_policy_gap: bool = False,
    ) -> None:
        """Increment aggregate metrics for today after every agent action."""
        today = date.today().isoformat()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(MetricsAggregate).where(MetricsAggregate.metric_date == today)
            )
            agg = result.scalar_one_or_none()
            if not agg:
                agg = MetricsAggregate(metric_date=today)
                db.add(agg)

            if event == "request_processed":
                agg.requests_processed += 1
            elif event == "supplier_scored":
                agg.supplier_scores_generated += 1
            elif event == "approval_decided":
                agg.approval_decisions_made += 1
            elif event == "finding_added":
                agg.process_findings_count += 1

            if is_escalation:
                total = agg.approval_decisions_made or 1
                # Recalculate escalation rate
                esc_result = await db.execute(
                    select(ApprovalDecision).where(ApprovalDecision.escalation_condition.isnot(None))
                )
                escalations = len(esc_result.scalars().all())
                agg.escalation_rate = round(escalations / total, 4)

            if is_policy_gap:
                agg.policy_gap_count += 1

            if confidence is not None:
                # Rolling average (simplified)
                total_scores = agg.supplier_scores_generated or 1
                agg.avg_confidence = round(
                    (agg.avg_confidence * (total_scores - 1) + confidence) / total_scores, 4
                )

            if agent_type:
                invocations = json.loads(agg.agent_invocations or "{}")
                invocations[agent_type] = invocations.get(agent_type, 0) + 1
                agg.agent_invocations = json.dumps(invocations)

            if pilot_team:
                pm_result = await db.execute(
                    select(PilotMetrics).where(
                        PilotMetrics.pilot_team == pilot_team,
                        PilotMetrics.status == "active",
                    ).order_by(PilotMetrics.stage.desc())
                )
                pm = pm_result.scalar_one_or_none()
                if pm and event == "request_processed":
                    pm.requests_processed += 1
                    pm.updated_at = datetime.utcnow().isoformat()

            agg.updated_at = datetime.utcnow().isoformat()
            await db.commit()

    async def generate_weekly_report(
        self,
        pilot_team: Optional[str] = None,
    ) -> dict:
        """Produce a weekly insight summary and push to Slack."""
        self._reset_retrieval()

        # ── Step 1: Mandatory data retrieval ─────────────────────────────────
        metrics_snapshot = await _collect_metrics_snapshot(pilot_team)
        self._mark_retrieval_done()

        context_payload = {"pilot_team": pilot_team, **metrics_snapshot}
        input_hash = self.payload_hash(context_payload)

        # ── Step 2: LLM report generation ────────────────────────────────────
        self._require_retrieval()
        prompt = self.get_versioned_prompt(PROMPT_VERSION)
        user_message = f"Metrics Snapshot:\n{json.dumps(metrics_snapshot, indent=2, default=str)}"

        try:
            report = await self._llm_call(prompt, user_message)
        except Exception as exc:
            print(f"[metrics-reporting] LLM unavailable ({exc}), using fallback report")
            report = _fallback_report(metrics_snapshot)

        # ── Step 3: Push to Slack ─────────────────────────────────────────────
        from ..notifications.slack import send_weekly_report
        await send_weekly_report(
            headline=report.get("headline", "Weekly procurement summary"),
            highlights=report.get("highlights", []),
            concerns=report.get("concerns", []),
            top_backlog_actions=report.get("top_backlog_actions", []),
            feedback_discrepancy=report.get("feedback_discrepancy"),
            recommended_focus=report.get("recommended_focus", ""),
            pilot_team=pilot_team,
        )

        # ── Step 4: Audit log ─────────────────────────────────────────────────
        await self.emit_audit_log(AuditLogEntry(
            timestamp=self._utcnow(),
            agent=self.agent_name,
            action="weekly_report_generated",
            confidence=0.9,
            prompt_version=PROMPT_VERSION,
            pilot_team=pilot_team,
            slack_channel="#procurement-weekly",
            status="sent",
            context_payload_hash=input_hash,
        ))

        return report


async def _collect_metrics_snapshot(pilot_team: Optional[str]) -> dict:
    today = date.today().isoformat()
    async with AsyncSessionLocal() as db:
        agg_result = await db.execute(
            select(MetricsAggregate).where(MetricsAggregate.metric_date == today)
        )
        agg = agg_result.scalar_one_or_none()

        backlog_result = await db.execute(
            select(ProcessBacklog)
            .where(ProcessBacklog.status == "backlog")
            .order_by(ProcessBacklog.score.desc())
            .limit(5)
        )
        top_items = backlog_result.scalars().all()

        fb_result = await db.execute(select(StakeholderFeedback))
        feedback = fb_result.scalars().all()
        avg_rating = (
            round(sum(f.rating or 0 for f in feedback) / len(feedback), 2)
            if feedback else None
        )

        return {
            "date": today,
            "requests_processed": agg.requests_processed if agg else 0,
            "supplier_scores_generated": agg.supplier_scores_generated if agg else 0,
            "approval_decisions_made": agg.approval_decisions_made if agg else 0,
            "avg_approval_cycle_hours": agg.avg_approval_cycle_hours if agg else 0,
            "escalation_rate": agg.escalation_rate if agg else 0,
            "policy_gap_count": agg.policy_gap_count if agg else 0,
            "process_findings_count": agg.process_findings_count if agg else 0,
            "avg_confidence": agg.avg_confidence if agg else 0,
            "avg_stakeholder_rating": avg_rating,
            "top_backlog_items": [
                {"finding_id": b.finding_id, "score": b.score, "bottleneck": b.bottleneck,
                 "recommended_action": b.recommended_action}
                for b in top_items
            ],
        }


def _fallback_report(snapshot: dict) -> dict:
    rp = snapshot.get("requests_processed", 0)
    esc = round(snapshot.get("escalation_rate", 0) * 100, 1)
    conf = round(snapshot.get("avg_confidence", 0) * 100, 1)
    rating = snapshot.get("avg_stakeholder_rating")

    concerns = []
    if esc > 15:
        concerns.append(f"Escalation rate of {esc}% exceeds 15% target")
    if conf < 60:
        concerns.append(f"Average scoring confidence of {conf}% is below 60% threshold")
    if not concerns:
        concerns.append("No critical concerns this week")

    discrepancy = None
    if rating and rating < 3.5 and esc < 10:
        discrepancy = (
            f"Stakeholder satisfaction ({rating}/5) is low despite escalation rate "
            f"of only {esc}% — investigate qualitative feedback for hidden friction points."
        )

    return {
        "headline": f"Processed {rp} requests this period with {esc}% escalation rate.",
        "highlights": [f"{rp} purchase requests handled", f"Average agent confidence: {conf}%"],
        "concerns": concerns,
        "top_backlog_actions": [
            b["recommended_action"] for b in snapshot.get("top_backlog_items", [])
            if b.get("recommended_action")
        ] or ["No backlog items to action this week"],
        "feedback_discrepancy": discrepancy,
        "recommended_focus": "Review policy gaps and low-confidence supplier scores.",
    }
