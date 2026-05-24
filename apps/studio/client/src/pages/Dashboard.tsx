import { useEffect, useState } from "react";
import { Link } from "wouter";

import { CursorBanner } from "@/components/CursorBanner";
import { FrameworkDot, StatusPill } from "@/components/StatusPill";
import { StatNumber, Tile } from "@/components/Tile";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Coins,
  Cpu,
  PlugZap,
  Sparkles,
} from "lucide-react";

import {
  fmtAgo,
  fmtCost,
  fmtDuration,
  getDashboardSummary,
  getIntegrationsStatus,
  type AllIntegrationStatus,
  type DashboardSummary,
} from "@/lib/api";
import { useSession } from "@/lib/auth";

const POLL_MS = 4000;

export default function Dashboard() {
  const { session } = useSession();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [status, setStatus] = useState<AllIntegrationStatus | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () => {
      getDashboardSummary().then((d) => alive && setData(d)).catch(() => {});
      getIntegrationsStatus().then((s) => alive && setStatus(s)).catch(() => {});
    };
    tick();
    const t = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const firstName = (session?.name || session?.email || "").split(/[@\s]/)[0] || "you";
  const sparkline = data?.sparkline ?? [];

  return (
    <>
      <CursorBanner />
      <section className="px-6 md:px-12 pt-12 md:pt-16 pb-20 max-w-6xl mx-auto">
        {/* Hero */}
        <div className="mb-10 md:mb-14">
          <div className="text-xs uppercase tracking-[0.18em] text-accent">
            Welcome back
          </div>
          <h1 className="mt-2 text-4xl md:text-6xl font-bold tracking-[-0.02em]">
            Hi, <span className="text-accent">{firstName}</span>.
          </h1>
          <p className="mt-3 text-sm md:text-base text-muted-foreground max-w-2xl">
            Your local Husk. Real-time view of every run, every intervention,
            every cost.
          </p>
        </div>

        {/* Hero tiles */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6 mb-6">
          <Tile
            size="hero"
            icon={<Activity className="size-3.5" />}
            label="Total runs"
            rightLabel={
              data?.last_24h.runs ? (
                <span className="text-xs text-accent font-mono">
                  +{data.last_24h.runs} · 24h
                </span>
              ) : null
            }
          >
            <StatNumber
              size="hero"
              value={data?.totals.runs ?? "—"}
              sub={
                data
                  ? `${data.totals.spans} spans recorded`
                  : "loading…"
              }
            />
            <SparklineSvg values={sparkline} />
          </Tile>

          <Tile
            size="hero"
            icon={<Coins className="size-3.5" />}
            label="Cost & tokens"
          >
            <StatNumber
              size="hero"
              value={data ? fmtCost(data.totals.cost_usd) : "—"}
              accent
              sub={
                data
                  ? `${data.totals.tokens_in.toLocaleString()} in · ${data.totals.tokens_out.toLocaleString()} out`
                  : "loading…"
              }
            />
            {data?.last_24h.cost_usd ? (
              <div className="mt-3 text-xs text-muted-foreground">
                {fmtCost(data.last_24h.cost_usd)} in the last 24h
              </div>
            ) : null}
          </Tile>
        </div>

        {/* Data tiles row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-12">
          <IntegrationTile
            name="OpenTelemetry"
            connected={status?.otel.connected}
            last={status?.otel.last_event_at}
            ever={status?.otel.ever_connected}
          />
          <IntegrationTile
            name="Cursor"
            connected={status?.cursor.connected}
            last={status?.cursor.last_event_at}
            ever={status?.cursor.ever_connected}
            badge={data?.pending_cursor ? `${data.pending_cursor} pending` : undefined}
          />
          <IntegrationTile
            name="LangGraph"
            connected={status?.langgraph.connected}
            last={status?.langgraph.last_event_at}
            ever={status?.langgraph.ever_connected}
          />
          <Tile
            icon={<AlertTriangle className="size-3.5" />}
            label="Errors"
            href="/runs"
          >
            <StatNumber
              value={data?.totals.errors ?? "—"}
              sub={data?.totals.errors ? "needs attention" : "all clean"}
            />
          </Tile>
        </div>

        {/* Recent activity */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
          <div className="md:col-span-2">
            <SectionTitle icon={<Sparkles className="size-3.5" />}>
              Recent activity
            </SectionTitle>
            {data && data.recent_runs.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="overflow-hidden rounded-xl border border-border/30 bg-secondary/10 divide-y divide-border/30">
                {(data?.recent_runs ?? []).map((r) => (
                  <Link
                    key={r.id}
                    href={`/runs/${r.id}`}
                    className="flex items-center gap-4 px-5 py-4 hover:bg-secondary/20 transition-colors"
                  >
                    <FrameworkDot framework={r.framework} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-foreground">
                        {r.script_path || (
                          <span className="font-mono text-xs text-muted-foreground">
                            {r.id.slice(0, 12)}…
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {r.framework} · {fmtAgo(r.started_at)}
                      </div>
                    </div>
                    <StatusPill status={r.status} />
                    <div className="hidden sm:block text-right text-xs text-muted-foreground tabular-nums">
                      <div>{fmtDuration(r.duration_ms)}</div>
                      <div className="mt-0.5">
                        {(r.total_tokens_in || 0) + (r.total_tokens_out || 0)} tok
                        {r.total_cost_usd ? ` · ${fmtCost(r.total_cost_usd)}` : ""}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div>
            <SectionTitle icon={<PlugZap className="size-3.5" />}>
              By framework
            </SectionTitle>
            <div className="rounded-xl border border-border/30 bg-secondary/10 p-4">
              {data && data.by_framework.length === 0 ? (
                <p className="text-sm text-muted-foreground py-2">
                  Connect a framework to see breakdown.
                </p>
              ) : (
                <ul className="divide-y divide-border/30">
                  {(data?.by_framework ?? []).map((f) => (
                    <li
                      key={f.framework}
                      className="flex items-center justify-between py-2.5 text-sm"
                    >
                      <span className="flex items-center gap-2">
                        <FrameworkDot framework={f.framework} />
                        <span className="font-mono text-xs">{f.framework}</span>
                      </span>
                      <span className="text-muted-foreground tabular-nums">
                        {f.count}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-4">
              <Link
                href="/onboarding"
                className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
              >
                Add an integration
                <ArrowRight className="size-3.5" />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

function IntegrationTile({
  name,
  connected,
  last,
  ever,
  badge,
}: {
  name: string;
  connected?: boolean;
  last?: number | null;
  ever?: boolean;
  badge?: string;
}) {
  const live = !!connected;
  return (
    <Tile className="!p-5">
      <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-3">
        {name}
      </div>
      <div className="flex items-center gap-2">
        <span
          className={`inline-block size-1.5 rounded-full ${
            live ? "bg-emerald-400 animate-pulse" : "bg-muted-foreground/40"
          }`}
        />
        <span
          className={`text-sm font-semibold ${live ? "text-emerald-300" : "text-muted-foreground"}`}
        >
          {live ? "live" : ever ? "idle" : "not connected"}
        </span>
      </div>
      {last && (
        <div className="mt-1 text-[11px] text-muted-foreground">
          {fmtAgo(last)}
        </div>
      )}
      {badge && (
        <div className="mt-3 inline-block rounded-full bg-destructive/15 px-2 py-0.5 text-[10px] font-semibold text-destructive">
          {badge}
        </div>
      )}
    </Tile>
  );
}

function SectionTitle({
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

function SparklineSvg({ values }: { values: number[] }) {
  if (values.length === 0)
    return <div className="mt-4 h-12 text-xs text-muted-foreground">no activity yet</div>;
  const max = Math.max(1, ...values);
  const w = 100;
  const h = 28;
  const step = w / Math.max(1, values.length - 1);
  const points = values
    .map((v, i) => `${(i * step).toFixed(2)},${(h - (v / max) * h).toFixed(2)}`)
    .join(" ");
  return (
    <div className="mt-5 h-12 relative">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        className="absolute inset-0 size-full"
      >
        <defs>
          <linearGradient id="spark-grad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#FF6B35" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#FF6B35" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon
          fill="url(#spark-grad)"
          points={`0,${h} ${points} ${w},${h}`}
        />
        <polyline
          fill="none"
          stroke="#FF6B35"
          strokeWidth="1.5"
          points={points}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-border/40 bg-secondary/5 p-10 text-center">
      <p className="text-sm text-muted-foreground mb-3">No runs yet.</p>
      <Link
        href="/onboarding"
        className="inline-flex items-center gap-1.5 rounded-md bg-accent text-white px-4 py-2 text-sm font-semibold hover:bg-accent/90 transition-colors"
      >
        Connect an integration
        <ArrowRight className="size-3.5" />
      </Link>
    </div>
  );
}
