"""Per-node graph view of a run — the structured data layer behind the UI graph.

Returns the run's nodes (with status incl. ``skipped``, per-node state +
before/after diff, model calls, tool calls, tokens, timing, and the failure
point), the edges (incl. conditional edges/labels when recoverable), the executed
path, and the latest debugger report (to overlay on the implicated nodes).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import RunRow, SpanRow
from husk_studio_backend.debugger.report import latest_report
from husk_studio_backend.graph_model import build_run_graph, run_graph_dict

router = APIRouter(prefix="/api/v1", tags=["graph"])


@router.get("/runs/{run_id}/graph")
async def get_run_graph(run_id: str) -> dict[str, Any]:
    async with async_session() as s:
        run = await s.get(RunRow, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        spans = (
            (
                await s.execute(
                    select(SpanRow)
                    .where(SpanRow.run_id == run_id)
                    .order_by(SpanRow.started_at.asc())
                )
            )
            .scalars()
            .all()
        )
    payload = run_graph_dict(build_run_graph(run, list(spans)))
    payload["debug_report"] = await latest_report(run_id)
    return payload
