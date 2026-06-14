"""Structural determinism of checkpoint-resume replay.

The load-bearing, genuinely-deterministic property behind the "100% replay
success" and token-bypass claims: resuming a parent run at a fork node re-runs
*exactly* that node and its successors, and nothing upstream. This test records a
real LangGraph run (canned LLM, no API key) and asserts the replay's executed
node set equals {fork} ∪ successors, with zero variance across repeats. It goes
red the instant replay drifts (e.g. an off-by-one in the predecessor map).
"""

from __future__ import annotations

import os
import tempfile
import uuid

import pytest

# The research graph reads HUSK_HOME and BENCH_FAST at import time (it builds a
# SqliteSaver and bakes in node sleeps), so set both before importing it: a
# throwaway home keeps ~/.husk untouched, and fast mode collapses the node
# sleeps so the suite runs in milliseconds, not minutes.
os.environ["HUSK_HOME"] = tempfile.mkdtemp(prefix="husk-determinism-")
os.environ["BENCH_FAST"] = "1"

pytest.importorskip("langgraph")

from opentelemetry import trace  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

from benchmark.research_agent import graph as G  # noqa: E402

NODE_NAMES = {"query_expansion", "retrieve", "analyze", "synthesize", "cite_check"}

# Resuming at `fork` must re-run exactly these nodes (fork + everything after).
EXPECTED: dict[str, set[str]] = {
    "cite_check": {"cite_check"},
    "synthesize": {"synthesize", "cite_check"},
    "analyze": {"analyze", "synthesize", "cite_check"},
    "retrieve": {"retrieve", "analyze", "synthesize", "cite_check"},
    "query_expansion": set(NODE_NAMES),  # predecessor is START -> full re-run
}


@pytest.fixture(scope="module")
def exporter() -> InMemorySpanExporter:
    exp = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exp))
    trace.set_tracer_provider(provider)
    G._tracer = None  # force the graph to bind to our in-memory provider
    return exp


def _replay_node_set(exp: InMemorySpanExporter, parent_thread_id: str, fork: str) -> set[str]:
    exp.clear()
    G.replay_from(state_override={}, parent_thread_id=parent_thread_id, fork_node=fork)
    return {s.name for s in exp.get_finished_spans() if s.name in NODE_NAMES}


@pytest.mark.parametrize("fork", sorted(EXPECTED))
def test_replay_reruns_exactly_fork_and_successors(exporter: InMemorySpanExporter, fork: str) -> None:
    tid = str(uuid.uuid4())
    G.invoke({"topic": f"determinism-{fork}", "failure_mode": None}, thread_id=tid)
    assert _replay_node_set(exporter, tid, fork) == EXPECTED[fork]


def test_replay_has_zero_variance(exporter: InMemorySpanExporter) -> None:
    observed: set[frozenset[str]] = set()
    for i in range(3):
        tid = str(uuid.uuid4())
        G.invoke({"topic": f"determinism-rep-{i}", "failure_mode": None}, thread_id=tid)
        observed.add(frozenset(_replay_node_set(exporter, tid, "synthesize")))
    assert observed == {frozenset(EXPECTED["synthesize"])}, observed
