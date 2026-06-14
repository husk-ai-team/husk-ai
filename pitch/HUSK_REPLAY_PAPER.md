# Measured State-Level Modify-and-Replay for LLM Agents: A Checkpoint-Resume Primitive and Its Token/Latency Savings

**Husk — Technical Report**
*Draft v1. All figures are measured; this is an internal/technical-DD artifact, not a peer-reviewed publication.*

---

## Abstract

Debugging an LLM agent today usually means re-running it from scratch: every fix re-pays the full
token cost and wall-clock latency of the entire graph, even when the failure is in a late step.
We describe and **measure** a *state-level modify-and-replay* primitive built on LangGraph's
checkpointing: resume an existing run from the checkpoint at the failing node, apply a state patch,
and re-execute **only that node and its successors**, deterministically bypassing all upstream work.

We found that our own initial implementation did not do this — it re-ran the whole graph with a fresh
thread id (measured token bypass **1.23%**, wall-time **0.56×**, i.e. *slower* than the parent). We
fixed it to perform a true checkpoint resume (`update_state(..., as_node=predecessor)` +
`invoke(None)`), and re-measured on a 5-node "Research Synthesizer" graph shaped like the canonical
Plan-then-Execute pattern (expensive reasoning upstream, cheap formatting downstream), over **500
parent runs and 117 replays** on OpenRouter (Llama-3.3-70B + Llama-3.1-8B), with matched timing and
BCa-bootstrap / Wilson confidence intervals.

**Headline measured results (n=117 replays):** mean per-replay **token bypass 42.9%** (95% CI
[36.5, 49.5]; token-weighted aggregate **55.2%**, 184,473 of 334,393 LLM tokens); **replay success
100%** (Wilson 95% CI [96.8%, 100%]); **wall-time speed-up median 6.5×** (mean 16.8× but
right-skewed — see §10). Bypass scales with failure depth: **87.9%** for failures downstream of the
costly node (N4), **43.1%** mid-graph (N3), and **~0%** for failures at or before it (N1/N2) — the
latter being a structural floor, not a defect. We report limitations frankly: a single synthetic
topology/model/provider/dataset, self-reported numbers, wall-time noise on a shared endpoint, and
the fact that the replay *primitive* is LangGraph's — Husk's contribution is the productized
debugger, the local trace store, and the **measurement**.

---

## 1. Introduction

Production LLM agents are graphs of LLM calls and tools. When one fails — a hallucinated citation, an
empty retrieval, a malformed plan — the standard developer loop is: edit a prompt or some state, then
**re-run the whole agent**. Every iteration re-pays the full token bill and the full latency of every
node, including the expensive upstream steps that were already correct.

Husk is a local-first visual debugger and replay engine for agents. Its central claim is a
*state-level modify-and-replay* primitive: pause at a checkpoint, change the state, and re-run only
what's downstream — turning a full re-execution into a partial one. The intuition is simple: the
outputs of the nodes before your fix are already computed and persisted, so they need not be re-paid.

This report does three things:

1. **Documents a real failure of our own first implementation** (it silently performed a full
   re-run) and the fix that makes the primitive actually skip upstream work.
2. **Defines a benchmark and five metrics** (D1–D5) for replay efficiency, with proper confidence
   intervals — a discipline absent from comparable commercial claims.
3. **Reports measured results** with an explicit account of what is robust (token bypass; replay
   reliability), what is noisy (wall-clock speed-up on a shared inference endpoint), and what is out
   of scope (generality across topologies, models, providers, and real workloads).

**Contributions.** (i) A precise statement and correctness argument for the checkpoint-resume
primitive on LangGraph; (ii) an empirical, CI-bearing benchmark of token bypass, wall-time speed-up,
and replay reliability; (iii) a structural proof that upstream nodes are deterministically skipped;
(iv) an honest limitations analysis positioning the work against LangGraph's native time-travel and
against commercial observability tools.

---

## 2. Background

**LangGraph checkpointing & time-travel.** LangGraph persists a checkpoint after every super-step of
a graph keyed by a `thread_id`. Its "time-travel" API exposes `get_state` / `get_state_history`,
`update_state(config, values, as_node=...)`, and resumption via `invoke(None, config)`.
`update_state` applies `values` to the channels *as if produced by node `as_node`*, which sets the
graph's `next` tasks to `as_node`'s successors; a subsequent `invoke(None, config)` resumes from
there without injecting new input. This is the mechanism Husk builds on.

**OpenTelemetry GenAI.** Husk ingests OpenTelemetry traces using the GenAI semantic conventions
(v1.36+): each LLM call is a span carrying `gen_ai.usage.input_tokens` / `output_tokens`,
`gen_ai.request.model`, etc. Token accounting in this report is taken directly from these spans, not
estimated.

**Cost asymmetry of agent topologies.** In the dominant *Plan-then-Execute* pattern, an expensive
reasoning/planning (or retrieval/analysis) step runs early and cheaply-callable executors/formatters
run late. The token cost is therefore concentrated *upstream*. This asymmetry is exactly what makes
downstream replay valuable, and it motivates our benchmark graph's shape (§6).

---

## 3. System and the Primitive

**Architecture.** Husk is local-first: a FastAPI backend (`:7654`) ingests OTel spans into a local
SQLite store (`~/.husk/traces.db`), a React "Studio" UI renders run timelines, and a replay engine
re-invokes instrumented LangGraph graphs. The graph under test persists LangGraph checkpoints to a
separate SQLite checkpointer (`~/.husk/benchmark_research.sqlite`).

**The bug.** The original replay engine resolved the graph from a run's `husk.graph_module` span
attribute and then called the graph's `invoke(state_override, thread_id=<fresh uuid4>)`. With a fresh
thread id and a full input state, LangGraph had no checkpoint to resume from, so it **re-executed
every node**. The SqliteSaver was configured but only ever *written*, never used to *resume*. Net
effect: every "replay" was a full re-run with a different initial state — measured token bypass
**1.23%** and wall-time **0.56×** (i.e. the replay was *slower* than the parent, due to import/setup
overhead on top of identical work).

**The fix.** We added `replay_from(state_override, parent_thread_id, fork_node)`:

1. Build `config = {"configurable": {"thread_id": parent_thread_id}}` — resume the parent's thread
   from its latest checkpoint.
2. Apply the patch *at the predecessor of the node to re-run*:
   `graph.update_state(config, values, as_node=PREDECESSOR[fork_node])`, where `values` also clears
   the parent's stale failure channels (`{failure_mode: None, status: None, error_node: None}`) so a
   "fixed" child does not inherit the parent's error state.
3. Resume with `graph.invoke(None, new_config)`.

The off-by-one is load-bearing: to *re-run* node X, `as_node` must be X's **predecessor** (so X's
predecessor's channels are re-written and X's successors fire). `update_state` runs only the node's
channel writers, not its Python function, so neither the predecessor nor any upstream node is
re-executed — they emit no spans and consume no tokens. A fresh `husk.replay.child_id` attribute is
written on the child's root span so the replay can be located unambiguously (parent and child share a
`thread_id`). The path is gated: it activates only when both `parent_thread_id` and `fork_node` are
present and the graph exposes `replay_from`; otherwise the engine falls back to the original full
re-run, preserving backward compatibility for the `/api/langgraph/replay` HTTP endpoint and the UI.

**Correctness / mechanism.** For a linear graph, resuming after `update_state(as_node=predecessor(X))`
executes exactly `{X} ∪ successors(X)`. Therefore the set of re-paid LLM nodes is precisely the nodes
at-or-after the fork, and the **bypassed** token cost equals the sum over strictly-upstream LLM
nodes. This is a deterministic property, not a heuristic; §8.3 verifies it empirically (child LLM-span
counts are exactly fork-node + successors, with zero variance).

---

## 4. Metrics and Statistics

All metrics are computed by SQL over the `runs`, `spans`, and `branches` tables of the live trace DB
and are attached confidence intervals.

| ID | Metric | Definition |
|----|--------|------------|
| **D1** | Wall-time speed-up | `parent_duration / child_duration` per replay (durations = `finished_at − started_at`). |
| **D2** | Token bypass by failure mode | D5 stratified by the parent's injected failure mode (N1–N4). |
| **D3** | Max token bypass | Maximum single-replay bypass observed. |
| **D4** | Replay success rate | Fraction of replays that produced a valid child run. |
| **D5** | Mean token bypass | Mean over replays of `(1 − child_llm_tokens / parent_llm_tokens)`, clamped at 0; "LLM tokens" = sum of `tokens_in + tokens_out` over `kind='llm'` spans. |

**Confidence intervals.** Continuous metrics (D1, D2, D3, D5) use the **Bias-Corrected and
Accelerated (BCa) bootstrap** with 10,000 resamples (Efron & Tibshirani 1993), implemented in pure
Python and self-validated against the canonical Efron law-school GPA example. The replay success rate
(D4) is a binomial proportion and uses the **Wilson score interval**, which is well-behaved at
`p ≈ 1` and small `n` (a bare "100%" is statistically meaningless without it; cf. the rule of three:
0 failures in `n` bounds the failure rate at ≈ `3/n`).

**Provenance.** Token figures come from OTel `gen_ai.usage.*` attributes on `kind='llm'` spans;
durations from run `started_at`/`finished_at`; parent↔child linkage from the `branches` table. No
metric is modeled or projected.

---

## 5. Benchmark Design

**Graph.** A 5-node "Research Synthesizer" LangGraph:

```
START → query_expansion → retrieve → analyze → synthesize → cite_check → END
```

- `query_expansion` (small model): expand a topic into sub-queries.
- `retrieve` (mock tool, no LLM): fetch sources.
- `analyze` (**large model, cost-dominant**): per-source claims/evidence/relevance analysis.
- `synthesize` (small model): write the cited answer from the analysis.
- `cite_check` (small model): audit citations.

This is deliberately the **Plan-then-Execute** shape: the expensive reasoning (`analyze`) is upstream;
the downstream nodes are cheap. **We disclose plainly that the topology was chosen to model that
pattern**, because the token-bypass figure depends on it (§9, §10). A graph with the expensive node
*downstream* of typical fix points would bypass far less; we discuss this adversarial case in §10 and
flag it as future work.

**Failure injection.** A deterministic, hash-seeded schedule injects one of four logical failures (or
none) per run. The failing node defines the fork point for that run's replay:

| Mode | Fails at | Replay re-runs | Strictly-upstream (bypassable) |
|------|----------|----------------|-------------------------------|
| N1 | query_expansion | all 4 LLM nodes | none |
| N2 | retrieve | analyze, synthesize, cite_check | query_expansion only |
| N3 | synthesize | synthesize, cite_check | query_expansion, analyze |
| N4 | cite_check | cite_check | query_expansion, analyze, synthesize |

The graph has no conditional edges — all nodes always execute; "failure" is logical state, so every
parent has a complete checkpoint history. Topics are 1,000 real TriviaQA questions.

---

## 6. Experimental Setup

- **Provider/models:** OpenRouter, `meta-llama/llama-3.3-70b-instruct` (the `analyze` node) and
  `meta-llama/llama-3.1-8b-instruct` (the three small nodes). Non-reasoning instruct models →
  predictable token counts.
- **Scale:** 500 parent runs; **117 replays** (one per failed parent).
- **Matched timing:** both parents and replays run with node sleeps disabled (`BENCH_FAST=1`), so
  wall-time reflects real LLM-API latency, not simulated node durations — making D1 an
  apples-to-apples ratio (see §10 for the residual caveat).
- **Client:** OpenAI SDK pointed at OpenRouter's base URL, with bounded retries and a 30 s timeout so
  a rate-limited call fails fast rather than blocking.
- **Volume/tokens:** 1,500,488 input + 478,284 output tokens (~1.98 M total). Real provider spend
  ≈ **$2.95**. (The in-DB `total_cost_usd` reads 0 because Husk's pricing table does not yet include
  these OpenRouter model IDs; the $2.95 is the provider-reported figure.)

---

## 7. Results

### 7.1 Headline (n = 117 replays)

| Metric | Value (95% CI) | Before the fix |
|--------|----------------|----------------|
| **D5 — Mean token bypass** | **42.87%** [36.47, 49.53] | 1.23% |
| **D5 — Token-weighted bypass** | **55.2%** (184,473 / 334,393 tokens) | — |
| **D1 — Wall-time speed-up (median)** | **6.53×** (mean 16.78× [13.05, 22.17]; right-skewed) | 0.56× |
| **D4 — Replay success (Wilson)** | **100%** (117/117), [96.82%, 100%] | — |
| **D3 — Max token bypass** | **89.39%** | — |

Two honest framings of bypass: the **mean per-replay rate** (42.9%) weights every replay equally; the
**token-weighted aggregate** (55.2%) is the actual fraction of all LLM tokens saved across the 117
replays and is higher because high-bypass replays tend to be larger. We lead with the more
conservative 42.9%.

*Caveat on the before/after.* The "before the fix" figures (1.23% bypass, 0.56× wall-time; 95% CIs
[0.59, 2.75] and [0.53, 0.58], n=173/209) were measured on an earlier *cost-late* graph with the
broken (full-re-run) engine, whereas the "after" figures are the fixed engine on the *cost-upstream*
graph. The comparison therefore combines two changes — the engine fix **and** the realistic topology
— and is not a single controlled A/B. It is still meaningful because the broken engine re-executes
every node regardless of topology, so its bypass is ≈0–1% on *any* graph; the fix is what enables
non-trivial bypass at all, and the topology sets the magnitude. A clean A/B (broken vs. fixed engine
on the *same* graph) is left as future work.

### 7.2 Bypass scales with failure depth (D2)

| Failure mode | Re-runs | Token bypass (95% CI) | n |
|--------------|---------|------------------------|---|
| **N4** (downstream of `analyze`) | cite_check only | **87.92%** [87.68, 88.17] | 38 |
| **N3** (at synthesize) | synthesize, cite_check | **43.09%** [42.68, 43.50] | 38 |
| **N2** (at retrieve) | analyze, synthesize, cite_check | **0%** | 26 |
| **N1** (at query_expansion) | all nodes | **0%** | 9 |

The per-mode CIs are extremely tight because, within a mode, the bypassed token fraction is nearly
deterministic (the per-node token distribution is stable). N1/N2 are **structural zeros**: repairing
an early failure requires re-running the expensive downstream `analyze`, so there is nothing upstream
to bypass (for N2 the parent's `analyze` ran on empty input at ~0 tokens, so the *fixed* child, which
does real analysis, can even cost more — bypass clamps to 0). These zeros are reported, not hidden;
they are the honest floor of the primitive.

### 7.3 Why the numbers are what they are: per-node token weights

Mean LLM tokens per node over parent runs (in / out):

| Node | Model | Mean tokens | in | out |
|------|-------|-------------|----|-----|
| synthesize | 8B | 1,577 | 1,457 | 121 |
| analyze | 70B | 1,486 | 785 | 701 |
| cite_check | 8B | 429 | 415 | 14 |
| query_expansion | 8B | 154 | 70 | 84 |

A typical run's LLM cost is ≈ 3,646 tokens. Bypassing `query_expansion`+`analyze` (N3) ≈ 45% of that;
bypassing `query_expansion`+`analyze`+`synthesize` (N4) ≈ 88% — matching the measured 43.1% and 87.9%.
(`synthesize` is token-heavy despite being the small model because its *input* is the full analysis.)

### 7.4 Structural proof: upstream nodes are deterministically skipped

For each replay we count the child's `kind='llm'` spans (the parent always has 4):

| Mode | Child LLM spans | Range | n |
|------|-----------------|-------|---|
| N1 | 4 | [4, 4] | 9 |
| N2 | 3 | [3, 3] | 26 |
| N3 | 2 | [2, 2] | 38 |
| N4 | 1 | [1, 1] | 38 |

The counts are exactly `fork-node + successors`, with **zero variance** across all 117 replays. This
is the empirical proof of §3's correctness argument: the engine genuinely skips upstream nodes (they
emit no spans), as opposed to merely producing similar outputs. Before the fix, every child re-ran all
4 nodes.

### 7.5 Supporting infrastructure metrics

- **Ingest overhead:** mean **0.65 ms** per span [0.52, 0.80] (p50 0, p95 5), n=617 — local SQLite
  ingest is effectively free vs. cloud round-trips.
- **Storage:** **23.3 KB / trace** (13.7 MB DB for this run).

These are secondary (infrastructure footnotes), not the hero result.

---

## 8. Discussion

**Bypass is a function of failure depth and topology.** The single most important interpretation: a
replay skips everything *upstream* of the fix point, so the saving is large exactly when the
expensive work precedes the failure — the common case when debugging the reasoning/synthesis stages
of a real agent. On this graph that is 88% (N4) and 43% (N3); the pooled 42.9% is dragged down by the
structural-zero early failures.

**The value compounds.** Token bypass is realized on *every* debug iteration. A developer who iterates
ten times on a downstream failure pays the upstream cost once instead of ten times.

**Token bypass is the robust metric; wall-time is supporting.** Token counts are provider-independent
and deterministic. Wall-clock speed-up, while real, depends on inference latency and is therefore
noisier (§10). We therefore headline token bypass and present speed-up as a median with explicit
caveats.

---

## 9. Threats to Validity and Limitations

We state these plainly; a sophisticated reviewer should weight the numbers accordingly.

1. **The primitive is LangGraph's, not ours.** LangGraph natively provides time-travel
   (`update_state`, fork, `invoke(None)`). Husk's contribution is (a) productizing it as a visual
   debugger, (b) the local OTel ingest + storage layer, and (c) **measuring** its efficiency — which,
   to our knowledge, no one has published. "LangGraph already does this" is a fair challenge; our
   answer is the debugger + measurement layer, not the resume mechanic itself.
2. **Single topology.** Bypass depends on where cost sits. We chose a Plan-then-Execute shape (cost
   upstream) and disclose it. We have **not** yet measured the adversarial case (expensive node
   *downstream* of the fork), which would show low bypass; reporting a bypass *range* across
   topologies is the most important piece of future work.
3. **Single model family, single provider, single dataset.** Llama-3.3-70B / 3.1-8B via OpenRouter on
   TriviaQA. We do not claim generality across models, providers, or task distributions.
4. **Synthetic, self-reported benchmark.** Failures are injected, not naturally occurring; all numbers
   are self-measured. Reviewers rightly discount self-reported results. Our mitigation is full
   reproducibility (§11) and publishing raw per-run data.
5. **Wall-time skew and shared-endpoint noise.** D1's mean (16.78×) is right-skewed (median 6.53×, p95
   52×, max 137×); the tail is inflated by variable latency on a shared inference endpoint (provider
   queueing/routing). The defensible claim is "median ≈ 6.5×, easily ≥ 2×", **not** a precise
   constant. A clean wall-time measurement requires a dedicated endpoint, off-peak, randomized paired
   trials.
6. **Small n for N1/N2.** With the natural failure mix, N1 has n=9 and N2 n=26. Their values are 0%
   (structural), so the thin n is low-risk, but a balanced-failure run would tighten them.
7. **Pooled vs. per-mode framing.** The pooled 42.9% can read as either generous or weak depending on
   the assumed production failure distribution. We present per-mode results so readers can re-weight.
8. **Counting quirk.** The metric tool reports `n_parents = 617` because replay children also have a
   null `parent_run_id`; there are **500 distinct parent runs** plus 117 children. Branch-level
   metrics (D1–D5) are unaffected; only the volume count is inflated.
9. **Earlier runs were rate-limited.** Prior attempts on free-tier providers (Groq daily-token cap;
   Cerebras per-minute/hour request quotas) produced corrupted, tiny-n data; the run reported here is
   the clean one. We mention this for transparency about the measurement history.

---

## 10. Related Work

No formal, published benchmark or standard for *agent replay/resume efficiency* appears to exist —
part of this report's contribution is defining the metric.

- **LangSmith** (LangChain) offers trace replay and node-by-node state diffs and re-running against
  new model versions, but re-executes the graph and publishes no token-savings benchmark; its strength
  is cloud collaboration and deep LangChain/LangGraph integration. Its cloud ingest round-trip is on
  the order of ~100 ms vs. Husk's local sub-ms.
- **AgentOps** markets "time-travel debugging" and "session replay" plus a marketing figure ("up to
  25× cheaper fine-tuning") with no published methodology or sample size.
- **Langfuse / Helicone / Arize Phoenix** lead with cost/latency/token dashboards and generous free
  tiers; efficiency claims, where present, lack sample sizes and CIs.
- **n1n "Mnemon"** reports ~93% token reduction, but this is a cross-invocation *cache* (not
  state-replay), measured at n=45 with no CI.
- **AIMultiple** published the most rigorous adjacent methodology we found — an observability-overhead
  benchmark (100 identical queries, temperature 0) — a good template to match or exceed.
- **Methodological standards.** We follow Kalibera & Jones (arXiv:2007.10899) in reporting
  execution-time *ratios with effect-size confidence intervals* rather than bare point numbers, and
  HELM (Liang et al., 2022) in favoring multiple metrics over a single headline. The Plan-then-Execute
  cost structure that motivates our topology is described in the agent-architecture literature
  (e.g., arXiv:2509.08646).

The salient gap: commercial tools publish efficiency claims without sample sizes or confidence
intervals. Reporting CIs at all, plus raw data and a reproducible harness, is both our differentiation
and the cheapest credibility move available.

---

## 11. Reproducibility

The benchmark, replay engine, and metrics are scripted. End to end (PowerShell shown; the `$KEY` is a
provider key supplied via environment variable only — never committed):

```powershell
# 0. clean slate
Remove-Item ~/.husk/traces.db, ~/.husk/benchmark_research.sqlite -ErrorAction SilentlyContinue
uv run husk-ai start --no-open-browser          # backend on :7654 (separate terminal)

# 1. parents (matched timing on; OpenRouter via the openai-compatible client)
$env:OPENROUTER_API_KEY = $KEY
$env:LLM_MODEL_LARGE = "meta-llama/llama-3.3-70b-instruct"
$env:LLM_MODEL_SMALL = "meta-llama/llama-3.1-8b-instruct"
$env:BENCH_FAST = "1"; $env:LLM_MAX_RETRIES = "2"
uv run --group examples python benchmark/run_benchmark.py `
    --runs 500 --topics benchmark/queries_1000.jsonl --concurrency 6

# 2. replays (one per failed parent; matched timing default)
uv run --group examples python benchmark/real_replays.py --limit 130

# 3. metrics + CIs
uv run python benchmark/hero_report.py --out benchmark/HERO_METRICS.md `
    --json-out benchmark/hero_metrics.json
```

Statistical routines: `benchmark/bootstrap.py` (`bca_ci`, `wilson_ci`, both self-tested). Metric SQL:
`benchmark/hero_report.py`. Raw per-run JSON and the trace DB can be published alongside this report;
doing so is recommended (no incumbent publishes its raw data).

---

## 12. Conclusion

State-level modify-and-replay turns a full agent re-run into a partial one by resuming from a
checkpoint and re-executing only the fork node and its successors. After fixing our implementation to
do this correctly, we measured — with confidence intervals and a deterministic structural proof — a
mean token bypass of **42.9%** (token-weighted **55.2%**), up to **87.9%** for failures downstream of
the costly node, **100%** replay success (Wilson [96.8%, 100%]), and a **median 6.5×** wall-time
speed-up, versus **1.23%** / **0.56×** before the fix. The savings scale with how much expensive work
precedes the fix point. The headline number is topology-dependent and the primitive itself is
LangGraph's; the durable contributions are the productized debugger, the local trace store, and a
rigorous, reproducible measurement of a capability that the surrounding tooling ships without
quantifying.

---

## References

1. B. Efron and R. Tibshirani. *An Introduction to the Bootstrap.* Chapman & Hall, 1993. (BCa intervals, ch. 14.)
2. E. B. Wilson. "Probable inference, the law of succession, and statistical inference." *JASA*, 1927. (Score interval for a proportion.)
3. T. Kalibera and R. Jones. "Quantifying Performance Changes with Effect Size Confidence Intervals." arXiv:2007.10899.
4. P. Liang et al. "Holistic Evaluation of Language Models (HELM)." 2022.
5. "Architecting Resilient LLM Agents: A Guide to Secure Plan-then-Execute Implementations." arXiv:2509.08646.
6. LangGraph documentation — persistence, time-travel, `update_state`/fork.
7. OpenTelemetry Semantic Conventions for Generative AI (v1.36+).

---

## Appendix A — Metric SQL (essence)

Per-replay token bypass joins each branch to its parent and child LLM spans:

```sql
WITH parent_tokens AS (
  SELECT b.id, SUM(s.tokens_in + s.tokens_out) AS pt
  FROM branches b JOIN spans s ON s.run_id = b.parent_run_id AND s.kind='llm' GROUP BY b.id),
child_tokens AS (
  SELECT b.id, SUM(s.tokens_in + s.tokens_out) AS ct
  FROM branches b JOIN spans s ON s.run_id = b.child_run_id AND s.kind='llm' GROUP BY b.id)
SELECT 100.0 * MAX(0, pt - ct) / pt AS bypass_pct FROM parent_tokens JOIN child_tokens USING(id);
```

D4 uses `wilson_ci(n_with_child, n_total_branches)`; D1 uses `parent.(finished_at−started_at) /
child.(finished_at−started_at)` per branch, aggregated with `bca_ci`.

## Appendix B — Failure-mode → fork-node map

`{N1: query_expansion, N2: retrieve, N3: synthesize, N4: cite_check}`. The replay resumes at
`PREDECESSOR[fork_node]` (with `query_expansion`'s predecessor being the graph's `START` sentinel, i.e.
a full re-run for N1).

## Appendix C — Glossary

- **Parent run:** an original agent execution.
- **Replay / child run:** a resumed execution from the parent's checkpoint with a state patch.
- **Fork node:** the failing node; the replay re-runs it and everything after it.
- **Token bypass:** fraction of the parent's LLM tokens not re-paid by the replay.
- **Matched timing:** parent and replay measured under identical timing settings (node sleeps off).
