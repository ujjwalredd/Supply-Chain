"""AI reasoning API router."""

import json
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Deviation, Order, OntologyConstraint, Supplier
from api.schemas import AIAnalysisRequest
from reasoning.engine import stream_analysis, analyze_structured

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
) -> tuple[dict, dict, list[dict]]:
    """Fetch order, supplier, and ontology constraints for AI context."""
    order_data: dict = {}
    supplier_data: dict = {}
    constraints: list[dict] = []

    if order_id:
        result = await db.execute(select(Order).where(Order.order_id == order_id))
        order = result.scalar_one_or_none()
        if order:
            order_data = _dict_from_row(order)
            supplier_id = order.supplier_id
            result2 = await db.execute(select(Supplier).where(Supplier.supplier_id == supplier_id))
            supplier = result2.scalar_one_or_none()
            if supplier:
                supplier_data = _dict_from_row(supplier)

    result3 = await db.execute(select(OntologyConstraint).limit(50))
    for row in result3.scalars().all():
        constraints.append(_dict_from_row(row))

    return order_data, supplier_data, constraints


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
    order_data, supplier_data, constraints = await _fetch_context(
        db, body.order_id, body.deviation_id
    )
    deviation = {
        "deviation_id": body.deviation_id,
        "order_id": body.order_id or "",
        "type": body.deviation_type,
        "severity": body.severity,
        "context": body.context or {},
    }

    def generate():
        try:
            for token in stream_analysis(deviation, order_data, supplier_data, constraints):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.exception("Stream error: %s", e)
            error_token = "\n\nError: " + str(e)
            yield f"data: {json.dumps({'token': error_token})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyze", response_model=dict)
async def analyze_structured_endpoint(
    body: AnalyzeBody,
    db: AsyncSession = Depends(get_db),
):
    """Get structured AI analysis (root cause, options, recommendation)."""
    order_data, supplier_data, constraints = await _fetch_context(
        db, body.order_id, body.deviation_id
    )
    deviation = {
        "deviation_id": body.deviation_id,
        "order_id": body.order_id or "",
        "type": body.deviation_type,
        "severity": body.severity,
        "context": body.context or {},
    }
    result = analyze_structured(deviation, order_data, supplier_data, constraints)
    return result.model_dump()
