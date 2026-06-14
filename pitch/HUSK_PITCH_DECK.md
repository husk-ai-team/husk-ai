# Husk -- Pre-seed Pitch Deck (10 slides)

> Format: Kawasaki 10/20/30, Sentry / Honeycomb seed template. Each slide is
> one screen of text, designed to be transferred 1:1 to Keynote/PPTX with
> minimal layout work. Numbers in `{curly}` are placeholders filled in by
> `benchmark/hero_report.py` once the 500-run Groq + TriviaQA benchmark
> completes.

---

## Slide 1 -- Cover

**Husk**

Time-Travel State Debugging for AI Agents.

*Stop guessing what your agent did. Re-run from the failure, in seconds.*

`github.com/husk-ai-team/husk-ai` -- BUSL-1.1 (Apache 2.0 from 2030)

---

## Slide 2 -- The Problem (validated by public data)

**AI agents fail. A lot. And debugging them costs real time.**

- **45.2%** of developers report debugging AI-generated code takes **longer**
  than writing it from scratch -- Stack Overflow 2025 Developer Survey
  (N>49,000).
- **66%** are frustrated by "almost-right" AI output.
- **46%** actively distrust AI output (up from 31% in 2024).
- **MAST taxonomy** (2025 paper, 1,642 traces / 7 frameworks): aggregate
  multi-agent failure rates of **41% to 86.7%**, dominated by specification
  errors (44%) and inter-agent state misalignment (32%).

The tools developers reach for today -- `print()`, log diffs, full re-runs
-- are 1995-grade for a 2025 problem.

---

## Slide 3 -- What's Missing in the Status Quo

Today's LLM observability stack tells you **what** broke. None of it lets you
**modify the state at a checkpoint and replay deterministically**.

| Layer | Examples | What they do |
|---|---|---|
| Cloud dashboards | LangSmith, Langfuse, Datadog LLM | passive traces, post-mortem |
| Proxy gateways | Helicone, OpenLLMetry | log API calls, cache, route |
| Eval platforms | Arize Phoenix, Braintrust | dataset scoring, regression check |
| **Time-travel debuggers** | **Replay.io ($43M Series B), rr (Mozilla)** | **the primitive we bring to AI agents** |

Cloud dashboards charge per-trace ($0.50/1k LangSmith overage, $8/10k req
Datadog) and cap retention to 14-90 days. Husk: local SQLite, infinite
retention, $0 recurring.

---

## Slide 4 -- Husk MVP

A visual debugger + state replay engine that lives in your terminal.

- **Visual timeline** of every LLM call, tool call, agent decision -- unified
  view from any framework (LangChain, LangGraph, OpenAI Agents SDK, AutoGen,
  CrewAI, plain Python+OTel).
- **Modify-and-replay** on LangGraph: Monaco editor on the state JSON at
  any checkpoint, click "Run from here" -> branch in a new run.
- **100% local**: FastAPI backend on `:7654`, React Studio at `/`, SQLite
  in `~/.husk/`. No cloud, no telemetry, no signup.
- **Standard OTel/GenAI v1.36+** ingest -- works with any agent that already
  emits spans.

Install:
```bash
git clone github.com/husk-ai-team/husk-ai && cd husk-ai
uv sync --all-packages
uv run husk-ai start
```

---

## Slide 5 -- The Benchmark

**Methodology, declared explicitly.** No Monte-Carlo, no canned LLMs.

- **500 real LangGraph runs** of a 5-node research agent
  (`query_expansion -> retrieve -> analyze -> synthesize -> cite_check`), the
  Plan-then-Execute shape where the costly `analyze` step is upstream.
- **Real LLM calls on OpenRouter** -- `meta-llama/llama-3.3-70b-instruct`
  (analyze) + `meta-llama/llama-3.1-8b-instruct` (the rest). Tokens and
  latencies from the provider. Live billing ≈ **$2.95 / €2.73** (routing +
  retries); list-price cost of the recorded tokens ≈ **$0.59**.
- **Real-world queries** from the **TriviaQA dataset** (Allen AI, ACL 2017).
  Industry-standard QA benchmark, 96k human-authored questions.
- **20% failure rate injected** -- validated as *conservative* against MAST
  taxonomy (41-86% failure rate measured in the 2025 multi-agent literature).
- **117 real replays** via the same `replay_graph` engine that Husk's
  `/api/langgraph/replay` exposes -- one per failed parent; spans land in
  `~/.husk/traces.db` via the standard OTel ingest path.
- **Bootstrap BCa CI 95%** (Efron-Tibshirani 1993) on 10,000 resamples,
  pure-Python (no scipy), self-validated against the canonical GPA example.
- **Reproduce offline in seconds, no API key:** `uv run python
  benchmark/reproduce.py` regenerates every figure from a committed fixture.

---

## Slide 6 -- Hero Numbers (measured, from `benchmark/HERO_METRICS.md`)

> **Re-measured after fixing the replay engine.** The engine now does a true
> LangGraph checkpoint resume (`update_state` + `invoke(None)`) instead of a
> full re-run — verified independently: a resumed child emits strictly fewer
> LLM spans than its parent (only the fork node + its successors execute).
> Measured on a realistic graph where an expensive upstream `analyze` node
> dominates cost — the canonical **Plan-then-Execute** pattern (costly
> reasoning early, cheap formatting late; cf. arXiv:2509.08646). **n=117 replays**
> over 500 parent runs, Llama-3.3-70B + 3.1-8B, matched timing.

| # | Metric | Value (CI 95%) | Note |
|---|---|---|---|
| H1a | **Token Bypass Rate** | **42.9% mean** [36.4, 49.4], n=117 | was **1.23%** before the fix; **max 89.4%** |
| H1b | **Replay Wall-Time Speed-up** | **median 6.5×** (mean 16.8× [13.1, 22.2]), n=117 | was **0.56×** before; wall-time noisy¹ |
| H1c | **Replay Success Rate** | **100%** (117/117), Wilson 95% CI **[96.8%, 100%]** | every replay produced a valid child run |
| H2 | **Husk Ingest Overhead** | **0.65 ms** (p50 0, p95 5) | Langfuse 0.1 ms / **LangSmith 132 ms (cloud RTT)** |
| H3 | **Storage Efficiency** | **~23 KB / trace** | Datadog $0.10/GB + $1.70/M events |

**Bypass scales with failure depth (D2, measured).** A replay skips every node
*upstream* of the fix point, so the saving depends on where the failure is:

| Failure mode | Re-runs | Token bypass (n) |
|---|---|---|
| **N4** — after the costly `analyze` node | `cite_check` only | **87.9%** (n=38) |
| **N3** — at `synthesize`, downstream of `analyze` | `synthesize`+`cite_check` | **43.1%** (n=38) |
| **N2 / N1** — at/before the costly node | must re-run `analyze` | **~0%** (n=26 / n=9) |

**Reading H1**: when a failure lands *downstream of the expensive work* — the
common case in real agents — a Husk replay deterministically skips that work,
bypassing the bulk of the LLM token cost and returning many× faster. The
primitive is new; no competitor offers state-level modify-and-replay (and none
publishes efficiency numbers with a sample size or confidence interval at all).

¹ *Token bypass (H1a) is the robust, provider-independent number. H1b is a
matched-timing measurement (parents and replays both run with node sleeps off →
wall-time = real LLM-API latency), but wall-time on a shared inference endpoint
is variable; read it as "easily ≥2×, point ~17×", not a precise constant. CIs
are BCa bootstrap (10k resamples); success rate uses a Wilson interval. Per-mode
N1/N2 are thinner (n=9/26) — pooled H1a is the headline. Cross-provider USD
conversion via `benchmark/cost_matrix.py`.*

---

## Slide 7 -- Competitor Positioning Matrix

Public pricing pages, vendor blog posts, customer case studies -- not made up.

| Tool | Layer | Entry $ | SDK overhead | Retention | Public claim |
|---|---|---|---|---|---|
| LangSmith | cloud dashboard | $39/u/mo | 132 ms | 14-400 d | Podium -90% manual review |
| Langfuse | OSS / cloud dashboard | $29/mo, free OSS | 0.1 ms | 30 d - 3 y | 1k-20k req/min ingest |
| Arize Phoenix | OSS / cloud OTel | $50/mo (AX Pro) | OTel | 15-30 d | Kafka, VPC isolation |
| Braintrust | eval platform | $249/mo | n/a | 14-30 d | -60% eval time |
| Helicone | proxy gateway | $79/mo | proxy hop | 1-10 GB | "386h saved via cache" |
| Datadog LLM | cloud APM | $8/10k req + APM | std | 15 d | (multi-product tax) |
| Replay.io | JS time-travel | $299/mo | record | n/a | MTTR 2-8h -> <30 min |
| **Husk** | **local state replay** | **$0 OSS** | **0.65 ms (~200x faster than LangSmith)** | **infinite (local)** | **42.9% Token Bypass Rate [36.4, 49.4]** |

(Full sources: `benchmark/competitor_matrix.md`.)

---

## Slide 8 -- Market & Wedge

**TAM**: every developer who uses an AI agent in their workflow.
- 84% of developers use AI tools today (SO 2025).
- Of those, **46%** distrust the output -- and they all need to debug.

**Wedge**: developer experience, bottom-up adoption, BUSL 1.1 OSS.
- Mirror of Sentry's path (David Cramer 2012-2014): build the cruda utility
  first, validate adoption locally, monetise enterprise orchestration later.
- **Husk Cloud** (M3+): optional sync, team collaboration, audit log --
  never required.

---

## Slide 9 -- Team & Execution

- **Founders**: Edoardo Bambini, Alessandro Citzia, Serena Mazzeo,
  Fabrizio Pelella (Italy).
- 4 engineers, full-stack -- Python/FastAPI backend, React/TS frontend,
  TypeScript IDE bridges (Cursor, VS Code).
- **Built in 3 months pre-seed**: working MVP, OSS published, benchmark
  reproducible **offline in seconds** (committed fixture, `reproduce.py`) or
  end-to-end with real LLM calls in ~30 minutes.

**Roadmap**:
- M1 -- visual timeline + LangGraph state replay
- M2 (**shipped**) -- HTTP cassette → model-free, byte-identical replay (zero
  provider calls); offline-reproducible benchmark; versioned recordings
- M3 (in progress) -- branching/diff UI (lineage + token-bypass already live);
  generic state snapshot beyond LangGraph; Husk Cloud (opt-in)

---

## Slide 10 -- The Ask

Looking for **pre-seed funding** to:

1. Extend model-free replay (HTTP cassettes, shipped for LangGraph) across
   any framework — generic state snapshot + cassette capture beyond LangGraph.
2. **Run the empirical study** (within-subjects crossover, N=15-20 engineers,
   paired T-test on MTTR) -- protocol is already coded in
   `benchmark/empirical_study/`. Roughly €1.500 + 30 h researcher time.
3. Hire one DX-focused engineer for the Studio UI polish + Husk Cloud
   (opt-in sync, never required).

**Why now**: every LLM observability vendor is racing to capture
post-mortem traces. None of them owns the *during-debug* primitive --
modify, replay, branch. The window to claim it is 12 months.

---

## Methodological honesty (spoken during the demo)

> *"We refused to publish Monte-Carlo MTTR numbers because they are
> tautological. We integrated 500 real TriviaQA queries through Groq,
> applied BCa Bootstrap on 10,000 resamples to bound every hero metric
> with 95 % CIs. We do not yet have a human-MTTR study -- our 4-founder
> team allocated zero budget to academic honoraria. The within-subjects
> crossover protocol that would produce it is already coded in the repo,
> ready to execute the day the round closes."*

This sentence buys credibility you can't synthesize.
