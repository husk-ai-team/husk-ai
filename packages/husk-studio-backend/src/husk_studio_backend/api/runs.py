from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import RunRow

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


@router.get("")
async def list_runs(limit: int = 50, offset: int = 0) -> list[dict]:
    async with async_session() as s:
        rows = (
            (
                await s.execute(
                    select(RunRow)
                    .order_by(RunRow.started_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return [_serialize(r) for r in rows]


@router.get("/{run_id}")
async def get_run(run_id: str) -> dict:
    async with async_session() as s:
        row = await s.get(RunRow, run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="run not found")
        return _serialize(row)


def _serialize(r: RunRow) -> dict:
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
