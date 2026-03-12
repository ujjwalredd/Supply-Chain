# Supply Chain AI OS — v9.0

[![CI](https://github.com/ujjwalredd/Supply-Chain/actions/workflows/ci.yml/badge.svg)](https://github.com/ujjwalredd/Supply-Chain/actions/workflows/ci.yml)
[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://supply-chain-silk.vercel.app)

[Live Demo → supply-chain-silk.vercel.app](https://supply-chain-silk.vercel.app)

![Landing Page](assets/landing_page.png)

An **end-to-end AI-native supply chain control tower** built for real-world client deployments.

Ingests live purchase-order data from **OpenBoxes** (open-source WMS/SCM), streams it through Kafka, and runs a full medallion lakehouse with AI reasoning, ML delay prediction, and autonomous action execution — on a production-grade 20-service Docker stack.

> **Primary data source:** OpenBoxes (live WMS) · **Secondary / offline fallback:** CSV seed data

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER                             │
│                                                                     │
│  OpenBoxes WMS (live POs) ──► Kafka (supply-chain-events)           │
│  CSV seed data (offline fallback) ─────────────────────────────────►│
│                    │           │                                    │
│                    │           └──► supply-chain-dlq (Dead Letter)  │
│                    ▼                                                │
│              ksqlDB (5-min tumbling windows)                        │
│              └── delay_rate_5m, region_demand_5m                    │
└───────────────────────┬─────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STORAGE & TRANSFORM                            │
│                                                                     │
│  pg-writer (consumer) ──► PostgreSQL (orders, deviations, events)   │
│                                                                     │
│  batch_loader ──► MinIO / Delta Lake                                │
│                   ├── bronze/orders  (raw, partitioned Parquet)     │
│                   ├── silver/orders  (validated, deduped)           │
│                   └── gold/          (AI-ready features)            │
│                                                                     │
│  Dagster (orchestration)                                            │
│  ├── medallion assets  (Bronze → Silver → Gold)                     │
│  ├── dbt transforms    (incremental models, dbt-expectations)       │
│  ├── XGBoost trainer   ──► MLflow registry                          │
│  ├── Prophet forecast  ──► demand 30-day yhat                       │
│  ├── NetworkX Graph ML ──► cascade risk scores                      │
│  ├── OpenLineage       ──► lineage_events table                     │
│  ├── Delta maintenance ──► OPTIMIZE + VACUUM                        │
│  └── self-healing sensor (auto-retry after 3 failures)              │
└───────────────────────┬─────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API LAYER (FastAPI)                         │
│                                                                     │
│  /orders  /suppliers  /alerts/enriched  /forecasts  /network        │
│  /ml/predict  /ai/analyze (stream)  /ai/query  /ai/whatif           │
│  /ontology/normalize  /ontology/constraints                         │
│  /suppliers/{id}/policy  /actions  /events  /lineage  /streaming    │
│                                                                     │
│  Glass-Box Autonomy ──► ActionExecutor                              │
│  ├── Gate 1: global confidence threshold (AUTONOMY_CONFIDENCE)      │
│  └── Gate 2: per-supplier SupplierPolicy (severity + order value)   │
│                                                                     │
│  AI Reasoning Engine (reasoning/engine.py)                          │
│  ├── Claude sonnet-4-6  (primary)                                   │
│  └── GPT-4o fallback    (quality < 0.4)                             │
│                                                                     │
│  OpenTelemetry ──► Jaeger (distributed traces)                      │
│  Prometheus metrics ──► Grafana dashboards                          │
└───────────────────────┬─────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       DASHBOARD (Next.js 14)                        │
│                                                                     │
│  Control Tower · Alerts · Orders · Suppliers · Scorecard            │
│  Analytics · Actions · Network (Neo4j-style) · What-If              │
│                                                                     │
│  WebSocket (/ws) ──► real-time deviation feed                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Minimum version | Notes |
|---|---|---|
| Docker Desktop | 4.20+ | Allocate **≥ 8 GB RAM** in Docker settings (ksqlDB + Spark need headroom) |
| Docker Compose | v2.20+ | Bundled with Docker Desktop |
| Python | 3.11+ | Only needed for local dev / tests outside Docker |
| Git | any | — |

> **macOS / Apple Silicon**: All images are multi-arch. No Rosetta flags needed.

---

## Quick Start

```bash
cp .env.example .env
# Open .env and set:
#   ANTHROPIC_API_KEY=sk-ant-...      (required)
#   OPENAI_API_KEY=sk-...             (optional — enables GPT-4o fallback)
#
# OpenBoxes (primary live data source — mock=true works out of the box):
#   OPENBOXES_MOCK=true               (default — no server needed)
#   OPENBOXES_MOCK=false              (connect to live OpenBoxes instance)
#   OPENBOXES_URL=https://demo.openboxes.com/openboxes
#   OPENBOXES_USERNAME=OPENBOXES_USERNAME
#   OPENBOXES_PASSWORD=OPENBOXES_PASSWORD

docker compose up --build -d

# Wait ~60 s for all services to become healthy
docker compose ps

# Seed the database with initial supplier/constraint data
docker exec supply-chain-api python scripts/seed_db.py

# Start the OpenBoxes connector (primary data stream into Kafka)
docker exec supply-chain-producer python ingestion/openboxes_connector.py &

# Optional: also load CSV-based historical dataset as supplementary data
# docker exec supply-chain-api python scripts/download_supply_chain_data.py
```

| Service | URL | Credentials |
|---|---|---|
| Dashboard | http://localhost:3000 | — |
| API Docs (Swagger) | http://localhost:8000/docs | — |
| Dagster UI | http://localhost:3001 | — |
| Grafana | http://localhost:3002 | admin / admin (Explore → Loki for logs) |
| Loki | http://localhost:3100/ready | API backend only — use Grafana Explore to query logs |
| Prometheus | http://localhost:9090 | — |
| MLflow | http://localhost:5001 | — |
| Jaeger (traces) | http://localhost:16686 | — |
| ksqlDB REST | http://localhost:8088 | — |
| MinIO Console | http://localhost:9001 | minioadmin / see .env |

---

## Stack

| Layer | Technology |
|---|---|
| Ingestion | OpenBoxes connector (primary), Kafka, kafka-python, JSON Schema validation |
| Lakehouse | Delta Lake, Parquet (partitioned by date), MinIO |
| Transform | dbt (incremental models, dbt-expectations) |
| Orchestration | Dagster 1.12+ (medallion assets, freshness policies, self-healing sensor) |
| ML | XGBoost, MLflow (experiment tracking + model registry) |
| Forecasting | Prophet (30-day demand forecast) |
| Graph ML | NetworkX (betweenness centrality, cascade risk) |
| Streaming | ksqlDB (5-min rolling delay rate, region demand) |
| API | FastAPI, SQLAlchemy async, PostgreSQL |
| Auth | Bearer token + X-API-Key middleware, env-configurable key rotation |
| Tracing | OpenTelemetry → Jaeger |
| AI Reasoning | Claude sonnet-4-6 + GPT-4o fallback + quality scoring |
| Data Quality | Soda Core contracts, Great Expectations |
| Event Sourcing | append-only `order_events` table (point-in-time recovery) |
| CI/CD | GitHub Actions 6-job pipeline (pytest + secret scan + dbt + docker + auto-tag + deploy) |
| Frontend | Next.js 14 App Router, Tailwind CSS |
| Observability | Grafana Alloy → Loki (logs) + Prometheus (metrics) + Grafana dashboards |

---

## What's New in v9.0

### Production Hardening + Full Observability Stack

| Change | Detail | Files |
|---|---|---|
| **API Key Auth** | `Authorization: Bearer <key>` or `X-API-Key: <key>` on all non-public routes. Set `API_KEYS=key1,key2` in `.env`. Empty = dev mode (auth disabled). | `api/auth.py`, `api/main.py` |
| **docker-compose.prod.yml** | Production override: removes source-code volume mounts, Redis AUTH, Grafana anonymous disabled, all sensitive ports bound to loopback, resource limits for 24 GB Oracle VM. | `docker-compose.prod.yml` |
| **Grafana Alloy log shipping** | Alloy agent discovers all `supply-chain-*` containers via Docker socket, parses JSON logs, labels by service/level, strips DEBUG, ships to Loki. Supports both local Loki and Grafana Cloud free tier. | `docker/alloy/config.alloy` |
| **Loki + Prometheus in compose** | Two new observability services added. Grafana pre-provisioned with Loki and Prometheus datasources. Alloy scrapes FastAPI `/metrics` into Prometheus. | `docker-compose.yml`, `docker/grafana/provisioning/datasources/loki.yml`, `docker/prometheus/prometheus.yml` |
| **GitHub Actions 6-job CI/CD** | Tests → Secret scan → dbt validate → Docker compose validate (both files) → Auto-tag → Deploy to Oracle VM via SSH. | `.github/workflows/ci.yml` |
| **Kafka at-least-once delivery** | `enable_auto_commit=False`; `consumer.commit()` called after every successful DB write path. | `ingestion/pg_writer.py` |
| **Rate limiter memory safety** | IP key store bounded to 10,000 entries with stale eviction. | `api/routers/ai.py` |
| **8 bugs fixed by QA sweep** | Auth bypass via `/` prefix, lineage resource DB credential leak, psycopg2 connection leak, dead `confidence` branch, non-deterministic column order in forecasts, timezone-naive datetime subtraction, `datetime.utcnow()` deprecation, `IndexError` on non-text Claude response blocks. | Various |
| **133 tests, 0 failures** | +62 new critical-path tests added covering all 404, 422, and edge-case paths. | `tests/test_critical_paths.py` |

---

## What's New in v8.0

### Adpot-Parity Features

| Feature | Description | Key files |
|---|---|---|
| **Ontology Schema Normalization** | `POST /ontology/normalize` maps 60+ messy ERP field aliases (vendor, sku, po_number, eta…) to canonical internal schema. Supports exact + partial matching. Returns `{normalized, unmapped, mapping_applied, canonical_fields}`. | `api/routers/ontology.py` |
| **Glass-Box Autonomy Policies** | Per-supplier `SupplierPolicy` controls which actions auto-execute. `GET/PUT /suppliers/{id}/policy` exposes `require_approval_at_severity`, `require_approval_above_value`, `max_auto_actions_per_day`, `min_confidence`. ActionExecutor dual-gates every action: (1) global confidence threshold, (2) per-supplier policy. | `api/routers/suppliers.py`, `integrations/action_executor.py`, `alembic/versions/006_add_supplier_policy.py` |
| **Financial Impact Scoring** | `GET /alerts/enriched` computes `cost_impact_usd = delay_days × order_value × 0.02` (2% daily carrying cost) and risk tier (`CRITICAL_COST >$10k`, `HIGH_COST >$2k`, `MODERATE`). Returns aggregate `total_cost_impact_usd` and `critical_cost_count`. | `api/routers/alerts.py` |

### Dashboard Upgrades

| Upgrade | Description |
|---|---|
| **Neo4j-style Network Graph** | Force-directed SVG simulation — Coulomb repulsion, spring edges, center gravity, alpha cooling. Dark background (#0f172a), glowing nodes (indigo/sky/emerald), arrow markers, hover highlighting. Pure JS (no D3). | `dashboard/components/SupplyChainGraph.tsx` |
| **Supplier Scorecard — Dual Y-axis** | Fixed chart: `ComposedChart` with left axis (0–100%) for On-Time % `Area` and right axis for `Bar` (Deviations, red) + dashed `Area` (Avg Delay, amber). Custom tooltip with TypeScript types. | `dashboard/components/SupplierScorecard.tsx` |

### OpenBoxes — Primary Data Source

`ingestion/openboxes_connector.py` is the **main ingestion path**. It polls [OpenBoxes](https://openboxes.com) (free, open-source WMS/SCM), flattens nested PO JSON, normalises field names via the ontology layer, and streams `OrderEvent` objects into Kafka. No paid API key required.

| Mode | How to use | When |
|---|---|---|
| **Mock** (default) | Generates realistic OpenBoxes-formatted POs locally — no server needed | Development, CI, demos |
| **Live — Public Demo** | Polls `demo.openboxes.com` (free, always up, `admin/password`) | Integration testing, client demos |
| **Live — Self-hosted** | Polls your own OpenBoxes instance | Production deployments |

**Full data flow:**
```
OpenBoxes PO (nested JSON)
  → _flatten_po()               # normalise nested structure
  → POST /ontology/normalize    # map 60+ ERP aliases to canonical fields
  → canonical OrderEvent        # order_id, supplier_id, product, region, ...
  → Kafka: supply-chain-events  # JSON-schema validated before produce
  → pg-writer consumer          # PostgreSQL upsert + DLQ on failure
  → Dagster medallion pipeline  # Bronze → Silver → Gold → ML
```

**Field mappings** (`_FIELD_MAP`, 60+ aliases): `orderNumber→order_id`, `originName→supplier_id`, `productCode→product`, `destinationName→region`, `quantityOrdered→quantity`, `unitPrice→unit_price`, `totalPrice→order_value`, `estimatedDeliveryDate→expected_delivery`, `dateReceived→actual_delivery`, `daysLate→delay_days`, `currentStockLevel→inventory_level`, and more.

```bash
# Run standalone (mock mode — no server needed)
python ingestion/openboxes_connector.py

# Connect to free public demo
OPENBOXES_MOCK=false OPENBOXES_URL=https://demo.openboxes.com/openboxes \
  OPENBOXES_USERNAME=admin OPENBOXES_PASSWORD=password \
  python ingestion/openboxes_connector.py

# Connect to self-hosted OpenBoxes
OPENBOXES_MOCK=false OPENBOXES_URL=http://localhost:8080/openboxes \
  OPENBOXES_USERNAME=admin OPENBOXES_PASSWORD=yourpassword \
  python ingestion/openboxes_connector.py
```

> **Secondary / fallback:** `ingestion/producer.py --count N` produces synthetic events. `scripts/download_supply_chain_data.py` loads a CSV dataset. Use these for bulk seeding or offline ML training — OpenBoxes is the preferred operational source.

### Infrastructure

- **ksqlDB memory fix**: Reduced heap from `-Xmx768m` → `-Xmx512m -Xms128m`, added `mem_limit: 768m` — eliminates OOM-kill (exit 137) on resource-constrained machines.
- **Alembic migration 006**: `supplier_policies` table. DB now at revision head=006.
- **Code audit**: Removed redundant inline `import datetime` statements from `actions.py`, `orders.py` — already imported at module level.

---

## Data Engineering Features

| # | Feature | Location |
|---|---|---|
| 1 | **Incremental dbt models** — `unique_key` + `is_incremental()` filter | `transforms/models/marts/` |
| 2 | **Dead Letter Queue** — `_send_to_dlq()` on Kafka parse/validation failure | `ingestion/pg_writer.py` |
| 3 | **Delta OPTIMIZE + VACUUM** — weekly maintenance asset | `pipeline/assets_medallion.py` |
| 4 | **Partitioned Parquet** — `year=/month=/day=` layout on every batch write | `ingestion/batch_loader.py` |
| 5 | **JSON Schema validation** — per-event-type schemas before produce | `ingestion/producer.py` |
| 6 | **OpenLineage tracker** — START/COMPLETE/FAIL → Postgres + Marquez | `pipeline/lineage_resource.py` |
| 7 | **Freshness policies** — `FreshnessPolicy.time_window()` on all gold assets | `pipeline/assets_medallion.py` |
| 8 | **dbt-expectations** — `packages.yml` + test macros on marts | `transforms/packages.yml` |

---

## Feature Catalog (v8.0)

### Tier 1 — High Signal

| Feature | What it does | Key files |
|---|---|---|
| **XGBoost + MLflow** | Trains delay classifier, logs metrics/artifact to MLflow registry; `POST /ml/predict` returns probability + confidence | `pipeline/ml_model.py`, `pipeline/assets_medallion.py`, `api/routers/ml.py` |
| **GitHub Actions CI/CD** | pytest on PR, dbt SQL validation, docker-compose syntax check, auto-tag on merge to main | `.github/workflows/ci.yml` |
| **ksqlDB Streaming** | 5-min tumbling window: delay rate per supplier + region demand; persistent queries on Kafka topic | `streaming/ksql_init.sql`, `streaming/ksql_queries.py`, `api/routers/streaming.py` |
| **Soda Core Contracts** | 11-check contract on orders (nulls, dupes, enum, freshness); silver layer contract | `contracts/orders.yml`, `contracts/silver_orders.yml` |

### Tier 2 — Higher Effort

| Feature | What it does | Key files |
|---|---|---|
| **NetworkX Graph ML** | Betweenness centrality + cascade risk on plant-port network; `GET /network/risk` returns top-20 at-risk nodes | `pipeline/graph_ml.py`, `api/routers/network.py` |
| **Prophet Forecasting** | 30-day demand forecast Dagster asset; `GET /forecasts/demand` returns yhat/bounds | `pipeline/demand_forecast.py`, `pipeline/assets_medallion.py` |
| **OpenTelemetry + Jaeger** | FastAPI + SQLAlchemy auto-instrumented; OTLP gRPC → Jaeger; graceful console fallback | `api/telemetry.py` |
| **Event Sourcing** | `order_events` append-only table; full audit trail + point-in-time replay via `?version=N` | `api/models.py`, `api/event_store.py`, `api/routers/events.py` |

### Tier 3 — Differentiators & v8.0 Adpot-Parity

| Feature | What it does | Key files |
|---|---|---|
| **Self-Healing Pipeline** | Dagster sensor auto-triggers RunRequest after 3 consecutive failures; writes JSON audit log | `pipeline/sensors.py` |
| **Multi-Model AI + Quality Scoring** | Claude primary; GPT-4o fallback on quality < 0.4; scores responses 0–1; `POST /ai/analyze-scored` | `reasoning/engine.py`, `api/routers/ai.py` |
| **Ontology Schema Normalization** | 60-alias `_FIELD_MAP` + partial matching; maps legacy ERP fields (vendor, sku, eta…) to canonical schema; `POST /ontology/normalize` | `api/routers/ontology.py` |
| **Glass-Box Autonomy Policies** | Per-supplier `SupplierPolicy` dual-gates every action: global confidence threshold + per-supplier severity/value ceiling; `GET/PUT /suppliers/{id}/policy` | `integrations/action_executor.py`, `api/routers/suppliers.py` |
| **Financial Impact Scoring** | `cost_impact_usd = delay_days × order_value × 0.02`; CRITICAL_COST / HIGH_COST / MODERATE tiers; `GET /alerts/enriched` | `api/routers/alerts.py` |
| **Neo4j-style Network Graph** | Force-directed SVG with Coulomb repulsion, spring edges, alpha cooling, glow filters, dark canvas, drag interaction | `dashboard/components/SupplyChainGraph.tsx` |

---

## Dashboard Pages

The Next.js 14 dashboard at http://localhost:3000 has 9 pages:

| Page | Route | What it shows |
|---|---|---|
| **Control Tower** | `/` | Pipeline value, on-time %, delayed count, recent deviations, supplier trust |
| **Alerts** | `/alerts` | Active deviations by severity, trend chart, alert fatigue suppression |
| **Orders** | `/orders` | Paginated order table with delay status, filter by supplier/region |
| **Suppliers** | `/suppliers` | Supplier risk matrix, trust scores, delay rates |
| **Scorecard** | `/scorecard` | Per-supplier weekly scorecard: dual Y-axis chart (On-Time % + Delay/Deviations), KPI strip |
| **Analytics** | `/analytics` | Delay predictions, trend chart, risk forecast, cost analytics, benchmarks |
| **Actions** | `/actions` | Autonomous AI action log, resolve/fail buttons, MTTR tracker |
| **Network** | `/network` | Neo4j-style force-directed topology graph, NetworkX cascade risk, glow nodes |
| **What-If** | `/whatif` | Scenario simulator: change inventory/delay params, see risk impact |

---

## API Endpoints

```
GET  /health                          — dependency health check
GET  /orders                          — paginated orders
GET  /suppliers                       — supplier risk matrix
GET  /alerts                          — active deviations
GET  /alerts/trend                    — severity trend over N days
GET  /forecasts                       — KPI forecasts
GET  /forecasts/summary               — at-risk counts
GET  /forecasts/demand                — 30-day Prophet demand forecast
GET  /network                         — plant-port topology graph
GET  /network/risk                    — NetworkX cascade risk scores
GET  /lineage                         — OpenLineage events + graph
GET  /streaming/aggregations          — ksqlDB 5-min window stats
GET  /streaming/supplier-delay-rates  — per-supplier delay rate
GET  /streaming/region-demand         — per-region demand aggregation
POST /streaming/init                  — initialize ksqlDB streams
POST /ml/predict                      — XGBoost delay prediction
POST /ai/analyze                      — Claude AI reasoning (streaming)
POST /ai/analyze-scored               — Multi-model AI with quality score
GET  /events/recent                   — recent order events
GET  /events/orders/{id}/history      — event sourcing audit trail
GET  /events/orders/{id}/replay       — point-in-time state recovery
GET  /actions/stats                   — MTTR + resolution stats
GET  /orders/delay-predictions        — batch delay predictions
GET  /suppliers/cost-analytics        — cost breakdown per supplier
GET  /suppliers/benchmarks            — supplier benchmark comparison
GET  /suppliers/{id}/policy           — get per-supplier autonomy policy (auto-creates default)
PUT  /suppliers/{id}/policy           — update per-supplier autonomy policy
GET  /alerts/enriched                 — alerts with financial impact scoring + risk tier
GET  /ontology/constraints            — list hard business rules per entity
POST /ontology/constraints            — create new ontology constraint (MAX_DELAY_DAYS, MIN_TRUST_SCORE…)
POST /ontology/normalize              — map legacy ERP field names to canonical schema
GET  /metrics                         — Prometheus metrics
WS   /ws                              — real-time deviation feed
```

Full interactive docs: http://localhost:8000/docs

---

## Medallion Lakehouse Assets (Dagster)

```
Bronze: bronze_orders               (OpenBoxes/Kafka → Delta + partitioned Parquet; CSV as fallback)
Silver: silver_orders               (validated, deduped, typed)
Gold:   gold_orders_ai_ready        (AI-ready features + freshness policy)
        gold_deviations             (delay/stockout anomalies)
        gold_supplier_risk          (risk scores per supplier)
        gold_forecasted_risks       (forward-looking risk)
        gold_delay_model            (XGBoost trained → MLflow registry)
        gold_demand_forecast        (Prophet 30-day forecast → Parquet)
        delta_maintenance           (weekly OPTIMIZE + VACUUM)
```

---

## dbt Models

```
transforms/models/
├── staging/
│   ├── stg_orders.sql          — cast + rename raw order columns
│   └── stg_suppliers.sql       — supplier dimension staging
└── marts/
    ├── fct_shipments.sql       — incremental fact table (unique_key: order_id)
    ├── dim_suppliers.sql       — incremental supplier dimension
    └── agg_control_tower.sql   — daily KPI rollup for dashboard
```

Run dbt manually inside the dagster container:
```bash
# Install dbt packages first (only needed once, or after dbt_packages is wiped)
docker exec supply-chain-dagster-webserver \
  dbt deps --profiles-dir /opt/dagster/app/transforms --project-dir /opt/dagster/app/transforms

# Run all models
docker exec supply-chain-dagster-webserver \
  dbt run --profiles-dir /opt/dagster/app/transforms --project-dir /opt/dagster/app/transforms
```

Run specific dbt models or tests:
```bash
# Run only the marts layer
docker exec supply-chain-dagster-webserver \
  dbt run --select marts --profiles-dir /opt/dagster/app/transforms --project-dir /opt/dagster/app/transforms

# Run dbt tests
docker exec supply-chain-dagster-webserver \
  dbt test --profiles-dir /opt/dagster/app/transforms --project-dir /opt/dagster/app/transforms
```

---

## Docker Services (20 total)

| Service | Port | Purpose |
|---|---|---|
| zookeeper | 2181 | Kafka coordination |
| kafka | 9092/9093 | Message broker |
| kafka-init | — | Topic creation (events + DLQ) |
| schema-registry | 8081 | Confluent Schema Registry |
| ksqldb-server | 8088 | Streaming SQL aggregations |
| ksqldb-init | — | ksqlDB stream/table creation |
| postgres | 5433 | Orders, events, lineage, Dagster metadata |
| minio | 9000/9001 | S3-compatible object storage |
| minio-init | — | Bucket creation |
| redis | 6379 | WebSocket pub/sub |
| dagster-webserver | 3001 | Pipeline orchestration UI |
| dagster-daemon | — | Scheduler + sensor runner |
| mlflow | 5001 | ML experiment tracking + model registry |
| fastapi | 8000 | REST API + WebSocket |
| nextjs | 3000 | Dashboard |
| grafana | 3002 | Metrics + log dashboards |
| jaeger | 16686 | Distributed traces (OTLP gRPC) |
| loki | 3100 | Log aggregation backend |
| prometheus | 9090 | Metrics collection |
| alloy | 12345 | Log + metric collection agent (Docker socket) |

---

## Environment Variables

Copy `.env.example` to `.env`. Key variables:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...           # Claude AI reasoning
SECRET_KEY=<32-char random string>     # generate: python -c "import secrets; print(secrets.token_hex(32))"

# API Authentication (production — leave empty for local dev)
# generate: python -c "import secrets; print('sc-' + secrets.token_hex(24))"
API_KEYS=sc-key1,sc-key2              # Authorization: Bearer <key>  OR  X-API-Key: <key>
AI_RATE_LIMIT_PER_MIN=30              # per-IP rate limit on /ai/* endpoints

# Database
POSTGRES_PASSWORD=change_me_in_production
DATABASE_URL=postgresql://supplychain:...@localhost:5433/supply_chain_db

# Object Storage (MinIO)
MINIO_ROOT_PASSWORD=change_me_in_production
AWS_SECRET_ACCESS_KEY=change_me_in_production

# Redis (AUTH required in production)
REDIS_PASSWORD=change_me_redis

# Optional — AI fallback
OPENAI_API_KEY=sk-...                  # enables GPT-4o fallback when Claude quality < 0.4

# Optional — Observability (Loki/Prometheus default to local docker-compose services)
LOKI_URL=http://loki:3100/loki/api/v1/push
PROMETHEUS_REMOTE_WRITE_URL=http://prometheus:9090/api/v1/write
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
MLFLOW_TRACKING_URI=http://localhost:5001
KSQLDB_URL=http://localhost:8088

# Optional — Grafana Cloud free tier (50GB logs/month, 10k metrics/day)
# GRAFANA_CLOUD_LOKI_URL=https://logs-prod-<region>.grafana.net/loki/api/v1/push
# GRAFANA_CLOUD_LOKI_USER=<user-id>
# GRAFANA_CLOUD_LOKI_API_KEY=<api-key>

# Optional — Alerting
SLACK_WEBHOOK_URL=https://hooks.slack.com/...   # CRITICAL deviation notifications

# Optional — Lineage
MARQUEZ_URL=                           # leave empty to write lineage to Postgres only
```

See `.env.example` for the complete list (~60 variables) with inline documentation.

---

## End-to-End Running Guide

### Step 1 — Start the full stack

```bash
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY (required) and OPENAI_API_KEY (optional)

docker compose up --build -d
```

Wait ~60 seconds for all services to become healthy:

```bash
docker compose ps   # all 20 services should show "healthy" or "running"
```

---

### Step 2 — Seed the database

```bash
docker exec supply-chain-api python scripts/seed_db.py
```

This creates initial suppliers, ontology constraints, and historical events in PostgreSQL.

> **Optional CSV supplement:** If you also want to load the historical CSV dataset as supplementary data (e.g., for ML training with a larger dataset), run:
> ```bash
> docker exec supply-chain-api python scripts/download_supply_chain_data.py
> ```

---

### Step 3 — Start the live data stream (OpenBoxes → Kafka)

OpenBoxes is the **primary data source**. It polls for real purchase orders (POs), normalises field names via the ontology layer, and streams them into Kafka.

```bash
# Option A — Mock mode (default, no server required)
# Generates realistic OpenBoxes-formatted POs locally
docker exec supply-chain-producer python ingestion/openboxes_connector.py

# Option B — Live public demo (free, always up)
docker exec -e OPENBOXES_MOCK=false \
  -e OPENBOXES_URL=https://demo.openboxes.com/openboxes \
  -e OPENBOXES_USERNAME=OPENBOXES_USERNAME \
  -e OPENBOXES_PASSWORD=OPENBOXES_PASSWORD \
  supply-chain-producer python ingestion/openboxes_connector.py

# Option C — Self-hosted OpenBoxes instance
docker exec -e OPENBOXES_MOCK=false \
  -e OPENBOXES_URL=http://your-host:8080/openboxes \
  -e OPENBOXES_USERNAME=OPENBOXES_USERNAME \
  -e OPENBOXES_PASSWORD=OPENBOXES_PASSWORD \
  supply-chain-producer python ingestion/openboxes_connector.py
```

**Data flow:** `OpenBoxes PO (nested JSON)` → `_flatten_po()` → `POST /ontology/normalize` → `canonical OrderEvent` → `Kafka topic: supply-chain-events` → `pg-writer → PostgreSQL`

> **Fallback / secondary source:** If you prefer to produce synthetic Kafka events without OpenBoxes:
> ```bash
> docker exec supply-chain-producer python ingestion/producer.py --count 500
> ```
> The pg-writer consumer is always running — it consumes from Kafka → PostgreSQL with DLQ on parse failure.

---

### Step 4 — Run the Dagster medallion pipeline

Open **Dagster UI** at http://localhost:3001

1. Click **Assets** in the left sidebar
2. Click **Materialize all** to run the full Bronze → Silver → Gold pipeline
3. Assets in order:
   - `bronze_orders` — raw OpenBoxes/Kafka → Delta + partitioned Parquet
   - `silver_orders` — validated, deduped, typed
   - `gold_orders_ai_ready` — AI-ready features
   - `gold_deviations` — delay/stockout anomalies
   - `gold_supplier_risk` — risk scores per supplier
   - `gold_delay_model` — **trains XGBoost, logs to MLflow registry**
   - `gold_demand_forecast` — **runs Prophet 30-day forecast**

Or trigger from CLI:
```bash
docker exec supply-chain-dagster-webserver \
  dagster asset materialize --select "*" -m pipeline.definitions_medallion
```

---

### Step 5 — MLflow: Train the XGBoost Model + View Registry

Open **MLflow UI** at http://localhost:5001

#### How to Train the Model

Training is triggered automatically as a Dagster asset (`gold_delay_model`). There are three ways to trigger it:

**Option A — Via Dagster UI (recommended):**
1. Open http://localhost:3001
2. Go to **Assets** → search `gold_delay_model`
3. Click **Materialize** — training runs on silver order data

**Option B — Via CLI** (runs bronze → silver → train in sequence):
```bash
docker exec supply-chain-dagster-webserver \
  dagster asset materialize --select "bronze_orders,silver_orders,gold_delay_model" -m pipeline.definitions_medallion
```

**Option C — Run the full medallion pipeline** (bronze → silver → gold → train):
```bash
docker exec supply-chain-dagster-webserver \
  dagster asset materialize --select "*" -m pipeline.definitions_medallion
```

> **Note:** Multiple assets in `--select` must be comma-separated (no spaces). `gold_delay_model` requires `silver_orders` to be materialized first — always include it or use `"*"` to run everything.

#### What Happens During Training

The `gold_delay_model` asset (`pipeline/ml_model.py`):
1. Reads `data/silver/orders/data.parquet` (or falls back to bronze)
2. Trains **XGBoost** classifier (`is_delayed = delay_days > 0`)
3. Features: `supplier_id`, `region`, `quantity`, `unit_price`, `order_value`, `inventory_level`
4. Logs to MLflow: accuracy, ROC-AUC, precision, recall + model artifact
5. Registers as `supply_chain_delay_model` in MLflow Model Registry
6. Saves local copy to `data/models/delay_model.json` (used as fallback)

#### View Results in MLflow UI

After training:
- **Experiments** → `supply_chain_delay_prediction` — metrics per run
- **Models** → `supply_chain_delay_model` — registered versions

#### Test the ML Prediction API

```bash
curl -X POST http://localhost:8000/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_id": "SUP-001",
    "region": "BOSTON",
    "quantity": 500,
    "unit_price": 45.0,
    "order_value": 22500.0,
    "inventory_level": 60.0
  }'
# Returns: { "is_delayed": true, "probability": 0.82, "confidence": "HIGH", "model_version": "local:xgboost" }
```

> If the model has not been trained yet, `model_version` will be `"heuristic"` — train first via Dagster.

#### Promote a Model to Production

```bash
# In MLflow UI: Models → supply_chain_delay_model → version 1 → Stage → "Production"
# Or via MLflow API:
curl -X POST http://localhost:5001/api/2.0/mlflow/model-versions/transition-stage \
  -H "Content-Type: application/json" \
  -d '{"name": "supply_chain_delay_model", "version": "1", "stage": "Production"}'
```

Once in Production, predictions automatically load from the registry (`model_version: "mlflow:Production"`).

![MLflow Experiment — xgboost_delay_classifier](assets/flow.png)

---

### Step 6 — ksqlDB: Initialize streams and query aggregations

**Initialize persistent streaming queries:**
```bash
curl -X POST http://localhost:8000/streaming/init
# Returns: { "success": true, "message": "ksqlDB streams initialized" }
```

**View real-time 5-minute aggregations:**
```bash
# Supplier delay rates (rolling 5-min window)
curl http://localhost:8000/streaming/supplier-delay-rates

# Regional demand aggregation
curl http://localhost:8000/streaming/region-demand

# Combined view
curl http://localhost:8000/streaming/aggregations
```

**Query ksqlDB directly (advanced):**
```bash
# Pull query from supplier_delay_rate_5m table
curl -X POST http://localhost:8088/query \
  -H "Content-Type: application/vnd.ksql.v1+json" \
  -d '{"ksql": "SELECT * FROM supplier_delay_rate_5m LIMIT 10;", "streamsProperties": {}}'
```

---

### Step 7 — Jaeger: View distributed traces

Open **Jaeger UI** at http://localhost:16686

Every FastAPI request is automatically traced via OpenTelemetry:
1. Select **Service**: `supply-chain-api`
2. Click **Find Traces**
3. Click any trace to see span waterfall: HTTP handler → SQLAlchemy queries → AI calls

**Trigger some traced requests:**
```bash
curl "http://localhost:8000/orders?limit=10"
curl http://localhost:8000/suppliers
curl http://localhost:8000/network/risk
curl -X POST http://localhost:8000/ai/analyze \
  -H "Content-Type: application/json" \
  -d '{"deviation_id": "DEV-SEED-0001", "order_id": "ORD-001", "deviation_type": "DELAY", "severity": "HIGH"}'
```

Then refresh Jaeger to see the traces appear.

---

### Step 8 — Try all extraordinary API endpoints

**30-day demand forecast (Prophet):**
```bash
curl http://localhost:8000/forecasts/demand
# Returns: { "forecast": [{"ds": "2026-03-11", "yhat": 1240.5, "yhat_lower": 980.2, "yhat_upper": 1500.8}, ...] }
```

**Network cascade risk (NetworkX):**
```bash
curl http://localhost:8000/network/risk
# Returns top-20 at-risk nodes with betweenness centrality + cascade_risk scores
```

**Event sourcing — order audit trail:**
```bash
curl http://localhost:8000/events/recent
curl http://localhost:8000/events/orders/ORD_001/history
curl "http://localhost:8000/events/orders/ORD_001/replay?version=3"
```

**Multi-model AI with quality scoring:**
```bash
curl -X POST http://localhost:8000/ai/analyze-scored \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "3 suppliers in Asia have delay rates above 40% this week. What are the top risk mitigation actions?"
  }'
# Returns: { "answer": "...", "quality_score": 0.82, "model_used": "claude-sonnet-4-6", "fallback_used": false }
# If quality < 0.4, automatically falls back to GPT-4o
```

**OpenLineage graph:**
```bash
curl http://localhost:8000/lineage
# Returns lineage events + upstream/downstream asset graph
```

**Financial impact scoring (v8.0):**
```bash
curl "http://localhost:8000/alerts/enriched?limit=20&severity=CRITICAL"
# Returns alerts with cost_impact_usd, risk_tier (CRITICAL_COST/HIGH_COST/MODERATE),
# total_cost_impact_usd, and critical_cost_count
```

**Ontology schema normalization (v8.0):**
```bash
curl -X POST http://localhost:8000/ontology/normalize \
  -H "Content-Type: application/json" \
  -d '{
    "po_number": "ORD-001",
    "vendor": "SUP-007",
    "sku": "SENSOR-PACK-A",
    "qty": 500,
    "eta": "2026-04-15",
    "ship_late_day_count": 3
  }'
# Returns: { "normalized": {"order_id": "ORD-001", "supplier_id": "SUP-007", ...},
#            "unmapped": {}, "mapping_applied": [...], "canonical_fields": [...] }
```

**Glass-Box supplier policy (v8.0):**
```bash
# Get current policy (auto-creates default on first call)
curl http://localhost:8000/suppliers/SUP-001/policy

# Update: require human approval for HIGH+ severity or orders > $25k
curl -X PUT http://localhost:8000/suppliers/SUP-001/policy \
  -H "Content-Type: application/json" \
  -d '{
    "require_approval_at_severity": "HIGH",
    "require_approval_above_value": 25000,
    "max_auto_actions_per_day": 5,
    "min_confidence": 0.80
  }'
```

---

### Step 9 — Grafana dashboards + logs

Open **Grafana** at http://localhost:3002 (admin/admin)

Grafana queries **PostgreSQL** for metrics and **Loki** for logs — both datasources are auto-provisioned. Make sure the database has been seeded before opening.

```bash
# If this is a fresh stack or you changed POSTGRES_PASSWORD, force re-provisioning:
docker compose restart grafana
```

**Logs (Loki — via Grafana Explore):**

Alloy ships all `supply-chain-*` container logs to Loki automatically. Query them in Grafana → Explore → Loki datasource:

```logql
# All ERROR logs across the stack
{project="supply-chain-os"} |= "ERROR"

# FastAPI errors only
{service="fastapi", level="ERROR"}

# Kafka consumer events
{service="pg-writer"} |= "committed"
```

**Metrics (Prometheus — via Grafana Explore):**

```promql
# FastAPI request rate (req/s)
rate(http_requests_total{job="fastapi"}[1m])

# P95 response time
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="fastapi"}[5m]))
```

**Supply Chain OS dashboard** (auto-loaded on startup):

| Panel | What it shows |
|---|---|
| Total Orders | `COUNT(*)` from orders table |
| Delayed Orders | Orders where `delay_days > 0` |
| Active Deviations | Unexecuted deviations |
| Critical Alerts | `CRITICAL` severity unexecuted deviations |
| MTTR (minutes) | Avg time from deviation detected → action completed |
| Deviations by Severity | Stacked bar chart — last 7 days, CRITICAL/HIGH/MEDIUM/LOW |
| Supplier Trust Scores | All suppliers sorted by trust score ascending |
| Recent Active Deviations | Latest 20 unexecuted deviations |

![Grafana Dashboard](assets/Grafana.png)

---

### Step 10 — Data contracts (Soda Core)

Run quality checks against the live database:

```bash
pip install soda-core soda-core-postgres

python -m soda scan -d supply_chain_db \
  -c contracts/soda_connection.yml \
  contracts/orders.yml

# Checks: row count, nulls, duplicates, valid status enum, delay bounds, freshness
```

---

### Step 11 — MinIO: Browse the lakehouse

Open **MinIO Console** at http://localhost:9001 (credentials in `.env`)

The `supply-chain-lakehouse` bucket contains:
```
supply-chain-lakehouse/
├── bronze/orders/          — raw Delta + year=/month=/day= Parquet partitions
├── silver/orders/          — validated, deduped Delta table
└── gold/                   — AI-ready features, deviations, risk scores
```

To sync local gold Parquet to MinIO:
```bash
docker exec supply-chain-api python scripts/sync_data_to_minio.py
```

To backfill gold data into PostgreSQL from Parquet:
```bash
docker exec supply-chain-api python scripts/sync_gold_to_postgres.py
```

---

### Production Deployment (Oracle Cloud Always Free)

Use the production compose override which removes source-code mounts, enforces Redis AUTH, disables Grafana anonymous access, and binds all sensitive ports to loopback:

```bash
# On the Oracle VM — first-time setup
git clone https://github.com/ujjwalredd/Supply-Chain.git supply-chain-os
cd supply-chain-os
cp .env.example .env

# Edit .env — set all required secrets:
#   ANTHROPIC_API_KEY, POSTGRES_PASSWORD, API_KEYS, REDIS_PASSWORD,
#   GRAFANA_PASSWORD, MINIO_ROOT_PASSWORD, SECRET_KEY

# Start with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Run migrations
docker exec supply-chain-api alembic upgrade head

# Health check
curl -H "X-API-Key: <your-api-key>" http://localhost:8000/health
```

**Required GitHub Secrets** for the auto-deploy CI job:

| Secret | Value |
|--------|-------|
| `VM_HOST` | Oracle VM public IP |
| `VM_USER` | `ubuntu` (or your user) |
| `VM_SSH_KEY` | Private SSH key (PEM) for the VM |
| `HEALTH_CHECK_KEY` | One of your `API_KEYS` values |

**Free infrastructure options:**

| Need | Free option |
|------|-------------|
| VM / compute | Oracle Cloud Always Free (4 OCPUs, 24 GB ARM) |
| PostgreSQL | Neon serverless (0.5 GB free) or Oracle VM Postgres |
| Redis | Upstash free tier (10k requests/day) |
| Kafka | Upstash Kafka free tier (10 GB/month) |
| Object storage | Cloudflare R2 (10 GB free) |
| Secrets | Doppler free tier |
| Log monitoring | Grafana Cloud free (50 GB logs, 14-day retention) |
| Metrics | Grafana Cloud free (10k metrics/day) |

---

### Troubleshooting

| Issue | Fix |
|---|---|
| Services stuck in "starting" | Increase Docker Desktop RAM to ≥ 8 GB and retry |
| MLflow not loading | Wait 30s after `docker compose up`; check `docker logs supply-chain-mlflow` |
| ksqlDB OOM-killed (exit 137) | Already fixed in v8.0 (heap capped at 512m, `mem_limit: 768m`). If it still fails, increase Docker Desktop RAM to ≥ 10 GB. |
| ksqlDB streams empty after restart | Run `curl -X POST http://localhost:8000/streaming/init` then produce Kafka events |
| Dagster assets stale | Click **Materialize all** in Dagster UI at http://localhost:3001 |
| Jaeger shows no traces | Make at least one API request first; `OTEL_ENABLED=true` must be set in `.env` |
| ML predict returns heuristic | Materialize `gold_delay_model` in Dagster first to train and register the model |
| Prophet forecast missing | Materialize `gold_demand_forecast` in Dagster; requires orders data to be seeded |
| `soda` command not found | Use `python -m soda scan ...` instead |
| `/orders?limit=10` — zsh glob error | Quote the URL: `curl "http://localhost:8000/orders?limit=10"` |
| `DATABASE_URL` connection refused | Confirm `POSTGRES_PORT=5433` in `.env`; host is `localhost` outside Docker |
| Grafana shows no data | Run `scripts/seed_db.py` first. If datasource shows "Connection refused", restart Grafana: `docker compose restart grafana` |
| Loki datasource — no logs | Wait ~30s for Alloy to discover containers. Verify with: `curl http://localhost:3100/ready` |
| API returns 401 Unauthorized | Set `API_KEYS=` in `.env` (empty = dev mode, auth disabled), or pass `Authorization: Bearer <key>` |
| CI docker-validate fails on prod file | Ensure your workflow runs `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` (not the prod file alone — it's an override) |

---

## Local Development (without Docker)

Run only the API and tests locally — useful for fast iteration:

```bash
# 1. Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install API dependencies
pip install -r requirements-api.txt

# 3. Set environment variables (or use a .env file with python-dotenv)
export DATABASE_URL=postgresql://supplychain:supplychain_secret@localhost:5433/supply_chain_db
export ANTHROPIC_API_KEY=sk-ant-...
export GOLD_PATH=data/gold
export SILVER_PATH=data/silver
export BRONZE_PATH=data/bronze

# 4. Run database migrations
alembic upgrade head

# 5. Start FastAPI
uvicorn api.main:app --reload --port 8000

# 6. Run tests (no live DB needed)
pytest tests/ -v -m "not docker_only"
```

For Dagster pipeline development:
```bash
pip install -r requirements-dagster.txt
dagster dev -m pipeline.definitions_medallion
```

---

## Database Migrations (Alembic)

```bash
# Apply all migrations
alembic upgrade head

# Check current revision
alembic current

# Create a new migration
alembic revision --autogenerate -m "add my_table"
```

Migration files in `alembic/versions/`:
| Revision | Description |
|---|---|
| `001` | Initial schema — orders, suppliers, deviations, order_events |
| `002` | Add pending_actions table |
| `003` | Add indexes + outcome tracking columns |
| `004` | Add confidence column to pending_actions |
| `005` | Add ontology_constraints table |
| `006` | Add supplier_policies table (Glass-Box Autonomy) |

---

## Testing

### Unit + Integration Tests

```bash
# Run all tests (no Docker required)
pytest tests/ -q
# Result: 133 passed, 3 skipped
# Skipped: Kafka broker tests, Dagster materialisation tests (require full Docker stack — pass there)

# Run a specific file
pytest tests/test_api_health.py -v
pytest tests/test_ml_scoring.py -v
pytest tests/test_openboxes_connector.py -v

# Run with coverage
pytest tests/ --cov=api --cov=ingestion --cov=reasoning
```

**Test coverage by area:**

| Area | File | Notes |
|---|---|---|
| API health + endpoints | `test_api_health.py` | All routes, status codes, response shapes |
| Orders API | `test_orders.py` | Pagination, filters, delay predictions, timeline |
| Suppliers API | `test_suppliers.py` | Risk matrix, cost analytics, benchmarks, policy CRUD |
| Alerts API | `test_alerts.py` | Severity filter, trend, financial impact enrichment |
| ML scoring | `test_ml_scoring.py` | XGBoost predict, heuristic fallback |
| AI reasoning | `test_ai_reasoning.py` | Claude analysis, quality scoring, multi-model fallback |
| OpenBoxes connector | `test_openboxes_connector.py` | Mock mode, field flattening, ontology normalisation |
| Ontology | `test_ontology.py` | Field mapping, constraint validation, negative value guard |
| Action executor | `test_action_executor.py` | Confidence gate, policy gate, REROUTE/EXPEDITE/ESCALATE |
| Event sourcing | `test_events.py` | Append-only log, point-in-time replay |
| Critical paths (v9.0) | `test_critical_paths.py` | 62 tests: 404s, 422s, edge cases, rate limit, auth, lineage |
| Kafka / Dagster | _(3 skipped locally)_ | Pass inside Docker stack |

CI runs on every push to `main` and `ujjwal` branches via GitHub Actions (`.github/workflows/ci.yml`).

---

### End-to-End Test Checklist

After `docker compose up --build -d`, run this sequence to verify the full stack:

```bash
# 1. Stack health
curl http://localhost:8000/health

# 2. Seed + ingest via OpenBoxes (primary source)
docker exec supply-chain-api python scripts/seed_db.py
docker exec supply-chain-producer python ingestion/openboxes_connector.py &
# Wait 10s, then verify orders landed:
curl "http://localhost:8000/orders?limit=5"

# 3. Ontology normalisation
curl -X POST http://localhost:8000/ontology/normalize \
  -H "Content-Type: application/json" \
  -d '{"po_number":"ORD-E2E","vendor":"SUP-001","sku":"WIDGET-A","qty":100,"eta":"2026-06-01"}'
# Expect: normalized.order_id="ORD-E2E", normalized.supplier_id="SUP-001"

# 4. AI deviation analysis (multi-model)
curl -X POST http://localhost:8000/ai/analyze-scored \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Supplier SUP-001 has a 40% delay rate this week. Recommend actions."}'
# Expect: quality_score > 0.4, model_used="claude-sonnet-4-6"

# 5. ML delay prediction
curl -X POST http://localhost:8000/ml/predict \
  -H "Content-Type: application/json" \
  -d '{"supplier_id":"SUP-001","region":"APAC","quantity":500,"unit_price":45,"order_value":22500,"inventory_level":60}'
# Expect: is_delayed (bool), probability (float), model_version

# 6. Financial impact scoring
curl "http://localhost:8000/alerts/enriched?limit=5"
# Expect: cost_impact_usd, risk_tier on each alert

# 7. Glass-box supplier policy
curl http://localhost:8000/suppliers/SUP-001/policy
curl -X PUT http://localhost:8000/suppliers/SUP-001/policy \
  -H "Content-Type: application/json" \
  -d '{"require_approval_at_severity":"HIGH","require_approval_above_value":25000}'

# 8. Dagster medallion pipeline
docker exec supply-chain-dagster-webserver \
  dagster asset materialize --select "*" -m pipeline.definitions_medallion
# Expect: all assets PASS

# 9. dbt transforms (run inside dagster container)
docker exec supply-chain-dagster-webserver \
  dbt deps --profiles-dir /opt/dagster/app/transforms --project-dir /opt/dagster/app/transforms
docker exec supply-chain-dagster-webserver \
  dbt run --profiles-dir /opt/dagster/app/transforms --project-dir /opt/dagster/app/transforms
# Expect: PASS=5 WARN=0 ERROR=0

# 10. Dashboard pages
open http://localhost:3000           # Control Tower
open http://localhost:3000/alerts    # Alerts
open http://localhost:3000/orders    # Orders
open http://localhost:3000/analytics # Delay predictions + cost analytics
open http://localhost:3000/network   # Network graph
```

**Expected result:** All 10 checks pass with no errors.

---

## Data Contracts (Soda Core)

```bash
pip install soda-core soda-core-postgres
soda scan -d supply_chain_db -c contracts/soda_connection.yml contracts/orders.yml
```

Contracts defined in `contracts/`:
- `orders.yml` — 11 checks: row count, nulls, duplicates, valid status enum, delay day bounds, freshness
- `silver_orders.yml` — silver layer post-transform quality gate

---

## Project Structure

```
supply-chain-os/
├── .github/workflows/ci.yml      # 6-job CI/CD: test + secret-scan + dbt + docker + auto-tag + deploy
├── alembic/                       # Database migrations (6 revisions)
│   └── versions/
├── api/                           # FastAPI application
│   ├── auth.py                    # API key middleware (Bearer + X-API-Key; disabled if API_KEYS unset)
│   ├── routers/                   # 15 routers: orders, suppliers, alerts, ontology, ml, ai, events...
│   ├── database.py                # SQLAlchemy async engine
│   ├── event_store.py             # Append-only order_events store
│   ├── models.py                  # SQLAlchemy ORM models (incl. SupplierPolicy)
│   └── telemetry.py               # OpenTelemetry setup
├── assets/                        # README screenshots + GIFs
├── contracts/                     # Soda Core data quality contracts
├── dashboard/                     # Next.js 14 App Router (9 pages)
├── docker/
│   ├── alloy/config.alloy         # Grafana Alloy: Docker log discovery → Loki; FastAPI metrics → Prometheus
│   ├── grafana/provisioning/
│   │   └── datasources/
│   │       ├── postgres.yml        # PostgreSQL datasource
│   │       └── loki.yml            # Loki + Prometheus datasources (auto-provisioned)
│   ├── prometheus/prometheus.yml   # Prometheus scrape config (FastAPI + Alloy)
│   └── ...                        # Dockerfiles, dagster.yaml, etc.
├── ingestion/                     # openboxes_connector (primary), Kafka producer, pg-writer, batch_loader
├── integrations/
│   └── action_executor.py         # Autonomous action execution — confidence gate + per-supplier policy gate
├── pipeline/                      # Dagster: medallion assets, sensors, ML, Graph ML
│   ├── assets_medallion.py        # Bronze/Silver/Gold + XGBoost + Prophet assets
│   ├── ml_model.py                # XGBoost training + MLflow logging
│   ├── demand_forecast.py         # Prophet 30-day forecasting
│   ├── graph_ml.py                # NetworkX betweenness + cascade risk
│   ├── lineage_resource.py        # OpenLineage START/COMPLETE/FAIL emitter
│   └── sensors.py                 # Self-healing sensor (auto-retry after 3 failures)
├── quality/                       # Great Expectations suites
├── reasoning/
│   └── engine.py                  # Multi-model AI: Claude + GPT-4o fallback + quality score
├── scripts/                       # Seed, sync, and data download scripts
├── streaming/                     # ksqlDB SQL + Python client
├── tests/                         # 133 pytest tests (130 pass, 3 skip without Docker)
│   └── test_critical_paths.py     # 62 critical-path tests added in v9.0
├── transforms/                    # dbt project (staging + marts + dbt-expectations)
├── docker-compose.yml             # 20-service stack (dev)
├── docker-compose.prod.yml        # Production overlay: loopback ports, Redis AUTH, no source mounts
├── .env.example                   # ~60 documented env vars
├── requirements-api.txt           # FastAPI + ML dependencies
├── requirements-dagster.txt       # Dagster + dbt + PySpark dependencies
└── requirements-ingestion.txt     # Kafka + ingestion dependencies
```
