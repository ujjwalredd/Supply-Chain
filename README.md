# Supply Chain AI OS

An AI-native supply chain control tower — v6.0. Real-time event streaming, autonomous deviation detection, Claude-powered reasoning, proactive delay forecasting, cost analytics, supplier benchmarking, outcome tracking, and a full-featured Next.js dashboard — all running locally in Docker.

**Live demo:** [supply-chain-silk.vercel.app](https://supply-chain-silk.vercel.app)

---

## What it does

The system ingests order and supplier events from Kafka, detects deviations (delays, stockouts, anomalies), runs them through Claude for root-cause analysis, and executes recommended actions autonomously when confidence exceeds a configurable threshold.

| Capability | Implementation |
|---|---|
| Live event ingest | Kafka producer at 50+ events/min with supplier state machines and causality chains |
| Deviation detection | Automatic DELAY / STOCKOUT / ANOMALY with MEDIUM / HIGH / CRITICAL severity |
| AI root-cause analysis | Claude Sonnet 4.6 via `tool_use` — structured output, no JSON fragility |
| Autonomous execution | REROUTE · EXPEDITE · SAFETY\_STOCK · ESCALATE based on confidence threshold |
| Supplier scorecard | Weekly on-time %, delay trend, and deviation frequency per supplier |
| What-if simulator | Model volume shifts between suppliers — cost, risk, and constraint analysis via Claude |
| Bulk triage | Analyze all open CRITICAL deviations at once — ranked action list in one shot |
| Order timeline | Full lifecycle from ORDER\_PLACED → IN\_TRANSIT → deviations → DELIVERED |
| Root cause clusters | Deviation patterns grouped by type + supplier with critical count |
| Audit trail | Every AI recommendation and executed action logged with full context |
| Financial impact | Carrying cost + delay cost + stockout penalty computed before every AI call |
| Ontology layer | 19 business rules (SLA tiers, penalties, dependency caps) injected into every prompt |
| Risk forecast | Time-decay scoring: `delay_probability × order_value × urgency` |
| Proactive delay scoring | Every in-flight order scored by delay probability using trust score + historical avg delay + urgency |
| Cost analytics | Per-supplier: total spend, delay cost exposure, cost efficiency score |
| Supplier benchmarks | Composite on-time/trust ranking with optional product-level filter |
| Outcome tracking | Every executed action can be resolved with an outcome note — feeds back into success rate tracking |
| Feedback loop | Per-action-type success rates displayed in audit trail header strip |
| Alert fatigue suppression | pg_writer skips CRITICAL insertions when supplier already has 5+ in 24h |
| Data lake | Dagster 14-asset medallion pipeline: bronze → silver → quality gate → dbt → gold |
| dbt data quality | Schema tests (not_null, unique, accepted_values) + singular SQL assertions on all marts |
| Incremental dbt models | `fct_shipments` + `dim_suppliers` use `materialized='incremental'` — only new rows processed |
| Dead Letter Queue | pg_writer sends parse/validation failures to `supply-chain-dlq` Kafka topic |
| Delta OPTIMIZE + VACUUM | Dagster `delta_maintenance` asset compacts small files and vacuums stale data after every gold run |
| Partitioned Parquet | batch_loader writes `year=/month=/day=` date partitions alongside Delta writes |
| Kafka schema validation | Producer validates every event against JSON Schema before producing — invalid events logged and skipped |
| OpenLineage | `lineage_resource.py` emits START/COMPLETE/FAIL events to Postgres + optional Marquez; `/lineage` API endpoint |
| Freshness policies | All gold Dagster assets enforce `FreshnessPolicy(maximum_lag_minutes=360)` — alerts if stale |
| dbt-expectations | `calogica/dbt_expectations` package with column-range tests on fct_shipments and dim_suppliers |

---

## Architecture

```
CSV Datasets ──► batch_loader
                     │
Kafka Producer       │
(50+ events/min)     │
     │               ▼
     ├──► pg_writer ──► PostgreSQL ──► FastAPI :8000
     │         │             │              │
     │    Redis pub/sub    Alembic       /orders
     │         │          migrations    /suppliers
     │         ▼                        /alerts
     │    WebSocket ──────────────►    /actions
     │                           │    /scorecard
     └──► consumer.py            │    /ai/analyze
               │            Next.js    /ai/bulk
               ▼             :3000     /ai/whatif
          Delta Lake            │
               │         Dashboard pages:
               ▼         • Overview (KPIs + graph)
          Dagster          • Deviations + clusters
          Pipeline         • Bulk triage
          14 assets        • Orders + timeline
               │           • Suppliers
               ▼           • Scorecard
           MinIO            • What-If simulator
         :9001              • Actions + audit trail
                            • Network graph
```

**Key services:** PostgreSQL · Redis · Kafka · MinIO · FastAPI · Next.js · Dagster

---

## Dashboard pages

| Page | URL | What's on it |
|---|---|---|
| Overview | `/` | KPI cards, deviation feed, supplier risk chart, forecast, network graph |
| Deviations | `/alerts` | Deviation feed, bulk AI triage, root cause clusters, actions log |
| Orders | `/orders` | Filterable order table with per-row timeline drawer |
| Suppliers | `/suppliers` | Supplier list with trust scores and risk metrics |
| Scorecard | `/scorecard` | Weekly trend charts (on-time %, delay, deviations) per supplier |
| Analytics | `/analytics` | Proactive delay predictions, deviation trend, risk forecast, cost analytics, supplier benchmarks |
| Actions | `/actions` | Pending actions + full audit trail with AI reasoning |
| Network | `/network` | Interactive plant → port graph (drag, pan, zoom) |
| What-If | `/whatif` | Volume shift simulator with Claude streaming analysis |

---

## Quick start

### Requirements

- Docker Desktop with Compose v2
- An Anthropic API key (only needed for AI features — all other endpoints work without it)

### 1. Clone and configure

```bash
git clone https://github.com/ujjwalredd/Supply-Chain.git
cd supply-chain-os
cp .env.example .env
```

Edit `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

All other `.env` values work as defaults.

### 2. Start the stack

```bash
docker compose up --build -d
```

First build takes ~5 minutes. Subsequent starts take ~30 seconds using cached layers.

### 3. Check containers

```bash
docker compose ps
```

All services should show `Up` or `Up (healthy)`:

```
supply-chain-postgres       Up (healthy)  :5433
supply-chain-redis          Up (healthy)  :6379
supply-chain-kafka          Up (healthy)  :9092
supply-chain-minio          Up (healthy)  :9000/:9001
supply-chain-api            Up (healthy)  :8000
supply-chain-pg-writer      Up
supply-chain-producer       Up
supply-chain-dagster-*      Up            :3001
supply-chain-dashboard      Up            :3000
```

### 4. Open the dashboard

- **Dashboard** → http://localhost:3000
- **API docs** → http://localhost:8000/docs
- **Dagster UI** → http://localhost:3001
- **MinIO console** → http://localhost:9001 (`minioadmin` / `minioadmin`)
- **Grafana** → http://localhost:3002 (`admin` / `admin`)

The stack seeds 8 suppliers, 120 orders, 20 deviations, and 19 ontology constraints automatically on first start.

---

## Load real data (optional)

Download the Brunel dataset (9,215 real supply chain orders):

```bash
docker compose run --rm fastapi python scripts/download_supply_chain_data.py
docker compose run --rm fastapi python -m ingestion.batch_loader
```

Run the Dagster pipeline — open http://localhost:3001 → Assets → **Materialize all**.

Push gold data to Postgres:
```bash
docker compose exec fastapi python scripts/sync_gold_to_postgres.py
```

---

## API reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/orders` | Orders — filter by `status`, `supplier_id`, `limit` |
| `GET` | `/orders/{id}/timeline` | Full order lifecycle events |
| `GET` | `/suppliers` | All suppliers |
| `GET` | `/suppliers/risk` | Trust score, delay rate, dependency metrics |
| `GET` | `/suppliers/{id}/scorecard` | Weekly performance breakdown (`?weeks=12`) |
| `GET` | `/alerts` | Deviation alerts — filter by `severity`, `executed`, `limit` |
| `GET` | `/alerts/trend` | Deviation counts per day by severity |
| `GET` | `/alerts/clusters` | Deviations grouped by type + supplier (`?days=30`) |
| `POST` | `/alerts/{id}/dismiss` | Execute recommendation → creates `PendingAction` |
| `GET` | `/actions` | All executed recommendations |
| `GET` | `/actions/audit` | Enriched audit log with deviation + order context |
| `GET` | `/actions/stats` | MTTR — avg minutes from detection to resolution |
| `GET` | `/actions/success-rates` | Per-action-type success/failure rate aggregation |
| `POST` | `/actions/{id}/resolve` | Record outcome note + mark success or failure |
| `GET` | `/orders/delay-predictions` | All in-flight orders scored by delay probability |
| `GET` | `/suppliers/cost-analytics` | Per-supplier spend, delay cost exposure, efficiency score |
| `GET` | `/suppliers/benchmarks` | Composite on-time/trust ranking (`?product=` filter) |
| `GET` | `/forecasts/summary` | At-risk order summary |
| `GET` | `/network` | Plant → port topology |
| `GET` | `/ontology/constraints` | Business rules |
| `POST` | `/ai/analyze` | Claude structured analysis (tool\_use) |
| `POST` | `/ai/analyze/stream` | Claude analysis as SSE token stream |
| `POST` | `/ai/analyze/bulk` | Bulk triage of all open deviations (SSE stream) |
| `POST` | `/ai/whatif/stream` | Volume shift scenario analysis (SSE stream) |
| `POST` | `/ai/query/stream` | Natural language question → live data context → SSE |
| `GET` | `/lineage` | Lineage events + DAG graph (`?job_name=` filter) |
| `GET` | `/lineage/jobs` | All tracked jobs with last run status |

### SSE streaming example

```bash
curl -N -X POST http://localhost:8000/ai/analyze/stream \
  -H "Content-Type: application/json" \
  -d '{"deviation_id":"DEV-SEED-0001","deviation_type":"DELAY","severity":"HIGH"}'
```

Each event:
```
data: {"token": "The root cause..."}
```

Final event:
```
data: {"done": true, "usage": {"input_tokens": 312, "output_tokens": 487, "analysis_time_ms": 4231}}
```

---

## Deviation detection rules

`pg_writer` evaluates these rules on every Kafka event:

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

## Tests

```bash
pip install -r requirements-api.txt pytest pytest-asyncio httpx
pytest tests/ -v
```

62 tests (8 skipped when kafka/dagster not installed locally — all pass inside Docker) covering: deviation detection, Claude tool\_use, API endpoints, MTTR, delay prediction scoring, cost analytics, audit resolution, DLQ, partitioned Parquet, OpenLineage, incremental dbt config.

**dbt tests** (run inside Dagster or directly):
```bash
docker compose exec fastapi bash -c "cd /app && dbt test --profiles-dir transforms"
```
Tests: `not_null`, `unique`, `accepted_values` on all marts + 3 singular SQL assertions (`assert_no_negative_order_values`, `assert_delay_days_non_negative`, `assert_trust_score_range`).

---

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for AI endpoints only |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model ID |
| `AUTONOMY_CONFIDENCE_THRESHOLD` | `0.70` | Below this, actions downgrade to ESCALATE |
| `DATABASE_URL` | `postgresql://supplychain:supplychain_secret@postgres:5432/supply_chain_db` | |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001` | |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | |
| `POSTGRES_PORT` | `5433` | Host port — avoids conflict with local Postgres on 5432 |
| `MINIO_ROOT_USER` | `minioadmin` | |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | |
| `DB_POOL_SIZE` | `10` | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Max overflow connections |
| `DB_POOL_TIMEOUT` | `30` | Seconds before pool timeout |
| `ALLOWED_HOSTS` | *(unset)* | Comma-separated allowed hosts (TrustedHostMiddleware) |
| `ALERT_FATIGUE_THRESHOLD` | `5` | Max CRITICAL alerts per supplier per 24h |
| `KAFKA_DLQ_TOPIC` | `supply-chain-dlq` | Dead letter queue topic name |
| `MARQUEZ_URL` | *(unset)* | Optional Marquez endpoint for OpenLineage emission |
| `LINEAGE_NAMESPACE` | `supply-chain-os` | OpenLineage namespace |

---

## Project structure

```
supply-chain-os/
├── api/
│   ├── main.py                    # FastAPI app, WebSocket, Redis subscriber
│   ├── models.py                  # SQLAlchemy models
│   ├── database.py                # Async engine + session
│   └── routers/
│       ├── orders.py              # Orders + timeline endpoint
│       ├── suppliers.py           # Suppliers + scorecard endpoint
│       ├── alerts.py              # Deviations + clusters endpoint
│       ├── actions.py             # Actions + audit endpoint
│       ├── ai.py                  # analyze / bulk / whatif / query endpoints
│       ├── forecasts.py
│       ├── network.py
│       └── ontology.py
├── dashboard/                     # Next.js 14 App Router
│   ├── app/
│   │   ├── page.tsx               # Overview
│   │   ├── alerts/page.tsx        # Deviations + clusters + bulk triage
│   │   ├── orders/page.tsx        # Orders table
│   │   ├── suppliers/page.tsx     # Supplier list
│   │   ├── scorecard/page.tsx     # Supplier scorecard
│   │   ├── analytics/page.tsx     # Trend charts + heatmap
│   │   ├── actions/page.tsx       # Actions + audit trail
│   │   ├── network/page.tsx       # Network graph
│   │   └── whatif/page.tsx        # What-if simulator
│   └── components/
│       ├── KPICards.tsx
│       ├── DeviationFeed.tsx      # Live feed via WebSocket
│       ├── AIReasoningPanel.tsx   # Streaming AI drawer
│       ├── SupplyChainGraph.tsx   # Interactive SVG graph (drag/pan/zoom)
│       ├── SupplierScorecard.tsx  # Weekly trend charts (Recharts)
│       ├── WhatIfSimulator.tsx    # Volume shift form + streaming output
│       ├── BulkTriagePanel.tsx    # Bulk deviation analysis
│       ├── DeviationClusters.tsx  # Root cause cluster cards
│       ├── OrderTimeline.tsx      # Order lifecycle drawer
│       ├── AuditTrail.tsx         # Enriched audit + outcome tracking + success rates
│       ├── ProactiveDelayPanel.tsx # In-flight order delay probability scoring
│       ├── CostAnalyticsPanel.tsx # Per-supplier spend / delay cost / efficiency
│       ├── SupplierBenchmark.tsx  # Composite ranked supplier table
│       ├── DeviationTrendChart.tsx
│       ├── OrderTable.tsx         # Filterable table + timeline button
│       ├── SupplierRisk.tsx
│       ├── SupplierHeatmap.tsx
│       ├── RiskForecast.tsx
│       ├── ActionsLog.tsx
│       ├── ErrorBoundary.tsx
│       └── PanelSkeleton.tsx
├── ingestion/
│   ├── producer.py                # Kafka event producer
│   ├── pg_writer.py               # Kafka → Postgres + deviation detection + Redis pub/sub
│   ├── consumer.py                # Kafka → Delta Lake
│   └── batch_loader.py            # CSV → bronze Parquet
├── pipeline/
│   ├── assets_medallion.py        # 15 Dagster assets (incl. delta_maintenance + freshness policies)
│   ├── lineage_resource.py        # OpenLineage emitter → Postgres + optional Marquez
│   └── definitions_medallion.py   # Schedule (6h)
├── integrations/
│   └── action_executor.py         # REROUTE / EXPEDITE / SAFETY_STOCK / ESCALATE
├── reasoning/
│   └── engine.py                  # Claude tool_use + SSE + bulk triage + what-if
├── transforms/
│   ├── models/
│   │   ├── staging/               # stg_orders.sql, stg_suppliers.sql + schema tests
│   │   └── marts/                 # fct_shipments.sql, dim_suppliers.sql, agg_control_tower.sql
│   ├── tests/                     # Singular SQL assertions
│   └── dbt_project.yml
├── quality/validations.py         # Great Expectations checks
├── scripts/
│   ├── seed_db.py                 # Seed data (suppliers, orders, deviations, constraints)
│   ├── sync_gold_to_postgres.py
│   ├── sync_data_to_minio.py
│   └── download_supply_chain_data.py
├── tests/                         # 50 unit tests
├── alembic/versions/              # DB migrations
├── docker/                        # Dockerfiles + entrypoint.sh
├── docker-compose.yml             # Full 11-service stack
├── .env.example
└── pyproject.toml                 # ruff config
```

---

## Troubleshooting

**API container restarting** — Postgres or Redis not ready yet. Wait 30s, it self-recovers.
```bash
docker compose logs fastapi --tail=40
```

**Port conflict on 5432** — This stack uses port 5433. If that's also taken, set `POSTGRES_PORT=5434` in `.env`.

**AI endpoints return 503** — `ANTHROPIC_API_KEY` not set in `.env`.

**pg-writer keeps restarting** — Kafka timing issue on first boot. Self-recovers, or: `docker compose restart pg-writer`.

**Dagster UI blank** — Takes 1–2 min after Kafka is healthy. Reload http://localhost:3001.

---

## License

MIT
