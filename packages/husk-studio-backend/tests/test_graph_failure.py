"""Failure detection + skipped-node derivation in the per-node graph model.

Covers the required "failure detection" surface: the graph API/model marks the
right node as the failure point and renders never-run topology nodes as skipped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUSK_HOME", str(tmp_path))
    import husk_studio_backend.db.engine as eng

    eng._async_engine = None
    eng._async_factory = None
    eng._sync_engine = None
    eng._sync_factory = None
    return tmp_path


_NODES = ["query_expansion", "retrieve", "analyze", "synthesize", "cite_check"]


async def _seed_failed_run() -> None:
    from husk_studio_backend.db.engine import async_session
    from husk_studio_backend.db.models import RunRow, SpanRow

    async with async_session() as s:
        s.add(
            RunRow(
                id="r1",
                script_path="agent.py",
                started_at=1,
                finished_at=100,
                status="error",
                error_message="failed at analyze",
            )
        )
        # Root span carries the topology.
        s.add(
            SpanRow(
                id="root",
                run_id="r1",
                kind="chain",
                name="agent.run",
                started_at=1,
                finished_at=100,
                status="error",
                attrs={
                    "husk.thread_id": "t1",
                    "husk.graph_module": "agent.py:graph",
                    "husk.graph.nodes": json.dumps(_NODES),
                    "husk.graph.edges": json.dumps(
                        [[a, b] for a, b in zip(_NODES, _NODES[1:], strict=False)]
                    ),
                },
            )
        )
        # query_expansion ran fine: a graph_node wrapper + its llm span.
        s.add(
            SpanRow(
                id="gn_qe",
                run_id="r1",
                kind="graph_node",
                name="node:query_expansion",
                started_at=2,
                finished_at=10,
                status="success",
                attrs={
                    "husk.node": "query_expansion",
                    "husk.node_seq": 0,
                    "husk.state_before": json.dumps({"topic": "x"}),
                    "husk.state_after": json.dumps({"topic": "x", "sub_queries": ["a"]}),
                    "husk.state_diff": json.dumps(
                        {"added": {"sub_queries": ["a"]}, "removed": {}, "changed": {}}
                    ),
                },
            )
        )
        s.add(
            SpanRow(
                id="llm_qe",
                run_id="r1",
                kind="llm",
                name="query_expansion",
                started_at=3,
                finished_at=9,
                status="success",
                tokens_in=50,
                tokens_out=20,
                model="gpt-4o-mini",
                input_inline={"messages": [{"role": "user", "content": "expand x"}]},
                output_inline={"choices": [{"message.content": "[\"a\"]"}]},
                attrs={"husk.node": "query_expansion", "gen_ai.operation.name": "chat"},
            )
        )
        # analyze failed.
        s.add(
            SpanRow(
                id="gn_an",
                run_id="r1",
                kind="graph_node",
                name="node:analyze",
                started_at=11,
                finished_at=20,
                status="error",
                attrs={
                    "husk.node": "analyze",
                    "husk.node_seq": 1,
                    "husk.state_before": json.dumps({"topic": "x", "sources": []}),
                    "husk.state_after": json.dumps(
                        {"topic": "x", "sources": [], "status": "error"}
                    ),
                    "husk.state_diff": json.dumps(
                        {"added": {"status": "error"}, "removed": {}, "changed": {}}
                    ),
                    "husk.error.traceback": "Traceback: no sources",
                },
            )
        )
        s.add(
            SpanRow(
                id="llm_an",
                run_id="r1",
                kind="llm",
                name="analyze",
                started_at=12,
                finished_at=19,
                status="error",
                tokens_in=0,
                tokens_out=0,
                model="gpt-4o",
                error_payload={"message": "no sources to analyse"},
                attrs={"husk.node": "analyze", "gen_ai.operation.name": "chat"},
            )
        )
        await s.commit()
        # synthesize + cite_check never ran -> no spans -> skipped.


@pytest.mark.asyncio
async def test_graph_marks_failure_and_skipped(fresh_db: Path) -> None:
    from sqlalchemy import select

    from husk_studio_backend.db.engine import async_session, init_db
    from husk_studio_backend.db.models import RunRow, SpanRow
    from husk_studio_backend.graph_model import build_run_graph

    await init_db()
    await _seed_failed_run()

    async with async_session() as s:
        run = await s.get(RunRow, "r1")
        spans = (
            (await s.execute(select(SpanRow).where(SpanRow.run_id == "r1")))
            .scalars()
            .all()
        )

    g = build_run_graph(run, list(spans))
    by_id = {n.id: n for n in g.nodes}

    # Failure point is analyze, not query_expansion.
    assert g.failure is not None
    assert g.failure["node_id"] == "analyze"
    assert by_id["analyze"].is_failure_point is True
    assert by_id["analyze"].status == "error"
    assert by_id["analyze"].traceback == "Traceback: no sources"

    # query_expansion succeeded and carries its state + a model call.
    qe = by_id["query_expansion"]
    assert qe.status == "success"
    assert qe.state_diff == {"added": {"sub_queries": ["a"]}, "removed": {}, "changed": {}}
    assert len(qe.model_calls) == 1

    # Topology nodes that never produced a span are skipped.
    assert by_id["synthesize"].status == "skipped"
    assert by_id["cite_check"].status == "skipped"

    # Edges came from the topology, not just the executed chain.
    assert {"from": "synthesize", "to": "cite_check", "conditional": False, "label": None} in g.edges


@pytest.mark.asyncio
async def test_graph_endpoint_attaches_report_slot(fresh_db: Path) -> None:
    from husk_studio_backend.api.graph import get_run_graph
    from husk_studio_backend.db.engine import init_db

    await init_db()
    await _seed_failed_run()

    payload = await get_run_graph("r1")
    assert payload["failure"]["node_id"] == "analyze"
    assert payload["debug_report"] is None  # no analysis run yet
    assert payload["run_status"] == "error"
