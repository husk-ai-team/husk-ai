"""IDE observability event ingest.

Flow:
  1. The Cursor or VS Code bridge POSTs hook events (`afterFileEdit`, `stop`,
     `terminal.command`, …) to `/api/cursor/events` as fire-and-forget.
  2. The Studio UI lists them in the timeline alongside agent spans so you can
     see every file edit and terminal command your agent issued.

This endpoint is observability-only — Husk never blocks the agent and never
returns a permission decision.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from ulid import ULID

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import CursorEventRow

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cursor", tags=["cursor"])


class EventIn(BaseModel):
    hook: str
    payload: dict[str, Any]
    project: str | None = None


class EventOut(BaseModel):
    event_id: str


@router.post("/events", response_model=EventOut)
async def create_event(req: EventIn) -> EventOut:
    """Ingest a single IDE observability event."""
    event_id = str(ULID())

    async with async_session() as s:
        s.add(
            CursorEventRow(
                id=event_id,
                hook=req.hook,
                project=req.project,
                payload=req.payload,
                created_at=int(time.time() * 1000),
            )
        )
        await s.commit()

    return EventOut(event_id=event_id)


@router.get("/events")
async def list_events(limit: int = 50) -> list[dict[str, Any]]:
    """List recent IDE events for the Studio timeline."""
    async with async_session() as s:
        q = select(CursorEventRow).order_by(CursorEventRow.created_at.desc()).limit(limit)
        rows = (await s.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "hook": r.hook,
            "project": r.project,
            "payload": r.payload,
            "created_at": r.created_at,
        }
        for r in rows
    ]
