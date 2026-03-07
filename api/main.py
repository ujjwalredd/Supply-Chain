"""
Supply Chain AI Operating System — FastAPI backend.

REST API + WebSocket for real-time dashboard updates.
Redis pub/sub powers multi-worker broadcast (falls back to in-process set).
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.database import init_db
from api.routers import actions, ai, alerts, forecasts, network, orders, ontology, suppliers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_CHANNEL = "deviations"

# Allowed origins — restrict to frontend URL in production
_CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001")
CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]

# In-process fallback subscriber set (used when Redis is unavailable)
_deviation_subscribers: set[WebSocket] = set()

# Redis async client (set during startup)
_redis_client = None


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
    global _redis_client
    logger.info("Starting Supply Chain API...")
    await init_db()
    _redis_client = await _get_async_redis()
    if _redis_client:
        # Start Redis subscriber task for broadcasting to connected WebSocket clients
        asyncio.create_task(_redis_subscriber_loop())
        logger.info("Redis pub/sub enabled on channel '%s'", REDIS_CHANNEL)
    yield
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders.router, prefix="/orders", tags=["orders"])
app.include_router(suppliers.router, prefix="/suppliers", tags=["suppliers"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])
app.include_router(ontology.router, prefix="/ontology", tags=["ontology"])
app.include_router(actions.router, prefix="/actions", tags=["actions"])
app.include_router(forecasts.router, prefix="/forecasts", tags=["forecasts"])
app.include_router(network.router, prefix="/network", tags=["network"])


async def _redis_subscriber_loop() -> None:
    """Subscribe to Redis channel and forward messages to WebSocket clients."""
    if not _redis_client:
        return
    try:
        pubsub = _redis_client.pubsub()
        await pubsub.subscribe(REDIS_CHANNEL)
        async for message in pubsub.listen():
            if message["type"] == "message":
                await _broadcast_raw(message["data"])
    except Exception as e:
        logger.warning("Redis subscriber loop error: %s", e)


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
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        _deviation_subscribers.discard(websocket)
        logger.info("WebSocket client disconnected")


def publish_deviation(deviation: dict) -> None:
    """Call from pipeline/consumer when new deviation detected. Triggers broadcast."""
    asyncio.create_task(broadcast_deviation(deviation))


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "service": "supply-chain-api"}


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
