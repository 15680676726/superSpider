# -*- coding: utf-8 -*-
from __future__ import annotations

from .shared import *  # noqa: F401,F403

from agentscope.message import Msg

from copaw.environments.models import SessionMount
from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelTurnExecutor
from copaw.kernel.main_brain_intake import MainBrainIntakeContract
from copaw.kernel.main_brain_orchestrator import MainBrainOrchestrator
from copaw.media import MediaService
from copaw.state import MediaAnalysisRecord
from copaw.state.repositories.base import BaseMediaAnalysisRepository


class _InMemoryMediaAnalysisRepository(BaseMediaAnalysisRepository):
    def __init__(self) -> None:
        self._records: dict[str, MediaAnalysisRecord] = {}

    def get_analysis(self, analysis_id: str) -> MediaAnalysisRecord | None:
        return self._records.get(analysis_id)

    def list_analyses(
        self,
        *,
        industry_instance_id: str | None = None,
        thread_id: str | None = None,
        entry_point: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MediaAnalysisRecord]:
        records = list(self._records.values())
        filtered: list[MediaAnalysisRecord] = []
        for record in records:
            if industry_instance_id is not None and record.industry_instance_id != industry_instance_id:
                continue
            if thread_id is not None and record.thread_id != thread_id:
                continue
            if entry_point is not None and record.entry_point != entry_point:
                continue
            if status is not None and record.status != status:
                continue
            filtered.append(record)
        filtered.sort(
            key=lambda item: item.updated_at or item.created_at,
            reverse=True,
        )
        return filtered[:limit] if isinstance(limit, int) else filtered

    def upsert_analysis(self, analysis: MediaAnalysisRecord) -> MediaAnalysisRecord:
        self._records[analysis.analysis_id] = analysis
        return analysis

    def delete_analysis(self, analysis_id: str) -> bool:
        return self._records.pop(analysis_id, None) is not None


def _build_media_service() -> MediaService:
    return MediaService(
        repository=_InMemoryMediaAnalysisRepository(),
        evidence_ledger=EvidenceLedger(),
    )


class _CapturingRouteQueryExecutionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.synced: dict[str, object] = {}

    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield Msg(name="assistant", role="assistant", content="kernel route done"), True

    def set_session_backend(self, session_backend) -> None:
        self.synced["session_backend"] = session_backend

    def set_kernel_dispatcher(self, kernel_dispatcher) -> None:
        self.synced["kernel_dispatcher"] = kernel_dispatcher

    def resolve_request_owner_agent_id(self, *, request) -> str | None:
        return getattr(request, "agent_id", None) or None


class _CapturingRouteChatService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.synced: dict[str, object] = {}

    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield Msg(name="assistant", role="assistant", content="chat route done"), True

    def set_session_backend(self, session_backend) -> None:
        self.synced["session_backend"] = session_backend


class _CapturingRouteEnvironmentService:
    def __init__(self, *, sessions: dict[str, SessionMount] | None = None) -> None:
        self._sessions = sessions or {}

    def get_session(self, session_mount_id: str) -> SessionMount | None:
        return self._sessions.get(session_mount_id)


def test_runtime_center_overview_uses_state_and_evidence_services():
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    app.state.governance_service = FakeGovernanceService()
    app.state.routine_service = FakeRoutineService()

    client = TestClient(app)
    response = client.get("/runtime-center/overview")

    assert response.status_code == 200
    assert response.headers["x-copaw-runtime-surface"] == "runtime-center"
    assert response.headers["x-copaw-runtime-surface-version"] == "runtime-center-v1"

    payload = response.json()
    assert payload["surface"]["version"] == "runtime-center-v1"
    assert payload["surface"]["status"] == "state-service"
    assert "bridge" not in payload

    cards = {card["key"]: card for card in payload["cards"]}
    assert cards["tasks"]["source"] == "state_query_service"
    assert cards["tasks"]["count"] == 1
    assert cards["tasks"]["entries"][0]["title"] == "Refresh competitor brief"
    assert cards["work-contexts"]["source"] == "state_query_service"
    assert cards["work-contexts"]["count"] == 1
    assert cards["work-contexts"]["entries"][0]["title"] == "Acme Pets execution core"
    assert cards["routines"]["source"] == "routine_service"
    assert cards["routines"]["count"] == 1
    routine_actions = cards["routines"]["entries"][0].get("actions") or {}
    assert "replay" not in routine_actions
    assert "goals" not in cards
    assert "schedules" not in cards
    assert cards["industry"]["source"] == "industry_service"
    assert cards["industry"]["count"] == 1
    industry_meta = cards["industry"]["entries"][0]["meta"]
    assert industry_meta["lane_count"] == 2
    assert industry_meta["backlog_count"] == 4
    assert industry_meta["cycle_count"] == 1
    assert industry_meta["assignment_count"] == 2
    assert industry_meta["report_count"] == 1
    assert industry_meta["schedule_count"] == 2
    assert "goal_count" not in industry_meta
    assert "active_goal_count" not in industry_meta
    assert cards["agents"]["source"] == "agent_profile_service"
    assert cards["agents"]["count"] == 4
    assert cards["capabilities"]["source"] == "capability_service"
    assert cards["capabilities"]["meta"]["total"] == 1
    assert cards["evidence"]["source"] == "evidence_query_service"
    assert cards["evidence"]["count"] == 1
    assert cards["decisions"]["entries"][0]["status"] == "open"
    assert cards["decisions"]["entries"][0]["actions"]["approve"] == "/api/runtime-center/decisions/decision-1/approve"
    assert cards["patches"]["source"] == "learning_service"
    assert cards["patches"]["count"] == 1
    assert (
        cards["patches"]["entries"][0]["actions"]["apply"]
        == "/api/runtime-center/learning/patches/patch-1/apply"
    )
    assert cards["growth"]["source"] == "learning_service"
    assert cards["growth"]["count"] == 1
    assert "legacy-surfaces" not in cards


def test_runtime_center_work_context_detail_endpoint() -> None:
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)
    response = client.get("/runtime-center/work-contexts/ctx-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["work_context"]["id"] == "ctx-1"
    assert payload["work_context"]["context_key"] == (
        "control-thread:industry-chat:industry-v1-ops:execution-core"
    )
    assert payload["stats"]["task_count"] == 3
    assert payload["tasks"][0]["work_context"]["id"] == "ctx-1"


def test_runtime_center_capability_optimizations_endpoint() -> None:
    app = build_runtime_center_app()
    app.state.prediction_service = FakePredictionService()

    client = TestClient(app)
    response = client.get("/runtime-center/governance/capability-optimizations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["actionable_count"] == 1
    assert payload["summary"]["retire_count"] == 1
    assert (
        payload["actionable"][0]["recommendation"]["recommendation"]["metadata"][
            "gap_kind"
        ]
        == "missing_capability"
    )
    assert (
        payload["history"][0]["recommendation"]["recommendation"]["metadata"][
            "optimization_stage"
        ]
        == "retire"
    )
    assert payload["routes"]["predictions"] == "/api/predictions"


def test_runtime_center_overview_returns_unavailable_cards_without_backing_state():
    app = build_runtime_center_app()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    client = TestClient(app)

    response = client.get("/runtime-center/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"]["status"] == "degraded"

    cards = {card["key"]: card for card in payload["cards"]}
    assert "goals" not in cards
    assert "schedules" not in cards
    assert cards["capabilities"]["status"] == "state-service"
    assert cards["capabilities"]["meta"]["total"] == 1
    for key, card in cards.items():
        if key in {"capabilities", "patches", "growth"}:
            continue
        if key == "industry":
            continue
        assert card["status"] == "unavailable"
        assert card["count"] == 0
        assert card["entries"] == []
    assert cards["patches"]["status"] == "state-service"
    assert cards["growth"]["status"] == "state-service"


def test_runtime_center_strategy_memory_lists_execution_core_strategy() -> None:
    app = build_runtime_center_app()
    app.state.strategy_memory_service = FakeStrategyMemoryService()

    client = TestClient(app)
    response = client.get(
        "/runtime-center/strategy-memory",
        params={"industry_instance_id": "industry-v1-ops"},
    )

    assert response.status_code == 200
    assert response.headers["x-copaw-runtime-surface"] == "runtime-center"
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["strategy_id"] == "strategy:industry:industry-v1-ops:copaw-agent-runner"
    assert payload[0]["title"] == "白泽执行中枢行业战略"
    assert payload[0]["scope_type"] == "industry"
    assert payload[0]["industry_instance_id"] == "industry-v1-ops"
    assert payload[0]["active_goal_titles"] == ["Launch runtime center"]
    assert all("亲自执行" not in item for item in payload[0]["direct_execution_policy"])
    assert any(
        "补位" in item or "改派" in item or "确认" in item
        for item in payload[0]["direct_execution_policy"]
    )


def test_runtime_center_overview_prefers_limited_list_reads() -> None:
    class StrictLimitedStateQueryService:
        def __init__(self) -> None:
            self.calls: list[int | None] = []

        async def list_tasks(self, limit: int | None = 5):
            self.calls.append(limit)
            assert limit == 5
            return [
                {
                    "id": "task-1",
                    "title": "Recent task only",
                    "kind": "task",
                    "status": "running",
                    "updated_at": "2026-03-09T08:00:00+00:00",
                },
            ]

    app = build_runtime_center_app()
    state_query = StrictLimitedStateQueryService()
    app.state.state_query_service = state_query
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()

    client = TestClient(app)
    response = client.get("/runtime-center/overview")

    assert response.status_code == 200
    assert state_query.calls == [5]


def test_runtime_center_chat_run_and_task_list_endpoints() -> None:
    app = build_runtime_center_app()
    app.state.turn_executor = FakeTurnExecutor()
    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)

    run_response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-task",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "登录京东后台并整理商品上架流程"}],
                },
            ],
            "agent_id": "copaw-agent-runner",
            "industry_instance_id": "industry-v1-ops",
            "industry_role_id": "execution-core",
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
        },
    )

    assert run_response.status_code == 200
    assert len(app.state.turn_executor.stream_calls) == 1
    request_payload = app.state.turn_executor.stream_calls[0]["request_payload"]
    assert getattr(request_payload, "interaction_mode", None) == "auto"

def test_runtime_center_chat_run_ignores_legacy_kernel_task_flags() -> None:
    app = build_runtime_center_app()
    turn_executor = FakeTurnExecutor()
    app.state.turn_executor = turn_executor

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        params={
            "kernel_task_id": "query:session:console:ops-user:industry-chat:industry-v1-ops:execution-core",
            "skip_kernel_admission": "true",
        },
        json={
            "id": "req-task-follow-up",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "继续执行并给我结果"}],
                },
            ],
            "session_kind": "industry-control-thread",
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
        },
    )

    assert response.status_code == 200
    assert len(turn_executor.stream_calls) == 1
    assert turn_executor.stream_calls[0]["kernel_task_id"] is None
    assert turn_executor.stream_calls[0]["skip_kernel_admission"] is False
    assert (
        getattr(turn_executor.stream_calls[0]["request_payload"], "interaction_mode", None)
        == "auto"
    )
    assert '"kernel_task_id": null' in response.text
    assert '"skip_kernel_admission": false' in response.text


def test_runtime_center_chat_run_preserves_explicit_environment_continuity_context() -> None:
    app = build_runtime_center_app()
    query_execution_service = _CapturingRouteQueryExecutionService()
    chat_service = _CapturingRouteChatService()
    session_backend = object()
    persisted_session = SessionMount(
        id="session:console:desktop-session-1",
        environment_id="env:desktop:session-1",
        channel="console",
        session_id="desktop-session-1",
        lease_status="leased",
        lease_owner="ops-agent",
        lease_token="lease-persisted",
        live_handle_ref="live:desktop:session-1",
    )

    async def _resolve_intake_contract(**_kwargs):
        return MainBrainIntakeContract(
            message_text="Continue the assigned desktop workflow.",
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
        )

    app.state.turn_executor = KernelTurnExecutor(
        session_backend=session_backend,
        environment_service=_CapturingRouteEnvironmentService(
            sessions={persisted_session.id: persisted_session},
        ),
        query_execution_service=query_execution_service,
        main_brain_chat_service=chat_service,
        main_brain_orchestrator=MainBrainOrchestrator(
            query_execution_service=query_execution_service,
            session_backend=session_backend,
            intake_contract_resolver=_resolve_intake_contract,
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-env-continuity",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "interaction_mode": "orchestrate",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "继续这个桌面会话并完成当前任务"}],
                },
            ],
                "session_kind": "industry-control-thread",
                "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
                "industry_instance_id": "industry-v1-ops",
                "environment_ref": "desktop:session-1",
                "environment_session_id": persisted_session.id,
                "continuity_token": "continuity:desktop-session-1",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(query_execution_service.calls) == 1
    assert chat_service.calls == []
    request = query_execution_service.calls[0]["request"]
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["environment_ref"] == "desktop:session-1"
    assert runtime_context["environment_session_id"] == persisted_session.id
    assert runtime_context["environment_continuity_token"] == "continuity:desktop-session-1"
    assert runtime_context["environment_continuity_source"] == "session-lease"
    assert runtime_context["environment_resume_ready"] is True
    assert runtime_context["recovery_mode"] == "resume-environment"
    assert runtime_context["recovery_reason"] == "session-lease"
    assert runtime_context["recovery_continuity_token"] == "continuity:desktop-session-1"
    assert '"resolved_interaction_mode":"orchestrate"' in response.text


def test_runtime_center_chat_run_attaches_environment_without_claiming_resume_on_session_only() -> None:
    app = build_runtime_center_app()
    query_execution_service = _CapturingRouteQueryExecutionService()
    chat_service = _CapturingRouteChatService()
    session_backend = object()

    async def _resolve_intake_contract(**_kwargs):
        return MainBrainIntakeContract(
            message_text="Continue the assigned desktop workflow.",
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
        )

    app.state.turn_executor = KernelTurnExecutor(
        session_backend=session_backend,
        query_execution_service=query_execution_service,
        main_brain_chat_service=chat_service,
        main_brain_orchestrator=MainBrainOrchestrator(
            query_execution_service=query_execution_service,
            session_backend=session_backend,
            intake_contract_resolver=_resolve_intake_contract,
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-env-attach-only",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "interaction_mode": "orchestrate",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "继续这个桌面会话并完成当前任务"}],
                },
            ],
                "session_kind": "industry-control-thread",
                "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
                "industry_instance_id": "industry-v1-ops",
                "environment_ref": "desktop:session-1",
                "environment_session_id": "session:console:desktop-session-1",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(query_execution_service.calls) == 1
    assert chat_service.calls == []
    request = query_execution_service.calls[0]["request"]
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["environment_ref"] == "desktop:session-1"
    assert runtime_context["environment_session_id"] == "session:console:desktop-session-1"
    assert runtime_context["environment_continuity_source"] == "environment-session"
    assert runtime_context["environment_resume_ready"] is False
    assert runtime_context["recovery_mode"] == "attach-environment"
    assert runtime_context["recovery_reason"] == "environment-session-without-continuity-proof"
    assert '"resolved_interaction_mode":"orchestrate"' in response.text


def test_runtime_center_chat_run_chat_only_turn_skips_orchestrator_runtime_context() -> None:
    app = build_runtime_center_app()
    query_execution_service = _CapturingRouteQueryExecutionService()
    chat_service = _CapturingRouteChatService()
    app.state.turn_executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=chat_service,
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-chat-only",
            "session_id": "sess-chat-only",
            "user_id": "ops-user",
            "channel": "console",
            "interaction_mode": "auto",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "如果继续执行会发生什么？"}],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(chat_service.calls) == 1
    assert query_execution_service.calls == []
    request = chat_service.calls[0]["request"]
    assert getattr(request, "_copaw_resolved_interaction_mode") == "chat"
    assert not hasattr(request, "_copaw_main_brain_runtime_context")
    assert '"resolved_interaction_mode":"chat"' in response.text


def test_runtime_center_chat_run_collects_requested_actions_and_enriches_media_inputs(
    tmp_path,
) -> None:
    app = build_runtime_center_app()
    turn_executor = FakeTurnExecutor()
    app.state.turn_executor = turn_executor
    media_service = _build_media_service()
    app.state.media_service = media_service

    attachment_path = tmp_path / "brief.md"
    attachment_path.write_text(
        "# 京东上架材料\n需要先登录后台，再核对库存、价格和物流模板。",
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-media-task",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "根据这份材料整理执行步骤"}],
                },
            ],
            "thread_id": "industry-chat:industry-v1-ops:execution-core",
            "industry_instance_id": "industry-v1-ops",
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
            "requested_actions": ["inspect_host", "writeback_backlog"],
            "media_inputs": [
                {
                    "source_kind": "upload",
                    "filename": attachment_path.name,
                    "storage_uri": str(attachment_path),
                    "entry_point": "chat",
                    "purpose": "chat-answer",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert len(turn_executor.stream_calls) == 1
    request_payload = turn_executor.stream_calls[0]["request_payload"]
    request_data = request_payload.model_dump(mode="python")
    assert request_data["media_inputs"] == []
    assert len(request_data["media_analysis_ids"]) == 1
    assert request_data["requested_actions"] == [
        "inspect_host",
        "writeback_backlog",
    ]
    assert getattr(request_payload, "interaction_mode", None) == "auto"

    analyses = media_service.list_analyses(
        thread_id="industry-chat:industry-v1-ops:execution-core",
        entry_point="chat",
        status="completed",
        limit=10,
    )
    assert len(analyses) == 1
    assert analyses[0].thread_id == "industry-chat:industry-v1-ops:execution-core"
    assert analyses[0].status == "completed"


def test_runtime_center_chat_run_enriches_request_from_media_inputs(tmp_path) -> None:
    app = build_runtime_center_app()
    turn_executor = FakeTurnExecutor()
    media_service = _build_media_service()
    app.state.turn_executor = turn_executor
    app.state.media_service = media_service

    attachment_path = tmp_path / "task-brief.md"
    attachment_path.write_text(
        "# 执行说明\n先整理上架流程，再输出待确认风险点。",
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-media-run",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "thread_id": "industry-chat:industry-v1-ops:execution-core",
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
            "session_kind": "industry-control-thread",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "继续执行，并结合附件输出结果"}],
                },
            ],
            "media_inputs": [
                {
                    "source_kind": "upload",
                    "filename": attachment_path.name,
                    "storage_uri": str(attachment_path),
                    "entry_point": "chat",
                    "purpose": "chat-answer",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert len(turn_executor.stream_calls) == 1

    request_payload = turn_executor.stream_calls[0]["request_payload"]
    request_data = request_payload.model_dump(mode="python")
    assert request_data["media_inputs"] == []
    assert len(request_data["media_analysis_ids"]) == 1
    assert getattr(request_payload, "interaction_mode", None) == "auto"

    message_blocks = request_data["input"][-1]["content"]
    text_blocks = [
        block["text"]
        for block in message_blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    assert any("Attached analyzed materials are available below." in block for block in text_blocks)


def test_runtime_center_chat_orchestrate_route_is_retired() -> None:
    app = build_runtime_center_app()
    turn_executor = FakeTurnExecutor()
    app.state.turn_executor = turn_executor

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/orchestrate",
        json={
            "id": "req-orchestrate",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "开始执行并给我结果"}],
                },
            ],
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
        },
    )

    assert response.status_code == 404
    assert len(turn_executor.stream_calls) == 0


def test_runtime_center_goal_dispatch_route_is_removed() -> None:
    app = build_runtime_center_app()
    client = TestClient(app)

    response = client.post(
        "/runtime-center/goals/goal-1/dispatch",
        json={"execute": True, "activate": True, "owner_agent_id": "ops-agent"},
    )

    assert response.status_code == 404


def test_runtime_center_task_review_endpoint() -> None:
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)
    response = client.get("/runtime-center/tasks/task-1/review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["review"]["headline"] == "Task is still progressing with formal writeback."
    assert payload["review"]["review_route"] == "/api/runtime-center/tasks/task-1/review"


def test_cron_exposes_runtime_center_surface_headers():
    app = FastAPI()
    app.include_router(cron_router)
    app.state.cron_manager = FakeCronManager([])

    client = TestClient(app)

    cron_response = client.get("/cron/jobs")
    assert cron_response.status_code == 200
    assert cron_response.headers["x-copaw-runtime-surface"] == "cron"
    assert cron_response.headers["x-copaw-runtime-overview"] == "/api/runtime-center/overview"


def test_runtime_center_schedule_control_endpoints() -> None:
    app = build_runtime_center_app()
    manager = FakeCronManager([make_job("sched-1")])
    app.state.cron_manager = manager
    app.state.state_query_service = FakeScheduleStateQueryService(manager)

    client = TestClient(app)

    list_response = client.get("/runtime-center/schedules")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == "sched-1"
    assert list_response.json()[0]["actions"]["delete"] == "/api/runtime-center/schedules/sched-1"

    detail_response = client.get("/runtime-center/schedules/sched-1")
    assert detail_response.status_code == 200
    assert detail_response.json()["actions"]["pause"] == "/api/runtime-center/schedules/sched-1/pause"

    pause_response = client.post("/runtime-center/schedules/sched-1/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["paused"] is True
    assert pause_response.json()["schedule"]["schedule"]["enabled"] is False
    assert "resume" in pause_response.json()["schedule"]["actions"]

    resume_response = client.post("/runtime-center/schedules/sched-1/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["resumed"] is True
    assert resume_response.json()["schedule"]["schedule"]["enabled"] is True
    assert "pause" in resume_response.json()["schedule"]["actions"]

    run_response = client.post("/runtime-center/schedules/sched-1/run")
    assert run_response.status_code == 200
    assert run_response.json()["started"] is True
    assert run_response.json()["schedule"]["runtime"]["status"] == "running"


def test_runtime_center_schedule_write_endpoints() -> None:
    app = build_runtime_center_app()
    manager = FakeCronManager([make_job("sched-1")])
    app.state.cron_manager = manager
    app.state.state_query_service = FakeScheduleStateQueryService(manager)

    client = TestClient(app)

    create_payload = make_job("sched-2").model_dump(mode="json")
    create_response = client.post("/runtime-center/schedules", json=create_payload)
    assert create_response.status_code == 200
    assert create_response.json()["created"] is True
    assert create_response.json()["schedule"]["schedule"]["id"] == "sched-2"

    duplicate_response = client.post("/runtime-center/schedules", json=create_payload)
    assert duplicate_response.status_code == 409

    update_payload = make_job("sched-2", enabled=False).model_dump(mode="json")
    update_payload["name"] = "Updated schedule"
    update_response = client.put("/runtime-center/schedules/sched-2", json=update_payload)
    assert update_response.status_code == 200
    assert update_response.json()["updated"] is True
    assert update_response.json()["schedule"]["schedule"]["title"] == "Updated schedule"
    assert update_response.json()["schedule"]["schedule"]["enabled"] is False

    mismatch_payload = make_job("sched-3").model_dump(mode="json")
    mismatch_response = client.put("/runtime-center/schedules/sched-2", json=mismatch_payload)
    assert mismatch_response.status_code == 400

    delete_response = client.delete("/runtime-center/schedules/sched-2")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    missing_response = client.get("/runtime-center/schedules/sched-2")
    assert missing_response.status_code == 404


def test_runtime_center_heartbeat_endpoints() -> None:
    app = build_runtime_center_app()
    manager = FakeCronManager(
        [],
        heartbeat_state=CronJobState(
            last_status="success",
            last_run_at=datetime(2026, 3, 9, 8, 0, tzinfo=timezone.utc),
            next_run_at=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
        ),
    )
    heartbeat_state = {
        "config": HeartbeatConfig(
            enabled=True,
            every="6h",
            target="main",
            activeHours={"start": "08:00", "end": "22:00"},
        ),
    }
    app.state.cron_manager = manager
    app.state.capability_service = FakeCapabilityService()
    app.state.kernel_dispatcher = FakeMutationDispatcher(heartbeat_state)

    def _get_heartbeat_config() -> HeartbeatConfig:
        return heartbeat_state["config"]

    client = TestClient(app)

    with patch(
        "copaw.app.routers.runtime_center.get_heartbeat_config",
        side_effect=_get_heartbeat_config,
    ):
        get_response = client.get("/runtime-center/heartbeat")
        assert get_response.status_code == 200
        assert get_response.json()["runtime"]["query_path"] == "system:run_operating_cycle"
        assert get_response.json()["actions"]["run"] == "/api/runtime-center/heartbeat/run"

        update_response = client.put(
            "/runtime-center/heartbeat",
            json={
                "enabled": True,
                "every": "4h",
                "target": "last",
                "activeHours": {"start": "09:00", "end": "18:00"},
            },
        )
        assert update_response.status_code == 200
        assert update_response.json()["updated"] is True
        assert update_response.json()["heartbeat"]["heartbeat"]["every"] == "4h"
        assert update_response.json()["heartbeat"]["heartbeat"]["target"] == "last"
        assert manager.heartbeat_rescheduled is True

        run_response = client.post("/runtime-center/heartbeat/run")
        assert run_response.status_code == 200
        assert run_response.json()["started"] is True
        assert run_response.json()["result"]["status"] == "success"
        assert run_response.json()["heartbeat"]["runtime"]["status"] == "success"


def test_runtime_center_decision_list_and_detail_endpoints() -> None:
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)

    list_response = client.get("/runtime-center/decisions")
    assert list_response.status_code == 200
    decisions = list_response.json()
    assert decisions[0]["id"] == "decision-1"
    assert decisions[0]["route"] == "/api/runtime-center/decisions/decision-1"

    detail_response = client.get("/runtime-center/decisions/decision-1")
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "open"

    missing_response = client.get("/runtime-center/decisions/missing")
    assert missing_response.status_code == 404


def test_runtime_center_agents_endpoint_supports_business_and_system_views() -> None:
    app = build_runtime_center_app()
    app.state.agent_profile_service = FakeAgentProfileService()

    client = TestClient(app)

    all_response = client.get("/runtime-center/agents")
    assert all_response.status_code == 200
    assert {item["agent_id"] for item in all_response.json()} == {
        "ops-agent",
        "copaw-agent-runner",
        "copaw-scheduler",
        "copaw-governance",
    }

    business_response = client.get("/runtime-center/agents", params={"view": "business"})
    assert business_response.status_code == 200
    assert [item["agent_id"] for item in business_response.json()] == ["ops-agent"]

    system_response = client.get("/runtime-center/agents", params={"view": "system"})
    assert system_response.status_code == 200
    assert [item["agent_id"] for item in system_response.json()] == [
        "copaw-scheduler",
        "copaw-governance",
    ]

    scoped_response = client.get(
        "/runtime-center/agents",
        params={
            "view": "business",
            "industry_instance_id": "industry-v1-ops",
        },
    )
    assert scoped_response.status_code == 200
    assert [item["agent_id"] for item in scoped_response.json()] == ["ops-agent"]


def test_runtime_center_decision_approve_and_reject_endpoints() -> None:
    app = build_runtime_center_app()
    app.state.kernel_dispatcher = FakeDecisionDispatcher()

    client = TestClient(app)

    approve_response = client.post(
        "/runtime-center/decisions/decision-1/approve",
        json={"resolution": "Approved from API", "execute": True},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["decision_request_id"] == "decision-1"
    assert approve_response.json()["phase"] == "completed"

    reject_response = client.post(
        "/runtime-center/decisions/decision-1/reject",
        json={"resolution": "Rejected from API"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["decision_request_id"] == "decision-1"
    assert reject_response.json()["phase"] == "cancelled"


def test_runtime_center_decision_approve_schedules_query_tool_resume() -> None:
    app = build_runtime_center_app()
    app.state.kernel_dispatcher = FakeDecisionDispatcher()
    app.state.decision_request_repository = FakeApproveDecisionRequestRepository(
        decision_type="query-tool-confirmation",
    )
    app.state.query_execution_service = FakeQueryExecutionService()

    scheduled: dict[str, object] = {}

    def _fake_create_task(coro, *args, **kwargs):
        scheduled["called"] = True
        scheduled["args"] = args
        scheduled["kwargs"] = kwargs
        scheduled["coroutine_name"] = getattr(getattr(coro, "cr_code", None), "co_name", None)
        coro.close()
        return SimpleNamespace()

    client = TestClient(app)

    with patch("copaw.app.routers.runtime_center.asyncio.create_task", side_effect=_fake_create_task):
        response = client.post("/runtime-center/decisions/decision-1/approve")

    assert response.status_code == 200
    assert response.json()["resume_scheduled"] is True
    assert response.json()["resume_kind"] == "query-tool-confirmation"
    assert scheduled["called"] is True
    assert scheduled["coroutine_name"] == "_resume_query_tool_confirmation_in_background"


def test_runtime_center_decision_approve_does_not_schedule_resume_for_normal_decisions() -> None:
    app = build_runtime_center_app()
    app.state.kernel_dispatcher = FakeDecisionDispatcher()
    app.state.decision_request_repository = FakeApproveDecisionRequestRepository(
        decision_type="capability-update",
    )
    app.state.query_execution_service = FakeQueryExecutionService()

    client = TestClient(app)

    with patch("copaw.app.routers.runtime_center.asyncio.create_task") as create_task:
        response = client.post("/runtime-center/decisions/decision-1/approve")

    assert response.status_code == 200
    assert "resume_scheduled" not in response.json()
    create_task.assert_not_called()


def test_runtime_center_decision_action_conflicts_map_to_http_errors() -> None:
    app = build_runtime_center_app()
    app.state.kernel_dispatcher = FakeDecisionDispatcher()

    client = TestClient(app)

    approve_response = client.post("/runtime-center/decisions/closed/approve")
    assert approve_response.status_code == 409

    reject_response = client.post("/runtime-center/decisions/closed/reject")
    assert reject_response.status_code == 409
