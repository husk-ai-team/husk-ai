"""End-to-end flows through the real ASGI app, external calls mocked.

Covers the three things a user actually does:
  1. Capture -> view: emit an OTLP trace to /v1/traces, read it back via the
     runs/spans/dashboard APIs.
  2. AI debug (BYOK): seed a failed run, mock the LLM provider, run analyze, and
     read the persisted report.
  3. Replay: drive the real replay dispatcher against the bundled example graph
     (Husk's own engine) and check it actually re-runs and returns state.

No network: the LLM provider is monkeypatched; the example graph uses canned
responses. The only "real" work is Husk's own ingest/DB/engine.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUSK_HOME", str(tmp_path))
    monkeypatch.setenv("HUSK_NO_AUTO_BUILD", "1")
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_global_tracer_provider() -> object:
    """The replay flow runs the example graph, which calls instrument() and sets
    OTel's process-global provider. Reset it so we don't leak into other tests
    (e.g. benchmark/test_determinism installs its own in-memory provider)."""
    yield
    import opentelemetry.trace as _t
    from opentelemetry.util._once import Once

    provider = _t._TRACER_PROVIDER
    if provider is not None and hasattr(provider, "shutdown"):
        try:
            provider.shutdown()
        except Exception:  # noqa: BLE001
            pass
    _t._TRACER_PROVIDER = None
    _t._TRACER_PROVIDER_SET_ONCE = Once()


def _otlp_trace(trace_id: str, *, error: bool) -> dict:
    code = 2 if error else 1
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "e2e-agent"}}
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": trace_id,
                                "spanId": "aaaa0000aaaa0000",
                                "name": "agent.run",
                                "startTimeUnixNano": "1000000",
                                "endTimeUnixNano": "2000000",
                                "attributes": [
                                    {"key": "gen_ai.system", "value": {"stringValue": "openai"}}
                                ],
                                "status": {"code": code},
                            },
                            {
                                "traceId": trace_id,
                                "spanId": "bbbb1111bbbb1111",
                                "parentSpanId": "aaaa0000aaaa0000",
                                "name": "chat gpt-4o",
                                "startTimeUnixNano": "1100000",
                                "endTimeUnixNano": "1900000",
                                "attributes": [
                                    {"key": "gen_ai.system", "value": {"stringValue": "openai"}},
                                    {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
                                    {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
                                    {"key": "gen_ai.usage.input_tokens", "value": {"intValue": "40"}},
                                    {"key": "gen_ai.usage.output_tokens", "value": {"intValue": "12"}},
                                    {"key": "husk.node", "value": {"stringValue": "answer"}},
                                ],
                                "events": [
                                    {
                                        "name": "gen_ai.user.message",
                                        "attributes": [
                                            {"key": "content", "value": {"stringValue": "What is the capital of Italy?"}}
                                        ],
                                    }
                                ],
                                "status": {"code": code},
                            },
                        ]
                    }
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_capture_then_read_e2e(_isolated_home: Path) -> None:
    from httpx import ASGITransport, AsyncClient

    from husk_studio_backend.db.engine import init_db
    from husk_studio_backend.ingest.otel_parser import _trace_id_to_run_id
    from husk_studio_backend.main import app

    await init_db()
    trace_id = "11112222333344445555666677778888"
    run_id = _trace_id_to_run_id(trace_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:7654") as c:
        ingest = await c.post(
            "/v1/traces", json=_otlp_trace(trace_id, error=False),
            headers={"content-type": "application/json"},
        )
        assert ingest.status_code == 200, ingest.text

        runs = (await c.get("/api/v1/runs")).json()
        assert any(r["id"] == run_id for r in runs)

        spans = (await c.get(f"/api/v1/runs/{run_id}/spans")).json()
        # The chat span carried token usage; it round-tripped through the DB.
        chat = next((s for s in spans if s.get("model") == "gpt-4o"), None)
        assert chat is not None
        assert chat["tokens_in"] == 40 and chat["tokens_out"] == 12

        summary = (await c.get("/api/dashboard/summary")).json()
        assert summary["totals"]["runs"] >= 1


@pytest.mark.asyncio
async def test_debugger_analyze_e2e_with_mocked_llm(_isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from httpx import ASGITransport, AsyncClient

    from husk_studio_backend.db.engine import init_db
    from husk_studio_backend.debugger import providers, secrets
    from husk_studio_backend.ingest.otel_parser import _trace_id_to_run_id
    from husk_studio_backend.main import app

    await init_db()
    secrets.save_config(provider="anthropic", model="claude-sonnet-4", api_key="sk-test-key-not-real")

    canned = json.dumps(
        {
            "failure_localization": {"node_id": "answer", "step_index": 1, "also_implicated": []},
            "failure_class": "wrong_answer",
            "root_cause": "The model answered before the tool result arrived.",
            "evidence": ["answer span finished in error"],
            "proposed_fix": {"summary": "Await the tool result", "diff": None, "rationale": "Order the steps."},
            "confidence": "medium",
            "missing_information": [],
        }
    )

    class _FakeProvider:
        name = "anthropic"

        def complete(self, **_kw: object) -> str:
            return canned

        def list_models(self) -> list[dict[str, object]]:
            return []

    monkeypatch.setattr(providers, "get_provider", lambda name: _FakeProvider())

    trace_id = "9999888877776666555544443333eeee"
    run_id = _trace_id_to_run_id(trace_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:7654") as c:
        assert (
            await c.post("/v1/traces", json=_otlp_trace(trace_id, error=True),
                         headers={"content-type": "application/json"})
        ).status_code == 200

        analyze = await c.post(f"/api/debugger/runs/{run_id}/analyze", json={})
        assert analyze.status_code == 200, analyze.text
        report = analyze.json()["report"]
        assert report["failure_class"] == "wrong_answer"

        got = (await c.get(f"/api/debugger/runs/{run_id}/report")).json()
        assert got["report"]["failure_localization"]["node_id"] == "answer"


def test_replay_runs_the_example_graph_e2e(_isolated_home: Path) -> None:
    """The real replay dispatcher imports the bundled example by path (allowlisted
    to cwd) and runs it on Husk's own engine, returning computed state."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    from husk_studio_backend.replay.graph_replay import replay_graph

    # Pre-install a processor-less provider so the example's instrument() reuses it
    # instead of wiring a real OTLP exporter (which would retry against a dead port).
    trace.set_tracer_provider(TracerProvider())

    example = Path("examples/husk_thread.py").resolve()
    assert example.is_file()  # repo cwd; under the allowed root

    result = replay_graph(
        graph_module=f"{example}:agent",
        state_override={"topic": "Rome"},
    )
    assert result.get("thread_id")
    # husk_thread's answerer produces a Rome-specific answer -> the graph really ran.
    assert "Rome" in json.dumps(result.get("state"))
