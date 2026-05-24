"""LangGraph integration: replay endpoint + checkpoint state lookup.

Replay flow:
  1. UI gets a run id + selected span id.
  2. UI POSTs {run_id, span_id, state_override} to /api/langgraph/replay.
  3. Backend resolves `husk.graph_module` from the run's root span attrs
     (set by the example), then re-invokes the graph with the new state.
  4. The graph's OTel exporter emits new traces which Husk ingests, creating
     a new Run that appears in /runs.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import RunRow, SpanRow

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/langgraph", tags=["langgraph"])


class ReplayRequest(BaseModel):
    run_id: str
    span_id: str | None = None
    state_override: dict[str, Any]


@router.post("/replay")
async def replay(req: ReplayRequest, request: Request) -> dict[str, Any]:
    """Re-invoke a LangGraph with a modified initial state.

    Returns the new thread_id; the resulting run will appear in /api/v1/runs
    once the OTel exporter flushes (typically within ~1s).
    """
    # Find husk.graph_module on the original run's spans (root span carries it).
    graph_module = await _find_graph_module(req.run_id)
    if not graph_module:
        raise HTTPException(
            status_code=400,
            detail=(
                "no husk.graph_module attribute on this run — only LangGraph runs "
                "instrumented by Husk can be replayed"
            ),
        )

    try:
        from husk_studio_backend.replay.langgraph_replay import replay_graph
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"replay module unavailable: {e}",
        ) from e

    # Tell the re-imported graph where to send its OTel traces. Examples that
    # honor $OTEL_EXPORTER_OTLP_ENDPOINT will export to whatever port THIS
    # backend is listening on, so traces flow back to us — not to a stale
    # backend on the hard-coded :7654.
    host = request.url.hostname or "localhost"
    port = request.url.port or 7654
    otel_endpoint = f"http://{host}:{port}"
    prev_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = otel_endpoint

    # Run the (sync) graph invocation in a thread so we don't block the loop.
    try:
        result = await asyncio.to_thread(
            replay_graph,
            graph_module=graph_module,
            state_override=req.state_override,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (ImportError, AttributeError, TypeError) as e:
        log.exception("graph import/invoke failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}") from e
    except Exception as e:  # noqa: BLE001
        log.exception("graph invocation crashed")
        raise HTTPException(status_code=500, detail=f"replay failed: {e}") from e
    finally:
        # Restore the prior env so we don't leak our override.
        if prev_endpoint is None:
            os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
        else:
            os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = prev_endpoint

    return {
        "thread_id": result.get("thread_id"),
        "state": result.get("state"),
        "note": "Refresh /runs in a moment — the new run will appear once OTel flushes.",
    }


async def _find_graph_module(run_id: str) -> str | None:
    async with async_session() as s:
        # Try the run's attrs first (set by some exporters).
        run = await s.get(RunRow, run_id)
        if run and run.extra_metadata:
            if isinstance(run.extra_metadata, dict):
                m = run.extra_metadata.get("husk.graph_module")
                if m:
                    return str(m)

        # Fall back to scanning span attrs.
        rows = (
            (
                await s.execute(
                    select(SpanRow).where(SpanRow.run_id == run_id)
                )
            )
            .scalars()
            .all()
        )
        for r in rows:
            attrs = r.attrs or {}
            m = attrs.get("husk.graph_module")
            if m:
                return str(m)
    return None
