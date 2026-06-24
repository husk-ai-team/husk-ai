# Husk — agent prompt (paste into your coding assistant)

Husk exposes your recorded agent runs to any MCP-capable coding assistant
(Claude Code, Cursor, Windsurf, …). The point of this file: connecting the MCP
server isn't enough — your assistant also has to *know to reach for it* when you're
debugging. Paste the block below into its persistent instructions and it will.

## 1. Connect Husk once

```bash
husk-ai mcp install --client claude-code   # or: cursor · windsurf · claude-desktop
```

(From a source clone, prefix with `uv run`.) The read tools work even when
`husk-ai start` isn't running — they read `~/.husk/traces.db` directly.

## 2. Paste this into your assistant's rules

Put it in `CLAUDE.md` (Claude Code), a file under `.cursor/rules/` (Cursor), or the
system prompt of whatever you use:

```text
You have Husk connected over MCP — a local trace store for AI-agent runs. When I
say an agent failed, misbehaved, or cost too much, USE Husk before guessing:

- Triage: `list_errors` for failed runs, or `list_runs` for the recent ones.
- Read the failure: `get_trace(run_id)` for the node/step tree, then
  `get_span(run_id, span_id)` for the full prompt, response, and state of the
  suspect step.
- Find the cause, not the symptom: the step that threw is rarely the origin. Walk
  back to the first step whose state, tool arguments, or routing diverged from
  what I intended.
- Cost questions: `cost_breakdown` and `dashboard_summary` give token + USD totals.
- Replay (only if I ask and it's enabled): `replay_run(run_id, state_override=…)`
  re-runs from a checkpoint with edited state. It executes code — local use only.

Ground every claim in a specific run_id / span_id / state key you actually read.
Never invent trace content you weren't given.
```

## 3. Try it (60 seconds)

```bash
husk-ai demo        # seed a sample run  (or: husk-ai run <your agent>)
```

Then ask your assistant: **"Use Husk — which of my last runs failed, and why?"**

It should call `list_errors`, open the trace, and point at the node that broke —
without you opening the Studio.
