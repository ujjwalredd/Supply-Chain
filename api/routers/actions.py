"""Feature 4: Pending actions router — queue and complete AI-recommended actions."""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import PendingAction
from api.schemas import PendingActionCreate, PendingActionRead

logger = logging.getLogger(__name__)

router = APIRouter()


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
