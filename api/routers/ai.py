"""AI reasoning API router."""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Deviation, OntologyConstraint, Order, Supplier
from reasoning.engine import (
    analyze_structured,
    analyze_with_quality_scoring,
    compute_financial_impact,
    stream_analysis,
    stream_bulk_triage,
    stream_whatif,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ── In-process rate limiter for AI endpoints ──────────────────────────────────
# Configurable via AI_RATE_LIMIT_PER_MIN env var (default: 30 req/min/IP).
# For multi-worker deployments, swap this for Redis-backed fastapi-limiter.
_AI_RATE_LIMIT_STORE: dict[str, list[float]] = defaultdict(list)
_AI_RATE_WINDOW = 60.0
_AI_RATE_MAX = int(os.getenv("AI_RATE_LIMIT_PER_MIN", "30"))


def _check_ai_rate_limit(client_ip: str) -> bool:
    """Return True if within rate limit, False if exceeded."""
    now = time.monotonic()
    cutoff = now - _AI_RATE_WINDOW
    calls = _AI_RATE_LIMIT_STORE[client_ip]
    calls[:] = [t for t in calls if t > cutoff]
    if len(calls) >= _AI_RATE_MAX:
        return False
    calls.append(now)
    return True

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class AnalyzeBody(BaseModel):
    deviation_id: str
    order_id: Optional[str] = None
    deviation_type: str = "DELAY"
    severity: str = "MEDIUM"
    context: Optional[dict[str, Any]] = None


class BulkAnalyzeBody(BaseModel):
    severity_filter: str = "CRITICAL"
    limit: int = 10
    include_executed: bool = False


class WhatIfBody(BaseModel):
    supplier_id: str
    volume_shift_pct: float = 30.0
    target_supplier_id: Optional[str] = None
    product: Optional[str] = None


def _dict_from_row(row: object) -> dict:
    from datetime import date, datetime
    if row is None:
        return {}
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


async def _get_redis_cache():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(redis_url, decode_responses=True)
        await client.ping()
        return client
    except Exception:
        return None


@router.post("/analyze/stream")
async def analyze_stream(
    body: AnalyzeBody,
    db: AsyncSession = Depends(get_db),
):
    """Stream Claude analysis token-by-token for real-time display."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="AI analysis unavailable: ANTHROPIC_API_KEY not set")
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

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/analyze/bulk")
async def analyze_bulk_stream(
    body: BulkAnalyzeBody,
    db: AsyncSession = Depends(get_db),
):
    """Stream a prioritized triage analysis of all open deviations matching severity_filter."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not set")

    q = select(Deviation).where(Deviation.severity == body.severity_filter)
    if not body.include_executed:
        q = q.where(Deviation.executed == False)  # noqa: E712
    q = q.order_by(Deviation.detected_at.desc()).limit(body.limit)
    result = await db.execute(q)
    deviations = result.scalars().all()

    dev_summaries = []
    for dev in deviations:
        order_data, supplier_data, _, _ = await _fetch_context(db, dev.order_id, dev.deviation_id)
        dev_summaries.append({
            "deviation_id": dev.deviation_id,
            "order_id": dev.order_id,
            "type": dev.type,
            "severity": dev.severity,
            "order_value": order_data.get("order_value", 0),
            "supplier": supplier_data.get("name", dev.order_id or "unknown"),
            "recommended_action": dev.recommended_action or "TBD",
        })

    if not dev_summaries:
        async def empty_gen():
            yield f"data: {json.dumps({'token': f'No open {body.severity_filter} deviations found.'})}\n\n"
            yield f"data: {json.dumps({'done': True, 'usage': {}, 'count': 0})}\n\n"
        return StreamingResponse(empty_gen(), media_type="text/event-stream", headers=_SSE_HEADERS)

    def generate():
        usage: dict = {}
        start_ms = time.monotonic()
        try:
            for token in stream_bulk_triage(dev_summaries, _usage_sink=usage):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.exception("Bulk triage error: %s", e)
            err_msg = "\n\nError: " + str(e)
            yield f"data: {json.dumps({'token': err_msg})}\n\n"
        elapsed_ms = int((time.monotonic() - start_ms) * 1000)
        yield f"data: {json.dumps({'done': True, 'usage': {**usage, 'analysis_time_ms': elapsed_ms}, 'count': len(dev_summaries)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/whatif/stream")
async def whatif_stream(
    body: WhatIfBody,
    db: AsyncSession = Depends(get_db),
):
    """Stream Claude's analysis of a volume shift what-if scenario."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not set")

    result = await db.execute(select(Supplier).where(Supplier.supplier_id == body.supplier_id))
    supplier_from = result.scalar_one_or_none()
    if not supplier_from:
        raise HTTPException(status_code=404, detail="Source supplier not found")

    supplier_to = None
    if body.target_supplier_id:
        result2 = await db.execute(
            select(Supplier).where(Supplier.supplier_id == body.target_supplier_id)
        )
        supplier_to = result2.scalar_one_or_none()

    # Get constraints (global + supplier-specific)
    result3 = await db.execute(
        select(OntologyConstraint).where(
            or_(
                OntologyConstraint.entity_id == "*",
                OntologyConstraint.entity_id == body.supplier_id,
                OntologyConstraint.entity_id == (body.target_supplier_id or ""),
            )
        ).limit(20)
    )
    constraints = [_dict_from_row(c) for c in result3.scalars().all()]

    # Compute current order volume for this supplier
    vol_result = await db.execute(
        select(
            Order.product,
            func.count().label("order_count"),
            func.sum(Order.order_value).label("total_value"),
        )
        .where(Order.supplier_id == body.supplier_id)
        .group_by(Order.product)
        .order_by(func.count().desc())
        .limit(5)
    )
    product_breakdown = [
        {"product": r.product, "orders": r.order_count, "total_value": float(r.total_value or 0)}
        for r in vol_result.all()
    ]

    scenario = {
        "source_supplier_id": body.supplier_id,
        "target_supplier_id": body.target_supplier_id or "best available",
        "volume_shift_pct": body.volume_shift_pct,
        "product_filter": body.product or "all products",
        "product_breakdown_top5": product_breakdown,
    }

    supplier_from_dict = _dict_from_row(supplier_from)
    supplier_to_dict = _dict_from_row(supplier_to) if supplier_to else None

    def generate():
        usage: dict = {}
        start_ms = time.monotonic()
        try:
            for token in stream_whatif(
                scenario,
                supplier_from_dict,
                supplier_to_dict,
                constraints,
                _usage_sink=usage,
            ):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.exception("What-if error: %s", e)
            err_msg = "\n\nError: " + str(e)
            yield f"data: {json.dumps({'token': err_msg})}\n\n"
        elapsed_ms = int((time.monotonic() - start_ms) * 1000)
        yield f"data: {json.dumps({'done': True, 'usage': {**usage, 'analysis_time_ms': elapsed_ms}})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/analyze", response_model=dict)
async def analyze_structured_endpoint(
    body: AnalyzeBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Structured AI analysis with network context + computed financial impact. Cached 1h."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_ai_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {_AI_RATE_MAX} requests/minute per IP",
        )

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
        # analyze_structured is a blocking sync call (Claude API, 5-30s).
        # Run in thread pool to avoid blocking the async event loop.
        result = await asyncio.to_thread(
            analyze_structured,
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
            try:
                await asyncio.wait_for(redis.aclose(), timeout=1.0)
            except Exception:
                pass


class ScoredAnalyzeBody(BaseModel):
    prompt: str
    system: Optional[str] = None
    deviation_id: str = ""
    max_tokens: int = 1024


@router.post("/analyze-scored", response_model=dict)
async def analyze_scored_endpoint(body: ScoredAnalyzeBody):
    """
    Multi-model AI analysis with quality scoring and GPT-4o fallback.

    Calls Claude (primary) and scores the response quality on a 0.0–1.0 scale.
    If quality < 0.4 and OPENAI_API_KEY is set, falls back to GPT-4o.

    Returns:
        response (str): The AI-generated analysis text.
        model_used (str): Which model produced the final response.
        quality_score (float): Heuristic quality score 0.0–1.0.
        latency_ms (float): Time taken for the winning model call.
        fallback_used (bool): True if GPT-4o was used instead of Claude.
    """
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="AI analysis unavailable: neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set",
        )

    system = body.system or (
        "You are an expert supply chain analyst. Analyze the given information and provide "
        "clear, actionable recommendations. Write in plain prose with no markdown headers or emojis."
    )

    # analyze_with_quality_scoring is a blocking sync call (Claude + optional GPT-4o).
    # Run in thread pool to avoid blocking the async event loop.
    result = await asyncio.to_thread(
        analyze_with_quality_scoring,
        prompt=body.prompt,
        system=system,
        deviation_id=body.deviation_id,
        max_tokens=body.max_tokens,
    )
    return result
