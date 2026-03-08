"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
const MAX_RETRIES = 12; // caps at ~30s delay; ~6 min total before giving up

export type WebSocketMessage = {
  type: string;
  data?: unknown;
};

export function useWebSocket(onMessage?: (msg: WebSocketMessage) => void) {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<NodeJS.Timeout | null>(null);
  const retriesRef = useRef(0);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (retriesRef.current >= MAX_RETRIES) return; // stop retrying after max attempts

    const ws = new WebSocket(`${WS_URL}/ws`);
    ws.onopen = () => {
      setConnected(true);
      retriesRef.current = 0;
    };
    ws.onclose = () => {
      setConnected(false);
      if (retriesRef.current < MAX_RETRIES) {
        const delay = Math.min(1000 * Math.pow(2, retriesRef.current), 30000);
        retriesRef.current += 1;
        reconnectRef.current = setTimeout(connect, delay);
      }
    };
    ws.onerror = () => {
      setConnected(false);
    };
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WebSocketMessage;
        setLastMessage(msg);
        onMessageRef.current?.(msg);
      } catch (e) {
        console.warn("[WS] Failed to parse message:", e);
      }
    };
    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };
  }, [connect]);

  const send = useCallback((data: Record<string, unknown>) => {
    wsRef.current?.send(JSON.stringify(data));
  }, []);

  const ping = useCallback(() => {
    send({ type: "ping" });
  }, [send]);

  return { connected, lastMessage, send, ping };
}
