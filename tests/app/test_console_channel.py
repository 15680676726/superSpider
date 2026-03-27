# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from copaw.app.channels.console.channel import ConsoleChannel


class _EncodingCheckingStdout:
    def __init__(self, *, encoding: str) -> None:
        self.encoding = encoding
        self.writes: list[str] = []

    def isatty(self) -> bool:
        return False

    def write(self, text: str) -> int:
        text.encode(self.encoding)
        self.writes.append(text)
        return len(text)

    def flush(self) -> None:
        return None


async def _noop_process(_request):
    if False:
        yield None


def test_console_channel_send_degrades_unencodable_output(monkeypatch) -> None:
    fake_stdout = _EncodingCheckingStdout(encoding="gbk")
    monkeypatch.setattr(
        "copaw.app.channels.console.channel.sys.stdout",
        fake_stdout,
    )
    channel = ConsoleChannel(
        process=_noop_process,
        enabled=True,
        bot_prefix="[BOT] ",
    )

    asyncio.run(channel.send("demo-user", "正常文本"))

    rendered = "".join(fake_stdout.writes)
    assert "demo-user" in rendered
    assert "正常文本" in rendered
