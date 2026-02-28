"use client";

import { useEffect, useRef, useState } from "react";
import { fetchNetworkGraph } from "@/lib/api";

type Node = {
  id: string;
  label: string;
  type: string;
  products?: string[];
};

type Edge = {
  source: string;
  target: string;
  label?: string;
};

type Graph = {
  nodes: Node[];
  edges: Edge[];
  stats?: { plant_count: number; port_count: number; edge_count: number };
};

const NODE_COLORS: Record<string, string> = {
  plant: "#6366f1",
  port: "#f59e0b",
  supplier: "#22c55e",
};

const NODE_R = 10;
const WIDTH = 800;
const HEIGHT = 340;

function layoutNodes(nodes: Node[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const plants = nodes.filter((n) => n.type === "plant");
  const ports = nodes.filter((n) => n.type === "port");

  const colX = (col: number, total: number) =>
    Math.round((WIDTH / (total + 1)) * (col + 1));

  plants.forEach((n, i) => {
    positions.set(n.id, { x: colX(i, plants.length), y: 90 });
  });
  ports.forEach((n, i) => {
    positions.set(n.id, { x: colX(i, ports.length), y: 250 });
  });

  return positions;
}

export function SupplyChainGraph() {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [tooltip, setTooltip] = useState<{ node: Node; x: number; y: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    fetchNetworkGraph()
      .then(setGraph)
      .catch(() => setGraph(null));
  }, []);

  if (!graph) {
    return (
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <p className="text-sm font-medium text-foreground">Supply Chain Network</p>
        </div>
        <p className="text-xs text-mutedForeground px-4 py-6">Loading network data…</p>
      </div>
    );
  }

  if (graph.nodes.length === 0) {
    return (
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <p className="text-sm font-medium text-foreground">Supply Chain Network</p>
        </div>
        <p className="text-xs text-mutedForeground px-4 py-6">
          No network data. Run the pipeline to load PlantPorts.csv.
        </p>
      </div>
    );
  }

  const positions = layoutNodes(graph.nodes);

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <p className="text-sm font-medium text-foreground">Supply Chain Network</p>
        <p className="text-xs text-mutedForeground">
          {graph.stats
            ? `${graph.stats.plant_count} plants · ${graph.stats.port_count} ports · ${graph.stats.edge_count} routes`
            : "Plant → Port topology"}
        </p>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 px-4 pt-3 pb-1">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: color }}
            />
            <span className="text-xs text-mutedForeground capitalize">{type}</span>
          </div>
        ))}
      </div>

      <div className="relative overflow-x-auto px-4 pb-4">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="w-full"
          style={{ height: HEIGHT }}
          onMouseLeave={() => setTooltip(null)}
        >
          {/* Edges */}
          {graph.edges.map((e, i) => {
            const src = positions.get(e.source);
            const tgt = positions.get(e.target);
            if (!src || !tgt) return null;
            return (
              <line
                key={i}
                x1={src.x}
                y1={src.y}
                x2={tgt.x}
                y2={tgt.y}
                stroke="#27272a"
                strokeWidth={1.5}
              />
            );
          })}

          {/* Nodes */}
          {graph.nodes.map((n) => {
            const pos = positions.get(n.id);
            if (!pos) return null;
            return (
              <g
                key={n.id}
                transform={`translate(${pos.x},${pos.y})`}
                className="cursor-pointer"
                onMouseEnter={(e) => {
                  const svgRect = svgRef.current?.getBoundingClientRect();
                  if (svgRect) {
                    setTooltip({
                      node: n,
                      x: e.clientX - svgRect.left,
                      y: e.clientY - svgRect.top,
                    });
                  }
                }}
              >
                <circle
                  r={NODE_R}
                  fill={NODE_COLORS[n.type] ?? "#71717a"}
                  opacity={0.9}
                />
                <text
                  y={NODE_R + 12}
                  textAnchor="middle"
                  fill="#a1a1aa"
                  fontSize={9}
                  fontFamily="monospace"
                >
                  {n.label.length > 10 ? n.label.slice(0, 10) + "…" : n.label}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="absolute bg-card border border-border rounded px-3 py-2 text-xs pointer-events-none z-10"
            style={{ left: tooltip.x + 12, top: tooltip.y - 12 }}
          >
            <p className="font-medium text-foreground">{tooltip.node.label}</p>
            <p className="text-mutedForeground capitalize mt-0.5">{tooltip.node.type}</p>
            {tooltip.node.products && tooltip.node.products.length > 0 && (
              <p className="text-mutedForeground mt-1">
                Products: {tooltip.node.products.slice(0, 3).join(", ")}
                {tooltip.node.products.length > 3 ? ` +${tooltip.node.products.length - 3}` : ""}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
