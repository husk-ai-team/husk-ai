# Husk — Hardening Plan

Prioritized work to make the core promise hold, the numbers regenerable from one offline command, the
tool pleasant to run, and the architecture defensible. Ordered **correctness → cleanup → features**. Each
item lands in small, reviewable commits with the test suite green in between. See [AUDIT.md](AUDIT.md) for
the findings behind each item.

## Canonical numbers (single source of truth — every doc must match)
OpenRouter Llama-3.3-70B (`analyze`) + Llama-3.1-8B (others), 5-node graph, 500 parents / 117 replays:
**D5 token bypass 42.87%** [36.47, 49.53] (token-weighted 55.2%); **D1 16.78× mean** [13.05, 22.17], **median 6.53×**;
**D4 100%** (117/117) Wilson [96.82, 100]; **D3 max 89.39%**; ≈ **$2.95** provider-reported spend.

## P0 — Correctness (the load-bearing claims)
1. **Offline-reproducible numbers (WS1).** Export the canonical run to a committed, versioned fixture
   (`benchmark/fixtures/`); add `benchmark/reproduce.py` — one command, **no API key**, that regenerates
   D1/D3/D4/D5 and asserts they match `hero_metrics.json`. Fix `pricing.py` (OpenRouter `meta-llama/*` IDs)
   so cost ≠ $0; resolve the `n_parents=617` parent/child counting quirk.
2. **Recording-format versioning (WS2).** `RECORDING_FORMAT_VERSION` in `husk-shared`; stamp DB + fixture;
   load → migrate-or-fail-loudly; migration shim + test.
3. **Determinism tests (WS4).** Hermetic, no-API-key: (a) replay re-runs exactly `{fork ∪ successors}` with
   zero variance across N1–N4; (b) under cassette mode, identical-state replay → byte-identical outputs +
   **zero** provider calls. Red the instant replay drifts.

## P1 — The model-free replay feature (user-requested: "TUTTO")
4. **HTTP cassettes (WS3).** Record/replay httpx transports in `husk-sandbox`; stable request hash;
   persist to `http_cassettes`; HIT→recorded ($0, deterministic) / MISS→real provider; wire through
   `replay_from` / `/api/langgraph/replay` / MCP `replay_run` behind `HUSK_REPLAY_CASSETTE`. This makes
   "replay without re-calling the model" actually true and is the basis for WS4(b).

## P2 — Cleanup & architecture
5. **Backend refactor + error handling (WS5).** Delete dead `replay/engine.py`; persist branch rows on the
   replay endpoint (UI replays become first-class); implement `/api/v1/branches` + `/api/v1/diff` (or remove);
   stop swallowing exceptions; tighten public types; make `mypy --strict` actually run and pass.

## P3 — UX revolution
6. **Studio UX (WS6).** Remove/wire dead buttons; visualize parent→child lineage + tokens/cost bypassed +
   per-step cassette hit/miss; jump-to-step replay, live-vs-cassette toggle, auto-navigate to the new run;
   better tool-call rendering; a frontend smoke test. Verify with preview tools.

## P4 — DX, CI, docs
7. **CI + docs (WS7).** CI adds `mypy`, frontend `tsc`, and a benchmark smoke (run `reproduce.py` on the
   fixture). Add `.pre-commit-config.yaml`. Rewrite the README (clone → replayed run < 5 min, real numbers,
   exact one-command repro). Reconcile **all** docs (README, paper, benchmark/README, pitch deck) to the
   canonical numbers. Write `CHANGELOG.md`. Commit the currently-untracked `benchmark/` + `pitch/`.

## Verification (done = all green)
`uv run python -m pytest -q` (incl. determinism) · `uv run ruff check .` · `uv run mypy` ·
`uv run python benchmark/reproduce.py` (offline, matches `hero_metrics.json`) ·
Studio replay in cassette mode shows bypass + zero provider calls · CI bench-smoke passes ·
README quickstart reaches a replayed run in < 5 min.
