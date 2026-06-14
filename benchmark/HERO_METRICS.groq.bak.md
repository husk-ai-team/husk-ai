# Husk benchmark -- hero metrics (Groq + Bootstrap BCa)

- Source: `C:\Users\monti\.husk\traces.db` (live SQLite)
- Filter: parent runs with `started_at >= 0`
- CI methodology: BCa Bootstrap, 10,000 resamples (benchmark/bootstrap.py)
- Self-validated against Efron-Tibshirani 1993 GPA example.

## Volume

- Parent runs in this benchmark: **51**
  - real Groq LLM calls: **51**
- Failed parent runs: **11** (21.57%)
- Total Groq spend: **$0.0410**
- Token consumption: 103,992 in / 34,535 out

Failure breakdown by injected mode:
  - N3: 5
  - N4: 3
  - N2: 2
  - N1: 1

## D1 -- Replay Wall-Time Speed-up (PRIMARY HERO)

**3.28x faster** -- mean wall-time of a replay vs the parent's full run (95% CI [1.77x, 5.16x], n=11)
- p50: 2.58x   p95: 8.4x   max: 8.4x

**Why this matters:** every replay short-circuits the upstream nodes.
The wall-clock saving compounds with every iteration in a debug cycle.

## D2 -- Token Bypass Rate per failure mode

| Failure mode | Mean bypass | 95% CI | Max | n |
|---|---:|---:|---:|---:|
| N1 | 50.51% | [50.51, 50.51] | 50.51% | 1 |
| N2 | 0.0% | [0.0, 0.0] | 0.0% | 2 |
| N3 | 25.17% | [6.36, 41.8] | 42.69% | 5 |
| N4 | 81.66% | [70.64, 87.28] | 87.51% | 3 |

**Why this matters:** failures late in the graph bypass more
upstream tokens than failures at the start. The pitch quotes
the *max-mode* row (best realistic case in production).

## D3 -- MAX Token Bypass Observed

**Best single replay: 87.51% of LLM tokens bypassed** (across n=11 replays)

## D4 -- Replay Success Rate

**100.0% replays produced a valid child run** (11/11)

This is the empirical reliability of the modify-and-replay flow.

## D5 -- Mean Token Bypass Rate (baseline)

**38.3% mean bypass** (95% CI [19.4, 57.86], n=11)

Across all branches: **13,236 tokens** bypassed out of **27,253** that would have been re-paid in a full re-run.

---

## Supporting (infrastructure footnote, not hero)

- **Husk ingest overhead**: mean 3.18 ms (95% CI [1.14, 7.49], p50=0.0 ms, p95=42.0 ms). Comparable: Langfuse 0.1 ms (batched), LangSmith 132 ms (cloud RTT).
- **Storage**: 24,174.4 bytes / trace (1.176 MB DB total). Comparable: Datadog $0.10/GB; Helicone 1-10 GB tiers.

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