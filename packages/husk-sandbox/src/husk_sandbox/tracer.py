from __future__ import annotations

import contextvars
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from ulid import ULID

from husk_shared import SpanKind, SpanStatus

log = logging.getLogger(__name__)

_current_span: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "husk_current_span", default=None
)


def _now_us() -> int:
    return time.time_ns() // 1_000


class SpanEmitter:
    """Single-process tracer that emits JSONL events to an append-only file.

    Thread-safe (one shared lock around the file handle). The backend ingest worker
    tails the same file. We deliberately keep the writer dumb: no batching, one line
    per event. Batching belongs in the ingest layer.
    """

    def __init__(self, run_id: str, event_path: Path):
        self.run_id = run_id
        self._path = event_path
        self._lock = threading.Lock()
        self._fh = event_path.open("a", encoding="utf-8", buffering=1)  # line-buffered
        # Stamp the run start.
        self._emit({"type": "run.start", "run_id": run_id, "ts": _now_us()})

    def close(self, status: str = "success", error: str | None = None) -> None:
        self._emit(
            {
                "type": "run.end",
                "run_id": self.run_id,
                "ts": _now_us(),
                "data": {"status": status, "error": error},
            }
        )
        with self._lock:
            self._fh.flush()
            self._fh.close()

    def start_span(
        self,
        *,
        kind: SpanKind,
        name: str,
        parent_span_id: str | None = None,
        input_inline: Any = None,
        attrs: dict[str, Any] | None = None,
    ) -> str:
        span_id = str(ULID())
        parent = parent_span_id if parent_span_id is not None else _current_span.get()
        self._emit(
            {
                "type": "span.start",
                "run_id": self.run_id,
                "span_id": span_id,
                "ts": _now_us(),
                "data": {
                    "parent_span_id": parent,
                    "kind": kind.value,
                    "name": name,
                    "input_inline": input_inline,
                    "attrs": attrs or {},
                },
            }
        )
        return span_id

    def end_span(
        self,
        span_id: str,
        *,
        status: SpanStatus = SpanStatus.SUCCESS,
        output_inline: Any = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        cost_usd: float | None = None,
        provider: str | None = None,
        model: str | None = None,
        error_payload: dict[str, Any] | None = None,
        attrs: dict[str, Any] | None = None,
    ) -> None:
        self._emit(
            {
                "type": "span.end",
                "run_id": self.run_id,
                "span_id": span_id,
                "ts": _now_us(),
                "data": {
                    "status": status.value,
                    "output_inline": output_inline,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_usd": cost_usd,
                    "provider": provider,
                    "model": model,
                    "error_payload": error_payload,
                    "attrs": attrs or {},
                },
            }
        )

    def _emit(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, default=_json_default, ensure_ascii=False)
        with self._lock:
            self._fh.write(line + "\n")


def _json_default(obj: Any) -> Any:
    """Last-resort JSON serializer for objects the user agent throws at us."""
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:  # noqa: BLE001
            pass
    if hasattr(obj, "__dict__"):
        return {"__repr__": repr(obj), "__type__": type(obj).__name__}
    return {"__repr__": repr(obj), "__type__": type(obj).__name__}


_emitter: SpanEmitter | None = None


def get_emitter() -> SpanEmitter | None:
    return _emitter


def install_emitter(emitter: SpanEmitter) -> None:
    global _emitter
    _emitter = emitter


def emitter_from_env() -> SpanEmitter | None:
    """Construct an emitter from HUSK_RUN_ID + HUSK_EVENT_PIPE env vars."""
    run_id = os.environ.get("HUSK_RUN_ID")
    event_path = os.environ.get("HUSK_EVENT_PIPE")
    if not run_id or not event_path:
        return None
    em = SpanEmitter(run_id, Path(event_path))
    install_emitter(em)
    return em
