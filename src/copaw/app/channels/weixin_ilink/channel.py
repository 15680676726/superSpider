# -*- coding: utf-8 -*-
"""Minimal Weixin iLink channel shell.

Task 1 only needs this class to load through the built-in registry so the
formal config surface can recognize `weixin_ilink`. Real polling, QR login,
and outbound send behavior land in later TDD tasks.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from ....config.config import WeixinILinkConfig as WeixinILinkChannelConfig
from ..base import BaseChannel, OnReplySent, ProcessHandler

logger = logging.getLogger(__name__)


class WeixinILinkChannel(BaseChannel):
    """Temporary minimal built-in shell for the iLink WeChat channel."""

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
        self.bot_token = bot_token
        self.bot_token_file = bot_token_file
        self.base_url = base_url
        self.media_dir = str(Path(media_dir).expanduser())
        self.group_reply_mode = group_reply_mode
        self.group_allowlist = list(group_allowlist or [])
        self.proactive_targets = list(proactive_targets or [])

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

    async def start(self) -> None:
        logger.debug("weixin_ilink channel shell started")

    async def stop(self) -> None:
        logger.debug("weixin_ilink channel shell stopped")

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: dict | None = None,
    ) -> None:
        del to_handle
        del text
        del meta
        raise NotImplementedError(
            "Weixin iLink send is not implemented yet; later TDD tasks will land the real runtime.",
        )
