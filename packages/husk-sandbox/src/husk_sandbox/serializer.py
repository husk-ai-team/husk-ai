"""Pydantic-aware serializer with a plugin registry.

Stub for M1 — implementation lands in M3 week 11. Plan:

* Pydantic v2 BaseModel  ->  `model_dump(mode="json")`
* LangChain BaseMessage   ->  custom plugin (role + content + tool_calls)
* LangGraph TypedDict     ->  recursive dict serialization
* dict / list / primitives ->  json.dumps as-is
* unknown                  ->  `{"__husk_unserialized__": True, "__repr__": repr(obj),
                                 "__type__": type(obj).__name__}`

The registry is module-level and additive (`register(type, fn)`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

_registry: dict[type, Callable[[Any], Any]] = {}


def register(t: type, fn: Callable[[Any], Any]) -> None:
    _registry[t] = fn


def to_jsonable(obj: Any) -> Any:
    for t, fn in _registry.items():
        if isinstance(obj, t):
            return fn(obj)
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json")
        except Exception:  # noqa: BLE001
            pass
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    return {
        "__husk_unserialized__": True,
        "__repr__": repr(obj),
        "__type__": type(obj).__name__,
    }
