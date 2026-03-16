"""
Human escalation endpoints.

When the orchestrator determines that a situation requires human judgement
(3+ cross-domain agents degraded, systemic failure, etc.) it writes a row to
the `human_escalations` table via agents/state.py.  These endpoints expose
that table to the dashboard and allow operators to acknowledge + resolve alerts.

Uses synchronous psycopg2 via agents.state (same DB pool as agents).
FastAPI runs sync route handlers in a thread pool automatically.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query

from agents import state as agent_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/escalations", tags=["escalations"])


_VALID_STATUSES = {"OPEN", "RESOLVED"}


@router.get("")
def list_escalations(
    status: Optional[str] = Query(None, description="OPEN | RESOLVED"),
    limit: int = Query(50, ge=1, le=200),
):
    """List human escalations, newest first.

    Returns all OPEN escalations by default.  Pass status=RESOLVED to see
    closed ones, or omit status to see everything.
    """
    if status and status.upper() not in _VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(_VALID_STATUSES)}")
    try:
        if status:
            rows = agent_state.execute(
                """
                SELECT id, agent_id, severity, reason, context, status,
                       resolved_by, resolved_at, created_at
                FROM human_escalations
                WHERE status = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (status.upper(), limit),
                fetch=True,
            )
        else:
            rows = agent_state.execute(
                """
                SELECT id, agent_id, severity, reason, context, status,
                       resolved_by, resolved_at, created_at
                FROM human_escalations
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
                fetch=True,
            )
        if rows:
            for r in rows:
                for col in ("created_at", "resolved_at"):
                    if r.get(col):
                        r[col] = str(r[col])
        return {"escalations": rows or [], "total": len(rows or [])}
    except Exception as e:
        logger.error("list_escalations failed: %s", e)
        raise HTTPException(status_code=503, detail="Failed to query escalations")


@router.get("/{escalation_id}")
def get_escalation(escalation_id: int):
    """Get a single escalation by id."""
    try:
        rows = agent_state.execute(
            """
            SELECT id, agent_id, severity, reason, context, status,
                   resolved_by, resolved_at, created_at
            FROM human_escalations
            WHERE id = %s
            """,
            (escalation_id,),
            fetch=True,
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Escalation not found")
        r = rows[0]
        for col in ("created_at", "resolved_at"):
            if r.get(col):
                r[col] = str(r[col])
        return r
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_escalation %d failed: %s", escalation_id, e)
        raise HTTPException(status_code=503, detail="Failed to query escalation")


@router.post("/{escalation_id}/resolve", status_code=200)
def resolve_escalation(
    escalation_id: int,
    resolved_by: str = Body(..., embed=True, min_length=1, max_length=120, description="Name or ID of the operator resolving this"),
):
    """Mark an escalation as resolved.

    Sets status → RESOLVED and records who resolved it and when.
    """
    try:
        # Verify the escalation exists and is OPEN
        rows = agent_state.execute(
            "SELECT id, status FROM human_escalations WHERE id = %s",
            (escalation_id,),
            fetch=True,
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Escalation not found")
        if rows[0]["status"] != "OPEN":
            raise HTTPException(
                status_code=409,
                detail=f"Escalation is already {rows[0]['status']}",
            )
        agent_state.resolve_escalation(escalation_id, resolved_by)
        logger.info("Escalation %d resolved by %s", escalation_id, resolved_by)
        return {"ok": True, "escalation_id": escalation_id, "resolved_by": resolved_by}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("resolve_escalation %d failed: %s", escalation_id, e)
        raise HTTPException(status_code=503, detail="Failed to resolve escalation")


@router.get("/stats/summary")
def escalation_summary():
    """Return open/resolved counts and mean time-to-resolve (minutes)."""
    try:
        rows = agent_state.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'OPEN')     AS open_count,
                COUNT(*) FILTER (WHERE status = 'RESOLVED') AS resolved_count,
                AVG(
                    EXTRACT(EPOCH FROM (resolved_at - created_at)) / 60.0
                ) FILTER (WHERE status = 'RESOLVED' AND resolved_at IS NOT NULL)
                    AS avg_resolve_minutes
            FROM human_escalations
            """,
            fetch=True,
        )
        row = rows[0] if rows else {}
        return {
            "open_count": int(row.get("open_count") or 0),
            "resolved_count": int(row.get("resolved_count") or 0),
            "avg_resolve_minutes": (
                round(float(row["avg_resolve_minutes"]), 1)
                if row.get("avg_resolve_minutes") is not None
                else None
            ),
        }
    except Exception as e:
        logger.error("escalation_summary failed: %s", e)
        raise HTTPException(status_code=503, detail="Failed to summarise escalations")
