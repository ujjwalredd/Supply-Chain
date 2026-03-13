"""
Natural language query endpoint — ask questions about your supply chain in plain English.

POST /ai/query  — streams Claude's answer with live data context injected.
"""

import json
import logging
import os
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import Deviation, Order, Supplier

logger = logging.getLogger(__name__)

router = APIRouter()

SUGGESTED_QUESTIONS = [
    "Which suppliers are at highest risk this week?",
    "What are my most critical delayed orders?",
    "Which orders should I expedite right now?",
    "Which region has the worst on-time delivery rate?",
    "Are any suppliers approaching single-source dependency risk?",
]


class QueryBody(BaseModel):
    question: str


@router.get("/suggestions")
async def query_suggestions():
    """Return suggested natural language questions."""
    return {"suggestions": SUGGESTED_QUESTIONS}


@router.post("/stream")
async def query_stream(
    body: QueryBody,
    db: AsyncSession = Depends(get_db),
):
    """Stream an answer to a natural language supply chain question."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="AI query unavailable: ANTHROPIC_API_KEY not set",
        )

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")
    if len(question) > 2000:
        raise HTTPException(status_code=400, detail="question must not exceed 2000 characters")

    # ── Pull a live data snapshot ────────────────────────────────────────────
    # Active deviations (limit 15)
    dev_result = await db.execute(
        select(Deviation)
        .where(Deviation.executed == False)  # noqa: E712
        .order_by(Deviation.detected_at.desc())
        .limit(15)
    )
    deviations = [
        {
            "deviation_id": d.deviation_id,
            "order_id": d.order_id,
            "type": d.type,
            "severity": d.severity,
            "detected_at": d.detected_at.isoformat() if d.detected_at else None,
            "recommended_action": d.recommended_action,
        }
        for d in dev_result.scalars().all()
    ]

    # Suppliers ordered by trust score asc (riskiest first)
    sup_result = await db.execute(
        select(Supplier).order_by(Supplier.trust_score.asc()).limit(10)
    )
    suppliers = [
        {
            "supplier_id": s.supplier_id,
            "name": s.name,
            "region": s.region,
            "trust_score": round(s.trust_score, 3),
            "total_orders": s.total_orders,
            "delayed_orders": s.delayed_orders,
            "delay_rate_pct": round(
                (s.delayed_orders / s.total_orders * 100) if s.total_orders else 0, 1
            ),
            "avg_delay_days": round(s.avg_delay_days, 1),
        }
        for s in sup_result.scalars().all()
    ]

    # Recent delayed orders (limit 10)
    ord_result = await db.execute(
        select(Order)
        .where(Order.delay_days > 0)
        .order_by(Order.delay_days.desc())
        .limit(10)
    )
    delayed_orders = [
        {
            "order_id": o.order_id,
            "supplier_id": o.supplier_id,
            "product": o.product,
            "region": o.region,
            "order_value": o.order_value,
            "delay_days": o.delay_days,
            "status": o.status,
        }
        for o in ord_result.scalars().all()
    ]

    # Build context block
    context_str = json.dumps(
        {
            "active_deviations": deviations,
            "suppliers_by_risk": suppliers,
            "most_delayed_orders": delayed_orders,
        },
        indent=2,
    )

    system = (
        "You are an expert supply chain analyst answering questions about a live supply chain control tower. "
        "You have access to real-time data: active deviations, supplier trust scores, and delayed orders. "
        "Answer in concise, professional prose. No emojis. No markdown headers. "
        "Lead with the most actionable insight. Cite specific order IDs, supplier IDs, or numbers when relevant."
    )

    prompt = (
        f"Question: {question}\n\n"
        f"Live supply chain data:\n{context_str}\n\n"
        "Answer the question using only the data above. Be specific and direct."
    )

    def generate():
        from anthropic import Anthropic, APIConnectionError, APIStatusError

        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        start_ms = time.monotonic()
        usage: dict = {}
        try:
            with client.messages.stream(
                model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
                max_tokens=600,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for token in stream.text_stream:
                    yield f"data: {json.dumps({'token': token})}\n\n"
                try:
                    final = stream.get_final_message()
                    usage = {
                        "input_tokens": final.usage.input_tokens,
                        "output_tokens": final.usage.output_tokens,
                    }
                except Exception as e:
                    logger.debug("Could not extract final usage tokens: %s", e)
        except (APIConnectionError, APIStatusError) as e:
            yield f"data: {json.dumps({'token': f'Error: {e}'})}\n\n"
        elapsed_ms = int((time.monotonic() - start_ms) * 1000)
        yield f"data: {json.dumps({'done': True, 'usage': {**usage, 'analysis_time_ms': elapsed_ms}})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
