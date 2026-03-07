# Supply Chain AI Operating System — v2.0

> Prototype inspired by [Auger](https://auger.com) — an AI-native supply chain control tower that collapses the gap between signal and execution.

---

## What This Does

An end-to-end supply chain AI platform running entirely in Docker. It replicates Auger's five core capabilities:

| Auger Concept | This Implementation |
|---|---|
| **Control Tower** | Next.js 14 dashboard — KPI cards, deviation feed, network graph, risk forecast |
| **Deviation Detection** | pg_writer consumes Kafka events live; 120 alerts seeded for instant demo |
| **AI Reasoning** | Claude Sonnet 4.6 via `tool_use` — structured root cause + trade-off options |
| **Ontology Layer** | 7 business rules injected into every AI call |
| **Action Execution** | Every executed recommendation persisted as an auditable `PendingAction` |

**Operator flow:**
```
Alert fires in Deviation Feed
  → Click "Analyze with AI"
  → Claude streams root cause + 3 trade-off options (structured tool_use output)
  → Click "Execute Recommendation"
  → PendingAction written to DB → Actions Log updates in real time
```

---

## Prerequisites

- Docker Desktop with Compose v2 — that's it
- Anthropic API key — only `/ai/analyze` needs it; everything else works without it

---

## Quick Start (Minimal Stack — Recommended for Demo)

Runs Postgres + Redis + FastAPI + Next.js. Auto-migrates and seeds on startup.

```bash
git clone https://github.com/ujjwalredd/Supply-Chain.git
cd supply-chain-os
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY=sk-ant-...

docker compose -f docker-compose.minimal.yml up --build -d
```

Wait ~30 seconds for the API to finish migrations and seeding, then open:

| URL | What |
|---|---|
| http://localhost:3000 | Dashboard (live with seeded data) |
| http://localhost:8000/docs | API Swagger |

The dashboard loads immediately with **8 suppliers · 120 orders · 20 deviations · 7 ontology constraints** — no extra steps.

Always use `-f docker-compose.minimal.yml` with this stack:
```bash
docker compose -f docker-compose.minimal.yml ps
docker compose -f docker-compose.minimal.yml logs fastapi -f
docker compose -f docker-compose.minimal.yml down
```

---

## Full Stack (10 Services — Includes Kafka, Dagster, MinIO)

```bash
docker compose up --build -d
docker compose ps
```

Wait for all containers to be healthy (Kafka takes ~60s):

| Container | Status |
|---|---|
| supply-chain-postgres | Up (healthy) |
| supply-chain-redis | Up (healthy) |
| supply-chain-kafka | Up (healthy) |
| supply-chain-minio | Up (healthy) |
| supply-chain-api | Up (healthy) |
| supply-chain-pg-writer | Up |
| supply-chain-producer | Up |
| supply-chain-dagster-webserver | Up |
| supply-chain-dagster-daemon | Up |
| supply-chain-dashboard | Up |

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API + Swagger | http://localhost:8000/docs |
| Dagster UI | http://localhost:3001 |
| MinIO Console | http://localhost:9001 (login: `minioadmin` / `minioadmin`) |
| PostgreSQL | localhost:5433 |

The API auto-migrates and seeds on every start — no manual seed step needed.

### Load the Brunel dataset + run the pipeline

```bash
# Download Brunel University LogisticsDataset (OrderList, FreightRates, etc.)
docker compose run --rm fastapi python scripts/download_supply_chain_data.py

# Ingest CSVs into the bronze data lake
docker compose run --rm fastapi python -m ingestion.batch_loader
```

Then open **http://localhost:3001** → Assets → Materialize all.
This runs the 14-asset medallion pipeline: bronze → silver → quality gate → dbt → gold.

After the pipeline completes, sync gold to Postgres:
```bash
docker compose exec fastapi python scripts/sync_gold_to_postgres.py
```

And upload to MinIO for browsing:
```bash
docker compose exec fastapi python scripts/sync_data_to_minio.py
```

---

## Architecture

```
Kafka Producer ──────────────────────────────────────────────────────────────┐
(50+ events/min,                                                              │
 DELAY->STOCKOUT causality,                                                   │
 supplier state machine)                                                      │
        │                                                                     │
        ├──> pg_writer ──> PostgreSQL ──> FastAPI ──> Next.js :3000           │
        │    (deviation          │         :8000       Dashboard               │
        │     detection,         │                                            │
        │     trust scores)      └──> Redis pub/sub ──> WebSocket broadcast   │
        │                                                                     │
        └──> Delta Lake bronze ──> DAGSTER (14 assets) ──────────────────────┘
                                   silver + quality gate
                                   dbt transforms
                                   gold_forecasted_risks
                                        │
                                        └──> MinIO :9001 (data lake browser)

CSV Sources (OrderList, FreightRates, PlantPorts, WhCapacities, ProductsPerPlant)
──> ingestion.batch_loader ──> bronze ──> same Dagster pipeline above
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/orders` | Orders (filter: status, supplier_id, limit, offset) |
| `GET` | `/suppliers` | All suppliers |
| `GET` | `/suppliers/risk` | Supplier risk rankings |
| `GET` | `/alerts` | Deviation alerts (filter: executed, severity, limit) |
| `POST` | `/alerts/{id}/dismiss` | Execute recommendation → creates PendingAction |
| `GET` | `/actions` | Audit log of all executed recommendations |
| `GET` | `/forecasts` | At-risk orders from gold layer |
| `GET` | `/forecasts/summary` | Forecast summary |
| `GET` | `/network` | Plant → Port topology |
| `GET` | `/ontology/constraints` | Business rules injected into AI calls |
| `POST` | `/ai/analyze` | Claude analysis via tool_use (full JSON) |
| `POST` | `/ai/analyze/stream` | Claude analysis (SSE streaming) |

### AI Analysis

```bash
# Structured output via tool_use
curl -X POST http://localhost:8000/ai/analyze \
  -H "Content-Type: application/json" \
  -d '{"deviation_id":"DEV-0001","deviation_type":"DELAY","severity":"HIGH"}'

# SSE streaming
curl -N -X POST http://localhost:8000/ai/analyze/stream \
  -H "Content-Type: application/json" \
  -d '{"deviation_id":"DEV-0001","deviation_type":"DELAY","severity":"HIGH"}'
```

SSE stream ends with:
```
data: {"done": true, "usage": {"input_tokens": 312, "output_tokens": 487, "analysis_time_ms": 4231}}
```

---

## v2.0 Changes

### pg_writer — Operational Data Path
`ingestion/pg_writer.py` consumes Kafka events, upserts orders/suppliers to Postgres, detects deviations, updates supplier trust scores, and publishes to Redis in real time. v1 only wrote to Delta Lake — the live dashboard had no real-time data.

Deviation thresholds:

| Type | Condition | Severity |
|---|---|---|
| DELAY | delay_days > 0 | MEDIUM |
| DELAY | delay_days > 7 | HIGH |
| DELAY | delay_days > 14 | CRITICAL |
| STOCKOUT | inventory_level < 10 | MEDIUM |
| STOCKOUT | inventory_level < 5 | HIGH |
| ANOMALY | order_value > $100,000 | MEDIUM |

### Redis Pub/Sub WebSocket
v1 used an in-process set that broke with `--workers > 1`. v2 routes all WebSocket broadcasts through Redis (`deviations` channel), making it multi-worker safe.

### Claude tool_use Structured Output
v1 called Claude with free-form text and tried `json.loads()` with markdown-stripping fallbacks. v2 uses `tool_use` with a typed JSON schema — guaranteed structured output, no parsing fragility.

### Migration 002 + Auto-seeding Entrypoint
`alembic/versions/002_add_pending_actions.py` — the table existed in models.py but had no migration in v1, causing the API to crash on the first `POST /alerts/{id}/dismiss`. The entrypoint now runs `alembic upgrade head` + `seed_db.py` automatically on every start.

### Test Suite — 43 tests, 0 warnings
- `tests/test_pg_writer.py` — 12 tests covering all deviation detection cases
- `tests/test_reasoning_engine.py` — 6 tests covering tool_use extraction, API error fallback, schema validation

---

## Medallion Lakehouse — 14 Dagster Assets

| Asset | Layer | Description |
|---|---|---|
| `bronze_orders` | Bronze | OrderList.csv → Parquet |
| `bronze_freight_rates` | Bronze | FreightRates.csv → Parquet |
| `bronze_wh_capacities` | Bronze | WhCapacities.csv → Parquet |
| `bronze_plant_ports` | Bronze | PlantPorts.csv → Parquet |
| `bronze_products_per_plant` | Bronze | ProductsPerPlant.csv → Parquet |
| `silver_orders` | Silver | Clean + validate orders |
| `silver_freight_rates` | Silver | Remove extreme outliers |
| `silver_wh_capacities` | Silver | Normalise capacity values |
| `quality_gate_silver_orders` | Quality | Great Expectations: not_null, value ranges, status in_set |
| `dbt_transforms` | Transform | `dbt run` — staging + fct_shipments + dim_suppliers |
| `gold_orders_ai_ready` | Gold | Enrich with risk score, delay flag, lead time |
| `gold_deviations` | Gold | Identify deviations above threshold |
| `gold_supplier_risk` | Gold | Trust scores, avg delay, on-time rate per supplier |
| `gold_forecasted_risks` | Gold | Time-decay ML: `delay_probability × order_value × urgency` |

Time-decay model:
```
weight      = exp(-days_old / 90)
delay_prob  = Σ(is_delayed × weight) / Σ(weight)
confidence  = 1 − 1/√n_orders
risk_score  = order_value × delay_prob × (1 / days_to_delivery)
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Claude API key (only `/ai/analyze` needs this) |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model |
| `DATABASE_URL` | `postgresql://supplychain:supplychain_secret@postgres:5432/supply_chain_db` | Postgres |
| `REDIS_URL` | `redis://redis:6379/0` | Redis for WebSocket pub/sub |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001` | Allowed CORS origins |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker |
| `PG_WRITER_BATCH_SIZE` | `10` | Events per batch in pg_writer |
| `POSTGRES_PORT` | `5433` | Host port for Postgres |
| `UVICORN_WORKERS` | `1` | Worker count (Redis pub/sub is multi-worker safe) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| Streaming | Kafka, Redis pub/sub, WebSocket, SSE |
| AI | Anthropic Claude Sonnet 4.6 — tool_use + SSE streaming |
| Data | PostgreSQL 15, Delta Lake, dbt, Pandas, PyArrow |
| Orchestration | Dagster (14 software-defined assets, 6-hour schedule) |
| Quality | Great Expectations |
| Frontend | Next.js 14 App Router, TailwindCSS, Recharts, SVG graph |
| Infrastructure | Docker Compose, MinIO, Redis |
| CI/CD | GitHub Actions — Docker build + ruff + pytest (43 tests) + tsc |

---

## Skills Demonstrated

| Domain | Technology |
|---|---|
| Data Engineering | Medallion lakehouse, Delta Lake, Parquet, batch + stream ingest |
| Orchestration | Dagster 14 SDAs, 6-hour schedule |
| Data Quality | Great Expectations on silver layer |
| SQL / dbt | Staging + fact + dimension models |
| ML Scoring | Time-decay delay probability, per-supplier confidence, composite risk score |
| Event Simulation | Kafka state machine (NORMAL→DEGRADING→CRITICAL), causality chains |
| AI / LLM | Claude tool_use structured output, SSE streaming, ontology injection |
| Backend | FastAPI async, SQLAlchemy 2.0, Alembic, Pydantic v2, WebSocket |
| Frontend | Next.js 14 App Router, Recharts, ErrorBoundary, AbortController |
| Infrastructure | Docker Compose, Redis, MinIO, PostgreSQL 15 |
| CI/CD | GitHub Actions — build, lint, test, type-check |

---

## Project Structure

```
supply-chain-os/
├── api/
│   ├── main.py                   # FastAPI app, Redis subscriber loop, WebSocket, CORS
│   ├── models.py                 # Order, Supplier, Deviation, PendingAction, OntologyConstraint
│   ├── schemas.py                # Pydantic request/response types
│   └── routers/
│       ├── orders.py, suppliers.py, alerts.py, actions.py
│       ├── forecasts.py, network.py, ontology.py
│       └── ai.py                 # /ai/analyze (tool_use) + /ai/analyze/stream (SSE)
├── dashboard/                    # Next.js 14
│   ├── app/page.tsx              # Control tower (ErrorBoundary + Suspense per panel)
│   └── components/
│       ├── KPICards, DeviationFeed, SupplierRisk, RiskForecast
│       ├── ActionsLog, SupplyChainGraph, OrderTable, OntologyGraph
│       ├── AIReasoningPanel.tsx  # Streaming modal (abort, copy, token badge)
│       ├── ErrorBoundary.tsx
│       └── PanelSkeleton.tsx
├── pipeline/
│   ├── assets_medallion.py       # 14 Dagster assets
│   └── definitions_medallion.py  # Definitions + 6-hour schedule
├── ingestion/
│   ├── producer.py               # Kafka producer: 50+ events/min, state machine, causality
│   ├── consumer.py               # Kafka → Delta Lake bronze
│   ├── pg_writer.py              # Kafka → PostgreSQL + Redis pub/sub (v2)
│   ├── schemas.py                # OrderEvent Pydantic model
│   └── batch_loader.py           # CSV → bronze Parquet
├── reasoning/
│   └── engine.py                 # Claude tool_use + stream + token tracking
├── transforms/dbt/models/        # staging/, marts/
├── quality/validations.py        # Great Expectations checks
├── scripts/
│   ├── seed_db.py                # 8 suppliers, 120 orders, 20 deviations, 7 constraints
│   ├── sync_gold_to_postgres.py
│   ├── sync_data_to_minio.py
│   └── download_supply_chain_data.py
├── tests/
│   ├── test_pg_writer.py         # 12 deviation detection tests
│   └── test_reasoning_engine.py  # 6 Claude tool_use tests
├── alembic/versions/
│   ├── 001_initial_schema.py
│   └── 002_add_pending_actions.py
├── docker/
│   ├── FastAPI.Dockerfile        # Runs entrypoint.sh
│   ├── Dagster.Dockerfile
│   ├── Nextjs.Dockerfile
│   ├── Producer.Dockerfile
│   └── entrypoint.sh             # alembic upgrade + seed + uvicorn
├── .github/workflows/ci.yml      # CI: docker build + ruff + pytest + tsc
├── docker-compose.yml            # Full 10-service stack
├── docker-compose.minimal.yml    # Postgres + Redis + API + Dashboard
├── requirements.txt              # includes requirements-api.txt + requirements-ingestion.txt
├── requirements-api.txt
├── requirements-ingestion.txt
├── requirements-dagster.txt
└── .env.example
```

---

## Troubleshooting

**Port 5432 already in use**
Local Postgres is running. Both compose files map Postgres to host port `5433` — this should not conflict. If it does:
```bash
# Check what's on 5432
lsof -i :5432
```

**API container unhealthy / crashing**
```bash
docker compose logs fastapi --tail=40
# or for minimal stack:
docker compose -f docker-compose.minimal.yml logs fastapi --tail=40
```

**AI returns 503**
`ANTHROPIC_API_KEY` not set in `.env`. All other endpoints work without it.

**Dagster UI blank**
Takes 1–2 minutes after Postgres + Kafka are healthy. Reload http://localhost:3001.

**MinIO Console empty**
Run the sync script after the Dagster pipeline completes:
```bash
docker compose exec fastapi python scripts/sync_data_to_minio.py
```

**pg-writer restarting**
Check logs: `docker compose logs pg-writer --tail=20`. Usually a Kafka not-ready race — it will self-recover once Kafka is fully healthy.

---

## License

MIT
