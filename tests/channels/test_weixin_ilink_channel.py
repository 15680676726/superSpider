# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from agentscope_runtime.engine.schemas.agent_schemas import ContentType

from copaw.app.channels.weixin_ilink.channel import WeixinILinkChannel


def _capturing_process(captured: list[object]):
    async def _process(request):
        captured.append(request)
        if False:
            yield None

    return _process


def _build_channel(**overrides) -> WeixinILinkChannel:
    return WeixinILinkChannel(
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
        **overrides,
    )


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
