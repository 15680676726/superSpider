from __future__ import annotations

import asyncio
import inspect
import logging
from types import SimpleNamespace
from typing import get_args

import pytest
from fastapi import FastAPI

from copaw.app.runtime_bootstrap import (
    RuntimeBootstrap,
    RuntimeManagerStack,
    RuntimeRepositories,
    attach_runtime_state,
    build_runtime_repositories,
    build_runtime_state_bindings,
    initialize_mcp_manager,
    runtime_manager_stack_from_app_state,
    stop_runtime_manager_stack,
)
from copaw.app import runtime_service_graph as runtime_service_graph_module
from copaw.app.runtime_bootstrap_query import build_runtime_query_services
from copaw.app.runtime_service_graph import (
    _build_kernel_runtime,
    _execute_runtime_discovery_action,
    _resolve_state_store,
    _warm_runtime_memory_services,
    _resolve_default_memory_recall_backend,
)
from copaw.memory.models import MemoryBackendKind
from copaw.discovery.models import DiscoveryActionRequest, DiscoverySourceSpec
from copaw.state import SQLiteStateStore
from copaw.state.models_memory import MemoryRelationViewRecord


class _AsyncStopper:
    def __init__(self, label: str, events: list[str]) -> None:
        self._label = label
        self._events = events

    async def stop(self) -> None:
        self._events.append(self._label)


class _AsyncChannelStopper:
    def __init__(self, label: str, events: list[str]) -> None:
        self._label = label
        self._events = events

    async def stop_all(self) -> None:
        self._events.append(self._label)


class _AsyncCancelledChannelStopper:
    def __init__(self, label: str, events: list[str]) -> None:
        self._label = label
        self._events = events

    async def stop_all(self) -> None:
        self._events.append(self._label)
        raise asyncio.CancelledError(f"{self._label} cancelled")


class _AsyncMcpStopper:
    def __init__(self, label: str, events: list[str]) -> None:
        self._label = label
        self._events = events

    async def close_all(self) -> None:
        self._events.append(self._label)


class _AsyncBrowserRuntimeStopper:
    def __init__(self, label: str, events: list[str]) -> None:
        self._label = label
        self._events = events

    async def shutdown(self) -> None:
        self._events.append(self._label)


def _build_bootstrap() -> RuntimeBootstrap:
    repositories = RuntimeRepositories(
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=object(),
        bootstrap_schedule_repository=object(),
        schedule_repository=object(),
        goal_repository=object(),
        human_assist_task_repository=object(),
        work_context_repository=object(),
        decision_request_repository=object(),
        governance_control_repository=object(),
        capability_override_repository=object(),
        agent_profile_override_repository=object(),
        agent_runtime_repository=object(),
        agent_mailbox_repository=object(),
        agent_checkpoint_repository=object(),
        agent_lease_repository=object(),
        agent_thread_binding_repository=object(),
        industry_instance_repository=object(),
        media_analysis_repository=object(),
        goal_override_repository=object(),
        strategy_memory_repository=object(),
        operating_lane_repository=object(),
        backlog_item_repository=object(),
        operating_cycle_repository=object(),
        assignment_repository=object(),
        agent_report_repository=object(),
        knowledge_chunk_repository=object(),
        memory_fact_index_repository=object(),
        memory_entity_view_repository=object(),
        memory_opinion_view_repository=object(),
        memory_relation_view_repository=object(),
        memory_reflection_run_repository=object(),
        memory_sleep_repository=object(),
        workflow_template_repository=object(),
        workflow_preset_repository=object(),
        workflow_run_repository=object(),
        fixed_sop_template_repository=object(),
        fixed_sop_binding_repository=object(),
        routine_repository=object(),
        routine_run_repository=object(),
        prediction_case_repository=object(),
        prediction_scenario_repository=object(),
        prediction_signal_repository=object(),
        prediction_recommendation_repository=object(),
        prediction_review_repository=object(),
        automation_loop_runtime_repository=object(),
        session_mount_repository=object(),
    )
    return RuntimeBootstrap(
        session_backend=object(),
        conversation_compaction_service=object(),
        runtime_thread_history_reader=object(),
        state_store=object(),
        repositories=repositories,
        evidence_ledger=object(),
        environment_registry=object(),
        environment_service=object(),
        runtime_event_bus=object(),
        runtime_health_service=object(),
        runtime_provider=object(),
        provider_admin_service=object(),
        state_query_service=object(),
        evidence_query_service=object(),
        donor_source_service=object(),
        capability_candidate_service=object(),
        capability_donor_service=object(),
        donor_package_service=object(),
        donor_trust_service=object(),
        capability_portfolio_service=object(),
        donor_scout_service=object(),
        skill_trial_service=object(),
        skill_lifecycle_decision_service=object(),
        human_assist_task_service=object(),
        strategy_memory_service=object(),
        work_context_service=object(),
        knowledge_service=object(),
        media_service=object(),
        derived_memory_index_service=object(),
        memory_recall_service=object(),
        memory_reflection_service=object(),
        memory_retain_service=object(),
        memory_sleep_service=object(),
        memory_activation_service=object(),
        knowledge_graph_service=object(),
        agent_experience_service=object(),
        reporting_service=object(),
        delegation_service=object(),
        capability_service=object(),
        agent_profile_service=object(),
        industry_service=object(),
        operating_lane_service=object(),
        backlog_service=object(),
        operating_cycle_service=object(),
        assignment_service=object(),
        agent_report_service=object(),
        workflow_template_service=object(),
        fixed_sop_service=object(),
        routine_service=object(),
        prediction_service=object(),
        goal_service=object(),
        learning_service=object(),
        governance_service=object(),
        kernel_dispatcher=object(),
        kernel_task_store=object(),
        kernel_tool_bridge=object(),
        turn_executor=object(),
        main_brain_chat_service=object(),
        query_execution_service=object(),
        actor_mailbox_service=object(),
        actor_worker=object(),
        actor_supervisor=object(),
    )


def test_build_runtime_query_services_returns_memory_activation_service_when_available(
    monkeypatch,
) -> None:
    created: dict[str, object] = {}

    class _FakeMemoryActivationService:
        def __init__(self, *, derived_index_service, strategy_memory_service) -> None:
            created["derived_index_service"] = derived_index_service
            created["strategy_memory_service"] = strategy_memory_service

    monkeypatch.setattr(
        "copaw.app.runtime_bootstrap_query._resolve_memory_activation_service_cls",
        lambda: _FakeMemoryActivationService,
    )

    repositories = SimpleNamespace(
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=object(),
        schedule_repository=object(),
        backlog_item_repository=object(),
        assignment_repository=object(),
        goal_repository=object(),
        work_context_repository=object(),
        decision_request_repository=object(),
        memory_fact_index_repository=object(),
        memory_entity_view_repository=object(),
        memory_opinion_view_repository=object(),
        memory_reflection_run_repository=object(),
        memory_sleep_repository=object(),
        knowledge_chunk_repository=object(),
        strategy_memory_repository=object(),
        agent_report_repository=object(),
        routine_repository=object(),
        routine_run_repository=object(),
        industry_instance_repository=object(),
    )

    bootstrap = build_runtime_query_services(
        repositories=repositories,
        evidence_ledger=object(),
        runtime_event_bus=object(),
        human_assist_task_service=object(),
        environment_service=object(),
    )

    assert len(bootstrap) == 11
    assert bootstrap[8] is not None
    assert bootstrap[9] is not None
    assert created["derived_index_service"] is bootstrap[4]
    assert created["strategy_memory_service"] is bootstrap[2]
    assert not hasattr(bootstrap[0], "_kernel_dispatcher")
    assert not hasattr(bootstrap[0], "_runtime_event_bus")


def test_build_runtime_query_services_attaches_capability_candidate_service() -> None:
    candidate_service = object()
    repositories = SimpleNamespace(
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=object(),
        schedule_repository=object(),
        backlog_item_repository=object(),
        assignment_repository=object(),
        goal_repository=object(),
        work_context_repository=object(),
        decision_request_repository=object(),
        memory_fact_index_repository=object(),
        memory_entity_view_repository=object(),
        memory_opinion_view_repository=object(),
        memory_reflection_run_repository=object(),
        memory_sleep_repository=object(),
        knowledge_chunk_repository=object(),
        strategy_memory_repository=object(),
        agent_report_repository=object(),
        routine_repository=object(),
        routine_run_repository=object(),
        industry_instance_repository=object(),
    )

    bootstrap = build_runtime_query_services(
        repositories=repositories,
        evidence_ledger=object(),
        runtime_event_bus=object(),
        human_assist_task_service=object(),
        environment_service=object(),
        capability_candidate_service=candidate_service,
    )

    assert bootstrap[0]._capability_candidate_service is candidate_service


def test_build_runtime_query_services_injects_runtime_provider_into_memory_sleep_inference() -> None:
    class _FakeSleepChatModel:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def __call__(self, *, messages, structured_model=None, **kwargs):
            self.calls.append(
                {
                    "messages": messages,
                    "structured_model": structured_model,
                    "kwargs": kwargs,
                },
            )
            payload = {
                "digest": {
                    "headline": "Model digest",
                    "summary": "Compiled by runtime model.",
                    "current_constraints": ["Wait for finance review."],
                    "current_focus": ["Close the approval blocker."],
                    "top_entities": ["finance review"],
                    "top_relations": ["approval depends on finance review"],
                    "evidence_refs": ["fact:ctx-1:1"],
                },
                "alias_maps": [],
                "merge_results": [],
                "soft_rules": [],
                "conflict_proposals": [],
            }
            metadata = (
                structured_model.model_validate(payload)
                if structured_model is not None
                else payload
            )
            return SimpleNamespace(metadata=metadata, content=[])

    fake_model = _FakeSleepChatModel()
    runtime_provider = SimpleNamespace(get_active_chat_model=lambda: fake_model)
    repositories = SimpleNamespace(
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=object(),
        schedule_repository=object(),
        backlog_item_repository=object(),
        assignment_repository=object(),
        goal_repository=object(),
        work_context_repository=object(),
        decision_request_repository=object(),
        memory_fact_index_repository=object(),
        memory_entity_view_repository=object(),
        memory_opinion_view_repository=object(),
        memory_reflection_run_repository=object(),
        memory_sleep_repository=object(),
        knowledge_chunk_repository=object(),
        strategy_memory_repository=object(),
        agent_report_repository=object(),
        routine_repository=object(),
        routine_run_repository=object(),
        industry_instance_repository=object(),
    )

    bootstrap = build_runtime_query_services(
        repositories=repositories,
        evidence_ledger=object(),
        runtime_event_bus=object(),
        human_assist_task_service=object(),
        environment_service=object(),
        runtime_provider=runtime_provider,
    )

    sleep_service = bootstrap[8]
    inference_service = sleep_service._inference_service
    model_runner = inference_service._model_runner

    assert callable(model_runner)
    result = model_runner(
        scope_type="work_context",
        scope_id="ctx-1",
        knowledge_chunks=[],
        strategies=[],
        fact_entries=[],
        entity_views=[],
        relation_views=[],
    )
    assert result["digest"]["headline"] == "Model digest"
    assert fake_model.calls
    assert fake_model.calls[0]["structured_model"] is not None


def test_build_runtime_repositories_exposes_external_runtime_repository(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")

    repositories = build_runtime_repositories(store)

    assert hasattr(repositories, "external_runtime_repository")
    assert repositories.external_runtime_repository is not None


def test_reconcile_external_runtime_truth_marks_missing_process_orphaned(
    monkeypatch,
    tmp_path,
) -> None:
    from copaw.app.runtime_service_graph import _reconcile_external_runtime_truth
    from copaw.state import ExternalCapabilityRuntimeService
    from copaw.state.repositories import SqliteExternalCapabilityRuntimeRepository

    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteExternalCapabilityRuntimeRepository(store)
    service = ExternalCapabilityRuntimeService(repository=repository)
    runtime = service.create_or_reuse_service_runtime(
        capability_id="runtime:flask",
        scope_kind="session",
        session_mount_id="session-1",
        owner_agent_id="copaw-agent-runner",
        command="python -m flask run",
    )
    service.update_runtime(
        runtime.runtime_id,
        status="ready",
        process_id=987654,
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "_external_runtime_process_exists",
        lambda pid: False,
    )

    summary = _reconcile_external_runtime_truth(service)
    updated = service.get_runtime(runtime.runtime_id)

    assert summary == {"checked": 1, "orphaned": 1}
    assert updated is not None
    assert updated.status == "orphaned"


def test_runtime_discovery_executor_dispatches_provider_hits(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_service_graph_module,
        "_search_github_repository_donors",
        lambda query, limit=20, search_url=None: [
            runtime_service_graph_module.DiscoveryHit(
                source_id="global-github",
                source_kind="github-repo",
                source_alias="global-github",
                candidate_kind="project",
                display_name="acme/browser-pilot",
                summary=f"query={query} limit={limit}",
                candidate_source_ref="https://github.com/acme/browser-pilot",
                candidate_source_version="main",
                candidate_source_lineage="donor:github:acme/browser-pilot",
                canonical_package_id="pkg:github:acme/browser-pilot",
                capability_keys=("browser", "automation"),
            ),
        ],
        raising=False,
    )
    source = DiscoverySourceSpec(
        source_id="global-github",
        chain_role="primary",
        source_kind="catalog",
        display_name="GitHub",
        endpoint="https://api.github.com/search/repositories",
        metadata={"provider": "github-repo"},
    )

    hits = _execute_runtime_discovery_action(
        source,
        DiscoveryActionRequest(
            action_id="discover-1",
            query="browser automation github",
            limit=5,
        ),
    )

    assert len(hits) == 1
    assert hits[0].canonical_package_id == "pkg:github:acme/browser-pilot"


def test_runtime_discovery_executor_forwards_source_endpoint_to_providers(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_github(query, limit=20, search_url=None):
        captured["github"] = {
            "query": query,
            "limit": limit,
            "search_url": search_url,
        }
        return []

    def _fake_skillhub(query, limit=20, search_url=None):
        captured["skillhub"] = {
            "query": query,
            "limit": limit,
            "search_url": search_url,
        }
        return []

    def _fake_mcp(query, limit=20, base_url=None):
        captured["mcp"] = {
            "query": query,
            "limit": limit,
            "base_url": base_url,
        }
        return []

    monkeypatch.setattr(
        runtime_service_graph_module,
        "_search_github_repository_donors",
        _fake_github,
        raising=False,
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "_search_skillhub_discovery_hits",
        _fake_skillhub,
        raising=False,
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "_search_mcp_registry_discovery_hits",
        _fake_mcp,
        raising=False,
    )

    _execute_runtime_discovery_action(
        DiscoverySourceSpec(
            source_id="global-github",
            chain_role="primary",
            source_kind="catalog",
            display_name="GitHub",
            endpoint="https://mirror.example/github-search",
            metadata={"provider": "github-repo"},
        ),
        DiscoveryActionRequest(
            action_id="discover-github",
            query="browser automation github",
            limit=5,
        ),
    )
    _execute_runtime_discovery_action(
        DiscoverySourceSpec(
            source_id="global-skillhub",
            chain_role="primary",
            source_kind="catalog",
            display_name="SkillHub",
            endpoint="https://mirror.example/skillhub-search",
            metadata={"provider": "skillhub-catalog"},
        ),
        DiscoveryActionRequest(
            action_id="discover-skillhub",
            query="browser automation",
            limit=4,
        ),
    )
    _execute_runtime_discovery_action(
        DiscoverySourceSpec(
            source_id="global-mcp-registry",
            chain_role="fallback",
            source_kind="catalog",
            display_name="MCP Registry",
            endpoint="https://mirror.example/mcp-registry",
            metadata={"provider": "mcp-registry"},
        ),
        DiscoveryActionRequest(
            action_id="discover-mcp",
            query="filesystem",
            limit=3,
        ),
    )

    assert captured["github"]["search_url"] == "https://mirror.example/github-search"
    assert captured["skillhub"]["search_url"] == "https://mirror.example/skillhub-search"
    assert captured["mcp"]["base_url"] == "https://mirror.example/mcp-registry"


def test_attach_runtime_state_binds_capability_candidate_service() -> None:
    app = FastAPI()
    bootstrap = _build_bootstrap()
    bootstrap.capability_candidate_service = object()
    bootstrap.skill_trial_service = object()
    bootstrap.skill_lifecycle_decision_service = object()

    attach_runtime_state(
        app,
        runtime_host=object(),
        bootstrap=bootstrap,
        manager_stack=RuntimeManagerStack(),
        startup_recovery_summary=object(),
    )

    assert app.state.capability_candidate_service is bootstrap.capability_candidate_service
    assert app.state.skill_trial_service is bootstrap.skill_trial_service
    assert (
        app.state.skill_lifecycle_decision_service
        is bootstrap.skill_lifecycle_decision_service
    )


def test_attach_runtime_state_binds_bootstrap_and_manager_stack() -> None:
    app = FastAPI()
    bootstrap = _build_bootstrap()
    runtime_host = object()
    startup_recovery_summary = {"reason": "startup"}
    automation_tasks = [object()]
    manager_stack = RuntimeManagerStack(
        mcp_manager=object(),
        channel_manager=object(),
        cron_manager=object(),
        job_repository=object(),
        config_watcher=object(),
        mcp_watcher=object(),
    )

    attach_runtime_state(
        app,
        runtime_host=runtime_host,
        bootstrap=bootstrap,
        manager_stack=manager_stack,
        startup_recovery_summary=startup_recovery_summary,
        automation_tasks=automation_tasks,
    )

    assert app.state.runtime_host is runtime_host
    assert app.state.turn_executor is bootstrap.turn_executor
    assert app.state.human_assist_task_service is bootstrap.human_assist_task_service
    assert app.state.main_brain_chat_service is bootstrap.main_brain_chat_service
    assert app.state.capability_service is bootstrap.capability_service
    assert app.state.runtime_health_service is bootstrap.runtime_health_service
    assert app.state.runtime_provider is bootstrap.runtime_provider
    assert app.state.provider_admin_service is bootstrap.provider_admin_service
    assert not hasattr(app.state, "provider_manager")
    assert app.state.channel_manager is manager_stack.channel_manager
    assert app.state.job_repository is manager_stack.job_repository
    assert app.state.schedule_repository is bootstrap.repositories.schedule_repository
    assert (
        app.state.human_assist_task_repository
        is bootstrap.repositories.human_assist_task_repository
    )
    assert app.state.work_context_repository is bootstrap.repositories.work_context_repository
    assert (
        app.state.automation_loop_runtime_repository
        is bootstrap.repositories.automation_loop_runtime_repository
    )
    assert app.state.session_mount_repository is bootstrap.repositories.session_mount_repository
    assert (
        app.state.media_analysis_repository
        is bootstrap.repositories.media_analysis_repository
    )
    assert app.state.operating_lane_repository is bootstrap.repositories.operating_lane_repository
    assert app.state.backlog_item_repository is bootstrap.repositories.backlog_item_repository
    assert app.state.operating_cycle_repository is bootstrap.repositories.operating_cycle_repository
    assert app.state.assignment_repository is bootstrap.repositories.assignment_repository
    assert app.state.agent_report_repository is bootstrap.repositories.agent_report_repository
    assert app.state.operating_lane_service is bootstrap.operating_lane_service
    assert app.state.backlog_service is bootstrap.backlog_service
    assert app.state.operating_cycle_service is bootstrap.operating_cycle_service
    assert app.state.assignment_service is bootstrap.assignment_service
    assert app.state.agent_report_service is bootstrap.agent_report_service
    assert app.state.routine_repository is bootstrap.repositories.routine_repository
    assert app.state.routine_run_repository is bootstrap.repositories.routine_run_repository
    assert (
        app.state.fixed_sop_template_repository
        is bootstrap.repositories.fixed_sop_template_repository
    )
    assert (
        app.state.fixed_sop_binding_repository
        is bootstrap.repositories.fixed_sop_binding_repository
    )
    assert app.state.routine_service is bootstrap.routine_service
    assert app.state.fixed_sop_service is bootstrap.fixed_sop_service
    assert app.state.work_context_service is bootstrap.work_context_service
    assert app.state.media_service is bootstrap.media_service
    assert app.state.startup_recovery_summary == startup_recovery_summary
    assert app.state.automation_tasks == automation_tasks


def test_attach_runtime_state_binds_memory_activation_service() -> None:
    app = FastAPI()
    bootstrap = _build_bootstrap()

    attach_runtime_state(
        app,
        runtime_host=object(),
        bootstrap=bootstrap,
        manager_stack=RuntimeManagerStack(),
        startup_recovery_summary={"reason": "startup"},
    )

    assert app.state.memory_activation_service is bootstrap.memory_activation_service


def test_attach_runtime_state_binds_knowledge_graph_service() -> None:
    app = FastAPI()
    bootstrap = _build_bootstrap()

    attach_runtime_state(
        app,
        runtime_host=object(),
        bootstrap=bootstrap,
        manager_stack=RuntimeManagerStack(),
        startup_recovery_summary={"reason": "startup"},
    )

    assert app.state.knowledge_graph_service is bootstrap.knowledge_graph_service


def test_build_runtime_state_bindings_materializes_single_state_payload() -> None:
    bootstrap = _build_bootstrap()
    runtime_host = object()
    startup_recovery_summary = {"reason": "startup"}
    automation_tasks = [object()]
    manager_stack = RuntimeManagerStack(
        mcp_manager=object(),
        channel_manager=object(),
        cron_manager=object(),
        job_repository=object(),
        config_watcher=object(),
        mcp_watcher=object(),
    )

    bindings = build_runtime_state_bindings(
        runtime_host=runtime_host,
        bootstrap=bootstrap,
        manager_stack=manager_stack,
        startup_recovery_summary=startup_recovery_summary,
        automation_tasks=automation_tasks,
    )

    assert bindings["runtime_host"] is runtime_host
    assert (
        bindings["conversation_compaction_service"]
        is bootstrap.conversation_compaction_service
    )
    assert "memory_manager" not in bindings
    assert "provider_manager" not in bindings
    assert bindings["runtime_provider"] is bootstrap.runtime_provider
    assert bindings["provider_admin_service"] is bootstrap.provider_admin_service
    assert bindings["schedule_repository"] is bootstrap.repositories.schedule_repository
    assert (
        bindings["human_assist_task_repository"]
        is bootstrap.repositories.human_assist_task_repository
    )
    assert bindings["work_context_repository"] is bootstrap.repositories.work_context_repository
    assert (
        bindings["automation_loop_runtime_repository"]
        is bootstrap.repositories.automation_loop_runtime_repository
    )
    assert (
        bindings["fixed_sop_template_repository"]
        is bootstrap.repositories.fixed_sop_template_repository
    )
    assert (
        bindings["fixed_sop_binding_repository"]
        is bootstrap.repositories.fixed_sop_binding_repository
    )
    assert bindings["fixed_sop_service"] is bootstrap.fixed_sop_service
    assert bindings["human_assist_task_service"] is bootstrap.human_assist_task_service
    assert (
        bindings["media_analysis_repository"]
        is bootstrap.repositories.media_analysis_repository
    )
    assert bindings["memory_activation_service"] is bootstrap.memory_activation_service
    assert bindings["knowledge_graph_service"] is bootstrap.knowledge_graph_service
    assert (
        bindings["memory_relation_view_repository"]
        is bootstrap.repositories.memory_relation_view_repository
    )
    assert bindings["operating_lane_repository"] is bootstrap.repositories.operating_lane_repository
    assert bindings["backlog_item_repository"] is bootstrap.repositories.backlog_item_repository
    assert bindings["operating_cycle_repository"] is bootstrap.repositories.operating_cycle_repository
    assert bindings["assignment_repository"] is bootstrap.repositories.assignment_repository
    assert bindings["agent_report_repository"] is bootstrap.repositories.agent_report_repository
    assert bindings["operating_lane_service"] is bootstrap.operating_lane_service
    assert bindings["backlog_service"] is bootstrap.backlog_service
    assert bindings["operating_cycle_service"] is bootstrap.operating_cycle_service
    assert bindings["assignment_service"] is bootstrap.assignment_service
    assert bindings["agent_report_service"] is bootstrap.agent_report_service
    assert bindings["routine_repository"] is bootstrap.repositories.routine_repository
    assert bindings["routine_run_repository"] is bootstrap.repositories.routine_run_repository
    assert bindings["routine_service"] is bootstrap.routine_service
    assert bindings["work_context_service"] is bootstrap.work_context_service
    assert bindings["channel_manager"] is manager_stack.channel_manager
    assert bindings["media_service"] is bootstrap.media_service
    assert bindings["main_brain_chat_service"] is bootstrap.main_brain_chat_service
    assert bindings["startup_recovery_summary"] == startup_recovery_summary
    assert bindings["latest_recovery_report"] is not startup_recovery_summary
    assert bindings["latest_recovery_report"]["reason"] == "startup"
    assert bindings["latest_recovery_report"]["source"] == "startup"
    assert bindings["automation_tasks"] == automation_tasks
    assert bindings["automation_tasks"] is not automation_tasks


def test_build_runtime_state_bindings_preserves_automation_group_contract() -> None:
    class _AutomationTasks(list):
        def loop_snapshots(self) -> dict[str, dict[str, object]]:
            return {
                "operating-cycle": {
                    "task_name": "operating-cycle",
                    "coordinator_contract": "automation-coordinator/v1",
                }
            }

    bootstrap = _build_bootstrap()
    manager_stack = RuntimeManagerStack(
        mcp_manager=object(),
        channel_manager=object(),
        cron_manager=object(),
        job_repository=object(),
        config_watcher=object(),
        mcp_watcher=object(),
    )
    automation_tasks = _AutomationTasks([object()])

    bindings = build_runtime_state_bindings(
        runtime_host=object(),
        bootstrap=bootstrap,
        manager_stack=manager_stack,
        startup_recovery_summary={"reason": "restart"},
        automation_tasks=automation_tasks,
    )

    assert bindings["automation_tasks"] is automation_tasks
    assert callable(bindings["automation_tasks"].loop_snapshots)
    assert bindings["automation_tasks"].loop_snapshots()["operating-cycle"][
        "coordinator_contract"
    ] == "automation-coordinator/v1"


def test_build_runtime_repositories_keeps_bootstrap_schedule_repo_separate(
    tmp_path,
) -> None:
    repositories = build_runtime_repositories(SQLiteStateStore(tmp_path / "state.db"))

    assert repositories.task_repository is not None
    assert repositories.schedule_repository is not None
    assert repositories.bootstrap_schedule_repository is not None
    assert repositories.bootstrap_schedule_repository is not repositories.schedule_repository
    assert repositories.automation_loop_runtime_repository is not None
    assert repositories.session_mount_repository is not None


def test_memory_relation_view_record_accepts_relation_metadata() -> None:
    record = MemoryRelationViewRecord(
        relation_id="rel:ctx-1:approval->finance",
        source_node_id="fact:approval",
        target_node_id="entity:finance-queue",
        relation_kind="supports",
        scope_type="work_context",
        scope_id="ctx-1",
        source_refs=["fact:approval"],
        metadata={"reason": "queue ownership"},
    )

    assert record.relation_kind == "supports"
    assert record.scope_type == "work_context"
    assert record.metadata == {"reason": "queue ownership"}


def test_build_runtime_repositories_includes_memory_relation_view_repository(
    tmp_path,
) -> None:
    repositories = build_runtime_repositories(SQLiteStateStore(tmp_path / "state.db"))

    assert repositories.memory_relation_view_repository is not None


def test_memory_relation_view_repository_round_trips_sqlite_records(tmp_path) -> None:
    repositories = build_runtime_repositories(SQLiteStateStore(tmp_path / "state.db"))
    repository = repositories.memory_relation_view_repository
    record = MemoryRelationViewRecord(
        relation_id="rel:ctx-1:approval->finance",
        source_node_id="fact:approval",
        target_node_id="entity:finance-queue",
        relation_kind="supports",
        scope_type="work_context",
        scope_id="ctx-1",
        owner_agent_id="agent:ops",
        industry_instance_id="industry:finops",
        summary="Approval supports finance queue review.",
        confidence=0.9,
        source_refs=["fact:approval", "report:daily-1"],
        metadata={"reason": "queue ownership"},
    )

    repository.upsert_view(record)

    stored = repository.get_view(record.relation_id)
    scoped = repository.list_views(
        scope_type="work_context",
        scope_id="ctx-1",
        relation_kind="supports",
        source_node_id="fact:approval",
        target_node_id="entity:finance-queue",
    )

    assert stored is not None
    assert stored.model_dump(mode="json") == record.model_dump(mode="json")
    assert [item.relation_id for item in scoped] == [record.relation_id]


def test_build_kernel_runtime_threads_state_store_into_capability_service(
    monkeypatch,
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    class _FakePatchExecutor:
        def __init__(self, **kwargs) -> None:
            captured["patch_executor_kwargs"] = kwargs

    class _FakeLearningService:
        def __init__(self, **kwargs) -> None:
            captured["learning_service_kwargs"] = kwargs

    class _FakeGovernanceService:
        def __init__(self, **kwargs) -> None:
            captured["governance_service_kwargs"] = kwargs

        def set_kernel_dispatcher(self, dispatcher) -> None:
            captured["governance_dispatcher"] = dispatcher

    class _FakeKernelTaskStore:
        def __init__(self, **kwargs) -> None:
            captured["kernel_task_store_kwargs"] = kwargs

    class _FakeKernelToolBridge:
        def __init__(self, **kwargs) -> None:
            captured["kernel_tool_bridge_kwargs"] = kwargs

    class _FakeCapabilityService:
        def __init__(self, **kwargs) -> None:
            captured["capability_service_kwargs"] = kwargs

    class _FakeKernelDispatcher:
        def __init__(self, **kwargs) -> None:
            captured["kernel_dispatcher_kwargs"] = kwargs

    class _FakeActorMailboxService:
        def __init__(self, **kwargs) -> None:
            captured["actor_mailbox_service_kwargs"] = kwargs

    class _FakeActorWorker:
        def __init__(self, **kwargs) -> None:
            captured["actor_worker_kwargs"] = kwargs

    class _FakeActorSupervisor:
        def __init__(self, **kwargs) -> None:
            captured["actor_supervisor_kwargs"] = kwargs

    monkeypatch.setattr(runtime_service_graph_module, "PatchExecutor", _FakePatchExecutor)
    monkeypatch.setattr(runtime_service_graph_module, "LearningService", _FakeLearningService)
    monkeypatch.setattr(runtime_service_graph_module, "GovernanceService", _FakeGovernanceService)
    monkeypatch.setattr(runtime_service_graph_module, "KernelTaskStore", _FakeKernelTaskStore)
    monkeypatch.setattr(runtime_service_graph_module, "KernelToolBridge", _FakeKernelToolBridge)
    monkeypatch.setattr(runtime_service_graph_module, "CapabilityService", _FakeCapabilityService)
    monkeypatch.setattr(runtime_service_graph_module, "KernelDispatcher", _FakeKernelDispatcher)
    monkeypatch.setattr(runtime_service_graph_module, "ActorMailboxService", _FakeActorMailboxService)
    monkeypatch.setattr(runtime_service_graph_module, "ActorWorker", _FakeActorWorker)
    monkeypatch.setattr(runtime_service_graph_module, "ActorSupervisor", _FakeActorSupervisor)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    repositories = SimpleNamespace(
        capability_override_repository=object(),
        agent_profile_override_repository=object(),
        goal_override_repository=object(),
        workflow_template_repository=object(),
        workflow_run_repository=object(),
        decision_request_repository=object(),
        task_repository=object(),
        governance_control_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=object(),
        agent_mailbox_repository=object(),
        agent_runtime_repository=object(),
        agent_checkpoint_repository=object(),
        agent_thread_binding_repository=object(),
    )
    state_query_service = SimpleNamespace()

    _build_kernel_runtime(
        mcp_manager=object(),
        environment_service=object(),
        evidence_ledger=object(),
        repositories=repositories,
        runtime_event_bus=object(),
        state_query_service=state_query_service,
        conversation_compaction_service=None,
        experience_memory_service=None,
        state_store=state_store,
        work_context_service=object(),
        runtime_provider=object(),
    )

    capability_service_kwargs = captured["capability_service_kwargs"]
    assert isinstance(capability_service_kwargs, dict)
    assert capability_service_kwargs["state_store"] is state_store
    assert "state_query_dispatcher" not in captured


def test_build_kernel_runtime_threads_external_runtime_service_into_capability_service(
    monkeypatch,
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    class _FakeCapabilityService:
        def __init__(self, **kwargs) -> None:
            captured["capability_service_kwargs"] = kwargs

    class _FakeActorWorker:
        def __init__(self, **kwargs) -> None:
            captured["actor_worker_kwargs"] = kwargs

    class _FakeActorSupervisor:
        def __init__(self, **kwargs) -> None:
            captured["actor_supervisor_kwargs"] = kwargs

    monkeypatch.setattr(runtime_service_graph_module, "PatchExecutor", lambda **kwargs: object())
    monkeypatch.setattr(runtime_service_graph_module, "LearningService", lambda **kwargs: object())
    monkeypatch.setattr(
        runtime_service_graph_module,
        "GovernanceService",
        lambda **kwargs: SimpleNamespace(set_kernel_dispatcher=lambda dispatcher: None),
    )
    monkeypatch.setattr(runtime_service_graph_module, "KernelTaskStore", lambda **kwargs: object())
    monkeypatch.setattr(runtime_service_graph_module, "KernelToolBridge", lambda **kwargs: object())
    monkeypatch.setattr(runtime_service_graph_module, "CapabilityService", _FakeCapabilityService)
    monkeypatch.setattr(runtime_service_graph_module, "KernelDispatcher", lambda **kwargs: object())
    monkeypatch.setattr(runtime_service_graph_module, "ActorMailboxService", lambda **kwargs: object())
    monkeypatch.setattr(runtime_service_graph_module, "ActorWorker", _FakeActorWorker)
    monkeypatch.setattr(runtime_service_graph_module, "ActorSupervisor", _FakeActorSupervisor)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    external_runtime_service = object()
    repositories = SimpleNamespace(
        capability_override_repository=object(),
        agent_profile_override_repository=object(),
        goal_override_repository=object(),
        workflow_template_repository=object(),
        workflow_run_repository=object(),
        decision_request_repository=object(),
        task_repository=object(),
        governance_control_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=object(),
        agent_mailbox_repository=object(),
        agent_runtime_repository=object(),
        agent_checkpoint_repository=object(),
        agent_thread_binding_repository=object(),
    )

    _build_kernel_runtime(
        mcp_manager=object(),
        environment_service=object(),
        evidence_ledger=object(),
        repositories=repositories,
        runtime_event_bus=object(),
        state_query_service=SimpleNamespace(),
        conversation_compaction_service=None,
        experience_memory_service=None,
        state_store=state_store,
        work_context_service=object(),
        runtime_provider=object(),
        external_runtime_service=external_runtime_service,
    )

    capability_service_kwargs = captured["capability_service_kwargs"]
    assert isinstance(capability_service_kwargs, dict)
    assert capability_service_kwargs["external_runtime_service"] is external_runtime_service


def test_runtime_manager_stack_from_app_state_reads_current_refs() -> None:
    app_state = SimpleNamespace(
        mcp_manager="mcp",
        channel_manager="channel",
        cron_manager="cron",
        job_repository="jobs",
        config_watcher="watcher",
        mcp_watcher="mcp-watcher",
    )

    stack = runtime_manager_stack_from_app_state(app_state)

    assert stack.mcp_manager == "mcp"
    assert stack.channel_manager == "channel"
    assert stack.cron_manager == "cron"
    assert stack.job_repository == "jobs"
    assert stack.config_watcher == "watcher"
    assert stack.mcp_watcher == "mcp-watcher"


@pytest.mark.asyncio
async def test_stop_runtime_manager_stack_stops_in_expected_order() -> None:
    events: list[str] = []
    stack = RuntimeManagerStack(
        mcp_manager=_AsyncMcpStopper("mcp", events),
        channel_manager=_AsyncChannelStopper("channel", events),
        cron_manager=_AsyncStopper("cron", events),
        config_watcher=_AsyncStopper("config", events),
        mcp_watcher=_AsyncStopper("mcp-watcher", events),
        browser_runtime_service=_AsyncBrowserRuntimeStopper("browser", events),
    )

    await stop_runtime_manager_stack(
        stack,
        logger=logging.getLogger(__name__),
        error_mode="ignore",
        context="test",
    )

    assert events == ["config", "mcp-watcher", "cron", "channel", "browser", "mcp"]


@pytest.mark.asyncio
async def test_stop_runtime_manager_stack_ignores_cancelled_teardown_errors() -> None:
    events: list[str] = []
    stack = RuntimeManagerStack(
        channel_manager=_AsyncCancelledChannelStopper("channel", events),
    )

    await stop_runtime_manager_stack(
        stack,
        logger=logging.getLogger(__name__),
        error_mode="ignore",
        context="test",
    )

    assert events == ["channel"]


def test_default_memory_backend_defaults_to_truth_first_when_unset(
    monkeypatch,
) -> None:
    monkeypatch.delenv("COPAW_MEMORY_RECALL_BACKEND", raising=False)

    assert _resolve_default_memory_recall_backend() == "truth-first"


def test_default_memory_backend_accepts_truth_first_override(monkeypatch) -> None:
    monkeypatch.setenv("COPAW_MEMORY_RECALL_BACKEND", "truth-first")

    assert _resolve_default_memory_recall_backend() == "truth-first"


def test_default_memory_backend_rejects_legacy_lexical_override(monkeypatch) -> None:
    monkeypatch.setenv("COPAW_MEMORY_RECALL_BACKEND", "lexical")

    assert _resolve_default_memory_recall_backend() == "truth-first"


def test_default_memory_backend_rejects_unknown_override(monkeypatch) -> None:
    monkeypatch.setenv("COPAW_MEMORY_RECALL_BACKEND", "legacy-sidecar")

    assert _resolve_default_memory_recall_backend() == "truth-first"


def test_warm_runtime_memory_services_extracts_startup_side_effects(monkeypatch) -> None:
    calls: dict[str, object] = {}
    repositories = SimpleNamespace(
        industry_instance_repository=SimpleNamespace(
            list_instances=lambda limit=None: [SimpleNamespace(instance_id="industry-1")],
        ),
    )
    derived_memory_index_service = SimpleNamespace(
        rebuild_all=lambda: calls.setdefault("rebuild_all", True),
    )
    memory_recall_service = SimpleNamespace(
        list_backends=lambda: [SimpleNamespace(backend_id="truth-first", is_default=True)],
    )
    memory_reflection_service = SimpleNamespace(
        reflect=lambda **kwargs: calls.setdefault("reflect_calls", []).append(kwargs),
    )

    _warm_runtime_memory_services(
        repositories=repositories,
        derived_memory_index_service=derived_memory_index_service,
        memory_reflection_service=memory_reflection_service,
    )

    assert calls["rebuild_all"] is True
    assert calls["reflect_calls"] == [
        {
            "scope_type": "global",
            "scope_id": "runtime",
            "trigger_kind": "startup",
            "create_learning_proposals": False,
        },
        {
            "scope_type": "industry",
            "scope_id": "industry-1",
            "industry_instance_id": "industry-1",
            "trigger_kind": "startup",
            "create_learning_proposals": False,
        },
    ]


def test_warm_runtime_memory_services_does_not_request_sidecar_prewarm(
    monkeypatch,
) -> None:
    monkeypatch.delenv("COPAW_MEMORY_RECALL_BACKEND", raising=False)
    calls: dict[str, object] = {}
    repositories = SimpleNamespace(
        industry_instance_repository=SimpleNamespace(list_instances=lambda limit=None: []),
    )
    derived_memory_index_service = SimpleNamespace(
        rebuild_all=lambda: calls.setdefault("rebuild_all", True),
    )
    memory_recall_service = SimpleNamespace(
        list_backends=lambda: [SimpleNamespace(backend_id="truth-first", is_default=True)],
    )
    memory_reflection_service = SimpleNamespace(
        reflect=lambda **kwargs: calls.setdefault("reflect_calls", []).append(kwargs),
    )

    _warm_runtime_memory_services(
        repositories=repositories,
        derived_memory_index_service=derived_memory_index_service,
        memory_reflection_service=memory_reflection_service,
    )

    assert calls["rebuild_all"] is True
    assert calls["reflect_calls"] == [
        {
            "scope_type": "global",
            "scope_id": "runtime",
            "trigger_kind": "startup",
            "create_learning_proposals": False,
        },
    ]


def test_warm_runtime_memory_services_skips_legacy_sidecar_prewarm_call() -> None:
    calls: dict[str, object] = {}
    repositories = SimpleNamespace(
        industry_instance_repository=SimpleNamespace(list_instances=lambda limit=None: []),
    )
    derived_memory_index_service = SimpleNamespace(
        rebuild_all=lambda: calls.setdefault("rebuild_all", True),
    )
    memory_recall_service = SimpleNamespace(
        list_backends=lambda: [SimpleNamespace(backend_id="truth-first", is_default=True)],
        prepare_sidecar_backends=lambda prewarm_backend_ids: calls.setdefault(
            "prewarm_backends",
            list(prewarm_backend_ids),
        ),
    )
    memory_reflection_service = SimpleNamespace(
        reflect=lambda **kwargs: calls.setdefault("reflect_calls", []).append(kwargs),
    )

    _warm_runtime_memory_services(
        repositories=repositories,
        derived_memory_index_service=derived_memory_index_service,
        memory_reflection_service=memory_reflection_service,
    )

    assert calls["rebuild_all"] is True
    assert "prewarm_backends" not in calls
    assert calls["reflect_calls"] == [
        {
            "scope_type": "global",
            "scope_id": "runtime",
            "trigger_kind": "startup",
            "create_learning_proposals": False,
        },
    ]


def test_warm_runtime_memory_services_runs_idle_sleep_catchup_when_available() -> None:
    calls: dict[str, object] = {}
    repositories = SimpleNamespace(
        industry_instance_repository=SimpleNamespace(list_instances=lambda limit=None: []),
    )
    derived_memory_index_service = SimpleNamespace(
        rebuild_all=lambda: calls.setdefault("rebuild_all", True),
    )
    memory_reflection_service = SimpleNamespace(
        reflect=lambda **kwargs: calls.setdefault("reflect_calls", []).append(kwargs),
    )
    memory_sleep_service = SimpleNamespace(
        run_idle_catchup=lambda **kwargs: calls.setdefault("idle_catchup_calls", []).append(kwargs),
    )

    _warm_runtime_memory_services(
        repositories=repositories,
        derived_memory_index_service=derived_memory_index_service,
        memory_reflection_service=memory_reflection_service,
        memory_sleep_service=memory_sleep_service,
    )

    assert calls["rebuild_all"] is True
    assert calls["idle_catchup_calls"] == [{"limit": 5}]


def test_formal_memory_backend_kind_excludes_vector_and_legacy_sidecar_variants() -> None:
    backend_kinds = set(get_args(MemoryBackendKind))

    assert backend_kinds == {"truth-first"}


def test_runtime_bootstrap_formal_contract_exposes_runtime_provider_only() -> None:
    bootstrap = _build_bootstrap()

    assert bootstrap.runtime_provider is not None
    assert bootstrap.provider_admin_service is not None
    assert not hasattr(bootstrap, "provider_manager")


def test_resolve_runtime_provider_facade_wraps_compatibility_provider_manager(
    monkeypatch,
) -> None:
    provider_manager = object()
    sentinel = object()
    monkeypatch.setattr(
        runtime_service_graph_module,
        "get_runtime_provider_facade",
        lambda *, provider_manager=None: sentinel,
    )

    assert runtime_service_graph_module._resolve_runtime_provider_facade(
        provider_manager,
    ) is sentinel


def test_domain_builder_formal_signature_uses_runtime_provider_only() -> None:
    parameters = inspect.signature(
        runtime_service_graph_module.build_runtime_domain_services,
    ).parameters

    assert "runtime_provider" in parameters
    assert "provider_manager" not in parameters


def test_resolve_state_store_uses_runtime_working_dir_layout(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runtime_service_graph_module, "WORKING_DIR", tmp_path)

    state_store = _resolve_state_store()

    assert isinstance(state_store, SQLiteStateStore)
    assert state_store.path == tmp_path / "state" / "phase1.sqlite3"


@pytest.mark.asyncio
async def test_initialize_mcp_manager_forwards_strict_and_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeMCPManager:
        async def init_from_config(
            self,
            config,
            *,
            strict: bool,
            timeout: float,
        ) -> None:
            captured["config"] = config
            captured["strict"] = strict
            captured["timeout"] = timeout

    monkeypatch.setattr(
        runtime_service_graph_module,
        "MCPClientManager",
        _FakeMCPManager,
    )
    config = SimpleNamespace(mcp=object())

    manager = await initialize_mcp_manager(
        config=config,
        logger=logging.getLogger(__name__),
        strict=True,
        timeout=9.5,
    )

    assert isinstance(manager, _FakeMCPManager)
    assert captured == {
        "config": config.mcp,
        "strict": True,
        "timeout": 9.5,
    }
