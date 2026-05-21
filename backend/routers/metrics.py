import json
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import MetricsAggregate, PilotMetrics, ProcessBacklog, AuditLog
from ..schemas import MetricsResponse

router = APIRouter()


@router.get("", response_model=MetricsResponse)
async def get_metrics(
    metric_date: str = Query(None, description="ISO date, defaults to today"),
    db: AsyncSession = Depends(get_db),
):
    target_date = metric_date or date.today().isoformat()

    agg_result = await db.execute(
        select(MetricsAggregate).where(MetricsAggregate.metric_date == target_date)
    )
    agg = agg_result.scalar_one_or_none()

    backlog_result = await db.execute(
        select(ProcessBacklog)
        .where(ProcessBacklog.status == "backlog")
        .order_by(ProcessBacklog.score.desc())
        .limit(5)
    )
    backlog_items = backlog_result.scalars().all()

    pilot_result = await db.execute(
        select(PilotMetrics).where(PilotMetrics.status == "active")
    )
    pilots = pilot_result.scalars().all()

    return MetricsResponse(
        date=target_date,
        requests_processed=agg.requests_processed if agg else 0,
        supplier_scores_generated=agg.supplier_scores_generated if agg else 0,
        approval_decisions_made=agg.approval_decisions_made if agg else 0,
        avg_approval_cycle_hours=agg.avg_approval_cycle_hours if agg else 0.0,
        escalation_rate=agg.escalation_rate if agg else 0.0,
        policy_gap_count=agg.policy_gap_count if agg else 0,
        process_findings_count=agg.process_findings_count if agg else 0,
        agent_invocations=json.loads(agg.agent_invocations) if agg else {},
        avg_confidence=agg.avg_confidence if agg else 0.0,
        top_backlog_items=[
            {
                "finding_id": b.finding_id,
                "workflow": b.workflow,
                "bottleneck": b.bottleneck,
                "score": b.score,
                "effort": b.effort,
                "impact": b.impact,
                "recommended_action": b.recommended_action,
                "status": b.status,
                "discovered_date": b.discovered_date,
            }
            for b in backlog_items
        ],
        pilot_breakdown=[
            {
                "pilot_team": p.pilot_team,
                "stage": p.stage,
                "active_users": p.active_users,
                "requests_processed": p.requests_processed,
                "routing_accuracy": p.routing_accuracy,
                "avg_scoring_confidence": p.avg_scoring_confidence,
                "stakeholder_satisfaction": p.stakeholder_satisfaction,
                "prompt_version": p.prompt_version,
            }
            for p in pilots
        ],
    )


@router.get("/history")
async def get_metrics_history(days: int = Query(7, le=90), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MetricsAggregate).order_by(MetricsAggregate.metric_date.desc()).limit(days)
    )
    rows = result.scalars().all()
    return [
        {
            "date": r.metric_date,
            "requests_processed": r.requests_processed,
            "supplier_scores_generated": r.supplier_scores_generated,
            "approval_decisions_made": r.approval_decisions_made,
            "avg_approval_cycle_hours": r.avg_approval_cycle_hours,
            "escalation_rate": r.escalation_rate,
            "avg_confidence": r.avg_confidence,
        }
        for r in rows
    ]


@router.get("/audit-summary")
async def get_audit_summary(limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    )
    logs = result.scalars().all()
    by_agent: dict = {}
    for log in logs:
        by_agent.setdefault(log.agent, 0)
        by_agent[log.agent] += 1
    return {"total": len(logs), "by_agent": by_agent, "recent": [
        {"id": l.id, "agent": l.agent, "action": l.action,
         "status": l.status, "timestamp": l.timestamp}
        for l in logs[:10]
    ]}
