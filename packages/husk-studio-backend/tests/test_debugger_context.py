"""Context assembler: full detail near the failure, summaries far away, in budget."""

from __future__ import annotations

import json

import pytest

from husk_studio_backend.db.models import RunRow, SpanRow
from husk_studio_backend.debugger import context_assembler

_NODES = [f"n{i}" for i in range(10)]
_FAIL_AT = 5
_BIG = "x" * 3000  # a chunky response so far-node summarization actually bites


def _spans() -> list[SpanRow]:
    rows: list[SpanRow] = []
    rows.append(
        SpanRow(
            id="root",
            run_id="r",
            kind="chain",
            name="agent.run",
            started_at=0,
            finished_at=1000,
            status="error",
            attrs={"husk.graph.nodes": json.dumps(_NODES)},
        )
    )
    for i, name in enumerate(_NODES):
        status = "error" if i == _FAIL_AT else "success"
        rows.append(
            SpanRow(
                id=f"gn_{i}",
                run_id="r",
                kind="graph_node",
                name=f"node:{name}",
                started_at=i * 10,
                finished_at=i * 10 + 5,
                status=status,
                attrs={
                    "husk.node": name,
                    "husk.node_seq": i,
                    "husk.state_before": json.dumps({"step": i}),
                    "husk.state_after": json.dumps({"step": i, "out": _BIG}),
                    "husk.state_diff": json.dumps(
                        {"added": {"out": _BIG}, "removed": {}, "changed": {}}
                    ),
                },
            )
        )
        rows.append(
            SpanRow(
                id=f"llm_{i}",
                run_id="r",
                kind="llm",
                name=name,
                started_at=i * 10 + 1,
                finished_at=i * 10 + 4,
                status=status,
                tokens_in=100,
                tokens_out=100,
                model="gpt-4o",
                input_inline={"messages": [{"role": "user", "content": _BIG}]},
                output_inline={"choices": [{"message.content": _BIG}]},
                attrs={"husk.node": name, "gen_ai.operation.name": "chat"},
            )
        )
    return rows


def test_window_kept_far_summarized_and_in_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force a small budget so far-from-failure regions must be compressed.
    monkeypatch.setattr(context_assembler, "context_window", lambda _m: 8000)
    monkeypatch.setattr(context_assembler, "max_output", lambda _m: 1000)

    run = RunRow(id="r", script_path="agent.py", started_at=0, status="error")
    run.extra_metadata = {}

    ctx = context_assembler.build_debug_context(run, _spans(), model="tiny", include_source=False)

    nodes = {n["id"]: n for n in ctx["nodes"]}
    # The failure node is present and rendered in full.
    assert nodes["n5"]["summarized"] is False
    assert nodes["n5"]["is_failure_point"] is True
    # A far node is summarized or dropped entirely (never sent in full).
    assert "n0" not in nodes or nodes["n0"]["summarized"] is True
    # Truncation was recorded and the whole context fits the model window.
    assert ctx["truncation"]["applied"] is True
    assert ctx["_assembled_token_estimate"] <= context_assembler.context_window("tiny")
    # Failure metadata is anchored on the right node.
    assert ctx["failure"]["node_id"] == "n5"


def test_no_truncation_when_it_fits() -> None:
    run = RunRow(id="r", script_path="agent.py", started_at=0, status="error")
    run.extra_metadata = {}
    # Default (large) window: a 10-node run fits, so nothing is summarized.
    ctx = context_assembler.build_debug_context(run, _spans(), model="gpt-4o", include_source=False)
    assert "truncation" not in ctx or ctx["truncation"]["applied"] is False
    assert all(n["summarized"] is False for n in ctx["nodes"])
