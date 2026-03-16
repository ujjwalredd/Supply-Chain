"""
Database Health Agent
Model: Claude Haiku (only on anomaly)
Interval: 60s

Monitors:
- Active connections count
- Long-running queries (>30s)
- Pending actions queue depth
- Table sizes
- Index usage
"""
import os
import time
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

from agents.base import BaseAgent, HAIKU_MODEL

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/supplychain")

MAX_CONNECTIONS_WARN = int(os.getenv("DB_MAX_CONNECTIONS_WARN", "80"))
LONG_QUERY_THRESHOLD_SEC = int(os.getenv("DB_LONG_QUERY_SEC", "30"))
MAX_PENDING_ACTIONS_WARN = int(os.getenv("MAX_PENDING_ACTIONS_WARN", "50"))


class DatabaseHealthAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="database_health",
            model=HAIKU_MODEL,
            interval_seconds=60,
            description="Monitors PostgreSQL health: connections, long queries, table sizes."
        )

    def check(self) -> dict:
        metrics = {}
        conn = None  # Bug 8/33: initialize before try so finally can safely guard on it

        try:
            conn = psycopg2.connect(DATABASE_URL)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:

                # 1. Active connections
                cur.execute("SELECT count(*) as cnt FROM pg_stat_activity WHERE state != 'idle'")
                active_conn = cur.fetchone()["cnt"]
                metrics["active_connections"] = active_conn

                if active_conn > MAX_CONNECTIONS_WARN:
                    self.alert("HIGH", f"High DB connections: {active_conn} active",
                               {"active_connections": active_conn})

                # 2. Long-running queries
                cur.execute("""
                    SELECT pid, now() - query_start as duration, query, state
                    FROM pg_stat_activity
                    WHERE state != 'idle'
                      AND query_start IS NOT NULL
                      AND EXTRACT(EPOCH FROM (now() - query_start)) > %s
                    ORDER BY duration DESC
                """, (LONG_QUERY_THRESHOLD_SEC,))
                long_queries = [dict(r) for r in cur.fetchall()]
                metrics["long_running_queries"] = len(long_queries)

                if long_queries:
                    logger.warning(f"{len(long_queries)} long-running queries detected")
                    for q in long_queries[:3]:
                        logger.warning(f"  PID={q['pid']} duration={q['duration']} query={str(q['query'])[:100]}")
                    self.alert("MEDIUM", f"{len(long_queries)} queries running >{LONG_QUERY_THRESHOLD_SEC}s",
                               {"queries": [{"pid": q["pid"],
                                             "duration_sec": q["duration"].total_seconds()}  # Bug 24: float seconds, consistent with other agents
                                            for q in long_queries[:5]]})

                # 3. Blocked queries
                cur.execute("""
                    SELECT count(*) as cnt FROM pg_stat_activity
                    WHERE wait_event_type = 'Lock'
                """)
                blocked = cur.fetchone()["cnt"]
                metrics["blocked_queries"] = blocked
                if blocked > 0:
                    self.alert("HIGH", f"{blocked} queries blocked by locks", {"blocked": blocked})

                # 4. Pending actions queue depth
                cur.execute("SELECT count(*) as cnt FROM pending_actions WHERE status='PENDING'")
                pending = cur.fetchone()["cnt"]
                metrics["pending_actions_queue"] = pending
                if pending > MAX_PENDING_ACTIONS_WARN:
                    self.alert("MEDIUM", f"Large pending actions queue: {pending} items",
                               {"pending_actions": pending})

                # 5. Table sizes (top 5)
                cur.execute("""
                    SELECT relname as table_name,
                           pg_size_pretty(pg_total_relation_size(relid)) as size,
                           n_live_tup as row_count
                    FROM pg_stat_user_tables
                    ORDER BY pg_total_relation_size(relid) DESC
                    LIMIT 5
                """)
                tables = [dict(r) for r in cur.fetchall()]
                metrics["top_tables"] = [{"table": t["table_name"], "size": t["size"],
                                          "rows": t["row_count"]} for t in tables]

                # 6. Sequential scans on large tables (index issue indicator)
                cur.execute("""
                    SELECT relname, seq_scan, idx_scan
                    FROM pg_stat_user_tables
                    WHERE seq_scan > COALESCE(idx_scan, 0) * 10
                      AND n_live_tup > 10000
                    ORDER BY seq_scan DESC
                    LIMIT 3
                """)
                seq_scan_heavy = [dict(r) for r in cur.fetchall()]
                if seq_scan_heavy:
                    logger.info(f"Tables with high seq_scan ratio: {[t['relname'] for t in seq_scan_heavy]}")

        finally:
            if conn:  # Bug 8/33: guard so a failed connect() doesn't cause NameError
                conn.close()

        metrics["task"] = f"conns={metrics.get('active_connections',0)}|long_q={metrics.get('long_running_queries',0)}|pending={metrics.get('pending_actions_queue',0)}"
        return metrics

    def heal(self, error: Exception) -> bool:
        if "connection" in str(error).lower() or "timeout" in str(error).lower():
            logger.warning("DB health agent: connection error, waiting 15s")
            time.sleep(15)
            return True
        return False
