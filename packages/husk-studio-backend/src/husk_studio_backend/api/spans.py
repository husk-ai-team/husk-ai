from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import SpanRow
from husk_studio_backend.ingest.broadcast import subscribe, unsubscribe

router = APIRouter(tags=["spans"])
log = logging.getLogger(__name__)


@router.get("/api/v1/runs/{run_id}/spans")
async def list_spans(run_id: str) -> list[dict]:
    async with async_session() as s:
        rows = (
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
        return [_serialize(r) for r in rows]


@router.websocket("/ws/runs/{run_id}")
async def run_stream(ws: WebSocket, run_id: str) -> None:
    await ws.accept()
    # Replay history first so a late-joining client sees the full timeline.
    async with async_session() as s:
        rows = (
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
        for r in rows:
            await ws.send_json({"type": "span.replay", "span": _serialize(r)})

    q = await subscribe(run_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
            except TimeoutError:
                await ws.send_json({"type": "ping"})
                continue
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        await unsubscribe(run_id, q)


def _serialize(r: SpanRow) -> dict:
    return {
        "id": r.id,
        "run_id": r.run_id,
        "parent_span_id": r.parent_span_id,
        "kind": r.kind,
        "name": r.name,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
        "status": r.status,
        "input_inline": r.input_inline,
        "output_inline": r.output_inline,
        "tokens_in": r.tokens_in,
        "tokens_out": r.tokens_out,
        "cost_usd": r.cost_usd,
        "provider": r.provider,
        "model": r.model,
        "error_payload": r.error_payload,
        "attrs": r.attrs,
    }
