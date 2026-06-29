# Multi-model debugging

A modern agent rarely uses one model. The common pattern: a small, cheap model
drives tool-calling and routing, a large model does the hard reasoning, and a
mid-tier model summarizes. One run, three models, three price points, three
failure modes. Husk captures the model, provider, tokens, and cost for every
step, so when a run goes wrong you can see exactly which model did what, what
each one cost, and which one produced the wrong answer.

That is the fast path through a multi-model run while you're building it — instead
of rereading the whole trace, you open the run and the per-model breakdown points
you straight at the call to suspect.

## What Husk captures per step

Every LLM span carries the fields needed to break a run down by model. Husk
reads them from the standard GenAI OpenTelemetry attributes your agent already
emits:

- **Model** from `gen_ai.response.model` (falls back to `gen_ai.request.model`).
- **Provider** from `gen_ai.system` (for example `openai`, `anthropic`, `openrouter`).
- **Tokens** in and out from `gen_ai.usage.input_tokens` / `output_tokens`.
- **Cost** computed per step from tokens and Husk's model cost table.
- **Status**, so an errored call is attributed to the model that produced it.

You do not configure anything extra. If your agent emits GenAI spans (see
[Instrumentation](./instrumentation.md)), the breakdown works. Different steps
can name different models, and Husk keeps them separate.

## See the models on the Runs list

The Runs list shows the distinct model(s) each run touched. A run that called
`gpt-4o-mini` for tool-calling and `gpt-4o` for reasoning shows both, so you can
scan your recent runs and spot the expensive ones at a glance, before opening any
of them.

```http
GET /api/v1/runs
```

Each run in the response includes a `models` array:

```json
{
  "id": "run_8f2c...",
  "framework": "openai-agents",
  "status": "ok",
  "total_cost_usd": 0.0142,
  "models": ["gpt-4o", "gpt-4o-mini"]
}
```

## Models in this run: the per-run breakdown

Open a run and Husk shows a **Models in this run** panel: one row per
`(model, provider)` pair, with calls, tokens, cost, cost share, and errors. It
answers the question that matters in a multi-model run — where did the money and
the failures go.

```http
GET /api/v1/runs/{id}/breakdown
```

```json
{
  "run_id": "run_8f2c...",
  "total_cost_usd": 0.0142,
  "by_model": [
    {
      "model": "gpt-4o",
      "provider": "openai",
      "calls": 3,
      "tokens_in": 5120,
      "tokens_out": 1840,
      "cost_usd": 0.0131,
      "errors": 0,
      "cost_share": 0.9225
    },
    {
      "model": "gpt-4o-mini",
      "provider": "openai",
      "calls": 11,
      "tokens_in": 8430,
      "tokens_out": 2110,
      "cost_usd": 0.0011,
      "errors": 1,
      "cost_share": 0.0775
    }
  ]
}
```

Rows are sorted by cost, highest first. `cost_share` is each model's fraction of
the run's total, so the line that dominates that run's cost is the first one you
read. The example above makes the point: the large model handled 3 calls but 92%
of the cost, while the small model made 11 calls for almost nothing, and is the
one that erred.

## Attribute a wrong answer to model A vs B

When a run returns a bad answer, the breakdown tells you which model to suspect,
and the per-call view confirms it. Each LLM step records the model that handled
it, so you can trace a specific completion back to a specific model and provider.
If the small router model picked the wrong tool, you see its call and its error.
If the large model reasoned its way to a wrong conclusion, you see that too. You
stop guessing whether to swap models or fix a prompt, because the data points at
one of them.

This is where the per-model breakdown earns its place — a failure is no longer
"the agent broke," it is "`gpt-4o-mini` returned malformed tool args on call 7."
The [automatic debugger](./ai-layer.md) reads this same per-model data when it
explains why a run failed, so its diagnosis names the model and the call, not
just the agent.

## Why it matters

- **Pick the right model for each step.** See whether the cheap model is actually
  carrying the load, or whether you are paying the large model for work the small
  one could do.
- **Localize failures.** Errors are attributed per model, so you fix the model or
  prompt that is actually failing instead of rewriting the whole agent.

The model, token, and cost data is local-first like the rest of Husk: it lives on
your machine and never leaves it. Husk is a development-time tool — trace ingest
is loopback-only, so the runs you break down here are always agents running on
this machine, never a production deployment. See the [README](../README.md) and
[Security & data](./security.md) for the full security model.
