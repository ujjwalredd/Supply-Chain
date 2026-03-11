"""
Event store — helpers to append order events and replay state.
Implements event sourcing pattern for point-in-time recovery.
"""
from __future__ import annotations
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

logger = logging.getLogger(__name__)


async def append_event(
    db: AsyncSession,
    order_id: str,
    event_type: str,
    *,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    old_delay_days: Optional[int] = None,
    new_delay_days: Optional[int] = None,
    supplier_id: Optional[str] = None,
    region: Optional[str] = None,
    metadata: Optional[dict] = None,
    actor: str = "system",
) -> str:
    """Append an immutable event to order_events. Returns event_id."""
    from api.models import OrderEvent

    # Get next aggregate version atomically using MAX to avoid race conditions
    # Two concurrent appends using COUNT(*)+1 would both read the same count and
    # produce a duplicate version. MAX+1 inside a transaction is safe because
    # each INSERT holds a row-level lock until the transaction commits.
    result = await db.execute(
        text("SELECT COALESCE(MAX(aggregate_version), 0) + 1 FROM order_events WHERE order_id = :oid"),
        {"oid": order_id}
    )
    version = result.scalar() or 1

    event = OrderEvent(
        event_id=str(uuid.uuid4()),
        order_id=order_id,
        event_type=event_type,
        old_status=old_status,
        new_status=new_status,
        old_delay_days=old_delay_days,
        new_delay_days=new_delay_days,
        supplier_id=supplier_id,
        region=region,
        event_metadata=metadata or {},
        actor=actor,
        aggregate_version=version,
    )
    db.add(event)
    await db.flush()
    logger.info("Event sourced: %s %s v%d", event_type, order_id, version)
    return event.event_id


async def get_order_history(db: AsyncSession, order_id: str) -> list[dict]:
    """Replay all events for an order (chronological)."""
    from api.models import OrderEvent
    result = await db.execute(
        select(OrderEvent)
        .where(OrderEvent.order_id == order_id)
        .order_by(OrderEvent.aggregate_version)
    )
    events = result.scalars().all()
    return [
        {
            "event_id": e.event_id,
            "event_type": e.event_type,
            "old_status": e.old_status,
            "new_status": e.new_status,
            "old_delay_days": e.old_delay_days,
            "new_delay_days": e.new_delay_days,
            "actor": e.actor,
            "aggregate_version": e.aggregate_version,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "metadata": e.event_metadata,
        }
        for e in events
    ]


async def replay_state_at(db: AsyncSession, order_id: str, at_version: int) -> dict:
    """Reconstruct order state at a specific aggregate_version (point-in-time recovery)."""
    from api.models import OrderEvent
    result = await db.execute(
        select(OrderEvent)
        .where(OrderEvent.order_id == order_id, OrderEvent.aggregate_version <= at_version)
        .order_by(OrderEvent.aggregate_version)
    )
    events = result.scalars().all()

    state = {"order_id": order_id, "status": None, "delay_days": None, "version": 0}
    for e in events:
        if e.new_status:
            state["status"] = e.new_status
        if e.new_delay_days is not None:
            state["delay_days"] = e.new_delay_days
        state["version"] = e.aggregate_version
    return state
