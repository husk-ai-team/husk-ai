"""LangGraph integration — stub for M1, full implementation in M2 week 8.

Plan:
  * Hook `StateGraph.compile()` to wrap the resulting Runnable with a tracer that
    emits a `graph_node` span per node execution.
  * Read the native `SqliteSaver` checkpoint file directly (path known via the
    checkpointer instance) and translate each checkpoint into a Husk snapshot row.
  * Emit `state_set` spans on every state transition.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install() -> None:
    log.debug("LangGraph integration install() — stub, wired in M2 week 8.")
