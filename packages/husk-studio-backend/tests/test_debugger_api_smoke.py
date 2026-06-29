"""ASGI smoke test: the debugger + graph routes are wired and behave."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUSK_HOME", str(tmp_path))
    monkeypatch.setenv("HUSK_NO_AUTO_BUILD", "1")
    monkeypatch.delenv("REGOLO_API_KEY", raising=False)  # Regolo is the default provider
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import husk_studio_backend.db.engine as eng

    eng._async_engine = None
    eng._async_factory = None
    eng._sync_engine = None
    eng._sync_factory = None
    return tmp_path


async def _seed_failed_run() -> None:
    from husk_studio_backend.db.engine import async_session
    from husk_studio_backend.db.models import RunRow, SpanRow

    async with async_session() as s:
        s.add(RunRow(id="run1", script_path="agent.py", started_at=1, finished_at=9,
                     status="error", error_message="boom at analyze"))
        s.add(SpanRow(id="root", run_id="run1", kind="chain", name="agent.run", started_at=1,
                      finished_at=9, status="error",
                      attrs={"husk.graph.nodes": json.dumps(["retrieve", "analyze"])}))
        s.add(SpanRow(id="gn", run_id="run1", kind="graph_node", name="node:analyze",
                      started_at=2, finished_at=8, status="error",
                      attrs={"husk.node": "analyze", "husk.node_seq": 1,
                             "husk.state_diff": json.dumps({"added": {"status": "error"}, "removed": {}, "changed": {}})}))
        await s.commit()


@pytest.mark.asyncio
async def test_debugger_and_graph_routes(isolated_home: Path) -> None:
    from httpx import ASGITransport, AsyncClient

    from husk_studio_backend.db.engine import init_db
    from husk_studio_backend.main import app

    await init_db()
    await _seed_failed_run()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Config starts keyless and never leaks a key field.
        cfg = (await c.get("/api/debugger/config")).json()
        assert cfg["has_key"] is False
        assert "keys" not in cfg

        # Models expose context windows.
        models = (await c.get("/api/debugger/models?provider=anthropic")).json()
        assert any(m["id"] == "claude-sonnet-4" for m in models["models"])

        # Analyze without a key is a clean 409, not a 500.
        r = await c.post("/api/debugger/runs/run1/analyze", json={})
        assert r.status_code == 409

        # Set a key; config now reports has_key but still never returns it.
        put = await c.put(
            "/api/debugger/config",
            json={"provider": "anthropic", "model": "claude-sonnet-4", "api_key": "sk-local-only"},
        )
        assert put.status_code == 200
        body = put.json()
        assert body["has_key"] is True
        assert "sk-local-only" not in json.dumps(body)

        # Graph endpoint localizes the failure and marks skipped nodes.
        g = (await c.get("/api/v1/runs/run1/graph")).json()
        assert g["failure"]["node_id"] == "analyze"
        assert g["debug_report"] is None
        statuses = {n["id"]: n["status"] for n in g["nodes"]}
        assert statuses["analyze"] == "error"
        assert statuses["retrieve"] == "skipped"
