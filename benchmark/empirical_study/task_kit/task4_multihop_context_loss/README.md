# Task T4 — Multi-hop context loss

## Scenario

A LangGraph agent with five nodes processes a customer email: extract
sender → enrich with CRM lookup → classify intent → route → draft reply.
The drafted reply addresses the sender by the wrong name — even though
the extract node correctly identified them.

## Observed symptom

The final reply uses a wrong / generic name ("Dear Customer") instead of
the extracted sender name. The participant must find where the name field
was dropped.

## Root cause (sealed)

The LangGraph state reducer for the `route` node uses an `add_messages`
reducer that overwrites the `sender_name` field instead of preserving it.
Three nodes back, the field is populated. By the time the `draft_reply`
node runs, the state has lost the original value.

The fix: change the reducer in `route` to preserve top-level keys, or
elevate `sender_name` into a separate channel that uses a `last_value`
reducer.

## Files in this kit

- `agent.py` — the broken agent (TBD).
- `failing_input.json` — a sample customer email.
- `expected_fix.md` — sealed.

## Success criterion

The agent's draft reply uses the correctly-extracted sender name from
the first node.

## Husk advantage modality

Husk's state inspection at each checkpoint shows the participant exactly
which node lost the `sender_name` field. They can replay from the
problematic node with a corrected state to verify the fix immediately.

In baseline, the engineer must add `print(state)` between every node and
re-run the whole agent each time, decoding the multi-line dict prints
visually.
