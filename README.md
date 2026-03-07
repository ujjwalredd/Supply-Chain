# Supply Chain AI Operating System — v2.0

> Prototype inspired by [Auger](https://auger.com) — an AI-native supply chain control tower that collapses the gap between signal and execution.

---

## What This Does

An end-to-end supply chain AI platform running entirely in Docker. Replicates Auger's five core capabilities:

| Auger Concept | This Implementation |
|---|---|
| **Control Tower** | Next.js 14 dashboard — KPI cards, deviation feed, network graph, risk forecast |
| **Deviation Detection** | pg_writer consumes Kafka events live; 120 alerts seeded for instant demo |
| **AI Reasoning** | Claude Sonnet 4.6 via `tool_use` — structured root cause + trade-off options |
| **Ontology Layer** | 7 business rules injected into every AI call |
| **Action Execution** | Every executed recommendation persisted as an auditable `PendingAction` |

---

## Prerequisites

- **Docker Desktop** (with Compose v2) — that's it for running
- **Anthropic API key** — only the AI analysis endpoints need this; everything else works without it
- **Python 3.11** — only needed to run the unit tests locally

---

## Option A — Minimal Stack (Recommended for Demo / CEO Presentation)

Runs **4 containers**: Postgres + Redis + FastAPI + Next.js dashboard.
Auto-migrates the database and seeds all sample data on startup. No manual steps after `up`.

### Step 1 — Clone and configure

```bash
git clone https://github.com/ujjwalredd/Supply-Chain.git
cd supply-chain-os
cp .env.example .env
```

Open `.env` and set:
```
ANTHROPIC_API_KEY=sk-ant-...
```

> If you skip the API key, everything works except the AI analysis modal.

### Step 2 — Start the stack

```bash
docker compose -f docker-compose.minimal.yml up --build -d
```

### Step 3 — Wait for healthy status (~30 seconds)

```bash
docker compose -f docker-compose.minimal.yml ps
```

Expected output:
```
NAME           STATUS
sc-postgres    Up (healthy)
sc-redis       Up (healthy)
sc-api         Up (healthy)
sc-dashboard   Up
```

If `sc-api` is still starting, watch it live:
```bash
docker compose -f docker-compose.minimal.yml logs fastapi -f
```
You should see `==> Seeding database...` then `==> Starting Supply Chain API...`.

### Step 4 — Open the dashboard

**http://localhost:3000**

You will see:
- **KPI Cards** — pipeline value, on-time %, delayed orders, critical alerts
- **Deviation Feed** — 20 live alerts (DELAY / STOCKOUT / ANOMALY)
- **Supplier Risk** — bar chart ranked by trust score (8 suppliers)
- **Risk Forecast** — at-risk orders scored by delay probability × order value
- **Actions Log** — executed recommendations audit trail
- **Orders Table** — 120 orders, filterable by status / supplier
- **Supply Chain Network** — Plant → Port topology SVG
- **Ontology Constraints** — 7 business rules

**API Swagger**: **http://localhost:8000/docs**

### Step 5 — Test AI reasoning

1. Click any deviation in the **Deviation Feed**
2. Click **"Analyze with AI"**
3. Claude streams root cause + trade-off options in real time
4. Click **"Execute Recommendation"** — creates a PendingAction
5. Check **Actions Log** — the executed action appears

Or test via curl:
```bash
# Pick a deviation ID
curl -s "http://localhost:8000/alerts?limit=1&executed=false" | python3 -m json.tool

# Run AI analysis (structured tool_use output)
curl -X POST http://localhost:8000/ai/analyze \
  -H "Content-Type: application/json" \
  -d '{"deviation_id":"DEV-SEED-0001","deviation_type":"DELAY","severity":"HIGH"}'

# Execute the recommendation
curl -X POST "http://localhost:8000/alerts/DEV-SEED-0001/dismiss"

# Confirm it was logged
curl http://localhost:8000/actions | python3 -m json.tool
```

### Stop the minimal stack

```bash
docker compose -f docker-compose.minimal.yml down
```

---

## Option B — Full Stack (10 Services — Kafka, Dagster, MinIO)

Adds live Kafka event streaming, the 14-asset Dagster pipeline, and MinIO data lake browser.

### Step 1 — Clone and configure (same as above)

```bash
git clone https://github.com/ujjwalredd/Supply-Chain.git
cd supply-chain-os
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env
```

### Step 2 — Start all 10 services

```bash
docker compose up --build -d
```

### Step 3 — Wait for healthy status (~60–90 seconds)

```bash
docker compose ps
```

Expected — all should show `Up` or `Up (healthy)`:
```
supply-chain-postgres          Up (healthy)
supply-chain-redis             Up (healthy)
supply-chain-zookeeper         Up (healthy)
supply-chain-kafka             Up (healthy)
supply-chain-minio             Up (healthy)
supply-chain-minio-init        Exited (0)    ← normal, runs once then exits
supply-chain-api               Up (healthy)
supply-chain-pg-writer         Up
supply-chain-producer          Up
supply-chain-dagster-webserver Up
supply-chain-dagster-daemon    Up
supply-chain-dashboard         Up
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API + Swagger | http://localhost:8000/docs |
| Dagster UI | http://localhost:3001 |
| MinIO Console | http://localhost:9001 — login: `minioadmin` / `minioadmin` |
| PostgreSQL | localhost:5433 |

The API auto-migrates and seeds on startup — no manual seed step needed.

### Step 4 — Load the real dataset (optional, for 9,215 real orders)

```bash
# Download Brunel University LogisticsDataset
docker compose run --rm fastapi python scripts/download_supply_chain_data.py

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

### Step 5 — Run the Dagster pipeline

Open **http://localhost:3001** → click **Assets** → click **Materialize all**

This runs 14 assets in order: bronze → silver → quality gate → dbt → gold.
The pipeline also runs automatically every **6 hours**.

### Step 6 — Sync gold layer to PostgreSQL

```bash
docker compose exec fastapi python scripts/sync_gold_to_postgres.py
```

Expected:
```
INFO: Orders: 9215 inserted, 0 skipped
INFO: Sync complete.
```

### Step 7 — Upload to MinIO (optional)

```bash
docker compose exec fastapi python scripts/sync_data_to_minio.py
```

Then browse **http://localhost:9001** → bucket `supply-chain-lakehouse` → bronze / silver / gold folders.

### Stop the full stack

```bash
docker compose down
```

---

## Running the Unit Tests

No Docker or live services needed — tests are pure unit tests with mocked dependencies.

### Step 1 — Install test dependencies

```bash
pip install -r requirements-api.txt pytest pytest-asyncio httpx
```

### Step 2 — Run all 43 tests

```bash
pytest tests/ -v
```

Expected output:
```
tests/test_api_health.py::test_health_returns_ok                     PASSED
tests/test_api_health.py::test_root_lists_endpoints                  PASSED
...
tests/test_pg_writer.py::test_no_deviation_on_clean_event            PASSED
tests/test_pg_writer.py::test_medium_delay_detected                  PASSED
tests/test_pg_writer.py::test_high_delay_detected                    PASSED
tests/test_pg_writer.py::test_critical_delay_detected                PASSED
tests/test_pg_writer.py::test_medium_stockout_detected               PASSED
tests/test_pg_writer.py::test_high_stockout_detected                 PASSED
tests/test_pg_writer.py::test_no_stockout_above_threshold            PASSED
tests/test_pg_writer.py::test_value_spike_anomaly_detected           PASSED
tests/test_pg_writer.py::test_no_anomaly_below_threshold             PASSED
tests/test_pg_writer.py::test_compound_delay_and_stockout            PASSED
tests/test_pg_writer.py::test_deviation_has_required_fields          PASSED
tests/test_pg_writer.py::test_deviation_ids_are_unique               PASSED
tests/test_reasoning_engine.py::test_analyze_structured_uses_tool_use PASSED
tests/test_reasoning_engine.py::test_analyze_structured_returns_fallback_on_api_error PASSED
tests/test_reasoning_engine.py::test_analyze_structured_no_api_key   PASSED
tests/test_reasoning_engine.py::test_analysis_tool_schema_has_required_fields PASSED
tests/test_reasoning_engine.py::test_analysis_tool_options_schema    PASSED
tests/test_reasoning_engine.py::test_stream_analysis_yields_tokens   PASSED
43 passed in X.XXs
```

### Run just a specific test file

```bash
pytest tests/test_pg_writer.py -v        # deviation detection logic
pytest tests/test_reasoning_engine.py -v # Claude tool_use logic
pytest tests/test_api_health.py -v       # API health endpoints
```

---

## Smoke Test — Verify All Endpoints

Run this after the stack is up to confirm everything is working:

```bash
# 1. Health check
curl http://localhost:8000/health
# → {"status":"ok","service":"supply-chain-api"}

# 2. Orders (120 seeded)
curl "http://localhost:8000/orders?limit=3" | python3 -m json.tool

# 3. Supplier risk (8 suppliers)
curl http://localhost:8000/suppliers/risk | python3 -m json.tool

# 4. Active deviation alerts (20 seeded)
curl "http://localhost:8000/alerts?executed=false&limit=5" | python3 -m json.tool

# 5. Ontology constraints (7 rules)
curl http://localhost:8000/ontology/constraints | python3 -m json.tool

# 6. Network graph
curl http://localhost:8000/network | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['stats'])"
# → {'plant_count': 19, 'port_count': 11, 'edge_count': 22}

# 7. Risk forecast
curl http://localhost:8000/forecasts/summary | python3 -m json.tool

# 8. Execute a recommendation (creates PendingAction)
DEV=$(curl -s "http://localhost:8000/alerts?limit=1&executed=false" | \
  python3 -c "import json,sys; print(json.load(sys.stdin)[0]['deviation_id'])")
curl -X POST "http://localhost:8000/alerts/${DEV}/dismiss"
# → {"status":"ok","executed":true,"action_id":1}

# 9. Confirm action was logged
curl http://localhost:8000/actions | python3 -m json.tool

# 10. AI analysis (requires ANTHROPIC_API_KEY)
curl -X POST http://localhost:8000/ai/analyze \
  -H "Content-Type: application/json" \
  -d "{\"deviation_id\":\"${DEV}\",\"deviation_type\":\"DELAY\",\"severity\":\"HIGH\"}" \
  | python3 -m json.tool
```

---

## Architecture

```
Kafka Producer ──────────────────────────────────────────────────────────────┐
(50+ events/min,                                                             │
 DELAY->STOCKOUT causality,                                                  │
 supplier state machine)                                                     │
        │                                                                    │
        ├──> pg_writer ──> PostgreSQL <──> FastAPI :8000 <──> Next.js :3000  │
        │    (deviation          │                                           │
        │     detection,         └──> Redis pub/sub ──> WebSocket broadcast  │
        │     trust scores)                                                  │
        │                                                                    │
        └──> Delta Lake bronze ──> DAGSTER (14 assets) ──────────────────────┘
                                   silver + quality gate + dbt + gold
                                        │
                                        └──> MinIO :9001 (data lake browser)

CSV Sources (OrderList, FreightRates, PlantPorts, WhCapacities, ProductsPerPlant)
──> ingestion.batch_loader ──> bronze ──> same Dagster pipeline
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
| `POST` | `/ai/analyze/stream` | Claude analysis (SSE token stream) |

---

## v2.0 Key Changes

| Change | Details |
|---|---|
| **pg_writer** | New Kafka→Postgres writer: deviation detection, trust score updates, Redis pub/sub publish |
| **Redis pub/sub WebSocket** | Multi-worker safe broadcast (v1 used an in-process set that broke with >1 worker) |
| **Claude tool_use** | Structured output via tool schema — no fragile `json.loads()` parsing |
| **Migration 002** | `pending_actions` table was in models.py but had no migration in v1 — API crashed on first action |
| **Auto-seeding entrypoint** | `alembic upgrade head` + `seed_db.py` run automatically on every container start |
| **Richer seed data** | 8 suppliers, 120 orders, 20 deviations, 5 pending actions, 7 ontology constraints |
| **43 unit tests** | 12 deviation detection tests + 6 Claude tool_use tests, 0 warnings |
| **CI fix** | Removed invalid `--parallel` flag from `docker compose build` |

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
| `POSTGRES_PORT` | `5433` | Host port for Postgres (avoids conflict with local installs) |
| `UVICORN_WORKERS` | `1` | Worker count (Redis pub/sub is multi-worker safe) |

---

## Troubleshooting

**`sc-api` stays unhealthy**
```bash
docker compose -f docker-compose.minimal.yml logs fastapi --tail=40
```
Common causes: Postgres not yet ready (wait longer), or missing `ANTHROPIC_API_KEY` (not required, but check for typos in `.env`).

**Port 5432 already in use**
Local Postgres is running. Both compose files map Postgres to host port `5433` — not 5432. If 5433 is also taken:
```bash
# In .env:
POSTGRES_PORT=5434
```

**AI returns 503**
`ANTHROPIC_API_KEY` not set or invalid. All other endpoints work without it.

**`docker compose` picks up wrong file**
Always specify `-f docker-compose.minimal.yml` when using the minimal stack. Without `-f`, Docker uses `docker-compose.yml` (the full 10-service stack).

**Dagster UI blank**
Takes 1–2 minutes after Postgres + Kafka are healthy. Reload http://localhost:3001.

**MinIO Console empty**
Run after the Dagster pipeline completes:
```bash
docker compose exec fastapi python scripts/sync_data_to_minio.py
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| Streaming | Kafka, Redis pub/sub, WebSocket, SSE |
| AI | Anthropic Claude Sonnet 4.6 — tool_use structured output + SSE streaming |
| Data | PostgreSQL 15, Delta Lake, dbt, Pandas, PyArrow |
| Orchestration | Dagster (14 software-defined assets, 6-hour schedule) |
| Quality | Great Expectations |
| Frontend | Next.js 14 App Router, TailwindCSS, Recharts, SVG graph |
| Infrastructure | Docker Compose, MinIO, Redis |
| CI/CD | GitHub Actions — Docker build + ruff lint + pytest (43 tests) + tsc |

---

## Project Structure

```
supply-chain-os/
├── api/                     # FastAPI backend
│   ├── main.py              # App, Redis subscriber loop, WebSocket, CORS
│   ├── models.py            # Order, Supplier, Deviation, PendingAction, OntologyConstraint
│   └── routers/             # orders, suppliers, alerts, actions, forecasts, network, ontology, ai
├── dashboard/               # Next.js 14 control tower
│   └── components/          # KPICards, DeviationFeed, AIReasoningPanel, SupplierRisk, ...
├── ingestion/
│   ├── producer.py          # Kafka: 50+ events/min, state machine, causality chains
│   ├── pg_writer.py         # Kafka → PostgreSQL + Redis pub/sub (v2)
│   └── schemas.py           # OrderEvent Pydantic model
├── pipeline/
│   └── assets_medallion.py  # 14 Dagster assets: bronze → silver → dbt → gold
├── reasoning/
│   └── engine.py            # Claude tool_use + SSE stream + token tracking
├── scripts/
│   ├── seed_db.py           # 8 suppliers, 120 orders, 20 deviations, 7 constraints
│   ├── sync_gold_to_postgres.py
│   └── sync_data_to_minio.py
├── tests/
│   ├── test_pg_writer.py         # 12 deviation detection tests
│   ├── test_reasoning_engine.py  # 6 Claude tool_use tests
│   └── test_api_health.py        # API health + endpoint tests
├── alembic/versions/
│   ├── 001_initial_schema.py
│   └── 002_add_pending_actions.py
├── docker/
│   ├── FastAPI.Dockerfile   # Runs entrypoint.sh (migrate + seed + uvicorn)
│   ├── entrypoint.sh
│   ├── Dagster.Dockerfile
│   ├── Nextjs.Dockerfile
│   └── Producer.Dockerfile
├── .github/workflows/ci.yml # CI: docker build + ruff + pytest + tsc
├── docker-compose.yml       # Full 10-service stack
├── docker-compose.minimal.yml # Postgres + Redis + API + Dashboard
└── .env.example
```

---

## License

MIT
