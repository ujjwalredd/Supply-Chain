"""
AI reasoning engine for supply chain deviations.

Calls Anthropic Claude API with full context: order data, supplier history, ontology
constraints. Streams token-by-token and returns structured output via tool_use
for automated action recommendations.
"""

import json
import logging
import os
import time
from typing import Any, AsyncIterator, Iterator

from anthropic import Anthropic, APIConnectionError, APIStatusError
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
    financial_impact: str = Field(..., description="Estimated financial impact (prose)")
    financial_impact_usd: float = Field(0.0, description="Computed financial impact in USD")
    options: list[TradeOffOption] = Field(default_factory=list)
    recommendation: str = Field(..., description="Primary recommendation")
    autonomous_executable: bool = Field(
        False,
        description="Whether the recommendation can be auto-executed",
    )
    execution_confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Confidence (0-1) that autonomous execution is safe. Compare against AUTONOMY_CONFIDENCE_THRESHOLD.",
    )
    input_tokens: int = Field(0, description="Claude input token count")
    output_tokens: int = Field(0, description="Claude output token count")


_STREAM_ERROR_TOKEN = "\n\nAn error occurred during analysis."

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
            "execution_confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "How confident you are that autonomous execution is safe (0.0=not confident, 1.0=fully confident). Use 0.0 if autonomous_executable is false.",
            },
        },
        "required": [
            "root_cause",
            "financial_impact",
            "options",
            "recommendation",
            "autonomous_executable",
            "execution_confidence",
        ],
    },
}


def compute_financial_impact(
    deviation: dict[str, Any],
    order: dict[str, Any] | None = None,
) -> dict[str, float]:
    """
    Compute financial impact of a deviation from structured order data.

    Returns:
        {"usd": total, "carrying_cost": ..., "delay_cost": ..., "stockout_penalty": ...}

    Formulas:
        carrying_cost  = order_value × (delay_days / 30) × 0.02   (2% monthly carrying)
        delay_cost     = delay_days × 500                           ($500/day SLA penalty)
        stockout_penalty = order_value × 0.15  (STOCKOUT only)     (15% margin at risk)
    """
    order = order or {}
    order_value = float(order.get("order_value", 0))
    delay_days = float(
        deviation.get("delay_days", 0) or order.get("delay_days", 0)
    )
    dev_type = str(deviation.get("type", "DELAY")).upper()

    carrying_cost = order_value * (delay_days / 30) * 0.02 if delay_days > 0 else 0.0
    delay_cost = delay_days * 500.0
    stockout_penalty = order_value * 0.15 if dev_type == "STOCKOUT" else 0.0

    total = round(carrying_cost + delay_cost + stockout_penalty, 2)
    return {
        "usd": total,
        "carrying_cost": round(carrying_cost, 2),
        "delay_cost": round(delay_cost, 2),
        "stockout_penalty": round(stockout_penalty, 2),
    }


def _build_context(
    deviation: dict[str, Any],
    order: dict | None,
    supplier: dict | None,
    constraints: list[dict],
    financial_impact: dict[str, float] | None = None,
    network_context: dict[str, Any] | None = None,
) -> str:
    """Build context string for Claude."""
    parts = [f"## Deviation\n{json.dumps(deviation, indent=2)}"]
    if order:
        parts.append(f"\n## Order\n{json.dumps(order, indent=2)}")
    if supplier:
        parts.append(f"\n## Supplier\n{json.dumps(supplier, indent=2)}")
    if constraints:
        parts.append(f"\n## Ontology Constraints\n{json.dumps(constraints, indent=2)}")
    if financial_impact:
        parts.append(
            f"\n## Computed Financial Impact\n"
            f"Total at risk: ${financial_impact['usd']:,.2f}\n"
            f"  Carrying cost: ${financial_impact['carrying_cost']:,.2f}\n"
            f"  Delay penalty: ${financial_impact['delay_cost']:,.2f}\n"
            f"  Stockout exposure: ${financial_impact['stockout_penalty']:,.2f}"
        )
    if network_context:
        parts.append(f"\n## Network Context\n{json.dumps(network_context, indent=2)}")
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
    financial_impact: dict[str, float] | None = None,
    network_context: dict[str, Any] | None = None,
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
        financial_impact=financial_impact,
        network_context=network_context,
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
        yield _STREAM_ERROR_TOKEN


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
        try:
            for token in stream_analysis(deviation, order, supplier, ontology_constraints):
                loop.call_soon_threadsafe(queue.put_nowait, token)
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, _STREAM_ERROR_TOKEN)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, "")

    task = asyncio.create_task(asyncio.to_thread(_run_stream))
    try:
        while True:
            token = await queue.get()
            if not token:
                break
            yield token
    finally:
        # Ensure background task is cleaned up if consumer exits early
        task.cancel()


def analyze_structured(
    deviation: dict[str, Any],
    order: dict | None = None,
    supplier: dict | None = None,
    ontology_constraints: list[dict] | None = None,
    max_retries: int = 2,
    financial_impact: dict[str, float] | None = None,
    network_context: dict[str, Any] | None = None,
) -> AIAnalysisOutput:
    """
    Call Claude with tool_use for reliable machine-readable structured output.
    No JSON parsing fragility — Claude fills in the tool input schema directly.
    Retries up to max_retries times on transient API errors with exponential backoff.
    """
    # Auto-compute financial impact if not provided
    if financial_impact is None:
        financial_impact = compute_financial_impact(deviation, order or {})

    client = _get_client()
    context = _build_context(
        deviation,
        order or {},
        supplier or {},
        ontology_constraints or [],
        financial_impact=financial_impact,
        network_context=network_context,
    )
    prompt = f"""Analyze this supply chain deviation and call the supply_chain_analysis tool with your findings.

{context}"""

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=[_ANALYSIS_TOOL],
                tool_choice={"type": "tool", "name": "supply_chain_analysis"},
                messages=[{"role": "user", "content": prompt}],
                timeout=30.0,
            )

            input_tokens = getattr(response.usage, "input_tokens", 0)
            output_tokens = getattr(response.usage, "output_tokens", 0)

            for block in response.content:
                if block.type == "tool_use" and block.name == "supply_chain_analysis":
                    data = block.input
                    result = AIAnalysisOutput.model_validate(data)
                    result.input_tokens = input_tokens
                    result.output_tokens = output_tokens
                    result.financial_impact_usd = financial_impact["usd"]
                    result.execution_confidence = float(data.get("execution_confidence", 0.0))
                    return result

            logger.warning("Claude returned no tool_use block (unexpected with forced tool_choice)")
            return AIAnalysisOutput(
                root_cause="Analysis unavailable — Claude did not return structured output",
                financial_impact="Unknown",
                options=[],
                recommendation="Manual review required",
                autonomous_executable=False,
            )

        except (APIConnectionError, APIStatusError) as e:
            last_exc = e
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(
                    "Claude API transient error (attempt %d/%d, retrying in %ds): %s",
                    attempt + 1, max_retries + 1, wait, e,
                )
                time.sleep(wait)
        except Exception as e:
            logger.exception("Claude structured call failed: %s", e)
            return AIAnalysisOutput(
                root_cause="Analysis unavailable",
                financial_impact="Unknown",
                options=[],
                recommendation="Manual review required",
                autonomous_executable=False,
            )

    logger.error("Claude structured call failed after %d attempts: %s", max_retries + 1, last_exc)
    return AIAnalysisOutput(
        root_cause="Analysis unavailable",
        financial_impact="Unknown",
        options=[],
        recommendation="Manual review required",
        autonomous_executable=False,
    )


def stream_bulk_triage(
    deviations: list[dict[str, Any]],
    _usage_sink: dict | None = None,
) -> Iterator[str]:
    """Stream a prioritized triage analysis of multiple open deviations."""
    client = _get_client()

    dev_lines = "\n".join([
        f"  {i + 1}. [{d['severity']}] {d['type']} — Order {d['order_id']} | "
        f"Supplier: {d.get('supplier', 'unknown')} | "
        f"Value: ${float(d.get('order_value', 0)):,.0f} | "
        f"Action: {d.get('recommended_action', 'TBD')}"
        for i, d in enumerate(deviations)
    ])

    prompt = f"""You are reviewing {len(deviations)} open supply chain deviation(s) that require triage.

Deviations:
{dev_lines}

Your task (write in plain prose — no markdown headers, no emojis, no symbols):
1. Top priority deviation — which one to resolve first and why (financial risk, cascading effects, constraint violations).
2. Ranked action list — one concise recommended action per remaining deviation, ordered by urgency.
3. Root cause pattern — any common thread across the group (same supplier, region, product category).
4. Total financial exposure — rough aggregate exposure across all deviations.

Be concrete, specific, and factual."""

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text
            if _usage_sink is not None:
                try:
                    final = stream.get_final_message()
                    _usage_sink["input_tokens"] = final.usage.input_tokens
                    _usage_sink["output_tokens"] = final.usage.output_tokens
                except Exception:
                    pass
    except Exception as e:
        logger.exception("Bulk triage stream failed: %s", e)
        yield _STREAM_ERROR_TOKEN


def stream_whatif(
    scenario: dict[str, Any],
    supplier_from: dict[str, Any],
    supplier_to: dict[str, Any] | None,
    constraints: list[dict],
    _usage_sink: dict | None = None,
) -> Iterator[str]:
    """Stream Claude's analysis of a what-if volume shift scenario."""
    client = _get_client()

    prompt = f"""You are analyzing a supply chain what-if scenario.

Scenario:
{json.dumps(scenario, indent=2)}

Source supplier (shifting volume away from):
{json.dumps(supplier_from, indent=2)}

Target supplier (shifting volume to):
{json.dumps(supplier_to or {}, indent=2) if supplier_to else "No specific target — recommend the best available option."}

Active business constraints:
{json.dumps(constraints[:10], indent=2)}

Analyze in plain prose (no markdown headers, no emojis):
1. Feasibility — does the shift violate any constraint? Name them explicitly if so.
2. Cost impact — estimated cost change based on order values and supplier pricing patterns.
3. Risk delta — net change in delivery risk (trust score, delay rate, concentration).
4. Recommendation — proceed, pause, or reject? Under what conditions?
5. Execution caveats — what must be in place for this shift to succeed.

Be specific. Do not hedge without data."""

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text
            if _usage_sink is not None:
                try:
                    final = stream.get_final_message()
                    _usage_sink["input_tokens"] = final.usage.input_tokens
                    _usage_sink["output_tokens"] = final.usage.output_tokens
                except Exception:
                    pass
    except Exception as e:
        logger.exception("What-if stream failed: %s", e)
        yield _STREAM_ERROR_TOKEN


# ── Multi-Model AI with Quality Scoring ──────────────────────────────────────


def _call_claude(prompt: str, system: str, max_tokens: int = 1024) -> tuple[str, float]:
    """
    Call Claude (primary model). Returns (response_text, latency_ms).
    """
    start = time.monotonic()
    try:
        client = _get_client()
        resp = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        latency = (time.monotonic() - start) * 1000
        text_blocks = [b for b in resp.content if getattr(b, "type", None) == "text"]
        if not text_blocks:
            raise ValueError("Claude returned no text content block")
        return text_blocks[0].text, latency
    except Exception:
        raise


def _call_openai_fallback(prompt: str, system: str, max_tokens: int = 1024) -> tuple[str, float]:
    """
    GPT-4o fallback when Claude is unavailable or quality is low.
    Returns ("", 0.0) if OpenAI not configured.
    """
    import os
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return "", 0.0

    start = time.monotonic()
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        latency = (time.monotonic() - start) * 1000
        return resp.choices[0].message.content or "", latency
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        logger.warning("OpenAI fallback failed: %s", e)
        return "", latency


def _score_response_quality(response: str, context: dict) -> float:
    """
    Score AI response quality on 0.0–1.0 scale.
    Heuristics: length, action keywords, specificity, structure.
    """
    if not response or len(response) < 50:
        return 0.0

    score = 0.0

    # Length signal (200-2000 chars is ideal)
    l = len(response)
    if 200 <= l <= 2000:
        score += 0.3
    elif l > 100:
        score += 0.15

    # Action keywords signal
    action_words = ["recommend", "action", "priority", "immediate", "route", "supplier",
                    "delay", "risk", "mitigate", "escalate", "alternative"]
    hits = sum(1 for w in action_words if w.lower() in response.lower())
    score += min(hits * 0.05, 0.3)

    # Structure signal (numbered lists, bullet points)
    if any(c in response for c in ["1.", "2.", "•", "-", "*"]):
        score += 0.2

    # Specificity: contains numbers/percentages
    import re
    if re.search(r"\d+(\.\d+)?%?", response):
        score += 0.2

    return min(round(score, 3), 1.0)


def analyze_with_quality_scoring(
    prompt: str,
    system: str,
    deviation_id: str = "",
    max_tokens: int = 1024,
) -> dict:
    """
    Multi-model AI call with quality scoring and GPT-4o fallback.

    Returns:
        {
            "response": str,
            "model_used": str,
            "quality_score": float,
            "latency_ms": float,
            "fallback_used": bool,
        }
    """
    result = {
        "response": "",
        "model_used": MODEL,
        "quality_score": 0.0,
        "latency_ms": 0.0,
        "fallback_used": False,
    }

    # Try Claude first
    try:
        text, latency = _call_claude(prompt, system, max_tokens)
        quality = _score_response_quality(text, {"deviation_id": deviation_id})
        result.update({
            "response": text,
            "model_used": MODEL,
            "quality_score": quality,
            "latency_ms": round(latency, 1),
        })

        # If quality is low (< 0.4), try OpenAI fallback
        if quality < 0.4:
            fallback_text, fallback_latency = _call_openai_fallback(prompt, system, max_tokens)
            if fallback_text:
                fallback_quality = _score_response_quality(fallback_text, {"deviation_id": deviation_id})
                if fallback_quality > quality:
                    result.update({
                        "response": fallback_text,
                        "model_used": "gpt-4o",
                        "quality_score": fallback_quality,
                        "latency_ms": round(fallback_latency, 1),
                        "fallback_used": True,
                    })

        return result

    except Exception as e:
        logger.warning("Claude call failed: %s — trying GPT-4o fallback", e)
        fallback_text, fallback_latency = _call_openai_fallback(prompt, system, max_tokens)
        if fallback_text:
            result.update({
                "response": fallback_text,
                "model_used": "gpt-4o",
                "quality_score": _score_response_quality(fallback_text, {}),
                "latency_ms": round(fallback_latency, 1),
                "fallback_used": True,
            })
        return result
