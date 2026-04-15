from __future__ import annotations

import asyncio

import pytest

from copaw.industry import draft_generator as draft_generator_module
from copaw.kernel import buddy_onboarding_reasoner as buddy_reasoner_module
from copaw.kernel import query_execution_writeback as writeback_module
from copaw.memory import sleep_inference_service as sleep_inference_module


class _KeyErrorChatResponse:
    def __getattr__(self, name: str):
        raise KeyError(name)


@pytest.mark.parametrize(
    ("materialize", "label"),
    [
        (draft_generator_module._materialize_response, "industry-draft"),
        (buddy_reasoner_module._materialize_response, "buddy-reasoner"),
        (writeback_module._materialize_response, "chat-writeback"),
        (sleep_inference_module._materialize_response, "memory-sleep"),
    ],
)
def test_materialize_response_treats_keyerror_chat_response_as_non_stream(
    materialize,
    label: str,
) -> None:
    response = _KeyErrorChatResponse()

    result = asyncio.run(materialize(response))

    assert result is response, label
