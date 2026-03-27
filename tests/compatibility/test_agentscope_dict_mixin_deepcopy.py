# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
import subprocess
import sys

import copaw  # noqa: F401  # Ensure package init installs compatibility patches.
from agentscope.message import TextBlock
from agentscope.model._model_response import ChatResponse
from agentscope.model._model_usage import ChatUsage


def test_agentscope_chat_response_supports_deepcopy_after_copaw_init() -> None:
    response = ChatResponse(
        content=[TextBlock(type="text", text="hello")],
        usage=ChatUsage(
            input_tokens=3,
            output_tokens=5,
            time=0.2,
            metadata={"provider": "openai"},
        ),
        metadata={"trace_id": "trace-1"},
    )

    cloned = deepcopy(response)

    assert isinstance(cloned, ChatResponse)
    assert cloned is not response
    assert isinstance(cloned.usage, ChatUsage)
    assert cloned.usage is not response.usage
    assert cloned.usage.input_tokens == 3
    assert cloned.metadata == {"trace_id": "trace-1"}


def test_agentscope_runtime_tracing_deepcopy_requires_patch_and_works_after_copaw_init() -> None:
    pre_patch = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from copy import deepcopy\n"
                "from agentscope.message import TextBlock\n"
                "from agentscope.model._model_response import ChatResponse\n"
                "from agentscope.model._model_usage import ChatUsage\n"
                "resp = ChatResponse(content=[TextBlock(type='text', text='x')], "
                "usage=ChatUsage(input_tokens=1, output_tokens=2, time=0.1))\n"
                "try:\n"
                "    deepcopy(resp)\n"
                "except Exception as exc:\n"
                "    print(type(exc).__name__, str(exc))\n"
                "else:\n"
                "    print('UNEXPECTED_OK')\n"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "KeyError '__deepcopy__'" in pre_patch.stdout

    post_patch = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import copaw\n"
                "from agentscope.message import TextBlock\n"
                "from agentscope.model._model_response import ChatResponse\n"
                "from agentscope.model._model_usage import ChatUsage\n"
                "from agentscope_runtime.engine.tracing.wrapper import _trace_last_resp\n"
                "class DummyEvent:\n"
                "    def on_log(self, *args, **kwargs):\n"
                "        print(kwargs.get('payload', {}).get('metadata', {}).get('trace_id'))\n"
                "class DummySpan:\n"
                "    def set_attribute(self, *args, **kwargs):\n"
                "        pass\n"
                "resp = ChatResponse(\n"
                "    content=[TextBlock(type='text', text='hello')],\n"
                "    usage=ChatUsage(input_tokens=1, output_tokens=2, time=0.1),\n"
                "    metadata={'trace_id': 'trace-2'},\n"
                ")\n"
                "_trace_last_resp(resp, lambda _: 'stop', DummyEvent(), DummySpan())\n"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert post_patch.returncode == 0, post_patch.stderr
    assert post_patch.stdout.strip() == "trace-2"
