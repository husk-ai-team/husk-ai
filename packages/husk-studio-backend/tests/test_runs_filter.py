"""Tests for the /api/v1/runs status/framework/q filters (added with the feature)."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUSK_HOME", str(tmp_path))
    monkeypatch.setenv("HUSK_NO_AUTO_BUILD", "1")
    return tmp_path


@pytest.mark.asyncio
async def test_list_runs_filters(isolated_home: Path) -> None:
    from httpx import ASGITransport, AsyncClient

    from husk_studio_backend.db.engine import async_session, init_db
    from husk_studio_backend.db.models import RunRow
    from husk_studio_backend.main import app

    await init_db()
    async with async_session() as s:
        s.add(RunRow(id="flt_ok", script_path="alpha_agent.py", framework="otel/openai", status="success", started_at=10))
        s.add(RunRow(id="flt_err", script_path="beta_agent.py", framework="otel/langgraph", status="error", started_at=20))
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:7654") as c:
        errs = {r["id"] for r in (await c.get("/api/v1/runs?status=error")).json()}
        alpha = {r["id"] for r in (await c.get("/api/v1/runs?q=alpha_agent")).json()}
        lg = {r["id"] for r in (await c.get("/api/v1/runs?framework=langgraph")).json()}

    # status filter: the error run is included, the success run is not.
    assert "flt_err" in errs and "flt_ok" not in errs
    # q matches script_path substring.
    assert "flt_ok" in alpha and "flt_err" not in alpha
    # framework substring match.
    assert "flt_err" in lg and "flt_ok" not in lg
