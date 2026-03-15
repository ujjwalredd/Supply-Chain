# Adopt Supply Chain AI OS

[![CI](https://github.com/ujjwalredd/Supply-Chain/actions/workflows/ci.yml/badge.svg)](https://github.com/ujjwalredd/Supply-Chain/actions/workflows/ci.yml)
[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://supply-chain-silk.vercel.app)

[Live Demo](https://supply-chain-silk.vercel.app)

An end-to-end AI-native supply chain control tower with a **fully autonomous 13-agent system**. Drop any CSV into a watched folder and the platform automatically infers the schema, builds data pipelines, engineers ML features, retrains the delay prediction model, promotes it to production, and updates the Grafana dashboard — with zero human intervention.

---

## What Makes This Different

Most supply chain platforms require humans to write ETL, tune models, and monitor pipelines. Adopt Supply Chain AI OS does all of that autonomously:

- **New data file dropped** → DataIngestionAgent infers schema via Claude, writes a validated loader, triggers the full pipeline
- **Model accuracy drops** → MLflowGuardian detects drift, triggers retraining, promotes better model via Claude tool_use decision
- **Pipeline fails** → DagsterGuardian detects it, triggers a re-run, escalates to Orchestrator if 3+ consecutive failures
- **New ML features discovered** → FeatureEngineerAgent reads Gold layer, asks Claude for 5 new features, validates each with a 5-gate sandbox, writes them — new features automatically included in the next model training run
- **Dashboard needs updating** → DashboardAgent pushes new Grafana panels every 10 minutes, all from structured Claude output (no free-form JSON)

---

## Architecture

```
                          NEW CUSTOMER DATA FLOW
  CSV Upload (API) ──────────────────────────────────────────────────┐
  S3 / MinIO Drop ────────────────────────────────────────────────── │
  Kafka Stream ──────────────────────────────────────────────────── ▼
                                                          /data/source/ (watched)
                                                                │
                                                   DataIngestionAgent (60s)
                                             Claude infers schema → validates
                                             → saves loader → triggers pipeline
                                                                │
                              INGESTION LAYER                   │
  OpenBoxes WMS ──────────────────────────────────────────────── │
  Kafka (supply-chain-events) ───────────────────────────────── │
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
                                       auto-promotes if better + roc_auc ≥ 0.60


                        ┌──────────────────────────────────────────────────────────┐
                        │               AUTONOMOUS AGENT SYSTEM (13 agents)        │
                        │                                                          │
                        │  Orchestrator (Sonnet)  ←── Redis pub/sub alerts        │
                        │       │                                                  │
                        │  Kafka Guardian    DagsterGuardian  DataIngestion        │
                        │  Bronze Agent      Silver Agent     Gold Agent           │
                        │  Medallion Supervisor               AI Quality Monitor  │
                        │  Database Health   MLflow Guardian  Feature Engineer     │
                        │  Dashboard Agent                                         │
                        └──────────────────────────────────────────────────────────┘
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
| **Orchestrator** | Claude Sonnet 4.6 | 5 min | Cross-agent correlation, root cause analysis, correction issuance via Redis pub/sub |
| **Kafka Guardian** | Claude Haiku | 30s | Consumer lag, DLQ spikes, producer silence. Restarts containers via Docker API. |
| **Dagster Guardian** | Claude Haiku | 2 min | Run failures, asset freshness, schedule health. Triggers full or incremental jobs. Responds to orchestrator corrections. |
| **Bronze Agent** | Claude Haiku | 5 min | Parquet existence, schema drift, freshness validation. Triggers materialization on anomaly. |
| **Silver Agent** | Claude Haiku | 5 min | Null rates, dedup verification, status enum, delay range. Triggers incremental on missing data. |
| **Gold Agent** | Claude Haiku | 10 min | Financial formula re-validation, ML output bounds, forecast sanity. Escalates to Medallion Supervisor. |
| **Medallion Supervisor** | Claude Haiku | 3 min | Data contract enforcement (Bronze→Silver→Gold dependency chain) |
| **AI Quality Monitor** | Claude Haiku | 60s | Stuck pending actions, low-confidence re-triggers, REROUTE validation |
| **Database Health** | Claude Haiku | 60s | Connection count, long queries, lock detection, table sizes |
| **Data Ingestion** | Claude Haiku | 60s | Watches `/data/source/` for new CSVs. Infers schema via Claude tool_use. Validates loader in sandbox. Triggers full pipeline. |
| **MLflow Guardian** | Claude Haiku | 5 min | Monitors roc_auc drift. Triggers retraining on 5% drop or model >24h stale. Auto-promotes via Claude tool_use decision. |
| **Feature Engineer** | Claude Haiku | 15 min | Reads Gold layer. Asks Claude for new features. Validates each via 5-gate sandbox. Writes to computed_features/. Triggers ML retraining. |
| **Dashboard Agent** | Claude Haiku | 10 min | Reads agent heartbeats + Gold metrics. Asks Claude for panel spec. Builds deterministic Grafana JSON. Pushes via Grafana API. |

### Agent Design Principles

1. **tool_use forced, never free text** — every LLM call uses `tool_choice={"type":"tool","name":"..."}`. Claude cannot hallucinate a response, only fill a typed schema.
2. **No LLM on every cycle** — `check()` runs threshold logic first. LLM called only on anomaly.
3. **5-gate code validation** — any code generated by Claude runs through: syntax check → subprocess sandbox → sample validation → schema check → timeout kill. Never executed without all 5 gates passing.
4. **Hard floors on ML** — `mlflow_guardian` never promotes a model with `roc_auc < 0.60` or `train_rows < 100`, regardless of Claude's decision.
5. **Orchestrator corrections are actionable** — each agent implements `apply_correction()` that parses the instruction and takes real action (trigger job, reset cooldown, force regeneration). Not just logging.
6. **All actions audited** — every agent action writes to `agent_audit_log` in PostgreSQL with reasoning, outcome, and details.

### Model Cost Strategy

- **Haiku** (12 agents): called only on threshold breach. Typical cost: < $0.50/day
- **Sonnet** (orchestrator only): triggered on CRITICAL alerts or multi-agent correlation. Typical cost: < $1.00/day
- Total estimated cost at moderate load: **< $2.00/day**

---

## New Customer Data — Zero-Touch Onboarding

This is the core of the agentic vision: a new customer sends you their data and the entire platform handles it without a single human action.

### How It Works Today

The `DataIngestionAgent` watches `/data/source/` every 60 seconds. When it sees a new file:

1. Reads a 10-row sample
2. Calls Claude `infer_csv_schema` tool_use → gets typed schema (column names, dtypes, nullable flags, primary key hint)
3. Generates a Python loader function from the schema
4. Validates the loader in a sandboxed subprocess on the sample (5-gate CodeExecutor)
5. If validation fails, calls Claude again with the error for one auto-fix retry
6. Saves the validated loader to `agents/_loaders/<table>.py`
7. Triggers `medallion_full_pipeline` in Dagster

After the pipeline runs:
- Bronze layer ingests the new table
- Silver layer validates and cleans it
- Gold layer enriches it with AI scoring
- Feature Engineer generates ML features from it
- MLflow Guardian detects data change, triggers model retraining with new data

### Easiest Way to Add New Customer Data

**Option 1 — HTTP Upload (recommended, already works)**

Add this endpoint to FastAPI (`api/routers/data.py`):

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

Then the customer just does:
```bash
curl -X POST http://your-server:8000/data/upload \
  -F "file=@customer_orders.csv"
```

Within 60 seconds:
- Schema is inferred autonomously
- Loader is validated
- Full pipeline is triggered
- Bronze/Silver/Gold tables are created
- ML model is retrained with the new data
- Dashboard updates to reflect new metrics

**Option 2 — MinIO Drop Zone (for large files or batch customers)**

Customers upload to a MinIO bucket. A sensor in Dagster or a small S3-polling agent detects new objects and copies them to `/data/source/`, then the same DataIngestionAgent flow runs.

```python
# agents/s3_ingestion_agent.py (extend DataIngestionAgent)
# polls MinIO every 60s, downloads new objects to /data/source/
# rest is handled by DataIngestionAgent automatically
```

**Option 3 — Kafka Stream (for real-time customer systems)**

Customer pushes events to a dedicated Kafka topic per customer ID. The `pg-writer` consumer writes to PostgreSQL, and a sensor triggers the pipeline.

### What Happens Fully Automatically After Drop

```
Customer drops CSV (any schema, any column names)
        │
        ▼  [< 60 seconds]
DataIngestionAgent wakes up
        │
        ├── Reads 10 sample rows
        ├── Claude infers: column names, dtypes, nullable, primary key
        ├── Generates Python loader function
        ├── Runs loader in sandbox on sample (5-gate validation)
        ├── Auto-fixes if validation fails (1 retry via Claude)
        └── Saves loader + triggers medallion_full_pipeline
                │
                ▼  [~ 2-3 minutes]
        Dagster Full Pipeline runs
                │
                ├── Bronze: raw parquet written
                ├── Silver: validated, deduplicated, typed
                ├── Gold: AI scoring, trust scores, delay flags
                ├── gold_delay_model: XGBoost retrained with new data
                │                    + computed features merged in
                └── demand_forecast: Prophet retrained
                        │
                        ▼  [< 5 minutes after pipeline]
        FeatureEngineerAgent detects Gold mtime change
                │
                ├── Profiles new Gold columns
                ├── Claude suggests 5 new features for new data schema
                ├── Validates each feature in sandbox
                └── Writes features.parquet → triggers incremental retraining
                        │
                        ▼  [next 5-min cycle]
        MLflowGuardianAgent checks new model metrics
                │
                ├── If roc_auc improved → Claude promotion decision (tool_use)
                ├── Hard floors: never promote if roc_auc < 0.60
                └── Promotes new model to Production stage in MLflow
                        │
                        ▼  [next 10-min cycle]
        DashboardAgent reads new metrics
                └── Claude generates panel spec → pushes to Grafana
                    New customer's data appears in dashboard automatically
```

**Total time from CSV drop to live dashboard: ~15-20 minutes, zero human action.**

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
| Lakehouse | Medallion (Bronze/Silver/Gold Parquet) |
| ML Training | XGBoost + Prophet |
| ML Tracking | MLflow |
| AI Reasoning | Claude Sonnet 4.6 (orchestrator) + Claude Haiku (12 sub-agents) |
| Code Sandbox | Python subprocess isolation (5-gate: syntax → exec → validate → schema → timeout) |
| API | FastAPI (async, WebSocket) |
| Frontend | Next.js 14 |
| Observability | Grafana + Prometheus + Loki + Jaeger |
| Log Collection | Grafana Alloy |
| WMS Integration | OpenBoxes (live or mock) |
| Autonomous Agents | Custom Python (13 agents, Redis pub/sub, PostgreSQL state) |

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

## Dropping New Customer Data

```bash
# Copy a CSV into the watched folder
docker cp customer_orders.csv supply-chain-agents:/data/source/

# Or use the HTTP upload endpoint (add to FastAPI)
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

### Pipeline Step Details

1. **Bronze**: Raw ingest from CSV or Kafka (append-only, schema-on-read)
2. **Silver**: Validated, deduplicated, typed, business rules applied
3. **Gold**: AI-ready with supplier trust scores, deviation flags, financial formulas
4. **gold_delay_model**: XGBoost trained on Silver orders + computed features from FeatureEngineerAgent. Logs to MLflow.
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
    print(f'run={run[\"info\"][\"run_id\"][:8]} roc_auc={m.get(\"roc_auc\",\"N/A\"):.4f} rows={m.get(\"train_rows\",0):.0f}')
"

# Check production model
docker exec supply-chain-agents python3 -c "
import requests
r = requests.get('http://mlflow:5000/api/2.0/mlflow/model-versions/search',
    params={'filter':'name=\"supply_chain_delay_model\" AND current_stage=\"Production\"'})
for v in r.json().get('model_versions',[]):
    print(f'Production: v{v[\"version\"]} run={v[\"run_id\"][:8]}')
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

## Verifying Everything Works

### 1. All Containers Running
```bash
docker compose ps
```
All 22 containers should show `Up`. Critical ones show `(healthy)`.

### 2. All 13 Agents HEALTHY
```bash
docker exec supply-chain-postgres psql -U supplychain -d supply_chain_db \
  -c "SELECT agent_id, status, error_count FROM agent_heartbeats ORDER BY agent_id;"
```
All 13 rows should show `HEALTHY` and `error_count=0`.

### 3. Feature Engineering Running
```bash
docker logs supply-chain-agents 2>&1 | grep "feature_engineer" | grep -E "(feature|valid|Written)" | tail -10
```
Should show features validated and written to computed_features/.

### 4. ML Model Trained With Computed Features
```bash
docker logs supply-chain-dagster-code-server 2>&1 | grep "Merged.*computed features" | tail -5
```
Should show: `Merged 5 computed features: ['order_value_per_unit', ...]`

### 5. Kafka Receiving Events
```bash
docker exec supply-chain-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic supply-chain-events \
  --max-messages 3 \
  --from-beginning 2>/dev/null
```

### 6. One-Liner Full Health Check
```bash
for url in "localhost:8000/health" "localhost:3000" "localhost:3001" "localhost:3002" "localhost:5001"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://$url)
  echo "$url → HTTP $code"
done
```

### Understanding Agent Logs

The agents report real issues as they find them — this is the system working correctly:

- `roc_auc dropped 0.0512 — retraining` → MLflow Guardian detected drift, triggered retraining
- `Gold updated — generating features from data.parquet` → Feature Engineer running on new Gold data
- `Merged 5 computed features` → ML training using AI-generated features
- `Model v14 promoted to Production` → Auto-promotion after improvement
- `Dagster webserver not reachable — waiting 60s` → Dagster is booting; agent waits with backoff and auto-retries
- `Orchestrator correction → triggering incremental job` → Orchestrator correction was acted on

---

## GitHub Actions CI

The CI pipeline runs on every push and PR to `main`:

1. **Unit Tests**: pytest with coverage (threshold: 45%)
2. **Secret Scan**: Detects hardcoded credentials in Python files
3. **dbt Validate**: Ensures all dbt model files have content
4. **Docker Validate**: Validates docker-compose syntax
5. **Agents Validate**: Verifies all 13 agent classes import correctly
6. **Tag Release**: Auto-tags on merge to main (`vYYYY.MM.DD-<sha>`)

---

## Project Structure

```
supply-chain-os/
  agents/                       # Autonomous agent system
    base.py                     # BaseAgent: infinite loop, heartbeat, LLM, corrections
    state.py                    # PostgreSQL: heartbeats, audit log, corrections
    communication.py            # Redis pub/sub: alerts, corrections, heartbeats
    orchestrator.py             # Main orchestrator (Claude Sonnet 4.6)
    kafka_guardian.py           # Kafka consumer lag + DLQ + container restart
    dagster_guardian.py         # Dagster run health + schedule + correction handler
    ai_quality_monitor.py       # AI output quality, stuck actions, confidence
    database_health.py          # PostgreSQL connections, locks, table sizes
    data_ingestion_agent.py     # New CSV detection + Claude schema inference + loader gen
    mlflow_guardian.py          # Model drift detection + auto-promotion via Claude tool_use
    feature_engineer.py         # Auto feature generation + 5-gate sandbox validation
    dashboard_agent.py          # Grafana auto-update via structured Claude panel spec
    run_all.py                  # Entry point — starts all 13 agents as daemon threads
    tools/
      code_executor.py          # 5-gate code sandbox (syntax→exec→validate→schema→timeout)
    medallion/
      bronze.py                 # Bronze parquet validation + materialization trigger
      silver.py                 # Silver dedup/null/enum validation + trigger
      gold.py                   # Gold financial formula + ML bounds + forecast sanity
      supervisor.py             # Medallion data contract (Bronze→Silver→Gold chain)
    _loaders/                   # Auto-generated CSV loaders (created by DataIngestionAgent)
  api/                          # FastAPI application
    routers/                    # REST endpoints (orders, suppliers, ai, alerts, etc.)
    models.py                   # SQLAlchemy ORM models
    database.py                 # Connection management
  reasoning/                    # Claude AI reasoning engine
    engine.py                   # Streaming + structured analysis
  ingestion/                    # Data ingestion
    producer.py                 # Kafka producer (synthetic events)
    pg_writer.py                # Kafka → PostgreSQL consumer
    openboxes_connector.py      # OpenBoxes WMS integration
  pipeline/                     # Dagster pipeline
    assets_medallion.py         # Bronze/Silver/Gold/ML assets (gold_delay_model reads computed_features)
    jobs_medallion.py           # medallion_full_pipeline + medallion_incremental (includes gold_delay_model)
    ml_model.py                 # XGBoost training with dynamic feature columns
    demand_forecast.py          # Prophet demand forecasting
    definitions.py              # Dagster definitions entry point
  transforms/                   # dbt models
  quality/                      # Great Expectations validations
  streaming/                    # ksqlDB + WebSocket
  docker/                       # Dockerfiles + dagster.yaml + workspace.yaml
  alembic/                      # Database migrations
  dashboard/                    # Next.js frontend
  data/
    source/                     # Drop new CSV files here — picked up automatically
    bronze/                     # Raw parquet (managed by Dagster)
    silver/                     # Validated parquet
    gold/
      orders_ai_ready/          # AI-enriched orders
      computed_features/        # Auto-generated ML features (manifest.json + features.parquet)
      supplier_risk/
      demand_forecast/
      deviations/
    models/                     # Local model artifacts (XGBoost .json + encoders .pkl)
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
