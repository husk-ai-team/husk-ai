import { useEffect, useState } from "react";
import { Link, useRoute } from "wouter";

import { Inspector } from "@/components/inspector/Inspector";
import { FrameworkBadge, StatusPill } from "@/components/StatusPill";
import { Timeline } from "@/components/timeline/Timeline";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import {
  fmtCost,
  fmtDuration,
  fmtTokens,
  getRun,
  getSpans,
  shortId,
  subscribeRun,
  type Run,
  type RunEvent,
  type Span,
} from "@/lib/api";
import {
  ArrowLeft,
  ArrowRight,
  GitCompare,
  PencilLine,
  Rewind,
  Wifi,
  WifiOff,
} from "lucide-react";

export default function RunDetail() {
  const [, params] = useRoute("/runs/:id");
  const runId = params?.id;

  const [run, setRun] = useState<Run | null>(null);
  const [spans, setSpans] = useState<Span[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    if (!runId) return;
    let alive = true;
    setRun(null);
    setSpans([]);
    setSelectedId(null);
    setError(null);

    Promise.all([getRun(runId), getSpans(runId)])
      .then(([r, s]) => {
        if (!alive) return;
        setRun(r);
        setSpans(s);
        if (s.length) setSelectedId(s[0].id);
      })
      .catch((e) => alive && setError(String(e)));

    const ws = subscribeRun(runId, (ev: RunEvent) => {
      if (!alive) return;
      if (ev.type === "span.replay" || ev.type === "span.created") {
        setSpans((prev) => mergeSpan(prev, ev.span));
        setSelectedId((sel) => sel ?? ev.span.id);
      }
    });
    ws.onopen = () => alive && setLive(true);
    ws.onclose = () => alive && setLive(false);

    return () => {
      alive = false;
      ws.close();
    };
  }, [runId]);

  if (error) {
    return (
      <section className="px-6 md:px-12 py-16 max-w-6xl mx-auto">
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      </section>
    );
  }

  const selected = spans.find((s) => s.id === selectedId) ?? null;
  const duration =
    run?.finished_at && run?.started_at ? run.finished_at - run.started_at : null;
  const totalTokens = (run?.total_tokens_in || 0) + (run?.total_tokens_out || 0);

  return (
    <section className="px-6 md:px-12 pt-12 pb-16 max-w-7xl mx-auto">
      <Link
        href="/runs"
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="size-3.5" />
        Runs
      </Link>

      <div className="mt-5 mb-6 flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-b border-border/30 pb-6">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-[0.18em] text-accent">
            Run detail
          </div>
          <h1 className="mt-2 font-mono text-2xl md:text-3xl font-bold tracking-tight">
            {runId ? shortId(runId, 20) : ""}
          </h1>
          {run && (
            <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-muted-foreground">
              <FrameworkBadge framework={run.framework} />
              <StatusPill status={run.status} />
              {duration && <Stat label="Duration" value={fmtDuration(duration)} />}
              {totalTokens > 0 && (
                <Stat
                  label="Tokens"
                  value={fmtTokens(run.total_tokens_in, run.total_tokens_out)}
                />
              )}
              {run.total_cost_usd ? (
                <Stat label="Cost" value={fmtCost(run.total_cost_usd)} highlight />
              ) : null}
              <Stat label="Spans" value={spans.length.toString()} />
            </div>
          )}
        </div>
        <LiveBadge on={live} />
      </div>

      <div className="h-[calc(100vh-260px)] min-h-[480px] overflow-hidden rounded-xl border border-border/30 bg-secondary/10">
        <ResizablePanelGroup direction="horizontal">
          <ResizablePanel defaultSize={42} minSize={28}>
            <Panel title={`Timeline · ${spans.length}`}>
              <Timeline
                spans={spans}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            </Panel>
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize={38} minSize={28}>
            <Panel title="Inspector">
              <Inspector span={selected} />
            </Panel>
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize={20} minSize={16}>
            <Actions span={selected} runId={runId ?? ""} />
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
    </section>
  );
}

function mergeSpan(prev: Span[], incoming: Span): Span[] {
  const idx = prev.findIndex((s) => s.id === incoming.id);
  if (idx === -1) {
    const next = [...prev, incoming];
    next.sort((a, b) => a.started_at - b.started_at);
    return next;
  }
  const copy = prev.slice();
  copy[idx] = { ...copy[idx], ...incoming };
  return copy;
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border/30 bg-secondary/30 px-4 py-2.5 text-[11px] uppercase tracking-[0.16em] text-muted-foreground font-semibold">
        {title}
      </div>
      <div className="flex-1 overflow-hidden">{children}</div>
    </div>
  );
}

function Stat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground/70">
        {label}
      </span>
      <span
        className={`tabular-nums ${highlight ? "text-accent" : "text-foreground"}`}
      >
        {value}
      </span>
    </span>
  );
}

function LiveBadge({ on }: { on: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${
        on
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
          : "border-border/40 bg-secondary/30 text-muted-foreground"
      }`}
    >
      {on ? <Wifi className="size-3" /> : <WifiOff className="size-3" />}
      {on ? "live" : "offline"}
    </span>
  );
}

function Actions({ span, runId }: { span: Span | null; runId: string }) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border/30 bg-secondary/30 px-4 py-2.5 text-[11px] uppercase tracking-[0.16em] text-muted-foreground font-semibold">
        Actions
      </div>
      <div className="flex flex-1 flex-col gap-2.5 p-4">
        <button
          type="button"
          disabled={!span}
          className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-border/50 bg-secondary/20 px-3 py-2 text-sm hover:border-accent/40 hover:text-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Rewind className="size-4" />
          Rewind to here
        </button>
        <Link
          href={span ? `/runs/${runId}/replay` : "#"}
          onClick={(e) => {
            if (!span) e.preventDefault();
          }}
          className={`inline-flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition-all ${
            span
              ? "bg-accent text-white hover:bg-accent/90"
              : "bg-accent/40 text-white cursor-not-allowed"
          }`}
        >
          <PencilLine className="size-4" />
          Modify and replay
          <ArrowRight className="size-4" />
        </Link>
        <button
          type="button"
          disabled={!span}
          className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-border/50 bg-secondary/20 px-3 py-2 text-sm hover:border-accent/40 hover:text-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <GitCompare className="size-4" />
          Compare runs
        </button>
        <p className="mt-auto pt-4 text-[11px] leading-relaxed text-muted-foreground">
          Modify & replay forks the LangGraph thread with your edited state and
          records the new run side-by-side.
        </p>
      </div>
    </div>
  );
}
