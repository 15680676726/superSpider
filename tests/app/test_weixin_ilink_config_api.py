# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.config import router as config_router


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
