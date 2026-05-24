"""OTLP/HTTP ingestion endpoint for OTel GenAI traces.

Accepts:
- Content-Type: application/json     (OTLP/HTTP JSON)
- Content-Type: application/x-protobuf (OTLP/HTTP proto)

Spans are mapped to Husk Run/Span rows via `ingest.otel_parser` and streamed
to WebSocket subscribers via `ingest.broadcast.publish`.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, Response

from husk_shared.pricing import cost_usd
from husk_studio_backend.db.engine import async_session
from husk_studio_backend.db.models import RunRow, SpanRow
from husk_studio_backend.ingest.broadcast import publish
from husk_studio_backend.ingest.otel_parser import ParsedSpan, parse_otlp_traces

log = logging.getLogger(__name__)
router = APIRouter(tags=["otel"])

_OK_BODY = b'{"partialSuccess":{}}'


@router.post("/v1/traces", status_code=200)
async def ingest_traces(request: Request) -> Response:
    content_type = (request.headers.get("content-type") or "").lower()
    body = await request.body()

    if "json" in content_type:
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"invalid json: {e}") from e
    elif "protobuf" in content_type or "x-protobuf" in content_type:
        try:
            from google.protobuf import json_format
            from opentelemetry.proto.collector.trace.v1 import trace_service_pb2

            req = trace_service_pb2.ExportTraceServiceRequest()
            req.ParseFromString(body)
            payload = json_format.MessageToDict(req, preserving_proto_field_name=False)
        except Exception as e:  # noqa: BLE001
            log.exception("OTLP proto decode failed")
            raise HTTPException(
                status_code=400, detail=f"proto decode failed: {e}"
            ) from e
    else:
        raise HTTPException(
            status_code=415,
            detail=f"unsupported content-type (need json or x-protobuf): {content_type!r}",
        )

    spans = parse_otlp_traces(payload)
    if not spans:
        return Response(content=_OK_BODY, media_type="application/json")

    # Group by run_id (= derived from trace_id).
    by_run: dict[str, list[ParsedSpan]] = {}
    for s in spans:
        by_run.setdefault(s.run_id, []).append(s)

    persisted_for_broadcast: list[tuple[str, dict]] = []

    async with async_session() as session:
        for run_id, run_spans in by_run.items():
            await _upsert_run(session, run_id, run_spans)
            for s in run_spans:
                added = await _upsert_span(session, s)
                if added:
                    persisted_for_broadcast.append((s.run_id, _serialize(s)))
        await session.commit()

    # Broadcast new spans to WebSocket subscribers (after commit).
    for run_id, span_payload in persisted_for_broadcast:
        await publish(
            run_id,
            {"type": "span.created", "run_id": run_id, "span": span_payload},
        )

    return Response(content=_OK_BODY, media_type="application/json")


async def _upsert_run(session, run_id: str, spans: list[ParsedSpan]) -> None:
    row = await session.get(RunRow, run_id)
    earliest = min(spans, key=lambda s: s.started_at_ms or 0)
    framework_id = earliest.gen_ai_system or earliest.service_name or "otel"
    framework_label = (
        f"otel/{framework_id}" if not framework_id.startswith("otel") else framework_id
    )

    if row is None:
        row = RunRow(
            id=run_id,
            script_path=earliest.service_name or "",
            framework=framework_label,
            status="running",
            started_at=earliest.started_at_ms,
        )
        session.add(row)

    # Roll forward finish time + status.
    latest_finish = max((s.finished_at_ms or 0) for s in spans)
    if latest_finish and (row.finished_at is None or latest_finish > row.finished_at):
        row.finished_at = latest_finish
    if any(s.status == "error" for s in spans):
        row.status = "error"
    elif latest_finish and row.status == "running":
        row.status = "success"


async def _upsert_span(session, s: ParsedSpan) -> bool:
    """Insert a new span or update terminal fields. Returns True if newly inserted."""
    existing = await session.get(SpanRow, s.id)
    cost = cost_usd(s.model, s.tokens_in, s.tokens_out)

    if existing is None:
        session.add(
            SpanRow(
                id=s.id,
                run_id=s.run_id,
                parent_span_id=s.parent_span_id,
                kind=s.kind,
                name=s.name,
                started_at=s.started_at_ms,
                finished_at=s.finished_at_ms,
                status=s.status,
                input_inline=s.input_inline,
                output_inline=s.output_inline,
                tokens_in=s.tokens_in,
                tokens_out=s.tokens_out,
                cost_usd=cost,
                provider=s.provider,
                model=s.model,
                error_payload=s.error_payload,
                attrs={k: v for k, v in s.attrs.items() if k != "_resource"},
            )
        )
        run = await session.get(RunRow, s.run_id)
        if run is not None:
            if s.tokens_in:
                run.total_tokens_in = (run.total_tokens_in or 0) + s.tokens_in
            if s.tokens_out:
                run.total_tokens_out = (run.total_tokens_out or 0) + s.tokens_out
            if cost:
                run.total_cost_usd = (run.total_cost_usd or 0.0) + cost
        return True

    # Span already exists — update terminal fields opportunistically.
    if existing.finished_at is None and s.finished_at_ms:
        existing.finished_at = s.finished_at_ms
    if s.status:
        existing.status = s.status
    if existing.output_inline is None and s.output_inline:
        existing.output_inline = s.output_inline
    return False


def _serialize(s: ParsedSpan) -> dict:
    return {
        "id": s.id,
        "run_id": s.run_id,
        "parent_span_id": s.parent_span_id,
        "kind": s.kind,
        "name": s.name,
        "started_at": s.started_at_ms,
        "finished_at": s.finished_at_ms,
        "status": s.status,
        "input_inline": s.input_inline,
        "output_inline": s.output_inline,
        "tokens_in": s.tokens_in,
        "tokens_out": s.tokens_out,
        "cost_usd": cost_usd(s.model, s.tokens_in, s.tokens_out),
        "provider": s.provider,
        "model": s.model,
        "error_payload": s.error_payload,
        "attrs": {k: v for k, v in s.attrs.items() if k != "_resource"},
    }
