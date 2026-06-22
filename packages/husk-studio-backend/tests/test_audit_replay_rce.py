"""AUDIT-ADDED (2026-06) — security regression tests for the replay path.

Written during the v0.3.0 audit. They first DEMONSTRATED the exploit; now they
LOCK IN the fix:

  * `graph_module` allowlist (replay/graph_replay.py) — `exec_module` only runs
    files under the cwd or `$HUSK_ALLOWED_GRAPH_DIRS`. An attacker-controlled
    path outside those roots is refused (403).
  * loopback/Origin guard (api/_guard.py) — non-loopback peers and cross-origin
    browser requests to replay/otel/debugger are refused (403).

Finding (CRITICAL, now mitigated): `POST /v1/traces` + `POST /api/replay` let an
attacker import an arbitrary `.py`. The two layers above close the chain.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUSK_HOME", str(tmp_path))
    monkeypatch.setenv("HUSK_NO_AUTO_BUILD", "1")
    # Ensure the allowlist does not include the temp dir unless a test opts in.
    monkeypatch.delenv("HUSK_ALLOWED_GRAPH_DIRS", raising=False)
    return tmp_path


def _otlp_trace(trace_id_hex: str, span_id_hex: str, graph_module: str | None) -> dict:
    attrs = []
    if graph_module is not None:
        attrs.append({"key": "husk.graph_module", "value": {"stringValue": graph_module}})
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "attacker"}}
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": trace_id_hex,
                                "spanId": span_id_hex,
                                "name": "agent.run",
                                "startTimeUnixNano": "1",
                                "endTimeUnixNano": "2",
                                "attributes": attrs,
                                "status": {"code": 1},
                            }
                        ]
                    }
                ],
            }
        ]
    }


def _write_evil_module(home: Path, marker: Path) -> str:
    evil = home / "evil_graph.py"
    evil.write_text(
        "from pathlib import Path\n"
        f"Path(r{str(marker)!r}).write_text('arbitrary-code-execution')\n"
        "def invoke(state, thread_id=None):\n"
        "    return {'ok': True}\n"
        "graph = object()\n",
        encoding="utf-8",
    )
    return f"{evil}:graph"


async def _ingest_and_replay(home: Path, graph_module: str | None, trace_id: str, span_id: str):
    from httpx import ASGITransport, AsyncClient

    from husk_studio_backend.db.engine import init_db
    from husk_studio_backend.ingest.otel_parser import _trace_id_to_run_id
    from husk_studio_backend.main import app

    await init_db()
    run_id = _trace_id_to_run_id(trace_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:7654") as client:
        ingest = await client.post(
            "/v1/traces",
            json=_otlp_trace(trace_id, span_id, graph_module),
            headers={"content-type": "application/json"},
        )
        assert ingest.status_code == 200, ingest.text
        replay = await client.post("/api/replay", json={"run_id": run_id, "state_override": {}})
    return replay


@pytest.mark.asyncio
async def test_replay_blocks_graph_module_outside_allowed_root(isolated_home: Path) -> None:
    """The exploit is now refused: a graph_module outside the allowed roots -> 403."""
    marker = isolated_home / "PWNED.txt"
    graph_module = _write_evil_module(isolated_home, marker)  # under HUSK_HOME (a temp dir, not cwd)

    replay = await _ingest_and_replay(
        isolated_home, graph_module, "abcdef0123456789abcdef0123456789", "1122334455667788"
    )

    assert replay.status_code == 403, replay.text
    assert "allowed roots" in replay.text
    assert not marker.exists(), "allowlist must prevent exec of the attacker module"


@pytest.mark.asyncio
async def test_replay_allows_graph_module_under_allowed_root(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legit replay still works: a graph_module under an allowed root runs (200)."""
    monkeypatch.setenv("HUSK_ALLOWED_GRAPH_DIRS", str(isolated_home))
    marker = isolated_home / "ran.txt"
    graph_module = _write_evil_module(isolated_home, marker)

    replay = await _ingest_and_replay(
        isolated_home, graph_module, "11ff11ff11ff11ff11ff11ff11ff11ff", "aabbccddeeff0011"
    )

    assert replay.status_code == 200, replay.text
    assert marker.exists(), "an allowed-root module should run (gate opens for trusted dirs)"


@pytest.mark.asyncio
async def test_replay_rejects_run_without_graph_module(isolated_home: Path) -> None:
    """A run with no husk.graph_module cannot be replayed (400)."""
    replay = await _ingest_and_replay(
        isolated_home, None, "00ff00ff00ff00ff00ff00ff00ff00ff", "8877665544332211"
    )
    assert replay.status_code == 400
    assert "graph_module" in replay.text


@pytest.mark.asyncio
async def test_guard_blocks_non_loopback_client(isolated_home: Path) -> None:
    """The loopback guard refuses a non-loopback peer (e.g. --host 0.0.0.0 + remote)."""
    from httpx import ASGITransport, AsyncClient

    from husk_studio_backend.db.engine import init_db
    from husk_studio_backend.main import app

    await init_db()
    transport = ASGITransport(app=app, client=("8.8.8.8", 1234))
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:7654") as client:
        r = await client.post("/api/replay", json={"run_id": "x", "state_override": {}})
    assert r.status_code == 403
    assert "non-loopback" in r.text


@pytest.mark.asyncio
async def test_guard_blocks_cross_origin_browser(isolated_home: Path) -> None:
    """A browser request with a non-loopback Origin (DNS-rebinding) is refused."""
    from httpx import ASGITransport, AsyncClient

    from husk_studio_backend.db.engine import init_db
    from husk_studio_backend.main import app

    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:7654") as client:
        r = await client.post(
            "/api/replay",
            json={"run_id": "x", "state_override": {}},
            headers={"origin": "http://evil.example"},
        )
    assert r.status_code == 403
    assert "cross-origin" in r.text
