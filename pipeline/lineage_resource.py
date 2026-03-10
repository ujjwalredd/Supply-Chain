"""
OpenLineage-compatible data lineage tracker.

Emits lineage events (run start/complete/fail) in OpenLineage format to:
  1. PostgreSQL `lineage_events` table (always)
  2. Marquez HTTP endpoint (if MARQUEZ_URL env var is set)

Usage in Dagster assets:
    from pipeline.lineage_resource import emit_lineage

    @asset(...)
    def my_asset(context):
        with emit_lineage(context, inputs=["bronze/orders"], output="silver/orders"):
            ... do work ...
            return MaterializeResult(...)
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://supplychain:supplychain_secret@localhost:5432/supply_chain_db",
)
MARQUEZ_URL = os.getenv("MARQUEZ_URL", "")  # e.g. http://marquez:5000
NAMESPACE = os.getenv("LINEAGE_NAMESPACE", "supply-chain-os")


def _ensure_table(conn) -> None:
    """Create lineage_events table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lineage_events (
            id          SERIAL PRIMARY KEY,
            run_id      TEXT NOT NULL,
            job_name    TEXT NOT NULL,
            event_type  TEXT NOT NULL,   -- START | COMPLETE | FAIL
            inputs      JSONB,
            output      TEXT,
            namespace   TEXT,
            started_at  TIMESTAMPTZ,
            ended_at    TIMESTAMPTZ,
            metadata    JSONB,
            created_at  TIMESTAMPTZ DEFAULT now()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_lineage_job_name ON lineage_events (job_name)"
    )


def _emit_to_postgres(event: dict) -> None:
    """Write a lineage event to PostgreSQL."""
    try:
        import psycopg2

        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            # Ensure table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lineage_events (
                    id          SERIAL PRIMARY KEY,
                    run_id      TEXT NOT NULL,
                    job_name    TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    inputs      TEXT,
                    output      TEXT,
                    namespace   TEXT,
                    started_at  TIMESTAMPTZ,
                    ended_at    TIMESTAMPTZ,
                    metadata    TEXT,
                    created_at  TIMESTAMPTZ DEFAULT now()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS ix_lineage_job_name
                ON lineage_events (job_name)
            """)
            cur.execute(
                """INSERT INTO lineage_events
                   (run_id, job_name, event_type, inputs, output, namespace,
                    started_at, ended_at, metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    event["run_id"],
                    event["job_name"],
                    event["event_type"],
                    json.dumps(event.get("inputs", [])),
                    event.get("output", ""),
                    event.get("namespace", NAMESPACE),
                    event.get("started_at"),
                    event.get("ended_at"),
                    json.dumps(event.get("metadata", {})),
                ),
            )
        conn.close()
    except Exception as e:
        logger.debug("Lineage PG write skipped: %s", e)


def _emit_to_marquez(event: dict) -> None:
    """POST an OpenLineage-compatible event to Marquez (if configured)."""
    if not MARQUEZ_URL:
        return
    try:
        import requests

        payload = {
            "eventType": event["event_type"],
            "eventTime": datetime.now(timezone.utc).isoformat(),
            "run": {
                "runId": event["run_id"],
                "facets": {"processing_engine": {"name": "dagster", "version": "1.x"}},
            },
            "job": {
                "namespace": event.get("namespace", NAMESPACE),
                "name": event["job_name"],
            },
            "inputs": [
                {"namespace": NAMESPACE, "name": inp}
                for inp in event.get("inputs", [])
            ],
            "outputs": (
                [{"namespace": NAMESPACE, "name": event["output"]}]
                if event.get("output")
                else []
            ),
            "producer": "supply-chain-os/dagster",
        }
        resp = requests.post(
            f"{MARQUEZ_URL}/api/v1/lineage",
            json=payload,
            timeout=3,
        )
        resp.raise_for_status()
        logger.debug("Lineage event emitted to Marquez: %s %s", event["event_type"], event["job_name"])
    except Exception as e:
        logger.debug("Marquez emit skipped: %s", e)


def emit_event(
    job_name: str,
    event_type: str,
    run_id: str,
    inputs: list[str] | None = None,
    output: str | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    metadata: dict | None = None,
) -> None:
    """Emit a lineage event to all configured sinks."""
    event = {
        "run_id": run_id,
        "job_name": job_name,
        "event_type": event_type,
        "inputs": inputs or [],
        "output": output or "",
        "namespace": NAMESPACE,
        "started_at": started_at,
        "ended_at": ended_at,
        "metadata": metadata or {},
    }
    _emit_to_postgres(event)
    _emit_to_marquez(event)


@contextmanager
def emit_lineage(
    context,
    inputs: list[str],
    output: str,
    extra_metadata: dict | None = None,
) -> Generator[None, None, None]:
    """
    Context manager for Dagster assets. Emits START on enter, COMPLETE/FAIL on exit.

    Usage:
        with emit_lineage(context, inputs=["silver/orders"], output="gold/orders_ai_ready"):
            ... compute gold layer ...
    """
    run_id = str(uuid.uuid4())
    job_name = context.asset_key.to_user_string() if hasattr(context, "asset_key") else "unknown"
    started_at = datetime.now(timezone.utc)

    emit_event(
        job_name=job_name,
        event_type="START",
        run_id=run_id,
        inputs=inputs,
        output=output,
        started_at=started_at,
        metadata=extra_metadata,
    )

    try:
        yield
        emit_event(
            job_name=job_name,
            event_type="COMPLETE",
            run_id=run_id,
            inputs=inputs,
            output=output,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
            metadata=extra_metadata,
        )
    except Exception as exc:
        emit_event(
            job_name=job_name,
            event_type="FAIL",
            run_id=run_id,
            inputs=inputs,
            output=output,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
            metadata={"error": str(exc), **(extra_metadata or {})},
        )
        raise
