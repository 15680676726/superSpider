# -*- coding: utf-8 -*-
from copaw.agents.memory.memory_manager import MemoryManager
from copaw.agents.memory import memory_manager as memory_manager_module


def _patch_memory_manager_base(monkeypatch) -> None:
    monkeypatch.setattr(memory_manager_module, "_REME_AVAILABLE", True)

    def fake_reme_init(self, **kwargs):
        self._reme_kwargs = kwargs

    monkeypatch.setattr(memory_manager_module.ReMeLight, "__init__", fake_reme_init)


def _capture_logger(monkeypatch) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []

    def capture(level: str):
        def _log(message, *args, **kwargs):
            rendered = message % args if args else message
            events.append((level, rendered))

        return _log

    monkeypatch.setattr(memory_manager_module.logger, "info", capture("info"))
    monkeypatch.setattr(memory_manager_module.logger, "warning", capture("warning"))
    return events


def test_memory_manager_runs_in_private_compaction_mode_without_vector_flags(
    monkeypatch,
) -> None:
    _patch_memory_manager_base(monkeypatch)
    events = _capture_logger(monkeypatch)
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "custom-embedding")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://example.com/v1")

    manager = MemoryManager(working_dir=".")
    runtime_health = manager.runtime_health_payload()

    assert manager._reme_kwargs["default_file_store_config"]["vector_enabled"] is False
    assert runtime_health["private_compaction_enabled"] is True
    assert "vector_enabled" not in runtime_health
    assert "embedding_model_name" not in runtime_health
    assert not any("Vector search" in message for _, message in events)


def test_memory_manager_stays_quiet_when_embedding_env_is_missing(
    monkeypatch,
) -> None:
    _patch_memory_manager_base(monkeypatch)
    events = _capture_logger(monkeypatch)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)

    manager = MemoryManager(working_dir=".")
    runtime_health = manager.runtime_health_payload()

    assert manager._reme_kwargs["default_file_store_config"]["vector_enabled"] is False
    assert runtime_health["private_compaction_enabled"] is True
    assert runtime_health["memory_store_backend"] in {"local", "chroma"}
    assert not any("EMBEDDING_" in message for _, message in events)
