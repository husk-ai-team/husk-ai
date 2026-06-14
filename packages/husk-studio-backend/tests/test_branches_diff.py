"""Branch recording + diff: the parent->child link and its token-bypass math.

Guards WS5: UI replays become first-class branches, and the Studio can read how
many LLM tokens a replay bypassed. Hermetic (temp HUSK_HOME, fresh engine).
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUSK_HOME", str(tmp_path))
    import husk_studio_backend.db.engine as eng

    # Reset cached engines so this test binds to the temp HUSK_HOME.
    eng._async_engine = None
    eng._async_factory = None
    eng._sync_engine = None
    eng._sync_factory = None
    return tmp_path


async def _seed_parent_and_child() -> None:
    from husk_studio_backend.db.engine import async_session
    from husk_studio_backend.db.models import RunRow, SpanRow

    async with async_session() as s:
        s.add(RunRow(id="parent", script_path="", started_at=1, finished_at=101, status="error"))
        s.add(RunRow(id="child", script_path="", started_at=200, finished_at=240, status="success"))
        # Parent: 1000 LLM tokens across two spans.
        s.add(SpanRow(id="p1", run_id="parent", kind="llm", name="analyze",
                      started_at=2, tokens_in=400, tokens_out=300,
                      model="meta-llama/llama-3.3-70b-instruct"))
        s.add(SpanRow(id="p2", run_id="parent", kind="llm", name="synthesize",
                      started_at=3, tokens_in=200, tokens_out=100,
                      model="meta-llama/llama-3.1-8b-instruct"))
        # Child re-ran only the tail: 300 LLM tokens -> 700 bypassed (70%).
        s.add(SpanRow(id="c1", run_id="child", kind="llm", name="cite_check",
                      started_at=201, tokens_in=200, tokens_out=100,
                      model="meta-llama/llama-3.1-8b-instruct"))
        await s.commit()


@pytest.mark.asyncio
async def test_branch_records_bypass_and_is_idempotent(fresh_db: Path) -> None:
    from husk_studio_backend.api.branches import (
        CreateBranchRequest,
        list_branches,
        record_branch,
    )
    from husk_studio_backend.db.engine import init_db

    await init_db()
    await _seed_parent_and_child()

    b = await record_branch(
        CreateBranchRequest(parent_run_id="parent", child_run_id="child", fork_span_id="p2", label="t")
    )
    assert b["parent_llm_tokens"] == 1000
    assert b["child_llm_tokens"] == 300
    assert b["tokens_bypassed"] == 700
    assert b["token_bypass_pct"] == 70.0

    # One branch per child: a second call returns the same row, not a duplicate.
    again = await record_branch(
        CreateBranchRequest(parent_run_id="parent", child_run_id="child", fork_span_id="p2")
    )
    assert again["id"] == b["id"]

    listed = await list_branches(parent_run_id="parent")
    assert len(listed) == 1 and listed[0]["child_run_id"] == "child"


@pytest.mark.asyncio
async def test_diff_reports_token_bypass(fresh_db: Path) -> None:
    from husk_studio_backend.api.diff import compute_diff
    from husk_studio_backend.db.engine import init_db

    await init_db()
    await _seed_parent_and_child()

    d = await compute_diff("parent", "child")
    assert d["a"]["llm_tokens"] == 1000
    assert d["b"]["llm_tokens"] == 300
    assert d["tokens_bypassed"] == 700
    assert d["token_bypass_pct"] == 70.0
