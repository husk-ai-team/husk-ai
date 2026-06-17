"""The OTLP parser honors an explicit husk.span_kind (e.g. graph_node).

This guards the one ingest-path change behind the per-node graph: a span the
engine telemetry hook tags as `graph_node` must survive OTLP ingest as kind
`graph_node`, not be reclassified by the gen_ai heuristics.
"""

from __future__ import annotations

from husk_studio_backend.ingest.otel_parser import parse_otlp_traces


def _span(name: str, attrs: dict[str, object]) -> dict[str, object]:
    return {
        "name": name,
        "traceId": "abcdef0123456789abcdef0123456789",
        "spanId": "1122334455667788",
        "startTimeUnixNano": "1000000",
        "endTimeUnixNano": "2000000",
        "attributes": [
            {"key": k, "value": {"stringValue": str(v)}} for k, v in attrs.items()
        ],
    }


def _wrap(spans: list[dict[str, object]]) -> dict[str, object]:
    return {"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}


def test_explicit_graph_node_kind_is_honored() -> None:
    parsed = parse_otlp_traces(
        _wrap([_span("node:analyze", {"husk.span_kind": "graph_node", "husk.node": "analyze"})])
    )
    assert len(parsed) == 1
    assert parsed[0].kind == "graph_node"


def test_gen_ai_heuristics_still_apply_without_explicit_kind() -> None:
    parsed = parse_otlp_traces(
        _wrap([_span("analyze", {"gen_ai.operation.name": "chat"})])
    )
    assert parsed[0].kind == "llm"


def test_unknown_explicit_kind_falls_back_to_heuristics() -> None:
    parsed = parse_otlp_traces(
        _wrap([_span("x", {"husk.span_kind": "bogus", "gen_ai.tool.name": "retrieve"})])
    )
    assert parsed[0].kind == "tool"
