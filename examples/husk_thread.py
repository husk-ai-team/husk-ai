"""Minimal example agent on Husk's own engine, with OTel instrumentation.

Run:
    uv run --group examples python examples/husk_thread.py

The graph has two nodes (planner -> answerer) running on `husk_shared.engine`:
a linear executor plus a local SQLite snapshot store. Each invocation:
- creates a new thread_id (stored in OTel attrs as `husk.thread_id`)
- emits OTel spans per node (so the run appears in Husk via /v1/traces)
- writes a state snapshot after every node to ~/.husk/husk_demo.sqlite

The backend's /api/replay endpoint re-imports THIS file by path and either
resumes it from a snapshot (`replay_from`) or re-invokes it (`invoke`) with a
modified state. The Studio Replay page wires that to a "Run from here" button:
resuming at a node re-runs only that node and its successors, so the upstream
nodes emit no spans and consume no tokens.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from pathlib import Path

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from husk_shared.engine import LinearExecutor, LinearGraph, SnapshotStore

log = logging.getLogger(__name__)

# OTLP endpoint — honors $OTEL_EXPORTER_OTLP_ENDPOINT (standard OTel env var)
# so the backend can override when replaying on a non-default port. Falls back
# to the default Husk port.
_otlp_base = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:7654").rstrip("/")
ENDPOINT = f"{_otlp_base}/v1/traces"
GRAPH_FILE = str(Path(__file__).resolve())

# Tracer is set up lazily so the module can be re-imported by the backend
# without setting up another global processor.
_tracer = None


def _get_tracer():  # type: ignore[no-untyped-def]
    global _tracer
    if _tracer is not None:
        return _tracer
    provider = trace.get_tracer_provider()
    if not hasattr(provider, "add_span_processor"):
        provider = TracerProvider(resource=Resource.create({"service.name": "husk-demo"}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=ENDPOINT)))
        trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("husk.examples.husk_thread")
    return _tracer


# --- Nodes: plain callables (state) -> state delta --------------------------


def planner(state: dict) -> dict:
    tracer = _get_tracer()
    with tracer.start_as_current_span("planner") as span:
        span.set_attribute("gen_ai.system", "openai")
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "gpt-4o-mini")
        span.set_attribute("gen_ai.usage.input_tokens", 24)
        span.set_attribute("gen_ai.usage.output_tokens", 32)
        span.set_attribute("husk.node", "planner")
        span.add_event("gen_ai.user.message", {"content": f"Plan for topic: {state.get('topic', '?')}"})
        plan = f"1. Research {state.get('topic')}\n2. Summarize\n3. Format final answer"
        span.add_event("gen_ai.choice", {"finish_reason": "stop", "message.content": plan})
        time.sleep(0.08)
        return {"plan": plan}


def answerer(state: dict) -> dict:
    tracer = _get_tracer()
    with tracer.start_as_current_span("answerer") as span:
        span.set_attribute("gen_ai.system", "openai")
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "gpt-4o")
        span.set_attribute("gen_ai.usage.input_tokens", 64)
        span.set_attribute("gen_ai.usage.output_tokens", 96)
        span.set_attribute("husk.node", "answerer")
        span.add_event(
            "gen_ai.user.message",
            {"content": f"plan={state.get('plan')}\ntopic={state.get('topic')}"},
        )
        topic = state.get("topic", "")
        plan = state.get("plan", "")
        if "rome" in topic.lower():
            answer = "Rome is the capital of Italy with ~2.87M people."
        elif "tokyo" in topic.lower():
            answer = "Tokyo is the capital of Japan with ~14M people."
        else:
            answer = f"{topic.capitalize()} — answered using plan: {plan[:40]}…"
        span.add_event("gen_ai.choice", {"finish_reason": "stop", "message.content": answer})
        time.sleep(0.12)
        return {"answer": answer}


# --- Husk-native graph + snapshot store -------------------------------------


def _snapshot_db_path() -> str:
    home = Path(os.environ.get("HUSK_HOME", str(Path.home() / ".husk")))
    home.mkdir(parents=True, exist_ok=True)
    return str(home / "husk_demo.sqlite")


def _build_graph() -> LinearGraph:
    g = LinearGraph()
    g.add_node("planner", planner)
    g.add_node("answerer", answerer)
    return g


# Built at import time so the backend can do `from examples.husk_thread import graph`.
graph = _build_graph()

_store: SnapshotStore | None = None
_store_lock = threading.Lock()


def _get_store() -> SnapshotStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = SnapshotStore(_snapshot_db_path())
        return _store


def invoke(state: dict, thread_id: str | None = None) -> dict:
    """Run the graph from scratch, snapshotting after each node."""
    tracer = _get_tracer()
    tid = thread_id or str(uuid.uuid4())
    executor = LinearExecutor(graph, _get_store())

    with tracer.start_as_current_span("agent.run") as root:
        root.set_attribute("service.name", "husk-demo")
        root.set_attribute("husk.thread_id", tid)
        root.set_attribute("husk.graph_module", f"{GRAPH_FILE}:graph")
        root.set_attribute("husk.replay.engine", "husk-native")
        result = executor.run_full(tid, state)
        root.set_attribute("husk.final_state", str(result))

    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()  # type: ignore[attr-defined]

    return {"thread_id": tid, "state": dict(result)}


def replay_from(*, state_override: dict, parent_thread_id: str, fork_node: str) -> dict:
    """Resume `parent_thread_id` from its snapshot and re-run `fork_node` onward.

    Upstream nodes are not re-run: their state comes from the snapshot, so they
    emit no spans and consume no tokens.
    """
    tracer = _get_tracer()
    executor = LinearExecutor(graph, _get_store())
    child_id = str(uuid.uuid4())
    child_thread_id = f"{parent_thread_id}::replay::{child_id}"

    with tracer.start_as_current_span("agent.run") as root:
        root.set_attribute("service.name", "husk-demo")
        root.set_attribute("husk.thread_id", parent_thread_id)
        root.set_attribute("husk.graph_module", f"{GRAPH_FILE}:graph")
        root.set_attribute("husk.replay.engine", "husk-native")
        root.set_attribute("husk.replay.child_id", child_id)
        root.set_attribute("husk.replay.fork_node", fork_node)
        result = executor.resume(
            parent_thread_id=parent_thread_id,
            child_thread_id=child_thread_id,
            fork_node=fork_node,
            patch=dict(state_override),
        )
        root.set_attribute("husk.final_state", str(result))

    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()  # type: ignore[attr-defined]

    return {"thread_id": parent_thread_id, "child_id": child_id, "state": dict(result)}


def main() -> None:
    result = invoke({"topic": "Rome"})
    log.info(f"Thread:  {result['thread_id']}")
    log.info(f"State:   {result['state']}")
    log.info("Open http://localhost:5174/runs to see the run, then 'Modify and replay'.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
