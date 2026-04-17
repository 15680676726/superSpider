# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from agentscope_runtime.engine.schemas.agent_schemas import ContentType

from copaw.app.channels.weixin_ilink.channel import WeixinILinkChannel
from copaw.app.channels.weixin_ilink.client import WeixinILinkUpdatesResponse
from copaw.app.channels.weixin_ilink.runtime_state import WeixinILinkRuntimeState
from copaw.config.config import WeixinILinkConfig


def _capturing_process(captured: list[object]):
    async def _process(request):
        captured.append(request)
        if False:
            yield None

    return _process


def _build_channel(**overrides) -> WeixinILinkChannel:
    runtime_state = overrides.pop("runtime_state", None)
    kwargs = dict(
        process=_capturing_process(overrides.pop("captured", [])),
        enabled=True,
        bot_prefix="[BOT]",
        bot_token="token-123",
        bot_token_file="~/.qwenpaw/weixin_bot_token",
        base_url="https://ilinkai.weixin.qq.com",
        media_dir="~/.qwenpaw/media",
        group_reply_mode=overrides.pop("group_reply_mode", "mention_or_prefix"),
        group_allowlist=overrides.pop("group_allowlist", []),
        proactive_targets=overrides.pop("proactive_targets", []),
    )
    if runtime_state is not None:
        kwargs["runtime_state"] = runtime_state
    kwargs.update(overrides)
    return WeixinILinkChannel(**kwargs)


def test_dm_message_always_enters_main_brain() -> None:
    captured: list[object] = []
    channel = _build_channel(captured=captured)
    payload = channel.build_native_payload_from_update(
        {
            "msg_id": "msg-1",
            "from_user_id": "user-1",
            "from_user_name": "Alice",
            "msg_type": "text",
            "content": "hello main brain",
            "context_token": "ctx-1",
        },
    )

    assert payload is not None

    asyncio.run(channel.consume_one(payload))

    assert len(captured) == 1
    request = captured[0]
    assert request.session_id == "channel:weixin_ilink:dm:user-1"
    assert request.channel == "weixin_ilink"


def test_group_message_requires_mention_or_prefix_by_default() -> None:
    channel = _build_channel()

    ignored = channel.build_native_payload_from_update(
        {
            "msg_id": "msg-2",
            "from_user_id": "user-2",
            "room_id": "group-1",
            "msg_type": "text",
            "content": "plain group chatter",
            "at_bot": False,
        },
    )
    routed = channel.build_native_payload_from_update(
        {
            "msg_id": "msg-3",
            "from_user_id": "user-2",
            "room_id": "group-1",
            "msg_type": "text",
            "content": "follow this up",
            "at_bot": True,
        },
    )

    assert ignored is None
    assert routed is not None
    assert routed["meta"]["is_mention"] is True


def test_allowlisted_group_can_run_full_open_mode() -> None:
    captured: list[object] = []
    channel = _build_channel(
        captured=captured,
        group_reply_mode="whitelist_full_open",
        group_allowlist=["group-allow"],
    )
    payload = channel.build_native_payload_from_update(
        {
            "msg_id": "msg-4",
            "from_user_id": "user-3",
            "room_id": "group-allow",
            "msg_type": "text",
            "content": "plain text still routes",
            "at_bot": False,
        },
    )

    assert payload is not None

    asyncio.run(channel.consume_one(payload))

    assert len(captured) == 1
    request = captured[0]
    assert request.session_id == "channel:weixin_ilink:group:group-allow"


def test_voice_payload_uses_asr_text_and_keeps_media_reference() -> None:
    channel = _build_channel()

    payload = channel.build_native_payload_from_update(
        {
            "msg_id": "msg-5",
            "from_user_id": "user-4",
            "msg_type": "voice",
            "asr_text": "voice transcript",
            "voice_url": "file:///tmp/voice.amr",
        },
    )

    assert payload is not None
    content_parts = payload["content_parts"]
    assert content_parts[0].type == ContentType.TEXT
    assert content_parts[0].text == "voice transcript"
    assert any(
        part.type == ContentType.AUDIO and getattr(part, "data", None) == "file:///tmp/voice.amr"
        for part in content_parts
    )


def test_send_uses_sendmessage_text_only_contract() -> None:
    channel = _build_channel()
    captured: dict[str, object] = {}

    class _FakeClient:
        async def send_text(self, **kwargs):
            captured.update(kwargs)
            return {"ret": 0}

    channel._client = _FakeClient()

    asyncio.run(
        channel.send(
            "user-5",
            "hello back",
            {"to_user_id": "user-5", "context_token": "ctx-5"},
        ),
    )

    assert captured == {
        "to_user_id": "user-5",
        "text": "hello back",
        "context_token": "ctx-5",
    }


def test_proactive_targets_reject_non_allowlisted_group_send() -> None:
    channel = _build_channel(proactive_targets=["group:group-allow"])

    with asyncio.Runner() as runner:
        try:
            runner.run(
                channel.send(
                    "group-locked",
                    "should not send",
                    {
                        "conversation_kind": "group",
                        "group_id": "group-locked",
                        "proactive": True,
                        "to_user_id": "group-locked",
                    },
                ),
            )
        except ValueError as exc:
            assert "group-locked" in str(exc)
        else:
            raise AssertionError("expected proactive group send guard to reject the target")


def test_start_reads_token_file_and_marks_runtime_running(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_state = WeixinILinkRuntimeState()
    token_path = tmp_path / "weixin_bot_token"
    token_path.write_text("token-from-file", encoding="utf-8")

    class _FakeApiClient:
        def __init__(self, *, bot_token: str, base_url: str = "") -> None:
            self.bot_token = bot_token
            self.base_url = base_url or "https://ilinkai.weixin.qq.com"

        async def get_updates(self, cursor: str = "") -> WeixinILinkUpdatesResponse:
            await asyncio.sleep(3600)
            return WeixinILinkUpdatesResponse(
                ret=0,
                messages=[],
                next_cursor=cursor,
                longpolling_timeout_ms=0,
            )

    monkeypatch.setattr(
        "copaw.app.channels.weixin_ilink.channel.WeixinILinkApiClient",
        _FakeApiClient,
    )
    channel = _build_channel(
        bot_token="",
        bot_token_file=str(token_path),
        runtime_state=runtime_state,
    )
    channel.set_enqueue(lambda payload: None)

    async def _run() -> None:
        await channel.start()
        snapshot = runtime_state.snapshot()
        assert snapshot["login_status"] == "running"
        assert snapshot["polling_status"] == "running"
        assert snapshot["token_source"] == "bot_token_file"
        assert channel._client is not None
        assert channel._client.bot_token == "token-from-file"
        await channel.stop()

    asyncio.run(_run())


def test_clone_preserves_runtime_state_for_config_reload() -> None:
    runtime_state = WeixinILinkRuntimeState()
    channel = _build_channel(runtime_state=runtime_state)

    clone = channel.clone(
        WeixinILinkConfig(
            enabled=True,
            bot_prefix="[BOT]",
            bot_token="token-456",
            bot_token_file="~/.qwenpaw/weixin_bot_token",
            base_url="https://ilinkai.weixin.qq.com",
            media_dir="~/.qwenpaw/media",
            dm_policy="open",
            group_policy="open",
            group_reply_mode="mention_or_prefix",
            group_allowlist=[],
            proactive_targets=[],
        ),
    )

    assert getattr(clone, "_runtime_state", None) is runtime_state


def test_poll_updates_records_last_receive_at_and_cursor() -> None:
    runtime_state = WeixinILinkRuntimeState()
    channel = _build_channel(runtime_state=runtime_state)
    captured: list[dict[str, object]] = []
    channel.set_enqueue(captured.append)

    class _FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        async def get_updates(self, cursor: str = "") -> WeixinILinkUpdatesResponse:
            self.calls += 1
            if self.calls == 1:
                return WeixinILinkUpdatesResponse(
                    ret=0,
                    messages=[
                        {
                            "msg_id": "msg-9",
                            "from_user_id": "user-9",
                            "msg_type": "text",
                            "content": "hello",
                        },
                    ],
                    next_cursor="cursor-next",
                    longpolling_timeout_ms=0,
                )
            raise asyncio.CancelledError

    channel._client = _FakeClient()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(channel._poll_updates_loop())

    snapshot = runtime_state.snapshot()
    assert snapshot["login_status"] == "running"
    assert snapshot["polling_status"] == "running"
    assert snapshot["last_update_id"] == "cursor-next"
    assert snapshot["last_receive_at"]
    assert len(captured) == 1
    assert captured[0]["meta"]["message_id"] == "msg-9"


def test_send_records_last_send_at() -> None:
    runtime_state = WeixinILinkRuntimeState()
    runtime_state._state.update(  # noqa: SLF001
        {
            "login_status": "running",
            "polling_status": "running",
            "token_source": "config",
        },
    )
    channel = _build_channel(runtime_state=runtime_state)

    class _FakeClient:
        async def send_text(self, **kwargs):
            return {"ret": 0}

    channel._client = _FakeClient()

    asyncio.run(
        channel.send(
            "user-6",
            "hello status",
            {"to_user_id": "user-6"},
        ),
    )

    snapshot = runtime_state.snapshot()
    assert snapshot["login_status"] == "running"
    assert snapshot["polling_status"] == "running"
    assert snapshot["last_send_at"]


def test_poll_auth_failure_marks_runtime_auth_expired() -> None:
    runtime_state = WeixinILinkRuntimeState()
    channel = _build_channel(runtime_state=runtime_state)
    channel.set_enqueue(lambda payload: None)
    request = httpx.Request("POST", "https://ilinkai.weixin.qq.com/ilink/bot/getupdates")
    response = httpx.Response(401, request=request)

    class _FakeClient:
        async def get_updates(self, cursor: str = "") -> WeixinILinkUpdatesResponse:
            raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    channel._client = _FakeClient()

    async def _run() -> None:
        task = asyncio.create_task(channel._poll_updates_loop())
        await asyncio.wait_for(task, timeout=0.2)

    asyncio.run(_run())

    snapshot = runtime_state.snapshot()
    assert snapshot["login_status"] == "auth_expired"
    assert snapshot["polling_status"] == "stopped"
    assert snapshot["last_error"] == "auth_failed:401"


def test_send_auth_failure_marks_runtime_auth_expired() -> None:
    runtime_state = WeixinILinkRuntimeState()
    runtime_state._state.update(  # noqa: SLF001
        {
            "login_status": "running",
            "polling_status": "running",
            "token_source": "config",
        },
    )
    channel = _build_channel(runtime_state=runtime_state)
    request = httpx.Request("POST", "https://ilinkai.weixin.qq.com/ilink/bot/sendmessage")
    response = httpx.Response(401, request=request)

    class _FakeClient:
        async def send_text(self, **kwargs):
            raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    channel._client = _FakeClient()

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(
            channel.send(
                "user-7",
                "hello fail",
                {"to_user_id": "user-7"},
            ),
        )

    snapshot = runtime_state.snapshot()
    assert snapshot["login_status"] == "auth_expired"
    assert snapshot["polling_status"] == "stopped"
    assert snapshot["last_error"] == "auth_failed:401"
