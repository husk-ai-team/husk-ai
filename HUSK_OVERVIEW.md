# Husk: the complete product overview

Husk is a local-first, single-user, development-time debugger for someone who builds AI agents. You use it while you are building an agent, before it ships. Connect your agent with one line, run it, and Husk replays every run as a visual story: what the agent did step by step, which model handled each call and what it cost, and — when something breaks — an automatic debugger that reads the whole run and tells you, in plain language, what went wrong and what to change. Then edit any step and replay from there, skipping the upstream token cost.

Killer feature, in one line: your agent fails, Husk debugs the run for you and proposes the fix.

Development only, never production. Husk debugs an agent while you build it. It cannot be pointed at production by design: trace ingest is loopback-only, so only an agent running on this machine can stream in — a production deployment on another host is refused at the door. Husk is not, and cannot be, production monitoring.

Local-first, zero data retention. Everything stays on your own machine. The only outbound call is the automatic debugger's, to a model provider you choose and bring your own key for (Regolo.ai by default: EU, GDPR, zero retention). Nothing core depends on any one framework.

---

## 1. Who it is for

Husk is for a single person who **uses** AI agents and needs to debug their own — typically a PM who builds agents mostly with no-code or hosted builders, not an engineer reading raw traces. The whole interface speaks in plain language: a step-by-step story of the run, not a wall of spans or code.

There is one honest exception to "no code": connecting an agent is a one-line SDK / OpenTelemetry setup step. That single line is the only code touchpoint. Everything after it — understanding a run, finding why it failed, fixing it — happens in the Studio, in plain language.

There is one user, on one machine. There are no teams, no projects, no logins, no accounts, no roles, no ingest keys, and no remote ingest. Husk runs for you, locally, and nothing about it assumes anyone else.

### Core principles

- Local-first. Everything lives in a single store under `~/.husk/` on your machine.
- Development-only, enforced in code. Trace ingest is gated to loopback, so Husk only ever sees an agent running on this machine. It cannot be wired to a production deployment.
- Zero data retention. Your traces stay on your machine. The only data that ever leaves is what the automatic debugger sends to the provider you choose.
- Framework-agnostic. OpenAI, Anthropic, LangGraph, LlamaIndex, and any OpenTelemetry GenAI emitter all work. No framework is privileged.
- It does the debugging. The automatic debugger reads the run and tells you the root cause and the fix; it is not a passive "explanation" you still have to interpret.
- Plain language over raw traces. The surface a PM can read, not a developer's span viewer.

---

## 2. How it works, end to end

```
  agent code                 the backend                      the Studio
 ────────────      ───────────────────────────────      ────────────────────
  instrument_*  ->  POST /v1/traces (OTLP/HTTP)      ->   Runs, Run detail,
  (one line)        loopback-only, no key                 Timeline, Inspector,
  or raw OTLP       parsed to runs + spans                Graph, Replay,
                    cost computed at ingest               Settings
                    stored in SQLite                      automatic debugger
                    streamed live over WebSocket
```

1. Instrument. You add one line (`instrument_openai(...)`, etc.) or point any OpenTelemetry GenAI exporter at the local backend.
2. Ingest. Spans arrive at `POST /v1/traces` (JSON or protobuf). The loopback guard accepts only a same-host caller — an agent running on this machine — and refuses anything from another host. Spans are mapped to Husk run and span rows; token cost is computed at ingest from a pricing table.
3. Store. Everything persists in a single SQLite file at `~/.husk/traces.db` (WAL mode, one writer).
4. Watch. The Studio reads the run and streams new spans live over a WebSocket. Polling pauses while the browser tab is hidden.
5. Debug. When a run fails, the automatic debugger reads the whole run, localizes the failure, and tells you in plain language what went wrong and what to change — on one click, or the moment a run fails if you turn on auto-debug.

---

## 3. The Studio, screen by screen

The Studio is a React 19 single-page app (Vite 7, Tailwind 4, shadcn/Radix, wouter router). The chrome is a sticky nav with the brand mark on the left and the section links beside it. A footer reminds you the data never leaves the machine.

### Runs

A live table of every run on this machine, newest first, polling every few seconds.

- Columns: agent (framework), models touched, status, started, duration, tokens, cost.
- Filters: free-text search on script path or run id, and a status filter (all / success / error / running).
- Click a row to open the run detail.

### Run detail

Everything about a single run.

- A "what failed" panel, and a clear "observability-only" state when there is no deep graph to analyze.
- A per-run model breakdown: in a multi-model run, exactly which model did what, what each cost, and which erred. This is the fastest way to find the call that gave a wrong answer.
- A timeline of spans, a span inspector, and a node graph for graph-instrumented runs.
- The automatic debugger's report when one exists, with the proposed fix.

### Replay (time travel)

For graph-instrumented runs: resume a run from any node with edited state, deterministically skipping the upstream nodes and their token cost. This is Husk's differentiator — the token-bypass primitive. Forks are recorded as branches, and two runs can be diffed.

### Connect (onboarding)

The one-line setup path: copy the local ingest endpoint and paste the instrumentation snippet into your agent. No key, no account — the endpoint is loopback and your agent runs on the same machine.

### Settings

- Automatic debugger (BYOK): pick a provider and model, set your key (stored locally, never echoed), toggle auto-analyze so the debugger runs the moment a run fails.
- Integrations: live status for OpenTelemetry, Cursor, and the framework adapters.
- Database schema: an inline reference for every table Husk stores.

### Design system: ink on paper

A single monochrome light theme defined in OKLCH (hue 264, chroma never above 0.004), so nothing is ever truly colored. Severity is encoded by tone, weight, fill, and inversion, never by color: an error is a solid ink chip, a success is quiet. Charts use explicit grays for faithful export. The Studio and the backend's fallback landing page share these tokens.

---

## 4. Feature catalog

### Ingestion and instrumentation

- OTLP/HTTP ingest at `POST /v1/traces`, JSON and protobuf, full OpenTelemetry GenAI semantic conventions — loopback-only, no key.
- One-line framework adapters (thin wrappers over OpenInference instrumentors): `instrument_openai`, `instrument_anthropic`, `instrument_langgraph`, `instrument_llamaindex`.
- A generic OTLP path for any framework that already emits GenAI spans, so coverage is "all frameworks, some way" rather than a closed list.
- MCP server (FastMCP, one-line install) so a coding assistant can query Husk directly.
- Cursor and VS Code IDE bridge: fire-and-forget observability events (file edits, stop signals, terminal commands) shown alongside agent spans.
- Cost computed at ingest from a pricing table, so spend is correct the moment a span lands.

### Multi-model attribution

- Per-run model breakdown: calls, tokens, cost, errors, and cost share by model and provider.
- Models shown on the runs list, so you see at a glance which models a run touched.
- Within a single run, this is the fastest way to find the call that produced a wrong answer.

### Automatic debugger (bring your own key)

- On-demand or auto-on-failure analysis of a (usually failed) run. Click once and Husk reads the whole run, localizes the failure, classifies it, and proposes a fix as a diff — in plain language. Turn on auto-analyze and it runs the moment a run fails.
- Propose-by-default: it never writes to a source file unless you explicitly confirm. Apply-fix writes the patch and keeps a backup.
- Providers: Regolo (default), Anthropic, OpenAI, OpenRouter. The key is stored only in `~/.husk/secrets.json`, sent only from your machine straight to the provider, never to a Husk server and never written into traces or exports.
- The analysis (never the key) is persisted so the report survives a reload.

### Replay and time travel

- Husk-native replay engine (`husk_shared.engine`: a linear executor plus a SQLite snapshot store), with zero framework dependency.
- Zero-boilerplate authoring: decorate plain `(state) -> delta` functions with `@husk.node` / `HuskAgent` and get the OTel root span, per-node telemetry with state diffs, the snapshot store, and `invoke` / `replay_from` generated for you.
- Modify-and-replay: resume from any node with edited state, deterministically skipping upstream nodes and their token cost.
- Branches and diff: forks are recorded as parent-to-child lineage, and two runs can be compared.

---

## 5. Data model and storage

A single store, one writer. SQLite at `~/.husk/traces.db` in WAL mode is the default and the right choice for a single-user, local tool: every trace flows through the one backend process on your machine.

Tables:

- `runs`: one row per agent invocation (status, timing, token and cost totals, framework).
- `spans`: every step inside a run (LLM call, tool, chain), with inputs and outputs, tokens, cost, provider, model, and raw OTel attributes.
- `snapshots`: captured state at a checkpoint, used by replay.
- `branches`: parent-to-fork lineage with the override payload.
- `http_cassettes`: recorded HTTP responses for deterministic replay.
- `debug_reports`: automatic-debugger analyses (the key is never stored here).
- `cursor_events`: IDE observability events.

Recording format versioning. Every trace DB is stamped with a format version (SQLite `PRAGMA user_version`). On open, Husk refuses to silently read a DB written by a newer Husk and migrates an older one forward through registered steps.

---

## 6. Security and privacy

- Loopback-only by design. Ingest, replay (runs code), and the debugger (holds your key and writes files) are all gated to loopback, same-host requests, with an Origin check that defeats DNS-rebinding. Husk only ever sees an agent running on this machine.
- Cannot be pointed at production. Because ingest is loopback-only, a production deployment on another host has no way to stream traces in. This is a structural property, not a setting to remember.
- Zero data retention. Traces stay on your machine. The only outbound call is the automatic debugger's, to the provider you configure (Regolo by default: EU, GDPR, zero retention).
- BYOK locality. The debugger key lives in `~/.husk/secrets.json`, is sent only from your machine to the provider, and is never returned by any endpoint, never written into traces or exports.
- The trace DB and the `~/.husk` directory are locked to the owner on creation (best-effort on Windows, where the user-profile ACL is the real protection).
- Cleartext caveat, stated honestly: the trace DB holds prompts, completions, and tool input and output in the clear, on your machine, by design.

---

## 7. API surface

Ingest

- `POST /v1/traces` OTLP/HTTP (JSON or protobuf), loopback-only.

Runs and spans

- `GET /api/v1/runs` list, filters: `status`, `framework`, `q`.
- `GET /api/v1/runs/{id}` one run.
- `GET /api/v1/runs/{id}/breakdown` per-model cost and usage.
- `GET /api/v1/runs/{id}/spans` the run's spans.
- `WS /ws/runs/{run_id}` live span stream.

Automatic debugger

- `GET /api/debugger/config`, `PUT /api/debugger/config` (loopback), `GET /api/debugger/providers`, `GET /api/debugger/models`.
- `POST /api/debugger/runs/{id}/analyze`, `GET /api/debugger/runs/{id}/report`, `POST /api/debugger/runs/{id}/apply-fix` (loopback, requires explicit `confirm: true`).

Graph, branches, diff, replay

- `GET .../runs/{run_id}/graph`, branches create and list, `GET .../{run_a}/{run_b}` diff, `POST /api/replay` (loopback).

Integrations, health

- `GET /api/integrations/status`.
- `GET /api/health`, `GET /healthz`.

---

## 8. CLI and install

The `husk-ai` CLI starts the backend, seeds demo data, checks health, and installs the MCP server.

- `husk-ai start` runs the backend and records the bound port to `~/.husk/port`, so `demo` and `replay` reach it even when `start` auto-bumped off a busy 7654.
- `husk-ai demo` seeds an example run to look at, then points to the next step.
- `husk-ai doctor` checks the install and prints a short next-steps block.
- `husk-ai mcp install` wires the MCP server into a coding assistant. `AGENT_PROMPT.md` is a ready-to-paste prompt that makes an assistant actually use Husk's MCP tools when debugging.

Quick start:

```bash
git clone https://github.com/husk-ai-team/husk-ai.git && cd husk-ai
uv sync --all-packages
uv run husk-ai start        # Studio at http://localhost:7654
uv run husk-ai demo         # seed a sample run to look at
```

Connect your own agent with one line of setup (any framework that speaks OpenTelemetry also just works):

```python
from husk_shared import instrument_openai
instrument_openai()         # every OpenAI SDK call now streams into Husk
```

---

## 9. The numbers

Husk's replay engine resumes a recorded run at the failing step and re-executes only that step and its successors, deterministically skipping the upstream work. On a committed 500-run benchmark: **mean token bypass 42.1%**, **median 6.9× speed-up**, **100% replay success**. Reproduce them offline, no API key:

```bash
uv run python benchmark/reproduce.py
```

Methodology: the [benchmark README](benchmark/README.md).

---

## 10. Deployment

Husk runs on your own machine, for you.

- Single binary path: install, `husk-ai start`, open the Studio.
- Container: a multi-stage `Dockerfile` (Node builds the Studio bundle, a uv/Python stage runs the backend that serves it). The public image is on GitHub Container Registry: `docker pull ghcr.io/husk-ai-team/husk-ai`. A tag-triggered workflow publishes it on every `vX.Y.Z` tag.
- Run it locally and open `http://localhost:7654`. Because ingest is loopback-only, only an agent on the same machine can stream into it — there is no remote ingest to configure, by design.

---

## 11. Glossary

- Run: one agent invocation, the top-level unit Husk records.
- Span: one step inside a run (an LLM call, a tool call, a chain step).
- Automatic debugger: the AI layer that reads a failed run, localizes the failure, and proposes a fix in plain language. On-demand or auto-on-failure.
- Replay: resuming a run from a node with edited state, deterministically skipping the upstream nodes.
- Branch: a recorded fork of a run.
- BYOK: bring your own key — the model the automatic debugger uses, stored locally and sent only to the provider you choose.

---

For the deeper wiki, see `docs/` (getting-started, instrumentation, multi-model, ai-layer, replay, mcp, docker, security, architecture, cli, troubleshooting, glossary). For version history, see `CHANGELOG.md`.
