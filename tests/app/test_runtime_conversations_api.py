# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.runtime_threads import RuntimeThreadHistory, RuntimeThreadSpec
from copaw.kernel.models import KernelTask
from copaw.kernel.persistence import encode_kernel_task_metadata
from copaw.state import (
    AgentThreadBindingRecord,
    HumanAssistTaskRecord,
    WorkContextRecord,
)


class _FakeHistoryReader:
    def __init__(self, *, empty_thread_ids: set[str] | None = None) -> None:
        self.calls: list[RuntimeThreadSpec] = []
        self._empty_thread_ids = set(empty_thread_ids or [])

    async def get_thread_history(
        self,
        thread_spec: RuntimeThreadSpec,
    ) -> RuntimeThreadHistory:
        self.calls.append(thread_spec)
        if (
            thread_spec.id in self._empty_thread_ids
            or thread_spec.session_id in self._empty_thread_ids
        ):
            return RuntimeThreadHistory(messages=[])
        return RuntimeThreadHistory(
            messages=[
                {
                    "id": "msg-1",
                    "role": "assistant",
                    "content": [{"type": "text", "text": f"history:{thread_spec.user_id}"}],
                },
            ],
        )


class _FakeIndustryService:
    def __init__(self, *, waiting_confirm: bool = False) -> None:
        self._waiting_confirm = waiting_confirm

    def get_instance_detail(self, instance_id: str):
        if instance_id != "industry-v1-acme":
            return None
        detail = {
            "instance_id": "industry-v1-acme",
            "label": "Acme Pets",
            "owner_scope": "pets-ops",
            "goals": [{"goal_id": "goal-1"}],
            "lanes": [
                {
                    "lane_id": "lane-growth",
                    "title": "增长获客",
                    "status": "active",
                    "priority": 3,
                },
                {
                    "lane_id": "lane-fulfillment",
                    "title": "交付履约",
                    "status": "queued",
                    "priority": 2,
                },
            ],
            "backlog": [{"backlog_item_id": "backlog-1"}],
            "assignments": [],
            "team": {
                "agents": [
                    {
                        "role_id": "execution-core",
                        "agent_id": "copaw-agent-runner",
                        "name": "Execution Core",
                        "role_name": "Execution Core",
                    },
                    {
                        "role_id": "researcher",
                        "agent_id": "research-agent",
                        "name": "Researcher",
                        "role_name": "Researcher",
                    },
                ],
            },
            "staffing": {
                "active_gap": {
                    "kind": "career-seat-proposal",
                    "target_role_name": "Platform Trader",
                    "decision_request_id": "decision-seat-1",
                    "requires_confirmation": True,
                },
                "pending_proposals": [
                    {
                        "kind": "career-seat-proposal",
                        "target_role_name": "Platform Trader",
                        "decision_request_id": "decision-seat-1",
                    },
                ],
                "temporary_seats": [],
                "researcher": {
                    "role_name": "Researcher",
                    "status": "waiting-review",
                    "pending_signal_count": 2,
                },
            },
        }
        if self._waiting_confirm:
            detail["autonomy_status"] = "waiting-confirm"
            detail["current_cycle"] = {
                "status": "waiting-confirm",
                "title": "Launch the first operating cycle",
            }
        return detail


class _FakeAgentProfileService:
    def get_agent(self, agent_id: str):
        if agent_id == "copaw-agent-runner":
            return {
                "agent_id": "copaw-agent-runner",
                "name": "Execution Core",
                "role_name": "Execution Core",
                "current_focus_kind": "goal",
                "current_focus_id": "goal-execution-core",
                "current_focus": "Run weekly industry review",
                "current_goal": "Run weekly industry review",
                "industry_instance_id": "industry-v1-acme",
                "industry_role_id": "execution-core",
            }
        if agent_id == "research-agent":
            return {
                "agent_id": "research-agent",
                "name": "Research Agent",
                "role_name": "Research Lead",
                "current_focus_kind": "goal",
                "current_focus_id": "goal-research",
                "current_focus": "Prepare the next evidence digest",
                "current_goal": "Prepare the next evidence digest",
            }
        return None


class _FakeThreadBindingRepository:
    def __init__(self) -> None:
        bindings = [
            AgentThreadBindingRecord(
                thread_id="industry-chat:industry-v1-acme:execution-core",
                agent_id="copaw-agent-runner",
                session_id="industry-chat:industry-v1-acme:execution-core",
                channel="console",
                binding_kind="industry-role-alias",
                industry_instance_id="industry-v1-acme",
                industry_role_id="execution-core",
                work_context_id="ctx-acme-execution-core",
                owner_scope="pets-ops",
            ),
            AgentThreadBindingRecord(
                thread_id="agent-chat:research-agent",
                agent_id="research-agent",
                session_id="agent-chat:research-agent",
                channel="console",
                binding_kind="agent-primary",
            ),
            # Binding with normalized (lowercase) role_id to test case-insensitive lookup
            AgentThreadBindingRecord(
                thread_id="industry-chat:industry-v1-acme:marketing-manager",
                agent_id="marketing-agent",
                session_id="industry-chat:industry-v1-acme:marketing-manager",
                channel="console",
                binding_kind="industry-role-alias",
                industry_instance_id="industry-v1-acme",
                industry_role_id="marketing-manager",
                owner_scope="pets-ops",
            ),
        ]
        self._bindings = {binding.thread_id: binding for binding in bindings}

    def get_binding(self, thread_id: str):
        return self._bindings.get(thread_id)

    def list_bindings(
        self,
        *,
        agent_id: str | None = None,
        industry_instance_id: str | None = None,
        active_only: bool = False,
        limit: int | None = None,
    ):
        bindings = list(self._bindings.values())
        if agent_id is not None:
            bindings = [binding for binding in bindings if binding.agent_id == agent_id]
        if industry_instance_id is not None:
            bindings = [
                binding
                for binding in bindings
                if binding.industry_instance_id == industry_instance_id
            ]
        if active_only:
            bindings = [binding for binding in bindings if binding.active]
        if isinstance(limit, int) and limit >= 0:
            return bindings[:limit]
        return bindings


class _FakeThreadBindingRepositoryWithoutWorkContext(_FakeThreadBindingRepository):
    def __init__(self) -> None:
        super().__init__()
        thread_id = "industry-chat:industry-v1-acme:execution-core"
        binding = self._bindings[thread_id]
        self._bindings[thread_id] = binding.model_copy(update={"work_context_id": None})


class _FakeTaskRepository:
    def __init__(self) -> None:
        task = KernelTask(
            id="query:session:console:ops-user:industry-chat:industry-v1-acme:execution-core",
            title="闁圭瑳鍡╂斀濞寸姾顕ф慨鐔兼晬濮橆厼鑵归弶鈺傜☉鐏忎即鎮垮Δ鈧幐鈺冩嫚閵忕姵绀嬮梻鍐枔濞堟垹绮旀担鍝ュ幍閺夆晜鍔橀幆鈧悹浣测偓鍐茬亰",
            capability_ref="system:dispatch_query",
            owner_agent_id="copaw-agent-runner",
            work_context_id="ctx-acme-execution-core",
            payload={
                "request": {
                    "session_id": "industry-chat:industry-v1-acme:execution-core",
                    "user_id": "ops-user",
                    "channel": "console",
                    "agent_id": "copaw-agent-runner",
                    "agent_name": "Execution Core",
                    "industry_instance_id": "industry-v1-acme",
                    "industry_label": "Acme Pets",
                    "industry_role_id": "execution-core",
                    "industry_role_name": "Execution Core",
                    "owner_scope": "pets-ops",
                    "control_thread_id": "industry-chat:industry-v1-acme:execution-core",
                    "task_title": "闁圭瑳鍡╂斀濞寸姾顕ф慨鐔兼晬濮橆厼鑵归弶鈺傜☉鐏忎即鎮垮Δ鈧幐鈺冩嫚閵忕姵绀嬮梻鍐枔濞堟垹绮旀担鍝ュ幍閺夆晜鍔橀幆鈧悹浣测偓鍐茬亰",
                },
                "meta": {
                    "task_title": "闁圭瑳鍡╂斀濞寸姾顕ф慨鐔兼晬濮橆厼鑵归弶鈺傜☉鐏忎即鎮垮Δ鈧幐鈺冩嫚閵忕姵绀嬮梻鍐枔濞堟垹绮旀担鍝ュ幍閺夆晜鍔橀幆鈧悹浣测偓鍐茬亰",
                    "control_thread_id": "industry-chat:industry-v1-acme:execution-core",
                },
            },
        )
        self._tasks = {
            task.id: SimpleTaskRecord(
                id=task.id,
                title=task.title,
                status="running",
                owner_agent_id=task.owner_agent_id,
                work_context_id=task.work_context_id,
                acceptance_criteria=encode_kernel_task_metadata(task),
            ),
        }

    def get_task(self, task_id: str):
        return self._tasks.get(task_id)


class _FakeTaskRepositoryWithoutFormalContext(_FakeTaskRepository):
    def __init__(self) -> None:
        task = KernelTask(
            id="query:session:console:ops-user:industry-chat:industry-v1-acme:execution-core",
            title="闂佸湱鐟抽崱鈺傛杸婵炲濮鹃褎鎱ㄩ悢鍏兼櫖婵﹩鍓欏☉褔鏌￠崼婵愭Ш闁搞倕娴风划娆戔偓锝傛櫇缁嬬粯绻涚仦绋垮⒉婵犫偓娴ｅ壊娼伴柨婵嗘噽绾偓 WorkContext",
            capability_ref="system:dispatch_query",
            owner_agent_id="copaw-agent-runner",
            payload={
                "request": {
                    "session_id": "industry-chat:industry-v1-acme:execution-core",
                    "user_id": "ops-user",
                    "channel": "console",
                    "agent_id": "copaw-agent-runner",
                    "agent_name": "Execution Core",
                    "industry_instance_id": "industry-v1-acme",
                    "industry_role_id": "execution-core",
                    "control_thread_id": "industry-chat:industry-v1-acme:execution-core",
                    "task_title": "闂佸湱鐟抽崱鈺傛杸婵炲濮鹃褎鎱ㄩ悢鍏兼櫖婵﹩鍓欏☉褔鏌￠崼婵愭Ш闁搞倕娴风划娆戔偓锝傛櫇缁嬬粯绻涚仦绋垮⒉婵犫偓娴ｅ壊娼伴柨婵嗘噽绾偓 WorkContext",
                },
                "meta": {
                    "task_title": "闂佸湱鐟抽崱鈺傛杸婵炲濮鹃褎鎱ㄩ悢鍏兼櫖婵﹩鍓欏☉褔鏌￠崼婵愭Ш闁搞倕娴风划娆戔偓锝傛櫇缁嬬粯绻涚仦绋垮⒉婵犫偓娴ｅ壊娼伴柨婵嗘噽绾偓 WorkContext",
                    "control_thread_id": "industry-chat:industry-v1-acme:execution-core",
                },
            },
        )
        self._tasks = {
            task.id: SimpleTaskRecord(
                id=task.id,
                title=task.title,
                status="running",
                owner_agent_id=task.owner_agent_id,
                work_context_id=None,
                acceptance_criteria=encode_kernel_task_metadata(task),
            ),
        }


class SimpleTaskRecord:
    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeTaskRuntimeRepository:
    def get_runtime(self, task_id: str):
        if task_id != "query:session:console:ops-user:industry-chat:industry-v1-acme:execution-core":
            return None
        return SimpleTaskRecord(runtime_status="running")


class _FakeWorkContextRepository:
    def __init__(self) -> None:
        self._contexts = {
            "ctx-acme-execution-core": WorkContextRecord(
                id="ctx-acme-execution-core",
                title="Acme Pets execution core",
                summary="Primary work boundary for the execution core control thread.",
                context_type="industry-control-thread",
                status="active",
                context_key="control-thread:industry-chat:industry-v1-acme:execution-core",
                owner_scope="pets-ops",
                owner_agent_id="copaw-agent-runner",
                industry_instance_id="industry-v1-acme",
                primary_thread_id="industry-chat:industry-v1-acme:execution-core",
            ),
        }

    def get_context(self, context_id: str):
        return self._contexts.get(context_id)

    def get_by_context_key(self, context_key: str):
        for record in self._contexts.values():
            if record.context_key == context_key:
                return record
        return None


class _FakeHumanAssistTaskService:
    def get_current_task(self, *, chat_thread_id: str):
        if chat_thread_id != "industry-chat:industry-v1-acme:execution-core":
            return None
        return HumanAssistTaskRecord(
            id="human-assist:task-1",
            industry_instance_id="industry-v1-acme",
            assignment_id="assignment-1",
            task_id="task-1",
            chat_thread_id=chat_thread_id,
            title="Upload receipt proof",
            summary="Host proof is required before resume.",
            task_type="evidence-submit",
            reason_code="blocked-by-proof",
            reason_summary="Payment receipt still needs host confirmation.",
            required_action="Upload the receipt in chat and say it is finished.",
            submission_mode="chat-message",
            acceptance_mode="evidence_verified",
            acceptance_spec={
                "version": "v1",
                "hard_anchors": ["receipt"],
                "result_anchors": ["uploaded"],
            },
            status="issued",
        )


def _build_app(
    *,
    history_reader: _FakeHistoryReader | None = None,
    industry_service: _FakeIndustryService | None = None,
    human_assist_task_service: object | None = None,
    thread_binding_repository: object | None = None,
    task_repository: object | None = None,
    work_context_repository: object | None = None,
) -> tuple[FastAPI, _FakeHistoryReader]:
    app = FastAPI()
    app.include_router(runtime_center_router)
    history_reader = history_reader or _FakeHistoryReader()
    app.state.runtime_thread_history_reader = history_reader
    app.state.industry_service = industry_service or _FakeIndustryService()
    app.state.agent_profile_service = _FakeAgentProfileService()
    app.state.agent_thread_binding_repository = (
        thread_binding_repository or _FakeThreadBindingRepository()
    )
    app.state.task_repository = task_repository or _FakeTaskRepository()
    app.state.task_runtime_repository = _FakeTaskRuntimeRepository()
    app.state.work_context_repository = work_context_repository or _FakeWorkContextRepository()
    app.state.human_assist_task_service = human_assist_task_service
    return app, history_reader


def test_runtime_conversation_detail_resolves_industry_thread() -> None:
    app, history_reader = _build_app()
    client = TestClient(app)

    response = client.get(
        "/runtime-center/conversations/industry-chat:industry-v1-acme:execution-core",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "industry-chat:industry-v1-acme:execution-core"
    assert payload["session_id"] == "industry-chat:industry-v1-acme:execution-core"
    assert payload["user_id"] == "copaw-agent-runner"
    assert payload["name"] == "Acme Pets - Execution Core"
    assert payload["meta"]["session_kind"] == "industry-control-thread"
    assert payload["meta"]["entry_source"] == "industry"
    assert payload["meta"]["current_focus_kind"] == "goal"
    assert payload["meta"]["current_focus_id"] == "goal-execution-core"
    assert payload["meta"]["current_focus"] == "Run weekly industry review"
    assert "current_goal" not in payload["meta"]
    assert payload["meta"]["context_key"] == "control-thread:industry-chat:industry-v1-acme:execution-core"
    assert payload["meta"]["work_context_id"] == "ctx-acme-execution-core"
    assert payload["meta"]["work_context"]["title"] == "Acme Pets execution core"
    assert payload["messages"][0]["content"][0]["text"] == "history:copaw-agent-runner"
    assert history_reader.calls[0].session_id == "industry-chat:industry-v1-acme:execution-core"
    assert history_reader.calls[0].user_id == "copaw-agent-runner"


def test_runtime_conversation_detail_exposes_current_human_assist_task_meta() -> None:
    app, _history_reader = _build_app(
        human_assist_task_service=_FakeHumanAssistTaskService(),
    )
    client = TestClient(app)

    response = client.get(
        "/runtime-center/conversations/industry-chat:industry-v1-acme:execution-core",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["human_assist_task"]["id"] == "human-assist:task-1"
    assert payload["meta"]["human_assist_task"]["status"] == "issued"
    assert (
        payload["meta"]["human_assist_tasks_route"]
        == "/api/runtime-center/human-assist-tasks?chat_thread_id=industry-chat%3Aindustry-v1-acme%3Aexecution-core"
    )


def test_runtime_conversation_detail_keeps_meta_surface_lightweight() -> None:
    app, _history_reader = _build_app(
        human_assist_task_service=_FakeHumanAssistTaskService(),
    )
    client = TestClient(app)

    response = client.get(
        "/runtime-center/conversations/industry-chat:industry-v1-acme:execution-core",
    )

    assert response.status_code == 200
    payload = response.json()
    meta = payload["meta"]
    disallowed_meta_keys = {
        "main_brain_chat_state",
        "main_brain_chat_snapshot",
        "chat_session_state",
        "conversation_history",
        "history_messages",
        "prompt_context",
        "prompt_cache",
    }
    assert disallowed_meta_keys.isdisjoint(meta.keys())
    # Guardrail: keep conversation metadata compact to avoid chat-chain bloat.
    assert len(meta) <= 24

    human_assist_task_meta = meta["human_assist_task"]
    assert human_assist_task_meta["chat_thread_id"] == payload["id"]
    assert "main_brain_runtime" not in human_assist_task_meta
    assert "conversation_history" not in human_assist_task_meta
    # Guardrail: task summary payload should stay bounded.
    assert len(human_assist_task_meta) <= 36


def test_runtime_conversation_detail_omits_human_assist_meta_when_current_task_is_resume_queued() -> None:
    class _ResumeQueuedHumanAssistTaskService:
        def get_current_task(self, *, chat_thread_id: str):
            del chat_thread_id
            return None

    app, _history_reader = _build_app(
        human_assist_task_service=_ResumeQueuedHumanAssistTaskService(),
    )
    client = TestClient(app)

    response = client.get(
        "/runtime-center/conversations/industry-chat:industry-v1-acme:execution-core",
    )

    assert response.status_code == 200
    payload = response.json()
    assert "human_assist_task" not in payload["meta"]
    assert "human_assist_tasks_route" not in payload["meta"]


def test_runtime_conversation_detail_injects_waiting_confirm_kickoff_prompt() -> None:
    thread_id = "industry-chat:industry-v1-acme:execution-core"
    app, history_reader = _build_app(
        history_reader=_FakeHistoryReader(empty_thread_ids={thread_id}),
        industry_service=_FakeIndustryService(waiting_confirm=True),
    )
    client = TestClient(app)

    response = client.get(f"/runtime-center/conversations/{thread_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == thread_id
    assert payload["messages"][0]["metadata"]["synthetic"] is True
    assert payload["messages"][0]["metadata"]["message_kind"] == "industry-kickoff-prompt"
    text = payload["messages"][0]["content"][0]["text"]
    assert text
    assert "Acme Pets" in text
    assert "当前待编排：goal" not in text
    assert "当前待编排：lane 2 / backlog 1 / cycle 1 / assignment 0 / report 0。" in text
    assert "当前 lane：增长获客、交付履约。" in text
    assert history_reader.calls[0].session_id == thread_id


def test_runtime_conversation_detail_kickoff_prompt_mentions_staffing_gap_and_researcher() -> None:
    thread_id = "industry-chat:industry-v1-acme:execution-core"
    app, history_reader = _build_app(
        history_reader=_FakeHistoryReader(empty_thread_ids={thread_id}),
        industry_service=_FakeIndustryService(waiting_confirm=True),
    )
    client = TestClient(app)

    response = client.get(f"/runtime-center/conversations/{thread_id}")

    assert response.status_code == 200
    payload = response.json()
    text = payload["messages"][0]["content"][0]["text"]
    assert "Platform Trader" in text
    assert "decision-seat-1" in text
    assert "Researcher" in text
    assert history_reader.calls[0].session_id == thread_id


def test_runtime_conversation_detail_kickoff_prompt_mentions_pending_proposals_and_temporary_seats() -> None:
    class _RichKickoffIndustryService(_FakeIndustryService):
        def get_instance_detail(self, instance_id: str):
            detail = super().get_instance_detail(instance_id)
            if detail is None:
                return None
            staffing = detail["staffing"]
            staffing["pending_proposals"] = [
                *list(staffing.get("pending_proposals") or []),
                {
                    "kind": "temporary-seat-proposal",
                    "target_role_name": "Browser QA Seat",
                    "decision_request_id": "decision-seat-2",
                },
            ]
            staffing["temporary_seats"] = [
                {
                    "role_id": "temporary-browser-runner",
                    "role_name": "Temporary Browser Runner",
                },
            ]
            return detail

    thread_id = "industry-chat:industry-v1-acme:execution-core"
    app, _history_reader = _build_app(
        history_reader=_FakeHistoryReader(empty_thread_ids={thread_id}),
        industry_service=_RichKickoffIndustryService(waiting_confirm=True),
    )
    client = TestClient(app)

    response = client.get(f"/runtime-center/conversations/{thread_id}")

    assert response.status_code == 200
    text = response.json()["messages"][0]["content"][0]["text"]
    assert "待确认 proposals" in text
    assert "Browser QA Seat" in text
    assert "Temporary Browser Runner" in text


def test_runtime_conversation_detail_rejects_retired_agent_thread_frontdoor() -> None:
    app, history_reader = _build_app()
    client = TestClient(app)

    response = client.get("/runtime-center/conversations/agent-chat:research-agent")

    assert response.status_code == 400
    assert "/chat" in response.json()["detail"]
    assert history_reader.calls == []


def test_runtime_conversation_detail_rejects_execution_core_agent_thread_frontdoor() -> None:
    app, history_reader = _build_app()
    client = TestClient(app)

    response = client.get("/runtime-center/conversations/agent-chat:copaw-agent-runner")

    assert response.status_code == 400
    assert "industry-chat:industry-v1-acme:execution-core" in response.json()["detail"]
    assert history_reader.calls == []


def test_runtime_conversation_detail_rejects_legacy_actor_thread_ids() -> None:
    app, history_reader = _build_app()
    client = TestClient(app)

    response = client.get("/runtime-center/conversations/actor-chat:research-agent")

    assert response.status_code == 400
    assert "industry-chat" in response.json()["detail"]
    assert history_reader.calls == []


def test_runtime_conversation_detail_rejects_task_thread_ids() -> None:
    app, history_reader = _build_app()
    client = TestClient(app)

    response = client.get(
        "/runtime-center/conversations/task-chat:query:session:console:ops-user:task-session:req-task",
    )

    assert response.status_code == 400
    assert response.json()["detail"]
    assert history_reader.calls == []


def test_runtime_conversation_detail_infers_bound_context_from_control_thread() -> None:
    app, _history_reader = _build_app(
        thread_binding_repository=_FakeThreadBindingRepositoryWithoutWorkContext(),
    )
    client = TestClient(app)

    response = client.get(
        "/runtime-center/conversations/industry-chat:industry-v1-acme:execution-core",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["work_context_id"] == "ctx-acme-execution-core"
    assert payload["meta"]["context_key"] == (
        "control-thread:industry-chat:industry-v1-acme:execution-core"
    )
    assert payload["meta"]["work_context"]["id"] == "ctx-acme-execution-core"


def test_runtime_conversation_detail_rejects_legacy_chat_shell_ids() -> None:
    app, _history_reader = _build_app()
    client = TestClient(app)

    response = client.get("/runtime-center/conversations/chat-legacy-shell")

    assert response.status_code == 400
    assert response.json()["detail"]


def test_runtime_conversation_detail_rejects_legacy_industry_thread_ids() -> None:
    app, _history_reader = _build_app()
    client = TestClient(app)

    response = client.get("/runtime-center/conversations/industry:industry-v1-acme:manager")

    assert response.status_code == 400
    assert response.json()["detail"]


def test_runtime_conversation_detail_rejects_unknown_industry_chat_role_ids() -> None:
    app, _history_reader = _build_app()
    client = TestClient(app)

    response = client.get("/runtime-center/conversations/industry-chat:industry-v1-acme:manager")

    assert response.status_code == 404
    assert response.json()["detail"]


def test_runtime_conversation_detail_rejects_missing_agent_thread_ids() -> None:
    app, _history_reader = _build_app()
    client = TestClient(app)

    response = client.get("/runtime-center/conversations/agent-chat:missing-actor")

    assert response.status_code == 400
    assert "/chat" in response.json()["detail"]


def test_runtime_conversation_detail_resolves_case_mismatched_industry_thread() -> None:
    """Test that industry-chat threads with case-mismatched role_id are resolved.

    This tests the fix for the '閻犲洢鍎抽崵搴ｇ矙鐎ｎ亜鍤掑璺哄船楠炴挾绱掗幋婵堟毎' error where the frontend sends
    a role_id with different case than what's stored in the binding repository.
    For example, frontend sends 'Marketing-Manager' but binding has 'marketing-manager'.
    """
    app, history_reader = _build_app()
    client = TestClient(app)

    # Request with mixed-case role_id, but binding has lowercase 'marketing-manager'
    response = client.get(
        "/runtime-center/conversations/industry-chat:industry-v1-acme:Marketing-Manager",
    )

    assert response.status_code == 200
    payload = response.json()
    # Should resolve to the normalized binding
    assert payload["id"] == "industry-chat:industry-v1-acme:marketing-manager"
    assert payload["session_id"] == "industry-chat:industry-v1-acme:marketing-manager"
    assert payload["user_id"] == "marketing-agent"
