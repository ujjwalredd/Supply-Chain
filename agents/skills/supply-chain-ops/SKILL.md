---
name: supply-chain-ops
description: Overall supply chain platform operations — agent roster, dependencies, escalation paths
---

## Platform Overview

Adopt Supply Chain AI OS is a fully autonomous 13-agent system running on 22 Docker containers.
All agents run as daemon threads in a single `supply-chain-agents` container.
Container image: `supply-chain-os-agents` built from `docker/Agents.Dockerfile`.

## Agent Roster and Dependencies

| Agent | Interval | Depends On | Failure Impact |
|---|---|---|---|
| kafka_guardian | 30s | Kafka, Redis | Message ingestion stops |
| dagster_guardian | 120s | Dagster webserver (port 3000) | Pipeline automation stops |
| bronze_agent | 300s | Dagster, /data/bronze/ | Silver/Gold validation goes blind |
| silver_agent | 300s | /data/silver/ | Gold validation goes blind |
| gold_agent | 600s | /data/gold/ | ML features stale |
| medallion_supervisor | 180s | All medallion agents | Data contract unenforced |
| ai_quality_monitor | 60s | PostgreSQL pending_actions | AI quality checks skip |
| database_health | 60s | PostgreSQL | DB issues undetected |
| orchestrator | 300s | All agents, Redis pub/sub | No cross-agent coordination |
| data_ingestion | 60s | /data/source/, Redis, Dagster | New data not auto-ingested |
| mlflow_guardian | 300s | MLflow, Redis, Dagster | Model drift undetected |
| feature_engineer | 900s | /data/gold/, Dagster | ML features not updated |
| dashboard_agent | 600s | Grafana, Redis, /data/gold/ | Dashboard goes stale |

## Medallion Pipeline Data Flow

```
/data/source/*.csv → DataIngestionAgent → Dagster → Bronze → Silver → Gold
                                                                   ↓
                                                           gold_delay_model (XGBoost)
                                                                   ↓
                                                           computed_features/ (FeatureEngineer)
                                                                   ↓
                                                           MLflow Production Model
```

## Key Paths (all in the agents container)

- Source data: `/data/source/`
- Bronze: `/data/bronze/<table>/data.parquet`
- Silver: `/data/silver/<table>/data.parquet`
- Gold: `/data/gold/<table>/data.parquet`
- Computed features: `/data/gold/computed_features/features.parquet`
- Generated loaders: `/data/source/_loaders/`
- Memories: `/app/agents/memories/`

## Startup Sequence (normal)

1. Infrastructure starts (Postgres, Redis, Kafka, Dagster) — 45s wait
2. Agents start staggered (2s apart) — 26s for all 13
3. First useful heartbeats appear ~70s after `docker compose up`
4. Dagster webserver fully ready at ~120s
5. First pipeline run starts at ~130s (dagster_guardian triggers it)
6. Bronze/Silver/Gold parquet files appear at ~150-180s

## Correlated Failure Patterns (Critical for Orchestrator)

| Pattern | Root Cause | Action |
|---|---|---|
| bronze_agent + silver_agent + gold_agent all report missing files | Dagster not running | Fix dagster_guardian → trigger full pipeline |
| dagster_guardian DEGRADED + medallion_supervisor alerts | Wrong DAGSTER_WEBSERVER_URL or port | Check env var, issue correction to dagster_guardian |
| mlflow_guardian shows roc_auc drop + feature_engineer shows new features | Expected — model updating | No action needed |
| database_health shows high connections + ai_quality_monitor shows stuck actions | PostgreSQL pool exhausted | Alert HIGH, reduce connection count |
| All agents STARTING but no HEALTHY after 3 min | Container crash loop | Check `docker logs supply-chain-agents` |

## Correction Dispatch Guide

When issuing corrections to agents, use these exact instruction patterns:
- dagster_guardian: `"trigger incremental"` or `"trigger full pipeline"` or `"reset consecutive error counter"`
- mlflow_guardian: `"force retraining"` or `"reset baseline"` or `"trigger retraining"`
- feature_engineer: `"force regeneration"` or `"trigger incremental pipeline"`
- bronze_agent: `"trigger materialization"`
- silver_agent: `"trigger materialization"`

## Escalation Rules

1. Single agent DEGRADED → issue correction, monitor next cycle
2. 2+ agents DEGRADED (same domain) → correlated failure → investigate root cause first, then correct
3. 3+ agents DEGRADED (cross-domain) → systemic failure → alert CRITICAL + human_intervention_needed=True
4. All agents offline → container crash → human_intervention_needed=True immediately
