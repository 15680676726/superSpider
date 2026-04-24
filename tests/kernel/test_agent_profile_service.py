# -*- coding: utf-8 -*-
from types import SimpleNamespace
from datetime import datetime, timezone

from copaw.evidence import ArtifactRecord, EvidenceLedger, EvidenceRecord, ReplayPointer
from copaw.kernel.agent_profile_service import AgentProfileService
from copaw.kernel import KernelTask, KernelTaskStore
from copaw.state import (
    AgentCheckpointRecord,
    DecisionRequestRecord,
    AgentProfileOverrideRecord,
    TaskRecord,
    SQLiteStateStore,
)
from copaw.state.repositories import (
    SqliteAgentCheckpointRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteDecisionRequestRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)
from tests.shared.executor_runtime_compat import (
    AgentRuntimeRecord,
    SqliteAgentRuntimeRepository,
)


def test_agent_profile_service_supports_business_and_system_views():
    service = AgentProfileService()

    business_ids = {agent.agent_id for agent in service.list_agents(view="business")}
    system_ids = {agent.agent_id for agent in service.list_agents(view="system")}
    all_ids = {agent.agent_id for agent in service.list_agents()}

    assert "copaw-agent-runner" in business_ids
    assert "copaw-scheduler" not in business_ids
    assert "copaw-governance" not in business_ids
    assert system_ids == {
        "copaw-scheduler",
        "copaw-governance",
    }
    assert business_ids | system_ids == all_ids
    assert "copaw-agent-runner" in all_ids


def test_agent_profile_service_does_not_mark_default_system_agents_as_goal_focus() -> None:
    service = AgentProfileService()

    for agent_id in ("copaw-agent-runner", "copaw-scheduler", "copaw-governance"):
        profile = service.get_agent(agent_id)

        assert profile is not None
        assert profile.current_focus_kind is None
        assert profile.current_focus_id is None
        assert profile.current_focus


def test_agent_profile_service_filters_agents_by_industry_instance(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    override_repo = SqliteAgentProfileOverrideRepository(store)
    override_repo.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="industry-ops-agent",
            name="Ops Agent",
            role_name="Operations",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operations",
        ),
    )
    override_repo.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="industry-sales-agent",
            name="Sales Agent",
            role_name="Sales",
            industry_instance_id="industry-v1-sales",
            industry_role_id="sales",
        ),
    )

    service = AgentProfileService(override_repository=override_repo)

    scoped_ids = {
        agent.agent_id
        for agent in service.list_agents(
            view="business",
            industry_instance_id="industry-v1-ops",
        )
    }
    assert scoped_ids == {"industry-ops-agent"}


def test_agent_profile_service_backfills_industry_baseline_capabilities(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    override_repo = SqliteAgentProfileOverrideRepository(store)
    override_repo.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="industry-researcher-ops",
            name="Ops Researcher",
            role_name="Industry Researcher",
            industry_instance_id="industry-v1-ops",
            industry_role_id="researcher",
            capabilities=["tool:read_file"],
        ),
    )
    override_repo.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="industry-execution-core-ops",
            name="白泽执行中枢",
            role_name="白泽执行中枢",
            industry_instance_id="industry-v1-ops",
            industry_role_id="execution-core",
            capabilities=[],
        ),
    )

    service = AgentProfileService(override_repository=override_repo)
    updated = service.backfill_industry_baseline_capabilities()
    assert updated == 2

    researcher = override_repo.get_override("industry-researcher-ops")
    assert researcher is not None
    assert "system:dispatch_query" in (researcher.capabilities or [])
    assert "tool:browser_use" in (researcher.capabilities or [])
    assert "tool:edit_file" in (researcher.capabilities or [])
    assert "tool:write_file" in (researcher.capabilities or [])
    assert "tool:get_current_time" in (researcher.capabilities or [])
    assert "tool:read_file" in (researcher.capabilities or [])
    assert "tool:execute_shell_command" in (researcher.capabilities or [])

    execution_core = override_repo.get_override("industry-execution-core-ops")
    assert execution_core is not None
    assert "system:dispatch_query" in (execution_core.capabilities or [])
    assert "system:dispatch_goal" not in (execution_core.capabilities or [])
    assert "system:dispatch_active_goals" not in (execution_core.capabilities or [])
    assert "system:delegate_task" not in (execution_core.capabilities or [])
    assert "system:apply_role" in (execution_core.capabilities or [])
    assert "system:discover_capabilities" in (execution_core.capabilities or [])
    assert "tool:edit_file" in (execution_core.capabilities or [])
    assert "tool:execute_shell_command" in (execution_core.capabilities or [])
    assert "tool:get_current_time" in (execution_core.capabilities or [])
    assert "tool:read_file" in (execution_core.capabilities or [])
    assert "tool:write_file" in (execution_core.capabilities or [])
    assert "tool:browser_use" not in (execution_core.capabilities or [])


def test_agent_profile_service_projects_runtime_only_actor(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)
    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
        ),
    )

    service = AgentProfileService(executor_runtime_service=runtime_repo.service)
    profile = service.get_agent("agent-1")

    assert profile is not None
    assert profile.name == "Ops Agent"
    assert profile.role_name == "Operations"
    assert profile.industry_role_id == "operator"
    assert "system:dispatch_query" in profile.capabilities
    assert "tool:browser_use" in profile.capabilities


def test_agent_profile_service_capability_surface_for_runtime_only_actor(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)
    task_repo = SqliteTaskRepository(store)
    task_runtime_repo = SqliteTaskRuntimeRepository(store)
    decision_repo = SqliteDecisionRequestRepository(store)
    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
        ),
    )

    task_store = KernelTaskStore(
        task_repository=task_repo,
        task_runtime_repository=task_runtime_repo,
        decision_request_repository=decision_repo,
    )
    task = KernelTask(
        id="task-capability-review-1",
        title="Govern operator capability surface",
        capability_ref="system:apply_role",
        owner_agent_id="copaw-governance",
        risk_level="confirm",
        phase="waiting-confirm",
        payload={
            "agent_id": "agent-1",
            "capabilities": ["system:dispatch_query"],
            "actor": "runtime-center",
        },
    )
    task_store.upsert(task)
    decision_repo.upsert_decision_request(
        DecisionRequestRecord(
            id="decision-capability-review-1",
            task_id=task.id,
            decision_type="capability-governance",
            risk_level="confirm",
            summary="Review operator capability change",
            status="open",
        ),
    )

    service = AgentProfileService(
        executor_runtime_service=runtime_repo.service,
        task_repository=task_repo,
        task_runtime_repository=task_runtime_repo,
        decision_request_repository=decision_repo,
    )
    surface = service.get_capability_surface("agent-1")

    assert surface is not None
    assert surface["default_mode"] == "governed"
    assert "system:dispatch_query" in surface["baseline_capabilities"]
    assert "system:dispatch_query" in surface["effective_capabilities"]
    assert surface["pending_decisions"][0]["actions"]["review"] == (
        "/api/runtime-center/governed/decisions/decision-capability-review-1/review"
    )


def test_agent_profile_service_capability_surface_reuses_mount_lookup_instead_of_per_item_catalog_scan(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)
    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
        ),
    )

    class _CountingCapabilityService:
        def __init__(self) -> None:
            self.list_capabilities_calls = 0
            self.get_capability_calls = 0
            self._mounts = [
                SimpleNamespace(
                    id="system:dispatch_query",
                    name="dispatch_query",
                    summary="Dispatch query",
                    kind="system",
                    source_kind="system",
                    risk_level="auto",
                    enabled=True,
                    role_access_policy=[],
                    tags=["system"],
                    environment_requirements=[],
                    evidence_contract=["decision"],
                ),
                SimpleNamespace(
                    id="tool:browser_use",
                    name="browser_use",
                    summary="Browser tool",
                    kind="tool",
                    source_kind="tool",
                    risk_level="guarded",
                    enabled=True,
                    role_access_policy=[],
                    tags=["tool"],
                    environment_requirements=["browser"],
                    evidence_contract=["screenshot"],
                ),
            ]

        def list_capabilities(self, *, kind=None, enabled_only=False):
            del kind, enabled_only
            self.list_capabilities_calls += 1
            return list(self._mounts)

        def get_capability(self, capability_id: str):
            del capability_id
            self.get_capability_calls += 1
            raise AssertionError(
                "get_capability_surface should reuse a single mount lookup instead of per-item get_capability() calls",
            )

    capability_service = _CountingCapabilityService()
    service = AgentProfileService(
        executor_runtime_service=runtime_repo.service,
        capability_service=capability_service,
    )

    surface = service.get_capability_surface("agent-1")

    assert surface is not None
    item_ids = {item["id"] for item in surface["items"]}
    assert {"system:dispatch_query", "tool:browser_use"} <= item_ids
    assert capability_service.list_capabilities_calls == 1
    assert capability_service.get_capability_calls == 0


def test_agent_profile_service_capability_surface_prefers_capability_lookup_api_when_available(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)
    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
        ),
    )

    class _LookupCapabilityService:
        def __init__(self) -> None:
            self.list_capability_lookup_calls = 0
            self.list_capabilities_calls = 0
            self._mounts = [
                SimpleNamespace(
                    id="system:dispatch_query",
                    name="dispatch_query",
                    summary="Dispatch query",
                    kind="system",
                    source_kind="system",
                    risk_level="auto",
                    enabled=True,
                    role_access_policy=[],
                    tags=["system"],
                    environment_requirements=[],
                    evidence_contract=["decision"],
                ),
                SimpleNamespace(
                    id="tool:browser_use",
                    name="browser_use",
                    summary="Browser tool",
                    kind="tool",
                    source_kind="tool",
                    risk_level="guarded",
                    enabled=True,
                    role_access_policy=[],
                    tags=["tool"],
                    environment_requirements=["browser"],
                    evidence_contract=["screenshot"],
                ),
            ]

        def list_capability_lookup(self):
            self.list_capability_lookup_calls += 1
            return {mount.id: mount for mount in self._mounts}

        def list_capabilities(self, *, kind=None, enabled_only=False):
            del kind, enabled_only
            self.list_capabilities_calls += 1
            raise AssertionError(
                "get_capability_surface should prefer list_capability_lookup() when the capability service exposes it",
            )

    capability_service = _LookupCapabilityService()
    service = AgentProfileService(
        executor_runtime_service=runtime_repo.service,
        capability_service=capability_service,
    )

    surface = service.get_capability_surface("agent-1")

    assert surface is not None
    item_ids = {item["id"] for item in surface["items"]}
    assert {"system:dispatch_query", "tool:browser_use"} <= item_ids
    assert capability_service.list_capability_lookup_calls == 1
    assert capability_service.list_capabilities_calls == 0


def test_agent_profile_service_capability_surfaces_batch_reuses_lookup_once(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)
    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
        ),
    )
    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-2",
            actor_key="industry-v1-ops:runner",
            actor_fingerprint="fp-agent-2",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent 2",
            role_name="Operations",
        ),
    )

    class _LookupCapabilityService:
        def __init__(self) -> None:
            self.list_capability_lookup_calls = 0
            self.list_capabilities_calls = 0
            self._mounts = [
                SimpleNamespace(
                    id="system:dispatch_query",
                    name="dispatch_query",
                    summary="Dispatch query",
                    kind="system",
                    source_kind="system",
                    risk_level="auto",
                    enabled=True,
                    role_access_policy=[],
                    tags=["system"],
                    environment_requirements=[],
                    evidence_contract=["decision"],
                ),
                SimpleNamespace(
                    id="tool:browser_use",
                    name="browser_use",
                    summary="Browser tool",
                    kind="tool",
                    source_kind="tool",
                    risk_level="guarded",
                    enabled=True,
                    role_access_policy=[],
                    tags=["tool"],
                    environment_requirements=["browser"],
                    evidence_contract=["screenshot"],
                ),
            ]

        def list_capability_lookup(self):
            self.list_capability_lookup_calls += 1
            return {mount.id: mount for mount in self._mounts}

        def list_capabilities(self, *, kind=None, enabled_only=False):
            del kind, enabled_only
            self.list_capabilities_calls += 1
            raise AssertionError(
                "get_capability_surfaces should reuse a single list_capability_lookup() call",
            )

    capability_service = _LookupCapabilityService()
    service = AgentProfileService(
        executor_runtime_service=runtime_repo.service,
        capability_service=capability_service,
    )

    surfaces = service.get_capability_surfaces(["agent-1", "agent-2"])

    assert set(surfaces) == {"agent-1", "agent-2"}
    assert {"system:dispatch_query", "tool:browser_use"} <= {
        item["id"] for item in surfaces["agent-1"]["items"]
    }
    assert {"system:dispatch_query", "tool:browser_use"} <= {
        item["id"] for item in surfaces["agent-2"]["items"]
    }
    assert capability_service.list_capability_lookup_calls == 1
    assert capability_service.list_capabilities_calls == 0


def test_agent_profile_service_builds_prompt_capability_projection(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    override_repo = SqliteAgentProfileOverrideRepository(store)
    override_repo.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="industry-execution-core-ops",
            name="白泽执行中枢",
            role_name="白泽执行中枢",
            industry_instance_id="industry-v1-ops",
            industry_role_id="execution-core",
            capabilities=["skill:test-skill", "mcp:browser"],
        ),
    )

    service = AgentProfileService(override_repository=override_repo)
    projection = service.get_prompt_capability_projection("industry-execution-core-ops")

    assert projection is not None
    assert projection["effective_count"] == 8
    assert projection["bucket_counts"]["system_dispatch"] >= 1
    assert projection["bucket_counts"]["system_governance"] >= 2
    assert projection["bucket_counts"]["tools"] == 5
    assert {item["label"] for item in projection["tools"]} == {
        "edit_file",
        "execute_shell_command",
        "get_current_time",
        "read_file",
    }
    assert any(
        item["label"] == "apply_role"
        for item in projection["system_governance"]
    )
    assert any(
        item["label"] == "discover_capabilities"
        for item in projection["system_governance"]
    )
    assert projection["skills"] == []
    assert projection["mcp"] == []


def test_agent_profile_service_hides_legacy_goal_dispatch_from_prompt_projection(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    override_repo = SqliteAgentProfileOverrideRepository(store)
    override_repo.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="industry-execution-core-ops",
            name="Execution Core",
            role_name="Execution Core",
            industry_instance_id="industry-v1-ops",
            industry_role_id="execution-core",
            capabilities=["system:dispatch_goal"],
        ),
    )

    service = AgentProfileService(override_repository=override_repo)
    projection = service.get_prompt_capability_projection("industry-execution-core-ops")

    assert projection is not None
    assert all(
        item["id"] != "system:dispatch_goal"
        for item in projection["system_dispatch"]
    )
    assert all(
        item["id"] != "system:dispatch_goal"
        for item in projection["system_governance"]
    )


def test_agent_profile_service_prefers_runtime_and_checkpoint_projection(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)
    checkpoint_repo = SqliteAgentCheckpointRepository(store)
    task_repo = SqliteTaskRepository(store)
    task_runtime_repo = SqliteTaskRuntimeRepository(store)

    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="running",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
            metadata={
                "current_focus_kind": "assignment",
                "current_focus_id": "assignment-runtime",
                "current_focus": "Runtime projected assignment",
                "current_query": {"task_id": "task-runtime"},
                "continuity": {"environment_ref": "session:industry:ops"},
                "last_query_summary": "Runtime result",
                "last_query_checkpoint_id": "checkpoint-1",
            },
        ),
    )
    checkpoint_repo.upsert_checkpoint(
        AgentCheckpointRecord(
            id="checkpoint-1",
            agent_id="agent-1",
            task_id="task-checkpoint",
            checkpoint_kind="worker-step",
            status="ready",
            phase="query-streaming",
            environment_ref="session:industry:ops",
            summary="Checkpoint summary",
            resume_payload={
                "current_focus_kind": "assignment",
                "current_focus_id": "assignment-checkpoint",
                "current_focus": "Checkpoint projected assignment",
            },
        ),
    )

    service = AgentProfileService(
        task_repository=task_repo,
        task_runtime_repository=task_runtime_repo,
        executor_runtime_service=runtime_repo.service,
        agent_checkpoint_repository=checkpoint_repo,
    )
    profile = service.get_agent("agent-1")

    assert profile is not None
    assert profile.current_focus_kind == "assignment"
    assert profile.current_focus_id == "assignment-runtime"
    assert profile.current_focus == "Runtime projected assignment"
    assert hasattr(profile, "current_goal_id") is False
    assert hasattr(profile, "current_goal") is False
    assert profile.current_task_id == "task-runtime"
    assert profile.current_mailbox_id is None
    assert profile.current_environment_id == "session:industry:ops"
    assert profile.queue_depth == 0
    assert profile.today_output_summary == "Runtime result"
    assert profile.last_checkpoint_id == "checkpoint-1"


def test_agent_profile_service_ignores_runtime_legacy_goal_focus_and_keeps_checkpoint_compat(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)
    checkpoint_repo = SqliteAgentCheckpointRepository(store)

    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="running",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
            metadata={
                "goal_id": "goal-runtime",
                "goal_title": "Legacy runtime goal",
            },
        ),
    )
    checkpoint_repo.upsert_checkpoint(
        AgentCheckpointRecord(
            id="checkpoint-1",
            agent_id="agent-1",
            checkpoint_kind="worker-step",
            status="ready",
            phase="query-streaming",
            summary="Checkpoint summary",
            resume_payload={
                "goal_id": "goal-checkpoint",
                "goal_title": "Legacy checkpoint goal",
            },
        ),
    )

    service = AgentProfileService(
        executor_runtime_service=runtime_repo.service,
        agent_checkpoint_repository=checkpoint_repo,
    )
    profile = service.get_agent("agent-1")

    assert profile is not None
    assert profile.current_focus_kind is None
    assert profile.current_focus_id is None
    assert profile.current_focus == ""


def test_agent_profile_service_does_not_overlay_current_focus_with_legacy_goal_metadata(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    override_repo = SqliteAgentProfileOverrideRepository(store)
    checkpoint_repo = SqliteAgentCheckpointRepository(store)

    override_repo.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="agent-1",
            name="Ops Agent",
            role_name="Operations",
            current_focus_kind="assignment",
            current_focus_id="assignment-stale",
            current_focus="Stale assignment",
        ),
    )
    checkpoint_repo.upsert_checkpoint(
        AgentCheckpointRecord(
            id="checkpoint-1",
            agent_id="agent-1",
            checkpoint_kind="worker-step",
            status="ready",
            phase="query-streaming",
            summary="Checkpoint summary",
            resume_payload={
                "goal_id": "goal-checkpoint",
                "goal_title": "Legacy checkpoint goal",
            },
        ),
    )

    service = AgentProfileService(
        override_repository=override_repo,
        agent_checkpoint_repository=checkpoint_repo,
    )
    profile = service.get_agent("agent-1")

    assert profile is not None
    assert profile.current_focus_kind == "assignment"
    assert profile.current_focus_id == "assignment-stale"
    assert profile.current_focus == "Stale assignment"


def test_agent_profile_service_uses_checkpoint_current_focus_when_runtime_focus_missing(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)
    checkpoint_repo = SqliteAgentCheckpointRepository(store)

    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="running",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
            metadata={},
        ),
    )
    checkpoint_repo.upsert_checkpoint(
        AgentCheckpointRecord(
            id="checkpoint-1",
            agent_id="agent-1",
            checkpoint_kind="worker-step",
            status="ready",
            phase="query-streaming",
            summary="Checkpoint summary",
            resume_payload={
                "current_focus_kind": "assignment",
                "current_focus_id": "assignment-checkpoint",
                "current_focus": "Checkpoint projected assignment",
            },
        ),
    )

    service = AgentProfileService(
        executor_runtime_service=runtime_repo.service,
        agent_checkpoint_repository=checkpoint_repo,
    )
    profile = service.get_agent("agent-1")

    assert profile is not None
    assert profile.current_focus_kind == "assignment"
    assert profile.current_focus_id == "assignment-checkpoint"
    assert profile.current_focus == "Checkpoint projected assignment"


def test_agent_profile_service_uses_checkpoint_current_focus_when_runtime_missing(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    override_repo = SqliteAgentProfileOverrideRepository(store)
    checkpoint_repo = SqliteAgentCheckpointRepository(store)
    override_repo.upsert_override(
        AgentProfileOverrideRecord(
            agent_id="agent-1",
            name="Ops Agent",
            role_name="Operations",
        ),
    )
    checkpoint_repo.upsert_checkpoint(
        AgentCheckpointRecord(
            id="checkpoint-1",
            agent_id="agent-1",
            checkpoint_kind="worker-step",
            status="ready",
            phase="query-streaming",
            summary="Checkpoint summary",
            resume_payload={
                "current_focus_kind": "assignment",
                "current_focus_id": "assignment-checkpoint",
                "current_focus": "Checkpoint projected assignment",
            },
        ),
    )

    service = AgentProfileService(
        override_repository=override_repo,
        agent_checkpoint_repository=checkpoint_repo,
    )
    profile = service.get_agent("agent-1")

    assert profile is not None
    assert profile.current_focus_kind == "assignment"
    assert profile.current_focus_id == "assignment-checkpoint"
    assert profile.current_focus == "Checkpoint projected assignment"


def test_agent_profile_service_ignores_legacy_focus_alias_fields_without_current_focus_contract(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)

    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-legacy-focus",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-legacy-focus",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
            metadata={
                "focus_kind": "goal",
                "focus_id": "goal-legacy",
                "focus_title": "Legacy focus title",
                "focus": "Legacy focus summary",
            },
        ),
    )

    service = AgentProfileService(executor_runtime_service=runtime_repo.service)
    profile = service.get_agent("agent-legacy-focus")

    assert profile is not None
    assert profile.current_focus_kind is None
    assert profile.current_focus_id is None
    assert profile.current_focus == ""


def test_agent_profile_service_detail_stats_drop_goal_count(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)
    task_repo = SqliteTaskRepository(store)
    task_runtime_repo = SqliteTaskRuntimeRepository(store)

    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
        ),
    )
    task_repo.upsert_task(
        TaskRecord(
            id="task-1",
            owner_agent_id="agent-1",
            title="Review backlog",
            summary="Summarize the next operating move.",
            task_type="assignment-step",
            goal_id="goal-1",
            status="completed",
        ),
    )

    service = AgentProfileService(
        task_repository=task_repo,
        task_runtime_repository=task_runtime_repo,
        executor_runtime_service=runtime_repo.service,
    )
    detail = service.get_agent_detail("agent-1")

    assert detail is not None
    assert detail["stats"]["task_count"] == 1
    assert "goal_count" not in detail["stats"]


def test_agent_profile_service_detail_reuses_canonical_evidence_projection(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)
    task_repo = SqliteTaskRepository(store)
    task_runtime_repo = SqliteTaskRuntimeRepository(store)
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")

    runtime_repo.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
        ),
    )
    task_repo.upsert_task(
        TaskRecord(
            id="task-1",
            owner_agent_id="agent-1",
            title="Write report file",
            summary="Persist the latest operator report.",
            task_type="assignment-step",
            status="completed",
        ),
    )
    evidence_ledger.append(
        EvidenceRecord(
            id="evidence-1",
            task_id="task-1",
            actor_ref="agent-1",
            environment_ref="session:web:main",
            capability_ref="tool:write_file",
            risk_level="auto",
            action_summary="Write report file",
            result_summary="Saved the latest operator report.",
            created_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
            metadata={"child_task_id": "task-child-1"},
            artifacts=(
                ArtifactRecord(
                    id="artifact-1",
                    artifact_type="file",
                    storage_uri="file:///tmp/report.md",
                    summary="Operator report file",
                ),
            ),
            replay_pointers=(
                ReplayPointer(
                    id="replay-1",
                    replay_type="browser",
                    storage_uri="replay://trace-1",
                    summary="Browser replay",
                ),
            ),
        ),
    )

    service = AgentProfileService(
        task_repository=task_repo,
        task_runtime_repository=task_runtime_repo,
        executor_runtime_service=runtime_repo.service,
        evidence_ledger=evidence_ledger,
    )
    detail = service.get_agent_detail("agent-1")

    assert detail is not None
    evidence = detail["evidence"][0]
    assert evidence["metadata"]["child_task_id"] == "task-child-1"
    assert evidence["artifact_count"] == 1
    assert evidence["replay_count"] == 1
    assert evidence["artifacts"] == [
        {
            "id": "artifact-1",
            "artifact_type": "file",
            "storage_uri": "file:///tmp/report.md",
            "summary": "Operator report file",
        }
    ]
    assert evidence["replay_pointers"] == [
        {
            "id": "replay-1",
            "replay_type": "browser",
            "storage_uri": "replay://trace-1",
            "summary": "Browser replay",
        }
    ]
