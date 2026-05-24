from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/diff", tags=["diff"])


@router.get("/{run_a}/{run_b}")
async def compute_diff(run_a: str, run_b: str) -> dict:
    """Stub: wired in M3 week 10 (DiffView + diff algorithm)."""
    raise HTTPException(status_code=501, detail="diff is wired in M3 week 10")
