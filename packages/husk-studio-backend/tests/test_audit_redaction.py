"""AUDIT-ADDED (2026-06) — ingest secret redaction.

Recorded prompts/completions are persisted in cleartext (and may be shipped to
the BYOK debugger LLM). The parser now scrubs common provider key/token shapes
before persist. These tests lock that in.
"""

from __future__ import annotations

from husk_studio_backend.ingest.otel_parser import _redact_text, parse_otlp_traces


def test_redacts_common_secret_shapes() -> None:
    assert _redact_text("key is sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345") == "key is ***REDACTED***"
    assert "***REDACTED***" in _redact_text("Authorization: Bearer abcdef1234567890xyz")
    assert "***REDACTED***" in _redact_text('{"api_key": "ABCDEFGH12345678"}')
    # A normal sentence is left untouched.
    assert _redact_text("What is the capital of Italy?") == "What is the capital of Italy?"


def test_parse_redacts_message_content() -> None:
    body = {
        "resourceSpans": [
            {
                "resource": {"attributes": []},
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "aaaa1111bbbb2222cccc3333dddd4444",
                                "spanId": "1212121212121212",
                                "name": "chat",
                                "startTimeUnixNano": "1",
                                "endTimeUnixNano": "2",
                                "attributes": [
                                    {
                                        "key": "gen_ai.operation.name",
                                        "value": {"stringValue": "chat"},
                                    }
                                ],
                                "events": [
                                    {
                                        "name": "gen_ai.user.message",
                                        "attributes": [
                                            {
                                                "key": "content",
                                                "value": {
                                                    "stringValue": "use sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345 please"
                                                },
                                            }
                                        ],
                                    }
                                ],
                                "status": {"code": 1},
                            }
                        ]
                    }
                ],
            }
        ]
    }
    spans = parse_otlp_traces(body)
    assert len(spans) == 1
    content = spans[0].input_inline["messages"][0]["content"]
    assert "sk-ABCDEF" not in content
    assert "***REDACTED***" in content
