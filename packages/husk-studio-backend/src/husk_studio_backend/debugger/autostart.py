"""Optional auto-analysis trigger for failed runs (OFF by default).

When the user has enabled ``auto_analyze`` in Settings AND a key is configured,
a run that finishes in ``error`` kicks off a debug analysis in the background, in
addition to the always-available on-demand button. An in-memory guard makes the
trigger fire at most once per run even though OTLP traces arrive in batches.
"""

from __future__ import annotations

import asyncio
import logging

from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import RunRow

log = logging.getLogger(__name__)

_triggered: set[str] = set()
# asyncio only holds a weak reference to a running task, so a fire-and-forget task
# can be garbage-collected mid-analysis. Keep a strong reference until it finishes.
_tasks: set[asyncio.Task[None]] = set()
# Bound the one-shot guard so a long-lived backend doesn't accumulate run ids forever.
_MAX_TRIGGERED = 5000


async def maybe_autostart(run_id: str) -> None:
    """Fire a one-shot auto analysis if enabled, keyed, failed, and not yet done."""
    if run_id in _triggered:
        return
    from husk_studio_backend.debugger import report, secrets

    cfg = secrets.public_config()
    if not cfg["auto_analyze"] or not cfg["has_key"]:
        return

    async with async_session() as s:
        run = await s.get(RunRow, run_id)
    if run is None or run.status != "error":
        return
    if await report.latest_report(run_id) is not None:
        _mark_triggered(run_id)
        return

    _mark_triggered(run_id)
    task = asyncio.create_task(_run(run_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _mark_triggered(run_id: str) -> None:
    if len(_triggered) >= _MAX_TRIGGERED:
        _triggered.clear()
    _triggered.add(run_id)


async def _run(run_id: str) -> None:
    from husk_studio_backend.debugger import report

    try:
        await report.run_debug_analysis(run_id, trigger="auto")
        log.info("auto debug analysis completed for run %s", run_id)
    except Exception:  # noqa: BLE001 - background task: log, never crash ingest
        log.exception("auto debug analysis failed for run %s", run_id)
