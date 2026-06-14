# Changelog

All notable changes from the audit, refactor, and hardening pass. Grouped by
theme; newest first. See [AUDIT.md](AUDIT.md) for the findings behind each change
and [PLAN.md](PLAN.md) for the prioritized plan.

## [Unreleased] — hardening pass

### Correctness — the core promise

- **Offline-reproducible hero numbers.** The published figures (42.9% token
  bypass, 6.5× median speed-up, 100% replay success) required a live API key and
  an uncommitted `~/.husk/traces.db`. The canonical run is now frozen into a
  committed, version-stamped fixture (`benchmark/fixtures/canonical_run/`), and
  `benchmark/reproduce.py` regenerates and **asserts** every figure offline with
  no key, no network. Guarded by `benchmark/tests/test_reproduce.py` and a CI
  job.
- **Determinism tests that go red on drift.** `benchmark/tests/test_determinism.py`
  records a real LangGraph run (canned LLM) and asserts a resume re-runs *exactly*
  the fork node + its successors, with zero variance across repeats.
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
  imported) is gone; the real engine is `replay/langgraph_replay.py`.
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
- Reconciled every doc — README, the technical report, the benchmark README, and
  the pitch deck — to the single canonical measured run. Added `AUDIT.md`,
  `PLAN.md`, and this changelog; committed the previously-untracked `benchmark/`
  and `pitch/` trees.
