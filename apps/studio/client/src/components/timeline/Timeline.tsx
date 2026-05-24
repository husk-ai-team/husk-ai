import { useMemo } from "react";

import { ParentSize } from "@visx/responsive";
import { scaleLinear } from "@visx/scale";

import { fmtDuration, fmtTokens, type Span } from "@/lib/api";

interface TimelineProps {
  spans: Span[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const ROW = 38;
const PADDING_TOP = 28;
const PADDING_BOTTOM = 16;
const LEFT_LABEL_WIDTH = 230;
const BAR_HEIGHT = 14;

export function Timeline({ spans, selectedId, onSelect }: TimelineProps) {
  if (spans.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-sm text-muted-foreground">
        <div className="text-center">
          <span className="inline-block size-3 animate-pulse rounded-full bg-accent/60 mb-2" />
          <p>Listening for spans…</p>
        </div>
      </div>
    );
  }

  const sorted = useMemo(
    () => [...spans].sort((a, b) => a.started_at - b.started_at),
    [spans],
  );

  const range = useMemo(() => {
    let minT = Infinity;
    let maxT = -Infinity;
    for (const s of sorted) {
      if (s.started_at) minT = Math.min(minT, s.started_at);
      const end = s.finished_at ?? s.started_at + 100;
      if (end) maxT = Math.max(maxT, end);
    }
    if (!isFinite(minT) || !isFinite(maxT) || maxT === minT) {
      return { minT: minT || 0, maxT: (minT || 0) + 1 };
    }
    return { minT, maxT };
  }, [sorted]);

  const totalDuration = range.maxT - range.minT;

  return (
    <div className="h-full overflow-y-auto px-1.5 py-2">
      <ParentSize>
        {({ width }) => {
          const barWidth = Math.max(width - LEFT_LABEL_WIDTH - 30, 80);
          const timeScale = scaleLinear({
            domain: [range.minT, range.maxT],
            range: [0, barWidth],
          });
          const height = PADDING_TOP + sorted.length * ROW + PADDING_BOTTOM;
          return (
            <svg width={width} height={height} className="block">
              {[0, 0.25, 0.5, 0.75, 1].map((p) => {
                const x = LEFT_LABEL_WIDTH + barWidth * p;
                const ms = totalDuration * p;
                return (
                  <g key={p}>
                    <line
                      x1={x}
                      y1={PADDING_TOP - 8}
                      x2={x}
                      y2={height - 6}
                      stroke="#30363D"
                      strokeWidth={1}
                      strokeDasharray="2 5"
                      opacity={0.5}
                    />
                    <text
                      x={x}
                      y={PADDING_TOP - 14}
                      textAnchor="middle"
                      className="fill-muted-foreground text-[10px]"
                    >
                      {p === 0 ? "0" : fmtDuration(Math.round(ms))}
                    </text>
                  </g>
                );
              })}
              {sorted.map((s, idx) => {
                const y = PADDING_TOP + idx * ROW;
                const x0 = LEFT_LABEL_WIDTH + timeScale(s.started_at);
                const x1 =
                  LEFT_LABEL_WIDTH + timeScale(s.finished_at ?? s.started_at + 50);
                const w = Math.max(x1 - x0, 4);
                const selected = s.id === selectedId;
                const fill = fillForKind(s.kind, s.status);
                return (
                  <g
                    key={s.id}
                    className="cursor-pointer"
                    onClick={() => onSelect(s.id)}
                  >
                    <rect
                      x={4}
                      y={y - 4}
                      width={width - 8}
                      height={ROW - 4}
                      rx={6}
                      ry={6}
                      className={
                        selected
                          ? "fill-secondary/40"
                          : "fill-transparent hover:fill-secondary/30"
                      }
                    />
                    {selected && (
                      <rect
                        x={4}
                        y={y - 4}
                        width={2.5}
                        height={ROW - 4}
                        rx={1.2}
                        ry={1.2}
                        fill="#FF6B35"
                      />
                    )}
                    <text
                      x={18}
                      y={y + ROW / 2 - 2}
                      className={`fill-foreground text-xs ${selected ? "font-semibold" : ""}`}
                    >
                      <tspan
                        fill={fill.bg}
                        style={{ letterSpacing: 0.5 }}
                      >
                        {kindGlyph(s.kind)}
                      </tspan>{" "}
                      <tspan>{truncate(s.name, 22)}</tspan>
                    </text>
                    <text
                      x={18}
                      y={y + ROW / 2 + 12}
                      className="fill-muted-foreground text-[10px]"
                    >
                      {s.model || s.kind.toUpperCase()}
                      {s.tokens_in || s.tokens_out
                        ? ` · ${fmtTokens(s.tokens_in, s.tokens_out)} tok`
                        : ""}
                    </text>
                    <rect
                      x={x0}
                      y={y + 8}
                      width={w}
                      height={BAR_HEIGHT}
                      rx={3.5}
                      ry={3.5}
                      fill={fill.bg}
                      fillOpacity={selected ? 1 : 0.85}
                      stroke={fill.stroke}
                      strokeWidth={selected ? 1.5 : 0.5}
                    />
                    {w > 50 && s.finished_at && (
                      <text
                        x={x0 + w + 7}
                        y={y + 8 + BAR_HEIGHT - 3}
                        className="fill-muted-foreground text-[10px]"
                      >
                        {fmtDuration(s.finished_at - s.started_at)}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
          );
        }}
      </ParentSize>
    </div>
  );
}

function fillForKind(kind: string, status: string): { bg: string; stroke: string } {
  if (status === "error") return { bg: "#F85149", stroke: "#FF8B85" };
  switch (kind) {
    case "llm":
      return { bg: "#FF6B35", stroke: "#FFA978" };
    case "tool":
      return { bg: "#5B9BD5", stroke: "#9DC7EC" };
    case "chain":
      return { bg: "#76C893", stroke: "#A5E0BD" };
    default:
      return { bg: "#8B949E", stroke: "#C0C7CE" };
  }
}

function kindGlyph(kind: string): string {
  switch (kind) {
    case "llm":
      return "◆";
    case "tool":
      return "▶";
    case "chain":
      return "●";
    default:
      return "·";
  }
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
