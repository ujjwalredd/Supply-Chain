"""Orders API router."""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Deviation, Order, Supplier
from api.schemas import OrderRead

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[OrderRead])
async def list_orders(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    supplier_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List orders with optional filters."""
    q = select(Order).order_by(Order.created_at.desc()).limit(limit).offset(offset)
    if status:
        q = q.where(Order.status == status)
    if supplier_id:
        q = q.where(Order.supplier_id == supplier_id)
    result = await db.execute(q)
    orders = result.scalars().all()
    return [OrderRead.model_validate(o) for o in orders]


@router.get("/{order_id}/timeline")
async def order_timeline(order_id: str, db: AsyncSession = Depends(get_db)):
    """Reconstruct order lifecycle timeline from order fields and linked deviations."""
    result = await db.execute(select(Order).where(Order.order_id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    events: list[dict] = []

    # 1. Order placed
    events.append({
        "event": "ORDER_PLACED",
        "label": "Order Placed",
        "timestamp": order.created_at.isoformat(),
        "color": "blue",
        "detail": f"Value: ${order.order_value:,.0f} · Qty: {order.quantity} · Product: {order.product}",
    })

    # 2. Transit start (estimated ~10% of lead time after creation)
    if order.status in ("IN_TRANSIT", "DELIVERED", "DELAYED"):
        lead_secs = (order.expected_delivery - order.created_at).total_seconds()
        transit_ts = order.created_at.timestamp() + lead_secs * 0.10
        transit_dt = datetime.fromtimestamp(transit_ts, tz=timezone.utc)
        events.append({
            "event": "IN_TRANSIT",
            "label": "In Transit",
            "timestamp": transit_dt.isoformat(),
            "color": "blue",
            "detail": "Shipment dispatched from supplier facility",
        })

    # 3. Deviations detected
    devs_result = await db.execute(
        select(Deviation)
        .where(Deviation.order_id == order_id)
        .order_by(Deviation.detected_at.asc())
    )
    for dev in devs_result.scalars().all():
        sev_color = {"CRITICAL": "red", "HIGH": "orange", "MEDIUM": "blue"}.get(dev.severity, "gray")
        events.append({
            "event": f"DEVIATION_{dev.type}",
            "label": f"{dev.type.title()} Detected",
            "timestamp": dev.detected_at.isoformat(),
            "color": sev_color,
            "detail": f"Severity: {dev.severity} · {dev.recommended_action or 'Investigation required'}",
            "deviation_id": dev.deviation_id,
            "severity": dev.severity,
        })

    # 4. Expected delivery milestone
    events.append({
        "event": "EXPECTED_DELIVERY",
        "label": "Expected Delivery",
        "timestamp": order.expected_delivery.isoformat(),
        "color": "gray",
        "detail": f"Original SLA: {order.expected_delivery.strftime('%b %d, %Y')}",
        "is_milestone": True,
    })

    # 5. Confirmed delivery or delay
    if order.status == "DELIVERED" and order.actual_delivery:
        on_time = (order.delay_days or 0) == 0
        events.append({
            "event": "DELIVERED",
            "label": "Delivered",
            "timestamp": order.actual_delivery.isoformat(),
            "color": "green" if on_time else "orange",
            "detail": f"Delivered {order.actual_delivery.strftime('%b %d, %Y')}"
                      + (" (on time)" if on_time else f" ({order.delay_days}d late)"),
        })
    elif order.status == "DELAYED":
        events.append({
            "event": "DELAY_CONFIRMED",
            "label": "Delay Confirmed",
            "timestamp": order.expected_delivery.isoformat(),
            "color": "red",
            "detail": f"Delayed by {order.delay_days} days — currently {order.status}",
        })

    events.sort(key=lambda e: e["timestamp"])

    return {
        "order_id": order.order_id,
        "supplier_id": order.supplier_id,
        "product": order.product,
        "status": order.status,
        "order_value": order.order_value,
        "delay_days": order.delay_days,
        "region": order.region,
        "events": events,
    }


@router.get("/delay-predictions")
async def delay_predictions(
    limit: int = Query(20, ge=1, le=100),
    min_probability: float = Query(0.3, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Proactive delay scoring for orders not yet delivered.
    Scores = weighted combination of supplier trust, avg_delay_days, lead_time_remaining.
    Returns orders sorted by delay probability descending.
    """
    now = datetime.now(timezone.utc)

    # Fetch up to 5× the requested limit so scoring has enough candidates
    # after min_probability filtering; capped at 500 to prevent full-table scans.
    fetch_limit = min(limit * 5, 500)
    result = await db.execute(
        select(Order, Supplier)
        .join(Supplier, Order.supplier_id == Supplier.supplier_id, isouter=True)
        .where(Order.status.not_in(["DELIVERED", "CANCELLED"]))
        .where(Order.expected_delivery.isnot(None))
        .limit(fetch_limit)
    )
    rows = result.all()

    predictions = []
    for order, supplier in rows:
        if order.expected_delivery is None:
            continue

        # Lead time remaining in days — normalise to UTC-aware datetime
        exp_dt = order.expected_delivery
        if not isinstance(exp_dt, datetime):
            # date object (no time component) — treat as UTC midnight
            exp_dt = datetime(exp_dt.year, exp_dt.month, exp_dt.day, tzinfo=timezone.utc)
        elif exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        days_remaining = (exp_dt - now).days

        # Already overdue
        is_overdue = days_remaining < 0

        # Base delay probability from supplier trust score
        trust = float(supplier.trust_score) if supplier else 0.7
        p_base = max(0.05, min(0.95, 1.0 - trust))

        # Amplify if supplier has high avg delay
        avg_delay = float(supplier.avg_delay_days) if supplier and supplier.avg_delay_days else 0
        delay_factor = min(2.0, 1.0 + avg_delay / 14.0)

        # Urgency factor: orders due soon are higher risk
        if is_overdue:
            urgency = 2.0
        elif days_remaining <= 3:
            urgency = 1.5
        elif days_remaining <= 7:
            urgency = 1.2
        else:
            urgency = 1.0

        p_delay = min(0.99, p_base * delay_factor * urgency)

        if p_delay < min_probability:
            continue

        predictions.append({
            "order_id": order.order_id,
            "supplier_id": order.supplier_id,
            "supplier_name": supplier.name if supplier else order.supplier_id,
            "product": order.product,
            "order_value": float(order.order_value or 0),
            "status": order.status,
            "expected_delivery": order.expected_delivery.isoformat() if order.expected_delivery else None,
            "days_remaining": days_remaining,
            "is_overdue": is_overdue,
            "delay_probability": round(p_delay, 3),
            "risk_level": "CRITICAL" if p_delay >= 0.75 else "HIGH" if p_delay >= 0.5 else "MEDIUM",
            "supplier_trust": round(trust, 3),
            "supplier_avg_delay_days": round(avg_delay, 1),
        })

    # Sort by delay probability desc
    predictions.sort(key=lambda x: x["delay_probability"], reverse=True)
    return {"predictions": predictions[:limit], "total_scored": len(rows)}


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Get order by ID."""
    result = await db.execute(select(Order).where(Order.order_id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderRead.model_validate(order)
