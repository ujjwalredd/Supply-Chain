---
name: mlflow-governance
description: Govern ML model lifecycle — drift detection, retraining triggers, promotion decisions
---

## System Context

MLflow runs at `http://mlflow:5000` (internal).
Experiment: `supply_chain_delay_prediction` (experiment_id=1)
Model: `supply_chain_delay_model`
Baseline stored in Redis key: `mlflow:baseline` (JSON: {roc_auc, accuracy, run_id})

## Model Lifecycle

```
Training (Dagster gold_delay_model) → MLflow run logged
         ↓
mlflow_guardian detects new run
         ↓
Compares roc_auc vs baseline (Redis)
         ↓
If improved AND roc_auc >= 0.60 → Claude promotion decision (tool_use)
         ↓
If promoted → update baseline in Redis, transition model stage to Production
```

## Promotion Rules (HARD — never override)

1. `roc_auc >= 0.60` — absolute floor, never promote below
2. `train_rows >= 100` — never promote with too little data
3. New model must be **strictly better** than current production
4. Claude makes promotion decision via `model_promotion_decision` tool_use (not free text)

## Retraining Triggers

- `roc_auc` drop > 5% from baseline → trigger `medallion_incremental`
- Model age > 24h with no successful run → trigger `medallion_incremental`
- 30-minute cooldown between retraining triggers (prevents thrashing)

## Computed Features Integration

The `feature_engineer` agent writes 5 AI-generated features to:
`/data/gold/computed_features/features.parquet`

These are automatically merged into `gold_delay_model` training by `assets_medallion.py`.
Current features (as of last run): order_value_per_unit, delay_rate_ratio, trust_score_inverse,
is_high_risk_supplier, quantity_price_interaction.

A roc_auc jump after feature regeneration is expected and healthy — do NOT flag as anomaly.

## Diagnosing Model Issues

Current production metrics:
- Baseline roc_auc: ~0.86-0.89 (after computed features)
- Accuracy: ~0.979
- Train rows: ~7200-9000

If `mlflow_guardian` shows `drop > 0.05` (> 5% drop):
1. Check if it's a data quality issue (silver_agent may have logged issues)
2. Check if computed features changed significantly
3. If unexplained → issue correction to mlflow_guardian: "force retraining with cooldown reset"

## Redis Baseline Management

The baseline is the reference point for drift detection.
If baseline gets corrupted or too stale:
- Issue correction to mlflow_guardian: "reset baseline" → clears Redis key → next run re-establishes it

## Critical Rules

- NEVER roll back a model without human approval — production model affects live order routing
- A roc_auc of 0.862 is excellent for supply chain delay prediction
- Model v1-v14 history in MLflow — use `get_mlflow_model_status` to see current stage
