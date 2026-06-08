"""Dynamic LangGraph replay.

The example writes `husk.graph_module = "/abs/path/file.py:graph"` on the run's
root span. The replay endpoint reads that attribute, imports the file fresh,
and invokes `graph` (or a callable named `invoke`) with the user's state
override.

Security note: this dynamically imports user code by path. Local-only MVP.
DO NOT expose this endpoint over a non-localhost interface.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_import_lock = threading.Lock()
_module_cache: dict[str, Any] = {}

# Serialises checkpoint-resume replays. The cached graph module shares a single
# compiled graph + SqliteSaver connection, so concurrent resumes on the same
# thread (possible via the HTTP endpoint's asyncio.to_thread) could interleave
# update_state/put and corrupt the resume. The benchmark CLI is sequential.
_replay_lock = threading.Lock()


def _load_module(path: str) -> Any:
    """Import a Python file by absolute path; cache by mtime."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Graph file not found: {path}")
    key = str(p.resolve())
    with _import_lock:
        cached = _module_cache.get(key)
        if cached is not None:
            return cached
        spec = importlib.util.spec_from_file_location(
            f"husk_graph_{p.stem}_{uuid.uuid4().hex[:8]}", str(p)
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot build import spec for {path}")
        module = importlib.util.module_from_spec(spec)
        # Make `examples/` importable as a sibling so relative imports work.
        sys.path.insert(0, str(p.parent.parent))
        try:
            spec.loader.exec_module(module)
        finally:
            try:
                sys.path.remove(str(p.parent.parent))
            except ValueError:
                pass
        _module_cache[key] = module
        return module


def replay_graph(
    *,
    graph_module: str,
    state_override: dict[str, Any],
    new_thread_id: str | None = None,
    parent_thread_id: str | None = None,
    fork_node: str | None = None,
) -> dict[str, Any]:
    """Invoke a LangGraph defined in `graph_module` with `state_override`.

    `graph_module` is "<abs_path_to_file>:<symbol>" — typically ":graph" or
    ":invoke". If the symbol is callable, it's called with state_override.
    If it's a compiled graph, we call `.invoke(state_override, config={...})`.

    TRUE checkpoint resume: when both `parent_thread_id` and `fork_node` are
    given and the module exposes `replay_from`, we resume that thread from its
    checkpoint and re-run only `fork_node` onward (the upstream nodes are
    bypassed). Otherwise we fall back to a full re-run with a fresh thread, which
    is the original behaviour and keeps the endpoint backward compatible.
    """
    # Split on the LAST colon so Windows drive letters (C:\...) survive.
    path, _, symbol = graph_module.rpartition(":")
    if not path:
        # No symbol separator → assume whole string is the path, default symbol.
        path, symbol = graph_module, "graph"
    symbol = symbol or "graph"
    module = _load_module(path)

    # Preferred path: a true checkpoint resume that skips the upstream nodes.
    if parent_thread_id and fork_node:
        replay_from = getattr(module, "replay_from", None)
        if callable(replay_from):
            with _replay_lock:
                return replay_from(
                    state_override=state_override,
                    parent_thread_id=parent_thread_id,
                    fork_node=fork_node,
                )

    target = getattr(module, symbol, None)
    if target is None:
        raise AttributeError(f"{path} has no attribute {symbol!r}")

    tid = new_thread_id or str(uuid.uuid4())

    # Preferred path: module exposes its own `invoke(state, thread_id=...)`.
    fn = getattr(module, "invoke", None)
    if callable(fn) and fn is not target:
        return fn(state_override, thread_id=tid)

    # Otherwise treat the symbol as a compiled LangGraph.
    if hasattr(target, "invoke"):
        config = {"configurable": {"thread_id": tid}}
        result = target.invoke(state_override, config=config)
        return {"thread_id": tid, "state": dict(result) if hasattr(result, "items") else result}

    if callable(target):
        return {"thread_id": tid, "state": target(state_override)}

    raise TypeError(
        f"{symbol!r} is not invokable: expected a LangGraph or callable, got {type(target).__name__}"
    )
