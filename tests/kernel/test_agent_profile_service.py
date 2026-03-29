# -*- coding: utf-8 -*-
from copaw.kernel.agent_profile_service import AgentProfileService
from copaw.state import (
    AgentCheckpointRecord,
    AgentMailboxRecord,
    AgentProfileOverrideRecord,
    AgentRuntimeRecord,
    TaskRecord,
    SQLiteStateStore,
)
from copaw.state.repositories import (
    SqliteAgentCheckpointRepository,
    SqliteAgentMailboxRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteAgentRuntimeRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
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
    assert "system:delegate_task" in (execution_core.capabilities or [])
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

    service = AgentProfileService(agent_runtime_repository=runtime_repo)
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

    service = AgentProfileService(agent_runtime_repository=runtime_repo)
    surface = service.get_capability_surface("agent-1")

    assert surface is not None
    assert surface["default_mode"] == "governed"
    assert "system:dispatch_query" in surface["baseline_capabilities"]
    assert "system:dispatch_query" in surface["effective_capabilities"]


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
    assert projection["effective_count"] == 9
    assert projection["bucket_counts"]["system_dispatch"] >= 2
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


def test_agent_profile_service_prefers_runtime_mailbox_checkpoint_projection(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repo = SqliteAgentRuntimeRepository(store)
    mailbox_repo = SqliteAgentMailboxRepository(store)
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
            current_task_id="task-runtime",
            current_mailbox_id="mailbox-1",
            current_environment_id="session:industry:ops",
            queue_depth=1,
            last_result_summary="Runtime result",
            metadata={
                "goal_id": "goal-runtime",
                "goal_title": "Runtime projected goal",
            },
        ),
    )
    mailbox_repo.upsert_item(
        AgentMailboxRecord(
            id="mailbox-1",
            agent_id="agent-1",
            task_id="task-mailbox",
            title="Mailbox task",
            summary="Mailbox summary",
            status="running",
            capability_ref="system:dispatch_query",
            payload={"environment_ref": "session:industry:ops"},
            metadata={"goal_id": "goal-mailbox", "goal_title": "Mailbox goal"},
        ),
    )
    checkpoint_repo.upsert_checkpoint(
        AgentCheckpointRecord(
            id="checkpoint-1",
            agent_id="agent-1",
            mailbox_id="mailbox-1",
            task_id="task-checkpoint",
            checkpoint_kind="worker-step",
            status="ready",
            phase="query-streaming",
            environment_ref="session:industry:ops",
            summary="Checkpoint summary",
            resume_payload={"goal_id": "goal-checkpoint", "goal_title": "Checkpoint goal"},
        ),
    )

    service = AgentProfileService(
        task_repository=task_repo,
        task_runtime_repository=task_runtime_repo,
        agent_runtime_repository=runtime_repo,
        agent_mailbox_repository=mailbox_repo,
        agent_checkpoint_repository=checkpoint_repo,
    )
    profile = service.get_agent("agent-1")

    assert profile is not None
    assert profile.current_focus_kind == "goal"
    assert profile.current_focus_id == "goal-runtime"
    assert profile.current_focus == "Runtime projected goal"
    assert profile.current_goal_id == "goal-runtime"
    assert profile.current_goal == "Runtime projected goal"
    assert profile.current_task_id == "task-runtime"
    assert profile.current_mailbox_id == "mailbox-1"
    assert profile.current_environment_id == "session:industry:ops"
    assert profile.queue_depth == 1
    assert profile.today_output_summary == "Runtime result"
    assert profile.last_checkpoint_id == "checkpoint-1"


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
        agent_runtime_repository=runtime_repo,
    )
    detail = service.get_agent_detail("agent-1")

    assert detail is not None
    assert detail["stats"]["task_count"] == 1
    assert "goal_count" not in detail["stats"]
