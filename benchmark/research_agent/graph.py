"""Research Synthesizer -- 4-node LangGraph pipeline.

LLM nodes call Groq for real when GROQ_API_KEY is set, otherwise emit canned
spans. The benchmark's failure injection (N1-N4) overrides the output of the
LLM call to produce a controlled failure, but the LLM call still happens
so the token/cost numbers in the spans are real.

Layout (state moves left -> right):

    START -> query_expansion -> retrieve -> analyze -> synthesize -> cite_check -> END

`analyze` (large model, large output) is the cost-dominant upstream reasoning
step; `synthesize` is now a cheap downstream formatter. This mirrors real agents
(expensive retrieval/analysis early, cheap formatting late) so a replay that
forks downstream of `analyze` bypasses the bulk of the token cost.

Failure modes (injected by inject_failures.py for the failing 20%):

    None  -> clean success
    "N1"  -> malformed sub-queries
    "N2"  -> retrieve returns empty
    "N3"  -> hallucinated citations
    "N4"  -> cite_check accepts mismatched citations
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# When Husk's replay engine imports this file via importlib (during a
# /api/langgraph/replay), the `benchmark` package root may not be on
# sys.path. Insert the workspace root so `benchmark.research_agent.*`
# resolves either way.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from benchmark.research_agent import prompts  # noqa: E402
from benchmark.research_agent.mock_retrieve import (  # noqa: E402
    Source,
    render_sources,
)
from benchmark.research_agent.mock_retrieve import (  # noqa: E402
    retrieve as mock_retrieve,
)
from husk_shared.pricing import cost_usd  # noqa: E402

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OTel + Groq setup
# ---------------------------------------------------------------------------

_otlp_base = os.environ.get(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:7654"
).rstrip("/")
ENDPOINT = f"{_otlp_base}/v1/traces"
GRAPH_FILE = str(Path(__file__).resolve())

_FAST = os.environ.get("BENCH_FAST", "0") == "1"
_LATENCY_N1 = 0.001 if _FAST else 4.5        # query_expansion
_LATENCY_N2 = 0.001 if _FAST else 3.0        # retrieve
_LATENCY_ANALYZE = 0.001 if _FAST else 9.5   # analyze (cost-dominant, was synthesize)
_LATENCY_N3 = 0.001 if _FAST else 2.0        # synthesize (now a cheap formatter)
_LATENCY_N4 = 0.001 if _FAST else 5.0        # cite_check

# ---------------------------------------------------------------------------
# HTTP cassettes (model-free replay). When HUSK_RECORD_CASSETTE=1 the LLM HTTP
# calls of a run are recorded under ~/.husk/cassettes/<thread_id>/. When
# HUSK_REPLAY_CASSETTE=1 a replay is served from the parent's cassette instead of
# calling the provider — free, deterministic, byte-identical (cache miss on a
# changed request falls through to the real provider and is recorded). The httpx
# monkeypatch is process-global, so a lock serialises cassette sessions; recording
# is therefore meant for the sequential replay path or a single-worker run.
# ---------------------------------------------------------------------------

_cassette_lock = threading.Lock()


def _cassette_dir(thread_id: str) -> str:
    home = Path(os.environ.get("HUSK_HOME", str(Path.home() / ".husk")))
    return str(home / "cassettes" / thread_id)


@contextmanager
def _cassette_session(thread_id: str, *, record: bool, replay: bool):
    if not (record or replay):
        yield
        return
    from husk_sandbox import cassette  # lazy: keep the graph importable without the sandbox

    with _cassette_lock:
        cm = (
            cassette.replaying(_cassette_dir(thread_id))
            if replay
            else cassette.recording(_cassette_dir(thread_id))
        )
        with cm:
            yield


def _want_record() -> bool:
    return os.environ.get("HUSK_RECORD_CASSETTE") == "1"


def _want_replay_cassette() -> bool:
    return os.environ.get("HUSK_REPLAY_CASSETTE") == "1"


# ---------------------------------------------------------------------------
# LLM provider: Cerebras (preferred when CEREBRAS_API_KEY is set) or Groq.
# Both expose the same OpenAI-style `chat.completions.create` interface, so the
# call path is identical -- only the client and the default model names differ.
# ---------------------------------------------------------------------------

if os.environ.get("OPENROUTER_API_KEY"):
    _PROVIDER = "openrouter"
elif os.environ.get("CEREBRAS_API_KEY"):
    _PROVIDER = "cerebras"
else:
    _PROVIDER = "groq"


def _llm_key() -> str | None:
    # Read at call-time so a backend that boots without the key, then is asked
    # to replay with the key in env, still works. Priority matches _PROVIDER.
    return (
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("CEREBRAS_API_KEY")
        or os.environ.get("GROQ_API_KEY")
    )


def _use_llm() -> bool:
    return bool(_llm_key())


# Provider-aware default model names (override with LLM_MODEL_SMALL/LARGE, or the
# legacy GROQ_MODEL_SMALL/LARGE).
if _PROVIDER == "openrouter":
    # Same Llama family as the Groq run → directly comparable; non-reasoning →
    # predictable token counts (no cost blow-up). Cheap on OpenRouter.
    _SMALL_DEFAULT = "meta-llama/llama-3.1-8b-instruct"
    _LARGE_DEFAULT = "meta-llama/llama-3.3-70b-instruct"
elif _PROVIDER == "cerebras":
    _SMALL_DEFAULT, _LARGE_DEFAULT = "llama3.1-8b", "llama-3.3-70b"
else:
    _SMALL_DEFAULT, _LARGE_DEFAULT = "llama-3.1-8b-instant", "llama-3.3-70b-versatile"

MODEL_SMALL = os.environ.get(
    "LLM_MODEL_SMALL", os.environ.get("GROQ_MODEL_SMALL", _SMALL_DEFAULT)
)
MODEL_LARGE = os.environ.get(
    "LLM_MODEL_LARGE", os.environ.get("GROQ_MODEL_LARGE", _LARGE_DEFAULT)
)

MODEL_QUERY_EXPANSION = MODEL_SMALL
# analyze is the cost-dominant upstream node (large model, large output).
MODEL_ANALYZE = MODEL_LARGE
# synthesize is now a cheap downstream formatter (small model, short output).
MODEL_SYNTHESIZE = MODEL_SMALL
MODEL_CITE_CHECK = MODEL_SMALL

_tracer = None
_llm_client = None
_llm_client_key: str | None = None


def _get_tracer():
    global _tracer
    if _tracer is not None:
        return _tracer
    provider = trace.get_tracer_provider()
    if not hasattr(provider, "add_span_processor"):
        provider = TracerProvider(
            resource=Resource.create({"service.name": "research-synthesizer"})
        )
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=ENDPOINT))
        )
        trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("husk.benchmark.research_agent")
    return _tracer


def _get_client():
    global _llm_client, _llm_client_key
    key = _llm_key()
    if _llm_client is None or _llm_client_key != key:
        # LLM_MAX_RETRIES default 0: on a FREE tier a 429 fails FAST instead of
        # letting the SDK block for minutes on the server's Retry-After (which
        # made a throttled batch take hours). On a PAID tier set LLM_MAX_RETRIES=2
        # so rare transient 429s recover cleanly. The short timeout still caps
        # any single hung call; persistent throttling yields a 0-token span we
        # filter out in analysis.
        retries = int(os.environ.get("LLM_MAX_RETRIES", "0"))
        if _PROVIDER == "openrouter":
            from openai import OpenAI

            _llm_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=key,
                max_retries=retries,
                timeout=30.0,
            )
        elif _PROVIDER == "cerebras":
            from cerebras.cloud.sdk import Cerebras

            _llm_client = Cerebras(api_key=key, max_retries=retries, timeout=30.0)
        else:
            from groq import Groq

            _llm_client = Groq(api_key=key, max_retries=retries, timeout=30.0)
        _llm_client_key = key
    return _llm_client


def _call_groq(
    model: str,
    system: str,
    user: str,
    max_tokens: int = 400,
    temperature: float = 0.3,
) -> tuple[str, int, int]:
    """Make a real LLM call (Cerebras or Groq). Returns (content, in, out).

    Retries once on transient errors. If no provider key is set, falls back to
    canned numbers so the benchmark still completes. (Name kept for the node
    call sites; the provider is selected by `_PROVIDER`.)
    """
    if not _use_llm():
        # Canned fallback — same numbers as the original synthetic benchmark.
        return (
            "(canned response — set CEREBRAS_API_KEY or GROQ_API_KEY for real LLM calls)",
            len(system) // 4 + len(user) // 4,
            80,
        )

    client = _get_client()
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            choice = resp.choices[0].message.content or ""
            usage = resp.usage
            ti = usage.prompt_tokens if usage else 0
            to = usage.completion_tokens if usage else 0
            return choice, int(ti), int(to)
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt == 0:
                time.sleep(0.5)
                continue
    log.warning("%s call failed after retry: %s", _PROVIDER, last_err)
    return f"({_PROVIDER} error: {type(last_err).__name__})", 0, 0


def _set_llm_attrs(
    span, system_name: str, model: str, tokens_in: int, tokens_out: int
) -> None:
    # Record the real provider (cerebras/groq), ignoring the legacy literal
    # passed by the node call sites.
    span.set_attribute("gen_ai.system", _PROVIDER)
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.request.model", model)
    span.set_attribute("gen_ai.response.model", model)
    span.set_attribute("gen_ai.usage.input_tokens", tokens_in)
    span.set_attribute("gen_ai.usage.output_tokens", tokens_out)
    c = cost_usd(model, tokens_in, tokens_out)
    if c is not None:
        span.set_attribute("gen_ai.usage.cost_usd", c)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class State(TypedDict, total=False):
    topic: str
    failure_mode: str | None  # None | "N1" | "N2" | "N3" | "N4"
    sub_queries: list[str]
    sources: list[dict]
    analysis: str
    answer: str
    verdict: str
    status: str
    error_node: str | None


# ---------------------------------------------------------------------------
# Node 1 -- query_expansion
# ---------------------------------------------------------------------------


def query_expansion(state: State) -> dict:
    tracer = _get_tracer()
    topic = state.get("topic", "")
    fail = state.get("failure_mode")
    with tracer.start_as_current_span("query_expansion") as span:
        span.set_attribute("langgraph.node", "query_expansion")

        user_msg = prompts.QUERY_EXPANSION_USER.format(topic=topic)
        span.add_event("gen_ai.user.message", {"content": user_msg})

        content, ti, to = _call_groq(
            MODEL_QUERY_EXPANSION,
            prompts.QUERY_EXPANSION_SYSTEM,
            user_msg,
            max_tokens=200,
        )
        _set_llm_attrs(span, "groq", MODEL_QUERY_EXPANSION, ti, to)

        if fail == "N1":
            sub_queries = [topic]
            span.set_attribute("benchmark.failure_mode", "N1")
            span.set_status(trace.Status(trace.StatusCode.ERROR, "malformed expansion"))
            span.add_event(
                "gen_ai.choice",
                {"finish_reason": "stop", "message.content": json.dumps(sub_queries)},
            )
            time.sleep(_LATENCY_N1)
            return {
                "sub_queries": sub_queries,
                "status": "error",
                "error_node": "query_expansion",
            }

        # Try to parse Groq's JSON output, otherwise fall back to a deterministic list.
        sub_queries: list[str] = []
        try:
            parsed = json.loads(content) if content.strip().startswith("[") else None
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                sub_queries = parsed[:5]
        except (json.JSONDecodeError, ValueError):
            pass
        if not sub_queries:
            sub_queries = [
                f"{topic} overview",
                f"{topic} key facts",
                f"{topic} recent developments",
                f"{topic} criticism",
            ]

        span.add_event(
            "gen_ai.choice",
            {"finish_reason": "stop", "message.content": json.dumps(sub_queries)},
        )
        time.sleep(_LATENCY_N1)
        return {"sub_queries": sub_queries}


# ---------------------------------------------------------------------------
# Node 2 -- retrieve (mock tool)
# ---------------------------------------------------------------------------


def retrieve(state: State) -> dict:
    tracer = _get_tracer()
    topic = state.get("topic", "")
    sub_queries = state.get("sub_queries") or [topic]
    fail = state.get("failure_mode")
    with tracer.start_as_current_span("retrieve") as span:
        span.set_attribute("gen_ai.tool.name", prompts.RETRIEVE_TOOL_NAME)
        span.set_attribute("gen_ai.tool.type", "function")
        span.set_attribute("langgraph.node", "retrieve")
        span.set_attribute("retrieve.query_count", len(sub_queries))

        all_sources: list[Source] = []
        force_empty = fail == "N2"
        for q in sub_queries[:2]:
            all_sources.extend(mock_retrieve(topic, q, force_empty=force_empty))

        span.add_event(
            "gen_ai.tool.message",
            {
                "name": prompts.RETRIEVE_TOOL_NAME,
                "arguments": json.dumps({"queries": sub_queries[:2]}),
                "content": render_sources(all_sources),
            },
        )

        if force_empty:
            span.set_attribute("benchmark.failure_mode", "N2")
            span.set_status(trace.Status(trace.StatusCode.ERROR, "empty result"))
            time.sleep(_LATENCY_N2)
            return {
                "sources": [],
                "status": "error",
                "error_node": "retrieve",
            }

        time.sleep(_LATENCY_N2)
        return {
            "sources": [
                {"id": s.id, "title": s.title, "snippet": s.snippet}
                for s in all_sources
            ]
        }


# ---------------------------------------------------------------------------
# Node 3 -- analyze (LLM, large model) -- cost-dominant upstream reasoning
# ---------------------------------------------------------------------------


def analyze(state: State) -> dict:
    tracer = _get_tracer()
    topic = state.get("topic", "")
    sources = state.get("sources") or []

    with tracer.start_as_current_span("analyze") as span:
        span.set_attribute("langgraph.node", "analyze")

        sources_rendered = "\n".join(
            f"[{s['id']}] {s['title']}: {s['snippet']}" for s in sources
        )
        user_msg = prompts.ANALYZE_USER.format(
            topic=topic, sources=sources_rendered or "(no sources)"
        )
        span.add_event("gen_ai.user.message", {"content": user_msg})

        if not sources:
            # Upstream N2 produced no sources -- nothing to analyse, propagate.
            _set_llm_attrs(span, "groq", MODEL_ANALYZE, 0, 0)
            span.set_status(trace.Status(trace.StatusCode.ERROR, "no sources"))
            analysis = f"(no sources to analyse for '{topic}')"
        else:
            # The expensive call: large model, large output. This is the bulk
            # of the graph's token cost and the work a downstream replay skips.
            content, ti, to = _call_groq(
                MODEL_ANALYZE,
                prompts.ANALYZE_SYSTEM,
                user_msg,
                max_tokens=700,
            )
            _set_llm_attrs(span, "groq", MODEL_ANALYZE, ti, to)
            analysis = content or f"(analysis unavailable for '{topic}')"

        span.add_event(
            "gen_ai.choice",
            {"finish_reason": "stop", "message.content": analysis},
        )
        time.sleep(_LATENCY_ANALYZE)
        return {"analysis": analysis}


# ---------------------------------------------------------------------------
# Node 4 -- synthesize (LLM, small model) -- cheap downstream formatter
# ---------------------------------------------------------------------------


def synthesize(state: State) -> dict:
    tracer = _get_tracer()
    topic = state.get("topic", "")
    sources = state.get("sources") or []
    fail = state.get("failure_mode")

    with tracer.start_as_current_span("synthesize") as span:
        span.set_attribute("langgraph.node", "synthesize")

        sources_rendered = "\n".join(
            f"[{s['id']}] {s['title']}: {s['snippet']}" for s in sources
        )
        user_msg = prompts.SYNTHESIZE_USER.format(
            topic=topic,
            sources=sources_rendered or "(no sources)",
            analysis=state.get("analysis") or "(no analysis)",
        )
        span.add_event("gen_ai.user.message", {"content": user_msg})

        if not sources:
            # Upstream N2 already errored -- skip the real LLM call, propagate.
            _set_llm_attrs(span, "groq", MODEL_SYNTHESIZE, 0, 0)
            span.set_status(trace.Status(trace.StatusCode.ERROR, "no sources"))
            answer = f"(could not synthesise -- no sources for '{topic}')"
        else:
            # Cheap formatter: small model, short output -- it just turns the
            # analysis into a cited answer.
            content, ti, to = _call_groq(
                MODEL_SYNTHESIZE,
                prompts.SYNTHESIZE_SYSTEM,
                user_msg,
                max_tokens=150,
            )
            _set_llm_attrs(span, "groq", MODEL_SYNTHESIZE, ti, to)

            if fail == "N3":
                # Override the LLM's content with a known-bad answer (mismatched cites).
                span.set_attribute("benchmark.failure_mode", "N3")
                answer = (
                    f"{topic.capitalize()} can be characterised by three things [1], "
                    f"[2], and [9]. Recent developments [3] confirm earlier "
                    f"speculation [9]. See [9] for further reading."
                )
            else:
                answer = content or (
                    f"{topic.capitalize()} can be characterised through several "
                    f"angles [1][2]. The available evidence [3] suggests a stable "
                    f"trend, though [4] introduces concerns."
                )

        span.add_event(
            "gen_ai.choice",
            {"finish_reason": "stop", "message.content": answer},
        )
        time.sleep(_LATENCY_N3)
        update: dict = {"answer": answer}
        if fail == "N3":
            update["status"] = "error"
            update["error_node"] = "synthesize"
        return update


# ---------------------------------------------------------------------------
# Node 4 -- cite_check (LLM, small model)
# ---------------------------------------------------------------------------


def cite_check(state: State) -> dict:
    tracer = _get_tracer()
    answer = state.get("answer", "")
    sources = state.get("sources") or []
    fail = state.get("failure_mode")

    with tracer.start_as_current_span("cite_check") as span:
        span.set_attribute("langgraph.node", "cite_check")

        sources_rendered = "\n".join(
            f"[{s['id']}] {s['title']}" for s in sources
        )
        user_msg = prompts.CITE_CHECK_USER.format(
            answer=answer, sources=sources_rendered
        )
        span.add_event("gen_ai.user.message", {"content": user_msg})

        # Real call for token/cost.
        content, ti, to = _call_groq(
            MODEL_CITE_CHECK,
            prompts.CITE_CHECK_SYSTEM,
            user_msg,
            max_tokens=20,
        )
        _set_llm_attrs(span, "groq", MODEL_CITE_CHECK, ti, to)

        # Deterministic verdict logic (we don't trust the LLM here -- this
        # node is a citation auditor, we compute correctness ourselves).
        all_cite_ids = {s["id"] for s in sources}
        cited = set()
        for token in answer.split("["):
            head = token.split("]")[0]
            try:
                cited.add(int(head))
            except ValueError:
                pass
        mismatched = cited - all_cite_ids

        upstream_status = state.get("status")
        upstream_error_node = state.get("error_node")

        if fail == "N4":
            verdict = "valid"
            span.set_attribute("benchmark.failure_mode", "N4")
            status_update: dict = {"status": "error", "error_node": "cite_check"}
        elif mismatched:
            verdict = "mismatch"
            status_update = {"status": "error", "error_node": "cite_check"}
            span.set_status(trace.Status(trace.StatusCode.ERROR, "mismatch"))
        elif upstream_status == "error":
            verdict = "valid" if not mismatched else "mismatch"
            status_update = {
                "status": "error",
                "error_node": upstream_error_node,
            }
        else:
            verdict = "valid"
            status_update = {"status": "ok"}

        span.add_event(
            "gen_ai.choice",
            {"finish_reason": "stop", "message.content": verdict},
        )
        # Use the verdict we computed, but also expose what Groq said for transparency.
        if content:
            span.add_event(
                "gen_ai.choice.llm_response",
                {"finish_reason": "stop", "message.content": content[:120]},
            )
        time.sleep(_LATENCY_N4)
        return {"verdict": verdict, **status_update}


# ---------------------------------------------------------------------------
# Build & invoke
# ---------------------------------------------------------------------------


def _db_path() -> str:
    home = Path(os.environ.get("HUSK_HOME", str(Path.home() / ".husk")))
    home.mkdir(parents=True, exist_ok=True)
    return str(home / "benchmark_research.sqlite")


def _build_graph_with_saver() -> tuple[object, SqliteSaver, sqlite3.Connection]:
    builder = StateGraph(State)
    builder.add_node("query_expansion", query_expansion)
    builder.add_node("retrieve", retrieve)
    builder.add_node("analyze", analyze)
    builder.add_node("synthesize", synthesize)
    builder.add_node("cite_check", cite_check)

    builder.add_edge(START, "query_expansion")
    builder.add_edge("query_expansion", "retrieve")
    builder.add_edge("retrieve", "analyze")
    builder.add_edge("analyze", "synthesize")
    builder.add_edge("synthesize", "cite_check")
    builder.add_edge("cite_check", END)

    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    saver = SqliteSaver(conn=conn)
    return builder.compile(checkpointer=saver), saver, conn


graph, _saver, _conn = _build_graph_with_saver()


def invoke(state: dict, thread_id: str | None = None) -> dict:
    tracer = _get_tracer()
    tid = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": tid}}

    with tracer.start_as_current_span("agent.run") as root:
        root.set_attribute("service.name", "research-synthesizer")
        root.set_attribute("gen_ai.system", "langgraph")
        root.set_attribute("langgraph.thread_id", tid)
        root.set_attribute("husk.graph_module", f"{GRAPH_FILE}:graph")
        root.set_attribute("husk.benchmark.real_llm", _use_llm())
        if state.get("failure_mode"):
            root.set_attribute("benchmark.failure_mode", state["failure_mode"])
        with _cassette_session(tid, record=_want_record(), replay=False):
            result = graph.invoke(state, config=config)
        root.set_attribute("benchmark.status", result.get("status", "ok"))
        if result.get("status") == "error":
            root.set_status(
                trace.Status(
                    trace.StatusCode.ERROR,
                    f"failed at {result.get('error_node')}",
                )
            )

    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()  # type: ignore[attr-defined]

    return {"thread_id": tid, "state": dict(result)}


# ---------------------------------------------------------------------------
# Checkpoint resume (modify-and-replay) -- the real primitive
# ---------------------------------------------------------------------------
#
# `invoke` above is a full run from scratch. `replay_from` resumes an EXISTING
# thread from its SqliteSaver checkpoint, applies a state patch, and re-executes
# ONLY the fork node + its successors. The upstream nodes are not re-run, so they
# emit no spans and consume no tokens -- that bypass is the whole point of Husk.
#
# Mechanic (LangGraph "time travel"): update_state(cfg, values, as_node=N) writes
# `values` to the channels as if node N produced them, which sets `next` to N's
# successors; invoke(None, cfg) then resumes from there. To RE-RUN node X we must
# therefore pass X's PREDECESSOR as `as_node` (passing X itself would skip X).
# update_state runs only the node's channel writers, not its Python function, so
# the predecessor is not re-executed either.

_PREDECESSOR = {
    "query_expansion": START,  # START is a real (hidden) node -> full re-run (N1)
    "retrieve": "query_expansion",
    "analyze": "retrieve",
    "synthesize": "analyze",
    "cite_check": "synthesize",
}


def replay_from(
    *, state_override: dict, parent_thread_id: str, fork_node: str
) -> dict:
    """Resume `parent_thread_id` from its checkpoint and re-run `fork_node` onward.

    Applies `state_override` (plus a reset of the stale failure channels) at the
    fork point so the re-run is clean, then resumes. Returns the child's thread_id
    (same as the parent -- checkpoints live under one thread), a unique `child_id`
    used to locate the resulting run, and the final state.
    """
    tracer = _get_tracer()
    as_node = _PREDECESSOR.get(fork_node, START)
    cfg = {"configurable": {"thread_id": parent_thread_id}}

    # Clear the parent's stale failure channels. Without this, cite_check's
    # `elif upstream_status == "error"` branch would re-flag the fixed child as
    # an error. Writing None filters the key out of the materialised state.
    values = {
        **state_override,
        "failure_mode": None,
        "status": None,
        "error_node": None,
    }
    child_id = str(uuid.uuid4())

    with tracer.start_as_current_span("agent.run") as root:
        root.set_attribute("service.name", "research-synthesizer")
        root.set_attribute("gen_ai.system", "langgraph")
        root.set_attribute("langgraph.thread_id", parent_thread_id)
        root.set_attribute("husk.graph_module", f"{GRAPH_FILE}:graph")
        root.set_attribute("husk.benchmark.real_llm", _use_llm())
        # Unique marker so the caller can find THIS child run (parent and child
        # share a thread_id, so thread_id alone is ambiguous).
        root.set_attribute("husk.replay.child_id", child_id)
        root.set_attribute("husk.replay.fork_node", fork_node)
        root.set_attribute("husk.replay.cassette", _want_replay_cassette())

        new_cfg = graph.update_state(cfg, values, as_node=as_node)
        with _cassette_session(parent_thread_id, record=False, replay=_want_replay_cassette()):
            result = graph.invoke(None, config=new_cfg)

        root.set_attribute("benchmark.status", result.get("status", "ok"))
        if result.get("status") == "error":
            root.set_status(
                trace.Status(
                    trace.StatusCode.ERROR,
                    f"failed at {result.get('error_node')}",
                )
            )

    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()  # type: ignore[attr-defined]

    return {
        "thread_id": parent_thread_id,
        "child_id": child_id,
        "state": dict(result),
    }
