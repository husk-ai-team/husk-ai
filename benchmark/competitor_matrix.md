# LLM observability landscape -- competitor reference matrix

Numbers below are from public pricing pages, vendor blog posts, customer
case studies, and the Replay.io seed/A pitch materials. They are NOT
Husk-equivalents -- each tool sits at a different layer of the stack.
The matrix is here to **position Husk by contrast**, not to claim parity.

## Pricing & overhead at a glance

| Tool | Category | Entry price | SDK overhead | Storage retention | Public hero claim |
|---|---|---|---|---|---|
| **LangSmith** | Cloud LLM observability dashboard | $39/user/mo (Plus) | 132 ms median | 14 d base / 400 d extended | Podium: -90% manual review intervention |
| **Langfuse** | Open-source LLM observability | $29/mo (Core), free self-host | **0.1 ms SDK** (batched) | 30 d - 3 y | 1k - 20k req/min ingest (Hobby - Pro) |
| **Arize Phoenix** | OSS LLM observability + Cloud (AX) | Free self-host; AX Pro $50/mo | OTel native, n/a measured | 15-30 d SaaS | Kafka-partitioned ingest, VPC isolation |
| **Braintrust** | Eval & dataset platform | $249/mo (Pro) | n/a | 14-30 d | -60% eval time, -40% hallucinations |
| **Helicone** | AI proxy gateway | $79/mo (Pro) | proxy hop | 1-10 GB tier | "386 hours saved via cache" |
| **Datadog LLM** | Cloud APM extension | $8 / 10k req + APM + ingest | std APM | 15 d base | (multi-product cloud APM tax) |
| **Honeycomb** | Event-based observability | $130 / 100M events | std OTel | fixed 60 d | (general-purpose, not LLM-specific) |
| **Weights & Biases (Weave)** | ML experiment + GenAI tracing | free dev tier, custom enterprise | "minimal impact" | varies | (no LLM-specific public benchmark) |
| **Replay.io** (precedent) | Time-travel debugger (JavaScript) | $299/mo small teams | runtime record | n/a | MTTR 2-8 h -> < 30 min (ROI calc) |
| **Husk** (us) | **Local visual + state replay** | **$0 self-hosted, BUSL 1.1** | **TBD by benchmark** | **infinite (local SQLite)** | **N% Token Bypass Rate (deterministic)** |

## Positioning takeaways

1. **Pricing**: every LLM observability competitor charges per traced request,
   per GB ingested, or per user. Husk is local and self-hosted: **infinite
   retention at zero recurring cost**. Comparable to Sentry / Honeycomb's
   open-source on-prem approach.

2. **Overhead**: Langfuse's 0.1 ms SDK is the best in class because they
   batch async; LangSmith's 132 ms median includes a network round-trip.
   Husk avoids both -- ingest is local SQLite write, *expected* to be in
   the sub-millisecond range per span (measured in our benchmark).

3. **Retention**: cloud vendors cap data at 14-90 days unless you pay
   significantly more. A debug session 3 months after a regression is
   impossible without exporting traces to your own warehouse. Husk
   retention is bounded only by your disk.

4. **The unique angle**: every tool in the table either *observes* (passive
   trace dashboards) or *gates* (proxy gateway). **None of them lets you
   modify the state at a checkpoint and replay deterministically from
   there**. The closest precedent is Replay.io, which has validated the
   primitive ($43M Series B, 2022) for JavaScript / web debugging.
   Husk brings the same primitive to AI agents.

## Sources cited

- LangSmith pricing: <https://www.langchain.com/pricing>
- LangSmith overage: <https://checkthat.ai/brands/langsmith/pricing>
- LangSmith vs Litellm latency: <https://docs.litellm.ai/docs/benchmarks>
- Podium case: <https://www.langchain.com/articles/langsmith-vs-langfuse>
- Langfuse pricing: <https://langfuse.com/pricing>
- Langfuse SDK overhead: <https://medium.com/@sharanharsoor/from-50-seconds-to-10-milliseconds-inside-langfuses-journey-to-zero-latency-llm-observability-800bb8e7f27e>
- Arize Phoenix pricing: <https://arize.com/pricing/>
- Braintrust pricing: <https://www.braintrust.dev/pricing>
- Helicone pricing & metrics: <https://www.helicone.ai/pricing>, <https://helicone-helicone-7.mintlify.app/observability/metrics>
- Replay.io seed round (a16z, $5.7M): <https://www.replay.io>
- Replay.io ROI calculator assumptions: <https://www.replay.io/pricing>

## Industrial case studies (verified, with source)

| Company | Tool used | Reported outcome | Source |
|---|---|---|---|
| Podium | LangSmith | -90% manual review intervention | LangChain blog |
| Digital Applied (SaaS) | Langfuse + OTel | MTTR from 31-52 h -> 27 min after 90-day rollout | Vendor case study (May 2026) |
| Vercel (Next.js team) | Replay.io | "1-2 h/dev/day saved on local repro attempts" | Tim Neutkens public commentary |
| DeepAI | Helicone | "65% LLM inference cost reduction" via caching | Helicone customer case |
| Klarna | LangSmith / LangGraph | -80% MTTR on root-cause analysis | Klarna AI assistant retro |
| Booking.com | Arize Phoenix | 5x latency reduction, +133% accuracy on task-specific metrics | Arize customer case |

## Academic / dataset references for our 20% failure-rate floor

- **MAST taxonomy** (Multi-Agent System Failure Taxonomy, 2025): 1,642
  execution traces across 7 OSS multi-agent frameworks (MetaGPT, ChatDev,
  AutoGen, ...). Aggregate failure rates 41% - 86.7%. Breakdown: 44.2%
  specification/design errors, 32.3% inter-agent misalignment, 23.5%
  verification failure. **Our 20% injected failure rate is conservative**
  by this evidence.
- **SWE-bench Verified**: 500 issues curated by OpenAI. Best resolution
  82.6% (GPT-5.5), Claude Opus 4.x at ~82.0%. **18-23% residual = the long
  tail where humans+observability remain required**.
- **Stack Overflow 2025 Developer Survey** (N>49,000): 46% actively distrust
  AI outputs (up from 31% in 2024), 66% frustrated by AI "almost-right"
  code, **45.2% explicitly report debugging AI-generated code takes longer
  than writing it from scratch**.
- **Data Agent Benchmark (UC Berkeley + PromptQL, 2025)**: 54 complex queries
  across 12 datasets / 4 DBMS. Best model (Gemini-3.1-Pro) reaches 38%
  Pass@1 -- agents systematically fail on malformed join keys, unstructured
  text transformations.
