from __future__ import annotations
import json
from typing import Optional

from sqlalchemy import select

from .base import BaseAgent
from ..database import AsyncSessionLocal
from ..models import PolicyRule, ApprovalDecision
from ..schemas import AuditLogEntry, ApprovalRoutingOutput

PROMPT_VERSION = "approval-route-v1.0"


class ApprovalRoutingAgent(BaseAgent):
    agent_name = "approval-routing"

    async def route(
        self,
        request_id: str,
        requester: str,
        value: float,
        currency: str,
        category: str,
        description: Optional[str] = None,
        pilot_team: Optional[str] = None,
    ) -> ApprovalRoutingOutput:
        self._reset_retrieval()

        # ── Step 1: Mandatory policy lookup (retrieval equivalent) ───────────
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PolicyRule).where(
                    PolicyRule.active == 1,
                    PolicyRule.min_value <= value,
                )
            )
            all_rules = result.scalars().all()

        # Filter by category and value range
        matching = [
            r for r in all_rules
            if _category_matches(r.category, category)
            and (r.max_value is None or value <= r.max_value)
        ]
        self._mark_retrieval_done()

        context_payload = {
            "request_id": request_id,
            "value": value,
            "currency": currency,
            "category": category,
            "matching_rule_ids": [r.rule_id for r in matching],
        }
        input_hash = self.payload_hash(context_payload)

        # ── Step 2: Route via LLM (or deterministic fallback) ────────────────
        self._require_retrieval()

        if not matching:
            output = _policy_gap_output(request_id, requester, value, currency, category)
        else:
            rules_payload = [
                {
                    "rule_id": r.rule_id,
                    "category": r.category,
                    "min_value": r.min_value,
                    "max_value": r.max_value,
                    "approver_level_1": r.approver_level_1,
                    "approver_level_2": r.approver_level_2,
                    "approver_level_3": r.approver_level_3,
                    "dual_approval_required": bool(r.dual_approval_required),
                    "escalation_condition": r.escalation_condition,
                    "sla_hours": r.sla_hours,
                    "description": r.description,
                }
                for r in matching
            ]
            prompt = self.get_versioned_prompt(PROMPT_VERSION)
            user_message = (
                f"Purchase Request:\n"
                f"  ID: {request_id}\n"
                f"  Requester: {requester}\n"
                f"  Value: {currency} {value:,.2f}\n"
                f"  Category: {category}\n"
                f"  Description: {description or 'N/A'}\n\n"
                f"Matching Policy Rules:\n{json.dumps(rules_payload, indent=2)}"
            )
            try:
                raw = await self._llm_call(prompt, user_message)
                output = _build_output(request_id, requester, value, currency, category, raw)
            except Exception as exc:
                # Deterministic fallback: pick highest-specificity matching rule
                print(f"[approval-routing] LLM unavailable ({exc}), using deterministic fallback")
                output = _deterministic_route(
                    request_id, requester, value, currency, category, matching
                )

        # ── Step 3: Persist decision ─────────────────────────────────────────
        async with AsyncSessionLocal() as db:
            decision = ApprovalDecision(
                request_id=request_id,
                policy_rule_id=output.policy_rule if not output.is_policy_gap else "POLICY-GAP",
                approval_chain=json.dumps(output.approval_chain),
                escalation_condition=output.escalation_condition,
                sla_hours=output.sla_hours,
                routing_confidence=output.routing_confidence,
                is_policy_gap=int(output.is_policy_gap),
            )
            db.add(decision)
            await db.commit()

        # ── Step 4: Audit log ────────────────────────────────────────────────
        await self.emit_audit_log(AuditLogEntry(
            timestamp=self._utcnow(),
            agent=self.agent_name,
            action="approval_route",
            request_id=request_id,
            confidence=output.routing_confidence,
            policy_rule=output.policy_rule,
            prompt_version=PROMPT_VERSION,
            pilot_team=pilot_team,
            slack_channel="#procurement-alerts" if output.escalation_condition else None,
            status="policy-gap" if output.is_policy_gap else "routed",
            context_payload_hash=input_hash,
        ))

        return output


# ── Helpers ───────────────────────────────────────────────────────────────────

def _category_matches(rule_cat: str, request_cat: str) -> bool:
    return (
        rule_cat.lower() == "all"
        or rule_cat.lower() == request_cat.lower()
        or request_cat.lower().startswith(rule_cat.lower())
    )


def _policy_gap_output(request_id, requester, value, currency, category) -> ApprovalRoutingOutput:
    return ApprovalRoutingOutput(
        request_id=request_id,
        requester=requester,
        value=value,
        currency=currency,
        category=category,
        policy_rule="POLICY-GAP — no matching rule found",
        approval_chain=["procurement-policy-owner"],
        escalation_condition="Policy gap: manual review required",
        sla_hours=48,
        is_policy_gap=True,
        routing_confidence=0.0,
    )


def _build_output(request_id, requester, value, currency, category, raw) -> ApprovalRoutingOutput:
    chain = raw.get("approval_chain", ["procurement-manager"])
    if not isinstance(chain, list):
        chain = [str(chain)]
    return ApprovalRoutingOutput(
        request_id=request_id,
        requester=requester,
        value=value,
        currency=currency,
        category=category,
        policy_rule=raw.get("policy_rule_id", "unknown"),
        approval_chain=chain,
        escalation_condition=raw.get("escalation_condition"),
        sla_hours=int(raw.get("sla_hours", 24)),
        is_policy_gap=bool(raw.get("is_policy_gap", False)),
        routing_confidence=float(raw.get("routing_confidence", 0.8)),
    )


def _deterministic_route(
    request_id, requester, value, currency, category, rules: list
) -> ApprovalRoutingOutput:
    # Pick narrowest value range; break ties by specificity of category match
    def specificity(r):
        cat_exact = 1 if r.category.lower() == category.lower() else 0
        value_range = (r.max_value or 1e9) - r.min_value
        return (cat_exact, -value_range)

    best = sorted(rules, key=specificity, reverse=True)[0]
    chain = [best.approver_level_1]
    if best.approver_level_2:
        chain.append(best.approver_level_2)
    if best.approver_level_3:
        chain.append(best.approver_level_3)
    return ApprovalRoutingOutput(
        request_id=request_id,
        requester=requester,
        value=value,
        currency=currency,
        category=category,
        policy_rule=best.rule_id,
        approval_chain=chain,
        escalation_condition=best.escalation_condition,
        sla_hours=best.sla_hours,
        is_policy_gap=False,
        routing_confidence=0.9,
    )
