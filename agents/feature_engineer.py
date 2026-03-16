"""
FeatureEngineerAgent
Model: Claude Haiku (tool_use only — structured feature suggestions)
Interval: 900s (15min)

What it does:
1. After each Gold materialization (detects via file mtime), reads gold_orders_ai_ready
2. Profiles existing features (mean, std, nulls, correlation with delay_probability)
3. Calls Claude tool_use → gets suggested new feature expressions (pandas one-liners)
4. Validates each feature:
     gate 1 — syntax check
     gate 2 — run on 20-row sample, check output is numeric/bool, no NaN explosion
     gate 6 — distribution sanity: no infinite / abs(value) > 1e10
     gate 7 — non-trivial variance: std > 0.001 (blocks constant features)
     gate 8 — novelty: max Pearson |r| with any existing column < 0.99
5. Writes validated features to /data/gold/computed_features/features.parquet
6. Writes feature manifest to /data/gold/computed_features/manifest.json
7. Triggers incremental pipeline so MLflow picks up new features

Anti-hallucination:
  - tool_use with strict schema (name, pandas_expr, dtype, description)
  - Each feature expression validated via CodeExecutor on real sample data
  - Features that produce >50% NaN or non-numeric output are rejected
  - Max 5 new features per cycle to prevent bloat
"""
import os
import json
import time
import logging
import hashlib
from pathlib import Path
from typing import Optional

import requests

from agents.base import BaseAgent, HAIKU_MODEL
from agents.tools.code_executor import CodeExecutor, CodeExecutionError

logger = logging.getLogger(__name__)

GOLD_PATH = os.getenv("GOLD_PATH", "/data/gold")
# Bug 21: standardise default port to 3000 to match data_ingestion_agent
DAGSTER_URL = os.getenv("DAGSTER_WEBSERVER_URL", "http://dagster-webserver:3000")
FEATURES_DIR = os.path.join(GOLD_PATH, "computed_features")
MAX_FEATURES_PER_CYCLE = 5
# Bug 12: reduce MAX_NAN_RATIO from 50% to 5% to properly gate high-null features
MAX_NAN_RATIO = 0.05

# ── tool schema for feature suggestions ──────────────────────────────────────
FEATURE_SUGGESTION_TOOL = {
    "name": "suggest_features",
    "description": (
        "Suggest new features that could improve supply chain delay prediction. "
        "Each feature must be expressible as a single pandas expression."
    ),
    "input_schema": {
        "type": "object",
        "required": ["features"],
        "properties": {
            "features": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "required": ["name", "pandas_expr", "dtype", "description"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Snake_case column name (no spaces)"
                        },
                        "pandas_expr": {
                            "type": "string",
                            "description": (
                                "RHS expression for: df['name'] = <expr>. "
                                "Only use columns that exist in the input. "
                                "No imports, no functions, single line."
                            )
                        },
                        "dtype": {
                            "type": "string",
                            "enum": ["float64", "int64", "bool"]
                        },
                        "description": {"type": "string"},
                        "expected_range": {
                            "type": "string",
                            "description": "E.g. '[0, 1]' or '> 0'"
                        }
                    }
                }
            }
        }
    }
}


class FeatureEngineerAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="feature_engineer",
            model=HAIKU_MODEL,
            interval_seconds=900,
            description=(
                "Auto feature engineering. "
                "Reads Gold layer, asks Claude for new features, "
                "validates them, writes to computed_features/."
            )
        )
        self._executor = CodeExecutor()
        self._last_gold_mtime: float = 0.0
        self._last_manifest_hash: str = ""

    # ── Main check ────────────────────────────────────────────────────────────
    def check(self) -> dict:
        metrics = {}
        gold_dir = Path(GOLD_PATH)

        # Find gold_orders_ai_ready parquet (file may be data.parquet inside orders_ai_ready/)
        ai_files = [
            f for f in gold_dir.rglob("*.parquet")
            if f.is_file() and "ai_ready" in str(f)
        ]
        if not ai_files:
            logger.debug("[feature_engineer] No gold ai_ready file yet")
            return {"task": "no_gold_file"}

        ai_file = ai_files[0]
        current_mtime = ai_file.stat().st_mtime

        # Only re-run if Gold was updated since last cycle
        if current_mtime <= self._last_gold_mtime:
            logger.debug("[feature_engineer] Gold unchanged — skipping")
            return {"task": "gold_unchanged|skipped"}

        logger.info(f"[feature_engineer] Gold updated — generating features from {ai_file.name}")

        # 1. Profile existing features
        profile = self._profile_gold(str(ai_file))
        if not profile.get("ok"):
            return {"task": "profile_failed"}

        existing_cols = profile["columns"]
        stats = profile["stats"]
        metrics["existing_features"] = len(existing_cols)

        # 2. Ask Claude for feature suggestions
        suggestions = self._suggest_features_llm(existing_cols, stats)
        if not suggestions:
            return {"task": "no_suggestions"}

        metrics["suggestions_received"] = len(suggestions)
        logger.info(f"[feature_engineer] Got {len(suggestions)} feature suggestions")

        # Bug 27: warn when suggestions are truncated to MAX_FEATURES_PER_CYCLE
        if len(suggestions) > MAX_FEATURES_PER_CYCLE:
            logger.warning(
                f"[feature_engineer] Received {len(suggestions)} suggestions but only processing "
                f"{MAX_FEATURES_PER_CYCLE} (MAX_FEATURES_PER_CYCLE limit). Excess suggestions dropped."
            )

        # 3. Validate each suggestion
        valid_features = []
        for feat in suggestions[:MAX_FEATURES_PER_CYCLE]:
            name = feat.get("name", "")
            expr = feat.get("pandas_expr", "")
            if not name or not expr:
                continue
            result = self._validate_feature(
                name=name,
                expr=expr,
                gold_path=str(ai_file),
            )
            if result.get("ok"):
                valid_features.append({**feat, "validated": True})
                logger.info(f"[feature_engineer] ✓ feature '{name}': {feat['description']}")
            else:
                logger.warning(
                    f"[feature_engineer] ✗ feature '{name}' rejected: {result.get('error')}"
                )

        metrics["valid_features"] = len(valid_features)

        if valid_features:
            # 4. Compute and write features parquet
            ok = self._compute_and_write_features(str(ai_file), valid_features)
            if ok:
                self._last_gold_mtime = current_mtime
                self.audit(
                    "FEATURES_GENERATED",
                    f"Generated {len(valid_features)} new features",
                    "SUCCESS",
                    {"features": [f["name"] for f in valid_features]}
                )
                # Trigger incremental so MLflow picks them up
                self._trigger_incremental()
            else:
                metrics["write_ok"] = False
        else:
            logger.info("[feature_engineer] No valid features this cycle")

        metrics["task"] = (
            f"suggestions={len(suggestions)}|"
            f"valid={len(valid_features)}|"
            f"cols={len(existing_cols)}"
        )
        return metrics

    # ── Profile Gold file ─────────────────────────────────────────────────────
    def _profile_gold(self, path: str) -> dict:
        code = f"""
import sys, json, shutil, tempfile
import pandas as pd
import pyarrow.parquet as pq

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as t:
    tmp = t.name
shutil.copy2({repr(path)}, tmp)
df = pq.read_table(tmp, use_threads=False).to_pandas().head(200)

numeric = df.select_dtypes(include="number")
stats = {{}}
for col in numeric.columns:
    s = numeric[col].dropna()
    if len(s) > 0:
        stats[col] = {{
            "mean": round(float(s.mean()), 4),
            "std": round(float(s.std()), 4),
            "min": round(float(s.min()), 4),
            "max": round(float(s.max()), 4),
            "null_pct": round(float(numeric[col].isnull().mean()), 4),
        }}

print(json.dumps({{"ok": True, "columns": list(df.columns), "stats": stats, "rows": len(df)}}))
"""
        res = self._executor.execute_python(code, timeout=30)
        if not res["ok"]:
            return {"ok": False, "error": res["stderr"]}
        try:
            return json.loads(res["stdout"].strip())
        except Exception:
            return {"ok": False, "error": res["stdout"][:200]}

    # ── LLM feature suggestions ───────────────────────────────────────────────
    def _suggest_features_llm(self, columns: list, stats: dict) -> list:
        # Only include columns relevant to delay prediction
        relevant_stats = {
            k: v for k, v in stats.items()
            if k in {"order_value", "delay_days", "quantity", "unit_price",
                     "carrying_cost", "delay_cost", "delay_probability",
                     "confidence", "trust_score"}
        }
        user_msg = json.dumps({
            "available_columns": columns,
            "column_statistics": relevant_stats,
            "task": "supply chain delay prediction",
            "instruction": (
                "Suggest up to 5 NEW features. "
                "ONLY use columns that are in available_columns. "
                "Each pandas_expr should be: df['col1'] op df['col2'] or similar. "
                "NO function calls, NO imports, pure arithmetic/comparison."
            )
        }, indent=2)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                system=(
                    "You are a supply chain ML feature engineer. "
                    "You MUST call suggest_features. No free-text responses. "
                    "Only suggest features using columns that exist in available_columns."
                ),
                tools=[FEATURE_SUGGESTION_TOOL],
                tool_choice={"type": "tool", "name": "suggest_features"},
                messages=[{"role": "user", "content": user_msg}]
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "suggest_features":
                    return block.input.get("features", [])
        except Exception as e:
            logger.error(f"[feature_engineer] LLM call failed: {e}")
        return []

    # ── Validate a single feature ─────────────────────────────────────────────
    def _validate_feature(self, name: str, expr: str, gold_path: str) -> dict:
        # Gate 1 — syntax check via CodeExecutor
        res = self._executor.validate_feature_code(
            feature_lines=[f"df[{repr(name)}] = {expr}"],
            sample_parquet=gold_path,
            max_rows=20,
        )
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "unknown")}

        # Gate 2 — no NaN explosion (>5% null in 50 rows)
        check_code = f"""
import sys, json, shutil, tempfile
import pandas as pd
import pyarrow.parquet as pq

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as t:
    tmp = t.name
shutil.copy2({repr(gold_path)}, tmp)
df = pq.read_table(tmp, use_threads=False).to_pandas().head(50)
try:
    df[{repr(name)}] = {expr}
    null_ratio = float(df[{repr(name)}].isnull().mean())
    dtype = str(df[{repr(name)}].dtype)
    print(json.dumps({{"ok": null_ratio < {MAX_NAN_RATIO}, "null_ratio": null_ratio, "dtype": dtype}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
"""
        res2 = self._executor.execute_python(check_code, timeout=20)
        if not res2["ok"]:
            return {"ok": False, "error": res2["stderr"]}
        try:
            gate2_result = json.loads(res2["stdout"].strip())
        except Exception:
            return {"ok": False, "error": "bad gate2 output"}
        if not gate2_result.get("ok"):
            return gate2_result

        # Gate 6 — distribution sanity: no infinite or astronomically large values
        # A feature producing values > 1e10 in absolute magnitude is almost certainly
        # a computation error (division by near-zero, overflow) rather than a signal.
        gate6_code = f"""
import sys, json, shutil, tempfile
import pandas as pd
import pyarrow.parquet as pq
import numpy as np

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as t:
    tmp = t.name
shutil.copy2({repr(gold_path)}, tmp)
df = pq.read_table(tmp, use_threads=False).to_pandas().head(200)
try:
    df[{repr(name)}] = {expr}
    col = pd.to_numeric(df[{repr(name)}], errors='coerce').dropna()
    has_inf = bool(np.any(np.isinf(col)))
    max_abs = float(col.abs().max()) if len(col) > 0 else 0.0
    ok = not has_inf and max_abs < 1e10
    print(json.dumps({{"ok": ok, "has_inf": has_inf, "max_abs": max_abs}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
"""
        res6 = self._executor.execute_python(gate6_code, timeout=20)
        if not res6["ok"]:
            return {"ok": False, "error": f"gate6 executor error: {res6['stderr'][:200]}"}
        try:
            g6 = json.loads(res6["stdout"].strip())
        except Exception:
            return {"ok": False, "error": "bad gate6 output"}
        if not g6.get("ok"):
            return {"ok": False, "error": f"gate6 distribution: has_inf={g6.get('has_inf')}, max_abs={g6.get('max_abs')}"}

        # Gate 7 — non-trivial variance: feature must carry a signal (std > 0.001).
        # A constant feature (std ≈ 0) adds no predictive value and wastes model capacity.
        gate7_code = f"""
import sys, json, shutil, tempfile
import pandas as pd
import pyarrow.parquet as pq

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as t:
    tmp = t.name
shutil.copy2({repr(gold_path)}, tmp)
df = pq.read_table(tmp, use_threads=False).to_pandas().head(200)
try:
    df[{repr(name)}] = {expr}
    col = pd.to_numeric(df[{repr(name)}], errors='coerce').dropna()
    std = float(col.std()) if len(col) > 1 else 0.0
    ok = std > 0.001
    print(json.dumps({{"ok": ok, "std": std}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
"""
        res7 = self._executor.execute_python(gate7_code, timeout=20)
        if not res7["ok"]:
            return {"ok": False, "error": f"gate7 executor error: {res7['stderr'][:200]}"}
        try:
            g7 = json.loads(res7["stdout"].strip())
        except Exception:
            return {"ok": False, "error": "bad gate7 output"}
        if not g7.get("ok"):
            return {"ok": False, "error": f"gate7 variance: std={g7.get('std')} — feature is near-constant"}

        # Gate 8 — novelty: the new feature must not be a near-duplicate of an existing
        # numeric column (Pearson |r| < 0.99).  A duplicate provides no new information
        # but increases dimensionality and can destabilise training.
        gate8_code = f"""
import sys, json, shutil, tempfile
import pandas as pd
import pyarrow.parquet as pq

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as t:
    tmp = t.name
shutil.copy2({repr(gold_path)}, tmp)
df = pq.read_table(tmp, use_threads=False).to_pandas().head(200)
try:
    df[{repr(name)}] = {expr}
    new_col = pd.to_numeric(df[{repr(name)}], errors='coerce')
    numeric_existing = df.select_dtypes(include='number').drop(columns=[{repr(name)}], errors='ignore')
    max_corr = 0.0
    corr_with = ""
    for col in numeric_existing.columns:
        existing = pd.to_numeric(numeric_existing[col], errors='coerce')
        paired = pd.concat([new_col, existing], axis=1).dropna()
        if len(paired) > 5:
            r = abs(float(paired.iloc[:, 0].corr(paired.iloc[:, 1])))
            if r > max_corr:
                max_corr = r
                corr_with = col
    ok = max_corr < 0.99
    print(json.dumps({{"ok": ok, "max_corr": round(max_corr, 4), "corr_with": corr_with}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
"""
        res8 = self._executor.execute_python(gate8_code, timeout=30)
        if not res8["ok"]:
            return {"ok": False, "error": f"gate8 executor error: {res8['stderr'][:200]}"}
        try:
            g8 = json.loads(res8["stdout"].strip())
        except Exception:
            return {"ok": False, "error": "bad gate8 output"}
        if not g8.get("ok"):
            return {
                "ok": False,
                "error": (
                    f"gate8 novelty: |r|={g8.get('max_corr')} with '{g8.get('corr_with')}' "
                    "— feature is near-duplicate of existing column"
                ),
            }

        # All gates passed — return gate2 result (contains null_ratio + dtype)
        return gate2_result

    # ── Compute features and write parquet ────────────────────────────────────
    def _compute_and_write_features(self, gold_path: str, features: list) -> bool:
        os.makedirs(FEATURES_DIR, exist_ok=True)
        feat_lines = "\n    ".join([
            f"df[{repr(f['name'])}] = {f['pandas_expr']}"
            for f in features
        ])
        feat_names = [f["name"] for f in features]
        out_path = os.path.join(FEATURES_DIR, "features.parquet")
        manifest_path = os.path.join(FEATURES_DIR, "manifest.json")

        code = f"""
import sys, json, shutil, tempfile
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as t:
    tmp = t.name
shutil.copy2({repr(gold_path)}, tmp)
df = pq.read_table(tmp, use_threads=False).to_pandas()

try:
    {feat_lines}
    out_df = df[{repr(feat_names)}].copy()
    # Add order_id as join key
    if "order_id" in df.columns:
        out_df.insert(0, "order_id", df["order_id"])
    out_df.to_parquet({repr(out_path)}, index=False)
    print(json.dumps({{"ok": True, "rows": len(out_df), "cols": list(out_df.columns)}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
"""
        res = self._executor.execute_python(code, timeout=60)
        if not res["ok"]:
            logger.error(f"[feature_engineer] Feature write failed: {res['stderr']}")
            return False
        try:
            result = json.loads(res["stdout"].strip())
            if result.get("ok"):
                # Write manifest
                manifest = {
                    "features": features,
                    "generated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    "gold_source": gold_path,
                    "rows": result.get("rows", 0),
                }
                Path(manifest_path).write_text(json.dumps(manifest, indent=2))
                logger.info(f"[feature_engineer] Written {result.get('rows')} rows → {out_path}")
                return True
        except Exception as e:
            logger.error(f"[feature_engineer] Manifest write error: {e}")
        return False

    # ── Trigger incremental pipeline ──────────────────────────────────────────
    def _trigger_incremental(self):
        try:
            resp = requests.post(
                f"{DAGSTER_URL}/graphql",
                json={"query": """
                    mutation {
                        launchRun(executionParams: {
                            selector: {
                                jobName: "medallion_incremental",
                                repositoryLocationName: "pipeline.definitions:defs",
                                repositoryName: "__repository__"
                            },
                            runConfigData: {}
                        }) {
                            ... on LaunchRunSuccess { run { runId } }
                            ... on PythonError { message }
                        }
                    }
                """},
                timeout=15
            )
            run_id = (resp.json().get("data", {})
                      .get("launchRun", {}).get("run", {}).get("runId"))
            if run_id:
                logger.info(f"[feature_engineer] Triggered incremental: {run_id}")
        except Exception as e:
            logger.warning(f"[feature_engineer] Trigger failed: {e}")

    def apply_correction(self, correction: str):
        """Act on orchestrator corrections."""
        # Bug 18: use .lower() for case-insensitive matching so "FORCE_REGENERATE" etc. work
        c = correction.lower()
        if "regenerate" in c or "rerun" in c or "re-run" in c or "force" in c:
            logger.info("[feature_engineer] Orchestrator correction → forcing feature regeneration")
            self._last_gold_mtime = 0.0  # reset cache so next cycle re-generates
        elif "trigger" in c and ("pipeline" in c or "incremental" in c):
            logger.info("[feature_engineer] Orchestrator correction → triggering incremental pipeline")
            self._trigger_incremental()
        else:
            logger.info(f"[feature_engineer] Orchestrator correction (no action matched): {correction}")

    def heal(self, error: Exception) -> bool:
        err_str = str(error)
        if "parquet" in err_str.lower() or "no such file" in err_str.lower():
            logger.warning(f"[feature_engineer] File error — resetting gold mtime cache")
            self._last_gold_mtime = 0.0
            time.sleep(10)
            return True
        logger.warning(f"[feature_engineer] Healing: {error}")
        time.sleep(15)
        return True
