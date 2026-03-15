# Supply Chain AI OS — Incident Pattern Memory

## Purpose
Persistent memory of recurring failure patterns observed across orchestration cycles.
The orchestrator loads this file at startup and appends new patterns after resolution.
Each pattern is a condensed case study: what happened, root cause, and what fixed it.

---

## Pattern Library

### P001 — Dagster Webserver Port Mismatch
**Symptoms**: dagster_guardian DEGRADED, consecutive connection refused errors
**Root cause**: DAGSTER_WEBSERVER_URL env var pointed to host port (3001) instead of container port (3000)
**Resolution**: Corrected docker-compose.yml to use http://dagster-webserver:3000
**Agents affected**: dagster_guardian → cascades to bronze_agent, silver_agent, gold_agent (all show "missing files" because pipeline never ran)
**Correction issued**: `trigger full pipeline` after env var was fixed

---

### P002 — Computed Features Path Never Found
**Symptoms**: feature_engineer heartbeat shows `no_gold_file` despite gold data existing
**Root cause**: Gold parquet files are at `/data/gold/orders_ai_ready/data.parquet` — f.name is `data.parquet`, not the parent directory name. Code was checking `"ai_ready" in f.name` which always failed.
**Resolution**: Changed to `"ai_ready" in str(f)` (full path check)
**Agents affected**: feature_engineer → computed_features never written → gold_delay_model trains without engineered features → lower roc_auc

---

### P003 — Silver Orders File Never Detected
**Symptoms**: silver_agent reports no orders found despite silver parquet existing
**Root cause**: Same f.name vs str(f) bug — silver orders are at `/data/silver/orders/data.parquet`, f.name = `data.parquet`
**Resolution**: Changed to `"orders" in str(f)`
**Agents affected**: silver_agent → false healthy status, gold validation blind

---

### P004 — ML Model Not Retraining on Incremental Run
**Symptoms**: `medallion_incremental` runs succeed but MLflow shows no new runs, model not improving
**Root cause**: `medallion_incremental` job selection only included bronze_orders, silver_orders, gold_orders_ai_ready — NOT gold_delay_model
**Resolution**: Added `gold_delay_model` to incremental job selection in jobs_medallion.py
**Agents affected**: mlflow_guardian sees stale model, triggers unnecessary full retrain

---

### P005 — PostgreSQL Connection Pool Exhaustion
**Symptoms**: database_health shows high connection count (>80), ai_quality_monitor shows stuck pending_actions
**Root cause**: Multiple agents all opening persistent connections without pooling
**Resolution**: Reduce max_connections in PostgreSQL config, add connection timeouts
**When to escalate**: If connections >90 and growing, alert CRITICAL + human_intervention_needed=True

---

### P006 — Kafka DLQ Growing
**Symptoms**: kafka_guardian heartbeat shows dlq > 0 and growing
**Root cause**: Schema Registry incompatibility — producer sending messages with new field not in schema
**Resolution**: Update Schema Registry compatibility mode to BACKWARD_TRANSITIVE
**When to alert**: dlq > 10 → HIGH alert; dlq > 50 → CRITICAL

---

### P007 — All Medallion Agents Report Missing Files After Fresh Start
**Symptoms**: bronze_agent + silver_agent + gold_agent all show file_missing immediately after container restart
**Root cause**: Normal startup — parquet files don't exist until first Dagster pipeline run completes (~150-180s)
**Resolution**: No action needed if within startup window (first 3 minutes). After 3 min, issue `trigger full pipeline` to dagster_guardian
**Do NOT alert**: During startup window

---

### P008 — MLflow Baseline Drift After Feature Engineering
**Symptoms**: mlflow_guardian reports roc_auc drop > 5% immediately after feature_engineer regenerates features
**Root cause**: This is EXPECTED — new features change the model's score distribution temporarily
**Resolution**: Wait 1 training cycle; roc_auc should recover. If roc_auc stays low after 2 cycles, then investigate data quality
**Do NOT retrain**: Automatically on this pattern alone

---

## How to Add New Patterns

When resolving a new incident, append a section following the format above:
```
### P00N — Short descriptive name
**Symptoms**: What the heartbeats/alerts showed
**Root cause**: The actual underlying issue
**Resolution**: What action fixed it
**Agents affected**: Which agents showed symptoms
**Correction issued**: Exact correction text sent (if any)
```
