import Editor from "@monaco-editor/react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Link, useLocation, useRoute } from "wouter";

import { Timeline } from "@/components/timeline/Timeline";
import {
  fmtDuration,
  getRun,
  getSpans,
  shortId,
  type Run,
  type Span,
} from "@/lib/api";
import {
  ArrowLeft,
  ArrowRight,
  ExternalLink,
  PencilLine,
  Play,
  Sparkles,
} from "lucide-react";

const FALLBACK_STATE = '{\n  "topic": "Rome"\n}';

export default function Replay() {
  const [, params] = useRoute("/runs/:id/replay");
  const [, setLocation] = useLocation();
  const runId = params?.id;

  const [run, setRun] = useState<Run | null>(null);
  const [spans, setSpans] = useState<Span[]>([]);
  const [stateJson, setStateJson] = useState(FALLBACK_STATE);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    thread_id?: string;
    state?: unknown;
    note?: string;
  } | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let alive = true;
    Promise.all([getRun(runId), getSpans(runId)])
      .then(([r, s]) => {
        if (!alive) return;
        setRun(r);
        setSpans(s);
        if (s.length) setSelectedId(s[0].id);
        const seed = pickInitialState(s);
        if (seed) setStateJson(seed);
      })
      .catch((e) => alive && setError(String(e)));
    return () => {
      alive = false;
    };
  }, [runId]);

  const runReplay = async () => {
    if (!runId) return;
    setError(null);
    setResult(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(stateJson);
    } catch (e) {
      const msg = `Invalid JSON: ${e}`;
      setError(msg);
      toast.error(msg);
      return;
    }
    setRunning(true);
    const loadingToast = toast.loading("Replaying graph…");
    try {
      const r = await fetch("/api/langgraph/replay", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          run_id: runId,
          span_id: selectedId,
          state_override: parsed,
        }),
      });
      if (!r.ok) {
        const txt = await r.text();
        throw new Error(`${r.status}: ${txt}`);
      }
      const j = await r.json();
      setResult(j);
      toast.success(
        j.thread_id
          ? `New run on thread ${shortId(j.thread_id, 10)}`
          : "Replay queued",
        { id: loadingToast },
      );
    } catch (e) {
      const msg = String(e);
      setError(msg);
      toast.error(msg, { id: loadingToast });
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="px-6 md:px-12 pt-12 pb-16 max-w-6xl mx-auto">
      <Link
        href={runId ? `/runs/${runId}` : "/runs"}
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="size-3.5" />
        Run {runId ? shortId(runId, 16) : ""}
      </Link>

      <div className="mt-5 mb-8">
        <div className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-accent">
          <Sparkles className="size-3.5" />
          Time-travel
        </div>
        <h1 className="mt-2 text-4xl md:text-5xl font-bold tracking-[-0.02em] flex items-baseline gap-3">
          <PencilLine className="hidden md:inline-block size-7 text-accent" />
          Modify <span className="text-accent">&amp;</span> replay
        </h1>
        {run && (
          <p className="mt-2 text-sm text-muted-foreground">
            Forking {run.framework} from the selected span. The original run is
            preserved.
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <section className="lg:col-span-2 overflow-hidden rounded-xl border border-border/30 bg-secondary/10">
          <div className="border-b border-border/30 bg-secondary/30 px-4 py-2.5 text-[11px] uppercase tracking-[0.16em] text-muted-foreground font-semibold flex items-center">
            <span>Original timeline</span>
            {run?.finished_at && run.started_at && (
              <span className="ml-3 font-mono text-[10px] normal-case tracking-normal">
                {fmtDuration(run.finished_at - run.started_at)}
              </span>
            )}
          </div>
          <div className="h-[55vh] min-h-[400px]">
            <Timeline
              spans={spans}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </div>
        </section>

        <section className="lg:col-span-3 overflow-hidden rounded-xl border border-border/30 bg-secondary/10">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/30 bg-secondary/30 px-4 py-2.5">
            <span className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground font-semibold">
              <Sparkles className="size-3.5 text-accent" />
              State override (JSON)
            </span>
            <button
              type="button"
              onClick={runReplay}
              disabled={running || !runId}
              className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-1.5 text-sm font-semibold text-white hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="size-3.5" />
              {running ? "Running…" : "Run from here"}
              {!running && <ArrowRight className="size-3.5" />}
            </button>
          </div>
          <div className="h-[55vh] min-h-[400px]">
            <Editor
              height="100%"
              defaultLanguage="json"
              value={stateJson}
              onChange={(v) => v != null && setStateJson(v)}
              theme="vs-dark"
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                tabSize: 2,
                wordWrap: "on",
                padding: { top: 12, bottom: 12 },
              }}
            />
          </div>
        </section>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 overflow-hidden rounded-xl border border-emerald-500/40 bg-emerald-500/5">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-emerald-500/20 bg-emerald-500/10 px-5 py-3">
            <div className="flex items-center gap-3">
              <span className="flex size-8 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-300">
                <Sparkles className="size-4" />
              </span>
              <div>
                <div className="text-sm font-semibold text-emerald-300">
                  Branch created.
                </div>
                <div className="font-mono text-[11px] text-muted-foreground">
                  {result.thread_id
                    ? `thread ${shortId(result.thread_id, 16)}`
                    : "new thread"}
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setLocation("/runs")}
              className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-accent/90"
            >
              See new run
              <ExternalLink className="size-3.5" />
            </button>
          </div>
          {result.state ? (
            <pre className="overflow-auto bg-background/40 p-4 font-mono text-xs leading-relaxed">
              {JSON.stringify(result.state, null, 2)}
            </pre>
          ) : (
            <p className="px-5 py-3 text-xs text-muted-foreground">
              {result.note ||
                "The new run will appear in /runs as the OTel exporter flushes."}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function pickInitialState(spans: Span[]): string | null {
  const root = spans.find(
    (s) => s.kind === "chain" && (s.attrs as any)?.["langgraph.thread_id"],
  );
  if (root) {
    const final = (root.attrs as any)?.["langgraph.final_state"];
    if (typeof final === "string") {
      try {
        return JSON.stringify(JSON.parse(final.replace(/'/g, '"')), null, 2);
      } catch {
        // fall through
      }
    }
  }
  const candidate = spans.find(
    (s) => s.input_inline && typeof s.input_inline === "object",
  );
  if (candidate?.input_inline && typeof candidate.input_inline === "object") {
    try {
      return JSON.stringify(candidate.input_inline, null, 2);
    } catch {
      return null;
    }
  }
  return null;
}
