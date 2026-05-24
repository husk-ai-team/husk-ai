"""Integration status — feeds the Onboarding wizard's "Verify connection" button."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import CursorEventRow, RunRow

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

# A connection is considered "live" if we've seen activity within this window.
LIVE_WINDOW_MS = 5 * 60_000  # 5 minutes


@router.get("/status")
async def status() -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    cutoff = now_ms - LIVE_WINDOW_MS

    async with async_session() as s:
        # OTel — any run whose framework starts with otel/ except otel/langgraph
        # (which is broken out below).
        otel_last = (
            await s.execute(
                select(func.max(RunRow.started_at)).where(
                    RunRow.framework.like("otel/%"),
                    ~RunRow.framework.like("%langgraph"),
                )
            )
        ).scalar()

        lg_last = (
            await s.execute(
                select(func.max(RunRow.started_at)).where(
                    RunRow.framework.like("%langgraph%")
                )
            )
        ).scalar()

        cursor_last = (
            await s.execute(select(func.max(CursorEventRow.created_at)))
        ).scalar()

    def _build(last_at: int | None) -> dict[str, Any]:
        return {
            "connected": last_at is not None and last_at >= cutoff,
            "ever_connected": last_at is not None,
            "last_event_at": last_at,
        }

    return {
        "now_ms": now_ms,
        "cursor": _build(cursor_last),
        "langgraph": _build(lg_last),
        "otel": _build(otel_last),
    }
