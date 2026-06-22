from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import RunRow

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


@router.get("")
async def list_runs(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    framework: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """Recent runs, newest first. Optional filters: ``status``, ``framework``
    (substring), and ``q`` (substring match on script_path or run id)."""
    async with async_session() as s:
        query = select(RunRow).order_by(RunRow.started_at.desc())
        if status:
            query = query.where(RunRow.status == status)
        if framework:
            query = query.where(RunRow.framework.like(f"%{framework}%"))
        if q:
            like = f"%{q}%"
            query = query.where(RunRow.script_path.like(like) | RunRow.id.like(like))
        rows = (await s.execute(query.limit(limit).offset(offset))).scalars().all()
        return [_serialize(r) for r in rows]


@router.get("/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    async with async_session() as s:
        row = await s.get(RunRow, run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="run not found")
        return _serialize(row)


def _serialize(r: RunRow) -> dict[str, Any]:
    return {
        "id": r.id,
        "parent_run_id": r.parent_run_id,
        "fork_span_id": r.fork_span_id,
        "script_path": r.script_path,
        "framework": r.framework,
        "status": r.status,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
        "total_tokens_in": r.total_tokens_in,
        "total_tokens_out": r.total_tokens_out,
        "total_cost_usd": r.total_cost_usd,
        "error_message": r.error_message,
    }
