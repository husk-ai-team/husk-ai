"""Tail a JSONL event file produced by the sandbox tracer, batch-insert into SQLite,
and broadcast each event to WebSocket subscribers.

Cross-OS strategy: poll the file size and read appended lines. Works on Windows
without any special FD machinery. We rely on the writer being line-buffered
(SpanEmitter opens the file with `buffering=1`) so we never see partial lines.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import RunRow, SpanRow
from husk_studio_backend.ingest.broadcast import publish

log = logging.getLogger(__name__)

POLL_INTERVAL_S = 0.05  # 50 ms
BATCH_FLUSH_S = 0.05
BATCH_FLUSH_N = 100


def _path_exists(p: Path) -> bool:
    return p.exists()


def _scan_run_event_files(runs_dir: Path) -> list[tuple[str, Path]]:
    """List (run_name, events.jsonl path) for each run dir that has an events file.

    Pure filesystem work — kept synchronous so async callers can offload it with
    asyncio.to_thread instead of blocking the event loop.
    """
    if not runs_dir.exists():
        return []
    out: list[tuple[str, Path]] = []
    for run_dir in runs_dir.iterdir():
        ev = run_dir / "events.jsonl"
        if ev.exists():
            out.append((run_dir.name, ev))
    return out


async def tail_events(run_id: str, event_path: Path) -> None:
    """Tail loop. Terminates when a run.end event is observed."""
    pending: list[dict] = []
    last_flush = time.monotonic()

    # Wait for the file to exist (the CLI creates it right before the sandbox spawns,
    # but we're defensive).
    for _ in range(40):
        if await asyncio.to_thread(_path_exists, event_path):
            break
        await asyncio.sleep(POLL_INTERVAL_S)

    finished = False
    fh = event_path.open("r", encoding="utf-8")
    try:
        while not finished:
            line = fh.readline()
            if line:
                line = line.strip()
                if line:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        log.warning("Bad JSONL line dropped (len=%d)", len(line))
                        continue
                    pending.append(event)
                    await publish(run_id, event)
                    if event.get("type") == "run.end":
                        finished = True
            else:
                await asyncio.sleep(POLL_INTERVAL_S)

            now = time.monotonic()
            if pending and (
                len(pending) >= BATCH_FLUSH_N or (now - last_flush) >= BATCH_FLUSH_S
            ):
                await _flush(pending)
                pending.clear()
                last_flush = now

        if pending:
            await _flush(pending)
    finally:
        fh.close()


async def _flush(events: list[dict]) -> None:
    """Persist a batch of events to SQLite. Idempotent on span ids."""
    async with async_session() as s:
        for ev in events:
            try:
                await _apply(s, ev)
            except Exception as e:  # noqa: BLE001
                log.exception("Failed to apply event %s: %s", ev.get("type"), e)
        await s.commit()


async def _apply(session, ev: dict[str, Any]) -> None:
    etype = ev.get("type")
    run_id = ev.get("run_id")
    if not run_id:
        return
    data = ev.get("data") or {}
    ts = int(ev.get("ts") or 0)

    if etype == "run.start":
        existing = await session.get(RunRow, run_id)
        if existing is None:
            session.add(
                RunRow(
                    id=run_id,
                    script_path=data.get("script_path") or "",
                    started_at=ts // 1000 or int(time.time() * 1000),
                    status="running",
                )
            )
        return

    if etype == "run.end":
        row = await session.get(RunRow, run_id)
        if row is not None:
            row.status = data.get("status") or "success"
            row.finished_at = ts // 1000 or int(time.time() * 1000)
            row.error_message = data.get("error")
        return

    span_id = ev.get("span_id")
    if not span_id:
        return

    if etype == "span.start":
        existing = await session.get(SpanRow, span_id)
        if existing is not None:
            return
        session.add(
            SpanRow(
                id=span_id,
                run_id=run_id,
                parent_span_id=data.get("parent_span_id"),
                kind=data.get("kind") or "chain",
                name=data.get("name") or "",
                started_at=ts,
                status="running",
                input_inline=data.get("input_inline"),
                attrs=data.get("attrs") or {},
            )
        )
        return

    if etype == "span.end":
        row = await session.get(SpanRow, span_id)
        if row is None:
            return
        row.finished_at = ts
        row.status = data.get("status") or "success"
        row.output_inline = data.get("output_inline")
        row.tokens_in = data.get("tokens_in")
        row.tokens_out = data.get("tokens_out")
        row.cost_usd = data.get("cost_usd")
        row.provider = data.get("provider")
        row.model = data.get("model")
        row.error_payload = data.get("error_payload")
        if data.get("attrs"):
            row.attrs = {**(row.attrs or {}), **data["attrs"]}
        # Bubble up totals to the run row.
        run = await session.get(RunRow, run_id)
        if run is not None:
            if row.tokens_in:
                run.total_tokens_in = (run.total_tokens_in or 0) + row.tokens_in
            if row.tokens_out:
                run.total_tokens_out = (run.total_tokens_out or 0) + row.tokens_out
            if row.cost_usd:
                run.total_cost_usd = (run.total_cost_usd or 0.0) + row.cost_usd
        return


async def discover_and_tail_active_runs(runs_dir: Path) -> None:
    """Scan runs_dir for events.jsonl files of pending runs and start tail tasks.

    Used by the backend at startup so a `husk run` started before the backend booted
    is still picked up. Idempotent via the `_active` set.
    """
    for run_name, ev in await asyncio.to_thread(_scan_run_event_files, runs_dir):
        async with async_session() as s:
            row = await s.get(RunRow, run_name)
        if row is None or row.status in ("running", "pending"):
            asyncio.create_task(tail_events(run_name, ev))


async def list_active_runs() -> list[str]:
    async with async_session() as s:
        rows = (
            (await s.execute(select(RunRow.id).where(RunRow.status == "running")))
            .scalars()
            .all()
        )
        return list(rows)
