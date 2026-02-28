"""Orders API router."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Order
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


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Get order by ID."""
    result = await db.execute(select(Order).where(Order.order_id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderRead.model_validate(order)
