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
        # Generic ingest: have ANY traces arrived? (the framework-agnostic OTLP
        # path). No framework is privileged here.
        otel_last = (
            await s.execute(select(func.max(RunRow.started_at)))
        ).scalar()

        # Per-framework breakdown so every adapter (openai, anthropic, langgraph,
        # …) shows up uniformly — LangGraph is one row among many, not special.
        adapter_rows = (
            await s.execute(
                select(RunRow.framework, func.max(RunRow.started_at))
                .group_by(RunRow.framework)
                .order_by(func.max(RunRow.started_at).desc())
            )
        ).all()

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
        "otel": _build(otel_last),
        "adapters": [
            {"framework": fw or "unknown", **_build(last)} for fw, last in adapter_rows
        ],
    }
