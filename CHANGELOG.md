# Changelog

All notable changes from the audit, refactor, and hardening pass. Grouped by
theme; newest first.

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
