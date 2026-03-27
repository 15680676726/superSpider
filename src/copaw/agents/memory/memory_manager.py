# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches
"""Memory Manager for CoPaw agents.

Extends ReMeLight to provide memory management capabilities including:
- Message compaction with configurable ratio
- Memory summarization with tool support
- Vector and full-text search integration
- Embedding configuration from environment variables
"""
from dataclasses import dataclass
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
from copaw.agents.tools import read_file, write_file, edit_file
from copaw.agents.utils import _get_token_counter
from copaw.config import load_config
from copaw.providers import ProviderManager

logger = logging.getLogger(__name__)

# Try to import reme, log warning if it fails
try:
    from reme.reme_light import ReMeLight

    _REME_AVAILABLE = True

except ImportError as e:
    _REME_AVAILABLE = False
    logger.warning(f"reme package not installed. {e}")

    class ReMeLight:  # type: ignore
        """Placeholder when reme is not available."""


class MemoryManager(ReMeLight):
    """Memory manager that extends ReMeLight for CoPaw agents.

    This class provides memory management capabilities including:
    - Memory compaction for long conversations via compact_memory()
    - Memory summarization with file operation tools via summary_memory()
    - In-memory memory retrieval via get_in_memory_memory()
    - Configurable vector search and full-text search backends
    """

    DEFAULT_EMBEDDING_BASE_URL = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    DEFAULT_EMBEDDING_MODEL_BY_BASE_URL = {
        DEFAULT_EMBEDDING_BASE_URL: "text-embedding-v4",
        "https://api.openai.com/v1": "text-embedding-3-small",
    }
    DEFAULT_EMBEDDING_MODEL_BY_PROVIDER_ID = {
        "dashscope": "text-embedding-v4",
        "openai": "text-embedding-3-small",
    }
    _VECTOR_DISABLE_REASON_MISSING_MODEL = "missing_embedding_model_name"
    _VECTOR_DISABLE_REASON_MISSING_API_KEY = "embedding_api_key_missing"
    _VECTOR_DISABLE_REASON_INHERITED_PROVIDER_NO_CREDS = (
        "inherited_provider_missing_embedding_credentials"
    )

    def __init__(self, working_dir: str):
        """Initialize MemoryManager with ReMeLight configuration.

        Args:
            working_dir: Working directory path for memory storage

        Environment Variables:
            EMBEDDING_API_KEY: API key for embedding service
            EMBEDDING_BASE_URL: Base URL for embedding API
                (default: dashscope)
            EMBEDDING_MODEL_NAME: Name of the embedding model
            EMBEDDING_FOLLOW_ACTIVE_PROVIDER: Reuse the resolved active
                model provider's API key/base URL for embeddings when
                EMBEDDING_API_KEY and EMBEDDING_BASE_URL are not set
                (default: true)
            EMBEDDING_DIMENSIONS: Embedding vector dimensions
                (default: 1024)
            EMBEDDING_CACHE_ENABLED: Enable embedding cache (default: true)
            EMBEDDING_MAX_CACHE_SIZE: Max cache size (default: 2000)
            EMBEDDING_MAX_INPUT_LENGTH: Max input length (default: 8192)
            EMBEDDING_MAX_BATCH_SIZE: Max batch size (default: 10)
            FTS_ENABLED: Enable full-text search (default: true)
            MEMORY_STORE_BACKEND: Memory backend - auto/local/chroma
                (default: auto)

        Note:
            Vector search is enabled only when an embedding API key and a
            resolved embedding model name are available. Missing explicit
            embedding credentials can fall back to the resolved active
            provider when supported.
        """
        if not _REME_AVAILABLE:
            raise RuntimeError("reme package not installed.")

        configured_embedding_api_key = self._safe_str(
            "EMBEDDING_API_KEY",
            "",
        )
        configured_embedding_base_url = self._safe_str(
            "EMBEDDING_BASE_URL",
            "",
        )
        configured_embedding_model_name = self._safe_str(
            "EMBEDDING_MODEL_NAME",
            "",
        )
        follow_active_provider = (
            self._safe_str("EMBEDDING_FOLLOW_ACTIVE_PROVIDER", "true").lower()
            == "true"
        )
        should_inherit_provider_config = (
            follow_active_provider
            and not configured_embedding_api_key.strip()
            and not configured_embedding_base_url.strip()
        )
        inherited_embedding_provider = (
            self._resolve_active_provider_embedding_config()
            if should_inherit_provider_config
            else None
        )
        inherited_provider_id = (
            inherited_embedding_provider.provider_id
            if inherited_embedding_provider is not None
            else None
        )
        inherited_provider = (
            inherited_embedding_provider.provider
            if inherited_embedding_provider is not None
            else None
        )
        embedding_api_key = (
            configured_embedding_api_key.strip()
            or (
                inherited_embedding_provider.api_key
                if inherited_embedding_provider is not None
                else ""
            )
        )
        embedding_base_url = (
            configured_embedding_base_url.strip()
            or (
                inherited_embedding_provider.base_url
                if inherited_embedding_provider is not None
                else ""
            )
            or self.DEFAULT_EMBEDDING_BASE_URL
        )
        embedding_model_name, inferred_embedding_model = (
            self._resolve_embedding_model_name(
                configured_embedding_model_name,
                embedding_base_url,
                provider_id=inherited_provider_id,
                provider=inherited_provider,
            )
        )
        embedding_dimensions = self._safe_int("EMBEDDING_DIMENSIONS", 1024)
        embedding_cache_enabled = (
            self._safe_str("EMBEDDING_CACHE_ENABLED", "true").lower() == "true"
        )
        embedding_max_cache_size = self._safe_int(
            "EMBEDDING_MAX_CACHE_SIZE",
            2000,
        )
        embedding_max_input_length = self._safe_int(
            "EMBEDDING_MAX_INPUT_LENGTH",
            8192,
        )
        embedding_max_batch_size = self._safe_int(
            "EMBEDDING_MAX_BATCH_SIZE",
            10,
        )

        # Determine if vector search should be enabled based on configuration
        # Vector search requires an embedding API key and a resolved model name.
        vector_enabled = bool(embedding_api_key) and bool(embedding_model_name)
        vector_disable_reason_code: str | None = None
        vector_disable_reason: str | None = None
        if inherited_embedding_provider is not None:
            logger.info(
                "Embedding settings inherited from active provider slot %s/%s (%s).",
                inherited_embedding_provider.provider_id,
                inherited_embedding_provider.model_slot,
                inherited_embedding_provider.provider_name,
            )
        if vector_enabled:
            if inferred_embedding_model:
                logger.info(
                    "EMBEDDING_MODEL_NAME not configured. "
                    "Defaulting to '%s' for embedding base URL %s.",
                    embedding_model_name,
                    embedding_base_url,
                )
            logger.info("Vector search enabled.")
        elif embedding_api_key:
            vector_disable_reason_code = (
                self._VECTOR_DISABLE_REASON_MISSING_MODEL
            )
            vector_disable_reason = (
                "Vector search disabled. EMBEDDING_API_KEY is configured, "
                "but EMBEDDING_MODEL_NAME is missing and no provider "
                "default could be inferred for base URL "
                f"{embedding_base_url}."
            )
            logger.warning("%s", vector_disable_reason)
        else:
            if (
                inherited_embedding_provider is not None
                and not embedding_api_key
            ):
                vector_disable_reason_code = (
                    self._VECTOR_DISABLE_REASON_INHERITED_PROVIDER_NO_CREDS
                )
                vector_disable_reason = (
                    "Vector search disabled because the active provider slot "
                    f"{inherited_embedding_provider.provider_id}/"
                    f"{inherited_embedding_provider.model_slot} does not "
                    "expose reusable embedding credentials. Memory search "
                    "will fall back to non-vector retrieval."
                )
                logger.info("%s", vector_disable_reason)
            else:
                vector_disable_reason_code = (
                    self._VECTOR_DISABLE_REASON_MISSING_API_KEY
                )
                vector_disable_reason = (
                    "Vector search disabled because EMBEDDING_API_KEY is not "
                    "configured. Memory search will fall back to non-vector "
                    "retrieval."
                )
                logger.info("%s", vector_disable_reason)

        # Check if full-text search (FTS) is enabled via environment variable
        fts_enabled = os.environ.get("FTS_ENABLED", "true").lower() == "true"

        # Determine the memory store backend to use
        # "auto" selects based on platform
        # (local for Windows, chroma otherwise)
        memory_store_backend = os.environ.get("MEMORY_STORE_BACKEND", "auto")
        if memory_store_backend == "auto":
            memory_backend = (
                "local" if platform.system() == "Windows" else "chroma"
            )
        else:
            memory_backend = memory_store_backend

        self._runtime_health_payload = {
            "embedding_api_key_configured": bool(embedding_api_key),
            "embedding_base_url": embedding_base_url,
            "embedding_model_name": embedding_model_name,
            "embedding_model_inferred": inferred_embedding_model,
            "embedding_follow_active_provider": follow_active_provider,
            "embedding_provider_inherited": (
                inherited_embedding_provider is not None
            ),
            "embedding_provider_id": inherited_provider_id,
            "embedding_provider_name": (
                inherited_embedding_provider.provider_name
                if inherited_embedding_provider is not None
                else None
            ),
            "embedding_provider_model_slot": (
                inherited_embedding_provider.model_slot
                if inherited_embedding_provider is not None
                else None
            ),
            "vector_enabled": vector_enabled,
            "vector_disable_reason_code": vector_disable_reason_code,
            "vector_disable_reason": vector_disable_reason,
            "fts_enabled": fts_enabled,
            "memory_store_backend": memory_backend,
            "working_dir": working_dir,
        }

        # Initialize parent ReMeCopaw class
        super().__init__(
            embedding_api_key=embedding_api_key,
            embedding_base_url=embedding_base_url,
            working_dir=working_dir,
            default_embedding_model_config={
                "model_name": embedding_model_name,
                "dimensions": embedding_dimensions,
                "enable_cache": embedding_cache_enabled,
                "use_dimensions": False,
                "max_cache_size": embedding_max_cache_size,
                "max_input_length": embedding_max_input_length,
                "max_batch_size": embedding_max_batch_size,
            },
            default_file_store_config={
                "backend": memory_backend,
                "store_name": "copaw",
                "vector_enabled": vector_enabled,
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
    def _safe_str(key: str, default: str) -> str:
        """
        Safely retrieve a string value from an environment variable.

        Args:
            key (str): The name of the environment variable to retrieve
            default (str): The default value to return if the variable
            is not set

        Returns:
            str: The value of the environment variable, or the default
            if not set
        """
        return os.environ.get(key, default)

    @classmethod
    def _normalize_base_url(cls, base_url: str) -> str:
        """Normalize provider base URLs before default-model matching."""
        return (base_url or "").strip().rstrip("/")

    @classmethod
    def _resolve_embedding_model_name(
        cls,
        configured_model_name: str,
        base_url: str,
        provider_id: str | None = None,
        provider: Any | None = None,
    ) -> tuple[str, bool]:
        """Resolve embedding model name with provider-aware defaults.

        Returns:
            Tuple of ``(resolved_model_name, inferred)``
        """
        model_name = (configured_model_name or "").strip()
        if model_name:
            return model_name, False

        provider_catalog_model = cls._infer_embedding_model_from_provider_catalog(
            provider,
        )
        if provider_catalog_model:
            return provider_catalog_model, True

        normalized_provider_id = (provider_id or "").strip().lower()
        if normalized_provider_id:
            default_model = cls.DEFAULT_EMBEDDING_MODEL_BY_PROVIDER_ID.get(
                normalized_provider_id,
            )
            if default_model:
                return default_model, True

        normalized_base_url = cls._normalize_base_url(base_url)
        default_model = cls.DEFAULT_EMBEDDING_MODEL_BY_BASE_URL.get(
            normalized_base_url,
        )
        if default_model:
            return default_model, True
        return "", False

    @classmethod
    def _infer_embedding_model_from_provider_catalog(
        cls,
        provider: Any | None,
    ) -> str:
        """Pick an embedding-capable model from a provider catalog if present."""
        if provider is None:
            return ""

        catalog = list(getattr(provider, "extra_models", []) or []) + list(
            getattr(provider, "models", []) or [],
        )
        matches: list[tuple[int, str]] = []
        for item in catalog:
            model_id = str(getattr(item, "id", "") or "").strip()
            model_name = str(getattr(item, "name", "") or "").strip()
            haystack = f"{model_id} {model_name}".lower()
            if "embedding" not in haystack:
                continue
            score = 0
            if "text-embedding-v4" in haystack:
                score = 100
            elif "text-embedding-3-small" in haystack:
                score = 90
            elif "text-embedding-3-large" in haystack:
                score = 80
            matches.append((score, model_id or model_name))

        if not matches:
            return ""

        matches.sort(key=lambda item: (-item[0], item[1]))
        return matches[0][1]

    @classmethod
    def _resolve_active_provider_embedding_config(
        cls,
    ) -> "_InheritedEmbeddingProviderConfig | None":
        """Reuse the resolved active provider when explicit embedding envs
        are not configured.
        """
        try:
            manager = ProviderManager.get_instance()
            resolved_slot, _, _, _ = manager.resolve_model_slot()
        except Exception:
            return None

        provider = manager.get_provider(resolved_slot.provider_id)
        if provider is None or getattr(provider, "is_local", False):
            return None

        api_key = str(getattr(provider, "api_key", "") or "").strip()
        if not api_key:
            return None

        return _InheritedEmbeddingProviderConfig(
            provider_id=str(getattr(provider, "id", resolved_slot.provider_id)),
            provider_name=str(
                getattr(provider, "name", resolved_slot.provider_id),
            ),
            model_slot=str(getattr(resolved_slot, "model", "") or "").strip(),
            api_key=api_key,
            base_url=str(getattr(provider, "base_url", "") or "").strip(),
            provider=provider,
        )

    @staticmethod
    def _safe_int(key: str, default: int) -> int:
        """
        Safely retrieve an integer value from an environment variable.

        This method handles cases where the environment variable is not set
        or contains a non-integer value by returning the specified default.

        Args:
            key (str): The name of the environment variable to retrieve
            default (int): The default value to return on failure or if not set

        Returns:
            int: The integer value of the environment variable,
                or the default

        Note:
            Logs a warning if the value exists but cannot be parsed
            as an integer
        """
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

    def prepare_model_formatter(self):
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
        """Compact a list of messages into a condensed summary.

        Args:
            messages: List of Msg objects to compact
            previous_summary: Optional previous summary to incorporate
            **_kwargs: Additional keyword arguments (ignored)

        Returns:
            str: Condensed summary of the messages
        """
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
        """Generate a comprehensive summary of the given messages.

        Uses file operation tools (read_file, write_file, edit_file) to support
        the summarization process.

        Args:
            messages: List of Msg objects to summarize
            **_kwargs: Additional keyword arguments (ignored)

        Returns:
            str: Comprehensive summary of the messages
        """
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
        """Retrieve in-memory memory content.

        Args:
            **kwargs: Additional keyword arguments (passed to parent)

        Returns:
            The in-memory memory content with token counting support
        """
        return super().get_in_memory_memory(token_counter=self.token_counter)

    def runtime_health_payload(self) -> dict[str, Any]:
        """Return a structured runtime-health snapshot for memory config."""
        return dict(self._runtime_health_payload)


@dataclass(frozen=True)
class _InheritedEmbeddingProviderConfig:
    provider_id: str
    provider_name: str
    model_slot: str
    api_key: str
    base_url: str
    provider: Any
