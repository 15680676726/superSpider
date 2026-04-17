# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import BaseModel, Field

from ..providers.runtime_model_call import (
    RuntimeModelCallError,
    RuntimeModelCallPolicy,
    RuntimeModelCallService,
)
from .identity import EXECUTION_CORE_ROLE_ID, is_execution_core_role_id
from ..providers.runtime_provider_facade import (
    ProviderRuntimeSurface,
    build_compat_runtime_provider_facade,
)
from ..utils.model_response import materialize_model_response
from .compiler import canonicalize_industry_draft
from .models import (
    IndustryDraftGoal,
    IndustryDraftPlan,
    IndustryDraftSchedule,
    IndustryProfile,
    IndustryRoleBlueprint,
    IndustryTeamBlueprint,
    normalize_industry_team_topology,
)
from .prompting import build_industry_draft_system_prompt


class IndustryDraftGenerationError(RuntimeError):
    """Operator-facing draft generation failure."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class _GeneratedRole(BaseModel):
    role_id: str | None = None
    agent_id: str | None = None
    name: str = ""
    role_name: str = ""
    role_summary: str = ""
    mission: str = ""
    goal_kind: str | None = None
    agent_class: str = "business"
    activation_mode: str = "persistent"
    suspendable: bool = False
    reports_to: str | None = None
    risk_level: str | None = None
    environment_constraints: list[str] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list)
    preferred_capability_families: list[str] = Field(default_factory=list)
    evidence_expectations: list[str] = Field(default_factory=list)


class _GeneratedGoal(BaseModel):
    goal_id: str | None = None
    kind: str | None = None
    owner_agent_id: str | None = None
    title: str = ""
    summary: str = ""
    plan_steps: list[str] = Field(default_factory=list)


class _GeneratedSchedule(BaseModel):
    schedule_id: str | None = None
    owner_agent_id: str | None = None
    title: str = ""
    summary: str = ""
    cron: str | None = None
    timezone: str | None = None
    dispatch_mode: str = "stream"


class _GeneratedTeam(BaseModel):
    team_id: str | None = None
    label: str = ""
    summary: str = ""
    topology: str | None = None
    agents: list[_GeneratedRole] = Field(default_factory=list)


class _GeneratedDraft(BaseModel):
    team: _GeneratedTeam
    goals: list[_GeneratedGoal] = Field(default_factory=list)
    schedules: list[_GeneratedSchedule] = Field(default_factory=list)
    generation_summary: str | None = None


def _is_researcher_role(role: IndustryRoleBlueprint) -> bool:
    role_id = str(role.role_id or "").strip().lower()
    goal_kind = str(role.goal_kind or "").strip().lower()
    return role_id == "researcher" or goal_kind == "researcher"


def _fallback_goal_plan_steps(*, role_name: str, execution_core: bool) -> list[str]:
    if execution_core:
        return [
            "Review the latest evidence, backlog, and operating constraints.",
            "Choose the next governed assignments and execution priorities.",
            "Report decisions, blockers, and follow-up actions with evidence.",
        ]
    return [
        f"Clarify the next deliverable for {role_name}.",
        "Execute the lane work and capture durable evidence.",
        "Report progress, blockers, and next actions back to the main brain.",
    ]


def _synthesize_fallback_goals(
    *,
    profile: IndustryProfile,
    draft: IndustryDraftPlan,
) -> list[IndustryDraftGoal]:
    goals: list[IndustryDraftGoal] = []
    seen_goal_ids: set[str] = set()
    for role in draft.team.agents:
        if _is_researcher_role(role):
            continue
        owner_ref = str(role.agent_id or role.role_id or role.goal_kind or "").strip()
        if not owner_ref:
            continue
        role_name = str(role.role_name or role.name or role.goal_kind or role.role_id or "Specialist").strip()
        execution_core = is_execution_core_role_id(role.role_id) or is_execution_core_role_id(
            role.goal_kind,
        )
        goal_kind = (
            EXECUTION_CORE_ROLE_ID
            if execution_core
            else str(role.goal_kind or role.role_id or "execution").strip()
        )
        goal_id_base = str(role.role_id or role.goal_kind or role_name).strip().lower().replace(" ", "-") or "goal"
        goal_id = f"{goal_id_base}-goal"
        counter = 2
        while goal_id in seen_goal_ids:
            goal_id = f"{goal_id_base}-goal-{counter}"
            counter += 1
        seen_goal_ids.add(goal_id)
        goals.append(
            IndustryDraftGoal(
                goal_id=goal_id,
                kind=goal_kind,
                owner_agent_id=owner_ref,
                title=(
                    f"Operate {profile.primary_label()}"
                    if execution_core
                    else f"Advance {profile.primary_label()} {role_name}"
                ),
                summary=(
                    str(role.mission or "").strip()
                    or (
                        "Maintain the governed operating loop and route the next best work."
                        if execution_core
                        else f"Execute {role_name} lane work and report durable evidence."
                    )
                ),
                plan_steps=_fallback_goal_plan_steps(
                    role_name=role_name,
                    execution_core=execution_core,
                ),
            )
        )
    return goals


def _response_to_payload(response: object) -> dict[str, Any]:
    metadata = getattr(response, "metadata", None)
    if isinstance(metadata, BaseModel):
        return metadata.model_dump(mode="json")
    if isinstance(metadata, dict):
        return metadata
    text = _response_to_text(response)
    if not text:
        raise ValueError("Industry draft generator returned an empty response.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Industry draft generator did not return valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Industry draft generator returned a non-object payload.")
    return payload


async def _materialize_response(response: object) -> object:
    return await materialize_model_response(response)


def _response_to_text(response: object) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
            else:
                text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


class IndustryDraftGenerator:
    """Generate an editable industry draft through the active chat model."""

    def __init__(
        self,
        *,
        model_factory: Callable[[], object] | None = None,
        provider_runtime: ProviderRuntimeSurface | None = None,
        provider_manager: ProviderRuntimeSurface | None = None,
    ) -> None:
        self._provider_runtime = (
            provider_runtime
            or provider_manager
            or build_compat_runtime_provider_facade()
        )
        self._model_factory = model_factory or self._provider_runtime.get_active_chat_model
        if model_factory is not None:
            self._model_call_service = RuntimeModelCallService(
                model_factory=self._model_factory,
            )
        else:
            service_getter = getattr(self._provider_runtime, "get_model_call_service", None)
            if callable(service_getter):
                self._model_call_service = service_getter()
            else:
                self._model_call_service = RuntimeModelCallService(
                    model_factory=self._model_factory,
                )

    async def generate(
        self,
        *,
        profile: IndustryProfile,
        owner_scope: str,
        media_context: str | None = None,
    ) -> IndustryDraftPlan:
        messages = self._build_messages(profile, media_context=media_context)
        try:
            payload = await self._model_call_service.invoke_structured(
                messages=messages,
                policy=RuntimeModelCallPolicy(
                    timeout_seconds=120,
                    structured_schema=_GeneratedDraft,
                ),
                feature="industry_draft_generation",
            )
        except RuntimeModelCallError as exc:
            detail = str(exc).strip()
            message = (
                "Industry draft preview could not complete because the active chat model call failed. "
                "Check the provider or model configuration and retry."
            )
            status_code = 503
            if exc.code == "MODEL_UPSTREAM_ERROR":
                message = (
                    "Industry draft preview requires an available active chat model. "
                    "Configure Settings > Models first and try again."
                )
            elif exc.code == "MODEL_STRUCTURED_VALIDATION_FAILED":
                message = (
                    "Industry draft preview received an invalid structured response from the active chat model. "
                    "Retry the preview or switch to a more stable model."
                )
                status_code = 502
            if detail:
                message = f"{message} ({detail})"
            raise IndustryDraftGenerationError(
                message,
                status_code=status_code,
            ) from exc
        try:
            payload = _GeneratedDraft.model_validate(
                payload.model_dump(mode="json")
                if isinstance(payload, BaseModel)
                else _response_to_payload(payload)
            )
        except ValueError as exc:
            detail = str(exc).strip()
            message = (
                "Industry draft preview received an invalid structured response from the active chat model. "
                "Retry the preview or switch to a more stable model."
            )
            if detail:
                message = f"{message} ({detail})"
            raise IndustryDraftGenerationError(
                message,
                status_code=502,
            ) from exc
        draft = IndustryDraftPlan(
            team=IndustryTeamBlueprint(
                team_id=payload.team.team_id or "",
                label=payload.team.label,
                summary=payload.team.summary,
                topology=normalize_industry_team_topology(payload.team.topology),
                agents=[
                    IndustryRoleBlueprint(
                        role_id=role.role_id or "",
                        agent_id=role.agent_id or "",
                        name=role.name,
                        role_name=role.role_name,
                        role_summary=role.role_summary,
                        mission=role.mission,
                        goal_kind=role.goal_kind or "",
                        agent_class=(
                            "system" if role.agent_class == "system" else "business"
                        ),
                        activation_mode=(
                            "on-demand"
                            if role.activation_mode == "on-demand"
                            else "persistent"
                        ),
                        suspendable=bool(role.suspendable),
                        reports_to=role.reports_to,
                        risk_level=(
                            role.risk_level
                            if role.risk_level in {"auto", "guarded", "confirm"}
                            else "guarded"
                        ),
                        environment_constraints=list(role.environment_constraints),
                        allowed_capabilities=list(role.allowed_capabilities),
                        preferred_capability_families=list(
                            role.preferred_capability_families
                        ),
                        evidence_expectations=list(role.evidence_expectations),
                    )
                    for role in payload.team.agents
                ],
            ),
            goals=[
                IndustryDraftGoal(
                    goal_id=goal.goal_id or "",
                    kind=goal.kind or "",
                    owner_agent_id=goal.owner_agent_id or "",
                    title=goal.title,
                    summary=goal.summary,
                    plan_steps=list(goal.plan_steps),
                )
                for goal in payload.goals
            ],
            schedules=[
                IndustryDraftSchedule(
                    schedule_id=schedule.schedule_id or "",
                    owner_agent_id=schedule.owner_agent_id or "",
                    title=schedule.title,
                    summary=schedule.summary,
                    cron=schedule.cron or "0 9 * * *",
                    timezone=schedule.timezone or "UTC",
                    dispatch_mode=(
                        "final" if schedule.dispatch_mode == "final" else "stream"
                    ),
                )
                for schedule in payload.schedules
            ],
            generation_summary=payload.generation_summary,
        )
        try:
            return canonicalize_industry_draft(
                profile,
                draft,
                owner_scope=owner_scope,
            )
        except ValueError as exc:
            if str(exc).strip() != "Industry draft must include at least one goal.":
                raise
            fallback_goals = _synthesize_fallback_goals(
                profile=profile,
                draft=draft,
            )
            if not fallback_goals:
                raise
            repaired_draft = draft.model_copy(update={"goals": fallback_goals})
            return canonicalize_industry_draft(
                profile,
                repaired_draft,
                owner_scope=owner_scope,
            )

    def describe(self) -> dict[str, str]:
        try:
            active = self._provider_runtime.get_active_model()
        except Exception:
            return {}
        if active is None:
            return {}
        return {
            "provider_id": active.provider_id,
            "model": active.model,
        }

    def _build_messages(
        self,
        profile: IndustryProfile,
        *,
        media_context: str | None = None,
    ) -> list[dict[str, str]]:
        brief_payload = json.dumps(
            profile.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        system_prompt = build_industry_draft_system_prompt()
        operator_lines = [
            f"Planning mode: {profile.experience_mode}",
        ]
        if profile.experience_mode == "operator-guided":
            operator_lines.append(
                "Respect the operator's existing experience and turn it into explicit roles, goals, schedules, and evidence expectations.",
            )
        else:
            operator_lines.append(
                "The operator does not have a fixed playbook here. Design the full operating loop yourself instead of waiting for step-by-step instructions.",
            )
        if profile.experience_notes:
            operator_lines.append(f"Experience notes: {profile.experience_notes}")
        if profile.operator_requirements:
            operator_lines.append("Operator requirements:")
            operator_lines.extend(
                f"- {item}" for item in profile.operator_requirements[:8]
            )
        operator_prompt = "\n".join(operator_lines)
        user_prompt = (
            "Generate the industry draft from this brief.\n\n"
            f"Brief JSON:\n{brief_payload}\n\n"
            f"Operator planning context:\n{operator_prompt}"
        )
        if media_context:
            user_prompt = f"{user_prompt}\n\nAttached material context:\n{media_context}"
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
