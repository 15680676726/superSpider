from __future__ import annotations

from typing import TYPE_CHECKING

from .identity import EXECUTION_CORE_NAME, EXECUTION_CORE_ROLE_ID

if TYPE_CHECKING:
    from .models import IndustryProfile, IndustryRoleBlueprint

_TEAM_TOPOLOGY_GUIDANCE = {
    "solo": "One specialist lane plus the execution core. Use this for simple professions or tightly scoped services.",
    "lead-plus-support": "One primary specialist plus one or two supporting lanes. Use this when the work needs light collaboration but not a full pod.",
    "pod": "Two to four durable lanes with clear ownership. Use this for ongoing multi-function operations.",
    "full-team": "Five or more durable lanes. Use this only when the brief truly demands broad parallel operations.",
}

_TEAM_GENERATION_EXAMPLES = (
    {
        "brief": "A fortune-telling assistant that mostly serves one customer request at a time.",
        "topology": "solo",
        "roles": [
            f"{EXECUTION_CORE_ROLE_ID} -> visible manager, intake, final response",
            "fortune-reader -> performs the reading and returns the evidence-backed interpretation",
        ],
    },
    {
        "brief": "A writer studio that drafts articles and occasionally gathers reference material.",
        "topology": "lead-plus-support",
        "roles": [
            f"{EXECUTION_CORE_ROLE_ID} -> editor-in-chief, planning, review, delivery",
            "writer -> drafts the manuscript",
            "researcher -> optional support lane only when recurring source collection is actually needed",
        ],
    },
    {
        "brief": "An operations consulting team that runs multiple loops across research, solution design, and delivery follow-up.",
        "topology": "pod",
        "roles": [
            f"{EXECUTION_CORE_ROLE_ID} -> control core, planning, delegation, reporting",
            "researcher -> signal collection",
            "solution-lead -> offer and process design",
            "delivery-ops -> follow-up and rollout readiness",
        ],
    },
)

_TASK_MODE_LABELS = {
    "team-orchestration": "team orchestration",
    "research-signal-collection": "research and signal collection",
    "solution-shaping": "solution shaping",
    "specialist-execution": "specialist execution",
    "recurring-review": "recurring review",
    "chat-writeback-followup": "chat writeback follow-up",
}


def build_industry_draft_system_prompt() -> str:
    topology_lines = "\n".join(
        f"- `{topology}`: {summary}"
        for topology, summary in _TEAM_TOPOLOGY_GUIDANCE.items()
    )
    example_lines: list[str] = []
    for example in _TEAM_GENERATION_EXAMPLES:
        example_lines.append(f"- Brief: {example['brief']}")
        example_lines.append(f"  Choose topology: `{example['topology']}`")
        for role in example["roles"]:
            example_lines.append(f"  Role: {role}")
    examples = "\n".join(example_lines)
    return "\n".join(
        [
            "You are generating an editable industry team draft for Spider Mesh.",
            "Return a structured team draft that an operator will review before activation.",
            "Keep the writing in the same language as the brief.",
            "",
            "Shared operating manifesto:",
            f"- Always include exactly one visible team control core with role_id `{EXECUTION_CORE_ROLE_ID}`.",
            f"- The visible name and role_name of `{EXECUTION_CORE_ROLE_ID}` must be `{EXECUTION_CORE_NAME}`.",
            f"- `{EXECUTION_CORE_ROLE_ID}` is the team's manager: it receives the human goal, decomposes work, delegates, supervises, verifies, and gives the final report.",
            f"- `{EXECUTION_CORE_ROLE_ID}` must not be treated as a default leaf worker. It should plan, route, and supervise instead.",
            f"- Treat `{EXECUTION_CORE_ROLE_ID}` as the brain only: researchers are the eyes, specialist roles are the hands and feet.",
            "- Choose the smallest viable team that can actually do the job.",
            "- If `experience_mode` is `operator-guided`, treat `experience_notes` and `operator_requirements` as first-class planning anchors instead of overwriting them with a generic template.",
            "- If `experience_mode` is `system-led`, design the operating loop end to end yourself and proactively add the durable lanes the brief will actually need.",
            "- Add a `researcher` role only when the brief truly needs a recurring evidence, sourcing, or signal-collection lane.",
            "- When the brief implies recurring market, platform, customer, competitor, or operating signal collection, keep `researcher` as a persistent role and give it a recurring schedule.",
            "- If the operator explicitly names a missing loop such as customer service, content, reporting, sourcing, or platform operations, make that loop visible in the draft instead of hiding it inside another role.",
            "- Do not create filler roles, mirrored roles, or roles whose missions overlap heavily.",
            "- Every non-core role must own a distinct loop, output, or evidence stream.",
            "- Prefer one durable specialist over multiple vague assistants.",
            "- Role names must describe the real operating loop. Avoid vague labels like `solution lead`, `specialist`, or `operator` unless the brief is genuinely about solution design or consulting delivery.",
            "- Use `industry`, `product`, `business_model`, `channels`, `goals`, and `operator_requirements` as naming anchors so the team reads like the selected business, not a generic AI org chart.",
            "- If the brief is e-commerce, retail, marketplace, or storefront work, prefer explicit store/platform/customer/content/fulfillment lanes over generic solution roles.",
            "- If the brief is SaaS, B2B service, or delivery work, prefer explicit customer success, account operations, implementation, or reporting lanes over generic assistants.",
            "- When a role clearly centers on one or two capability families, fill `preferred_capability_families` with the canonical family ids (for example `research`, `workflow`, `content`, `crm`, `browser`, `data`).",
            "- Technical safety fields can be approximate; the server will finalize them.",
            "",
            "Allowed team topologies:",
            topology_lines,
            "",
            "Topology selection rules:",
            "- `solo` is the default for simple professions and single-loop work.",
            "- `lead-plus-support` is for one main worker plus light recurring support.",
            "- `pod` is for genuinely multi-loop operations.",
            "- `full-team` is rare and must be justified by the brief.",
            "",
            "Few-shot examples:",
            examples,
            "",
            "Goals and schedules:",
            "- Provide goals aligned to the roles you created.",
            "- Provide schedules only when there is a real recurring loop worth running.",
            "- Do not manufacture goals or schedules for placeholder roles.",
        ]
    )


def build_team_operating_model_lines(
    *,
    has_team_context: bool,
    is_execution_core_runtime: bool,
) -> list[str]:
    if not has_team_context:
        return []
    if is_execution_core_runtime:
        return [
            "- Operating mode: team control core.",
            "- Receive the user's objective, decide the next operating move, and break work into role-sized packets when specialists exist.",
            "- Prefer dispatching, delegating, supervising, and verifying over absorbing leaf execution into the control core.",
            "- Compare reports before deciding the next move.",
            "- Detect conflicts and holes before closing the loop.",
            "- Surface staffing/routing gaps explicitly when owners, lanes, or capability routes are missing.",
            "- Own final operator-facing synthesis before delegating more work.",
            "- Treat researcher lanes as the team's eyes and specialist lanes as the hands and feet; the control core keeps orchestration authority.",
            "- If the exact procedure is unclear, first inspect the relevant knowledge, SOPs, mounted skills, or prior evidence before dispatching or acting.",
            "- Collect evidence and status back from teammates before closing the loop.",
            "- Own role and capability routing when governed assignment tools are mounted; do not leave executable authority changes as vague suggestions.",
            "- Deliver the final operator-facing summary only after checking outcomes, blockers, and remaining risk.",
            "- When the operator adds a new task, points out a missing loop, or corrects a bad plan through chat, treat it as a live brief update and revise delegation, goals, and schedules instead of defending the stale plan.",
        ]
    return [
        "- Operating mode: specialized teammate.",
        "- Execute within your assigned role envelope instead of taking over the whole team plan.",
        "- If the exact procedure is unclear, first inspect the relevant knowledge, mounted skills, SOPs, or prior evidence, then execute inside your role envelope.",
        "- Return concrete evidence, blockers, and the recommended next move back to the execution core.",
        "- Escalate missing authority or capability gaps rather than improvising outside your role.",
    ]


def infer_industry_task_mode(
    *,
    role_id: str | None,
    goal_kind: str | None = None,
    source: str = "goal",
) -> str:
    normalized_source = str(source or "").strip().lower() or "goal"
    normalized_role_id = str(role_id or "").strip().lower()
    normalized_goal_kind = str(goal_kind or "").strip().lower()
    if normalized_source == "chat-writeback":
        return "chat-writeback-followup"
    if normalized_source == "schedule":
        return "recurring-review"
    if normalized_role_id == EXECUTION_CORE_ROLE_ID or normalized_goal_kind == EXECUTION_CORE_ROLE_ID:
        return "team-orchestration"
    if normalized_role_id == "researcher" or normalized_goal_kind == "researcher":
        return "research-signal-collection"
    if normalized_role_id in {"solution-lead", "solution"} or normalized_goal_kind in {
        "solution-lead",
        "solution",
    }:
        return "solution-shaping"
    return "specialist-execution"


def describe_industry_task_mode(task_mode: str | None) -> str | None:
    normalized = str(task_mode or "").strip().lower()
    if not normalized:
        return None
    return _TASK_MODE_LABELS.get(normalized, normalized)


def build_role_execution_contract_lines(
    *,
    role_id: str | None,
    is_execution_core_runtime: bool,
) -> list[str]:
    normalized_role_id = str(role_id or "").strip().lower()
    if is_execution_core_runtime or normalized_role_id == EXECUTION_CORE_ROLE_ID:
        return [
            "- You are the team control core. Own intake, sequencing, delegation, supervision, and final operator-facing synthesis.",
            "- Compare reports, detect conflicts and holes, then decide what to delegate next.",
            "- Always assign clear owners and closure criteria; if no specialist lane fits, surface the staffing or routing gap instead of doing the leaf work yourself.",
        ]
    if normalized_role_id == "researcher":
        return [
            "- Stay inside the research lane: gather signals, verify sources, and return decision-useful findings.",
            "- You are the team's eyes, not a parallel brain or independent execution center.",
            "- Do not finalize commercial or operational moves without handing back an owner-ready recommendation.",
        ]
    if normalized_role_id in {"solution-lead", "solution"}:
        return [
            "- Turn raw demand into an executable plan, workflow, offer structure, or operating design.",
            "- Hand off implementation-ready actions instead of drifting into unbounded research or unrelated execution.",
        ]
    return [
        "- Stay inside the assigned specialist lane and finish the concrete work packet you own.",
        "- Escalate missing authority, dependencies, or cross-role decisions instead of improvising outside scope.",
    ]


def build_task_mode_contract_lines(
    task_mode: str | None,
) -> list[str]:
    normalized = str(task_mode or "").strip().lower()
    if normalized == "team-orchestration":
        return [
            "- This task is orchestration-first: decide the next move, assign owners, and define handoff boundaries.",
            "- Keep leaf execution off the control core; route it to a specialist or surface the staffing/routing gap.",
        ]
    if normalized == "research-signal-collection":
        return [
            "- This task is research-first: gather current signals, compare sources, and return a usable conclusion.",
            "- Separate observed facts, interpretation, and open questions.",
        ]
    if normalized == "solution-shaping":
        return [
            "- This task is solution-shaping: convert demand into a concrete plan, process, or offer structure.",
            "- Return explicit next actions, dependencies, assumptions, and decision points.",
        ]
    if normalized == "recurring-review":
        return [
            "- This task is a recurring review loop: inspect the newest evidence, detect drift, and decide the next cycle.",
            "- Prefer delta analysis over rewriting the whole plan from scratch.",
        ]
    if normalized == "chat-writeback-followup":
        return [
            "- This task comes from operator chat writeback: execute against the newly recorded instruction, not the stale plan.",
            "- If the new instruction changes priority or cadence, reflect that change in the proposed next move.",
        ]
    return [
        "- Focus on completing the current role-owned work packet and report the next required handoff.",
    ]


def build_evidence_contract_lines(
    *,
    task_mode: str | None,
    is_execution_core_runtime: bool,
) -> list[str]:
    normalized = str(task_mode or "").strip().lower()
    lines = [
        "- Return concrete evidence, not only conclusions. Include artifacts, source references, decisions, or execution traces when available.",
    ]
    if is_execution_core_runtime or normalized == "team-orchestration":
        lines.append(
            "- When delegating or closing the loop, name the owner, expected output, risk, and proof required.",
        )
    elif normalized == "research-signal-collection":
        lines.append(
            "- Cite sources, signal comparisons, and confidence gaps so the execution core can reuse the finding.",
        )
    elif normalized == "solution-shaping":
        lines.append(
            "- Return the workflow, offer structure, dependencies, and assumptions that still need validation.",
        )
    elif normalized == "recurring-review":
        lines.append(
            "- Compare this cycle with the last known state and call out what changed, what stalled, and what should happen next.",
        )
    elif normalized == "chat-writeback-followup":
        lines.append(
            "- Show how the new operator instruction changed the plan, priority, owner routing, or cadence.",
        )
    else:
        lines.append(
            "- Show what was completed, what is blocked, and what is ready for handoff.",
        )
    return lines


def build_industry_execution_prompt(
    *,
    profile: IndustryProfile,
    role: IndustryRoleBlueprint,
    primary_instruction: str,
    goal_title: str | None = None,
    goal_summary: str | None = None,
    team_label: str | None = None,
    cadence_summary: str | None = None,
    task_mode: str | None = None,
) -> str:
    label = (team_label or profile.primary_label()).strip()
    normalized_task_mode = task_mode or infer_industry_task_mode(
        role_id=role.role_id,
        goal_kind=role.goal_kind,
        source="schedule" if cadence_summary else "goal",
    )
    task_mode_label = describe_industry_task_mode(normalized_task_mode)
    role_contract_lines = build_role_execution_contract_lines(
        role_id=role.role_id,
        is_execution_core_runtime=role.role_id == EXECUTION_CORE_ROLE_ID,
    )
    task_contract_lines = build_task_mode_contract_lines(normalized_task_mode)
    evidence_contract_lines = build_evidence_contract_lines(
        task_mode=normalized_task_mode,
        is_execution_core_runtime=role.role_id == EXECUTION_CORE_ROLE_ID,
    )

    lines = [
        f"You are now acting as {role.role_name} for the industry team '{label}'.",
        f"Industry: {profile.industry}.",
    ]
    if task_mode_label:
        lines.append(f"Task mode: {task_mode_label}.")
    if role.role_summary.strip():
        lines.append(f"Role summary: {role.role_summary.strip()}")
    if role.mission.strip():
        lines.append(f"Mission: {role.mission.strip()}")
    if goal_title:
        lines.append(f"Current goal: {goal_title}")
    if goal_summary:
        lines.append(f"Goal summary: {goal_summary}")
    if cadence_summary:
        lines.append(f"Cadence: {cadence_summary}")
    lines.append(f"Primary instruction: {primary_instruction.strip()}")

    target_customers = _preview_items(profile.target_customers)
    if target_customers:
        lines.append(f"Target customers: {target_customers}")
    priority_channels = _preview_items(profile.channels)
    if priority_channels:
        lines.append(f"Priority channels: {priority_channels}")
    operating_constraints = _preview_items(profile.constraints)
    if operating_constraints:
        lines.append(f"Operating constraints: {operating_constraints}")
    operator_requirements = _preview_items(profile.operator_requirements, limit=4)
    if operator_requirements:
        lines.append(f"Operator requirements: {operator_requirements}")
    environment_constraints = _preview_items(role.environment_constraints, limit=4)
    if environment_constraints:
        lines.append(f"Environment constraints: {environment_constraints}")
    evidence_expectations = _preview_items(role.evidence_expectations, limit=4)
    if evidence_expectations:
        lines.append(f"Evidence expectations: {evidence_expectations}")

    lines.extend(["", "Role contract:", *role_contract_lines])
    lines.extend(["", "Task mode contract:", *task_contract_lines])
    lines.extend(["", "Evidence contract:", *evidence_contract_lines])
    lines.extend(
        [
            "",
            "Execution rules:",
            "- Read the newest formal evidence and active constraints before acting.",
            "- If SOPs, mounted skills, or reusable artifacts exist, inspect them before inventing new procedures.",
            "- Surface blockers, missing authority, and risk clearly instead of hiding them in prose.",
        ]
    )
    if role.role_id == EXECUTION_CORE_ROLE_ID:
        lines.append(
            "- If specialist lanes exist, prefer assigning and verifying work over absorbing every task yourself.",
        )
    else:
        lines.append(
            "- Return the next handoff back to the execution core once your role-owned work packet is complete.",
        )
    return "\n".join(line for line in lines if line)


def _preview_items(items: list[str] | tuple[str, ...] | None, *, limit: int = 3) -> str:
    if not items:
        return ""
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return ""
    preview = values[:limit]
    if len(values) > limit:
        preview.append(f"...(+{len(values) - limit})")
    return ", ".join(preview)
