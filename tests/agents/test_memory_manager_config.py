# -*- coding: utf-8 -*-
from types import SimpleNamespace

from copaw.agents.memory.memory_manager import MemoryManager
from copaw.agents.memory import memory_manager as memory_manager_module


def _patch_memory_manager_base(monkeypatch) -> None:
    monkeypatch.setattr(memory_manager_module, "_REME_AVAILABLE", True)

    def fake_reme_init(self, **kwargs):
        self._reme_kwargs = kwargs

    monkeypatch.setattr(memory_manager_module.ReMeLight, "__init__", fake_reme_init)
    _patch_provider_manager(monkeypatch)


def _capture_logger(monkeypatch) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []

    def capture(level: str):
        def _log(message, *args, **kwargs):
            rendered = message % args if args else message
            events.append((level, rendered))

        return _log

    monkeypatch.setattr(memory_manager_module.logger, "info", capture("info"))
    monkeypatch.setattr(
        memory_manager_module.logger,
        "warning",
        capture("warning"),
    )
    return events


def _patch_provider_manager(monkeypatch, manager=None) -> None:
    if manager is None:
        manager = SimpleNamespace(
            resolve_model_slot=lambda: (_ for _ in ()).throw(
                ValueError("No active or fallback model configured."),
            ),
            get_provider=lambda _provider_id: None,
        )

    class _ProviderManagerStub:
        @staticmethod
        def get_instance():
            return manager

    monkeypatch.setattr(
        memory_manager_module,
        "ProviderManager",
        _ProviderManagerStub,
    )


def test_memory_manager_infers_default_dashscope_embedding_model(
    monkeypatch,
) -> None:
    _patch_memory_manager_base(monkeypatch)
    events = _capture_logger(monkeypatch)
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)

    manager = MemoryManager(working_dir=".")

    assert (
        manager._reme_kwargs["default_embedding_model_config"]["model_name"]
        == "text-embedding-v4"
    )
    assert manager._reme_kwargs["default_file_store_config"]["vector_enabled"] is True
    assert any("Defaulting to 'text-embedding-v4'" in message for _, message in events)
    assert any(message == "Vector search enabled." for _, message in events)


def test_memory_manager_uses_explicit_embedding_model(
    monkeypatch,
) -> None:
    _patch_memory_manager_base(monkeypatch)
    events = _capture_logger(monkeypatch)
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "custom-embedding")
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)

    manager = MemoryManager(working_dir=".")

    assert (
        manager._reme_kwargs["default_embedding_model_config"]["model_name"]
        == "custom-embedding"
    )
    assert manager._reme_kwargs["default_file_store_config"]["vector_enabled"] is True
    assert not any("Defaulting to 'text-embedding-v4'" in message for _, message in events)


def test_memory_manager_logs_info_when_embedding_api_key_missing(
    monkeypatch,
) -> None:
    _patch_memory_manager_base(monkeypatch)
    events = _capture_logger(monkeypatch)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)

    manager = MemoryManager(working_dir=".")

    assert (
        manager._reme_kwargs["default_embedding_model_config"]["model_name"]
        == "text-embedding-v4"
    )
    assert manager._reme_kwargs["default_file_store_config"]["vector_enabled"] is False
    assert any("EMBEDDING_API_KEY is not configured" in message for _, message in events)


def test_memory_manager_warns_for_unknown_provider_without_model_name(
    monkeypatch,
) -> None:
    _patch_memory_manager_base(monkeypatch)
    events = _capture_logger(monkeypatch)
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://example.com/v1")
    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)

    manager = MemoryManager(working_dir=".")

    assert manager._reme_kwargs["default_embedding_model_config"]["model_name"] == ""
    assert manager._reme_kwargs["default_file_store_config"]["vector_enabled"] is False
    assert any(
        "no provider default could be inferred" in message
        for _, message in events
    )


def test_memory_manager_reports_vector_degraded_without_embedding_model_name(
    monkeypatch,
) -> None:
    _patch_memory_manager_base(monkeypatch)
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://example.com/v1")
    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)

    manager = MemoryManager(working_dir=".")
    runtime_health = manager.runtime_health_payload()

    assert runtime_health["vector_enabled"] is False
    assert (
        runtime_health["vector_disable_reason_code"]
        == "missing_embedding_model_name"
    )
    assert "EMBEDDING_MODEL_NAME" in runtime_health["vector_disable_reason"]
    assert runtime_health["embedding_model_name"] == ""
    assert runtime_health["embedding_api_key_configured"] is True
    assert runtime_health["embedding_base_url"] == "https://example.com/v1"


def test_memory_manager_inherits_active_openai_provider_for_embeddings(
    monkeypatch,
) -> None:
    _patch_memory_manager_base(monkeypatch)
    events = _capture_logger(monkeypatch)
    provider = SimpleNamespace(
        id="openai",
        name="OpenAI",
        api_key="provider-key",
        base_url="https://api.openai.com/v1",
        is_local=False,
        models=[],
        extra_models=[],
    )
    _patch_provider_manager(
        monkeypatch,
        SimpleNamespace(
            resolve_model_slot=lambda: (
                SimpleNamespace(provider_id="openai", model="gpt-5"),
                False,
                "Using configured active model.",
                [],
            ),
            get_provider=lambda provider_id: provider
            if provider_id == "openai"
            else None,
        ),
    )
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)
    monkeypatch.delenv("EMBEDDING_FOLLOW_ACTIVE_PROVIDER", raising=False)

    manager = MemoryManager(working_dir=".")

    assert manager._reme_kwargs["embedding_api_key"] == "provider-key"
    assert manager._reme_kwargs["embedding_base_url"] == "https://api.openai.com/v1"
    assert (
        manager._reme_kwargs["default_embedding_model_config"]["model_name"]
        == "text-embedding-3-small"
    )
    assert manager._reme_kwargs["default_file_store_config"]["vector_enabled"] is True
    assert any(
        "Embedding settings inherited from active provider slot openai/gpt-5"
        in message
        for _, message in events
    )


def test_memory_manager_allows_explicit_model_with_inherited_provider_credentials(
    monkeypatch,
) -> None:
    _patch_memory_manager_base(monkeypatch)
    provider = SimpleNamespace(
        id="openai",
        name="OpenAI",
        api_key="provider-key",
        base_url="https://api.openai.com/v1",
        is_local=False,
        models=[],
        extra_models=[],
    )
    _patch_provider_manager(
        monkeypatch,
        SimpleNamespace(
            resolve_model_slot=lambda: (
                SimpleNamespace(provider_id="openai", model="gpt-5"),
                False,
                "Using configured active model.",
                [],
            ),
            get_provider=lambda provider_id: provider
            if provider_id == "openai"
            else None,
        ),
    )
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "custom-embedding")
    monkeypatch.delenv("EMBEDDING_FOLLOW_ACTIVE_PROVIDER", raising=False)

    manager = MemoryManager(working_dir=".")

    assert manager._reme_kwargs["embedding_api_key"] == "provider-key"
    assert manager._reme_kwargs["embedding_base_url"] == "https://api.openai.com/v1"
    assert (
        manager._reme_kwargs["default_embedding_model_config"]["model_name"]
        == "custom-embedding"
    )
    assert manager._reme_kwargs["default_file_store_config"]["vector_enabled"] is True


def test_memory_manager_can_disable_active_provider_embedding_inheritance(
    monkeypatch,
) -> None:
    _patch_memory_manager_base(monkeypatch)
    events = _capture_logger(monkeypatch)
    provider = SimpleNamespace(
        id="openai",
        name="OpenAI",
        api_key="provider-key",
        base_url="https://api.openai.com/v1",
        is_local=False,
        models=[],
        extra_models=[],
    )
    _patch_provider_manager(
        monkeypatch,
        SimpleNamespace(
            resolve_model_slot=lambda: (
                SimpleNamespace(provider_id="openai", model="gpt-5"),
                False,
                "Using configured active model.",
                [],
            ),
            get_provider=lambda provider_id: provider
            if provider_id == "openai"
            else None,
        ),
    )
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)
    monkeypatch.setenv("EMBEDDING_FOLLOW_ACTIVE_PROVIDER", "false")

    manager = MemoryManager(working_dir=".")

    assert manager._reme_kwargs["embedding_api_key"] == ""
    assert (
        manager._reme_kwargs["embedding_base_url"]
        == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    assert (
        manager._reme_kwargs["default_embedding_model_config"]["model_name"]
        == "text-embedding-v4"
    )
    assert manager._reme_kwargs["default_file_store_config"]["vector_enabled"] is False
    assert not any(
        "Embedding settings inherited from active provider slot" in message
        for _, message in events
    )
