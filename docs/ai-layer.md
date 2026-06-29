# Automatic debugger

When a run you're building fails, Husk debugs it for you. Click once — or turn on
auto-debug and it runs the moment a run fails — and Husk reads the whole run and tells
you, in plain language, what went wrong and what to change. It does the debugging; it is
not just an explanation of the trace.

This is the only part of Husk that makes an outbound call, and it calls one model provider
you choose and bring your own key for. Everything else stays on your machine. See the
[README](../README.md) for how runs get into Husk in the first place.

## Development-only, by design

The debugger works on runs that streamed into Husk from an agent on **this machine**. Trace
ingest is loopback-only, so a production deployment on another host is refused at the door —
Husk cannot be pointed at production, and the debugger inherits that. The config and
apply-fix endpoints below are loopback-only too: only a process on your own machine can set a
key or write a fix.

## Run a debug analysis

Two ways to start one, both producing the same report.

**On demand.** When a run fails, ask Husk to debug it:

```bash
curl -X POST http://localhost:7654/api/debugger/runs/run_a1b2/analyze \
  -H 'content-type: application/json' -d '{}'
```

Husk loads the run and its steps, builds a failure-focused context sized to the model's
window, calls your provider, and persists the report. Pass `provider` / `model` in the body
to override the configured default for one call.

**Auto-debug on failure (off by default).** Turn on `auto_analyze` in Settings and a run
that finishes in `error` kicks off the same analysis in the background — once per run — so
the report is already waiting when you open it. It only fires when a key is configured;
without one, nothing happens and ingest is unaffected.

Without a provider key, `analyze` returns `409` with a message pointing to Settings. Read the
latest report for a run at any time:

```bash
curl http://localhost:7654/api/debugger/runs/run_a1b2/report
```

## What the report says

The model returns a strict JSON report — extra keys are rejected, so it can't smuggle in
invented fields. A report has:

```json
{
  "failure_localization": { "node_id": "search_tool", "step_index": 7, "also_implicated": [] },
  "failure_class": "tool_timeout",
  "root_cause": "The search tool call exceeded its timeout because the query was unbounded.",
  "evidence": ["step 7 errored after 30s", "no max_results passed to the search tool"],
  "proposed_fix": {
    "summary": "Bound the search query and shorten the timeout.",
    "diff": "--- a/agent.py\n+++ b/agent.py\n@@ ...",
    "rationale": "An unbounded query can hang; capping results returns within the budget."
  },
  "confidence": "high",
  "missing_information": []
}
```

- **`failure_localization`** points at the step that broke (`node_id`, `step_index`) and any
  others implicated.
- **`failure_class`** and **`root_cause`** are the plain-language "what went wrong".
- **`evidence`** is the specific lines from the run the analysis leaned on, so you can check
  the work.
- **`proposed_fix`** is the "what to change": a summary, a rationale, and — when the analysis
  can locate the source — a unified `diff`.
- **`confidence`** is `high` / `medium` / `low`; **`missing_information`** lists what the
  analysis couldn't see, instead of guessing.

## Apply a proposed fix

When a report carries a `diff`, you can apply it to the agent's source file. This is
propose-by-default: nothing is written unless you confirm.

```bash
curl -X POST http://localhost:7654/api/debugger/runs/run_a1b2/apply-fix \
  -H 'content-type: application/json' \
  -d '{"report_id": "rep_...", "confirm": true}'
```

Husk locates the source file behind the run, writes a `.husk-bak` backup next to it, applies
the diff, and marks the report applied. Without `confirm: true` the call is a `400` — it never
edits your code by accident. If the diff doesn't apply cleanly, you get a `422` and the file
is left untouched.

## Providers, keys, and privacy

Husk never self-hosts a model. The debugger calls one provider you configure.

**Default: Regolo.ai.** EU-hosted (Italy), GDPR, zero data-retention inference, so the run
data sent for analysis stays in the EU. The default model is `Llama-3.3-70B-Instruct`.

**Alternatives.** Anthropic, OpenAI, and OpenRouter are selectable in Settings. OpenRouter is
handy when your agent itself ran on an OpenRouter model and you want to debug with the same
one.

```bash
curl http://localhost:7654/api/debugger/providers          # the four selectable providers
curl 'http://localhost:7654/api/debugger/models?provider=regolo'   # models for one provider
```

**Bring your own key, stored locally.** Your key lives in `~/.husk/secrets.json` on your
machine (chmod 0600 on POSIX), outside the repo, never committed and never logged. An
environment variable (`REGOLO_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) is honored as
a fallback so a key already in your shell works without re-entry. The config endpoint reports
`has_key: true/false` and never returns the key itself:

```bash
curl http://localhost:7654/api/debugger/config
# { "provider": "regolo", "model": "Llama-3.3-70B-Instruct", "auto_analyze": false, "has_key": false }
```

Set the provider, model, auto-debug toggle, or key with a loopback-only `PUT`:

```bash
curl -X PUT http://localhost:7654/api/debugger/config \
  -H 'content-type: application/json' \
  -d '{"provider": "regolo", "api_key": "sk-..."}'
```

Provider calls go through plain `httpx` so Husk controls exactly what is sent: request headers
and bodies are never logged, so your key and your run data never leak into logs.

## What the debugger does not do

- It does not run a model on Husk's own infrastructure. There is nothing to host.
- It does not phone home. The only outbound call is to the provider you chose.
- It does not monitor production. Ingest is loopback-only, so it only ever sees an agent
  running on this machine.
- It does not write to your code without confirmation. Apply-fix is propose-by-default and
  always leaves a backup.

## Related

- [README](../README.md): install Husk, instrument an agent, and get runs flowing.
- [Multi-model](./multi-model.md): which model handled each step and what each cost — the
  fastest way to find the call that gave a wrong answer.
- [Modify & replay](./replay.md): re-run from the broken step with edited state, skipping the
  upstream token cost.
- [Security & data](./security.md): the loopback model and what leaves your machine.
