"""Alerts (deviations) API router."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.get("/trend")
async def deviation_trend(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Deviation counts per day for the last N days, grouped by severity."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(Deviation.detected_at).label("day"),
            Deviation.severity,
            func.count().label("count"),
        )
        .where(Deviation.detected_at >= cutoff)
        .group_by(func.date(Deviation.detected_at), Deviation.severity)
        .order_by(func.date(Deviation.detected_at))
    )
    rows = result.all()

    today = datetime.now(timezone.utc).date()
    date_range = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    data: dict[str, dict] = {
        d: {"date": d, "CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "total": 0}
        for d in date_range
    }
    for row in rows:
        day_str = str(row.day)
        if day_str in data:
            sev = row.severity if row.severity in ("CRITICAL", "HIGH", "MEDIUM") else "MEDIUM"
            data[day_str][sev] += row.count
            data[day_str]["total"] += row.count
    return list(data.values())


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
