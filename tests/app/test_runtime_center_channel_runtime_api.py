# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.channels.weixin_ilink.runtime_state import WeixinILinkRuntimeState
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.runtime_center.state_query import RuntimeCenterStateQueryService
from copaw.state import SQLiteStateStore
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)


def _build_runtime_center_app(tmp_path) -> tuple[TestClient, WeixinILinkRuntimeState]:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    runtime_state = WeixinILinkRuntimeState()
    query_service = RuntimeCenterStateQueryService(
        task_repository=SqliteTaskRepository(state_store),
        task_runtime_repository=SqliteTaskRuntimeRepository(state_store),
        runtime_frame_repository=SqliteRuntimeFrameRepository(state_store),
        schedule_repository=SqliteScheduleRepository(state_store),
        goal_repository=SqliteGoalRepository(state_store),
        work_context_repository=SqliteWorkContextRepository(state_store),
        decision_request_repository=SqliteDecisionRequestRepository(state_store),
        weixin_ilink_runtime_state=runtime_state,
    )
    app = FastAPI()
    app.include_router(runtime_center_router)
    app.state.state_query_service = query_service
    return TestClient(app), runtime_state


def test_runtime_center_lists_weixin_ilink_runtime_projection(tmp_path) -> None:
    client, runtime_state = _build_runtime_center_app(tmp_path)
    runtime_state.begin_qr_login(
        qrcode="qr-1",
        qrcode_img_content="https://open.weixin.qq.com/qrcode/qr-1",
        base_url="https://ilinkai.weixin.qq.com",
    )

    response = client.get("/runtime-center/channel-runtimes")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["channel"] == "weixin_ilink"
    assert payload[0]["login_status"] == "waiting_scan"
    assert payload[0]["route"] == "/api/runtime-center/channel-runtimes/weixin_ilink"


def test_runtime_center_channel_runtime_detail_surfaces_login_polling_and_last_error_truth(
    tmp_path,
) -> None:
    client, runtime_state = _build_runtime_center_app(tmp_path)
    runtime_state.mark_authorized_pending_save(
        bot_token="token-abc",
        base_url="https://ilinkai.weixin.qq.com",
        ilink_bot_id="bot-1",
        ilink_user_id="user-1",
        token_source="qr",
    )
    runtime_state.mark_auth_expired(reason="rebind_requested")

    response = client.get("/runtime-center/channel-runtimes/weixin_ilink")

    assert response.status_code == 200
    payload = response.json()
    assert payload["channel"] == "weixin_ilink"
    assert payload["login_status"] == "auth_expired"
    assert payload["token_source"] == "qr"
    assert payload["last_error"] == "rebind_requested"
