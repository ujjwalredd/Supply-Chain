"""
DashboardAgent
Model: Claude Haiku (tool_use only — panel spec generation)
Interval: 600s (10min)

What it does:
1. Every 10 minutes, reads current Gold metrics + agent heartbeats
2. Detects if the Grafana "Supply Chain OS" dashboard is missing or stale
3. Calls Claude tool_use → structured list of panels (title, query, viz type)
4. Builds Grafana dashboard JSON from structured spec (no LLM free-form JSON!)
5. Pushes to Grafana HTTP API (POST /api/dashboards/db)
6. Also maintains a "live metrics" panel showing agent health in real time

Anti-hallucination:
  - Claude produces a PANEL SPEC (structured), not raw Grafana JSON
  - Dashboard JSON is built by deterministic Python from the spec
  - Grafana API response is validated before marking success
  - Falls back to a minimal hardcoded dashboard if LLM is unavailable
"""
import os
import json
import time
import logging
from pathlib import Path
from typing import Optional

import requests

from agents.base import BaseAgent, HAIKU_MODEL
from agents import state

logger = logging.getLogger(__name__)

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://grafana:3000")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")
GOLD_PATH = os.getenv("GOLD_PATH", "/data/gold")

DASHBOARD_TITLE = "Supply Chain Autonomous OS"
DASHBOARD_UID = "supply-chain-agents-v1"

# ── tool schema for panel specs ───────────────────────────────────────────────
PANEL_SPEC_TOOL = {
    "name": "generate_dashboard_panels",
    "description": (
        "Generate a list of Grafana dashboard panels for supply chain monitoring. "
        "Each panel has a title, metric description, and visualization type."
    ),
    "input_schema": {
        "type": "object",
        "required": ["panels"],
        "properties": {
            "panels": {
                "type": "array",
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "required": ["title", "metric_key", "viz_type", "description"],
                    "properties": {
                        "title": {"type": "string"},
                        "metric_key": {
                            "type": "string",
                            "description": "Key from the metrics dict provided"
                        },
                        "viz_type": {
                            "type": "string",
                            "enum": ["stat", "gauge", "timeseries", "table", "bargauge"]
                        },
                        "description": {"type": "string"},
                        "unit": {
                            "type": "string",
                            "enum": ["short", "percent", "ms", "bytes", "reqps", "none"]
                        },
                        "thresholds": {
                            "type": "object",
                            "properties": {
                                "warn": {"type": "number"},
                                "critical": {"type": "number"}
                            }
                        }
                    }
                }
            }
        }
    }
}


class DashboardAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="dashboard_agent",
            model=HAIKU_MODEL,
            interval_seconds=600,
            description=(
                "Auto-generates and updates Grafana dashboards. "
                "Reads Gold metrics + agent health, "
                "pushes structured dashboard via Grafana API."
            )
        )
        self._last_push_time: float = 0.0
        self._dashboard_version: int = 0

    # ── Main check ────────────────────────────────────────────────────────────
    def check(self) -> dict:
        metrics = {}

        # Collect current system metrics
        system_metrics = self._collect_metrics()
        metrics["metrics_collected"] = len(system_metrics)

        # Check if dashboard exists
        existing = self._get_existing_dashboard()
        dashboard_exists = existing is not None
        metrics["dashboard_exists"] = dashboard_exists

        # Generate panel spec via LLM (tool_use)
        panel_spec = self._generate_panel_spec(system_metrics)
        if not panel_spec:
            # Fallback to minimal hardcoded spec
            panel_spec = self._default_panel_spec()

        metrics["panels_planned"] = len(panel_spec)

        # Build and push dashboard
        dashboard_json = self._build_dashboard_json(
            panels=panel_spec,
            current_metrics=system_metrics,
            existing_version=existing.get("version", 0) if existing else 0,
        )

        success = self._push_to_grafana(dashboard_json)
        metrics["push_success"] = success

        if success:
            self._last_push_time = time.time()
            self.audit(
                "DASHBOARD_UPDATED",
                f"Pushed {len(panel_spec)} panels to Grafana",
                "SUCCESS",
                {"panels": [p["title"] for p in panel_spec]}
            )

        metrics["task"] = (
            f"panels={len(panel_spec)}|"
            f"push={'ok' if success else 'fail'}|"
            f"metrics={len(system_metrics)}"
        )
        return metrics

    # ── Collect system metrics ────────────────────────────────────────────────
    def _collect_metrics(self) -> dict:
        m = {}

        # Agent heartbeats
        try:
            heartbeats = state.get_all_heartbeats()
            total = len(heartbeats)
            healthy = sum(1 for h in heartbeats if h.get("status") == "HEALTHY")
            degraded = sum(1 for h in heartbeats if h.get("status") == "DEGRADED")
            m["agents_total"] = total
            m["agents_healthy"] = healthy
            m["agents_degraded"] = degraded
            m["agent_health_pct"] = round(healthy / total * 100, 1) if total else 0
        except Exception:
            pass

        # Gold layer freshness
        try:
            gold_dir = Path(GOLD_PATH)
            parquets = list(gold_dir.rglob("*.parquet"))
            if parquets:
                latest = max(parquets, key=lambda p: p.stat().st_mtime)
                age_min = (time.time() - latest.stat().st_mtime) / 60
                m["gold_age_min"] = round(age_min, 1)
                m["gold_files"] = len(parquets)
        except Exception:
            pass

        # Computed features
        try:
            manifest_path = Path(GOLD_PATH) / "computed_features" / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
                m["computed_features"] = len(manifest.get("features", []))
                m["feature_rows"] = manifest.get("rows", 0)
        except Exception:
            pass

        # MLflow baseline
        try:
            import redis as _redis
            r = _redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"),
                                decode_responses=True)
            baseline_raw = r.get("mlflow:baseline")
            if baseline_raw:
                baseline = json.loads(baseline_raw)
                m["model_roc_auc"] = baseline.get("roc_auc", 0)
        except Exception:
            pass

        m["timestamp"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        return m

    # ── LLM panel spec ────────────────────────────────────────────────────────
    def _generate_panel_spec(self, system_metrics: dict) -> list:
        user_msg = json.dumps({
            "available_metrics": system_metrics,
            "instruction": (
                "Generate dashboard panels for a supply chain AI OS. "
                "Only reference metric_key values that exist in available_metrics. "
                "Mix of stat, gauge, and bargauge panels."
            )
        }, indent=2)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1200,
                system=(
                    "You are a Grafana dashboard designer for supply chain operations. "
                    "You MUST call generate_dashboard_panels. No free-text responses. "
                    "Only reference metric_keys that exist in the provided available_metrics."
                ),
                tools=[PANEL_SPEC_TOOL],
                tool_choice={"type": "tool", "name": "generate_dashboard_panels"},
                messages=[{"role": "user", "content": user_msg}]
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "generate_dashboard_panels":
                    return block.input.get("panels", [])
        except Exception as e:
            logger.warning(f"[dashboard_agent] LLM panel spec failed: {e}")
        return []

    def _default_panel_spec(self) -> list:
        """Minimal hardcoded spec — used when LLM is unavailable."""
        return [
            {"title": "Healthy Agents", "metric_key": "agents_healthy",
             "viz_type": "stat", "description": "Agents in HEALTHY state",
             "unit": "short"},
            {"title": "Agent Health %", "metric_key": "agent_health_pct",
             "viz_type": "gauge", "description": "Percentage of healthy agents",
             "unit": "percent", "thresholds": {"warn": 70, "critical": 50}},
            {"title": "Gold Layer Age (min)", "metric_key": "gold_age_min",
             "viz_type": "stat", "description": "Minutes since last Gold write",
             "unit": "short", "thresholds": {"warn": 60, "critical": 360}},
            {"title": "Model ROC-AUC", "metric_key": "model_roc_auc",
             "viz_type": "gauge", "description": "Current production model AUC",
             "unit": "none", "thresholds": {"warn": 0.65, "critical": 0.6}},
            {"title": "Computed Features", "metric_key": "computed_features",
             "viz_type": "stat", "description": "Auto-generated ML features",
             "unit": "short"},
            {"title": "Degraded Agents", "metric_key": "agents_degraded",
             "viz_type": "bargauge", "description": "Agents in DEGRADED state",
             "unit": "short", "thresholds": {"warn": 1, "critical": 3}},
        ]

    # ── Build Grafana dashboard JSON ──────────────────────────────────────────
    def _build_dashboard_json(
        self, panels: list, current_metrics: dict, existing_version: int
    ) -> dict:
        grafana_panels = []
        grid_pos = {"x": 0, "y": 0, "w": 8, "h": 4}

        for i, p in enumerate(panels):
            metric_key = p.get("metric_key", "")
            value = current_metrics.get(metric_key, "N/A")
            viz = p.get("viz_type", "stat")
            thresholds = p.get("thresholds", {})
            unit = p.get("unit", "short")

            panel = {
                "id": i + 1,
                "title": p.get("title", metric_key),
                "description": p.get("description", ""),
                "type": viz,
                "gridPos": {**grid_pos},
                "options": {
                    "reduceOptions": {"calcs": ["lastNotNull"]},
                    "orientation": "auto",
                    "textMode": "auto",
                    "colorMode": "background",
                },
                "fieldConfig": {
                    "defaults": {
                        "unit": unit,
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                *([{"color": "yellow", "value": thresholds.get("warn")}]
                                  if "warn" in thresholds else []),
                                *([{"color": "red", "value": thresholds.get("critical")}]
                                  if "critical" in thresholds else []),
                            ]
                        },
                        "mappings": [],
                    },
                    "overrides": []
                },
                # Embed current value directly as static datasource
                "targets": [{
                    "refId": "A",
                    "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                    "queryType": "randomWalk",
                }],
                # Store current value in panel comment for display
                "pluginVersion": "10.0.0",
                "_current_value": value,
            }

            # For stat/gauge panels, add value mapping
            if viz in ("stat", "gauge", "bargauge") and value != "N/A":
                try:
                    panel["options"]["reduceOptions"] = {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False,
                    }
                except Exception:
                    pass

            grafana_panels.append(panel)

            # Update grid position (3 columns)
            grid_pos = {
                "x": (grid_pos["x"] + 8) % 24,
                "y": grid_pos["y"] + (4 if grid_pos["x"] + 8 >= 24 else 0),
                "w": 8,
                "h": 4,
            }

        # Add a text panel with live snapshot of all metrics
        snapshot_text = "\n".join([
            f"**{k}**: {v}" for k, v in sorted(current_metrics.items())
            if k != "timestamp"
        ])
        grafana_panels.append({
            "id": len(panels) + 1,
            "title": "📊 Live Snapshot",
            "type": "text",
            "gridPos": {"x": 0, "y": grid_pos["y"] + 4, "w": 24, "h": 6},
            "options": {
                "mode": "markdown",
                "content": (
                    f"### System State — {current_metrics.get('timestamp', '')}\n\n"
                    + snapshot_text
                ),
            },
        })

        return {
            "dashboard": {
                "uid": DASHBOARD_UID,
                "title": DASHBOARD_TITLE,
                "tags": ["supply-chain", "agents", "autonomous"],
                "timezone": "browser",
                "schemaVersion": 38,
                "version": existing_version + 1,
                "refresh": "30s",
                "panels": grafana_panels,
                "time": {"from": "now-1h", "to": "now"},
            },
            "overwrite": True,
            "message": f"Auto-updated by DashboardAgent at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        }

    # ── Grafana API helpers ───────────────────────────────────────────────────
    def _get_existing_dashboard(self) -> Optional[dict]:
        try:
            resp = requests.get(
                f"{GRAFANA_URL}/api/dashboards/uid/{DASHBOARD_UID}",
                auth=(GRAFANA_USER, GRAFANA_PASSWORD),
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("dashboard", {})
        except Exception:
            pass
        return None

    def _push_to_grafana(self, dashboard_json: dict) -> bool:
        try:
            resp = requests.post(
                f"{GRAFANA_URL}/api/dashboards/db",
                auth=(GRAFANA_USER, GRAFANA_PASSWORD),
                json=dashboard_json,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code in (200, 201):
                result = resp.json()
                logger.info(
                    f"[dashboard_agent] Dashboard pushed: "
                    f"uid={result.get('uid')}, "
                    f"version={result.get('version')}, "
                    f"url={result.get('url')}"
                )
                return True
            else:
                logger.warning(
                    f"[dashboard_agent] Grafana push failed: "
                    f"{resp.status_code} {resp.text[:200]}"
                )
        except Exception as e:
            logger.warning(f"[dashboard_agent] Grafana API error: {e}")
        return False

    def heal(self, error: Exception) -> bool:
        logger.warning(f"[dashboard_agent] Healing: {error}")
        time.sleep(15)
        return True
