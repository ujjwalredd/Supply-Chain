"""Alerts (deviations) API router."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Deviation, Order, PendingAction
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


@router.get("/clusters")
async def deviation_clusters(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Group deviations by (type, supplier_id) to surface patterns over N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Single query: total count + critical count in one pass via conditional aggregation
    result = await db.execute(
        select(
            Deviation.type,
            Order.supplier_id,
            func.count(Deviation.deviation_id).label("count"),
            func.sum(
                case((Deviation.severity == "CRITICAL", 1), else_=0)
            ).label("critical_count"),
            func.max(Deviation.detected_at).label("last_seen"),
        )
        .join(Order, Deviation.order_id == Order.order_id)
        .where(Deviation.detected_at >= cutoff)
        .group_by(Deviation.type, Order.supplier_id)
        .order_by(func.count(Deviation.deviation_id).desc())
        .limit(50)
    )
    rows = result.all()

    clusters = []
    for row in rows:
        clusters.append({
            "type": row.type,
            "supplier_id": row.supplier_id,
            "count": row.count,
            "critical_count": int(row.critical_count or 0),
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        })

    return {"days": days, "clusters": clusters}


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
    """Mark deviation as executed and create a PendingAction record."""
    result = await db.execute(select(Deviation).where(Deviation.deviation_id == deviation_id))
    deviation = result.scalar_one_or_none()
    if not deviation:
        raise HTTPException(status_code=404, detail="Deviation not found")
    deviation.executed = True
    now = datetime.now(timezone.utc)

    action = PendingAction(
        deviation_id=deviation_id,
        action_type="DISMISSED",
        description=deviation.recommended_action or "Alert dismissed by operator",
        payload={"deviation_type": deviation.type, "severity": deviation.severity},
        status="COMPLETED",
        completed_at=now,
    )
    db.add(action)
    await db.commit()
    await db.refresh(deviation)
    return {"status": "ok", "executed": True, "action_id": action.id}
