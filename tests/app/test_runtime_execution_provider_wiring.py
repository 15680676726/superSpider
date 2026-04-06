from __future__ import annotations

from types import SimpleNamespace

from copaw.app import runtime_service_graph as runtime_service_graph_module
from copaw.app.runtime_bootstrap_execution import build_runtime_execution_stack
from copaw.state import SQLiteStateStore


def _repositories() -> SimpleNamespace:
    return SimpleNamespace(
        capability_override_repository=object(),
        agent_profile_override_repository=object(),
        goal_override_repository=object(),
        governance_control_repository=object(),
        decision_request_repository=object(),
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=object(),
        agent_mailbox_repository=object(),
        agent_runtime_repository=object(),
        agent_checkpoint_repository=object(),
        agent_thread_binding_repository=object(),
    )


def test_build_runtime_execution_stack_passes_runtime_provider_to_capability_service(
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    class _LearningService:
        def __init__(self, **kwargs) -> None:
            captured["learning_service_kwargs"] = kwargs

    class _GovernanceService:
        def __init__(self, **kwargs) -> None:
            captured["governance_service_kwargs"] = kwargs

        def set_kernel_dispatcher(self, kernel_dispatcher) -> None:
            captured["governance_kernel_dispatcher"] = kernel_dispatcher

    class _KernelTaskStore:
        def __init__(self, **kwargs) -> None:
            captured["kernel_task_store_kwargs"] = kwargs

    class _KernelToolBridge:
        def __init__(self, **kwargs) -> None:
            captured["kernel_tool_bridge_kwargs"] = kwargs

    class _CapabilityService:
        def __init__(self, **kwargs) -> None:
            captured["capability_service_kwargs"] = kwargs

    class _KernelDispatcher:
        def __init__(self, **kwargs) -> None:
            captured["kernel_dispatcher_kwargs"] = kwargs

    class _ActorMailboxService:
        def __init__(self, **kwargs) -> None:
            captured["actor_mailbox_kwargs"] = kwargs

    class _ActorWorker:
        def __init__(self, **kwargs) -> None:
            captured["actor_worker_kwargs"] = kwargs

    class _ActorSupervisor:
        def __init__(self, **kwargs) -> None:
            captured["actor_supervisor_kwargs"] = kwargs

    build_runtime_execution_stack(
        mcp_manager=object(),
        environment_service=object(),
        evidence_ledger=object(),
        repositories=_repositories(),
        runtime_event_bus=object(),
        state_query_service=object(),
        conversation_compaction_service=None,
        experience_memory_service=None,
        state_store=SQLiteStateStore(tmp_path / "state.sqlite3"),
        work_context_service=object(),
        runtime_provider="provider-runtime-facade",
        learning_service_cls=_LearningService,
        governance_service_cls=_GovernanceService,
        kernel_task_store_cls=_KernelTaskStore,
        kernel_tool_bridge_cls=_KernelToolBridge,
        capability_service_cls=_CapabilityService,
        kernel_dispatcher_cls=_KernelDispatcher,
        actor_mailbox_service_cls=_ActorMailboxService,
        actor_worker_cls=_ActorWorker,
        actor_supervisor_cls=_ActorSupervisor,
    )

    assert (
        captured["capability_service_kwargs"]["runtime_provider"]
        == "provider-runtime-facade"
    )


def test_build_kernel_runtime_forwards_runtime_provider_to_execution_stack(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        runtime_service_graph_module,
        "build_runtime_execution_stack_components",
        lambda **kwargs: captured.setdefault("kwargs", kwargs) or (
            "learning",
            "governance",
            "task-store",
            "tool-bridge",
            "capability-service",
            "dispatcher",
            "mailbox",
            "worker",
            "supervisor",
        ),
    )

    runtime_service_graph_module._build_kernel_runtime(
        mcp_manager=object(),
        environment_service=object(),
        evidence_ledger=object(),
        repositories=object(),
        runtime_event_bus=object(),
        state_query_service=object(),
        conversation_compaction_service=None,
        experience_memory_service=None,
        state_store=SQLiteStateStore(":memory:"),
        work_context_service=object(),
        runtime_provider="provider-runtime-facade",
        external_runtime_service=None,
    )

    assert captured["kwargs"]["runtime_provider"] == "provider-runtime-facade"
