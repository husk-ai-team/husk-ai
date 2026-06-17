import { useMemo } from "react";

import { fmtDuration, fmtTokens, type GraphNode, type RunGraph } from "@/lib/api";
import { AlertTriangle, Bug } from "lucide-react";

import { layoutGraph, NODE_H, NODE_W, type PositionedEdge } from "./graphLayout";

interface GraphViewProps {
  graph: RunGraph;
  selectedId: string | null;
  onSelect: (nodeId: string) => void;
}

function colorFor(status: string): { fill: string; stroke: string; text: string } {
  switch (status) {
    case "error":
      return { fill: "#2A1416", stroke: "#F85149", text: "#FF8B85" };
    case "success":
      return { fill: "#13211A", stroke: "#76C893", text: "#A5E0BD" };
    case "skipped":
      return { fill: "#1A1D23", stroke: "#3A424D", text: "#6B7280" };
    case "running":
      return { fill: "#241A12", stroke: "#FF6B35", text: "#FFA978" };
    default:
      return { fill: "#1A1D23", stroke: "#30363D", text: "#8B949E" };
  }
}

export function GraphView({ graph, selectedId, onSelect }: GraphViewProps) {
  const layout = useMemo(
    () => layoutGraph(graph.nodes, graph.edges),
    [graph.nodes, graph.edges],
  );

  const implicated = useMemo(() => {
    const set = new Set<string>();
    const r = graph.debug_report?.report;
    if (r) {
      if (r.failure_localization.node_id) set.add(r.failure_localization.node_id);
      for (const id of r.failure_localization.also_implicated) set.add(id);
    }
    return set;
  }, [graph.debug_report]);

  if (graph.nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted-foreground">
        No graph nodes for this run yet.
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-3">
      <svg width={layout.width} height={layout.height} className="block">
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#5A626D" />
          </marker>
        </defs>

        {layout.edges.map((e, i) => (
          <EdgePath key={`${e.from}-${e.to}-${i}`} e={e} />
        ))}

        {layout.nodes.map(({ node, x, y, w, h }) => {
          const c = colorFor(node.status);
          const selected = node.id === selectedId;
          const failure = node.is_failure_point;
          const flagged = implicated.has(node.id);
          return (
            <g
              key={node.id}
              transform={`translate(${x}, ${y})`}
              className="cursor-pointer"
              onClick={() => onSelect(node.id)}
            >
              {failure && (
                <rect
                  x={-3}
                  y={-3}
                  width={w + 6}
                  height={h + 6}
                  rx={11}
                  fill="none"
                  stroke="#F85149"
                  strokeWidth={2}
                  opacity={0.5}
                >
                  <animate
                    attributeName="opacity"
                    values="0.25;0.7;0.25"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                </rect>
              )}
              <rect
                width={w}
                height={h}
                rx={9}
                fill={c.fill}
                stroke={selected ? "#FF6B35" : c.stroke}
                strokeWidth={selected ? 2.5 : 1.4}
                strokeDasharray={node.status === "skipped" ? "5 4" : undefined}
              />
              <text x={14} y={26} className="text-[13px] font-semibold" fill={c.text}>
                {truncate(node.name, 22)}
              </text>
              <text x={14} y={46} className="text-[11px]" fill="#8B949E">
                {node.status}
                {node.tokens_in || node.tokens_out
                  ? ` · ${fmtTokens(node.tokens_in, node.tokens_out)} tok`
                  : ""}
              </text>
              <text x={14} y={61} className="text-[10px]" fill="#6B7280">
                {node.duration_ms != null ? fmtDuration(node.duration_ms) : "—"}
                {node.cost_usd ? ` · $${node.cost_usd.toFixed(4)}` : ""}
              </text>
              {failure && (
                <g transform={`translate(${w - 26}, 8)`}>
                  <AlertTriangle width={16} height={16} color="#F85149" />
                </g>
              )}
              {flagged && !failure && (
                <g transform={`translate(${w - 26}, 8)`}>
                  <Bug width={16} height={16} color="#FF6B35" />
                </g>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function EdgePath({ e }: { e: PositionedEdge }) {
  // A gentle vertical S-curve between layer rows.
  const midY = (e.y1 + e.y2) / 2;
  const d = `M ${e.x1} ${e.y1} C ${e.x1} ${midY}, ${e.x2} ${midY}, ${e.x2} ${e.y2}`;
  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke="#5A626D"
        strokeWidth={1.4}
        strokeDasharray={e.conditional ? "5 4" : undefined}
        markerEnd="url(#arrow)"
      />
      {e.conditional && e.label && (
        <text
          x={(e.x1 + e.x2) / 2 + 6}
          y={midY - 2}
          className="text-[10px]"
          fill="#8B949E"
        >
          {e.label}
        </text>
      )}
    </g>
  );
}

export function findNode(graph: RunGraph, id: string | null): GraphNode | null {
  if (!id) return null;
  return graph.nodes.find((n) => n.id === id) ?? null;
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
