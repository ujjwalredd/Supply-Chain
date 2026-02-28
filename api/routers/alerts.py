"""Alerts (deviations) API router."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.database import get_db
from api.models import Deviation, PendingAction
from api.schemas import DeviationRead

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[DeviationRead])
async def list_alerts(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    type: Optional[str] = Query(None, description="DELAY | STOCKOUT | ANOMALY"),
    severity: Optional[str] = Query(None),
    executed: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List deviations (alerts)."""
    q = select(Deviation).order_by(Deviation.detected_at.desc()).limit(limit).offset(offset)
    if type:
        q = q.where(Deviation.type == type)
    if severity:
        q = q.where(Deviation.severity == severity)
    if executed is not None:
        q = q.where(Deviation.executed == executed)
    result = await db.execute(q)
    deviations = result.scalars().all()
    return [DeviationRead.model_validate(d) for d in deviations]


@router.get("/{deviation_id}", response_model=DeviationRead)
async def get_alert(deviation_id: str, db: AsyncSession = Depends(get_db)):
    """Get deviation by ID."""
    result = await db.execute(select(Deviation).where(Deviation.deviation_id == deviation_id))
    deviation = result.scalar_one_or_none()
    if not deviation:
        raise HTTPException(status_code=404, detail="Deviation not found")
    return DeviationRead.model_validate(deviation)


@router.post("/{deviation_id}/dismiss")
async def dismiss_alert(
    deviation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Mark deviation as executed and create a PendingAction record (Feature 4)."""
    result = await db.execute(select(Deviation).where(Deviation.deviation_id == deviation_id))
    deviation = result.scalar_one_or_none()
    if not deviation:
        raise HTTPException(status_code=404, detail="Deviation not found")
    deviation.executed = True

    # Create a pending action so the execution is tracked
    action = PendingAction(
        deviation_id=deviation_id,
        action_type="EXECUTE_RECOMMENDATION",
        description=deviation.recommended_action or "AI recommendation executed",
        payload={"deviation_type": deviation.type, "severity": deviation.severity},
        status="COMPLETED",
    )
    db.add(action)
    await db.commit()
    await db.refresh(deviation)
    return {"status": "ok", "executed": True, "action_id": action.id}
