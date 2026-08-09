"""The run WebSocket must not drop spans that land while it is starting up.

History used to be read *before* subscribing, leaving a window in which an arriving
span was broadcast to nobody and never reached the client — exactly while a run is
live, which is when someone is watching it.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("HUSK_HOME", tempfile.mkdtemp())
os.environ["HUSK_NO_AUTO_BUILD"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from husk_studio_backend.ingest.broadcast import publish  # noqa: E402
from husk_studio_backend.main import app  # noqa: E402


def _otlp(span_id: str, trace: str) -> dict:
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "a"}}
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": trace,
                                "spanId": span_id,
                                "name": "n",
                                "startTimeUnixNano": "1000000",
                                "endTimeUnixNano": "2000000",
                                "attributes": [],
                            }
                        ]
                    }
                ],
            }
        ]
    }


def test_backlog_arrives_as_one_batch_frame() -> None:
    trace = "1a" * 16
    with TestClient(app, base_url="http://127.0.0.1:7654", client=("127.0.0.1", 54321)) as c:
        c.post("/v1/traces", json=_otlp("1c" * 8, trace))
        with c.websocket_connect(f"/ws/runs/{trace[:26]}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "span.replay.batch"
            assert [s["id"] for s in msg["spans"]] == ["1c" * 8]


def test_span_published_after_the_backlog_is_delivered_once() -> None:
    """Subscribing before reading history can only duplicate; the dedupe set means
    the client still sees each span exactly once."""
    trace = "2b" * 16
    run_id = trace[:26]
    with TestClient(app, base_url="http://127.0.0.1:7654", client=("127.0.0.1", 54321)) as c:
        c.post("/v1/traces", json=_otlp("2c" * 8, trace))
        with c.websocket_connect(f"/ws/runs/{run_id}") as ws:
            backlog = ws.receive_json()
            assert [s["id"] for s in backlog["spans"]] == ["2c" * 8]

            # A span already in the backlog must not be re-delivered...
            c.portal.call(  # type: ignore[attr-defined]
                publish,
                run_id,
                {"type": "span.created", "run_id": run_id, "span": {"id": "2c" * 8}},
            )
            # ...but a genuinely new one must be.
            c.portal.call(  # type: ignore[attr-defined]
                publish,
                run_id,
                {"type": "span.created", "run_id": run_id, "span": {"id": "2d" * 8}},
            )
            nxt = ws.receive_json()
            assert nxt["type"] == "span.created"
            assert nxt["span"]["id"] == "2d" * 8


def test_empty_run_still_sends_a_batch_frame() -> None:
    """The client keys its 'live' state off the socket opening; an empty run must
    not leave it waiting for a frame that never comes."""
    with TestClient(app, base_url="http://127.0.0.1:7654", client=("127.0.0.1", 54321)) as c:
        with c.websocket_connect("/ws/runs/does-not-exist") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "span.replay.batch"
            assert msg["spans"] == []


@pytest.mark.asyncio
async def test_publish_to_a_run_with_no_subscribers_is_a_noop() -> None:
    await publish("nobody-listening", {"type": "span.created", "span": {"id": "x"}})
