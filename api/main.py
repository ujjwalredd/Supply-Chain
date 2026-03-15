"""
Supply Chain AI Operating System — FastAPI backend.

REST API + WebSocket for real-time dashboard updates.
Redis pub/sub powers multi-worker broadcast (falls back to in-process set).
"""

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.auth import APIKeyMiddleware
from api.database import init_db
from api.routers import actions, ai, alerts, data, events, forecasts, lineage, ml, network, orders, ontology, query, streaming, suppliers
from api.telemetry import setup_tracing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_CHANNEL = "deviations"

# Allowed origins — read from env, comma-separated. Do NOT use wildcard * in production.
_CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001")
CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]

# Bug 23: validate CORS_ORIGINS — warn on wildcard, reject in production
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
if "*" in CORS_ORIGINS:
    if _ENVIRONMENT == "production":
        raise RuntimeError(
            "CORS wildcard '*' is not allowed in production. "
            "Set CORS_ORIGINS to explicit origins."
        )
    else:
        logger.warning(
            "CORS_ORIGINS contains wildcard '*' — this is insecure and must not be used in production."
        )

# Trusted hosts — comma-separated list from env (e.g. "example.com,api.example.com")
_ALLOWED_HOSTS_RAW = os.getenv("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _ALLOWED_HOSTS_RAW.split(",") if h.strip()]

# NOTE: Rate limiting — install `fastapi-limiter` and configure SlowAPI or
# fastapi-limiter with Redis to add per-IP or per-API-key rate limits.
# Example: @limiter.limit("60/minute") on each route.

# In-process fallback subscriber set (used when Redis is unavailable)
_deviation_subscribers: set[WebSocket] = set()

# Redis async client and subscriber task (set during startup)
_redis_client = None
_subscriber_task: asyncio.Task | None = None


async def _get_async_redis():
    """Return async Redis client or None if unavailable."""
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
        return client
    except Exception as e:
        logger.warning("Redis unavailable, using in-process WebSocket broadcast: %s", e)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global _redis_client, _subscriber_task
    logger.info("Starting Supply Chain API...")
    await init_db()
    _redis_client = await _get_async_redis()
    if _redis_client:
        _subscriber_task = asyncio.create_task(_redis_subscriber_loop())
        logger.info("Redis pub/sub enabled on channel '%s'", REDIS_CHANNEL)
    yield
    if _subscriber_task:
        _subscriber_task.cancel()
        try:
            await _subscriber_task
        except asyncio.CancelledError:
            pass
    if _redis_client:
        await _redis_client.aclose()
    logger.info("Shutting down Supply Chain API...")


app = FastAPI(
    title="Supply Chain AI OS",
    description="AI-native supply chain control tower API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

class _RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach X-Request-ID to every request/response for tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


setup_tracing(app)

# Middleware is applied in reverse order (last-added = outermost).
# Desired request order: TrustedHost → CORS → APIKey → RequestID → handler
app.add_middleware(_RequestIDMiddleware)
app.add_middleware(APIKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "Accept"],
)
# Only enforce trusted host checking when ALLOWED_HOSTS is explicitly configured
if ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(data.router)
app.include_router(orders.router, prefix="/orders", tags=["orders"])
app.include_router(suppliers.router, prefix="/suppliers", tags=["suppliers"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])
app.include_router(ontology.router, prefix="/ontology", tags=["ontology"])
app.include_router(actions.router, prefix="/actions", tags=["actions"])
app.include_router(forecasts.router, prefix="/forecasts", tags=["forecasts"])
app.include_router(network.router, prefix="/network", tags=["network"])
app.include_router(query.router, prefix="/ai/query", tags=["ai"])
app.include_router(lineage.router)
app.include_router(ml.router, prefix="/ml", tags=["ml"])
app.include_router(streaming.router)
app.include_router(events.router)


async def _redis_subscriber_loop() -> None:
    """Subscribe to Redis channel and forward messages to WebSocket clients.
    Auto-restarts on error with exponential backoff (max 30 s).
    """
    if not _redis_client:
        return
    backoff = 1.0
    while True:
        pubsub = None
        try:
            pubsub = _redis_client.pubsub()
            await pubsub.subscribe(REDIS_CHANNEL)
            backoff = 1.0  # reset on successful connection
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await _broadcast_raw(message["data"])
        except asyncio.CancelledError:
            # Bug 11: always unsubscribe and close pubsub on exit
            if pubsub:
                try:
                    await pubsub.unsubscribe()
                    await pubsub.aclose()
                except Exception:
                    pass
            return
        except Exception as e:
            logger.warning("Redis subscriber loop error (retrying in %.0fs): %s", backoff, e)
            # Bug 11: release pubsub on error path too
            if pubsub:
                try:
                    await pubsub.unsubscribe()
                    await pubsub.aclose()
                except Exception:
                    pass
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


async def _broadcast_raw(payload: str) -> None:
    """Broadcast raw JSON string to all connected WebSocket clients."""
    disconnected = set()
    for ws in _deviation_subscribers:
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.add(ws)
    for ws in disconnected:
        _deviation_subscribers.discard(ws)


async def broadcast_deviation(deviation: dict) -> None:
    """Broadcast a deviation dict. Uses Redis if available, else in-process."""
    payload = json.dumps({"type": "deviation", "data": deviation})
    if _redis_client:
        try:
            await _redis_client.publish(REDIS_CHANNEL, payload)
            return
        except Exception as e:
            logger.warning("Redis publish failed, falling back to in-process: %s", e)
    await _broadcast_raw(payload)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time deviation feed and KPI updates."""
    await websocket.accept()
    _deviation_subscribers.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                logger.debug("WebSocket: received non-JSON message, ignoring")
                continue
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    except Exception:
        # Bug 4: catch all disconnect-related errors so cleanup always runs
        pass
    finally:
        # Bug 4: always remove from subscriber set to prevent accumulation of dead sockets
        _deviation_subscribers.discard(websocket)
        logger.info("WebSocket client disconnected")


def _log_broadcast_error(task: asyncio.Task) -> None:
    """Log unhandled exceptions from the fire-and-forget broadcast task."""
    if not task.cancelled() and task.exception():
        logger.error("WebSocket broadcast failed: %s", task.exception())


def publish_deviation(deviation: dict) -> None:
    """Call from pipeline/consumer when new deviation detected. Triggers broadcast."""
    task = asyncio.create_task(broadcast_deviation(deviation))
    task.add_done_callback(_log_broadcast_error)


@app.get("/health")
async def health():
    """Dependency health check — reports db, redis, and websocket subscriber status."""
    from sqlalchemy import text
    from api.database import AsyncSessionLocal

    checks: dict[str, str] = {}

    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("SELECT 1"))
            checks["db"] = "ok"
        except Exception:
            # Bug 22: do not expose raw exception which may contain DB URL with credentials
            checks["db"] = "error: connection failed"

    if _redis_client:
        try:
            await _redis_client.ping()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"
    else:
        checks["redis"] = "unavailable"

    checks["ws_subscribers"] = str(len(_deviation_subscribers))
    sub_running = bool(_subscriber_task and not _subscriber_task.done())
    checks["redis_subscriber"] = "running" if sub_running else "stopped"

    overall = "ok" if checks["db"] == "ok" else "degraded"
    return {"status": overall, "service": "supply-chain-api", "checks": checks}


@app.get("/")
async def root():
    """Root: API info and links."""
    return {
        "message": "Supply Chain AI OS API",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "orders": "/orders",
            "suppliers": "/suppliers",
            "alerts": "/alerts",
            "ontology": "/ontology/constraints",
            "ai": "/ai/analyze",
            "actions": "/actions",
            "forecasts": "/forecasts",
            "network": "/network",
        },
    }
