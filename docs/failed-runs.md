# Failed runs

When an agent you're building fails, the question is "what went wrong on *this* run, and what do I change." Husk answers it without making you read a raw trace: filter the runs list down to failures, open the one you care about, and let the automatic debugger debug it for you.

This is a development-time loop. You run it on your own machine while building an agent, before production — Husk ingests traces over loopback only, so only an agent running on this same machine can stream in. It cannot be pointed at a production host by design.

## Find the failed runs

The Runs list is the starting point. It polls every few seconds and shows every run Husk has captured, newest first, with the agent's framework, the models it called, status, duration, tokens, and cost.

To narrow it to failures, use the status filter at the top of the list:

| Filter | Shows |
| --- | --- |
| `all` | Every run, regardless of status |
| `success` | Runs that finished cleanly |
| `error` | Runs that ended in failure |
| `running` | Runs still in flight |

Pick `error` and the list collapses to just the runs that failed. You can also search by script path or run id to jump straight to a known run. The filter is a query parameter on the underlying read endpoint:

```bash
curl "http://localhost:7654/api/v1/runs?status=error"
```

A failed run carries an `error_message` and a `status` of `error`; that's what the filter keys on. Click any row to open the run.

## Open a failed run and debug it

Inside a failed run you get the full step-by-step view — every model call and tool call, what went in and what came back, where the run broke. Alongside it sits the **automatic debugger**.

The debugger does the debugging for you. Click **Debug this run for me** and Husk reads the entire run and tells you, in plain language, what went wrong and what to change. It is not just an explanation of the trace — it localizes the failure, names the failure class, gives its evidence, and proposes a concrete fix.

```bash
curl -X POST "http://localhost:7654/api/debugger/runs/<run_id>/analyze"
```

The report it produces has these fields:

| Field | Meaning |
| --- | --- |
| `failure_localization` | Where the run broke — the node and step it points to |
| `failure_class` | The kind of failure (timeout, bad tool args, model error, …) |
| `root_cause` | What actually went wrong, in plain language |
| `evidence` | The specific things in the run that support that conclusion |
| `proposed_fix` | What to change, with a rationale (and, when applicable, a diff) |
| `confidence` | `high`, `medium`, or `low` |
| `missing_information` | What to check yourself to be sure |

You can re-run the analysis at any time, and if the fix comes with a diff you can apply it to the agent's source file from the run (Husk writes a backup first and never touches disk without explicit confirmation).

### Auto-debug

If you'd rather not click, turn on **auto-debug** in Settings. With it enabled and a key configured, the moment a run finishes in `error` Husk kicks off the analysis in the background, so the report is already waiting when you open the run. It fires at most once per run, and a failure in the background analysis never disrupts trace ingest. The on-demand button is always available too.

The debugger needs an API key. Without one, the analyze endpoint returns `409` and the panel points you to Settings to add a key. The key stays on your machine.

## See which model gave the wrong answer

Within a single run, Husk shows which model handled each step and what each one cost. When a run returns something wrong, that breakdown is the fastest way to find the call to blame — and to decide whether the fix is a different model rather than different code. See [multi-model](./multi-model.md) for the per-run model breakdown.

## Fix it and re-run

Once you know the broken step and have a change in mind, you don't have to re-run the whole agent from the top. Re-run from the broken step with edited state, deterministically replaying the upstream steps so you don't pay their token cost again. See [modify & replay](./replay.md).

## Local-first, zero retention

Everything here is computed from runs in your own database on your own machine. Nothing about your runs leaves the box on its own. The only outbound call Husk makes is the automatic debugger reaching the model provider you configure — Regolo.ai by default (EU-hosted, GDPR, zero data retention), or another provider you select. The runs list and the failed-run view themselves talk to nothing but localhost.

## Where to go next

- Connecting an agent so its runs show up here is a one-line SDK / OpenTelemetry setup step: [Instrumentation](./instrumentation.md).
- Which model ran each step, and what each cost: [multi-model](./multi-model.md).
- Re-run a failed run from the broken step with an edited state: [modify & replay](./replay.md).
