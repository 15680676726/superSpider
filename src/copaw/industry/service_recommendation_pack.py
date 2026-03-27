# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_context import *  # noqa: F401,F403
from .service_recommendation_search import *  # noqa: F401,F403


def _role_display_label(role: IndustryRoleBlueprint) -> str:
    return role.role_name.strip() or role.name.strip() or role.role_id.strip() or role.agent_id.strip()


def _collect_goal_context_by_agent(draft: IndustryDraftPlan) -> dict[str, list[str]]:
    context_by_agent_id: dict[str, list[str]] = {}
    for goal in draft.goals:
        context = context_by_agent_id.setdefault(goal.owner_agent_id, [])
        context.extend(
            [
                goal.title,
                goal.summary,
                *list(goal.plan_steps or []),
            ]
        )
    return context_by_agent_id


def _enrich_draft_role_capability_families(
    *,
    profile: IndustryProfile,
    draft: IndustryDraftPlan,
) -> IndustryDraftPlan:
    goal_context_by_agent = _collect_goal_context_by_agent(draft)
    changed = False
    roles: list[IndustryRoleBlueprint] = []
    for role in draft.team.agents:
        role_goal_context = goal_context_by_agent.get(role.agent_id, [])
        families = list(role.preferred_capability_families or [])
        inferred_families = _role_capability_family_ids(
            profile=profile,
            role=role,
            goal_context=role_goal_context,
        )
        if is_execution_core_role_id(role.role_id):
            families = _unique_strings(inferred_families, families)
        else:
            families = _unique_strings(families, inferred_families)
        if not families and is_execution_core_role_id(role.role_id):
            families = ["workflow"]
        refined_role = _refine_generic_role_positioning(
            profile=profile,
            role=role,
            goal_context=role_goal_context,
            family_ids=families,
        )
        if refined_role is not role:
            changed = True
            role = refined_role
        expanded_families = _expand_role_capability_family_ids(
            role=role,
            goal_context=role_goal_context,
            family_ids=families,
        )
        if expanded_families != list(role.preferred_capability_families or []):
            changed = True
            role = role.model_copy(
                update={
                    "preferred_capability_families": expanded_families,
                },
            )
        roles.append(role)
    if not changed:
        return draft
    return draft.model_copy(
        update={
            "team": draft.team.model_copy(update={"agents": roles}),
        },
    )


def _recommendation_item_key(item: IndustryCapabilityRecommendation) -> str:
    return (
        _string(item.source_url)
        or _string(item.template_id)
        or _string(item.recommendation_id)
        or ""
    ).lower()


def _recommendation_target_agent_ids(
    item: IndustryCapabilityRecommendation,
    target_roles: list[IndustryRoleBlueprint],
) -> list[str]:
    direct_targets = _unique_strings(list(item.target_agent_ids or []))
    if direct_targets:
        return direct_targets
    role_targets = set(item.suggested_role_ids or [])
    if not role_targets:
        return []
    return [
        role.agent_id
        for role in target_roles
        if role.agent_id and role.role_id in role_targets
    ]


def _decorate_recommendation_item(
    item: IndustryCapabilityRecommendation,
    target_roles: list[IndustryRoleBlueprint],
) -> IndustryCapabilityRecommendation:
    target_agent_ids = _recommendation_target_agent_ids(item, target_roles)
    resolved_role_ids = [
        role.role_id
        for role in target_roles
        if role.agent_id and role.agent_id in target_agent_ids and role.role_id
    ]
    suggested_role_ids = _unique_strings(item.suggested_role_ids, resolved_role_ids)
    target_role_set = set(suggested_role_ids)
    if item.template_id in {"browser-local", "desktop-windows"} or item.install_kind == "builtin-runtime":
        recommendation_group = "system-baseline"
        assignment_scope = "system"
    elif target_role_set == {EXECUTION_CORE_ROLE_ID}:
        recommendation_group = "execution-core"
        assignment_scope = "agent"
    elif len(target_agent_ids) > 1 or len(target_role_set) > 1:
        recommendation_group = "shared"
        assignment_scope = "shared"
    else:
        recommendation_group = "role-specific"
        assignment_scope = "agent"
    return item.model_copy(
        update={
            "target_agent_ids": target_agent_ids,
            "suggested_role_ids": suggested_role_ids,
            "recommendation_group": recommendation_group,
            "assignment_scope": assignment_scope,
            "shared_reuse": assignment_scope != "agent",
        },
    )


def _recommendation_exceeds_family_budget(
    item: IndustryCapabilityRecommendation,
    family_counts: dict[str, int],
) -> bool:
    families = _unique_strings(item.capability_families)
    for family_id in families:
        limit = _RECOMMENDATION_FAMILY_BUDGETS.get(family_id, 2)
        if family_counts.get(family_id, 0) >= limit:
            return True
    return False


def _consume_recommendation_family_budget(
    item: IndustryCapabilityRecommendation,
    family_counts: dict[str, int],
) -> None:
    for family_id in _unique_strings(item.capability_families):
        family_counts[family_id] = family_counts.get(family_id, 0) + 1


def _recommendation_sort_key(item: IndustryCapabilityRecommendation) -> tuple[object, ...]:
    source_priority = {
        "install-template": 0,
        "mcp-registry": 1,
        "skillhub-curated": 2,
        "hub-search": 3,
    }
    target_span = max(
        1,
        len(_unique_strings(item.target_agent_ids)),
        len(_unique_strings(item.suggested_role_ids)),
    )
    return (
        item.installed,
        item.review_required,
        _RECOMMENDATION_GROUP_PRIORITY.get(item.recommendation_group, 9),
        source_priority.get(str(item.source_kind or ""), 9),
        -target_span,
        str(item.title or "").lower(),
    )


def _standardized_recommendation_target(
    target_roles: list[IndustryRoleBlueprint],
) -> int:
    count = max(1, len(target_roles))
    if count <= 2:
        return 4
    if count <= 4:
        return 3
    return 2


def _standardize_recommendation_items(
    items: list[IndustryCapabilityRecommendation],
    target_roles: list[IndustryRoleBlueprint],
) -> list[IndustryCapabilityRecommendation]:
    if not items:
        return []
    decorated = [
        _decorate_recommendation_item(item, target_roles)
        for item in items
    ]
    deduped: list[IndustryCapabilityRecommendation] = []
    seen_keys: set[str] = set()
    for item in sorted(decorated, key=_recommendation_sort_key):
        key = _recommendation_item_key(item)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(item)
    role_quota = _standardized_recommendation_target(target_roles)
    max_total = max(
        6,
        min(_STANDARD_RECOMMENDATION_MAX_TOTAL, max(1, len(target_roles)) * role_quota + 2),
    )
    selected: list[IndustryCapabilityRecommendation] = []
    selected_keys: set[str] = set()
    role_counts: dict[str, int] = {
        role.agent_id: 0 for role in target_roles if role.agent_id
    }
    family_counts: dict[str, int] = {}

    def try_select(
        item: IndustryCapabilityRecommendation,
        *,
        respect_role_quota: bool,
    ) -> bool:
        if len(selected) >= max_total:
            return False
        key = _recommendation_item_key(item)
        if not key or key in selected_keys:
            return False
        if _recommendation_exceeds_family_budget(item, family_counts):
            return False
        targets = _recommendation_target_agent_ids(item, target_roles)
        if respect_role_quota and targets:
            if not any(role_counts.get(agent_id, 0) < role_quota for agent_id in targets):
                return False
        selected.append(item)
        selected_keys.add(key)
        _consume_recommendation_family_budget(item, family_counts)
        if item.recommendation_group in {"execution-core", "role-specific"}:
            for agent_id in targets:
                role_counts[agent_id] = role_counts.get(agent_id, 0) + 1
        return True

    for group in ("system-baseline", "execution-core", "shared", "role-specific"):
        for item in deduped:
            if item.recommendation_group != group:
                continue
            try_select(
                item,
                respect_role_quota=group in {"execution-core", "role-specific"},
            )
    for item in deduped:
        if len(selected) >= max_total:
            break
        try_select(
            item,
            respect_role_quota=item.recommendation_group in {"execution-core", "role-specific"},
        )
    return selected[:max_total]


def _build_recommendation_sections(
    items: list[IndustryCapabilityRecommendation],
    target_roles: list[IndustryRoleBlueprint],
) -> list[IndustryCapabilityRecommendationSection]:
    if not items:
        return []
    sections: list[IndustryCapabilityRecommendationSection] = []
    core_role = next(
        (role for role in target_roles if is_execution_core_role_id(role.role_id)),
        None,
    )

    def append_section(
        *,
        section_id: str,
        section_kind: str,
        title: str,
        summary: str,
        section_items: list[IndustryCapabilityRecommendation],
        role: IndustryRoleBlueprint | None = None,
    ) -> None:
        if not section_items:
            return
        sections.append(
            IndustryCapabilityRecommendationSection(
                section_id=section_id,
                section_kind=section_kind,
                title=title,
                summary=summary,
                role_id=role.role_id if role is not None else None,
                role_name=_role_display_label(role) if role is not None else None,
                target_agent_id=role.agent_id if role is not None else None,
                items=section_items,
            ),
        )

    system_items = [item for item in items if item.recommendation_group == "system-baseline"]
    execution_core_items = [
        item for item in items if item.recommendation_group == "execution-core"
    ]
    shared_items = [item for item in items if item.recommendation_group == "shared"]
    role_specific_items = [
        item for item in items if item.recommendation_group == "role-specific"
    ]
    append_section(
        section_id="system-baseline",
        section_kind="system-baseline",
        title="system-baseline",
        summary="Shared runtime and baseline capability prerequisites.",
        section_items=system_items,
    )
    append_section(
        section_id="execution-core",
        section_kind="execution-core",
        title="execution-core",
        summary="Recommendations bound to the team control core.",
        section_items=execution_core_items,
        role=core_role,
    )
    append_section(
        section_id="shared",
        section_kind="shared",
        title="shared",
        summary="Reusable skills shared across multiple roles.",
        section_items=shared_items,
    )
    for role in target_roles:
        if not role.agent_id or is_execution_core_role_id(role.role_id):
            continue
        role_items = [
            item
            for item in role_specific_items
            if role.agent_id in _recommendation_target_agent_ids(item, target_roles)
        ]
        append_section(
            section_id=f"role:{role.role_id}",
            section_kind="role",
            title=_role_display_label(role),
            summary=f"Role-specific recommendations for {_role_display_label(role)}.",
            section_items=role_items,
            role=role,
        )
    return sections


def _build_desktop_match_signals(
    *,
    role: IndustryRoleBlueprint,
    goal_context: list[str],
    client_key: str,
    template_tags: list[str],
) -> list[str]:
    target_capability = f"mcp:{client_key}".lower()
    explicit_external_capabilities = [
        capability.strip()
        for capability in role.allowed_capabilities
        if capability.strip().lower().startswith(("mcp:", "skill:"))
    ]
    signals: list[str] = []
    explicit_match = next(
        (
            capability
            for capability in explicit_external_capabilities
            if capability.strip().lower() == target_capability
        ),
        None,
    )
    if explicit_match is not None:
        signals.append(f"显式能力 {explicit_match}")

    template_tokens = {
        token
        for value in [client_key, *list(template_tags or [])]
        for token in _tokenize_capability_hint(value)
    }
    overlapping_external = [
        capability
        for capability in explicit_external_capabilities
        if capability.strip().lower() != target_capability
        and (_tokenize_capability_hint(capability) & template_tokens)
    ]
    if overlapping_external:
        signals.append(
            "外部能力线索 " + ", ".join(overlapping_external[:2])
        )

    search_values = [
        role.name,
        role.role_name,
        role.role_summary,
        role.mission,
        *list(role.environment_constraints or []),
        *list(role.evidence_expectations or []),
        *list(goal_context or []),
    ]
    blob = _search_blob(search_values)
    direct_matches = _match_keyword_labels(blob, _DESKTOP_DIRECT_TEXT_HINTS)
    if direct_matches:
        signals.append("角色语义 " + " / ".join(direct_matches[:3]))
        return _unique_strings(signals)

    surface_matches = _match_keyword_labels(blob, _DESKTOP_SURFACE_HINTS)
    action_matches = _match_keyword_labels(blob, _DESKTOP_ACTION_HINTS)
    if surface_matches and action_matches:
        compound = [*surface_matches[:2], *action_matches[:2]]
        signals.append("执行线索 " + " / ".join(compound[:3]))
    return _unique_strings(signals)


def _build_browser_match_signals(
    *,
    role: IndustryRoleBlueprint,
    goal_context: list[str],
) -> list[str]:
    search_values = [
        role.name,
        role.role_name,
        role.role_summary,
        role.mission,
        *list(goal_context or []),
    ]
    blob = _search_blob(search_values)
    direct_matches = _match_keyword_labels(blob, _BROWSER_DIRECT_TEXT_HINTS)
    action_matches = _match_keyword_labels(blob, _BROWSER_ACTION_HINTS)
    signals: list[str] = []
    if direct_matches:
        signals.append("浏览器语义 " + " / ".join(direct_matches[:3]))
    if direct_matches and action_matches:
        signals.append("浏览器流程 " + " / ".join(action_matches[:3]))
    return _unique_strings(signals)


def _install_template_default_ref(
    template: object,
    *,
    browser_runtime_service: BrowserRuntimeService | None = None,
) -> str:
    default_client_key = str(getattr(template, "default_client_key", "") or "").strip()
    if default_client_key:
        return default_client_key
    template_id = str(getattr(template, "id", "") or "").strip()
    if template_id == "browser-local":
        if browser_runtime_service is not None:
            default_profile = browser_runtime_service.get_default_profile()
            if default_profile is not None and default_profile.profile_id:
                return default_profile.profile_id
        support = getattr(template, "support", {}) or {}
        profiles = list(support.get("profiles") or [])
        for profile in profiles:
            if bool(profile.get("is_default")):
                profile_id = str(profile.get("profile_id") or "").strip()
                if profile_id:
                    return profile_id
        return "browser-local-default"
    return template_id


def _install_template_capability_ids(template: object) -> list[str]:
    manifest = getattr(template, "manifest", None)
    capability_ids = list(getattr(manifest, "capability_ids", []) or [])
    default_capability_id = str(getattr(template, "default_capability_id", "") or "").strip()
    default_client_key = str(getattr(template, "default_client_key", "") or "").strip()
    if default_capability_id:
        capability_ids.append(default_capability_id)
    if default_client_key:
        capability_ids.append(f"mcp:{default_client_key}")
    return _unique_strings(capability_ids)


def _install_template_recommendation_satisfied(
    template: object,
    *,
    browser_runtime_service: BrowserRuntimeService | None = None,
) -> bool:
    template_id = str(getattr(template, "id", "") or "").strip()
    if template_id == "browser-local":
        if browser_runtime_service is not None:
            return bool(getattr(template, "enabled", False)) and (
                browser_runtime_service.get_default_profile() is not None
            )
        support = getattr(template, "support", {}) or {}
        profiles = list(support.get("profiles") or [])
        has_default_profile = any(bool(profile.get("is_default")) for profile in profiles)
        return bool(getattr(template, "enabled", False)) and has_default_profile
    return bool(getattr(template, "installed", False))


def _install_template_gap_notes(
    template: object,
    *,
    browser_runtime_service: BrowserRuntimeService | None = None,
) -> list[str]:
    template_id = str(getattr(template, "id", "") or "").strip()
    if template_id != "browser-local":
        return []
    notes: list[str] = []
    if not bool(getattr(template, "enabled", False)):
        notes.append("当前浏览器运行时 capability 尚未启用。")
    has_default_profile = False
    if browser_runtime_service is not None:
        has_default_profile = browser_runtime_service.get_default_profile() is not None
    else:
        support = getattr(template, "support", {}) or {}
        profiles = list(support.get("profiles") or [])
        has_default_profile = any(bool(profile.get("is_default")) for profile in profiles)
    if not has_default_profile:
        notes.append("当前还没有默认浏览器 profile，bootstrap 时会自动创建。")
    return notes


def _build_recommendation_reason_notes(
    matches: list[tuple[IndustryRoleBlueprint, list[str]]],
) -> list[str]:
    notes: list[str] = []
    for role, signals in matches:
        if not signals:
            continue
        notes.append(
            f"角色匹配：{_role_display_label(role)} -> {'；'.join(signals[:2])}"
        )
    return _unique_strings(notes)


def _normalize_role_blueprint(role: IndustryRoleBlueprint) -> IndustryRoleBlueprint:
    role_id = normalize_industry_role_id(role.role_id) or role.role_id
    role_summary = role.role_summary
    mission = role.mission
    employment_mode = "temporary" if role.employment_mode == "temporary" else "career"
    reports_to = (
        EXECUTION_CORE_AGENT_ID
        if is_execution_core_reference(role.reports_to)
        else role.reports_to
    )
    if is_execution_core_role_id(role_id):
        return role.model_copy(
            update={
                "role_id": EXECUTION_CORE_ROLE_ID,
                "agent_id": EXECUTION_CORE_AGENT_ID,
                "goal_kind": EXECUTION_CORE_ROLE_ID,
                "name": _EXECUTION_CORE_NAME,
                "role_name": _EXECUTION_CORE_NAME,
                "role_summary": role_summary or _EXECUTION_CORE_SUMMARY,
                "mission": mission or _EXECUTION_CORE_MISSION,
                "agent_class": "business",
                "employment_mode": "career",
                "reports_to": None,
            },
        )
    return role.model_copy(
        update={
            "role_id": role_id,
            "role_summary": role_summary,
            "mission": mission,
            "employment_mode": employment_mode,
            "reports_to": reports_to,
        },
    )


def _normalize_execution_core_schedule_title(value: object | None) -> str:
    return _string(value) or ""


def _normalize_execution_core_schedule_summary(value: object | None) -> str:
    return _string(value) or "围绕团队执行中枢闭环的定期复盘。"


def _build_execution_core_thinking_axes(profile: IndustryProfile) -> list[str]:
    return _unique_strings(
        f"行业聚焦：{profile.industry}" if _string(profile.industry) else None,
        (
            f"细分行业视角：{profile.sub_industry}"
            if _string(profile.sub_industry)
            else None
        ),
        f"产品聚焦：{profile.product}" if _string(profile.product) else None,
        (
            f"商业模式：{profile.business_model}"
            if _string(profile.business_model)
            else None
        ),
        f"区域聚焦：{profile.region}" if _string(profile.region) else None,
        (
            f"客户视角：{', '.join(profile.target_customers[:4])}"
            if profile.target_customers
            else None
        ),
        (
            f"渠道视角：{', '.join(profile.channels[:4])}"
            if profile.channels
            else None
        ),
        (
            f"经营目标：{', '.join(profile.goals[:4])}"
            if profile.goals
            else None
        ),
        (
            f"硬约束：{', '.join(profile.constraints[:4])}"
            if profile.constraints
            else None
        ),
        (
            "规划方式：沿用操作方已有经验与要求"
            if profile.experience_mode == "operator-guided"
            else "规划方式：系统主导补齐完整执行闭环"
        ),
        (
            f"既有经验/SOP：{profile.experience_notes}"
            if _string(profile.experience_notes)
            else None
        ),
        *(
            f"必须纳入：{item}"
            for item in list(profile.operator_requirements or [])[:4]
        ),
    )


def _build_execution_core_delegation_policy() -> list[str]:
    return _unique_strings(
        "主脑只负责理解目标、拆解计划、分派、监督和复盘，不直接吞掉叶子执行。",
        "研究岗位负责看世界、补信号和证据，专业执行位负责动手交付，主脑负责统一编排与验收。",
        "每个执行动作都必须落到明确执行位；缺岗位时先暴露缺口或发起补位，而不是让主脑亲自下场。",
        "当 operator 只是追问状态、讨论方案或纠偏时，优先把它当作讨论/规划更新，而不是立刻物化成新执行任务。",
    )


def _build_execution_core_direct_execution_policy() -> list[str]:
    return _unique_strings(
        "主脑不直接使用浏览器、桌面、文件编辑等叶子执行能力。",
        "没有合适执行位时，先补位、改派或请求确认，不让主脑兜底变成执行员。",
    )


def _build_operator_strategy_constraints(profile: IndustryProfile) -> list[str]:
    constraints: list[str] = []
    if profile.experience_mode == "operator-guided":
        constraints.append("优先沿用操作方已提供的经验、SOP 与执行要求，不要无故改写关键流程。")
    else:
        constraints.append("当前行业由系统主导规划并补齐完整执行闭环，不等待操作方逐步补流程。")
    if _string(profile.experience_notes):
        constraints.append(f"既有经验/SOP：{profile.experience_notes}")
    constraints.extend(
        f"必须纳入：{item}"
        for item in list(profile.operator_requirements or [])[:6]
    )
    return constraints

__all__ = [name for name in globals() if not name.startswith("__")]
