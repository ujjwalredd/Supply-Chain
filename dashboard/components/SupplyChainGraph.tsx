"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchNetworkGraph } from "@/lib/api";

type Node = { id: string; label: string; type: string; products?: string[] };
type Edge = { source: string; target: string; label?: string };
type Graph = { nodes: Node[]; edges: Edge[]; stats?: { plant_count: number; port_count: number; edge_count: number } };
type Pos = { x: number; y: number };

const NODE_COLORS: Record<string, string> = {
  plant:    "#0070F3",
  port:     "#f59e0b",
  supplier: "#10b981",
};

const NODE_R = 12;
const WIDTH  = 800;
const HEIGHT = 360;

function layoutNodes(nodes: Node[]): Map<string, Pos> {
  const pos = new Map<string, Pos>();
  const plants   = nodes.filter((n) => n.type === "plant");
  const ports    = nodes.filter((n) => n.type === "port");
  const others   = nodes.filter((n) => n.type !== "plant" && n.type !== "port");
  const colX = (col: number, total: number) =>
    Math.round((WIDTH / (total + 1)) * (col + 1));
  plants.forEach((n, i)  => pos.set(n.id, { x: colX(i, plants.length),  y: 80  }));
  others.forEach((n, i)  => pos.set(n.id, { x: colX(i, others.length),  y: 180 }));
  ports.forEach((n, i)   => pos.set(n.id, { x: colX(i, ports.length),   y: 290 }));
  return pos;
}

export function SupplyChainGraph() {
  const [graph, setGraph]       = useState<Graph | null>(null);
  const [positions, setPositions] = useState<Map<string, Pos>>(new Map());
  const [tooltip, setTooltip]   = useState<{ node: Node; x: number; y: number } | null>(null);
  const [viewport, setViewport] = useState({ x: 0, y: 0, scale: 1 });
  const [isPanning, setIsPanning] = useState(false);

  const svgRef      = useRef<SVGSVGElement>(null);
  const dragNode    = useRef<{ id: string; sx: number; sy: number; ox: number; oy: number } | null>(null);
  const panState    = useRef<{ sx: number; sy: number; ox: number; oy: number } | null>(null);

  useEffect(() => {
    fetchNetworkGraph()
      .then((g) => { setGraph(g); setPositions(layoutNodes(g.nodes)); })
      .catch(() => setGraph(null));
  }, []);

  /* ── Node drag ────────────────────────────────────────────────── */
  const onNodeMouseDown = useCallback((e: React.MouseEvent, id: string, pos: Pos) => {
    e.stopPropagation();
    e.preventDefault();
    dragNode.current = { id, sx: e.clientX, sy: e.clientY, ox: pos.x, oy: pos.y };
  }, []);

  /* ── Pan ──────────────────────────────────────────────────────── */
  const onBgMouseDown = useCallback((e: React.MouseEvent) => {
    if (dragNode.current) return;
    setIsPanning(true);
    panState.current = { sx: e.clientX, sy: e.clientY, ox: viewport.x, oy: viewport.y };
  }, [viewport]);

  /* ── Mouse move ───────────────────────────────────────────────── */
  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (dragNode.current) {
      const { id, sx, sy, ox, oy } = dragNode.current;
      const dx = (e.clientX - sx) / viewport.scale;
      const dy = (e.clientY - sy) / viewport.scale;
      setPositions((prev) => { const n = new Map(prev); n.set(id, { x: ox + dx, y: oy + dy }); return n; });
      setTooltip(null);
    } else if (panState.current) {
      const { sx, sy, ox, oy } = panState.current;
      setViewport((v) => ({ ...v, x: ox + (e.clientX - sx), y: oy + (e.clientY - sy) }));
    }
  }, [viewport.scale]);

  const onMouseUp = useCallback(() => {
    dragNode.current = null;
    panState.current = null;
    setIsPanning(false);
  }, []);

  /* ── Wheel zoom ───────────────────────────────────────────────── */
  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const f = e.deltaY > 0 ? 0.9 : 1.1;
    setViewport((v) => ({ ...v, scale: Math.min(3, Math.max(0.25, v.scale * f)) }));
  }, []);

  const zoom  = (f: number) => setViewport((v) => ({ ...v, scale: Math.min(3, Math.max(0.25, v.scale * f)) }));
  const reset = () => setViewport({ x: 0, y: 0, scale: 1 });

  /* ── Tooltip on hover (skip when dragging) ────────────────────── */
  const onNodeEnter = useCallback((e: React.MouseEvent, node: Node) => {
    if (dragNode.current) return;
    const r = svgRef.current?.getBoundingClientRect();
    if (r) setTooltip({ node, x: e.clientX - r.left, y: e.clientY - r.top });
  }, []);
  const onNodeLeave = useCallback(() => { if (!dragNode.current) setTooltip(null); }, []);

  /* ── Empty states ─────────────────────────────────────────────── */
  if (!graph) {
    return (
      <div className="glass-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-semibold text-foreground">Supply Chain Network</p>
        </div>
        <p className="text-xs text-mutedForeground px-5 py-8">Loading network data…</p>
      </div>
    );
  }
  if (graph.nodes.length === 0) {
    return (
      <div className="glass-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <p className="text-sm font-semibold text-foreground">Supply Chain Network</p>
        </div>
        <p className="text-xs text-mutedForeground px-5 py-8">
          No network data. Run the pipeline to load PlantPorts.csv.
        </p>
      </div>
    );
  }

  const vt = `translate(${viewport.x},${viewport.y}) scale(${viewport.scale})`;

  return (
    <div className="glass-card card-hover overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-border flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-foreground">Supply Chain Network</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">
            {graph.stats
              ? `${graph.stats.plant_count} plants · ${graph.stats.port_count} ports · ${graph.stats.edge_count} routes`
              : "Drag nodes · scroll to zoom · drag background to pan"}
          </p>
        </div>
        {/* Zoom controls */}
        <div className="flex items-center gap-1">
          {[
            { label: "+", action: () => zoom(1.25) },
            { label: "−", action: () => zoom(0.8) },
            { label: "⟳", action: reset },
          ].map(({ label, action }) => (
            <button
              key={label}
              type="button"
              onClick={action}
              className="h-7 w-7 rounded-lg text-[13px] font-medium text-mutedForeground hover:text-foreground hover:bg-surfaceRaised border border-border transition-colors flex items-center justify-center"
            >
              {label}
            </button>
          ))}
          <span className="ml-2 text-[11px] text-mutedForeground tabular-nums min-w-[36px]">
            {Math.round(viewport.scale * 100)}%
          </span>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-5 px-5 pt-3 pb-1">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
            <span className="text-[11px] text-mutedForeground capitalize">{type}</span>
          </div>
        ))}
        <span className="ml-auto text-[10px] text-mutedForeground italic">Drag nodes · scroll to zoom</span>
      </div>

      {/* SVG canvas */}
      <div className="relative px-4 pb-4" style={{ height: HEIGHT }}>
        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          style={{ cursor: isPanning ? "grabbing" : "grab", display: "block" }}
          onMouseDown={onBgMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
          onWheel={onWheel}
        >
          <g transform={vt}>
            {/* Edges */}
            {graph.edges.map((e, i) => {
              const src = positions.get(e.source);
              const tgt = positions.get(e.target);
              if (!src || !tgt) return null;
              return (
                <g key={i}>
                  {/* Static base line */}
                  <line
                    x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y}
                    stroke="#e2e8f0" strokeWidth={1.5}
                  />
                  {/* Animated flow overlay */}
                  <line
                    x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y}
                    stroke="#0070F3" strokeWidth={1.5} opacity={0.35}
                    className="edge-flow"
                  />
                </g>
              );
            })}

            {/* Nodes */}
            {graph.nodes.map((n) => {
              const pos = positions.get(n.id);
              if (!pos) return null;
              const color = NODE_COLORS[n.type] ?? "#94a3b8";
              return (
                <g
                  key={n.id}
                  transform={`translate(${pos.x},${pos.y})`}
                  className="node-draggable"
                  onMouseDown={(e) => onNodeMouseDown(e, n.id, pos)}
                  onMouseEnter={(e) => onNodeEnter(e, n)}
                  onMouseLeave={onNodeLeave}
                >
                  {/* Glow ring */}
                  <circle r={NODE_R + 4} fill={color} opacity={0.06} />
                  {/* Main circle */}
                  <circle r={NODE_R} fill={color} opacity={0.9} />
                  {/* White inner dot */}
                  <circle r={4} fill="white" opacity={0.6} />
                  {/* Label */}
                  <text
                    y={NODE_R + 15}
                    textAnchor="middle"
                    fill="#64748b"
                    fontSize={9}
                    fontFamily="var(--font-geist-mono, monospace)"
                    pointerEvents="none"
                  >
                    {n.label.length > 10 ? n.label.slice(0, 10) + "…" : n.label}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {/* Tooltip */}
        {tooltip && !dragNode.current && (
          <div
            className="absolute bg-surface border border-border rounded-xl px-3 py-2.5 text-xs pointer-events-none z-10"
            style={{
              left: tooltip.x + 14,
              top: tooltip.y - 14,
              boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
              maxWidth: 200,
            }}
          >
            <p className="font-semibold text-foreground">{tooltip.node.label}</p>
            <p className="text-mutedForeground capitalize mt-0.5">{tooltip.node.type}</p>
            {tooltip.node.products && tooltip.node.products.length > 0 && (
              <p className="text-mutedForeground mt-1.5 leading-relaxed">
                {tooltip.node.products.slice(0, 3).join(", ")}
                {tooltip.node.products.length > 3 ? ` +${tooltip.node.products.length - 3} more` : ""}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
