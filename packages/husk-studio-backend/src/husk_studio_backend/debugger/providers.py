"""Provider abstraction for the debugger's LLM calls.

Pure ``httpx`` (already a dependency) so we control exactly what is sent and
never log headers or bodies — no SDK that might log the key. Adding a provider is
a small class + one registry entry. Each provider exposes the chosen model's
context window via :mod:`husk_shared.model_metadata`, which the context assembler
uses to size the budget.

Tests inject ``transport=httpx.MockTransport(...)`` to exercise the call path
without network, mirroring ``packages/husk-sandbox/tests/test_cassette_sdk.py``.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

import httpx

from husk_shared import model_metadata

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(120.0)


class ProviderError(RuntimeError):
    """A provider call failed (network, auth, or a non-2xx response)."""


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        api_key: str,
        max_output_tokens: int,
        transport: httpx.BaseTransport | None = None,
    ) -> str: ...

    def list_models(self) -> list[dict[str, Any]]: ...


def _models_payload(model_ids: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "id": m,
            "context_window": model_metadata.context_window(m),
            "max_output": model_metadata.max_output(m),
        }
        for m in model_ids
    ]


class AnthropicProvider:
    name = "anthropic"
    _URL = "https://api.anthropic.com/v1/messages"
    _KNOWN = [
        "claude-opus-4",
        "claude-sonnet-4",
        "claude-haiku-4-5",
        "claude-3-5-sonnet",
        "claude-3-5-haiku",
    ]

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        api_key: str,
        max_output_tokens: int,
        transport: httpx.BaseTransport | None = None,
    ) -> str:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        data = _post(self._URL, headers, body, transport)
        try:
            blocks = data["content"]
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        except (KeyError, TypeError) as e:
            raise ProviderError(f"unexpected Anthropic response shape: {e}") from e

    def list_models(self) -> list[dict[str, Any]]:
        return _models_payload(self._KNOWN)


class OpenAIProvider:
    name = "openai"
    _URL = "https://api.openai.com/v1/chat/completions"
    _KNOWN = ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "o3", "o3-mini"]

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        api_key: str,
        max_output_tokens: int,
        transport: httpx.BaseTransport | None = None,
    ) -> str:
        headers = {
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_completion_tokens": max_output_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = _post(self._URL, headers, body, transport)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"unexpected OpenAI response shape: {e}") from e

    def list_models(self) -> list[dict[str, Any]]:
        return _models_payload(self._KNOWN)


def _post(
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    transport: httpx.BaseTransport | None,
) -> dict[str, Any]:
    """POST JSON and return the parsed body. Never logs headers or body."""
    try:
        with httpx.Client(transport=transport, timeout=_TIMEOUT) as client:
            resp = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as e:
        # Log only the exception type — never the URL with creds or the body.
        raise ProviderError(f"request failed: {type(e).__name__}") from e
    if resp.status_code >= 400:
        # Provider error bodies do not contain the API key; include a short,
        # truncated snippet to aid debugging (status + provider message).
        raise ProviderError(f"provider returned {resp.status_code}: {resp.text[:300]}")
    return resp.json()


_PROVIDERS: dict[str, LLMProvider] = {
    AnthropicProvider.name: AnthropicProvider(),
    OpenAIProvider.name: OpenAIProvider(),
}


def get_provider(name: str) -> LLMProvider:
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ProviderError(
            f"unknown provider {name!r}; available: {sorted(_PROVIDERS)}"
        ) from None


def available_providers() -> list[str]:
    return sorted(_PROVIDERS)
