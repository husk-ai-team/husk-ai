# Husk benchmark — 500-run industrial case study (Groq + TriviaQA)

A **fully reproducible** benchmark that drives ~500 invocations of a 4-node
LangGraph "Research Synthesizer" through Husk using **real LLM calls** to
Groq and **real-world queries** from the TriviaQA dataset (Allen AI, ACL 2017).

Every hero metric carries a **Bootstrap BCa 95% CI** computed in pure Python
(`benchmark/bootstrap.py`, self-validated against Efron-Tibshirani 1993).

Pipeline:
```
TriviaQA (500 queries)  →  research_agent (LangGraph 4-node)  →  Groq llama-3.x
                                       ↓
                              Husk SQLite + spans
                                       ↓
                       real_replays.py → /api/langgraph/replay
                                       ↓
                         hero_report.py + cost_matrix.py + bootstrap.py
                                       ↓
                              HERO_METRICS.md + COST_MATRIX.md
```

Cost on Groq free/paid tier: **~$2-5 total**. Wall-time: ~40-60 min depending
on Groq rate-limit.

---

## What Husk is — and what it isn't

Before reading the numbers, please understand which **product category** they
belong to. The benchmark only makes sense if Husk is placed in the right
bucket. Investors and technical buyers smell the wrong bucket instantly.

| Category | Examples | Husk fits? |
|---|---|---|
| **AI proxy gateway / API observability** | Helicone, OpenLLMetry, OpenLIT | ❌ Different layer — Helicone & co. sit on the HTTP boundary between your agent and the LLM API. They never see your agent's internal state. |
| **Cloud LLM observability dashboard** | Langfuse (cloud), LangSmith (cloud), Datadog LLM, New Relic AI | ⚠️ Adjacent but cloud-first and generic. Citable as "neighbouring category", not as direct comparable. |
| **MLOps eval / dataset platforms** | Arize Phoenix, Braintrust, Weights & Biases | ❌ Eval and dataset curation, not interactive debugging. |
| **Visual / time-travel state debuggers** | **Replay.io** (JS), **rr** (Mozilla), **LangSmith Studio replay** (cloud) | ✅ **Husk's category.** Local in-process state inspection + modify-and-replay. |
| **Native IDE debuggers** | PyCharm debugger, VS Code Debug | ❌ Built for deterministic process state, not non-deterministic LLM flows. |

**Therefore**: claims like "Helicone customers report 90% debug time reduction"
are **not ground truth for Husk**. They measure something different
(replacing raw API log inspection with a dashboard view). Replay.io's
record/replay paradigm is the real precedent — same primitive (state-level
time travel), different language ecosystem.

---

## Why this scenario

A 4-node LangGraph pipeline (`query_expansion → retrieve → synthesize →
cite_check`) is the smallest realistic *deep-research agent* pattern and one
of the most common architectures in the wild (Perplexity, You.com, OpenAI
Deep Research clones, internal research bots).

LangGraph is also the only framework where Husk's modify-and-replay works
natively in M1 (checkpointer + `husk.graph_module`), so the benchmark's
hero metrics directly reflect product capability.

---

## Architecture

```
benchmark/
├── research_agent/
│   ├── __init__.py
│   ├── graph.py            ← 4-node LangGraph, OTel-instrumented, canned LLM
│   ├── mock_retrieve.py    ← deterministic mock for the retrieve tool call
│   └── prompts.py          ← system + user prompt templates
├── generate_topics.py      ← deterministic synthesis of 10k topic strings
├── inject_failures.py      ← controlled 20% failure schedule
├── run_benchmark.py        ← orchestrator (parallel ThreadPool)
├── metrics.sql             ← HERO metrics (DHV / DCS / MRTT) + supporting
│
├── baseline_replay.py      ← (illustrative-only) Monte-Carlo MTTR baseline
├── husk_replay_sim.py      ← (illustrative-only) Monte-Carlo MTTR Husk
│
└── empirical_study/        ← infrastructure-only, NOT in current pitch
    ├── protocol.md         #   (within-subjects crossover spec, ready
    ├── task_kit/           #    when post-funding budget allows
    ├── timing_template.csv #    recruiting 12-20 engineers — see the
    └── analysis.py         #    STATUS banner in protocol.md)
```

> **Current pitch evidence is SQL-only.** The hero metrics in the pitch
> come exclusively from `metrics.sql` (DHV / DCS / MRTT) extracted from
> the live SQLite database. Those numbers are objective COUNT/SUM
> aggregations on tables populated by the 10k-run benchmark — verifiable
> in 30 seconds by any technical reviewer.
>
> The two `*_replay*.py` scripts at the top level are **illustrative
> Monte-Carlo simulators**, not hero metric sources. The
> `empirical_study/` subtree is **infrastructure-ready but not yet
> conducted** (post-funding work).

---

## Reproducing the benchmark

### Prereqs

- Husk backend running locally (`uv run husk-ai start`)
- `uv sync --all-packages --group examples` (langgraph + OTel deps)

### Steps (current canonical pipeline)

```bash
# 1. Download 500 real-world queries from TriviaQA (~30 s)
uv run python benchmark/load_dataset.py --source triviaqa --n 500

# 2. Generate failure schedule (deterministic, seed=42)
uv run python benchmark/inject_failures.py -n 500

# 3. Start Husk backend in a separate terminal
uv run husk-ai start

# 4. Set Groq API key (env var, never committed) and run the benchmark
$env:GROQ_API_KEY = '<your-key>'  # PowerShell
# or: export GROQ_API_KEY=<your-key>  # bash/zsh
BENCH_FAST=1 uv run --group examples python benchmark/run_benchmark.py \
    --runs 500 --topics benchmark/queries_500.jsonl --concurrency 4

# 5. Trigger REAL replays via Husk's /api/langgraph/replay API
#    (one replay per failed parent run; honest DHV = 1.0, no inflation)
uv run python benchmark/real_replays.py

# 6. Extract hero metrics with BCa CI 95%
uv run python benchmark/hero_report.py --out benchmark/HERO_METRICS.md

# 7. Cross-provider cost equivalence table
uv run python benchmark/cost_matrix.py --from-db --out benchmark/COST_MATRIX.md
```

### Legacy / illustrative-only scripts (NOT pitch sources)

```bash
# Monte-Carlo simulators kept only for sanity-checking ranges.
# Outputs are NOT cited in the pitch — they are tautological.
uv run python benchmark/baseline_replay.py -n 200
uv run python benchmark/husk_replay_sim.py -n 200

# Synthetic 10k benchmark (canned LLM, fake token counts) -- LEGACY
# Provided only for those who want to see what the synthetic path looks
# like without spending Groq tokens.
uv run python benchmark/generate_topics.py -n 10000
uv run python benchmark/run_benchmark.py --runs 10000
```

### Future work (post-funding)

```bash
# Run the within-subjects MTTR empirical study (requires 12-20 engineers
# + €1.500 honoraria + 30h researcher time -- infrastructure ready in
# benchmark/empirical_study/).
uv run python benchmark/empirical_study/analysis.py
```

### Timing modes

`run_benchmark.py` defaults to `--fast` (per-node latency collapsed to ~1 ms)
so 10k runs complete in minutes on a modern laptop. Pass `--realistic-timing`
to keep the per-node latencies a real agent would experience (~24 s/run,
~67 h for the full 10k). All hero metrics are derived from SQL on the
recorded spans, so both modes produce the same outcome distribution.

---

## Hero metrics -- measured with real LLM calls + BCa CI 95%

The current canonical pitch numbers come from `benchmark/hero_report.py`,
which extracts three metrics directly from the live SQLite + computes BCa
Bootstrap 95 % confidence intervals on 10,000 resamples.

### H1 -- Token Bypass Rate

**Question**: *"How many LLM tokens does Husk's state replay deterministically
skip per branch, as a percentage of full-graph token cost?"*

**Computation**: for each row in `branches`, sum `tokens_in + tokens_out` of
the LLM spans in the parent run that lie at or before the fork point. Divide
by the parent run's total LLM tokens. Aggregate across all branches; report
mean + BCa CI 95%.

**Why this is unique**: every other LLM observability tool *observes*. None
of them lets the engineer skip upstream work on a re-run. Token Bypass Rate
is a deterministic primitive only Husk exposes today.

### H2 -- Husk Ingest Overhead (ms)

**Question**: *"What latency does Husk add to each emitted OTel span?"*

**Computation**: measured as the wall-clock gap between agent.run started_at
and the first child span landing in `~/.husk/traces.db`. Per-run sample,
aggregated to mean + p50 + p95 with BCa CI.

**Reference points**:
- Langfuse SDK: 0.1 ms (batched async, optimised)
- LangSmith median: 132 ms (network round-trip to cloud)
- Husk: local SQLite write, no network hop

### H3 -- Storage Efficiency

**Question**: *"How many bytes does Husk store per recorded trace?"*

**Computation**: `(traces.db file size) / (count of parent runs)`. Single
scalar; no CI needed.

**Why it matters**: cloud vendors charge per GB ingested ($0.10/GB Datadog,
1-10 GB tiers Helicone). Husk's footprint is bounded only by local disk;
infinite retention at $0 recurring cost.

### Supporting metrics (also from `metrics.sql`)

- Total runs / spans / branches
- Outcome distribution (success / error / aborted)
- Failure breakdown by injected mode (N1-N4)
- % failed runs with ≥1 replay
- Token / cost totals + per-model breakdown
- Run wall-time distribution + per-node mean latency

---

## Ground truth bounds (cited in the pitch)

These external numbers anchor the benchmark in published reality. They are
**not equivalences** — they are bounds and validation points.

### Time-travel debugging is a validated category

- **Replay.io** — record/replay debugger for JS/Node, raised $43M Series B
  (2022). Validates that time-travel state debugging is a market that
  engineers pay for. *This is the closest technological precedent for Husk.*
- **rr** (Mozilla) — record/replay native debugger on Linux, peer-reviewed
  papers + adopted by kernel & browser teams. Validates that deterministic
  state replay is a primitive engineers rely on.

### Multi-agent failure rate validation

The benchmark's 20 % injected failure rate is **conservative** by published
evidence:

- **MAST taxonomy** (Multi-Agent System failure paper): 41.8 % specification
  problems, 36.9 % inter-agent misalignment, 21.3 % task verification — total
  failure rate well above 20 % on real MAS benchmarks.
- **SWE-bench**: state-of-the-art agents resolve ~50 % of issues, meaning
  >30-40 % failure rate is normal in dev/staging.
- **RAG production studies**: 80 % of enterprise RAG projects fail at
  deployment; 73 % of RAG errors originate in retrieval (not generation).
  This validates the per-node distribution in the benchmark (N2 retrieve
  failures present, plus synthesize & cite_check failures downstream).

### Developer experience pain — Stack Overflow 2025 Survey

- 66 % of developers are frustrated by "almost-right" AI-generated code.
- 45 % explicitly report that debugging AI-generated code **takes longer**
  than debugging traditional code.
- 87 % are concerned about agent accuracy.
- 46.2 % find it hard to integrate agent observability into their workflow.

→ This is the *validated pain* that justifies the product. Husk doesn't need
to simulate this — it's the documented status quo.

### Adjacent-category outcomes (citable for market sizing, NOT as
Husk-equivalent performance)

- **LangSmith** — 550k hours saved aggregated across customers; ServiceNow,
  Harmonic, Klarna as named case studies. Cloud-first LLM observability,
  adjacent to Husk.
- **Klarna AI assistant retro** — 80 % MTTR reduction on support root-cause
  analysis. Adjacent product category (customer-support AI), useful only as
  evidence that "AI ops debugging" is worth hours/week to enterprises.

---

## Volume calibration

The 10k-run benchmark looks bloated only when miscontextualised. Calibrated:

| Segment | Engineers | Estimated runs/month | Failures (20-30 %) |
|---|---:|---:|---:|
| Single dev team (seed/Series A) | 5-15 | 10.000 - 15.000 | 2.000 - 4.500 |
| Mid-size company | 50-100 | 50.000 - 100.000+ | 10.000 - 30.000 |
| Enterprise (e.g. Arize public scale) | 100+ | 1.000.000+ | tracked via CI/evals |

10k runs ≈ **one month for a 10-engineer dev team** running RAG/LangGraph
pipelines ~50 times/day across dev + staging. Realistic, not inflated.

---

## Methodological caveats (the pitch states these explicitly)

1. **State replay ≠ output determinism.** M1 guarantees perfect restore of
   the LangGraph state JSON at a checkpoint. The LLM at the next node remains
   stochastic. Full output determinism (HTTP cassette + provider mocking) is
   on the M2 roadmap.
2. **Sequential graphs ≠ concurrent multi-agent systems.** The visual
   timeline excels on directed graphs (LangGraph, RAG chains). Truly async
   MAS with messaging race conditions are out of scope for the MVP.
3. **API cost saved ≠ total cost of ownership saved.** DCS measures tokens
   bypassed at OpenAI/Anthropic. It does not include local compute, network
   latency, or self-hosted vector DB costs.
4. **20 % failure rate = "dev/staging imperfections".** Includes tolerable
   hallucinations and imperfect retrievals (aligned with the 66 % SO 2025
   frustration figure). It is **not** unhandled exceptions or production
   crashes.
5. **No human MTTR claim in this pitch.** The Monte-Carlo simulators
   (`baseline_replay.py`, `husk_replay_sim.py`) are kept for sanity-
   checking ranges only — they are **not pitch sources**. A real
   within-subjects MTTR study (full protocol in `empirical_study/`)
   would require recruiting 12-20 external engineers, which is outside
   the pre-seed in-house budget. The current pitch makes **zero claims
   about human time saved** and stays exclusively on the three
   SQL-objective hero metrics.

---

## File outputs

After a full run you have:

- `topics.jsonl` — 10k input topics
- `failure_schedule.jsonl` — per-index failure mode
- `results_run.jsonl` — per-run summary (status, error_node, thread_id)
- `~/.husk/traces.db` — the canonical record (consulted by `metrics.sql`)
- `results.txt` — output of `metrics.sql` (the pitch source)
- Optional: `baseline_mttr.jsonl`, `husk_mttr.jsonl` — illustrative MC samples
- Empirical study: `empirical_study/results/` — paired T-test + CI 95% data

Every hero number on the pitch deck must trace back to a column in
`results.txt` (from `metrics.sql`) or to the empirical study's analysis.
