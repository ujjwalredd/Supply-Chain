"""
Supply Chain AI Operating System — FastAPI backend.

REST API + WebSocket for real-time dashboard updates.
"""

import asyncio
import json
import logging
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

# In-memory broadcast for deviations (use Redis pub/sub in multi-worker prod)
_deviation_subscribers: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting Supply Chain API...")
    await init_db()
    yield
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
    allow_origins=["*"],  # Restrict in production
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


async def broadcast_deviation(deviation: dict) -> None:
    """Broadcast deviation to all connected WebSocket clients."""
    payload = json.dumps({"type": "deviation", "data": deviation})
    disconnected = set()
    for ws in _deviation_subscribers:
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.add(ws)
    for ws in disconnected:
        _deviation_subscribers.discard(ws)


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
