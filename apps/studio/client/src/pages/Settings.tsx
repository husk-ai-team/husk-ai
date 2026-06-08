import { useEffect, useState } from "react";
import { Link } from "wouter";
import { toast } from "sonner";

import { Tile } from "@/components/Tile";
import {
  fmtAgo,
  getIntegrationsStatus,
  type AllIntegrationStatus,
} from "@/lib/api";
import { useSession } from "@/lib/auth";
import {
  ArrowLeft,
  CheckCircle2,
  CircleDashed,
  Database,
  FolderOpen,
  Save,
  ShieldCheck,
} from "lucide-react";

const LG_PATH_KEY = "husk.langgraph_db_path";

const TABLES = [
  {
    name: "runs",
    purpose: "One row per agent invocation.",
    cols: [
      { name: "id", type: "string(26)", note: "ULID or trace_id-derived" },
      { name: "parent_run_id", type: "string?", note: "forked from this run" },
      { name: "framework", type: "string", note: "otel/openai, otel/langgraph…" },
      { name: "status", type: "string", note: "running | success | error" },
      { name: "started_at / finished_at", type: "bigint(ms)" },
      { name: "total_tokens_in / out", type: "int" },
      { name: "total_cost_usd", type: "float" },
    ],
  },
  {
    name: "spans",
    purpose: "Every step inside a run (LLM call, tool, agent decision).",
    cols: [
      { name: "id, run_id, parent_span_id", type: "string" },
      { name: "kind", type: "string", note: "llm | tool | chain" },
      { name: "input_inline / output_inline", type: "json" },
      { name: "tokens_in / out, cost_usd", type: "numeric" },
      { name: "provider, model", type: "string" },
      { name: "attrs", type: "json", note: "raw OTel + husk.graph_module, etc." },
    ],
  },
  {
    name: "snapshots",
    purpose: "Captured state at a checkpoint (used by replay).",
    cols: [
      { name: "id, run_id, span_id", type: "string" },
      { name: "state_ref", type: "string", note: "filesystem ref under ~/.husk/runs/" },
      { name: "rng_state, http_cassette_ref", type: "mixed" },
    ],
  },
  {
    name: "branches",
    purpose: "Parent runs ↔ forks link table.",
    cols: [
      { name: "id, parent_run_id, child_run_id", type: "string" },
      { name: "fork_span_id", type: "string" },
      { name: "override_payload", type: "json", note: "what changed" },
      { name: "label, notes", type: "text?" },
    ],
  },
  {
    name: "cursor_events",
    purpose: "IDE observability events from the Cursor / VS Code bridges.",
    cols: [
      { name: "id, hook, project", type: "string" },
      { name: "payload", type: "json", note: "raw IDE hook payload (file edits, terminal commands, stop)" },
      { name: "created_at", type: "bigint(ms)" },
    ],
  },
  {
    name: "http_cassettes",
    purpose: "Recorded HTTP responses for deterministic replay.",
    cols: [
      { name: "id, run_id, span_id", type: "string" },
      { name: "method, url, request_hash", type: "string" },
      { name: "response_status, response_body_ref", type: "mixed" },
      { name: "latency_ms", type: "int" },
    ],
  },
];

export default function Settings() {
  const { session } = useSession();
  const [status, setStatus] = useState<AllIntegrationStatus | null>(null);
  const [lgPath, setLgPath] = useState<string>(
    () => localStorage.getItem(LG_PATH_KEY) || "",
  );

  useEffect(() => {
    let alive = true;
    const tick = () =>
      getIntegrationsStatus()
        .then((s) => alive && setStatus(s))
        .catch(() => {});
    tick();
    const t = setInterval(tick, 3000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const saveLgPath = () => {
    localStorage.setItem(LG_PATH_KEY, lgPath);
    toast.success("LangGraph DB path saved");
  };

  return (
    <section className="px-6 md:px-12 pt-12 pb-20 max-w-6xl mx-auto">
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="size-3.5" />
        Dashboard
      </Link>

      <div className="mt-5 mb-10 border-b border-border/30 pb-6">
        <div className="text-xs uppercase tracking-[0.18em] text-accent">
          Configuration
        </div>
        <h1 className="mt-2 text-4xl md:text-5xl font-bold tracking-[-0.02em]">
          Settings
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Account, integrations, and what Husk stores under the hood.
        </p>
      </div>

      {/* Account */}
      <section className="mb-10">
        <H2 icon={<ShieldCheck className="size-3.5" />}>Account</H2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 md:gap-4">
          <Tile label="Email">
            <div className="text-base font-semibold break-all">
              {session?.email || "—"}
            </div>
          </Tile>
          <Tile label="Plan">
            <div className="text-base font-semibold capitalize">
              {session?.plan || "—"}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              Free while in beta
            </div>
          </Tile>
          <Tile label="Session age">
            <div className="text-base font-semibold">
              {session?.saved_at ? fmtAgo(session.saved_at) : "—"}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              Auto-refreshes from cloud
            </div>
          </Tile>
        </div>
      </section>

      {/* Integrations */}
      <section className="mb-10">
        <H2>Integrations</H2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 md:gap-4">
          <IntegrationCard
            name="OpenTelemetry GenAI"
            hint="Any framework, passive"
            s={status?.otel}
          />
          <IntegrationCard
            name="Cursor"
            hint="IDE observability — file edits, stop signals"
            s={status?.cursor}
          />
          <IntegrationCard
            name="LangGraph"
            hint="Time-travel replay"
            s={status?.langgraph}
          />
        </div>
      </section>

      {/* LangGraph DB path */}
      <section className="mb-10">
        <H2 icon={<FolderOpen className="size-3.5" />}>LangGraph</H2>
        <div className="rounded-xl border border-border/30 bg-secondary/10 p-5 md:p-6">
          <label className="block">
            <span className="block text-xs uppercase tracking-wide text-muted-foreground mb-1.5">
              Checkpointer DB path
            </span>
            <input
              type="text"
              value={lgPath}
              onChange={(e) => setLgPath(e.target.value)}
              placeholder="~/.husk/langgraph_demo.sqlite"
              className="w-full rounded-md border border-border/40 bg-background/40 px-3 py-2 font-mono text-sm focus:border-accent/60 focus:outline-none"
            />
          </label>
          <button
            type="button"
            onClick={saveLgPath}
            className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-accent text-white px-3 py-1.5 text-sm font-semibold hover:bg-accent/90"
          >
            <Save className="size-3.5" />
            Save
          </button>
        </div>
      </section>

      {/* Schema */}
      <section className="mb-10">
        <H2 icon={<Database className="size-3.5" />}>Database schema</H2>
        <p className="mb-4 text-sm text-muted-foreground">
          Husk persists everything in a single SQLite file at{" "}
          <code className="rounded bg-secondary/40 px-1.5 py-0.5 font-mono text-xs text-foreground">
            ~/.husk/traces.db
          </code>
          .
        </p>
        <div className="space-y-2.5">
          {TABLES.map((t) => (
            <details
              key={t.name}
              className="group overflow-hidden rounded-xl border border-border/30 bg-secondary/10 open:border-accent/40"
            >
              <summary className="flex cursor-pointer items-center justify-between gap-4 px-5 py-3.5 hover:bg-secondary/20 transition-colors">
                <div className="min-w-0">
                  <div className="font-mono text-sm font-semibold">{t.name}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {t.purpose}
                  </div>
                </div>
                <span className="rounded-md border border-border/40 bg-secondary/40 px-2 py-0.5 font-mono text-[10px] text-muted-foreground transition-transform group-open:rotate-180">
                  ▼
                </span>
              </summary>
              <div className="border-t border-border/30 bg-background/40 px-5 py-3">
                <ul className="divide-y divide-border/30 text-sm">
                  {t.cols.map((c) => (
                    <li
                      key={c.name}
                      className="flex flex-wrap items-baseline justify-between gap-2 py-1.5"
                    >
                      <span className="font-mono text-xs">{c.name}</span>
                      <span className="flex items-baseline gap-2">
                        <span className="rounded bg-secondary/30 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                          {c.type}
                        </span>
                        {c.note && (
                          <span className="text-xs text-muted-foreground">
                            {c.note}
                          </span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </details>
          ))}
        </div>
      </section>
    </section>
  );
}

function H2({
  icon,
  children,
}: {
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <h2 className="mb-3 flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
      {icon}
      {children}
    </h2>
  );
}

function IntegrationCard({
  name,
  hint,
  s,
}: {
  name: string;
  hint: string;
  s?: { connected: boolean; ever_connected: boolean; last_event_at: number | null };
}) {
  const live = !!s?.connected;
  const ever = !!s?.ever_connected;
  return (
    <div
      className={`rounded-xl border bg-secondary/10 p-4 transition-colors ${
        live ? "border-emerald-500/40" : "border-border/30"
      }`}
    >
      <div className="flex items-center gap-3">
        <span
          className={`flex size-9 items-center justify-center rounded-lg ${
            live
              ? "bg-emerald-500/15 text-emerald-300"
              : "bg-secondary/40 text-muted-foreground"
          }`}
        >
          {live ? (
            <CheckCircle2 className="size-5" />
          ) : (
            <CircleDashed className="size-5" />
          )}
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold">{name}</div>
          <div className="text-[11px] text-muted-foreground">{hint}</div>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-1.5 text-xs">
        <span
          className={`inline-block size-1.5 rounded-full ${
            live ? "bg-emerald-400 animate-pulse" : "bg-muted-foreground/40"
          }`}
        />
        <span className={live ? "text-emerald-300" : "text-muted-foreground"}>
          {live
            ? `live · ${fmtAgo(s?.last_event_at)}`
            : ever
              ? `idle · ${fmtAgo(s?.last_event_at)}`
              : "not connected yet"}
        </span>
      </div>
    </div>
  );
}
