const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export async function fetchOrders(params?: {
  limit?: number;
  offset?: number;
  status?: string;
  supplier_id?: string;
}) {
  const filtered = Object.fromEntries(
    Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== null && v !== "")
  ) as Record<string, string>;
  const search = new URLSearchParams(filtered);
  const res = await fetch(`${API_BASE}/orders?${search}`);
  if (!res.ok) throw new Error("Failed to fetch orders");
  return res.json();
}

export async function fetchOrder(id: string) {
  const res = await fetch(`${API_BASE}/orders/${id}`);
  if (!res.ok) throw new Error("Order not found");
  return res.json();
}

export async function fetchSuppliers(params?: {
  limit?: number;
  offset?: number;
  region?: string;
}) {
  const filtered = Object.fromEntries(
    Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== null && v !== "")
  ) as Record<string, string>;
  const search = new URLSearchParams(filtered);
  const res = await fetch(`${API_BASE}/suppliers?${search}`);
  if (!res.ok) throw new Error("Failed to fetch suppliers");
  return res.json();
}

export async function fetchSupplierRisk(limit = 20) {
  const res = await fetch(`${API_BASE}/suppliers/risk?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch supplier risk");
  return res.json();
}

export async function fetchAlerts(params?: {
  limit?: number;
  offset?: number;
  type?: string;
  severity?: string;
  executed?: boolean;
}) {
  const filtered = Object.fromEntries(
    Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== null)
  ) as Record<string, string>;
  const search = new URLSearchParams(filtered);
  const res = await fetch(`${API_BASE}/alerts?${search}`);
  if (!res.ok) throw new Error("Failed to fetch alerts");
  return res.json();
}

export async function dismissAlert(id: string) {
  const res = await fetch(`${API_BASE}/alerts/${id}/dismiss`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to dismiss alert");
  return res.json();
}

export type StreamUsage = {
  input_tokens?: number;
  output_tokens?: number;
  analysis_time_ms?: number;
};

export async function analyzeDeviationStream(
  body: {
    deviation_id: string;
    order_id?: string;
    deviation_type?: string;
    severity?: string;
    context?: Record<string, unknown>;
  },
  onToken: (token: string) => void,
  options?: {
    signal?: AbortSignal;
    onDone?: (usage: StreamUsage) => void;
  }
) {
  const res = await fetch(`${API_BASE}/ai/analyze/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: options?.signal,
  });
  if (!res.ok) {
    const text = await res.text();
    let message = `AI analysis failed (${res.status})`;
    try {
      const j = JSON.parse(text);
      if (j.detail) message = typeof j.detail === "string" ? j.detail : j.detail.join?.(" ") || message;
    } catch {
      if (text) message = text.slice(0, 200);
    }
    throw new Error(message);
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.token) onToken(data.token);
            if (data.done && options?.onDone) options.onDone(data.usage ?? {});
          } catch {}
        }
      }
    }
  } catch (err) {
    if ((err as Error).name === "AbortError") return; // cancelled — not an error
    throw err;
  }
}

export async function analyzeDeviation(body: {
  deviation_id: string;
  order_id?: string;
  deviation_type?: string;
  severity?: string;
}) {
  const res = await fetch(`${API_BASE}/ai/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("AI analysis failed");
  return res.json();
}

export async function fetchActions(params?: { limit?: number; status?: string }) {
  const filtered = Object.fromEntries(
    Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== null && v !== "")
  ) as Record<string, string>;
  const search = new URLSearchParams(filtered);
  const res = await fetch(`${API_BASE}/actions?${search}`);
  if (!res.ok) throw new Error("Failed to fetch actions");
  return res.json();
}

export async function fetchForecasts(params?: { limit?: number; min_risk_score?: number }) {
  const filtered = Object.fromEntries(
    Object.entries(params ?? {})
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => [k, String(v)])
  );
  const search = new URLSearchParams(filtered);
  const res = await fetch(`${API_BASE}/forecasts?${search}`);
  if (!res.ok) throw new Error("Failed to fetch forecasts");
  return res.json();
}

export async function fetchNetworkGraph() {
  const res = await fetch(`${API_BASE}/network`);
  if (!res.ok) throw new Error("Failed to fetch network graph");
  return res.json();
}

export { WS_URL };
