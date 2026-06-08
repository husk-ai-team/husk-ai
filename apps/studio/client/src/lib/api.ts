// Typed REST + WebSocket client for the Husk Studio backend.
// In dev, Vite proxies /api and /ws → http://localhost:7654.

export interface Run {
  id: string;
  parent_run_id: string | null;
  fork_span_id: string | null;
  script_path: string;
  framework: string;
  status: string;
  started_at: number;
  finished_at: number | null;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost_usd: number;
  error_message: string | null;
}

export interface Span {
  id: string;
  run_id: string;
  parent_span_id: string | null;
  kind: string;
  name: string;
  started_at: number;
  finished_at: number | null;
  status: string;
  input_inline: unknown;
  output_inline: unknown;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  provider: string | null;
  model: string | null;
  error_payload: Record<string, unknown> | null;
  attrs: Record<string, unknown>;
}

export type RunEvent =
  | { type: "span.replay"; span: Span }
  | { type: "span.created"; run_id: string; span: Span }
  | { type: "ping" };

const BASE = "/api/v1";

async function fetcher<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status} ${r.statusText}`);
  return (await r.json()) as T;
}

export const getRuns = () => fetcher<Run[]>(`${BASE}/runs`);
export const getRun = (id: string) => fetcher<Run>(`${BASE}/runs/${id}`);
export const getSpans = (id: string) => fetcher<Span[]>(`${BASE}/runs/${id}/spans`);

export function subscribeRun(
  id: string,
  onEvent: (e: RunEvent) => void,
): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${window.location.host}/ws/runs/${id}`);
  ws.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as RunEvent);
    } catch {
      // ignore malformed
    }
  };
  return ws;
}

// --- formatters ---

export function fmtDuration(ms: number | null): string {
  if (ms == null || ms <= 0) return "—";
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60_000);
  const s = Math.floor((ms % 60_000) / 1000);
  return `${m}m ${s}s`;
}

export function fmtTokens(inT: number | null, outT: number | null): string {
  const total = (inT || 0) + (outT || 0);
  return total ? total.toLocaleString() : "—";
}

export function fmtCost(usd: number | null): string {
  if (usd == null || usd === 0) return "—";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

export function fmtTime(ms: number | null): string {
  if (!ms) return "—";
  const d = new Date(ms);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function shortId(id: string, n = 8): string {
  return id.length > n ? id.slice(0, n) : id;
}

export function spanKindColor(kind: string): string {
  switch (kind) {
    case "llm":
      return "text-primary";
    case "tool":
      return "text-sky-400";
    case "chain":
      return "text-emerald-400";
    default:
      return "text-muted-foreground";
  }
}

// --- Dashboard types ---

export interface DashboardSummary {
  now_ms: number;
  totals: {
    runs: number;
    spans: number;
    tokens_in: number;
    tokens_out: number;
    cost_usd: number;
    errors: number;
  };
  last_24h: {
    runs: number;
    tokens_in: number;
    tokens_out: number;
    cost_usd: number;
  };
  by_framework: { framework: string; count: number }[];
  recent_runs: {
    id: string;
    framework: string;
    status: string;
    started_at: number;
    finished_at: number | null;
    duration_ms: number | null;
    total_tokens_in: number;
    total_tokens_out: number;
    total_cost_usd: number;
    script_path: string;
  }[];
  sparkline: number[];
}

export const getDashboardSummary = () =>
  fetcher<DashboardSummary>("/api/dashboard/summary");

export interface AllIntegrationStatus {
  now_ms: number;
  cursor: { connected: boolean; ever_connected: boolean; last_event_at: number | null };
  langgraph: { connected: boolean; ever_connected: boolean; last_event_at: number | null };
  otel: { connected: boolean; ever_connected: boolean; last_event_at: number | null };
}

export const getIntegrationsStatus = () =>
  fetcher<AllIntegrationStatus>("/api/integrations/status");

export function fmtAgo(ms: number | null | undefined): string {
  if (!ms) return "—";
  const diff = Date.now() - ms;
  if (diff < 0) return "just now";
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

// --- IDE observability events (Cursor / VS Code bridges) ---

export interface CursorEvent {
  id: string;
  hook: string;
  project: string | null;
  payload: Record<string, unknown>;
  created_at: number;
}

export const listCursorEvents = (limit = 50) =>
  fetcher<CursorEvent[]>(`/api/cursor/events?limit=${limit}`);

export function summarizeCursorEvent(e: CursorEvent): string {
  const p = e.payload as Record<string, unknown>;
  switch (e.hook) {
    case "afterFileEdit":
      return (p.file_path as string) || "(file edit)";
    case "stop":
      return "agent stop";
    case "terminal.command":
      return (p.command as string) || "(terminal command)";
    default:
      return e.hook;
  }
}
