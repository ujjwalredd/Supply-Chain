"""Order event sourcing endpoints."""
from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from api.database import get_db
from api.event_store import get_order_history, replay_state_at

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["events"])


@router.get("/orders/{order_id}/history")
async def get_event_history(
    order_id: str,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return event history for an order (event sourcing audit trail)."""
    try:
        history = await get_order_history(db, order_id, limit=limit, offset=offset)
        return {"order_id": order_id, "events": history, "total": len(history), "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning("get_event_history: order_id=%s error: %s", order_id, e)
        raise HTTPException(status_code=500, detail="Failed to retrieve event history")


@router.get("/orders/{order_id}/replay")
async def replay_order_state(
    order_id: str,
    version: int = Query(..., description="Aggregate version to replay to"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Point-in-time recovery: reconstruct order state at a specific version."""
    try:
        state = await replay_state_at(db, order_id, version)
        return {"order_id": order_id, "state_at_version": version, "state": state}
    except Exception as e:
        logger.warning("replay_order_state: order_id=%s version=%s error: %s", order_id, version, e)
        raise HTTPException(status_code=500, detail="Failed to replay order state")


@router.get("/recent")
async def get_recent_events(
    limit: int = Query(50, le=200),
    event_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return recent order events across all orders."""
    try:
        # Check table exists
        exists = await db.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'order_events')"
        ))
        if not exists.scalar():
            return {"events": [], "total": 0, "note": "order_events table not yet created"}

        if event_type:
            result = await db.execute(
                text("SELECT * FROM order_events WHERE event_type = :et ORDER BY created_at DESC LIMIT :lim"),
                {"et": event_type, "lim": limit}
            )
        else:
            result = await db.execute(
                text("SELECT * FROM order_events ORDER BY created_at DESC LIMIT :lim"),
                {"lim": limit}
            )
        rows = result.mappings().all()
        events = []
        for r in rows:
            e = dict(r)
            for k in ("created_at",):
                if e.get(k):
                    e[k] = str(e[k])
            events.append(e)
        return {"events": events, "total": len(events)}
    except Exception as e:
        logger.warning("get_recent_events error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve recent events")
