"""Replay engine — stub for M1.

Wired in M2 week 7 (node-level replay) and M3 week 9 (branching with overrides).

API surface:
  * `start_replay(run_id, from_span_id, overrides) -> new_run_id`
    Spawns a fresh sandbox subprocess with HUSK_RESUME_FROM and HUSK_OVERRIDES env vars.
    The sandbox loads the snapshot at `from_span_id`, re-installs HTTP virtualization in
    replay mode against the cassette, applies the override, and continues execution.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


async def start_replay(
    run_id: str,
    from_span_id: str,
    overrides: dict | None = None,
) -> str:
    log.debug("start_replay(%s, %s) — stub, wired in M2 week 7.", run_id, from_span_id)
    raise NotImplementedError("replay engine is wired in M2 week 7")
