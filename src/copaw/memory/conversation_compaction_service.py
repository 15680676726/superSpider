# -*- coding: utf-8 -*-
"""Private conversation compaction service for runtime agents."""
from __future__ import annotations

import asyncio
import logging
import os
import platform
from typing import Any

from agentscope.formatter import FormatterBase
from agentscope.message import Msg
from agentscope.model import ChatModelBase
from agentscope.tool import Toolkit

from copaw.agents.model_factory import (
    build_runtime_model_fingerprint,
    create_model_and_formatter,
)
from copaw.agents.tools import edit_file, read_file, write_file
from copaw.agents.utils import _get_token_counter
from copaw.config import load_config
from copaw.constant import MEMORY_COMPACT_KEEP_RECENT

logger = logging.getLogger(__name__)

try:
    from reme.reme_light import ReMeLight

    _REME_AVAILABLE = True
except ImportError as e:
    _REME_AVAILABLE = False
    logger.warning("reme package not installed. %s", e)

    class ReMeLight:  # type: ignore
        """Placeholder when reme is not available."""


def _consume_current_task_cancellation() -> int:
    current = asyncio.current_task()
    if current is None:
        return 0
    uncancel = getattr(current, "uncancel", None)
    if not callable(uncancel):
        return 0
    cleared = 0
    while current.cancelling():
        uncancel()
        cleared += 1
    return cleared


class ConversationCompactionService(ReMeLight):
    """Private compaction/search state for one runtime actor/session."""

    def __init__(self, working_dir: str):
        if not _REME_AVAILABLE:
            raise RuntimeError("reme package not installed.")

        fts_enabled = os.environ.get("FTS_ENABLED", "true").lower() == "true"
        memory_store_backend = os.environ.get("MEMORY_STORE_BACKEND", "auto")
        if memory_store_backend == "auto":
            memory_backend = "local" if platform.system() == "Windows" else "chroma"
        else:
            memory_backend = memory_store_backend
        file_watchers_enabled = (
            os.environ.get("COPAW_COMPACTION_FILE_WATCHERS_ENABLED", "false").lower()
            == "true"
        )

        self._runtime_health_payload = {
            "private_compaction_enabled": True,
            "fts_enabled": fts_enabled,
            "memory_store_backend": memory_backend,
            "working_dir": working_dir,
            "file_watchers_enabled": file_watchers_enabled,
        }

        super().__init__(
            embedding_api_key="",
            embedding_base_url="",
            working_dir=working_dir,
            default_embedding_model_config={
                "model_name": "",
                "dimensions": self._safe_int("EMBEDDING_DIMENSIONS", 1024),
                "enable_cache": (
                    os.environ.get("EMBEDDING_CACHE_ENABLED", "true").lower()
                    == "true"
                ),
                "use_dimensions": False,
                "max_cache_size": self._safe_int("EMBEDDING_MAX_CACHE_SIZE", 2000),
                "max_input_length": self._safe_int("EMBEDDING_MAX_INPUT_LENGTH", 8192),
                "max_batch_size": self._safe_int("EMBEDDING_MAX_BATCH_SIZE", 10),
            },
            default_file_store_config={
                "backend": memory_backend,
                "store_name": "copaw",
                "vector_enabled": False,
                "fts_enabled": fts_enabled,
            },
        )
        if not file_watchers_enabled:
            try:
                self.service_config.file_watchers = {}
            except Exception:
                logger.debug(
                    "Failed to disable conversation compaction file watchers",
                    exc_info=True,
                )

        self.summary_toolkit = Toolkit()
        self.summary_toolkit.register_tool_function(read_file)
        self.summary_toolkit.register_tool_function(write_file)
        self.summary_toolkit.register_tool_function(edit_file)

        self.chat_model: ChatModelBase | None = None
        self.formatter: FormatterBase | None = None
        self._runtime_model_fingerprint: str = ""
        self._token_counter: Any | None = None
        self._close_timeout_seconds = self._safe_float(
            "COPAW_COMPACTION_CLOSE_TIMEOUT_SECONDS",
            1.0,
        )

    @property
    def token_counter(self) -> Any:
        token_counter = getattr(self, "_token_counter", None)
        if token_counter is None:
            self._token_counter = _get_token_counter()
            token_counter = self._token_counter
        return token_counter

    @staticmethod
    def _safe_int(key: str, default: int) -> int:
        value = os.environ.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning(
                "Invalid int value '%s' for key '%s', using default %s",
                value,
                key,
                default,
            )
            return default

    @staticmethod
    def _safe_float(key: str, default: float) -> float:
        value = os.environ.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            logger.warning(
                "Invalid float value '%s' for key '%s', using default %s",
                value,
                key,
                default,
            )
            return default

    @staticmethod
    def _normalize_visibility_dict(
        value: Any,
        *,
        allowed_keys: tuple[str, ...],
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        normalized = {
            key: item
            for key, item in value.items()
            if key in allowed_keys and item is not None
        }
        return normalized or None

    @staticmethod
    def _normalize_visibility_list(
        value: Any,
        *,
        max_items: int = 6,
    ) -> list[str] | None:
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, (list, tuple, set)):
            items = list(value)
        else:
            return None
        normalized: list[str] = []
        for item in items:
            text = str(item).strip()
            if not text or text in normalized:
                continue
            normalized.append(text)
            if len(normalized) >= max_items:
                break
        return normalized or None

    @classmethod
    def build_visibility_payload(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        payload: dict[str, Any] = {}
        compaction_state = cls._normalize_visibility_dict(
            value.get("compaction_state"),
            allowed_keys=("mode", "summary", "spill_count", "replacement_count"),
        )
        if compaction_state is not None:
            payload["compaction_state"] = compaction_state
        tool_result_budget = cls._normalize_visibility_dict(
            value.get("tool_result_budget"),
            allowed_keys=("message_budget", "used_budget", "remaining_budget"),
        )
        if tool_result_budget is not None:
            payload["tool_result_budget"] = tool_result_budget
        tool_use_summary = cls._normalize_visibility_dict(
            value.get("tool_use_summary"),
            allowed_keys=("summary", "artifact_refs"),
        )
        if tool_use_summary is not None:
            artifact_refs = cls._normalize_visibility_list(tool_use_summary.get("artifact_refs"))
            if artifact_refs is not None:
                tool_use_summary["artifact_refs"] = artifact_refs
            else:
                tool_use_summary.pop("artifact_refs", None)
            payload["tool_use_summary"] = tool_use_summary
        donor_trial_carry_forward = cls._normalize_visibility_dict(
            value.get("donor_trial_carry_forward"),
            allowed_keys=(
                "status",
                "summary",
                "retained_metadata_keys",
                "truncated_metadata_keys",
                "artifact_refs",
            ),
        )
        if donor_trial_carry_forward is not None:
            for key in (
                "retained_metadata_keys",
                "truncated_metadata_keys",
                "artifact_refs",
            ):
                normalized_items = cls._normalize_visibility_list(
                    donor_trial_carry_forward.get(key),
                )
                if normalized_items is not None:
                    donor_trial_carry_forward[key] = normalized_items
                else:
                    donor_trial_carry_forward.pop(key, None)
            payload["donor_trial_carry_forward"] = donor_trial_carry_forward
        return payload

    async def start(self) -> None:
        starter = getattr(super(), "start", None)
        if callable(starter):
            await starter()

    async def close(self) -> bool:
        self._cleanup_tool_results()
        if not getattr(self, "_started", False):
            logger.warning("Application is not started")
            return True

        await self._close_service_bucket(
            "vector store",
            getattr(self.service_context, "vector_stores", {}),
        )
        await self._close_service_bucket(
            "file store",
            getattr(self.service_context, "file_stores", {}),
        )
        await self._close_service_bucket(
            "file watcher",
            getattr(self.service_context, "file_watchers", {}),
            force_stop_on_timeout=True,
        )
        await self._close_service_bucket(
            "LLM",
            getattr(self.service_context, "llms", {}),
        )
        await self._close_service_bucket(
            "embedding model",
            getattr(self.service_context, "embedding_models", {}),
        )

        self.shutdown_thread_pool()
        self.shutdown_ray()
        self._started = False
        return False

    async def _close_service_bucket(
        self,
        bucket_label: str,
        components: dict[str, Any],
        *,
        force_stop_on_timeout: bool = False,
    ) -> None:
        for name, component in (components or {}).items():
            logger.info("Closing %s: %s", bucket_label, name)
            await self._close_service_component(
                bucket_label,
                name,
                component,
                force_stop_on_timeout=force_stop_on_timeout,
            )

    async def _close_service_component(
        self,
        bucket_label: str,
        name: str,
        component: Any,
        *,
        force_stop_on_timeout: bool = False,
    ) -> None:
        closer = getattr(component, "close", None)
        if not callable(closer):
            return
        if force_stop_on_timeout:
            await self._close_file_watcher_component(name, component, closer)
            return
        try:
            async with asyncio.timeout(self._close_timeout_seconds):
                await closer()
        except asyncio.TimeoutError:
            logger.warning(
                "Conversation compaction %s '%s' close timed out after %ss",
                bucket_label,
                name,
                self._close_timeout_seconds,
            )
            if force_stop_on_timeout:
                await self._force_stop_file_watcher(name, component)
        except Exception as exc:
            logger.warning(
                "Conversation compaction %s '%s' close failed: %s",
                bucket_label,
                name,
                exc,
            )

    async def _close_file_watcher_component(
        self,
        name: str,
        component: Any,
        closer: Any,
    ) -> None:
        close_task = asyncio.create_task(
            closer(),
            name=f"copaw-compaction-close-{name}",
        )
        force_stop = False
        try:
            await asyncio.wait_for(close_task, timeout=self._close_timeout_seconds)
        except asyncio.TimeoutError:
            _consume_current_task_cancellation()
            logger.warning(
                "Conversation compaction file watcher '%s' close timed out after %ss",
                name,
                self._close_timeout_seconds,
            )
            force_stop = True
        except asyncio.CancelledError:
            _consume_current_task_cancellation()
            logger.warning(
                "Conversation compaction file watcher '%s' close was cancelled; forcing stop",
                name,
            )
            force_stop = True
        except Exception as exc:
            _consume_current_task_cancellation()
            logger.warning(
                "Conversation compaction file watcher '%s' close failed: %s",
                name,
                exc,
            )
            force_stop = True

        if close_task.done():
            if close_task.cancelled():
                force_stop = True
            else:
                outcome = close_task.exception()
                if outcome is not None:
                    force_stop = True
        else:
            close_task.cancel()
            await asyncio.gather(close_task, return_exceptions=True)
            force_stop = True

        if force_stop:
            await self._force_stop_file_watcher(name, component)

    async def _force_stop_file_watcher(
        self,
        name: str,
        file_watcher: Any,
    ) -> None:
        stop_event = getattr(file_watcher, "_stop_event", None)
        if callable(getattr(stop_event, "set", None)):
            stop_event.set()

        watch_task = getattr(file_watcher, "_watch_task", None)
        if isinstance(watch_task, asyncio.Task) and not watch_task.done():
            watch_task.cancel()
            _consume_current_task_cancellation()
            done, pending = await asyncio.wait(
                {watch_task},
                timeout=self._close_timeout_seconds,
            )
            _consume_current_task_cancellation()
            if pending:
                logger.warning(
                    "Conversation compaction file watcher '%s' task did not stop after forced cancel",
                    name,
                )
            elif done:
                await asyncio.gather(*done, return_exceptions=True)
                _consume_current_task_cancellation()

        if hasattr(file_watcher, "_running"):
            file_watcher._running = False

    async def check_context(
        self,
        *,
        messages: list[Any],
        memory_compact_threshold: int,
        memory_compact_reserve: int,
        token_counter: Any = None,
    ) -> tuple[list[Any], list[Any], bool]:
        checker = getattr(super(), "check_context", None)
        if callable(checker) and hasattr(self, "service_context"):
            try:
                return await checker(
                    messages=messages,
                    memory_compact_threshold=memory_compact_threshold,
                    memory_compact_reserve=memory_compact_reserve,
                    token_counter=token_counter,
                )
            except Exception:
                logger.debug(
                    "Conversation compaction check_context fallback triggered",
                    exc_info=True,
                )
        preserve_system = 1 if self._has_system_message(messages) else 0
        compact_end = max(
            len(messages) - MEMORY_COMPACT_KEEP_RECENT,
            preserve_system,
        )
        return messages[preserve_system:compact_end], [], True

    @staticmethod
    def _has_system_message(messages: list[Any]) -> bool:
        if not messages:
            return False
        return getattr(messages[0], "role", None) == "system"

    def prepare_model_formatter(self) -> None:
        try:
            fingerprint = build_runtime_model_fingerprint()
        except Exception:
            fingerprint = ""

        if fingerprint and fingerprint != self._runtime_model_fingerprint:
            self.chat_model = None
            self.formatter = None
            self._runtime_model_fingerprint = fingerprint

        if self.chat_model is None or self.formatter is None:
            chat_model, formatter = create_model_and_formatter()
            self.chat_model = chat_model
            self.formatter = formatter
            if fingerprint:
                self._runtime_model_fingerprint = fingerprint

    async def compact_memory(
        self,
        messages: list[Msg],
        previous_summary: str = "",
        **_kwargs,
    ) -> str:
        self.prepare_model_formatter()

        config = load_config()
        max_input_length = config.agents.running.max_input_length
        memory_compact_ratio = config.agents.running.memory_compact_ratio
        language = config.agents.language

        return await super().compact_memory(
            messages=messages,
            as_llm=self.chat_model,
            as_llm_formatter=self.formatter,
            token_counter=self.token_counter,
            language=language,
            max_input_length=max_input_length,
            compact_ratio=memory_compact_ratio,
            previous_summary=previous_summary,
        )

    async def summary_memory(self, messages: list[Msg], **_kwargs) -> str:
        self.prepare_model_formatter()
        config = load_config()
        max_input_length = config.agents.running.max_input_length
        memory_compact_ratio = config.agents.running.memory_compact_ratio
        language = config.agents.language

        return await super().summary_memory(
            messages=messages,
            as_llm=self.chat_model,
            as_llm_formatter=self.formatter,
            token_counter=self.token_counter,
            toolkit=self.summary_toolkit,
            language=language,
            max_input_length=max_input_length,
            compact_ratio=memory_compact_ratio,
        )

    def get_in_memory_memory(self, **_kwargs):
        return super().get_in_memory_memory(token_counter=self.token_counter)

    def runtime_health_payload(self) -> dict[str, Any]:
        return dict(self._runtime_health_payload)


__all__ = [
    "ConversationCompactionService",
    "ReMeLight",
    "_REME_AVAILABLE",
]
