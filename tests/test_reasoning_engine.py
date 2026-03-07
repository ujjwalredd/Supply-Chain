"""Unit tests for reasoning/engine.py — mocks Anthropic client."""

from unittest.mock import MagicMock, patch

import pytest


def _make_tool_use_block(data: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.name = "supply_chain_analysis"
    block.input = data
    return block


def _make_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_usage(input_tokens: int = 100, output_tokens: int = 50):
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    return usage


# ── analyze_structured ───────────────────────────────────────────────────────

def test_analyze_structured_uses_tool_use():
    """analyze_structured should extract data from tool_use block."""
    from reasoning.engine import analyze_structured

    tool_data = {
        "root_cause": "Supplier SUP-004 exceeded max_delay_days constraint",
        "financial_impact": "$45,000 at risk",
        "options": [
            {"action": "Expedite via air freight", "pros": ["Fast"], "cons": ["Expensive"], "confidence": 0.8},
        ],
        "recommendation": "Expedite via air freight and issue supplier warning",
        "autonomous_executable": False,
    }

    mock_response = MagicMock()
    mock_response.content = [_make_tool_use_block(tool_data)]
    mock_response.usage = _make_usage(120, 60)

    with patch("reasoning.engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = analyze_structured(
            deviation={"deviation_id": "DEV-0001", "type": "DELAY", "severity": "HIGH"},
            order={"order_id": "ORD-001", "delay_days": 10},
        )

    assert result.root_cause == tool_data["root_cause"]
    assert result.financial_impact == tool_data["financial_impact"]
    assert len(result.options) == 1
    assert result.options[0].action == "Expedite via air freight"
    assert result.options[0].confidence == pytest.approx(0.8)
    assert result.recommendation == tool_data["recommendation"]
    assert result.autonomous_executable is False
    assert result.input_tokens == 120
    assert result.output_tokens == 60


def test_analyze_structured_returns_fallback_on_api_error():
    """Should return graceful fallback when Anthropic API raises."""
    from reasoning.engine import analyze_structured

    with patch("reasoning.engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API timeout")
        mock_get_client.return_value = mock_client

        result = analyze_structured(
            deviation={"deviation_id": "DEV-0002", "type": "STOCKOUT", "severity": "MEDIUM"},
        )

    assert result.root_cause == "Analysis unavailable"
    assert result.recommendation == "Manual review required"
    assert result.autonomous_executable is False


def test_analyze_structured_no_api_key():
    """Should raise ValueError when ANTHROPIC_API_KEY is not set."""
    import os
    from reasoning.engine import _get_client

    original = os.environ.pop("ANTHROPIC_API_KEY", None)
    import reasoning.engine as eng
    original_key = eng.ANTHROPIC_API_KEY
    eng.ANTHROPIC_API_KEY = None
    try:
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            _get_client()
    finally:
        eng.ANTHROPIC_API_KEY = original_key
        if original:
            os.environ["ANTHROPIC_API_KEY"] = original


# ── Tool schema ──────────────────────────────────────────────────────────────

def test_analysis_tool_schema_has_required_fields():
    """_ANALYSIS_TOOL must define all required output fields."""
    from reasoning.engine import _ANALYSIS_TOOL

    required = set(_ANALYSIS_TOOL["input_schema"]["required"])
    assert "root_cause" in required
    assert "financial_impact" in required
    assert "options" in required
    assert "recommendation" in required
    assert "autonomous_executable" in required


def test_analysis_tool_options_schema():
    """options array items must require action, pros, cons, confidence."""
    from reasoning.engine import _ANALYSIS_TOOL

    items = _ANALYSIS_TOOL["input_schema"]["properties"]["options"]["items"]
    required = set(items["required"])
    assert {"action", "pros", "cons", "confidence"} == required


# ── stream_analysis ──────────────────────────────────────────────────────────

def test_stream_analysis_yields_tokens():
    """stream_analysis should yield tokens from Claude text stream."""
    from reasoning.engine import stream_analysis

    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.text_stream = iter(["Root ", "cause: ", "supplier delay"])
    final_msg = MagicMock()
    final_msg.usage = _make_usage(80, 40)
    mock_stream.get_final_message.return_value = final_msg

    with patch("reasoning.engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        mock_get_client.return_value = mock_client

        usage_sink: dict = {}
        tokens = list(stream_analysis(
            deviation={"deviation_id": "DEV-0003", "type": "DELAY"},
            _usage_sink=usage_sink,
        ))

    assert tokens == ["Root ", "cause: ", "supplier delay"]
    assert usage_sink["input_tokens"] == 80
    assert usage_sink["output_tokens"] == 40
