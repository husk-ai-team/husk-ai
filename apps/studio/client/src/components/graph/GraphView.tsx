import { useMemo } from "react";

import { fmtCost, fmtDuration, fmtTokens, type GraphNode, type RunGraph } from "@/lib/api";
import { AlertTriangle, Bug } from "lucide-react";

import { layoutGraph, type PositionedEdge } from "./graphLayout";

interface GraphViewProps {
  graph: RunGraph;
  selectedId: string | null;
  onSelect: (nodeId: string) => void;
}

// Status palette, kept in step with the Timeline's vocabulary and the theme
// tokens (emerald = success, destructive #F85149 = error, accent = running,
// muted = skipped). Dark tinted fills so the colored stroke reads as the signal.
const STATUS = {
  error: { fill: "#251513", stroke: "#F0564E", dot: "#F0564E", text: "#FFB3AD" },
  success: { fill: "#172017", stroke: "#4FB07E", dot: "#5FC08C", text: "#A4E0BC" },
  skipped: { fill: "#1B1814", stroke: "#3C362E", dot: "#6E665A", text: "#8A8276" },
  running: { fill: "#26190F", stroke: "#FF7A45", dot: "#FF7A45", text: "#FFB892" },
} as const;

function statusOf(s: string) {
  return STATUS[s as keyof typeof STATUS] ?? STATUS.skipped;
}

export function GraphView({ graph, selectedId, onSelect }: GraphViewProps) {
  const layout = useMemo(() => layoutGraph(graph.nodes, graph.edges), [graph.nodes, graph.edges]);

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
    <div className="flex h-full flex-col">
      {graph.failure && (
        <div className="flex items-center gap-2 border-b border-destructive/20 bg-destructive/[0.07] px-4 py-2 text-xs">
          <AlertTriangle className="size-3.5 shrink-0 text-destructive" />
          <span className="text-destructive">Failure at</span>
          <span className="font-mono font-semibold text-foreground">{graph.failure.node_id}</span>
          {graph.failure.message && (
            <span className="truncate text-muted-foreground">— {graph.failure.message}</span>
          )}
        </div>
      )}

      <div className="flex items-center gap-4 border-b border-border/30 px-4 py-2 text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
        <LegendDot color={STATUS.success.dot} label="success" />
        <LegendDot color={STATUS.error.dot} label="failed" />
        <LegendDot color={STATUS.skipped.dot} label="skipped" dashed />
        <LegendDot color={STATUS.running.dot} label="running" />
      </div>

      <div className="flex-1 overflow-auto p-4">
        <svg width={layout.width} height={layout.height} className="block">
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6.5"
              markerHeight="6.5"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#6E665A" />
            </marker>
          </defs>

          {layout.edges.map((e, i) => (
            <EdgePath key={`${e.from}-${e.to}-${i}`} e={e} />
          ))}

          {layout.nodes.map(({ node, x, y, w, h }) => {
            const c = statusOf(node.status);
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
                    x={-4}
                    y={-4}
                    width={w + 8}
                    height={h + 8}
                    rx={13}
                    fill="none"
                    stroke="#F85149"
                    strokeWidth={1.5}
                    opacity={0.55}
                  />
                )}
                <rect
                  width={w}
                  height={h}
                  rx={10}
                  fill={c.fill}
                  stroke={selected ? "#FF6B35" : c.stroke}
                  strokeWidth={selected ? 2.5 : 1.4}
                  strokeDasharray={node.status === "skipped" ? "5 4" : undefined}
                  opacity={node.status === "skipped" ? 0.85 : 1}
                />
                <circle cx={16} cy={18} r={4} fill={c.dot} />
                <text x={28} y={22} className="text-[13px] font-semibold" fill="#E6E6E6">
                  {truncate(node.name, 20)}
                </text>
                <text x={16} y={42} className="text-[11px]" fill={c.text}>
                  {node.status}
                  {node.tokens_in || node.tokens_out ? ` · ${fmtTokens(node.tokens_in, node.tokens_out)} tok` : ""}
                </text>
                <text x={16} y={58} className="text-[10px]" fill="#6E7681">
                  {node.duration_ms != null ? fmtDuration(node.duration_ms) : "—"}
                  {node.cost_usd ? ` · ${fmtCost(node.cost_usd)}` : ""}
                </text>
                {failure ? (
                  <AlertTriangle x={w - 26} y={9} width={15} height={15} color="#F85149" />
                ) : flagged ? (
                  <Bug x={w - 26} y={9} width={15} height={15} color="#FF6B35" />
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

function EdgePath({ e }: { e: PositionedEdge }) {
  const midY = (e.y1 + e.y2) / 2;
  const d = `M ${e.x1} ${e.y1} C ${e.x1} ${midY}, ${e.x2} ${midY}, ${e.x2} ${e.y2}`;
  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke="#464036"
        strokeWidth={1.5}
        strokeDasharray={e.conditional ? "5 4" : undefined}
        markerEnd="url(#arrow)"
      />
      {e.conditional && e.label && (
        <text x={(e.x1 + e.x2) / 2 + 6} y={midY - 2} className="text-[10px]" fill="#8B949E">
          {e.label}
        </text>
      )}
    </g>
  );
}

function LegendDot({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block size-2 rounded-full"
        style={dashed ? { border: `1.5px dashed ${color}` } : { background: color }}
      />
      {label}
    </span>
  );
}

export function findNode(graph: RunGraph, id: string | null): GraphNode | null {
  if (!id) return null;
  return graph.nodes.find((n) => n.id === id) ?? null;
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
