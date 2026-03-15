# Adopt Supply Chain AI OS

[![CI](https://github.com/ujjwalredd/Supply-Chain/actions/workflows/ci.yml/badge.svg)](https://github.com/ujjwalredd/Supply-Chain/actions/workflows/ci.yml)
[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://supply-chain-silk.vercel.app)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-203%20passed-brightgreen)](#validation-playbook)
[![Agents](https://img.shields.io/badge/agents-13%20HEALTHY-brightgreen)](#autonomous-agent-system)

[Live Demo](https://supply-chain-silk.vercel.app)

An end-to-end AI-native supply chain control tower with a **fully autonomous 13-agent system** powered by **deepagents (LangGraph)**. Drop any CSV into a watched folder and the platform automatically infers the schema, builds data pipelines, engineers ML features, retrains the delay prediction model, promotes it to production, and updates the Grafana dashboard — with zero human intervention.

---

## What Makes This Different

Most supply chain platforms require humans to write ETL, tune models, and monitor pipelines. Adopt Supply Chain AI OS does all of that autonomously:

- **New data file dropped** → DataIngestionAgent uses a deepagents iterative loop to infer schema, validate the loader (up to 3 auto-fix attempts), and trigger the full pipeline
- **Model accuracy drops** → MLflowGuardian detects drift, triggers retraining, promotes better model via Claude tool_use decision with hard floors (`roc_auc >= 0.60`)
- **Pipeline fails** → DagsterGuardian detects it, triggers a re-run, escalates to Orchestrator if 3+ consecutive failures
- **Cross-agent failure detected** → Orchestrator's deepagents LangGraph graph with 3 specialist sub-agents diagnoses root cause, issues structured `OrchestrationResult` corrections — no regex JSON parsing
- **New ML features discovered** → FeatureEngineerAgent reads Gold layer, asks Claude for 5 new features, validates each in a 5-gate sandbox, writes them — automatically merged into the next training run
- **Dashboard needs updating** → DashboardAgent pushes new Grafana panels every 10 minutes, all from structured Claude output

---

## Architecture

```
                          NEW CUSTOMER DATA FLOW
  CSV Upload (API) ─────────────────────────────────────────────────┐
  S3 / MinIO Drop ──────────────────────────────────────────────────│
  Kafka Stream ───────────────────────────────────────────────────── ▼
                                                          /data/source/ (watched)
                                                                │
                                                   DataIngestionAgent (60s)
                                             deepagents iterative loop:
                                             read_csv_sample → generate loader
                                             → validate_python_loader → fix if needed
                                             → save loader → trigger pipeline
                                                                │
                              INGESTION LAYER                   │
  OpenBoxes WMS ──────────────────────────────────────────────-─│
  Kafka (supply-chain-events) ──────────────────────────────-───│
         │                                                      │
         v                                                      v
    pg-writer                                         Dagster Full Pipeline
  (Kafka → PostgreSQL)                                          │
                                              ┌─────────────────┼─────────────────┐
                                              ▼                 ▼                 ▼
                                          Bronze             Silver             Gold
                                        (raw parquet)    (validated)      (AI-ready + ML)
                                              │                 │                 │
                                              └─────────────────┼─────────────────┘
                                                                │
                                                   ┌────────────┼────────────┐
                                                   ▼            ▼            ▼
                                           gold_delay_model  demand_forecast  supplier_risk
                                           (XGBoost + MLflow)  (Prophet)
                                                   │
                                                   ▼
                                       FeatureEngineerAgent (15 min)
                                       Claude suggests features →
                                       5-gate sandbox validation →
                                       written to computed_features/ →
                                       merged into next training run
                                                   │
                                                   ▼
                                       MLflowGuardianAgent (5 min)
                                       detects roc_auc drift →
                                       triggers retraining →
                                       Claude tool_use promotion decision →
                                       hard floors: roc_auc ≥ 0.60, train_rows ≥ 100


                        ┌──────────────────────────────────────────────────────────────┐
                        │          AUTONOMOUS AGENT SYSTEM (13 agents)                 │
                        │                                                              │
                        │  Orchestrator (Sonnet + deepagents LangGraph)                │
                        │    ├── 3 sub-agents: kafka_investigator,                     │
                        │    │                 dagster_investigator, ml_investigator   │
                        │    ├── 7 LangChain tools (heartbeats, audit, Kafka,          │
                        │    │   Dagster, MLflow, issue_correction, trigger_pipeline)  │
                        │    ├── Skills: 5 SKILL.md domain knowledge files             │
                        │    └── Memory: incident_patterns.md (8 patterns)             │
                        │                                                              │
                        │  Kafka Guardian    DagsterGuardian  DataIngestion            │
                        │  Bronze Agent      Silver Agent     Gold Agent               │
                        │  Medallion Supervisor               AI Quality Monitor       │
                        │  Database Health   MLflow Guardian  Feature Engineer         │
                        │  Dashboard Agent                                             │
                        └──────────────────────────────────────────────────────────────┘
                                                   │
                        ┌──────────────────────────┼──────────────────────────┐
                        │                          │                          │
                        ▼                          ▼                          ▼
                  PostgreSQL                  FastAPI                    Grafana
                  (orders, deviations,        (REST + WebSocket)         (auto-updated
                   suppliers, audit_log)                                  by DashboardAgent)
                        │                          │
                        ▼                          ▼
                   Next.js Dashboard          Prometheus + Loki + Jaeger
```

---

## Autonomous Agent System

13 specialized agents run as daemon threads in a single container. Each has its own monitoring interval, self-healing logic, correction handler, and escalation path. No agent ever exits under normal operation.

### Agent Roster

| Agent | Model | Interval | Responsibility |
|-------|-------|----------|----------------|
| **Orchestrator** | Claude Sonnet 4.6 | 5 min | deepagents LangGraph with 3 sub-agents and 7 tools. Cross-agent root cause analysis, structured `OrchestrationResult` corrections via Redis pub/sub. Loads 5 domain skills + incident memory. |
| **Kafka Guardian** | Claude Haiku | 30s | Consumer lag, DLQ spikes, producer silence. Restarts containers via Docker API. |
| **Dagster Guardian** | Claude Haiku | 2 min | Run failures, asset freshness, schedule health. Triggers full or incremental jobs. Responds to orchestrator corrections. |
| **Bronze Agent** | Claude Haiku | 5 min | Parquet existence, schema drift, freshness validation. `apply_correction("trigger materialization")` → real Dagster trigger. |
| **Silver Agent** | Claude Haiku | 5 min | Null rates, dedup verification, status enum, delay range. Path check uses `str(f)` for nested parquet dirs. |
| **Gold Agent** | Claude Haiku | 10 min | Financial formula re-validation, ML output bounds, forecast sanity. Escalates to Medallion Supervisor. |
| **Medallion Supervisor** | Claude Haiku | 3 min | Data contract enforcement (Bronze→Silver→Gold dependency chain) |
| **AI Quality Monitor** | Claude Haiku | 60s | Stuck pending actions, low-confidence re-triggers, REROUTE validation |
| **Database Health** | Claude Haiku | 60s | Connection count, long queries, lock detection, table sizes |
| **Data Ingestion** | Claude Haiku | 60s | deepagents iterative validation loop (up to 3 fix attempts). Watches `/data/source/`. Infers schema via `read_csv_sample` + `validate_python_loader` tools. |
| **MLflow Guardian** | Claude Haiku | 5 min | Monitors roc_auc drift. Hard floors: never promote if `roc_auc < 0.60` or `train_rows < 100`. `apply_correction()` resets cooldown and triggers real retrain. |
| **Feature Engineer** | Claude Haiku | 15 min | Reads Gold layer. Asks Claude for new features. Validates each via 5-gate sandbox. Writes to `computed_features/`. Triggers ML retraining. |
| **Dashboard Agent** | Claude Haiku | 10 min | Reads agent heartbeats + Gold metrics. Asks Claude for panel spec. Builds deterministic Grafana JSON. Pushes via Grafana API. |

### Agent Design Principles

1. **tool_use forced, never free text** — every LLM call uses `tool_choice={"type":"tool","name":"..."}`. Claude cannot hallucinate a response, only fill a typed schema.
2. **No LLM on every cycle** — `check()` runs threshold logic first. LLM called only on anomaly.
3. **5-gate code validation** — any code generated by Claude runs through: syntax check → subprocess sandbox → sample validation → schema check → timeout kill. Never executed without all 5 gates passing.
4. **Hard floors on ML** — `mlflow_guardian` never promotes a model with `roc_auc < 0.60` or `train_rows < 100`, regardless of Claude's decision.
5. **Corrections are actionable** — every agent's `apply_correction()` parses the instruction keyword and takes a real action (trigger job, reset cooldown, force regeneration). Not just logging.
6. **All actions audited** — every agent action writes to `agent_audit_log` in PostgreSQL with reasoning, outcome, and details.
7. **Graceful fallback** — deepagents orchestrator and ingestion agent fall back to the legacy Anthropic SDK path if the library is unavailable. System never goes down on a missing dependency.
8. **Path checks use full path** — all parquet file detection uses `str(f)` (full path), not `f.name` (just `data.parquet`). Prevents silent misses on nested directories like `orders_ai_ready/data.parquet`.

### Orchestrator deepagents Architecture

The orchestrator uses `create_deep_agent()` from the deepagents library (LangGraph-based):

```
OrchestratorAgent.check()
  │
  ├── < 2 degraded, no alerts → threshold logic only (no LLM)
  │
  └── ≥ 2 degraded or any CRITICAL/HIGH alert → deepagents invoked
            │
            ▼
      create_deep_agent(llm=Sonnet, tools=[7 tools], subagents=[3 subagents],
                        response_format=OrchestrationResult,
                        memory_files=[incident_patterns.md],
                        system_prompt=skills_text)
            │
            ├── Calls tools: get_all_heartbeats, get_dagster_recent_runs, etc.
            ├── Delegates to sub-agents if deep investigation needed
            └── Returns structured OrchestrationResult (Pydantic)
                  {root_cause_analysis, correlations, corrections[],
                   human_intervention_needed, confidence}
                        │
                        ▼
              state.write_correction() + communication.publish_correction()
              for each correction in the result
```

**Escalation rules:**
- 1 agent DEGRADED → issue correction, monitor next cycle
- 2+ agents DEGRADED (same domain) → correlated failure → investigate root cause first
- 3+ agents DEGRADED (cross-domain) → `human_intervention_needed=True`
- All agents offline → `human_intervention_needed=True` immediately

### Skills System

5 domain knowledge files are loaded into the orchestrator and ingestion agent system prompts at startup:

| Skill | File | Contents |
|-------|------|----------|
| `supply-chain-ops` | `agents/skills/supply-chain-ops/SKILL.md` | Agent roster, failure correlation patterns, correction dispatch guide |
| `dagster-diagnosis` | `agents/skills/dagster-diagnosis/SKILL.md` | Job names, GraphQL patterns, self-healing actions |
| `kafka-diagnosis` | `agents/skills/kafka-diagnosis/SKILL.md` | Consumer groups, DLQ diagnosis, lag thresholds |
| `mlflow-governance` | `agents/skills/mlflow-governance/SKILL.md` | Promotion rules, retraining triggers, baseline management |
| `data-ingestion` | `agents/skills/data-ingestion/SKILL.md` | Loader patterns, validation gates, error diagnosis |

### Incident Memory

`agents/memories/incident_patterns.md` stores 8 documented incident patterns (P001–P008). Loaded into the orchestrator system prompt at startup so it recognizes recurring issues without re-learning them:

- P001 — Dagster webserver port mismatch (3001 vs 3000)
- P002 — Feature engineer `f.name` vs `str(f)` path bug
- P003 — Silver agent same path bug
- P004 — `medallion_incremental` not including `gold_delay_model`
- P005 — PostgreSQL connection pool exhaustion
- P006 — Kafka DLQ growing (schema registry incompatibility)
- P007 — All medallion agents missing files during startup (expected — not an incident)
- P008 — MLflow baseline drift after feature regeneration (expected — not an incident)

### Model Cost Strategy

- **Haiku** (12 agents): called only on threshold breach. Typical cost: < $0.50/day
- **Sonnet** (orchestrator only): triggered on CRITICAL alerts or multi-agent correlation. Typical cost: < $1.00/day
- Total estimated cost at moderate load: **< $2.00/day**

---

## New Customer Data — Zero-Touch Onboarding

This is the core of the agentic vision: a new customer sends you their data and the entire platform handles it without a single human action.

### How It Works

The `DataIngestionAgent` watches `/data/source/` every 60 seconds. When it sees a new file:

**deepagents path (when available):**
1. Calls `read_csv_sample` tool to understand the file structure
2. Generates a Python `load_csv` loader function
3. Calls `validate_python_loader` tool — runs the loader against the real CSV in a sandbox
4. If validation fails, feeds the exact error back to the LLM and retries — up to **3 attempts**
5. Returns structured `IngestionResult` (Pydantic) with `validation_passed=True` and attempt count
6. Saves loader + triggers `medallion_full_pipeline`

**Legacy path (fallback):**
1. Reads 10-row sample
2. Calls Claude `infer_csv_schema` tool_use → typed schema (column names, dtypes, nullable flags)
3. Validates loader in CodeExecutor 5-gate sandbox
4. One auto-fix retry with Claude if validation fails
5. Saves loader + triggers pipeline

After the pipeline runs:
- Bronze layer ingests the new table
- Silver layer validates and cleans it
- Gold layer enriches it with AI scoring
- Feature Engineer generates ML features from it
- MLflow Guardian detects data change, triggers model retraining with new data

### Easiest Way to Add New Customer Data

**Option 1 — Direct file drop**

```bash
# Copy any CSV (any schema, any column names) into the watched folder
docker cp customer_orders.csv supply-chain-agents:/data/source/

# Within 60 seconds, DataIngestionAgent auto-processes it
# Watch it happen:
docker logs supply-chain-agents 2>&1 | grep "data_ingestion" | tail -20
```

**Option 2 — HTTP Upload endpoint**

Add to FastAPI (`api/routers/data.py`):

```python
from fastapi import APIRouter, UploadFile
from pathlib import Path

router = APIRouter(prefix="/data", tags=["data"])

@router.post("/upload")
async def upload_customer_data(file: UploadFile):
    dest = Path("/data/source") / file.filename
    dest.write_bytes(await file.read())
    return {
        "status": "received",
        "file": file.filename,
        "message": "DataIngestionAgent will auto-process within 60 seconds"
    }
```

Customer just runs:
```bash
curl -X POST http://your-server:8000/data/upload \
  -F "file=@customer_orders.csv"
```

**Option 3 — MinIO Drop Zone (large files / batch)**

Customers upload to a MinIO bucket. A sensor or S3-polling agent copies to `/data/source/` and the same DataIngestionAgent flow handles the rest.

### What Happens Automatically After Drop

```
Customer drops CSV (any schema, any column names)
        │
        ▼  [< 60 seconds]
DataIngestionAgent wakes up
        │
        ├── deepagents: read_csv_sample → generate loader → validate → fix if needed (3 attempts)
        ├── loader validated against real CSV in sandbox
        └── Saves loader + triggers medallion_full_pipeline
                │
                ▼  [~ 2-3 minutes]
        Dagster Full Pipeline runs
                │
                ├── Bronze: raw parquet written
                ├── Silver: validated, deduplicated, typed
                ├── Gold: AI scoring, trust scores, delay flags
                ├── gold_delay_model: XGBoost retrained with new data
                │                    + computed features merged in by order_id join
                └── demand_forecast: Prophet retrained
                        │
                        ▼  [< 5 minutes after pipeline]
        FeatureEngineerAgent detects Gold mtime change
                │
                ├── Profiles new Gold columns
                ├── Claude suggests 5 new features
                ├── Validates each in 5-gate sandbox
                └── Writes features.parquet → triggers incremental retraining
                        │
                        ▼  [next 5-min cycle]
        MLflowGuardianAgent checks new model metrics
                │
                ├── If roc_auc improved → Claude promotion decision (tool_use)
                ├── Hard floors enforced: roc_auc ≥ 0.60, train_rows ≥ 100
                └── Promotes new model to Production stage in MLflow
                        │
                        ▼  [next 10-min cycle]
        DashboardAgent reads new metrics
                └── Claude generates panel spec → pushes to Grafana
                    New customer's data appears in dashboard automatically
```

**Total time from CSV drop to live dashboard: ~15–20 minutes, zero human action.**

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Message Broker | Apache Kafka + Zookeeper |
| Stream Processing | ksqlDB (tumbling windows) |
| Database | PostgreSQL 15 |
| Cache / Pub-Sub | Redis 7 |
| Object Storage | MinIO (S3-compatible) |
| Pipeline Orchestration | Dagster 3-container (webserver + daemon + gRPC code server) |
| Lakehouse | Medallion Architecture (Bronze / Silver / Gold Parquet) |
| ML Training | XGBoost (delay prediction, dynamic feature columns) + Prophet (demand) |
| ML Tracking | MLflow (model registry, promotion history, baseline management) |
| AI Reasoning | Claude Sonnet 4.6 (orchestrator) + Claude Haiku 4.5 (12 sub-agents) |
| Agentic Framework | deepagents 0.4.11 (LangGraph-based) — orchestrator + data ingestion |
| LLM Wrappers | LangChain Anthropic + LangChain Core + LangGraph |
| Structured Output | Pydantic v2 (`OrchestrationResult`, `IngestionResult` response models) |
| Code Sandbox | Python subprocess isolation (5-gate: syntax → exec → validate → schema → timeout) |
| API | FastAPI (async, WebSocket, OpenAPI) |
| Frontend | Next.js 14 |
| Observability | Grafana + Prometheus + Loki + Jaeger |
| Log Collection | Grafana Alloy |
| WMS Integration | OpenBoxes (live or mock) |
| Autonomous Agents | 13 agents, Redis pub/sub, PostgreSQL state, Skills + Memory system |

---

## Prerequisites

- Docker and Docker Compose v2
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- 8 GB RAM minimum (16 GB recommended)

---

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/ujjwalredd/Supply-Chain.git && cd supply-chain-os
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY and change default passwords

# 2. Start everything (22 services including agents)
docker compose up -d --build

# 3. Wait ~60s for all services to initialize, then open:
#    Dashboard:       http://localhost:3000
#    API:             http://localhost:8000/docs
#    Dagster:         http://localhost:3001
#    Grafana:         http://localhost:3002  (auto-updated every 10 min)
#    MLflow:          http://localhost:5001
#    MinIO:           http://localhost:9001
#    Jaeger:          http://localhost:16686
```

---

## Environment Variables

All configuration is in `.env.example`. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Required. Claude API key. | — |
| `POSTGRES_PASSWORD` | Database password | `change_me_in_production` |
| `AGENT_MODEL_HAIKU` | Model for sub-agents | `claude-haiku-4-5-20251001` |
| `AGENT_MODEL_SONNET` | Model for orchestrator | `claude-sonnet-4-6` |
| `KAFKA_LAG_CRITICAL` | Consumer lag threshold for container restart | `2000` |
| `AI_MIN_CONFIDENCE` | Min confidence before re-trigger | `0.4` |
| `AUTONOMY_CONFIDENCE_THRESHOLD` | Auto-execute threshold | `0.70` |
| `AGENT_STARTUP_DELAY` | Seconds to wait for infra before agents start | `45` |
| `DAGSTER_WEBSERVER_URL` | Internal Dagster URL for agents | `http://dagster-webserver:3000` |
| `MLFLOW_TRACKING_URI` | MLflow server URL | `http://mlflow:5000` |
| `GOLD_PATH` | Gold layer parquet directory | `/data/gold` |
| `DATA_SOURCE_DIR` | Watched folder for new customer CSV files | `/data/source` |
| `GRAFANA_URL` | Grafana API endpoint | `http://grafana:3000` |

See `.env.example` for the full list of 50+ configurable variables.

---

## Validation Playbook

### Layer 1 — Automated tests (runs in 4 seconds)

```bash
python -m pytest tests/ -v --tb=short -q
# Expected: 203 passed, 3 skipped, 0 failed
```

203 tests across 14 test classes covering: deepagents integration, escalation rules, correction dispatch, path-checking bug proof, CSV loader gates, concurrent ingestion, Pydantic schemas, skill/memory files, docker config, pipeline config, and requirements.

### Layer 2 — All 13 agents HEALTHY

```bash
docker exec supply-chain-agents python -c "
from agents import state
hbs = state.get_all_heartbeats()
print(f'Agents: {len(hbs)}/13')
for h in sorted(hbs, key=lambda x: x.get('agent_id','')):
    print(f'  [{h[\"status\"]:10}] {h[\"agent_id\"]:25} {str(h.get(\"current_task\",\"\"))[:60]}')
degraded = [h['agent_id'] for h in hbs if h['status'] not in ('HEALTHY',)]
print(f'\nDEGRADED/OFFLINE: {degraded if degraded else \"none — all good\"}')
"
```

**Pass:** All 13 show `[HEALTHY   ]`, 0 DEGRADED, 0 OFFLINE.

### Layer 3 — API health

```bash
# Health check
curl -s http://localhost:8000/health | python -m json.tool

# ML delay prediction (tests the 10-feature model with computed features)
curl -s -X POST http://localhost:8000/ml/predict \
  -H "Content-Type: application/json" \
  -d '{"supplier_id":"SUP-001","region":"US-EAST","quantity":10,"unit_price":5.0,"order_value":50.0,"inventory_level":500.0}' \
  | python -m json.tool
```

**Pass:** health returns `{"status":"ok"}`, predict returns `{"is_delayed":false,"probability":...,"confidence":...}`.

> The predict endpoint auto-fills missing computed features with `0.0` — it reads the model's actual `feature_names_in_` and handles any feature count without crashing.

### Layer 4 — Dagster pipelines

```bash
curl -s -X POST http://localhost:3001/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"{ runsOrError(limit:5){... on Runs{results{runId status pipelineName}}}}"}' \
  | python -m json.tool
```

**Pass:** Last 5 runs show `SUCCESS`. Or open [http://localhost:3001](http://localhost:3001) → Runs tab.

### Layer 5 — MLflow model in Production

```bash
docker exec supply-chain-agents python -c "
import redis, json
r = redis.from_url('redis://redis:6379/0', decode_responses=True)
baseline = json.loads(r.get('mlflow:baseline') or '{}')
print(f'Production roc_auc : {baseline.get(\"roc_auc\", \"not set\")}')
print(f'Accuracy           : {baseline.get(\"accuracy\", \"not set\")}')
print(f'Train rows         : {baseline.get(\"train_rows\", \"not set\")}')
"
```

**Pass:** `roc_auc >= 0.86`, `train_rows >= 7000`.

### Layer 6 — New customer CSV end-to-end test

```bash
# Drop a brand new CSV into the source directory
docker exec supply-chain-agents bash -c "cat > /data/source/stress_test_customer.csv << 'EOF'
CustomerID,CompanyName,Region,OrderVolume,ContractValue,RiskScore
CUST001,Stress Test Corp,US-WEST,500,250000.00,0.12
CUST002,Validation Inc,EU-NORTH,150,89500.00,0.45
EOF"

# Wait 70s for DataIngestionAgent to detect + infer schema + trigger pipeline
sleep 70

# Verify ingested
docker exec supply-chain-agents python -c "
import redis
r = redis.from_url('redis://redis:6379/0', decode_responses=True)
known = r.smembers('ingestion:known_files')
found = [f for f in known if 'stress_test' in f]
print('Ingested:', found if found else 'NOT YET — wait 60s more')
"

# Check the generated loader
docker exec supply-chain-agents cat /data/source/_loaders/stress_test_customer.py
```

**Pass:** Loader file exists, contains `def load_csv`, `validation_passed=True` in agent logs.

### Layer 7 — Orchestrator deepagents is active

```bash
docker exec supply-chain-agents python -c "
from agents import state
entries = state.get_recent_audit(limit=20)
orch = [e for e in (entries or []) if e.get('agent_id')=='orchestrator']
for e in orch[-3:]:
    engine = e.get('details',{}).get('engine','unknown')
    print(f'  [{e[\"outcome\"]}] engine={engine} | {str(e.get(\"reasoning\",\"\"))[:80]}')
"
```

**Pass:** Shows `engine=deepagents` when anomalies were detected, or `engine=legacy-sdk` if no issues warranted reasoning (both are correct).

### Layer 8 — Force an incident and watch self-healing

```bash
# Inject a fake degraded status
docker exec supply-chain-agents python -c "
from agents import state, communication
state.write_heartbeat('dagster_guardian','DEGRADED','fake_error',
    {'consecutive_failures':3},'test injection','CONN_REFUSED',
    'claude-haiku-4-5-20251001',60)
communication.publish_alert('dagster_guardian','HIGH',
    'Test: dagster_guardian connection refused',{})
print('Incident injected — orchestrator responds within 5 minutes')
"

# Wait 5 min then check corrections were issued
sleep 300
docker exec supply-chain-agents python -c "
from agents import state
entries = state.get_recent_audit(limit=15)
for e in (entries or []):
    if 'orchestrat' in e.get('agent_id','') or 'CORRECTION' in e.get('action',''):
        print(f'  [{e[\"outcome\"]}] {e[\"agent_id\"]} | {e[\"action\"]} | {str(e.get(\"reasoning\",\"\"))[:100]}')
"
```

**Pass:** Shows `ORCHESTRATION_CYCLE SUCCESS` and/or `CORRECTION_ISSUED` to `dagster_guardian`.

### Quick one-liner health check

```bash
docker exec supply-chain-agents python -c "
from agents import state
hbs = state.get_all_heartbeats()
healthy = sum(1 for h in hbs if h['status']=='HEALTHY')
print(f'RESULT: {healthy}/13 HEALTHY — {\"ALL GOOD\" if healthy==13 else \"ISSUES FOUND\"}')
for h in hbs:
    if h['status'] != 'HEALTHY':
        print(f'  ISSUE: {h[\"agent_id\"]} is {h[\"status\"]} — {h.get(\"last_error\",\"\")}')
"
```

---

## Dropping New Customer Data

```bash
# Option 1 — Direct docker cp
docker cp customer_orders.csv supply-chain-agents:/data/source/

# Option 2 — HTTP upload (after adding the endpoint)
curl -X POST http://localhost:8000/data/upload \
  -F "file=@customer_orders.csv"

# Within 60s, check DataIngestionAgent picked it up
docker exec supply-chain-postgres psql -U supplychain -d supply_chain_db \
  -c "SELECT agent_id, action, reasoning, outcome FROM agent_audit_log ORDER BY created_at DESC LIMIT 5;"

# Watch the pipeline run in Dagster UI
open http://localhost:3001
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/orders` | List orders with filtering |
| GET | `/suppliers` | List suppliers with trust scores |
| GET | `/alerts/enriched` | Deviations with AI analysis |
| POST | `/ai/analyze` | Structured AI analysis (cached) |
| POST | `/ai/analyze/stream` | Streaming AI analysis (SSE) |
| POST | `/ai/analyze/bulk` | Bulk triage of open deviations |
| POST | `/ai/whatif/stream` | What-if scenario analysis |
| POST | `/ai/analyze-scored` | Multi-model AI with quality scoring |
| GET | `/forecasts/at-risk` | ML-predicted at-risk orders |
| GET | `/forecasts/demand` | Prophet demand forecast |
| POST | `/ml/predict` | Delay prediction (auto-detects model feature count) |
| POST | `/actions/{id}/execute` | Execute a pending action |
| GET | `/events` | Event sourcing log |
| GET | `/lineage` | Data lineage graph |
| GET | `/ontology/constraints` | Business rule constraints |
| WS | `/ws` | Real-time deviation stream |

Full OpenAPI docs at `http://localhost:8000/docs`.

---

## Data Pipeline

The Dagster medallion pipeline runs on a 6-hour schedule and on-demand via agents:

| Job | Steps | Trigger |
|-----|-------|---------|
| `medallion_full_pipeline` | All 16 assets (Bronze + Silver + Gold + ML + Forecast + Risk) | Schedule, DataIngestion, DagsterGuardian |
| `medallion_incremental` | `bronze_orders → silver_orders → gold_orders_ai_ready → gold_delay_model` | FeatureEngineer, MLflowGuardian, agents |

Both jobs include `gold_delay_model` — ML retraining happens on every incremental run, not just the full pipeline.

### Pipeline Step Details

1. **Bronze**: Raw ingest from CSV or Kafka (append-only, schema-on-read)
2. **Silver**: Validated, deduplicated, typed, business rules applied
3. **Gold**: AI-ready with supplier trust scores, deviation flags, financial formulas
4. **gold_delay_model**: XGBoost trained on Silver orders + computed features merged by `order_id` join. Logs to MLflow. Supports dynamic feature columns via `extra_feature_cols` parameter.
5. **demand_forecast**: Prophet demand forecast by product
6. **supplier_risk**: Risk scoring per supplier

---

## Checking Agent Status

### All 13 Agent Heartbeats
```bash
docker exec supply-chain-postgres psql -U supplychain -d supply_chain_db \
  -c "SELECT agent_id, status, current_task, error_count, last_seen FROM agent_heartbeats ORDER BY last_seen DESC;"
```

Expected: all 13 agents `HEALTHY`, `error_count=0`.

### Agent Audit Log (Every Action Taken)
```bash
docker exec supply-chain-postgres psql -U supplychain -d supply_chain_db \
  -c "SELECT agent_id, action, outcome, to_char(created_at,'HH24:MI:SS') FROM agent_audit_log ORDER BY created_at DESC LIMIT 15;"
```

### Check Computed Features Generated
```bash
docker exec supply-chain-agents python3 -c "
import json
from pathlib import Path
m = Path('/data/gold/computed_features/manifest.json')
if m.exists():
    d = json.loads(m.read_text())
    print(f'Features: {[f[\"name\"] for f in d[\"features\"]]}')
    print(f'Rows: {d[\"rows\"]}')
else:
    print('Not yet generated')
"
```

### Check MLflow Production Model
```bash
docker exec supply-chain-agents python3 -c "
import requests
r = requests.get('http://mlflow:5000/api/2.0/mlflow/model-versions/search',
    params={'filter':'name=\"supply_chain_delay_model\"', 'max_results':3})
for v in r.json().get('model_versions', []):
    print(f'v{v[\"version\"]} stage={v[\"current_stage\"]} run={v[\"run_id\"][:8]}')
"
```

---

## Checking Dagster Pipeline Runs

### Via Browser
Open **http://localhost:3001** → click **Runs** in the left sidebar.

### Via Terminal

```bash
# Check latest runs
docker exec supply-chain-postgres psql -U supplychain -d dagster \
  -c "SELECT run_id, pipeline_name, status, create_timestamp FROM runs ORDER BY create_timestamp DESC LIMIT 10;"

# Trigger incremental pipeline manually
curl -s -X POST http://localhost:3001/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation { launchRun(executionParams: { selector: { jobName: \"medallion_incremental\", repositoryLocationName: \"pipeline.definitions:defs\", repositoryName: \"__repository__\" }, runConfigData: {} }) { ... on LaunchRunSuccess { run { runId } } ... on PythonError { message } } }"}'

# Trigger full pipeline manually
curl -s -X POST http://localhost:3001/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation { launchRun(executionParams: { selector: { jobName: \"medallion_full_pipeline\", repositoryLocationName: \"pipeline.definitions:defs\", repositoryName: \"__repository__\" }, runConfigData: {} }) { ... on LaunchRunSuccess { run { runId } } ... on PythonError { message } } }"}'

# Watch dagster daemon logs
docker logs supply-chain-dagster-daemon --follow
```

---

## Checking MLflow Experiments

### Via Browser
Open **http://localhost:5001** — all experiments, runs, model metrics, and registered models.

### Via Terminal

```bash
# Check latest run metrics
docker exec supply-chain-agents python3 -c "
import requests, json
r = requests.post('http://mlflow:5000/api/2.0/mlflow/runs/search',
    json={'experiment_ids':['1'],'filter':\"status = 'FINISHED'\",
          'order_by':['start_time DESC'],'max_results':3})
for run in r.json().get('runs',[]):
    m = {x['key']:x['value'] for x in run['data'].get('metrics',[]) if isinstance(x,dict)}
    print(f'run={run[\"info\"][\"run_id\"][:8]} roc_auc={float(m.get(\"roc_auc\",0)):.4f} rows={float(m.get(\"train_rows\",0)):.0f}')
"
```

---

## Observability

| Service | URL | What to check |
|---------|-----|---------------|
| **Dashboard** | http://localhost:3000 | Live KPIs, deviation feed, AI reasoning panel |
| **Dagster** | http://localhost:3001 | Pipeline runs, asset graph, schedules |
| **FastAPI Docs** | http://localhost:8000/docs | All routers and endpoints |
| **Grafana** | http://localhost:3002 | Auto-updated supply chain metrics (pushed by DashboardAgent) |
| **MLflow** | http://localhost:5001 | ML experiments, model versions, promotion history |
| **MinIO** | http://localhost:9001 | Bronze/Silver/Gold/computed_features parquet files |
| **Jaeger** | http://localhost:16686 | Distributed traces |
| **Prometheus** | http://localhost:9090 | Raw metrics |

---

## Understanding Agent Logs

The agents report real activity — this is the system working correctly:

- `deepagents available — will use structured LangGraph orchestration` → Orchestrator using deepagents path
- `roc_auc dropped 0.0512 — retraining` → MLflow Guardian detected drift, triggered retraining
- `Gold updated — generating features from data.parquet` → Feature Engineer running on new Gold data
- `Merged 5 computed features` → ML training using AI-generated features
- `Model v23 promoted to Production` → Auto-promotion after improvement
- `Dagster webserver not reachable — waiting 60s` → Dagster is booting; agent waits with backoff
- `Orchestrator correction → triggering incremental job` → deepagents correction was acted on
- `Loader validated for customer.csv: 10 rows` → DataIngestionAgent iterative loop succeeded

---

## GitHub Actions CI

The CI pipeline runs on every push and PR to `main`:

1. **Unit Tests**: pytest with coverage (threshold: 45%, currently 203 tests)
2. **Secret Scan**: Detects hardcoded credentials in Python files
3. **dbt Validate**: Ensures all dbt model files have content
4. **Docker Validate**: Validates docker-compose syntax
5. **Agents Validate**: Verifies all 13 agent classes import correctly
6. **Tag Release**: Auto-tags on merge to main (`vYYYY.MM.DD-<sha>`)

---

## Project Structure

```
supply-chain-os/
  agents/                         # Autonomous agent system
    base.py                       # BaseAgent: infinite loop, heartbeat, LLM, corrections
    state.py                      # PostgreSQL: heartbeats, audit log, corrections
    communication.py              # Redis pub/sub: alerts, corrections, heartbeats
    orchestrator.py               # Orchestrator: deepagents LangGraph + 7 tools + 3 sub-agents
    kafka_guardian.py             # Kafka consumer lag + DLQ + container restart
    dagster_guardian.py           # Dagster run health + schedule + apply_correction()
    ai_quality_monitor.py         # AI output quality, stuck actions, confidence
    database_health.py            # PostgreSQL connections, locks, table sizes
    data_ingestion_agent.py       # deepagents iterative loop: read_csv_sample + validate_python_loader
    mlflow_guardian.py            # Model drift + auto-promotion + apply_correction()
    feature_engineer.py           # Auto feature gen + 5-gate sandbox + apply_correction()
    dashboard_agent.py            # Grafana auto-update via structured Claude panel spec
    run_all.py                    # Entry point — starts all 13 agents as daemon threads
    tools/
      code_executor.py            # 5-gate code sandbox (syntax→exec→validate→schema→timeout)
    medallion/
      bronze.py                   # Bronze parquet validation + apply_correction()
      silver.py                   # Silver validation, str(f) path check, apply_correction()
      gold.py                     # Gold financial formula + ML bounds, str(f) path check
      supervisor.py               # Medallion data contract (Bronze→Silver→Gold chain)
    skills/                       # Domain knowledge injected into agent system prompts
      supply-chain-ops/SKILL.md   # Agent roster, escalation rules, correction dispatch guide
      dagster-diagnosis/SKILL.md  # Job names, failure patterns, GraphQL patterns
      kafka-diagnosis/SKILL.md    # Consumer groups, DLQ thresholds, lag diagnosis
      mlflow-governance/SKILL.md  # Promotion rules, hard floors, retraining triggers
      data-ingestion/SKILL.md     # Loader patterns, validation gates, error diagnosis
    memories/
      incident_patterns.md        # 8 documented incident patterns loaded at orchestrator startup
    _loaders/                     # Auto-generated CSV loaders (created by DataIngestionAgent)
  api/                            # FastAPI application
    routers/                      # REST endpoints (orders, suppliers, ai, alerts, ml, etc.)
    models.py                     # SQLAlchemy ORM models
    database.py                   # Connection management
  reasoning/                      # Claude AI reasoning engine
    engine.py                     # Streaming + structured analysis
  ingestion/                      # Data ingestion
    producer.py                   # Kafka producer (synthetic events)
    pg_writer.py                  # Kafka → PostgreSQL consumer
    openboxes_connector.py        # OpenBoxes WMS integration
  pipeline/                       # Dagster pipeline
    assets_medallion.py           # Bronze/Silver/Gold/ML assets (computed_features merge by order_id)
    jobs_medallion.py             # medallion_full_pipeline + medallion_incremental (includes gold_delay_model)
    ml_model.py                   # XGBoost: dynamic feature columns + predict handles any feature count
    demand_forecast.py            # Prophet demand forecasting
    definitions.py                # Dagster definitions entry point
  tests/
    test_stress_deepagents.py     # 70 tests: deepagents integration, escalation, ingestion, skills, memory
    test_critical_paths.py        # Critical path tests (ML predict, API, pipeline)
    test_api_health.py            # API endpoint health tests
    (+ 8 more test files)         # Total: 203 passing tests
  transforms/                     # dbt models
  quality/                        # Great Expectations validations
  streaming/                      # ksqlDB + WebSocket
  docker/                         # Dockerfiles + dagster.yaml + workspace.yaml
  alembic/                        # Database migrations
  dashboard/                      # Next.js frontend
  data/
    source/                       # Drop new CSV files here — picked up automatically
    bronze/                       # Raw parquet (managed by Dagster)
    silver/                       # Validated parquet
    gold/
      orders_ai_ready/            # AI-enriched orders (data.parquet)
      computed_features/          # Auto-generated ML features (features.parquet + manifest.json)
      supplier_risk/
      demand_forecast/
      deviations/
    models/                       # Local model artifacts (XGBoost .json + encoders .pkl)
```

---

## Contributing

1. Fork the repository
2. Create a feature branch from `main`
3. Write tests for new functionality
4. Ensure CI passes: `python -m pytest tests/ -q --tb=short`
5. Validate Docker: `docker compose config --quiet`
6. Validate agents: `python -c "from agents.run_all import AGENT_CLASSES; print(len(AGENT_CLASSES))"`
7. Open a PR against `main`

### Agent Contribution Guidelines

New agents must:
- Extend `BaseAgent` with `check()`, `heal()`, and `apply_correction()` methods
- Register in `agents/run_all.py` `AGENT_CLASSES` dict
- Write heartbeats and audit logs via `state.py`
- Use LLM calls sparingly — only on anomaly, not every cycle
- Use `tool_choice={"type":"tool","name":"..."}` — never free-text LLM responses
- Any generated code must pass through `CodeExecutor` (5-gate validation) before execution
- Path checks on parquet files must use `str(f)` not `f.name` (files live in subdirectories)
- `apply_correction()` must take real action, not just log

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)** — see the [LICENSE](LICENSE) file for details.

**What this means:**
- ✅ Free to use, modify, and self-host for any purpose
- ✅ Free for internal business use
- ⚠️ If you run this as a **network service or SaaS**, you must release your full source code under AGPL-3.0
- 💼 For a **commercial license** (to build a closed-source product on top), contact the maintainer
