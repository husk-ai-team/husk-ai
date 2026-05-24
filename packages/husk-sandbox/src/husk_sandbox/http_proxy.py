"""HTTP virtualization layer (record/replay).

Stub for M1 — full implementation in M2 (week 7). The structure is:

* `record_mode()` — monkey-patches httpx.Client.send and httpx.AsyncClient.send to
  capture HAR-like cassettes keyed by sha256(normalized_request).
* `replay_mode(cassette_dir)` — same patch, but responses are looked up by hash
  and returned without hitting the network.

Cross-cutting concerns deferred to M2:
  - SSE / streaming response capture (OpenAI streams)
  - Header normalization (drop Authorization, Date, x-request-id, etc. from hash)
  - Cassette storage layout (one JSON per request, indexed by request_hash)
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_record_mode() -> None:
    log.debug("install_record_mode — stub, wired in M2 week 7.")


def install_replay_mode(cassette_dir: str) -> None:
    log.debug("install_replay_mode(%s) — stub, wired in M2 week 7.", cassette_dir)
