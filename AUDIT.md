# Husk — Audit

*Audit date: 2026-06-14. Auditor pass: full read of the recording, storage, replay, benchmark, CLI/MCP,
and Studio UI surfaces, plus a baseline build/test/lint/repro run on this machine
(Windows 11, Python 3.11 via uv).*

This document is the **before** picture and the running log of what changed. It classifies every headline
claim honestly, records what builds and what is broken, and states plainly whether the published numbers
reproduce. A matching **After** section at the bottom is updated as the hardening lands. See
[CHANGELOG.md](CHANGELOG.md) for the chronological change log and [PLAN.md](PLAN.md) for the prioritized plan.

---

## 1. What Husk claims to be

A local-first **visual debugger + deterministic replay engine** for LLM agents: record an agent run,
inspect the trajectory visually, and replay it cheaply by skipping work that was already correct. The
published materials put three hard numbers on the replay engine:

- **~42.9% mean token bypass**
- **~6.5× median wall-time speedup** on replay
- **100% replay success rate**

## 2. Methodology of this audit

For each claim I located the backing code and classified it: *real+tested-by-rerunnable-harness*,
*real+measured-once*, *partially-built*, or *aspirational prose*. I separated what a committed,
rerunnable harness measures from what is merely asserted. I ran the suite, the linter, the type checker,
and the metric pipeline on this machine and recorded the literal results below. **No number in this repo
was nudged to match the paper.**

## 3. Baseline on this machine (literal results)

| Check | Command | Result |
|---|---|---|
| Tests | `uv run python -m pytest -q` | **20 passed** in ~6 s |
| Lint | `uv run ruff check .` | **All checks passed** |
| Types | `uv run mypy packages` | **Broken** — `Duplicate module named "tests"` aborts the run before any real checking. `mypy` is configured `strict` but has never actually run. |
| Metrics repro (live DB) | `hero_report.py --db ~/.husk/traces.db` | **Reproduces exactly**: D5 42.87, D1 16.78 (median 6.53), D4 100.0, D3 89.39 — identical to [`hero_metrics.json`](benchmark/hero_metrics.json). |

> Note for this checkout: it is a *copy*, and `uv run pytest` resolves a stale interpreter shim. Use
> `uv run python -m pytest`. CI (a fresh checkout) is unaffected.

**The canonical recorded run is `~/.husk/traces.db`** (617 run rows = 500 parents + 117 replay children,
117 branches, 3,410 spans, 1,500,488 in / 478,284 out tokens) — an exact match for `hero_metrics.json`.
Several sibling backups exist (`.orig-bak`, `.groq-bak`, `.cerebras-bak`, `.smoke-bak`, `.toy-bak`); they
are earlier/other runs and are **not** the published dataset.

## 4. Claim-by-claim classification

| Claim | Backing code | Classification | Notes |
|---|---|---|---|
| 42.9% mean token bypass | [`graph.py:replay_from`](benchmark/research_agent/graph.py), [`hero_report.py`](benchmark/hero_report.py) (D5) | **Real, measured, rerunnable — but only with a live API key.** Not reproducible offline because `traces.db` is not committed. | The mechanism (checkpoint-resume skipping upstream nodes) is genuine and the SQL is sound. |
| 6.5× median wall-time speedup | `hero_report.py` (D1) | **Real, measured** (median 6.53×; mean 16.78× is right-skewed). Same offline-repro gap. | Paper correctly leads with the median and flags wall-time as noisy. |
| 100% replay success | `hero_report.py` (D4, Wilson) | **Real, measured** (117/117, Wilson [96.82, 100]). | "Success" = every replay produced a valid child run — not output-identical replay. |
| "Deterministic replay engine" / "replay without re-calling the model" | — | **Aspirational as worded.** What exists re-runs downstream nodes **against the real model**; only *upstream* nodes are skipped. True model-free replay (HTTP cassettes) is **stubbed**: [`http_proxy.py`](packages/husk-sandbox/src/husk_sandbox/http_proxy.py) is a no-op, [`replay/engine.py`](packages/husk-studio-backend/src/husk_studio_backend/replay/engine.py) raises `NotImplementedError`. | The paper is honest about this ("State replay ≠ output determinism", M2 roadmap). The README/deck oversell it. |
| Structural determinism (child re-runs exactly fork+successors, zero variance) | `graph.py:replay_from`, paper §7.4 | **Real, measured — but untested.** No automated test guards it. | This is the load-bearing, genuinely-deterministic property and the right thing to pin with a test. |

## 5. Architecture map (as found)

- **Recording.** Two paths: (a) sandbox JSONL events ([`tracer.py`](packages/husk-sandbox/src/husk_sandbox/tracer.py) → [`jsonl_reader.py`](packages/husk-studio-backend/src/husk_studio_backend/ingest/jsonl_reader.py)); (b) OTel/OTLP over HTTP ([`api/otel.py`](packages/husk-studio-backend/src/husk_studio_backend/api/otel.py) → [`otel_parser.py`](packages/husk-studio-backend/src/husk_studio_backend/ingest/otel_parser.py)). The benchmark uses path (b).
- **Storage.** SQLite via SQLAlchemy ([`db/models.py`](packages/husk-studio-backend/src/husk_studio_backend/db/models.py), [`db/engine.py`](packages/husk-studio-backend/src/husk_studio_backend/db/engine.py)). Tables: `runs`, `spans`, `snapshots`, `branches`, `http_cassettes`, `cursor_events`. `init_db` uses `create_all` with **no migrations and no format version** ("Alembic lands in M2").
- **Replay.** Real engine is [`langgraph_replay.py`](packages/husk-studio-backend/src/husk_studio_backend/replay/langgraph_replay.py) (dynamic import of the graph by `husk.graph_module`, checkpoint-resume via `update_state(as_node=predecessor) + invoke(None)`). [`replay/engine.py`](packages/husk-studio-backend/src/husk_studio_backend/replay/engine.py) is **dead** (NotImplementedError, never called).
- **Benchmark.** 5-node "Research Synthesizer" graph ([`research_agent/graph.py`](benchmark/research_agent/graph.py)); drivers `run_benchmark.py` (parents) + `real_replays.py` (replays, write `branches`); metrics `hero_report.py` + `bootstrap.py` (BCa + Wilson, self-tested).
- **UI.** React 19 + Vite + shadcn/ui. Working timeline ([`Timeline.tsx`](apps/studio/client/src/components/timeline/Timeline.tsx)), inspector, and replay page. Gaps in §7.
- **CLI/MCP.** `husk-ai start|demo|list|doctor|clean|mcp`; MCP exposes read tools + gated `replay_run`.

## 6. Sources of nondeterminism (as found)

| Source | Handled today? |
|---|---|
| LLM sampling / temperature / model drift | **No.** Downstream nodes re-call the real model on replay. (Cassettes will fix this — WS3.) |
| Upstream node re-execution | **Yes, deterministically skipped** via checkpoint-resume (the bypass). |
| Wall-clock / `datetime.now()` | No — not captured. |
| RNG | No — `snapshots.rng_state` column exists but is unused. |
| Tool side effects (network) | No today; will be cassette-covered when they ride httpx (WS3). |
| Tool side effects (local file/db) | No — out of scope; will be documented. |
| Concurrent ordering | LangGraph super-steps are deterministic for a fixed graph; documented. |
| Environment | Partial — replay `env_overrides` is allowlisted; general env not captured. |

## 7. Concrete defects / gaps found

1. **Numbers not offline-reproducible** — `traces.db` uncommitted; no single offline command. *(WS1)*
2. **No determinism test** — the strongest claim has zero guard. *(WS4)*
3. **Recording format unversioned** — no version field, no migration, silent-load risk. *(WS2)*
4. **`mypy --strict` never runs** — duplicate `tests` package name aborts it; not in CI either. *(WS5/WS7)*
5. **In-DB cost = $0** — [`pricing.py`](packages/husk-shared/src/husk_shared/pricing.py) lacks the OpenRouter `meta-llama/*` IDs used by the canonical run. *(WS1)*
6. **Dead code** — `replay/engine.py` stub. *(WS5)*
7. **Exceptions swallowed** — `jsonl_reader.py` drops bad lines / failed events with a log and continues; loose `dict[str, Any]` on the replay request surface. *(WS5)*
8. **UI: two dead buttons** ("Rewind to here", "Compare runs") with no handlers; **UI replays don't persist a branch row** (the `/api/v1/branches` POST is a 501 stub), so they never appear in metrics or as lineage; **token-bypass / parent→child is never visualized** — the core product story is invisible. *(WS5/WS6)*
9. **Documentation drift** — the docs disagree with each other and with the measured run:
   - Pitch [`HUSK_PITCH_DECK.md`](pitch/HUSK_PITCH_DECK.md) Slide 5: "250 runs / 247 / $0.068 / 48 replays / **4-node**"; Slide 7: "**34.7%** bypass [25.8, 43.2]", "0.2 ms / 660×" — all stale vs the real 500/117/**5-node**/42.9% run.
   - [`benchmark/README.md`](benchmark/README.md): describes a **4-node** graph, a **10k-run** benchmark, and says `metrics.sql` is the pitch source — superseded by the 5-node graph and `hero_report.py`.
   - [`README.md`](README.md)/deck ingest "~0.1 ms" and "~16 KB/trace" vs measured **0.65 ms** and **23.3 KB/trace**.
   - `benchmark/` and `pitch/` are **untracked in git** — not even in the history yet. *(WS7)*

## 8. Argued rewrites (per the brief: justify before doing)

- **HTTP-cassette replay (new, but user-requested):** the `http_cassettes` table + `snapshots.http_cassette_ref` already exist in the schema; the stubs ([`http_proxy.py`](packages/husk-sandbox/src/husk_sandbox/http_proxy.py), [`serializer.py`](packages/husk-sandbox/src/husk_sandbox/serializer.py), [`state.py`](packages/husk-sandbox/src/husk_sandbox/state.py)) are the intended scaffold. Implementing record/replay at the **httpx transport boundary** (the layer the OpenAI/Groq SDKs share) is the boring, well-worn approach (vcrpy-style) and turns the existing schema into a working feature rather than a rewrite.
- **No speculative rewrites otherwise.** The replay engine, metric pipeline, and BCa stats are sound and stay.

---

## After (updated as hardening lands)

*To be filled in as workstreams complete — before/after numbers, what is now true that wasn't, and what
was deliberately left undone with the reason.*
