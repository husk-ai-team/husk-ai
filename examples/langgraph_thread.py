"""Minimal LangGraph example with SQLite checkpointer + OTel instrumentation.

Run:
    uv run --group examples python examples/langgraph_thread.py

The graph has two nodes (planner → answerer). Each invocation:
- creates a new thread_id (stored in OTel attrs as `langgraph.thread_id`)
- emits OTel spans per node (so the run appears in Husk via /v1/traces)
- writes checkpoints to ~/.husk/langgraph_demo.sqlite

The backend's /api/langgraph/replay endpoint re-imports THIS file by path and
invokes `graph` with a modified state. The Studio Replay page wires that to a
"Run from here" button.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

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


def _get_tracer():
    global _tracer
    if _tracer is not None:
        return _tracer
    provider = trace.get_tracer_provider()
    # If no provider is configured (or only the proxy), set ours up.
    if not hasattr(provider, "add_span_processor"):
        provider = TracerProvider(
            resource=Resource.create({"service.name": "langgraph-demo"})
        )
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=ENDPOINT))
        )
        trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("husk.examples.langgraph")
    return _tracer


# --- Graph definition ------------------------------------------------------


class State(TypedDict, total=False):
    topic: str
    plan: str
    answer: str


def planner(state: State) -> dict:
    tracer = _get_tracer()
    with tracer.start_as_current_span("planner") as span:
        span.set_attribute("gen_ai.system", "openai")
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "gpt-4o-mini")
        span.set_attribute("gen_ai.usage.input_tokens", 24)
        span.set_attribute("gen_ai.usage.output_tokens", 32)
        span.set_attribute("langgraph.node", "planner")
        span.add_event(
            "gen_ai.user.message",
            {"content": f"Plan for topic: {state.get('topic', '?')}"},
        )
        plan = f"1. Research {state.get('topic')}\n2. Summarize\n3. Format final answer"
        span.add_event(
            "gen_ai.choice",
            {"finish_reason": "stop", "message.content": plan},
        )
        time.sleep(0.08)
        return {"plan": plan}


def answerer(state: State) -> dict:
    tracer = _get_tracer()
    with tracer.start_as_current_span("answerer") as span:
        span.set_attribute("gen_ai.system", "openai")
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "gpt-4o")
        span.set_attribute("gen_ai.usage.input_tokens", 64)
        span.set_attribute("gen_ai.usage.output_tokens", 96)
        span.set_attribute("langgraph.node", "answerer")
        span.add_event(
            "gen_ai.user.message",
            {"content": f"plan={state.get('plan')}\ntopic={state.get('topic')}"},
        )
        topic = state.get("topic", "")
        plan = state.get("plan", "")
        # Tiny canned response that varies by topic so branches look meaningful.
        if "rome" in topic.lower():
            answer = "Rome is the capital of Italy with ~2.87M people."
        elif "tokyo" in topic.lower():
            answer = "Tokyo is the capital of Japan with ~14M people."
        else:
            answer = f"{topic.capitalize()} — answered using plan: {plan[:40]}…"
        span.add_event(
            "gen_ai.choice",
            {"finish_reason": "stop", "message.content": answer},
        )
        time.sleep(0.12)
        return {"answer": answer}


def _db_path() -> str:
    home = Path(os.environ.get("HUSK_HOME", str(Path.home() / ".husk")))
    home.mkdir(parents=True, exist_ok=True)
    return str(home / "langgraph_demo.sqlite")


def _build_graph_with_saver() -> tuple[object, SqliteSaver, sqlite3.Connection]:
    """Build the graph; keeps the SQLite connection open so the saver stays usable."""
    builder = StateGraph(State)
    builder.add_node("planner", planner)
    builder.add_node("answerer", answerer)
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "answerer")
    builder.add_edge("answerer", END)

    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    saver = SqliteSaver(conn=conn)
    return builder.compile(checkpointer=saver), saver, conn


# Built at import time so backend replay can do `from examples.langgraph_thread import graph`.
graph, _saver, _conn = _build_graph_with_saver()


def invoke(state: dict, thread_id: str | None = None) -> dict:
    """Run the graph with given initial state. Returns the final state dict."""
    tracer = _get_tracer()
    tid = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": tid}}

    with tracer.start_as_current_span("agent.run") as root:
        root.set_attribute("service.name", "langgraph-demo")
        root.set_attribute("gen_ai.system", "langgraph")
        root.set_attribute("langgraph.thread_id", tid)
        root.set_attribute("husk.graph_module", f"{GRAPH_FILE}:graph")
        result = graph.invoke(state, config=config)
        root.set_attribute("langgraph.final_state", str(result))

    # Flush the OTel batch so the trace reaches Husk before we return.
    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()  # type: ignore[attr-defined]

    return {"thread_id": tid, "state": dict(result)}


def main() -> None:
    result = invoke({"topic": "Rome"})
    log.info(f"Thread:  {result['thread_id']}")
    log.info(f"State:   {result['state']}")
    log.info("Open http://localhost:5174/runs to see the run.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
