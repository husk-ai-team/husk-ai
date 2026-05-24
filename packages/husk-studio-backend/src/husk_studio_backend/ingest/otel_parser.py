"""Parse OTLP traces (JSON shape) into Husk Run/Span rows.

Supports OTel GenAI v1.36 semantic conventions with a defensive fallback to
older names (`gen_ai.usage.prompt_tokens` → `input_tokens`).

The input shape matches OTLP/HTTP JSON output (also what
`google.protobuf.json_format.MessageToDict` produces from the proto form).
"""

from __future__ import annotations

import base64
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


def decode_attr_value(v: dict[str, Any]) -> Any:
    """Decode an OTLP AnyValue dict into a native Python value."""
    if not v:
        return None
    if "stringValue" in v:
        return v["stringValue"]
    if "intValue" in v:
        try:
            return int(v["intValue"])
        except (TypeError, ValueError):
            return None
    if "doubleValue" in v:
        try:
            return float(v["doubleValue"])
        except (TypeError, ValueError):
            return None
    if "boolValue" in v:
        return bool(v["boolValue"])
    if "arrayValue" in v:
        return [decode_attr_value(x) for x in v["arrayValue"].get("values") or []]
    if "kvlistValue" in v:
        return decode_attributes(v["kvlistValue"].get("values") or [])
    if "bytesValue" in v:
        return v["bytesValue"]
    return None


def decode_attributes(attrs: Iterable[dict]) -> dict[str, Any]:
    """Decode an OTLP attributes list into a flat {key: value} dict."""
    out: dict[str, Any] = {}
    for a in attrs or []:
        k = a.get("key")
        if k is None:
            continue
        out[k] = decode_attr_value(a.get("value") or {})
    return out


def _nano_to_ms(n: Any) -> int:
    if n is None:
        return 0
    try:
        return int(n) // 1_000_000
    except (TypeError, ValueError):
        return 0


def _resolve_kind(span_attrs: dict[str, Any]) -> str:
    """Heuristic mapping from GenAI span attributes to Husk span kinds.

    Note: `gen_ai.system` alone is not enough (root agent spans often set
    just the system tag for context). We require `gen_ai.operation.name` to
    classify as `llm`.
    """
    if span_attrs.get("gen_ai.tool.name") or span_attrs.get("gen_ai.tool.type"):
        return "tool"
    if "gen_ai.operation.name" in span_attrs:
        return "llm"
    return "chain"


def _tokens(attrs: dict[str, Any], side: str) -> int | None:
    # v1.36: gen_ai.usage.input_tokens / output_tokens
    # legacy: gen_ai.usage.prompt_tokens / completion_tokens
    v = attrs.get(f"gen_ai.usage.{side}_tokens")
    if v is None:
        legacy = {"input": "prompt", "output": "completion"}[side]
        v = attrs.get(f"gen_ai.usage.{legacy}_tokens")
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _normalize_id(s: str) -> str:
    """Normalize an OTLP trace/span ID to hex (lowercase).

    The JSON wire form represents bytes as hex; the proto wire form (after
    `MessageToDict`) represents them as base64. We canonicalize so URLs and
    DB keys are stable regardless of input format.
    """
    if not s:
        return ""
    s = s.replace("-", "")
    if all(c in "0123456789abcdefABCDEF" for c in s):
        return s.lower()
    # Treat as base64 — pad if needed before decoding.
    try:
        padded = s + "=" * ((-len(s)) % 4)
        return base64.b64decode(padded).hex()
    except Exception:  # noqa: BLE001
        return s


def _trace_id_to_run_id(trace_id: str) -> str:
    # Stable + idempotent: first 26 hex chars (~104 bits of entropy).
    return _normalize_id(trace_id)[:26]


def _span_id_short(span_id: str) -> str:
    return _normalize_id(span_id)[:26]


def _extract_messages(events: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split GenAI span events into input messages and output choices."""
    inputs: list[dict] = []
    outputs: list[dict] = []
    for ev in events or []:
        name = ev.get("name") or ""
        attrs = decode_attributes(ev.get("attributes") or [])
        if name.startswith("gen_ai.") and name.endswith(".message"):
            # e.g. gen_ai.user.message, gen_ai.assistant.message, gen_ai.tool.message
            role = name.removeprefix("gen_ai.").removesuffix(".message")
            inputs.append({"role": role, **attrs})
        elif name == "gen_ai.choice":
            outputs.append(attrs)
    return inputs, outputs


@dataclass
class ParsedSpan:
    run_id: str
    id: str
    parent_span_id: str | None
    kind: str
    name: str
    started_at_ms: int
    finished_at_ms: int | None
    status: str
    input_inline: Any
    output_inline: Any
    tokens_in: int | None
    tokens_out: int | None
    provider: str | None
    model: str | None
    attrs: dict[str, Any]
    error_payload: dict[str, Any] | None
    service_name: str | None
    gen_ai_system: str | None


def parse_otlp_traces(body: dict[str, Any]) -> list[ParsedSpan]:
    """Walk OTLP `resourceSpans` → `scopeSpans` → `spans` and yield ParsedSpans."""
    out: list[ParsedSpan] = []
    for rs in body.get("resourceSpans") or []:
        resource_attrs = decode_attributes(
            (rs.get("resource") or {}).get("attributes") or []
        )
        service_name = resource_attrs.get("service.name")
        for ss in rs.get("scopeSpans") or []:
            for span in ss.get("spans") or []:
                span_attrs = decode_attributes(span.get("attributes") or [])
                inputs, outputs = _extract_messages(span.get("events") or [])
                trace_id = span.get("traceId") or ""
                span_id = span.get("spanId") or ""
                parent_span = span.get("parentSpanId") or None

                status_block = span.get("status") or {}
                status_code = status_block.get("code")
                is_error = status_code == 2 or status_code == "STATUS_CODE_ERROR"
                status = "error" if is_error else "success"
                err_payload = (
                    {"message": status_block.get("message")} if is_error else None
                )

                out.append(
                    ParsedSpan(
                        run_id=_trace_id_to_run_id(trace_id),
                        id=_span_id_short(span_id),
                        parent_span_id=(
                            _span_id_short(parent_span) if parent_span else None
                        ),
                        kind=_resolve_kind(span_attrs),
                        name=span.get("name") or "",
                        started_at_ms=_nano_to_ms(span.get("startTimeUnixNano")),
                        finished_at_ms=_nano_to_ms(span.get("endTimeUnixNano")) or None,
                        status=status,
                        input_inline={"messages": inputs} if inputs else None,
                        output_inline={"choices": outputs} if outputs else None,
                        tokens_in=_tokens(span_attrs, "input"),
                        tokens_out=_tokens(span_attrs, "output"),
                        provider=span_attrs.get("gen_ai.system"),
                        model=(
                            span_attrs.get("gen_ai.response.model")
                            or span_attrs.get("gen_ai.request.model")
                        ),
                        attrs={**span_attrs, "_resource": resource_attrs},
                        error_payload=err_payload,
                        service_name=service_name,
                        gen_ai_system=span_attrs.get("gen_ai.system"),
                    )
                )
    return out
