# Task T3 — Tool JSON parse error

## Scenario

An agent uses a `weather_api` tool that returns JSON. On one specific
city, the API returns an unexpected shape (a single-element list instead
of an object) and the downstream parser crashes with `KeyError: 'temp'`.

## Observed symptom

The agent crashes with a `KeyError` exception. The participant must make
the parsing robust so the agent continues regardless of the API's shape
quirk.

## Root cause (sealed)

The `weather_api` tool's response schema is inconsistent: for major cities
it returns `{"temp": …, …}` (object), for some smaller cities it returns
`[{"temp": …, …}]` (single-element list). The downstream parse code does
`response["temp"]` which only works for the object form.

The fix: unwrap a single-element list before dict access, or upgrade the
parser to pydantic with a discriminated union.

## Files in this kit

- `agent.py` — the broken agent (TBD).
- `failing_input.json` — `{"city": "Caltagirone"}`.
- `expected_fix.md` — sealed.

## Success criterion

The agent returns a valid weather summary for the failing input without
raising.

## Husk advantage modality

Husk's span detail panel shows the raw tool output JSON in one click. The
participant immediately sees it's a list, not an object. They edit the
parsing code and replay the run from the tool span — no need to re-call
the actual API.

In baseline, the engineer reads the traceback, then re-runs the whole
agent with extra `print(response)` statements to inspect the shape.
