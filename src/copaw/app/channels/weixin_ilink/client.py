# -*- coding: utf-8 -*-
"""Minimal iLink Bot HTTP API client."""

from __future__ import annotations

import base64
import secrets
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

DEFAULT_WEIXIN_ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"


def _expand_path(path: str) -> Path:
    return Path(path).expanduser()


def read_bot_token_file(path: str) -> str:
    token_path = _expand_path(path)
    if not token_path.is_file():
        return ""
    return token_path.read_text(encoding="utf-8").strip()


def write_bot_token_file(path: str, token: str) -> None:
    token_path = _expand_path(path)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(str(token or ""), encoding="utf-8")


def _normalize_base_url(base_url: str) -> str:
    text = str(base_url or "").strip()
    return (text or DEFAULT_WEIXIN_ILINK_BASE_URL).rstrip("/")


def _random_wechat_uin() -> str:
    raw = struct.pack("<I", secrets.randbits(32))
    return base64.b64encode(raw).decode("ascii")


@dataclass(slots=True)
class WeixinILinkQRCodeSession:
    qrcode: str
    qrcode_img_content: str


@dataclass(slots=True)
class WeixinILinkQRCodeStatus:
    status: str
    bot_token: str
    base_url: str
    ilink_bot_id: str
    ilink_user_id: str


@dataclass(slots=True)
class WeixinILinkUpdatesResponse:
    ret: int
    messages: list[dict[str, Any]]
    next_cursor: str
    longpolling_timeout_ms: int


class WeixinILinkApiClient:
    def __init__(
        self,
        *,
        bot_token: str,
        base_url: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._bot_token = str(bot_token or "").strip()
        self._base_url = _normalize_base_url(base_url)
        self._transport = transport
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        return self._base_url

    def _build_url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _auth_headers(self) -> dict[str, str]:
        if not self._bot_token:
            raise ValueError("weixin_ilink bot token is required for this operation")
        return {
            "Authorization": f"Bearer {self._bot_token}",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": _random_wechat_uin(),
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=self._timeout,
        ) as client:
            response = await client.request(
                method,
                self._build_url(path),
                params=params,
                json=json_body,
                headers=headers,
            )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("weixin_ilink response must be a JSON object")
        return data

    async def get_bot_qrcode(
        self,
        *,
        bot_type: int = 3,
    ) -> WeixinILinkQRCodeSession:
        data = await self._request(
            "GET",
            "/ilink/bot/get_bot_qrcode",
            params={"bot_type": bot_type},
        )
        return WeixinILinkQRCodeSession(
            qrcode=str(data.get("qrcode") or ""),
            qrcode_img_content=str(data.get("qrcode_img_content") or ""),
        )

    async def get_qrcode_status(
        self,
        qrcode: str,
    ) -> WeixinILinkQRCodeStatus:
        data = await self._request(
            "GET",
            "/ilink/bot/get_qrcode_status",
            params={"qrcode": qrcode},
        )
        return WeixinILinkQRCodeStatus(
            status=str(data.get("status") or ""),
            bot_token=str(data.get("bot_token") or ""),
            base_url=str(data.get("baseurl") or data.get("base_url") or self._base_url),
            ilink_bot_id=str(data.get("ilink_bot_id") or ""),
            ilink_user_id=str(data.get("ilink_user_id") or ""),
        )

    async def get_updates(
        self,
        *,
        cursor: str = "",
        channel_version: str = "1.0.0",
    ) -> WeixinILinkUpdatesResponse:
        data = await self._request(
            "POST",
            "/ilink/bot/getupdates",
            json_body={
                "base_info": {"channel_version": channel_version},
                "get_updates_buf": cursor,
            },
            headers=self._auth_headers(),
        )
        messages = data.get("msgs")
        return WeixinILinkUpdatesResponse(
            ret=int(data.get("ret") or 0),
            messages=list(messages) if isinstance(messages, list) else [],
            next_cursor=str(data.get("get_updates_buf") or ""),
            longpolling_timeout_ms=int(data.get("longpolling_timeout_ms") or 0),
        )

    async def send_text(
        self,
        *,
        to_user_id: str,
        text: str,
        context_token: str | None = None,
        channel_version: str = "1.0.0",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "to_user_id": to_user_id,
            "msg": {
                "type": "text",
                "content": text,
            },
            "base_info": {"channel_version": channel_version},
        }
        if context_token:
            payload["context_token"] = context_token
        return await self._request(
            "POST",
            "/ilink/bot/sendmessage",
            json_body=payload,
            headers=self._auth_headers(),
        )
