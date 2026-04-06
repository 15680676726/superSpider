# -*- coding: utf-8 -*-
"""Abstract repositories for the state layer."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence

from ..models import (
    AgentCheckpointRecord,
    AgentLeaseRecord,
    AgentMailboxRecord,
    AgentReportRecord,
    AssignmentRecord,
    AgentRuntimeRecord,
    AgentThreadBindingRecord,
    AutomationLoopRuntimeRecord,
    BacklogItemRecord,
    DecisionRequestRecord,
    ExecutionRoutineRecord,
    FixedSopBindingRecord,
    FixedSopTemplateRecord,
    GovernanceControlRecord,
    GoalRecord,
    HumanAssistTaskRecord,
    IndustryInstanceRecord,
    MediaAnalysisRecord,
    OperatingCycleRecord,
    OperatingLaneRecord,
    PredictionCaseRecord,
    PredictionRecommendationRecord,
    PredictionReviewRecord,
    PredictionScenarioRecord,
    PredictionSignalRecord,
    RuntimeFrameRecord,
    RoutineRunRecord,
    ScheduleRecord,
    StrategyMemoryRecord,
    TaskRecord,
    TaskRuntimeRecord,
    WorkflowPresetRecord,
    WorkflowRunRecord,
    WorkflowTemplateRecord,
)
from ..models_external_runtime import ExternalCapabilityRuntimeInstanceRecord
from ..models_knowledge import KnowledgeChunkRecord
from ..models_memory import (
    MemoryEntityViewRecord,
    MemoryFactIndexRecord,
    MemoryOpinionViewRecord,
    MemoryRelationViewRecord,
    MemoryReflectionRunRecord,
)
from ..models_work_context import WorkContextRecord


class BaseAgentRuntimeRepository(ABC):
    """Abstract repository for persisted actor runtime records."""

    @abstractmethod
    def get_runtime(self, agent_id: str) -> Optional[AgentRuntimeRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_runtimes(
        self,
        *,
        runtime_status: str | None = None,
        desired_state: str | None = None,
        industry_instance_id: str | None = None,
        limit: int | None = None,
    ) -> list[AgentRuntimeRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_runtime(self, runtime: AgentRuntimeRecord) -> AgentRuntimeRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_runtime(self, agent_id: str) -> bool:
        raise NotImplementedError


class BaseAgentMailboxRepository(ABC):
    """Abstract repository for actor mailbox entries."""

    @abstractmethod
    def get_item(self, item_id: str) -> Optional[AgentMailboxRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_items(
        self,
        *,
        agent_id: str | None = None,
        status: str | None = None,
        conversation_thread_id: str | None = None,
        work_context_id: str | None = None,
        limit: int | None = None,
    ) -> list[AgentMailboxRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_item(self, item: AgentMailboxRecord) -> AgentMailboxRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_item(self, item_id: str) -> bool:
        raise NotImplementedError


class BaseAgentCheckpointRepository(ABC):
    """Abstract repository for actor execution checkpoints."""

    @abstractmethod
    def get_checkpoint(self, checkpoint_id: str) -> Optional[AgentCheckpointRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_checkpoints(
        self,
        *,
        agent_id: str | None = None,
        mailbox_id: str | None = None,
        task_id: str | None = None,
        work_context_id: str | None = None,
        limit: int | None = None,
    ) -> list[AgentCheckpointRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_checkpoint(
        self,
        checkpoint: AgentCheckpointRecord,
    ) -> AgentCheckpointRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        raise NotImplementedError


class BaseAgentLeaseRepository(ABC):
    """Abstract repository for persisted actor lease records."""

    @abstractmethod
    def get_lease(self, lease_id: str) -> Optional[AgentLeaseRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_leases(
        self,
        *,
        agent_id: str | None = None,
        lease_status: str | None = None,
        lease_kind: str | None = None,
        limit: int | None = None,
    ) -> list[AgentLeaseRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_lease(self, lease: AgentLeaseRecord) -> AgentLeaseRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_lease(self, lease_id: str) -> bool:
        raise NotImplementedError


class BaseAgentThreadBindingRepository(ABC):
    """Abstract repository for actor-first thread binding records."""

    @abstractmethod
    def get_binding(self, thread_id: str) -> Optional[AgentThreadBindingRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_bindings(
        self,
        *,
        agent_id: str | None = None,
        industry_instance_id: str | None = None,
        work_context_id: str | None = None,
        active_only: bool = False,
        limit: int | None = None,
    ) -> list[AgentThreadBindingRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_binding(
        self,
        binding: AgentThreadBindingRecord,
    ) -> AgentThreadBindingRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_binding(self, thread_id: str) -> bool:
        raise NotImplementedError


class BaseAutomationLoopRuntimeRepository(ABC):
    """Abstract repository for durable automation-loop runtime snapshots."""

    @abstractmethod
    def get_loop(self, automation_task_id: str) -> Optional[AutomationLoopRuntimeRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_loops(
        self,
        *,
        owner_agent_id: str | None = None,
        health_status: str | None = None,
        limit: int | None = None,
    ) -> list[AutomationLoopRuntimeRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_loop(
        self,
        loop: AutomationLoopRuntimeRecord,
    ) -> AutomationLoopRuntimeRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_loop(self, automation_task_id: str) -> bool:
        raise NotImplementedError


class BaseGoalRepository(ABC):
    """Abstract repository for goal records."""

    @abstractmethod
    def get_goal(self, goal_id: str) -> Optional[GoalRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_goals(
        self,
        *,
        status: str | None = None,
        owner_scope: str | None = None,
        industry_instance_id: str | None = None,
        goal_ids: Sequence[str] | None = None,
        activity_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[GoalRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_goal(self, goal: GoalRecord) -> GoalRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_goal(self, goal_id: str) -> bool:
        raise NotImplementedError


class BaseWorkContextRepository(ABC):
    """Abstract repository for formal continuous work boundaries."""

    @abstractmethod
    def get_context(self, context_id: str) -> Optional[WorkContextRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_by_context_key(self, context_key: str) -> Optional[WorkContextRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_contexts(
        self,
        *,
        context_type: str | None = None,
        status: str | None = None,
        context_key: str | None = None,
        owner_scope: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        primary_thread_id: str | None = None,
        parent_work_context_id: str | None = None,
        source_kind: str | None = None,
        source_ref: str | None = None,
        limit: int | None = None,
    ) -> list[WorkContextRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_context(self, context: WorkContextRecord) -> WorkContextRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_context(self, context_id: str) -> bool:
        raise NotImplementedError


class BaseExternalCapabilityRuntimeRepository(ABC):
    @abstractmethod
    def get_runtime(
        self,
        runtime_id: str,
    ) -> Optional[ExternalCapabilityRuntimeInstanceRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_runtimes(
        self,
        *,
        capability_id: str | None = None,
        runtime_kind: str | None = None,
        scope_kind: str | None = None,
        status: str | None = None,
        owner_agent_id: str | None = None,
        session_mount_id: str | None = None,
        work_context_id: str | None = None,
        environment_ref: str | None = None,
        limit: int | None = None,
    ) -> list[ExternalCapabilityRuntimeInstanceRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_runtime(
        self,
        runtime: ExternalCapabilityRuntimeInstanceRecord,
    ) -> ExternalCapabilityRuntimeInstanceRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_runtime(self, runtime_id: str) -> bool:
        raise NotImplementedError


class BaseTaskRepository(ABC):
    """Abstract repository for task records."""

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_tasks(
        self,
        *,
        goal_id: str | None = None,
        industry_instance_id: str | None = None,
        assignment_id: str | None = None,
        lane_id: str | None = None,
        cycle_id: str | None = None,
        status: str | None = None,
        owner_agent_id: str | None = None,
        parent_task_id: str | None = None,
        work_context_id: str | None = None,
        task_type: str | None = None,
        goal_ids: Sequence[str] | None = None,
        assignment_ids: Sequence[str] | None = None,
        task_ids: Sequence[str] | None = None,
        owner_agent_ids: Sequence[str] | None = None,
        acceptance_criteria_like: str | None = None,
        activity_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[TaskRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_task(self, task: TaskRecord) -> TaskRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        raise NotImplementedError


class BaseHumanAssistTaskRepository(ABC):
    """Abstract repository for formal host-side assist tasks."""

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[HumanAssistTaskRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_tasks(
        self,
        *,
        profile_id: str | None = None,
        chat_thread_id: str | None = None,
        industry_instance_id: str | None = None,
        assignment_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[HumanAssistTaskRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_task(self, task: HumanAssistTaskRecord) -> HumanAssistTaskRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        raise NotImplementedError


class BaseTaskRuntimeRepository(ABC):
    """Abstract repository for task runtime records."""

    @abstractmethod
    def get_runtime(self, task_id: str) -> Optional[TaskRuntimeRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_runtimes(
        self,
        *,
        runtime_status: str | None = None,
        risk_level: str | None = None,
        task_ids: Sequence[str] | None = None,
        last_owner_agent_ids: Sequence[str] | None = None,
        updated_since: datetime | None = None,
    ) -> list[TaskRuntimeRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_runtime(self, runtime: TaskRuntimeRecord) -> TaskRuntimeRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_runtime(self, task_id: str) -> bool:
        raise NotImplementedError


class BaseRuntimeFrameRepository(ABC):
    """Abstract repository for runtime frame records."""

    @abstractmethod
    def get_frame(self, frame_id: str) -> Optional[RuntimeFrameRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_frames(
        self,
        task_id: str,
        *,
        limit: int | None = None,
    ) -> list[RuntimeFrameRecord]:
        raise NotImplementedError

    @abstractmethod
    def append_frame(self, frame: RuntimeFrameRecord) -> RuntimeFrameRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_frame(self, frame_id: str) -> bool:
        raise NotImplementedError


class BaseScheduleRepository(ABC):
    """Abstract repository for schedule projection records."""

    @abstractmethod
    def get_schedule(self, schedule_id: str) -> Optional[ScheduleRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_schedules(
        self,
        *,
        status: str | None = None,
        enabled: bool | None = None,
        limit: int | None = None,
    ) -> list[ScheduleRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_schedule(self, schedule: ScheduleRecord) -> ScheduleRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_schedule(self, schedule_id: str) -> bool:
        raise NotImplementedError


class BaseWorkflowPresetRepository(ABC):
    """Abstract repository for workflow preset records."""

    @abstractmethod
    def get_preset(self, preset_id: str) -> Optional[WorkflowPresetRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_presets(
        self,
        *,
        template_id: str,
        industry_scope: str | None = None,
        owner_scope: str | None = None,
    ) -> list[WorkflowPresetRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_preset(self, preset: WorkflowPresetRecord) -> WorkflowPresetRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_preset(self, preset_id: str) -> bool:
        raise NotImplementedError


class BaseDecisionRequestRepository(ABC):
    """Abstract repository for decision request records."""

    @abstractmethod
    def get_decision_request(
        self,
        decision_id: str,
    ) -> Optional[DecisionRequestRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_decision_requests(
        self,
        *,
        task_id: str | None = None,
        status: str | None = None,
        task_ids: Sequence[str] | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[DecisionRequestRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_decision_request(
        self,
        decision: DecisionRequestRecord,
    ) -> DecisionRequestRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_decision_request(self, decision_id: str) -> bool:
        raise NotImplementedError


class BaseGovernanceControlRepository(ABC):
    """Abstract repository for runtime governance controls."""

    @abstractmethod
    def get_control(self, control_id: str = "runtime") -> Optional[GovernanceControlRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_control(
        self,
        control: GovernanceControlRecord,
    ) -> GovernanceControlRecord:
        raise NotImplementedError


class BaseIndustryInstanceRepository(ABC):
    """Abstract repository for formal industry instance records."""

    @abstractmethod
    def get_instance(self, instance_id: str) -> Optional[IndustryInstanceRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_instances(
        self,
        *,
        owner_scope: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[IndustryInstanceRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_instance(
        self,
        instance: IndustryInstanceRecord,
    ) -> IndustryInstanceRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_instance(self, instance_id: str) -> bool:
        raise NotImplementedError


class BaseMediaAnalysisRepository(ABC):
    """Abstract repository for persisted media analyses."""

    @abstractmethod
    def get_analysis(self, analysis_id: str) -> Optional[MediaAnalysisRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_analyses(
        self,
        *,
        industry_instance_id: str | None = None,
        thread_id: str | None = None,
        work_context_id: str | None = None,
        entry_point: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MediaAnalysisRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_analysis(
        self,
        analysis: MediaAnalysisRecord,
    ) -> MediaAnalysisRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_analysis(self, analysis_id: str) -> bool:
        raise NotImplementedError


class BaseOperatingLaneRepository(ABC):
    """Abstract repository for long-lived operating lanes."""

    @abstractmethod
    def get_lane(self, lane_id: str) -> Optional[OperatingLaneRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_lanes(
        self,
        *,
        industry_instance_id: str | None = None,
        status: str | None = None,
        owner_agent_id: str | None = None,
        limit: int | None = None,
    ) -> list[OperatingLaneRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_lane(self, lane: OperatingLaneRecord) -> OperatingLaneRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_lane(self, lane_id: str) -> bool:
        raise NotImplementedError


class BaseBacklogItemRepository(ABC):
    """Abstract repository for main-brain backlog items."""

    @abstractmethod
    def get_item(self, item_id: str) -> Optional[BacklogItemRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_items(
        self,
        *,
        industry_instance_id: str | None = None,
        lane_id: str | None = None,
        cycle_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[BacklogItemRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_item(self, item: BacklogItemRecord) -> BacklogItemRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_item(self, item_id: str) -> bool:
        raise NotImplementedError


class BaseOperatingCycleRepository(ABC):
    """Abstract repository for operating cycle records."""

    @abstractmethod
    def get_cycle(self, cycle_id: str) -> Optional[OperatingCycleRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_cycles(
        self,
        *,
        industry_instance_id: str | None = None,
        cycle_kind: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[OperatingCycleRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_cycle(self, cycle: OperatingCycleRecord) -> OperatingCycleRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_cycle(self, cycle_id: str) -> bool:
        raise NotImplementedError


class BaseAssignmentRepository(ABC):
    """Abstract repository for cycle-to-agent assignments."""

    @abstractmethod
    def get_assignment(self, assignment_id: str) -> Optional[AssignmentRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_assignments(
        self,
        *,
        industry_instance_id: str | None = None,
        cycle_id: str | None = None,
        lane_id: str | None = None,
        goal_id: str | None = None,
        owner_agent_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[AssignmentRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_assignment(self, assignment: AssignmentRecord) -> AssignmentRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_assignment(self, assignment_id: str) -> bool:
        raise NotImplementedError


class BaseAgentReportRepository(ABC):
    """Abstract repository for structured agent reports."""

    @abstractmethod
    def get_report(self, report_id: str) -> Optional[AgentReportRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_reports(
        self,
        *,
        industry_instance_id: str | None = None,
        cycle_id: str | None = None,
        assignment_id: str | None = None,
        task_id: str | None = None,
        work_context_id: str | None = None,
        owner_agent_id: str | None = None,
        status: str | None = None,
        processed: bool | None = None,
        limit: int | None = None,
    ) -> list[AgentReportRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_report(self, report: AgentReportRecord) -> AgentReportRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_report(self, report_id: str) -> bool:
        raise NotImplementedError


class BaseFixedSopTemplateRepository(ABC):
    """Abstract repository for native fixed SOP templates."""

    @abstractmethod
    def get_template(self, template_id: str) -> Optional[FixedSopTemplateRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_templates(
        self,
        *,
        status: str | None = None,
    ) -> list[FixedSopTemplateRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_template(
        self,
        template: FixedSopTemplateRecord,
    ) -> FixedSopTemplateRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_template(self, template_id: str) -> bool:
        raise NotImplementedError


class BaseFixedSopBindingRepository(ABC):
    """Abstract repository for installed native fixed SOP bindings."""

    @abstractmethod
    def get_binding(self, binding_id: str) -> Optional[FixedSopBindingRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_bindings(
        self,
        *,
        template_id: str | None = None,
        status: str | None = None,
        industry_instance_id: str | None = None,
        owner_agent_id: str | None = None,
        limit: int | None = None,
    ) -> list[FixedSopBindingRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_binding(
        self,
        binding: FixedSopBindingRecord,
    ) -> FixedSopBindingRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_binding(self, binding_id: str) -> bool:
        raise NotImplementedError


class BaseWorkflowTemplateRepository(ABC):
    """Abstract repository for workflow template records."""

    @abstractmethod
    def get_template(self, template_id: str) -> Optional[WorkflowTemplateRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_templates(
        self,
        *,
        category: str | None = None,
        status: str | None = None,
    ) -> list[WorkflowTemplateRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_template(
        self,
        template: WorkflowTemplateRecord,
    ) -> WorkflowTemplateRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_template(self, template_id: str) -> bool:
        raise NotImplementedError


class BaseWorkflowRunRepository(ABC):
    """Abstract repository for workflow run records."""

    @abstractmethod
    def get_run(self, run_id: str) -> Optional[WorkflowRunRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_runs(
        self,
        *,
        template_id: str | None = None,
        status: str | None = None,
        industry_instance_id: str | None = None,
    ) -> list[WorkflowRunRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_run(self, run: WorkflowRunRecord) -> WorkflowRunRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_run(self, run_id: str) -> bool:
        raise NotImplementedError


class BaseExecutionRoutineRepository(ABC):
    """Abstract repository for execution routine records."""

    @abstractmethod
    def get_routine(self, routine_id: str) -> Optional[ExecutionRoutineRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_routines(
        self,
        *,
        status: str | None = None,
        owner_scope: str | None = None,
        owner_agent_id: str | None = None,
        engine_kind: str | None = None,
        trigger_kind: str | None = None,
        routine_ids: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[ExecutionRoutineRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_routine(
        self,
        routine: ExecutionRoutineRecord,
    ) -> ExecutionRoutineRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_routine(self, routine_id: str) -> bool:
        raise NotImplementedError


class BaseRoutineRunRepository(ABC):
    """Abstract repository for routine replay runs."""

    @abstractmethod
    def get_run(self, run_id: str) -> Optional[RoutineRunRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_runs(
        self,
        *,
        routine_id: str | None = None,
        status: str | None = None,
        source_type: str | None = None,
        owner_agent_id: str | None = None,
        failure_class: str | None = None,
        limit: int | None = None,
    ) -> list[RoutineRunRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_run(self, run: RoutineRunRecord) -> RoutineRunRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_run(self, run_id: str) -> bool:
        raise NotImplementedError


class BasePredictionCaseRepository(ABC):
    """Abstract repository for persisted prediction cases."""

    @abstractmethod
    def get_case(self, case_id: str) -> Optional[PredictionCaseRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_cases(
        self,
        *,
        case_kind: str | None = None,
        status: str | None = None,
        industry_instance_id: str | None = None,
        owner_scope: str | None = None,
        owner_agent_id: str | None = None,
        case_ids: Sequence[str] | None = None,
        activity_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[PredictionCaseRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_case(self, record: PredictionCaseRecord) -> PredictionCaseRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_case(self, case_id: str) -> bool:
        raise NotImplementedError


class BasePredictionScenarioRepository(ABC):
    """Abstract repository for prediction scenarios."""

    @abstractmethod
    def get_scenario(self, scenario_id: str) -> Optional[PredictionScenarioRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_scenarios(
        self,
        *,
        case_id: str,
    ) -> list[PredictionScenarioRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_scenario(
        self,
        record: PredictionScenarioRecord,
    ) -> PredictionScenarioRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_scenario(self, scenario_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete_for_case(self, case_id: str) -> int:
        raise NotImplementedError


class BasePredictionSignalRepository(ABC):
    """Abstract repository for prediction signals."""

    @abstractmethod
    def get_signal(self, signal_id: str) -> Optional[PredictionSignalRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_signals(
        self,
        *,
        case_id: str,
    ) -> list[PredictionSignalRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_signal(self, record: PredictionSignalRecord) -> PredictionSignalRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_signal(self, signal_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete_for_case(self, case_id: str) -> int:
        raise NotImplementedError


class BasePredictionRecommendationRepository(ABC):
    """Abstract repository for prediction recommendations."""

    @abstractmethod
    def get_recommendation(
        self,
        recommendation_id: str,
    ) -> Optional[PredictionRecommendationRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_recommendations(
        self,
        *,
        case_id: str | None = None,
        case_ids: Sequence[str] | None = None,
        status: str | None = None,
        auto_eligible: bool | None = None,
        target_agent_id: str | None = None,
        activity_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[PredictionRecommendationRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_recommendation(
        self,
        record: PredictionRecommendationRecord,
    ) -> PredictionRecommendationRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_recommendation(self, recommendation_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete_for_case(self, case_id: str) -> int:
        raise NotImplementedError


class BasePredictionReviewRepository(ABC):
    """Abstract repository for prediction reviews."""

    @abstractmethod
    def get_review(self, review_id: str) -> Optional[PredictionReviewRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_reviews(
        self,
        *,
        case_id: str | None = None,
        case_ids: Sequence[str] | None = None,
        recommendation_id: str | None = None,
        activity_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[PredictionReviewRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_review(self, record: PredictionReviewRecord) -> PredictionReviewRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_review(self, review_id: str) -> bool:
        raise NotImplementedError


class BaseStrategyMemoryRepository(ABC):
    """Abstract repository for formal strategy memory records."""

    @abstractmethod
    def get_strategy(self, strategy_id: str) -> Optional[StrategyMemoryRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_strategies(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[StrategyMemoryRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_strategy(self, record: StrategyMemoryRecord) -> StrategyMemoryRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_strategy(self, strategy_id: str) -> bool:
        raise NotImplementedError


class BaseKnowledgeChunkRepository(ABC):
    """Abstract repository for formal knowledge chunks."""

    @abstractmethod
    def get_chunk(self, chunk_id: str) -> Optional[KnowledgeChunkRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_chunks(
        self,
        *,
        document_id: str | None = None,
    ) -> list[KnowledgeChunkRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_chunk(self, chunk: KnowledgeChunkRecord) -> KnowledgeChunkRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_chunk(self, chunk_id: str) -> bool:
        raise NotImplementedError


class BaseMemoryFactIndexRepository(ABC):
    """Abstract repository for rebuildable memory fact index entries."""

    @abstractmethod
    def get_entry(self, entry_id: str) -> Optional[MemoryFactIndexRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_entries(
        self,
        *,
        source_type: str | None = None,
        source_ref: str | None = None,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryFactIndexRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_entry(self, record: MemoryFactIndexRecord) -> MemoryFactIndexRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_entry(self, entry_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete_by_source(self, *, source_type: str, source_ref: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def clear(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> int:
        raise NotImplementedError


class BaseMemoryEntityViewRepository(ABC):
    """Abstract repository for compiled memory entity views."""

    @abstractmethod
    def get_view(
        self,
        entity_id: str,
    ) -> Optional[MemoryEntityViewRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_views(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        entity_key: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryEntityViewRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_view(
        self,
        record: MemoryEntityViewRecord,
    ) -> MemoryEntityViewRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_view(self, entity_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def clear(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> int:
        raise NotImplementedError


class BaseMemoryOpinionViewRepository(ABC):
    """Abstract repository for compiled memory opinion/confidence views."""

    @abstractmethod
    def get_view(
        self,
        opinion_id: str,
    ) -> Optional[MemoryOpinionViewRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_views(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        subject_key: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryOpinionViewRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_view(
        self,
        record: MemoryOpinionViewRecord,
    ) -> MemoryOpinionViewRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_view(self, opinion_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def clear(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> int:
        raise NotImplementedError


class BaseMemoryRelationViewRepository(ABC):
    """Abstract repository for compiled memory relation views."""

    @abstractmethod
    def get_view(
        self,
        relation_id: str,
    ) -> Optional[MemoryRelationViewRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_views(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        relation_kind: str | None = None,
        source_node_id: str | None = None,
        target_node_id: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryRelationViewRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_view(
        self,
        record: MemoryRelationViewRecord,
    ) -> MemoryRelationViewRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_view(self, relation_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def clear(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> int:
        raise NotImplementedError


class BaseMemoryReflectionRunRepository(ABC):
    """Abstract repository for memory reflection job records."""

    @abstractmethod
    def get_run(
        self,
        run_id: str,
    ) -> Optional[MemoryReflectionRunRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_runs(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryReflectionRunRecord]:
        raise NotImplementedError

    @abstractmethod
    def upsert_run(
        self,
        record: MemoryReflectionRunRecord,
    ) -> MemoryReflectionRunRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_run(self, run_id: str) -> bool:
        raise NotImplementedError
