"""Minimal OTel GenAI emitter that hits Husk at http://localhost:7654/v1/traces.

Run with:
    uv run --group examples python examples/otel-autogen.py

What it does: opens an `agent.run` parent span and three child spans (one LLM
chat, one tool call, one second LLM chat). Each LLM span carries GenAI v1.36
attributes (gen_ai.system, gen_ai.request.model, gen_ai.usage.input_tokens,
etc.) and emits gen_ai.*.message events so Husk can display prompt + output.
"""

from __future__ import annotations

import logging
import os
import random
import time

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Standard OTel env var so the backend (or any caller) can override the port.
_otlp_base = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:7654").rstrip("/")
ENDPOINT = f"{_otlp_base}/v1/traces"

resource = Resource.create({"service.name": "otel-demo-agent"})
provider = TracerProvider(resource=resource)
exporter = OTLPSpanExporter(endpoint=ENDPOINT)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("husk.examples.otel-demo")
log = logging.getLogger(__name__)


def _llm_span(name: str, *, model: str, prompt: str, completion: str, tokens_in: int, tokens_out: int) -> None:
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("gen_ai.system", "openai")
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.response.model", model)
        span.set_attribute("gen_ai.usage.input_tokens", tokens_in)
        span.set_attribute("gen_ai.usage.output_tokens", tokens_out)
        span.add_event("gen_ai.user.message", {"content": prompt})
        span.add_event(
            "gen_ai.choice",
            {"finish_reason": "stop", "message.content": completion},
        )
        time.sleep(random.uniform(0.05, 0.15))


def _tool_span(name: str, *, tool: str, args: str, output: str) -> None:
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("gen_ai.tool.name", tool)
        span.set_attribute("gen_ai.tool.type", "function")
        span.add_event("gen_ai.tool.message", {"name": tool, "arguments": args, "content": output})
        time.sleep(random.uniform(0.02, 0.06))


def main() -> None:
    with tracer.start_as_current_span("agent.run") as root:
        root.set_attribute("service.name", "otel-demo-agent")
        root.set_attribute("gen_ai.system", "openai")

        _llm_span(
            "chat openai gpt-4o-mini (plan)",
            model="gpt-4o-mini",
            prompt="What's the capital of Italy and how many people live there?",
            completion="I'll look up the population, then answer.",
            tokens_in=42,
            tokens_out=18,
        )
        _tool_span(
            "tool: web_search",
            tool="web_search",
            args='{"q": "Rome population"}',
            output="Rome (Roma), Italy. Population: ~2.87M (2024).",
        )
        _llm_span(
            "chat openai gpt-4o (answer)",
            model="gpt-4o",
            prompt="Compose the final answer using the search result.",
            completion="Rome is the capital of Italy; ~2.87 million people live there.",
            tokens_in=88,
            tokens_out=64,
        )

    provider.shutdown()
    log.info(f"Sent traces to {ENDPOINT}.")
    log.info("Open http://localhost:5174/runs to see the new run.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
