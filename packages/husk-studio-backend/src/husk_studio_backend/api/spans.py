from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import SpanRow
from husk_studio_backend.ingest.broadcast import subscribe, unsubscribe

router = APIRouter(tags=["spans"])
log = logging.getLogger(__name__)


# A single run's span list is fully materialised in memory and shipped as one JSON
# body, and each span carries its whole prompt and completion. Without a ceiling a
# pathological run turns one request into hundreds of megabytes.
_MAX_SPANS = 5000


async def _fetch_spans(run_id: str, limit: int) -> list[SpanRow]:
    async with async_session() as s:
        return list(
            (
                await s.execute(
                    select(SpanRow)
                    .where(SpanRow.run_id == run_id)
                    .order_by(SpanRow.started_at.asc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )


@router.get("/api/v1/runs/{run_id}/spans")
async def list_spans(run_id: str, limit: int = _MAX_SPANS) -> list[dict[str, Any]]:
    rows = await _fetch_spans(run_id, min(max(limit, 1), _MAX_SPANS))
    return [_serialize(r) for r in rows]


@router.websocket("/ws/runs/{run_id}")
async def run_stream(ws: WebSocket, run_id: str) -> None:
    await ws.accept()

    # Subscribe BEFORE reading history. The other order leaves a window between the
    # history query and the subscription in which an arriving span is broadcast to
    # nobody and never reaches this client — precisely while a run is live, which is
    # when someone is watching. Subscribing first can only duplicate, and the
    # `seen` set below drops the duplicates.
    q = await subscribe(run_id)
    try:
        rows = await _fetch_spans(run_id, _MAX_SPANS)
        seen = {r.id for r in rows}
        # One frame for the whole backlog: a long run was previously thousands of
        # individual sends, each with its own await and frame overhead.
        await ws.send_json(
            {"type": "span.replay.batch", "spans": [_serialize(r) for r in rows]}
        )

        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
            except TimeoutError:
                await ws.send_json({"type": "ping"})
                continue
            span_id = (event.get("span") or {}).get("id")
            if span_id is not None:
                if span_id in seen:
                    continue  # already delivered in the backlog
                seen.add(span_id)
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        await unsubscribe(run_id, q)


def _serialize(r: SpanRow) -> dict[str, Any]:
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
