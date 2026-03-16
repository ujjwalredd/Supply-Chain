"""
Agent state management — PostgreSQL persistence layer.
All writes are idempotent. Connection failures retry with backoff.

Tables managed here:
  agent_heartbeats       — live agent health (upserted every cycle)
  agent_audit_log        — mutable audit log (legacy, kept for compatibility)
  agent_audit_log_v2     — immutable hash-chained audit log (SHA-256)
  agent_corrections      — signed orchestrator corrections (HMAC-verified)
  human_escalations      — corrections that need a human to act
  decision_provenance    — full reasoning chain for each AI decision
  correction_outcomes    — effectiveness measured 15 min after correction
  data_classifications   — per-column data sensitivity labels
"""
import os
import time
import json
import logging
import hashlib
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool as pg_pool

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/supplychain")

_pool: Optional[pg_pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()  # Bug 15: guard pool init against race condition

def _get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool
    # Bug 15: use lock to guard pool initialization against race condition
    with _pool_lock:
        if _pool is None or _pool.closed:
            retries = 0
            while retries < 10:
                try:
                    _pool = pg_pool.ThreadedConnectionPool(1, 5, DATABASE_URL)
                    logger.info("Agent state DB pool created")
                    return _pool
                except Exception as e:
                    retries += 1
                    wait = min(2 ** retries, 30)
                    logger.warning(f"DB pool creation failed (attempt {retries}): {e}. Retrying in {wait}s")
                    time.sleep(wait)
            raise RuntimeError("Could not connect to PostgreSQL after 10 retries")
        return _pool

def execute(query: str, params=None, fetch=False):
    """Execute a query with automatic connection retry."""
    pool = _get_pool()
    conn = None
    for attempt in range(3):
        try:
            conn = pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch:
                    result = cur.fetchall()
                    conn.commit()
                    return [dict(r) for r in result]
                conn.commit()
                return None
        except psycopg2.OperationalError as e:
            logger.warning(f"DB execute attempt {attempt+1} failed: {e}")
            if conn:
                try:
                    pool.putconn(conn, close=True)
                except:
                    pass
                conn = None
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                try:
                    pool.putconn(conn)
                except:
                    pass

def ensure_tables():
    """Create agent tables if they don't exist (idempotent)."""
    execute("""
        CREATE TABLE IF NOT EXISTS agent_heartbeats (
            agent_id VARCHAR(60) PRIMARY KEY,
            status VARCHAR(20) NOT NULL DEFAULT 'STARTING',
            last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            current_task TEXT,
            metrics JSONB DEFAULT '{}',
            error_count INTEGER DEFAULT 0,
            last_error TEXT,
            model VARCHAR(80),
            uptime_seconds INTEGER DEFAULT 0
        )
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS agent_audit_log (
            id SERIAL PRIMARY KEY,
            agent_id VARCHAR(60) NOT NULL,
            action VARCHAR(120) NOT NULL,
            reasoning TEXT,
            outcome VARCHAR(20),
            details JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS agent_corrections (
            id SERIAL PRIMARY KEY,
            from_agent VARCHAR(60) NOT NULL,
            to_agent VARCHAR(60) NOT NULL,
            message TEXT NOT NULL,
            signature TEXT NOT NULL DEFAULT '',
            applied BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # Idempotent migration: add signature column to pre-existing tables
    execute("""
        ALTER TABLE agent_corrections
            ADD COLUMN IF NOT EXISTS signature TEXT NOT NULL DEFAULT ''
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS agent_audit_log_v2 (
            id BIGSERIAL PRIMARY KEY,
            agent_id VARCHAR(60) NOT NULL,
            action VARCHAR(120) NOT NULL,
            reasoning TEXT,
            outcome VARCHAR(20),
            details JSONB DEFAULT '{}',
            prev_hash CHAR(64) NOT NULL DEFAULT '0000000000000000000000000000000000000000000000000000000000000000',
            row_hash CHAR(64) NOT NULL,
            prompt_hash CHAR(64) DEFAULT '',
            model_version VARCHAR(80) DEFAULT '',
            confidence FLOAT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS human_escalations (
            id SERIAL PRIMARY KEY,
            agent_id VARCHAR(60) NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'HIGH',
            reason TEXT NOT NULL,
            context JSONB DEFAULT '{}',
            status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
            resolved_by VARCHAR(120),
            resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS decision_provenance (
            id SERIAL PRIMARY KEY,
            decision_id VARCHAR(80) NOT NULL,
            agent_id VARCHAR(60) NOT NULL,
            trigger_event TEXT,
            data_sources JSONB DEFAULT '[]',
            llm_prompt_hash CHAR(64) DEFAULT '',
            llm_response_hash CHAR(64) DEFAULT '',
            confidence FLOAT,
            outcome_action TEXT,
            correction_id INTEGER REFERENCES agent_corrections(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS correction_outcomes (
            id SERIAL PRIMARY KEY,
            correction_id INTEGER NOT NULL,
            from_agent VARCHAR(60) NOT NULL,
            to_agent VARCHAR(60) NOT NULL,
            correction_message TEXT NOT NULL,
            measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            agent_status_before VARCHAR(20),
            agent_status_after VARCHAR(20),
            effective BOOLEAN,
            notes TEXT
        )
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS data_classifications (
            id SERIAL PRIMARY KEY,
            table_name VARCHAR(120) NOT NULL,
            column_name VARCHAR(120) NOT NULL,
            classification VARCHAR(20) NOT NULL DEFAULT 'INTERNAL',
            pii BOOLEAN NOT NULL DEFAULT FALSE,
            retention_days INTEGER,
            last_reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (table_name, column_name)
        )
    """)
    logger.info("Agent tables ensured")

def write_heartbeat(agent_id: str, status: str, current_task: str = None,
                    metrics: Dict[str, Any] = None, error_count: int = 0,
                    last_error: str = None, model: str = None, uptime_seconds: int = 0):
    execute("""
        INSERT INTO agent_heartbeats (agent_id, status, last_seen, current_task, metrics, error_count, last_error, model, uptime_seconds)
        VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s)
        ON CONFLICT (agent_id) DO UPDATE SET
            status = EXCLUDED.status,
            last_seen = NOW(),
            current_task = EXCLUDED.current_task,
            metrics = EXCLUDED.metrics,
            error_count = EXCLUDED.error_count,
            last_error = EXCLUDED.last_error,
            model = EXCLUDED.model,
            uptime_seconds = EXCLUDED.uptime_seconds
    """, (agent_id, status, current_task, json.dumps(metrics or {}),
          error_count, last_error, model, uptime_seconds))

def get_all_heartbeats():
    return execute("SELECT * FROM agent_heartbeats ORDER BY last_seen DESC", fetch=True)

def write_audit(agent_id: str, action: str, reasoning: str = None,
                outcome: str = "SUCCESS", details: Dict[str, Any] = None):
    execute("""
        INSERT INTO agent_audit_log (agent_id, action, reasoning, outcome, details)
        VALUES (%s, %s, %s, %s, %s)
    """, (agent_id, action, reasoning, outcome, json.dumps(details or {})))


def get_recent_audit(limit: int = 20) -> List[Dict[str, Any]]:
    """Return the most recent agent_audit_log entries (used by orchestrator tools)."""
    limit = min(int(limit), 50)
    rows = execute("""
        SELECT agent_id, action, reasoning, outcome, details, created_at
        FROM agent_audit_log
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,), fetch=True)
    if rows:
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])
    return rows or []


def write_audit_immutable(
    agent_id: str,
    action: str,
    reasoning: str = None,
    outcome: str = "SUCCESS",
    details: Dict[str, Any] = None,
    prompt_hash: str = "",
    model_version: str = "",
    confidence: float = None,
):
    """Write to the immutable hash-chained audit log (agent_audit_log_v2).

    Each row stores:
    - prev_hash: the row_hash of the previous row (genesis = 64 zeros)
    - row_hash:  SHA-256 of (agent_id|action|reasoning|outcome|details|ts|prev_hash)

    Uses a single connection + transaction so the prev_hash fetch and the insert
    are atomic — preventing hash-chain gaps under concurrent writes.
    """
    pool = _get_pool()
    conn = None
    try:
        conn = pool.getconn()
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Acquire an advisory lock so concurrent writers serialize the
            # prev_hash fetch + insert atomically across all connections.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('audit_chain'))")
            # Fetch the most recent row_hash
            cur.execute(
                "SELECT row_hash FROM agent_audit_log_v2 "
                "ORDER BY id DESC LIMIT 1"
            )
            last = cur.fetchone()
            prev_hash = last["row_hash"] if last else "0" * 64

            ts = datetime.now(timezone.utc).isoformat()
            content = (
                f"{agent_id}|{action}|{reasoning or ''}|{outcome}|"
                f"{json.dumps(details or {})}|{ts}|{prev_hash}"
            )
            row_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

            cur.execute(
                """
                INSERT INTO agent_audit_log_v2
                    (agent_id, action, reasoning, outcome, details,
                     prev_hash, row_hash, prompt_hash, model_version, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    agent_id, action, reasoning, outcome,
                    json.dumps(details or {}),
                    prev_hash, row_hash,
                    prompt_hash or "", model_version or "", confidence,
                ),
            )
        conn.commit()
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error("write_audit_immutable failed: %s", e)
    finally:
        if conn:
            try:
                conn.autocommit = True
                pool.putconn(conn)
            except Exception:
                pass

def write_correction(from_agent: str, to_agent: str, message: str, signature: str = ""):
    """Write a correction to the DB. Pass signature from security.sign_correction()."""
    execute("""
        INSERT INTO agent_corrections (from_agent, to_agent, message, signature)
        VALUES (%s, %s, %s, %s)
    """, (from_agent, to_agent, message, signature))


def get_pending_corrections(agent_id: str) -> List[str]:
    """Return pending correction messages (strings) for the given agent.

    This is the backwards-compatible interface used by BaseAgent.check_for_corrections().
    Signature verification is done in base.py via get_pending_corrections_raw().
    """
    rows = execute("""
        SELECT id, message FROM agent_corrections
        WHERE to_agent = %s AND applied = FALSE
        ORDER BY created_at ASC
    """, (agent_id,), fetch=True)
    if rows:
        ids = [r['id'] for r in rows]
        # Bug 1: ANY(%s) is not valid psycopg2 parameterized SQL; use UNNEST instead
        execute("UPDATE agent_corrections SET applied = TRUE WHERE id = ANY(SELECT UNNEST(%s::int[]))", (ids,))
    return [r['message'] for r in (rows or [])]


def get_pending_corrections_raw(agent_id: str) -> List[Dict[str, Any]]:
    """Return pending corrections as dicts with id, message, and signature.

    Used by BaseAgent.check_for_corrections() for HMAC verification before applying.
    Marks corrections as applied in the same DB roundtrip.
    """
    rows = execute("""
        SELECT id, message, signature FROM agent_corrections
        WHERE to_agent = %s AND applied = FALSE
        ORDER BY created_at ASC
    """, (agent_id,), fetch=True)
    if rows:
        ids = [r['id'] for r in rows]
        execute(
            "UPDATE agent_corrections SET applied = TRUE "
            "WHERE id = ANY(SELECT UNNEST(%s::int[]))",
            (ids,),
        )
    return rows or []


# ── Human escalation functions ────────────────────────────────────────────────

def write_escalation(
    agent_id: str,
    reason: str,
    severity: str = "HIGH",
    context: Dict[str, Any] = None,
) -> Optional[int]:
    """Create a new human escalation record. Returns the new row id."""
    rows = execute("""
        INSERT INTO human_escalations (agent_id, severity, reason, context)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (agent_id, severity, reason, json.dumps(context or {})), fetch=True)
    if rows:
        return rows[0]["id"]
    return None


def get_open_escalations() -> List[Dict[str, Any]]:
    rows = execute("""
        SELECT id, agent_id, severity, reason, context, status, created_at
        FROM human_escalations
        WHERE status = 'OPEN'
        ORDER BY created_at DESC
    """, fetch=True)
    if rows:
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])
    return rows or []


def resolve_escalation(escalation_id: int, resolved_by: str):
    execute("""
        UPDATE human_escalations
        SET status = 'RESOLVED', resolved_by = %s, resolved_at = NOW()
        WHERE id = %s
    """, (resolved_by, escalation_id))


# ── Decision provenance ───────────────────────────────────────────────────────

def write_provenance(
    decision_id: str,
    agent_id: str,
    trigger_event: str = None,
    data_sources: List[str] = None,
    llm_prompt_hash: str = "",
    llm_response_hash: str = "",
    confidence: float = None,
    outcome_action: str = None,
    correction_id: int = None,
):
    execute("""
        INSERT INTO decision_provenance
            (decision_id, agent_id, trigger_event, data_sources,
             llm_prompt_hash, llm_response_hash, confidence,
             outcome_action, correction_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        decision_id, agent_id, trigger_event,
        json.dumps(data_sources or []),
        llm_prompt_hash or "", llm_response_hash or "",
        confidence, outcome_action, correction_id,
    ))


# ── Correction outcome tracking ───────────────────────────────────────────────

def write_correction_outcome(
    correction_id: int,
    from_agent: str,
    to_agent: str,
    correction_message: str,
    agent_status_before: str = None,
    agent_status_after: str = None,
    effective: bool = None,
    notes: str = None,
):
    execute("""
        INSERT INTO correction_outcomes
            (correction_id, from_agent, to_agent, correction_message,
             agent_status_before, agent_status_after, effective, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        correction_id, from_agent, to_agent, correction_message,
        agent_status_before, agent_status_after, effective, notes,
    ))


# ── Data classification ───────────────────────────────────────────────────────

def upsert_data_classification(
    table_name: str,
    column_name: str,
    classification: str = "INTERNAL",
    pii: bool = False,
    retention_days: int = None,
):
    """Upsert a data classification label for a column.

    classification must be one of: PUBLIC, INTERNAL, CONFIDENTIAL, PII.
    """
    execute("""
        INSERT INTO data_classifications
            (table_name, column_name, classification, pii, retention_days, last_reviewed_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (table_name, column_name) DO UPDATE SET
            classification = EXCLUDED.classification,
            pii = EXCLUDED.pii,
            retention_days = EXCLUDED.retention_days,
            last_reviewed_at = NOW()
    """, (table_name, column_name, classification, pii, retention_days))
