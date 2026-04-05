# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from agentscope.message import Msg
from fastapi.testclient import TestClient

from copaw.evidence import EvidenceRecord
from copaw.industry.chat_writeback import build_chat_writeback_plan
from copaw.kernel import KernelTurnExecutor
from copaw.kernel.main_brain_chat_service import MainBrainChatService
from copaw.kernel.main_brain_intake import MainBrainIntakeContract
from copaw.kernel.main_brain_orchestrator import MainBrainOrchestrator
from copaw.sop_kernel import FixedSopBindingCreateRequest
from copaw.state import AgentReportRecord

from .industry_api_parts.shared import _build_industry_app


class _StaticResponseModel:
    def __init__(self, text: str) -> None:
        self.text = text
        self.stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        return SimpleNamespace(content=self.text)


class _CanonicalFlowQueryExecutionService:
    def __init__(
        self,
        *,
        chat_service: MainBrainChatService,
        industry_service: object,
    ) -> None:
        self._chat_service = chat_service
        self._industry_service = industry_service
        self.calls: list[dict[str, object]] = []
        self.writeback_result: dict[str, object] | None = None

    def set_session_backend(self, session_backend) -> None:
        self._chat_service.set_session_backend(session_backend)

    def set_kernel_dispatcher(self, kernel_dispatcher) -> None:
        _ = kernel_dispatcher

    def resolve_request_owner_agent_id(self, *, request) -> str | None:
        return getattr(request, "agent_id", None) or "copaw-agent-runner"

    async def execute_stream(self, **kwargs):
        msgs = list(kwargs.get("msgs") or [])
        request = kwargs["request"]
        self.calls.append({"request": request, "msgs": msgs})

        buffered = [
            item async for item in self._chat_service.execute_stream(msgs=msgs, request=request)
        ]

        intake_contract = getattr(request, "_copaw_main_brain_intake_contract", None)
        if intake_contract is not None and intake_contract.writeback_requested:
            self.writeback_result = await self._industry_service.apply_execution_chat_writeback(
                industry_instance_id=request.industry_instance_id,
                message_text=intake_contract.message_text,
                owner_agent_id=getattr(request, "agent_id", None) or "copaw-agent-runner",
                session_id=request.session_id,
                channel=request.channel,
                writeback_plan=intake_contract.writeback_plan,
            )

        if buffered:
            for index, (message, _last) in enumerate(buffered):
                yield message, index == len(buffered) - 1
            return

        yield Msg(name="assistant", role="assistant", content="Recorded."), True


def _message_text(message: dict[str, object]) -> str:
    content = message.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _flatten_memory_messages(memory_state: object) -> list[dict[str, object]]:
    if isinstance(memory_state, dict):
        content = memory_state.get("content") or []
    elif isinstance(memory_state, list):
        content = memory_state
    else:
        content = []

    flattened: list[dict[str, object]] = []
    for item in content:
        if isinstance(item, dict):
            flattened.append(item)
            continue
        if isinstance(item, list) and item:
            first = item[0]
            if isinstance(first, dict):
                flattened.append(first)
    return flattened


def test_runtime_canonical_flow_covers_identity_chat_execution_and_runtime_reads(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)

    instruction = (
        "Please publish the customer notice in the browser, update the desktop tracker, "
        "and report back on the same control thread."
    )
    control_ack = "Recorded. I will write this into the runtime chain and prepare the next move."
    environment_ref = "session:console:industry-control"

    chat_service = MainBrainChatService(
        session_backend=app.state.session_backend,
        industry_service=app.state.industry_service,
        agent_profile_service=app.state.agent_profile_service,
        model_factory=lambda: _StaticResponseModel(control_ack),
    )
    query_execution_service = _CanonicalFlowQueryExecutionService(
        chat_service=chat_service,
        industry_service=app.state.industry_service,
    )

    async def _resolve_intake_contract(**_kwargs):
        return MainBrainIntakeContract(
            message_text=instruction,
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=False),
            intent_kind="execute-task",
            writeback_requested=True,
            writeback_plan=build_chat_writeback_plan(
                instruction,
                approved_classifications=["backlog"],
                goal_title="Customer notice publish handoff",
                goal_summary="Publish the customer notice with governed browser and desktop follow-up.",
                goal_plan_steps=[
                    "Prepare the governed browser and desktop execution scope.",
                    "Require approval before any external action.",
                    "Write back the result and evidence on the same control thread.",
                ],
            ),
            should_kickoff=False,
        )

    app.state.turn_executor = KernelTurnExecutor(
        session_backend=app.state.session_backend,
        query_execution_service=query_execution_service,
        main_brain_chat_service=chat_service,
        main_brain_orchestrator=MainBrainOrchestrator(
            query_execution_service=query_execution_service,
            session_backend=app.state.session_backend,
            intake_contract_resolver=_resolve_intake_contract,
        ),
    )

    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Field Operations",
            "company_name": "Northwind Robotics",
            "product": "inspection orchestration",
            "goals": ["keep one canonical operator loop"],
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()

    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": preview_payload["draft"],
            "auto_activate": True,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    execution_binding = app.state.agent_thread_binding_repository.get_binding(control_thread_id)
    assert execution_binding is not None
    assert execution_binding.work_context_id is not None
    work_context_id = execution_binding.work_context_id

    chat_response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-canonical-flow",
            "session_id": control_thread_id,
            "thread_id": control_thread_id,
            "user_id": "copaw-agent-runner",
            "channel": "console",
            "agent_id": "copaw-agent-runner",
            "industry_instance_id": instance_id,
            "industry_role_id": "execution-core",
            "session_kind": "industry-control-thread",
            "control_thread_id": control_thread_id,
            "interaction_mode": "orchestrate",
            "requested_actions": ["writeback_backlog"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": instruction}],
                }
            ],
        },
    )

    assert chat_response.status_code == 200
    assert chat_response.headers["content-type"].startswith("text/event-stream")
    assert len(query_execution_service.calls) == 1
    assert query_execution_service.writeback_result is not None

    writeback = query_execution_service.writeback_result
    decision_id = str(writeback["decision_request_id"])
    backlog_id = str(writeback["created_backlog_ids"][0])

    conversation = client.get(f"/runtime-center/conversations/{control_thread_id}")
    assert conversation.status_code == 200
    conversation_payload = conversation.json()
    assert conversation_payload["id"] == control_thread_id
    assert conversation_payload["meta"]["control_thread_id"] == control_thread_id
    assert conversation_payload["meta"]["work_context_id"] == work_context_id
    message_texts = [_message_text(message) for message in conversation_payload["messages"]]
    assert any(instruction in text for text in message_texts)
    assert any(control_ack in text for text in message_texts)

    approved = client.post(
        f"/runtime-center/decisions/{decision_id}/approve",
        json={"resolution": "Approved for the canonical flow test.", "execute": True},
    )
    assert approved.status_code == 200

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:canonical-flow-cycle",
            force=True,
            backlog_item_ids=[backlog_id],
            auto_dispatch_materialized_goals=False,
        ),
    )
    assignment_id = cycle_result["processed_instances"][0]["created_assignment_ids"][0]
    cycle_id = cycle_result["processed_instances"][0]["started_cycle_id"]
    assignment = app.state.assignment_repository.get_assignment(assignment_id)
    assert assignment is not None

    evidence = app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id=assignment_id,
            actor_ref="copaw-agent-runner",
            capability_ref="system:dispatch_query",
            risk_level="guarded",
            action_summary="Canonical flow operator execution",
            result_summary="Prepared the governed browser and desktop follow-up.",
            metadata={
                "industry_instance_id": instance_id,
                "control_thread_id": control_thread_id,
                "assignment_id": assignment_id,
            },
        ),
    )

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_id,
        owner_agent_id=assignment.owner_agent_id,
        owner_role_id=assignment.owner_role_id,
        headline="Customer notice publish still needs same-thread follow-up",
        summary="The browser and desktop work reached the checkpoint, but the publish still needs main-brain follow-up.",
        status="recorded",
        result="failed",
        findings=["The governed publish step still requires same-thread confirmation."],
        recommendation="Re-open the follow-up backlog on the same control thread.",
        evidence_ids=[evidence.id],
        work_context_id=work_context_id,
        metadata={
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "environment_ref": environment_ref,
            "evidence_id": evidence.id,
        },
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    second_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:canonical-flow-replan",
            force=True,
        ),
    )
    assert report.id in second_cycle["processed_instances"][0]["processed_report_ids"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == report.id
    )

    snapshot = app.state.session_backend.load_session_snapshot(
        session_id=control_thread_id,
        user_id="copaw-agent-runner",
        allow_not_exist=True,
    )
    assert snapshot is not None
    memory_messages = _flatten_memory_messages(snapshot["agent"]["memory"])
    report_message = next(
        message
        for message in memory_messages
        if message.get("id") == f"agent-report:{report.id}"
    )
    assert report_message["metadata"]["message_kind"] == "agent-report-writeback"
    assert report_message["metadata"]["control_thread_id"] == control_thread_id
    assert report_message["metadata"]["work_context_id"] == work_context_id

    runtime_detail = client.get(f"/runtime-center/industry/{instance_id}")
    assert runtime_detail.status_code == 200
    runtime_payload = runtime_detail.json()
    assert runtime_payload["execution"]["current_focus_id"] is None
    assert runtime_payload["main_chain"]["current_focus_id"] is None
    assert runtime_payload["execution"]["current_focus"] is None
    assert runtime_payload["main_chain"]["current_focus"] is None
    assert followup_backlog["metadata"]["work_context_id"] == work_context_id

    main_brain = client.get("/runtime-center/surface")
    assert main_brain.status_code == 200
    main_brain_payload = main_brain.json()["main_brain"]
    assert main_brain_payload["carrier"]["industry_instance_id"] == instance_id
    assert main_brain_payload["meta"]["industry_instance_id"] == instance_id
    assert main_brain_payload["assignments"]
    assert main_brain_payload["reports"]

    overview = client.get("/runtime-center/surface")
    assert overview.status_code == 200
    cards = {card["key"]: card for card in overview.json()["cards"]}
    assert cards["industry"]["count"] >= 1
    assert cards["main-brain"]["count"] == 1
    assert cards["decisions"]["count"] >= 1
    assert cards["evidence"]["count"] >= 1

    evidence_list = client.get("/runtime-center/evidence")
    assert evidence_list.status_code == 200
    evidence_ids = {item["id"] for item in evidence_list.json()}
    assert evidence.id in evidence_ids


def test_runtime_canonical_flow_auto_writeback_requested_actions_still_closes_real_frontdoor(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)

    instruction = "Please turn this into the governed execution backlog and keep the same control thread."
    control_ack = "Recorded. I will move this into the governed execution chain."

    chat_service = MainBrainChatService(
        session_backend=app.state.session_backend,
        industry_service=app.state.industry_service,
        agent_profile_service=app.state.agent_profile_service,
        model_factory=lambda: _StaticResponseModel(control_ack),
    )
    query_execution_service = _CanonicalFlowQueryExecutionService(
        chat_service=chat_service,
        industry_service=app.state.industry_service,
    )

    async def _resolve_intake_contract(**_kwargs):
        return MainBrainIntakeContract(
            message_text=instruction,
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=False),
            intent_kind="execute-task",
            writeback_requested=True,
            writeback_plan=build_chat_writeback_plan(
                instruction,
                approved_classifications=["backlog"],
                goal_title="Governed execution backlog handoff",
                goal_summary="Carry the requested work into the governed execution backlog on the same control thread.",
                goal_plan_steps=[
                    "Normalize the operator request into a governed execution backlog item.",
                    "Keep the same control thread and execution-core ownership.",
                    "Return the writeback result and next step.",
                ],
            ),
            should_kickoff=False,
        )

    app.state.turn_executor = KernelTurnExecutor(
        session_backend=app.state.session_backend,
        query_execution_service=query_execution_service,
        main_brain_chat_service=chat_service,
        main_brain_orchestrator=MainBrainOrchestrator(
            query_execution_service=query_execution_service,
            session_backend=app.state.session_backend,
            intake_contract_resolver=_resolve_intake_contract,
        ),
    )

    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "governed execution backlog",
            "goals": ["keep one canonical execution ingress"],
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()

    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": preview_payload["draft"],
            "auto_activate": True,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    control_thread_id = f"industry-chat:{instance_id}:execution-core"

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-canonical-flow-auto-writeback",
            "session_id": control_thread_id,
            "thread_id": control_thread_id,
            "user_id": "copaw-agent-runner",
            "channel": "console",
            "agent_id": "copaw-agent-runner",
            "industry_instance_id": instance_id,
            "industry_role_id": "execution-core",
            "session_kind": "industry-control-thread",
            "control_thread_id": control_thread_id,
            "interaction_mode": "auto",
            "requested_actions": ["writeback_backlog"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": instruction}],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(query_execution_service.calls) == 1
    routed_request = query_execution_service.calls[0]["request"]
    assert getattr(routed_request, "_copaw_resolved_interaction_mode") == "orchestrate"
    assert query_execution_service.writeback_result is not None

    writeback = query_execution_service.writeback_result
    assert writeback["created_backlog_ids"]
    backlog_id = str(writeback["created_backlog_ids"][0])

    detail = client.get(f"/runtime-center/industry/{instance_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    backlog_item = next(
        item
        for item in detail_payload["backlog"]
        if item["backlog_item_id"] == backlog_id
    )
    assert backlog_item["metadata"]["control_thread_id"] == control_thread_id
    assert backlog_item["metadata"]["source"] == "chat-writeback"


def test_runtime_canonical_flow_auto_frontdoor_replan_materializes_followup_assignment_on_same_thread(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)

    instruction = (
        "Please turn this into a governed execution chain, keep the same control thread, "
        "and carry any follow-up on the same thread as well."
    )
    control_ack = "Recorded. I will keep this on the governed execution chain."

    chat_service = MainBrainChatService(
        session_backend=app.state.session_backend,
        industry_service=app.state.industry_service,
        agent_profile_service=app.state.agent_profile_service,
        model_factory=lambda: _StaticResponseModel(control_ack),
    )
    query_execution_service = _CanonicalFlowQueryExecutionService(
        chat_service=chat_service,
        industry_service=app.state.industry_service,
    )

    async def _resolve_intake_contract(**_kwargs):
        return MainBrainIntakeContract(
            message_text=instruction,
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=False),
            intent_kind="execute-task",
            writeback_requested=True,
            writeback_plan=build_chat_writeback_plan(
                instruction,
                approved_classifications=["backlog"],
                goal_title="Canonical follow-up continuity handoff",
                goal_summary="Keep the entire governed execution and follow-up chain on one control thread.",
                goal_plan_steps=[
                    "Write this into the governed execution backlog.",
                    "Carry report follow-up on the same control thread and work context.",
                    "Materialize the next assignment without dropping continuity.",
                ],
            ),
            should_kickoff=False,
        )

    app.state.turn_executor = KernelTurnExecutor(
        session_backend=app.state.session_backend,
        query_execution_service=query_execution_service,
        main_brain_chat_service=chat_service,
        main_brain_orchestrator=MainBrainOrchestrator(
            query_execution_service=query_execution_service,
            session_backend=app.state.session_backend,
            intake_contract_resolver=_resolve_intake_contract,
        ),
    )

    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "guided customer follow-up",
        },
    )
    assert preview.status_code == 200
    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview.json()["profile"],
            "draft": preview.json()["draft"],
            "auto_activate": True,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    binding = app.state.agent_thread_binding_repository.get_binding(control_thread_id)
    assert binding is not None
    work_context_id = binding.work_context_id
    assert work_context_id is not None

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-auto-followup-continuity",
            "session_id": control_thread_id,
            "thread_id": control_thread_id,
            "user_id": "copaw-agent-runner",
            "channel": "console",
            "agent_id": "copaw-agent-runner",
            "industry_instance_id": instance_id,
            "industry_role_id": "execution-core",
            "session_kind": "industry-control-thread",
            "control_thread_id": control_thread_id,
            "interaction_mode": "auto",
            "requested_actions": ["writeback_backlog"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": instruction}],
                }
            ],
        },
    )
    assert response.status_code == 200
    assert query_execution_service.writeback_result is not None

    writeback = query_execution_service.writeback_result
    initial_backlog_id = str(writeback["created_backlog_ids"][0])

    first_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:auto-frontdoor-cycle",
            force=True,
            backlog_item_ids=[initial_backlog_id],
            auto_dispatch_materialized_goals=False,
        ),
    )
    first_assignment_id = first_cycle["processed_instances"][0]["created_assignment_ids"][0]
    cycle_id = first_cycle["processed_instances"][0]["started_cycle_id"]
    first_assignment = app.state.assignment_repository.get_assignment(first_assignment_id)
    assert first_assignment is not None

    evidence = app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id=first_assignment_id,
            actor_ref="copaw-agent-runner",
            capability_ref="system:dispatch_query",
            risk_level="guarded",
            action_summary="Auto frontdoor continuity execution",
            result_summary="Work reached checkpoint but needs governed follow-up on the same thread.",
            metadata={
                "industry_instance_id": instance_id,
                "control_thread_id": control_thread_id,
                "assignment_id": first_assignment_id,
            },
        ),
    )
    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=first_assignment_id,
        owner_agent_id=first_assignment.owner_agent_id,
        owner_role_id=first_assignment.owner_role_id,
        headline="Same-thread follow-up still required",
        summary="The governed execution reached checkpoint, but the remaining move must stay on the same control thread.",
        status="recorded",
        result="failed",
        findings=["The next move still needs same-thread supervisor continuity."],
        recommendation="Materialize the next assignment on the same control thread and work context.",
        evidence_ids=[evidence.id],
        work_context_id=work_context_id,
        metadata={
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "environment_ref": "session:console:industry-control",
            "evidence_id": evidence.id,
        },
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    second_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:auto-frontdoor-replan",
            force=True,
        ),
    )
    processed_instance = second_cycle["processed_instances"][0]
    assert report.id in processed_instance["processed_report_ids"]
    assert processed_instance["created_assignment_ids"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == report.id
    )
    followup_assignment_id = str(followup_backlog["assignment_id"])
    assert followup_assignment_id in processed_instance["created_assignment_ids"]
    followup_assignment = app.state.assignment_repository.get_assignment(followup_assignment_id)
    assert followup_assignment is not None
    assert followup_assignment.metadata["control_thread_id"] == control_thread_id
    assert followup_assignment.metadata["session_id"] == control_thread_id
    assert followup_assignment.metadata["work_context_id"] == work_context_id
    assert followup_assignment.metadata["source_report_id"] == report.id

    if followup_assignment.task_id:
        followup_task = app.state.task_repository.get_task(followup_assignment.task_id or "")
        assert followup_task is not None
        kernel_metadata = decode_kernel_task_metadata(followup_task.acceptance_criteria)
        assert kernel_metadata is not None
        payload = dict(kernel_metadata.get("payload") or {})
        compiler_meta = dict(payload.get("compiler") or {})
        task_seed = dict(payload.get("task_seed") or {})

        assert compiler_meta["control_thread_id"] == control_thread_id
        assert task_seed["request_context"]["control_thread_id"] == control_thread_id
        assert task_seed["request_context"]["work_context_id"] == work_context_id

    runtime_detail = client.get(f"/runtime-center/industry/{instance_id}")
    assert runtime_detail.status_code == 200
    runtime_payload = runtime_detail.json()
    runtime_assignment = next(
        item
        for item in runtime_payload["assignments"]
        if item["assignment_id"] == followup_assignment_id
    )
    assert runtime_assignment["metadata"]["control_thread_id"] == control_thread_id
    assert runtime_assignment["metadata"]["work_context_id"] == work_context_id


def test_runtime_canonical_flow_chat_frontdoor_can_close_through_real_fixed_sop_terminal_report(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)

    instruction = "Please run the repeatable SOP on the same control thread and return the result."
    control_ack = "Recorded. I will move this into the governed execution chain."

    chat_service = MainBrainChatService(
        session_backend=app.state.session_backend,
        industry_service=app.state.industry_service,
        agent_profile_service=app.state.agent_profile_service,
        model_factory=lambda: _StaticResponseModel(control_ack),
    )
    query_execution_service = _CanonicalFlowQueryExecutionService(
        chat_service=chat_service,
        industry_service=app.state.industry_service,
    )
    fixed_sop_binding_ref: dict[str, str] = {}

    async def _resolve_intake_contract(**_kwargs):
        return MainBrainIntakeContract(
            message_text=instruction,
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=False),
            intent_kind="execute-task",
            writeback_requested=True,
            writeback_plan=build_chat_writeback_plan(
                instruction,
                approved_classifications=["backlog"],
                goal_title="Run canonical flow fixed SOP",
                goal_summary="Trigger the governed fixed SOP and report back on the same control thread.",
                goal_plan_steps=[
                    "Run the governed fixed SOP binding.",
                    "Keep the same control thread and work context.",
                    "Write back the terminal report and evidence.",
                ],
                goal_metadata={
                    "fixed_sop_binding_id": fixed_sop_binding_ref["binding_id"],
                    "fixed_sop_binding_name": fixed_sop_binding_ref["binding_name"],
                    "fixed_sop_source_type": "assignment",
                    "fixed_sop_source_ref": "runtime-canonical-flow-chat",
                    "fixed_sop_input_payload": {"window": "today"},
                },
            ),
            should_kickoff=False,
        )

    app.state.turn_executor = KernelTurnExecutor(
        session_backend=app.state.session_backend,
        query_execution_service=query_execution_service,
        main_brain_chat_service=chat_service,
        main_brain_orchestrator=MainBrainOrchestrator(
            query_execution_service=query_execution_service,
            session_backend=app.state.session_backend,
            intake_contract_resolver=_resolve_intake_contract,
        ),
    )
    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "guided customer follow-up",
        },
    )
    assert preview.status_code == 200
    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview.json()["profile"],
            "draft": preview.json()["draft"],
            "auto_activate": True,
        },
    )
    assert bootstrap.status_code == 200
    instance_id = bootstrap.json()["team"]["team_id"]
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    binding = app.state.agent_thread_binding_repository.get_binding(control_thread_id)
    assert binding is not None
    work_context_id = binding.work_context_id
    assert work_context_id is not None

    fixed_sop_binding = app.state.fixed_sop_service.create_binding(
        FixedSopBindingCreateRequest(
            template_id="fixed-sop-http-routine-bridge",
            binding_name="Canonical Flow Fixed SOP",
            status="active",
            owner_scope=record.owner_scope,
            owner_agent_id="copaw-agent-runner",
            industry_instance_id=instance_id,
            metadata={"binding_source": "runtime-canonical-flow-e2e"},
        ),
    )
    fixed_sop_binding_ref.update(
        {
            "binding_id": fixed_sop_binding.binding.binding_id,
            "binding_name": fixed_sop_binding.binding.binding_name,
        }
    )

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-canonical-flow-fixed-sop",
            "session_id": control_thread_id,
            "thread_id": control_thread_id,
            "user_id": "copaw-agent-runner",
            "channel": "console",
            "agent_id": "copaw-agent-runner",
            "industry_instance_id": instance_id,
            "industry_role_id": "execution-core",
            "session_kind": "industry-control-thread",
            "control_thread_id": control_thread_id,
            "interaction_mode": "auto",
            "requested_actions": ["writeback_backlog"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": instruction}],
                }
            ],
        },
    )
    assert response.status_code == 200
    assert query_execution_service.writeback_result is not None

    writeback = query_execution_service.writeback_result
    backlog_id = str(writeback["created_backlog_ids"][0])
    decision_id = writeback.get("decision_request_id")
    if decision_id is not None:
        approved = client.post(
            f"/runtime-center/decisions/{decision_id}/approve",
            json={"resolution": "Approved for the fixed SOP closure test.", "execute": True},
        )
        assert approved.status_code == 200

    first_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:canonical-flow-fixed-sop-cycle",
            force=True,
            backlog_item_ids=[backlog_id],
            auto_dispatch_materialized_goals=True,
        ),
    )
    processed_instance = first_cycle["processed_instances"][0]
    assert processed_instance["created_assignment_ids"]
    assert processed_instance["created_task_ids"]

    task = app.state.task_repository.get_task(processed_instance["created_task_ids"][0])
    assert task is not None
    assert task.task_type == "system:run_fixed_sop"
    assert task.work_context_id == work_context_id

    second_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:canonical-flow-fixed-sop-reconcile",
            force=True,
        ),
    )
    processed_report_ids = second_cycle["processed_instances"][0]["processed_report_ids"]
    assert processed_report_ids

    runtime_detail = client.get(f"/runtime-center/industry/{instance_id}")
    assert runtime_detail.status_code == 200
    runtime_payload = runtime_detail.json()
    report = next(
        item
        for item in runtime_payload["agent_reports"]
        if item["report_id"] in processed_report_ids
    )
    assert report["result"] == "completed"
    assert report["evidence_ids"]
    assert report["metadata"]["fixed_sop_binding_id"] == fixed_sop_binding.binding.binding_id

    snapshot = app.state.session_backend.load_session_snapshot(
        session_id=control_thread_id,
        user_id="copaw-agent-runner",
        allow_not_exist=True,
    )
    assert snapshot is not None
    memory_messages = _flatten_memory_messages(snapshot["agent"]["memory"])
    report_message = next(
        message
        for message in memory_messages
        if message.get("id") == f"agent-report:{report['report_id']}"
    )
    assert report_message["metadata"]["control_thread_id"] == control_thread_id
    assert report_message["metadata"]["work_context_id"] == work_context_id
