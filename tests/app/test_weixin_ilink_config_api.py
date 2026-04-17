# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.config import router as config_router
from copaw.app.channels.weixin_ilink.client import (
    WeixinILinkQRCodeSession,
    WeixinILinkQRCodeStatus,
)
from copaw.config.config import ChannelConfig, Config, WeixinILinkConfig


def _build_config_app() -> TestClient:
    app = FastAPI()
    app.include_router(config_router)
    return TestClient(app)


def test_list_channel_types_includes_weixin_ilink_builtin() -> None:
    client = _build_config_app()

    response = client.get("/config/channels/types")

    assert response.status_code == 200
    assert "weixin_ilink" in response.json()


def test_put_weixin_ilink_channel_accepts_formal_config_shape(monkeypatch) -> None:
    client = _build_config_app()

    async def _fake_dispatch(*args, **kwargs) -> dict[str, object]:
        return {"success": True, "phase": "completed"}

    monkeypatch.setattr(
        "copaw.app.routers.config._dispatch_config_mutation",
        _fake_dispatch,
    )

    response = client.put(
        "/config/channels/weixin_ilink",
        json={
            "enabled": True,
            "bot_prefix": "[BOT]",
            "bot_token": "token-123",
            "bot_token_file": "~/.qwenpaw/weixin_bot_token",
            "base_url": "",
            "media_dir": "~/.qwenpaw/media",
            "dm_policy": "open",
            "group_policy": "open",
            "group_reply_mode": "mention_or_prefix",
            "group_allowlist": ["group-alpha"],
            "proactive_targets": ["dm:user-alpha", "group:group-alpha"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["bot_token"] == "token-123"
    assert payload["group_reply_mode"] == "mention_or_prefix"
    assert payload["group_allowlist"] == ["group-alpha"]
    assert payload["proactive_targets"] == ["dm:user-alpha", "group:group-alpha"]


def test_weixin_ilink_login_qr_returns_waiting_scan_runtime_projection(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _build_config_app()

    config = Config(
        channels=ChannelConfig(
            weixin_ilink=WeixinILinkConfig(
                bot_token_file=str(tmp_path / "weixin.token"),
            ),
        ),
    )
    monkeypatch.setattr("copaw.app.routers.config.load_config", lambda: config)

    async def _fake_get_bot_qrcode(self, *, bot_type: int = 3):
        assert bot_type == 3
        return WeixinILinkQRCodeSession(
            qrcode="qr-1",
            qrcode_img_content="https://open.weixin.qq.com/qrcode/qr-1",
        )

    monkeypatch.setattr(
        "copaw.app.channels.weixin_ilink.client.WeixinILinkApiClient.get_bot_qrcode",
        _fake_get_bot_qrcode,
    )

    response = client.post("/config/channels/weixin_ilink/login/qr")

    assert response.status_code == 200
    payload = response.json()
    assert payload["login_status"] == "waiting_scan"
    assert payload["qrcode"] == "qr-1"
    assert payload["qrcode_img_content"] == "https://open.weixin.qq.com/qrcode/qr-1"


def test_weixin_ilink_login_status_returns_authorized_pending_save_until_channel_config_is_saved(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _build_config_app()
    token_path = tmp_path / "weixin.token"
    config = Config(
        channels=ChannelConfig(
            weixin_ilink=WeixinILinkConfig(
                bot_token_file=str(token_path),
            ),
        ),
    )
    monkeypatch.setattr("copaw.app.routers.config.load_config", lambda: config)

    async def _fake_get_bot_qrcode(self, *, bot_type: int = 3):
        return WeixinILinkQRCodeSession(
            qrcode="qr-2",
            qrcode_img_content="https://open.weixin.qq.com/qrcode/qr-2",
        )

    async def _fake_get_qrcode_status(self, qrcode: str):
        assert qrcode == "qr-2"
        return WeixinILinkQRCodeStatus(
            status="confirmed",
            bot_token="token-abc",
            base_url="https://ilinkai.weixin.qq.com",
            ilink_bot_id="bot-1",
            ilink_user_id="user-1",
        )

    monkeypatch.setattr(
        "copaw.app.channels.weixin_ilink.client.WeixinILinkApiClient.get_bot_qrcode",
        _fake_get_bot_qrcode,
    )
    monkeypatch.setattr(
        "copaw.app.channels.weixin_ilink.client.WeixinILinkApiClient.get_qrcode_status",
        _fake_get_qrcode_status,
    )

    admitted = client.post("/config/channels/weixin_ilink/login/qr")
    assert admitted.status_code == 200

    response = client.get("/config/channels/weixin_ilink/login/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["login_status"] == "authorized_pending_save"
    assert payload["bot_token"] == "token-abc"
    assert payload["token_source"] == "qr"
    assert token_path.read_text(encoding="utf-8") == "token-abc"


def test_weixin_ilink_rebind_marks_old_token_expired_without_mutating_formal_config(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = _build_config_app()
    config = Config(
        channels=ChannelConfig(
            weixin_ilink=WeixinILinkConfig(
                bot_token="config-token",
                bot_token_file=str(tmp_path / "weixin.token"),
            ),
        ),
    )
    monkeypatch.setattr("copaw.app.routers.config.load_config", lambda: config)

    response = client.post("/config/channels/weixin_ilink/login/rebind")

    assert response.status_code == 200
    payload = response.json()
    assert payload["login_status"] == "auth_expired"
    assert payload["last_error"] == "rebind_requested"
    assert config.channels.weixin_ilink.bot_token == "config-token"
