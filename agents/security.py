"""
Agent security utilities.

1. HMAC-signed corrections — only the orchestrator can issue valid corrections.
   - sign_correction(message)            → hex signature string
   - verify_correction(message, sig)     → bool

2. Prompt injection defense — sanitize external data before embedding in LLM prompts.
   - sanitize_for_prompt(text, ...)      → cleaned text
   - is_prompt_injection(text)           → (bool, description)

Set CORRECTION_HMAC_KEY env var to enable signing (32+ random bytes recommended).
When the key is absent, signing is disabled — all corrections are accepted (dev mode).
"""

import hashlib
import hmac
import logging
import os
import re
from typing import Tuple

logger = logging.getLogger(__name__)

# HMAC key — loaded once at import time.
# Empty string → signing disabled (dev/test mode, all corrections accepted).
_HMAC_KEY: bytes = os.getenv("CORRECTION_HMAC_KEY", "").encode("utf-8")


# ── HMAC signing ──────────────────────────────────────────────────────────────

def sign_correction(message: str) -> str:
    """Return HMAC-SHA256 hex digest for a correction message.

    Returns an empty string when CORRECTION_HMAC_KEY is not set (signing disabled).
    """
    if not _HMAC_KEY:
        return ""
    return hmac.new(_HMAC_KEY, message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_correction(message: str, signature: str) -> bool:
    """Verify HMAC-SHA256 signature for a correction message.

    Returns True when:
    - CORRECTION_HMAC_KEY is not set (signing disabled — accept all)
    - Signature matches the expected HMAC (constant-time comparison)

    Returns False when the key is set but the signature is missing or wrong.
    """
    if not _HMAC_KEY:
        return True  # signing disabled in dev/test mode
    if not signature:
        logger.warning(
            "verify_correction: unsigned correction received but CORRECTION_HMAC_KEY "
            "is set — rejecting"
        )
        return False
    expected = hmac.new(_HMAC_KEY, message.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Prompt injection defense ──────────────────────────────────────────────────

# Patterns that suggest an attempt to override agent instructions via external data.
# These are checked on any text sourced from outside the system (CSV values, API
# responses, Kafka messages, file names, etc.) before it is embedded in an LLM prompt.
_INJECTION_PATTERNS: list[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?"),
     "instruction override"),
    (re.compile(r"(?i)forget\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|context)"),
     "context wipe"),
    (re.compile(r"(?i)you\s+are\s+now\s+(?:a\s+)?(?:different|new|another|evil|unrestricted)"),
     "role override"),
    (re.compile(r"(?i)disregard\s+(?:your\s+)?(?:previous\s+|prior\s+)?(?:system\s+)?(?:instructions?|prompt)"),
     "system prompt override"),
    (re.compile(r"(?i)<\s*/?(?:system|instruction|prompt|override)\s*>"),
     "XML/HTML tag injection"),
    (re.compile(r"(?i)\[INST\]|\[\/INST\]|<\|im_start\|>|<\|im_end\|>"),
     "model-delimiter injection"),
    (re.compile(r"(?i)act\s+as\s+(?:if\s+you\s+are\s+)?(?:jailbroken|unrestricted|dan|evil)"),
     "jailbreak attempt"),
    (re.compile(r"(?i)print\s+(?:your\s+)?(?:system\s+prompt|instructions?|api\s+key)"),
     "secret extraction attempt"),
]


def is_prompt_injection(text: str) -> Tuple[bool, str]:
    """Check text for known prompt injection patterns.

    Returns (detected: bool, description: str).
    The description names the attack category when detected, or is empty string.
    """
    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True, label
    return False, ""


def sanitize_for_prompt(
    text: str,
    max_length: int = 4000,
    field_name: str = "input",
) -> str:
    """Sanitize external text before embedding it in an LLM prompt.

    Operations (in order):
    1. Coerce to string.
    2. Strip null bytes and non-printable control chars (keeps \\n, \\t, \\r).
    3. Truncate to max_length, appending a truncation marker.
    4. Log a WARNING if prompt injection patterns are detected.

    The caller is responsible for wrapping the returned text in XML data tags
    so the LLM treats it as data rather than instructions, e.g.:
        f"<supplier_note>{sanitize_for_prompt(note)}</supplier_note>"
    """
    if not isinstance(text, str):
        text = str(text)

    # Strip null bytes and dangerous control characters; keep \n \t \r
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    if len(text) > max_length:
        logger.warning(
            "sanitize_for_prompt: truncating %s from %d to %d chars",
            field_name, len(text), max_length,
        )
        text = text[:max_length] + "...[truncated]"

    detected, label = is_prompt_injection(text)
    if detected:
        logger.warning(
            "sanitize_for_prompt: potential prompt injection detected in %s (%s)",
            field_name, label,
        )

    return text
