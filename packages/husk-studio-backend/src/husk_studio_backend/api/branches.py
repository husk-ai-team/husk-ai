from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/branches", tags=["branches"])
log = logging.getLogger(__name__)


class CreateBranchRequest(BaseModel):
    parent_run_id: str
    fork_span_id: str
    override_type: str
    override_payload: dict
    label: str | None = None


@router.post("")
async def create_branch(req: CreateBranchRequest) -> dict:
    """Stub: wired end-to-end in M3 week 9 (BranchModal + replay engine override)."""
    log.info("branch request received: %s", req.model_dump())
    raise HTTPException(status_code=501, detail="branching is wired in M3 week 9")
