"""
Agent communication layer — Redis pub/sub.
Channels:
  agent:alerts      — sub-agents publish anomalies (orchestrator subscribes)
  agent:corrections — orchestrator publishes fixes (agents subscribe)
  agent:heartbeats  — 30s keepalive pings
"""
import os
import json
import logging
import time
from typing import Optional, Callable
import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_client: Optional[redis.Redis] = None

def get_client() -> redis.Redis:
    global _client
    if _client is None:
        retries = 0
        while retries < 10:
            try:
                _client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)
                _client.ping()
                logger.info("Redis client connected")
                return _client
            except Exception as e:
                retries += 1
                wait = min(2 ** retries, 30)
                logger.warning(f"Redis connect attempt {retries} failed: {e}. Retrying in {wait}s")
                time.sleep(wait)
        raise RuntimeError("Could not connect to Redis after 10 retries")
    try:
        _client.ping()
    except:
        _client = None
        return get_client()
    return _client

def publish_alert(agent_id: str, severity: str, message: str, details: dict = None):
    try:
        payload = json.dumps({
            "agent_id": agent_id,
            "severity": severity,
            "message": message,
            "details": details or {},
            "timestamp": time.time()
        })
        get_client().publish("agent:alerts", payload)
        logger.info(f"[{agent_id}] Alert published: {severity} - {message}")
    except Exception as e:
        logger.error(f"Failed to publish alert: {e}")

def publish_heartbeat(agent_id: str, status: str):
    try:
        payload = json.dumps({"agent_id": agent_id, "status": status, "ts": time.time()})
        get_client().setex(f"agent:hb:{agent_id}", 120, payload)
    except Exception as e:
        logger.debug(f"Heartbeat Redis write failed: {e}")

def publish_correction(to_agent: str, message: str):
    try:
        payload = json.dumps({"to": to_agent, "message": message, "ts": time.time()})
        get_client().publish(f"agent:corrections:{to_agent}", payload)
    except Exception as e:
        logger.error(f"Failed to publish correction: {e}")

def get_all_agent_statuses() -> dict:
    try:
        client = get_client()
        keys = client.keys("agent:hb:*")
        result = {}
        for key in keys:
            agent_id = key.replace("agent:hb:", "")
            raw = client.get(key)
            if raw:
                result[agent_id] = json.loads(raw)
        return result
    except Exception as e:
        logger.error(f"Failed to get agent statuses: {e}")
        return {}
