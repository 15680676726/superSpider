# -*- coding: utf-8 -*-
"""Process-local runtime state for the Weixin iLink channel."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WeixinILinkRuntimeState:
    def __init__(self) -> None:
        self._state: dict[str, Any] = {
            "login_status": "unconfigured",
            "polling_status": "stopped",
            "token_source": "",
            "last_qr_issued_at": None,
            "last_update_id": None,
            "last_receive_at": None,
            "last_send_at": None,
            "last_error": "",
            "qrcode": "",
            "qrcode_img_content": "",
            "bot_token": "",
            "base_url": "",
            "ilink_bot_id": "",
            "ilink_user_id": "",
        }

    def snapshot(self) -> dict[str, Any]:
        return dict(self._state)

    @property
    def qrcode(self) -> str:
        return str(self._state.get("qrcode") or "")

    def begin_qr_login(
        self,
        *,
        qrcode: str,
        qrcode_img_content: str,
        base_url: str,
    ) -> dict[str, Any]:
        self._state.update(
            {
                "login_status": "waiting_scan",
                "last_qr_issued_at": _utc_now(),
                "last_error": "",
                "qrcode": qrcode,
                "qrcode_img_content": qrcode_img_content,
                "bot_token": "",
                "base_url": base_url,
                "ilink_bot_id": "",
                "ilink_user_id": "",
            },
        )
        return self.snapshot()

    def mark_authorized_pending_save(
        self,
        *,
        bot_token: str,
        base_url: str,
        ilink_bot_id: str,
        ilink_user_id: str,
        token_source: str,
    ) -> dict[str, Any]:
        self._state.update(
            {
                "login_status": "authorized_pending_save",
                "last_error": "",
                "bot_token": bot_token,
                "base_url": base_url,
                "ilink_bot_id": ilink_bot_id,
                "ilink_user_id": ilink_user_id,
                "token_source": token_source,
            },
        )
        return self.snapshot()

    def mark_auth_expired(self, *, reason: str) -> dict[str, Any]:
        self._state.update(
            {
                "login_status": "auth_expired",
                "polling_status": "stopped",
                "last_error": reason,
            },
        )
        return self.snapshot()
