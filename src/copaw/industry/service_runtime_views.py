# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_context import *  # noqa: F401,F403
from .service_recommendation_search import *  # noqa: F401,F403
from .service_recommendation_pack import *  # noqa: F401,F403


class _IndustryRuntimeViewsMixin:
    def _build_instance_main_chain(
        self,
        *,
        record: IndustryInstanceRecord,
        lanes: list[dict[str, Any]],
        backlog: list[dict[str, Any]],
        current_cycle: dict[str, Any] | None,
        cycles: list[dict[str, Any]],
        assignments: list[dict[str, Any]],
        agent_reports: list[dict[str, Any]],
        goals: list[dict[str, Any]],
        agents: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        execution: IndustryExecutionSummary | None,
        strategy_memory: StrategyMemoryRecord | None,
    ) -> IndustryMainChainGraph:
        focus_task = self._pick_execution_focus_task(tasks)
        if focus_task is None and execution is not None and execution.current_task_id:
            focus_task = next(
                (
                    item
                    for item in tasks
                    if _string(_mapping(item.get("task")).get("id"))
                    == _string(execution.current_task_id)
                ),
                None,
            )
        child_tasks = [
            item
            for item in tasks
            if _string(_mapping(item.get("task")).get("parent_task_id"))
        ]
        current_child_task = self._resolve_chain_child_task(
            child_tasks=child_tasks,
            execution=execution,
        )
        latest_evidence = (
            max(evidence, key=lambda item: _sort_timestamp(item.get("created_at")))
            if evidence
            else None
        )
        agents_by_id = {
            _string(agent.get("agent_id")): agent
            for agent in agents
            if _string(agent.get("agent_id"))
        }
        lanes_by_id = {
            _string(lane.get("lane_id")): lane
            for lane in lanes
            if _string(lane.get("lane_id"))
        }
        assignments_by_id = {
            _string(assignment.get("assignment_id")): assignment
            for assignment in assignments
            if _string(assignment.get("assignment_id"))
        }
        tasks_by_id = {
            _string(_mapping(item.get("task")).get("id")): item
            for item in tasks
            if _string(_mapping(item.get("task")).get("id"))
        }
        current_task_payload = (
            _mapping(focus_task.get("task")) if isinstance(focus_task, dict) else {}
        )
        current_task_id = _string(current_task_payload.get("id"))
        current_task_route = (
            _string(focus_task.get("route")) if isinstance(focus_task, dict) else None
        )
        current_child_payload = (
            _mapping(current_child_task.get("task"))
            if isinstance(current_child_task, dict)
            else {}
        )
        current_child_id = _string(current_child_payload.get("id"))
        current_child_route = (
            _string(current_child_task.get("route"))
            if isinstance(current_child_task, dict)
            else None
        )
        current_assignment_id = (
            _string(current_task_payload.get("assignment_id"))
            or (
                _string(execution.current_task_id)
                if execution is not None
                else None
            )
        )
        current_assignment = (
            assignments_by_id.get(current_assignment_id)
            if current_assignment_id is not None
            else None
        )
        if current_assignment is None and assignments:
            current_assignment = assignments[0]
        current_assignment_id = (
            _string(current_assignment.get("assignment_id"))
            if isinstance(current_assignment, dict)
            else None
        )
        current_assignment_meta = (
            _mapping(current_assignment.get("metadata"))
            if isinstance(current_assignment, dict)
            else {}
        )
        current_cycle_id = (
            _string(current_task_payload.get("cycle_id"))
            or (
                _string(current_assignment.get("cycle_id"))
                if isinstance(current_assignment, dict)
                else None
            )
            or (
                _string(current_cycle.get("cycle_id"))
                if isinstance(current_cycle, dict)
                else None
            )
        )
        current_cycle_entry = None
        if current_cycle_id is not None:
            current_cycle_entry = next(
                (
                    item
                    for item in cycles
                    if _string(item.get("cycle_id")) == current_cycle_id
                ),
                None,
            )
        if current_cycle_entry is None:
            current_cycle_entry = current_cycle or (cycles[0] if cycles else None)
        current_cycle_id = (
            _string(current_cycle_entry.get("cycle_id"))
            if isinstance(current_cycle_entry, dict)
            else None
        )
        current_lane_id = (
            _string(current_task_payload.get("lane_id"))
            or (
                _string(current_assignment.get("lane_id"))
                if isinstance(current_assignment, dict)
                else None
            )
            or (
                _string(_mapping(current_cycle_entry).get("focus_lane_ids")[0])
                if isinstance(_mapping(current_cycle_entry).get("focus_lane_ids"), list)
                and _mapping(current_cycle_entry).get("focus_lane_ids")
                else None
            )
        )
        current_lane = (
            lanes_by_id.get(current_lane_id)
            if current_lane_id is not None
            else None
        )
        if current_lane is None and lanes:
            current_lane = next(
                (
                    item
                    for item in lanes
                    if _string(item.get("status")) == "active"
                ),
                lanes[0],
            )
        current_lane_id = (
            _string(current_lane.get("lane_id")) if isinstance(current_lane, dict) else None
        )
        current_report = None
        if current_assignment_id is not None:
            current_report = next(
                (
                    item
                    for item in agent_reports
                    if _string(item.get("assignment_id")) == current_assignment_id
                ),
                None,
            )
        if current_report is None and current_cycle_id is not None:
            current_report = next(
                (
                    item
                    for item in agent_reports
                    if _string(item.get("cycle_id")) == current_cycle_id
                ),
                None,
            )
        if current_report is None and agent_reports:
            current_report = agent_reports[0]
        current_report_id = (
            _string(current_report.get("report_id"))
            if isinstance(current_report, dict)
            else None
        )
        if focus_task is None and isinstance(current_report, dict):
            report_task_id = _string(current_report.get("task_id"))
            report_assignment_id = _string(current_report.get("assignment_id"))
            report_cycle_id = _string(current_report.get("cycle_id"))
            report_task = (
                tasks_by_id.get(report_task_id)
                if report_task_id is not None
                else None
            )
            report_assignment = (
                assignments_by_id.get(report_assignment_id)
                if report_assignment_id is not None
                else None
            )
            report_cycle = (
                next(
                    (
                        item
                        for item in cycles
                        if _string(item.get("cycle_id")) == report_cycle_id
                    ),
                    None,
                )
                if report_cycle_id is not None
                else None
            )
            if isinstance(report_task, dict):
                focus_task = report_task
                current_task_payload = _mapping(report_task.get("task"))
                current_task_id = _string(current_task_payload.get("id"))
                current_task_route = _string(report_task.get("route"))
            if isinstance(report_assignment, dict):
                current_assignment = report_assignment
                current_assignment_id = _string(report_assignment.get("assignment_id"))
                current_assignment_meta = _mapping(report_assignment.get("metadata"))
            if isinstance(report_cycle, dict):
                current_cycle_entry = report_cycle
                current_cycle_id = _string(report_cycle.get("cycle_id"))
            if isinstance(current_assignment, dict):
                current_lane_id = (
                    _string(current_task_payload.get("lane_id"))
                    or _string(current_assignment.get("lane_id"))
                )
                current_lane = (
                    lanes_by_id.get(current_lane_id)
                    if current_lane_id is not None
                    else current_lane
                )
        current_sop_binding_id = (
            _string(current_task_payload.get("fixed_sop_binding_id"))
            or _string(
                _mapping(current_report).get("metadata", {}).get("fixed_sop_binding_id"),
            )
            or _string(current_assignment_meta.get("fixed_sop_binding_id"))
        )
        current_sop_binding_name = (
            _string(current_task_payload.get("fixed_sop_binding_name"))
            or _string(current_assignment_meta.get("fixed_sop_binding_name"))
        )
        current_routine_id = (
            _string(current_task_payload.get("routine_id"))
            or _string(_mapping(current_report).get("metadata", {}).get("routine_run_id"))
            or _string(current_assignment_meta.get("routine_id"))
        )
        current_routine_name = (
            _string(current_task_payload.get("routine_name"))
            or _string(current_assignment_meta.get("routine_name"))
        )
        current_execution_ref = current_sop_binding_id or current_routine_id
        current_execution_route = (
            f"/api/fixed-sops/bindings/{quote(current_sop_binding_id)}"
            if current_sop_binding_id is not None
            else (
                f"/api/routines/{quote(current_routine_id)}"
                if current_routine_id is not None
                else None
            )
        )
        current_execution_status = (
            _string(execution.status)
            if current_execution_ref is not None
            and execution is not None
            and _string(execution.status)
            else (
                _string(current_task_payload.get("status"))
                if current_execution_ref is not None
                else "idle"
            )
        ) or "idle"
        current_execution_name = current_sop_binding_name or current_routine_name
        current_execution_label = (
            "Fixed SOP" if current_sop_binding_id is not None else "Routine"
        )
        current_execution_truth_source = (
            "FixedSopBindingRecord + WorkflowRunRecord + EvidenceRecord"
            if current_sop_binding_id is not None
            else "ExecutionRoutineRecord + RoutineRunRecord"
        )
        current_execution_backflow_port = (
            "FixedSopService.run_binding()"
            if current_sop_binding_id is not None
            else "RoutineService.replay_routine()"
        )
        current_execution_summary = (
            current_execution_name
            or (
                "The current assignment is executing through a governed SOP binding."
                if current_sop_binding_id is not None
                else (
                    "The current assignment is executing through a formal routine replay."
                    if current_routine_id is not None
                    else "No formal routine or SOP binding is currently attached to the selected task."
                )
            )
        )
        current_execution_mode = (
            "sop-binding"
            if current_sop_binding_id is not None
            else ("routine" if current_routine_id is not None else "none")
        )
        latest_evidence_id = (
            _string(latest_evidence.get("id"))
            if isinstance(latest_evidence, dict)
            else None
        )
        evidence_route = (
            f"/api/runtime-center/evidence/{quote(latest_evidence_id)}"
            if latest_evidence_id is not None
            else None
        )
        strategy_route = (
            f"/api/runtime-center/strategy-memory?industry_instance_id={quote(record.instance_id)}"
            if record.instance_id
            else None
        )
        current_owner_agent_id = (
            _string(execution.current_owner_agent_id)
            if execution is not None and _string(execution.current_owner_agent_id)
            else (
                _string(current_assignment.get("owner_agent_id"))
                if isinstance(current_assignment, dict)
                else None
            )
            or (
                _string(current_lane.get("owner_agent_id"))
                if isinstance(current_lane, dict)
                else None
            )
        )
        current_owner_payload = (
            agents_by_id.get(current_owner_agent_id)
            if current_owner_agent_id is not None
            else None
        )
        current_owner = (
            _string(execution.current_owner)
            if execution is not None and _string(execution.current_owner)
            else (
                _string(current_owner_payload.get("role_name"))
                or _string(current_owner_payload.get("name"))
                if isinstance(current_owner_payload, dict)
                else None
            )
        )
        current_risk = (
            _string(execution.current_risk)
            if execution is not None and _string(execution.current_risk)
            else (
                _string(current_report.get("risk_level"))
                if isinstance(current_report, dict)
                else None
            )
        )
        loop_state = (
            _string(execution.status)
            if execution is not None and _string(execution.status)
            else _string(record.autonomy_status) or _string(record.status)
            or "idle"
        )
        open_backlog_count = sum(
            1 for item in backlog if _string(item.get("status")) in {"open", "selected"}
        )
        pending_report_count = sum(
            1 for item in agent_reports if not bool(item.get("processed"))
        )
        chat_writeback_items = [
            item
            for item in backlog
            if str(item.get("source_ref") or "").startswith("chat-writeback:")
            or _string(_mapping(item.get("metadata")).get("source")) == "chat-writeback"
        ]
        latest_writeback = (
            max(
                chat_writeback_items,
                key=lambda item: _sort_timestamp(
                    item.get("updated_at") or item.get("created_at"),
                ),
            )
            if chat_writeback_items
            else None
        )
        latest_writeback_id = (
            _string(latest_writeback.get("backlog_item_id"))
            if isinstance(latest_writeback, dict)
            else None
        )
        latest_writeback_route = (
            _string(latest_writeback.get("route"))
            if isinstance(latest_writeback, dict)
            else None
        )
        current_backlog = (
            next(
                (
                    item
                    for item in backlog
                    if _string(item.get("backlog_item_id"))
                    == (
                        _string(current_assignment.get("backlog_item_id"))
                        if isinstance(current_assignment, dict)
                        else None
                    )
                ),
                None,
            )
            if backlog
            else None
        )
        if current_backlog is None:
            current_backlog = latest_writeback or (backlog[0] if backlog else None)
        current_backlog_id = (
            _string(current_backlog.get("backlog_item_id"))
            if isinstance(current_backlog, dict)
            else None
        )
        current_focus_title = (
            _string(execution.current_goal)
            if execution is not None and _string(execution.current_goal)
            else (
                _string(current_assignment.get("title"))
                if isinstance(current_assignment, dict)
                else None
            )
            or (
                _string(current_backlog.get("title"))
                if isinstance(current_backlog, dict)
                else None
            )
        )
        current_backlog_route = (
            _string(current_backlog.get("route"))
            if isinstance(current_backlog, dict)
            else None
        )
        current_cycle_synthesis = _mapping(_mapping(current_cycle_entry).get("synthesis"))
        if not current_cycle_synthesis:
            current_cycle_synthesis = _mapping(
                _mapping(_mapping(current_cycle_entry).get("metadata")).get("report_synthesis"),
            )
        synthesis_conflicts = list(current_cycle_synthesis.get("conflicts") or [])
        synthesis_holes = list(current_cycle_synthesis.get("holes") or [])
        replan_needed = bool(current_cycle_synthesis.get("needs_replan")) or bool(
            synthesis_conflicts or synthesis_holes
        )
        replan_summary = (
            f"Conflicts={len(synthesis_conflicts)}, holes={len(synthesis_holes)}; main brain should compare reports and decide whether to dispatch a follow-up cycle."
            if replan_needed
            else "No explicit replan request is pending."
        )
        nodes = [
            IndustryMainChainNode(
                node_id="carrier",
                label="Carrier",
                status=_string(record.status) or "active",
                truth_source="IndustryInstanceRecord",
                current_ref=record.instance_id,
                route=f"/api/runtime-center/industry/{quote(record.instance_id)}",
                summary=(
                    f"{len(lanes)} lanes, {open_backlog_count} open backlog item(s), "
                    f"{len(assignments)} assignment(s), {len(agent_reports)} report(s)."
                ),
                backflow_port="IndustryService.run_operating_cycle() / reconcile_instance_status()",
                metrics={
                    "lane_count": len(lanes),
                    "backlog_count": len(backlog),
                    "open_backlog_count": open_backlog_count,
                    "assignment_count": len(assignments),
                    "report_count": len(agent_reports),
                    "agent_count": len(agents),
                    "schedule_count": len(record.schedule_ids or []),
                },
            ),
            IndustryMainChainNode(
                node_id="writeback",
                label="Writeback",
                status=(
                    _string(latest_writeback.get("status"))
                    if isinstance(latest_writeback, dict)
                    else "idle"
                ),
                truth_source="ChatWritebackPlan + BacklogItemRecord(source=chat-writeback)",
                current_ref=latest_writeback_id,
                route=latest_writeback_route,
                summary=(
                    _string(latest_writeback.get("title"))
                    or _string(latest_writeback.get("summary"))
                    if isinstance(latest_writeback, dict)
                    else "No formal chat writeback has been recorded yet."
                ),
                backflow_port="IndustryService.apply_execution_chat_writeback()",
                metrics={
                    "chat_writeback_count": len(chat_writeback_items),
                },
            ),
            IndustryMainChainNode(
                node_id="strategy",
                label="Strategy",
                status=(
                    _string(strategy_memory.status)
                    if strategy_memory is not None
                    else "idle"
                ),
                truth_source="StrategyMemoryRecord",
                current_ref=(
                    _string(strategy_memory.strategy_id)
                    if strategy_memory is not None
                    else None
                ),
                route=strategy_route,
                summary=(
                    (_string(strategy_memory.north_star) or _string(strategy_memory.summary))
                    if strategy_memory is not None
                    else "No active strategy memory is linked yet."
                ),
                backflow_port="StateStrategyMemoryService.resolve_strategy_payload()",
                metrics={
                    "focus_count": (
                        len(strategy_memory.current_focuses)
                        if strategy_memory is not None
                        else 0
                    ),
                    "priority_count": (
                        len(strategy_memory.priority_order)
                        if strategy_memory is not None
                        else 0
                    ),
                    "paused_lane_count": (
                        len(strategy_memory.paused_lane_ids)
                        if strategy_memory is not None
                        else 0
                    ),
                },
            ),
            IndustryMainChainNode(
                node_id="lane",
                label="Lane",
                status=(
                    _string(current_lane.get("status"))
                    if isinstance(current_lane, dict)
                    else "idle"
                ),
                truth_source="OperatingLaneRecord",
                current_ref=current_lane_id,
                route=(
                    _string(current_lane.get("route"))
                    if isinstance(current_lane, dict)
                    else None
                ),
                summary=(
                    _string(current_lane.get("title"))
                    or _string(current_lane.get("summary"))
                    if isinstance(current_lane, dict)
                    else "No operating lane is currently selected."
                ),
                backflow_port="OperatingLaneService.resolve_lane()",
                metrics={
                    "lane_count": len(lanes),
                    "lane_backlog_count": sum(
                        1
                        for item in backlog
                        if _string(item.get("lane_id")) == current_lane_id
                    ),
                },
            ),
            IndustryMainChainNode(
                node_id="backlog",
                label="Backlog",
                status=(
                    _string(current_backlog.get("status"))
                    if isinstance(current_backlog, dict)
                    else "idle"
                ),
                truth_source="BacklogItemRecord",
                current_ref=current_backlog_id,
                route=current_backlog_route,
                summary=(
                    _string(current_backlog.get("title"))
                    or _string(current_backlog.get("summary"))
                    if isinstance(current_backlog, dict)
                    else "No backlog item is currently selected."
                ),
                backflow_port="BacklogService.record_chat_writeback() / mark_item_materialized()",
                metrics={
                    "backlog_count": len(backlog),
                    "open_backlog_count": open_backlog_count,
                },
            ),
            IndustryMainChainNode(
                node_id="cycle",
                label="Cycle",
                status=(
                    _string(current_cycle_entry.get("status"))
                    if isinstance(current_cycle_entry, dict)
                    else "idle"
                ),
                truth_source="OperatingCycleRecord",
                current_ref=current_cycle_id,
                route=(
                    _string(current_cycle_entry.get("route"))
                    if isinstance(current_cycle_entry, dict)
                    else f"/api/runtime-center/industry/{quote(record.instance_id)}"
                ),
                summary=(
                    _string(current_cycle_entry.get("title"))
                    or _string(current_cycle_entry.get("summary"))
                    if isinstance(current_cycle_entry, dict)
                    else "No active operating cycle is currently selected."
                ),
                backflow_port="OperatingCycleService.reconcile_cycle()",
                metrics={
                    "cycle_count": len(cycles),
                    "pending_report_count": pending_report_count,
                    "open_backlog_count": open_backlog_count,
                },
            ),
            IndustryMainChainNode(
                node_id="assignment",
                label="Assignment",
                status=(
                    _string(current_assignment.get("status"))
                    if isinstance(current_assignment, dict)
                    else "idle"
                ),
                truth_source="AssignmentRecord",
                current_ref=current_assignment_id,
                route=(
                    _string(current_assignment.get("route"))
                    if isinstance(current_assignment, dict)
                    else None
                ),
                summary=(
                    _string(current_assignment.get("title"))
                    or _string(current_assignment.get("summary"))
                    if isinstance(current_assignment, dict)
                    else "No formal assignment is currently selected."
                ),
                backflow_port="AssignmentService.reconcile_assignments()",
                metrics={
                    "assignment_count": len(assignments),
                    "active_assignment_count": sum(
                        1 for item in assignments if _string(item.get("status")) == "active"
                    ),
                },
            ),
            IndustryMainChainNode(
                node_id="routine",
                label=current_execution_label,
                status=current_execution_status,
                truth_source=current_execution_truth_source,
                current_ref=current_execution_ref,
                route=current_execution_route,
                summary=current_execution_summary,
                backflow_port=current_execution_backflow_port,
                metrics={
                    "attached": 1 if current_execution_ref is not None else 0,
                    "execution_mode": current_execution_mode,
                    "task_type": _string(current_task_payload.get("task_type")),
                },
            ),
            IndustryMainChainNode(
                node_id="child-task",
                label="Child Task",
                status=self._derive_child_task_chain_status(child_tasks),
                truth_source="TaskRecord.parent_task_id + TaskRuntimeRecord",
                current_ref=current_child_id,
                route=current_child_route,
                summary=(
                    _string(current_child_payload.get("title"))
                    or (
                        f"{len(child_tasks)} delegated child task(s) linked to the parent chain."
                        if child_tasks
                        else "No delegated child task is currently attached."
                    )
                ),
                backflow_port="KernelDispatcher._reconcile_parent_after_child_terminal()",
                metrics=self._child_task_chain_metrics(child_tasks),
            ),
            IndustryMainChainNode(
                node_id="evidence",
                label="Evidence",
                status="active" if latest_evidence is not None else "idle",
                truth_source="EvidenceRecord",
                current_ref=latest_evidence_id,
                route=evidence_route,
                summary=self._evidence_summary(latest_evidence)
                or ("No evidence written yet." if not evidence else None),
                backflow_port="EvidenceLedger + Runtime Center evidence reads",
                metrics={"evidence_count": len(evidence)},
            ),
            IndustryMainChainNode(
                node_id="report",
                label="Report",
                status=(
                    _string(current_report.get("status"))
                    if isinstance(current_report, dict)
                    else "idle"
                ),
                truth_source="AgentReportRecord",
                current_ref=current_report_id,
                route=(
                    _string(current_report.get("route"))
                    if isinstance(current_report, dict)
                    else None
                ),
                summary=(
                    _string(current_report.get("headline"))
                    or _string(current_report.get("summary"))
                    if isinstance(current_report, dict)
                    else "No structured agent report has flowed back yet."
                ),
                backflow_port="AgentReportService.mark_processed() + BacklogService.mark_item_completed()",
                metrics={
                    "report_count": len(agent_reports),
                    "pending_report_count": pending_report_count,
                },
            ),
            IndustryMainChainNode(
                node_id="replan",
                label="Replan",
                status="active" if replan_needed else "idle",
                truth_source="OperatingCycle.synthesis + AgentReportRecord",
                current_ref=current_cycle_id,
                route=(
                    _string(current_cycle_entry.get("route"))
                    if isinstance(current_cycle_entry, dict)
                    else f"/api/runtime-center/industry/{quote(record.instance_id)}"
                ),
                summary=replan_summary,
                backflow_port="IndustryService._process_pending_agent_reports() / run_operating_cycle()",
                metrics={
                    "conflict_count": len(synthesis_conflicts),
                    "hole_count": len(synthesis_holes),
                    "needs_replan": replan_needed,
                },
            ),
            IndustryMainChainNode(
                node_id="instance-reconcile",
                label="Instance Reconcile",
                status=_string(record.status) or "active",
                truth_source="IndustryService.reconcile_instance_status() over IndustryInstanceRecord + cycle/backlog/goal/report state",
                current_ref=record.instance_id,
                route=f"/api/runtime-center/industry/{quote(record.instance_id)}",
                summary=f"Team status is {_string(record.status) or 'active'}.",
                backflow_port="IndustryService._sync_strategy_memory_for_instance()",
                metrics={
                    "active_assignment_count": sum(
                        1 for assignment in assignments if _string(assignment.get("status")) == "active"
                    ),
                    "open_backlog_count": open_backlog_count,
                    "pending_report_count": pending_report_count,
                },
            ),
        ]
        return IndustryMainChainGraph(
            loop_state=loop_state or "idle",
            current_goal_id=(
                _string(execution.current_goal_id)
                if execution is not None
                else None
            ),
            current_goal=current_focus_title,
            current_owner_agent_id=current_owner_agent_id,
            current_owner=current_owner,
            current_risk=current_risk,
            latest_evidence_summary=(
                self._evidence_summary(latest_evidence)
                or (
                    _string(execution.latest_evidence_summary)
                    if execution is not None
                    else None
                )
            ),
            nodes=nodes,
        )

    def _resolve_chain_child_task(
        self,
        *,
        child_tasks: list[dict[str, Any]],
        execution: IndustryExecutionSummary | None,
    ) -> dict[str, Any] | None:
        parent_task_id = _string(execution.current_task_id) if execution is not None else None
        if parent_task_id is not None:
            matched = next(
                (
                    task
                    for task in child_tasks
                    if _string(_mapping(task.get("task")).get("parent_task_id"))
                    == parent_task_id
                ),
                None,
            )
            if matched is not None:
                return matched
        return child_tasks[0] if child_tasks else None

    def _derive_child_task_chain_status(
        self,
        child_tasks: list[dict[str, Any]],
    ) -> str:
        if not child_tasks:
            return "idle"
        statuses = [
            str(self._derive_execution_task_state(task).get("status") or "")
            for task in child_tasks
        ]
        statuses = [status for status in statuses if status]
        if any(status in {"failed", "blocked", "idle-loop"} for status in statuses):
            return "blocked"
        if any(status in {"executing", "running", "active", "waiting-confirm"} for status in statuses):
            return "active"
        if statuses and all(status == "completed" for status in statuses):
            return "completed"
        return statuses[0] if statuses else "idle"

    def _child_task_chain_metrics(
        self,
        child_tasks: list[dict[str, Any]],
    ) -> dict[str, int]:
        metrics = {"total": len(child_tasks), "active": 0, "completed": 0, "blocked": 0}
        for task in child_tasks:
            status = str(self._derive_execution_task_state(task).get("status") or "")
            if status in {"executing", "running", "active", "waiting-confirm"}:
                metrics["active"] += 1
            elif status == "completed":
                metrics["completed"] += 1
            elif status:
                metrics["blocked"] += 1
        return metrics

    def _apply_execution_core_identity_to_agents(
        self,
        *,
        agents: list[dict[str, Any]],
        execution_core_identity: IndustryExecutionCoreIdentity | None,
        goals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if execution_core_identity is None:
            return agents
        current_goal = self._resolve_execution_core_goal(goals)
        for item in agents:
            agent_id = _string(item.get("agent_id"))
            if not is_execution_core_agent_id(agent_id):
                continue
            item["industry_instance_id"] = execution_core_identity.industry_instance_id
            item["industry_role_id"] = execution_core_identity.role_id
            item["identity_label"] = execution_core_identity.identity_label
            item["industry_label"] = execution_core_identity.industry_label
            item["industry_summary"] = execution_core_identity.industry_summary
            item["thinking_axes"] = list(execution_core_identity.thinking_axes)
            item["role_name"] = execution_core_identity.role_name
            item["role_summary"] = execution_core_identity.role_summary
            item["mission"] = execution_core_identity.mission
            item["environment_constraints"] = list(
                execution_core_identity.environment_constraints,
            )
            item["evidence_expectations"] = list(
                execution_core_identity.evidence_expectations,
            )
            item["allowed_capabilities"] = list(
                execution_core_identity.allowed_capabilities,
            )
            item["operating_mode"] = execution_core_identity.operating_mode
            item["delegation_policy"] = list(
                execution_core_identity.delegation_policy,
            )
            item["direct_execution_policy"] = list(
                execution_core_identity.direct_execution_policy,
            )
            if current_goal is not None:
                item["current_goal_id"] = current_goal.get("goal_id")
                item["current_goal"] = current_goal.get("title")
            return agents

        seed = self._get_agent_snapshot(EXECUTION_CORE_AGENT_ID) or {}
        item = dict(seed)
        item["agent_id"] = EXECUTION_CORE_AGENT_ID
        item["name"] = _string(item.get("name")) or _EXECUTION_CORE_NAME
        item["industry_instance_id"] = execution_core_identity.industry_instance_id
        item["industry_role_id"] = execution_core_identity.role_id
        item["identity_label"] = execution_core_identity.identity_label
        item["industry_label"] = execution_core_identity.industry_label
        item["industry_summary"] = execution_core_identity.industry_summary
        item["thinking_axes"] = list(execution_core_identity.thinking_axes)
        item["role_name"] = execution_core_identity.role_name
        item["role_summary"] = execution_core_identity.role_summary
        item["mission"] = execution_core_identity.mission
        item["environment_constraints"] = list(
            execution_core_identity.environment_constraints,
        )
        item["evidence_expectations"] = list(
            execution_core_identity.evidence_expectations,
        )
        item["allowed_capabilities"] = list(
            execution_core_identity.allowed_capabilities,
        )
        item["operating_mode"] = execution_core_identity.operating_mode
        item["delegation_policy"] = list(
            execution_core_identity.delegation_policy,
        )
        item["direct_execution_policy"] = list(
            execution_core_identity.direct_execution_policy,
        )
        item.setdefault("status", "running")
        if current_goal is not None:
            item["current_goal_id"] = current_goal.get("goal_id")
            item["current_goal"] = current_goal.get("title")
        item["route"] = f"/api/runtime-center/agents/{EXECUTION_CORE_AGENT_ID}"
        agents.append(item)
        agents.sort(
            key=lambda agent: _sort_timestamp(agent.get("updated_at")),
            reverse=True,
        )
        return agents

    def _resolve_execution_core_goal(
        self,
        goals: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        matches = [
            goal
            for goal in goals
            if is_execution_core_agent_id(_string(goal.get("owner_agent_id")))
            or is_execution_core_role_id(_string(goal.get("role_id")))
        ]
        if not matches:
            return None
        for status in ("active", "draft", "paused", "blocked"):
            for goal in matches:
                if _string(goal.get("status")) == status:
                    return goal
        return matches[0]

    def _build_instance_execution_summary(
        self,
        *,
        record: IndustryInstanceRecord,
        goals: list[dict[str, Any]],
        agents: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> IndustryExecutionSummary:
        goals_by_id = {
            _string(goal.get("goal_id")): goal
            for goal in goals
            if _string(goal.get("goal_id"))
        }
        agents_by_id = {
            _string(agent.get("agent_id")): agent
            for agent in agents
            if _string(agent.get("agent_id"))
        }
        evidence_by_id = {
            _string(item.get("id")): item
            for item in evidence
            if _string(item.get("id"))
        }
        latest_evidence = (
            max(evidence, key=lambda item: _sort_timestamp(item.get("created_at")))
            if evidence
            else None
        )
        autonomy_status = _string(record.autonomy_status)
        waiting_confirm_goal = next(
            (
                goal
                for goal in goals
                if _string(goal.get("status")) in {"paused", "draft"}
            ),
            None,
        )
        waiting_confirm_agent = next(
            (
                agent
                for agent in agents
                if _string(agent.get("status")) == "waiting-confirm"
                or _string(agent.get("runtime_status")) == "waiting-confirm"
            ),
            None,
        )
        fallback_goal = self._resolve_execution_core_goal(goals) or next(
            (goal for goal in goals if _string(goal.get("status")) == "active"),
            waiting_confirm_goal or (goals[0] if goals else None),
        )
        focus_task = self._pick_execution_focus_task(tasks)
        if focus_task is None:
            if autonomy_status == "learning":
                pending_goal = fallback_goal or waiting_confirm_goal
                fallback_owner_agent_id = (
                    _string(pending_goal.get("owner_agent_id"))
                    if isinstance(pending_goal, dict)
                    else None
                )
                fallback_owner = (
                    agents_by_id.get(fallback_owner_agent_id)
                    if fallback_owner_agent_id is not None
                    else None
                )
                return IndustryExecutionSummary(
                    status="learning",
                    current_goal_id=(
                        _string(pending_goal.get("goal_id"))
                        if isinstance(pending_goal, dict)
                        else None
                    ),
                    current_goal=(
                        _string(pending_goal.get("title"))
                        if isinstance(pending_goal, dict)
                        else None
                    ),
                    current_owner_agent_id=fallback_owner_agent_id,
                    current_owner=(
                        _string(fallback_owner.get("role_name"))
                        or _string(fallback_owner.get("name"))
                        if isinstance(fallback_owner, dict)
                        else None
                    ),
                    current_risk=(
                        _string(fallback_owner.get("risk_level"))
                        if isinstance(fallback_owner, dict)
                        else None
                    ),
                    evidence_count=len(evidence),
                    latest_evidence_summary=self._evidence_summary(latest_evidence),
                    next_step="系统正在补齐行业学习材料，完成后会自动转入执行阶段。",
                    updated_at=_parse_datetime(
                        (
                            latest_evidence.get("created_at")
                            if isinstance(latest_evidence, dict)
                            else None
                        )
                        or (
                            pending_goal.get("updated_at")
                            if isinstance(pending_goal, dict)
                            else None
                        ),
                    ),
                )
            if autonomy_status == "coordinating":
                pending_goal = fallback_goal or waiting_confirm_goal
                fallback_owner_agent_id = (
                    _string(pending_goal.get("owner_agent_id"))
                    if isinstance(pending_goal, dict)
                    else None
                )
                fallback_owner = (
                    agents_by_id.get(fallback_owner_agent_id)
                    if fallback_owner_agent_id is not None
                    else None
                )
                return IndustryExecutionSummary(
                    status="coordinating",
                    current_goal_id=(
                        _string(pending_goal.get("goal_id"))
                        if isinstance(pending_goal, dict)
                        else None
                    ),
                    current_goal=(
                        _string(pending_goal.get("title"))
                        if isinstance(pending_goal, dict)
                        else None
                    ),
                    current_owner_agent_id=fallback_owner_agent_id,
                    current_owner=(
                        _string(fallback_owner.get("role_name"))
                        or _string(fallback_owner.get("name"))
                        if isinstance(fallback_owner, dict)
                        else None
                    ),
                    current_risk=(
                        _string(fallback_owner.get("risk_level"))
                        if isinstance(fallback_owner, dict)
                        else None
                    ),
                    evidence_count=len(evidence),
                    latest_evidence_summary=self._evidence_summary(latest_evidence),
                    next_step="主脑正在协调执行位与 backlog，命中条件后会自动继续执行。",
                    updated_at=_parse_datetime(
                        (
                            latest_evidence.get("created_at")
                            if isinstance(latest_evidence, dict)
                            else None
                        )
                        or (
                            pending_goal.get("updated_at")
                            if isinstance(pending_goal, dict)
                            else None
                        ),
                    ),
                )
            if (
                autonomy_status == "waiting-confirm"
                or waiting_confirm_goal is not None
                or waiting_confirm_agent is not None
            ):
                pending_goal = waiting_confirm_goal or fallback_goal
                fallback_owner_agent_id = (
                    _string(pending_goal.get("owner_agent_id"))
                    if isinstance(pending_goal, dict)
                    else None
                )
                fallback_owner = (
                    agents_by_id.get(fallback_owner_agent_id)
                    if fallback_owner_agent_id is not None
                    else waiting_confirm_agent
                )
                return IndustryExecutionSummary(
                    status="waiting-confirm",
                    current_goal_id=(
                        _string(pending_goal.get("goal_id"))
                        if isinstance(pending_goal, dict)
                        else None
                    ),
                    current_goal=(
                        _string(pending_goal.get("title"))
                        if isinstance(pending_goal, dict)
                        else None
                    ),
                    current_owner_agent_id=fallback_owner_agent_id,
                    current_owner=(
                        _string(fallback_owner.get("role_name"))
                        or _string(fallback_owner.get("name"))
                        if isinstance(fallback_owner, dict)
                        else None
                    ),
                    current_risk=(
                        _string(fallback_owner.get("risk_level"))
                        if isinstance(fallback_owner, dict)
                        else None
                    ),
                    evidence_count=len(evidence),
                    latest_evidence_summary=self._evidence_summary(latest_evidence),
                    next_step="请先在主脑控制线程里确认是否启动这一阶段。",
                    blocked_reason="系统正在等待首轮启动确认。",
                    updated_at=_parse_datetime(
                        (
                            latest_evidence.get("created_at")
                            if isinstance(latest_evidence, dict)
                            else None
                        )
                        or (
                            pending_goal.get("updated_at")
                            if isinstance(pending_goal, dict)
                            else None
                        ),
                    ),
                )
            fallback_owner_agent_id = (
                _string(fallback_goal.get("owner_agent_id")) if isinstance(fallback_goal, dict) else None
            )
            fallback_owner = (
                agents_by_id.get(fallback_owner_agent_id)
                if fallback_owner_agent_id is not None
                else None
            )
            return IndustryExecutionSummary(
                status="idle",
                current_goal_id=_string(fallback_goal.get("goal_id")) if isinstance(fallback_goal, dict) else None,
                current_goal=_string(fallback_goal.get("title")) if isinstance(fallback_goal, dict) else None,
                current_owner_agent_id=fallback_owner_agent_id,
                current_owner=(
                    _string(fallback_owner.get("role_name"))
                    or _string(fallback_owner.get("name"))
                    if isinstance(fallback_owner, dict)
                    else None
                ),
                current_risk=(
                    _string(fallback_owner.get("risk_level"))
                    if isinstance(fallback_owner, dict)
                    else None
                ),
                evidence_count=len(evidence),
                latest_evidence_summary=self._evidence_summary(latest_evidence),
                next_step=(
                    "当前未自动续跑，等待手动触发目标或计划触发。"
                    if fallback_goal is not None
                    else "当前还没有可执行任务。"
                ),
                updated_at=_parse_datetime(
                    latest_evidence.get("created_at")
                    if isinstance(latest_evidence, dict)
                    else None
                ),
            )

        task_payload = _mapping(focus_task.get("task"))
        runtime_payload = _mapping(focus_task.get("runtime"))
        focus_state = self._derive_execution_task_state(focus_task)
        task_goal_id = _string(task_payload.get("goal_id"))
        current_goal = goals_by_id.get(task_goal_id) if task_goal_id is not None else None
        if current_goal is None:
            current_goal = fallback_goal
        owner_agent_id = (
            _string(runtime_payload.get("last_owner_agent_id"))
            or _string(task_payload.get("owner_agent_id"))
            or (_string(current_goal.get("owner_agent_id")) if isinstance(current_goal, dict) else None)
        )
        owner_payload = agents_by_id.get(owner_agent_id) if owner_agent_id is not None else None
        latest_evidence_id = _string(focus_task.get("latest_evidence_id"))
        latest_task_evidence = (
            evidence_by_id.get(latest_evidence_id)
            if latest_evidence_id is not None
            else None
        ) or latest_evidence
        trigger = self._extract_execution_task_trigger(focus_task)
        updated_at = _parse_datetime(
            runtime_payload.get("updated_at")
            or task_payload.get("updated_at")
            or (
                latest_task_evidence.get("created_at")
                if isinstance(latest_task_evidence, dict)
                else None
            ),
        )
        focus_status = str(focus_state["status"])
        if focus_status == "idle" and autonomy_status in {"learning", "coordinating"}:
            next_step = (
                "系统正在补齐行业学习材料，完成后会自动转入执行阶段。"
                if autonomy_status == "learning"
                else "主脑正在协调执行位与 backlog，命中条件后会自动继续执行。"
            )
            return IndustryExecutionSummary(
                status=autonomy_status,
                current_goal_id=(
                    _string(current_goal.get("goal_id"))
                    if isinstance(current_goal, dict)
                    else task_goal_id
                ),
                current_goal=(
                    _string(current_goal.get("title"))
                    if isinstance(current_goal, dict)
                    else None
                ),
                current_owner_agent_id=owner_agent_id,
                current_owner=(
                    _string(owner_payload.get("role_name"))
                    or _string(owner_payload.get("name"))
                    if isinstance(owner_payload, dict)
                    else None
                ),
                current_risk=(
                    _string(runtime_payload.get("risk_level"))
                    or _string(task_payload.get("current_risk_level"))
                    or (
                        _string(owner_payload.get("risk_level"))
                        if isinstance(owner_payload, dict)
                        else None
                    )
                ),
                evidence_count=int(focus_task.get("evidence_count") or 0),
                latest_evidence_summary=self._evidence_summary(latest_task_evidence),
                next_step=next_step,
                current_task_id=_string(task_payload.get("id")),
                current_task_route=_string(focus_task.get("route")),
                current_stage=autonomy_status,
                trigger_source=trigger["source"],
                trigger_actor=trigger["actor"],
                trigger_reason=trigger["reason"],
                updated_at=updated_at,
            )
        return IndustryExecutionSummary(
            status=focus_status,
            current_goal_id=_string(current_goal.get("goal_id")) if isinstance(current_goal, dict) else task_goal_id,
            current_goal=_string(current_goal.get("title")) if isinstance(current_goal, dict) else None,
            current_owner_agent_id=owner_agent_id,
            current_owner=(
                _string(owner_payload.get("role_name"))
                or _string(owner_payload.get("name"))
                if isinstance(owner_payload, dict)
                else None
            ),
            current_risk=(
                _string(runtime_payload.get("risk_level"))
                or _string(task_payload.get("current_risk_level"))
                or (
                    _string(owner_payload.get("risk_level"))
                    if isinstance(owner_payload, dict)
                    else None
                )
            ),
            evidence_count=int(focus_task.get("evidence_count") or 0),
            latest_evidence_summary=self._evidence_summary(latest_task_evidence),
            next_step=self._execution_next_step(
                status=str(focus_state["status"]),
                current_goal=current_goal,
            ),
            current_task_id=_string(task_payload.get("id")),
            current_task_route=_string(focus_task.get("route")),
            current_stage=(
                _string(runtime_payload.get("current_phase"))
                or _string(task_payload.get("status"))
            ),
            trigger_source=trigger["source"],
            trigger_actor=trigger["actor"],
            trigger_reason=trigger["reason"],
            blocked_reason=(
                str(focus_state["blocked_reason"])
                if focus_state.get("blocked_reason") is not None
                else None
            ),
            stuck_reason=(
                str(focus_state["stuck_reason"])
                if focus_state.get("stuck_reason") is not None
                else None
            ),
            updated_at=updated_at,
        )

    def _pick_execution_focus_task(
        self,
        tasks: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not tasks:
            return None
        priorities = {
            "waiting-verification": 0,
            "waiting-confirm": 1,
            "waiting-resource": 2,
            "idle-loop": 3,
            "failed": 4,
            "executing": 5,
            "idle": 6,
        }
        ranked = sorted(
            tasks,
            key=lambda item: (
                priorities.get(
                    str(self._derive_execution_task_state(item)["status"]),
                    99,
                ),
                -_sort_timestamp(
                    _mapping(item.get("runtime")).get("updated_at")
                    or _mapping(item.get("task")).get("updated_at"),
                ).timestamp(),
            ),
        )
        return ranked[0] if ranked else None

    def _derive_execution_task_state(
        self,
        task_entry: dict[str, Any],
    ) -> dict[str, object]:
        task_payload = _mapping(task_entry.get("task"))
        runtime_payload = _mapping(task_entry.get("runtime"))
        runtime_status = _string(runtime_payload.get("runtime_status"))
        task_status = _string(task_payload.get("status")) or "created"
        status = runtime_status if task_status == "running" and runtime_status else task_status
        phase = _string(runtime_payload.get("current_phase")) or status or "created"
        detail_text = (
            _string(runtime_payload.get("last_error_summary"))
            or _string(runtime_payload.get("last_result_summary"))
            or _string(task_payload.get("summary"))
        )
        decision_count = int(task_entry.get("decision_count") or 0)
        verification_markers = (
            "验证码",
            "短信",
            "2fa",
            "two-factor",
            "二次验证",
            "设备确认",
            "滑块",
            "人机",
            "captcha",
            "verification",
            "verify",
        )
        resource_markers = (
            "缺少",
            "未找到",
            "不可用",
            "permission",
            "forbidden",
            "not available",
            "install",
            "api key",
            "登录",
            "cookie",
            "session",
            "resource",
            "文件",
        )
        if decision_count > 0 or status == "waiting-confirm" or phase == "waiting-confirm":
            if self._matches_execution_marker(detail_text, verification_markers):
                return {
                    "status": "waiting-verification",
                    "blocked_reason": detail_text or "Waiting for user-owned verification checkpoint.",
                    "stuck_reason": None,
                }
            return {
                "status": "waiting-confirm",
                "blocked_reason": detail_text or "Waiting for operator confirmation before continuing.",
                "stuck_reason": None,
            }
        if status in {"failed", "blocked", "cancelled"}:
            if self._matches_execution_marker(detail_text, verification_markers):
                return {
                    "status": "waiting-verification",
                    "blocked_reason": detail_text or "Waiting for user-owned verification checkpoint.",
                    "stuck_reason": None,
                }
            if self._matches_execution_marker(detail_text, resource_markers):
                return {
                    "status": "waiting-resource",
                    "blocked_reason": detail_text or "Waiting for an external resource or environment prerequisite.",
                    "stuck_reason": None,
                }
            return {
                "status": "failed",
                "blocked_reason": detail_text or "Execution failed or was blocked.",
                "stuck_reason": None,
            }
        if status in {"executing", "claimed", "running", "active", "queued", "created", "waiting"}:
            updated_at = _parse_datetime(
                runtime_payload.get("updated_at") or task_payload.get("updated_at"),
            )
            if (
                updated_at is not None
                and (datetime.now(timezone.utc) - updated_at).total_seconds() >= 180
            ):
                return {
                    "status": "idle-loop",
                    "blocked_reason": None,
                    "stuck_reason": "Task has not produced a new result or state transition for more than 3 minutes.",
                }
            return {
                "status": "executing",
                "blocked_reason": None,
                "stuck_reason": None,
            }
        return {
            "status": "idle",
            "blocked_reason": None,
            "stuck_reason": None,
        }

    def _extract_execution_task_trigger(
        self,
        task_entry: dict[str, Any],
    ) -> dict[str, str | None]:
        task_payload = _mapping(task_entry.get("task"))
        metadata = decode_kernel_task_metadata(task_payload.get("acceptance_criteria"))
        payload = _mapping(metadata.get("payload"))
        compiler = _mapping(payload.get("compiler"))
        task_seed = _mapping(payload.get("task_seed"))
        meta = _mapping(payload.get("meta"))
        return {
            "source": (
                _string(compiler.get("trigger_source"))
                or _string(task_seed.get("trigger_source"))
                or _string(meta.get("trigger_source"))
            ),
            "actor": (
                _string(compiler.get("trigger_actor"))
                or _string(task_seed.get("trigger_actor"))
                or _string(meta.get("trigger_actor"))
            ),
            "reason": (
                _string(compiler.get("trigger_reason"))
                or _string(task_seed.get("trigger_reason"))
                or _string(meta.get("trigger_reason"))
            ),
        }

    def _execution_next_step(
        self,
        *,
        status: str,
        current_goal: dict[str, Any] | None,
    ) -> str:
        if status == "waiting-verification":
            return "等待用户完成验证码、短信、设备确认或其他人工验证后继续。"
        if status == "waiting-confirm":
            return "等待人工确认通过后继续推进当前执行链。"
        if status == "waiting-resource":
            return "等待外部资源、登录态或环境前置条件补齐后继续。"
        if status == "idle-loop":
            return "当前长时间无进展，先检查是否在重复空转，再决定重试或改派。"
        if status == "failed":
            return "先处理失败原因，再决定重试、改派或终止。"
        if status == "executing":
            return "继续当前执行，并把关键动作和证据持续回写。"
        if current_goal is not None:
            return "当前未自动续跑，等待手动触发目标或计划触发。"
        return "当前没有可继续的执行链。"
