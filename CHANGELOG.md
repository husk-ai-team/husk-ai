# Changelog

All notable changes, grouped by theme; newest first.

## [0.7.0] — Back to a single-user development debugger

Husk is, again, an interactive debugger you use while building an AI agent, before production —
for a single Product Manager debugging their own agent, not a team. The production-observability /
multi-user direction has been reversed.

### Repositioned
- **Single-user, local-first, development-time.** No login, no accounts, no project switcher, no
  team dashboard. The Studio opens straight onto the agent you're building on this machine.
- **Development-only, enforced in code.** Trace ingest is loopback-only, so only an agent running
  on this machine can stream in — a production deployment on another host is refused. Husk cannot
  be pointed at production by design.
- **The AI debugs for you.** The automatic debugger reads a failed run and tells you, in plain
  language, what went wrong and what to change — on one click, or automatically the moment a run
  fails.

### Removed from the public product (moved to a private enterprise edition)
- User accounts + login, teams, projects, per-project ingest API keys, the project switcher, the
  "Connect your team" settings, and the keyed networked-ingest path.
- The production-analytics layer: over-time cost/failure insights, anomaly cards, and the grounded
  chatbot, plus the over-time Errors-analysis page.

### Kept
- Multi-model attribution (which model handled each step, and its cost, within a run),
  modify-and-replay (resume from the broken step, skipping upstream token cost), and local-first /
  zero data retention.

## [0.6.0] — Zero-boilerplate native replay: `@husk.node` / `HuskAgent`

The gap this closes: the headline modify-and-replay feature (resume a run from any
node with edited state, skipping the upstream nodes) required hand-wiring ~150
lines of OTel/snapshot/`replay_from` plumbing onto Husk's engine. This release
collapses that into two decorators.

### `@husk.node` / `HuskAgent`
- New `husk_shared.agent.HuskAgent`: decorate plain `(state) -> delta` functions
  with `@agent.node` and get full node-skip modify-and-replay (the token-bypass
  primitive) — the OTel root span, per-node `graph_node` telemetry with state
  diffs, topology attributes, snapshot store, and `invoke` / `replay_from` are all
  generated. `husk.graph_module` is resolved automatically from the agent's
  module-global name.
- `examples/husk_thread.py` shrinks from ~150 lines of boilerplate to its two node
  functions plus the decorators.
- The replay dispatcher (`replay/graph_replay.py`) learns to drive a decorated
  agent (marked `_husk_agent`) — finding `invoke` / `replay_from` on the agent
  object — without changing how it drives module-level functions or LangGraph's
  `invoke(state, config=)` convention.

## [0.5.1] — Container image (GHCR) + onboarding & polling polish

### Packaging
- **Container image on GitHub Packages.** A multi-stage `Dockerfile` (Node builds
  the Studio bundle, which is gitignored; a uv/Python stage runs the backend that
  serves it) and a tag-triggered workflow (`.github/workflows/docker-publish.yml`)
  publish `ghcr.io/husk-ai-team/husk-ai` on every `vX.Y.Z` tag, using the built-in
  `GITHUB_TOKEN` — no secrets. `docker run -p 7654:7654 -v husk-data:/data
  ghcr.io/husk-ai-team/husk-ai`. README documents the loopback caveat (great for
  the Studio + same-network capture; cross-host ingest still wants a local install).

### Onboarding
- **No more port footgun.** `husk-ai start` records the bound port to
  `~/.husk/port`, and `demo` / `replay` default to it (fallback 7654) — so they
  reach the backend even when `start` auto-bumped off a busy 7654.
- `husk-ai demo` now points to the next step (`husk-ai mcp install` + the new
  paste-in `AGENT_PROMPT.md`), and `husk-ai doctor` prints a short "next steps"
  block. Added `AGENT_PROMPT.md` (a ready-to-paste prompt that makes a coding
  assistant actually use Husk's MCP tools when debugging).

### Performance
- The Studio's Runs and Dashboard pages stop polling while the browser tab is
  hidden (one-line `document.hidden` guard) — no wasted requests in the background.

## [0.5.0] — OpenRouter debugger provider + example state-diff telemetry

### Debugger
- **OpenRouter provider** (`debugger/providers.py`): the BYOK auto-debugger now
  supports OpenRouter alongside Anthropic and OpenAI, so you can debug a run with
  the same provider it ran on (Husk's own benchmark runs on OpenRouter Llama).
  OpenAI-compatible call path (Bearer auth, classic `max_tokens`); `GET
  /api/debugger/providers` now returns `anthropic, openai, openrouter`. Added
  context-window / output metadata (`husk_shared/model_metadata.py`) for the
  `meta-llama/*`, `openai/*`, and `anthropic/*` OpenRouter model ids.

### Example
- **`examples/husk_thread.py` now demonstrates per-node state.** It wires the engine
  telemetry hook (`on_node`) so each node emits a `graph_node` span carrying
  `state_before` / `state_after` / `state_diff`, and records the linear topology on
  the root span. The Studio's per-node **State diff** view and node graph now
  populate from the bundled example (previously the example emitted no state). Fixed
  the post-run hint, which pointed at the Vite dev URL (`:5174`) instead of the
  running backend.

### Tests
- OpenRouter provider call-shape + registry tests. Suite: 112 passing.

## [0.4.0] — Security hardening, dead-code removal, terminal/CI workflow

### Security
- **Replay RCE closed.** `/api/replay` imported and executed a graph-module path
  taken from stored run data with no auth. Added a shared loopback + Origin guard
  (`api/_guard.py`) on the replay / OTel-ingest / debugger routers, and a
  `graph_module` allowlist in `replay/graph_replay.py` (cwd or
  `$HUSK_ALLOWED_GRAPH_DIRS`) so only trusted project files can be imported.
- **At-rest hardening.** `~/.husk` is created `0700` and `traces.db` `0600`; an
  opt-out redaction pass (`HUSK_NO_REDACT=1`) scrubs common key/token shapes from
  ingested prompts/completions/tool I/O before they are persisted.
- Removed all `husk.dev` references (CORS allow-list, landing page, Studio footer,
  package metadata) — links now point at the GitHub repository.

### Zero-friction capture + terminal/CI
- **`husk_shared.instrument()`** — one call wires OpenTelemetry export to Husk
  (lazy OTel import, no new hard dependency); `llm_span()` sets the GenAI attrs.
- **`husk run <command…>`** runs your agent and captures it in one step (auto-starts
  the backend, sets `$OTEL_EXPORTER_OTLP_ENDPOINT`, prints the run URL).
  **`husk replay <run_id>`** and **`husk export <run_id>`** bring replay and portable
  run bundles to the shell and CI.

### Studio
- Run **search + status filters**, a **Recent failures** dashboard tile, and the
  **Errors** tile deep-links to the filtered view. **Replay is gated**: runs without
  a graph module show a clear explanation instead of a `400`.

### Cleanup
- Deleted the dead legacy `husk run` / sandbox execution path (~8k LOC); `husk-sandbox`
  is now just the HTTP cassette. Removed the inert `auto_apply` config. Pruned 50
  unused Studio components and 35 unused frontend dependencies.

### Tests
- Security regressions (replay-RCE allowlist, loopback guard, ingest redaction),
  `instrument()` / CLI / runs-filter tests, and end-to-end flows (capture→read,
  BYOK debugger with a mocked LLM, replay on Husk's own engine). Suite: 110 passing.

## [0.3.0] — Automatic LLM debugger (BYOK) + node-graph visualization

### Automatic debugger (bring your own key)

- **BYOK provider layer** (`husk_studio_backend/debugger/providers.py`): a small
  provider abstraction over pure `httpx` (no new SDK deps) with Anthropic and
  OpenAI implementations and a one-line registry to add more. The user picks the
  provider and model; the model's context window (`husk_shared/model_metadata.py`)
  sizes the context budget.
- **Local-first key handling** (`debugger/secrets.py`): the key lives only in
  `~/.husk/secrets.json` (chmod 0600 on POSIX) with an `ANTHROPIC_API_KEY` /
  `OPENAI_API_KEY` env fallback. It is never logged, never written into traces or
  exports, and `GET /api/debugger/config` returns `has_key` only — never the key.
  Provider calls go straight from the local backend to the provider, never through
  a Husk server.
- **Failure-focused context assembler** (`debugger/context_assembler.py`): builds
  the LLM input from a run — topology, executed path, per-node state + diff, tool
  calls, model calls (prompt/response/tokens), exceptions/stack traces, and the
  recursion-limit signal. Big traces are windowed: full detail around the failure,
  far regions summarized or dropped to fit the selected model's window — the
  failure region is never cut.
- **Shipped, versioned system prompt** (`debugger/system_prompt.py`): instructs
  symptom-vs-cause reasoning, walking back to the first divergence, failure
  classification, and strict JSON output. Output is validated with a forbid-extra
  Pydantic schema and a tolerant extractor (`debugger/schemas.py`); fabricated
  trace content and silent guessing are forbidden.
- **Propose, don't apply.** `POST /api/debugger/runs/{id}/analyze` runs on demand;
  auto-analysis of failed runs is opt-in and **off by default**. A proposed fix is
  shown as a diff; applying it (`/apply-fix`) requires an explicit confirm and the
  off-by-default "allow applying fixes" toggle, writes a `.husk-bak` backup, and is
  atomic (clean apply or nothing). Reports persist in a new `debug_reports` table.

### Agent visualization (UI + structured data layer)

- **Structural per-node data.** The engine (`husk_shared/engine.py`) gained an
  optional, no-op-by-default telemetry hook; the example agent uses it to emit a
  `graph_node` span per node carrying before/after state, the state diff, and (on
  exceptions) a stack trace, with the node's model/tool spans nested under it. Graph
  topology is written onto the root span. This data now exists in the trace rather
  than being reconstructed.
- **Per-node graph API** (`GET /api/v1/runs/{id}/graph`): nodes with status
  (success / error / **skipped** / running), per-node state + diff, model and tool
  calls, tokens, timing, the detected failure point, edges (incl. conditional
  edges/labels when recoverable), and the attached debugger report.
- **Node-graph UI**: a new dependency-free SVG graph view in the run detail page —
  state-colored nodes, a highlighted failure point, arrowed/labeled edges, a
  per-node context panel (input/output, prompt/response, errors, before/after state
  diff), a Timeline/Graph toggle, and the debugger report overlaid on the
  implicated nodes. A BYOK panel was added to Settings.
- **No recording-format bump.** `debug_reports` is a brand-new table created by
  `create_all`; it does not change the shape of `runs`/`spans`/`branches`, so
  `RECORDING_FORMAT_VERSION` stays at 1 and old/new DBs stay mutually readable.

## [0.2.0] — Husk's own replay engine

### The modify-and-replay primitive is now Husk's own

- **Husk's own checkpoint/replay engine** (`husk_shared.engine`): a small,
  framework-agnostic linear executor plus a local SQLite snapshot store. After
  each node a snapshot of the merged state is persisted; `replay_from` reloads the
  snapshot before a fork node, applies a patch, and re-runs exactly that node and
  its successors — the upstream nodes are never called, so they emit no spans and
  consume no tokens. The primitive no longer depends on any agent framework.
- **Core rebuilt as Husk's own.** The replay endpoint is `/api/replay`
  (`api/replay.py`), the dispatcher is `replay/graph_replay.py`, and the engine
  emits `husk.*` telemetry (`husk.thread_id`, `husk.node`). The benchmark graph
  and the bundled `examples/husk_thread.py` run on the native engine.
- **Republished benchmark, measured on Husk's engine.** The committed canonical
  run (`benchmark/fixtures/canonical_run/`) and hero numbers are regenerated from
  a 500-parent / 118-replay run on Husk's own engine (OpenRouter Llama-3.3-70B +
  3.1-8B, TriviaQA, seed 42): **42.07%** mean token bypass [35.65, 48.81],
  token-weighted 55.0%, median **6.9×** wall-time speed-up, **100%** replay
  success (118/118), max single bypass **90.7%**. Metric definitions, the BCa
  bootstrap, the Wilson interval, and the offline reproduce harness are unchanged;
  `benchmark/reproduce.py` passes against the new fixture.
- **Framework integrations stay.** Husk still traces agents built with LangChain
  and LangGraph via the sandbox integrations; those plugins and the framework
  labels are untouched.

## [0.1.0] — hardening pass

### Correctness — the core promise

- **Offline-reproducible hero numbers.** The published figures (token bypass,
  median speed-up, replay success) required a live API key and
  an uncommitted `~/.husk/traces.db`. The canonical run is now frozen into a
  committed, version-stamped fixture (`benchmark/fixtures/canonical_run/`), and
  `benchmark/reproduce.py` regenerates and **asserts** every figure offline with
  no key, no network. Guarded by `benchmark/tests/test_reproduce.py` and a CI
  job.
- **Determinism tests that go red on drift.** `benchmark/tests/test_determinism.py`
  records a real run (canned LLM) and asserts a resume re-runs *exactly* the fork
  node + its successors, with zero variance across repeats.
  `packages/husk-sandbox/tests/test_cassette_sdk.py` drives the real OpenAI SDK
  through a cassette and asserts a replay touches **zero** network and is
  byte-identical.
- **Honest, reproducible metrics.** `hero_report.py` now computes cost/tokens
  from authoritative per-span counts (the stored rollup was a stale `$0`),
  excludes replay children from the parent count (the disclosed 617→500 quirk),
  and sorts samples before its seeded BCa bootstrap so the numbers — CI bounds
  included — are byte-reproducible from any DB or fixture with the same data.
  Hero point estimates are unchanged.

### Model-free, deterministic replay (new)

- **HTTP cassettes** (`packages/husk-sandbox/cassette.py`): record provider HTTP
  at the httpx transport boundary (shared by the OpenAI/Anthropic/Groq SDKs)
  keyed by a stable request hash; replay serves the recorded response with no
  network — deterministic, byte-identical, $0. A changed request misses and
  falls through to the live provider, then is recorded. Wired into the research
  graph (`HUSK_RECORD_CASSETTE` / `HUSK_REPLAY_CASSETTE`) and the replay endpoint
  (`use_cassette`). The M1 `http_proxy.py` stub is now a thin façade over it.

### Recording format

- **Versioned recordings** (`husk_shared.recording`): every trace DB is stamped
  with `RECORDING_FORMAT_VERSION` in `PRAGMA user_version`. On open, the backend
  refuses a DB written by a newer Husk (loud `RecordingFormatError`) and runs a
  registered migration chain for an older one, instead of silently misreading it.

### Backend & architecture

- **Branches are first-class.** `/api/v1/branches` (was a 501 stub) now creates
  (idempotently) and lists parent→child replay links, each reporting
  `token_bypass_pct` / tokens / cost saved. The replay endpoint records the
  branch automatically once the child run is ingested. `/api/v1/diff` (was a
  stub) returns a real run-vs-run diff.
- **Dead code removed.** `replay/engine.py` (a `NotImplementedError` stub nothing
  imported) is gone; the real dispatcher is `replay/graph_replay.py`.
- **Strict types.** `mypy --strict` now actually runs (a duplicate `tests`
  package had been aborting it) and passes across the package surface; the
  public API is annotated (no bare `dict`/`Any` returns). CI enforces it.

### Studio (UI/UX)

- The replay **lineage** and **token bypass** — the product's core story — are
  now visible: a run shows its replays (and its parent, if it is one) with
  bypass %, tokens, and cost saved, plus a real parent-vs-replay **diff**.
- The replay view gains a **Model-free** toggle (cassette replay) and links
  straight to the new run with its bypass once recorded.
- Removed the two dead buttons ("Rewind to here", "Compare runs"); "Compare" is
  now the diff. Added Studio unit tests (vitest).

### CI / DX / docs

- CI now runs **ruff + mypy + pytest + an offline benchmark smoke** (Python
  matrix) and **tsc + vitest + build** (Studio), and syncs the `examples` group
  so the determinism/model-free tests actually run.
- Added the missing `.pre-commit-config.yaml`.
- Pricing table gained the OpenRouter `meta-llama/*` IDs the benchmark used.
- Reconciled the public docs (README, benchmark README) to the single canonical
  measured run, and added this changelog; committed the previously-untracked
  `benchmark/` harness. (Internal working notes and pitch/DD materials are kept
  out of the public tree.)
