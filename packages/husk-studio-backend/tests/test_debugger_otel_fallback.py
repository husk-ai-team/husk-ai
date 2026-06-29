"""Observability-only debugger fallback.

A run ingested via OTel (no husk graph instrumentation) has no node graph, so the
debugger context falls back to a span-level view it can still localize on. A run
WITH husk.node spans keeps the rich node-graph context (no regression).
"""

from __future__ import annotations

from husk_studio_backend.db.models import RunRow, SpanRow
from husk_studio_backend.debugger.context_assembler import build_debug_context


def _span(
    sid: str,
    name: str,
    *,
    kind: str = "llm",
    status: str = "success",
    model: str | None = None,
    err: dict | None = None,
    started: int = 0,
) -> SpanRow:
    return SpanRow(
        id=sid,
        run_id="otelrun",
        kind=kind,
        name=name,
        started_at=started,
        finished_at=started + 1,
        status=status,
        model=model,
        provider="openai" if model else None,
        tokens_in=5,
        tokens_out=5,
        cost_usd=0.001,
        error_payload=err,
    )


def test_observability_only_fallback_builds_span_context() -> None:
    run = RunRow(
        id="otelrun",
        script_path="agent.py",
        framework="otel/openai",
        status="error",
        started_at=0,
        error_message="tool returned 500",
    )
    spans = [
        _span("s1", "chat gpt-4o", model="gpt-4o", started=1),
        _span("s2", "search tool", kind="tool", status="error",
              err={"message": "500 from search"}, started=2),
    ]
    ctx = build_debug_context(run, spans, model="gpt-4o", include_source=False)

    assert ctx["mode"] == "observability_only"
    assert "nodes" not in ctx  # no husk graph nodes in this mode
    assert {n["id"] for n in ctx["spans"]} == {"chat gpt-4o", "search tool"}
    assert ctx["failure"]["failing_spans"] == ["search tool"]
    assert ctx["failure"]["run_error"] == "tool returned 500"


def test_graph_run_still_uses_node_context() -> None:
    run = RunRow(
        id="graphrun",
        script_path="agent.py",
        framework="langgraph",
        status="error",
        started_at=0,
    )
    wrapper = SpanRow(
        id="w1",
        run_id="graphrun",
        kind="chain",
        name="node_a",
        started_at=1,
        finished_at=2,
        status="error",
        attrs={"husk.node": "node_a", "husk.node_seq": 0},
    )
    ctx = build_debug_context(run, [wrapper], model="gpt-4o", include_source=False)

    assert ctx.get("mode") != "observability_only"
    assert "nodes" in ctx
