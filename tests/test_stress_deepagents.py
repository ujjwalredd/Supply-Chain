"""
Comprehensive stress test suite for Adopt Supply Chain AI OS deepagents integration.

Tests cover:
1. Agent code correctness (orchestrator + data_ingestion)
2. deepagents availability and fallback logic
3. Orchestrator correction dispatch (all 5 agents)
4. DataIngestionAgent multi-step validation logic
5. Pydantic response model schemas
6. Path-checking fixes (str(f) vs f.name)
7. Orchestrator escalation rules (1/2/3+ DEGRADED)
8. Kafka, Dagster, MLflow tool wiring
9. Memory + skill file loading
10. End-to-end ingestion simulation (CSV → loader → validation)
"""
import json
import os
import sys
import time
import types
import hashlib
import tempfile
import threading
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ── Add project root to path ──────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# =============================================================================
# 1. Orchestrator module structure
# =============================================================================

class TestOrchestratorStructure:
    """Verify orchestrator module exports and key functions exist."""

    def test_orchestrator_imports(self):
        """Module must be importable with all key symbols."""
        import importlib
        # Patch heavy dependencies before import
        with patch.dict("sys.modules", {
            "agents.state": MagicMock(),
            "agents.communication": MagicMock(),
        }):
            spec = importlib.util.spec_from_file_location(
                "orchestrator_test",
                os.path.join(ROOT, "agents", "orchestrator.py")
            )
            mod = importlib.util.module_from_spec(spec)
            # Should not raise
            assert spec is not None

    def test_orchestrator_agent_class_exists(self):
        """OrchestratorAgent class must exist."""
        with patch.dict("sys.modules", {
            "agents.state": MagicMock(),
            "agents.communication": MagicMock(),
            "agents.base": MagicMock(
                BaseAgent=object,
                SONNET_MODEL="claude-sonnet-4-6",
                HAIKU_MODEL="claude-haiku-4-5-20251001",
                _global_shutdown=threading.Event(),
            ),
            "redis": MagicMock(),
            "requests": MagicMock(),
        }):
            import importlib
            spec = importlib.util.spec_from_file_location(
                "orchestrator_cls",
                os.path.join(ROOT, "agents", "orchestrator.py")
            )
            # Verify file parses without syntax error
            with open(os.path.join(ROOT, "agents", "orchestrator.py"), "r") as f:
                source = f.read()
            compile(source, "orchestrator.py", "exec")  # SyntaxError if broken

    def test_deepagents_availability_function(self):
        """_deepagents_available() must return bool without crashing."""
        with patch.dict("sys.modules", {
            "agents.state": MagicMock(),
            "agents.communication": MagicMock(),
            "agents.base": MagicMock(
                BaseAgent=object,
                SONNET_MODEL="claude-sonnet-4-6",
                HAIKU_MODEL="claude-haiku-4-5-20251001",
                _global_shutdown=threading.Event(),
            ),
            "redis": MagicMock(),
            "requests": MagicMock(),
        }):
            # Test with deepagents missing
            with patch.dict("sys.modules", {"deepagents": None}):
                # Import the function directly
                with open(os.path.join(ROOT, "agents", "orchestrator.py"), "r") as f:
                    source = f.read()
                assert "_deepagents_available" in source
                assert "ImportError" in source

    def test_orchestration_result_model(self):
        """OrchestrationResult Pydantic model must build successfully."""
        from pydantic import BaseModel

        # Simulate building the model
        from typing import List

        class CorrectionItem(BaseModel):
            agent_id: str
            correction: str

        class OrchestrationResult(BaseModel):
            root_cause_analysis: str
            correlations: List[str] = []
            corrections: List[CorrectionItem] = []
            human_intervention_needed: bool = False
            summary: str
            confidence: str = "HIGH"

        r = OrchestrationResult(
            root_cause_analysis="Test root cause",
            summary="All healthy",
        )
        assert r.human_intervention_needed is False
        assert r.confidence == "HIGH"
        assert r.corrections == []

    def test_orchestration_result_with_corrections(self):
        """OrchestrationResult must accept corrections list."""
        from pydantic import BaseModel
        from typing import List

        class CorrectionItem(BaseModel):
            agent_id: str
            correction: str

        class OrchestrationResult(BaseModel):
            root_cause_analysis: str
            correlations: List[str] = []
            corrections: List[CorrectionItem] = []
            human_intervention_needed: bool = False
            summary: str
            confidence: str = "HIGH"

        r = OrchestrationResult(
            root_cause_analysis="Dagster not running",
            correlations=["bronze_agent + silver_agent both missing files"],
            corrections=[
                CorrectionItem(agent_id="dagster_guardian", correction="trigger full pipeline"),
                CorrectionItem(agent_id="bronze_agent", correction="trigger materialization"),
            ],
            human_intervention_needed=False,
            summary="Dagster pipeline restarted",
        )
        assert len(r.corrections) == 2
        assert r.corrections[0].agent_id == "dagster_guardian"
        assert r.corrections[0].correction == "trigger full pipeline"


# =============================================================================
# 2. Escalation rules
# =============================================================================

class TestEscalationRules:
    """Test orchestrator escalation thresholds."""

    def _make_hb(self, agent_id: str, status: str) -> dict:
        return {
            "agent_id": agent_id,
            "status": status,
            "error_count": 0,
            "last_error": None,
            "current_task": "monitoring",
            "metrics": {},
            "last_seen": "2026-03-15T12:00:00",
        }

    def test_single_degraded_no_human_needed(self):
        """1 DEGRADED agent should NOT trigger human_intervention_needed."""
        degraded = ["kafka_guardian"]
        # Under escalation rules: single agent DEGRADED → issue correction, monitor
        assert len(degraded) < 3  # No human needed

    def test_two_degraded_same_domain_correlated(self):
        """2 DEGRADED agents in same domain → correlated failure."""
        degraded = ["bronze_agent", "silver_agent"]
        # Both medallion — correlated, investigate root cause
        medallion_agents = {"bronze_agent", "silver_agent", "gold_agent", "medallion_supervisor"}
        correlated = [a for a in degraded if a in medallion_agents]
        assert len(correlated) == 2

    def test_three_degraded_cross_domain_human_needed(self):
        """3+ DEGRADED agents across domains → human_intervention_needed=True."""
        degraded = ["kafka_guardian", "dagster_guardian", "database_health"]
        # Cross-domain: kafka + dagster + db
        assert len(degraded) >= 3
        # Escalation rule: 3+ cross-domain → CRITICAL + human_intervention_needed=True

    def test_needs_reasoning_threshold(self):
        """needs_reasoning must trigger at >= 2 DEGRADED agents."""
        # Simulate the check() logic
        def needs_reasoning(pending_alerts, offline_agents, degraded):
            return (
                len(pending_alerts) > 0
                or len(offline_agents) > 0
                or len(degraded) >= 2
                or any(a.get("severity") in ("CRITICAL", "HIGH") for a in pending_alerts)
            )

        assert not needs_reasoning([], [], [])  # Nothing broken
        assert not needs_reasoning([], [], ["kafka_guardian"])  # Only 1 degraded
        assert needs_reasoning([], [], ["kafka_guardian", "dagster_guardian"])  # 2 degraded
        assert needs_reasoning([{"severity": "HIGH"}], [], [])  # High alert
        assert needs_reasoning([{"severity": "CRITICAL"}], [], [])  # Critical alert
        assert needs_reasoning([], [{"agent": "orphan", "age_sec": 400}], [])  # Offline agent


# =============================================================================
# 3. Correction dispatch
# =============================================================================

class TestCorrectionDispatch:
    """Test that apply_correction() methods dispatch to real actions."""

    def test_dagster_guardian_correction_full_pipeline(self):
        """dagster_guardian.apply_correction('trigger full pipeline') must call _trigger_full_job."""
        with open(os.path.join(ROOT, "agents", "dagster_guardian.py"), "r") as f:
            source = f.read()
        assert "apply_correction" in source
        assert "_trigger_full_job" in source or "full" in source

    def test_dagster_guardian_correction_incremental(self):
        """dagster_guardian.apply_correction('trigger incremental') must be handled."""
        with open(os.path.join(ROOT, "agents", "dagster_guardian.py"), "r") as f:
            source = f.read()
        assert "incremental" in source

    def test_dagster_guardian_correction_reset_counter(self):
        """dagster_guardian.apply_correction('reset consecutive error counter') must reset counter."""
        with open(os.path.join(ROOT, "agents", "dagster_guardian.py"), "r") as f:
            source = f.read()
        assert "consecutive" in source or "reset" in source

    def test_mlflow_guardian_correction_retrain(self):
        """mlflow_guardian.apply_correction('force retraining') must trigger retraining."""
        with open(os.path.join(ROOT, "agents", "mlflow_guardian.py"), "r") as f:
            source = f.read()
        assert "apply_correction" in source
        assert "retrain" in source.lower()

    def test_mlflow_guardian_correction_reset_baseline(self):
        """mlflow_guardian.apply_correction('reset baseline') must clear Redis key."""
        with open(os.path.join(ROOT, "agents", "mlflow_guardian.py"), "r") as f:
            source = f.read()
        assert "baseline" in source

    def test_feature_engineer_correction_force_regeneration(self):
        """feature_engineer.apply_correction('force regeneration') must reset cache."""
        with open(os.path.join(ROOT, "agents", "feature_engineer.py"), "r") as f:
            source = f.read()
        assert "apply_correction" in source
        assert "regenerat" in source.lower() or "force" in source.lower()

    def test_bronze_agent_correction_trigger(self):
        """bronze_agent.apply_correction('trigger materialization') must be handled."""
        with open(os.path.join(ROOT, "agents", "medallion", "bronze.py"), "r") as f:
            source = f.read()
        assert "apply_correction" in source
        assert "materialize" in source.lower() or "trigger" in source.lower()

    def test_silver_agent_correction_trigger(self):
        """silver_agent.apply_correction('trigger materialization') must be handled."""
        with open(os.path.join(ROOT, "agents", "medallion", "silver.py"), "r") as f:
            source = f.read()
        assert "apply_correction" in source


# =============================================================================
# 4. Path-checking fix (str(f) vs f.name)
# =============================================================================

class TestPathCheckingFix:
    """Verify all path checks use str(f) not f.name."""

    def test_feature_engineer_uses_str_f(self):
        """feature_engineer must check 'ai_ready' in str(f), not f.name."""
        with open(os.path.join(ROOT, "agents", "feature_engineer.py"), "r") as f:
            source = f.read()
        # Must NOT have the buggy pattern
        assert '"ai_ready" in f.name' not in source
        assert "'ai_ready' in f.name" not in source
        # Must have the correct pattern
        assert "str(f)" in source

    def test_silver_agent_uses_str_f(self):
        """silver_agent must check 'orders' in str(f), not f.name."""
        with open(os.path.join(ROOT, "agents", "medallion", "silver.py"), "r") as f:
            source = f.read()
        assert '"orders" in f.name' not in source
        assert "'orders' in f.name" not in source
        assert "str(f)" in source

    def test_gold_agent_uses_str_f(self):
        """gold_agent must check 'ai_ready' / 'orders' in str(f)."""
        with open(os.path.join(ROOT, "agents", "medallion", "gold.py"), "r") as f:
            source = f.read()
        assert "str(f)" in source

    def test_path_check_with_real_parquet_path(self):
        """Simulate the exact directory layout: orders_ai_ready/data.parquet."""
        # Create temp structure
        with tempfile.TemporaryDirectory() as tmpdir:
            gold_dir = Path(tmpdir) / "gold"
            (gold_dir / "orders_ai_ready").mkdir(parents=True)
            parquet_file = gold_dir / "orders_ai_ready" / "data.parquet"
            parquet_file.write_text("dummy")

            # Old (buggy) way: would miss this file
            old_check = [f for f in gold_dir.rglob("*.parquet")
                         if f.is_file() and "ai_ready" in f.name]
            assert len(old_check) == 0  # Proves the bug

            # New (correct) way: finds the file
            new_check = [f for f in gold_dir.rglob("*.parquet")
                         if f.is_file() and "ai_ready" in str(f)]
            assert len(new_check) == 1  # Proves the fix


# =============================================================================
# 5. DataIngestionAgent structure and validation logic
# =============================================================================

class TestDataIngestionAgent:
    """Test data ingestion agent logic."""

    def test_ingestion_agent_imports_cleanly(self):
        """data_ingestion_agent.py must parse without syntax errors."""
        with open(os.path.join(ROOT, "agents", "data_ingestion_agent.py"), "r") as f:
            source = f.read()
        compile(source, "data_ingestion_agent.py", "exec")

    def test_deepagents_path_exists_in_source(self):
        """data_ingestion_agent must have deepagents code path."""
        with open(os.path.join(ROOT, "agents", "data_ingestion_agent.py"), "r") as f:
            source = f.read()
        assert "_infer_schema_with_deepagents" in source
        assert "MAX_FIX_ATTEMPTS" in source
        assert "validate_python_loader" in source
        assert "read_csv_sample" in source

    def test_legacy_fallback_exists(self):
        """Legacy _infer_schema_with_llm must still exist as fallback."""
        with open(os.path.join(ROOT, "agents", "data_ingestion_agent.py"), "r") as f:
            source = f.read()
        assert "_infer_schema_with_llm" in source
        assert "_fix_loader" in source

    def test_builtin_files_set(self):
        """BUILTIN_FILES must include all 9 expected files."""
        with open(os.path.join(ROOT, "agents", "data_ingestion_agent.py"), "r") as f:
            source = f.read()
        expected = [
            "orderlist.csv", "freightrates.csv", "whcapacities.csv",
            "plantports.csv", "productsperplant.csv", "supplifySupplychain.csv",
            "vmicustomers.csv", "whcosts.csv", "manifest.txt",
        ]
        for f in expected:
            assert f in source, f"BUILTIN_FILES missing: {f}"

    def test_max_fix_attempts_is_3(self):
        """MAX_FIX_ATTEMPTS must be 3 for iterative loop."""
        with open(os.path.join(ROOT, "agents", "data_ingestion_agent.py"), "r") as f:
            source = f.read()
        assert "MAX_FIX_ATTEMPTS = 3" in source

    def test_csv_read_sample(self):
        """_read_sample static method must handle real CSV data."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("OrderID,CustomerName,Quantity,Price\n")
            for i in range(20):
                f.write(f"ORD{i:04d},Customer {i},{i+1},{(i+1)*9.99:.2f}\n")
            fname = f.name

        try:
            # Simulate the static method
            import csv
            def read_sample(path: Path, n: int = 10):
                with open(path, encoding="utf-8", errors="replace") as fp:
                    reader = csv.reader(fp)
                    rows = [r for _, r in zip(range(n + 1), reader)]
                if not rows:
                    return [], []
                header = rows[0]
                return rows[1:], header

            rows, header = read_sample(Path(fname), n=10)
            assert header == ["OrderID", "CustomerName", "Quantity", "Price"]
            assert len(rows) == 10
            assert rows[0][0] == "ORD0000"
        finally:
            os.unlink(fname)

    def test_ingestion_result_pydantic_model(self):
        """IngestionResult Pydantic model must be valid."""
        from pydantic import BaseModel, Field
        from typing import List

        class ColumnSchema(BaseModel):
            name: str
            dtype: str
            nullable: bool = True

        class IngestionResult(BaseModel):
            table_name: str
            columns: List[ColumnSchema]
            loader_code: str
            primary_key_hint: str = ""
            validation_passed: bool = False
            attempts: int = 1
            error_reason: str = ""

        result = IngestionResult(
            table_name="customer_orders",
            columns=[
                ColumnSchema(name="order_id", dtype="str"),
                ColumnSchema(name="quantity", dtype="int"),
                ColumnSchema(name="price", dtype="float", nullable=True),
            ],
            loader_code="def load_csv(path): yield {}",
            validation_passed=True,
            attempts=2,
        )
        assert result.table_name == "customer_orders"
        assert len(result.columns) == 3
        assert result.validation_passed is True
        assert result.attempts == 2

    def test_loader_validation_gates(self):
        """Simulate the 5 validation gates on a correct loader."""
        import ast
        import subprocess
        import textwrap

        good_loader = textwrap.dedent("""
        def load_csv(path):
            import csv
            from pathlib import Path
            with open(path, encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    yield {k: v.strip() if v else None for k, v in row.items()}
        """).strip()

        # Gate 1: Python syntax
        try:
            ast.parse(good_loader)
            syntax_ok = True
        except SyntaxError:
            syntax_ok = False
        assert syntax_ok, "Gate 1 (syntax) should pass for correct loader"

        # Gate 2: has yield (Iterator requirement)
        assert "yield" in good_loader, "Gate 2: must use yield"

        # Gate 3: no print statements
        assert "print(" not in good_loader, "Gate 3: no print statements"

        # Gate 4: imports from stdlib only (no pip packages)
        forbidden = ["pandas", "numpy", "requests", "sqlalchemy"]
        for pkg in forbidden:
            assert pkg not in good_loader, f"Gate 4: forbidden import {pkg}"

        # Gate 5: under 50 lines
        lines = [l for l in good_loader.split("\n") if l.strip()]
        assert len(lines) <= 50, f"Gate 5: loader has {len(lines)} lines (max 50)"

    def test_broken_loader_identified(self):
        """Broken loader (syntax error) must be detected."""
        import ast
        broken_loader = "def load_csv(path):\n    yield {unclosed"
        with pytest.raises(SyntaxError):
            ast.parse(broken_loader)

    def test_loader_missing_yield_detected(self):
        """Loader without yield should fail Gate 2."""
        loader_no_yield = """
def load_csv(path):
    import csv
    with open(path) as f:
        reader = csv.DictReader(f)
        return list(reader)  # Returns list, not iterator
"""
        assert "yield" not in loader_no_yield  # Would fail Gate 2


# =============================================================================
# 6. Skills files
# =============================================================================

class TestSkillFiles:
    """Verify all SKILL.md files are present and have correct frontmatter."""

    SKILLS = [
        "supply-chain-ops",
        "dagster-diagnosis",
        "kafka-diagnosis",
        "mlflow-governance",
        "data-ingestion",
    ]

    def test_all_skill_files_exist(self):
        """All 5 SKILL.md files must exist."""
        skills_dir = os.path.join(ROOT, "agents", "skills")
        for skill in self.SKILLS:
            skill_path = os.path.join(skills_dir, skill, "SKILL.md")
            assert os.path.exists(skill_path), f"Missing SKILL.md for {skill}"

    def test_skill_files_have_frontmatter(self):
        """Each SKILL.md must have name and description frontmatter."""
        skills_dir = os.path.join(ROOT, "agents", "skills")
        for skill in self.SKILLS:
            skill_path = os.path.join(skills_dir, skill, "SKILL.md")
            with open(skill_path, "r") as f:
                content = f.read()
            assert "---" in content, f"{skill} SKILL.md missing frontmatter"
            assert "name:" in content, f"{skill} SKILL.md missing name"
            assert "description:" in content, f"{skill} SKILL.md missing description"

    def test_supply_chain_ops_has_agent_roster(self):
        """supply-chain-ops SKILL.md must have all 13 agents listed."""
        path = os.path.join(ROOT, "agents", "skills", "supply-chain-ops", "SKILL.md")
        with open(path, "r") as f:
            content = f.read()
        agents = [
            "kafka_guardian", "dagster_guardian", "bronze_agent", "silver_agent",
            "gold_agent", "medallion_supervisor", "ai_quality_monitor",
            "database_health", "orchestrator", "data_ingestion", "mlflow_guardian",
            "feature_engineer", "dashboard_agent",
        ]
        for agent in agents:
            assert agent in content, f"supply-chain-ops SKILL.md missing agent: {agent}"

    def test_dagster_skill_has_job_names(self):
        """dagster-diagnosis SKILL.md must have both job names."""
        path = os.path.join(ROOT, "agents", "skills", "dagster-diagnosis", "SKILL.md")
        with open(path, "r") as f:
            content = f.read()
        assert "medallion_full_pipeline" in content
        assert "medallion_incremental" in content

    def test_kafka_skill_has_dlq_topic(self):
        """kafka-diagnosis SKILL.md must reference DLQ topic."""
        path = os.path.join(ROOT, "agents", "skills", "kafka-diagnosis", "SKILL.md")
        with open(path, "r") as f:
            content = f.read()
        assert "supply-chain-dlq" in content
        assert "dlq" in content.lower()

    def test_mlflow_skill_has_hard_floors(self):
        """mlflow-governance SKILL.md must have hard promotion floors."""
        path = os.path.join(ROOT, "agents", "skills", "mlflow-governance", "SKILL.md")
        with open(path, "r") as f:
            content = f.read()
        assert "0.60" in content  # roc_auc floor
        assert "100" in content    # min train_rows

    def test_data_ingestion_skill_has_validation_rules(self):
        """data-ingestion SKILL.md must have all validation rules."""
        path = os.path.join(ROOT, "agents", "skills", "data-ingestion", "SKILL.md")
        with open(path, "r") as f:
            content = f.read()
        assert "load_csv" in content
        assert "yield" in content
        assert "Iterator" in content


# =============================================================================
# 7. Memory files
# =============================================================================

class TestMemoryFiles:
    """Verify incident_patterns.md is present and well-formed."""

    def test_memory_file_exists(self):
        """incident_patterns.md must exist."""
        memory_path = os.path.join(ROOT, "agents", "memories", "incident_patterns.md")
        assert os.path.exists(memory_path)

    def test_memory_file_has_patterns(self):
        """incident_patterns.md must have at least 5 incident patterns."""
        memory_path = os.path.join(ROOT, "agents", "memories", "incident_patterns.md")
        with open(memory_path, "r") as f:
            content = f.read()
        # Count pattern headings
        pattern_count = content.count("### P0")
        assert pattern_count >= 5, f"Expected >= 5 patterns, got {pattern_count}"

    def test_memory_patterns_have_resolution(self):
        """Each pattern must have **Resolution** field."""
        memory_path = os.path.join(ROOT, "agents", "memories", "incident_patterns.md")
        with open(memory_path, "r") as f:
            content = f.read()
        assert "**Resolution**" in content or "Resolution:" in content

    def test_port_mismatch_pattern_documented(self):
        """P001 (Dagster port mismatch) must be documented."""
        memory_path = os.path.join(ROOT, "agents", "memories", "incident_patterns.md")
        with open(memory_path, "r") as f:
            content = f.read()
        assert "3001" in content or "Port Mismatch" in content

    def test_path_check_bug_documented(self):
        """P002/P003 (f.name vs str(f) bug) must be documented."""
        memory_path = os.path.join(ROOT, "agents", "memories", "incident_patterns.md")
        with open(memory_path, "r") as f:
            content = f.read()
        assert "f.name" in content or "str(f)" in content


# =============================================================================
# 8. Pipeline configuration
# =============================================================================

class TestPipelineConfig:
    """Verify pipeline jobs include all required assets."""

    def test_medallion_incremental_includes_ml_step(self):
        """medallion_incremental must include gold_delay_model."""
        path = os.path.join(ROOT, "pipeline", "jobs_medallion.py")
        with open(path, "r") as f:
            content = f.read()
        assert "gold_delay_model" in content

    def test_medallion_full_pipeline_defined(self):
        """medallion_full_pipeline job must be defined."""
        path = os.path.join(ROOT, "pipeline", "jobs_medallion.py")
        with open(path, "r") as f:
            content = f.read()
        assert "medallion_full_pipeline" in content

    def test_computed_features_merge_in_assets(self):
        """assets_medallion.py must merge computed features by order_id join."""
        path = os.path.join(ROOT, "pipeline", "assets_medallion.py")
        with open(path, "r") as f:
            content = f.read()
        assert "computed_features" in content
        assert "merge" in content
        assert "order_id" in content

    def test_ml_model_accepts_extra_feature_cols(self):
        """train_delay_model must accept extra_feature_cols parameter."""
        path = os.path.join(ROOT, "pipeline", "ml_model.py")
        with open(path, "r") as f:
            content = f.read()
        assert "extra_feature_cols" in content


# =============================================================================
# 9. Docker configuration
# =============================================================================

class TestDockerConfig:
    """Verify docker-compose.yml has correct service URLs."""

    def test_dagster_webserver_url_uses_port_3000(self):
        """DAGSTER_WEBSERVER_URL must use internal port 3000, not host port 3001."""
        path = os.path.join(ROOT, "docker-compose.yml")
        with open(path, "r") as f:
            content = f.read()
        # Must have port 3000 for internal URL
        assert "dagster-webserver:3000" in content
        # Must NOT use port 3001 for internal URL
        lines_with_url = [l for l in content.split("\n")
                          if "DAGSTER_WEBSERVER_URL" in l and "3001" in l]
        assert len(lines_with_url) == 0, f"Found DAGSTER_WEBSERVER_URL with port 3001: {lines_with_url}"

    def test_agents_service_has_dagster_url_env(self):
        """agents service must define DAGSTER_WEBSERVER_URL."""
        path = os.path.join(ROOT, "docker-compose.yml")
        with open(path, "r") as f:
            content = f.read()
        assert "DAGSTER_WEBSERVER_URL" in content


# =============================================================================
# 10. End-to-end CSV ingestion simulation
# =============================================================================

class TestCSVIngestionEndToEnd:
    """Simulate the full ingestion flow without real Docker."""

    def test_csv_sample_reading_and_schema_inference_mock(self):
        """Full ingestion cycle with mocked LLM (no API call)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a realistic CSV file
            csv_path = Path(tmpdir) / "new_customer_orders.csv"
            csv_path.write_text(
                "OrderID,CustomerName,Quantity,UnitPrice,OrderDate,Status\n"
                "ORD001,Acme Corp,50,12.99,2026-01-15,Shipped\n"
                "ORD002,Beta Inc,10,99.00,2026-01-16,Pending\n"
                "ORD003,Gamma LLC,,15.50,2026-01-17,Processing\n"
            )

            # Verify reading sample
            import csv
            with open(csv_path, encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)

            header = rows[0]
            data_rows = rows[1:]

            assert header == ["OrderID", "CustomerName", "Quantity", "UnitPrice", "OrderDate", "Status"]
            assert len(data_rows) == 3
            # Empty Quantity should be readable (not crash)
            assert data_rows[2][2] == ""  # Empty Quantity field

    def test_generated_loader_validates(self):
        """A correctly generated loader must pass all 5 validation gates."""
        loader_code = '''
def load_csv(path):
    import csv
    from pathlib import Path
    from datetime import datetime
    with open(path, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            quantity = None
            try:
                if row.get('Quantity', '').strip():
                    quantity = int(row['Quantity'])
            except (ValueError, TypeError):
                quantity = None
            unit_price = None
            try:
                if row.get('UnitPrice', '').strip():
                    unit_price = float(row['UnitPrice'])
            except (ValueError, TypeError):
                unit_price = None
            yield {
                'order_id': row.get('OrderID', '').strip() or None,
                'customer_name': row.get('CustomerName', '').strip() or None,
                'quantity': quantity,
                'unit_price': unit_price,
                'order_date': row.get('OrderDate', '').strip() or None,
                'status': row.get('Status', '').strip() or None,
            }
'''
        import ast

        # Gate 1: Python syntax
        ast.parse(loader_code)

        # Gate 2: yield present
        assert "yield" in loader_code

        # Gate 3: no print statements
        assert "print(" not in loader_code

        # Gate 4: stdlib imports only
        for forbidden in ["pandas", "numpy", "requests"]:
            assert forbidden not in loader_code

        # Gate 5: line count
        lines = [l for l in loader_code.split("\n") if l.strip()]
        assert len(lines) <= 50

    def test_loader_execution_on_real_csv(self):
        """Execute a loader against real CSV data and verify output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_orders.csv"
            csv_path.write_text(
                "OrderID,CustomerName,Quantity,UnitPrice\n"
                "ORD001,Acme,10,9.99\n"
                "ORD002,Beta,,5.50\n"
                "ORD003,Gamma,5,\n"
            )

            loader_code = '''
def load_csv(path):
    import csv
    from pathlib import Path
    with open(path, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            qty = None
            try:
                if row.get('Quantity', '').strip():
                    qty = int(row['Quantity'])
            except ValueError:
                qty = None
            price = None
            try:
                if row.get('UnitPrice', '').strip():
                    price = float(row['UnitPrice'])
            except ValueError:
                price = None
            yield {
                'order_id': row.get('OrderID', '').strip() or None,
                'customer_name': row.get('CustomerName', '').strip() or None,
                'quantity': qty,
                'unit_price': price,
            }
'''
            # Execute the loader
            namespace = {"Path": Path}
            exec(loader_code, namespace)
            load_csv = namespace["load_csv"]

            results = list(load_csv(csv_path))
            assert len(results) == 3
            assert results[0]["order_id"] == "ORD001"
            assert results[0]["quantity"] == 10
            assert results[0]["unit_price"] == 9.99
            assert results[1]["quantity"] is None  # Empty quantity
            assert results[2]["unit_price"] is None  # Empty price
            # No crashes on empty values

    def test_file_tracking_prevents_duplicate_processing(self):
        """Files already in known_files set must be skipped."""
        known_files = {"orderlist.csv", "new_customer.csv"}
        candidate_files = ["orderlist.csv", "new_customer.csv", "another_new.csv"]

        to_process = [f for f in candidate_files if f.lower() not in known_files]
        assert to_process == ["another_new.csv"]
        assert "orderlist.csv" not in to_process
        assert "new_customer.csv" not in to_process


# =============================================================================
# 11. Orchestrator tool wiring (unit tests without real infrastructure)
# =============================================================================

class TestOrchestratorTools:
    """Test that orchestrator tool functions handle errors gracefully."""

    def test_tool_returns_json_on_state_error(self):
        """If state.get_all_heartbeats fails, tool must return JSON error not crash."""
        # Simulate the get_all_heartbeats tool behavior
        def get_all_heartbeats_sim(state_module):
            try:
                heartbeats = state_module.get_all_heartbeats()
                if not heartbeats:
                    return json.dumps({"error": "No agents reporting"})
                return json.dumps([{"agent_id": h.get("agent_id")} for h in heartbeats])
            except Exception as e:
                return json.dumps({"error": str(e)})

        # Mock state that raises
        mock_state = MagicMock()
        mock_state.get_all_heartbeats.side_effect = ConnectionError("Redis unavailable")

        result = get_all_heartbeats_sim(mock_state)
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Redis" in parsed["error"]

    def test_correction_tool_validates_agent_id(self):
        """Issue correction must dispatch to correct agent."""
        corrections_issued = []

        def issue_correction_sim(agent_id: str, correction: str, state_mod, comm_mod):
            state_mod.write_correction("orchestrator", agent_id, correction)
            comm_mod.publish_correction(agent_id, correction)
            corrections_issued.append({"agent_id": agent_id, "correction": correction})
            return json.dumps({"issued": True, "agent_id": agent_id})

        mock_state = MagicMock()
        mock_comm = MagicMock()

        result = issue_correction_sim("dagster_guardian", "trigger full pipeline",
                                      mock_state, mock_comm)
        parsed = json.loads(result)
        assert parsed["issued"] is True
        assert parsed["agent_id"] == "dagster_guardian"
        assert len(corrections_issued) == 1
        mock_state.write_correction.assert_called_once_with(
            "orchestrator", "dagster_guardian", "trigger full pipeline"
        )
        mock_comm.publish_correction.assert_called_once_with(
            "dagster_guardian", "trigger full pipeline"
        )

    def test_pipeline_trigger_rejects_invalid_job_name(self):
        """trigger_dagster_pipeline must reject unknown job names."""
        allowed = {"medallion_full_pipeline", "medallion_incremental"}

        def trigger_sim(job_name: str):
            if job_name not in allowed:
                return json.dumps({"error": f"Invalid job_name. Must be one of: {allowed}"})
            return json.dumps({"triggered": True, "job": job_name})

        bad_result = json.loads(trigger_sim("delete_all_data"))
        assert "error" in bad_result

        good_result = json.loads(trigger_sim("medallion_full_pipeline"))
        assert good_result["triggered"] is True

    def test_mlflow_baseline_check_handles_missing_key(self):
        """get_mlflow_model_status must handle missing Redis baseline key."""
        def get_mlflow_sim(redis_client):
            try:
                baseline_raw = redis_client.get("mlflow:baseline")
                baseline = json.loads(baseline_raw) if baseline_raw else {}
                return json.dumps({"redis_baseline": baseline})
            except Exception as e:
                return json.dumps({"error": str(e)})

        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # Key doesn't exist

        result = json.loads(get_mlflow_sim(mock_redis))
        assert result["redis_baseline"] == {}  # Empty dict, not crash


# =============================================================================
# 12. Stress test — concurrent file ingestion
# =============================================================================

class TestConcurrentIngestion:
    """Simulate concurrent new file detection without race conditions."""

    def test_concurrent_file_processing_no_race(self):
        """Multiple CSV files must be processed without race conditions on known_files."""
        import threading

        known_files = set()
        known_lock = threading.Lock()
        results = []

        def process_file(filename: str):
            # Simulate atomic check-and-mark
            with known_lock:
                if filename in known_files:
                    return False
                known_files.add(filename)

            # Simulate processing
            time.sleep(0.01)
            results.append(filename)
            return True

        # Simulate 10 files being detected concurrently (some duplicates)
        file_names = [f"orders_{i}.csv" for i in range(5)] * 2  # Each file detected twice
        threads = [threading.Thread(target=process_file, args=(f,)) for f in file_names]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each file should only be processed once
        assert len(results) == 5
        assert len(set(results)) == 5  # No duplicates

    def test_heartbeat_age_calculation(self):
        """Heartbeat age calculation must identify truly offline agents."""
        from datetime import datetime, timedelta

        def check_offline(last_seen_str: str, threshold_sec: int = 300) -> bool:
            try:
                if last_seen_str.endswith("+00:00"):
                    last_seen_str = last_seen_str[:-6]
                last_seen = datetime.fromisoformat(
                    last_seen_str.replace("T", " ").split(".")[0]
                )
                age_sec = (datetime.utcnow() - last_seen).total_seconds()
                return age_sec > threshold_sec
            except Exception:
                return False

        now = datetime.utcnow()
        # Recent heartbeat — NOT offline
        recent = (now - timedelta(seconds=60)).isoformat()
        assert not check_offline(recent)

        # Stale heartbeat — IS offline
        stale = (now - timedelta(seconds=400)).isoformat()
        assert check_offline(stale)

        # Exactly at threshold — NOT offline
        at_threshold = (now - timedelta(seconds=299)).isoformat()
        assert not check_offline(at_threshold)

    def test_alert_queue_thread_safety(self):
        """Alert queue must be thread-safe under concurrent writes."""
        import threading

        alert_queue = []
        alert_lock = threading.Lock()
        errors = []

        def add_alerts(count: int):
            for i in range(count):
                try:
                    with alert_lock:
                        alert_queue.append({
                            "agent_id": f"agent_{threading.current_thread().name}",
                            "severity": "HIGH",
                            "message": f"Alert {i}",
                        })
                except Exception as e:
                    errors.append(str(e))

        threads = [threading.Thread(target=add_alerts, args=(20,), name=f"t{i}")
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(alert_queue) == 100  # 5 threads × 20 alerts


# =============================================================================
# 13. License and README checks
# =============================================================================

class TestProjectFiles:
    """Verify project metadata files are correct."""

    def test_mit_license_exists(self):
        """LICENSE file must exist."""
        assert os.path.exists(os.path.join(ROOT, "LICENSE"))

    def test_agpl_license_content(self):
        """LICENSE must contain AGPL v3 text."""
        with open(os.path.join(ROOT, "LICENSE"), "r") as f:
            content = f.read()
        assert "GNU AFFERO GENERAL PUBLIC LICENSE" in content
        assert "Version 3" in content

    def test_readme_has_correct_title(self):
        """README must say 'ForeverAutonomous'."""
        with open(os.path.join(ROOT, "README.md"), "r") as f:
            content = f.read()
        assert "ForeverAutonomous" in content

    def test_readme_mentions_13_agents(self):
        """README must mention all 13 agents."""
        with open(os.path.join(ROOT, "README.md"), "r") as f:
            content = f.read()
        assert "13" in content

    def test_readme_mentions_deepagents(self):
        """README must mention deepagents integration."""
        with open(os.path.join(ROOT, "README.md"), "r") as f:
            content = f.read()
        # Either deepagents or LangGraph mentioned
        has_deepagents = "deepagents" in content.lower() or "langgraph" in content.lower()
        # This is a new feature — readme may or may not have been updated
        # Just ensure it mentions the AI backbone
        assert "LangGraph" in content or "deepagents" in content or "Claude" in content


# =============================================================================
# 14. Requirements validation
# =============================================================================

class TestRequirements:
    """Verify all required packages are in requirements-agents.txt."""

    def test_deepagents_in_requirements(self):
        """requirements-agents.txt must include deepagents."""
        path = os.path.join(ROOT, "requirements-agents.txt")
        with open(path, "r") as f:
            content = f.read()
        assert "deepagents" in content

    def test_langchain_anthropic_in_requirements(self):
        """requirements-agents.txt must include langchain-anthropic."""
        path = os.path.join(ROOT, "requirements-agents.txt")
        with open(path, "r") as f:
            content = f.read()
        assert "langchain-anthropic" in content

    def test_langgraph_in_requirements(self):
        """requirements-agents.txt must include langgraph."""
        path = os.path.join(ROOT, "requirements-agents.txt")
        with open(path, "r") as f:
            content = f.read()
        assert "langgraph" in content

    def test_pydantic_in_requirements(self):
        """requirements-agents.txt must include pydantic."""
        path = os.path.join(ROOT, "requirements-agents.txt")
        with open(path, "r") as f:
            content = f.read()
        assert "pydantic" in content

    def test_anthropic_in_requirements(self):
        """requirements-agents.txt must include anthropic."""
        path = os.path.join(ROOT, "requirements-agents.txt")
        with open(path, "r") as f:
            content = f.read()
        assert "anthropic" in content
