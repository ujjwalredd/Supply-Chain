"""Suppliers API router."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Deviation, Order, Supplier
from api.schemas import SupplierRead, SupplierRisk

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[SupplierRead])
async def list_suppliers(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    region: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List suppliers."""
    q = select(Supplier).order_by(Supplier.trust_score.desc()).limit(limit).offset(offset)
    if region:
        q = q.where(Supplier.region == region)
    result = await db.execute(q)
    suppliers = result.scalars().all()
    return [SupplierRead.model_validate(s) for s in suppliers]


@router.get("/risk", response_model=list[SupplierRisk])
async def list_supplier_risk(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List suppliers by risk — trust score, delay rate, and single-product dependency %."""
    result = await db.execute(
        select(Supplier).order_by(Supplier.trust_score.asc()).limit(limit)
    )
    suppliers = result.scalars().all()

    dep_result = await db.execute(
        select(
            Order.supplier_id,
            Order.product,
            func.count().label("cnt"),
        ).group_by(Order.supplier_id, Order.product)
    )
    dep_map: dict[str, dict[str, int]] = {}
    for row in dep_result.all():
        dep_map.setdefault(row.supplier_id, {})[row.product] = row.cnt

    total_per_product: dict[str, int] = {}
    for prod_counts in dep_map.values():
        for prod, cnt in prod_counts.items():
            total_per_product[prod] = total_per_product.get(prod, 0) + cnt

    risks = []
    for s in suppliers:
        prod_counts = dep_map.get(s.supplier_id, {})
        if prod_counts and total_per_product:
            max_dep = max(
                cnt / total_per_product.get(prod, max(cnt, 1)) * 100
                for prod, cnt in prod_counts.items()
            )
        else:
            max_dep = 0.0
        max_dep = round(max_dep, 1)
        concentration = "HIGH" if max_dep >= 70 else ("MEDIUM" if max_dep >= 40 else "LOW")

        risks.append(SupplierRisk(
            supplier_id=s.supplier_id,
            name=s.name,
            region=s.region,
            trust_score=s.trust_score,
            total_orders=s.total_orders,
            delayed_orders=s.delayed_orders,
            delay_rate_pct=(s.delayed_orders / s.total_orders * 100) if s.total_orders > 0 else 0,
            max_product_dependency_pct=max_dep,
            concentration_risk=concentration,
        ))
    return risks


@router.get("/{supplier_id}/scorecard")
async def supplier_scorecard(
    supplier_id: str,
    weeks: int = Query(12, ge=4, le=52),
    db: AsyncSession = Depends(get_db),
):
    """Weekly performance metrics for a supplier over the last N weeks."""
    result = await db.execute(select(Supplier).where(Supplier.supplier_id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    orders_result = await db.execute(
        select(Order)
        .where(Order.supplier_id == supplier_id)
        .order_by(Order.created_at.asc())
    )
    orders = orders_result.scalars().all()

    devs_result = await db.execute(
        select(Deviation)
        .join(Order, Deviation.order_id == Order.order_id)
        .where(Order.supplier_id == supplier_id)
        .order_by(Deviation.detected_at.asc())
    )
    deviations = devs_result.scalars().all()

    today = datetime.now(timezone.utc).date()
    weekly_data = []
    for w in range(weeks - 1, -1, -1):
        week_end = today - timedelta(weeks=w)
        week_start = week_end - timedelta(days=6)

        week_orders = [
            o for o in orders
            if week_start <= o.created_at.date() <= week_end
        ]
        total = len(week_orders)
        delayed = sum(1 for o in week_orders if (o.delay_days or 0) > 0)
        on_time_pct = round((total - delayed) / total * 100, 1) if total > 0 else None
        avg_delay = round(
            sum(o.delay_days or 0 for o in week_orders) / total, 1
        ) if total > 0 else 0.0

        dev_count = sum(
            1 for d in deviations
            if week_start <= d.detected_at.date() <= week_end
        )

        weekly_data.append({
            "week": week_end.isoformat(),
            "total_orders": total,
            "on_time_pct": on_time_pct,
            "avg_delay_days": avg_delay,
            "deviation_count": dev_count,
        })

    return {
        "supplier": {
            "supplier_id": supplier.supplier_id,
            "name": supplier.name,
            "region": supplier.region,
            "trust_score": supplier.trust_score,
            "total_orders": supplier.total_orders,
            "delayed_orders": supplier.delayed_orders,
            "avg_delay_days": supplier.avg_delay_days,
            "delay_rate_pct": round(
                supplier.delayed_orders / supplier.total_orders * 100, 1
            ) if supplier.total_orders > 0 else 0.0,
        },
        "weeks": weekly_data,
    }


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(supplier_id: str, db: AsyncSession = Depends(get_db)):
    """Get supplier by ID."""
    result = await db.execute(select(Supplier).where(Supplier.supplier_id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return SupplierRead.model_validate(supplier)
