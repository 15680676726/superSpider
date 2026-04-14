# -*- coding: utf-8 -*-
from copaw.agents import memory as agents_memory_module
from copaw.memory import conversation_compaction_service as service_module
from copaw.memory.conversation_compaction_service import ConversationCompactionService


def _patch_compaction_base(monkeypatch) -> None:
    monkeypatch.setattr(service_module, "_REME_AVAILABLE", True)

    def fake_reme_init(self, **kwargs):
        self._reme_kwargs = kwargs

    monkeypatch.setattr(service_module.ReMeLight, "__init__", fake_reme_init)


def _capture_logger(monkeypatch) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []

    def capture(level: str):
        def _log(message, *args, **kwargs):
            rendered = message % args if args else message
            events.append((level, rendered))

        return _log

    monkeypatch.setattr(service_module.logger, "info", capture("info"))
    monkeypatch.setattr(service_module.logger, "warning", capture("warning"))
    return events


def test_agents_memory_module_does_not_export_legacy_memory_alias() -> None:
    assert not hasattr(agents_memory_module, "MemoryManager")


def test_conversation_compaction_service_runs_in_private_compaction_mode_without_vector_flags(
    monkeypatch,
) -> None:
    _patch_compaction_base(monkeypatch)
    events = _capture_logger(monkeypatch)
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "custom-embedding")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://example.com/v1")

    service = ConversationCompactionService(working_dir=".")
    runtime_health = service.runtime_health_payload()

    assert service._reme_kwargs["default_file_store_config"]["vector_enabled"] is False
    assert runtime_health["private_compaction_enabled"] is True
    assert "vector_enabled" not in runtime_health
    assert "embedding_model_name" not in runtime_health
    assert not any("Vector search" in message for _, message in events)


def test_conversation_compaction_service_stays_quiet_when_embedding_env_is_missing(
    monkeypatch,
) -> None:
    _patch_compaction_base(monkeypatch)
    events = _capture_logger(monkeypatch)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)

    service = ConversationCompactionService(working_dir=".")
    runtime_health = service.runtime_health_payload()

    assert service._reme_kwargs["default_file_store_config"]["vector_enabled"] is False
    assert runtime_health["private_compaction_enabled"] is True
    assert runtime_health["memory_store_backend"] in {"local", "chroma"}
    assert not any("EMBEDDING_" in message for _, message in events)
