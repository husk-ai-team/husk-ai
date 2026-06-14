# Husk benchmark -- hero metrics (OpenRouter Llama + Bootstrap BCa)

- Source: `C:\Users\monti\.husk\traces.db` (live SQLite)
- Filter: parent runs with `started_at >= 0`
- CI methodology: BCa Bootstrap, 10,000 resamples (benchmark/bootstrap.py)
- Self-validated against Efron-Tibshirani 1993 GPA example.

## Volume

- Parent runs in this benchmark: **500** (+ 117 replay children = 617 total recorded traces)
  - with real LLM calls: **500**
- Failed parent runs: **117** (23.4%)
- LLM spend (list-price estimate over recorded tokens): **$0.5862**
- Token consumption: 1,500,488 in / 478,284 out

Failure breakdown by injected mode:
  - N4: 38
  - N3: 38
  - N2: 26
  - N1: 9

## D1 -- Replay Wall-Time Speed-up (PRIMARY HERO)

**16.78x faster** -- mean wall-time of a replay vs the parent's full run (95% CI [13.1x, 21.98x], n=117)
- p50: 6.53x   p95: 52.14x   max: 136.94x

**Why this matters:** every replay short-circuits the upstream nodes.
The wall-clock saving compounds with every iteration in a debug cycle.

## D2 -- Token Bypass Rate per failure mode

| Failure mode | Mean bypass | 95% CI | Max | n |
|---|---:|---:|---:|---:|
| N1 | 0.0% | [0.0, 0.0] | 0.0% | 9 |
| N2 | 0.0% | [0.0, 0.0] | 0.0% | 26 |
| N3 | 43.09% | [42.68, 43.51] | 45.73% | 38 |
| N4 | 87.92% | [87.68, 88.17] | 89.39% | 38 |
| unknown | 6.15% | [1.75, 10.26] | 14.17% | 6 |

**Why this matters:** failures late in the graph bypass more
upstream tokens than failures at the start. The pitch quotes
the *max-mode* row (best realistic case in production).

## D3 -- MAX Token Bypass Observed

**Best single replay: 89.39% of LLM tokens bypassed** (across n=117 replays)

## D4 -- Replay Success Rate

**100.0% replays produced a valid child run** (117/117) — 95% CI [96.82%, 100.0%] (Wilson)

This is the empirical reliability of the modify-and-replay flow.

## D5 -- Mean Token Bypass Rate (baseline)

**42.87% mean bypass** (95% CI [36.44, 49.4], n=117)

Across all branches: **184,473 tokens** bypassed out of **334,393** that would have been re-paid in a full re-run.

---

## Supporting (infrastructure footnote, not hero)

- **Husk ingest overhead**: mean 0.65 ms (95% CI [0.53, 0.79], p50=0.0 ms, p95=5.0 ms). Comparable: Langfuse 0.1 ms (batched), LangSmith 132 ms (cloud RTT).
- **Storage**: 23,268.2 bytes / trace (13.691 MB DB total). Comparable: Datadog $0.10/GB; Helicone 1-10 GB tiers.

## Reproducibility

```bash
uv run python benchmark/load_dataset.py --source triviaqa --n 1000
uv run husk-ai start   # in another terminal
$env:GROQ_API_KEY = '<your key>'
BENCH_FAST=1 uv run --group examples python benchmark/run_benchmark.py \
    --runs 1000 --topics benchmark/queries_1000.jsonl --concurrency 6
uv run --group examples python benchmark/real_replays.py --limit 250
uv run python benchmark/hero_report.py --out benchmark/HERO_METRICS.md
uv run python benchmark/cost_matrix.py --from-db --out benchmark/COST_MATRIX.md
```