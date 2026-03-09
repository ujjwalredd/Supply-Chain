"""Feature 4: Pending actions router — queue and complete AI-recommended actions."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, join as sql_join, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Deviation, PendingAction
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
