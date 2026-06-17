"""Debugger API: BYOK config, model list, on-demand analysis, apply-fix.

Local-first: the API key set via PUT /config is stored only in ``~/.husk/secrets.json``
and is never returned by any endpoint (GET /config exposes ``has_key`` only).
Fix application is propose-by-default: it never writes to disk unless the caller
sends ``confirm: true``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import DebugReportRow, RunRow
from husk_studio_backend.debugger import providers, report, secrets
from husk_studio_backend.debugger.context_assembler import read_source_for_run
from husk_studio_backend.debugger.patcher import PatchError, apply_to_file
from husk_studio_backend.debugger.report import DebuggerError
from husk_studio_backend.debugger.schemas import ReportParseError

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/debugger", tags=["debugger"])


class ConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    auto_analyze: bool | None = None
    auto_apply: bool | None = None
    api_key: str | None = None  # write-only; never echoed back


class AnalyzeRequest(BaseModel):
    provider: str | None = None
    model: str | None = None


class ApplyFixRequest(BaseModel):
    report_id: str
    confirm: bool = False


@router.get("/config")
async def get_config() -> dict[str, Any]:
    return secrets.public_config()


@router.put("/config")
async def update_config(body: ConfigUpdate) -> dict[str, Any]:
    if body.provider is not None and body.provider not in providers.available_providers():
        raise HTTPException(status_code=400, detail=f"unknown provider {body.provider!r}")
    secrets.save_config(
        provider=body.provider,
        model=body.model,
        auto_analyze=body.auto_analyze,
        auto_apply=body.auto_apply,
        api_key=body.api_key,
    )
    return secrets.public_config()


@router.get("/providers")
async def list_providers() -> dict[str, Any]:
    return {"providers": providers.available_providers()}


@router.get("/models")
async def list_models(provider: str | None = None) -> dict[str, Any]:
    name = provider or secrets.public_config()["provider"]
    try:
        prov = providers.get_provider(name)
    except providers.ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"provider": name, "models": prov.list_models()}


@router.post("/runs/{run_id}/analyze")
async def analyze_run(run_id: str, body: AnalyzeRequest) -> dict[str, Any]:
    cfg = secrets.public_config()
    provider_name = body.provider or cfg["provider"]
    if secrets.resolve_api_key(provider_name) is None:
        raise HTTPException(
            status_code=409,
            detail=f"no API key configured for {provider_name!r}; set one in Settings",
        )
    try:
        return await report.run_debug_analysis(
            run_id, provider=body.provider, model=body.model, trigger="manual"
        )
    except ReportParseError as e:
        raise HTTPException(status_code=422, detail=f"model returned invalid report: {e}") from e
    except DebuggerError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/runs/{run_id}/report")
async def get_report(run_id: str) -> dict[str, Any]:
    rep = await report.latest_report(run_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="no debug report for this run")
    return rep


@router.post("/runs/{run_id}/apply-fix")
async def apply_fix(run_id: str, body: ApplyFixRequest) -> dict[str, Any]:
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="apply-fix requires explicit confirmation (confirm: true)",
        )
    async with async_session() as s:
        row = await s.get(DebugReportRow, body.report_id)
        if row is None or row.run_id != run_id:
            raise HTTPException(status_code=404, detail="report not found for this run")
        run = await s.get(RunRow, run_id)
        from husk_studio_backend.db.models import SpanRow

        spans = (
            (await s.execute(select(SpanRow).where(SpanRow.run_id == run_id)))
            .scalars()
            .all()
        )

    diff = ((row.report_json or {}).get("proposed_fix") or {}).get("diff")
    if not diff:
        raise HTTPException(status_code=400, detail="report has no proposed diff to apply")
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    _source, path = read_source_for_run(run, list(spans))
    if not path:
        raise HTTPException(status_code=400, detail="could not locate the agent source file")

    try:
        written = apply_to_file(path, diff)
    except PatchError as e:
        raise HTTPException(status_code=422, detail=f"diff did not apply cleanly: {e}") from e
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"could not write file: {e}") from e

    async with async_session() as s:
        row = await s.get(DebugReportRow, body.report_id)
        if row is not None:
            row.applied = True
            await s.commit()

    return {"applied": True, "path": written, "backup": f"{path}.husk-bak", "at": int(time.time() * 1000)}
