"""
Data lineage endpoints — query the lineage_events table.
"""

from __future__ import annotations

import json
from typing import Any

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db

router = APIRouter(prefix="/lineage", tags=["lineage"])


@router.get("")
async def get_lineage(
    job_name: str | None = Query(None, description="Filter by asset/job name"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return recent lineage events from the lineage_events table."""
    try:
        # Check table exists
        exists = await db.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'lineage_events')"
        ))
        if not exists.scalar():
            return {"events": [], "total": 0, "note": "lineage_events table not yet created"}

        if job_name:
            result = await db.execute(
                text(
                    "SELECT run_id, job_name, event_type, inputs, output, namespace, "
                    "started_at, ended_at, metadata, created_at "
                    "FROM lineage_events WHERE job_name = :job ORDER BY created_at DESC "
                    "LIMIT :limit OFFSET :offset"
                ),
                {"job": job_name, "limit": limit, "offset": offset},
            )
        else:
            result = await db.execute(
                text(
                    "SELECT run_id, job_name, event_type, inputs, output, namespace, "
                    "started_at, ended_at, metadata, created_at "
                    "FROM lineage_events ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                ),
                {"limit": limit, "offset": offset},
            )

        rows = result.mappings().all()
        events = [dict(r) for r in rows]

        # Convert datetimes to ISO strings
        for e in events:
            for key in ("started_at", "ended_at", "created_at"):
                if e.get(key) is not None:
                    e[key] = str(e[key])

        # Build a simple lineage graph: edges from input → job → output
        graph: dict[str, Any] = {"nodes": {}, "edges": []}
        seen_edges: set[tuple[str, str]] = set()
        for e in events:
            if e.get("event_type") != "COMPLETE":
                continue
            job = e["job_name"]
            graph["nodes"][job] = {"type": "job"}
            try:
                inputs = json.loads(e.get("inputs") or "[]")
            except Exception:
                inputs = []
            for inp in inputs:
                graph["nodes"][inp] = {"type": "dataset"}
                edge = (inp, job)
                if edge not in seen_edges:
                    graph["edges"].append({"from": inp, "to": job})
                    seen_edges.add(edge)
            if e.get("output"):
                out = e["output"]
                graph["nodes"][out] = {"type": "dataset"}
                edge = (job, out)
                if edge not in seen_edges:
                    graph["edges"].append({"from": job, "to": out})
                    seen_edges.add(edge)

        return {
            "events": events,
            "total": len(events),
            "graph": {
                "nodes": [{"id": k, **v} for k, v in graph["nodes"].items()],
                "edges": graph["edges"],
            },
        }
    except Exception as e:
        logger.error("Lineage query failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Lineage query failed: {e}")


@router.get("/jobs")
async def get_lineage_jobs(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return unique job names with last run status."""
    try:
        result = await db.execute(text("""
            SELECT DISTINCT ON (job_name)
                job_name, event_type as last_status, created_at as last_run
            FROM lineage_events
            ORDER BY job_name, created_at DESC
        """))
        rows = result.mappings().all()
        return {"jobs": [dict(r) for r in rows]}
    except Exception as e:
        logger.error("Lineage jobs query failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Lineage jobs query failed: {e}")
