import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db, AsyncSessionLocal
from ..models import PurchaseRequest, SupplierScore, ApprovalDecision
from ..schemas import (
    PurchaseRequestCreate, PurchaseRequestResponse,
    SupplierScoreRequest, OrchestratorRequest,
)

router = APIRouter()


@router.post("/request", response_model=PurchaseRequestResponse, status_code=201)
async def submit_purchase_request(
    req: PurchaseRequestCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    request_id = f"PR-{uuid.uuid4().hex[:8].upper()}"
    pr = PurchaseRequest(request_id=request_id, **req.model_dump())
    db.add(pr)
    await db.commit()
    await db.refresh(pr)

    orch_req = OrchestratorRequest(
        request_type="purchase_request",
        payload={**req.model_dump(), "request_id": request_id},
        pilot_team=req.pilot_team,
    )
    background_tasks.add_task(_run_orch_in_new_session, orch_req)

    return PurchaseRequestResponse(
        request_id=pr.request_id,
        requester=pr.requester,
        supplier_name=pr.supplier_name,
        category=pr.category,
        value=pr.value,
        currency=pr.currency,
        description=pr.description,
        pilot_team=pr.pilot_team,
        status=pr.status,
        submitted_at=pr.submitted_at,
    )


@router.get("/request/{request_id}")
async def get_request_status(request_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PurchaseRequest).where(PurchaseRequest.request_id == request_id)
    )
    pr = result.scalar_one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Request not found")

    decision_result = await db.execute(
        select(ApprovalDecision).where(ApprovalDecision.request_id == request_id)
    )
    decision = decision_result.scalar_one_or_none()

    score_result = await db.execute(
        select(SupplierScore)
        .where(SupplierScore.request_id == request_id)
        .order_by(SupplierScore.id.desc())
    )
    score = score_result.scalar_one_or_none()

    import json
    return {
        "request_id": pr.request_id,
        "requester": pr.requester,
        "supplier_name": pr.supplier_name,
        "category": pr.category,
        "value": pr.value,
        "currency": pr.currency,
        "status": pr.status,
        "submitted_at": pr.submitted_at,
        "approval_decision": {
            "policy_rule_id": decision.policy_rule_id,
            "approval_chain": json.loads(decision.approval_chain),
            "sla_hours": decision.sla_hours,
            "is_policy_gap": bool(decision.is_policy_gap),
            "status": decision.status,
        } if decision else None,
        "supplier_score": {
            "composite": score.composite_score,
            "status": score.status,
            "confidence": score.confidence,
        } if score else None,
    }


@router.post("/supplier/score", status_code=202)
async def score_supplier(
    req: SupplierScoreRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    orch_req = OrchestratorRequest(
        request_type="supplier_score",
        payload=req.model_dump(),
        pilot_team=req.pilot_team,
    )
    background_tasks.add_task(_run_orch_in_new_session, orch_req)
    return {"status": "accepted", "supplier_name": req.supplier_name, "category": req.category}


@router.post("/process-discovery")
async def trigger_process_discovery(
    background_tasks: BackgroundTasks,
    pilot_team: str = Query(None),
):
    orch_req = OrchestratorRequest(
        request_type="process_discovery",
        payload={"trigger": "on_demand"},
        pilot_team=pilot_team,
    )
    background_tasks.add_task(_run_orch_in_new_session, orch_req)
    return {"message": "Process discovery triggered", "pilot_team": pilot_team}


@router.post("/weekly-report")
async def generate_weekly_report(
    background_tasks: BackgroundTasks,
    pilot_team: str = Query(None),
):
    orch_req = OrchestratorRequest(
        request_type="weekly_report",
        payload={"trigger": "manual"},
        pilot_team=pilot_team,
    )
    background_tasks.add_task(_run_orch_in_new_session, orch_req)
    return {"message": "Weekly report generation triggered", "pilot_team": pilot_team}


async def _run_orch_in_new_session(orch_req: OrchestratorRequest):
    from ..agents.orchestrator import run_orchestrator
    try:
        await run_orchestrator(orch_req)
    except Exception as exc:
        print(f"[orchestrator-background] error: {exc}")
