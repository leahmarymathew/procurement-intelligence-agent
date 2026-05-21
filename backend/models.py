from datetime import datetime
from sqlalchemy import Integer, String, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class MigrationLog(Base):
    __tablename__ = "migration_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    executed_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())
    executed_by: Mapped[str] = mapped_column(String, default="system")


class PromptRegistry(Base):
    __tablename__ = "prompt_registry"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    agent_type: Mapped[str] = mapped_column(String, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    registered_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())


class PolicyRule(Base):
    __tablename__ = "policy_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    min_value: Mapped[float] = mapped_column(Float, default=0)
    max_value: Mapped[float] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String, default="USD")
    approver_level_1: Mapped[str] = mapped_column(String, nullable=False)
    approver_level_2: Mapped[str] = mapped_column(String, nullable=True)
    approver_level_3: Mapped[str] = mapped_column(String, nullable=True)
    dual_approval_required: Mapped[int] = mapped_column(Integer, default=0)
    escalation_condition: Mapped[str] = mapped_column(Text, nullable=True)
    sla_hours: Mapped[int] = mapped_column(Integer, default=24)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    requester: Mapped[str] = mapped_column(String, nullable=False)
    supplier_name: Mapped[str] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="USD")
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    pilot_team: Mapped[str] = mapped_column(String, nullable=True)
    submitted_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    policy_rule_id: Mapped[str] = mapped_column(String, nullable=True)
    approval_chain: Mapped[str] = mapped_column(Text, default="[]")
    escalation_condition: Mapped[str] = mapped_column(Text, nullable=True)
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    routing_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    is_policy_gap: Mapped[int] = mapped_column(Integer, default=0)
    decided_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())


class SupplierScore(Base):
    __tablename__ = "supplier_scores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String, nullable=False)
    request_id: Mapped[str] = mapped_column(String, nullable=True)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=True)
    compliance_score: Mapped[float] = mapped_column(Float, nullable=True)
    cost_score: Mapped[float] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=True)
    fit_score: Mapped[float] = mapped_column(Float, nullable=True)
    composite_score: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=True)
    source_chunks: Mapped[str] = mapped_column(Text, default="{}")
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    scored_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())


class ProcessBacklog(Base):
    __tablename__ = "process_backlog"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finding_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    workflow: Mapped[str] = mapped_column(String, nullable=False)
    bottleneck: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_hypothesis: Mapped[str] = mapped_column(Text, nullable=True)
    effort: Mapped[str] = mapped_column(String, nullable=False)
    impact: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="backlog")
    discovered_date: Mapped[str] = mapped_column(String, nullable=False)
    pilot_team: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[str] = mapped_column(String, nullable=False)
    agent: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    request_id: Mapped[str] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    policy_rule: Mapped[str] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String, nullable=True)
    pilot_team: Mapped[str] = mapped_column(String, nullable=True)
    slack_channel: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=True)
    context_payload_hash: Mapped[str] = mapped_column(String, nullable=True)
    source_agent: Mapped[str] = mapped_column(String, nullable=True)
    target_agent: Mapped[str] = mapped_column(String, nullable=True)
    triggering_condition: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())


class MetricsAggregate(Base):
    __tablename__ = "metrics_aggregate"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_date: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    requests_processed: Mapped[int] = mapped_column(Integer, default=0)
    supplier_scores_generated: Mapped[int] = mapped_column(Integer, default=0)
    approval_decisions_made: Mapped[int] = mapped_column(Integer, default=0)
    avg_approval_cycle_hours: Mapped[float] = mapped_column(Float, default=0)
    escalation_rate: Mapped[float] = mapped_column(Float, default=0)
    policy_gap_count: Mapped[int] = mapped_column(Integer, default=0)
    process_findings_count: Mapped[int] = mapped_column(Integer, default=0)
    agent_invocations: Mapped[str] = mapped_column(Text, default="{}")
    avg_confidence: Mapped[float] = mapped_column(Float, default=0)
    updated_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())


class PilotMetrics(Base):
    __tablename__ = "pilot_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pilot_team: Mapped[str] = mapped_column(String, nullable=False)
    stage: Mapped[int] = mapped_column(Integer, default=1)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    requests_processed: Mapped[int] = mapped_column(Integer, default=0)
    routing_accuracy: Mapped[float] = mapped_column(Float, default=0)
    avg_scoring_confidence: Mapped[float] = mapped_column(Float, default=0)
    stakeholder_satisfaction: Mapped[float] = mapped_column(Float, default=0)
    open_feedback_items: Mapped[int] = mapped_column(Integer, default=0)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    blockers: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String, default="active")
    started_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())


class StakeholderFeedback(Base):
    __tablename__ = "stakeholder_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pilot_team: Mapped[str] = mapped_column(String, nullable=True)
    request_id: Mapped[str] = mapped_column(String, nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=True)
    feedback_text: Mapped[str] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[str] = mapped_column(String, nullable=True)
    submitted_at: Mapped[str] = mapped_column(String, default=lambda: datetime.utcnow().isoformat())
