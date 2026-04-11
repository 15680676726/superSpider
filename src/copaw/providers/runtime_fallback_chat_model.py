# -*- coding: utf-8 -*-
"""Runtime fallback wrapper for chat models."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any, TYPE_CHECKING

from agentscope.model import ChatModelBase, OpenAIChatModel

from .model_diagnostics import (
    ModelAttemptRecord,
    build_exhausted_model_exception,
    failed_attempt,
    format_slot_label,
    unavailable_attempt,
)

if TYPE_CHECKING:  # pragma: no cover
    from .provider_manager import ModelSlotConfig, ProviderManager

logger = logging.getLogger(__name__)


class RuntimeFallbackChatModel(ChatModelBase):
    """Chat model wrapper that retries across configured fallback slots."""

    def __init__(self, manager: "ProviderManager") -> None:
        active_model = manager.get_active_model()
        model_name = active_model.model if active_model is not None else "copaw-runtime"
        super().__init__(model_name=model_name, stream=True)
        self._manager = manager
        self.preferred_chat_model_class = manager.get_preferred_chat_model_class()

    async def __call__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        candidates = list(self._manager._iter_model_slot_candidates())
        if not candidates:
            raise build_exhausted_model_exception(attempts=[])

        if not self.stream:
            return await self._call_non_stream(candidates, *args, **kwargs)
        return await self._call_stream(candidates, *args, **kwargs)

    async def _call_non_stream(
        self,
        candidates: list[tuple[str, "ModelSlotConfig"]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        attempts: list[ModelAttemptRecord] = []
        last_exception = None
        for index, (source, slot) in enumerate(candidates):
            available, reason = self._manager._slot_is_available(slot)
            if not available:
                attempts.append(unavailable_attempt(slot=slot, source=source, reason=reason))
                continue
            try:
                model = self._manager.build_chat_model_for_slot(slot, stream=False)
            except Exception as exc:
                last_exception = exc
                record, classification = failed_attempt(
                    slot=slot,
                    source=source,
                    exc=exc,
                    stage="model_init",
                )
                attempts.append(record)
                if classification.fallback_eligible and index < len(candidates) - 1:
                    continue
                raise build_exhausted_model_exception(
                    attempts=attempts,
                    last_classification=classification,
                ) from exc
            try:
                self._apply_stream_mode(model, stream=False)
                result = await model(*args, **kwargs)
                self._log_fallback_success(index=index, slot=slot, attempts=attempts)
                return result
            except Exception as exc:  # pragma: no cover - exercised in stream path
                last_exception = exc
                record, classification = failed_attempt(
                    slot=slot,
                    source=source,
                    exc=exc,
                    stage="request",
                )
                attempts.append(record)
                if classification.fallback_eligible and index < len(candidates) - 1:
                    continue
                raise build_exhausted_model_exception(
                    attempts=attempts,
                    last_classification=classification,
                ) from exc
        if last_exception is not None:
            raise build_exhausted_model_exception(attempts=attempts) from last_exception
        raise build_exhausted_model_exception(attempts=attempts)

    async def _call_stream(
        self,
        candidates: list[tuple[str, "ModelSlotConfig"]],
        *args: Any,
        attempts: list[ModelAttemptRecord] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        if attempts is None:
            attempts = []
        for index, (source, slot) in enumerate(candidates):
            available, reason = self._manager._slot_is_available(slot)
            if not available:
                attempts.append(unavailable_attempt(slot=slot, source=source, reason=reason))
                continue
            try:
                model = self._manager.build_chat_model_for_slot(slot, stream=True)
            except Exception as exc:
                record, classification = failed_attempt(
                    slot=slot,
                    source=source,
                    exc=exc,
                    stage="model_init",
                )
                attempts.append(record)
                if classification.fallback_eligible and index < len(candidates) - 1:
                    continue
                raise build_exhausted_model_exception(
                    attempts=attempts,
                    last_classification=classification,
                ) from exc
            try:
                self._apply_stream_mode(model, stream=True)
                result = await model(*args, **kwargs)
            except Exception as exc:
                record, classification = failed_attempt(
                    slot=slot,
                    source=source,
                    exc=exc,
                    stage="request",
                )
                attempts.append(record)
                if classification.fallback_eligible and index < len(candidates) - 1:
                    continue
                raise build_exhausted_model_exception(
                    attempts=attempts,
                    last_classification=classification,
                ) from exc

            if not hasattr(result, "__aiter__"):
                self._log_fallback_success(index=index, slot=slot, attempts=attempts)

                async def _single_response() -> AsyncGenerator[Any, None]:
                    yield result

                return _single_response()

            async def _stream_current(
                current_result: Any,
                current_index: int,
                current_slot: "ModelSlotConfig",
                current_source: str,
            ) -> AsyncGenerator[Any, None]:
                yielded = False
                try:
                    async for item in current_result:
                        yielded = True
                        if not attempts:
                            self._log_fallback_success(
                                index=current_index,
                                slot=current_slot,
                                attempts=attempts,
                            )
                        yield item
                    self._log_fallback_success(
                        index=current_index,
                        slot=current_slot,
                        attempts=attempts,
                    )
                    return
                except Exception as exc:
                    stage = "stream" if yielded else "first_token"
                    record, classification = failed_attempt(
                        slot=current_slot,
                        source=current_source,
                        exc=exc,
                        stage=stage,
                    )
                    attempts.append(record)
                    if yielded or not classification.fallback_eligible:
                        raise build_exhausted_model_exception(
                            attempts=attempts,
                            last_classification=classification,
                        ) from exc
                    next_stream = await self._call_stream(
                        candidates[current_index + 1 :],
                        *args,
                        attempts=attempts,
                        **kwargs,
                    )
                    async for resumed in next_stream:
                        yield resumed
                    return

            return _stream_current(result, index, slot, source)

        raise build_exhausted_model_exception(attempts=attempts)

    @staticmethod
    def _apply_stream_mode(model: Any, *, stream: bool) -> None:
        current = getattr(model, "stream", None)
        if isinstance(current, bool):
            try:
                setattr(model, "stream", stream)
            except Exception:
                logger.debug("Failed to set child chat model stream=%s", stream)

    def _log_fallback_success(
        self,
        *,
        index: int,
        slot: "ModelSlotConfig",
        attempts: list[ModelAttemptRecord],
    ) -> None:
        self.model_name = slot.model
        if index <= 0 and not attempts:
            return
        attempt_preview = " -> ".join(
            attempt.slot_label()
            for attempt in attempts
            if attempt.stage != "availability"
        )
        logger.warning(
            "Provider runtime fallback applied: resolved to %s after %s",
            format_slot_label(slot),
            attempt_preview or "previous slot failures",
        )


def default_chat_model_class() -> type[ChatModelBase]:
    return OpenAIChatModel


__all__ = ["RuntimeFallbackChatModel", "default_chat_model_class"]
