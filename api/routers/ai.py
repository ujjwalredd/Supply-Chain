"""AI reasoning API router."""

import json
import logging
import os
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Order, OntologyConstraint, Supplier
from reasoning.engine import analyze_structured, compute_financial_impact, stream_analysis

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeBody(BaseModel):
    deviation_id: str
    order_id: Optional[str] = None
    deviation_type: str = "DELAY"
    severity: str = "MEDIUM"
    context: Optional[dict[str, Any]] = None


def _dict_from_row(row: object) -> dict:
    """Convert SQLAlchemy row to JSON-serializable dict (datetime -> ISO string)."""
    if row is None:
        return {}
    from datetime import date, datetime

    if hasattr(row, "_mapping"):
        data = dict(row._mapping)
    else:
        data = {k: v for k, v in getattr(row, "__dict__", {}).items() if not k.startswith("_")}
    out = {}
    for k, v in data.items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif hasattr(v, "isoformat") and callable(getattr(v, "isoformat")):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


async def _fetch_context(
    db: AsyncSession,
    order_id: Optional[str],
    deviation_id: str,
) -> tuple[dict, dict, list[dict], dict]:
    """
    Fetch order, supplier, filtered ontology constraints, and network context.

    Network context:
      co_affected_orders   — other open orders from same supplier (up to 5)
      alternate_suppliers  — higher-trust suppliers in same region (up to 3)
    """
    order_data: dict = {}
    supplier_data: dict = {}
    constraints: list[dict] = []
    network_context: dict = {}
    supplier_id: Optional[str] = None

    if order_id:
        result = await db.execute(select(Order).where(Order.order_id == order_id))
        order = result.scalar_one_or_none()
        if order:
            order_data = _dict_from_row(order)
            supplier_id = order.supplier_id

            result2 = await db.execute(
                select(Supplier).where(Supplier.supplier_id == supplier_id)
            )
            supplier = result2.scalar_one_or_none()
            if supplier:
                supplier_data = _dict_from_row(supplier)

            # Co-affected: other open orders from same supplier
            co_result = await db.execute(
                select(Order)
                .where(Order.supplier_id == supplier_id)
                .where(Order.order_id != order_id)
                .where(Order.status.not_in(["DELIVERED", "CANCELLED"]))
                .order_by(Order.expected_delivery.asc())
                .limit(5)
            )
            co_orders = [
                {
                    "order_id": o.order_id,
                    "product": o.product,
                    "order_value": o.order_value,
                    "delay_days": o.delay_days,
                    "status": o.status,
                }
                for o in co_result.scalars().all()
            ]

            # Alternates: same region, trust >= 0.75, different supplier
            alt_result = await db.execute(
                select(Supplier)
                .where(Supplier.region == order.region)
                .where(Supplier.supplier_id != supplier_id)
                .where(Supplier.trust_score >= 0.75)
                .order_by(Supplier.trust_score.desc())
                .limit(3)
            )
            alternates = [
                {
                    "supplier_id": s.supplier_id,
                    "name": s.name,
                    "trust_score": s.trust_score,
                    "avg_delay_days": s.avg_delay_days,
                }
                for s in alt_result.scalars().all()
            ]

            network_context = {
                "co_affected_orders": co_orders,
                "co_affected_count": len(co_orders),
                "alternate_suppliers": alternates,
                "current_supplier_trust": float(supplier_data.get("trust_score", 0)),
            }

    # Constraints filtered to relevant entities (global + this supplier/region/product)
    q = select(OntologyConstraint).where(
        or_(
            OntologyConstraint.entity_id == "*",
            OntologyConstraint.entity_id == (supplier_id or ""),
            OntologyConstraint.entity_id == order_data.get("region", ""),
            OntologyConstraint.entity_id == order_data.get("product", ""),
        )
    ).limit(30)
    result3 = await db.execute(q)
    for row in result3.scalars().all():
        constraints.append(_dict_from_row(row))

    return order_data, supplier_data, constraints, network_context


@router.post("/analyze/stream")
async def analyze_stream(
    body: AnalyzeBody,
    db: AsyncSession = Depends(get_db),
):
    """Stream Claude analysis token-by-token for real-time display."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="AI analysis unavailable: ANTHROPIC_API_KEY not set",
        )
    order_data, supplier_data, constraints, network_context = await _fetch_context(
        db, body.order_id, body.deviation_id
    )
    deviation = {
        "deviation_id": body.deviation_id,
        "order_id": body.order_id or "",
        "type": body.deviation_type,
        "severity": body.severity,
        "context": body.context or {},
    }
    fi = compute_financial_impact(deviation, order_data)

    def generate():
        usage: dict = {}
        start_ms = time.monotonic()
        try:
            for token in stream_analysis(
                deviation, order_data, supplier_data, constraints,
                _usage_sink=usage,
                financial_impact=fi,
                network_context=network_context,
            ):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.exception("Stream error: %s", e)
            yield f"data: {json.dumps({'token': chr(10) + chr(10) + 'Error: ' + str(e)})}\n\n"
        elapsed_ms = int((time.monotonic() - start_ms) * 1000)
        yield f"data: {json.dumps({'done': True, 'usage': {**usage, 'analysis_time_ms': elapsed_ms}, 'financial_impact_usd': fi['usd']})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _get_redis_cache():
    """Return a Redis async client for caching, or None if unavailable."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(redis_url, decode_responses=True)
        await client.ping()
        return client
    except Exception:
        return None


@router.post("/analyze", response_model=dict)
async def analyze_structured_endpoint(
    body: AnalyzeBody,
    db: AsyncSession = Depends(get_db),
):
    """Structured AI analysis with network context + computed financial impact. Cached 1h."""
    cache_key = f"ai:analysis:{body.deviation_id}:{body.deviation_type}:{body.severity}"

    redis = await _get_redis_cache()
    try:
        if redis:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    logger.info("AI cache hit for %s", body.deviation_id)
                    return json.loads(cached)
            except Exception as e:
                logger.warning("Redis cache read failed: %s", e)

        order_data, supplier_data, constraints, network_context = await _fetch_context(
            db, body.order_id, body.deviation_id
        )
        deviation = {
            "deviation_id": body.deviation_id,
            "order_id": body.order_id or "",
            "type": body.deviation_type,
            "severity": body.severity,
            "context": body.context or {},
        }
        result = analyze_structured(
            deviation, order_data, supplier_data, constraints,
            network_context=network_context,
        )
        result_dict = result.model_dump()

        if redis:
            try:
                await redis.set(cache_key, json.dumps(result_dict), ex=3600)
            except Exception as e:
                logger.warning("Redis cache write failed: %s", e)

        return result_dict
    finally:
        if redis:
            await redis.aclose()
