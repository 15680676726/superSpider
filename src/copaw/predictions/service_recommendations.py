# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403


class _PredictionServiceRecommendationMixin:
    def _build_signals(
        self,
        case: PredictionCaseRecord,
        facts: _FactPack,
    ) -> list[PredictionSignalRecord]:
        signals: list[PredictionSignalRecord] = []
        report_id = _string(facts.report.get("id"))

        def append_signal(
            *,
            label: str,
            summary: str,
            source_kind: str,
            source_ref: str | None = None,
            direction: str = "neutral",
            strength: float = 0.2,
            metric_key: str | None = None,
            evidence_id: str | None = None,
            agent_id: str | None = None,
            workflow_run_id: str | None = None,
            payload: dict[str, Any] | None = None,
        ) -> None:
            normalized_label = label.strip()
            if not normalized_label:
                return
            signals.append(
                PredictionSignalRecord(
                    case_id=case.case_id,
                    label=normalized_label[:160],
                    summary=summary.strip(),
                    source_kind=source_kind,  # type: ignore[arg-type]
                    source_ref=source_ref,
                    direction=direction,  # type: ignore[arg-type]
                    strength=max(0.0, min(1.0, round(float(strength), 3))),
                    metric_key=metric_key,
                    report_id=report_id,
                    evidence_id=evidence_id,
                    agent_id=agent_id,
                    workflow_run_id=workflow_run_id,
                    payload=dict(payload or {}),
                ),
            )

        metric_payloads = [
            _safe_dict(item)
            for item in _safe_list(facts.performance.get("metrics"))
        ]
        for metric in metric_payloads[:8]:
            key = str(metric.get("key") or "").strip()
            if not key:
                continue
            label = str(metric.get("label") or _metric_label(key))
            try:
                value = float(metric.get("value") or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            display_value = str(metric.get("display_value") or value)
            direction = "neutral"
            strength = 0.25
            summary = f"{label}当前为 {display_value}。"
            if key == "task_success_rate":
                if value < 70:
                    direction = "negative"
                    strength = max(0.25, min(1.0, round((70.0 - value) / 70.0, 3)))
                    summary = f"{label}已降至 {display_value}，交付风险正在上升。"
                else:
                    direction = "positive"
                    strength = max(0.2, min(0.9, round((value - 70.0) / 30.0, 3)))
                    summary = f"{label}为 {display_value}，支撑当前执行稳定性。"
            elif key == "manual_intervention_rate":
                if value > 40:
                    direction = "negative"
                    strength = max(0.25, min(1.0, round((value - 40.0) / 60.0, 3)))
                    summary = (
                        f"{label}为 {display_value}，说明运行面需要比预期更多的人工介入。"
                    )
            elif key == "exception_rate":
                if value > 15:
                    direction = "negative"
                    strength = max(0.3, min(1.0, round((value - 15.0) / 85.0, 3)))
                    summary = f"{label}为 {display_value}，表明失败压力正在上升。"
            elif key == "patch_apply_rate":
                if value >= 50:
                    direction = "positive"
                    strength = max(0.2, min(0.85, round((value - 50.0) / 50.0, 3)))
                    summary = f"{label}为 {display_value}，说明改进行动正在落地。"
            elif key == "rollback_rate":
                if value > 20:
                    direction = "negative"
                    strength = max(0.25, min(1.0, round((value - 20.0) / 80.0, 3)))
                    summary = f"{label}为 {display_value}，说明近期变更可能仍不稳定。"
            elif key == "active_task_load":
                if value > 2.5:
                    direction = "negative"
                    strength = max(0.25, min(1.0, round((value - 2.5) / 3.5, 3)))
                    summary = f"{label}为 {display_value}，可能导致活跃智能体过载。"
            elif key == "prediction_hit_rate":
                if value >= 60:
                    direction = "positive"
                    strength = max(0.2, min(0.85, round((value - 60.0) / 40.0, 3)))
                    summary = f"{label}为 {display_value}，说明近期预测质量保持稳定。"
                else:
                    direction = "negative"
                    strength = max(0.2, min(0.8, round((60.0 - value) / 60.0, 3)))
                    summary = f"{label}仅为 {display_value}，建议质量需要进一步复核。"
            append_signal(
                label=label,
                summary=summary,
                source_kind="metric",
                source_ref=f"metric:{key}",
                direction=direction,
                strength=strength,
                metric_key=key,
                payload=metric,
            )

        for highlight in _safe_list(facts.report.get("highlights"))[:4]:
            text = str(highlight).strip()
            if not text:
                continue
            lowered = text.lower()
            direction = "neutral"
            strength = 0.2
            if any(token in lowered for token in ("failed", "rollback", "blocked", "decision")) or any(
                token in text for token in ("失败", "回滚", "阻塞", "决策")
            ):
                direction = "negative"
                strength = 0.45
            elif any(token in lowered for token in ("applied", "success", "growth")) or any(
                token in text for token in ("已应用", "成功", "成长", "增长")
            ):
                direction = "positive"
                strength = 0.35
            append_signal(
                label="报告亮点",
                summary=text,
                source_kind="report",
                source_ref=report_id,
                direction=direction,
                strength=strength,
                payload={"highlight": text},
            )

        for workflow in facts.workflows[:4]:
            preview = _safe_dict(workflow.preview_payload)
            missing = [
                str(item).strip()
                for item in _safe_list(preview.get("missing_capability_ids"))
                if str(item).strip()
            ]
            gaps = [
                str(item).strip()
                for item in _safe_list(preview.get("assignment_gap_capability_ids"))
                if str(item).strip()
            ]
            direction = "neutral"
            strength = 0.25
            summary = f"工作流“{workflow.title}”当前状态为“{workflow.status}”。"
            if missing or gaps or str(workflow.status).lower() in {"failed", "cancelled", "blocked"}:
                direction = "negative"
                strength = min(1.0, 0.35 + (0.12 * len(missing)) + (0.1 * len(gaps)))
                summary = (
                    f"工作流“{workflow.title}”存在能力阻塞"
                    f"（缺失 {len(missing)} 项，分配缺口 {len(gaps)} 项）。"
                )
            elif str(workflow.status).lower() in {"running", "planned"}:
                direction = "positive"
                strength = 0.35
                summary = f"工作流“{workflow.title}”当前可承接后续协同执行。"
            append_signal(
                label=workflow.title,
                summary=summary,
                source_kind="workflow-run",
                source_ref=workflow.run_id,
                direction=direction,
                strength=strength,
                workflow_run_id=workflow.run_id,
                payload={
                    "status": workflow.status,
                    "missing_capability_ids": missing,
                    "assignment_gap_capability_ids": gaps,
                },
            )

        for agent in _safe_list(facts.performance.get("agent_breakdown"))[:3]:
            payload = _safe_dict(agent)
            agent_id = _string(payload.get("agent_id"))
            if agent_id is None:
                continue
            name = str(payload.get("name") or agent_id)
            active_task_count = int(payload.get("active_task_count") or 0)
            failed_task_count = int(payload.get("failed_task_count") or 0)
            success_rate = float(payload.get("success_rate") or 0.0)
            direction = "neutral"
            strength = 0.25
            summary = f"智能体“{name}”当前有 {active_task_count} 个活跃任务。"
            if failed_task_count > 0:
                direction = "negative"
                strength = min(1.0, 0.45 + (0.1 * failed_task_count))
                summary = f"智能体“{name}”在当前窗口内有 {failed_task_count} 个失败任务。"
            elif active_task_count >= 4:
                direction = "negative"
                strength = min(1.0, 0.3 + ((active_task_count - 3) * 0.12))
                summary = f"智能体“{name}”当前承载 {active_task_count} 个活跃任务，可能出现过载。"
            elif success_rate >= 80:
                direction = "positive"
                strength = max(0.2, min(0.85, round((success_rate - 80.0) / 20.0, 3)))
                summary = f"智能体“{name}”当前维持 {success_rate:.1f}% 的成功率。"
            append_signal(
                label=name,
                summary=summary,
                source_kind="agent",
                source_ref=agent_id,
                direction=direction,
                strength=strength,
                agent_id=agent_id,
                payload=payload,
            )

        strategy = facts.strategy or {}
        strategy_source_kind = "industry" if facts.scope_type == "industry" else "manual"
        strategy_source_ref = _string(strategy.get("strategy_id")) or facts.scope_id
        north_star = _string(strategy.get("north_star"))
        if north_star:
            append_signal(
                label="战略北极星",
                summary=f"当前预测应优先服务于北极星目标：{north_star}。",
                source_kind=strategy_source_kind,
                source_ref=strategy_source_ref,
                direction="positive",
                strength=0.42,
                payload={
                    "strategy_id": _string(strategy.get("strategy_id")),
                    "north_star": north_star,
                },
            )
        priority_order = _string_list(strategy.get("priority_order"))
        if priority_order:
            append_signal(
                label="战略优先级",
                summary=f"当前优先顺序为：{' / '.join(priority_order[:3])}。",
                source_kind=strategy_source_kind,
                source_ref=strategy_source_ref,
                direction="neutral",
                strength=0.36,
                payload={
                    "strategy_id": _string(strategy.get("strategy_id")),
                    "priority_order": priority_order,
                },
            )
        execution_constraints = _string_list(strategy.get("execution_constraints"))
        if execution_constraints:
            append_signal(
                label="执行约束",
                summary=f"当前执行需要遵守：{'；'.join(execution_constraints[:3])}。",
                source_kind=strategy_source_kind,
                source_ref=strategy_source_ref,
                direction="neutral",
                strength=0.34,
                payload={
                    "strategy_id": _string(strategy.get("strategy_id")),
                    "execution_constraints": execution_constraints,
                },
            )

        if case.industry_instance_id:
            append_signal(
                label="行业范围",
                summary=(
                    f"预测范围当前锚定在行业实例“{case.industry_instance_id}”。"
                ),
                source_kind="industry",
                source_ref=case.industry_instance_id,
                direction="neutral",
                strength=0.2,
                payload={"scope_type": facts.scope_type, "scope_id": facts.scope_id},
            )
        if case.question:
            append_signal(
                label="提问",
                summary=case.question,
                source_kind="manual",
                source_ref=case.owner_agent_id or case.owner_scope,
                direction="neutral",
                strength=0.35,
                payload={"question": case.question},
            )
        if not signals:
            append_signal(
                label="运行基线",
                summary="当前没有足够强的结构化信号，因此本案例退回到基础运行事实进行判断。",
                source_kind="manual",
                direction="neutral",
                strength=0.2,
                payload={"fallback": True},
            )
        signals.sort(key=lambda item: (-item.strength, item.label))
        return signals

    def _build_recommendations(
        self,
        case: PredictionCaseRecord,
        facts: _FactPack,
        signals: list[PredictionSignalRecord],
    ) -> list[PredictionRecommendationRecord]:
        recommendations: list[PredictionRecommendationRecord] = []
        hottest_agent = self._hottest_agent(facts)
        confidence_baseline = self._case_confidence(signals, [])
        strategy = facts.strategy or {}
        north_star = _string(strategy.get("north_star"))
        priority_order = _string_list(strategy.get("priority_order"))
        execution_constraints = _string_list(strategy.get("execution_constraints"))
        delegation_policy = _string_list(
            strategy.get("delegation_policy"),
            strategy.get("direct_execution_policy"),
        )
        seen_keys: set[tuple[str, str]] = set()
        team_gap_findings = self._team_role_gap_findings(case=case, facts=facts)

        def append_recommendation(
            *,
            recommendation_type: str,
            title: str,
            summary: str,
            priority: int,
            confidence: float,
            risk_level: str,
            action_kind: str,
            executable: bool,
            auto_eligible: bool,
            status: str,
            target_agent_id: str | None = None,
            target_goal_id: str | None = None,
            target_schedule_id: str | None = None,
            target_capability_ids: list[str] | None = None,
            action_payload: dict[str, Any] | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            normalized_title = title.strip()
            if not normalized_title:
                return
            dedupe_key = (recommendation_type, normalized_title.lower())
            if dedupe_key in seen_keys:
                return
            seen_keys.add(dedupe_key)
            strategy_metadata: dict[str, Any] = {}
            if strategy:
                strategy_metadata = {
                    "strategy_id": _string(strategy.get("strategy_id")),
                    "strategy_north_star": north_star,
                    "strategy_priority_order": priority_order[:5],
                    "strategy_execution_constraints": execution_constraints[:4],
                }
            recommendations.append(
                PredictionRecommendationRecord(
                    case_id=case.case_id,
                    recommendation_type=recommendation_type,  # type: ignore[arg-type]
                    title=normalized_title[:180],
                    summary=summary.strip(),
                    priority=max(0, priority),
                    confidence=max(0.0, min(1.0, round(confidence, 3))),
                    risk_level=risk_level,  # type: ignore[arg-type]
                    action_kind=action_kind,
                    executable=executable,
                    auto_eligible=auto_eligible,
                    status=status,  # type: ignore[arg-type]
                    target_agent_id=target_agent_id,
                    target_goal_id=target_goal_id,
                    target_schedule_id=target_schedule_id,
                    target_capability_ids=list(target_capability_ids or []),
                    action_payload=dict(action_payload or {}),
                    metadata={**strategy_metadata, **dict(metadata or {})},
                ),
            )

        def strategy_summary_suffix() -> str:
            notes: list[str] = []
            if north_star:
                notes.append(f"当前北极星是“{north_star}”")
            if execution_constraints:
                notes.append(f"需遵守：{'；'.join(execution_constraints[:2])}")
            if not notes:
                return ""
            return " " + "；".join(notes) + "。"

        active_goal_ids = {
            goal_id for goal_id in _string_list(strategy.get("active_goal_ids")) if goal_id
        }
        strategic_goal_titles = _string_list(
            strategy.get("active_goal_titles"),
            strategy.get("priority_order"),
        )

        def goal_alignment_score(goal: GoalRecord) -> int:
            score = 0
            if goal.id in active_goal_ids:
                score += 100
            haystack = f"{goal.title} {goal.summary}".lower()
            for index, item in enumerate(strategic_goal_titles):
                normalized = item.lower()
                if normalized and normalized in haystack:
                    score = max(score, 80 - (index * 5))
            if str(goal.status).lower() == "active":
                score += 10
            return score

        get_mcp_client_info = getattr(self._capability_service, "get_mcp_client_info", None)
        for workflow in facts.workflows[:4]:
            preview = _safe_dict(workflow.preview_payload)
            dependency_items = [
                _safe_dict(item)
                for item in _safe_list(preview.get("dependencies"))
            ]
            missing_ids = {
                str(item).strip()
                for item in _safe_list(preview.get("missing_capability_ids"))
                if str(item).strip()
            }
            assignment_gap_ids = {
                str(item).strip()
                for item in _safe_list(preview.get("assignment_gap_capability_ids"))
                if str(item).strip()
            }
            for dependency in dependency_items:
                capability_id = _string(dependency.get("capability_id"))
                if capability_id is None:
                    continue
                if capability_id in missing_ids:
                    client_key = self._capability_client_key(capability_id)
                    existing_client = (
                        get_mcp_client_info(client_key)
                        if client_key is not None and callable(get_mcp_client_info)
                        else None
                    )
                    install_templates = [
                        _safe_dict(item)
                        for item in _safe_list(dependency.get("install_templates"))
                    ]
                    if client_key and isinstance(existing_client, dict):
                        append_recommendation(
                            recommendation_type="capability_recommendation",
                            title=f"启用 MCP 客户端“{client_key}”",
                            summary=(
                                f"工作流“{workflow.title}”当前被“{capability_id}”阻塞。"
                                f"启用现有 MCP 客户端“{client_key}”后即可恢复运行。"
                            ),
                            priority=95,
                            confidence=min(0.96, confidence_baseline + 0.18),
                            risk_level="guarded",
                            action_kind="system:update_mcp_client",
                            executable=True,
                            auto_eligible=True,
                            status="proposed",
                            target_capability_ids=[capability_id],
                            action_payload={
                                "client_key": client_key,
                                "client": {"enabled": True},
                                "reason": f"prediction:{case.case_id}:enable-mcp",
                            },
                            metadata={
                                "workflow_run_id": workflow.run_id,
                                "capability_id": capability_id,
                                "install_templates": install_templates,
                            },
                        )
                    else:
                        append_recommendation(
                            recommendation_type="capability_recommendation",
                            title=f"安装能力“{capability_id}”",
                            summary=(
                                f"工作流“{workflow.title}”当前被阻塞，因为“{capability_id}”尚未安装。"
                                "请先通过能力市场安装模板完成接入。"
                            ),
                            priority=92,
                            confidence=min(0.92, confidence_baseline + 0.14),
                            risk_level="guarded",
                            action_kind="manual:install-capability",
                            executable=False,
                            auto_eligible=False,
                            status="manual-only",
                            target_capability_ids=[capability_id],
                            metadata={
                                "workflow_run_id": workflow.run_id,
                                "capability_id": capability_id,
                                "install_templates": install_templates,
                            },
                        )
                if capability_id in assignment_gap_ids:
                    target_agent_ids = [
                        str(item).strip()
                        for item in _safe_list(dependency.get("target_agent_ids"))
                        if str(item).strip()
                    ]
                    target_agent_id = (
                        target_agent_ids[0]
                        if target_agent_ids
                        else _string(hottest_agent.get("agent_id")) if hottest_agent else None
                    )
                    if target_agent_id:
                        append_recommendation(
                            recommendation_type="role_recommendation",
                            title=f"将“{capability_id}”分配给“{target_agent_id}”",
                            summary=(
                                f"工作流“{workflow.title}”所需能力已安装，"
                                f"但目标智能体“{target_agent_id}”尚未拥有“{capability_id}”。"
                            ),
                            priority=88,
                            confidence=min(0.94, confidence_baseline + 0.1),
                            risk_level="guarded",
                            action_kind="system:apply_role",
                            executable=True,
                            auto_eligible=False,
                            status="proposed",
                            target_agent_id=target_agent_id,
                            target_capability_ids=[capability_id],
                            action_payload={
                                "agent_id": target_agent_id,
                                "capabilities": [capability_id],
                                "capability_assignment_mode": "merge",
                                "reason": f"prediction:{case.case_id}:assignment-gap",
                            },
                            metadata={
                                "workflow_run_id": workflow.run_id,
                                "capability_id": capability_id,
                                "target_agent_ids": target_agent_ids,
                            },
                        )

            for step in _safe_list(preview.get("steps")):
                step_payload = _safe_dict(step)
                execution_mode = str(step_payload.get("execution_mode") or "").strip().lower()
                owner_role_id = str(step_payload.get("owner_role_id") or "").strip().lower()
                owner_agent_id = _string(step_payload.get("owner_agent_id"))
                if execution_mode != "leaf":
                    continue
                if owner_agent_id != EXECUTION_CORE_AGENT_ID and owner_role_id != "execution-core":
                    continue
                gap_finding = team_gap_findings.get(
                    self._team_gap_finding_key(workflow.run_id, step_payload),
                )
                if gap_finding is not None:
                    role = gap_finding["role"]
                    goal = gap_finding["goal"]
                    family_id = str(gap_finding.get("family_id") or "").strip()
                    append_recommendation(
                        recommendation_type="role_recommendation",
                        title=f"为团队补位“{role.role_name}”",
                        summary=(
                            f"工作流“{workflow.title}”的叶子执行仍压在执行中枢上，"
                            f"当前团队缺少可长期承接该环路的“{role.role_name}”。"
                            "建议把它作为正式岗位补进团队，而不是继续让执行中枢兜底。"
                        ),
                        priority=86,
                        confidence=min(0.93, confidence_baseline + 0.12),
                        risk_level="confirm",
                        action_kind="system:update_industry_team",
                        executable=True,
                        auto_eligible=False,
                        status="proposed",
                        target_agent_id=role.agent_id,
                        action_payload={
                            "instance_id": case.industry_instance_id,
                            "operation": "add-role",
                            "role": role.model_dump(mode="json"),
                            "goal": goal.model_dump(mode="json"),
                            "reason": f"prediction:{case.case_id}:team-role-gap",
                        },
                        metadata={
                            "gap_kind": "team_role_gap",
                            "industry_instance_id": case.industry_instance_id,
                            "workflow_run_id": workflow.run_id,
                            "workflow_title": workflow.title,
                            "step_id": gap_finding.get("step_id"),
                            "family_id": family_id,
                            "suggested_role_id": role.role_id,
                            "suggested_role_name": role.role_name,
                            "match_signals": _string_list(gap_finding.get("signals")),
                        },
                    )
                    continue
                append_recommendation(
                    recommendation_type="role_recommendation",
                    title="将叶子执行步骤移出执行中枢",
                    summary=(
                        f"工作流“{workflow.title}”仍把叶子步骤压在控制中枢上。"
                        "应将具体执行下放给专业智能体，让控制中枢保持监督角色。"
                    ),
                    priority=82 if delegation_policy else 70,
                    confidence=min(
                        0.9,
                        confidence_baseline + (0.1 if delegation_policy else 0.08),
                    ),
                    risk_level="guarded",
                    action_kind="manual:reassign-leaf",
                    executable=False,
                    auto_eligible=False,
                    status="manual-only",
                    target_agent_id=owner_agent_id,
                    metadata={
                        "workflow_run_id": workflow.run_id,
                        "step_id": _string(step_payload.get("step_id")),
                        "delegation_policy": delegation_policy[:4],
                    },
                )

        telemetry = self._capability_telemetry(case=case, facts=facts)
        getter = getattr(self._capability_service, "get_capability", None)
        capability_getter = getter if callable(getter) else None
        remote_findings = [
            *self._missing_remote_capability_findings(facts=facts),
            *self._underperforming_remote_skill_findings(
                facts=facts,
                telemetry=telemetry,
            ),
            *self._trial_followup_findings(
                case=case,
                facts=facts,
                telemetry=telemetry,
            ),
        ]
        for finding in remote_findings[:5]:
            gap_kind = str(finding.get("gap_kind") or "").strip()
            target_agent_id = _string(finding.get("target_agent_id"))
            if gap_kind in {"missing_capability", "underperforming_capability"}:
                capability_id = _string(finding.get("capability_id"))
                queries = self._compile_remote_skill_queries(
                    facts=facts,
                    target_agent_id=target_agent_id,
                    capability_id=capability_id,
                    workflow_titles=_string_list(
                        finding.get("workflow_title"),
                        finding.get("workflow_titles"),
                    ),
                    task_titles=_string_list(finding.get("task_titles")),
                    task_summaries=_string_list(finding.get("task_summaries")),
                )
                if not queries:
                    continue
                candidates = self._remote_skill_candidates_for_queries(
                    queries=queries,
                    current_capability_id=capability_id if gap_kind == "underperforming_capability" else None,
                )
                if not candidates or target_agent_id is None:
                    continue
                candidate = candidates[0]
                replacement_capability_ids = [capability_id] if gap_kind == "underperforming_capability" and capability_id else []
                requested_capability_ids = resolve_candidate_capability_ids(candidate)
                trial_mode = "replace" if replacement_capability_ids else "merge"
                preflight = build_remote_skill_preflight(
                    candidate=candidate,
                    target_agent_id=target_agent_id,
                    capability_assignment_mode=trial_mode,  # type: ignore[arg-type]
                    replacement_capability_ids=replacement_capability_ids,
                    requested_capability_ids=requested_capability_ids,
                    get_capability_fn=capability_getter,
                    agent_profile_service=self._agent_profile_service,
                )
                metadata = {
                    "gap_kind": gap_kind,
                    "optimization_stage": "trial",
                    "industry_instance_id": case.industry_instance_id,
                    "search_queries": queries,
                    "candidate": candidate.model_dump(mode="json"),
                    "preflight": preflight.model_dump(mode="json"),
                    "replacement_capability_ids": replacement_capability_ids,
                    "replacement_capability_id": replacement_capability_ids[0] if replacement_capability_ids else None,
                    "requested_capability_ids": requested_capability_ids,
                    "workflow_run_id": _string(finding.get("workflow_run_id")),
                    "workflow_run_ids": _string_list(finding.get("workflow_run_ids")),
                    "stats": self._json_safe(finding.get("stats")),
                    "target_agent_id": target_agent_id,
                }
                if candidate.installed and requested_capability_ids:
                    action_kind = "system:apply_role"
                    action_payload: dict[str, Any]
                    if replacement_capability_ids:
                        final_capabilities = [
                            item
                            for item in self._effective_capabilities_for_agent(target_agent_id)
                            if item not in replacement_capability_ids
                        ]
                        for capability_name in requested_capability_ids:
                            if capability_name not in final_capabilities:
                                final_capabilities.append(capability_name)
                        action_payload = {
                            "agent_id": target_agent_id,
                            "capabilities": final_capabilities,
                            "capability_assignment_mode": "replace",
                            "reason": (
                                f"prediction:{case.case_id}:replace-underperforming-capability"
                            ),
                        }
                    else:
                        action_payload = {
                            "agent_id": target_agent_id,
                            "capabilities": requested_capability_ids,
                            "capability_assignment_mode": "merge",
                            "reason": f"prediction:{case.case_id}:assign-installed-remote-candidate",
                        }
                    append_recommendation(
                        recommendation_type="capability_recommendation",
                        title=(
                            f"将已安装能力候选“{candidate.title}”分配给“{target_agent_id}”"
                            if not replacement_capability_ids
                            else f"用“{candidate.title}”替换“{self._capability_hint(capability_id)}”"
                        ),
                        summary=(
                            f"执行中枢已为“{target_agent_id}”找到本地可用候选“{candidate.title}”，"
                            "可直接走治理分配，不需要再次远程安装。"
                            if not replacement_capability_ids
                            else f"能力“{self._capability_hint(capability_id)}”在当前窗口内表现偏弱，"
                            f"先在单个 agent 上用已安装候选“{candidate.title}”进行治理替换。"
                        ),
                        priority=90 if replacement_capability_ids else 84,
                        confidence=min(0.96, confidence_baseline + (0.14 if replacement_capability_ids else 0.1)),
                        risk_level="confirm" if replacement_capability_ids else "guarded",
                        action_kind=action_kind,
                        executable=True,
                        auto_eligible=False,
                        status="proposed",
                        target_agent_id=target_agent_id,
                        target_capability_ids=_string_list(
                            requested_capability_ids,
                            replacement_capability_ids,
                        ),
                        action_payload=action_payload,
                        metadata=metadata,
                    )
                else:
                    append_recommendation(
                        recommendation_type="capability_recommendation",
                        title=(
                            f"试投放远程候选“{candidate.title}”补齐“{self._capability_hint(capability_id)}”"
                            if not replacement_capability_ids
                            else f"试投放远程候选“{candidate.title}”替换“{self._capability_hint(capability_id)}”"
                        ),
                        summary=(
                            f"执行中枢已从 allowlisted 远程源找到候选“{candidate.title}”，"
                            "建议先完成预检与受治理试投放，再决定是否继续扩散。"
                        ),
                        priority=94 if replacement_capability_ids else 86,
                        confidence=min(0.97, confidence_baseline + (0.16 if replacement_capability_ids else 0.12)),
                        risk_level=preflight.risk_level,
                        action_kind="system:trial_remote_skill_assignment",
                        executable=preflight.ready,
                        auto_eligible=preflight.ready and preflight.risk_level == "guarded" and not candidate.review_required,
                        status="proposed" if preflight.ready else "manual-only",
                        target_agent_id=target_agent_id,
                        target_capability_ids=_string_list(
                            requested_capability_ids,
                            replacement_capability_ids,
                        ),
                        action_payload={
                            "candidate": candidate.model_dump(mode="json"),
                            "target_agent_id": target_agent_id,
                            "capability_ids": requested_capability_ids,
                            "replacement_capability_ids": replacement_capability_ids,
                            "capability_assignment_mode": trial_mode,
                            "review_acknowledged": True,
                            "enable": True,
                            "overwrite": False,
                            "reason": (
                                f"prediction:{case.case_id}:trial-remote-skill"
                            ),
                        },
                        metadata=metadata,
                    )
                continue

            old_capability_id = _string(finding.get("old_capability_id"))
            new_capability_id = _string(finding.get("new_capability_id"))
            if old_capability_id is None or new_capability_id is None:
                continue
            if gap_kind == "capability_rollout" and target_agent_id:
                final_capabilities = [
                    item
                    for item in self._effective_capabilities_for_agent(target_agent_id)
                    if item != old_capability_id
                ]
                if new_capability_id not in final_capabilities:
                    final_capabilities.append(new_capability_id)
                append_recommendation(
                    recommendation_type="capability_recommendation",
                    title=f"将“{new_capability_id}”滚动替换到“{target_agent_id}”",
                    summary=(
                        f"试投放链路已证明“{new_capability_id}”优于“{old_capability_id}”，"
                        "可以继续按治理流逐个 agent 扩散替换。"
                    ),
                    priority=87,
                    confidence=min(0.95, confidence_baseline + 0.12),
                    risk_level="guarded",
                    action_kind="system:apply_role",
                    executable=True,
                    auto_eligible=False,
                    status="proposed",
                    target_agent_id=target_agent_id,
                    target_capability_ids=[old_capability_id, new_capability_id],
                    action_payload={
                        "agent_id": target_agent_id,
                        "capabilities": final_capabilities,
                        "capability_assignment_mode": "replace",
                        "reason": f"prediction:{case.case_id}:rollout-remote-skill-replacement",
                    },
                    metadata={
                        "gap_kind": gap_kind,
                        "optimization_stage": str(finding.get("optimization_stage") or "rollout"),
                        "industry_instance_id": case.industry_instance_id,
                        "old_capability_id": old_capability_id,
                        "new_capability_id": new_capability_id,
                        "source_recommendation_id": _string(finding.get("source_recommendation_id")),
                        "stats": self._json_safe(finding.get("stats")),
                    },
                )
                continue
            if gap_kind == "capability_retirement":
                append_recommendation(
                    recommendation_type="capability_recommendation",
                    title=f"降级旧能力“{old_capability_id}”",
                    summary=(
                        f"新候选“{new_capability_id}”已经在试投放中稳定，旧能力“{old_capability_id}”"
                        "可以按治理流降级，避免继续被默认选中。"
                    ),
                    priority=78,
                    confidence=min(0.92, confidence_baseline + 0.08),
                    risk_level="guarded",
                    action_kind="system:set_capability_enabled",
                    executable=True,
                    auto_eligible=False,
                    status="proposed",
                    target_agent_id=target_agent_id,
                    target_capability_ids=[old_capability_id, new_capability_id],
                    action_payload={
                        "capability_id": old_capability_id,
                        "enabled": False,
                        "reason": f"prediction:{case.case_id}:retire-legacy-capability",
                    },
                    metadata={
                        "gap_kind": gap_kind,
                        "optimization_stage": str(finding.get("optimization_stage") or "retire"),
                        "industry_instance_id": case.industry_instance_id,
                        "old_capability_id": old_capability_id,
                        "new_capability_id": new_capability_id,
                        "source_recommendation_id": _string(finding.get("source_recommendation_id")),
                        "stats": self._json_safe(finding.get("stats")),
                    },
                )

        coordinate_goal_candidates = [
            goal
            for goal in facts.goals
            if str(goal.status).lower() in {"active", "draft"}
        ]
        coordinate_goal_candidates.sort(
            key=lambda goal: (
                -goal_alignment_score(goal),
                0 if str(goal.status).lower() == "active" else 1,
                -int(goal.priority),
                goal.title.lower(),
            ),
        )
        coordinate_goal = coordinate_goal_candidates[0] if coordinate_goal_candidates else None
        if coordinate_goal is not None:
            preferred_owner = (
                case.owner_agent_id
                or (_string(hottest_agent.get("agent_id")) if hottest_agent else None)
                or EXECUTION_CORE_AGENT_ID
            )
            aligned_to_strategy = goal_alignment_score(coordinate_goal) > 0
            append_recommendation(
                recommendation_type="plan_recommendation",
                title=f"交给主脑协调“{coordinate_goal.title}”",
                summary=(
                    f"当前范围内已存在目标“{coordinate_goal.title}”，"
                    "但它仍停留在旧 GoalRecord 兼容边界。"
                    "请交给主脑决定是否把它纳入当前 backlog / cycle。"
                ),
                priority=88 if aligned_to_strategy else 76,
                confidence=min(
                    0.94 if aligned_to_strategy else 0.9,
                    confidence_baseline + (0.1 if aligned_to_strategy else 0.06),
                ),
                risk_level="guarded",
                action_kind="manual:coordinate-main-brain",
                executable=False,
                auto_eligible=False,
                status="manual-only",
                target_agent_id=preferred_owner,
                target_goal_id=coordinate_goal.id,
                action_payload={},
                metadata={
                    "goal_title": coordinate_goal.title,
                    "aligned_to_strategy": aligned_to_strategy,
                },
            )

        if hottest_agent is not None:
            hottest_agent_id = _string(hottest_agent.get("agent_id"))
            failed_task_count = int(hottest_agent.get("failed_task_count") or 0)
            active_task_count = int(hottest_agent.get("active_task_count") or 0)
            if hottest_agent_id and hottest_agent_id != EXECUTION_CORE_AGENT_ID and (
                failed_task_count > 0 or active_task_count >= 4
            ):
                append_recommendation(
                    recommendation_type="risk_recommendation",
                    title=f"暂停执行体“{hottest_agent_id}”并复核",
                    summary=(
                        f"智能体“{hottest_agent.get('name') or hottest_agent_id}”当前有 "
                        f"{failed_task_count} 个失败任务、{active_task_count} 个活跃任务。"
                        "建议先暂停该执行体，避免继续放大运行不稳定性。"
                    ),
                    priority=82,
                    confidence=min(0.93, confidence_baseline + 0.12),
                    risk_level="confirm",
                    action_kind="system:pause_actor",
                    executable=True,
                    auto_eligible=False,
                    status="proposed",
                    target_agent_id=hottest_agent_id,
                    action_payload={
                        "agent_id": hottest_agent_id,
                        "target_agent_id": hottest_agent_id,
                        "reason": f"prediction:{case.case_id}:load-shedding",
                    },
                    metadata=dict(hottest_agent),
                )

        if not facts.workflows and facts.goals:
            append_recommendation(
                recommendation_type="schedule_recommendation",
                title="补充周期性自动化计划",
                summary=(
                    "当前范围内已有活跃目标，但缺少可见的自动化执行上下文。"
                    "建议把周期性工作收口为固定 SOP 或运行计划。"
                ),
                priority=58,
                confidence=max(0.55, confidence_baseline),
                risk_level="guarded",
                action_kind="manual:create-schedule",
                executable=False,
                auto_eligible=False,
                status="manual-only",
                metadata={"goal_ids": [goal.id for goal in facts.goals[:5]]},
            )

        if not recommendations:
            append_recommendation(
                recommendation_type="plan_recommendation",
                title="人工复核该预测案例",
                summary=(
                    "当前事实还不足以安全映射到受治理的内核动作。"
                    "请先人工复核，再决定下一步变更。"
                ),
                priority=40,
                confidence=max(0.45, confidence_baseline),
                risk_level="guarded",
                action_kind="manual:review",
                executable=False,
                auto_eligible=False,
                status="manual-only",
            )
        recommendations.sort(
            key=lambda item: (-item.priority, -item.confidence, item.title),
        )
        return recommendations

    def _build_scenarios(
        self,
        case: PredictionCaseRecord,
        facts: _FactPack,
        signals: list[PredictionSignalRecord],
        recommendations: list[PredictionRecommendationRecord],
    ) -> list[PredictionScenarioRecord]:
        positive_strength = sum(item.strength for item in signals if item.direction == "positive")
        negative_strength = sum(item.strength for item in signals if item.direction == "negative")
        signal_balance = positive_strength - negative_strength
        confidence = self._case_confidence(signals, recommendations)
        executable_recommendations = [item for item in recommendations if item.executable]
        top_recommendations = recommendations[:3]
        risk_factors = [item.label for item in signals if item.direction == "negative"][:4]
        assumptions = [
            f"观测窗口：{case.time_window_days} 天。",
            f"已分析信号：{len(signals)} 条。",
            f"已生成建议：{len(recommendations)} 条。",
        ]
        recommended_actions = [item.recommendation_id for item in top_recommendations]
        strategy = facts.strategy or {}
        north_star = _string(strategy.get("north_star"))
        if north_star:
            assumptions.append(f"战略北极星：{north_star}。")
        priority_order = _string_list(strategy.get("priority_order"))
        if priority_order:
            assumptions.append(f"战略优先顺序：{' / '.join(priority_order[:3])}。")
        execution_constraints = _string_list(strategy.get("execution_constraints"))
        if execution_constraints:
            risk_factors = _string_list(
                risk_factors,
                [f"执行约束：{item}" for item in execution_constraints[:2]],
            )[:6]
        base_goal_delta = round((signal_balance * 18.0) + (len(executable_recommendations) * 2.0), 1)
        base_task_delta = round((negative_strength * 9.0) - (positive_strength * 5.0), 1)
        base_risk_delta = round((negative_strength * 12.0) - (positive_strength * 6.0), 1)
        base_resource_delta = round(len(recommendations) * 1.5, 1)
        base_externality_delta = round(signal_balance * 6.0, 1)
        scenario_specs = [
            {
                "kind": "best",
                "title": "最优情景",
                "summary": (
                    "高价值建议被采纳，缺失能力阻塞被清除，"
                    "任务负载在不稳定放大前就完成再分配。"
                ),
                "goal_delta": round(base_goal_delta + 12.0, 1),
                "task_load_delta": round(base_task_delta - 8.0, 1),
                "risk_delta": round(base_risk_delta - 10.0, 1),
                "resource_delta": round(base_resource_delta + 3.0, 1),
                "externality_delta": round(base_externality_delta + 4.0, 1),
                "confidence": min(0.95, confidence + 0.08),
                "assumptions": assumptions + ["受治理建议能够被快速采纳。"],
                "risk_factors": risk_factors[:2],
            },
            {
                "kind": "base",
                "title": "基线情景",
                "summary": (
                    "当前运行轨迹大体延续，只进行选择性人工跟进，"
                    "能力分布没有发生显著结构变化。"
                ),
                "goal_delta": base_goal_delta,
                "task_load_delta": base_task_delta,
                "risk_delta": base_risk_delta,
                "resource_delta": base_resource_delta,
                "externality_delta": base_externality_delta,
                "confidence": confidence,
                "assumptions": assumptions,
                "risk_factors": risk_factors,
            },
            {
                "kind": "worst",
                "title": "最差情景",
                "summary": (
                    "当前阻塞持续未解，过载执行体继续吸收工作，"
                    "运行质量进一步退化并带来更多人工介入。"
                ),
                "goal_delta": round(base_goal_delta - 14.0, 1),
                "task_load_delta": round(base_task_delta + 10.0, 1),
                "risk_delta": round(base_risk_delta + 12.0, 1),
                "resource_delta": round(base_resource_delta + 5.0, 1),
                "externality_delta": round(base_externality_delta - 5.0, 1),
                "confidence": max(0.25, confidence - 0.08),
                "assumptions": assumptions + ["没有任何受治理建议被及时采纳。"],
                "risk_factors": risk_factors + ["建议积压仍在持续扩大。"],
            },
        ]
        return [
            PredictionScenarioRecord(
                case_id=case.case_id,
                scenario_kind=item["kind"],  # type: ignore[arg-type]
                title=str(item["title"]),
                summary=str(item["summary"]),
                confidence=max(0.0, min(1.0, round(float(item["confidence"]), 3))),
                goal_delta=float(item["goal_delta"]),
                task_load_delta=float(item["task_load_delta"]),
                risk_delta=float(item["risk_delta"]),
                resource_delta=float(item["resource_delta"]),
                externality_delta=float(item["externality_delta"]),
                assumptions=list(item["assumptions"]),
                risk_factors=list(item["risk_factors"]),
                recommendation_ids=recommended_actions,
                metadata={
                    "scope_type": facts.scope_type,
                    "scope_id": facts.scope_id,
                },
            )
            for item in scenario_specs
        ]
