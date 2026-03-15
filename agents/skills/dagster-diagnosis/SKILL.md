---
name: dagster-diagnosis
description: Diagnose and self-heal Dagster pipeline failures in the Adopt Supply Chain AI OS
---

## System Context

Dagster runs as 3 containers:
- `dagster-webserver` — HTTP API on port 3000 (internal), 3001 (host). GraphQL at `/graphql`.
- `dagster-daemon` — Executes schedules and sensors.
- `dagster-code-server` — gRPC on port 4266. Hosts the actual pipeline code.

Repository location name: `pipeline.definitions:defs`
Repository name: `__repository__`

## Jobs

| Job Name | Steps | Trigger |
|---|---|---|
| `medallion_full_pipeline` | All 16 assets (Bronze+Silver+Gold+ML+Forecast+Risk) | New data, daily schedule |
| `medallion_incremental` | bronze_orders → silver_orders → gold_orders_ai_ready → gold_delay_model | Feature updates, incremental data |

## Diagnosing a Failed Run

Use `get_dagster_recent_runs` to check recent run statuses. If runs show FAILURE:

1. Check `error.message` from the run details tool.
2. Common failures:
   - `"Connection refused"` on dagster-webserver → webserver not yet ready, wait and retry
   - `"No module named"` → pipeline code not installed, needs rebuild
   - `"FileNotFoundError"` on parquet → source data missing, trigger `medallion_full_pipeline`
   - `"Two Definitions objects"` → code server started with wrong `-a` flag, needs restart
   - `"FUSE errno 35"` on macOS → transient file lock, retry same job
3. Step failures: check which step failed. `bronze_*` failures usually cascade to silver/gold.

## Self-Healing Actions

- **Stale runs (> 2h old)** → trigger `medallion_incremental` via `trigger_dagster_job`
- **3+ consecutive FAILURE** → trigger `medallion_full_pipeline` (full rebuild)
- **Connection refused to webserver** → issue correction to dagster_guardian: "wait 60s and retry"
- **No runs in 24h** → trigger `medallion_full_pipeline` immediately

## GraphQL Patterns

Check recent runs:
```
{ runsOrError(limit: 5, filter: {statuses: [FAILURE, SUCCESS]}) {
    ... on Runs { results { runId status startTime endTime pipelineName
      stats { ... on RunStatsSnapshot { stepsFailed stepsSucceeded } }
    }}
}}
```

Trigger a job: use `trigger_dagster_job` tool with job_name and reason.

## Critical Rules

- NEVER trigger both jobs simultaneously — they share assets
- Always wait at least 30s after triggering before checking status
- If `medallion_incremental` fails 3x → escalate to `medallion_full_pipeline`
- The `gold_delay_model` step trains XGBoost + logs to MLflow — it is the most expensive step (~30s)
