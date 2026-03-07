"""
AI reasoning engine for supply chain deviations.

Calls Anthropic Claude API with full context: order data, supplier history, ontology
constraints. Streams token-by-token and returns structured output via tool_use
for automated action recommendations.
"""

import json
import logging
import os
from typing import Any, AsyncIterator, Iterator

from anthropic import Anthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")


class TradeOffOption(BaseModel):
    """A single trade-off option evaluated by AI."""

    action: str = Field(..., description="Recommended action")
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1)


class AIAnalysisOutput(BaseModel):
    """Structured output from Claude for deviation analysis."""

    root_cause: str = Field(..., description="Identified root cause")
    financial_impact: str = Field(..., description="Estimated financial impact")
    options: list[TradeOffOption] = Field(default_factory=list)
    recommendation: str = Field(..., description="Primary recommendation")
    autonomous_executable: bool = Field(
        False,
        description="Whether the recommendation can be auto-executed",
    )
    input_tokens: int = Field(0, description="Claude input token count")
    output_tokens: int = Field(0, description="Claude output token count")


SYSTEM_PROMPT = """You are an expert supply chain analyst for a control tower. Analyze deviations and recommend corrective actions.

You have access to:
- Order data: product, quantity, value, expected vs actual delivery, delay days, status
- Supplier history: trust score, delayed orders %, avg delay days
- Ontology constraints: hard limits like max_delay_days, min_inventory_level, max_single_supplier_dependency

Output rules:
- Write in clear, professional prose. No emojis. No symbols like ●, ◆, or →.
- Do not use markdown headers (## or **). Use plain paragraph breaks instead.
- Be concise and factual. Avoid filler phrases like "Great news" or "It is important to note".
- If an ontology constraint is violated, name it explicitly in the root cause.
- Express confidence as a decimal between 0.0 and 1.0 for each trade-off option."""

# Tool schema for structured output — Claude fills this via tool_use instead of free-form JSON
_ANALYSIS_TOOL = {
    "name": "supply_chain_analysis",
    "description": "Record the structured analysis of a supply chain deviation",
    "input_schema": {
        "type": "object",
        "properties": {
            "root_cause": {
                "type": "string",
                "description": "Identified root cause of the deviation",
            },
            "financial_impact": {
                "type": "string",
                "description": "Estimated financial impact (e.g. '$12,000 at risk')",
            },
            "options": {
                "type": "array",
                "description": "Trade-off options with pros/cons",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "pros": {"type": "array", "items": {"type": "string"}},
                        "cons": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["action", "pros", "cons", "confidence"],
                },
            },
            "recommendation": {
                "type": "string",
                "description": "Primary recommended action",
            },
            "autonomous_executable": {
                "type": "boolean",
                "description": "True if the recommendation can be auto-executed without human approval",
            },
        },
        "required": [
            "root_cause",
            "financial_impact",
            "options",
            "recommendation",
            "autonomous_executable",
        ],
    },
}


def _build_context(deviation: dict[str, Any], order: dict | None, supplier: dict | None, constraints: list[dict]) -> str:
    """Build context string for Claude."""
    parts = [f"## Deviation\n{json.dumps(deviation, indent=2)}"]
    if order:
        parts.append(f"\n## Order\n{json.dumps(order, indent=2)}")
    if supplier:
        parts.append(f"\n## Supplier\n{json.dumps(supplier, indent=2)}")
    if constraints:
        parts.append(f"\n## Ontology Constraints\n{json.dumps(constraints, indent=2)}")
    return "\n".join(parts)


def _get_client() -> Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is required")
    return Anthropic(api_key=ANTHROPIC_API_KEY)


def stream_analysis(
    deviation: dict[str, Any],
    order: dict | None = None,
    supplier: dict | None = None,
    ontology_constraints: list[dict] | None = None,
    _usage_sink: dict | None = None,
) -> Iterator[str]:
    """
    Stream Claude's analysis token-by-token for real-time dashboard display.

    If _usage_sink dict is provided, it is populated with:
      {"input_tokens": int, "output_tokens": int}
    after all tokens have been yielded.
    """
    client = _get_client()
    context = _build_context(
        deviation,
        order or {},
        supplier or {},
        ontology_constraints or [],
    )
    prompt = f"""Analyze this supply chain deviation. Write in plain prose — no emojis, no markdown symbols, no headers. Use paragraph breaks between sections.

Cover these areas in order:
Root cause — what caused this deviation and whether any ontology constraints are violated.
Financial impact — estimated dollar exposure and operational risk.
Options — two or three trade-off options, each with pros, cons, and a confidence score (0.0 to 1.0).
Recommendation — your primary recommended action with rationale.

{context}"""

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text
            # Capture token usage after all content has streamed
            if _usage_sink is not None:
                try:
                    final = stream.get_final_message()
                    _usage_sink["input_tokens"] = final.usage.input_tokens
                    _usage_sink["output_tokens"] = final.usage.output_tokens
                except Exception:
                    pass
    except Exception as e:
        logger.exception("Claude stream failed: %s", e)
        yield f"\n\nError: {str(e)}"


async def stream_analysis_async(
    deviation: dict[str, Any],
    order: dict | None = None,
    supplier: dict | None = None,
    ontology_constraints: list[dict] | None = None,
) -> AsyncIterator[str]:
    """Async version of stream_analysis."""
    # Anthropic SDK sync streaming - run in executor for async
    import asyncio

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str] = asyncio.Queue()

    def _run_stream() -> None:
        for token in stream_analysis(deviation, order, supplier, ontology_constraints):
            loop.call_soon_threadsafe(queue.put_nowait, token)
        loop.call_soon_threadsafe(queue.put_nowait, "")

    asyncio.create_task(asyncio.to_thread(_run_stream))
    while True:
        token = await queue.get()
        if not token:
            break
        yield token


def analyze_structured(
    deviation: dict[str, Any],
    order: dict | None = None,
    supplier: dict | None = None,
    ontology_constraints: list[dict] | None = None,
) -> AIAnalysisOutput:
    """
    Call Claude with tool_use for reliable machine-readable structured output.
    No JSON parsing fragility — Claude fills in the tool input schema directly.
    """
    client = _get_client()
    context = _build_context(
        deviation,
        order or {},
        supplier or {},
        ontology_constraints or [],
    )
    prompt = f"""Analyze this supply chain deviation and call the supply_chain_analysis tool with your findings.

{context}"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[_ANALYSIS_TOOL],
            tool_choice={"type": "tool", "name": "supply_chain_analysis"},
            messages=[{"role": "user", "content": prompt}],
        )

        input_tokens = getattr(response.usage, "input_tokens", 0)
        output_tokens = getattr(response.usage, "output_tokens", 0)

        # Extract tool_use block — Claude is guided to call the tool
        for block in response.content:
            if block.type == "tool_use" and block.name == "supply_chain_analysis":
                data = block.input
                result = AIAnalysisOutput.model_validate(data)
                result.input_tokens = input_tokens
                result.output_tokens = output_tokens
                return result

        # tool_choice=tool forces Claude to always call the tool, so no fallback needed
        logger.warning("Claude returned no tool_use block (unexpected with forced tool_choice)")
        return AIAnalysisOutput(
            root_cause="Analysis unavailable — Claude did not return structured output",
            financial_impact="Unknown",
            options=[],
            recommendation="Manual review required",
            autonomous_executable=False,
        )

    except Exception as e:
        logger.exception("Claude structured call failed: %s", e)
        return AIAnalysisOutput(
            root_cause="Analysis unavailable",
            financial_impact="Unknown",
            options=[],
            recommendation="Manual review required",
            autonomous_executable=False,
        )
