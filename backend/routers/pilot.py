import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from sqlalchemy import func
from ..models import PilotMetrics, StakeholderFeedback
from ..schemas import PilotCreate, PilotSummaryResponse, FeedbackCreate

router = APIRouter()


@router.post("", response_model=PilotSummaryResponse, status_code=201)
async def create_pilot(body: PilotCreate, db: AsyncSession = Depends(get_db)):
    pilot = PilotMetrics(**body.model_dump())
    db.add(pilot)
    await db.commit()
    await db.refresh(pilot)
    return _to_summary(pilot)


@router.get("/{pilot_team}/summary", response_model=PilotSummaryResponse)
async def get_pilot_summary(pilot_team: str, stage: int = Query(None), db: AsyncSession = Depends(get_db)):
    q = select(PilotMetrics).where(PilotMetrics.pilot_team == pilot_team)
    if stage is not None:
        q = q.where(PilotMetrics.stage == stage)
    q = q.order_by(PilotMetrics.stage.desc())
    result = await db.execute(q)
    pilot = result.scalar_one_or_none()
    if not pilot:
        raise HTTPException(status_code=404, detail="Pilot not found")
    return _to_summary(pilot)


@router.patch("/{pilot_team}/advance")
async def advance_pilot_stage(pilot_team: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PilotMetrics)
        .where(PilotMetrics.pilot_team == pilot_team, PilotMetrics.status == "active")
        .order_by(PilotMetrics.stage.desc())
    )
    current = result.scalar_one_or_none()
    if not current:
        raise HTTPException(status_code=404, detail="Active pilot not found")

    current.status = "completed"
    new_stage = PilotMetrics(
        pilot_team=pilot_team,
        stage=current.stage + 1,
        prompt_version=current.prompt_version,
        active_users=current.active_users,
    )
    db.add(new_stage)
    await db.commit()
    return {"message": f"Advanced {pilot_team} to stage {new_stage.stage}"}


@router.post("/{pilot_team}/feedback", status_code=201)
async def submit_feedback(pilot_team: str, body: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    fb = StakeholderFeedback(pilot_team=pilot_team, **body.model_dump(exclude={"pilot_team"}))
    db.add(fb)

    # Update open_feedback_items count on pilot
    result = await db.execute(
        select(PilotMetrics)
        .where(PilotMetrics.pilot_team == pilot_team, PilotMetrics.status == "active")
        .order_by(PilotMetrics.stage.desc())
    )
    pilot = result.scalar_one_or_none()
    if pilot:
        pilot.open_feedback_items += 1

        # Recompute average satisfaction from all ratings for this pilot
        avg_result = await db.execute(
            select(func.avg(StakeholderFeedback.rating)).where(
                StakeholderFeedback.pilot_team == pilot_team,
                StakeholderFeedback.rating.isnot(None),
            )
        )
        avg_rating = avg_result.scalar_one_or_none()
        if avg_rating is not None:
            pilot.stakeholder_satisfaction = round(float(avg_rating), 2)

        pilot.updated_at = datetime.utcnow().isoformat()

    await db.commit()
    return {"message": "Feedback recorded"}


@router.get("/{pilot_team}/feedback")
async def get_feedback(pilot_team: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StakeholderFeedback)
        .where(StakeholderFeedback.pilot_team == pilot_team)
        .order_by(StakeholderFeedback.id.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "rating": r.rating,
            "feedback_text": r.feedback_text,
            "submitted_by": r.submitted_by,
            "submitted_at": r.submitted_at,
        }
        for r in rows
    ]


@router.get("")
async def list_pilots(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PilotMetrics).order_by(PilotMetrics.id.desc()))
    return [_to_summary(p) for p in result.scalars().all()]


def _to_summary(p: PilotMetrics) -> PilotSummaryResponse:
    blockers = json.loads(p.blockers) if p.blockers else []
    return PilotSummaryResponse(
        pilot_team=p.pilot_team,
        stage=p.stage,
        active_users=p.active_users,
        requests_processed=p.requests_processed,
        routing_accuracy=p.routing_accuracy,
        avg_scoring_confidence=p.avg_scoring_confidence,
        stakeholder_satisfaction=p.stakeholder_satisfaction,
        open_feedback_items=p.open_feedback_items,
        prompt_version=p.prompt_version,
        blockers=blockers,
        status=p.status,
    )
