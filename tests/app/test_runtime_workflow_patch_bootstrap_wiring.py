# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.app.runtime_bootstrap_execution import build_runtime_execution_stack


def test_runtime_execution_stack_wires_workflow_repositories_into_patch_executor() -> None:
    captured: dict[str, object] = {}

    class _PatchExecutor:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    class _LearningService:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _GovernanceService:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def set_kernel_dispatcher(self, value) -> None:
            self.kernel_dispatcher = value

    class _KernelTaskStore:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _KernelToolBridge:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _CapabilityService:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _KernelDispatcher:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    repositories = SimpleNamespace(
        capability_override_repository=object(),
        agent_profile_override_repository=object(),
        goal_override_repository=object(),
        workflow_template_repository=object(),
        workflow_run_repository=object(),
        governance_control_repository=object(),
        decision_request_repository=object(),
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=object(),
        agent_mailbox_repository=object(),
        agent_runtime_repository=object(),
        agent_thread_binding_repository=object(),
        evidence_ledger_repository=object(),
    )

    build_runtime_execution_stack(
        mcp_manager=object(),
        environment_service=object(),
        evidence_ledger=object(),
        repositories=repositories,
        runtime_event_bus=object(),
        state_query_service=object(),
        conversation_compaction_service=None,
        experience_memory_service=None,
        state_store=object(),
        work_context_service=object(),
        runtime_provider=None,
        patch_executor_cls=_PatchExecutor,
        learning_service_cls=_LearningService,
        governance_service_cls=_GovernanceService,
        kernel_task_store_cls=_KernelTaskStore,
        kernel_tool_bridge_cls=_KernelToolBridge,
        capability_service_cls=_CapabilityService,
        kernel_dispatcher_cls=_KernelDispatcher,
    )

    assert (
        captured["workflow_template_repository"]
        is repositories.workflow_template_repository
    )
    assert captured["workflow_run_repository"] is repositories.workflow_run_repository
