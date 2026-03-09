"use client";

import { useEffect, useRef, useState } from "react";
import { fetchSuppliers, analyzeWhatIfStream, StreamUsage } from "@/lib/api";
import { Play, Square } from "lucide-react";

type Supplier = { supplier_id: string; name: string; region: string; trust_score: number };

export function WhatIfSimulator() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [fromId, setFromId] = useState("");
  const [toId, setToId] = useState("");
  const [shift, setShift] = useState(30);
  const [product, setProduct] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<StreamUsage | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchSuppliers({ limit: 100 })
      .then((s) => {
        setSuppliers(s);
        if (s.length >= 2) {
          setFromId(s[0].supplier_id);
          setToId(s[1].supplier_id);
        }
      })
      .catch(() => {});
  }, []);

  const run = async () => {
    if (!fromId || !toId || fromId === toId) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setStreaming(true);
    setText("");
    setError(null);
    setUsage(null);
    try {
      await analyzeWhatIfStream(
        {
          supplier_id: fromId,
          volume_shift_pct: shift,
          target_supplier_id: toId,
          product: product.trim() || undefined,
        },
        (token) => setText((t) => t + token),
        { signal: ctrl.signal, onDone: (u) => setUsage(u) }
      );
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError((e as Error).message);
    } finally {
      setStreaming(false);
    }
  };

  const cancel = () => {
    abortRef.current?.abort();
    setStreaming(false);
  };

  const fromSupplier = suppliers.find((s) => s.supplier_id === fromId);
  const toSupplier = suppliers.find((s) => s.supplier_id === toId);

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border">
        <p className="text-sm font-semibold text-foreground">What-If Simulator</p>
        <p className="text-[11px] text-mutedForeground mt-0.5">
          Model the impact of shifting volume between suppliers — cost, risk, and constraint analysis via Claude
        </p>
      </div>

      {/* Controls */}
      <div className="px-5 py-4 border-b border-border grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="space-y-1">
          <label className="text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground">
            From Supplier
          </label>
          <select
            value={fromId}
            onChange={(e) => setFromId(e.target.value)}
            className="w-full text-[12px] font-medium text-foreground rounded-lg px-3 py-1.5 bg-surfaceRaised border border-border focus:outline-none focus:ring-1 focus:ring-accent"
          >
            {suppliers.map((s) => (
              <option key={s.supplier_id} value={s.supplier_id}>{s.name}</option>
            ))}
          </select>
          {fromSupplier && (
            <p className="text-[10px] text-mutedForeground">
              Trust: {(fromSupplier.trust_score * 100).toFixed(0)}% · {fromSupplier.region}
            </p>
          )}
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground">
            To Supplier
          </label>
          <select
            value={toId}
            onChange={(e) => setToId(e.target.value)}
            className="w-full text-[12px] font-medium text-foreground rounded-lg px-3 py-1.5 bg-surfaceRaised border border-border focus:outline-none focus:ring-1 focus:ring-accent"
          >
            {suppliers
              .filter((s) => s.supplier_id !== fromId)
              .map((s) => (
                <option key={s.supplier_id} value={s.supplier_id}>{s.name}</option>
              ))}
          </select>
          {toSupplier && (
            <p className="text-[10px] text-mutedForeground">
              Trust: {(toSupplier.trust_score * 100).toFixed(0)}% · {toSupplier.region}
            </p>
          )}
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground">
            Volume Shift — {shift}%
          </label>
          <input
            type="range"
            min={5}
            max={100}
            step={5}
            value={shift}
            onChange={(e) => setShift(Number(e.target.value))}
            className="w-full accent-accent"
          />
          <div className="flex justify-between text-[10px] text-mutedForeground">
            <span>5%</span><span>100%</span>
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground">
            Product (optional)
          </label>
          <input
            type="text"
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            placeholder="e.g. Electronics"
            className="w-full text-[12px] text-foreground rounded-lg px-3 py-1.5 bg-surfaceRaised border border-border focus:outline-none focus:ring-1 focus:ring-accent placeholder:text-mutedForeground"
          />
        </div>
      </div>

      {/* Action bar */}
      <div className="px-5 py-3 border-b border-border flex items-center gap-3">
        {!streaming ? (
          <button
            type="button"
            onClick={run}
            disabled={!fromId || !toId || fromId === toId}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-white text-xs font-medium transition-colors disabled:opacity-40"
            style={{ background: "#0070F3" }}
          >
            <Play className="h-3.5 w-3.5" />
            Run Scenario
          </button>
        ) : (
          <button
            type="button"
            onClick={cancel}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium border border-border hover:bg-surfaceRaised transition-colors"
          >
            <Square className="h-3.5 w-3.5" />
            Cancel
          </button>
        )}
        {usage && (
          <span className="text-[10px] text-mutedForeground px-2 py-0.5 rounded bg-surfaceRaised border border-border">
            {(usage.input_tokens ?? 0) + (usage.output_tokens ?? 0)}t
            {usage.analysis_time_ms ? ` · ${(usage.analysis_time_ms / 1000).toFixed(1)}s` : ""}
          </span>
        )}
      </div>

      {/* Output */}
      <div className="px-5 py-5 min-h-[180px]">
        {error && (
          <div
            className="p-3 rounded-lg text-xs text-destructive"
            style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)" }}
          >
            {error}
          </div>
        )}
        {!text && !error && !streaming && (
          <p className="text-xs text-mutedForeground text-center mt-10">
            Configure suppliers and volume shift, then run the scenario to get Claude&apos;s analysis.
          </p>
        )}
        {(text || streaming) && (
          <div className="rounded-lg p-4 bg-surfaceRaised border border-border">
            <p className="whitespace-pre-wrap font-sans text-[13px] leading-relaxed text-foreground">
              {text}
              {streaming && (
                <span className="inline-block w-1.5 h-[14px] ml-0.5 bg-accent animate-pulse align-middle" aria-hidden />
              )}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
