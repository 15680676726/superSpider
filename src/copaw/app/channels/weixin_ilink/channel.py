# -*- coding: utf-8 -*-
"""Weixin iLink channel."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Optional

from agentscope_runtime.engine.schemas.agent_schemas import (
    AudioContent,
    ContentType,
    FileContent,
    ImageContent,
    TextContent,
)

from ....config.config import WeixinILinkConfig as WeixinILinkChannelConfig
from .client import WeixinILinkApiClient, read_bot_token_file
from ..base import BaseChannel, OnReplySent, ProcessHandler

logger = logging.getLogger(__name__)


def _text(value: object | None) -> str:
    return str(value or "").strip()


class WeixinILinkChannel(BaseChannel):
    """Personal WeChat channel backed by the iLink Bot HTTP API."""

    channel = "weixin_ilink"

    def __init__(
        self,
        process: ProcessHandler,
        *,
        enabled: bool,
        bot_prefix: str,
        bot_token: str,
        bot_token_file: str,
        base_url: str,
        media_dir: str,
        group_reply_mode: str,
        group_allowlist: list[str] | None = None,
        proactive_targets: list[str] | None = None,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
        filter_tool_messages: bool = False,
        filter_thinking: bool = False,
        dm_policy: str = "open",
        group_policy: str = "open",
        allow_from: list[str] | None = None,
        deny_message: str = "",
    ) -> None:
        super().__init__(
            process,
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
            filter_tool_messages=filter_tool_messages,
            filter_thinking=filter_thinking,
            dm_policy=dm_policy,
            group_policy=group_policy,
            allow_from=allow_from,
            deny_message=deny_message,
        )
        self.enabled = enabled
        self.bot_prefix = bot_prefix
        self.bot_token = _text(bot_token)
        self.bot_token_file = bot_token_file
        self.base_url = base_url
        self.media_dir = str(Path(media_dir).expanduser())
        self.group_reply_mode = group_reply_mode or "mention_or_prefix"
        self.group_allowlist = list(group_allowlist or [])
        self.proactive_targets = list(proactive_targets or [])
        self._client: WeixinILinkApiClient | None = None
        self._poll_task: asyncio.Task | None = None
        self._cursor = ""
        self._media_root = Path(self.media_dir)
        self._load_client_if_possible()

    @classmethod
    def from_env(
        cls,
        process: ProcessHandler,
        on_reply_sent: OnReplySent = None,
    ) -> "WeixinILinkChannel":
        return cls(
            process=process,
            enabled=os.getenv("WEIXIN_CHANNEL_ENABLED", "0") == "1",
            bot_prefix=os.getenv("WEIXIN_BOT_PREFIX", "[BOT]"),
            bot_token=os.getenv("WEIXIN_BOT_TOKEN", ""),
            bot_token_file=os.getenv(
                "WEIXIN_BOT_TOKEN_FILE",
                "~/.qwenpaw/weixin_bot_token",
            ),
            base_url=os.getenv("WEIXIN_BASE_URL", ""),
            media_dir=os.getenv("WEIXIN_MEDIA_DIR", "~/.qwenpaw/media"),
            group_reply_mode=os.getenv(
                "WEIXIN_GROUP_REPLY_MODE",
                "mention_or_prefix",
            ),
            group_allowlist=[],
            proactive_targets=[],
            on_reply_sent=on_reply_sent,
            dm_policy=os.getenv("WEIXIN_DM_POLICY", "open"),
            group_policy=os.getenv("WEIXIN_GROUP_POLICY", "open"),
        )

    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: WeixinILinkChannelConfig,
        on_reply_sent: OnReplySent = None,
        show_tool_details: bool = True,
        filter_tool_messages: bool = False,
        filter_thinking: bool = False,
    ) -> "WeixinILinkChannel":
        return cls(
            process=process,
            enabled=config.enabled,
            bot_prefix=config.bot_prefix or "[BOT]",
            bot_token=config.bot_token,
            bot_token_file=config.bot_token_file,
            base_url=config.base_url,
            media_dir=config.media_dir,
            group_reply_mode=config.group_reply_mode,
            group_allowlist=list(config.group_allowlist),
            proactive_targets=list(config.proactive_targets),
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
            filter_tool_messages=filter_tool_messages,
            filter_thinking=filter_thinking,
            dm_policy=config.dm_policy,
            group_policy=config.group_policy,
            allow_from=list(config.allow_from),
            deny_message=config.deny_message,
        )

    def _load_client_if_possible(self) -> None:
        token = self.bot_token or read_bot_token_file(self.bot_token_file)
        self.bot_token = token
        self._client = (
            WeixinILinkApiClient(
                bot_token=token,
                base_url=self.base_url,
            )
            if token
            else None
        )

    def resolve_session_id(
        self,
        sender_id: str,
        channel_meta: Optional[dict[str, Any]] = None,
    ) -> str:
        meta = channel_meta or {}
        group_id = _text(meta.get("group_id") or meta.get("room_id"))
        if group_id:
            return f"channel:{self.channel}:group:{group_id}"
        return f"channel:{self.channel}:dm:{sender_id}"

    def build_native_payload_from_update(
        self,
        update: dict[str, Any],
    ) -> dict[str, Any] | None:
        sender_id = _text(
            update.get("from_user_id")
            or update.get("sender_id")
            or update.get("from_user")
            or update.get("ilink_user_id"),
        )
        if not sender_id:
            return None

        group_id = _text(
            update.get("room_id")
            or update.get("group_id")
            or update.get("chat_id"),
        )
        sender_name = _text(update.get("from_user_name") or update.get("sender_name"))
        group_name = _text(update.get("room_name") or update.get("group_name"))
        conversation_kind = "group" if group_id else "dm"
        is_mention = bool(update.get("at_bot") or update.get("is_mention"))
        text = _text(update.get("content") or update.get("text"))
        has_bot_prefix = bool(self.bot_prefix and text.startswith(self.bot_prefix))
        if has_bot_prefix:
            text = text[len(self.bot_prefix) :].lstrip()

        if conversation_kind == "group":
            full_open = (
                self.group_reply_mode == "whitelist_full_open"
                and group_id in self.group_allowlist
            )
            if not (full_open or is_mention or has_bot_prefix):
                return None

        content_parts: list[Any] = []
        asr_text = _text(update.get("asr_text") or update.get("asr"))
        msg_type = _text(update.get("msg_type") or update.get("type")).lower()

        if text:
            content_parts.append(TextContent(type=ContentType.TEXT, text=text))
        elif msg_type == "voice" and asr_text:
            content_parts.append(
                TextContent(type=ContentType.TEXT, text=asr_text),
            )

        image_url = _text(update.get("image_url") or update.get("image_path"))
        if image_url:
            content_parts.append(
                ImageContent(type=ContentType.IMAGE, image_url=image_url),
            )

        file_url = _text(update.get("file_url") or update.get("file_path"))
        if file_url:
            content_parts.append(
                FileContent(type=ContentType.FILE, file_url=file_url),
            )

        voice_url = _text(
            update.get("voice_url")
            or update.get("audio_url")
            or update.get("voice_path"),
        )
        if voice_url:
            content_parts.append(
                AudioContent(type=ContentType.AUDIO, data=voice_url),
            )

        if not content_parts:
            content_parts.append(TextContent(type=ContentType.TEXT, text=""))

        to_user_id = _text(
            update.get("to_user_id")
            or group_id
            or sender_id,
        )
        meta = {
            "chat_id": group_id or sender_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "group_id": group_id,
            "group_name": group_name,
            "message_id": _text(update.get("msg_id") or update.get("message_id")),
            "conversation_kind": conversation_kind,
            "is_group": conversation_kind == "group",
            "is_mention": is_mention,
            "has_bot_prefix": has_bot_prefix,
            "context_token": _text(update.get("context_token")),
            "to_user_id": to_user_id,
        }
        session_id = self.resolve_session_id(sender_id, meta)
        return {
            "channel_id": self.channel,
            "sender_id": sender_id,
            "session_id": session_id,
            "content_parts": content_parts,
            "meta": meta,
        }

    def build_agent_request_from_native(self, native_payload: Any) -> Any:
        payload = native_payload if isinstance(native_payload, dict) else {}
        sender_id = _text(payload.get("sender_id"))
        meta = dict(payload.get("meta") or {})
        session_id = _text(payload.get("session_id")) or self.resolve_session_id(
            sender_id,
            meta,
        )
        request = self.build_agent_request_from_user_content(
            channel_id=payload.get("channel_id") or self.channel,
            sender_id=sender_id,
            session_id=session_id,
            content_parts=list(payload.get("content_parts") or []),
            channel_meta=meta,
        )
        request.user_id = sender_id
        request.channel_meta = meta
        return request

    def get_to_handle_from_request(self, request: Any) -> str:
        meta = getattr(request, "channel_meta", None) or {}
        return _text(
            meta.get("to_user_id")
            or meta.get("group_id")
            or getattr(request, "user_id", ""),
        )

    def to_handle_from_target(self, *, user_id: str, session_id: str) -> str:
        if session_id.startswith(f"channel:{self.channel}:group:"):
            return session_id.rsplit(":", 1)[-1]
        if session_id.startswith(f"channel:{self.channel}:dm:"):
            return session_id.rsplit(":", 1)[-1]
        return user_id

    async def _poll_updates_loop(self) -> None:
        assert self._client is not None
        while True:
            try:
                response = await self._client.get_updates(cursor=self._cursor)
                if response.next_cursor:
                    self._cursor = response.next_cursor
                for item in response.messages:
                    if not isinstance(item, dict):
                        continue
                    payload = self.build_native_payload_from_update(item)
                    if payload is not None and self._enqueue is not None:
                        self._enqueue(payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("weixin_ilink polling failed")
                await asyncio.sleep(5)

    async def start(self) -> None:
        if not self.enabled:
            logger.debug("weixin_ilink channel disabled")
            return
        if self._client is None:
            self._load_client_if_possible()
        if self._client is None or self._enqueue is None or self._poll_task is not None:
            return
        self._poll_task = asyncio.create_task(
            self._poll_updates_loop(),
            name="weixin_ilink_polling",
        )

    async def stop(self) -> None:
        if self._poll_task is None:
            return
        self._poll_task.cancel()
        try:
            await self._poll_task
        except asyncio.CancelledError:
            pass
        finally:
            self._poll_task = None

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: dict | None = None,
    ) -> None:
        if not self.enabled:
            return
        if self._client is None:
            self._load_client_if_possible()
        if self._client is None:
            raise RuntimeError("weixin_ilink bot token is not configured")

        meta = dict(meta or {})
        conversation_kind = _text(meta.get("conversation_kind")) or "dm"
        group_id = _text(meta.get("group_id") or (to_handle if conversation_kind == "group" else ""))
        if meta.get("proactive") and conversation_kind == "group":
            allowed = (
                f"group:{group_id}" in self.proactive_targets
                or group_id in self.group_allowlist
            )
            if not allowed:
                raise ValueError(
                    f"weixin_ilink proactive group target '{group_id}' is not allowlisted",
                )
        await self._client.send_text(
            to_user_id=_text(meta.get("to_user_id") or to_handle),
            text=text,
            context_token=_text(meta.get("context_token")) or None,
        )
