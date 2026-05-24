"""Cursor SDK Hooks bridge.

Flow:
  1. Cursor invokes `husk-cursor-hook hook --event=<X>` (npm package).
  2. The hook script POSTs to `/api/cursor/events` and long-polls
     `/api/cursor/events/{event_id}/decision` for up to ~25s.
  3. The Studio UI displays a banner with pending interventions; user clicks
     Allow / Deny / Ask, which POSTs to `/api/cursor/events/{event_id}/decision`.
  4. The long-poll unblocks and returns the decision to the hook, which
     writes the appropriate JSON to stdout for Cursor.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from ulid import ULID

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import CursorEventRow

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cursor", tags=["cursor"])

# In-memory signal map: event_id -> Event (set when decision recorded).
_signals: dict[str, asyncio.Event] = {}

# Hooks that block the agent vs. fire-and-forget.
_BLOCKING_HOOKS = {
    "beforeSubmitPrompt",
    "beforeShellExecution",
    "beforeMCPExecution",
    "beforeReadFile",
}


class EventIn(BaseModel):
    hook: str
    payload: dict[str, Any]
    project: str | None = None


class EventOut(BaseModel):
    event_id: str
    blocking: bool


class DecisionIn(BaseModel):
    permission: str  # allow | deny | ask
    user_message: str | None = None
    agent_message: str | None = None


@router.post("/events", response_model=EventOut)
async def create_event(req: EventIn) -> EventOut:
    """Cursor hook calls this when a hook event arrives."""
    event_id = str(ULID())
    blocking = req.hook in _BLOCKING_HOOKS

    async with async_session() as s:
        s.add(
            CursorEventRow(
                id=event_id,
                hook=req.hook,
                project=req.project,
                payload=req.payload,
                created_at=int(time.time() * 1000),
                permission="pending" if blocking else "allow",
                decided_at=None if blocking else int(time.time() * 1000),
            )
        )
        await s.commit()

    if blocking:
        _signals[event_id] = asyncio.Event()

    return EventOut(event_id=event_id, blocking=blocking)


@router.get("/events/{event_id}/decision")
async def wait_for_decision(
    event_id: str, timeout_s: Annotated[float, Query(alias="timeout")] = 25.0
) -> dict[str, Any]:
    """Long-poll for a decision. Returns the decision once the user resolves it,
    or {permission: "ask"} on timeout (so Cursor will prompt the user directly).
    """
    sig = _signals.get(event_id)
    if sig is None:
        # Either not blocking, or already decided. Look up the row.
        async with async_session() as s:
            row = await s.get(CursorEventRow, event_id)
        if row is None:
            raise HTTPException(status_code=404, detail="event not found")
        return _decision_payload(row)

    try:
        await asyncio.wait_for(sig.wait(), timeout=timeout_s)
    except TimeoutError:
        # Mark as ask/expired and let Cursor prompt the user directly.
        async with async_session() as s:
            row = await s.get(CursorEventRow, event_id)
            if row is not None and row.permission == "pending":
                row.permission = "ask"
                row.decided_at = int(time.time() * 1000)
                row.user_message = "Husk timed out waiting for a decision."
                await s.commit()
        _signals.pop(event_id, None)
        return {"permission": "ask", "user_message": "Husk timed out — please decide manually."}

    async with async_session() as s:
        row = await s.get(CursorEventRow, event_id)
    _signals.pop(event_id, None)
    if row is None:
        raise HTTPException(status_code=404, detail="event vanished")
    return _decision_payload(row)


@router.post("/events/{event_id}/decision")
async def submit_decision(event_id: str, req: DecisionIn) -> dict[str, str]:
    """Studio UI calls this when the user clicks Allow / Deny / Ask."""
    if req.permission not in ("allow", "deny", "ask"):
        raise HTTPException(status_code=400, detail="permission must be allow/deny/ask")

    async with async_session() as s:
        row = await s.get(CursorEventRow, event_id)
        if row is None:
            raise HTTPException(status_code=404, detail="event not found")
        if row.permission != "pending":
            return {"event_id": event_id, "status": "already_decided"}
        row.permission = req.permission
        row.user_message = req.user_message
        row.agent_message = req.agent_message
        row.decided_at = int(time.time() * 1000)
        await s.commit()

    sig = _signals.get(event_id)
    if sig is not None:
        sig.set()

    return {"event_id": event_id, "status": "ok"}


@router.get("/events")
async def list_events(
    status: str = "pending", limit: int = 50
) -> list[dict[str, Any]]:
    """List Cursor hook events. Used by the Studio banner to poll for pending interventions."""
    async with async_session() as s:
        q = select(CursorEventRow).order_by(CursorEventRow.created_at.desc()).limit(limit)
        if status != "all":
            q = q.where(CursorEventRow.permission == status)
        rows = (await s.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "hook": r.hook,
            "project": r.project,
            "payload": r.payload,
            "created_at": r.created_at,
            "decided_at": r.decided_at,
            "permission": r.permission,
            "user_message": r.user_message,
            "agent_message": r.agent_message,
        }
        for r in rows
    ]


def _decision_payload(row: CursorEventRow) -> dict[str, Any]:
    return {
        "permission": row.permission if row.permission in ("allow", "deny", "ask") else "ask",
        "user_message": row.user_message,
        "agent_message": row.agent_message,
    }
