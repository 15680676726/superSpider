# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable

from .identity import (
    EXECUTION_CORE_AGENT_ID,
    EXECUTION_CORE_LEGACY_NAMES,
    EXECUTION_CORE_NAME,
    EXECUTION_CORE_ROLE_ID,
    is_execution_core_role_id,
    normalize_industry_role_id,
)
from .models import (
    IndustryDraftGoal,
    IndustryDraftPlan,
    IndustryDraftSchedule,
    IndustryGoalSeed,
    IndustryPreviewRequest,
    IndustryProfile,
    IndustryRoleBlueprint,
    IndustryScheduleSeed,
    IndustryTeamBlueprint,
    normalize_industry_team_topology,
)
from .prompting import (
    build_industry_execution_prompt,
    infer_industry_task_mode,
)

_EXECUTION_CORE_ALLOWED_CAPABILITIES = [
    "tool:edit_file",
    "tool:execute_shell_command",
    "tool:get_current_time",
    "tool:read_file",
    "tool:write_file",
]

_RESEARCHER_ALLOWED_CAPABILITIES = [
    "tool:browser_use",
    "tool:edit_file",
    "tool:execute_shell_command",
    "tool:get_current_time",
    "tool:read_file",
    "tool:write_file",
]

_BUSINESS_ALLOWED_CAPABILITIES = [
    "tool:browser_use",
    "tool:edit_file",
    "tool:execute_shell_command",
    "tool:get_current_time",
    "tool:read_file",
    "tool:write_file",
]

_ROLE_BASELINE_CAPABILITIES = {
    EXECUTION_CORE_ROLE_ID: [
    "system:dispatch_query",
    "system:delegate_task",
    "system:apply_role",
    "system:discover_capabilities",
    ],
    "researcher": [
        "system:dispatch_query",
        "system:replay_routine",
        "system:run_fixed_sop",
    ],
}

_DEFAULT_BASELINE_CAPABILITIES = [
    "system:dispatch_query",
    "system:replay_routine",
    "system:run_fixed_sop",
]
_EXPLICIT_EXTERNAL_CAPABILITY_PREFIXES = ("mcp:", "skill:")
_RESEARCH_SIGNAL_KEYWORDS = (
    "research",
    "researcher",
    "signal",
    "signals",
    "evidence",
    "trend",
    "market",
    "competitor",
    "competitors",
    "platform",
    "sourcing",
    "selection",
    "pricing",
    "customer service",
    "content",
    "campaign",
    "ads",
    "seo",
    "insight",
    "industry",
    "analysis",
)
_RESEARCH_NEGATION_KEYWORDS = (
    "no research",
    "no researcher",
    "without research",
    "no signal loop",
)
_MONITORING_BRIEF_KEYWORDS = (
    "monitoring brief",
    "monitoring-brief",
    "监测简报",
    "监控简报",
)

_EXECUTION_CORE_ENVIRONMENT = [
    "Own the main control thread, delegation queue, and governed operating loop.",
    "Coordinate reports, backlog routing, and assignment supervision.",
    "Avoid direct leaf execution; dispatch execution to specialist agents instead.",
    "Use shell/browser/desktop only through governed delegation and evidence capture.",
]

_RESEARCHER_ENVIRONMENT = [
    "Continuously observe market, customer, platform, and competitor signals.",
    "Collect durable evidence for the main-brain review loop.",
    "Operate as a long-running support role rather than a separate strategy center.",
    "Use browser and file tools to gather signals with evidence.",
]

_BUSINESS_ENVIRONMENT = [
    "Execute durable lane work under main-brain supervision.",
    "Produce evidence, summaries, and report-ready outputs.",
    "Reuse mounted environments instead of recovering everything through prompts.",
    "Escalate blockers and risky actions back to the main brain.",
]

_EXECUTION_CORE_NAME = EXECUTION_CORE_NAME
_EXECUTION_CORE_SUMMARY = (
    f"{EXECUTION_CORE_NAME} is the main-brain control role for planning, delegation, "
    "supervision, and governed writeback."
)
_EXECUTION_CORE_MISSION = (
    "Maintain the long-running operating loop, keep strategy aligned with execution, "
    "and route work to the correct specialist or support role."
)

def _build_actor_key(
    *,
    slug: str,
    role_id: str,
    explicit: str | None = None,
) -> str:
    normalized = _slugify_identifier(
        explicit or role_id,
        fallback=role_id or "role",
    )
    return f"industry:{slug}:{normalized}"


def _build_actor_fingerprint(
    *,
    slug: str,
    role_id: str,
    role_name: str,
    goal_kind: str,
    reports_to: str | None,
    activation_mode: str,
    employment_mode: str,
    agent_class: str,
) -> str:
    payload = {
        "slug": slug,
        "role_id": role_id,
        "role_name": role_name.strip().lower(),
        "goal_kind": goal_kind.strip().lower(),
        "reports_to": (reports_to or "").strip().lower(),
        "activation_mode": activation_mode.strip().lower(),
        "employment_mode": employment_mode.strip().lower(),
        "agent_class": agent_class.strip().lower(),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def resolve_role_capability_baseline(
    role: IndustryRoleBlueprint | None,
    role_id: str | None = None,
) -> list[str]:
    resolved_id = normalize_industry_role_id(role_id)
    if resolved_id is None and role is not None:
        resolved_id = normalize_industry_role_id(
            role.role_id,
        ) or normalize_industry_role_id(role.goal_kind)
    baseline = _ROLE_BASELINE_CAPABILITIES.get(
        resolved_id or "",
        _DEFAULT_BASELINE_CAPABILITIES,
    )
    return list(baseline)


def normalize_industry_profile(
    request: IndustryPreviewRequest | IndustryProfile,
) -> IndustryProfile:
    if isinstance(request, IndustryProfile):
        return request
    return request.to_profile()


def industry_slug(profile: IndustryProfile) -> str:
    raw = profile.primary_label().strip().lower()
    ascii_raw = raw.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_raw).strip("-")
    if slug:
        return slug
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
    return f"industry-{digest}"


def canonicalize_industry_draft(
    profile: IndustryProfile,
    draft: IndustryDraftPlan,
    *,
    owner_scope: str,
) -> IndustryDraftPlan:
    del owner_scope
    slug = industry_slug(profile)
    raw_roles = list(draft.team.agents)
    execution_core_source = _pick_system_role(
        raw_roles,
        expected=EXECUTION_CORE_ROLE_ID,
    )
    researcher_source = _pick_system_role(raw_roles, expected="researcher")
    if execution_core_source is None:
        raise ValueError("Industry draft must include an execution core root role.")

    execution_core = _canonicalize_execution_core_role(
        execution_core_source,
        profile=profile,
        slug=slug,
    )
    if researcher_source is None:
        researcher_source = _build_default_researcher_source(profile)
    support_roles: list[IndustryRoleBlueprint] = []
    seen_role_ids = {execution_core.role_id}
    seen_agent_ids = {execution_core.agent_id}
    alias_to_agent_id = _role_aliases(execution_core)
    alias_to_agent_id.update(
        _source_role_aliases(
            execution_core_source,
            resolved_agent_id=execution_core.agent_id,
        ),
    )
    if researcher_source is not None:
        researcher = _canonicalize_researcher_role(
            researcher_source,
            profile=profile,
            slug=slug,
            execution_core_agent_id=execution_core.agent_id,
        )
        support_roles.append(researcher)
        seen_role_ids.add(researcher.role_id)
        seen_agent_ids.add(researcher.agent_id)
        alias_to_agent_id.update(_role_aliases(researcher))
        alias_to_agent_id.update(
            _source_role_aliases(
                researcher_source,
                resolved_agent_id=researcher.agent_id,
            ),
        )

    business_roles: list[IndustryRoleBlueprint] = []
    for raw_role in raw_roles:
        if _is_system_role(raw_role, expected=EXECUTION_CORE_ROLE_ID) or _is_system_role(
            raw_role,
            expected="researcher",
        ):
            continue
        role = _canonicalize_business_role(
            raw_role,
            profile=profile,
            slug=slug,
            execution_core_agent_id=execution_core.agent_id,
            seen_role_ids=seen_role_ids,
            seen_agent_ids=seen_agent_ids,
            alias_to_agent_id=alias_to_agent_id,
        )
        business_roles.append(role)
        alias_to_agent_id.update(_role_aliases(role))
        alias_to_agent_id.update(
            _source_role_aliases(
                raw_role,
                resolved_agent_id=role.agent_id,
            ),
        )
    if not business_roles:
        raise ValueError("Industry draft must include at least one business role.")

    roles = [execution_core, *support_roles, *business_roles]
    topology = _resolve_team_topology(
        draft.team.topology,
        roles=roles,
    )
    team = IndustryTeamBlueprint(
        team_id=f"industry-v1-{slug}",
        label=draft.team.label.strip() or f"{profile.primary_label()} Spider Mesh Team",
        summary=(
            draft.team.summary.strip()
            or f"{profile.primary_label()} Spider Mesh team for {profile.industry} operations."
        ),
        topology=topology,
        agents=roles,
    )
    goals = _canonicalize_goals(
        profile,
        draft.goals,
        team_id=team.team_id,
        roles=roles,
        alias_to_agent_id=alias_to_agent_id,
    )
    schedules = _canonicalize_schedules(
        profile,
        draft.schedules,
        roles=roles,
        alias_to_agent_id=alias_to_agent_id,
        team_id=team.team_id,
        goals=goals,
    )
    generation_summary = draft.generation_summary
    if not generation_summary or not generation_summary.strip():
        generation_summary = (
            f"Compiled {profile.primary_label()} into a {topology or 'standard'} Spider Mesh team "
            f"with {len(roles) - 1} durable execution roles."
        )
    return IndustryDraftPlan(
        team=team,
        goals=goals,
        schedules=schedules,
        generation_summary=generation_summary,
    )



def _goal_kickoff_stage(role: IndustryRoleBlueprint) -> str:
    return "learning" if normalize_industry_role_id(role.role_id) == "researcher" else "execution"


def _schedule_kickoff_stage(role: IndustryRoleBlueprint) -> str:
    del role
    return "execution"

def compile_industry_goal_seeds(
    profile: IndustryProfile,
    *,
    draft: IndustryDraftPlan,
    owner_scope: str,
) -> list[IndustryGoalSeed]:
    roles_by_agent_id = {role.agent_id: role for role in draft.team.agents}
    return [
        IndustryGoalSeed(
            goal_id=goal.goal_id,
            kind=goal.kind,
            owner_agent_id=goal.owner_agent_id,
            title=goal.title,
            summary=goal.summary,
            plan_steps=list(goal.plan_steps),
            role=roles_by_agent_id[goal.owner_agent_id],
            compiler_context={
                "owner_scope": owner_scope,
                "owner_agent_id": goal.owner_agent_id,
                "industry_instance_id": draft.team.team_id,
                "industry_label": draft.team.label,
                "industry_summary": draft.team.summary,
                "industry_role_id": roles_by_agent_id[goal.owner_agent_id].role_id,
                "industry_role_name": roles_by_agent_id[goal.owner_agent_id].role_name,
                "role_name": roles_by_agent_id[goal.owner_agent_id].role_name,
                "role_summary": roles_by_agent_id[goal.owner_agent_id].role_summary,
                "mission": roles_by_agent_id[goal.owner_agent_id].mission,
                "environment_constraints": list(
                    roles_by_agent_id[goal.owner_agent_id].environment_constraints
                ),
                "evidence_expectations": list(
                    roles_by_agent_id[goal.owner_agent_id].evidence_expectations
                ),
                "goal_kind": goal.kind,
                "task_mode": infer_industry_task_mode(
                    role_id=roles_by_agent_id[goal.owner_agent_id].role_id,
                    goal_kind=goal.kind,
                    source="goal",
                ),
                "session_kind": "industry-agent-chat",
                "kickoff_stage": _goal_kickoff_stage(
                    roles_by_agent_id[goal.owner_agent_id]
                ),
            },
        )
        for goal in draft.goals
        if goal.owner_agent_id in roles_by_agent_id
    ]


def build_goal_dispatch_context(seed: IndustryGoalSeed) -> dict[str, object]:
    return {
        "channel": "industry",
        "bootstrap_kind": "industry-v1",
        "trigger_source": "bootstrap:industry",
        "trigger_actor": "industry-bootstrap",
        "trigger_reason": "Initial industry bootstrap dispatch.",
        **seed.compiler_context,
    }


def compile_industry_schedule_seeds(
    profile: IndustryProfile,
    *,
    draft: IndustryDraftPlan,
    owner_scope: str,
) -> list[IndustryScheduleSeed]:
    roles_by_agent_id = {role.agent_id: role for role in draft.team.agents}
    goals_by_agent_id: dict[str, IndustryDraftGoal] = {}
    for goal in draft.goals:
        goals_by_agent_id.setdefault(goal.owner_agent_id, goal)
    seeds: list[IndustryScheduleSeed] = []
    for schedule in draft.schedules:
        role = roles_by_agent_id.get(schedule.owner_agent_id)
        if role is None:
            continue
        goal = goals_by_agent_id.get(schedule.owner_agent_id)
        task_mode = infer_industry_task_mode(
            role_id=role.role_id,
            goal_kind=goal.kind if goal is not None else role.goal_kind,
            source="schedule",
        )
        kickoff_stage = _schedule_kickoff_stage(role)
        session_id = _default_schedule_session_id(
            team_id=draft.team.team_id,
            role=role,
        )
        prompt = _build_schedule_prompt(
            profile,
            role=role,
            goal=goal,
            team_label=draft.team.label,
            cadence_summary=schedule.summary,
            task_mode=task_mode,
        )
        research_schedule_metadata = _build_research_schedule_metadata(
            schedule=schedule,
            role=role,
            goal=goal,
        )
        request_payload = {
            "channel": "console",
            "session_id": session_id,
            "user_id": owner_scope,
            "agent_id": role.agent_id,
            "owner_scope": owner_scope,
            "industry_instance_id": draft.team.team_id,
            "industry_role_id": role.role_id,
            "industry_role_name": role.role_name,
            "industry_label": draft.team.label,
            "task_mode": task_mode,
            "kickoff_stage": kickoff_stage,
            "session_kind": (
                "industry-control-thread"
                if is_execution_core_role_id(role.role_id)
                else "industry-agent-chat"
            ),
            "control_thread_id": (
                session_id if is_execution_core_role_id(role.role_id) else None
            ),
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                },
            ],
        }
        request_payload.update(research_schedule_metadata)
        seeds.append(
            IndustryScheduleSeed(
                schedule_id=schedule.schedule_id,
                title=schedule.title,
                summary=schedule.summary,
                cron=schedule.cron,
                timezone=schedule.timezone,
                owner_agent_id=schedule.owner_agent_id,
                dispatch_channel="console",
                dispatch_user_id=owner_scope,
                dispatch_session_id=session_id,
                dispatch_mode=schedule.dispatch_mode,
                request_payload=request_payload,
                metadata={
                    "bootstrap_kind": "industry-v1",
                    "industry_instance_id": draft.team.team_id,
                    "industry_role_id": role.role_id,
                    "owner_agent_id": role.agent_id,
                    "goal_kind": goal.kind if goal is not None else role.goal_kind,
                    "task_mode": task_mode,
                    "kickoff_stage": kickoff_stage,
                    **research_schedule_metadata,
                },
            ),
        )
    return seeds


def _build_research_schedule_metadata(
    *,
    schedule: IndustryDraftSchedule,
    role: IndustryRoleBlueprint,
    goal: IndustryDraftGoal | None,
) -> dict[str, str]:
    if normalize_industry_role_id(role.role_id) != "researcher":
        return {}
    schedule_text = _normalize_search_text(
        [
            schedule.schedule_id,
            schedule.title,
            schedule.summary,
            goal.title if goal is not None else None,
            goal.summary if goal is not None else None,
        ],
    )
    if not _contains_any_keyword(schedule_text, _MONITORING_BRIEF_KEYWORDS):
        return {}
    research_goal = _first_non_empty_text(
        schedule.summary,
        goal.summary if goal is not None else None,
        goal.title if goal is not None else None,
        schedule.title,
    )
    if research_goal is None:
        return {}
    metadata = {
        "research_provider": "baidu-page",
        "research_mode": "monitoring-brief",
        "research_goal": research_goal,
        "owner_agent_id": role.agent_id,
    }
    supervisor_agent_id = _first_non_empty_text(role.reports_to)
    if supervisor_agent_id is not None:
        metadata["supervisor_agent_id"] = supervisor_agent_id
    return metadata


def _pick_system_role(
    roles: list[IndustryRoleBlueprint],
    *,
    expected: str,
) -> IndustryRoleBlueprint | None:
    for role in roles:
        if _is_system_role(role, expected=expected):
            return role
    return None


def _is_system_role(role: IndustryRoleBlueprint, *, expected: str) -> bool:
    return normalize_industry_role_id(role.role_id) == expected


def _canonicalize_execution_core_role(
    role: IndustryRoleBlueprint,
    *,
    profile: IndustryProfile,
    slug: str,
) -> IndustryRoleBlueprint:
    del profile, slug
    role_name = _EXECUTION_CORE_NAME
    role_id = EXECUTION_CORE_ROLE_ID
    actor_key = _build_actor_key(
        slug="global",
        role_id=role_id,
        explicit=role.actor_key,
    )
    return IndustryRoleBlueprint(
        role_id=role_id,
        agent_id=EXECUTION_CORE_AGENT_ID,
        actor_key=actor_key,
        actor_fingerprint=_build_actor_fingerprint(
            slug="global",
            role_id=role_id,
            role_name=role_name,
            goal_kind=EXECUTION_CORE_ROLE_ID,
            reports_to=None,
            activation_mode="persistent",
            employment_mode="career",
            agent_class="business",
        ),
        name=role_name,
        role_name=role_name,
        role_summary=role.role_summary.strip() or _EXECUTION_CORE_SUMMARY,
        mission=role.mission.strip() or _EXECUTION_CORE_MISSION,
        goal_kind=EXECUTION_CORE_ROLE_ID,
        agent_class="business",
        employment_mode="career",
        activation_mode="persistent",
        suspendable=False,
        reports_to=None,
        risk_level="guarded",
        environment_constraints=list(role.environment_constraints or _EXECUTION_CORE_ENVIRONMENT),
        allowed_capabilities=_filter_capabilities(
            role.allowed_capabilities,
            default=_EXECUTION_CORE_ALLOWED_CAPABILITIES,
            required=resolve_role_capability_baseline(role, EXECUTION_CORE_ROLE_ID),
        ),
        preferred_capability_families=list(role.preferred_capability_families or []),
        evidence_expectations=list(
            role.evidence_expectations
            or [
                "Delegation receipts and routing decisions.",
                "Main-brain review summaries and report intake.",
                "Governed operating-cycle updates and supervision evidence.",
            ]
        ),
    )



def _canonicalize_researcher_role(
    role: IndustryRoleBlueprint,
    *,
    profile: IndustryProfile,
    slug: str,
    execution_core_agent_id: str,
) -> IndustryRoleBlueprint:
    label_core = profile.primary_label()
    role_id = "researcher"
    role_name = role.role_name.strip() or "Researcher"
    actor_key = _build_actor_key(
        slug=slug,
        role_id=role_id,
        explicit=role.actor_key,
    )
    return IndustryRoleBlueprint(
        role_id=role_id,
        agent_id=f"industry-researcher-{slug}",
        actor_key=actor_key,
        actor_fingerprint=_build_actor_fingerprint(
            slug=slug,
            role_id=role_id,
            role_name=role_name,
            goal_kind="researcher",
            reports_to=execution_core_agent_id,
            activation_mode="persistent",
            employment_mode="career",
            agent_class="system",
        ),
        name=role.name.strip() or f"{label_core} Researcher",
        role_name=role_name,
        role_summary=(
            role.role_summary.strip()
            or "Research support role that executes explicit research briefs for the main brain."
        ),
        mission=(
            role.mission.strip()
            or f"Feed {_EXECUTION_CORE_NAME} with evidence-backed findings from explicit monitoring briefs and follow-up research."
        ),
        goal_kind="researcher",
        agent_class="system",
        employment_mode="career",
        activation_mode="persistent",
        suspendable=False,
        reports_to=execution_core_agent_id,
        risk_level="guarded",
        environment_constraints=list(
            role.environment_constraints or _RESEARCHER_ENVIRONMENT,
        ),
        allowed_capabilities=_filter_capabilities(
            role.allowed_capabilities,
            default=_RESEARCHER_ALLOWED_CAPABILITIES,
            required=resolve_role_capability_baseline(role, "researcher"),
        ),
        preferred_capability_families=list(
            role.preferred_capability_families or ["research"]
        ),
        evidence_expectations=list(
            role.evidence_expectations
            or [
                "Evidence-backed research summaries tied to the active brief.",
                "Evidence links for the monitored platform, customer, market, or source changes.",
                "Research or monitoring brief reports routed back to the main brain.",
            ]
        ),
    )



def _canonicalize_business_role(
    role: IndustryRoleBlueprint,
    *,
    profile: IndustryProfile,
    slug: str,
    execution_core_agent_id: str,
    seen_role_ids: set[str],
    seen_agent_ids: set[str],
    alias_to_agent_id: dict[str, str],
) -> IndustryRoleBlueprint:
    label_core = profile.primary_label()
    role_name = role.role_name.strip() or role.name.strip() or "Specialist"
    role_id = _reserve_identifier(
        _slugify_identifier(
            role.role_id or role.goal_kind or role_name,
            fallback="business-role",
        ),
        seen_role_ids,
    )
    agent_id = _reserve_identifier(
        role.agent_id.strip() if role.agent_id.strip() else f"industry-{role_id}-{slug}",
        seen_agent_ids,
        sanitizer=lambda value: _slugify_identifier(value, fallback=f"industry-{role_id}-{slug}"),
    )
    reports_to = _resolve_agent_reference(
        role.reports_to,
        alias_to_agent_id=alias_to_agent_id,
        fallback=execution_core_agent_id,
    )
    goal_kind = _slugify_identifier(role.goal_kind or role_id, fallback=role_id)
    evidence_expectations = list(role.evidence_expectations)
    if not evidence_expectations:
        evidence_expectations = [
            f"{role_name} execution outputs and deliverables.",
            f"{role_name} evidence and reporting artifacts.",
            f"{role_name} blocker and risk summaries.",
        ]
    employment_mode = (
        "temporary" if role.employment_mode == "temporary" else "career"
    )
    activation_mode = (
        "on-demand" if role.activation_mode == "on-demand" else "persistent"
    )
    actor_key = _build_actor_key(
        slug=slug,
        role_id=role_id,
        explicit=role.actor_key,
    )
    return IndustryRoleBlueprint(
        role_id=role_id,
        agent_id=agent_id,
        actor_key=actor_key,
        actor_fingerprint=_build_actor_fingerprint(
            slug=slug,
            role_id=role_id,
            role_name=role_name,
            goal_kind=goal_kind,
            reports_to=reports_to,
            activation_mode=activation_mode,
            employment_mode=employment_mode,
            agent_class="business",
        ),
        name=role.name.strip() or f"{label_core} {role_name}",
        role_name=role_name,
        role_summary=(
            role.role_summary.strip()
            or f"Durable execution role focused on {role_name} work for the operating loop."
        ),
        mission=(
            role.mission.strip()
            or "Execute assigned lane work, report progress, and surface blockers with evidence."
        ),
        goal_kind=goal_kind,
        agent_class="business",
        employment_mode=employment_mode,
        activation_mode=activation_mode,
        suspendable=bool(role.suspendable),
        reports_to=reports_to,
        risk_level=_normalize_risk_level(role.risk_level),
        environment_constraints=list(
            role.environment_constraints or _BUSINESS_ENVIRONMENT,
        ),
        allowed_capabilities=_filter_capabilities(
            role.allowed_capabilities,
            default=_BUSINESS_ALLOWED_CAPABILITIES,
            required=resolve_role_capability_baseline(role, role_id),
        ),
        preferred_capability_families=list(role.preferred_capability_families or []),
        evidence_expectations=evidence_expectations,
    )



def _canonicalize_goals(
    profile: IndustryProfile,
    goals: list[IndustryDraftGoal],
    *,
    team_id: str,
    roles: list[IndustryRoleBlueprint],
    alias_to_agent_id: dict[str, str],
) -> list[IndustryDraftGoal]:
    roles_by_agent_id = {role.agent_id: role for role in roles}
    seen_goal_ids: set[str] = set()
    normalized: list[IndustryDraftGoal] = []
    for goal in goals:
        owner_agent_id = _resolve_agent_reference(
            goal.owner_agent_id,
            alias_to_agent_id=alias_to_agent_id,
        )
        if owner_agent_id is None or owner_agent_id not in roles_by_agent_id:
            continue
        role = roles_by_agent_id[owner_agent_id]
        goal_id = _reserve_identifier(
            _slugify_identifier(
                f"{team_id}-{goal.goal_id or goal.kind or role.goal_kind}",
                fallback=f"{team_id}-{role.goal_kind}",
            ),
            seen_goal_ids,
        )
        goal_kind = _slugify_identifier(
            goal.kind or role.goal_kind,
            fallback=role.goal_kind,
        )
        if is_execution_core_role_id(role.role_id):
            goal_kind = EXECUTION_CORE_ROLE_ID
        plan_steps = [step for step in list(goal.plan_steps)]
        if not plan_steps:
            plan_steps = [
                f"Clarify the operating objective for {role.role_name}.",
                "Execute the next governed steps with evidence.",
                "Report blockers, results, and follow-up actions back to the main brain.",
            ]
        normalized.append(
            IndustryDraftGoal(
                goal_id=goal_id,
                kind=goal_kind,
                owner_agent_id=owner_agent_id,
                title=goal.title.strip() or f"{profile.primary_label()} {role.role_name} operating goal",
                summary=goal.summary.strip() or role.mission,
                plan_steps=plan_steps,
            ),
        )
    if not normalized:
        raise ValueError("Industry draft must include at least one goal.")
    return normalized


def _canonicalize_schedules(
    profile: IndustryProfile,
    schedules: list[IndustryDraftSchedule],
    *,
    roles: list[IndustryRoleBlueprint],
    alias_to_agent_id: dict[str, str],
    team_id: str,
    goals: list[IndustryDraftGoal],
) -> list[IndustryDraftSchedule]:
    roles_by_agent_id = {role.agent_id: role for role in roles}
    goals_by_agent_id: dict[str, IndustryDraftGoal] = {}
    for goal in goals:
        goals_by_agent_id.setdefault(goal.owner_agent_id, goal)
    normalized: list[IndustryDraftSchedule] = []
    seen_schedule_ids: set[str] = set()
    for index, schedule in enumerate(schedules):
        owner_agent_id = _resolve_agent_reference(
            schedule.owner_agent_id,
            alias_to_agent_id=alias_to_agent_id,
        )
        if owner_agent_id is None or owner_agent_id not in roles_by_agent_id:
            continue
        role = roles_by_agent_id[owner_agent_id]
        schedule_slug = _slugify_identifier(
            schedule.schedule_id or schedule.title or role.role_id,
            fallback=role.role_id,
        )
        schedule_id = _reserve_identifier(
            f"{team_id}-{schedule_slug}",
            seen_schedule_ids,
            sanitizer=lambda value: value.strip("-"),
        )
        title = schedule.title.strip() or _default_schedule_title(profile, role)
        summary = schedule.summary.strip() or _default_schedule_summary(role)
        if is_execution_core_role_id(role.role_id):
            title = _normalize_execution_core_schedule_title(title, profile=profile)
            summary = _normalize_execution_core_schedule_summary(summary)
        normalized.append(
            IndustryDraftSchedule(
                schedule_id=schedule_id,
                owner_agent_id=owner_agent_id,
                title=title,
                summary=summary,
                cron=_normalize_cron(schedule.cron, role_id=role.role_id, index=index),
                timezone=schedule.timezone.strip() or "UTC",
                dispatch_channel="console",
                dispatch_mode=(
                    "final" if schedule.dispatch_mode == "final" else "stream"
                ),
            ),
        )
    return _ensure_default_schedules(
        profile,
        schedules=normalized,
        roles=roles,
        team_id=team_id,
        seen_schedule_ids=seen_schedule_ids,
    )


def _ensure_default_schedules(
    profile: IndustryProfile,
    *,
    schedules: list[IndustryDraftSchedule],
    roles: list[IndustryRoleBlueprint],
    team_id: str,
    seen_schedule_ids: set[str],
) -> list[IndustryDraftSchedule]:
    normalized = list(schedules)
    roles_by_agent_id = {role.agent_id: role for role in roles}
    existing_signatures: set[str] = set()
    for schedule in normalized:
        role = roles_by_agent_id.get(schedule.owner_agent_id)
        if role is None:
            continue
        existing_signatures.add(
            _schedule_signature(
                role_id=role.role_id,
                title=schedule.title,
                summary=schedule.summary,
            ),
        )
    for role in roles:
        if not is_execution_core_role_id(role.role_id):
            continue
        for blueprint in _default_schedule_blueprints(profile, role):
            signature = blueprint["signature"]
            if signature in existing_signatures:
                continue
            schedule_id = _reserve_identifier(
                f"{team_id}-{blueprint['slug']}",
                seen_schedule_ids,
                sanitizer=lambda value: value.strip("-"),
            )
            normalized.append(
                IndustryDraftSchedule(
                    schedule_id=schedule_id,
                    owner_agent_id=role.agent_id,
                    title=blueprint["title"],
                    summary=blueprint["summary"],
                    cron=blueprint["cron"],
                    timezone="Asia/Shanghai",
                    dispatch_channel="console",
                    dispatch_mode=(
                        "final" if blueprint["dispatch_mode"] == "final" else "stream"
                    ),
                ),
            )
            existing_signatures.add(signature)
    return normalized


def _filter_capabilities(
    requested: list[str] | None,
    *,
    default: list[str],
    required: list[str] | None = None,
    optional: list[str] | None = None,
) -> list[str]:
    filtered: list[str] = []
    seen: set[str] = set()
    baseline = [capability for capability in default if capability]
    allowed = {capability for capability in baseline if capability}
    for capability in (required or []):
        if capability:
            allowed.add(capability)
    for capability in (optional or []):
        if capability:
            allowed.add(capability)
    for capability in baseline:
        if capability and capability not in seen:
            seen.add(capability)
            filtered.append(capability)
    for capability in (requested or []):
        if not capability or capability in seen:
            continue
        if capability not in allowed and not _is_explicit_external_capability(capability):
            continue
        seen.add(capability)
        filtered.append(capability)

    for capability in (required or []):
        if not capability or capability in seen:
            continue
        filtered.append(capability)
        seen.add(capability)
    return filtered


def _is_explicit_external_capability(capability: str) -> bool:
    normalized = capability.strip().lower()
    if not normalized:
        return False
    return normalized.startswith(_EXPLICIT_EXTERNAL_CAPABILITY_PREFIXES)


def _normalize_risk_level(value: str | None) -> str:
    if value in {"auto", "guarded", "confirm"}:
        return value
    return "guarded"


def _normalize_search_text(values: list[object | None]) -> str:
    parts = [str(value).strip().lower() for value in values if str(value or "").strip()]
    return " ".join(parts)


def _first_non_empty_text(*values: object | None) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _profile_requires_research_lane(profile: IndustryProfile) -> bool:
    combined_text = _normalize_search_text(
        [
            profile.industry,
            profile.sub_industry,
            profile.product,
            profile.business_model,
            profile.region,
            profile.notes,
            profile.experience_notes,
            *profile.target_customers,
            *profile.channels,
            *profile.goals,
            *profile.constraints,
            *profile.operator_requirements,
        ],
    )
    if not combined_text:
        return False
    if _contains_any_keyword(combined_text, _RESEARCH_NEGATION_KEYWORDS):
        return False
    if not _contains_any_keyword(combined_text, _RESEARCH_SIGNAL_KEYWORDS):
        return False
    score = 2
    if len(profile.channels) >= 2:
        score += 1
    if len(profile.goals) >= 2:
        score += 1
    if profile.experience_mode == "system-led" and profile.operator_requirements:
        score += 1
    return score >= 2


def _build_default_researcher_source(
    profile: IndustryProfile,
) -> IndustryRoleBlueprint:
    return IndustryRoleBlueprint(
        role_id="researcher",
        agent_id="researcher",
        name=f"{profile.primary_label()} Researcher",
        role_name="Researcher",
        role_summary=(
            "Research support role that executes explicit research briefs for the main brain."
        ),
        mission=(
            f"Feed {_EXECUTION_CORE_NAME} with evidence-backed findings from explicit monitoring briefs and follow-up research."
        ),
        goal_kind="researcher",
        agent_class="system",
        employment_mode="career",
        activation_mode="persistent",
        suspendable=False,
        reports_to=EXECUTION_CORE_ROLE_ID,
        risk_level="guarded",
        environment_constraints=[],
        allowed_capabilities=[],
        preferred_capability_families=["research"],
        evidence_expectations=[],
    )



def _role_aliases(role: IndustryRoleBlueprint) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for raw in (
        role.role_id,
        role.agent_id,
        role.name,
        role.role_name,
        role.goal_kind,
    ):
        alias = _normalize_alias(raw)
        if alias:
            aliases[alias] = role.agent_id
    return aliases



def _source_role_aliases(
    role: IndustryRoleBlueprint,
    *,
    resolved_agent_id: str,
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for raw in (
        role.role_id,
        role.agent_id,
        role.name,
        role.role_name,
        role.goal_kind,
    ):
        alias = _normalize_alias(raw)
        if alias:
            aliases[alias] = resolved_agent_id
    return aliases



def _resolve_agent_reference(
    value: str | None,
    *,
    alias_to_agent_id: dict[str, str],
    fallback: str | None = None,
) -> str | None:
    alias = _normalize_alias(value)
    if alias and alias in alias_to_agent_id:
        return alias_to_agent_id[alias]
    return fallback



def _normalize_alias(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return _slugify_identifier(text, fallback=text)



def _reserve_identifier(
    raw_value: str,
    seen: set[str],
    *,
    sanitizer: Callable[[str], str] | None = None,
) -> str:
    value = sanitizer(raw_value) if sanitizer is not None else raw_value
    value = value.strip("-")
    if not value:
        value = "item"
    candidate = value
    counter = 2
    while candidate in seen:
        candidate = f"{value}-{counter}"
        counter += 1
    seen.add(candidate)
    return candidate



def _slugify_identifier(value: str | None, *, fallback: str) -> str:
    raw = (value or "").strip().lower()
    ascii_raw = raw.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_raw).strip("-")
    if slug:
        return slug
    fallback_raw = fallback.strip().lower() or "item"
    fallback_ascii = fallback_raw.encode("ascii", "ignore").decode("ascii")
    fallback_slug = re.sub(r"[^a-z0-9]+", "-", fallback_ascii).strip("-")
    if fallback_slug:
        return fallback_slug
    digest = hashlib.md5(fallback_raw.encode("utf-8")).hexdigest()[:8]
    return f"item-{digest}"



def _normalize_cron(value: str, *, role_id: str, index: int) -> str:
    raw = value.strip()
    if len(raw.split()) == 5:
        return raw
    return _default_cron(role_id=role_id, index=index)



def _default_schedule_session_id(
    *,
    team_id: str,
    role: IndustryRoleBlueprint,
) -> str:
    if is_execution_core_role_id(role.role_id):
        return f"industry-chat:{team_id}:{role.role_id}"
    return f"industry:{team_id}:{role.role_id}"



def _schedule_signature(
    *,
    role_id: str,
    title: str,
    summary: str,
) -> str:
    normalized = _normalize_search_text([role_id, title, summary])
    if is_execution_core_role_id(role_id):
        if "morning" in normalized:
            return "main-brain-morning-review"
        if "evening" in normalized or "night" in normalized:
            return "main-brain-evening-review"
    if role_id == "researcher":
        return "research-signal-loop"
    return normalized or role_id



def _default_schedule_blueprints(
    profile: IndustryProfile,
    role: IndustryRoleBlueprint,
) -> list[dict[str, str]]:
    label = profile.primary_label()
    if is_execution_core_role_id(role.role_id):
        return [
            {
                "signature": "main-brain-morning-review",
                "slug": "main-brain-morning-review",
                "title": f"{label} Spider Mesh Morning Review",
                "summary": "Morning main-brain review over reports, backlog, assignments, blockers, and next moves.",
                "cron": "0 9 * * *",
                "dispatch_mode": "final",
            },
            {
                "signature": "main-brain-evening-review",
                "slug": "main-brain-evening-review",
                "title": f"{label} Spider Mesh Evening Review",
                "summary": "Evening main-brain review over execution results, unresolved risks, and tomorrow routing.",
                "cron": "0 19 * * *",
                "dispatch_mode": "final",
            },
        ]
    return []



def _default_cron(*, role_id: str, index: int) -> str:
    if is_execution_core_role_id(role_id):
        return "0 9 * * *"
    if role_id == "researcher":
        return "0 11 * * *"
    weekday = 1 + (index % 5)
    hour = min(17, 11 + (index % 6))
    return f"0 {hour} * * {weekday}"



def _default_schedule_title(
    profile: IndustryProfile,
    role: IndustryRoleBlueprint,
) -> str:
    if is_execution_core_role_id(role.role_id):
        return f"{profile.primary_label()} {_EXECUTION_CORE_NAME} Review"
    if role.role_id == "researcher":
        return f"{profile.primary_label()} Research Signal Loop"
    return f"{profile.primary_label()} {role.role_name} Routine"



def _default_schedule_summary(role: IndustryRoleBlueprint) -> str:
    if is_execution_core_role_id(role.role_id):
        return "Run the main-brain review cadence and route the next governed moves."
    if role.role_id == "researcher":
        return "Collect and report durable industry, customer, platform, and competitor signals."
    return f"Run the durable routine for {role.role_name} and report outcomes with evidence."



def _normalize_execution_core_schedule_title(
    value: str,
    *,
    profile: IndustryProfile,
) -> str:
    normalized = _replace_execution_core_legacy_brand(value.strip())
    return normalized or f"{profile.primary_label()} {_EXECUTION_CORE_NAME} Review"



def _normalize_execution_core_schedule_summary(value: str) -> str:
    normalized = _replace_execution_core_legacy_brand(value.strip())
    return normalized or "Run the main-brain review cadence and route the next governed moves."



def _replace_execution_core_legacy_brand(value: str) -> str:
    normalized = value
    for legacy in EXECUTION_CORE_LEGACY_NAMES:
        normalized = normalized.replace(legacy, EXECUTION_CORE_NAME)
    return normalized.replace("Execution Core", EXECUTION_CORE_NAME)



def _resolve_team_topology(
    value: object | None,
    *,
    roles: list[IndustryRoleBlueprint],
) -> str:
    normalized = normalize_industry_team_topology(value)
    if normalized is not None:
        return normalized
    return _infer_team_topology(roles)



def _infer_team_topology(roles: list[IndustryRoleBlueprint]) -> str:
    non_core_roles = [
        role for role in roles if not is_execution_core_role_id(role.role_id)
    ]
    if len(non_core_roles) <= 1:
        return "solo"
    if len(non_core_roles) <= 3:
        return "lead-plus-support"
    if len(non_core_roles) <= 5:
        return "pod"
    return "full-team"



def _build_schedule_prompt(
    profile: IndustryProfile,
    *,
    role: IndustryRoleBlueprint,
    goal: IndustryDraftGoal | None,
    team_label: str | None = None,
    cadence_summary: str | None = None,
    task_mode: str | None = None,
) -> str:
    return build_industry_execution_prompt(
        profile=profile,
        role=role,
        goal_title=goal.title if goal is not None else None,
        goal_summary=goal.summary if goal is not None else None,
        team_label=team_label,
        cadence_summary=cadence_summary,
        task_mode=task_mode,
        primary_instruction=(
            "Run this scheduled routine as a durable operating loop, capture evidence, and route the result back through the governed chain."
        ),
    )
