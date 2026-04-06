# -*- coding: utf-8 -*-
from __future__ import annotations
import json
from collections.abc import Mapping
from hashlib import sha1
from .service_context import *  # noqa: F401,F403
from .service_recommendation_search import *  # noqa: F401,F403
from .service_recommendation_pack import *  # noqa: F401,F403
from ..compiler.planning import (
    AssignmentPlanningCompiler,
    CyclePlanningCompiler,
    PlanningStrategyConstraints,
    ReportReplanEngine,
    StrategyPlanningCompiler,
    build_uncertainty_register_payload,
)
from ..compiler.models import CompilationUnit
from ..kernel import KernelTask
from ..state.strategy_memory_service import resolve_strategy_payload
from .service_report_closure import (
    build_agent_report_control_thread_message as _build_agent_report_control_thread_message_helper,
    build_report_followup_metadata as _build_report_followup_metadata_helper,
    merge_report_followup_metadata as _merge_report_followup_metadata_helper,
    persist_cycle_report_synthesis as _persist_cycle_report_synthesis_helper,
    record_report_synthesis_backlog as _record_report_synthesis_backlog_helper,
    resolve_report_followup_metadata as _resolve_report_followup_metadata_helper,
    synthesize_agent_reports as _synthesize_agent_reports_helper,
    write_agent_report_back_to_control_thread as _write_agent_report_back_to_control_thread_helper,
)
from .seat_gap_policy import resolve_chat_writeback_seat_gap

_PREVIEW_DEFERRED_CAPABILITY_MESSAGE = (
    "预览阶段只生成角色、目标与节奏草案；技能、MCP 与工作流将在身份创建后由主脑结合学习上下文继续配置。"
)
_BOOTSTRAP_DEFERRED_CAPABILITY_MESSAGE = (
    "身份创建阶段暂不立即匹配技能、MCP 与工作流；创建完成后由主脑结合学习上下文继续配置。"
)
_TEAM_UPDATE_DEFERRED_CAPABILITY_MESSAGE = (
    "团队更新阶段暂不立即匹配技能、MCP 与工作流；更新完成后由主脑结合学习上下文继续配置。"
)

class _IndustryLifecycleMixin:
    def __init__(
        self,
        *,
        goal_service: GoalService,
        industry_instance_repository: SqliteIndustryInstanceRepository,
        goal_override_repository: SqliteGoalOverrideRepository,
        agent_profile_override_repository: SqliteAgentProfileOverrideRepository,
        evidence_ledger: EvidenceLedger | None = None,
        learning_service: object | None = None,
        agent_profile_service: object | None = None,
        capability_service: object | None = None,
        strategy_memory_service: object | None = None,
        prediction_service: object | None = None,
        state_store: SQLiteStateStore | None = None,
        runtime_bindings: IndustryServiceRuntimeBindings | None = None,
        draft_generator: IndustryDraftGenerator | None = None,
        enable_hub_recommendations: bool = True,
        enable_curated_skill_catalog: bool = True,
        schedule_writer: object | None = None,
        cron_manager: object | None = None,
        media_service: object | None = None,
        memory_retain_service: object | None = None,
        work_context_service: object | None = None,
        actor_mailbox_service: object | None = None,
        session_backend: object | None = None,
    ) -> None:
        self._goal_service = goal_service
        self._industry_instance_repository = industry_instance_repository
        self._goal_override_repository = goal_override_repository
        self._agent_profile_override_repository = agent_profile_override_repository
        self._evidence_ledger = evidence_ledger
        self._learning_service = learning_service
        self._agent_profile_service = agent_profile_service
        self._capability_service = capability_service
        self._strategy_memory_service = strategy_memory_service
        self._prediction_service = prediction_service
        self._state_store = state_store
        bindings = runtime_bindings or IndustryServiceRuntimeBindings()
        self._kernel_dispatcher = bindings.kernel_dispatcher
        self._operating_lane_repository = bindings.operating_lane_repository
        self._backlog_item_repository = bindings.backlog_item_repository
        self._operating_cycle_repository = bindings.operating_cycle_repository
        self._assignment_repository = bindings.assignment_repository
        self._agent_report_repository = bindings.agent_report_repository
        self._agent_runtime_repository = bindings.agent_runtime_repository
        self._agent_thread_binding_repository = bindings.agent_thread_binding_repository
        self._schedule_repository = bindings.schedule_repository
        self._agent_mailbox_repository = bindings.agent_mailbox_repository
        self._agent_checkpoint_repository = bindings.agent_checkpoint_repository
        self._agent_lease_repository = bindings.agent_lease_repository
        self._strategy_memory_repository = bindings.strategy_memory_repository
        self._workflow_run_repository = bindings.workflow_run_repository
        self._prediction_case_repository = bindings.prediction_case_repository
        self._prediction_scenario_repository = bindings.prediction_scenario_repository
        self._prediction_signal_repository = bindings.prediction_signal_repository
        self._prediction_recommendation_repository = (
            bindings.prediction_recommendation_repository
        )
        self._prediction_review_repository = bindings.prediction_review_repository
        self._browser_runtime_service = bindings.browser_runtime_service
        self._draft_generator = draft_generator or IndustryDraftGenerator()
        self._enable_hub_recommendations = enable_hub_recommendations
        self._enable_curated_skill_catalog = enable_curated_skill_catalog
        self._hub_search_cache: dict[
            tuple[str, int],
            tuple[datetime, list[HubSkillResult]],
        ] = {}
        self._schedule_writer = schedule_writer
        self._cron_manager = cron_manager
        self._actor_mailbox_service = actor_mailbox_service
        self._operating_lane_service = bindings.operating_lane_service
        self._backlog_service = bindings.backlog_service
        self._operating_cycle_service = bindings.operating_cycle_service
        self._assignment_service = bindings.assignment_service
        self._agent_report_service = bindings.agent_report_service
        self._media_service = media_service
        self._memory_retain_service = memory_retain_service
        self._work_context_service = work_context_service
        self._session_backend = session_backend
        self._strategy_compiler = (
            getattr(bindings, "strategy_planning_compiler", None)
            or getattr(bindings, "strategy_compiler", None)
            or StrategyPlanningCompiler()
        )
        self._cycle_planner = (
            getattr(bindings, "cycle_planner", None)
            or CyclePlanningCompiler()
        )
        self._assignment_planner = (
            getattr(bindings, "assignment_planner", None)
            or AssignmentPlanningCompiler()
        )
        self._report_replan_engine = (
            getattr(bindings, "report_replan_engine", None)
            or ReportReplanEngine()
        )
        report_retain_setter = getattr(
            self._agent_report_service,
            "set_memory_retain_service",
            None,
        )
        if callable(report_retain_setter):
            report_retain_setter(memory_retain_service)
        self._normalize_industry_surfaces()
        linker = getattr(goal_service, "set_industry_service", None)
        if callable(linker):
            linker(self)
        capability_linker = getattr(self._capability_service, "set_industry_service", None)
        if callable(capability_linker):
            capability_linker(self)

    def _get_industry_kernel_dispatcher(self) -> object | None:
        dispatcher = self._kernel_dispatcher
        if dispatcher is not None:
            return dispatcher
        return getattr(self._goal_service, "_dispatcher", None)
    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._agent_profile_service = agent_profile_service
    def _get_capability_discovery_service(self) -> object | None:
        service = self._capability_service
        if service is None:
            return None
        getter = getattr(service, "get_discovery_service", None)
        if not callable(getter):
            return None
        try:
            discovery_service = getter()
        except Exception:
            return None
        setter = getattr(discovery_service, "set_state_store", None)
        if callable(setter):
            setter(self._state_store)
        return discovery_service
    def set_prediction_service(self, prediction_service: object | None) -> None:
        self._prediction_service = prediction_service
    def set_schedule_runtime(
        self,
        *,
        schedule_writer: object | None = None,
        cron_manager: object | None = None,
    ) -> None:
        self._schedule_writer = schedule_writer
        self._cron_manager = cron_manager
    def set_browser_runtime_service(
        self,
        browser_runtime_service: BrowserRuntimeService | None,
    ) -> None:
        self._browser_runtime_service = browser_runtime_service
    def _get_browser_runtime_service(self) -> BrowserRuntimeService | None:
        return self._browser_runtime_service
    def _list_operating_lanes(
        self,
        instance_id: str,
        *,
        status: str | None = None,
    ) -> list[OperatingLaneRecord]:
        if self._operating_lane_service is None:
            return []
        return self._operating_lane_service.list_lanes(
            industry_instance_id=instance_id,
            status=status,
            limit=None,
        )
    def _list_backlog_items(
        self,
        instance_id: str,
        *,
        status: str | None = None,
        cycle_id: str | None = None,
        limit: int | None = None,
    ) -> list[BacklogItemRecord]:
        if self._backlog_service is None:
            return []
        return self._backlog_service.list_items(
            industry_instance_id=instance_id,
            status=status,
            cycle_id=cycle_id,
            limit=limit,
        )
    def _backlog_item_staffing_resolution_closed(
        self,
        item: BacklogItemRecord,
    ) -> bool:
        metadata = dict(item.metadata or {})
        target_role_id = _string(metadata.get("seat_target_role_id")) or _string(
            metadata.get("industry_role_id"),
        )
        target_agent_id = _string(metadata.get("seat_target_agent_id")) or _string(
            metadata.get("owner_agent_id"),
        )
        if target_role_id is None and target_agent_id is None:
            return False
        record = self._industry_instance_repository.get_instance(item.industry_instance_id)
        if record is None:
            return False
        team = self._materialize_team_blueprint(record)
        return (
            self._match_instance_team_role(
                team,
                role_id=target_role_id,
                agent_id=target_agent_id,
            )
            is not None
        )
    def _backlog_item_waits_for_staffing_resolution(
        self,
        item: BacklogItemRecord,
    ) -> bool:
        if _string(item.source_kind) != "operator":
            return False
        metadata = dict(item.metadata or {})
        source = _string(metadata.get("source")) or _string(item.source_ref)
        if source != "chat-writeback" and not str(source or "").startswith("chat-writeback:"):
            return False
        if self._backlog_item_staffing_resolution_closed(item):
            return False
        gap_kind = _string(metadata.get("chat_writeback_gap_kind"))
        seat_resolution_kind = _string(metadata.get("seat_resolution_kind"))
        decision_request_id = _string(metadata.get("decision_request_id"))
        proposal_status = _string(metadata.get("proposal_status"))
        if gap_kind in {
            "routing-pending",
            "capability-gap",
            "temporary-seat-proposal",
            "career-seat-proposal",
        }:
            return True
        if seat_resolution_kind in {
            "routing-pending",
            "temporary-seat-proposal",
            "career-seat-proposal",
        }:
            return True
        return decision_request_id is not None and proposal_status in {
            "waiting-confirm",
            "proposed",
        }
    def _materializable_backlog_items(
        self,
        items: list[BacklogItemRecord],
    ) -> list[BacklogItemRecord]:
        return [
            item
            for item in items
            if self._backlog_item_is_report_followup(item)
            or not self._backlog_item_waits_for_staffing_resolution(item)
        ]

    def _backlog_item_value(
        self,
        item: object,
        key: str,
    ) -> object | None:
        if isinstance(item, dict):
            return item.get(key)
        return getattr(item, key, None)

    def _backlog_item_metadata(
        self,
        item: object,
    ) -> dict[str, Any]:
        metadata = self._backlog_item_value(item, "metadata")
        return metadata if isinstance(metadata, dict) else {}

    def _backlog_item_is_report_followup(self, item: object) -> bool:
        metadata = self._backlog_item_metadata(item)
        if _string(metadata.get("source_report_id")) is not None:
            return True
        source_report_ids = metadata.get("source_report_ids")
        if isinstance(source_report_ids, list) and any(
            _string(value) is not None for value in source_report_ids
        ):
            return True
        return _string(metadata.get("synthesis_kind")) in {
            "followup-needed",
            "failed-report",
            "conflict",
        }

    def _clone_materialization_metadata_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): self._clone_materialization_metadata_value(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._clone_materialization_metadata_value(item) for item in value]
        return value

    def _materialized_assignment_continuity_metadata(
        self,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            return {}
        carried: dict[str, Any] = {}
        for key in (
            "supervisor_owner_agent_id",
            "supervisor_industry_role_id",
            "supervisor_role_name",
            "owner_agent_id",
            "industry_role_id",
            "industry_role_name",
            "role_name",
            "role_summary",
            "mission",
            "work_context_id",
            "chat_writeback_channel",
            "chat_writeback_requested_surfaces",
            "seat_requested_surfaces",
            "requested_surfaces",
            "control_thread_id",
            "session_id",
            "environment_ref",
            "recommended_scheduler_action",
            "report_back_mode",
            "decision_request_id",
            "proposal_status",
            "source_report_id",
            "source_report_ids",
            "synthesis_kind",
            "activation_top_entities",
            "activation_top_opinions",
            "activation_top_relations",
            "activation_top_relation_kinds",
            "activation_top_relation_ids",
            "activation_top_constraints",
            "activation_top_next_actions",
            "activation_relation_source_refs",
            "activation_support_refs",
            "upstream_backlog_source_ref",
        ):
            value = metadata.get(key)
            if value is None:
                continue
            carried[key] = self._clone_materialization_metadata_value(value)
        return carried

    def _planner_sidecar_payload(self, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            try:
                payload = value.model_dump(mode="json", exclude_none=True)  # type: ignore[call-arg]
            except TypeError:
                payload = value.model_dump(mode="json")  # type: ignore[call-arg]
            return dict(payload) if isinstance(payload, dict) else {}
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    def _assignment_plan_context_from_formal_planning(
        self,
        assignment: AssignmentRecord,
    ) -> dict[str, object]:
        formal_planning = (
            dict((assignment.metadata or {}).get("formal_planning") or {})
            if isinstance(assignment.metadata, Mapping)
            else {}
        )
        envelope = formal_planning.get("assignment_plan")
        if not isinstance(envelope, Mapping):
            return {}
        assignment_plan_envelope = dict(envelope)
        checkpoints = assignment_plan_envelope.get("checkpoints")
        acceptance_criteria = assignment_plan_envelope.get("acceptance_criteria")
        sidecar_plan = assignment_plan_envelope.get("sidecar_plan")
        context: dict[str, object] = {
            "assignment_plan_envelope": assignment_plan_envelope,
        }
        if isinstance(checkpoints, list):
            context["assignment_plan_checkpoints"] = [
                dict(item) for item in checkpoints if isinstance(item, Mapping)
            ]
        if isinstance(acceptance_criteria, list):
            context["assignment_plan_acceptance_criteria"] = [
                str(item).strip()
                for item in acceptance_criteria
                if isinstance(item, str) and str(item).strip()
            ]
        if isinstance(sidecar_plan, Mapping):
            context["assignment_sidecar_plan"] = dict(sidecar_plan)
        report_back_mode = (
            _string(assignment.report_back_mode)
            or _string(assignment_plan_envelope.get("report_back_mode"))
        )
        if report_back_mode is not None:
            context["report_back_mode"] = report_back_mode
        return context

    def _mapping_list(self, value: object | None) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [dict(item) for item in value if isinstance(item, Mapping)]

    def _resolve_strategy_payload_mapping(
        self,
        *,
        record: IndustryInstanceRecord,
    ) -> dict[str, Any]:
        payload = resolve_strategy_payload(
            service=self._strategy_memory_service,
            scope_type="industry",
            scope_id=record.instance_id,
            fallback_owner_agent_ids=(EXECUTION_CORE_AGENT_ID,),
        )
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _strategy_constraints_sidecar_payload(
        self,
        *,
        record: IndustryInstanceRecord,
        strategy_constraints: PlanningStrategyConstraints | None = None,
        strategy_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        raw_payload = (
            dict(strategy_payload)
            if isinstance(strategy_payload, Mapping)
            else self._resolve_strategy_payload_mapping(record=record)
        )
        payload = self._planner_sidecar_payload(
            strategy_constraints or self._compile_strategy_constraints(record=record),
        )
        metadata = dict(raw_payload.get("metadata") or {})
        strategic_uncertainties = self._mapping_list(
            payload.get("strategic_uncertainties"),
        ) or self._mapping_list(raw_payload.get("strategic_uncertainties")) or self._mapping_list(
            metadata.get("strategic_uncertainties"),
        )
        lane_budgets = self._mapping_list(payload.get("lane_budgets")) or self._mapping_list(
            raw_payload.get("lane_budgets"),
        ) or self._mapping_list(metadata.get("lane_budgets"))
        if strategic_uncertainties:
            payload["strategic_uncertainties"] = strategic_uncertainties
        if lane_budgets:
            payload["lane_budgets"] = lane_budgets
        return payload

    def _report_replan_sidecar_payload(
        self,
        *,
        synthesis: Mapping[str, Any] | None,
        strategy_constraints_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved = dict(synthesis) if isinstance(synthesis, Mapping) else {}
        payload = self._planner_sidecar_payload(
            self._report_replan_engine.compile(resolved),
        )
        raw_decision = (
            dict(resolved.get("replan_decision"))
            if isinstance(resolved.get("replan_decision"), Mapping)
            else {}
        )
        if raw_decision:
            payload.update(raw_decision)
        trigger_context = (
            dict(raw_decision.get("trigger_context"))
            if isinstance(raw_decision.get("trigger_context"), Mapping)
            else {}
        )
        strategic_uncertainties = self._mapping_list(
            _mapping(strategy_constraints_payload).get("strategic_uncertainties"),
        )
        lane_budgets = self._mapping_list(
            _mapping(strategy_constraints_payload).get("lane_budgets"),
        )
        strategy_trigger_rules = self._mapping_list(
            _mapping(strategy_constraints_payload).get("strategy_trigger_rules"),
        )
        conflict_items = list(resolved.get("conflicts") or [])
        hole_items = list(resolved.get("holes") or [])
        replan_reasons = _unique_strings(
            resolved.get("replan_reasons"),
            payload.get("reason_ids"),
        )
        if payload.get("status") == "needs-replan":
            conflict_count = len(conflict_items)
            hole_count = len(hole_items)
            preferred_decision_kind = None
            if strategic_uncertainties and (
                conflict_count or hole_count or replan_reasons
            ):
                preferred_decision_kind = "strategy_review_required"
            elif lane_budgets and (conflict_count or hole_count):
                preferred_decision_kind = "lane_reweight"
            elif conflict_count or hole_count:
                preferred_decision_kind = "cycle_rebalance"
            else:
                preferred_decision_kind = "follow_up_backlog"
            if preferred_decision_kind is not None:
                payload["decision_kind"] = preferred_decision_kind
            if not trigger_context:
                trigger_families: list[str] = []
                if resolved.get("followup_backlog") or resolved.get("needs_followup"):
                    trigger_families.append("repeated-blocker")
                if conflict_items:
                    trigger_families.append("repeated-contradiction")
                if hole_items:
                    trigger_families.append("target-miss")
                if strategic_uncertainties:
                    trigger_families.append("confidence-collapse")
                trigger_context = {
                    "trigger_families": trigger_families,
                    "strategic_uncertainty_ids": [
                        _string(item.get("uncertainty_id"))
                        for item in strategic_uncertainties
                        if _string(item.get("uncertainty_id")) is not None
                    ],
                    "lane_budget_pressure": {
                        _string(item.get("lane_id")) or f"lane-{index}": _string(
                            item.get("review_pressure"),
                        )
                        or "review-required"
                        for index, item in enumerate(lane_budgets)
                        if _string(item.get("lane_id")) is not None
                    },
                }
            if strategic_uncertainties:
                trigger_context["strategic_uncertainty_ids"] = [
                    _string(item.get("uncertainty_id"))
                    for item in strategic_uncertainties
                    if _string(item.get("uncertainty_id")) is not None
                ]
                trigger_families = _unique_strings(
                    trigger_context.get("trigger_families"),
                    ["confidence-collapse"],
                )
                if trigger_families:
                    trigger_context["trigger_families"] = trigger_families
            if lane_budgets:
                trigger_context["lane_budget_pressure"] = {
                    _string(item.get("lane_id")) or f"lane-{index}": _string(
                        item.get("review_pressure"),
                    )
                    or "review-required"
                    for index, item in enumerate(lane_budgets)
                    if _string(item.get("lane_id")) is not None
                }
            payload["trigger_context"] = trigger_context
        directives = self._mapping_list(resolved.get("replan_directives"))
        if directives:
            payload["directives"] = directives
        recommended_actions = self._mapping_list(resolved.get("recommended_actions"))
        if recommended_actions:
            payload["recommended_actions"] = recommended_actions
        activation = _mapping(resolved.get("activation"))
        if activation:
            payload["activation"] = dict(activation)
        uncertainty_register = build_uncertainty_register_payload(
            strategic_uncertainties=strategic_uncertainties,
            lane_budgets=lane_budgets,
            strategy_trigger_rules=strategy_trigger_rules,
            source="formal-planning-sidecar",
        )
        if uncertainty_register:
            payload["uncertainty_register"] = uncertainty_register
        return payload

    def _stable_assignment_id(
        self,
        *,
        cycle_id: str,
        goal_id: str | None,
        backlog_item_id: str | None,
        title: str | None,
    ) -> str:
        normalized = "|".join(
            str(part).strip()
            for part in (
                cycle_id,
                goal_id or backlog_item_id or title or "",
            )
            if str(part).strip()
        )
        digest = sha1(normalized.encode("utf-8")).hexdigest()[:16]
        return f"assignment:{digest}"

    def _compile_strategy_constraints(
        self,
        *,
        record: IndustryInstanceRecord,
    ) -> PlanningStrategyConstraints:
        payload = self._resolve_strategy_payload_mapping(record=record)
        if not payload:
            return PlanningStrategyConstraints()
        try:
            strategy_record = StrategyMemoryRecord.model_validate(
                {
                    "scope_type": payload.get("scope_type") or "industry",
                    "scope_id": payload.get("scope_id") or record.instance_id,
                    "industry_instance_id": (
                        payload.get("industry_instance_id") or record.instance_id
                    ),
                    "title": payload.get("title") or "Strategy Memory",
                    **payload,
                },
            )
        except Exception:
            lane_weights: dict[str, float] = {}
            for lane_id, weight in dict(payload.get("lane_weights") or {}).items():
                normalized_lane_id = str(lane_id).strip()
                if not normalized_lane_id:
                    continue
                try:
                    lane_weights[normalized_lane_id] = float(weight)
                except (TypeError, ValueError):
                    continue
            return PlanningStrategyConstraints(
                mission=_string(payload.get("mission")) or "",
                north_star=_string(payload.get("north_star")) or "",
                priority_order=_unique_strings(payload.get("priority_order")),
                lane_weights=lane_weights,
                planning_policy=_unique_strings(payload.get("planning_policy")),
                review_rules=_unique_strings(payload.get("review_rules")),
                paused_lane_ids=_unique_strings(payload.get("paused_lane_ids")),
                current_focuses=_unique_strings(payload.get("current_focuses")),
            )
        return self._strategy_compiler.compile(strategy_record)

    def _build_planning_activation_query(
        self,
        *,
        record: IndustryInstanceRecord,
        open_backlog: Sequence[BacklogItemRecord],
        pending_reports: Sequence[AgentReportRecord],
    ) -> str:
        query_parts = _unique_strings(
            [
                record.label,
                record.summary,
                *[
                    item.title
                    for item in list(open_backlog)[:3]
                ],
                *[
                    item.summary
                    for item in list(open_backlog)[:2]
                ],
                *[
                    report.headline
                    for report in list(pending_reports)[:3]
                ],
                *[
                    report.summary
                    for report in list(pending_reports)[:2]
                ],
            ],
        )
        query = " | ".join(query_parts[:6]).strip()
        if not query:
            query = record.label or record.summary or record.instance_id
        return query

    def _resolve_planning_activation_result(
        self,
        *,
        record: IndustryInstanceRecord,
        open_backlog: Sequence[BacklogItemRecord],
        pending_reports: Sequence[AgentReportRecord],
    ) -> object | None:
        activation_service = getattr(self, "_memory_activation_service", None)
        activate_for_query = getattr(activation_service, "activate_for_query", None)
        if not callable(activate_for_query):
            return None
        query = self._build_planning_activation_query(
            record=record,
            open_backlog=open_backlog,
            pending_reports=pending_reports,
        )
        try:
            return activate_for_query(
                query=query,
                industry_instance_id=record.instance_id,
                owner_agent_id=EXECUTION_CORE_AGENT_ID,
                current_phase="operating-cycle-planning",
                limit=12,
            )
        except Exception:
            return None

    def _resolve_planning_task_subgraph(
        self,
        *,
        record: IndustryInstanceRecord,
        open_backlog: Sequence[BacklogItemRecord],
        pending_reports: Sequence[AgentReportRecord],
        activation_result: object | None = None,
    ) -> object | None:
        subgraph_service = getattr(self, "_subgraph_activation_service", None)
        activate_for_query = getattr(subgraph_service, "activate_for_query", None)
        if callable(activate_for_query):
            query = self._build_planning_activation_query(
                record=record,
                open_backlog=open_backlog,
                pending_reports=pending_reports,
            )
            try:
                return activate_for_query(
                    query=query,
                    industry_instance_id=record.instance_id,
                    owner_agent_id=EXECUTION_CORE_AGENT_ID,
                    current_phase="operating-cycle-planning",
                    limit=12,
                )
            except Exception:
                return None
        to_task_subgraph = getattr(activation_result, "to_task_subgraph", None)
        if callable(to_task_subgraph):
            try:
                return to_task_subgraph()
            except Exception:
                return None
        return None

    def _apply_activation_to_strategy_constraints(
        self,
        *,
        constraints: PlanningStrategyConstraints,
        activation_result: object | None,
    ) -> PlanningStrategyConstraints:
        if activation_result is None:
            return constraints
        graph_focus_entities = _unique_strings(
            getattr(activation_result, "top_entities", None),
        )
        graph_focus_opinions = _unique_strings(
            getattr(activation_result, "top_opinions", None),
        )
        graph_focus_relations = _unique_strings(
            getattr(activation_result, "top_relations", None),
        )
        relation_evidence = list(
            getattr(activation_result, "top_relation_evidence", None) or [],
        )
        graph_relation_evidence: list[dict[str, Any]] = []
        for item in relation_evidence:
            model_dump = getattr(item, "model_dump", None)
            if callable(model_dump):
                payload = model_dump(mode="json")
            elif isinstance(item, Mapping):
                payload = dict(item)
            else:
                payload = None
            if isinstance(payload, dict):
                graph_relation_evidence.append(payload)
        if (
            not graph_focus_entities
            and not graph_focus_opinions
            and not graph_focus_relations
            and not graph_relation_evidence
        ):
            return constraints
        return constraints.model_copy(
            update={
                "current_focuses": _unique_strings(
                    constraints.current_focuses,
                    getattr(activation_result, "top_constraints", None),
                    getattr(activation_result, "top_next_actions", None),
                ),
                "graph_focus_entities": graph_focus_entities,
                "graph_focus_opinions": graph_focus_opinions,
                "graph_focus_relations": graph_focus_relations,
                "graph_relation_evidence": graph_relation_evidence,
            },
        )

    def _decorate_report_synthesis_with_replan(
        self,
        synthesis: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        resolved = dict(synthesis) if isinstance(synthesis, Mapping) else {}
        decision_payload = self._report_replan_sidecar_payload(synthesis=resolved)
        if decision_payload:
            resolved["replan_decision"] = decision_payload
            resolved["formal_replan"] = decision_payload
            resolved["report_replan"] = decision_payload
            resolved["needs_replan"] = (
                _string(decision_payload.get("status")) == "needs-replan"
                or bool(resolved.get("needs_replan"))
            )
        return resolved

    def _compat_cycle_reason(
        self,
        reason: str | None,
    ) -> str | None:
        normalized = _string(reason)
        if normalized is None:
            return None
        return {
            "planned-open-backlog": "open-backlog",
            "planner-no-open-backlog": "no-open-backlog",
        }.get(normalized, normalized)

    def _materialize_backlog_into_cycle(
        self,
        *,
        record: IndustryInstanceRecord,
        cycle: OperatingCycleRecord,
        selected_backlog: Sequence[BacklogItemRecord],
        strategy_constraints: PlanningStrategyConstraints,
        strategy_constraints_sidecar: Mapping[str, Any] | None = None,
        cycle_decision_sidecar: Mapping[str, Any] | None = None,
        report_replan_sidecar: Mapping[str, Any] | None = None,
        task_subgraph: object | None = None,
    ) -> tuple[OperatingCycleRecord, list[str]]:
        if (
            self._assignment_service is None
            or self._operating_cycle_service is None
            or self._backlog_service is None
        ):
            return cycle, []
        assignment_specs: list[dict[str, object]] = []
        for item in selected_backlog:
            lane = (
                self._operating_lane_service.get_lane(item.lane_id)
                if self._operating_lane_service is not None and item.lane_id is not None
                else None
            )
            assignment_plan = self._assignment_planner.plan(
                assignment_id=self._stable_assignment_id(
                    cycle_id=cycle.id,
                    goal_id=item.goal_id,
                    backlog_item_id=item.id,
                    title=item.title,
                ),
                cycle_id=cycle.id,
                backlog_item=item,
                lane=lane,
                strategy_constraints=strategy_constraints,
                task_subgraph=task_subgraph,
            )
            assignment_plan_payload = self._planner_sidecar_payload(assignment_plan)
            assignment_specs.append(
                {
                    "backlog_item_id": item.id,
                    "lane_id": item.lane_id,
                    "owner_agent_id": assignment_plan.owner_agent_id,
                    "owner_role_id": assignment_plan.owner_role_id,
                    "title": item.title,
                    "summary": item.summary,
                    "status": (
                        "planned"
                        if _string(record.autonomy_status) == "waiting-confirm"
                        else "queued"
                    ),
                    "report_back_mode": assignment_plan.report_back_mode,
                    "metadata": {
                        **self._materialized_assignment_continuity_metadata(item.metadata),
                        **dict(assignment_plan.metadata or {}),
                        "source_ref": item.source_ref,
                        "source_kind": item.source_kind,
                        "fixed_sop_binding_id": _string(
                            item.metadata.get("fixed_sop_binding_id"),
                        ),
                        "fixed_sop_binding_name": _string(
                            item.metadata.get("fixed_sop_binding_name"),
                        ),
                        "routine_id": _string(item.metadata.get("routine_id")),
                        "routine_name": _string(item.metadata.get("routine_name")),
                        "formal_planning": {
                            "strategy_constraints": dict(
                                strategy_constraints_sidecar or {},
                            ),
                            "cycle_decision": dict(cycle_decision_sidecar or {}),
                            "report_replan": dict(report_replan_sidecar or {}),
                            "assignment_plan": assignment_plan_payload,
                        },
                    },
                },
            )
        created_assignments = self._assignment_service.ensure_assignments(
            industry_instance_id=record.instance_id,
            cycle_id=cycle.id,
            specs=assignment_specs,
        )
        assignment_ids = [assignment.id for assignment in created_assignments]
        cycle = self._operating_cycle_service.update_cycle_links(
            cycle,
            assignment_ids=_unique_strings(
                list(cycle.assignment_ids or []),
                assignment_ids,
            ),
            backlog_item_ids=_unique_strings(
                list(cycle.backlog_item_ids or []),
                [item.id for item in selected_backlog],
            ),
            focus_lane_ids=_unique_strings(
                list(cycle.focus_lane_ids or []),
                [
                    item.lane_id
                    for item in selected_backlog
                    if item.lane_id is not None
                ],
            ),
        )
        assignment_map = {
            assignment.backlog_item_id: assignment
            for assignment in created_assignments
            if assignment.backlog_item_id
        }
        for item in selected_backlog:
            assignment = assignment_map.get(item.id)
            self._backlog_service.mark_item_materialized(
                item,
                cycle_id=cycle.id,
                goal_id=None,
                assignment_id=assignment.id if assignment is not None else None,
            )
        return cycle, assignment_ids

    def _rank_materializable_backlog_items(
        self,
        items: list[Any],
    ) -> list[Any]:
        return sorted(
            items,
            key=lambda item: (
                1 if self._backlog_item_is_report_followup(item) else 0,
                int(self._backlog_item_value(item, "priority") or 0),
                _sort_timestamp(
                    self._backlog_item_value(item, "updated_at")
                    or self._backlog_item_value(item, "created_at"),
                ),
            ),
            reverse=True,
        )

    def _current_operating_cycle_record(
        self,
        instance_id: str,
    ) -> OperatingCycleRecord | None:
        if self._operating_cycle_service is None:
            return None
        return self._operating_cycle_service.get_current_cycle(
            industry_instance_id=instance_id,
        )
    def _list_operating_cycles(
        self,
        instance_id: str,
        *,
        status: str | None = None,
        limit: int | None = 8,
    ) -> list[OperatingCycleRecord]:
        if self._operating_cycle_service is None:
            return []
        return self._operating_cycle_service.list_cycles(
            industry_instance_id=instance_id,
            status=status,
            limit=limit,
        )
    def _list_assignment_records(
        self,
        instance_id: str,
        *,
        cycle_id: str | None = None,
        goal_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[AssignmentRecord]:
        if self._assignment_service is None:
            return []
        return self._assignment_service.list_assignments(
            industry_instance_id=instance_id,
            cycle_id=cycle_id,
            goal_id=goal_id,
            status=status,
            limit=limit,
        )
    def _list_agent_report_records(
        self,
        instance_id: str,
        *,
        cycle_id: str | None = None,
        processed: bool | None = None,
        limit: int | None = None,
    ) -> list[AgentReportRecord]:
        if self._agent_report_service is None:
            return []
        return self._agent_report_service.list_reports(
            industry_instance_id=instance_id,
            cycle_id=cycle_id,
            processed=processed,
            limit=limit,
        )
    def _synthesize_agent_reports(
        self,
        *,
        instance_id: str,
        cycle_id: str | None,
        activation_result: object | None = None,
    ) -> dict[str, Any]:
        knowledge_writeback_service = None
        knowledge_service = getattr(self, "_knowledge_service", None)
        if knowledge_service is not None:
            from ..memory.knowledge_writeback_service import KnowledgeWritebackService

            knowledge_writeback_service = KnowledgeWritebackService(
                knowledge_service=knowledge_service,
            )
        synthesis = _synthesize_agent_reports_helper(
            list_agent_report_records=self._list_agent_report_records,
            instance_id=instance_id,
            cycle_id=cycle_id,
            activation_result=activation_result,
            knowledge_writeback_service=knowledge_writeback_service,
        )
        return self._decorate_report_synthesis_with_replan(synthesis)

    def _record_report_synthesis_backlog(
        self,
        *,
        record: IndustryInstanceRecord,
        synthesis: Mapping[str, Any] | None,
    ) -> None:
        _record_report_synthesis_backlog_helper(
            backlog_service=self._backlog_service,
            record=record,
            synthesis=synthesis,
            resolve_report_followup_metadata=lambda action_metadata: self._resolve_report_followup_metadata(
                action_metadata=action_metadata,
            ),
        )

    def _resolve_report_followup_metadata(
        self,
        *,
        action_metadata: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        return _resolve_report_followup_metadata_helper(
            action_metadata=action_metadata,
            agent_report_repository=self._agent_report_repository,
            assignment_repository=self._assignment_repository,
            backlog_service=self._backlog_service,
            build_report_followup_metadata_fn=self._build_report_followup_metadata,
            merge_report_followup_metadata_fn=self._merge_report_followup_metadata,
        )

    def _merge_report_followup_metadata(
        self,
        base: Mapping[str, Any],
        extra: Mapping[str, Any],
    ) -> dict[str, Any]:
        return _merge_report_followup_metadata_helper(base=base, extra=extra)

    def _build_report_followup_metadata(
        self,
        *,
        report: AgentReportRecord | None,
        assignment: AssignmentRecord | None,
        original_backlog_item: BacklogItemRecord | None,
    ) -> dict[str, Any]:
        return _build_report_followup_metadata_helper(
            report=report,
            assignment=assignment,
            original_backlog_item=original_backlog_item,
        )

    def _persist_cycle_report_synthesis(
        self,
        *,
        cycle: OperatingCycleRecord | None,
        synthesis: Mapping[str, Any] | None,
    ) -> OperatingCycleRecord | None:
        return _persist_cycle_report_synthesis_helper(
            cycle=cycle,
            synthesis=synthesis,
            operating_cycle_repository=self._operating_cycle_repository,
            utc_now=_utc_now,
        )
    def _resolve_goal_lane(
        self,
        *,
        instance_id: str,
        role: IndustryRoleBlueprint | None,
        goal_kind: str | None,
        owner_agent_id: str | None,
    ) -> OperatingLaneRecord | None:
        if self._operating_lane_service is None:
            return None
        return self._operating_lane_service.resolve_lane(
            industry_instance_id=instance_id,
            role_id=role.role_id if role is not None else None,
            goal_kind=goal_kind,
            owner_agent_id=owner_agent_id,
        )
    def _upsert_schedule_lane(
        self,
        *,
        schedule_id: str,
        lane_id: str | None,
        schedule_kind: str | None = None,
        trigger_target: str | None = None,
    ) -> None:
        if self._schedule_repository is None:
            return
        record = self._schedule_repository.get_schedule(schedule_id)
        if record is None:
            return
        self._schedule_repository.upsert_schedule(
            record.model_copy(
                update={
                    "lane_id": lane_id,
                    "schedule_kind": schedule_kind or record.schedule_kind,
                    "trigger_target": trigger_target or record.trigger_target,
                    "updated_at": _utc_now(),
                },
            ),
        )
    def _chat_writeback_control_thread_id(
        self,
        *,
        instance_id: str,
        session_id: str | None,
    ) -> str:
        return _string(session_id) or f"industry-chat:{instance_id}:{EXECUTION_CORE_ROLE_ID}"
    async def _submit_chat_writeback_team_update(
        self,
        *,
        record: IndustryInstanceRecord,
        role: IndustryRoleBlueprint,
        owner_agent_id: str,
        session_id: str | None,
        risk_level: str,
        human_confirmation_required: bool,
    ) -> dict[str, Any]:
        dispatcher = self._get_industry_kernel_dispatcher()
        if dispatcher is None:
            return {
                "success": False,
                "summary": "Kernel dispatcher is not available for governed industry team updates.",
                "decision_request_id": None,
                "phase": "failed",
                "output": {},
            }
        control_thread_id = self._chat_writeback_control_thread_id(
            instance_id=record.instance_id,
            session_id=session_id,
        )
        task = KernelTask(
            title=f"Update staffing seat for {role.role_name}",
            capability_ref="system:update_industry_team",
            owner_agent_id=owner_agent_id,
            risk_level=risk_level,
            payload={
                "operation": "add-role",
                "instance_id": record.instance_id,
                "role": role.model_dump(mode="json"),
                "seed_default_goal": False,
                "control_thread_id": control_thread_id,
                "session_id": control_thread_id,
                "human_confirmation_required": human_confirmation_required,
                "decision_requested_by": "copaw-main-brain",
            },
        )
        admitted = dispatcher.submit(task)
        result = admitted
        if admitted.phase == "executing":
            result = await dispatcher.execute_task(task.id)
        output = dict(result.output or {}) if isinstance(result.output, dict) else {}
        success = bool(result.success)
        if isinstance(output.get("success"), bool):
            success = success and bool(output.get("success"))
        return {
            "success": success,
            "summary": _string(output.get("summary")) or result.summary,
            "decision_request_id": result.decision_request_id,
            "phase": result.phase,
            "output": output,
        }

    async def _auto_close_temporary_seat_capability_gap(
        self,
        *,
        record: IndustryInstanceRecord,
        profile: IndustryProfile,
        role: IndustryRoleBlueprint,
        plan: ChatWritebackPlan,
    ) -> list[IndustryBootstrapInstallResult]:
        goal_context_by_agent = self._build_instance_goal_context_by_agent(
            record=record,
        )
        goal_context_by_agent[role.agent_id] = _unique_strings(
            list(goal_context_by_agent.get(role.agent_id, [])),
            plan.normalized_text,
            plan.goal.title if plan.goal is not None else None,
            plan.goal.summary if plan.goal is not None else None,
            list(plan.goal.plan_steps) if plan.goal is not None else [],
            list(plan.classifications),
        )
        recommendations = self._build_install_template_recommendations(
            profile=profile,
            target_roles=[role],
            goal_context_by_agent=goal_context_by_agent,
        )
        results: list[IndustryBootstrapInstallResult] = []
        for recommendation in recommendations:
            auto_recommendation = recommendation.model_copy(
                update={
                    "risk_level": "auto",
                    "review_required": False,
                    "review_summary": "",
                    "review_notes": _unique_strings(
                        list(recommendation.review_notes or []),
                        [
                            "Auto-approved because seat-gap policy already classified this request as low-risk local work.",
                        ],
                    ),
                },
            )
            results.append(
                await self.auto_close_capability_gap_for_instance(
                    record.instance_id,
                    auto_recommendation,
                    target_agent_ids=[role.agent_id],
                    capability_assignment_mode="merge",
                ),
            )
        return results
    async def _search_hub_skills_cached(
        self,
        *,
        query: str,
        limit: int = 6,
    ) -> list[HubSkillResult]:
        normalized_query = " ".join(query.strip().split())
        if not normalized_query:
            return []
        cache_key = (normalized_query.lower(), limit)
        cached = self._hub_search_cache.get(cache_key)
        now = _utc_now()
        if cached is not None and cached[0] >= now:
            return list(cached[1])
        results = await asyncio.to_thread(
            search_hub_skills,
            normalized_query,
            limit,
        )
        self._hub_search_cache[cache_key] = (
            now + timedelta(minutes=10),
            list(results),
        )
        return list(results)
    async def preview_v1(
        self,
        request: IndustryPreviewRequest,
    ) -> IndustryPreviewResponse:
        plan = await self._prepare_preview(request)
        return IndustryPreviewResponse(
            profile=plan.profile,
            draft=plan.draft,
            recommendation_pack=plan.recommendation_pack,
            readiness_checks=plan.readiness_checks,
            can_activate=all(
                not check.required or check.status != "missing"
                for check in plan.readiness_checks
            ),
            media_analyses=plan.media_analyses,
            media_warnings=plan.media_warnings,
        )
    def _public_bootstrap_activation_flags(
        self,
        request: IndustryBootstrapRequest,
    ) -> tuple[dict[str, bool], bool]:
        """
        Public bootstrap contract:
        - Public bootstrap should create the formal industry identity and let the
          main brain start supervising by default.
        - Human confirmation is reserved for real risk boundaries, not the default
          post-bootstrap state.
        """
        auto_activate = bool(request.auto_activate)
        auto_dispatch = auto_activate and bool(request.auto_dispatch)
        execute = auto_dispatch and bool(request.execute)
        return (
            {
                "auto_activate": auto_activate,
                "auto_dispatch": auto_dispatch,
                "execute": execute,
            },
            False,
        )
    async def bootstrap_v1(
        self,
        request: IndustryBootstrapRequest,
    ) -> IndustryBootstrapResponse:
        plan = await self._prepare_bootstrap(request)
        flags, auto_start_learning = self._public_bootstrap_activation_flags(request)
        return await self._activate_plan(
            plan=plan,
            goal_priority=request.goal_priority,
            auto_activate=flags["auto_activate"],
            auto_dispatch=flags["auto_dispatch"],
            execute=flags["execute"],
            install_plan=list(request.install_plan or []),
            auto_start_learning=auto_start_learning,
        )
    async def update_instance_team(
        self,
        instance_id: str,
        request: IndustryBootstrapRequest,
        *,
        public_contract: bool = True,
    ) -> IndustryBootstrapResponse:
        current_detail = self.get_instance_detail(instance_id)
        plan = await self._prepare_team_update(
            instance_id=instance_id,
            request=request,
        )
        flags = (
            self._default_team_update_flags(current_detail)
            if public_contract
            and current_detail is not None
            else {
                "auto_activate": bool(request.auto_activate),
                "auto_dispatch": bool(request.auto_dispatch),
                "execute": bool(request.execute),
            }
        )
        return await self._activate_plan(
            plan=plan,
            goal_priority=request.goal_priority,
            auto_activate=flags["auto_activate"],
            auto_dispatch=flags["auto_dispatch"],
            execute=flags["execute"],
            install_plan=list(request.install_plan or []),
        )
    async def add_role_to_instance_team(
        self,
        instance_id: str,
        *,
        role: IndustryRoleBlueprint,
        goal: IndustryDraftGoal | None = None,
        schedule: IndustryDraftSchedule | None = None,
        seed_default_goal: bool = True,
        auto_activate: bool | None = None,
        auto_dispatch: bool | None = None,
        execute: bool | None = None,
    ) -> IndustryBootstrapResponse:
        detail = self.get_instance_detail(instance_id)
        if detail is None:
            raise KeyError(f"Industry instance '{instance_id}' not found")
        if any(
            normalize_industry_role_id(agent.role_id)
            == normalize_industry_role_id(role.role_id)
            or _string(agent.agent_id) == _string(role.agent_id)
            for agent in detail.team.agents
        ):
            raise ValueError(
                f"Industry instance '{instance_id}' already contains role '{role.role_id}'",
            )
        draft = self._build_draft_from_instance_detail(detail)
        goal_additions: list[IndustryDraftGoal] = []
        if goal is not None:
            goal_additions.append(goal)
        elif seed_default_goal and role.employment_mode != "temporary":
            goal_additions.append(self._build_default_goal_for_role(detail.profile, role))
        draft = draft.model_copy(
            update={
                "team": draft.team.model_copy(
                    update={"agents": [*draft.team.agents, role]},
                ),
                "goals": [
                    *draft.goals,
                    *goal_additions,
                ],
                "schedules": [
                    *draft.schedules,
                    *([schedule] if schedule is not None else []),
                ],
            },
        )
        update_flags = self._default_team_update_flags(detail)
        request = IndustryBootstrapRequest(
            profile=detail.profile,
            draft=draft,
            auto_activate=(
                update_flags["auto_activate"]
                if auto_activate is None
                else bool(auto_activate)
            ),
            auto_dispatch=(
                update_flags["auto_dispatch"]
                if auto_dispatch is None
                else bool(auto_dispatch)
            ),
            execute=(
                update_flags["execute"]
                if execute is None
                else bool(execute)
            ),
        )
        return await self.update_instance_team(
            instance_id,
            request,
            public_contract=False,
        )
    def _match_instance_team_role(
        self,
        team: IndustryTeamBlueprint,
        *,
        role_id: str | None = None,
        agent_id: str | None = None,
    ) -> IndustryRoleBlueprint | None:
        normalized_role_id = normalize_industry_role_id(role_id)
        normalized_agent_id = _string(agent_id)
        for agent in team.agents:
            if (
                normalized_role_id is not None
                and normalize_industry_role_id(agent.role_id) == normalized_role_id
            ):
                return agent
            if normalized_agent_id is not None and _string(agent.agent_id) == normalized_agent_id:
                return agent
        return None
    def _replace_instance_team_agents(
        self,
        *,
        instance_id: str,
        agents: list[IndustryRoleBlueprint],
    ) -> IndustryInstanceDetail:
        record = self._industry_instance_repository.get_instance(instance_id)
        if record is None:
            raise KeyError(f"Industry instance '{instance_id}' not found")
        team = self._materialize_team_blueprint(record).model_copy(
            update={"agents": list(agents)},
        )
        self._industry_instance_repository.upsert_instance(
            record.model_copy(
                update={
                    "team_payload": team.model_dump(mode="json"),
                    "agent_ids": [agent.agent_id for agent in team.agents],
                    "updated_at": _utc_now(),
                },
            ),
        )
        self._normalize_industry_surfaces()
        detail = self.get_instance_detail(instance_id)
        if detail is None:
            raise KeyError(f"Industry instance '{instance_id}' not found")
        return detail
    def _role_has_live_work(
        self,
        *,
        record: IndustryInstanceRecord,
        agent_id: str,
        role_id: str,
    ) -> bool:
        normalized_agent_id = _string(agent_id)
        normalized_role_id = normalize_industry_role_id(role_id)
        if normalized_agent_id is None or normalized_role_id is None:
            return False
        for item in self._list_backlog_items(record.instance_id, limit=None):
            if item.status in {"completed", "deferred", "cancelled"}:
                continue
            metadata = dict(item.metadata or {})
            if (
                _string(metadata.get("owner_agent_id")) == normalized_agent_id
                or normalize_industry_role_id(_string(metadata.get("industry_role_id")))
                == normalized_role_id
                or _string(metadata.get("seat_target_agent_id")) == normalized_agent_id
                or normalize_industry_role_id(_string(metadata.get("seat_target_role_id")))
                == normalized_role_id
                or _string(metadata.get("source_owner_agent_id")) == normalized_agent_id
                or normalize_industry_role_id(_string(metadata.get("source_industry_role_id")))
                == normalized_role_id
            ):
                return True
        for assignment in self._list_assignment_records(record.instance_id):
            if assignment.status not in {"planned", "queued", "running", "waiting-report"}:
                continue
            if (
                _string(assignment.owner_agent_id) == normalized_agent_id
                or normalize_industry_role_id(_string(assignment.owner_role_id))
                == normalized_role_id
            ):
                return True
        for report in self._list_agent_report_records(
            record.instance_id,
            processed=False,
            limit=None,
        ):
            if (
                _string(report.owner_agent_id) == normalized_agent_id
                or normalize_industry_role_id(_string(report.owner_role_id))
                == normalized_role_id
            ):
                return True
        return False
    def _select_primary_assignment_for_role(
        self,
        *,
        assignments: list[AssignmentRecord],
    ) -> AssignmentRecord | None:
        if not assignments:
            return None
        status_priority = {
            "running": 0,
            "queued": 1,
            "planned": 2,
            "waiting-report": 3,
        }
        candidates = [
            assignment
            for assignment in assignments
            if assignment.status in status_priority
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda assignment: (
                status_priority.get(assignment.status, 99),
                -(
                    (assignment.updated_at or assignment.created_at or _utc_now()).timestamp()
                ),
            ),
        )

    def _resolve_role_runtime_sync_status(
        self,
        *,
        agent_id: str,
        primary_assignment: AssignmentRecord | None,
        goal_link: tuple[str, str] | None,
    ) -> str:
        existing = (
            self._agent_runtime_repository.get_runtime(agent_id)
            if self._agent_runtime_repository is not None
            else None
        )
        if primary_assignment is not None:
            if primary_assignment.status == "running":
                return "running"
            return "waiting"
        if existing is not None and existing.runtime_status == "blocked":
            return "blocked"
        if existing is not None and (
            existing.runtime_status == "running"
            or existing.current_task_id
            or existing.current_mailbox_id
            or int(existing.queue_depth or 0) > 0
        ):
            return "running"
        if goal_link is not None:
            return "running"
        return "idle"

    def _sync_role_runtime_surfaces_for_record(
        self,
        *,
        record: IndustryInstanceRecord,
    ) -> None:
        team = self._materialize_team_blueprint(record)
        goal_links = self._list_active_goal_links_for_instance(record)
        current_cycle = self._current_operating_cycle_record(record.instance_id)
        assignments = self._list_assignment_records(
            record.instance_id,
            cycle_id=current_cycle.id if current_cycle is not None else None,
        )
        assignments_by_agent_id: dict[str, list[AssignmentRecord]] = {}
        assignments_by_role_id: dict[str, list[AssignmentRecord]] = {}
        for assignment in assignments:
            if assignment.status not in {"planned", "queued", "running", "waiting-report"}:
                continue
            owner_agent_id = _string(assignment.owner_agent_id)
            if owner_agent_id is not None:
                assignments_by_agent_id.setdefault(owner_agent_id, []).append(assignment)
            owner_role_id = normalize_industry_role_id(_string(assignment.owner_role_id))
            if owner_role_id is not None:
                assignments_by_role_id.setdefault(owner_role_id, []).append(assignment)
        for agent in team.agents:
            candidates = list(assignments_by_agent_id.get(agent.agent_id, []))
            normalized_role_id = normalize_industry_role_id(agent.role_id)
            if normalized_role_id is not None:
                for assignment in assignments_by_role_id.get(normalized_role_id, []):
                    if all(item.id != assignment.id for item in candidates):
                        candidates.append(assignment)
            primary_assignment = self._select_primary_assignment_for_role(
                assignments=candidates,
            )
            goal_link = goal_links.get(agent.agent_id)
            goal_id = (
                goal_link[0]
                if goal_link is not None
                else (
                    _string(primary_assignment.goal_id)
                    if primary_assignment is not None
                    else None
                )
            )
            goal_title = (
                goal_link[1]
                if goal_link is not None
                else (
                    _string(primary_assignment.title)
                    if primary_assignment is not None
                    else None
                )
            )
            status = self._resolve_role_runtime_sync_status(
                agent_id=agent.agent_id,
                primary_assignment=primary_assignment,
                goal_link=goal_link,
            )
            self._upsert_agent_profile(
                agent,
                instance_id=record.instance_id,
                goal_id=goal_id,
                goal_title=goal_title,
                status=status,
            )
            self._sync_actor_runtime_surface(
                agent=agent,
                instance_id=record.instance_id,
                owner_scope=record.owner_scope,
                goal_id=goal_id,
                goal_title=goal_title,
                status=status,
                assignment_id=primary_assignment.id if primary_assignment is not None else None,
                assignment_title=(
                    _string(primary_assignment.title)
                    if primary_assignment is not None
                    else None
                ),
                assignment_summary=(
                    _string(primary_assignment.summary)
                    if primary_assignment is not None
                    else None
                ),
                assignment_status=(
                    _string(primary_assignment.status)
                    if primary_assignment is not None
                    else None
                ),
            )

    def _retire_completed_temporary_roles(
        self,
        *,
        record: IndustryInstanceRecord,
    ) -> IndustryInstanceRecord:
        team = self._materialize_team_blueprint(record)
        retired_pairs: set[tuple[str, str]] = set()
        for role in team.agents:
            if role.employment_mode != "temporary":
                continue
            if is_execution_core_role_id(role.role_id):
                continue
            if self._role_has_live_work(
                record=record,
                agent_id=role.agent_id,
                role_id=role.role_id,
            ):
                continue
            retired_pairs.add((role.role_id, role.agent_id))
        if not retired_pairs:
            return record
        survivors = [
            agent
            for agent in team.agents
            if (agent.role_id, agent.agent_id) not in retired_pairs
        ]
        self._replace_instance_team_agents(
            instance_id=record.instance_id,
            agents=survivors,
        )
        refreshed = self._industry_instance_repository.get_instance(record.instance_id)
        return refreshed or record
    def promote_role_in_instance_team(
        self,
        instance_id: str,
        *,
        role: IndustryRoleBlueprint | None = None,
        role_id: str | None = None,
        agent_id: str | None = None,
    ) -> IndustryInstanceDetail:
        detail = self.get_instance_detail(instance_id)
        if detail is None:
            raise KeyError(f"Industry instance '{instance_id}' not found")
        incoming_role_id = role.role_id if role is not None else role_id
        incoming_agent_id = role.agent_id if role is not None else agent_id
        current = self._match_instance_team_role(
            detail.team,
            role_id=incoming_role_id,
            agent_id=incoming_agent_id,
        )
        if current is None:
            raise KeyError("Target industry role was not found")
        next_role = current.model_copy(
            update={
                **(
                    role.model_dump(mode="python")
                    if role is not None
                    else {}
                ),
                "role_id": current.role_id,
                "agent_id": current.agent_id,
                "employment_mode": "career",
                "activation_mode": (
                    role.activation_mode
                    if role is not None
                    else "persistent"
                ),
                "suspendable": (
                    role.suspendable
                    if role is not None
                    else False
                ),
            },
        )
        next_agents = [
            next_role
            if agent.role_id == current.role_id or agent.agent_id == current.agent_id
            else agent
            for agent in detail.team.agents
        ]
        return self._replace_instance_team_agents(
            instance_id=instance_id,
            agents=next_agents,
        )
    def retire_role_from_instance_team(
        self,
        instance_id: str,
        *,
        role_id: str | None = None,
        agent_id: str | None = None,
        force: bool = False,
    ) -> IndustryInstanceDetail:
        detail = self.get_instance_detail(instance_id)
        if detail is None:
            raise KeyError(f"Industry instance '{instance_id}' not found")
        current = self._match_instance_team_role(
            detail.team,
            role_id=role_id,
            agent_id=agent_id,
        )
        if current is None:
            raise KeyError("Target industry role was not found")
        if not force and is_execution_core_role_id(current.role_id):
            raise ValueError("Execution core cannot be removed without force")
        record = self._industry_instance_repository.get_instance(instance_id)
        if record is None:
            raise KeyError(f"Industry instance '{instance_id}' not found")
        if not force and self._role_has_live_work(
            record=record,
            agent_id=current.agent_id,
            role_id=current.role_id,
        ):
            raise ValueError("Role still has live work and cannot retire yet")
        next_agents = [
            agent
            for agent in detail.team.agents
            if agent.role_id != current.role_id and agent.agent_id != current.agent_id
        ]
        return self._replace_instance_team_agents(
            instance_id=instance_id,
            agents=next_agents,
        )
    def _resolve_goal_kickoff_stage(
        self,
        goal: GoalRecord,
        *,
        override: GoalOverrideRecord | None = None,
        record: IndustryInstanceRecord | None = None,
        team: IndustryTeamBlueprint | None = None,
    ) -> str:
        kickoff_stage = _string(
            self._resolve_goal_runtime_context(
                goal,
                override=override,
                record=record,
                team=team,
            ).get("kickoff_stage"),
        )
        if kickoff_stage in {"learning", "execution"}:
            return kickoff_stage
        return "execution"
    def _resolve_schedule_kickoff_stage(self, schedule: object | None) -> str:
        spec_payload = dict(getattr(schedule, "spec_payload", None) or {})
        meta_mapping = (
            dict(spec_payload.get("meta"))
            if isinstance(spec_payload.get("meta"), dict)
            else {}
        )
        kickoff_stage = _string(meta_mapping.get("kickoff_stage"))
        if kickoff_stage in {"learning", "execution"}:
            return kickoff_stage
        role_id = normalize_industry_role_id(_string(meta_mapping.get("industry_role_id")))
        return "learning" if role_id == "researcher" else "execution"
    def _kickoff_assignment_backlog_item(
        self,
        assignment: AssignmentRecord,
    ) -> BacklogItemRecord | None:
        if self._backlog_service is None or assignment.backlog_item_id is None:
            return None
        return self._backlog_service.get_item(assignment.backlog_item_id)
    def _resolve_assignment_kickoff_stage(
        self,
        assignment: AssignmentRecord,
        *,
        backlog_item: BacklogItemRecord | None = None,
    ) -> str:
        assignment_metadata = dict(assignment.metadata or {})
        kickoff_stage = _string(assignment_metadata.get("kickoff_stage"))
        if kickoff_stage in {"learning", "execution"}:
            return kickoff_stage
        resolved_backlog_item = backlog_item or self._kickoff_assignment_backlog_item(
            assignment,
        )
        if resolved_backlog_item is not None:
            backlog_metadata = dict(resolved_backlog_item.metadata or {})
            kickoff_stage = _string(backlog_metadata.get("kickoff_stage"))
            if kickoff_stage in {"learning", "execution"}:
                return kickoff_stage
        goal_id = _string(assignment.goal_id)
        if goal_id is not None:
            goal = self._goal_service.get_goal(goal_id)
            if goal is not None:
                override = self._goal_override_repository.get_override(goal.id)
                return self._resolve_goal_kickoff_stage(
                    goal,
                    override=override,
                )
        role_id = normalize_industry_role_id(
            _string(assignment_metadata.get("industry_role_id"))
            or _string(assignment.owner_role_id),
        )
        return "learning" if role_id == "researcher" else "execution"
    def _assignment_has_live_task(
        self,
        assignment: AssignmentRecord,
    ) -> bool:
        task_repository = getattr(self._goal_service, "_task_repository", None)
        if task_repository is None:
            return False
        task_runtime_repository = getattr(
            self._goal_service,
            "_task_runtime_repository",
            None,
        )
        seen_task_ids: set[str] = set()
        tasks: list[TaskRecord] = []
        if assignment.id:
            for task in task_repository.list_tasks(
                assignment_ids=[assignment.id],
                limit=None,
            ):
                if task.id in seen_task_ids:
                    continue
                seen_task_ids.add(task.id)
                tasks.append(task)
        goal_id = _string(assignment.goal_id)
        if goal_id is not None and not tasks:
            for task in task_repository.list_tasks(goal_id=goal_id):
                if task.id in seen_task_ids:
                    continue
                seen_task_ids.add(task.id)
                tasks.append(task)
        for task in tasks:
            if task.status in {
                "created",
                "queued",
                "running",
                "needs-confirm",
                "waiting",
                "blocked",
            }:
                return True
            if task_runtime_repository is None:
                continue
            runtime = task_runtime_repository.get_runtime(task.id)
            if runtime is None:
                continue
            if runtime.current_phase in {
                "compiled",
                "risk-check",
                "executing",
                "waiting-confirm",
            }:
                return True
            if runtime.runtime_status in {
                "cold",
                "hydrating",
                "active",
                "waiting-confirm",
            }:
                return True
        return False
    def _list_pending_kickoff_assignments(
        self,
        record: IndustryInstanceRecord,
    ) -> list[AssignmentRecord]:
        current_cycle = self._current_operating_cycle_record(record.instance_id)
        pending: list[AssignmentRecord] = []
        for assignment in self._list_assignment_records(
            record.instance_id,
            cycle_id=current_cycle.id if current_cycle is not None else None,
        ):
            if assignment.status in {"completed", "waiting-report", "failed", "cancelled"}:
                continue
            if self._assignment_has_live_task(assignment):
                continue
            pending.append(assignment)
        return pending
    def _list_live_kickoff_assignments(
        self,
        record: IndustryInstanceRecord,
        *,
        stage: str,
    ) -> list[AssignmentRecord]:
        current_cycle = self._current_operating_cycle_record(record.instance_id)
        live_assignments: list[AssignmentRecord] = []
        for assignment in self._list_assignment_records(
            record.instance_id,
            cycle_id=current_cycle.id if current_cycle is not None else None,
        ):
            if self._resolve_assignment_kickoff_stage(assignment) != stage:
                continue
            if not self._assignment_has_live_task(assignment):
                continue
            live_assignments.append(assignment)
        return live_assignments
    def _reconcile_kickoff_autonomy_status(
        self,
        record: IndustryInstanceRecord,
    ) -> IndustryInstanceRecord:
        if _string(record.lifecycle_status) == "retired":
            return record
        pending_assignments = self._list_pending_kickoff_assignments(record)
        pending_learning = any(
            self._resolve_assignment_kickoff_stage(assignment) == "learning"
            for assignment in pending_assignments
        )
        pending_execution = any(
            self._resolve_assignment_kickoff_stage(assignment) == "execution"
            for assignment in pending_assignments
        )
        current_autonomy_status = _string(record.autonomy_status) or "waiting-confirm"
        next_autonomy_status = current_autonomy_status
        if self._list_live_kickoff_assignments(record, stage="learning"):
            next_autonomy_status = "learning"
        elif pending_learning:
            next_autonomy_status = (
                "learning"
                if current_autonomy_status in {"learning", "coordinating"}
                else "waiting-confirm"
            )
        elif pending_execution:
            next_autonomy_status = (
                "coordinating"
                if current_autonomy_status in {"learning", "coordinating"}
                else "waiting-confirm"
            )
        elif current_autonomy_status in {"waiting-confirm", "learning"} and self._instance_has_live_operation_surface(record):
            next_autonomy_status = "coordinating"
        elif current_autonomy_status in {"coordinating"} and self._instance_has_live_operation_surface(record):
            next_autonomy_status = "coordinating"
        if next_autonomy_status == current_autonomy_status:
            return record
        return self._industry_instance_repository.upsert_instance(
            record.model_copy(
                update={
                    "autonomy_status": next_autonomy_status,
                    "updated_at": _utc_now(),
                },
            ),
        )
    def list_instances(
        self,
        *,
        status: str | None = "active",
        limit: int | None = None,
    ) -> list[IndustryInstanceSummary]:
        records = [
            self.reconcile_instance_status(record.instance_id) or record
            for record in self._industry_instance_repository.list_instances(
                status=None,
                limit=None,
            )
        ]
        summaries = [
            summary
            for summary in (self._build_instance_summary(record) for record in records)
            if status is None or summary.status == status
            if any(
                (summary.stats.get(key) or 0) > 0
                for key in (
                    "agent_count",
                    "lane_count",
                    "backlog_count",
                    "cycle_count",
                    "assignment_count",
                    "report_count",
                    "schedule_count",
                )
            )
        ]
        summaries.sort(
            key=lambda item: item.updated_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        if limit is not None:
            summaries = summaries[: max(0, limit)]
        return summaries
    def count_instances(self) -> int:
        return len(self.list_instances(status="active", limit=None))
    def get_instance_record(self, instance_id: str) -> IndustryInstanceRecord | None:
        return self.reconcile_instance_status(instance_id)
    def get_instance_detail(
        self,
        instance_id: str,
        *,
        assignment_id: str | None = None,
        backlog_item_id: str | None = None,
    ) -> IndustryInstanceDetail | None:
        record = self.reconcile_instance_status(instance_id)
        if record is None:
            return None
        return self._build_instance_detail(
            record,
            assignment_id=assignment_id,
            backlog_item_id=backlog_item_id,
        )
    def reconcile_instance_status(
        self,
        instance_id: str,
    ) -> IndustryInstanceRecord | None:
        record = self._industry_instance_repository.get_instance(instance_id)
        if record is None:
            return None
        record = self._reconcile_kickoff_autonomy_status(record)
        next_status = self._derive_instance_status(record)
        if next_status == record.status:
            return record
        updated = record.model_copy(
            update={
                "status": next_status,
                "updated_at": _utc_now(),
            },
        )
        return self._industry_instance_repository.upsert_instance(updated)
    def reconcile_instance_status_for_goal(self, goal_id: str) -> None:
        normalized_goal_id = _string(goal_id)
        if not normalized_goal_id:
            return
        goal = self._goal_service.get_goal(normalized_goal_id)
        if goal is None:
            return
        override = self._goal_override_repository.get_override(goal.id)
        candidate_records: list[IndustryInstanceRecord] = []
        if goal.industry_instance_id:
            record = self._industry_instance_repository.get_instance(goal.industry_instance_id)
            if record is not None:
                candidate_records.append(record)
        elif goal.owner_scope:
            candidate_records.extend(
                self._industry_instance_repository.list_instances(
                    owner_scope=goal.owner_scope,
                    limit=None,
                ),
            )
        for record in candidate_records:
            if not self._goal_belongs_to_instance(
                goal,
                record=record,
                override=override,
            ):
                continue
            current_cycle = self._current_operating_cycle_record(record.instance_id)
            cycle_id = current_cycle.id if current_cycle is not None else None
            self._ensure_terminal_agent_reports(
                record=record,
                cycle_id=cycle_id,
            )
            self._process_pending_agent_reports(
                record=record,
                cycle_id=cycle_id,
            )
            if current_cycle is not None and self._operating_cycle_service is not None:
                self._operating_cycle_service.reconcile_cycle(
                    current_cycle,
                    goal_statuses=[
                        goal.status
                        for owned_goal_id in self._resolve_instance_goal_ids(record)
                        if (goal := self._goal_service.get_goal(owned_goal_id)) is not None
                    ],
                    assignment_statuses=[
                        assignment.status
                        for assignment in self._list_assignment_records(
                            record.instance_id,
                            cycle_id=current_cycle.id,
                        )
                    ],
                    report_ids=[
                        report.id
                        for report in self._list_agent_report_records(
                            record.instance_id,
                            cycle_id=current_cycle.id,
                            limit=None,
                        )
                    ],
                    allow_paused_goals_without_confirmation=(
                        _string(record.autonomy_status) in {"learning", "coordinating"}
                    ),
                )
            record = self._retire_completed_temporary_roles(record=record)
            updated = self.reconcile_instance_status(record.instance_id) or record
            self._sync_role_runtime_surfaces_for_record(record=updated)
            self._sync_strategy_memory_for_instance(updated)
    async def kickoff_execution_from_chat(
        self,
        *,
        industry_instance_id: str,
        message_text: str,
        owner_agent_id: str | None = None,
        session_id: str | None = None,
        channel: str | None = None,
        execute_background: bool = False,
        trigger_source: str | None = None,
        trigger_reason_override: str | None = None,
    ) -> dict[str, Any] | None:
        record = self._industry_instance_repository.get_instance(industry_instance_id)
        if record is None:
            return None
        acquisition_runner = getattr(
            self._learning_service,
            "run_industry_acquisition_cycle",
            None,
        )

        async def _maybe_run_learning_acquisition_cycle() -> dict[str, Any] | None:
            if execute_background:
                return None
            if not callable(acquisition_runner):
                return None
            try:
                return await acquisition_runner(
                    industry_instance_id=record.instance_id,
                    actor=owner_agent_id or EXECUTION_CORE_AGENT_ID,
                    rerun_existing=False,
                )
            except Exception as exc:
                return {
                    "success": False,
                    "industry_instance_id": record.instance_id,
                    "summary": str(exc).strip() or "Automatic acquisition cycle failed.",
                    "proposals": [],
                    "plans": [],
                    "onboarding_runs": [],
                    "warnings": ["acquisition-cycle-exception"],
                }
        pending_assignments = self._list_pending_kickoff_assignments(record)
        pending_assignment_entries = [
            (
                assignment,
                self._kickoff_assignment_backlog_item(assignment),
                self._resolve_assignment_kickoff_stage(
                    assignment,
                    backlog_item=self._kickoff_assignment_backlog_item(assignment),
                ),
            )
            for assignment in pending_assignments
        ]
        if not pending_assignment_entries:
            if self._list_live_kickoff_assignments(record, stage="learning"):
                return {
                    "activated": False,
                    "kickoff_stage": "learning",
                    "blocked_stage": "learning",
                    "blocked_reason": "Industry learning stage is still in progress.",
                    "started_assignment_ids": [],
                    "started_assignment_titles": [],
                    "assignment_dispatches": [],
                    "goal_dispatches": [],
                    "pending_execution_remaining": False,
                    "acquisition_cycle": await _maybe_run_learning_acquisition_cycle(),
                }
            return None
        has_pending_learning = any(
            stage == "learning"
            for _assignment, _backlog_item, stage in pending_assignment_entries
        )
        if has_pending_learning:
            kickoff_stage = "learning"
        elif self._list_live_kickoff_assignments(record, stage="learning"):
            return {
                "activated": False,
                "kickoff_stage": "learning",
                "blocked_stage": "learning",
                "blocked_reason": "Industry learning stage is still in progress.",
                "started_assignment_ids": [],
                "started_assignment_titles": [],
                "assignment_dispatches": [],
                "goal_dispatches": [],
                "pending_execution_remaining": True,
                "acquisition_cycle": await _maybe_run_learning_acquisition_cycle(),
            }
        else:
            kickoff_stage = "execution"
        selected_assignment_entries = [
            (assignment, backlog_item)
            for assignment, backlog_item, stage in pending_assignment_entries
            if stage == kickoff_stage
        ]
        if not selected_assignment_entries:
            return None
        current_cycle = self._current_operating_cycle_record(record.instance_id)
        trigger_reason = (
            "Industry learning stage started from the execution-core control thread."
            if kickoff_stage == "learning"
            else "Execution stage resumed from the execution-core control thread."
        )
        trigger_message_text = _string(message_text)
        if trigger_reason_override is not None:
            trigger_reason = trigger_reason_override
        elif trigger_message_text is not None:
            trigger_reason = f"{trigger_reason} Operator message: {trigger_message_text}"
        assignment_dispatch_result = None
        if selected_assignment_entries:
            assignment_dispatch_result = await self._dispatch_operating_cycle_assignments(
                instance_id=record.instance_id,
                assignment_ids=[
                    assignment.id for assignment, _backlog_item in selected_assignment_entries
                ],
                actor=owner_agent_id or EXECUTION_CORE_AGENT_ID,
                allow_waiting_confirm=True,
                include_execution_core=True,
                execute_background=execute_background,
            )
        assignment_dispatches = list(
            (assignment_dispatch_result or {}).get("assignment_dispatches") or [],
        )
        selected_assignment_by_id = {
            assignment.id: assignment
            for assignment, _backlog_item in selected_assignment_entries
        }
        started_assignment_ids = [
            assignment_id
            for assignment_id in (
                _string(item.get("assignment_id")) for item in assignment_dispatches
            )
            if assignment_id is not None and assignment_id in selected_assignment_by_id
        ]
        started_assignment_titles = [
            selected_assignment_by_id[assignment_id].title
            for assignment_id in started_assignment_ids
        ]
        pending_execution_transition = kickoff_stage == "learning" and (
            any(
                stage == "execution"
                for _assignment, _backlog_item, stage in pending_assignment_entries
            )
        )
        updated_record = self._industry_instance_repository.upsert_instance(
            record.model_copy(
                update={
                    "autonomy_status": "learning" if kickoff_stage == "learning" else "coordinating",
                    "current_cycle_id": current_cycle.id if current_cycle is not None else record.current_cycle_id,
                    "next_cycle_due_at": current_cycle.due_at if current_cycle is not None else record.next_cycle_due_at,
                    "last_cycle_started_at": current_cycle.started_at if current_cycle is not None else record.last_cycle_started_at,
                    "updated_at": _utc_now(),
                },
            ),
        )
        if current_cycle is not None and self._operating_cycle_service is not None:
            self._operating_cycle_service.reconcile_cycle(
                current_cycle,
                goal_statuses=[],
                assignment_statuses=[
                    assignment.status
                    for assignment in self._list_assignment_records(
                        updated_record.instance_id,
                        cycle_id=current_cycle.id,
                    )
                ],
                report_ids=[
                    report.id
                    for report in self._list_agent_report_records(
                        updated_record.instance_id,
                        cycle_id=current_cycle.id,
                        limit=None,
                    )
                ],
                allow_paused_goals_without_confirmation=(
                    _string(updated_record.autonomy_status) in {"learning", "coordinating"}
                ),
            )
        if execute_background:
            self._sync_role_runtime_surfaces_for_record(record=updated_record)
        else:
            updated_record = (
                self.reconcile_instance_status(updated_record.instance_id) or updated_record
            )
            self._sync_role_runtime_surfaces_for_record(record=updated_record)
            self._sync_strategy_memory_for_instance(updated_record)
        acquisition_cycle: dict[str, Any] | None = None
        if kickoff_stage == "learning":
            acquisition_cycle = await _maybe_run_learning_acquisition_cycle()
        return {
            "activated": bool(started_assignment_ids),
            "kickoff_stage": kickoff_stage,
            "started_assignment_ids": started_assignment_ids,
            "started_assignment_titles": started_assignment_titles,
            "assignment_dispatches": assignment_dispatches,
            "goal_dispatches": [],
            "pending_execution_remaining": pending_execution_transition,
            "acquisition_cycle": acquisition_cycle,
        }
    def _should_auto_resume_execution_stage(
        self,
        record: IndustryInstanceRecord,
    ) -> bool:
        if _string(record.lifecycle_status) == "retired":
            return False
        if _string(record.autonomy_status) not in {"learning", "coordinating"}:
            return False
        if self._list_live_kickoff_assignments(record, stage="learning"):
            return False
        pending_assignments = self._list_pending_kickoff_assignments(record)
        has_pending_learning = any(
            self._resolve_assignment_kickoff_stage(assignment) == "learning"
            for assignment in pending_assignments
        )
        has_pending_execution = any(
            self._resolve_assignment_kickoff_stage(assignment) == "execution"
            for assignment in pending_assignments
        )
        return not has_pending_learning and has_pending_execution
    async def _maybe_auto_resume_execution_stage(
        self,
        instance_id: str,
    ) -> dict[str, Any] | None:
        record = self.reconcile_instance_status(instance_id)
        if record is None or not self._should_auto_resume_execution_stage(record):
            return None
        return await self.kickoff_execution_from_chat(
            industry_instance_id=instance_id,
            message_text="继续执行",
            owner_agent_id=EXECUTION_CORE_AGENT_ID,
            execute_background=True,
            trigger_source="system:auto-resume-execution",
            trigger_reason_override=(
                "Execution stage resumed automatically after the learning stage completed."
            ),
        )
    async def apply_execution_chat_writeback(
        self,
        *,
        industry_instance_id: str,
        message_text: str,
        owner_agent_id: str | None = None,
        session_id: str | None = None,
        channel: str | None = None,
        writeback_plan: ChatWritebackPlan | None = None,
    ) -> dict[str, Any] | None:
        record = self._industry_instance_repository.get_instance(industry_instance_id)
        if record is None:
            return None
        plan = writeback_plan
        if plan is None:
            raise RuntimeError(
                "Execution-core chat writeback now requires a structured approved writeback plan.",
            )
        if plan is None or not plan.active:
            return None
        profile = IndustryProfile.model_validate(
            record.profile_payload or {"industry": record.label},
        )
        team = self._materialize_team_blueprint(record)
        execution_core_identity = self._materialize_execution_core_identity(
            record,
            profile=profile,
            team=team,
        )
        resolved_execution_owner_agent_id = (
            owner_agent_id
            or execution_core_identity.agent_id
            or EXECUTION_CORE_AGENT_ID
        )
        (
            team_surface_capability_ids,
            team_surface_capability_mounts,
            team_surface_environment_texts,
        ) = self._collect_team_surface_context(team=team)
        requested_surfaces = self._list_chat_writeback_requested_surfaces(
            message_text=plan.normalized_text,
            plan=plan,
            capability_ids=team_surface_capability_ids,
            capability_mounts=team_surface_capability_mounts,
            environment_texts=team_surface_environment_texts,
        )
        matched_role, target_match_signals = self._resolve_chat_writeback_target_role(
            record=record,
            team=team,
            message_text=plan.normalized_text,
            requested_surfaces=requested_surfaces,
        )
        seat_resolution = resolve_chat_writeback_seat_gap(
            message_text=plan.normalized_text,
            requested_surfaces=requested_surfaces,
            matched_role=matched_role,
            team=team,
        )
        seat_resolution_kind = seat_resolution.kind
        seat_resolution_reason = _string(seat_resolution.reason) or ""
        requested_surfaces = list(seat_resolution.requested_surfaces or requested_surfaces)
        control_thread_id = self._chat_writeback_control_thread_id(
            instance_id=record.instance_id,
            session_id=session_id,
        )
        control_thread_binding = (
            self._agent_thread_binding_repository.get_binding(control_thread_id)
            if self._agent_thread_binding_repository is not None
            else None
        )
        control_thread_work_context_id = _string(
            getattr(control_thread_binding, "work_context_id", None),
        )
        chat_writeback_channel = _string(channel) or "console"
        chat_writeback_environment_ref = (
            f"session:{chat_writeback_channel}:industry:{record.instance_id}"
        )
        decision_request_id: str | None = None
        proposal_status: str | None = None
        capability_gap_closure_results: list[IndustryBootstrapInstallResult] = []
        target_role = matched_role
        dispatch_role = matched_role
        if seat_resolution_kind != "existing-role":
            plan.classifications = _unique_strings(
                list(plan.classifications),
                [seat_resolution_kind],
            )
        if seat_resolution_reason:
            target_match_signals = _unique_strings(
                list(target_match_signals),
                [seat_resolution_reason],
            )
        if seat_resolution_kind == "temporary-seat-auto" and seat_resolution.role is not None:
            seat_update = await self._submit_chat_writeback_team_update(
                record=record,
                role=seat_resolution.role,
                owner_agent_id=resolved_execution_owner_agent_id,
                session_id=session_id,
                risk_level="guarded",
                human_confirmation_required=False,
            )
            proposal_status = _string(seat_update.get("phase"))
            if seat_update.get("success"):
                refreshed_record = self._industry_instance_repository.get_instance(
                    record.instance_id,
                )
                if refreshed_record is not None:
                    record = refreshed_record
                team = self._materialize_team_blueprint(record)
                execution_core_identity = self._materialize_execution_core_identity(
                    record,
                    profile=profile,
                    team=team,
                )
                target_role = self._match_instance_team_role(
                    team,
                    role_id=seat_resolution.target_role_id,
                    agent_id=seat_resolution.target_agent_id,
                ) or seat_resolution.role
                dispatch_role = target_role
                if target_role is not None:
                    capability_gap_closure_results = (
                        await self._auto_close_temporary_seat_capability_gap(
                            record=record,
                            profile=profile,
                            role=target_role,
                            plan=plan,
                        )
                    )
                failed_capability_result = next(
                    (
                        item
                        for item in capability_gap_closure_results
                        if item.status == "failed"
                    ),
                    None,
                )
                if failed_capability_result is not None:
                    target_role = None
                    dispatch_role = None
                    seat_resolution_kind = "routing-pending"
                    seat_resolution_reason = (
                        _string(failed_capability_result.detail)
                        or "Temporary seat capability gap could not be closed automatically."
                    )
                    plan.classifications = _unique_strings(
                        list(plan.classifications),
                        ["routing-pending", "capability-gap"],
                    )
                    target_match_signals = _unique_strings(
                        list(target_match_signals),
                        [
                            "temporary seat was created but the runtime capability gap is still unresolved",
                            seat_resolution_reason,
                        ],
                    )
                else:
                    target_match_signals = _unique_strings(
                        list(target_match_signals),
                        ["temporary seat was created through the governed team updater"],
                        [
                            _string(item.detail)
                            for item in capability_gap_closure_results
                            if _string(item.detail)
                        ],
                    )
            else:
                target_role = None
                dispatch_role = None
                seat_resolution_kind = "routing-pending"
                seat_resolution_reason = _string(seat_update.get("summary")) or seat_resolution_reason
                plan.classifications = _unique_strings(
                    list(plan.classifications),
                    ["routing-pending"],
                )
                if requested_surfaces:
                    plan.classifications = _unique_strings(
                        list(plan.classifications),
                        ["capability-gap"],
                    )
                target_match_signals = _unique_strings(
                    list(target_match_signals),
                    [_string(seat_update.get("summary")) or "temporary seat creation failed"],
                )
        elif seat_resolution_kind in {
            "temporary-seat-proposal",
            "career-seat-proposal",
        } and seat_resolution.role is not None:
            seat_update = await self._submit_chat_writeback_team_update(
                record=record,
                role=seat_resolution.role,
                owner_agent_id=resolved_execution_owner_agent_id,
                session_id=session_id,
                risk_level="confirm",
                human_confirmation_required=True,
            )
            decision_request_id = _string(seat_update.get("decision_request_id"))
            proposal_status = _string(seat_update.get("phase")) or "waiting-confirm"
            if decision_request_id is not None:
                target_role = seat_resolution.role
                dispatch_role = None
                target_match_signals = _unique_strings(
                    list(target_match_signals),
                    ["governed staffing proposal is waiting for operator confirmation"],
                )
            else:
                target_role = None
                dispatch_role = None
                seat_resolution_kind = "routing-pending"
                seat_resolution_reason = _string(seat_update.get("summary")) or seat_resolution_reason
                plan.classifications = _unique_strings(
                    list(plan.classifications),
                    ["routing-pending"],
                )
                if requested_surfaces:
                    plan.classifications = _unique_strings(
                        list(plan.classifications),
                        ["capability-gap"],
                    )
        if target_role is None and seat_resolution_kind == "routing-pending":
            gap_message = (
                "no specialist matched for requested execution surface: "
                + ",".join(requested_surfaces)
                if requested_surfaces
                else "no specialist matched; kept in backlog for control-core review"
            )
            target_match_signals = _unique_strings(
                list(target_match_signals),
                [gap_message],
            )
            plan.classifications = _unique_strings(
                list(plan.classifications),
                ["routing-pending"],
            )
            if requested_surfaces:
                plan.classifications = _unique_strings(
                    list(plan.classifications),
                    ["capability-gap"],
                )
        supervisor_owner_agent_id = resolved_execution_owner_agent_id
        supervisor_industry_role_id = EXECUTION_CORE_ROLE_ID
        target_owner_agent_id = (
            target_role.agent_id
            if target_role is not None
            else None
        )
        target_industry_role_id = (
            target_role.role_id
            if target_role is not None
            else None
        )
        target_goal_kind = (
            target_role.goal_kind
            if target_role is not None
            else None
        )
        schedule_owner_agent_id = target_owner_agent_id or supervisor_owner_agent_id
        schedule_industry_role_id = (
            target_industry_role_id or supervisor_industry_role_id
        )
        schedule_goal_kind = target_goal_kind or supervisor_industry_role_id
        role_contract = target_role or seat_resolution.role
        target_role_name = (
            _string(getattr(role_contract, "role_name", None))
            if role_contract is not None
            else None
        ) or (
            _string(getattr(role_contract, "name", None))
            if role_contract is not None
            else None
        ) or (
            "Pending staffing resolution"
            if dispatch_role is None
            else execution_core_identity.role_name
        )
        target_role_summary = (
            _string(getattr(role_contract, "role_summary", None))
            if role_contract is not None
            else None
        ) or (
            "No execution assignee is committed yet; keep the work in formal backlog until staffing closes."
            if dispatch_role is None
            else execution_core_identity.role_summary
        )
        target_mission = (
            _string(getattr(role_contract, "mission", None))
            if role_contract is not None
            else None
        ) or (
            "Wait for a matched specialist seat, then execute and report back."
            if dispatch_role is None
            else execution_core_identity.mission
        )
        target_environment_constraints = (
            list(getattr(role_contract, "environment_constraints", []) or [])
            if role_contract is not None
            else []
        )
        target_evidence_expectations = (
            list(getattr(role_contract, "evidence_expectations", []) or [])
            if role_contract is not None
            else list(execution_core_identity.evidence_expectations)
        )
        target_task_mode = infer_industry_task_mode(
            role_id=schedule_industry_role_id,
            goal_kind=schedule_goal_kind,
            source="chat-writeback",
        )
        target_lane = self._resolve_goal_lane(
            instance_id=record.instance_id,
            role=dispatch_role,
            goal_kind=target_goal_kind,
            owner_agent_id=target_owner_agent_id,
        )
        if target_lane is not None and (plan.goal is not None or plan.schedule is not None):
            plan.classifications = _unique_strings(list(plan.classifications), ["lane"])
        existing_strategy = self._load_strategy_memory(
            record,
            profile=profile,
            team=team,
            execution_core_identity=execution_core_identity,
        )
        updated_profile = self._apply_chat_writeback_to_profile(profile, plan=plan)
        created_goal_ids: list[str] = []
        created_goal_titles: list[str] = []
        created_backlog_ids: list[str] = []
        reused_backlog_ids: list[str] = []
        if plan.goal is not None:
            existing_backlog = next(
                (
                    item
                    for item in self._list_backlog_items(record.instance_id, limit=None)
                    if _string(item.source_ref) == f"chat-writeback:{plan.fingerprint}"
                ),
                None,
            )
            if existing_backlog is not None:
                reused_backlog_ids.append(existing_backlog.id)
                existing_metadata = dict(existing_backlog.metadata or {})
                decision_request_id = (
                    decision_request_id
                    or _string(existing_metadata.get("decision_request_id"))
                )
                proposal_status = proposal_status or _string(
                    existing_metadata.get("proposal_status"),
                )
            elif self._backlog_service is not None:
                extra_goal_metadata = (
                    dict(plan.goal_metadata or {})
                    if isinstance(plan.goal_metadata, dict)
                    else {}
                )
                backlog_item = self._backlog_service.record_chat_writeback(
                    industry_instance_id=record.instance_id,
                    lane_id=target_lane.id if target_lane is not None else None,
                    title=plan.goal.title,
                    summary=plan.goal.summary,
                    priority=3,
                    source_ref=f"chat-writeback:{plan.fingerprint}",
                    metadata={
                        **extra_goal_metadata,
                        "plan_steps": list(plan.goal.plan_steps),
                        "owner_agent_id": target_owner_agent_id,
                        "industry_role_id": target_industry_role_id,
                        "supervisor_owner_agent_id": supervisor_owner_agent_id,
                        "supervisor_industry_role_id": supervisor_industry_role_id,
                        "supervisor_role_name": execution_core_identity.role_name,
                        "industry_role_name": target_role_name,
                        "role_name": target_role_name,
                        "role_summary": target_role_summary,
                        "mission": target_mission,
                        "environment_constraints": list(target_environment_constraints),
                        "evidence_expectations": list(target_evidence_expectations),
                        "goal_kind": target_goal_kind,
                        "task_mode": target_task_mode,
                        "report_back_mode": "summary",
                        "source": "chat-writeback",
                        "chat_writeback_fingerprint": plan.fingerprint,
                        "chat_writeback_instruction": plan.normalized_text,
                        "chat_writeback_classes": list(plan.classifications),
                        "chat_writeback_target_role_name": target_role_name,
                        "chat_writeback_target_match_signals": list(target_match_signals),
                        "chat_writeback_requested_surfaces": list(requested_surfaces),
                        "capability_gap_closure_results": [
                            item.model_dump(mode="json")
                            for item in capability_gap_closure_results
                        ],
                        "chat_writeback_channel": chat_writeback_channel,
                        "control_thread_id": control_thread_id,
                        "session_id": control_thread_id,
                        "work_context_id": control_thread_work_context_id,
                        "environment_ref": chat_writeback_environment_ref,
                        "seat_resolution_kind": seat_resolution_kind,
                        "seat_resolution_reason": seat_resolution_reason or None,
                        "seat_requested_surfaces": list(requested_surfaces),
                        "seat_target_role_id": (
                            _string(getattr(seat_resolution.role, "role_id", None))
                            if seat_resolution.role is not None
                            else target_industry_role_id
                        ),
                        "seat_target_role_name": (
                            _string(getattr(seat_resolution.role, "role_name", None))
                            if seat_resolution.role is not None
                            else target_role_name
                        ),
                        "seat_target_agent_id": (
                            _string(getattr(seat_resolution.role, "agent_id", None))
                            if seat_resolution.role is not None
                            else target_owner_agent_id
                        ),
                        "decision_request_id": decision_request_id,
                        "proposal_status": proposal_status,
                        "chat_writeback_gap_kind": (
                            "capability-gap"
                            if seat_resolution_kind == "routing-pending" and requested_surfaces
                            else "routing-pending"
                            if seat_resolution_kind == "routing-pending"
                            else seat_resolution_kind
                        ),
                    },
                )
                created_backlog_ids.append(backlog_item.id)
        created_schedule_ids: list[str] = []
        created_schedule_titles: list[str] = []
        reused_schedule_ids: list[str] = []
        if plan.schedule is not None:
            existing_schedule_id = self._find_chat_writeback_schedule(
                industry_instance_id=record.instance_id,
                fingerprint=plan.fingerprint,
            )
            if existing_schedule_id is not None:
                reused_schedule_ids.append(existing_schedule_id)
            else:
                schedule_seed = self._build_chat_writeback_schedule_seed(
                    record=record,
                    profile=updated_profile,
                    team=team,
                    plan=plan,
                    session_id=session_id,
                    channel=channel,
                    owner_agent_id=schedule_owner_agent_id,
                    industry_role_id=schedule_industry_role_id,
                    goal_kind=schedule_goal_kind,
                )
                await self._upsert_schedule_seed(schedule_seed, enabled=True)
                self._upsert_schedule_lane(
                    schedule_id=schedule_seed.schedule_id,
                    lane_id=target_lane.id if target_lane is not None else None,
                    schedule_kind="cadence",
                    trigger_target=target_goal_kind or "main-brain",
                )
                created_schedule_ids.append(schedule_seed.schedule_id)
                created_schedule_titles.append(schedule_seed.title)
        goal_dispatches: list[dict[str, Any]] = []
        profile_payload = updated_profile.model_dump(mode="json")
        active_record = record
        profile_changed = profile_payload != dict(record.profile_payload or {})
        if profile_changed:
            active_record = record.model_copy(
                update={
                    "profile_payload": profile_payload,
                    "updated_at": _utc_now(),
                },
            )
            self._industry_instance_repository.upsert_instance(active_record)
        strategy_updated = False
        strategy_id: str | None = None
        merged_strategy = None
        if self._strategy_memory_service is not None:
            merged_strategy = self._merge_chat_writeback_strategy(
                record=active_record,
                profile=updated_profile,
                team=team,
                execution_core_identity=execution_core_identity,
                existing_strategy=existing_strategy,
                plan=plan,
            )
            strategy_id = merged_strategy.strategy_id
            strategy_updated = self._strategy_memory_changed(
                existing_strategy,
                merged_strategy,
            )
            self._strategy_memory_service.upsert_strategy(merged_strategy)
        retain = getattr(self._memory_retain_service, "retain_chat_writeback", None)
        if callable(retain):
            try:
                retain(
                    industry_instance_id=active_record.instance_id,
                    title=plan.goal.title if plan.goal is not None else "Industry chat writeback",
                    content="\n".join(
                        part
                        for part in (
                            plan.normalized_text,
                            plan.goal.summary if plan.goal is not None else "",
                            plan.schedule.summary if plan.schedule is not None else "",
                            f"classifications={','.join(plan.classifications)}" if plan.classifications else "",
                        )
                        if part
                    ).strip(),
                    source_ref=f"chat-writeback:{plan.fingerprint}",
                    role_bindings=[target_industry_role_id or supervisor_industry_role_id]
                    if (target_industry_role_id or supervisor_industry_role_id)
                    else [],
                    tags=list(plan.classifications),
                )
            except Exception:
                pass
        dispatch_deferred = bool(created_backlog_ids)
        return {
            "applied": bool(
                strategy_updated
                or created_backlog_ids
                or created_schedule_ids
                or profile_changed
            ),
            "deduplicated": bool(
                not created_backlog_ids
                and not created_schedule_ids
                and (reused_backlog_ids or reused_schedule_ids)
            ),
            "fingerprint": plan.fingerprint,
            "classification": list(plan.classifications),
            "strategy_updated": strategy_updated,
            "strategy_id": strategy_id,
            "created_goal_ids": created_goal_ids,
            "created_goal_titles": created_goal_titles,
            "created_backlog_ids": created_backlog_ids,
            "goal_dispatches": goal_dispatches,
            "reused_backlog_ids": reused_backlog_ids,
            "created_schedule_ids": created_schedule_ids,
            "created_schedule_titles": created_schedule_titles,
            "reused_schedule_ids": reused_schedule_ids,
            "target_owner_agent_id": target_owner_agent_id,
            "target_industry_role_id": target_industry_role_id,
            "supervisor_owner_agent_id": supervisor_owner_agent_id,
            "supervisor_industry_role_id": supervisor_industry_role_id,
            "target_role_name": target_role_name,
            "target_lane_id": target_lane.id if target_lane is not None else None,
            "target_lane_title": target_lane.title if target_lane is not None else None,
            "target_match_signals": list(target_match_signals),
            "seat_resolution_kind": seat_resolution_kind,
            "seat_resolution_reason": seat_resolution_reason or None,
            "seat_requested_surfaces": list(requested_surfaces),
            "capability_gap_closure_results": [
                item.model_dump(mode="json")
                for item in capability_gap_closure_results
            ],
            "decision_request_id": decision_request_id,
            "proposal_status": proposal_status,
            "dispatch_deferred": dispatch_deferred,
            "delegated": False,
        }
    def _stable_prediction_source_ref(
        self,
        *,
        action_kind: str | None,
        target_agent_id: str | None,
        target_goal_id: str | None,
        title: str,
        action_payload: dict[str, object],
    ) -> str:
        normalized = {
            "action_kind": _string(action_kind),
            "target_agent_id": _string(target_agent_id),
            "target_goal_id": _string(target_goal_id),
            "title": title.strip().lower(),
            "action_payload": dict(action_payload),
        }
        serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True, default=str)
        return f"prediction:{sha1(serialized.encode('utf-8')).hexdigest()[:16]}"
    def _prediction_backlog_priority(self, priority: object | None) -> int:
        try:
            value = int(priority or 0)
        except (TypeError, ValueError):
            return 2
        return max(2, min(5, max(1, int(round(value / 25.0)))))
    def _resolve_prediction_lane_id(
        self,
        *,
        industry_instance_id: str,
        recommendation: dict[str, object],
    ) -> str | None:
        if self._operating_lane_service is None:
            return None
        metadata = _mapping(recommendation.get("metadata"))
        action_payload = _mapping(recommendation.get("action_payload"))
        target_agent_id = (
            _string(recommendation.get("target_agent_id"))
            or _string(metadata.get("target_agent_id"))
            or _string(action_payload.get("agent_id"))
        )
        lane = self._operating_lane_service.resolve_lane(
            industry_instance_id=industry_instance_id,
            lane_key=_string(metadata.get("goal_kind")) or _string(metadata.get("family_id")),
            role_id=_string(metadata.get("industry_role_id")) or _string(action_payload.get("role_id")),
            owner_agent_id=target_agent_id,
        )
        return lane.id if lane is not None else None
    def _current_prediction_review_window(self) -> str | None:
        now = datetime.now().astimezone()
        if 5 <= now.hour < 12:
            return "morning"
        if 17 <= now.hour < 23:
            return "evening"
        return None
    def _resolve_prediction_review_window(
        self,
        *,
        record: IndustryInstanceRecord,
        prediction_service: object,
        force: bool,
    ) -> str | None:
        review_window = self._current_prediction_review_window()
        if force:
            return review_window or "forced"
        if review_window is None:
            return None
        lister = getattr(prediction_service, "list_cases", None)
        if not callable(lister):
            return review_window
        review_date_local = datetime.now().astimezone().date().isoformat()
        try:
            recent_cases = lister(
                case_kind="cycle",
                industry_instance_id=record.instance_id,
                limit=12,
            )
        except Exception:
            return review_window
        for item in list(recent_cases or []):
            case_payload = _mapping(
                item.get("case") if isinstance(item, dict) else getattr(item, "case", None),
            )
            metadata = _mapping(case_payload.get("metadata"))
            if (
                _string(metadata.get("meeting_window")) == review_window
                and _string(metadata.get("review_date_local")) == review_date_local
            ):
                return None
        return review_window
    def _due_prediction_review_window(
        self,
        *,
        record: IndustryInstanceRecord,
    ) -> str | None:
        prediction_service = getattr(self, "_prediction_service", None)
        create_cycle_case = getattr(prediction_service, "create_cycle_case", None)
        if not callable(create_cycle_case):
            return None
        return self._resolve_prediction_review_window(
            record=record,
            prediction_service=prediction_service,
            force=False,
        )
    def _build_prediction_participant_inputs(
        self,
        *,
        record: IndustryInstanceRecord,
        assignments: list[AssignmentRecord],
        pending_reports: list[AgentReportRecord],
        created_reports: list[AgentReportRecord],
        processed_reports: list[AgentReportRecord],
    ) -> list[dict[str, object]]:
        combined = [*pending_reports, *created_reports, *processed_reports]
        combined.sort(key=lambda report: _sort_timestamp(report.updated_at), reverse=True)
        items: list[dict[str, object]] = []
        seen_report_ids: set[str] = set()
        seen_participants: set[str] = set()
        latest_report_by_agent_id: dict[str, AgentReportRecord] = {}
        for report in combined:
            if report.id in seen_report_ids:
                continue
            seen_report_ids.add(report.id)
            participant_key = _string(report.owner_agent_id) or _string(report.owner_role_id)
            if participant_key is not None:
                seen_participants.add(participant_key)
            owner_agent_id = _string(report.owner_agent_id)
            if owner_agent_id is not None and owner_agent_id not in latest_report_by_agent_id:
                latest_report_by_agent_id[owner_agent_id] = report
            items.append(
                {
                    "participant_kind": "agent-report",
                    "report_id": report.id,
                    "assignment_id": report.assignment_id,
                    "owner_agent_id": report.owner_agent_id,
                    "owner_role_id": report.owner_role_id,
                    "headline": report.headline,
                    "summary": report.summary,
                    "result": report.result,
                    "status": report.status,
                },
            )
            if len(items) >= 8:
                break
        assignment_titles_by_agent_id: dict[str, list[str]] = {}
        for assignment in assignments:
            owner_agent_id = _string(assignment.owner_agent_id)
            if owner_agent_id is None:
                continue
            titles = assignment_titles_by_agent_id.setdefault(owner_agent_id, [])
            if assignment.title and assignment.title not in titles and len(titles) < 3:
                titles.append(assignment.title)
        interesting_agent_ids = {EXECUTION_CORE_AGENT_ID}
        for assignment in assignments:
            owner_agent_id = _string(assignment.owner_agent_id)
            if owner_agent_id is not None:
                interesting_agent_ids.add(owner_agent_id)
        team = self._materialize_team_blueprint(record)
        for role in team.agents:
            if normalize_industry_role_id(role.role_id) == "researcher":
                interesting_agent_ids.add(role.agent_id)
        for role in team.agents:
            if role.agent_id not in interesting_agent_ids:
                continue
            participant_key = role.agent_id or role.role_id
            if participant_key in seen_participants:
                continue
            latest_report = latest_report_by_agent_id.get(role.agent_id)
            assignment_titles = assignment_titles_by_agent_id.get(role.agent_id, [])
            summary_parts = [
                part
                for part in [
                    _string(latest_report.summary) if latest_report is not None else None,
                    _string(latest_report.result) if latest_report is not None else None,
                    f"Assignments: {', '.join(assignment_titles)}." if assignment_titles else None,
                    _string(role.role_summary),
                    _string(role.mission),
                ]
                if part
            ]
            items.append(
                {
                    "participant_kind": "role-snapshot",
                    "owner_agent_id": role.agent_id,
                    "owner_role_id": role.role_id,
                    "role_name": role.role_name,
                    "headline": f"{role.role_name} structured input",
                    "summary": " ".join(summary_parts[:3]).strip(),
                    "assignment_titles": assignment_titles,
                    "status": (
                        _string(latest_report.status)
                        if latest_report is not None
                        else "assigned"
                        if assignment_titles
                        else "ready"
                    ),
                },
            )
            seen_participants.add(participant_key)
            if len(items) >= 12:
                break
        return items
    def _build_prediction_assignment_summaries(
        self,
        assignments: list[AssignmentRecord],
    ) -> list[dict[str, object]]:
        return [
            {
                "assignment_id": assignment.id,
                "goal_id": assignment.goal_id,
                "backlog_item_id": assignment.backlog_item_id,
                "owner_agent_id": assignment.owner_agent_id,
                "owner_role_id": assignment.owner_role_id,
                "title": assignment.title,
                "status": assignment.status,
            }
            for assignment in assignments[:8]
        ]
    def _build_prediction_lane_summaries(
        self,
        *,
        industry_instance_id: str,
        planning_backlog: list[BacklogItemRecord],
    ) -> list[dict[str, object]]:
        lane_backlog_counts: dict[str, int] = {}
        for item in planning_backlog:
            if item.lane_id is None:
                continue
            lane_backlog_counts[item.lane_id] = lane_backlog_counts.get(item.lane_id, 0) + 1
        lanes = self._list_operating_lanes(industry_instance_id, status="active")
        return [
            {
                "lane_id": lane.id,
                "title": lane.title,
                "status": lane.status,
                "priority": lane.priority,
                "owner_agent_id": lane.owner_agent_id,
                "owner_role_id": lane.owner_role_id,
                "open_backlog_count": lane_backlog_counts.get(lane.id, 0),
            }
            for lane in lanes[:8]
        ]

    def _build_prediction_formal_planning_context(
        self,
        *,
        record: IndustryInstanceRecord,
        cycle_decision: CyclePlanningDecision,
        meeting_window: str,
        strategy_constraints_sidecar: Mapping[str, Any] | None = None,
        report_replan_sidecar: Mapping[str, Any] | None = None,
    ) -> dict[str, object]:
        metadata = dict(cycle_decision.metadata or {})
        review_anchor = cycle_decision.selected_backlog_item_ids or [
            cycle_decision.reason,
            meeting_window,
        ]
        review_ref = "|".join(
            str(part).strip()
            for part in (
                "formal-cycle-review",
                record.instance_id,
                *review_anchor[:4],
            )
            if str(part).strip()
        )
        return {
            "review_ref": review_ref,
            "review_window": meeting_window,
            "summary": cycle_decision.summary,
            "planning_policy": list(cycle_decision.planning_policy or []),
            "strategy_constraints": dict(strategy_constraints_sidecar or {}),
            "cycle_decision": self._planner_sidecar_payload(cycle_decision),
            "report_replan": dict(report_replan_sidecar or {}),
            "selected_lane_ids": list(cycle_decision.selected_lane_ids or []),
            "selected_backlog_item_ids": list(
                cycle_decision.selected_backlog_item_ids or []
            ),
            "metadata": metadata,
        }

    def _create_cycle_prediction_opportunities(
        self,
        *,
        record: IndustryInstanceRecord,
        actor: str,
        force: bool,
        current_cycle: OperatingCycleRecord | None,
        open_backlog: list[BacklogItemRecord],
        pending_reports: list[AgentReportRecord],
        created_reports: list[AgentReportRecord],
        processed_reports: list[AgentReportRecord],
        strategy_constraints: PlanningStrategyConstraints | None = None,
        formal_planning_context: Mapping[str, Any] | None = None,
        report_synthesis: Mapping[str, Any] | None = None,
        activation_result: object | None = None,
        task_subgraph: object | None = None,
    ) -> tuple[str | None, list[BacklogItemRecord]]:
        prediction_service = getattr(self, "_prediction_service", None)
        create_cycle_case = getattr(prediction_service, "create_cycle_case", None)
        if not callable(create_cycle_case) or self._backlog_service is None:
            return (None, [])
        planning_backlog = [
            item for item in open_backlog if _string(item.source_kind) != "prediction"
        ]
        meeting_window = self._resolve_prediction_review_window(
            record=record,
            prediction_service=prediction_service,
            force=force,
        )
        if meeting_window is None:
            return (None, [])
        if report_synthesis is None:
            report_synthesis = self._synthesize_agent_reports(
                instance_id=record.instance_id,
                cycle_id=current_cycle.id if current_cycle is not None else None,
                activation_result=activation_result,
            )
        if formal_planning_context is None:
            cycle_decision = self._cycle_planner.plan(
                record=record,
                current_cycle=current_cycle,
                next_cycle_due_at=record.next_cycle_due_at,
                open_backlog=self._materializable_backlog_items(planning_backlog),
                pending_reports=pending_reports,
                force=force,
                strategy_constraints=strategy_constraints,
                task_subgraph=task_subgraph,
            )
            strategy_constraints_payload = self._strategy_constraints_sidecar_payload(
                record=record,
                strategy_constraints=strategy_constraints,
            )
            report_replan_payload = self._report_replan_sidecar_payload(
                synthesis=report_synthesis,
                strategy_constraints_payload=strategy_constraints_payload,
            )
            formal_planning_context = self._build_prediction_formal_planning_context(
                record=record,
                cycle_decision=cycle_decision,
                meeting_window=meeting_window,
                strategy_constraints_sidecar=strategy_constraints_payload,
                report_replan_sidecar=report_replan_payload,
            )
        goal_statuses: dict[str, str] = {}
        for goal_id in self._resolve_instance_goal_ids(record):
            goal = self._goal_service.get_goal(goal_id)
            if goal is None:
                continue
            goal_statuses[goal.id] = goal.status
        assignments = self._list_assignment_records(
            record.instance_id,
            cycle_id=current_cycle.id if current_cycle is not None else None,
        )
        case_detail = create_cycle_case(
            industry_instance_id=record.instance_id,
            industry_label=record.label,
            owner_scope=record.owner_scope,
            owner_agent_id=EXECUTION_CORE_AGENT_ID,
            actor=actor,
            cycle_id=current_cycle.id if current_cycle is not None else None,
            pending_report_ids=[report.id for report in pending_reports],
            open_backlog_ids=[item.id for item in planning_backlog],
            open_backlog_source_refs=[
                item.source_ref or item.id
                for item in planning_backlog
            ],
            goal_statuses=goal_statuses,
            meeting_window=meeting_window,
            participant_inputs=self._build_prediction_participant_inputs(
                record=record,
                assignments=assignments,
                pending_reports=pending_reports,
                created_reports=created_reports,
                processed_reports=processed_reports,
            ),
            assignment_summaries=self._build_prediction_assignment_summaries(assignments),
            lane_summaries=self._build_prediction_lane_summaries(
                industry_instance_id=record.instance_id,
                planning_backlog=planning_backlog,
            ),
            formal_planning_context=formal_planning_context,
            report_synthesis=report_synthesis,
            force=force,
        )
        if case_detail is None:
            return (None, [])
        case_payload = _mapping(getattr(case_detail, "case", None))
        case_id = _string(case_payload.get("case_id"))
        recommendation_views = [
            view
            for view in list(getattr(case_detail, "recommendations", []) or [])
            if _string(_mapping(getattr(view, "recommendation", None)).get("status"))
            not in {"executed", "failed", "rejected"}
        ]
        recommendation_views.sort(
            key=lambda view: (
                int(_mapping(getattr(view, "recommendation", None)).get("priority") or 0),
                float(_mapping(getattr(view, "recommendation", None)).get("confidence") or 0.0),
                _string(_mapping(getattr(view, "recommendation", None)).get("recommendation_id"))
                or "",
            ),
            reverse=True,
        )
        backlog_items: list[BacklogItemRecord] = []
        for view in recommendation_views[:3]:
            recommendation = _mapping(getattr(view, "recommendation", None))
            recommendation_metadata = _mapping(recommendation.get("metadata"))
            action_payload = _mapping(recommendation.get("action_payload"))
            routes = _mapping(getattr(view, "routes", None))
            target_agent_id = (
                _string(recommendation.get("target_agent_id"))
                or _string(recommendation_metadata.get("target_agent_id"))
                or _string(action_payload.get("agent_id"))
            )
            backlog_items.append(
                self._backlog_service.record_generated_item(
                    industry_instance_id=record.instance_id,
                    lane_id=self._resolve_prediction_lane_id(
                        industry_instance_id=record.instance_id,
                        recommendation=recommendation,
                    ),
                    title=_string(recommendation.get("title")) or "Cycle Opportunity",
                    summary=(
                        _string(recommendation.get("summary"))
                        or "Prediction surfaced a governed opportunity for the main brain."
                    ),
                    priority=self._prediction_backlog_priority(recommendation.get("priority")),
                    source_kind="prediction",
                    source_ref=self._stable_prediction_source_ref(
                        action_kind=_string(recommendation.get("action_kind")),
                        target_agent_id=target_agent_id,
                        target_goal_id=_string(recommendation.get("target_goal_id")),
                        title=_string(recommendation.get("title")) or "Cycle Opportunity",
                        action_payload=action_payload,
                    ),
                    metadata={
                        "source": "operating-cycle",
                        "trigger_source": f"prediction:{case_id}" if case_id is not None else "prediction:cycle",
                        "trigger_actor": actor,
                        "trigger_reason": "Operating cycle surfaced a prediction-backed opportunity for the main brain.",
                        "prediction_case_id": case_id,
                        "prediction_recommendation_id": _string(recommendation.get("recommendation_id")),
                        "prediction_case_kind": _string(case_payload.get("case_kind")),
                        "prediction_status": _string(recommendation.get("status")),
                        "prediction_confidence": recommendation.get("confidence"),
                        "meeting_window": meeting_window,
                        "action_kind": _string(recommendation.get("action_kind")),
                        "risk_level": _string(recommendation.get("risk_level")),
                        "executable": bool(recommendation.get("executable")),
                        "owner_agent_id": target_agent_id,
                        "target_goal_id": _string(recommendation.get("target_goal_id")),
                        "industry_role_id": (
                            _string(recommendation_metadata.get("industry_role_id"))
                            or _string(action_payload.get("role_id"))
                        ),
                        "industry_role_name": (
                            _string(recommendation_metadata.get("industry_role_name"))
                            or _string(recommendation_metadata.get("suggested_role_name"))
                        ),
                        "goal_kind": (
                            _string(recommendation_metadata.get("goal_kind"))
                            or _string(recommendation_metadata.get("family_id"))
                        ),
                        "report_back_mode": "summary",
                        "source_route": _string(routes.get("case")),
                        "plan_steps": [
                            "Review the main-brain meeting recommendation and lock the concrete objective.",
                            "Execute the next governed move and leave evidence.",
                            "Report the result, blocker, or follow-up back to the main brain.",
                        ],
                    },
                ),
            )
        return (case_id, backlog_items)
    def should_run_operating_cycle(self) -> tuple[bool, str]:
        for record in self._industry_instance_repository.list_instances(status=None):
            if _string(record.status) == "retired":
                continue
            if self._list_agent_report_records(
                record.instance_id,
                processed=False,
                limit=1,
            ):
                return (True, "pending-agent-report")
            if self._materializable_backlog_items(
                self._list_backlog_items(record.instance_id, status="open", limit=None)
            ):
                return (True, "open-backlog")
            if record.next_cycle_due_at is not None and record.next_cycle_due_at <= _utc_now():
                return (True, "cycle-due")
            if self._enabled_schedule_records_for_instance(record):
                current_cycle = self._current_operating_cycle_record(record.instance_id)
                if current_cycle is None or current_cycle.status in {"completed", "cancelled"}:
                    return (True, "enabled-schedule")
            review_window = self._due_prediction_review_window(record=record)
            if review_window is not None:
                return (True, f"review-window:{review_window}")
        return (False, "no-cycle-work")
    async def run_operating_cycle(
        self,
        *,
        instance_id: str | None = None,
        actor: str = "system:automation",
        force: bool = False,
        limit: int | None = None,
        backlog_item_ids: list[str] | None = None,
        auto_dispatch_materialized_goals: bool = False,
    ) -> dict[str, Any]:
        if instance_id is not None:
            target = self._industry_instance_repository.get_instance(instance_id)
            records = [target] if target is not None else []
        else:
            records = self._industry_instance_repository.list_instances(status=None, limit=None)
        processed_instances: list[dict[str, Any]] = []
        for record in records:
            if record is None or _string(record.status) == "retired":
                continue
            result = self._run_operating_cycle_for_instance(
                record,
                actor=actor,
                force=force,
                backlog_item_ids=backlog_item_ids,
            )
            auto_dispatch = None
            if result is not None and auto_dispatch_materialized_goals:
                auto_dispatch = await self._dispatch_operating_cycle_assignments(
                    instance_id=record.instance_id,
                    assignment_ids=result.get("created_assignment_ids"),
                    actor=actor,
                )
            auto_resume = await self._maybe_auto_resume_execution_stage(
                record.instance_id,
            )
            if result is not None:
                if auto_dispatch is not None:
                    result["created_task_ids"] = list(
                        auto_dispatch.get("created_task_ids") or [],
                    )
                else:
                    result["created_task_ids"] = list(result.get("created_task_ids") or [])
                result["auto_dispatched_goal_ids"] = []
                result["goal_dispatches"] = []
                if auto_resume is not None:
                    result["auto_resumed_execution"] = True
                    result["auto_resumed_assignment_ids"] = list(
                        auto_resume.get("started_assignment_ids") or [],
                    )
                processed_instances.append(result)
            if limit is not None and len(processed_instances) >= limit:
                break
        return {
            "processed_instances": processed_instances,
            "count": len(processed_instances),
        }
    async def _dispatch_operating_cycle_assignments(
        self,
        *,
        instance_id: str,
        assignment_ids: list[str] | None,
        actor: str,
        allow_waiting_confirm: bool = False,
        include_execution_core: bool = False,
        execute_background: bool = False,
    ) -> dict[str, Any] | None:
        normalized_assignment_ids = _unique_strings(assignment_ids)
        if not normalized_assignment_ids:
            return None
        dispatcher = getattr(self._goal_service, "_dispatcher", None)
        compiler = getattr(self._goal_service, "_compiler", None)
        task_repository = getattr(self._goal_service, "_task_repository", None)
        if dispatcher is None or compiler is None or task_repository is None:
            return None
        record = self.reconcile_instance_status(instance_id)
        if record is None:
            return None
        if _string(record.autonomy_status) == "waiting-confirm" and not allow_waiting_confirm:
            return None
        current_cycle = self._current_operating_cycle_record(record.instance_id)
        cycle_id = current_cycle.id if current_cycle is not None else None
        assignments = [
            assignment
            for assignment in self._list_assignment_records(
                record.instance_id,
                cycle_id=cycle_id,
            )
            if assignment.id in normalized_assignment_ids
        ]
        if not assignments:
            return None
        existing_tasks = task_repository.list_tasks(
            industry_instance_id=record.instance_id,
            assignment_ids=normalized_assignment_ids,
            cycle_id=cycle_id,
            limit=None,
        )
        tasks_by_assignment_id: dict[str, list[TaskRecord]] = {}
        for task in existing_tasks:
            assignment_id = _string(task.assignment_id)
            if assignment_id is None:
                continue
            tasks_by_assignment_id.setdefault(assignment_id, []).append(task)
        created_task_ids: list[str] = []
        dispatches: list[dict[str, Any]] = []
        for assignment in assignments:
            owner_agent_id = _string(assignment.owner_agent_id)
            if owner_agent_id is None:
                continue
            if not include_execution_core and is_execution_core_agent_id(owner_agent_id):
                continue
            assignment_tasks = list(tasks_by_assignment_id.get(assignment.id, []))
            if assignment.task_id is not None or any(
                task.status in {"created", "queued", "running", "needs-confirm", "waiting", "blocked"}
                for task in assignment_tasks
            ):
                continue
            backlog_item = (
                self._backlog_service.get_item(assignment.backlog_item_id)
                if self._backlog_service is not None and assignment.backlog_item_id is not None
                else None
            )
            if backlog_item is None or current_cycle is None:
                continue
            unit = self._build_operating_cycle_assignment_unit(
                record=record,
                item=backlog_item,
                cycle=current_cycle,
                assignment=assignment,
                actor=actor,
            )
            compiled_specs = compiler.compile(unit)
            kernel_tasks = compiler.compile_to_kernel_tasks(unit, specs=compiled_specs)
            if not kernel_tasks:
                continue
            enqueue = getattr(self._actor_mailbox_service, "enqueue_item", None)
            block_mailbox = getattr(self._actor_mailbox_service, "block_item", None)
            primary_task_id: str | None = None
            for compiled_task in kernel_tasks:
                task = compiled_task.model_copy(update={"title": assignment.title})
                admitted = dispatcher.submit(task)
                execution_result = None
                mailbox_item = None
                if callable(enqueue):
                    mailbox_item = enqueue(
                        agent_id=owner_agent_id,
                        task_id=task.id,
                        work_context_id=task.work_context_id,
                        source_agent_id=EXECUTION_CORE_AGENT_ID,
                        parent_mailbox_id=None,
                        envelope_type="task",
                        title=assignment.title,
                        summary=assignment.summary or assignment.title,
                        capability_ref=task.capability_ref,
                        conversation_thread_id=f"agent-chat:{owner_agent_id}",
                        payload={
                            "capability_ref": task.capability_ref,
                            "environment_ref": task.environment_ref,
                            "risk_level": task.risk_level,
                            "payload": dict(task.payload or {}),
                        },
                        metadata={
                            "industry_instance_id": record.instance_id,
                            "industry_role_id": assignment.owner_role_id,
                            "assignment_id": assignment.id,
                            "lane_id": assignment.lane_id,
                            "cycle_id": assignment.cycle_id,
                            "work_context_id": task.work_context_id,
                            "execution_source": "assignment",
                        },
                    )
                    if admitted.phase != "executing" and callable(block_mailbox):
                        mailbox_item = block_mailbox(
                            mailbox_item.id,
                            reason=admitted.summary or f"Task is in phase '{admitted.phase}'",
                            task_id=task.id,
                        )
                elif admitted.phase == "executing" and not execute_background:
                    execution_result = await dispatcher.execute_task(task.id)
                created_task_ids.append(task.id)
                primary_task_id = primary_task_id or task.id
                dispatches.append(
                    {
                        "assignment_id": assignment.id,
                        "task_id": task.id,
                        "capability_ref": task.capability_ref,
                        "phase": (
                            execution_result.phase
                            if execution_result is not None
                            else admitted.phase
                        ),
                        "summary": (
                            execution_result.summary
                            if execution_result is not None
                            else admitted.summary
                        ),
                        "mailbox_id": getattr(mailbox_item, "id", None),
                    },
                )
            if primary_task_id is not None and self._assignment_repository is not None:
                self._assignment_repository.upsert_assignment(
                    assignment.model_copy(
                        update={
                            "task_id": primary_task_id,
                            "updated_at": _utc_now(),
                        },
                    ),
                )
        if not created_task_ids:
            return None
        return {
            "created_task_ids": created_task_ids,
            "assignment_dispatches": dispatches,
        }
    def _run_operating_cycle_for_instance(
        self,
        record: IndustryInstanceRecord,
        *,
        actor: str,
        force: bool,
        backlog_item_ids: list[str] | None = None,
    ) -> dict[str, Any] | None:
        if (
            self._backlog_service is None
            or self._operating_cycle_service is None
            or self._assignment_service is None
            or self._agent_report_service is None
        ):
            return None
        enabled_schedules = self._enabled_schedule_records_for_instance(record)
        self._backlog_service.ensure_schedule_items(
            industry_instance_id=record.instance_id,
            schedules=enabled_schedules,
        )
        current_cycle = self._current_operating_cycle_record(record.instance_id)
        created_reports = self._ensure_terminal_agent_reports(
            record=record,
            cycle_id=current_cycle.id if current_cycle is not None else None,
        )
        processed_reports = self._process_pending_agent_reports(
            record=record,
            cycle_id=current_cycle.id if current_cycle is not None else None,
        )
        open_backlog = self._backlog_service.list_open_items(
            industry_instance_id=record.instance_id,
            limit=None,
        )
        scoped_backlog_ids = {
            item_id
            for item_id in list(backlog_item_ids or [])
            if isinstance(item_id, str) and item_id
        }
        prediction_open_backlog = (
            [item for item in open_backlog if item.id in scoped_backlog_ids]
            if scoped_backlog_ids
            else list(open_backlog)
        )
        pending_reports = self._list_agent_report_records(
            record.instance_id,
            cycle_id=current_cycle.id if current_cycle is not None else None,
            processed=False,
            limit=None,
        )
        planning_activation_result = self._resolve_planning_activation_result(
            record=record,
            open_backlog=prediction_open_backlog,
            pending_reports=pending_reports,
        )
        planning_task_subgraph = self._resolve_planning_task_subgraph(
            record=record,
            open_backlog=prediction_open_backlog,
            pending_reports=pending_reports,
            activation_result=planning_activation_result,
        )
        prediction_strategy_constraints = self._apply_activation_to_strategy_constraints(
            constraints=self._compile_strategy_constraints(record=record),
            activation_result=planning_activation_result,
        )
        prediction_case_id, prediction_backlog_items = self._create_cycle_prediction_opportunities(
            record=record,
            actor=actor,
            force=force,
            current_cycle=current_cycle,
            open_backlog=prediction_open_backlog,
            pending_reports=pending_reports,
            created_reports=created_reports,
            processed_reports=processed_reports,
            strategy_constraints=prediction_strategy_constraints,
            activation_result=planning_activation_result,
            task_subgraph=planning_task_subgraph,
        )
        open_backlog = self._backlog_service.list_open_items(
            industry_instance_id=record.instance_id,
            limit=None,
        )
        if scoped_backlog_ids:
            open_backlog = [
                item for item in open_backlog if item.id in scoped_backlog_ids
            ]
        open_backlog = self._materializable_backlog_items(open_backlog)
        pending_reports = self._list_agent_report_records(
            record.instance_id,
            cycle_id=current_cycle.id if current_cycle is not None else None,
            processed=False,
            limit=None,
        )
        goals_by_id = {
            goal_id: goal
            for goal_id in self._resolve_instance_goal_ids(record)
            if (goal := self._goal_service.get_goal(goal_id)) is not None
        }
        assignments = self._list_assignment_records(
            record.instance_id,
            cycle_id=current_cycle.id if current_cycle is not None else None,
        )
        tasks_by_assignment_id: dict[str, list[TaskRecord]] = {}
        tasks_by_goal_id: dict[str, list[TaskRecord]] = {}
        task_repository = getattr(self._goal_service, "_task_repository", None)
        if task_repository is not None:
            existing_tasks = task_repository.list_tasks(
                industry_instance_id=record.instance_id,
                cycle_id=current_cycle.id if current_cycle is not None else None,
                limit=None,
            )
            for task in existing_tasks:
                assignment_id = _string(task.assignment_id)
                if assignment_id is not None:
                    tasks_by_assignment_id.setdefault(assignment_id, []).append(task)
                goal_id = _string(task.goal_id)
                if goal_id is not None:
                    tasks_by_goal_id.setdefault(goal_id, []).append(task)
        latest_reports_by_assignment_id = self._agent_report_service.latest_reports_by_assignment(
            industry_instance_id=record.instance_id,
            cycle_id=current_cycle.id if current_cycle is not None else None,
        )
        assignments = self._assignment_service.reconcile_assignments(
            industry_instance_id=record.instance_id,
            cycle_id=current_cycle.id if current_cycle is not None else None,
            goals_by_id=goals_by_id,
            tasks_by_assignment_id=tasks_by_assignment_id,
            tasks_by_goal_id=tasks_by_goal_id,
            latest_reports_by_assignment_id=latest_reports_by_assignment_id,
        )
        report_synthesis = self._synthesize_agent_reports(
            instance_id=record.instance_id,
            cycle_id=current_cycle.id if current_cycle is not None else None,
            activation_result=planning_activation_result,
        )
        if current_cycle is not None:
            current_cycle = self._operating_cycle_service.reconcile_cycle(
                current_cycle,
                goal_statuses=[goal.status for goal in goals_by_id.values()],
                assignment_statuses=[assignment.status for assignment in assignments],
                report_ids=[
                    report.id
                    for report in self._list_agent_report_records(
                        record.instance_id,
                        cycle_id=current_cycle.id,
                        limit=None,
                    )
                ],
                allow_paused_goals_without_confirmation=(
                    _string(record.autonomy_status) in {"learning", "coordinating"}
                ),
            )
            current_cycle = self._persist_cycle_report_synthesis(
                cycle=current_cycle,
                synthesis=report_synthesis,
            )
        record = self._retire_completed_temporary_roles(record=record)
        strategy_constraints = self._compile_strategy_constraints(record=record)
        strategy_constraints = self._apply_activation_to_strategy_constraints(
            constraints=strategy_constraints,
            activation_result=planning_activation_result,
        )
        reason: str | None = None
        new_cycle: OperatingCycleRecord | None = None
        new_goal_ids: list[str] = []
        new_assignment_ids: list[str] = []
        planner_current_cycle = None if force and backlog_item_ids else current_cycle
        if new_cycle is None:
            cycle_decision = self._cycle_planner.plan(
                record=record,
                current_cycle=planner_current_cycle,
                next_cycle_due_at=record.next_cycle_due_at,
                open_backlog=open_backlog,
                pending_reports=pending_reports,
                force=force,
                force_scoped_backlog=bool(scoped_backlog_ids),
                strategy_constraints=strategy_constraints,
                task_subgraph=planning_task_subgraph,
            )
            reason = cycle_decision.reason
            if cycle_decision.should_start and cycle_decision.selected_backlog_item_ids:
                open_backlog_by_id = {
                    item.id: item
                    for item in open_backlog
                }
                selected_backlog = [
                    open_backlog_by_id[item_id]
                    for item_id in cycle_decision.selected_backlog_item_ids
                    if item_id in open_backlog_by_id
                ]
                if selected_backlog:
                    strategy_constraints_payload = self._strategy_constraints_sidecar_payload(
                        record=record,
                        strategy_constraints=strategy_constraints,
                    )
                    cycle_decision_payload = self._planner_sidecar_payload(cycle_decision)
                    report_replan_payload = self._report_replan_sidecar_payload(
                        synthesis=report_synthesis,
                        strategy_constraints_payload=strategy_constraints_payload,
                    )
                    cycle_planning_metadata = {
                        "strategy_constraints": strategy_constraints_payload,
                        "cycle_decision": cycle_decision_payload,
                        "report_replan": report_replan_payload,
                    }
                    new_cycle = self._operating_cycle_service.start_cycle(
                        industry_instance_id=record.instance_id,
                        label=record.label,
                        cycle_kind=cycle_decision.cycle_kind,
                        status="active",
                        focus_lane_ids=list(cycle_decision.selected_lane_ids),
                        backlog_item_ids=[item.id for item in selected_backlog],
                        source_ref=actor,
                        summary=cycle_decision.summary or "Autonomous operating cycle materialized from backlog.",
                        metadata={
                            "report_synthesis": report_synthesis,
                            "formal_planning": cycle_planning_metadata,
                        },
                    )
                    new_cycle, new_assignment_ids = self._materialize_backlog_into_cycle(
                        record=record,
                        cycle=new_cycle,
                        selected_backlog=selected_backlog,
                        strategy_constraints=strategy_constraints,
                        strategy_constraints_sidecar=strategy_constraints_payload,
                        cycle_decision_sidecar=cycle_decision_payload,
                        report_replan_sidecar=report_replan_payload,
                        task_subgraph=planning_task_subgraph,
                    )
                    record = self._industry_instance_repository.upsert_instance(
                        record.model_copy(
                            update={
                                "current_cycle_id": new_cycle.id,
                                "next_cycle_due_at": new_cycle.due_at,
                                "last_cycle_started_at": new_cycle.started_at,
                                "autonomy_status": "coordinating",
                                "lifecycle_status": "running",
                                "updated_at": _utc_now(),
                            },
                        ),
                    )
                else:
                    reason = "planner-selected-missing-backlog"
            elif current_cycle is not None:
                record = self._industry_instance_repository.upsert_instance(
                    record.model_copy(
                        update={
                            "current_cycle_id": current_cycle.id,
                            "next_cycle_due_at": current_cycle.due_at,
                            "last_cycle_started_at": current_cycle.started_at,
                            "updated_at": _utc_now(),
                        },
                    ),
                )
        reconciled = self.reconcile_instance_status(record.instance_id) or record
        self._sync_role_runtime_surfaces_for_record(record=reconciled)
        self._sync_strategy_memory_for_instance(reconciled)
        return {
            "instance_id": reconciled.instance_id,
            "started_cycle_id": new_cycle.id if new_cycle is not None else None,
            "created_goal_ids": new_goal_ids,
            "materialized_goal_ids": [],
            "created_assignment_ids": new_assignment_ids,
            "created_task_ids": [],
            "created_report_ids": [report.id for report in created_reports],
            "processed_report_ids": [report.id for report in processed_reports],
            "created_prediction_case_id": prediction_case_id,
            "created_prediction_backlog_ids": [item.id for item in prediction_backlog_items],
            "reason": self._compat_cycle_reason(reason),
        }
    def _enabled_schedule_records_for_instance(
        self,
        record: IndustryInstanceRecord,
    ) -> list[ScheduleRecord]:
        if self._schedule_repository is None:
            return []
        records: list[ScheduleRecord] = []
        schedule_ids = self._list_schedule_ids_for_instance(record.instance_id)
        for schedule_id in schedule_ids:
            schedule = self._schedule_repository.get_schedule(schedule_id)
            if schedule is None or not schedule.enabled or schedule.status == "deleted":
                continue
            records.append(schedule)
        return records
    def _ensure_terminal_agent_reports(
        self,
        *,
        record: IndustryInstanceRecord,
        cycle_id: str | None,
    ) -> list[AgentReportRecord]:
        task_repository = getattr(self._goal_service, "_task_repository", None)
        runtime_repository = getattr(self._goal_service, "_task_runtime_repository", None)
        decision_repository = getattr(self._goal_service, "_decision_request_repository", None)
        if task_repository is None or self._agent_report_service is None:
            return []
        assignments = {
            assignment.id: assignment
            for assignment in self._list_assignment_records(
                record.instance_id,
                cycle_id=cycle_id,
            )
        }
        created: list[AgentReportRecord] = []
        tasks = task_repository.list_tasks(
            industry_instance_id=record.instance_id,
            assignment_ids=list(assignments) or None,
            cycle_id=cycle_id,
            limit=None,
        )
        for task in tasks:
            if task.status not in {"completed", "failed", "cancelled"}:
                continue
            runtime = (
                runtime_repository.get_runtime(task.id)
                if runtime_repository is not None
                else None
            )
            assignment = assignments.get(task.assignment_id or "")
            if assignment is None:
                continue
            evidence_ids: list[str] = []
            task_routine_run_id: str | None = None
            task_fixed_sop_binding_id: str | None = None
            task_fixed_sop_workflow_run_id: str | None = None
            if self._evidence_ledger is not None:
                for evidence in self._evidence_ledger.list_by_task(task.id):
                    if evidence.id is not None and evidence.id not in evidence_ids:
                        evidence_ids.append(evidence.id)
                    evidence_meta = _mapping(evidence.metadata)
                    nested_routine_run_id = _string(evidence_meta.get("routine_run_id"))
                    if task_routine_run_id is None and nested_routine_run_id is not None:
                        task_routine_run_id = nested_routine_run_id
                    nested_ids = evidence_meta.get("routine_evidence_ids")
                    if isinstance(nested_ids, list):
                        for nested_id in nested_ids:
                            nested_text = _string(nested_id)
                            if nested_text is not None and nested_text not in evidence_ids:
                                evidence_ids.append(nested_text)
                    nested_fixed_sop_binding_id = _string(
                        evidence_meta.get("fixed_sop_binding_id"),
                    )
                    if (
                        task_fixed_sop_binding_id is None
                        and nested_fixed_sop_binding_id is not None
                    ):
                        task_fixed_sop_binding_id = nested_fixed_sop_binding_id
                    nested_fixed_sop_workflow_run_id = (
                        _string(evidence_meta.get("fixed_sop_workflow_run_id"))
                        or _string(evidence_meta.get("workflow_run_id"))
                    )
                    if (
                        task_fixed_sop_workflow_run_id is None
                        and nested_fixed_sop_workflow_run_id is not None
                    ):
                        task_fixed_sop_workflow_run_id = nested_fixed_sop_workflow_run_id
                    nested_fixed_sop_evidence_ids = evidence_meta.get(
                        "fixed_sop_evidence_ids",
                    )
                    if isinstance(nested_fixed_sop_evidence_ids, list):
                        for nested_id in nested_fixed_sop_evidence_ids:
                            nested_text = _string(nested_id)
                            if nested_text is not None and nested_text not in evidence_ids:
                                evidence_ids.append(nested_text)
            decision_ids = (
                [
                    decision.id
                    for decision in decision_repository.list_decision_requests(task_id=task.id)
                ]
                if decision_repository is not None
                else []
            )
            report = self._agent_report_service.record_task_terminal_report(
                task=task,
                runtime=runtime,
                assignment=assignment,
                evidence_ids=evidence_ids,
                decision_ids=decision_ids,
                owner_role_id=assignment.owner_role_id if assignment is not None else None,
                metadata={
                    key: value
                    for key, value in {
                        "routine_run_id": task_routine_run_id,
                        "fixed_sop_binding_id": task_fixed_sop_binding_id,
                        "workflow_run_id": task_fixed_sop_workflow_run_id,
                    }.items()
                    if value is not None
                }
                or None,
            )
            if report is not None:
                created.append(report)
        return created
    def _process_pending_agent_reports(
        self,
        *,
        record: IndustryInstanceRecord,
        cycle_id: str | None,
    ) -> list[AgentReportRecord]:
        if self._agent_report_service is None or self._backlog_service is None:
            return []
        processed: list[AgentReportRecord] = []
        pending_reports = self._list_agent_report_records(
            record.instance_id,
            cycle_id=cycle_id,
            processed=False,
            limit=None,
        )
        if not pending_reports:
            return processed
        assignments = {
            assignment.id: assignment
            for assignment in self._list_assignment_records(
                record.instance_id,
                cycle_id=cycle_id,
            )
        }
        for report in pending_reports:
            assignment = assignments.get(report.assignment_id or "")
            original_backlog_item: BacklogItemRecord | None = None
            if assignment is not None and assignment.backlog_item_id is not None:
                original_backlog_item = (
                    self._backlog_service.get_item(assignment.backlog_item_id)
                    if self._backlog_service is not None
                    else None
                )
                if (
                    original_backlog_item is not None
                    and report.result in {"completed", "success"}
                ):
                    self._backlog_service.mark_item_completed(original_backlog_item)
            if report.result in {"failed", "cancelled", "blocked"}:
                followup_metadata = self._build_report_followup_metadata(
                    report=report,
                    assignment=assignment,
                    original_backlog_item=original_backlog_item,
                )
                followup_metadata.setdefault("source_report_id", report.id)
                followup_source_ids = _unique_strings(
                    followup_metadata.get("source_report_ids"),
                    report.id,
                )
                if followup_source_ids:
                    followup_metadata["source_report_ids"] = list(followup_source_ids)
                followup_metadata.setdefault("owner_agent_id", report.owner_agent_id)
                followup_metadata.setdefault("industry_role_id", report.owner_role_id)
                followup_metadata.setdefault("report_back_mode", "summary")
                self._backlog_service.record_chat_writeback(
                    industry_instance_id=record.instance_id,
                    lane_id=_string(report.lane_id) or (assignment.lane_id if assignment is not None else None),
                    title=f"Follow up: {report.headline}",
                    summary=report.summary,
                    priority=4,
                    source_ref=f"agent-report:{report.id}",
                    metadata=followup_metadata,
                )
                if original_backlog_item is not None:
                    self._backlog_service.mark_item_completed(original_backlog_item)
            self._write_agent_report_back_to_control_thread(
                record=record,
                report=report,
                assignment=assignment,
            )
            processed.append(self._agent_report_service.mark_processed(report))
        synthesis = self._synthesize_agent_reports(
            instance_id=record.instance_id,
            cycle_id=cycle_id,
        )
        self._record_report_synthesis_backlog(
            record=record,
            synthesis=synthesis,
        )
        target_cycle = (
            self._operating_cycle_service.get_cycle(cycle_id)
            if cycle_id is not None and self._operating_cycle_service is not None
            else self._current_operating_cycle_record(record.instance_id)
        )
        self._persist_cycle_report_synthesis(
            cycle=target_cycle,
            synthesis=synthesis,
        )
        return processed
    def _write_agent_report_back_to_control_thread(
        self,
        *,
        record: IndustryInstanceRecord,
        report: AgentReportRecord,
        assignment: AssignmentRecord | None,
    ) -> None:
        _write_agent_report_back_to_control_thread_helper(
            session_backend=self._session_backend,
            backlog_service=self._backlog_service,
            record=record,
            report=report,
            assignment=assignment,
            build_report_followup_metadata_fn=self._build_report_followup_metadata,
            build_agent_report_control_thread_message_fn=self._build_agent_report_control_thread_message,
            execution_core_role_id=EXECUTION_CORE_ROLE_ID,
            execution_core_agent_id=EXECUTION_CORE_AGENT_ID,
        )

    def _build_agent_report_control_thread_message(
        self,
        *,
        report: AgentReportRecord,
        assignment: AssignmentRecord | None,
    ) -> str:
        return _build_agent_report_control_thread_message_helper(
            report=report,
            assignment=assignment,
        )
    def _build_operating_cycle_assignment_unit(
        self,
        *,
        record: IndustryInstanceRecord,
        item: BacklogItemRecord,
        cycle: OperatingCycleRecord,
        assignment: AssignmentRecord,
        actor: str,
    ) -> CompilationUnit:
        metadata = dict(item.metadata or {})
        source = _string(metadata.get("source")) or (
            "chat-writeback" if item.source_kind == "operator" else "operating-cycle"
        )
        trigger_source = (
            _string(metadata.get("trigger_source"))
            or item.source_ref
            or f"cycle:{cycle.cycle_kind}"
        )
        trigger_actor = _string(metadata.get("trigger_actor")) or (
            "industry-chat-writeback"
            if source == "chat-writeback"
            else "main-brain-cycle"
        )
        trigger_reason = _string(metadata.get("trigger_reason")) or (
            "Chat writeback materialized a new goal for the main brain."
            if source == "chat-writeback"
            else "Operating cycle materialized backlog into an executable assignment."
        )
        role_id = _string(assignment.owner_role_id) or _string(metadata.get("industry_role_id"))
        owner_agent_id = _string(assignment.owner_agent_id) or _string(metadata.get("owner_agent_id"))
        lane = (
            self._operating_lane_service.get_lane(item.lane_id)
            if self._operating_lane_service is not None and item.lane_id is not None
            else None
        )
        assignment_formal_planning = (
            dict((assignment.metadata or {}).get("formal_planning") or {})
            if isinstance(assignment.metadata, Mapping)
            else {}
        )
        assignment_plan = (
            dict(assignment_formal_planning.get("assignment_plan") or {})
            if isinstance(assignment_formal_planning.get("assignment_plan"), Mapping)
            else {}
        )
        assignment_sidecar_plan = (
            dict(assignment_plan.get("sidecar_plan") or {})
            if isinstance(assignment_plan.get("sidecar_plan"), Mapping)
            else {}
        )
        checklist_steps = _unique_strings(assignment_sidecar_plan.get("checklist"))
        if checklist_steps:
            plan_steps = list(checklist_steps)
        else:
            plan_steps = _unique_strings(
                metadata.get("plan_steps"),
                [
                    "Confirm the backlog goal and the expected delivery boundary.",
                    "Execute the goal, collect evidence, and update the current status.",
                    "Return the completion summary together with the next recommendation.",
                ],
            )
        control_thread_id = self._chat_writeback_control_thread_id(
            instance_id=record.instance_id,
            session_id=(
                _string(metadata.get("control_thread_id"))
                or _string(metadata.get("session_id"))
            ),
        )
        environment_ref = _string(metadata.get("environment_ref")) or (
            f"session:{_string(metadata.get('chat_writeback_channel')) or 'console'}:industry:{record.instance_id}"
        )
        compiler_context: dict[str, object] = {
            "goal_title": item.title,
            "goal_summary": item.summary,
            "steps": list(plan_steps),
            "channel": "industry-cycle",
            "bootstrap_kind": "industry-v7",
            "owner_scope": record.owner_scope,
            "industry_instance_id": record.instance_id,
            "industry_label": record.label,
            "industry_role_id": role_id or (lane.owner_role_id if lane is not None else None),
            "industry_role_name": (
                _string(metadata.get("industry_role_name"))
                or _string(metadata.get("role_name"))
                or (lane.title if lane is not None else None)
            ),
            "role_name": (
                _string(metadata.get("industry_role_name"))
                or _string(metadata.get("role_name"))
                or (lane.title if lane is not None else None)
            ),
            "role_summary": (
                _string(metadata.get("role_summary"))
                or (lane.summary if lane is not None else None)
            ),
            "mission": (
                _string(metadata.get("mission"))
                or (lane.summary if lane is not None else None)
            ),
            "environment_constraints": list(metadata.get("environment_constraints") or []),
            "evidence_expectations": list(metadata.get("evidence_expectations") or []),
            "owner_agent_id": owner_agent_id or (lane.owner_agent_id if lane is not None else None),
            "actor_owner_id": owner_agent_id or (lane.owner_agent_id if lane is not None else None),
            "goal_kind": _string(metadata.get("goal_kind")) or (lane.lane_key if lane is not None else None),
            "goal_id": assignment.goal_id,
            "task_mode": _string(metadata.get("task_mode")) or "autonomy-cycle",
            "lane_id": item.lane_id,
            "cycle_id": cycle.id,
            "assignment_id": assignment.id,
            "fixed_sop_binding_id": _string(metadata.get("fixed_sop_binding_id")),
            "fixed_sop_source_ref": _string(metadata.get("fixed_sop_source_ref"))
            or item.source_ref
            or item.id,
            "fixed_sop_source_type": _string(metadata.get("fixed_sop_source_type"))
            or "assignment",
            "fixed_sop_risk_level": _string(metadata.get("fixed_sop_risk_level")),
            "fixed_sop_input_payload": (
                dict(metadata.get("fixed_sop_input_payload"))
                if isinstance(metadata.get("fixed_sop_input_payload"), dict)
                else {}
            ),
            "fixed_sop_metadata": (
                dict(metadata.get("fixed_sop_metadata"))
                if isinstance(metadata.get("fixed_sop_metadata"), dict)
                else {
                    key: value
                    for key, value in {
                        "fixed_sop_binding_name": _string(
                            metadata.get("fixed_sop_binding_name"),
                        ),
                        "backlog_item_id": item.id,
                    }.items()
                    if value is not None
                }
            ),
            "fixed_sop_workflow_run_id": _string(
                metadata.get("fixed_sop_workflow_run_id"),
            ),
            "routine_id": _string(metadata.get("routine_id")),
            "routine_source_ref": _string(metadata.get("routine_source_ref"))
            or item.source_ref
            or item.id,
            "routine_source_type": _string(metadata.get("routine_source_type"))
            or "assignment",
            "routine_session_id": _string(metadata.get("routine_session_id")),
            "routine_risk_level": _string(metadata.get("routine_risk_level")),
            "routine_input_payload": (
                dict(metadata.get("routine_input_payload"))
                if isinstance(metadata.get("routine_input_payload"), dict)
                else {}
            ),
            "routine_metadata": (
                dict(metadata.get("routine_metadata"))
                if isinstance(metadata.get("routine_metadata"), dict)
                else {
                    key: value
                    for key, value in {
                        "routine_name": _string(metadata.get("routine_name")),
                        "backlog_item_id": item.id,
                    }.items()
                    if value is not None
                }
            ),
            "report_back_mode": _string(metadata.get("report_back_mode")) or "summary",
            "source": source,
            "backlog_item_id": item.id,
            "source_ref": item.source_ref,
            "trigger_source": trigger_source,
            "trigger_actor": trigger_actor or actor or EXECUTION_CORE_AGENT_ID,
            "trigger_reason": trigger_reason,
            "environment_ref": environment_ref,
            "session_id": control_thread_id,
            "control_thread_id": control_thread_id,
            "work_context_id": _string(metadata.get("work_context_id")),
        }
        compiler_context.update(
            self._assignment_plan_context_from_formal_planning(assignment),
        )
        build_strategy_context = getattr(self._goal_service, "_build_strategy_context", None)
        if callable(build_strategy_context):
            compiler_context.update(build_strategy_context(context=compiler_context))
        return CompilationUnit(
            kind="goal",
            source_text=item.summary or item.title,
            context=compiler_context,
            actor_owner_id=_string(compiler_context.get("owner_agent_id")),
            compiled_at=_utc_now(),
        )
    async def delete_instance(self, instance_id: str) -> dict[str, Any]:
        record = self._industry_instance_repository.get_instance(instance_id)
        if record is None:
            raise KeyError(f"Industry instance '{instance_id}' not found")
        goal_ids = self._resolve_instance_goal_ids(record)
        agent_ids = self._resolve_instance_agent_ids(record)
        thread_ids = self._resolve_instance_thread_ids(record.instance_id)
        task_ids = self._resolve_instance_task_ids(
            goal_ids=goal_ids,
            agent_ids=agent_ids,
        )
        schedule_ids = self._list_schedule_ids_for_instance(record.instance_id)
        base_evidence_ids = self._collect_instance_evidence_ids(task_ids=task_ids)
        learning_deletion_plan = self._plan_instance_learning_deletion(
            instance_id=record.instance_id,
            goal_ids=goal_ids,
            task_ids=task_ids,
            agent_ids=agent_ids,
            evidence_ids=base_evidence_ids,
        )
        patch_evidence_ids = self._collect_instance_evidence_ids(
            task_ids=learning_deletion_plan.patch_ids,
        )
        evidence_ids = _unique_strings(
            base_evidence_ids,
            patch_evidence_ids,
            learning_deletion_plan.evidence_ids,
        )
        learning_deletion_plan = self._plan_instance_learning_deletion(
            instance_id=record.instance_id,
            goal_ids=goal_ids,
            task_ids=task_ids,
            agent_ids=agent_ids,
            evidence_ids=evidence_ids,
        )
        evidence_ids = _unique_strings(evidence_ids, learning_deletion_plan.evidence_ids)
        decision_task_ids = _unique_strings(
            task_ids,
            learning_deletion_plan.patch_ids,
            learning_deletion_plan.acquisition_proposal_ids,
        )
        await self._cancel_instance_tasks(
            goal_ids=goal_ids,
            reason=f"Industry instance '{record.instance_id}' was deleted.",
        )
        deleted_counts = {
            "instances": 0,
            "decisions": self._delete_instance_decisions(decision_task_ids),
            "evidence": self._delete_instance_evidence_records(evidence_ids),
            "learning_proposals": self._delete_instance_learning_proposals(
                learning_deletion_plan.proposal_ids,
            ),
            "learning_patches": self._delete_instance_learning_patches(
                learning_deletion_plan.patch_ids,
            ),
            "learning_growth": self._delete_instance_learning_growth(
                learning_deletion_plan.growth_ids,
            ),
            "acquisition_proposals": self._delete_instance_acquisition_proposals(
                learning_deletion_plan.acquisition_proposal_ids,
            ),
            "install_binding_plans": self._delete_instance_install_binding_plans(
                learning_deletion_plan.install_binding_plan_ids,
            ),
            "onboarding_runs": self._delete_instance_onboarding_runs(
                learning_deletion_plan.onboarding_run_ids,
            ),
            "goals": self._delete_instance_goals(goal_ids),
            "tasks": self._delete_instance_tasks(task_ids),
            "schedules": await self._delete_instance_schedules(schedule_ids),
            "thread_bindings": self._delete_instance_thread_bindings(record.instance_id),
            "agent_overrides": self._delete_instance_agent_overrides(agent_ids),
            "agent_runtimes": self._delete_instance_agent_runtimes(agent_ids),
            "mailbox_items": self._delete_instance_mailbox_items(
                agent_ids=agent_ids,
                thread_ids=thread_ids,
            ),
            "checkpoints": self._delete_instance_checkpoints(
                agent_ids=agent_ids,
                task_ids=task_ids,
            ),
            "leases": self._delete_instance_leases(agent_ids),
            "runtime_frames": self._delete_instance_runtime_frames(task_ids),
            "task_runtimes": self._delete_instance_task_runtimes(task_ids),
            "workflow_runs": self._delete_instance_workflow_runs(record.instance_id),
            "prediction_cases": self._delete_instance_prediction_cases(record.instance_id),
            "strategies": self._delete_instance_strategy_records(record.instance_id),
        }
        if self._industry_instance_repository.delete_instance(record.instance_id):
            deleted_counts["instances"] = 1
        return {
            "deleted": deleted_counts["instances"] == 1,
            "instance_id": record.instance_id,
            "previous_status": record.status,
            "deleted_counts": deleted_counts,
        }
    async def _resolve_media_plan_payload(
        self,
        *,
        media_inputs: list[MediaSourceSpec] | None,
        media_analysis_ids: list[str] | None,
        industry_instance_id: str | None,
        thread_id: str | None,
        entry_point: str,
        purpose: str,
        writeback: bool,
    ) -> tuple[list[MediaAnalysisSummary], list[str], list[str], str | None]:
        service = getattr(self, "_media_service", None)
        collected_ids = _unique_strings(list(media_analysis_ids or []))
        analyses: list[MediaAnalysisSummary] = []
        warnings: list[str] = []
        if service is None:
            if media_inputs or collected_ids:
                warnings.append("Media service is not available.")
            return [], collected_ids, warnings, None
        for analysis_id in collected_ids:
            summary = service.get_analysis(analysis_id)
            if summary is not None:
                analyses.append(summary)
        if media_inputs:
            response = await service.analyze(
                MediaAnalysisRequest(
                    sources=list(media_inputs),
                    industry_instance_id=industry_instance_id,
                    thread_id=thread_id,
                    entry_point=entry_point,
                    purpose=purpose,
                    writeback=writeback,
                )
            )
            warnings.extend(list(response.warnings or []))
            analyses.extend(list(response.analyses or []))
        deduped: list[MediaAnalysisSummary] = []
        seen_ids: set[str] = set()
        for analysis in analyses:
            analysis_id = _string(getattr(analysis, "analysis_id", None))
            if analysis_id is None or analysis_id in seen_ids:
                continue
            seen_ids.add(analysis_id)
            deduped.append(analysis)
        final_ids = _unique_strings(collected_ids, [item.analysis_id for item in deduped])
        context = (
            service.build_prompt_context(final_ids, limit_chars=6000)
            if final_ids
            else None
        )
        return deduped, final_ids, _unique_strings(warnings), context
    async def _generate_draft_plan(
        self,
        *,
        profile: IndustryProfile,
        owner_scope: str,
        media_context: str | None = None,
    ) -> IndustryDraftPlan:
        generator = self._draft_generator
        try:
            return await generator.generate(
                profile=profile,
                owner_scope=owner_scope,
                media_context=media_context,
            )
        except TypeError as exc:
            if "media_context" not in str(exc):
                raise
            return await generator.generate(
                profile=profile,
                owner_scope=owner_scope,
            )
    async def _prepare_preview(self, request: IndustryPreviewRequest) -> _IndustryPlan:
        profile = normalize_industry_profile(request)
        slug = industry_slug(profile)
        owner_scope = request.owner_scope or f"industry-v1-{slug}"
        media_analyses, media_analysis_ids, media_warnings, media_context = (
            await self._resolve_media_plan_payload(
                media_inputs=list(request.media_inputs or []),
                media_analysis_ids=[],
                industry_instance_id=None,
                thread_id=None,
                entry_point="industry-preview",
                purpose="draft-enrichment",
                writeback=False,
            )
        )
        draft = await self._generate_draft_plan(
            profile=profile,
            owner_scope=owner_scope,
            media_context=media_context,
        )
        draft = _enrich_draft_role_capability_families(
            profile=profile,
            draft=draft,
        )
        goal_seeds = compile_industry_goal_seeds(
            profile,
            draft=draft,
            owner_scope=owner_scope,
        )
        schedule_seeds = compile_industry_schedule_seeds(
            profile,
            draft=draft,
            owner_scope=owner_scope,
        )
        recommendation_pack = await self._build_recommendation_pack(
            profile=profile,
            draft=draft,
            include_install_templates=False,
            include_remote_sources=False,
            deferred_message=_PREVIEW_DEFERRED_CAPABILITY_MESSAGE,
        )
        readiness_checks = self._build_readiness_checks(
            team=draft.team,
            schedule_count=len(schedule_seeds),
        )
        return _IndustryPlan(
            profile=profile,
            owner_scope=owner_scope,
            draft=draft,
            goal_seeds=goal_seeds,
            schedule_seeds=schedule_seeds,
            recommendation_pack=recommendation_pack,
            readiness_checks=readiness_checks,
            media_analyses=media_analyses,
            media_analysis_ids=media_analysis_ids,
            media_warnings=media_warnings,
        )
    async def _prepare_bootstrap(self, request: IndustryBootstrapRequest) -> _IndustryPlan:
        profile = normalize_industry_profile(request.profile)
        slug = industry_slug(profile)
        owner_scope = request.owner_scope or f"industry-v1-{slug}"
        media_analyses, media_analysis_ids, media_warnings, _media_context = (
            await self._resolve_media_plan_payload(
                media_inputs=list(request.media_inputs or []),
                media_analysis_ids=list(request.media_analysis_ids or []),
                industry_instance_id=None,
                thread_id=None,
                entry_point="industry-bootstrap",
                purpose="learn-and-writeback",
                writeback=False,
            )
        )
        draft = canonicalize_industry_draft(
            profile,
            request.draft,
            owner_scope=owner_scope,
        )
        existing = self._industry_instance_repository.get_instance(draft.team.team_id)
        draft = self._reconcile_draft_actors(
            draft=draft,
            existing=existing,
        )
        draft = _enrich_draft_role_capability_families(
            profile=profile,
            draft=draft,
        )
        goal_seeds = compile_industry_goal_seeds(
            profile,
            draft=draft,
            owner_scope=owner_scope,
        )
        schedule_seeds = compile_industry_schedule_seeds(
            profile,
            draft=draft,
            owner_scope=owner_scope,
        )
        recommendation_pack = await self._build_recommendation_pack(
            profile=profile,
            draft=draft,
            include_install_templates=False,
            include_remote_sources=False,
            deferred_message=_BOOTSTRAP_DEFERRED_CAPABILITY_MESSAGE,
        )
        readiness_checks = self._build_readiness_checks(
            team=draft.team,
            schedule_count=len(schedule_seeds),
        )
        return _IndustryPlan(
            profile=profile,
            owner_scope=owner_scope,
            draft=draft,
            goal_seeds=goal_seeds,
            schedule_seeds=schedule_seeds,
            recommendation_pack=recommendation_pack,
            readiness_checks=readiness_checks,
            media_analyses=media_analyses,
            media_analysis_ids=media_analysis_ids,
            media_warnings=media_warnings,
        )
    async def _prepare_team_update(
        self,
        *,
        instance_id: str,
        request: IndustryBootstrapRequest,
    ) -> _IndustryPlan:
        existing = self._industry_instance_repository.get_instance(instance_id)
        if existing is None:
            raise KeyError(f"Industry instance '{instance_id}' not found")
        profile = normalize_industry_profile(request.profile)
        owner_scope = request.owner_scope or existing.owner_scope
        media_analyses, media_analysis_ids, media_warnings, _media_context = (
            await self._resolve_media_plan_payload(
                media_inputs=list(request.media_inputs or []),
                media_analysis_ids=list(request.media_analysis_ids or []),
                industry_instance_id=instance_id,
                thread_id=None,
                entry_point="industry-bootstrap",
                purpose="learn-and-writeback",
                writeback=True,
            )
        )
        draft = canonicalize_industry_draft(
            profile,
            request.draft,
            owner_scope=owner_scope,
        )
        draft = draft.model_copy(
            update={
                "team": draft.team.model_copy(update={"team_id": instance_id}),
            },
        )
        draft = self._reconcile_draft_actors(
            draft=draft,
            existing=existing,
        )
        draft = _enrich_draft_role_capability_families(
            profile=profile,
            draft=draft,
        )
        goal_seeds = compile_industry_goal_seeds(
            profile,
            draft=draft,
            owner_scope=owner_scope,
        )
        schedule_seeds = compile_industry_schedule_seeds(
            profile,
            draft=draft,
            owner_scope=owner_scope,
        )
        recommendation_pack = await self._build_recommendation_pack(
            profile=profile,
            draft=draft,
            include_install_templates=False,
            include_remote_sources=False,
            deferred_message=_TEAM_UPDATE_DEFERRED_CAPABILITY_MESSAGE,
        )
        readiness_checks = self._build_readiness_checks(
            team=draft.team,
            schedule_count=len(schedule_seeds),
        )
        return _IndustryPlan(
            profile=profile,
            owner_scope=owner_scope,
            draft=draft,
            goal_seeds=goal_seeds,
            schedule_seeds=schedule_seeds,
            recommendation_pack=recommendation_pack,
            readiness_checks=readiness_checks,
            media_analyses=media_analyses,
            media_analysis_ids=media_analysis_ids,
            media_warnings=media_warnings,
        )
