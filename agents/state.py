"""
Agent state management — PostgreSQL persistence layer.
All writes are idempotent. Connection failures retry with backoff.
"""
import os
import time
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool as pg_pool

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/supplychain")

_pool: Optional[pg_pool.SimpleConnectionPool] = None

def _get_pool() -> pg_pool.SimpleConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        retries = 0
        while retries < 10:
            try:
                _pool = pg_pool.SimpleConnectionPool(1, 5, DATABASE_URL)
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
            applied BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

def write_correction(from_agent: str, to_agent: str, message: str):
    execute("""
        INSERT INTO agent_corrections (from_agent, to_agent, message)
        VALUES (%s, %s, %s)
    """, (from_agent, to_agent, message))

def get_pending_corrections(agent_id: str):
    rows = execute("""
        SELECT id, message FROM agent_corrections
        WHERE to_agent = %s AND applied = FALSE
        ORDER BY created_at ASC
    """, (agent_id,), fetch=True)
    if rows:
        ids = [r['id'] for r in rows]
        execute(f"UPDATE agent_corrections SET applied = TRUE WHERE id = ANY(%s)", (ids,))
    return [r['message'] for r in (rows or [])]
