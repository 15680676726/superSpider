# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from copaw.app.channels.weixin_ilink.client import (
    DEFAULT_WEIXIN_ILINK_BASE_URL,
    WeixinILinkApiClient,
    read_bot_token_file,
    write_bot_token_file,
)


def test_token_file_round_trip_uses_utf8_and_expands_user_home(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    token_path = "~/.qwenpaw/weixin_bot_token"

    write_bot_token_file(token_path, "token-123")

    assert (tmp_path / ".qwenpaw" / "weixin_bot_token").read_text(
        encoding="utf-8",
    ) == "token-123"
    assert read_bot_token_file(token_path) == "token-123"


def test_request_login_qr_uses_default_base_url_when_config_is_blank() -> None:
    captured: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "qrcode": "qr-1",
                "qrcode_img_content": "https://open.weixin.qq.com/qrcode/qr-1",
            },
        )

    async def _run() -> None:
        client = WeixinILinkApiClient(
            bot_token="",
            base_url="",
            transport=httpx.MockTransport(_handler),
        )
        session = await client.get_bot_qrcode()
        assert session.qrcode == "qr-1"
        assert session.qrcode_img_content == "https://open.weixin.qq.com/qrcode/qr-1"

    asyncio.run(_run())

    assert captured["method"] == "GET"
    assert captured["url"] == (
        f"{DEFAULT_WEIXIN_ILINK_BASE_URL}/ilink/bot/get_bot_qrcode?bot_type=3"
    )


def test_poll_qrcode_status_returns_confirmed_token_payload() -> None:
    captured: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "status": "confirmed",
                "bot_token": "token-abc",
                "ilink_bot_id": "bot-1",
                "baseurl": "https://ilinkai.weixin.qq.com",
                "ilink_user_id": "user-1",
            },
        )

    async def _run() -> None:
        client = WeixinILinkApiClient(
            bot_token="",
            base_url="",
            transport=httpx.MockTransport(_handler),
        )
        status = await client.get_qrcode_status("qr-1")
        assert status.status == "confirmed"
        assert status.bot_token == "token-abc"
        assert status.base_url == "https://ilinkai.weixin.qq.com"
        assert status.ilink_user_id == "user-1"

    asyncio.run(_run())

    assert captured["url"] == (
        f"{DEFAULT_WEIXIN_ILINK_BASE_URL}/ilink/bot/get_qrcode_status?qrcode=qr-1"
    )


def test_get_updates_posts_cursor_and_auth_headers() -> None:
    captured: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["auth"] = request.headers.get("Authorization")
        captured["auth_type"] = request.headers.get("AuthorizationType")
        captured["wechat_uin"] = request.headers.get("X-WECHAT-UIN")
        captured["json"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "ret": 0,
                "msgs": [],
                "get_updates_buf": "cursor-next",
                "longpolling_timeout_ms": 35000,
            },
        )

    async def _run() -> None:
        client = WeixinILinkApiClient(
            bot_token="token-abc",
            base_url="https://ilinkai.weixin.qq.com",
            transport=httpx.MockTransport(_handler),
        )
        response = await client.get_updates(cursor="cursor-1")
        assert response.next_cursor == "cursor-next"
        assert response.longpolling_timeout_ms == 35000

    asyncio.run(_run())

    assert captured["method"] == "POST"
    assert captured["auth"] == "Bearer token-abc"
    assert captured["auth_type"] == "ilink_bot_token"
    assert captured["wechat_uin"]
    assert '"get_updates_buf":"cursor-1"' in str(captured["json"])
    assert '"channel_version":"1.0.0"' in str(captured["json"])


def test_send_text_wraps_context_token_in_message_payload() -> None:
    captured: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = request.read().decode("utf-8")
        return httpx.Response(200, json={"ret": 0})

    async def _run() -> None:
        client = WeixinILinkApiClient(
            bot_token="token-abc",
            base_url="https://ilinkai.weixin.qq.com",
            transport=httpx.MockTransport(_handler),
        )
        await client.send_text(
            to_user_id="user@im.wechat",
            text="hello back",
            context_token="ctx-1",
        )

    asyncio.run(_run())

    assert '"to_user_id":"user@im.wechat"' in str(captured["json"])
    assert '"context_token":"ctx-1"' in str(captured["json"])
    assert '"hello back"' in str(captured["json"])
