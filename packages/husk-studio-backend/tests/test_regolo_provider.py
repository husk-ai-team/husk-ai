"""Regolo provider: httpx call shape via MockTransport, registration, default.

Mirrors test_debugger_providers.py — a mock transport proves the request shape
without touching the network, and the key never reaches the logs.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest

from husk_studio_backend.debugger.providers import (
    RegoloProvider,
    available_providers,
    get_provider,
)

_SECRET = "regolo-super-secret-key-123"


def test_regolo_call_shape_and_no_key_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    with caplog.at_level(logging.DEBUG):
        out = RegoloProvider().complete(
            system="s",
            user="u",
            model="Llama-3.3-70B-Instruct",
            api_key=_SECRET,
            max_output_tokens=64,
            transport=httpx.MockTransport(handler),
        )

    assert out == "ok"
    assert seen["authorization"] == f"Bearer {_SECRET}"
    assert "api.regolo.ai" in str(seen["url"])
    # OpenAI-compatible: the classic `max_tokens` field, not `max_completion_tokens`.
    body = str(seen["body"])
    assert '"max_tokens": 64' in body or '"max_tokens":64' in body
    assert _SECRET not in caplog.text


def test_regolo_is_registered() -> None:
    assert "regolo" in available_providers()
    assert get_provider("regolo").name == "regolo"


def test_regolo_is_the_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Fresh home (no stored secrets) + no env key -> the shipped default shows.
    monkeypatch.setenv("HUSK_HOME", str(tmp_path))
    monkeypatch.delenv("REGOLO_API_KEY", raising=False)
    from husk_studio_backend.debugger import secrets

    cfg = secrets.public_config()
    assert cfg["provider"] == "regolo"
    assert cfg["has_key"] is False
