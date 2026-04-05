# -*- coding: utf-8 -*-

from __future__ import annotations



from .service_context import *  # noqa: F401,F403

from .service_recommendation_search import *  # noqa: F401,F403

from .service_recommendation_pack import *  # noqa: F401,F403

from .main_brain_cognitive_surface import build_main_brain_cognitive_surface
from .report_synthesis import synthesize_reports





class _IndustryStrategyMixin:
    def _staffing_backlog_resolution_closed(
        self,
        *,
        team: IndustryTeamBlueprint,
        metadata: dict[str, Any],
    ) -> bool:
        target_role_id = _string(metadata.get("seat_target_role_id")) or _string(
            metadata.get("industry_role_id"),
        )
        target_agent_id = _string(metadata.get("seat_target_agent_id")) or _string(
            metadata.get("owner_agent_id"),
        )
        if target_role_id is None and target_agent_id is None:
            return False
        normalized_role_id = normalize_industry_role_id(target_role_id)
        normalized_agent_id = _string(target_agent_id)
        for role in team.agents:
            if (
                normalized_role_id is not None
                and normalize_industry_role_id(role.role_id) == normalized_role_id
            ):
                return True
            if normalized_agent_id is not None and _string(role.agent_id) == normalized_agent_id:
                return True
        return False

    def _decorate_report_synthesis_payload(

        self,

        payload: dict[str, Any],

    ) -> dict[str, Any]:

        resolved = dict(payload)

        resolved.setdefault(

            "control_core_contract",

            [

                "compare reports",

                "detect conflicts and holes",

                "surface staffing/routing gaps",

                "own final operator-facing synthesis before delegating more work",

            ],

        )

        return resolved



    def _resolve_report_synthesis_payload(

        self,

        *,

        cycle_record: OperatingCycleRecord | None,

        agent_report_records: Sequence[AgentReportRecord],

    ) -> dict[str, Any]:

        metadata = cycle_record.metadata if cycle_record is not None else None

        if isinstance(metadata, dict):

            payload = metadata.get("report_synthesis")

            if isinstance(payload, dict):

                return self._decorate_report_synthesis_payload(dict(payload))

        scoped_reports = [

            report

            for report in agent_report_records

            if cycle_record is None or report.cycle_id == cycle_record.id

        ]

        return self._decorate_report_synthesis_payload(

            synthesize_reports(scoped_reports),

        )

    def _apply_chat_writeback_to_profile(

        self,

        profile: IndustryProfile,

        *,

        plan: ChatWritebackPlan,

    ) -> IndustryProfile:

        updated_requirements = _unique_strings(

            list(profile.operator_requirements or []),

            list(plan.strategy.operator_requirements),

        )

        experience_mode = (

            "operator-guided"

            if plan.strategy.switch_to_operator_guided

            else profile.experience_mode

        )

        if (

            updated_requirements == list(profile.operator_requirements or [])

            and experience_mode == profile.experience_mode

        ):

            return profile

        return profile.model_copy(

            update={

                "experience_mode": experience_mode,

                "operator_requirements": updated_requirements,

            },

        )



    def _resolve_chat_writeback_target_role(

        self,

        *,

        record: IndustryInstanceRecord,

        team: IndustryTeamBlueprint,

        message_text: str,

        requested_surfaces: list[str] | None = None,

    ) -> tuple[IndustryRoleBlueprint | None, list[str]]:

        goal_context_by_agent = self._build_instance_goal_context_by_agent(record=record)

        normalized_requested_surfaces = _unique_strings(list(requested_surfaces or []))

        best_role: IndustryRoleBlueprint | None = None

        best_score = 0

        best_signals: list[str] = []

        for role in team.agents:

            if is_execution_core_role_id(role.role_id):

                continue

            score, signals = self._score_chat_writeback_role(

                role=role,

                message_text=message_text,

                goal_context=goal_context_by_agent.get(role.agent_id, []),

                requested_surfaces=normalized_requested_surfaces,

            )

            if score > best_score or (

                score == best_score and len(signals) > len(best_signals)

            ):

                best_role = role

                best_score = score

                best_signals = signals

        if best_role is None:

            return None, []

        if normalized_requested_surfaces:

            if best_score < 4:

                return None, []

        elif best_score < 8:

            return None, []

        return best_role, best_signals



    def _build_instance_goal_context_by_agent(

        self,

        *,

        record: IndustryInstanceRecord,

    ) -> dict[str, list[str]]:

        owner_scope = _string(record.owner_scope)

        if owner_scope is None:

            return {}

        context_by_agent_id: dict[str, list[str]] = {}

        for goal in self._goal_service.list_goals(owner_scope=owner_scope):

            override = self._goal_override_repository.get_override(goal.id)

            if not self._goal_belongs_to_instance(

                goal,

                record=record,

                override=override,

            ):

                continue

            owner_agent_id = self._resolve_goal_owner_agent_id(

                goal,

                override=override,

                record=record,

            )

            if owner_agent_id is None:

                continue

            bucket = context_by_agent_id.setdefault(owner_agent_id, [])

            bucket.extend(

                _unique_strings(

                    goal.title,

                    goal.summary,

                    list(override.plan_steps) if override is not None else [],

                ),

            )

        return {

            agent_id: _unique_strings(values)

            for agent_id, values in context_by_agent_id.items()

        }



    def _message_has_research_intent(
        self,
        *,
        message_blob: str,
        message_terms: set[str],
    ) -> bool:
        if not message_blob:
            return False
        direct_hints = {
            "research",
            "analysis",
            "monitor",
            "monitoring",
            "signal",
            "signals",
            "insight",
            "competitor",
            "competitors",
            "benchmark",
            "调研",
            "研究",
            "分析",
            "监控",
            "竞品",
            "同行",
            "情报",
            "趋势",
            "线索",
        }
        return any(hint in message_blob or hint in message_terms for hint in direct_hints)

    def _score_chat_writeback_role(
        self,
        *,
        role: IndustryRoleBlueprint,
        message_text: str,
        goal_context: list[str],
        requested_surfaces: list[str] | None = None,
    ) -> tuple[int, list[str]]:
        capability_mounts = self._list_chat_writeback_role_capability_mounts(role=role)
        capability_ids = self._list_chat_writeback_role_capability_ids(
            role=role,
            capability_mounts=capability_mounts,
        )
        normalized_requested_surfaces = _unique_strings(list(requested_surfaces or []))

        message_blob = _search_blob([message_text])
        message_terms = {
            term
            for term in _extract_search_terms([message_text], limit=24)
            if term not in _CHAT_WRITEBACK_ROUTING_STOPWORDS
        }
        research_intent = self._message_has_research_intent(
            message_blob=message_blob,
            message_terms=message_terms,
        )
        values = self._build_chat_writeback_role_values(
            role=role,
            goal_context=goal_context,
        )
        primary_values = _unique_strings(
            role.role_id,
            role.goal_kind,
            role.role_name,
            role.name,
        )
        score = 0
        signals: list[str] = []
        if "system:dispatch_query" in capability_ids:
            score += 1

        matched_surface_count = 0
        missing_surface_count = 0
        for surface in normalized_requested_surfaces:
            surface_signal = self._role_surface_support_signal(
                role=role,
                capability_ids=capability_ids,
                capability_mounts=capability_mounts,
                surface=surface,
            )
            if surface_signal is None:
                missing_surface_count += 1
                continue
            matched_surface_count += 1
            score += 6 if surface_signal.endswith("capability match") else 4
            signals.append(surface_signal)
        if normalized_requested_surfaces and matched_surface_count == 0:
            return 0, []
        if missing_surface_count:
            score -= missing_surface_count * 3
        if normalized_requested_surfaces and matched_surface_count:
            is_researcher = normalize_industry_role_id(role.role_id) == "researcher"
            if is_researcher and not research_intent:
                score -= 2
                signals.append("support-role penalty on non-research surface")
            elif not is_researcher and role.agent_class == "business":
                score += 1
                signals.append("execution role surface fit")

        for value in primary_values:
            normalized = _string(value)
            lowered = normalized.lower() if normalized is not None else ""
            if lowered and lowered in message_blob:
                score += 8
                signals.append(f"explicit role match: {normalized}")

        for value in values:
            normalized = _string(value)
            if normalized is None:
                continue
            lowered = normalized.lower()
            if len(lowered) >= 4 and lowered in message_blob:
                score += 4
                signals.append(f"context match: {normalized[:32]}")
            overlap = [
                term
                for term in _tokenize_capability_hint(lowered)
                if term in message_terms and term not in _CHAT_WRITEBACK_ROUTING_STOPWORDS
            ]
            if overlap:
                score += min(len(overlap), 3) * 2
                signals.append("keyword match: " + "/".join(overlap[:3]))

        role_blob = _search_blob(values)
        for triggers, hints in _CHAT_WRITEBACK_ROLE_SIGNAL_HINTS:
            if not any(trigger in role_blob for trigger in triggers):
                continue
            matched = [
                hint
                for hint in hints
                if hint.strip() and hint.lower() in message_blob
            ]
            if matched:
                score += 3
                signals.append("intent match: " + "/".join(matched[:2]))

        if not normalized_requested_surfaces:
            inferred_surfaces = infer_requested_execution_surfaces(
                texts=[message_text],
                capability_ids=list(capability_ids),
                capability_mounts=capability_mounts,
                environment_texts=self._build_chat_writeback_role_surface_environment_texts(
                    role=role,
                ),
            )
            for surface in inferred_surfaces:
                surface_signal = self._role_surface_support_signal(
                    role=role,
                    capability_ids=capability_ids,
                    capability_mounts=capability_mounts,
                    surface=surface,
                )
                if surface_signal is not None:
                    score += 4 if surface_signal.endswith("capability match") else 2
                    signals.append(surface_signal)
        return score, _unique_strings(signals)

    def _build_chat_writeback_role_values(

        self,

        *,

        role: IndustryRoleBlueprint,

        goal_context: list[str],

    ) -> list[str]:

        return _unique_strings(

            role.role_id,

            role.goal_kind,

            role.name,

            role.role_name,

            role.role_summary,

            role.mission,

            list(role.environment_constraints),

            list(role.evidence_expectations),

            goal_context,

        )



    def _list_chat_writeback_role_capability_ids(

        self,

        *,

        role: IndustryRoleBlueprint,

        capability_mounts: Sequence[Any] | None = None,

    ) -> set[str]:

        capability_ids = {

            capability.strip().lower()

            for capability in role.allowed_capabilities

            if isinstance(capability, str) and capability.strip()

        }

        mounts = (
            list(capability_mounts)
            if capability_mounts is not None
            else self._list_chat_writeback_role_capability_mounts(role=role)
        )
        for mount in mounts:

            capability_id = _string(getattr(mount, "id", None))

            if capability_id is not None:

                capability_ids.add(capability_id.lower())

        return capability_ids



    def _list_chat_writeback_role_capability_mounts(

        self,

        *,

        role: IndustryRoleBlueprint,

    ) -> list[Any]:

        service = self._capability_service

        lister = getattr(service, "list_accessible_capabilities", None)

        if not callable(lister):

            return []

        try:

            mounts = lister(agent_id=role.agent_id, enabled_only=True)

        except Exception:

            logger.exception(

                "Failed to list accessible capabilities for chat writeback role '%s'",

                role.agent_id,

            )

            return []

        return list(mounts or [])



    def _build_chat_writeback_role_surface_environment_texts(

        self,

        *,

        role: IndustryRoleBlueprint,

    ) -> list[str]:

        return _unique_strings(

            list(role.environment_constraints),

            role.role_summary,

            role.mission,

            role.role_name,

            role.name,

            list(role.preferred_capability_families or []),

        )



    def _collect_team_surface_context(

        self,

        *,

        team: IndustryTeamBlueprint,

    ) -> tuple[list[str], list[Any], list[str]]:

        capability_ids: list[str] = []

        capability_mounts: list[Any] = []

        environment_texts: list[str] = []

        for role in team.agents:

            if is_execution_core_role_id(role.role_id):

                continue

            role_mounts = self._list_chat_writeback_role_capability_mounts(role=role)

            capability_mounts.extend(role_mounts)

            capability_ids.extend(

                self._list_chat_writeback_role_capability_ids(

                    role=role,

                    capability_mounts=role_mounts,

                )

            )

            environment_texts.extend(

                self._build_chat_writeback_role_surface_environment_texts(role=role)

            )

        return _unique_strings(capability_ids), capability_mounts, _unique_strings(environment_texts)



    def _role_surface_support_signal(

        self,

        *,

        role: IndustryRoleBlueprint,

        capability_ids: set[str],

        capability_mounts: Sequence[Any] | None = None,

        surface: str,

    ) -> str | None:
        return resolve_execution_surface_support(

            surface=surface,

            capability_ids=list(capability_ids),

            capability_mounts=capability_mounts,

            environment_texts=self._build_chat_writeback_role_surface_environment_texts(

                role=role,

            ),

            preferred_families=list(role.preferred_capability_families or []),

        )



    def _collect_chat_writeback_surface_texts(

        self,

        *,

        message_text: str,

        plan: ChatWritebackPlan | None = None,

    ) -> list[str]:

        texts = _unique_strings(message_text)

        if plan is not None:

            if plan.goal is not None:

                texts = _unique_strings(

                    texts,

                    plan.goal.title,

                    plan.goal.summary,

                    list(plan.goal.plan_steps),

                )

            if plan.schedule is not None:

                texts = _unique_strings(

                    texts,

                    plan.schedule.title,

                    plan.schedule.summary,

                    plan.schedule.prompt,

                )

        return [text for text in texts if _string(text)]



    def _list_chat_writeback_requested_surfaces(

        self,

        *,

        message_text: str,

        plan: ChatWritebackPlan | None = None,

        capability_ids: Sequence[str] | None = None,

        capability_mounts: Sequence[Any] | None = None,

        environment_texts: Sequence[str] | None = None,

    ) -> list[str]:

        texts = self._collect_chat_writeback_surface_texts(

            message_text=message_text,

            plan=plan,

        )

        return infer_requested_execution_surfaces(

            texts=texts,

            capability_ids=capability_ids,

            capability_mounts=capability_mounts,

            environment_texts=environment_texts,

        )



    def _resolve_chat_writeback_agent_status(

        self,

        *,

        role: IndustryRoleBlueprint,

    ) -> str:

        snapshot = self._get_agent_snapshot(role.agent_id) or {}

        status = _string(snapshot.get("status"))

        if status:

            return status

        runtime_status = _string(snapshot.get("runtime_status"))

        if runtime_status in {"running", "active"}:

            return "running"

        return "idle"



    def _find_chat_writeback_schedule(

        self,

        *,

        industry_instance_id: str,

        fingerprint: str,

    ) -> str | None:

        if self._schedule_repository is None:

            return None

        for schedule in self._schedule_repository.list_schedules():

            if _string(schedule.status) == "deleted":

                continue

            spec_payload = dict(schedule.spec_payload or {})

            meta_mapping = (

                dict(spec_payload.get("meta"))

                if isinstance(spec_payload.get("meta"), dict)

                else {}

            )

            if _string(meta_mapping.get("industry_instance_id")) != industry_instance_id:

                continue

            if _string(meta_mapping.get("chat_writeback_fingerprint")) != fingerprint:

                continue

            return _string(schedule.id)

        return None



    def _build_chat_writeback_schedule_seed(

        self,

        *,

        record: IndustryInstanceRecord,

        profile: IndustryProfile,

        team: IndustryTeamBlueprint,

        plan: ChatWritebackPlan,

        session_id: str | None,

        channel: str | None,

        owner_agent_id: str,

        industry_role_id: str,

        goal_kind: str,

    ) -> IndustryScheduleSeed:

        schedule_plan = plan.schedule

        if schedule_plan is None:

            raise ValueError("schedule plan is required")

        schedule_id = f"{record.instance_id}-chat-loop-{plan.fingerprint}"

        resolved_channel = _string(channel) or "console"

        default_session_id = f"industry:{record.instance_id}:{industry_role_id}"

        resolved_session_id = (

            _string(session_id)

            if industry_role_id == EXECUTION_CORE_ROLE_ID

            else None

        ) or default_session_id

        role = next(

            (

                item

                for item in team.agents

                if item.agent_id == owner_agent_id or item.role_id == industry_role_id

            ),

            None,

        )

        task_mode = infer_industry_task_mode(

            role_id=industry_role_id,

            goal_kind=goal_kind,

            source="chat-writeback",

        )

        prompt_text = schedule_plan.prompt

        if role is not None:

            prompt_text = build_industry_execution_prompt(

                profile=profile,

                role=role,

                goal_title=plan.goal.title if plan.goal is not None else None,

                goal_summary=plan.goal.summary if plan.goal is not None else None,

                team_label=team.label or record.label,

                cadence_summary=schedule_plan.summary,

                task_mode=task_mode,

                primary_instruction=(

                    f"Translate this operator instruction into the next actionable schedule: {plan.normalized_text}"

                ),

            )

        request_payload = {

            "channel": resolved_channel,

            "session_id": resolved_session_id,

            "user_id": record.owner_scope,

            "agent_id": owner_agent_id,

            "owner_scope": record.owner_scope,

            "industry_instance_id": record.instance_id,

            "industry_role_id": industry_role_id,

            "industry_label": team.label or record.label,

            "task_mode": task_mode,

            "session_kind": "industry-agent-chat",

            "input": [

                {

                    "type": "message",

                    "role": "user",

                    "content": [

                        {

                            "type": "text",

                            "text": prompt_text,

                        }

                    ],

                }

            ],

        }

        if role is not None and _string(role.role_name):

            request_payload["industry_role_name"] = role.role_name

        return IndustryScheduleSeed(

            schedule_id=schedule_id,

            title=schedule_plan.title,

            summary=schedule_plan.summary,

            cron=schedule_plan.cron,

            timezone="UTC",

            owner_agent_id=owner_agent_id,

            dispatch_channel=resolved_channel,

            dispatch_user_id=record.owner_scope,

            dispatch_session_id=resolved_session_id,

            dispatch_mode="stream",

            request_payload=request_payload,

            metadata={

                "bootstrap_kind": "industry-v1",

                "industry_instance_id": record.instance_id,

                "industry_role_id": industry_role_id,

                "owner_agent_id": owner_agent_id,

                "goal_kind": goal_kind,

                "task_mode": task_mode,

                "source": "chat-writeback",

                "chat_writeback_fingerprint": plan.fingerprint,

                "chat_writeback_instruction": plan.normalized_text,

            },

        )



    def _merge_chat_writeback_strategy(

        self,

        *,

        record: IndustryInstanceRecord,

        profile: IndustryProfile,

        team: IndustryTeamBlueprint,

        execution_core_identity: IndustryExecutionCoreIdentity,

        existing_strategy: StrategyMemoryRecord | None,

        plan: ChatWritebackPlan,

    ) -> StrategyMemoryRecord:

        base_strategy = self._build_strategy_memory_record(

            record,

            profile=profile,

            team=team,

            execution_core_identity=execution_core_identity,

        )

        existing_metadata = (

            dict(existing_strategy.metadata or {})

            if existing_strategy is not None

            else {}

        )

        chat_history = [

            dict(item)

            for item in list(existing_metadata.get("chat_writeback_history") or [])

            if isinstance(item, dict)

        ]

        existing_history_item = next(

            (

                item

                for item in chat_history

                if _string(item.get("fingerprint")) == plan.fingerprint

            ),

            None,

        )

        merged_classification = _unique_strings(

            list(existing_history_item.get("classification") or [])

            if existing_history_item is not None

            else [],

            list(plan.classifications),

        )

        if existing_history_item is None:

            chat_history.append(

                {

                    "fingerprint": plan.fingerprint,

                    "instruction": plan.normalized_text,

                    "classification": merged_classification,

                    "updated_at": _utc_now().isoformat(),

                },

            )

        elif (

            _string(existing_history_item.get("instruction")) != plan.normalized_text

            or list(existing_history_item.get("classification") or []) != merged_classification

        ):

            existing_history_item.update(

                {

                    "instruction": plan.normalized_text,

                    "classification": merged_classification,

                    "updated_at": _utc_now().isoformat(),

                },

            )

        merged_metadata = {

            **existing_metadata,

            **dict(base_strategy.metadata or {}),

            "chat_writeback_history": chat_history,

        }

        return base_strategy.model_copy(

            update={

                "priority_order": _unique_strings(

                    list(plan.strategy.priority_order),

                    list(existing_strategy.priority_order or [])

                    if existing_strategy is not None

                    else [],

                    list(base_strategy.priority_order or []),

                ),

                "execution_constraints": _unique_strings(

                    list(base_strategy.execution_constraints or []),

                    list(existing_strategy.execution_constraints or [])

                    if existing_strategy is not None

                    else [],

                    list(plan.strategy.execution_constraints),

                ),

                "metadata": merged_metadata,

            },

        )



    def _strategy_memory_changed(

        self,

        existing_strategy: StrategyMemoryRecord | None,

        merged_strategy: StrategyMemoryRecord,

    ) -> bool:

        if existing_strategy is None:

            return True

        existing_payload = compact_strategy_payload(

            existing_strategy.model_dump(mode="json"),

        )

        merged_payload = compact_strategy_payload(

            merged_strategy.model_dump(mode="json"),

        )

        return any(

            existing_payload.get(field_name) != merged_payload.get(field_name)

            for field_name in (

                "priority_order",

                "execution_constraints",

                "metadata",

                "active_goal_ids",

                "active_goal_titles",

            )

        )



    def _build_instance_record(

        self,

        plan: _IndustryPlan,

        *,

        existing: IndustryInstanceRecord | None,

        goal_ids: list[str],

        schedule_ids: list[str],

        status: str,

        lifecycle_status: str | None = None,

        autonomy_status: str | None = None,

        current_cycle_id: str | None = None,

        next_cycle_due_at: datetime | None = None,

        last_cycle_started_at: datetime | None = None,

    ) -> IndustryInstanceRecord:

        now = _utc_now()

        execution_core_identity = self._build_execution_core_identity(

            instance_id=plan.draft.team.team_id,

            profile=plan.profile,

            team=plan.draft.team,

            industry_label=plan.draft.team.label or plan.profile.primary_label(),

            industry_summary=plan.draft.team.summary,

        )

        return IndustryInstanceRecord(

            instance_id=plan.draft.team.team_id,

            bootstrap_kind="industry-v1",

            label=plan.draft.team.label or plan.profile.primary_label(),

            summary=plan.draft.team.summary or (

                f"Industry runtime instance for {plan.profile.primary_label()} in {plan.profile.industry}."

            ),

            owner_scope=plan.owner_scope,

            status=status,

            profile_payload=plan.profile.model_dump(mode="json"),

            team_payload=plan.draft.team.model_dump(mode="json"),

            execution_core_identity_payload=execution_core_identity.model_dump(mode="json"),

            goal_ids=list(goal_ids),

            agent_ids=[agent.agent_id for agent in plan.draft.team.agents],

            schedule_ids=list(schedule_ids),

            lifecycle_status=(

                lifecycle_status

                if lifecycle_status is not None

                else (existing.lifecycle_status if existing is not None else "running")

            ),

            autonomy_status=(

                autonomy_status

                if autonomy_status is not None

                else (existing.autonomy_status if existing is not None else "waiting-confirm")

            ),

            current_cycle_id=(

                current_cycle_id

                if current_cycle_id is not None

                else (existing.current_cycle_id if existing is not None else None)

            ),

            next_cycle_due_at=(

                next_cycle_due_at

                if next_cycle_due_at is not None

                else (existing.next_cycle_due_at if existing is not None else None)

            ),

            last_cycle_started_at=(

                last_cycle_started_at

                if last_cycle_started_at is not None

                else (existing.last_cycle_started_at if existing is not None else None)

            ),

            created_at=existing.created_at if existing is not None else now,

            updated_at=now,

        )



    def _build_execution_core_identity(

        self,

        *,

        instance_id: str,

        profile: IndustryProfile,

        team: IndustryTeamBlueprint,

        industry_label: str | None = None,

        industry_summary: str | None = None,

    ) -> IndustryExecutionCoreIdentity:

        execution_core = self._resolve_role_blueprint(team, EXECUTION_CORE_ROLE_ID)

        resolved_label = (

            _string(team.label)

            or _string(industry_label)

            or profile.primary_label()

        )

        resolved_summary = (

            _string(team.summary)

            or _string(industry_summary)

            or f"Industry runtime instance for {profile.primary_label()} in {profile.industry}."

        )

        delegation_policy = _build_execution_core_delegation_policy()

        direct_execution_policy = _build_execution_core_direct_execution_policy()

        return IndustryExecutionCoreIdentity(

            binding_id=f"{instance_id}:{EXECUTION_CORE_ROLE_ID}",

            agent_id=EXECUTION_CORE_AGENT_ID,

            role_id=EXECUTION_CORE_ROLE_ID,

            industry_instance_id=instance_id,

            identity_label=f"{resolved_label} / {_EXECUTION_CORE_NAME}",

            industry_label=resolved_label,

            industry_summary=resolved_summary,

            role_name=(

                _string(execution_core.role_name)

                if execution_core is not None

                else _EXECUTION_CORE_NAME

            )

            or _EXECUTION_CORE_NAME,

            role_summary=(

                _string(execution_core.role_summary)

                if execution_core is not None

                else _EXECUTION_CORE_SUMMARY

            )

            or _EXECUTION_CORE_SUMMARY,

            mission=(

                _string(execution_core.mission)

                if execution_core is not None

                else _EXECUTION_CORE_MISSION

            )

            or _EXECUTION_CORE_MISSION,

            thinking_axes=_build_execution_core_thinking_axes(profile),

            environment_constraints=(

                list(execution_core.environment_constraints)

                if execution_core is not None

                else []

            ),

            allowed_capabilities=(

                list(execution_core.allowed_capabilities)

                if execution_core is not None

                else []

            ),

            operating_mode="control-core",

            delegation_policy=delegation_policy,

            direct_execution_policy=direct_execution_policy,

            evidence_expectations=(

                list(execution_core.evidence_expectations)

                if execution_core is not None

                else []

            ),

        )



    def _materialize_execution_core_identity(

        self,

        record: IndustryInstanceRecord,

        *,

        profile: IndustryProfile | None = None,

        team: IndustryTeamBlueprint | None = None,

    ) -> IndustryExecutionCoreIdentity:

        resolved_profile = profile or IndustryProfile.model_validate(

            record.profile_payload or {"industry": record.label},

        )

        resolved_team = team or self._materialize_team_blueprint(record)

        fallback_identity = self._build_execution_core_identity(

            instance_id=record.instance_id,

            profile=resolved_profile,

            team=resolved_team,

            industry_label=record.label,

            industry_summary=record.summary,

        )

        payload = dict(record.execution_core_identity_payload or {})

        if payload:

            try:

                identity = IndustryExecutionCoreIdentity.model_validate(payload)

                return identity.model_copy(

                    update={

                        "identity_label": identity.identity_label

                        or fallback_identity.identity_label,

                        "industry_label": identity.industry_label

                        or fallback_identity.industry_label,

                        "industry_summary": identity.industry_summary

                        or fallback_identity.industry_summary,

                        "role_name": identity.role_name or fallback_identity.role_name,

                        "role_summary": identity.role_summary

                        or fallback_identity.role_summary,

                        "mission": identity.mission or fallback_identity.mission,

                        "thinking_axes": list(identity.thinking_axes)

                        or list(fallback_identity.thinking_axes),

                        "environment_constraints": list(identity.environment_constraints)

                        or list(fallback_identity.environment_constraints),

                        "allowed_capabilities": list(identity.allowed_capabilities)

                        or list(fallback_identity.allowed_capabilities),

                        "operating_mode": identity.operating_mode

                        or fallback_identity.operating_mode,

                        "delegation_policy": list(identity.delegation_policy)

                        or list(fallback_identity.delegation_policy),

                        "direct_execution_policy": list(identity.direct_execution_policy)

                        or list(fallback_identity.direct_execution_policy),

                        "evidence_expectations": list(identity.evidence_expectations)

                        or list(fallback_identity.evidence_expectations),

                    },

                )

            except Exception:

                pass

        return fallback_identity



    def _load_strategy_memory(

        self,

        record: IndustryInstanceRecord,

        *,

        profile: IndustryProfile,

        team: IndustryTeamBlueprint,

        execution_core_identity: IndustryExecutionCoreIdentity,

    ) -> StrategyMemoryRecord | None:

        existing_strategy = self._peek_strategy_memory(record)

        if _string(record.status) == "retired":

            return existing_strategy

        if existing_strategy is not None:

            merged_strategy = self._build_strategy_memory_record(

                record,

                profile=profile,

                team=team,

                execution_core_identity=execution_core_identity,

                existing_strategy=existing_strategy,

            )

            if self._strategy_memory_changed(existing_strategy, merged_strategy):

                upsert = getattr(self._strategy_memory_service, "upsert_strategy", None)

                if callable(upsert):

                    return upsert(merged_strategy)

                return merged_strategy

            return existing_strategy

        return self._sync_strategy_memory(

            record,

            profile=profile,

            team=team,

            execution_core_identity=execution_core_identity,

        )



    def _peek_strategy_memory(

        self,

        record: IndustryInstanceRecord,

    ) -> StrategyMemoryRecord | None:

        service = self._strategy_memory_service

        if service is None:

            return None

        if _string(record.status) == "retired":

            lister = getattr(service, "list_strategies", None)

            if callable(lister):

                records = lister(

                    scope_type="industry",

                    scope_id=record.instance_id,

                    owner_agent_id=EXECUTION_CORE_AGENT_ID,

                    limit=1,

                )

                if records:

                    return records[0]

            return None

        getter = getattr(service, "get_active_strategy", None)

        if callable(getter):

            return getter(

                scope_type="industry",

                scope_id=record.instance_id,

                owner_agent_id=EXECUTION_CORE_AGENT_ID,

            )

        return None



    def _sync_strategy_memory(

        self,

        record: IndustryInstanceRecord,

        *,

        profile: IndustryProfile | None = None,

        team: IndustryTeamBlueprint | None = None,

        execution_core_identity: IndustryExecutionCoreIdentity | None = None,

    ) -> StrategyMemoryRecord | None:

        service = self._strategy_memory_service

        if service is None:

            return None

        existing_strategy = self._peek_strategy_memory(record)

        strategy = self._build_strategy_memory_record(

            record,

            profile=profile,

            team=team,

            execution_core_identity=execution_core_identity,

            existing_strategy=existing_strategy,

        )

        upsert = getattr(service, "upsert_strategy", None)

        if not callable(upsert):

            return strategy

        return upsert(strategy)



    def _build_strategy_memory_record(

        self,

        record: IndustryInstanceRecord,

        *,

        profile: IndustryProfile | None = None,

        team: IndustryTeamBlueprint | None = None,

        execution_core_identity: IndustryExecutionCoreIdentity | None = None,

        existing_strategy: StrategyMemoryRecord | None = None,

    ) -> StrategyMemoryRecord:

        service = self._strategy_memory_service

        resolved_profile = profile or IndustryProfile.model_validate(

            record.profile_payload or {"industry": record.label},

        )

        resolved_team = team or self._materialize_team_blueprint(record)

        resolved_identity = execution_core_identity or self._materialize_execution_core_identity(

            record,

            profile=resolved_profile,

            team=resolved_team,

        )

        existing = existing_strategy or self._peek_strategy_memory(record)

        active_goal_ids = self._active_strategy_goal_ids(record.goal_ids or [])

        goal_titles = self._list_strategy_goal_titles(active_goal_ids)

        priority_order = _unique_strings(

            list(existing.priority_order or []) if existing is not None else [],

            goal_titles or list(resolved_profile.goals),

        )

        north_star = (

            goal_titles[0]

            if goal_titles

            else _string((resolved_profile.goals or [None])[0])

            or _string(record.summary)

            or resolved_identity.mission

        )

        execution_constraints = _unique_strings(

            resolved_profile.constraints,

            resolved_identity.environment_constraints,

            _build_operator_strategy_constraints(resolved_profile),

            list(existing.execution_constraints or []) if existing is not None else [],

        )

        delegation_policy = _build_execution_core_delegation_policy()

        direct_execution_policy = _build_execution_core_direct_execution_policy()

        lane_records = self._list_operating_lanes(record.instance_id, status=None)

        lane_weights = dict(existing.lane_weights or {}) if existing is not None else {}

        if not lane_weights:

            lane_weights = {

                lane.id: float(max(1, lane.priority))

                for lane in lane_records

                if lane.id

            }

        current_cycle = self._current_operating_cycle_record(record.instance_id)

        cycle_records = self._list_operating_cycles(record.instance_id, limit=None)

        open_backlog = self._list_backlog_items(

            record.instance_id,

            status="open",

            limit=None,

        )

        pending_reports = self._list_agent_report_records(

            record.instance_id,

            processed=False,

            limit=None,

        )

        agent_report_records = self._list_agent_report_records(

            record.instance_id,

            limit=None,

        )

        backlog_records = self._list_backlog_items(

            record.instance_id,

            status=None,

            limit=None,

        )

        main_brain_cognitive_surface = build_main_brain_cognitive_surface(

            current_cycle=current_cycle,

            cycles=cycle_records,

            backlog=backlog_records,

            agent_reports=agent_report_records,

        )

        planning_policy = _unique_strings(

            list(existing.planning_policy or []) if existing is not None else [],

            [

                "Run work through explicit cycles instead of letting goals sprawl indefinitely.",

                "Materialize only the most relevant backlog items for the current cycle.",

                "Use agent reports and evidence to decide the next cycle focus.",

            ],

        )

        current_focuses = _unique_strings(

            list(existing.current_focuses or []) if existing is not None else [],

            goal_titles,

            list(resolved_profile.goals),

        )

        paused_lane_ids = [

            lane.id

            for lane in lane_records

            if lane.id and lane.status == "paused"

        ]

        review_rules = _unique_strings(

            list(existing.review_rules or []) if existing is not None else [],

            [

                "Review evidence before changing strategy or priority.",

                "Use unresolved blockers and pending reports as inputs to the next cycle.",

            ],

        )

        report_synthesis = self._resolve_report_synthesis_payload(
            cycle_record=current_cycle,
            agent_report_records=agent_report_records,
        )
        strategic_uncertainties = self._build_strategy_uncertainties(
            pending_reports=pending_reports,
            report_synthesis=report_synthesis,
        )
        lane_budgets = self._build_strategy_lane_budgets(
            lane_records=lane_records,
            lane_weights=lane_weights,
            cycle_records=cycle_records,
            open_backlog=open_backlog,
            pending_reports=pending_reports,
            strategic_uncertainties=strategic_uncertainties,
        )

        strategy_id = (

            getattr(service, "canonical_strategy_id", None)(

                scope_type="industry",

                scope_id=record.instance_id,

                owner_agent_id=EXECUTION_CORE_AGENT_ID,

            )

            if service is not None

            and callable(getattr(service, "canonical_strategy_id", None))

            else f"strategy:industry:{record.instance_id}:{EXECUTION_CORE_AGENT_ID}"

        )

        strategy_record = StrategyMemoryRecord(

            strategy_id=strategy_id,

            scope_type="industry",

            scope_id=record.instance_id,

            owner_agent_id=EXECUTION_CORE_AGENT_ID,

            owner_scope=record.owner_scope,

            industry_instance_id=record.instance_id,

            title=f"{record.label} strategy memory",

            summary=_string(record.summary) or resolved_identity.industry_summary,

            mission=resolved_identity.mission,

            north_star=north_star,

            priority_order=priority_order,

            thinking_axes=list(resolved_identity.thinking_axes),

            delegation_policy=delegation_policy,

            direct_execution_policy=direct_execution_policy,

            execution_constraints=execution_constraints,

            evidence_requirements=list(resolved_identity.evidence_expectations),

            active_goal_ids=active_goal_ids,

            active_goal_titles=goal_titles,

            teammate_contracts=self._build_strategy_teammate_contracts(resolved_team),

            lane_weights=lane_weights,

            strategic_uncertainties=strategic_uncertainties,

            lane_budgets=lane_budgets,

            planning_policy=planning_policy,

            current_focuses=_unique_strings(

                current_focuses,

                [report.headline for report in pending_reports],

            ),

            paused_lane_ids=paused_lane_ids,

            review_rules=review_rules,

            source_ref=f"industry-instance:{record.instance_id}",

            status="active",

            metadata={

                **(dict(existing.metadata or {}) if existing is not None else {}),

                "industry_label": record.label,

                "industry_summary": resolved_identity.industry_summary,

                "identity_label": resolved_identity.identity_label,

                "team_topology": resolved_team.topology,

                "company_name": resolved_profile.company_name,

                "product": resolved_profile.product,

                "business_model": resolved_profile.business_model,

                "experience_mode": resolved_profile.experience_mode,

                "experience_notes": resolved_profile.experience_notes,

                "operator_requirements": list(resolved_profile.operator_requirements),

                "target_customers": list(resolved_profile.target_customers),

                "channels": list(resolved_profile.channels),

                "allowed_capabilities": list(resolved_identity.allowed_capabilities),

                "current_cycle_id": current_cycle.id if current_cycle is not None else None,

                "current_cycle_status": current_cycle.status if current_cycle is not None else None,

                "open_backlog_count": len(open_backlog),

                "pending_report_count": len(pending_reports),

                "main_brain_cognitive_surface": main_brain_cognitive_surface,

            },

            created_at=record.created_at,

            updated_at=record.updated_at,

        )
        compiled_constraints = self._strategy_compiler.compile(strategy_record)
        return strategy_record.model_copy(
            update={
                "strategy_trigger_rules": list(
                    compiled_constraints.strategy_trigger_rules or [],
                ),
            },
        )



    def _list_strategy_goal_titles(self, goal_ids: list[str]) -> list[str]:

        titles: list[str] = []

        for goal_id in goal_ids:

            goal = self._goal_service.get_goal(goal_id)

            title = _string(getattr(goal, "title", None)) if goal is not None else None

            if title is not None:

                titles.append(title)

        return titles

    def _build_strategy_uncertainties(
        self,
        *,
        pending_reports: list[AgentReportRecord],
        report_synthesis: dict[str, Any],
    ) -> list[StrategicUncertaintyRecord]:
        uncertainties: list[StrategicUncertaintyRecord] = []
        seen_ids: set[str] = set()
        reports_by_id = {
            report.id: report
            for report in pending_reports
            if report.id
        }
        holes = list(report_synthesis.get("holes") or [])
        for hole in holes:
            if not isinstance(hole, dict):
                continue
            hole_id = _string(hole.get("hole_id"))
            hole_kind = _string(hole.get("kind"))
            if hole_id is None or hole_kind not in {"uncertainty", "evidence-insufficient"}:
                continue
            if hole_id in seen_ids:
                continue
            seen_ids.add(hole_id)
            report = reports_by_id.get(_string(hole.get("report_id")) or "")
            uncertainties.append(
                StrategicUncertaintyRecord(
                    uncertainty_id=hole_id,
                    statement=_string(hole.get("summary")) or hole_id,
                    scope="lane" if report is not None and report.lane_id else "strategy",
                    impact_level="high" if hole_kind == "evidence-insufficient" else "medium",
                    current_confidence=0.25 if hole_kind == "evidence-insufficient" else 0.35,
                    evidence_against_refs=(
                        [f"agent-report:{report.id}"] if report is not None else []
                    ),
                    review_by_cycle="next-cycle",
                    escalate_when=["confidence-drop", "target-miss"],
                    lane_id=report.lane_id if report is not None else None,
                ),
            )
        for report in pending_reports:
            for index, item in enumerate(list(report.uncertainties or [])):
                summary = _string(item)
                if summary is None:
                    continue
                uncertainty_id = f"uncertainty:{report.id}:{index}"
                if uncertainty_id in seen_ids:
                    continue
                seen_ids.add(uncertainty_id)
                uncertainties.append(
                    StrategicUncertaintyRecord(
                        uncertainty_id=uncertainty_id,
                        statement=summary,
                        scope="lane" if report.lane_id else "strategy",
                        impact_level="high" if bool(report.needs_followup) else "medium",
                        current_confidence=0.4 if bool(report.needs_followup) else 0.5,
                        evidence_for_refs=[f"agent-report:{report.id}"],
                        review_by_cycle="next-cycle",
                        escalate_when=(
                            ["repeated-blocker", "confidence-drop"]
                            if bool(report.needs_followup)
                            else ["confidence-drop", "target-miss"]
                        ),
                        lane_id=report.lane_id,
                    ),
                )
        return uncertainties

    def _build_strategy_lane_budgets(
        self,
        *,
        lane_records: list[OperatingLaneRecord],
        lane_weights: dict[str, float],
        cycle_records: list[OperatingCycleRecord],
        open_backlog: list[BacklogItemRecord],
        pending_reports: list[AgentReportRecord],
        strategic_uncertainties: list[StrategicUncertaintyRecord],
    ) -> list[LaneBudgetRecord]:
        recent_cycles = list(cycle_records[:3])
        total_recent_cycles = max(1, len(recent_cycles))
        lane_cycle_counts: dict[str, int] = {}
        for cycle in recent_cycles:
            for lane_id in list(cycle.focus_lane_ids or []):
                normalized_lane_id = _string(lane_id)
                if normalized_lane_id is None:
                    continue
                lane_cycle_counts[normalized_lane_id] = (
                    lane_cycle_counts.get(normalized_lane_id, 0) + 1
                )
        open_backlog_counts: dict[str, int] = {}
        for item in open_backlog:
            lane_id = _string(item.lane_id)
            if lane_id is None:
                continue
            open_backlog_counts[lane_id] = open_backlog_counts.get(lane_id, 0) + 1
        pending_report_counts: dict[str, int] = {}
        for report in pending_reports:
            lane_id = _string(report.lane_id)
            if lane_id is None:
                continue
            pending_report_counts[lane_id] = pending_report_counts.get(lane_id, 0) + 1
        uncertainty_counts: dict[str, int] = {}
        for uncertainty in strategic_uncertainties:
            lane_id = _string(uncertainty.lane_id)
            if lane_id is None:
                continue
            uncertainty_counts[lane_id] = uncertainty_counts.get(lane_id, 0) + 1
        total_weight = sum(max(float(weight), 0.0) for weight in lane_weights.values()) or 1.0
        budgets: list[LaneBudgetRecord] = []
        for lane in lane_records:
            if not lane.id:
                continue
            target_share = max(float(lane_weights.get(lane.id, max(1, lane.priority))), 0.0)
            target_share = round(target_share / total_weight, 4)
            min_share = round(max(0.0, target_share * 0.5), 4)
            max_share = round(min(1.0, max(target_share, target_share * 1.5)), 4)
            current_share = round(
                float(lane_cycle_counts.get(lane.id, 0)) / float(total_recent_cycles),
                4,
            )
            target_cycle_count = max(1, int(round(target_share * total_recent_cycles)))
            consumed_cycles = lane_cycle_counts.get(lane.id, 0)
            missed_target_cycles = max(target_cycle_count - consumed_cycles, 0)
            consecutive_missed_cycles = 0
            if target_share > 0.0:
                for cycle in recent_cycles:
                    focus_lane_ids = {
                        normalized_lane_id
                        for normalized_lane_id in (
                            _string(item) for item in list(cycle.focus_lane_ids or [])
                        )
                        if normalized_lane_id is not None
                    }
                    if lane.id in focus_lane_ids:
                        break
                    consecutive_missed_cycles += 1
            pressure_count = (
                open_backlog_counts.get(lane.id, 0)
                + pending_report_counts.get(lane.id, 0)
                + uncertainty_counts.get(lane.id, 0)
            )
            review_pressure = (
                "high"
                if pressure_count >= 2
                else ("medium" if pressure_count == 1 else "low")
            )
            defer_reason = (
                f"{lane.title} lane is already over the current budget window."
                if current_share > max_share and open_backlog_counts.get(lane.id, 0) > 0
                else ""
            )
            force_include_reason = (
                f"{lane.title} lane is underfunded relative to current operating pressure."
                if current_share < min_share and pressure_count > 0
                else ""
            )
            budgets.append(
                LaneBudgetRecord(
                    lane_id=lane.id,
                    budget_window="next-3-cycles",
                    target_share=target_share,
                    min_share=min_share,
                    max_share=max_share,
                    current_share=current_share,
                    review_pressure=review_pressure,
                    defer_reason=defer_reason,
                    force_include_reason=force_include_reason,
                    completed_cycles=total_recent_cycles,
                    consumed_cycles=consumed_cycles,
                    metadata={
                        "target_cycle_count": target_cycle_count,
                        "missed_target_cycles": missed_target_cycles,
                        "consecutive_missed_cycles": consecutive_missed_cycles,
                        "open_backlog_count": open_backlog_counts.get(lane.id, 0),
                        "pending_report_count": pending_report_counts.get(lane.id, 0),
                        "uncertainty_count": uncertainty_counts.get(lane.id, 0),
                    },
                ),
            )
        return budgets



    def _build_strategy_teammate_contracts(

        self,

        team: IndustryTeamBlueprint,

    ) -> list[dict[str, Any]]:

        contracts: list[dict[str, Any]] = []

        for agent in team.agents:

            if is_execution_core_agent_id(agent.agent_id):

                continue

            contracts.append(

                {

                    "agent_id": agent.agent_id,

                    "role_id": agent.role_id,

                    "role_name": agent.role_name,

                    "role_summary": agent.role_summary,

                    "mission": agent.mission,

                    "employment_mode": agent.employment_mode,

                    "reports_to": agent.reports_to,

                    "goal_kind": agent.goal_kind,

                    "risk_level": agent.risk_level,

                    "capabilities": list(agent.allowed_capabilities),

                    "evidence_expectations": list(agent.evidence_expectations),

                },

            )

        return contracts



    def _build_instance_summary(

        self,

        record: IndustryInstanceRecord,

    ) -> IndustryInstanceSummary:

        profile = IndustryProfile.model_validate(

            record.profile_payload or {"industry": record.label},

        )

        team = self._materialize_team_blueprint(record)

        status = self._derive_instance_status(record)

        team = team.model_copy(

            update={

                "status": (

                    _string(record.autonomy_status)

                    or _string(record.lifecycle_status)

                    or status

                ),

                "autonomy_status": _string(record.autonomy_status),

                "lifecycle_status": _string(record.lifecycle_status),

            },

        )

        execution_core_identity = self._materialize_execution_core_identity(

            record,

            profile=profile,

            team=team,

        )

        strategy_memory = self._load_strategy_memory(

            record,

            profile=profile,

            team=team,

            execution_core_identity=execution_core_identity,

        )

        lane_records = self._list_operating_lanes(record.instance_id, status=None)
        backlog_records = self._list_backlog_items(record.instance_id, limit=None)
        cycle_records = self._list_operating_cycles(
            record.instance_id,
            status=None,
            limit=None,
        )
        assignment_records = self._list_assignment_records(record.instance_id)
        agent_report_records = self._list_agent_report_records(
            record.instance_id,
            limit=None,
        )

        acquisition_proposals = self._list_instance_acquisition_proposals(

            record.instance_id,

        )

        install_binding_plans = self._list_instance_install_binding_plans(

            record.instance_id,

        )

        onboarding_runs = self._list_instance_onboarding_runs(record.instance_id)

        stats = {
            "agent_count": len(record.agent_ids or []),
            "lane_count": len(lane_records),
            "backlog_count": len(backlog_records),
            "open_backlog_count": sum(
                1
                for item in backlog_records
                if _string(item.status) in {"open", "selected"}
            ),
            "cycle_count": len(cycle_records),
            "assignment_count": len(assignment_records),
            "report_count": len(agent_report_records),

            "schedule_count": len(record.schedule_ids or []),

            "acquisition_proposal_count": len(acquisition_proposals),

            "install_binding_plan_count": len(install_binding_plans),

            "onboarding_run_count": len(onboarding_runs),

        }

        routes = {

            "detail": f"/api/industry/v1/instances/{record.instance_id}",

            "runtime_detail": f"/api/runtime-center/industry/{record.instance_id}",

            "runtime_center": "/api/runtime-center/surface",

        }

        return IndustryInstanceSummary(

            instance_id=record.instance_id,

            bootstrap_kind="industry-v1",

            label=record.label,

            summary=record.summary,

            owner_scope=record.owner_scope,

            profile=profile,

            team=team,

            execution_core_identity=execution_core_identity,

            strategy_memory=strategy_memory,

            status=status,

            autonomy_status=_string(record.autonomy_status),

            lifecycle_status=_string(record.lifecycle_status),

            updated_at=record.updated_at or record.created_at,

            stats=stats,

            routes=routes,

        )



    def _build_instance_detail(

        self,

        record: IndustryInstanceRecord,

        *,

        assignment_id: str | None = None,

        backlog_item_id: str | None = None,

    ) -> IndustryInstanceDetail:

        from .service_runtime_views import _IndustryRuntimeViewsMixin

        return _IndustryRuntimeViewsMixin._build_instance_detail(

            self,

            record,

            assignment_id=assignment_id,

            backlog_item_id=backlog_item_id,

        )

    def _summarize_staffing_assignment(

        self,

        assignment: dict[str, Any] | None,

    ) -> dict[str, Any] | None:

        if not isinstance(assignment, dict):

            return None

        return {

            "assignment_id": _string(assignment.get("assignment_id")),

            "goal_id": _string(assignment.get("goal_id")),

            "backlog_item_id": _string(assignment.get("backlog_item_id")),

            "lane_id": _string(assignment.get("lane_id")),

            "title": _string(assignment.get("title")),

            "summary": _string(assignment.get("summary")),

            "status": _string(assignment.get("status")),

            "route": _string(assignment.get("route")),

            "updated_at": assignment.get("updated_at"),

        }



    def _summarize_staffing_report(

        self,

        report: dict[str, Any] | None,

    ) -> dict[str, Any] | None:

        if not isinstance(report, dict):

            return None

        return {

            "report_id": _string(report.get("report_id")),

            "assignment_id": _string(report.get("assignment_id")),

            "goal_id": _string(report.get("goal_id")),

            "headline": _string(report.get("headline")),

            "summary": _string(report.get("summary")),

            "status": _string(report.get("status")),

            "result": _string(report.get("result")),

            "processed": bool(report.get("processed")),

            "route": _string(report.get("route")),

            "updated_at": report.get("updated_at"),

        }



    def _build_staffing_gap_entry(

        self,

        *,

        backlog_item: dict[str, Any],

        metadata: dict[str, Any],

        decision_request_repository: Any | None,

    ) -> dict[str, Any]:

        decision_request_id = _string(metadata.get("decision_request_id"))

        decision = (

            decision_request_repository.get_decision_request(decision_request_id)

            if decision_request_repository is not None and decision_request_id is not None

            else None

        )

        decision_status = _string(getattr(decision, "status", None))

        proposal_status = _string(metadata.get("proposal_status"))

        backlog_status = _string(backlog_item.get("status"))

        resolution_kind = _string(metadata.get("seat_resolution_kind")) or "routing-pending"

        decision_terminal = decision_status in {"approved", "rejected", "expired"}

        requested_surfaces = _unique_strings(

            [

                surface

                for value in (

                    metadata.get("seat_requested_surfaces"),

                    metadata.get("chat_writeback_requested_surfaces"),

                )

                for surface in (

                    value

                    if isinstance(value, list)

                    else [value]

                )

                if isinstance(surface, str) and surface.strip()

            ]

        )

        return {

            "backlog_item_id": _string(backlog_item.get("backlog_item_id")),

            "kind": resolution_kind,

            "reason": _string(metadata.get("seat_resolution_reason"))

            or _string(backlog_item.get("summary")),

            "requested_surfaces": requested_surfaces,

            "target_role_id": _string(metadata.get("seat_target_role_id")),

            "target_role_name": _string(metadata.get("seat_target_role_name"))

            or _string(metadata.get("industry_role_name")),

            "target_agent_id": _string(metadata.get("seat_target_agent_id"))

            or _string(metadata.get("owner_agent_id")),

            "decision_request_id": decision_request_id,

            "proposal_status": proposal_status,

            "status": decision_status or proposal_status or backlog_status,

            "requires_confirmation": (

                decision_status in {"open", "reviewing"}

                or (

                    not decision_terminal

                    and resolution_kind

                    in {"temporary-seat-proposal", "career-seat-proposal"}

                )

            ),

            "title": _string(backlog_item.get("title")),

            "summary": _string(backlog_item.get("summary")),

            "route": _string(backlog_item.get("route")),

            "updated_at": backlog_item.get("updated_at"),

        }



    def _build_instance_staffing(

        self,

        *,

        team: IndustryTeamBlueprint,

        agents: list[dict[str, Any]],

        backlog: list[dict[str, Any]],

        assignments: list[dict[str, Any]],

        agent_reports: list[dict[str, Any]],

    ) -> dict[str, Any]:

        agent_by_id: dict[str, dict[str, Any]] = {}

        for agent in agents:

            agent_id = _string(agent.get("agent_id")) or _string(agent.get("id"))

            if agent_id is not None:

                agent_by_id[agent_id] = agent



        assignment_by_agent_id: dict[str, dict[str, Any]] = {}

        for assignment in assignments:

            owner_agent_id = _string(assignment.get("owner_agent_id"))

            if owner_agent_id is None or owner_agent_id in assignment_by_agent_id:

                continue

            assignment_by_agent_id[owner_agent_id] = assignment



        report_by_agent_id: dict[str, dict[str, Any]] = {}

        pending_signal_count_by_agent_id: dict[str, int] = {}

        for report in agent_reports:

            owner_agent_id = _string(report.get("owner_agent_id"))

            if owner_agent_id is None:

                continue

            if owner_agent_id not in report_by_agent_id:

                report_by_agent_id[owner_agent_id] = report

            if not bool(report.get("processed")) and _string(report.get("status")) != "cancelled":

                pending_signal_count_by_agent_id[owner_agent_id] = (

                    pending_signal_count_by_agent_id.get(owner_agent_id, 0) + 1

                )



        seat_backlog: list[tuple[dict[str, Any], dict[str, Any]]] = []

        for backlog_item in backlog:

            metadata = (

                dict(backlog_item.get("metadata"))

                if isinstance(backlog_item.get("metadata"), dict)

                else {}

            )

            if _string(metadata.get("seat_resolution_kind")) is None:

                continue

            if self._staffing_backlog_resolution_closed(team=team, metadata=metadata):

                continue

            seat_backlog.append((backlog_item, metadata))

        seat_backlog.sort(

            key=lambda item: _sort_timestamp(item[0].get("updated_at")),

            reverse=True,

        )



        decision_request_repository = getattr(

            self._goal_service,

            "_decision_request_repository",

            None,

        )

        gap_entries = [

            self._build_staffing_gap_entry(

                backlog_item=backlog_item,

                metadata=metadata,

                decision_request_repository=decision_request_repository,

            )

            for backlog_item, metadata in seat_backlog

            if _string(backlog_item.get("status")) in {"open", "selected"}

            and (_string(metadata.get("seat_resolution_kind")) or "routing-pending")

            in {

                "routing-pending",

                "temporary-seat-proposal",

                "career-seat-proposal",

            }

        ]

        active_gap = gap_entries[0] if gap_entries else None

        pending_proposals = [

            entry

            for entry in gap_entries

            if entry.get("kind") in {"temporary-seat-proposal", "career-seat-proposal"}

            and entry.get("status") not in {"approved", "rejected", "expired"}

        ]



        temporary_seats: list[dict[str, Any]] = []

        for role in team.agents:

            if role.employment_mode != "temporary":

                continue

            agent_snapshot = agent_by_id.get(role.agent_id, {})

            assignment = assignment_by_agent_id.get(role.agent_id)

            report = report_by_agent_id.get(role.agent_id)

            temporary_status = _string(agent_snapshot.get("status"))

            if temporary_status is None and isinstance(report, dict):

                temporary_status = _string(report.get("status"))

            if temporary_status is None and isinstance(assignment, dict):

                temporary_status = _string(assignment.get("status"))

            origin_entry = next(

                (

                    self._build_staffing_gap_entry(

                        backlog_item=backlog_item,

                        metadata=metadata,

                        decision_request_repository=decision_request_repository,

                    )

                    for backlog_item, metadata in seat_backlog

                    if _string(metadata.get("seat_target_role_id")) == role.role_id

                    or _string(metadata.get("seat_target_agent_id")) == role.agent_id

                ),

                None,

            )

            temporary_seats.append(

                {

                    "role_id": role.role_id,

                    "role_name": role.role_name,

                    "agent_id": role.agent_id,

                    "status": temporary_status or "ready",

                    "employment_mode": role.employment_mode,

                    "activation_mode": role.activation_mode,

                    "reports_to": role.reports_to,

                    "route": _string(agent_snapshot.get("route"))

                    or f"/api/runtime-center/agents/{quote(role.agent_id)}",

                    "current_assignment": self._summarize_staffing_assignment(assignment),

                    "latest_report": self._summarize_staffing_report(report),

                    "origin": origin_entry,

                    "auto_retire_hint": "Retire this temporary seat after the delegated workload closes.",

                }

            )



        researcher_role = next(

            (

                role

                for role in team.agents

                if normalize_industry_role_id(role.role_id) == "researcher"

            ),

            None,

        )

        researcher: dict[str, Any] | None = None

        if researcher_role is not None:

            agent_snapshot = agent_by_id.get(researcher_role.agent_id, {})

            assignment = assignment_by_agent_id.get(researcher_role.agent_id)

            report = report_by_agent_id.get(researcher_role.agent_id)

            pending_signal_count = pending_signal_count_by_agent_id.get(

                researcher_role.agent_id,

                0,

            )

            researcher_status = _string(agent_snapshot.get("status"))

            if researcher_status is None:

                if pending_signal_count:

                    researcher_status = "waiting-review"

                elif assignment is not None:

                    researcher_status = "assigned"

                else:

                    researcher_status = "ready"

            researcher = {

                "role_id": researcher_role.role_id,

                "role_name": researcher_role.role_name,

                "agent_id": researcher_role.agent_id,

                "status": researcher_status,

                "route": _string(agent_snapshot.get("route"))

                or f"/api/runtime-center/agents/{quote(researcher_role.agent_id)}",

                "current_assignment": self._summarize_staffing_assignment(assignment),

                "latest_report": self._summarize_staffing_report(report),

                "pending_signal_count": pending_signal_count,

                "waiting_for_main_brain": pending_signal_count > 0,

            }



        return {

            "active_gap": active_gap,

            "pending_proposals": pending_proposals,

            "temporary_seats": temporary_seats,

            "researcher": researcher,

        }



    def _collect_instance_goal_statuses(

        self,

        record: IndustryInstanceRecord,

    ) -> list[str]:

        statuses: list[str] = []

        for goal_id in record.goal_ids:

            goal = self._goal_service.get_goal(goal_id)

            if goal is None:

                continue

            statuses.append(_string(goal.status))

        return statuses



    def _active_strategy_goal_ids(self, goal_ids: list[str]) -> list[str]:

        active_goal_ids: list[str] = []

        for goal_id in goal_ids:

            goal = self._goal_service.get_goal(goal_id)

            if goal is None:

                continue

            if _string(goal.status) in {"completed", "archived"}:

                continue

            active_goal_ids.append(goal.id)

        return active_goal_ids



    def _instance_has_live_operation_surface(

        self,

        record: IndustryInstanceRecord,

    ) -> bool:

        current_cycle = self._current_operating_cycle_record(record.instance_id)

        if current_cycle is not None and current_cycle.status not in {"completed", "cancelled"}:

            return True

        if self._list_backlog_items(record.instance_id, status="open", limit=1):

            return True

        if self._list_agent_report_records(record.instance_id, processed=False, limit=1):

            return True

        goal_ids = {goal_id for goal_id in record.goal_ids if isinstance(goal_id, str) and goal_id}

        task_repository = getattr(self._goal_service, "_task_repository", None)

        task_runtime_repository = getattr(self._goal_service, "_task_runtime_repository", None)

        decision_request_repository = getattr(

            self._goal_service,

            "_decision_request_repository",

            None,

        )



        task_ids: list[str] = []

        if task_repository is not None and goal_ids:

            for goal_id in goal_ids:

                for task in task_repository.list_tasks(goal_id=goal_id):

                    task_ids.append(task.id)

                    if task.status in {"created", "queued", "running", "needs-confirm"}:

                        return True

                    if task_runtime_repository is None:

                        continue

                    runtime = task_runtime_repository.get_runtime(task.id)

                    if runtime is None:

                        continue

                    if runtime.current_phase in {"compiled", "risk-check", "executing", "waiting-confirm"}:

                        return True

                    if runtime.runtime_status in {"cold", "hydrating", "active", "waiting-confirm"}:

                        return True



        if decision_request_repository is not None and task_ids:

            decisions = decision_request_repository.list_decision_requests(

                task_ids=task_ids,

            )

            if any(getattr(decision, "status", None) in {"open", "reviewing"} for decision in decisions):

                return True



        if self._schedule_repository is not None:

            for schedule_id in list(record.schedule_ids or []):

                schedule = self._schedule_repository.get_schedule(schedule_id)

                if schedule is not None and schedule.enabled:

                    return True

        return False



    def _derive_instance_status(self, record: IndustryInstanceRecord) -> str:

        if _string(record.status) == "retired" or _string(record.lifecycle_status) == "retired":

            return "retired"

        statuses = [status for status in self._collect_instance_goal_statuses(record) if status]

        if not statuses and self._instance_has_live_operation_surface(record):

            return "active"

        if not statuses:

            return record.status

        if any(status == "blocked" for status in statuses):

            return "blocked"

        if all(status in {"completed", "archived"} for status in statuses):

            if self._instance_has_live_operation_surface(record):

                return "active"

            return "completed"

        if any(status in {"active", "paused"} for status in statuses):

            return "active"

        if any(status == "draft" for status in statuses):

            return "draft"

        return record.status



    def _sync_strategy_memory_for_instance(

        self,

        record: IndustryInstanceRecord,

    ) -> None:

        if self._strategy_memory_service is None:

            return

        if _string(record.status) == "retired":

            self._retire_strategy_memory(record)

            return

        profile = IndustryProfile.model_validate(

            record.profile_payload or {"industry": record.label},

        )

        team = self._materialize_team_blueprint(record)

        execution_core_identity = self._materialize_execution_core_identity(

            record,

            profile=profile,

            team=team,

        )

        self._sync_strategy_memory(

            record,

            profile=profile,

            team=team,

            execution_core_identity=execution_core_identity,

        )





