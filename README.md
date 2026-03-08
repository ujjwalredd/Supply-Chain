# Supply Chain AI Operating System — v3.0

> Prototype inspired by [Auger](https://auger.com) — an AI-native supply chain control tower that collapses the gap between signal and execution.

---

## What This Does

Auger (raised ~$100M, founded by Dave Clark — former Amazon Worldwide Consumer CEO) built a platform where AI doesn't just surface alerts — it reasons about them and generates executable actions. This project replicates that architecture end-to-end.

| Auger Capability | This Implementation |
|---|---|
| **Control Tower** | Next.js 14 dashboard — 5 KPI cards (incl. MTTR), deviation feed, deviation trend chart, supplier heatmap, risk forecast, actions log, network graph |
| **Real-time Signal Ingest** | Kafka producer → pg_writer → PostgreSQL (50+ events/min with causality chains) |
| **Deviation Detection** | Automatic: DELAY / STOCKOUT / ANOMALY with severity levels (MEDIUM / HIGH / CRITICAL) |
| **AI Root-Cause Reasoning** | Claude Sonnet 4.6 via forced `tool_use` — 100% structured output, no JSON fallback |
| **AI Response Cache** | Redis-backed 1-hour TTL per deviation — eliminates duplicate API calls |
| **Ontology Layer** | 7 business rules injected into every AI call as hard constraints |
| **Action Execution** | Every recommendation click persisted as an auditable `PendingAction` |
| **Risk Forecasting** | Time-decay ML scoring: `delay_probability × order_value × urgency` |
| **Slack Alerting** | Webhook notification for every CRITICAL deviation |
| **Observability** | Prometheus `/metrics` endpoint via `prometheus-fastapi-instrumentator` |
| **Data Lake** | Dagster 14-asset medallion pipeline: bronze → silver → quality gate → dbt → gold |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           SUPPLY CHAIN AI OS — v3.0                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘

 ┌────────────────-─┐     ┌─────────────────────────────────────────────────────────┐
 │  CSV Datasets    │     │                  KAFKA EVENT STREAM                     │
 │                  │     │  Producer: 50+ events/min                               │
 │  OrderList       │     │  • Supplier state machine: NORMAL → DEGRADING → CRITICAL│
 │  FreightRates    │     │  • Causality chains: DELAY triggers STOCKOUT (30%)      │
 │  PlantPorts      │     │  • Anomaly rate: 12% base, up to 60% for CRITICAL sups  │
 │  WhCapacities    │     └──────────────────────┬──────────────────────────────────┘
 │  ProductsPerPlant│                            │
 └────────┬───────-─┘                            │
          │                           ┌──────────┴──────────┐
          │ batch_loader              │                     │
          │                           ▼                     ▼
          │                  ┌──────────────┐    ┌──────────────────┐
          │                  │   pg_writer  │    │    consumer.py   │
          │                  │              │    │                  │
          │                  │ • Upsert     │    │ Delta Lake sink  │
          │                  │   orders &   │    │ (analytics path) │
          │                  │   suppliers  │    └────────┬─────────┘
          │                  │ • Detect     │             │
          │                  │   deviations │             ▼
          │                  │ • Update     │   ┌──────────────────┐
          │                  │   trust score│   │  DAGSTER PIPELINE│
          │                  └──────┬───────┘   │  14 SDAs         │
          │                         │           │                  │
          │                         │ write     │  bronze (×5)     │
          │                         ▼           │    ↓             │
          └────────────────► ┌─────────────┐    │  silver (×3)     │
                             │  PostgreSQL │    │    ↓             │
                             │             │    │  quality gate    │
                             │  orders     │    │    ↓             │
                             │  suppliers  │◄───│  dbt transforms  │
                             │  deviations │    │    ↓             │
                             │  pending_   │    │  gold (×5)       │
                             │  actions    │    │  forecasted_risks│
                             │  ontology   │    └────────┬─────────┘
                             └──────┬──────┘             │
                                    │                    ▼
                             ┌──────┴──────┐    ┌──────────────────┐
                             │   FastAPI   │    │  MinIO :9001     │
                             │   :8000     │    │  supply-chain-   │
                             │             │    │  lakehouse       │
                             │  /orders    │    │  (S3-compatible  │
                             │  /suppliers │    │   data lake      │
                             │  /alerts    │    │   browser)       │
                             │  /actions   │    └──────────────────┘
                             │  /forecasts │
                             │  /network   │
                             │  /ontology  │◄──── Ontology constraints
                             │  /ai/analyze│       injected into
                             │   ↕ tool_use│       every AI call
                             └──────┬──────┘
                                    │                 ┌────────────────┐
                        ┌───────────┴──────────┐      │ Claude Sonnet  │
                        │      Redis :6379     │      │ 4.6            │
                        │   pub/sub channel:   │      │                │
                        │    "deviations"      │      │ tool_use →     │
                        │                      │      │ structured     │
                        │  pg_writer publishes │      │ JSON output    │
                        │  FastAPI subscribes  │      │                │
                        └───────────┬──────────┘      │ SSE stream →   │
                                    │                 │ real-time      │
                                    ▼                 │ token feed     │
                             ┌─────────────┐          └───────┬────────┘
                             │  Next.js    │                  │
                             │  :3000      │◄─────────────────┘
                             │             │  (AI reasoning modal)
                             │  KPI Cards  │
                             │  Deviation  │
                             │  Feed  ◄────┼── WebSocket: live deviation push
                             │  Supplier   │
                             │  Risk Chart │
                             │  Risk       │
                             │  Forecast   │
                             │  Actions Log│
                             │  Network    │
                             │  Graph SVG  │
                             │  Ontology   │
                             └─────────────┘

 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │  v3.0 IMPROVEMENTS                                                               │
 │  • Forced tool_use (tool_choice=tool) — Claude always returns structured output  │
 │  • Redis AI cache (1h TTL) — eliminates redundant Claude calls                   │
 │  • Trust score incremental mean — proper weighted history, not running average   │
 │  • Slack webhook — CRITICAL deviations notify on-call instantly                  │
 │  • Prometheus /metrics — drop into Grafana for real monitoring                   │
 │  • WebSocket exponential backoff — min(1s×2^n, 30s) on reconnect                 │
 │  • Dashboard v3 — sticky topnav with live pill, severity-colored left bars,      │
 │                   shimmer skeleton loaders, rgba border system, clean dark UI    │
 │  • AI output humanized — no emojis, no markdown noise, plain professional prose  │
 │  • AI panel: ontology constraints shown, copy button, token + latency footer     │
 │  • Deviation trend chart — 7-day stacked bar (CRITICAL / HIGH / MEDIUM)          │
 │  • Supplier health heatmap — trust score grid with progress bars                 │
 │  • MTTR KPI card — avg time from detection to resolution (server-computed)       │
 │  • /alerts/trend endpoint — daily deviation counts grouped by severity           │
 │  • /actions/stats endpoint — MTTR computed via SQL join on deviations table      │
 │  • AI panel converted to right-side drawer (420px) — no more full-screen modal   │
 │  • Severity filter (ALL/CRITICAL/HIGH/MEDIUM) on Deviation feed                  │
 │  • CSV export button on Order table — downloads visible rows as dated .csv       │
 │  • Grafana dashboard (port 3002) — pre-built supply chain panels, PostgreSQL     │
 │    datasource auto-provisioned; stat cards, barchart, supplier table, alert log  │
 │  • Seed timestamps fixed — MTTR now realistic (~15 min vs hours before)          │
 └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Dagster Medallion Pipeline — 14 Assets

```
  CSV Sources ──► batch_loader
                       │
                       ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  BRONZE (raw ingest)                                           │
  │  bronze_orders  bronze_freight_rates  bronze_wh_capacities     │
  │  bronze_plant_ports  bronze_products_per_plant                 │
  └──────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  SILVER (cleaned)                                              │
  │  silver_orders  silver_freight_rates  silver_wh_capacities     │
  └──────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  QUALITY GATE (Great Expectations)                             │
  │  quality_gate_silver_orders                                    │
  │  • not_null checks  • value range checks  • status in_set      │
  └──────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  dbt TRANSFORMS                                                │
  │  stg_orders → fct_shipments → dim_suppliers                    │
  └──────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  GOLD (AI-ready)                                               │
  │  gold_orders_ai_ready    gold_deviations    gold_supplier_risk │
  │  gold_forecasted_risks                                         │
  │    weight = exp(-days_old/90)                                  │
  │    delay_prob = Σ(is_delayed × weight) / Σ(weight)             │
  │    risk_score = order_value × delay_prob × urgency             │
  └────────────────────────────────────────────────────────────────┘
```

Runs on a **6-hour schedule** automatically. Trigger manually via Dagster UI.

---

## Stack

| Layer | Technology |
|---|---|
| Event Streaming | Apache Kafka + Zookeeper |
| Operational DB | PostgreSQL 15 |
| Cache / Pub-Sub | Redis 7 |
| Data Lake | Delta Lake, MinIO (S3-compatible), PyArrow, Parquet |
| Orchestration | Dagster (14 software-defined assets) |
| Data Quality | Great Expectations |
| SQL Transforms | dbt |
| AI | Anthropic Claude Sonnet 4.6 — `tool_use` + SSE streaming |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| Frontend | Next.js 14 App Router, TailwindCSS, Recharts, WebSocket |
| Infrastructure | Docker Compose (10 services) |
| CI/CD | GitHub Actions |

---

## Prerequisites

- **Docker Desktop** with Compose v2
- **Anthropic API key** — only `/ai/analyze` needs this; all other features work without it

---

## Step-by-Step: Run the Full Stack

### Step 1 — Clone and configure

```bash
git clone https://github.com/ujjwalredd/Supply-Chain.git
cd supply-chain-os
cp .env.example .env
```

Edit `.env` and set your API key:
```
ANTHROPIC_API_KEY=sk-ant-...
```

All other values in `.env` work as defaults. Do not change port numbers unless you have a conflict.

---

### Step 2 — Build and start all 10 services

```bash
docker compose up --build -d
```

First build takes ~5 minutes (downloading images + compiling dependencies). Subsequent starts use cached layers and take ~30 seconds.

---

### Step 3 — Verify all containers are healthy

```bash
docker compose ps
```

Expected — all should show `Up` or `Up (healthy)`:

```
supply-chain-postgres          Up (healthy)   ← port 5433
supply-chain-redis             Up (healthy)   ← port 6379
supply-chain-zookeeper         Up (healthy)   ← port 2181
supply-chain-kafka             Up (healthy)   ← port 9092/9093
supply-chain-minio             Up (healthy)   ← port 9000/9001
supply-chain-minio-init        Exited (0)     ← normal, runs once then exits
supply-chain-api               Up (healthy)   ← port 8000  (auto-migrated + seeded)
supply-chain-pg-writer         Up             ← consuming Kafka, writing to Postgres
supply-chain-producer          Up             ← streaming 50+ events/min
supply-chain-dagster-webserver Up             ← port 3001
supply-chain-dagster-daemon    Up             ← 6-hour pipeline scheduler
supply-chain-dashboard         Up             ← port 3000
```

> If `supply-chain-kafka` takes longer than 90 seconds, check: `docker compose logs kafka --tail=20`

---

### Step 4 — Open the dashboard

**http://localhost:3000** — dashboard, live with seeded data (120 orders, 20 alerts)

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API + Swagger | http://localhost:8000/docs |
| Dagster UI | http://localhost:3001 |
| Grafana | http://localhost:3002 (admin / admin) |
| MinIO Console | http://localhost:9001 |

MinIO login: `minioadmin` / `minioadmin`

### Grafana Dashboard

Pre-built supply chain dashboard auto-provisioned with a PostgreSQL datasource. Includes stat cards, 7-day deviation bar chart, supplier trust score table, and active alert log.

![Grafana Dashboard](assets/Grafana.png)

---

### Step 5 — Load the Brunel dataset (9,215 real orders)

```bash
# Download OrderList, FreightRates, PlantPorts, WhCapacities, ProductsPerPlant
docker compose run --rm fastapi python scripts/download_supply_chain_data.py
```

Expected:
```
Downloaded OrderList.csv — 9215 rows
Downloaded FreightRates.csv — 1532 rows
Downloaded PlantPorts.csv — 22 rows
Downloaded WhCapacities.csv — 19 rows
Downloaded ProductsPerPlant.csv — 1968 rows
```

```bash
# Ingest all CSVs into the bronze data lake
docker compose run --rm fastapi python -m ingestion.batch_loader
```

Expected:
```
INFO: Wrote 9215 rows to bronze/orders
INFO: Wrote 1532 rows to bronze/freight_rates
INFO: Wrote 19 rows to bronze/wh_capacities
INFO: Wrote 22 rows to bronze/plant_ports
INFO: Wrote 1968 rows to bronze/products_per_plant
```

---

### Step 6 — Run the Dagster pipeline

Open **http://localhost:3001** → click **Assets** (left sidebar) → click **Materialize all** (top right).

Watch all 14 assets run in order: bronze → silver → quality gate → dbt → gold.

Or trigger from the terminal:
```bash
docker compose exec dagster-webserver dagster asset materialize \
  --select "*" \
  -w /opt/dagster/app/workspace.yaml
```

---

### Step 7 — Sync gold layer to PostgreSQL

After the pipeline completes, push gold data to Postgres so the API and dashboard serve real data:

```bash
docker compose exec fastapi python scripts/sync_gold_to_postgres.py
```

Expected:
```
INFO: Orders: 9215 inserted, 0 skipped
INFO: Sync complete.
```

Safe to re-run any time — uses `INSERT ... ON CONFLICT DO NOTHING`.

---

### Step 8 — Upload to MinIO (browse the data lake)

```bash
docker compose exec fastapi python scripts/sync_data_to_minio.py
```

Then open **http://localhost:9001** → bucket `supply-chain-lakehouse` → browse `bronze/`, `silver/`, `gold/` folders.

---

## Step-by-Step: Test Everything

### Unit Tests (no Docker required)

```bash
pip install -r requirements-api.txt pytest pytest-asyncio httpx
pytest tests/ -v
```

Expected — all 50 pass:

```
tests/test_pg_writer.py::test_no_deviation_on_clean_event           PASSED
tests/test_pg_writer.py::test_medium_delay_detected                 PASSED
tests/test_pg_writer.py::test_high_delay_detected                   PASSED
tests/test_pg_writer.py::test_critical_delay_detected               PASSED
tests/test_pg_writer.py::test_medium_stockout_detected              PASSED
tests/test_pg_writer.py::test_high_stockout_detected                PASSED
tests/test_pg_writer.py::test_no_stockout_above_threshold           PASSED
tests/test_pg_writer.py::test_value_spike_anomaly_detected          PASSED
tests/test_pg_writer.py::test_no_anomaly_below_threshold            PASSED
tests/test_pg_writer.py::test_compound_delay_and_stockout           PASSED
tests/test_pg_writer.py::test_deviation_has_required_fields         PASSED
tests/test_pg_writer.py::test_deviation_ids_are_unique              PASSED
tests/test_reasoning_engine.py::test_analyze_structured_uses_tool_use         PASSED
tests/test_reasoning_engine.py::test_analyze_structured_returns_fallback_on_api_error PASSED
tests/test_reasoning_engine.py::test_analyze_structured_no_api_key            PASSED
tests/test_reasoning_engine.py::test_analysis_tool_schema_has_required_fields PASSED
tests/test_reasoning_engine.py::test_analysis_tool_options_schema             PASSED
tests/test_reasoning_engine.py::test_stream_analysis_yields_tokens            PASSED
tests/test_new_endpoints.py::test_alerts_trend_returns_7_days       PASSED
tests/test_new_endpoints.py::test_alerts_trend_fills_severity_counts PASSED
tests/test_new_endpoints.py::test_alerts_trend_unknown_severity_maps_to_medium PASSED
tests/test_new_endpoints.py::test_alerts_trend_days_param_controls_length PASSED
tests/test_new_endpoints.py::test_actions_stats_returns_mttr        PASSED
tests/test_new_endpoints.py::test_actions_stats_no_completed_actions PASSED
tests/test_new_endpoints.py::test_actions_stats_mttr_rounds_to_one_decimal PASSED
... (50 total)
```

### API Smoke Test (stack must be running)

```bash
# 1. Health
curl http://localhost:8000/health
# → {"status":"ok","service":"supply-chain-api"}

# 2. Orders
curl "http://localhost:8000/orders?limit=3" | python3 -m json.tool

# 3. Supplier risk
curl http://localhost:8000/suppliers/risk | python3 -m json.tool

# 4. Deviation alerts
curl "http://localhost:8000/alerts?executed=false&limit=5" | python3 -m json.tool

# 5. Ontology constraints
curl http://localhost:8000/ontology/constraints | python3 -m json.tool

# 6. Network graph
curl http://localhost:8000/network | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d['stats'])"
# → {'plant_count': 19, 'port_count': 11, 'edge_count': 22}

# 7. Risk forecast
curl http://localhost:8000/forecasts/summary | python3 -m json.tool

# 8. Execute a recommendation (creates PendingAction)
DEV=$(curl -s "http://localhost:8000/alerts?limit=1&executed=false" | \
  python3 -c "import json,sys; print(json.load(sys.stdin)[0]['deviation_id'])")
curl -X POST "http://localhost:8000/alerts/${DEV}/dismiss"
# → {"status":"ok","executed":true,"action_id":1}

# 9. Confirm it was logged
curl http://localhost:8000/actions | python3 -m json.tool

# 10. AI analysis (requires ANTHROPIC_API_KEY in .env)
curl -X POST http://localhost:8000/ai/analyze \
  -H "Content-Type: application/json" \
  -d "{\"deviation_id\":\"${DEV}\",\"deviation_type\":\"DELAY\",\"severity\":\"HIGH\"}" \
  | python3 -m json.tool
```

### Test AI Reasoning from the Dashboard

1. Open **http://localhost:3000**
2. Find a deviation in the **Deviation Feed** — click it
3. Click **"Analyze with AI"** — Claude streams root cause + 3 trade-off options
4. Click **"Execute Recommendation"** — a `PendingAction` is created
5. Check **Actions Log** — the entry appears with timestamp and status

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/orders` | Orders — filter: `status`, `supplier_id`, `limit`, `offset` |
| `GET` | `/suppliers` | All suppliers |
| `GET` | `/suppliers/risk` | Supplier risk rankings (trust score, delay stats) |
| `GET` | `/alerts` | Deviation alerts — filter: `executed`, `severity`, `limit` |
| `GET` | `/alerts/trend` | Deviation counts per day for last N days, grouped by severity |
| `POST` | `/alerts/{id}/dismiss` | Execute recommendation → creates `PendingAction` |
| `GET` | `/actions` | Audit log of all executed recommendations |
| `GET` | `/actions/stats` | MTTR — avg minutes from deviation detection to resolution |
| `GET` | `/forecasts` | At-risk orders from gold layer |
| `GET` | `/forecasts/summary` | Forecast summary stats |
| `GET` | `/network` | Plant → Port topology (nodes, edges, stats) |
| `GET` | `/ontology/constraints` | Business rules injected into every AI call |
| `POST` | `/ai/analyze` | Claude `tool_use` analysis (full structured JSON) |
| `POST` | `/ai/analyze/stream` | Claude analysis (SSE token stream) |

### SSE Streaming

```bash
curl -N -X POST http://localhost:8000/ai/analyze/stream \
  -H "Content-Type: application/json" \
  -d '{"deviation_id":"DEV-SEED-0001","deviation_type":"DELAY","severity":"HIGH"}'
```

Each token:
```
data: {"token": "The root cause..."}
```

Final event:
```
data: {"done": true, "usage": {"input_tokens": 312, "output_tokens": 487, "analysis_time_ms": 4231}}
```

---

## Deviation Detection Rules

`pg_writer` applies these rules to every Kafka event and inserts matching deviations to Postgres:

| Type | Condition | Severity |
|---|---|---|
| DELAY | `delay_days > 0` | MEDIUM |
| DELAY | `delay_days > 7` | HIGH |
| DELAY | `delay_days > 14` | CRITICAL |
| STOCKOUT | `inventory_level < 10` | MEDIUM |
| STOCKOUT | `inventory_level < 5` | HIGH |
| ANOMALY | `order_value > $100,000` | MEDIUM |

Multiple deviations can fire for the same order (compound events).

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Claude API key — only `/ai/analyze` needs this |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model ID |
| `DATABASE_URL` | `postgresql://supplychain:supplychain_secret@postgres:5432/supply_chain_db` | Postgres |
| `REDIS_URL` | `redis://redis:6379/0` | Redis for WebSocket pub/sub |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001` | Allowed CORS origins |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker (internal Docker DNS) |
| `PG_WRITER_BATCH_SIZE` | `10` | Events per batch in pg_writer consumer |
| `POSTGRES_PORT` | `5433` | Host port for Postgres (avoids conflict with local installs on 5432) |
| `MINIO_ROOT_USER` | `minioadmin` | MinIO access key |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | MinIO secret key |
| `S3_STORAGE_BUCKET` | `supply-chain-lakehouse` | MinIO bucket name |
| `UVICORN_WORKERS` | `1` | Uvicorn worker count (Redis pub/sub is multi-worker safe) |

---

## Troubleshooting

**API container unhealthy / restarting**
```bash
docker compose logs fastapi --tail=40
```
Common causes: Postgres or Redis not yet ready (the `depends_on` healthchecks handle this — wait 30s and it self-recovers).

**Port conflict on 5432**
Local PostgreSQL is running on 5432. This stack maps Postgres to **5433** — no conflict. If 5433 is also taken, set `POSTGRES_PORT=5434` in `.env`.

**AI returns 503**
`ANTHROPIC_API_KEY` not set in `.env`. All other endpoints work without it.

**Dagster UI blank / not loading**
Takes 1–2 minutes after Kafka and Postgres are healthy. Reload http://localhost:3001.

**MinIO Console empty after pipeline runs**
```bash
docker compose exec fastapi python scripts/sync_data_to_minio.py
```

**pg-writer keeps restarting**
```bash
docker compose logs pg-writer --tail=20
```
Usually a Kafka timing issue on first boot — it self-recovers once Kafka is fully ready. If it persists: `docker compose restart pg-writer`.

**`docker compose` uses wrong file**
Using `docker compose` with no `-f` flag always uses `docker-compose.yml` (the full 11-service stack). That is correct — the minimal compose file has been removed.

---

## Project Structure

```
supply-chain-os/
├── api/
│   ├── main.py                    # FastAPI app, Redis subscriber loop, WebSocket, lifespan
│   ├── models.py                  # Order, Supplier, Deviation, PendingAction, OntologyConstraint
│   ├── database.py                # Async SQLAlchemy engine + session
│   ├── schemas.py                 # Pydantic request/response models
│   └── routers/
│       ├── orders.py              # GET/POST /orders
│       ├── suppliers.py           # /suppliers, /suppliers/risk
│       ├── alerts.py              # /alerts, /alerts/{id}/dismiss
│       ├── actions.py             # /actions audit log
│       ├── forecasts.py           # /forecasts
│       ├── network.py             # /network (Plant → Port SVG topology)
│       ├── ontology.py            # /ontology/constraints
│       └── ai.py                  # /ai/analyze (tool_use) + /ai/analyze/stream (SSE)
├── dashboard/                     # Next.js 14 App Router
│   ├── app/page.tsx               # Control tower — ErrorBoundary + Suspense per panel
│   └── components/
│       ├── KPICards.tsx
│       ├── DeviationFeed.tsx      # WebSocket + Redis pub/sub live feed
│       ├── SupplierRisk.tsx       # Recharts bar chart
│       ├── RiskForecast.tsx       # At-risk orders from /forecasts
│       ├── ActionsLog.tsx         # Executed recommendations log
│       ├── SupplyChainGraph.tsx   # SVG Plant → Port network
│       ├── OrderTable.tsx         # Filterable orders table
│       ├── OntologyGraph.tsx      # Constraints list
│       ├── DeviationTrendChart.tsx # 7-day stacked bar chart by severity
│       ├── SupplierHeatmap.tsx    # Supplier trust score heatmap grid
│       ├── AIReasoningPanel.tsx   # Streaming modal — constraints shown, copy, token/latency
│       ├── ErrorBoundary.tsx      # Isolates panel render failures
│       └── PanelSkeleton.tsx      # Animated Suspense fallback
├── ingestion/
│   ├── producer.py                # Kafka: 50+ events/min, state machine, causality chains
│   ├── consumer.py                # Kafka → Delta Lake bronze (analytics path)
│   ├── pg_writer.py               # Kafka → PostgreSQL + Redis pub/sub (operational path)
│   ├── schemas.py                 # OrderEvent Pydantic model
│   └── batch_loader.py            # CSV → bronze Parquet (all 5 datasets)
├── pipeline/
│   ├── assets_medallion.py        # 14 Dagster software-defined assets
│   └── definitions_medallion.py   # Definitions object + 6-hour ScheduleDefinition
├── reasoning/
│   └── engine.py                  # Claude tool_use + SSE streaming + token tracking
├── transforms/
│   └── models/
│       ├── staging/               # stg_orders.sql, stg_suppliers.sql
│       └── marts/                 # fct_shipments.sql, dim_suppliers.sql
├── quality/
│   └── validations.py             # Great Expectations checks (not_null, between, in_set)
├── scripts/
│   ├── seed_db.py                 # 8 suppliers, 120 orders, 20 deviations, 7 constraints
│   ├── sync_gold_to_postgres.py   # Gold/bronze Parquet → Postgres (idempotent upsert)
│   ├── sync_data_to_minio.py      # Local Parquet → MinIO bucket (boto3)
│   └── download_supply_chain_data.py
├── tests/
│   ├── test_pg_writer.py          # 12 deviation detection unit tests
│   ├── test_reasoning_engine.py   # 6 Claude tool_use unit tests
│   └── test_api_health.py         # API endpoint tests
├── alembic/
│   └── versions/
│       ├── 001_initial_schema.py  # Orders, suppliers, deviations, ontology
│       └── 002_add_pending_actions.py  # pending_actions table
├── docker/
│   ├── FastAPI.Dockerfile         # Runs entrypoint.sh → migrate + seed + uvicorn
│   ├── Dagster.Dockerfile
│   ├── Nextjs.Dockerfile
│   ├── Producer.Dockerfile        # Used by both producer and pg-writer
│   └── entrypoint.sh              # alembic upgrade head → seed_db → uvicorn
├── .github/
│   └── workflows/ci.yml           # docker build + ruff + pytest (50) + tsc --noEmit
├── docker-compose.yml             # Full 11-service production stack (incl. Grafana)
├── requirements-api.txt           # FastAPI + SQLAlchemy + Anthropic + Redis + ...
├── requirements-ingestion.txt     # Kafka + Pydantic + Delta Lake + SQLAlchemy + Redis
├── requirements-dagster.txt       # Dagster + PySpark + dbt + Great Expectations
├── requirements.txt               # Aggregates api + ingestion requirements
├── pyproject.toml                 # ruff config
└── .env.example                   # Copy to .env and fill in ANTHROPIC_API_KEY
```

---

## License

MIT
