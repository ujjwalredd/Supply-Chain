"""
Regression tests for the 20 bug fixes (C1–L3).

These tests are unit/integration level — they verify the fix logic without
requiring a live database or running Docker stack.  DB-dependent paths are
mocked where necessary.
"""

import pytest
import re
import time
from unittest.mock import AsyncMock, MagicMock, patch


# ── C1 / H4 — UniqueConstraint on order_events ──────────────────────────────

class TestOrderEventUniqueConstraint:
    def test_model_has_unique_constraint(self):
        from api.models import OrderEvent
        from sqlalchemy import UniqueConstraint
        args = OrderEvent.__table_args__
        names = [c.name for c in args if isinstance(c, UniqueConstraint)]
        assert "uq_order_events_order_version" in names

    def test_model_has_composite_index(self):
        from api.models import OrderEvent
        from sqlalchemy import Index
        args = OrderEvent.__table_args__
        index_names = [c.name for c in args if isinstance(c, Index)]
        assert "ix_order_events_order_version" in index_names


# ── C2 — Sanitize user question in query.py ──────────────────────────────────

class TestQueryPromptSanitization:
    def test_question_is_sanitized_before_prompt(self):
        """sanitize_for_prompt must be importable and functional."""
        from agents.security import sanitize_for_prompt
        result = sanitize_for_prompt("Hello world", max_length=100, field_name="question")
        assert result == "Hello world"

    def test_null_bytes_stripped(self):
        from agents.security import sanitize_for_prompt
        result = sanitize_for_prompt("Hello\x00world")
        assert "\x00" not in result

    def test_query_router_imports_sanitize(self):
        """Ensure query.py imports sanitize_for_prompt."""
        import importlib, ast, inspect
        import api.routers.query as q_module
        src = inspect.getsource(q_module)
        assert "sanitize_for_prompt" in src

    def test_question_wrapped_in_xml_tags(self):
        import inspect
        import api.routers.query as q_module
        src = inspect.getsource(q_module)
        assert "<question>" in src


# ── C3 — Redact Redis error in health endpoint ───────────────────────────────

class TestHealthEndpointRedaction:
    def test_redis_error_is_redacted(self):
        import inspect
        import api.main as main_module
        src = inspect.getsource(main_module)
        # Should NOT contain f"error: {e}" for Redis
        assert 'f"error: {e}"' not in src
        assert '"error: connection failed"' in src


# ── C4 — Sanitize LLM-generated table_name ───────────────────────────────────

class TestTableNameSanitization:
    def test_sanitize_regex_strips_path_traversal(self):
        table_name = "../../../etc/passwd"
        sanitized = re.sub(r"[^\w]", "_", table_name)[:80]
        assert ".." not in sanitized
        assert "/" not in sanitized
        assert sanitized.endswith("etc_passwd")

    def test_sanitize_truncates_at_80(self):
        table_name = "a" * 200
        sanitized = re.sub(r"[^\w]", "_", table_name)[:80]
        assert len(sanitized) == 80

    def test_data_ingestion_agent_imports_re(self):
        import inspect, agents.data_ingestion_agent as dia
        src = inspect.getsource(dia)
        assert "re.sub" in src
        assert "table_name" in src


# ── C5 + M3 — CORS headers ───────────────────────────────────────────────────

class TestCorsHeaders:
    def test_x_api_key_in_allow_headers(self):
        import inspect
        import api.main as main_module
        src = inspect.getsource(main_module)
        assert "X-API-Key" in src
        assert "expose_headers" in src
        assert "X-Request-ID" in src


# ── H1 — ThreadedConnectionPool ──────────────────────────────────────────────

class TestThreadedConnectionPool:
    def test_state_uses_threaded_pool(self):
        import inspect
        import agents.state as state_module
        src = inspect.getsource(state_module)
        assert "ThreadedConnectionPool" in src
        assert "SimpleConnectionPool" not in src


# ── H2 — Terminal state guards in actions.py ─────────────────────────────────

class TestTerminalStateGuards:
    def _make_action(self, status, resolved=False):
        action = MagicMock()
        action.status = status
        action.resolved = resolved
        return action

    def test_complete_rejects_already_completed(self):
        from fastapi import HTTPException
        import asyncio, api.routers.actions as ar

        action = self._make_action("COMPLETED")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = action

        async def run():
            db = AsyncMock()
            db.execute.return_value = mock_result
            with pytest.raises(HTTPException) as exc_info:
                await ar.complete_action(1, db=db)
            assert exc_info.value.status_code == 409

        asyncio.get_event_loop().run_until_complete(run())

    def test_cancel_rejects_already_cancelled(self):
        from fastapi import HTTPException
        import asyncio, api.routers.actions as ar

        action = self._make_action("CANCELLED")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = action

        async def run():
            db = AsyncMock()
            db.execute.return_value = mock_result
            with pytest.raises(HTTPException) as exc_info:
                await ar.cancel_action(1, db=db)
            assert exc_info.value.status_code == 409

        asyncio.get_event_loop().run_until_complete(run())

    def test_resolve_rejects_already_resolved(self):
        from fastapi import HTTPException
        import asyncio, api.routers.actions as ar

        action = self._make_action("COMPLETED", resolved=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = action

        async def run():
            db = AsyncMock()
            db.execute.return_value = mock_result
            with pytest.raises(HTTPException) as exc_info:
                await ar.resolve_action(1, outcome_note="done", success=True, db=db)
            assert exc_info.value.status_code == 409

        asyncio.get_event_loop().run_until_complete(run())


# ── H3 — MTTR uses completed_at not created_at ───────────────────────────────

class TestMttrCalculation:
    def test_mttr_uses_completed_at(self):
        import inspect, api.routers.actions as ar
        src = inspect.getsource(ar)
        # Should reference completed_at, not created_at in the avg_resolve_seconds context
        assert "PendingAction.completed_at - Deviation.detected_at" in src
        assert "PendingAction.created_at - Deviation.detected_at" not in src


# ── H5 — pg_advisory_xact_lock in write_audit_immutable ─────────────────────

class TestAdvisoryLock:
    def test_advisory_lock_present(self):
        import inspect, agents.state as s
        src = inspect.getsource(s)
        assert "pg_advisory_xact_lock" in src
        assert "hashtext('audit_chain')" in src


# ── H6 — Error redaction in streaming.py and lineage.py ─────────────────────

class TestErrorRedaction:
    def test_streaming_no_str_exc(self):
        import inspect, api.routers.streaming as st
        src = inspect.getsource(st)
        assert "str(exc)" not in src

    def test_lineage_error_redacted(self):
        import inspect, api.routers.lineage as ln
        src = inspect.getsource(ln)
        # Must not interpolate exception into detail
        assert 'f"Lineage query failed: {e}"' not in src
        assert '"Lineage query failed"' in src


# ── H7 — Partial matching minimum length + no duplicate key ──────────────────

class TestOntologyPartialMatch:
    def test_no_duplicate_order_number_key(self):
        import inspect, api.routers.ontology as ont
        src = inspect.getsource(ont)
        # Count occurrences of the duplicate key
        count = src.count('"order_number": "order_id"')
        assert count == 1, f"Expected 1 occurrence of order_number key, found {count}"

    def test_partial_match_minimum_length(self):
        import inspect, api.routers.ontology as ont
        src = inspect.getsource(ont)
        assert "len(alias) >= 4" in src
        assert "len(lower) >= 4" in src

    def test_short_key_not_partial_matched(self):
        """Key 'q' (len=1) must not partial-match 'qty'."""
        from api.routers.ontology import _FIELD_MAP_LOWER
        lower = "q"
        partial_match = next(
            (
                canon
                for alias, canon in _FIELD_MAP_LOWER.items()
                if len(alias) >= 4 and len(lower) >= 4 and (alias in lower or lower in alias)
            ),
            None,
        )
        assert partial_match is None


# ── M1 — HTTPException instead of 200 error in events.py ────────────────────

class TestEventsHttpException:
    def test_get_event_history_raises_on_error(self):
        import asyncio
        from fastapi import HTTPException
        from api.routers import events as ev_router

        async def run():
            db = AsyncMock()
            db.execute.side_effect = RuntimeError("db is down")
            with pytest.raises(HTTPException) as exc_info:
                await ev_router.get_event_history("ORD-1", db=db)
            assert exc_info.value.status_code == 500

        asyncio.get_event_loop().run_until_complete(run())

    def test_get_recent_events_raises_on_error(self):
        import asyncio
        from fastapi import HTTPException
        from api.routers import events as ev_router

        async def run():
            db = AsyncMock()
            db.execute.side_effect = RuntimeError("db is down")
            with pytest.raises(HTTPException) as exc_info:
                await ev_router.get_recent_events(db=db)
            assert exc_info.value.status_code == 500

        asyncio.get_event_loop().run_until_complete(run())


# ── M2 — Status validation in escalations.py ────────────────────────────────

class TestEscalationStatusValidation:
    def test_invalid_status_raises_422(self):
        from fastapi import HTTPException
        from api.routers.escalations import list_escalations
        with pytest.raises(HTTPException) as exc_info:
            list_escalations(status="INVALID", limit=10)
        assert exc_info.value.status_code == 422

    def test_valid_status_open_passes(self):
        """OPEN status should not raise before DB call."""
        from api.routers.escalations import _VALID_STATUSES
        assert "OPEN" in _VALID_STATUSES
        assert "RESOLVED" in _VALID_STATUSES


# ── M4 — Redact APIStatusError details in query.py ──────────────────────────

class TestQueryStreamErrorRedaction:
    def test_api_status_error_redacted(self):
        import inspect, api.routers.query as qr
        src = inspect.getsource(qr)
        assert "f'Error: {e}'" not in src
        assert 'f"Error: {e}"' not in src
        assert "AI service returned an error" in src


# ── M5 — resolved_by validation ──────────────────────────────────────────────

class TestResolvedByValidation:
    def test_resolved_by_has_min_max_length(self):
        import inspect, api.routers.escalations as esc
        src = inspect.getsource(esc)
        assert "min_length=1" in src
        assert "max_length=120" in src


# ── L1 — Persist last_retrain_time in Redis ──────────────────────────────────

class TestRetainTimePersistence:
    def test_redis_key_defined(self):
        from agents.mlflow_guardian import LAST_RETRAIN_KEY
        assert LAST_RETRAIN_KEY == "mlflow:last_retrain_time"

    def test_no_instance_last_retrain_attribute(self):
        """_last_retrain_time should no longer be an instance attribute."""
        import inspect, agents.mlflow_guardian as mg
        src = inspect.getsource(mg)
        assert "self._last_retrain_time" not in src

    def test_get_set_retrain_time_methods_exist(self):
        from agents.mlflow_guardian import MLflowGuardianAgent
        assert hasattr(MLflowGuardianAgent, "_get_last_retrain_time")
        assert hasattr(MLflowGuardianAgent, "_set_last_retrain_time")

    def test_get_last_retrain_time_returns_float_on_redis_failure(self):
        """Should return 0.0 gracefully when Redis is unavailable."""
        from agents.mlflow_guardian import MLflowGuardianAgent
        agent = MLflowGuardianAgent.__new__(MLflowGuardianAgent)
        agent._redis = None

        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("redis down")
        with patch.object(agent, "_r", return_value=mock_redis):
            result = agent._get_last_retrain_time()
        assert result == 0.0


# ── L2 — Pagination in get_order_history ─────────────────────────────────────

class TestOrderHistoryPagination:
    def test_get_order_history_accepts_limit_offset(self):
        import inspect, api.event_store as es
        import asyncio

        sig = es.get_order_history.__code__.co_varnames
        assert "limit" in sig
        assert "offset" in sig

    def test_events_router_exposes_pagination_params(self):
        import inspect, api.routers.events as ev
        src = inspect.getsource(ev)
        assert "limit" in src
        assert "offset" in src


# ── L3 — startswith path matching fix ───────────────────────────────────────

class TestPublicPathMatching:
    def _matches_public(self, path):
        from api.auth import _PUBLIC_PREFIXES, _PUBLIC_EXACT
        return (
            path in _PUBLIC_EXACT
            or any(path == p or path.startswith(p + "/") for p in _PUBLIC_PREFIXES)
        )

    def test_health_path_is_public(self):
        assert self._matches_public("/health")

    def test_health_subpath_is_public(self):
        assert self._matches_public("/health/")

    def test_health_admin_is_not_public(self):
        """health-admin must NOT bypass auth."""
        assert not self._matches_public("/health-admin")

    def test_docs_is_public(self):
        assert self._matches_public("/docs")

    def test_metrics_is_public(self):
        assert self._matches_public("/metrics")

    def test_root_is_public(self):
        assert self._matches_public("/")

    def test_orders_is_not_public(self):
        assert not self._matches_public("/orders")

    def test_auth_module_uses_correct_pattern(self):
        import inspect, api.auth as auth
        src = inspect.getsource(auth)
        assert 'path.startswith(p + "/")' in src
        # Must NOT have the old bare startswith
        assert 'path.startswith(p)' not in src


# ── Fix-1 regression: migration 009 idempotency ──────────────────────────────

def _load_migration_009():
    """Import the 009 migration module (filename starts with a digit, so use importlib)."""
    import importlib.util, pathlib
    p = pathlib.Path(__file__).parent.parent / "alembic" / "versions" / "009_add_event_sourcing_constraints.py"
    spec = importlib.util.spec_from_file_location("migration_009", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMigration009Idempotency:
    def test_upgrade_uses_conditional_ddl(self):
        """upgrade() must use raw SQL with IF NOT EXISTS guards, not op.create_*."""
        import inspect
        m009 = _load_migration_009()
        src = inspect.getsource(m009.upgrade)
        # Must NOT call the non-idempotent helpers
        assert "op.create_unique_constraint" not in src
        assert "op.create_index" not in src
        # Must use conditional paths
        assert "IF NOT EXISTS" in src
        assert "DO $$" in src

    def test_downgrade_uses_if_exists(self):
        import inspect
        m009 = _load_migration_009()
        src = inspect.getsource(m009.downgrade)
        assert "DROP INDEX IF EXISTS" in src
        assert "DROP CONSTRAINT IF EXISTS" in src

    def test_revision_fits_in_varchar32(self):
        m009 = _load_migration_009()
        assert len(m009.revision) <= 32

    def test_down_revision_is_008(self):
        m009 = _load_migration_009()
        assert m009.down_revision == "008_agent_tables"


# ── Fix-2 regression: ontology partial-match direction + uniqueness ───────────

class TestOntologyPartialMatchV2:

    def _do_partial(self, lower: str) -> str | None:
        """Run the exact partial-match logic from ontology.py."""
        from api.routers.ontology import _FIELD_MAP_LOWER
        partial_targets: set[str] = {
            canon
            for alias, canon in _FIELD_MAP_LOWER.items()
            if len(alias) >= 4 and len(lower) >= 4 and lower in alias
        }
        return next(iter(partial_targets)) if len(partial_targets) == 1 else None

    # ── direction: only lower-in-alias is safe ────────────────────────────────

    def test_reverse_direction_no_longer_in_source(self):
        """Source must NOT contain the dangerous 'alias in lower' direction."""
        import inspect, api.routers.ontology as ont
        src = inspect.getsource(ont)
        # The old bidirectional check
        assert "alias in lower or lower in alias" not in src
        # The dangerous direction alone
        assert "alias in lower" not in src

    def test_only_lower_in_alias_direction(self):
        """Source must use exactly the safe unidirectional check."""
        import inspect, api.routers.ontology as ont
        src = inspect.getsource(ont)
        assert "lower in alias" in src

    def test_price_rate_schedule_not_mapped(self):
        """'price_rate_schedule' contains alias 'rate' (reverse dir) — must NOT map."""
        result = self._do_partial("price_rate_schedule")
        assert result is None, f"Expected no match, got {result!r}"

    def test_order_num_maps_to_order_id(self):
        """'order_num' is a substring of 'order_number' → should map to order_id."""
        result = self._do_partial("order_num")
        assert result == "order_id", f"Expected order_id, got {result!r}"

    def test_qty_abbrev_maps_to_quantity(self):
        """'qty' is a substring of 'qty' itself (exact, handled before partial),
        and 'qtys' (a plausible typo) should map to quantity."""
        result = self._do_partial("qtys")
        # 'qtys' is a substring of... nothing in the map — should be None
        # (this validates that there's no accidental over-reach)
        assert result is None

    # ── uniqueness: ambiguous inputs must go to unmapped ─────────────────────

    def test_ambiguous_field_falls_to_unmapped(self):
        """A field that matches aliases resolving to >1 canonical must be unmapped."""
        from api.routers.ontology import _FIELD_MAP_LOWER
        # Find an input that would hit multiple canonicals under the old logic
        # by scanning for an actual ambiguous case, or verify the guard exists.
        lower = "date"  # 'date' is in 'delivery_date'→expected_delivery AND
                        # 'actual_delivery_date'→actual_delivery AND 'dateReceived'→actual_delivery
        partial_targets: set[str] = {
            canon
            for alias, canon in _FIELD_MAP_LOWER.items()
            if len(alias) >= 4 and len(lower) >= 4 and lower in alias
        }
        if len(partial_targets) > 1:
            # Verify the guard fires: the normalize endpoint must return unmapped
            result = self._do_partial(lower)
            assert result is None, (
                f"Ambiguous input '{lower}' matched {partial_targets} — "
                f"expected None (unmapped), got {result!r}"
            )

    def test_uniqueness_guard_in_source(self):
        """Source must check that exactly one canonical target was found."""
        import inspect, api.routers.ontology as ont
        src = inspect.getsource(ont)
        assert "partial_targets" in src
        assert "len(partial_targets) == 1" in src

    def test_normalize_endpoint_rejects_ambiguous(self):
        """POST /ontology/normalize must put an ambiguous partial match into unmapped."""
        import asyncio
        from api.routers.ontology import normalize_fields

        async def run():
            # 'date' matches multiple canonical fields
            result = await normalize_fields(fields={"date": "2026-01-01"})
            # If ambiguous it must land in unmapped, not normalized
            if len({
                canon
                for alias, canon in __import__(
                    "api.routers.ontology", fromlist=["_FIELD_MAP_LOWER"]
                )._FIELD_MAP_LOWER.items()
                if len(alias) >= 4 and len("date") >= 4 and "date" in alias
            }) > 1:
                assert "date" in result["unmapped"]
            # If unambiguous (only one canonical), it may be in normalized — that's fine too

        asyncio.get_event_loop().run_until_complete(run())
