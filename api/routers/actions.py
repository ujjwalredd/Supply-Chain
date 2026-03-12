"""Feature 4: Pending actions router — queue and complete AI-recommended actions."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, join as sql_join, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Deviation, Order, PendingAction
from api.schemas import PendingActionCreate, PendingActionRead

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats")
async def actions_stats(
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Look-back window for MTTR calculation"),
):
    """MTTR: avg time (minutes) from deviation detection to action completion within the window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    j = sql_join(PendingAction, Deviation, PendingAction.deviation_id == Deviation.deviation_id)
    result = await db.execute(
        select(
            func.count().label("total"),
            func.avg(
                func.extract("epoch", PendingAction.created_at - Deviation.detected_at)
            ).label("avg_resolve_seconds"),
        )
        .select_from(j)
        .where(PendingAction.status == "COMPLETED")
        .where(PendingAction.created_at >= cutoff)
    )
    row = result.one()
    avg_secs = float(row.avg_resolve_seconds or 0)
    return {
        "total_completed": int(row.total or 0),
        "mttr_minutes": round(avg_secs / 60, 1),
        "window_days": days,
    }


@router.get("/audit")
async def actions_audit(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Enriched audit log: every action with linked deviation + order context."""
    j = sql_join(
        PendingAction,
        Deviation,
        PendingAction.deviation_id == Deviation.deviation_id,
        isouter=True,
    )
    j2 = sql_join(j, Order, Deviation.order_id == Order.order_id, isouter=True)

    result = await db.execute(
        select(
            PendingAction.id,
            PendingAction.action_type,
            PendingAction.description,
            PendingAction.status,
            PendingAction.created_at,
            PendingAction.completed_at,
            PendingAction.resolved,
            PendingAction.outcome_note,
            PendingAction.resolved_at,
            Deviation.deviation_id,
            Deviation.type.label("deviation_type"),
            Deviation.severity,
            Order.order_id,
            Order.supplier_id,
            Order.order_value,
            Order.product,
        )
        .select_from(j2)
        .order_by(PendingAction.created_at.desc())
        .limit(limit)
    )

    rows = []
    for row in result.all():
        rows.append({
            "id": row.id,
            "action_type": row.action_type,
            "description": row.description,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "resolved": row.resolved,
            "outcome_note": row.outcome_note,
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            "deviation_id": row.deviation_id,
            "deviation_type": row.deviation_type,
            "severity": row.severity,
            "order_id": row.order_id,
            "supplier_id": row.supplier_id,
            "order_value": float(row.order_value) if row.order_value else None,
            "product": row.product,
        })
    return rows


@router.get("", response_model=list[PendingActionRead])
async def list_actions(
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = Query(None, description="PENDING | COMPLETED | CANCELLED"),
    db: AsyncSession = Depends(get_db),
):
    """List pending actions."""
    q = select(PendingAction).order_by(PendingAction.created_at.desc()).limit(limit)
    if status:
        q = q.where(PendingAction.status == status)
    result = await db.execute(q)
    return [PendingActionRead.model_validate(a) for a in result.scalars().all()]


@router.post("", response_model=PendingActionRead, status_code=201)
async def create_action(
    body: PendingActionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new pending action."""
    action = PendingAction(
        deviation_id=body.deviation_id,
        action_type=body.action_type,
        description=body.description,
        payload=body.payload,
        status="PENDING",
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return PendingActionRead.model_validate(action)


@router.post("/{action_id}/complete", response_model=PendingActionRead)
async def complete_action(action_id: int, db: AsyncSession = Depends(get_db)):
    """Mark an action as completed."""
    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    action.status = "COMPLETED"
    action.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(action)
    return PendingActionRead.model_validate(action)


@router.post("/{action_id}/cancel", response_model=PendingActionRead)
async def cancel_action(action_id: int, db: AsyncSession = Depends(get_db)):
    """Cancel a pending action."""
    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    action.status = "CANCELLED"
    await db.commit()
    await db.refresh(action)
    return PendingActionRead.model_validate(action)


@router.post("/{action_id}/resolve")
async def resolve_action(
    action_id: int,
    outcome_note: str = Body(..., embed=True),
    success: bool = Body(True, embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Mark an action as resolved with an outcome note. Used for feedback loop tracking."""
    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    action.resolved = True
    action.outcome_note = outcome_note
    action.resolved_at = datetime.now(timezone.utc)
    # If success=False, mark as FAILED so it shows distinctly
    if not success and action.status == "EXECUTED":
        action.status = "FAILED"
    await db.commit()
    return {"ok": True, "action_id": action_id, "resolved": True}


@router.get("/success-rates")
async def action_success_rates(db: AsyncSession = Depends(get_db)):
    """Return success rate per action type based on resolved outcomes."""
    result = await db.execute(
        select(
            PendingAction.action_type,
            func.count().label("total"),
            func.sum(case((PendingAction.resolved == True, 1), else_=0)).label("resolved_count"),
            func.sum(case((and_(PendingAction.resolved == True, PendingAction.status != "FAILED"), 1), else_=0)).label("success_count"),
            func.avg(PendingAction.confidence).label("avg_confidence"),
        )
        .group_by(PendingAction.action_type)
        .order_by(func.count().desc())
    )
    rows = result.all()
    rates = []
    for r in rows:
        success_rate = (r.success_count / r.resolved_count * 100) if r.resolved_count > 0 else None
        rates.append({
            "action_type": r.action_type,
            "total": r.total,
            "resolved_count": r.resolved_count,
            "success_count": r.success_count,
            "success_rate_pct": round(success_rate, 1) if success_rate is not None else None,
            "avg_confidence": round(float(r.avg_confidence or 0), 3),
        })
    return {"success_rates": rates}
