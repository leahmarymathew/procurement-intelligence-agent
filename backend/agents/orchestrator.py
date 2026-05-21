"""
LangGraph orchestrator — state machine for the full S2P agent pipeline.

State transitions are logged to /audit-log before execution.
No agent is invoked without a prior retrieval step (enforced inside each agent).
"""
from __future__ import annotations
import hashlib
import json
import uuid
from datetime import datetime
from typing import Annotated, Optional
import operator

from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from ..schemas import AuditLogEntry, OrchestratorRequest
from .base import BaseAgent

# ── State definition ──────────────────────────────────────────────────────────

class ProcurementState(TypedDict):
    run_id: str
    request_type: str
    payload: dict
    pilot_team: Optional[str]

    supplier_score_result: Optional[dict]
    approval_routing_result: Optional[dict]
    process_findings: Optional[list]
    weekly_report_result: Optional[dict]

    audit_entries: Annotated[list, operator.add]
    notifications_sent: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]

    needs_supplier_score: bool
    needs_approval_routing: bool
    complete: bool


# ── Transition logger (emitted before each node executes) ─────────────────────

_base = BaseAgent()
_base.agent_name = "orchestrator"


async def _log_transition(state: ProcurementState, source: str, target: str, trigger: str):
    payload_hash = hashlib.sha256(
        json.dumps(state["payload"], sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    await _base.emit_audit_log(AuditLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        agent="orchestrator",
        action="state_transition",
        request_id=state["payload"].get("request_id"),
        pilot_team=state.get("pilot_team"),
        status="transition",
        context_payload_hash=payload_hash,
        source_agent=source,
        target_agent=target,
        triggering_condition=trigger,
    ))


# ── Node implementations ──────────────────────────────────────────────────────

async def intake_node(state: ProcurementState) -> dict:
    await _log_transition(state, "external", "intake", f"request_type={state['request_type']}")
    rtype = state["request_type"]
    payload = state["payload"]
    return {
        "needs_supplier_score": (
            rtype in ("purchase_request", "supplier_score")
            and bool(payload.get("supplier_name"))
        ),
        "needs_approval_routing": rtype == "purchase_request",
        "errors": [],
        "audit_entries": [],
        "notifications_sent": [],
    }


async def supplier_scoring_node(state: ProcurementState) -> dict:
    await _log_transition(state, "intake", "supplier_scoring", "needs_supplier_score=True")
    from .supplier_scoring import SupplierScoringAgent
    agent = SupplierScoringAgent()
    p = state["payload"]
    try:
        result = await agent.score(
            supplier_name=p["supplier_name"],
            category=p.get("category", "general"),
            request_id=p.get("request_id"),
            pilot_team=state.get("pilot_team"),
        )
        score_dict = result.model_dump()
    except Exception as exc:
        score_dict = {"error": str(exc)}
        return {"supplier_score_result": score_dict, "errors": [f"supplier_scoring: {exc}"]}

    # Update aggregate metrics
    from .metrics_reporting import MetricsReportingAgent
    await MetricsReportingAgent().update_metrics(
        "supplier_scored",
        agent_type="supplier-scoring",
        pilot_team=state.get("pilot_team"),
        confidence=score_dict.get("confidence"),
    )

    # Slack if watch-list or disqualified
    notifications = []
    if score_dict.get("status") in ("watch-list", "disqualified"):
        from ..notifications.slack import send_supplier_flag
        scores = score_dict.get("scores", {})
        concerns = [
            f"reliability={score_dict['reliability']['score']}" if "reliability" in score_dict else "",
        ]
        await send_supplier_flag(
            supplier_name=p["supplier_name"],
            composite_score=score_dict.get("composite", 0),
            status=score_dict["status"],
            category=p.get("category", "general"),
            top_concern=" | ".join(c for c in concerns if c),
            pilot_team=state.get("pilot_team"),
        )
        notifications.append({"channel": "#supplier-intel", "event": "supplier_flag"})

    return {
        "supplier_score_result": score_dict,
        "notifications_sent": notifications,
    }


async def approval_routing_node(state: ProcurementState) -> dict:
    await _log_transition(state, "supplier_scoring", "approval_routing", "needs_approval_routing=True")
    from .approval_routing import ApprovalRoutingAgent
    agent = ApprovalRoutingAgent()
    p = state["payload"]
    try:
        result = await agent.route(
            request_id=p.get("request_id", f"PR-{uuid.uuid4().hex[:6].upper()}"),
            requester=p.get("requester", "unknown"),
            value=float(p.get("value", 0)),
            currency=p.get("currency", "USD"),
            category=p.get("category", "general"),
            description=p.get("description"),
            pilot_team=state.get("pilot_team"),
        )
        routing_dict = result.model_dump()
    except Exception as exc:
        routing_dict = {"error": str(exc)}
        return {"approval_routing_result": routing_dict, "errors": [f"approval_routing: {exc}"]}

    # Update metrics
    from .metrics_reporting import MetricsReportingAgent
    await MetricsReportingAgent().update_metrics(
        "approval_decided",
        agent_type="approval-routing",
        pilot_team=state.get("pilot_team"),
        is_escalation=bool(routing_dict.get("escalation_condition")),
        is_policy_gap=routing_dict.get("is_policy_gap", False),
    )
    await MetricsReportingAgent().update_metrics(
        "request_processed",
        pilot_team=state.get("pilot_team"),
    )

    # Slack escalation alert
    notifications = []
    if routing_dict.get("escalation_condition"):
        from ..notifications.slack import send_escalation_alert
        await send_escalation_alert(
            request_id=routing_dict["request_id"],
            requester=routing_dict["requester"],
            value=routing_dict["value"],
            currency=routing_dict["currency"],
            category=routing_dict["category"],
            escalation_reason=routing_dict["escalation_condition"],
            pilot_team=state.get("pilot_team"),
        )
        notifications.append({"channel": "#procurement-alerts", "event": "escalation"})

    return {
        "approval_routing_result": routing_dict,
        "notifications_sent": notifications,
    }


async def process_discovery_node(state: ProcurementState) -> dict:
    await _log_transition(state, "intake", "process_discovery", "request_type=process_discovery")
    from .process_discovery import ProcessDiscoveryAgent
    agent = ProcessDiscoveryAgent()
    try:
        findings = await agent.discover(pilot_team=state.get("pilot_team"))
        findings_list = [f.model_dump() for f in findings]
    except Exception as exc:
        return {"process_findings": [], "errors": [f"process_discovery: {exc}"]}

    # Update metrics count
    from .metrics_reporting import MetricsReportingAgent
    reporter = MetricsReportingAgent()
    for _ in findings_list:
        await reporter.update_metrics("finding_added", agent_type="process-discovery")

    # Slack for high-score findings
    notifications = []
    for f in findings_list:
        if f.get("score", 0) >= 7:
            from ..notifications.slack import send_backlog_alert
            await send_backlog_alert(
                finding_id=f["finding_id"],
                workflow=f["workflow"],
                bottleneck=f["bottleneck"],
                score=f["score"],
                recommended_action=f.get("recommended_action", ""),
                pilot_team=state.get("pilot_team"),
            )
            notifications.append({"channel": "#ops-process", "event": "backlog_alert"})

    return {"process_findings": findings_list, "notifications_sent": notifications}


async def weekly_report_node(state: ProcurementState) -> dict:
    await _log_transition(state, "intake", "weekly_report", "request_type=weekly_report")
    from .metrics_reporting import MetricsReportingAgent
    agent = MetricsReportingAgent()
    try:
        report = await agent.generate_weekly_report(pilot_team=state.get("pilot_team"))
    except Exception as exc:
        return {"weekly_report_result": {"error": str(exc)}, "errors": [f"weekly_report: {exc}"]}
    return {"weekly_report_result": report}


async def complete_node(state: ProcurementState) -> dict:
    await _log_transition(state, "pipeline", "complete", "all_nodes_done")
    return {"complete": True}


# ── Routing logic ─────────────────────────────────────────────────────────────

def _route_from_intake(state: ProcurementState) -> str:
    rtype = state["request_type"]
    if rtype == "process_discovery":
        return "process_discovery"
    if rtype == "weekly_report":
        return "weekly_report"
    if state.get("needs_supplier_score"):
        return "supplier_scoring"
    if state.get("needs_approval_routing"):
        return "approval_routing"
    return "complete"


def _route_after_supplier_scoring(state: ProcurementState) -> str:
    if state.get("needs_approval_routing"):
        return "approval_routing"
    return "complete"


# ── Graph assembly ────────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    g = StateGraph(ProcurementState)

    g.add_node("intake", intake_node)
    g.add_node("supplier_scoring", supplier_scoring_node)
    g.add_node("approval_routing", approval_routing_node)
    g.add_node("process_discovery", process_discovery_node)
    g.add_node("weekly_report", weekly_report_node)
    g.add_node("complete", complete_node)

    g.set_entry_point("intake")

    g.add_conditional_edges("intake", _route_from_intake, {
        "supplier_scoring": "supplier_scoring",
        "approval_routing": "approval_routing",
        "process_discovery": "process_discovery",
        "weekly_report": "weekly_report",
        "complete": "complete",
    })
    g.add_conditional_edges("supplier_scoring", _route_after_supplier_scoring, {
        "approval_routing": "approval_routing",
        "complete": "complete",
    })
    g.add_edge("approval_routing", "complete")
    g.add_edge("process_discovery", "complete")
    g.add_edge("weekly_report", "complete")
    g.add_edge("complete", END)

    return g


_graph = _build_graph().compile()


# ── Public entry point ────────────────────────────────────────────────────────

async def run_orchestrator(request: OrchestratorRequest) -> dict:
    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    initial_state: ProcurementState = {
        "run_id": run_id,
        "request_type": request.request_type,
        "payload": request.payload,
        "pilot_team": request.pilot_team,
        "supplier_score_result": None,
        "approval_routing_result": None,
        "process_findings": None,
        "weekly_report_result": None,
        "audit_entries": [],
        "notifications_sent": [],
        "errors": [],
        "needs_supplier_score": False,
        "needs_approval_routing": False,
        "complete": False,
    }

    final_state = await _graph.ainvoke(initial_state)

    return {
        "run_id": run_id,
        "request_type": request.request_type,
        "supplier_score": final_state.get("supplier_score_result"),
        "approval_routing": final_state.get("approval_routing_result"),
        "process_findings": final_state.get("process_findings"),
        "weekly_report": final_state.get("weekly_report_result"),
        "notifications_sent": final_state.get("notifications_sent", []),
        "errors": final_state.get("errors", []),
        "complete": final_state.get("complete", False),
    }
