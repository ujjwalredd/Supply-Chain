"""
API key authentication middleware.

Set API_KEYS env var to a comma-separated list of valid keys:
    API_KEYS=key-abc123,key-def456

Public paths (health, docs, metrics, WebSocket) are exempt.
All other routes require:
    Authorization: Bearer <api-key>
  or
    X-API-Key: <api-key>
"""

import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Paths that never require auth
_PUBLIC_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
    "/ws",
)

# Exact paths that are public (root only, not prefix)
_PUBLIC_EXACT = {"/"}



def _load_api_keys() -> set[str]:
    raw = os.getenv("API_KEYS", "")
    keys = {k.strip() for k in raw.split(",") if k.strip()}
    if not keys:
        logger.warning(
            "API_KEYS not set — authentication is DISABLED. "
            "Set API_KEYS=<key1>,<key2> in environment to enable."
        )
    return keys


_API_KEYS: set[str] = _load_api_keys()


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests without a valid API key (unless path is public)."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth if no keys are configured (dev/local mode)
        if not _API_KEYS:
            return await call_next(request)

        # Skip auth for public paths
        path = request.url.path
        if path in _PUBLIC_EXACT or any(path == p or path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        # Extract key from Authorization header or X-API-Key header
        api_key = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:].strip()
        if not api_key:
            api_key = request.headers.get("X-API-Key", "").strip()

        if not api_key or api_key not in _API_KEYS:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
