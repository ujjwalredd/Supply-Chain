"""Suppliers API router."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Supplier
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
    """List suppliers by risk (trust score, delay rate)."""
    result = await db.execute(
        select(Supplier).order_by(Supplier.trust_score.asc()).limit(limit)
    )
    suppliers = result.scalars().all()
    return [
        SupplierRisk(
            supplier_id=s.supplier_id,
            name=s.name,
            region=s.region,
            trust_score=s.trust_score,
            total_orders=s.total_orders,
            delayed_orders=s.delayed_orders,
            delay_rate_pct=(s.delayed_orders / s.total_orders * 100) if s.total_orders > 0 else 0,
        )
        for s in suppliers
    ]


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(supplier_id: str, db: AsyncSession = Depends(get_db)):
    """Get supplier by ID."""
    result = await db.execute(select(Supplier).where(Supplier.supplier_id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return SupplierRead.model_validate(supplier)
