from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import RunRow, SpanRow

router = APIRouter(prefix="/api/v1/diff", tags=["diff"])


def _run_summary(run: RunRow, spans: list[SpanRow]) -> dict[str, Any]:
    llm = [s for s in spans if s.kind == "llm"]
    return {
        "run_id": run.id,
        "status": run.status,
        "duration_ms": (run.finished_at - run.started_at)
        if (run.finished_at and run.started_at)
        else None,
        "llm_spans": len(llm),
        "llm_tokens": sum((s.tokens_in or 0) + (s.tokens_out or 0) for s in llm),
        "nodes": [s.name for s in spans if s.kind in ("llm", "tool", "graph_node")],
    }


@router.get("/{run_a}/{run_b}")
async def compute_diff(run_a: str, run_b: str) -> dict[str, Any]:
    """Diff two runs: per-run token/latency/node summary + token delta.

    Lightweight, deterministic, and read-only — enough to power the Studio's
    parent-vs-child comparison (e.g. how many LLM tokens a replay bypassed).
    """
    async with async_session() as s:
        a = await s.get(RunRow, run_a)
        b = await s.get(RunRow, run_b)
        if a is None or b is None:
            raise HTTPException(status_code=404, detail="one or both runs not found")
        a_spans = list(
            (await s.execute(select(SpanRow).where(SpanRow.run_id == run_a))).scalars().all()
        )
        b_spans = list(
            (await s.execute(select(SpanRow).where(SpanRow.run_id == run_b))).scalars().all()
        )

    sa = _run_summary(a, a_spans)
    sb = _run_summary(b, b_spans)
    a_tokens = int(sa["llm_tokens"])
    b_tokens = int(sb["llm_tokens"])
    bypass_pct = round(100.0 * max(0, a_tokens - b_tokens) / a_tokens, 2) if a_tokens else 0.0
    return {
        "a": sa,
        "b": sb,
        "tokens_delta": b_tokens - a_tokens,
        "tokens_bypassed": max(0, a_tokens - b_tokens),
        "token_bypass_pct": bypass_pct,
    }
