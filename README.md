# Supply Chain AI OS — v7.0

![Landing Page](assets/landing_page.png)

An **end-to-end AI-native supply chain control tower** demonstrating senior data engineering, MLOps, and AI engineering skills.

Built on a production-grade 17-service Docker stack with real-time streaming, medallion lakehouse, ML model training & registry, distributed tracing, and autonomous AI reasoning.

---

## Architecture at a Glance

```
Kafka (events) ──► ksqlDB (streaming aggregations)
       │                        │
       ▼                        ▼
pg-writer ──► PostgreSQL ◄── FastAPI ──► Next.js 14
       │              │          │
       ▼              │          ▼
MinIO/Delta      Dagster ──► MLflow
(bronze/silver/gold)    │
       │           ▼
       └── XGBoost model ──► /ml/predict
                │
                ▼
           OpenTelemetry ──► Jaeger
```

---

## Quick Start

```bash
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env

docker compose up --build -d

docker exec supply-chain-api python scripts/seed_db.py
docker exec supply-chain-api python scripts/download_supply_chain_data.py
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |
| Dagster | http://localhost:3001 |
| Grafana | http://localhost:3002 |
| MLflow | http://localhost:5001 |
| Jaeger (traces) | http://localhost:16686 |
| ksqlDB | http://localhost:8088 |
| MinIO | http://localhost:9001 |

---

## Stack

| Layer | Technology |
|---|---|
| Ingestion | Kafka, kafka-python, JSON Schema validation |
| Lakehouse | Delta Lake, Parquet (partitioned by date), MinIO |
| Transform | dbt (incremental models, dbt-expectations) |
| Orchestration | Dagster 1.12+ (medallion assets, freshness policies, self-healing sensor) |
| ML | XGBoost, MLflow (experiment tracking + model registry) |
| Forecasting | Prophet (30-day demand forecast) |
| Graph ML | NetworkX (betweenness centrality, cascade risk) |
| Streaming | ksqlDB (5-min rolling delay rate, region demand) |
| API | FastAPI, SQLAlchemy async, PostgreSQL |
| Tracing | OpenTelemetry → Jaeger |
| AI Reasoning | Claude sonnet-4-6 + GPT-4o fallback + quality scoring |
| Data Quality | Soda Core contracts, Great Expectations |
| Event Sourcing | append-only `order_events` table (point-in-time recovery) |
| CI/CD | GitHub Actions (pytest + dbt validate + docker-compose + auto-tag) |
| Frontend | Next.js 14 App Router, Tailwind CSS |
| Observability | Prometheus, Grafana, OpenTelemetry |

---

## Data Engineering Features (v7.0 — All Built & Tested)

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

## Extraordinary Features (v7.0)

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

### Tier 3 — Differentiators

| Feature | What it does | Key files |
|---|---|---|
| **Self-Healing Pipeline** | Dagster sensor auto-triggers RunRequest after 3 consecutive failures; writes JSON audit log | `pipeline/sensors.py` |
| **Multi-Model AI + Quality Scoring** | Claude primary; GPT-4o fallback on quality < 0.4; scores responses 0–1; `POST /ai/analyze-scored` | `reasoning/engine.py`, `api/routers/ai.py` |

---

![Landing Page](assets/Grafana.png)

## API Endpoints

```
GET  /health                          — dependency health check
GET  /orders                          — paginated orders
GET  /suppliers                       — supplier risk matrix
GET  /alerts                          — active deviations
GET  /forecasts                       — KPI forecasts
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
GET  /metrics                         — Prometheus metrics
WS   /ws                              — real-time deviation feed
```

---

## Medallion Lakehouse Assets (Dagster)

```
Bronze: bronze_orders               (raw CSV/Kafka → Delta + partitioned Parquet)
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

## Docker Services (17 total)

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
| grafana | 3002 | Metrics dashboards |
| jaeger | 16686 | Distributed traces (OTLP gRPC) |

---

## Environment Variables

See `.env.example` for the full list. Key additions in v7.0:

```env
MLFLOW_TRACKING_URI=http://localhost:5001
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
KSQLDB_URL=http://localhost:8088
OPENAI_API_KEY=          # optional — enables GPT-4o fallback
```

---

## End-to-End Running Guide

### Step 1 — Start the full stack

```bash
cp .env.example .env
# Edit .env and set:
#   ANTHROPIC_API_KEY=sk-ant-...       (required — AI reasoning)
#   OPENAI_API_KEY=sk-...              (optional — GPT-4o fallback)

docker compose up --build -d
```

Wait ~60 seconds for all services to become healthy:

```bash
docker compose ps   # all 17 services should show "healthy" or "running"
```

---

### Step 2 — Seed the database and load data

```bash
docker exec supply-chain-api python scripts/seed_db.py
docker exec supply-chain-api python scripts/download_supply_chain_data.py
```

This creates orders, suppliers, ontology constraints, and historical events in PostgreSQL.

---

### Step 3 — Start the Kafka event stream

```bash
# Produce ~500 synthetic supply chain events to Kafka
docker exec supply-chain-producer python ingestion/producer.py --count 500

# The pg-writer consumer is already running inside the container
# It consumes from Kafka → PostgreSQL, with DLQ on parse failure
```

---

### Step 4 — Run the Dagster medallion pipeline

Open **Dagster UI** at http://localhost:3001

1. Click **Assets** in the left sidebar
2. Click **Materialize all** to run the full Bronze → Silver → Gold pipeline
3. Assets in order:
   - `bronze_orders` — raw CSV/Kafka → Delta + partitioned Parquet
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

### Step 5 — MLflow: View experiments and model registry

Open **MLflow UI** at http://localhost:5001

**After `gold_delay_model` materializes:**
- Click **Experiments** → `delay_prediction` — view accuracy, AUC, feature importances
- Click **Models** → `delay_classifier` — view registered versions and promotion stage

**Test the ML prediction API:**
```bash
curl -X POST http://localhost:8000/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_id": "PT-01",
    "region": "BOSTON",
    "quantity": 500,
    "unit_price": 45.0,
    "order_value": 22500.0,
    "inventory_level": 60.0
  }'
# Returns: { "is_delayed": true, "probability": 0.99, "confidence": "HIGH", "model_version": "local:xgboost" }
```

**Promote a model to Production (optional):**
```bash
# In MLflow UI: Models → delay_classifier → version → Stage → Transition to Production
# Or via API:
curl -X PATCH http://localhost:5001/api/2.0/mlflow/model-versions/update \
  -H "Content-Type: application/json" \
  -d '{"name": "delay_classifier", "version": "1", "stage": "Production"}'
```

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
# ai/analyze requires a seeded deviation_id from /alerts
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
# Get recent events
curl http://localhost:8000/events/recent

# Full history for a specific order
curl http://localhost:8000/events/orders/ORD_001/history

# Point-in-time state recovery
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

---

### Step 9 — Grafana dashboards

Open **Grafana** at http://localhost:3002 (admin/admin)

- **Supply Chain Overview** — order volumes, delay rates, supplier risk
- **FastAPI Metrics** — request rate, latency p50/p95/p99, error rate (from `/metrics`)

---

### Step 10 — Data contracts (Soda Core)

Run quality checks against the live database:

```bash
pip install soda-core soda-core-postgres

# If 'soda' is not in PATH, use:
python -m soda scan -d supply_chain_db \
  -c contracts/soda_connection.yml \
  contracts/orders.yml

# Checks: row count, nulls, duplicates, valid status enum, delay bounds, freshness
```

---

### Troubleshooting

| Issue | Fix |
|---|---|
| MLflow not loading | Wait 30s after `docker compose up`; check `docker logs supply-chain-mlflow` |
| ksqlDB OOM-killed (exit 137) | Run `docker compose up -d ksqldb-server ksqldb-init` to restart; may need to increase Docker Desktop memory beyond 4 GB |
| ksqlDB streams empty after restart | Run `curl -X POST http://localhost:8000/streaming/init` then produce Kafka events |
| Dagster assets stale | Click **Materialize all** in Dagster UI at http://localhost:3001 |
| Jaeger shows no traces | Make at least one API request first; OTEL_ENABLED=true must be set in .env |
| ML predict returns heuristic | Materialize `gold_delay_model` in Dagster first to train and register the model |
| Prophet forecast missing | Materialize `gold_demand_forecast` in Dagster; requires orders data to be seeded |
| `soda` command not found | Use `python -m soda scan ...` instead |
| `/orders?limit=10` — zsh glob error | Quote the URL: `curl "http://localhost:8000/orders?limit=10"` |

---

## Testing

```bash
python -m pytest tests/ -v
# 62 passed, 8 skipped (kafka/dagster tests skip locally, pass in Docker)
```

---

## Data Contracts (Soda Core)

```bash
pip install soda-core soda-core-postgres
soda scan -d supply_chain_db -c contracts/soda_connection.yml contracts/orders.yml
```

---

## Project Structure

```
supply-chain-os/
├── .github/workflows/ci.yml      # CI/CD pipeline
├── api/                           # FastAPI: 13 routers, event_store, telemetry
├── contracts/                     # Soda Core data contracts
├── dashboard/                     # Next.js 14 App Router
├── docker/                        # Dockerfiles + Grafana provisioning
├── ingestion/                     # Kafka producer + pg-writer + batch loader
├── pipeline/                      # Dagster: assets, sensors, ml_model, graph_ml
├── reasoning/engine.py            # Multi-model AI + quality scoring
├── streaming/                     # ksqlDB SQL + Python client
├── tests/                         # 62 pytest tests
├── transforms/                    # dbt models + packages.yml + contracts
└── docker-compose.yml             # 17-service production stack
```
