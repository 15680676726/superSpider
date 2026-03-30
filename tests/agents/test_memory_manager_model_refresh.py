# -*- coding: utf-8 -*-
from __future__ import annotations

from importlib import import_module


def test_conversation_compaction_service_prepare_model_formatter_refreshes_on_fingerprint_change(
    monkeypatch,
) -> None:
    service_module = import_module("copaw.memory.conversation_compaction_service")
    monkeypatch.setattr(service_module, "_REME_AVAILABLE", True)

    def fake_reme_init(self, **kwargs):
        self._reme_kwargs = kwargs

    monkeypatch.setattr(service_module.ReMeLight, "__init__", fake_reme_init)

    service = service_module.ConversationCompactionService(working_dir=".")
    assert service.chat_model is None
    assert service.formatter is None

    model_a = object()
    fmt_a = object()
    monkeypatch.setattr(
        service_module,
        "build_runtime_model_fingerprint",
        lambda: "fp-a",
    )
    monkeypatch.setattr(
        service_module,
        "create_model_and_formatter",
        lambda: (model_a, fmt_a),
    )
    service.prepare_model_formatter()
    assert service.chat_model is model_a
    assert service.formatter is fmt_a

    monkeypatch.setattr(
        service_module,
        "create_model_and_formatter",
        lambda: (_ for _ in ()).throw(RuntimeError("should not recreate")),
    )
    service.prepare_model_formatter()
    assert service.chat_model is model_a
    assert service.formatter is fmt_a

    model_b = object()
    fmt_b = object()
    monkeypatch.setattr(
        service_module,
        "build_runtime_model_fingerprint",
        lambda: "fp-b",
    )
    monkeypatch.setattr(
        service_module,
        "create_model_and_formatter",
        lambda: (model_b, fmt_b),
    )
    service.prepare_model_formatter()
    assert service.chat_model is model_b
    assert service.formatter is fmt_b
