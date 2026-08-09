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
  models?: string[];
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
  // The backlog a late-joining client receives, as one frame rather than one per span.
  | { type: "span.replay.batch"; spans: Span[] }
  | { type: "span.created"; run_id: string; span: Span }
  | { type: "ping" };

const BASE = "/api/v1";

async function fetcher<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status} ${r.statusText}`);
  return (await r.json()) as T;
}

export const getRuns = (params?: {
  status?: string;
  framework?: string;
  q?: string;
  limit?: number;
}) => {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.framework) qs.set("framework", params.framework);
  if (params?.q) qs.set("q", params.q);
  if (params?.limit) qs.set("limit", String(params.limit));
  const suffix = qs.toString() ? `?${qs}` : "";
  return fetcher<Run[]>(`${BASE}/runs${suffix}`);
};
export const getRun = (id: string) => fetcher<Run>(`${BASE}/runs/${id}`);
export const getSpans = (id: string) => fetcher<Span[]>(`${BASE}/runs/${id}/spans`);

// --- Branches (parent -> child replay lineage) ---

export interface Branch {
  id: string;
  parent_run_id: string;
  child_run_id: string;
  fork_span_id: string;
  override_type: string;
  override_payload: Record<string, unknown>;
  label: string | null;
  notes: string | null;
  created_at: number;
  parent_llm_tokens: number;
  child_llm_tokens: number;
  tokens_bypassed: number;
  token_bypass_pct: number;
  cost_bypassed_usd: number;
}

export function listBranches(params: {
  parent_run_id?: string;
  child_run_id?: string;
}): Promise<Branch[]> {
  const q = new URLSearchParams();
  if (params.parent_run_id) q.set("parent_run_id", params.parent_run_id);
  if (params.child_run_id) q.set("child_run_id", params.child_run_id);
  return fetcher<Branch[]>(`${BASE}/branches?${q.toString()}`);
}

// --- Diff (run vs run) ---

export interface RunDiffSide {
  run_id: string;
  status: string;
  duration_ms: number | null;
  llm_spans: number;
  llm_tokens: number;
  nodes: string[];
}

export interface RunDiff {
  a: RunDiffSide;
  b: RunDiffSide;
  tokens_delta: number;
  tokens_bypassed: number;
  token_bypass_pct: number;
}

export const getDiff = (a: string, b: string) =>
  fetcher<RunDiff>(`${BASE}/diff/${a}/${b}`);

// --- Replay (modify-and-replay / model-free) ---

export interface ReplayResult {
  thread_id?: string;
  child_id?: string;
  state?: unknown;
  note?: string;
}

export async function replayRun(body: {
  run_id: string;
  span_id?: string | null;
  state_override: unknown;
  use_cassette?: boolean;
  parent_thread_id?: string | null;
  fork_node?: string | null;
}): Promise<ReplayResult> {
  const r = await fetch("/api/replay", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return (await r.json()) as ReplayResult;
}

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

export function fmtCompact(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}K`;
  if (n < 1_000_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  return `${(n / 1_000_000_000).toFixed(1)}B`;
}

export function fmtCost(usd: number | null): string {
  if (usd == null || usd === 0) return "—";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

export function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
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
      return "text-foreground";
    case "chain":
      return "text-muted-foreground";
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
    avg_latency_ms: number;
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

// --- Per-run model breakdown (the multi-model "insight gigantesco") ---

export interface RunModelBreakdown {
  model: string;
  provider: string | null;
  calls: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  errors: number;
  cost_share: number;
}
export interface RunBreakdown {
  run_id: string;
  total_cost_usd: number;
  by_model: RunModelBreakdown[];
}

export const getRunBreakdown = (id: string) =>
  fetcher<RunBreakdown>(`${BASE}/runs/${id}/breakdown`);

export interface IntegrationState {
  connected: boolean;
  ever_connected: boolean;
  last_event_at: number | null;
}

export interface AdapterStatus extends IntegrationState {
  framework: string;
}

export interface AllIntegrationStatus {
  now_ms: number;
  cursor: IntegrationState;
  // "Any traces arriving at all" — the framework-agnostic ingest path.
  otel: IntegrationState;
  // Per-framework breakdown; no framework is privileged (LangGraph is one row here).
  adapters: AdapterStatus[];
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

// --- Per-node graph view (Feature: agent visualization) ---

export interface StateDiff {
  added: Record<string, unknown>;
  removed: Record<string, unknown>;
  changed: Record<string, { from: unknown; to: unknown }>;
}

export interface GraphModelCall {
  span_id: string;
  model: string | null;
  provider: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  prompt: unknown;
  response: unknown;
  status: string;
  error: Record<string, unknown> | null;
}

export interface GraphToolCall {
  span_id: string;
  name: string;
  args: unknown;
  result: unknown;
  status: string;
  error: Record<string, unknown> | null;
}

export type NodeStatus = "success" | "error" | "skipped" | "running";

export interface GraphNode {
  id: string;
  name: string;
  seq: number;
  status: NodeStatus;
  span_id: string | null;
  started_at: number | null;
  finished_at: number | null;
  duration_ms: number | null;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  is_failure_point: boolean;
  state_before: unknown;
  state_after: unknown;
  state_diff: StateDiff | null;
  model_calls: GraphModelCall[];
  tool_calls: GraphToolCall[];
  error: Record<string, unknown> | null;
  traceback: string | null;
}

export interface GraphEdge {
  from: string;
  to: string;
  conditional: boolean;
  label: string | null;
}

export interface RunGraph {
  run_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  executed_path: string[];
  failure: { node_id: string; seq: number; span_id: string | null; message: string | null } | null;
  recursion_limit_hit: boolean;
  run_status: string;
  run_error: string | null;
  debug_report: DebugReportRow | null;
}

export const getRunGraph = (id: string) =>
  fetcher<RunGraph>(`${BASE}/runs/${id}/graph`);

// --- Automatic debugger (BYOK) ---

export interface DebugReportBody {
  failure_localization: { node_id: string | null; step_index: number | null; also_implicated: string[] };
  failure_class: string;
  root_cause: string;
  evidence: string[];
  proposed_fix: { summary: string; diff: string | null; rationale: string };
  confidence: "high" | "medium" | "low";
  missing_information: string[];
}

export interface DebugReportRow {
  id: string;
  run_id: string;
  report: DebugReportBody;
  provider: string;
  model: string;
  failure_node: string | null;
  failure_class: string | null;
  confidence: string | null;
  system_prompt_version: string;
  trigger: string;
  applied: boolean;
  created_at: number;
}

export interface DebuggerConfig {
  provider: string;
  model: string;
  auto_analyze: boolean;
  has_key: boolean;
}

export interface DebuggerModel {
  id: string;
  context_window: number;
  max_output: number;
}

export const getDebuggerConfig = () =>
  fetcher<DebuggerConfig>("/api/debugger/config");

export async function saveDebuggerConfig(body: Partial<DebuggerConfig> & { api_key?: string }): Promise<DebuggerConfig> {
  const r = await fetch("/api/debugger/config", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return (await r.json()) as DebuggerConfig;
}

export const getDebuggerProviders = () =>
  fetcher<{ providers: string[] }>("/api/debugger/providers");

export const getDebuggerModels = (provider?: string) =>
  fetcher<{ provider: string; models: DebuggerModel[] }>(
    `/api/debugger/models${provider ? `?provider=${encodeURIComponent(provider)}` : ""}`,
  );

export async function analyzeRun(
  runId: string,
  body: { provider?: string; model?: string } = {},
): Promise<DebugReportRow> {
  const r = await fetch(`/api/debugger/runs/${runId}/analyze`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return (await r.json()) as DebugReportRow;
}

export async function getDebugReport(runId: string): Promise<DebugReportRow | null> {
  const r = await fetch(`/api/debugger/runs/${runId}/report`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return (await r.json()) as DebugReportRow;
}

export async function applyDebugFix(
  runId: string,
  reportId: string,
): Promise<{ applied: boolean; path: string; backup: string }> {
  const r = await fetch(`/api/debugger/runs/${runId}/apply-fix`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ report_id: reportId, confirm: true }),
  });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return (await r.json()) as { applied: boolean; path: string; backup: string };
}

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
