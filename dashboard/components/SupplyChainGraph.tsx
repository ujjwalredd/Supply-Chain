"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchNetworkGraph } from "@/lib/api";

type GraphNode = { id: string; label: string; type: string; products?: string[] };
type GraphEdge = { source: string; target: string; label?: string };
type Graph = { nodes: GraphNode[]; edges: GraphEdge[]; stats?: { plant_count: number; port_count: number; edge_count: number } };

// Neo4j-inspired color palette
const NODE_STYLES: Record<string, { fill: string; glow: string; ring: string; textColor: string }> = {
  plant:    { fill: "#4f46e5", glow: "rgba(79,70,229,0.45)", ring: "rgba(79,70,229,0.15)", textColor: "#a5b4fc" },
  port:     { fill: "#0ea5e9", glow: "rgba(14,165,233,0.45)", ring: "rgba(14,165,233,0.15)", textColor: "#7dd3fc" },
  supplier: { fill: "#10b981", glow: "rgba(16,185,129,0.45)", ring: "rgba(16,185,129,0.15)", textColor: "#6ee7b7" },
};
const EDGE_COLOR = "rgba(148,163,184,0.25)";
const EDGE_HIGHLIGHT = "rgba(148,163,184,0.6)";
const BG = "#0f172a";

const NODE_R = 14;
const LABEL_MAX = 9;
const WIDTH = 760;
const HEIGHT = 400;

// ── Force simulation ─────────────────────────────────────────────────────────
interface SimNode extends GraphNode { x: number; y: number; vx: number; vy: number }

function buildSim(nodes: GraphNode[]): SimNode[] {
  const cx = WIDTH / 2;
  const cy = HEIGHT / 2;
  return nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / nodes.length;
    const r = Math.min(cx, cy) * 0.65;
    return { ...n, x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle), vx: 0, vy: 0 };
  });
}

function tickForce(
  nodes: SimNode[],
  edges: GraphEdge[],
  alpha: number,
): SimNode[] {
  const K_REPEL = 4500;
  const K_SPRING = 0.04;
  const IDEAL = 110;
  const FRICTION = 0.82;
  const cx = WIDTH / 2;
  const cy = HEIGHT / 2;

  const next = nodes.map((n) => ({ ...n }));
  const idx = Object.fromEntries(next.map((n, i) => [n.id, i]));

  // Repulsion between all node pairs
  for (let i = 0; i < next.length; i++) {
    for (let j = i + 1; j < next.length; j++) {
      const dx = next[i].x - next[j].x;
      const dy = next[i].y - next[j].y;
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const f = (K_REPEL / (dist * dist)) * alpha;
      const fx = (dx / dist) * f;
      const fy = (dy / dist) * f;
      next[i].vx += fx;
      next[i].vy += fy;
      next[j].vx -= fx;
      next[j].vy -= fy;
    }
  }

  // Spring attraction along edges
  for (const e of edges) {
    const si = idx[e.source];
    const ti = idx[e.target];
    if (si === undefined || ti === undefined) continue;
    const dx = next[ti].x - next[si].x;
    const dy = next[ti].y - next[si].y;
    const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
    const f = K_SPRING * (dist - IDEAL) * alpha;
    const fx = (dx / dist) * f;
    const fy = (dy / dist) * f;
    next[si].vx += fx;
    next[si].vy += fy;
    next[ti].vx -= fx;
    next[ti].vy -= fy;
  }

  // Gravity toward center
  for (const n of next) {
    n.vx += (cx - n.x) * 0.004 * alpha;
    n.vy += (cy - n.y) * 0.004 * alpha;
  }

  // Integrate + friction + bounds
  for (const n of next) {
    n.vx *= FRICTION;
    n.vy *= FRICTION;
    n.x = Math.max(NODE_R + 2, Math.min(WIDTH - NODE_R - 2, n.x + n.vx));
    n.y = Math.max(NODE_R + 2, Math.min(HEIGHT - NODE_R - 2, n.y + n.vy));
  }
  return next;
}

export function SupplyChainGraph() {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const [hovered, setHovered] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{ node: SimNode; x: number; y: number } | null>(null);
  const [viewport, setViewport] = useState({ x: 0, y: 0, scale: 1 });
  const [running, setRunning] = useState(true);

  const svgRef = useRef<SVGSVGElement>(null);
  const dragNode = useRef<{ id: string; sx: number; sy: number; ox: number; oy: number } | null>(null);
  const panState = useRef<{ sx: number; sy: number; ox: number; oy: number } | null>(null);
  const alphaRef = useRef(1.0);
  const rafRef = useRef<number | null>(null);
  const simRef = useRef<SimNode[]>([]);

  useEffect(() => {
    fetchNetworkGraph()
      .then((g) => {
        setGraph(g);
        const s = buildSim(g.nodes);
        setSimNodes(s);
        simRef.current = s;
      })
      .catch(() => setGraph(null));
  }, []);

  // Force simulation loop
  useEffect(() => {
    if (!graph || !running) return;
    const animate = () => {
      alphaRef.current *= 0.994;
      if (alphaRef.current < 0.005) { setRunning(false); return; }
      if (dragNode.current) { rafRef.current = requestAnimationFrame(animate); return; }
      const next = tickForce(simRef.current, graph.edges, alphaRef.current);
      simRef.current = next;
      setSimNodes([...next]);
      rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [graph, running]);

  // Node drag
  const onNodeMouseDown = useCallback((e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    e.preventDefault();
    const node = simRef.current.find((n) => n.id === id);
    if (!node) return;
    dragNode.current = { id, sx: e.clientX, sy: e.clientY, ox: node.x, oy: node.y };
    alphaRef.current = 0.4;
    setRunning(true);
  }, []);

  const onBgMouseDown = useCallback((e: React.MouseEvent) => {
    if (dragNode.current) return;
    panState.current = { sx: e.clientX, sy: e.clientY, ox: viewport.x, oy: viewport.y };
  }, [viewport]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (dragNode.current) {
      const { id, sx, sy, ox, oy } = dragNode.current;
      const dx = (e.clientX - sx) / viewport.scale;
      const dy = (e.clientY - sy) / viewport.scale;
      simRef.current = simRef.current.map((n) =>
        n.id === id ? { ...n, x: ox + dx, y: oy + dy, vx: 0, vy: 0 } : n
      );
      setSimNodes([...simRef.current]);
      setTooltip(null);
    } else if (panState.current) {
      const { sx, sy, ox, oy } = panState.current;
      setViewport((v) => ({ ...v, x: ox + (e.clientX - sx), y: oy + (e.clientY - sy) }));
    }
  }, [viewport.scale]);

  const onMouseUp = useCallback(() => {
    dragNode.current = null;
    panState.current = null;
  }, []);

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const f = e.deltaY > 0 ? 0.9 : 1.1;
    setViewport((v) => ({ ...v, scale: Math.min(3, Math.max(0.2, v.scale * f)) }));
  }, []);

  const zoom = (f: number) => setViewport((v) => ({ ...v, scale: Math.min(3, Math.max(0.2, v.scale * f)) }));
  const reset = () => { setViewport({ x: 0, y: 0, scale: 1 }); alphaRef.current = 1.0; setRunning(true); };

  if (!graph) {
    return (
      <div className="glass-card overflow-hidden" style={{ background: BG }}>
        <div className="px-5 py-4 border-b border-white/10">
          <p className="text-sm font-semibold text-white">Supply Chain Network</p>
        </div>
        <p className="text-xs text-slate-400 px-5 py-8">Loading network…</p>
      </div>
    );
  }
  if (simNodes.length === 0) {
    return (
      <div className="glass-card overflow-hidden" style={{ background: BG }}>
        <div className="px-5 py-4 border-b border-white/10">
          <p className="text-sm font-semibold text-white">Supply Chain Network</p>
        </div>
        <p className="text-xs text-slate-400 px-5 py-8">No network data. Run pipeline to load PlantPorts.csv.</p>
      </div>
    );
  }

  const posMap = Object.fromEntries(simNodes.map((n) => [n.id, { x: n.x, y: n.y }]));
  const vt = `translate(${viewport.x},${viewport.y}) scale(${viewport.scale})`;

  // Highlight connected nodes when hovering
  const connectedIds = hovered
    ? new Set(graph.edges.flatMap((e) => e.source === hovered ? [e.target] : e.target === hovered ? [e.source] : []))
    : null;

  return (
    <div className="glass-card overflow-hidden" style={{ background: BG }}>
      {/* Header */}
      <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-white">Supply Chain Network</p>
          <p className="text-[11px] text-slate-400 mt-0.5">
            {graph.stats
              ? `${graph.stats.plant_count} plants · ${graph.stats.port_count} ports · ${graph.stats.edge_count} routes`
              : "Force-directed graph · drag nodes · scroll to zoom"}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {[
            { label: "+", action: () => zoom(1.25) },
            { label: "−", action: () => zoom(0.8) },
            { label: "⟳", action: reset },
          ].map(({ label, action }) => (
            <button
              key={label}
              type="button"
              onClick={action}
              className="h-7 w-7 rounded-lg text-[13px] font-medium text-slate-400 hover:text-white hover:bg-white/10 border border-white/10 transition-colors flex items-center justify-center"
            >
              {label}
            </button>
          ))}
          <span className="ml-1.5 text-[11px] text-slate-500 tabular-nums min-w-[36px]">
            {Math.round(viewport.scale * 100)}%
          </span>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-5 px-5 pt-3 pb-1">
        {Object.entries(NODE_STYLES).map(([type, style]) => (
          <div key={type} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: style.fill, boxShadow: `0 0 6px ${style.glow}` }} />
            <span className="text-[11px] text-slate-400 capitalize">{type}</span>
          </div>
        ))}
        <span className="ml-auto text-[10px] text-slate-600 italic">Force-directed · drag · scroll</span>
      </div>

      {/* SVG canvas */}
      <div className="relative px-2 pb-3" style={{ height: HEIGHT }}>
        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          style={{ cursor: "grab", display: "block" }}
          onMouseDown={onBgMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
          onWheel={onWheel}
        >
          <defs>
            {/* Arrow marker */}
            <marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
              <polygon points="0 0, 7 3.5, 0 7" fill="rgba(148,163,184,0.4)" />
            </marker>
            {/* Glow filters per type */}
            {Object.entries(NODE_STYLES).map(([type, style]) => (
              <filter key={type} id={`glow-${type}`} x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="3.5" result="blur" />
                <feFlood floodColor={style.fill} floodOpacity="0.6" result="color" />
                <feComposite in="color" in2="blur" operator="in" result="glow" />
                <feMerge><feMergeNode in="glow" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            ))}
          </defs>

          <g transform={vt}>
            {/* Edges */}
            {graph.edges.map((e, i) => {
              const src = posMap[e.source];
              const tgt = posMap[e.target];
              if (!src || !tgt) return null;
              const isHighlighted = hovered === e.source || hovered === e.target;
              return (
                <line
                  key={i}
                  x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y}
                  stroke={isHighlighted ? EDGE_HIGHLIGHT : EDGE_COLOR}
                  strokeWidth={isHighlighted ? 1.5 : 1}
                  markerEnd="url(#arrow)"
                  strokeLinecap="round"
                />
              );
            })}

            {/* Nodes */}
            {simNodes.map((n) => {
              const style = NODE_STYLES[n.type] ?? NODE_STYLES.plant;
              const isHovered = hovered === n.id;
              const isConnected = connectedIds?.has(n.id) ?? false;
              const dimmed = hovered !== null && !isHovered && !isConnected;
              const label = n.label.length > LABEL_MAX ? n.label.slice(0, LABEL_MAX) + "…" : n.label;
              return (
                <g
                  key={n.id}
                  transform={`translate(${n.x},${n.y})`}
                  style={{ cursor: "pointer", opacity: dimmed ? 0.25 : 1, transition: "opacity 0.15s" }}
                  onMouseDown={(e) => onNodeMouseDown(e, n.id)}
                  onMouseEnter={(e) => {
                    if (dragNode.current) return;
                    setHovered(n.id);
                    const r = svgRef.current?.getBoundingClientRect();
                    if (r) setTooltip({ node: n, x: e.clientX - r.left, y: e.clientY - r.top });
                  }}
                  onMouseLeave={() => { if (!dragNode.current) { setHovered(null); setTooltip(null); } }}
                >
                  {/* Outer glow ring */}
                  <circle r={NODE_R + 8} fill={style.ring} opacity={isHovered ? 1 : 0.5} />
                  {/* Glow effect */}
                  <circle r={NODE_R + 2} fill={style.glow} filter={isHovered ? `url(#glow-${n.type})` : undefined} opacity={isHovered ? 0.8 : 0.3} />
                  {/* Main node */}
                  <circle
                    r={NODE_R}
                    fill={style.fill}
                    stroke={isHovered ? "rgba(255,255,255,0.6)" : "rgba(255,255,255,0.15)"}
                    strokeWidth={isHovered ? 2 : 1}
                  />
                  {/* Inner highlight */}
                  <circle r={NODE_R * 0.45} fill="rgba(255,255,255,0.18)" />
                  {/* Label */}
                  <text
                    y={NODE_R + 14}
                    textAnchor="middle"
                    fill={isHovered ? style.textColor : "rgba(148,163,184,0.8)"}
                    fontSize={isHovered ? 10 : 9}
                    fontFamily="var(--font-geist-mono, monospace)"
                    fontWeight={isHovered ? "600" : "400"}
                    pointerEvents="none"
                  >
                    {label}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="absolute pointer-events-none z-20 rounded-xl px-3 py-2.5 text-xs"
            style={{
              left: tooltip.x + 16,
              top: tooltip.y - 16,
              background: "rgba(15,23,42,0.95)",
              border: "1px solid rgba(148,163,184,0.2)",
              boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
              maxWidth: 220,
            }}
          >
            <p className="font-semibold text-white">{tooltip.node.label}</p>
            <p className="capitalize mt-0.5" style={{ color: NODE_STYLES[tooltip.node.type]?.textColor ?? "#94a3b8" }}>
              {tooltip.node.type}
            </p>
            {tooltip.node.products && tooltip.node.products.length > 0 && (
              <div className="mt-1.5 text-slate-400 leading-relaxed">
                {tooltip.node.products.slice(0, 3).join(" · ")}
                {tooltip.node.products.length > 3 && (
                  <span className="text-slate-500"> +{tooltip.node.products.length - 3} more</span>
                )}
              </div>
            )}
            <p className="mt-1.5 text-slate-500">
              {graph.edges.filter((e) => e.source === tooltip.node.id || e.target === tooltip.node.id).length} connections
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
