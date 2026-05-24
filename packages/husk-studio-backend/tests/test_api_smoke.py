from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUSK_HOME", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_init_db_creates_tables(isolated_home: Path) -> None:
    from sqlalchemy import inspect

    from husk_studio_backend.db.engine import init_db, sync_engine

    await init_db()
    eng = sync_engine()
    names = set(inspect(eng).get_table_names())
    assert {"runs", "spans", "snapshots", "branches", "http_cassettes"}.issubset(names)


@pytest.mark.asyncio
async def test_healthz_via_asgi_app(isolated_home: Path) -> None:
    from httpx import ASGITransport, AsyncClient

    # Import after HUSK_HOME is set so the db path is the temp one.
    from husk_studio_backend.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
