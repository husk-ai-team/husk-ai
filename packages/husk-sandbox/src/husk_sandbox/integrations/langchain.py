"""LangChain integration: a callback handler that captures spans into Husk's tracer.

Lazy-imported. `install()` registers `HuskCallbackHandler` on the LangChain global
callback manager so user agent code can be imported as-is.

Hooks captured in M1:
  * on_llm_start / on_llm_end / on_llm_error
  * on_chat_model_start (Chat models)
  * on_tool_start / on_tool_end / on_tool_error
  * on_chain_start / on_chain_end / on_chain_error
  * on_agent_action / on_agent_finish
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from husk_sandbox.serializer import to_jsonable
from husk_sandbox.tracer import get_emitter
from husk_shared import SpanKind, SpanStatus

log = logging.getLogger(__name__)


def install() -> None:
    """Register HuskCallbackHandler as a LangChain global handler."""
    # Lazy import: avoid forcing langchain at module load time.
    from langchain_core.tracers.context import register_configure_hook

    handler = HuskCallbackHandler()
    # `register_configure_hook` ensures the handler is appended to every Runnable's
    # callbacks unless explicitly disabled. This is the supported way for LC>=0.3.
    register_configure_hook(handler, inheritable=True)
    log.info("Husk LangChain callback handler installed.")


def _provider_from_serialized(serialized: dict[str, Any] | None) -> str | None:
    if not serialized:
        return None
    # serialized["id"] is a list path like ["langchain", "chat_models", "openai", "ChatOpenAI"]
    path = serialized.get("id") or []
    if isinstance(path, list) and path:
        for part in path:
            p = str(part).lower()
            if p in ("openai", "anthropic", "google", "mistral", "cohere"):
                return p
    return None


def _model_from_kwargs(kwargs: dict[str, Any] | None) -> str | None:
    if not kwargs:
        return None
    return kwargs.get("model") or kwargs.get("model_name") or kwargs.get("invocation_params", {}).get("model")


class HuskCallbackHandler:
    """LangChain callback handler that translates lifecycle events to Husk spans.

    Implemented as a duck-typed class rather than inheriting from BaseCallbackHandler
    to avoid a hard import of langchain at this module's top level. LangChain only
    inspects the `on_*` methods by name.
    """

    # LangChain inspects this attribute to decide whether to skip the handler when
    # a particular flag (verbose etc.) is on. We always want to run.
    raise_error: bool = False
    run_inline: bool = True

    def __init__(self) -> None:
        self._span_by_run: dict[UUID, str] = {}

    # ------------- LLM -------------

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        invocation_params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        em = get_emitter()
        if em is None:
            return
        parent = self._span_by_run.get(parent_run_id) if parent_run_id else None
        name = (serialized or {}).get("name") or "llm"
        provider = _provider_from_serialized(serialized)
        model = _model_from_kwargs(invocation_params)
        span_id = em.start_span(
            kind=SpanKind.LLM,
            name=name,
            parent_span_id=parent,
            input_inline=to_jsonable({"prompts": prompts}),
            attrs={
                "provider": provider,
                "model": model,
                "lc_run_id": str(run_id),
                "invocation_params": to_jsonable(invocation_params or {}),
            },
        )
        self._span_by_run[run_id] = span_id

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        invocation_params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        em = get_emitter()
        if em is None:
            return
        parent = self._span_by_run.get(parent_run_id) if parent_run_id else None
        name = (serialized or {}).get("name") or "chat_model"
        provider = _provider_from_serialized(serialized)
        model = _model_from_kwargs(invocation_params)
        span_id = em.start_span(
            kind=SpanKind.LLM,
            name=name,
            parent_span_id=parent,
            input_inline=to_jsonable({"messages": messages}),
            attrs={
                "provider": provider,
                "model": model,
                "lc_run_id": str(run_id),
            },
        )
        self._span_by_run[run_id] = span_id

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        em = get_emitter()
        if em is None:
            return
        span_id = self._span_by_run.pop(run_id, None)
        if not span_id:
            return
        usage: dict[str, Any] = {}
        try:
            llm_output = getattr(response, "llm_output", None) or {}
            usage = (llm_output or {}).get("token_usage") or (llm_output or {}).get("usage") or {}
        except Exception:  # noqa: BLE001
            usage = {}
        em.end_span(
            span_id,
            status=SpanStatus.SUCCESS,
            output_inline=to_jsonable(response),
            tokens_in=usage.get("prompt_tokens") or usage.get("input_tokens"),
            tokens_out=usage.get("completion_tokens") or usage.get("output_tokens"),
        )

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        em = get_emitter()
        if em is None:
            return
        span_id = self._span_by_run.pop(run_id, None)
        if not span_id:
            return
        em.end_span(
            span_id,
            status=SpanStatus.ERROR,
            error_payload={"type": type(error).__name__, "message": str(error)},
        )

    # ------------- Tool -------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        em = get_emitter()
        if em is None:
            return
        parent = self._span_by_run.get(parent_run_id) if parent_run_id else None
        name = (serialized or {}).get("name") or "tool"
        span_id = em.start_span(
            kind=SpanKind.TOOL,
            name=name,
            parent_span_id=parent,
            input_inline={"input": input_str},
            attrs={"lc_run_id": str(run_id)},
        )
        self._span_by_run[run_id] = span_id

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        em = get_emitter()
        if em is None:
            return
        span_id = self._span_by_run.pop(run_id, None)
        if not span_id:
            return
        em.end_span(span_id, status=SpanStatus.SUCCESS, output_inline=to_jsonable(output))

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        em = get_emitter()
        if em is None:
            return
        span_id = self._span_by_run.pop(run_id, None)
        if not span_id:
            return
        em.end_span(
            span_id,
            status=SpanStatus.ERROR,
            error_payload={"type": type(error).__name__, "message": str(error)},
        )

    # ------------- Chain -------------

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        em = get_emitter()
        if em is None:
            return
        parent = self._span_by_run.get(parent_run_id) if parent_run_id else None
        name = (serialized or {}).get("name") or "chain"
        span_id = em.start_span(
            kind=SpanKind.CHAIN,
            name=name,
            parent_span_id=parent,
            input_inline=to_jsonable(inputs),
            attrs={"lc_run_id": str(run_id)},
        )
        self._span_by_run[run_id] = span_id

    def on_chain_end(self, outputs: dict[str, Any], *, run_id: UUID, **kwargs: Any) -> None:
        em = get_emitter()
        if em is None:
            return
        span_id = self._span_by_run.pop(run_id, None)
        if not span_id:
            return
        em.end_span(span_id, status=SpanStatus.SUCCESS, output_inline=to_jsonable(outputs))

    def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        em = get_emitter()
        if em is None:
            return
        span_id = self._span_by_run.pop(run_id, None)
        if not span_id:
            return
        em.end_span(
            span_id,
            status=SpanStatus.ERROR,
            error_payload={"type": type(error).__name__, "message": str(error)},
        )

    # ------------- Agent -------------

    def on_agent_action(self, action: Any, *, run_id: UUID, **kwargs: Any) -> None:
        em = get_emitter()
        if em is None:
            return
        parent = self._span_by_run.get(run_id)
        em.start_span(
            kind=SpanKind.AGENT_DECISION,
            name=getattr(action, "tool", "agent_action"),
            parent_span_id=parent,
            input_inline=to_jsonable(action),
        )

    def on_agent_finish(self, finish: Any, *, run_id: UUID, **kwargs: Any) -> None:
        em = get_emitter()
        if em is None:
            return
        parent = self._span_by_run.get(run_id)
        span_id = em.start_span(
            kind=SpanKind.AGENT_DECISION,
            name="agent_finish",
            parent_span_id=parent,
            input_inline=to_jsonable(finish),
        )
        em.end_span(span_id, status=SpanStatus.SUCCESS)
