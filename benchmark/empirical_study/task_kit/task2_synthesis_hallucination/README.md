# Task T2 — Synthesis hallucination

## Scenario

A research-synthesis agent must answer a multi-part question by combining
four retrieved sources. The output cites sources `[1]`, `[2]`, `[3]`, and
`[9]` — but only sources 1–4 exist.

## Observed symptom

`cite_check` flags a citation mismatch on every run. The participant must
prevent the `synthesize` node from inventing citations.

## Root cause (sealed)

The system prompt in `synthesize` instructs the LLM to "cite sources
generously". Combined with a high temperature setting, the model fabricates
plausible-looking citation numbers. The fix is one of: (a) tighten the
prompt to "cite only the N source numbers provided"; (b) drop temperature
to 0; (c) add a JSON-schema-constrained output format.

## Files in this kit

- `agent.py` — the broken agent (TBD).
- `failing_input.json` — `{"topic": "Edge inference accelerators 2025"}`.
- `expected_fix.md` — sealed.

## Success criterion

The agent's answer cites only existing source numbers. `cite_check`
returns `valid`.

## Husk advantage modality

The participant opens the `synthesize` span, sees the actual prompt and
completion, identifies the loose "cite generously" instruction, edits the
state's `synthesize.system_prompt`, and replays just `synthesize +
cite_check` from the checkpoint — no full graph re-run.

In baseline, this requires reading raw stdout logs to find what prompt
was sent and what came back, then re-running the whole graph each
iteration to verify.
