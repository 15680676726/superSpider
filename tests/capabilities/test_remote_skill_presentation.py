from types import SimpleNamespace

from copaw.capabilities.remote_skill_contract import (
    RemoteSkillCandidate,
    build_remote_skill_preflight,
)
from copaw.capabilities.remote_skill_presentation import (
    localize_remote_skill_text,
    present_remote_skill_name,
)


def test_present_remote_skill_name_avoids_generic_verb_title_from_summary() -> None:
    title = present_remote_skill_name(
        slug="powerpoint-pptx",
        name="Powerpoint / PPTX",
        summary=(
            "Create, inspect, and edit Microsoft PowerPoint presentations.\n"
            "创建、检查和编辑 Microsoft PowerPoint 演示文稿及 PPTX 文件。"
        ),
        curated=True,
    )

    assert title != "创建"
    assert "Powerpoint" in title or "PPTX" in title


def test_present_remote_skill_name_strips_legacy_brand_tokens() -> None:
    title = present_remote_skill_name(
        slug="openclaw-github-assistant",
        name="OpenClaw GitHub Assistant",
        summary="Query and manage GitHub repositories.",
    )

    assert "OpenClaw" not in title
    assert "GitHub" in title


def test_localize_remote_skill_text_repairs_mojibake_chinese() -> None:
    mojibake = "?????????????????".encode("utf-8").decode("latin1")
    localized = localize_remote_skill_text(mojibake)

    assert localized == "?????????????????"


def _remote_candidate(skill_name: str) -> RemoteSkillCandidate:
    return RemoteSkillCandidate(
        candidate_key=f"hub:{skill_name}",
        source_kind="hub",
        source_label="SkillHub",
        title=skill_name.replace("_", " ").title(),
        description="Governed remote skill candidate.",
        bundle_url=(
            "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/"
            f"skills/{skill_name}.zip"
        ),
        source_url=(
            "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/"
            f"skills/{skill_name}.zip"
        ),
        slug=skill_name,
        version="1.0.0",
        install_name=skill_name,
        capability_ids=[f"skill:{skill_name}"],
        capability_tags=["skill", "remote"],
        review_required=False,
        search_query="guarded outreach",
    )


def _agent_profile_service(
    *,
    effective_capability_ids: list[str],
    seat_instance_capability_ids: list[str],
    role_prototype_capability_ids: list[str] | None = None,
    seat_ref: str = "env-browser-primary",
) -> object:
    prototype_ids = list(role_prototype_capability_ids or ["tool:read_file"])
    return SimpleNamespace(
        get_agent=lambda _agent_id: SimpleNamespace(
            agent_id="agent-1",
            agent_class="business",
            industry_role_id="solution-lead",
            role_name="Solution Lead",
        ),
        get_capability_surface=lambda _agent_id: {
            "baseline_capabilities": list(prototype_ids),
            "effective_capabilities": list(effective_capability_ids),
        },
        get_agent_detail=lambda _agent_id: {
            "runtime": {
                "industry_role_id": "solution-lead",
                "metadata": {
                    "selected_seat_ref": seat_ref,
                    "capability_layers": {
                        "schema_version": "industry-seat-capability-layers-v1",
                        "role_prototype_capability_ids": list(prototype_ids),
                        "seat_instance_capability_ids": list(
                            seat_instance_capability_ids,
                        ),
                        "cycle_delta_capability_ids": [],
                        "session_overlay_capability_ids": [],
                    },
                },
            },
        },
    )


def test_build_remote_skill_preflight_blocks_candidate_when_role_and_seat_skill_budget_overflow() -> None:
    existing_skill_ids = [f"skill:seat-pack-{index}" for index in range(12)]
    preflight = build_remote_skill_preflight(
        candidate=_remote_candidate("nextgen_outreach"),
        target_agent_id="agent-1",
        capability_assignment_mode="merge",
        agent_profile_service=_agent_profile_service(
            effective_capability_ids=["tool:read_file", *existing_skill_ids],
            seat_instance_capability_ids=existing_skill_ids,
        ),
    )

    checks = {item.code: item for item in preflight.checks}

    assert preflight.ready is False
    assert preflight.lifecycle_stage == "blocked"
    assert preflight.trial_plan is not None
    assert preflight.trial_plan.lifecycle_stage == "blocked"
    assert preflight.trial_plan.next_lifecycle_stage == "blocked"
    assert preflight.trial_plan.rollout_scope == "single-seat"
    assert preflight.trial_plan.target_role_id == "solution-lead"
    assert preflight.trial_plan.target_seat_ref == "env-browser-primary"
    assert checks["role-skill-budget"].status == "fail"
    assert checks["seat-skill-budget"].status == "fail"


def test_build_remote_skill_preflight_keeps_overlap_replacement_within_single_seat_budget() -> None:
    existing_skill_ids = [f"skill:seat-pack-{index}" for index in range(11)] + [
        "skill:legacy_outreach",
    ]
    preflight = build_remote_skill_preflight(
        candidate=_remote_candidate("nextgen_outreach"),
        target_agent_id="agent-1",
        capability_assignment_mode="replace",
        replacement_capability_ids=["skill:legacy_outreach"],
        agent_profile_service=_agent_profile_service(
            effective_capability_ids=["tool:read_file", *existing_skill_ids],
            seat_instance_capability_ids=existing_skill_ids,
        ),
    )

    checks = {item.code: item for item in preflight.checks}

    assert preflight.ready is True
    assert preflight.lifecycle_stage == "candidate"
    assert preflight.trial_plan is not None
    assert preflight.trial_plan.lifecycle_stage == "candidate"
    assert preflight.trial_plan.next_lifecycle_stage == "trial"
    assert preflight.trial_plan.replacement_target_ids == ["skill:legacy_outreach"]
    assert preflight.trial_plan.rollout_scope == "single-seat"
    assert checks["role-skill-budget"].status == "pass"
    assert checks["seat-skill-budget"].status == "pass"
