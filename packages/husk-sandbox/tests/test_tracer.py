from __future__ import annotations

import json
from pathlib import Path

from husk_sandbox.tracer import SpanEmitter
from husk_shared import SpanKind, SpanStatus


def test_emitter_writes_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "events.jsonl"
    em = SpanEmitter("run-test", p)
    sid = em.start_span(kind=SpanKind.LLM, name="openai.chat", input_inline={"prompt": "hi"})
    em.end_span(sid, status=SpanStatus.SUCCESS, output_inline={"text": "hello"}, tokens_in=4, tokens_out=2)
    em.close()

    lines = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    types = [entry["type"] for entry in lines]
    assert types == ["run.start", "span.start", "span.end", "run.end"]
    assert lines[1]["data"]["kind"] == "llm"
    assert lines[2]["data"]["tokens_in"] == 4


def test_provider_cost_openai() -> None:
    from husk_sandbox.providers.openai import cost_usd

    c = cost_usd("gpt-4o-mini-2024-07-18", 1000, 500)
    assert c is not None
    assert c > 0


def test_provider_cost_anthropic() -> None:
    from husk_sandbox.providers.anthropic import cost_usd

    c = cost_usd("claude-3-5-sonnet-20240620", 1_000_000, 500_000)
    assert c is not None
    assert c > 0
