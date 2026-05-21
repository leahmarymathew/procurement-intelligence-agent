from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import AuditLog
from ..schemas import AuditLogEntry, AuditLogResponse

router = APIRouter()


@router.post("", response_model=AuditLogResponse, status_code=201)
async def create_audit_log(entry: AuditLogEntry, db: AsyncSession = Depends(get_db)):
    log = AuditLog(**entry.model_dump())
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return _to_response(log)


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(50, le=500),
    agent: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if agent:
        q = q.where(AuditLog.agent == agent)
    result = await db.execute(q)
    return [_to_response(r) for r in result.scalars().all()]


def _to_response(log: AuditLog) -> AuditLogResponse:
    return AuditLogResponse(
        id=log.id,
        timestamp=log.timestamp,
        agent=log.agent,
        action=log.action,
        request_id=log.request_id,
        confidence=log.confidence,
        policy_rule=log.policy_rule,
        prompt_version=log.prompt_version,
        pilot_team=log.pilot_team,
        slack_channel=log.slack_channel,
        status=log.status,
        context_payload_hash=log.context_payload_hash,
        source_agent=log.source_agent,
        target_agent=log.target_agent,
        triggering_condition=log.triggering_condition,
        created_at=log.created_at,
    )
