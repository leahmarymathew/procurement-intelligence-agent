from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ── Audit Log ────────────────────────────────────────────────────────────────

class AuditLogEntry(BaseModel):
    timestamp: str
    agent: str
    action: str
    request_id: Optional[str] = None
    confidence: Optional[float] = None
    policy_rule: Optional[str] = None
    prompt_version: Optional[str] = None
    pilot_team: Optional[str] = None
    slack_channel: Optional[str] = None
    status: Optional[str] = None
    context_payload_hash: Optional[str] = None
    source_agent: Optional[str] = None
    target_agent: Optional[str] = None
    triggering_condition: Optional[str] = None


class AuditLogResponse(AuditLogEntry):
    id: int
    created_at: str


# ── Purchase Requests ────────────────────────────────────────────────────────

class PurchaseRequestCreate(BaseModel):
    requester: str
    supplier_name: Optional[str] = None
    category: str
    value: float
    currency: str = "USD"
    description: Optional[str] = None
    pilot_team: Optional[str] = None


class PurchaseRequestResponse(PurchaseRequestCreate):
    request_id: str
    status: str
    submitted_at: str


# ── Supplier Scoring ─────────────────────────────────────────────────────────

class SupplierScoreRequest(BaseModel):
    supplier_name: str
    category: str
    request_id: Optional[str] = None
    pilot_team: Optional[str] = None


class DimensionScore(BaseModel):
    score: float
    source_chunk: str


class SupplierScoreOutput(BaseModel):
    supplier: str
    reliability: DimensionScore
    compliance: DimensionScore
    cost: DimensionScore
    risk: DimensionScore
    fit: DimensionScore
    composite: float
    status: str  # preferred | conditional | watch-list | disqualified
    prompt_version: str
    confidence: float
    input_hash: str


# ── Approval Routing ─────────────────────────────────────────────────────────

class ApprovalRoutingOutput(BaseModel):
    request_id: str
    requester: str
    value: float
    currency: str
    category: str
    policy_rule: str
    approval_chain: List[str]
    escalation_condition: Optional[str]
    sla_hours: int
    is_policy_gap: bool
    routing_confidence: float


# ── Process Finding ──────────────────────────────────────────────────────────

class ProcessFinding(BaseModel):
    finding_id: str
    workflow: str
    bottleneck: str
    root_cause_hypothesis: Optional[str]
    effort: str   # low | medium | high
    impact: str   # low | medium | high
    score: int    # 1–9
    recommended_action: Optional[str]
    status: str = "backlog"
    discovered_date: str


# ── Metrics ──────────────────────────────────────────────────────────────────

class MetricsResponse(BaseModel):
    date: str
    requests_processed: int
    supplier_scores_generated: int
    approval_decisions_made: int
    avg_approval_cycle_hours: float
    escalation_rate: float
    policy_gap_count: int
    process_findings_count: int
    agent_invocations: Dict[str, int]
    avg_confidence: float
    top_backlog_items: List[Dict[str, Any]]
    pilot_breakdown: List[Dict[str, Any]]


# ── Pilot ────────────────────────────────────────────────────────────────────

class PilotCreate(BaseModel):
    pilot_team: str
    stage: int = 1
    active_users: int = 0
    prompt_version: str


class PilotSummaryResponse(BaseModel):
    pilot_team: str
    stage: int
    active_users: int
    requests_processed: int
    routing_accuracy: float
    avg_scoring_confidence: float
    stakeholder_satisfaction: float
    open_feedback_items: int
    prompt_version: str
    blockers: List[str]
    status: str


# ── Stakeholder Feedback ─────────────────────────────────────────────────────

class FeedbackCreate(BaseModel):
    pilot_team: Optional[str] = None
    request_id: Optional[str] = None
    rating: int = Field(ge=1, le=5)
    feedback_text: Optional[str] = None
    submitted_by: Optional[str] = None


# ── Orchestrator State ───────────────────────────────────────────────────────

class OrchestratorRequest(BaseModel):
    request_type: str  # purchase_request | supplier_score | process_discovery | weekly_report
    payload: Dict[str, Any]
    pilot_team: Optional[str] = None
