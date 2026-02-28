# Supply Chain AI Operating System

> *Prototype inspired by [Auger](https://auger.com) — an AI-native supply chain control tower that collapses the gap between signal and execution.*

---

## What is Auger?

Auger is a next-generation supply chain AI platform (raised ~$100M, founded by Dave Clark — former Amazon Worldwide Consumer CEO and Flexport CEO). Its thesis: traditional supply chain tools surface dashboards and alerts but leave humans to manually interpret them and decide what to do. Auger collapses that gap by connecting real-time signals directly to AI reasoning that generates specific, auditable action recommendations.

| Auger Concept | What it means |
|---|---|
| **Control Tower** | Single pane of glass across all suppliers, orders, ports, and freight lanes |
| **Deviation Detection** | Automated alerts when orders deviate from expected lead times or freight rates |
| **AI Reasoning** | LLM explains *why* a deviation occurred and proposes trade-off options |
| **Ontology Layer** | Business rules (SLA limits, capacity caps, preferred routes) injected into every AI call |
| **Action Execution** | AI recommendations can be approved and executed — logged as auditable records |

This project implements all five concepts end-to-end in a fully Dockerised stack.

---

## How This Project Maps to Auger

| Auger Feature | This Implementation |
|---|---|
| Control Tower UI | Next.js 14 dashboard — KPI cards, deviation feed, network graph, risk forecast |
| Real-time signal ingest | Kafka producer → consumer → Delta Lake bronze layer (50+ events/min) |
| Deviation detection | Dagster pipeline auto-generates deviations; seeded alerts for immediate testing |
| AI root-cause reasoning | Claude Sonnet 4.6 streaming SSE — reads deviation + ontology → structured analysis |
| Ontology / business rules | `ontology_constraints` table; rules injected into every `/ai/analyze` call |
| Action execution + audit | `POST /alerts/{id}/dismiss` creates `PendingAction` record; `/actions` shows full log |
| Risk forecasting | `gold_forecasted_risks` Dagster asset; `/forecasts` endpoint; RiskForecast dashboard panel |
| Network visibility | `/network` endpoint reads PlantPorts.csv → 19 plants, 11 ports, 22 routes; SVG graph |
| Data quality gate | Great Expectations validation on every silver layer promotion |
| Medallion lakehouse | Dagster 14-asset pipeline: bronze → silver → quality gate → dbt → gold |

**Operator flow (mimics Auger's UX):**
```
Alert fires in Deviation Feed
    → Operator clicks "Analyze with AI"
    → Claude streams: root cause + 3 trade-off options
    → Operator clicks "Execute Recommendation"
    → PendingAction written to DB (deviation_id, type, payload, status=COMPLETED)
    → Actions Log panel updates in real time
```

---

## What This Builds

An end-to-end supply chain AI platform running entirely in Docker:

- **Real-time event ingestion** — Kafka producer streams 50+ supply chain events/min
- **Medallion data lake** — Dagster orchestrates bronze → silver → gold pipeline across 14 assets
- **Data quality gate** — Great Expectations validation on every silver layer promotion
- **dbt transforms** — SQL staging + mart models run as a Dagster asset
- **AI reasoning** — Claude Sonnet 4.6 analyses deviations, streams root cause + trade-off options
- **Risk forecasting** — predicts at-risk orders before delay using supplier history
- **Action audit trail** — every "Execute Recommendation" click is persisted as a PendingAction
- **Supply chain network graph** — interactive Plant → Port topology (19 plants, 11 ports)
- **Live dashboard** — Next.js control tower with WebSocket, KPI cards, deviation feed, network SVG

---

## Medallion Lakehouse — 14 Dagster Assets

| Asset | Layer | Description |
|---|---|---|
| `bronze_orders` | Bronze | Ingest OrderList.csv → Parquet |
| `bronze_freight_rates` | Bronze | Ingest FreightRates.csv → Parquet |
| `bronze_wh_capacities` | Bronze | Ingest WhCapacities.csv → Parquet |
| `bronze_plant_ports` | Bronze | Ingest PlantPorts.csv → Parquet |
| `bronze_products_per_plant` | Bronze | Ingest ProductsPerPlant.csv → Parquet |
| `silver_orders` | Silver | Clean + validate orders (drop nulls, cast types) |
| `silver_freight_rates` | Silver | Clean freight rates — remove extreme outliers |
| `silver_wh_capacities` | Silver | Normalise warehouse capacity values |
| `quality_gate_silver_orders` | Quality | Great Expectations: not_null, value ranges, status in_set |
| `dbt_transforms` | Transform | `dbt run` — staging models + fct_shipments + dim_suppliers |
| `gold_orders_ai_ready` | Gold | Enrich orders with risk score, delay flag, lead time |
| `gold_deviations` | Gold | Identify deviations (delay_days > threshold) |
| `gold_supplier_risk` | Gold | Aggregate trust scores, avg delay, on-time rate per supplier |
| `gold_forecasted_risks` | Gold | Predict at-risk orders using supplier delay history |

---

## Dashboard Panels

| Panel | Data Source | Description |
|---|---|---|
| **KPI Cards** | `/orders` aggregate | Pipeline value, on-time %, delayed count, critical alerts |
| **Deviation Feed** | `/alerts` WebSocket | Live alert list — click any row to open AI reasoning modal |
| **AI Reasoning Modal** | `/ai/analyze/stream` SSE | Claude streams root cause + trade-off options |
| **Supplier Risk** | `/suppliers/risk` | Bar chart ranked by trust score (Great Expectations validated) |
| **Risk Forecast** | `/forecasts` | Orders predicted to be late — color-coded by urgency |
| **Actions Log** | `/actions` | Every executed recommendation with timestamp + status |
| **Orders Table** | `/orders` | All 9,215+ orders — filterable by status, supplier |
| **Supply Chain Network** | `/network` | Interactive SVG: Plant → Port topology, hover for products |
| **Ontology Constraints** | `/ontology/constraints` | Hard limits injected into every AI call |

---

## API Reference

### Core Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `GET` | `/orders` | List orders (filter: `status`, `supplier_id`, `limit`, `offset`) |
| `POST` | `/orders` | Create a new order |
| `GET` | `/suppliers` | List all suppliers |
| `GET` | `/suppliers/risk` | Supplier risk rankings (trust score, delay stats) |
| `GET` | `/alerts` | List deviation alerts (filter: `executed`, `severity`, `limit`) |
| `POST` | `/alerts/{id}/dismiss` | Execute recommendation → creates PendingAction |
| `GET` | `/actions` | Audit log of all executed recommendations |
| `POST` | `/actions` | Manually create a pending action |
| `GET` | `/forecasts` | At-risk order predictions from gold layer |
| `GET` | `/forecasts/summary` | Forecast summary stats |
| `GET` | `/network` | Plant → Port topology (nodes + edges + stats) |
| `GET` | `/ontology/constraints` | Business rules injected into AI calls |
| `POST` | `/ai/analyze` | Claude analysis (full JSON response) |
| `POST` | `/ai/analyze/stream` | Claude analysis (SSE streaming) |

### AI Analysis Request

```json
POST /ai/analyze
{
  "deviation_id": "DEV-0001",
  "deviation_type": "DELAY",
  "severity": "HIGH"
}
```

### AI Streaming (SSE)

```bash
curl -N -X POST http://localhost:8000/ai/analyze/stream \
  -H "Content-Type: application/json" \
  -d '{"deviation_id":"DEV-0001","deviation_type":"DELAY","severity":"HIGH"}'
```

Streams tokens as `data: <token>\n\n` — consumed by `AIReasoningPanel.tsx` in real time.

---

## Ontology Constraints

The ontology layer is what separates Auger-style AI from raw LLM chatbots. Every `/ai/analyze` call receives the current constraints as hard rules the AI must respect.

### Brunel University LogisticsDataset (Source Data)

| Dataset | Rows | Key Columns |
|---|---|---|
| `OrderList.csv` | 9,215 | Order_ID, Origin_Port, Carrier, Service_Level, Ship_ahead_day, Ship_Late_Day, Customer, Product_ID, Plant_Code, Destination_Port, Unit_quantity, Weight |
| `FreightRates.csv` | 1,532 | Carrier, orig_port_cd, dest_port_cd, svc_cd, minimum_cost, rate, mode_dsc, tpt_day_cnt,effdt, expdt |
| `PlantPorts.csv` | 22 | Plant_Code, Ports |
| `WhCapacities.csv` | 19 | Plant_ID, Daily_Capacity |
| `ProductsPerPlant.csv` | 1,968 | Plant_Code, Product_ID |

### Derived Constraint Categories

| Category | Example Rule |
|---|---|
| **Lead Time SLA** | Max acceptable delay before escalation (e.g., 5 days) |
| **Carrier Preference** | Preferred freight carrier per route |
| **Capacity Cap** | Daily warehouse throughput limits per plant |
| **Service Level** | Standard vs. Express routing constraints |
| **Port Restrictions** | Certain plant→port routes disallowed |

### Seeded Defaults (from `seed_db.py`)

| Constraint | Default Value |
|---|---|
| `max_delay_days` | 5 |
| `preferred_carrier` | "V444" |
| `capacity_limit_per_day` | 1000 units |

---

## Skills Demonstrated

| Domain | Technology / Technique |
|---|---|
| **Data Engineering** | Medallion lakehouse, Delta Lake, PySpark, Parquet, batch + stream ingest |
| **Orchestration** | Dagster 14 software-defined assets, 6-hour schedule, sensor-ready |
| **Data Quality** | Great Expectations — not_null, between, in_set checks on silver layer |
| **SQL / dbt** | Staging models, fact + dimension mart models, incremental-ready patterns |
| **AI / LLM** | Claude Sonnet 4.6 streaming SSE, structured JSON output, RAG-style ontology injection |
| **Backend** | FastAPI, SQLAlchemy 2.0, Alembic migrations, Pydantic v2, WebSocket, SSE |
| **Frontend** | Next.js 14 App Router, TailwindCSS, Recharts, SVG network graph, polling + WebSocket |
| **Streaming** | Kafka producer/consumer, 12% anomaly injection, Delta Lake bronze sink |
| **Infrastructure** | Docker Compose 10-service stack, MinIO S3-compatible, Redis, PostgreSQL 15 |
| **Audit Trail** | PendingAction model — every AI recommendation execution is persisted and queryable |

---

## Prerequisites

- **Docker Desktop** (with Compose v2) — that's it
- **Anthropic API key** — only needed for AI analysis (`/ai/analyze`). Everything else works without it.

---

## End-to-End Setup (run this once)

### Step 1 — Clone and configure

```bash
git clone https://github.com/ujjwalredd/Supply-Chain.git
cd supply-chain-os
cp .env.example .env
```

Open `.env` and set your API key:
```
ANTHROPIC_API_KEY=sk-ant-...
```

> Everything else in `.env` works with the defaults. Don't change port numbers unless you have conflicts.

---

### Step 2 — Start the full stack

```bash
docker compose up --build -d
```

This builds and starts **10 containers**. First build takes ~5 minutes (downloading images + compiling deps).

Wait until all containers are healthy:
```bash
docker compose ps
```

Expected output — all should show `Up` or `Up (healthy)`:
```
supply-chain-api                 Up
supply-chain-dagster-daemon      Up
supply-chain-dagster-webserver   Up
supply-chain-dashboard           Up
supply-chain-kafka               Up (healthy)
supply-chain-minio               Up (healthy)
supply-chain-minio-init          Exited (0)      ← normal, init runs once then exits
supply-chain-postgres            Up (healthy)
supply-chain-producer            Up
supply-chain-redis               Up (healthy)
supply-chain-zookeeper           Up (healthy)
```

**Service URLs:**

| Service | URL | Notes |
|---------|-----|-------|
| **Dashboard** | http://localhost:3000 | Main control tower UI |
| **API + Swagger** | http://localhost:8000/docs | All REST endpoints |
| **Dagster UI** | http://localhost:3001 | Pipeline orchestration |
| **MinIO Console** | http://localhost:9001 | Data lake browser (login: `minioadmin` / `minioadmin`) |
| **PostgreSQL** | localhost:5433 | Mapped to 5433 to avoid local conflicts |

---

### Step 3 — Seed the database

```bash
docker compose exec fastapi python scripts/seed_db.py
```

Inserts sample data: **5 suppliers · 50 orders · 10 deviation alerts · 3 ontology constraints**

---

### Step 4 — Load the real dataset

Download the Brunel University LogisticsDataset (OrderList, FreightRates, PlantPorts, WhCapacities, ProductsPerPlant):

```bash
docker compose run --rm fastapi python scripts/download_supply_chain_data.py
```

Ingest all CSVs into the bronze data lake:

```bash
docker compose run --rm fastapi python -m ingestion.batch_loader
```

Expected output:
```
INFO: Wrote 9215 rows to bronze/orders (Parquet)
INFO: Wrote 1532 rows to bronze/freight_rates
INFO: Wrote 19 rows to bronze/wh_capacities
INFO: Wrote 22 rows to bronze/plant_ports
INFO: Wrote 1968 rows to bronze/products_per_plant
```

---

### Step 5 — Run the Dagster pipeline

Open **http://localhost:3001**, then:

1. Click **Assets** in the left sidebar
2. Click **Materialize all** (top right)
3. Watch the 14 assets run in order: bronze → silver → quality gate → dbt → gold

Or trigger via CLI:
```bash
docker compose exec dagster-webserver dagster asset materialize \
  --select "*" \
  -w /opt/dagster/app/workspace.yaml
```

The pipeline runs automatically every **6 hours** after setup.

---

### Step 6 — Sync data to PostgreSQL

After the pipeline runs, sync the gold layer to Postgres so the API and dashboard serve real data:

```bash
docker compose exec fastapi python scripts/sync_gold_to_postgres.py
```

Expected output:
```
INFO: Orders: 9215 inserted, 0 skipped
INFO: Sync complete. Total new rows inserted: 9215
```

Safe to re-run any time — uses `INSERT ... ON CONFLICT DO NOTHING`.

---

### Step 7 — Upload data lake to MinIO

Make the MinIO Console show the real Parquet files:

```bash
docker compose exec fastapi python scripts/sync_data_to_minio.py
```

Then open **http://localhost:9001** → bucket `supply-chain-lakehouse` → browse bronze/silver/gold folders.

---

### Step 8 — Open the dashboard

**http://localhost:3000**

What you'll see:

| Panel | Data |
|-------|------|
| **KPI Cards** | Pipeline value, on-time %, delayed orders, critical alerts |
| **Deviation Feed** | Live alert list — click any row to open AI reasoning |
| **Supplier Risk** | Bar chart ranked by trust score |
| **Risk Forecast** | Orders predicted to be late (from gold_forecasted_risks) |
| **Actions Log** | Every executed recommendation with timestamp |
| **Orders Table** | All 9,215+ orders — filterable by status, supplier |
| **Supply Chain Network** | Interactive SVG: Plant → Port topology, hover for products |
| **Ontology Constraints** | Hard limits injected into every AI call |

---

### Step 9 — Test AI reasoning

Click any deviation in the feed → **Analyze with AI** → Claude streams root cause + options in real time.

![AI Analysis — Claude streaming root cause and trade-off options in real time](assets/ai-analysis.gif)

Or via curl:
```bash
# Get a deviation ID first
curl -s "http://localhost:8000/alerts?limit=1&executed=false" | python3 -m json.tool

# Run AI analysis
curl -X POST http://localhost:8000/ai/analyze \
  -H "Content-Type: application/json" \
  -d '{"deviation_id":"DEV-0001","deviation_type":"DELAY","severity":"HIGH"}'
```

---

## Verify Everything Works

Run this full smoke test to confirm all endpoints respond correctly:

```bash
# Health
curl http://localhost:8000/health
# → {"status":"ok","service":"supply-chain-api"}

# Orders (should show 9000+ after sync)
curl "http://localhost:8000/orders?limit=3" | python3 -m json.tool

# Supplier risk
curl http://localhost:8000/suppliers/risk

# Active alerts
curl "http://localhost:8000/alerts?executed=false&limit=5"

# Ontology constraints
curl http://localhost:8000/ontology/constraints

# Network graph (19 plants, 11 ports, 22 routes)
curl http://localhost:8000/network | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['stats'])"
# → {'plant_count': 19, 'port_count': 11, 'edge_count': 22}

# Risk forecast
curl http://localhost:8000/forecasts/summary

# Actions log
curl http://localhost:8000/actions

# Execute a recommendation → creates PendingAction
DEV=$(curl -s "http://localhost:8000/alerts?limit=1&executed=false" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['deviation_id'])")
curl -X POST "http://localhost:8000/alerts/${DEV}/dismiss"
# → {"status":"ok","executed":true,"action_id":1}

# Confirm action was logged
curl http://localhost:8000/actions | python3 -m json.tool
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required for AI)* | Claude API key — only `/ai/analyze` needs this |
| `DATABASE_URL` | `postgresql://supplychain:supplychain_secret@postgres:5432/supply_chain_db` | Postgres connection string |
| `POSTGRES_PORT` | `5433` | Host port for Postgres (avoids conflicts with local installs) |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker address (internal Docker DNS) |
| `MINIO_ENDPOINT_URL` | `http://minio:9000` | MinIO S3 endpoint (internal) |
| `MINIO_ROOT_USER` | `minioadmin` | MinIO access key |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | MinIO secret key |
| `S3_STORAGE_BUCKET` | `supply-chain-lakehouse` | MinIO bucket name |
| `DATA_ROOT` | `/app/data` | Root path for bronze/silver/gold Parquet files |
| `BRONZE_PATH` | `$DATA_ROOT/bronze` | Bronze layer path |
| `SILVER_PATH` | `$DATA_ROOT/silver` | Silver layer path |
| `GOLD_PATH` | `$DATA_ROOT/gold` | Gold layer path |
| `REDIS_URL` | `redis://redis:6379` | Redis for WebSocket pub/sub |

---

## Architecture

```
CSV Sources ──────────────────────────────────────────────────────────┐
(OrderList, FreightRates,                                             │
 WhCapacities, PlantPorts,       Kafka Events                         │
 ProductsPerPlant)               (50+/min)                            │
       │                              │                               │
       └──────────────────────────────┴───────────────────────────────▼
                                                         DAGSTER (14 assets)
                                                         bronze → silver → gold
                                                         quality gate + dbt
                                                                    │
                    ┌───────────────────────────────────────────────┘
                    ▼
  ┌─────────────────────┐     ┌──────────────────────┐   ┌─────────────────┐
  │  Next.js :3000      │     │  FastAPI :8000       │   │  PostgreSQL     │
  │  KPI cards          │ ◀─▶ │  /orders             │◀─▶│  orders         │
  │  Deviation feed     │     │  /suppliers          │   │  deviations     │
  │  Risk forecast      │     │  /alerts             │   │  suppliers      │
  │  Actions log        │     │  /actions            │   │  pending_actions│
  │  Network graph      │     │  /forecasts          │   │  ontology       │
  │  AI reasoning modal │     │  /network            │   └─────────────────┘
  └─────────────────────┘     │  /ai/analyze (stream)│              │
                              └──────────────────────┘              ▼
                                          │               Claude Sonnet 4.6
                                          ▼               (trade-off analysis)
                                 MinIO :9001 (data lake browser)
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| Streaming | Kafka, WebSocket, SSE |
| Data | PostgreSQL 15, Delta Lake, PySpark, dbt, Pandas, PyArrow |
| Orchestration | Dagster (14 software-defined assets, 6-hour schedule) |
| Quality | Great Expectations |
| AI | Anthropic Claude Sonnet 4.6 — streaming + structured JSON |
| Frontend | Next.js 14 App Router, TailwindCSS, Recharts, SVG graph |
| Infrastructure | Docker Compose, MinIO (S3-compatible), Redis |

---

## Troubleshooting

**Containers not healthy after `docker compose up`**
```bash
docker compose logs <service-name> --tail=30
# Common fix: wait 60s for Kafka + Postgres to fully start, then:
docker compose restart fastapi
```

**AI returns 503**
`ANTHROPIC_API_KEY` missing in `.env`. Only `/ai/analyze` is affected — everything else works.

**Seed script: duplicate key error**
```bash
# Check what's already in the DB
docker compose exec postgres psql -U supplychain -d supply_chain_db -c "SELECT COUNT(*) FROM orders;"
# If data exists, the seed already ran — this is fine
```

**Dagster pipeline: `pyarrow` not found**
```bash
docker compose build dagster-webserver dagster-daemon
docker compose up -d dagster-webserver dagster-daemon
```

**Sync reports 0 rows**
Run steps 4 → 5 → 6 in order. The sync reads from bronze (or gold if pipeline ran).

**Port conflicts**
Postgres uses host port **5433** (not 5432). If any port is taken, update it in `.env`:
```
POSTGRES_PORT=5434
```

**MinIO Console empty**
Run `docker compose exec fastapi python scripts/sync_data_to_minio.py` to upload local Parquet files.

**Dagster UI blank / not loading**
Takes 1–2 minutes after Postgres + Kafka are healthy. Reload http://localhost:3001.

---

## Project Structure

```
supply-chain-os/
├── api/                          # FastAPI backend
│   ├── main.py                   # App entry, WebSocket, router registration
│   ├── models.py                 # Order, Supplier, Deviation, OntologyConstraint, PendingAction
│   ├── schemas.py                # Pydantic request/response types
│   └── routers/
│       ├── orders.py             # GET/POST /orders
│       ├── suppliers.py          # /suppliers, /suppliers/risk
│       ├── alerts.py             # /alerts, /alerts/{id}/dismiss → creates PendingAction
│       ├── actions.py            # /actions (audit log)
│       ├── forecasts.py          # /forecasts (at-risk orders from gold layer)
│       ├── network.py            # /network (Plant → Port topology)
│       ├── ontology.py           # /ontology/constraints
│       └── ai.py                 # /ai/analyze + /ai/analyze/stream (Claude SSE)
├── dashboard/                    # Next.js 14
│   ├── app/page.tsx              # Control tower — all panels
│   ├── components/
│   │   ├── KPICards.tsx
│   │   ├── DeviationFeed.tsx     # Real-time WebSocket + polling
│   │   ├── SupplierRisk.tsx      # Recharts bar chart
│   │   ├── RiskForecast.tsx      # At-risk orders from /forecasts
│   │   ├── ActionsLog.tsx        # Executed recommendations log
│   │   ├── SupplyChainGraph.tsx  # SVG Plant → Port network
│   │   ├── OrderTable.tsx        # Filterable orders table
│   │   ├── OntologyGraph.tsx     # Hard constraints list
│   │   └── AIReasoningPanel.tsx  # Streaming Claude modal
│   ├── hooks/useWebSocket.ts
│   └── lib/api.ts                # Typed fetch client
├── pipeline/                     # Dagster
│   ├── assets_medallion.py       # 14 assets: bronze×5 silver×3 quality dbt gold×5
│   └── definitions_medallion.py  # Definitions + 6-hour schedule
├── ingestion/
│   ├── producer.py               # Kafka: 50+ events/min, 12% anomaly rate
│   ├── consumer.py               # Kafka → Delta Lake bronze
│   └── batch_loader.py           # CSV → bronze Parquet (all 5 datasets)
├── reasoning/
│   └── engine.py                 # Claude Sonnet 4.6: stream + structured analysis
├── transforms/                   # dbt
│   └── models/
│       ├── staging/              # stg_orders.sql, stg_suppliers.sql
│       └── marts/                # fct_shipments.sql, dim_suppliers.sql
├── quality/
│   └── validations.py            # Great Expectations checks (not_null, between, in_set)
├── scripts/
│   ├── seed_db.py                # Sample data: 50 orders, 5 suppliers, 10 deviations
│   ├── sync_gold_to_postgres.py  # Gold/bronze Parquet → Postgres (idempotent upsert)
│   ├── sync_data_to_minio.py     # Local Parquet → MinIO bucket (boto3)
│   └── download_supply_chain_data.py
├── alembic/versions/
│   ├── 001_initial_schema.py
│   └── 002_pending_actions.py
├── docker/
│   ├── FastAPI.Dockerfile
│   ├── Dagster.Dockerfile
│   ├── Nextjs.Dockerfile
│   └── Producer.Dockerfile
├── docker-compose.yml            # Full stack (10 services)
├── docker-compose.minimal.yml    # Minimal: Postgres + Redis + API + Dashboard
├── requirements-dagster.txt      # pyarrow, pandas, deltalake, dbt, great-expectations
├── requirements-api.txt
└── .env.example
```

---

## Minimal Stack (no Kafka / Dagster)

If you just want the API + dashboard without the full pipeline:

```bash
docker compose -f docker-compose.minimal.yml up --build -d
docker compose -f docker-compose.minimal.yml exec fastapi python scripts/seed_db.py
open http://localhost:3000
```

---

## License

MIT
