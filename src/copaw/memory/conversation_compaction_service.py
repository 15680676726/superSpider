# -*- coding: utf-8 -*-
"""Private conversation compaction service for runtime agents."""
from __future__ import annotations

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

        self._runtime_health_payload = {
            "private_compaction_enabled": True,
            "fts_enabled": fts_enabled,
            "memory_store_backend": memory_backend,
            "working_dir": working_dir,
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

        self.summary_toolkit = Toolkit()
        self.summary_toolkit.register_tool_function(read_file)
        self.summary_toolkit.register_tool_function(write_file)
        self.summary_toolkit.register_tool_function(edit_file)

        self.chat_model: ChatModelBase | None = None
        self.formatter: FormatterBase | None = None
        self._runtime_model_fingerprint: str = ""
        self.token_counter = _get_token_counter()

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

    async def close(self) -> None:
        closer = getattr(super(), "close", None)
        if callable(closer):
            await closer()

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
