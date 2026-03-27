from __future__ import annotations

import asyncio

from copaw.providers.provider_manager import ModelSlotConfig
from copaw.providers.runtime_fallback_chat_model import RuntimeFallbackChatModel


class _DummyChatModel:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, dict(kwargs)))
        return {"ok": True}


class _DummyManager:
    def __init__(self) -> None:
        self.slot = ModelSlotConfig(provider_id="dummy", model="dummy-model")
        self.model = _DummyChatModel()

    def get_active_model(self) -> ModelSlotConfig:
        return self.slot

    def get_preferred_chat_model_class(self):
        return object

    def _iter_model_slot_candidates(self):
        return [("active", self.slot)]

    def _slot_is_available(self, slot):
        _ = slot
        return True, "ready"

    def build_chat_model_for_slot(self, slot):
        _ = slot
        return self.model


def test_runtime_fallback_chat_model_keeps_positional_messages_in_stream_path() -> None:
    manager = _DummyManager()
    wrapper = RuntimeFallbackChatModel(manager)

    async def _run() -> list[object]:
        result = await wrapper(
            [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
            tool_choice="auto",
        )
        payloads: list[object] = []
        async for item in result:
            payloads.append(item)
        return payloads

    payloads = asyncio.run(_run())

    assert payloads == [{"ok": True}]
    assert manager.model.calls == [
        (
            (
                [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
            ),
            {"tool_choice": "auto"},
        ),
    ]
