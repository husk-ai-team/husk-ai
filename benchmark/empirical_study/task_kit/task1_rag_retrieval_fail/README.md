# Task T1 — RAG retrieval failure

## Scenario

The participant is given a RAG agent that answers questions about a small
internal knowledge base (4 markdown files about Husk product features).
For one specific question it produces an obviously wrong answer ("Husk
supports tracing via FlatBuffers protocol" — fabricated).

## Observed symptom

The agent returns a confident-sounding but factually wrong answer. The
participant must identify why the retrieval step fed the synthesis node
the wrong documents.

## Root cause (sealed)

The vector index path in the agent's config points to a *stale* snapshot
of the knowledge base, taken before the relevant feature was documented.
The synthesis node correctly summarises what it was given — the failure is
upstream in retrieval.

## Files in this kit

- `agent.py` — the broken agent (TBD when the empirical study is run).
- `failing_input.json` — `{"question": "How does Husk handle protocol buffers in OTel export?"}`.
- `expected_fix.md` — sealed envelope describing the exact remediation.

## Success criterion

The agent, when invoked on `failing_input.json` after the participant's
edit, returns an answer that mentions the **actual** OTel/HTTP transport
documented in the knowledge base (no FlatBuffers fabrication).

## Husk advantage modality

In the Husk timeline the participant sees the `retrieve` span returning
documents from the wrong path — immediate root-cause identification.
Modify-and-replay lets them swap the index path on the state and re-run
just the retrieve + synthesize nodes.

In the baseline modality, the participant must add print statements, re-run
the whole graph, and infer from log output what was retrieved.
