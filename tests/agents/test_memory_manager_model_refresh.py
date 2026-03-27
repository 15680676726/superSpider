# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.agents.memory.memory_manager import MemoryManager
from copaw.agents.memory import memory_manager as memory_manager_module


def _patch_memory_manager_base(monkeypatch) -> None:
    monkeypatch.setattr(memory_manager_module, "_REME_AVAILABLE", True)

    def fake_reme_init(self, **kwargs):
        self._reme_kwargs = kwargs

    monkeypatch.setattr(memory_manager_module.ReMeLight, "__init__", fake_reme_init)

    class _ProviderManagerStub:
        @staticmethod
        def get_instance():
            return SimpleNamespace(
                resolve_model_slot=lambda: (_ for _ in ()).throw(
                    ValueError("No active or fallback model configured."),
                ),
                get_provider=lambda _provider_id: None,
            )

    monkeypatch.setattr(memory_manager_module, "ProviderManager", _ProviderManagerStub)


def test_memory_manager_prepare_model_formatter_refreshes_on_fingerprint_change(
    monkeypatch,
) -> None:
    _patch_memory_manager_base(monkeypatch)

    manager = MemoryManager(working_dir=".")
    assert manager.chat_model is None
    assert manager.formatter is None

    model_a = object()
    fmt_a = object()
    monkeypatch.setattr(
        memory_manager_module,
        "build_runtime_model_fingerprint",
        lambda: "fp-a",
    )
    monkeypatch.setattr(
        memory_manager_module,
        "create_model_and_formatter",
        lambda: (model_a, fmt_a),
    )
    manager.prepare_model_formatter()
    assert manager.chat_model is model_a
    assert manager.formatter is fmt_a

    # Same fingerprint: keep cached model/formatter.
    monkeypatch.setattr(
        memory_manager_module,
        "create_model_and_formatter",
        lambda: (_ for _ in ()).throw(RuntimeError("should not recreate")),
    )
    manager.prepare_model_formatter()
    assert manager.chat_model is model_a
    assert manager.formatter is fmt_a

    # Fingerprint changed: refresh model/formatter.
    model_b = object()
    fmt_b = object()
    monkeypatch.setattr(
        memory_manager_module,
        "build_runtime_model_fingerprint",
        lambda: "fp-b",
    )
    monkeypatch.setattr(
        memory_manager_module,
        "create_model_and_formatter",
        lambda: (model_b, fmt_b),
    )
    manager.prepare_model_formatter()
    assert manager.chat_model is model_b
    assert manager.formatter is fmt_b

