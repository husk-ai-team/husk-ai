"""Snapshot capture + restore.

Stub for M1 — implementation lands in M2 week 7 and M3 week 11 (serializer plugins).
The shape:

* `capture(span_id, locals_dict)` — serializes captured state to ~/.husk/runs/<run>/snapshots/
  using the serializer registry; returns a Snapshot row to persist.
* `restore(snapshot_id)` — reverse: loads the JSON, re-hydrates Pydantic / LangGraph
  state, applies plugins, returns the live object graph.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def capture(span_id: str, payload: dict) -> str | None:
    log.debug("snapshot.capture(span_id=%s) — stub, wired in M2.", span_id)
    return None


def restore(snapshot_id: str) -> dict | None:
    log.debug("snapshot.restore(%s) — stub, wired in M2.", snapshot_id)
    return None
