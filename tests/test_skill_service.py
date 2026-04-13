from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from copaw.capabilities.skill_evolution_service import SkillEvolutionService
from copaw.capabilities.skill_service import CapabilitySkillService
from copaw import skill_service as skill_service_module
from copaw.skill_service import SkillService


def _patch_skill_dirs(monkeypatch, tmp_path) -> tuple[Path, Path, Path]:
    builtin_dir = tmp_path / "builtin"
    customized_dir = tmp_path / "customized"
    active_dir = tmp_path / "active"
    builtin_dir.mkdir()
    customized_dir.mkdir()
    active_dir.mkdir()
    monkeypatch.setattr("copaw.skill_service.get_builtin_skills_dir", lambda: builtin_dir)
    monkeypatch.setattr("copaw.skill_service.get_customized_skills_dir", lambda: customized_dir)
    monkeypatch.setattr("copaw.skill_service.get_active_skills_dir", lambda: active_dir)
    return builtin_dir, customized_dir, active_dir


def test_skill_service_create_skill_rejects_path_traversal_in_tree_keys(
    monkeypatch,
    tmp_path,
) -> None:
    _, customized_dir, _ = _patch_skill_dirs(monkeypatch, tmp_path)

    created = SkillService.create_skill(
        name="research",
        content="---\nname: research\ndescription: Research skill\n---\n# Research\n",
        references={"..": {"escape.md": "bad"}},
    )

    assert created is False
    assert not (customized_dir / "escape.md").exists()
    assert not (customized_dir / "research" / "references" / "escape.md").exists()


def test_skill_service_create_skill_rejects_duplicate_package_identity(
    monkeypatch,
    tmp_path,
) -> None:
    _, customized_dir, _ = _patch_skill_dirs(monkeypatch, tmp_path)
    existing_dir = customized_dir / "existing"
    existing_dir.mkdir()
    (existing_dir / "SKILL.md").write_text(
        """---
name: existing
description: Existing skill
package_ref: https://github.com/acme/skills/tree/main/research
package_kind: hub-bundle
package_version: 1.0.0
---
# Existing
""",
        encoding="utf-8",
    )

    created = SkillService.create_skill(
        name="research",
        content="""---
name: research
description: Research skill
package_ref: https://github.com/acme/skills/tree/main/research
package_kind: hub-bundle
package_version: 1.0.0
---
# Research
""",
    )

    assert created is False
    assert not (customized_dir / "research").exists()


def test_capability_skill_service_reads_upgrade_lifecycle_metadata_from_skill_frontmatter(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_skill_dirs(monkeypatch, tmp_path)

    created = SkillService.create_skill(
        name="research",
        content="""---
name: research
description: Research skill
lifecycle_stage: trial
next_lifecycle_stage: rollout
replacement_target_ids:
  - skill:legacy_research
rollback_target_ids:
  - skill:legacy_research
target_agent_id: industry-solution-lead-demo
target_role_id: solution-lead
target_seat_ref: env-browser-primary
rollout_scope: single-seat
role_budget_limit: 12
seat_budget_limit: 4
---
# Research
""",
    )

    assert created is True

    service = CapabilitySkillService()
    skill = service.find_skill("research")
    metadata = service.read_skill_upgrade_metadata(skill)

    assert metadata["lifecycle_stage"] == "trial"
    assert metadata["next_lifecycle_stage"] == "rollout"
    assert metadata["replacement_target_ids"] == ["skill:legacy_research"]
    assert metadata["rollback_target_ids"] == ["skill:legacy_research"]
    assert metadata["target_agent_id"] == "industry-solution-lead-demo"
    assert metadata["target_role_id"] == "solution-lead"
    assert metadata["target_seat_ref"] == "env-browser-primary"
    assert metadata["rollout_scope"] == "single-seat"
    assert metadata["role_budget_limit"] == 12
    assert metadata["seat_budget_limit"] == 4


def test_skill_evolution_service_prefers_reuse_and_preserves_mcp_candidate_form() -> None:
    class _CandidateService:
        def list_candidates(self, *, limit: int | None = None):
            _ = limit
            return [
                SimpleNamespace(
                    candidate_id="cand-browser-reuse",
                    donor_id="donor-browser",
                    package_id="pkg-browser",
                    canonical_package_id="pkg:browser-runtime",
                    candidate_kind="mcp-bundle",
                    candidate_source_kind="external_catalog",
                    candidate_source_ref="registry://browser-runtime",
                    candidate_source_version="2026.04.04",
                    target_scope="seat",
                    target_role_id="operator",
                    target_seat_ref="seat-primary",
                    status="active",
                    lifecycle_stage="active",
                ),
            ]

    class _PackageService:
        def find_reusable_package(self, **kwargs):
            _ = kwargs
            return None

    service = SkillEvolutionService(
        candidate_service=_CandidateService(),
        donor_package_service=_PackageService(),
    )

    resolution = service.resolve_candidate_path(
        candidate_kind="mcp-bundle",
        candidate_source_kind="external_catalog",
        candidate_source_ref="registry://browser-runtime",
        candidate_source_version="2026.04.04",
        canonical_package_id="pkg:browser-runtime",
        target_scope="seat",
        target_role_id="operator",
        target_seat_ref="seat-primary",
        target_capability_ids=["mcp:browser_runtime"],
    )

    assert resolution["resolution_kind"] == "reuse_existing_candidate"
    assert resolution["selected_candidate_id"] == "cand-browser-reuse"
    assert resolution["package_form"] == "mcp-bundle"
    assert resolution["fallback_required"] is False


def test_skill_evolution_service_only_uses_local_fallback_when_no_donor_or_reuse_exists() -> None:
    class _CandidateService:
        def list_candidates(self, *, limit: int | None = None):
            _ = limit
            return []

    class _PackageService:
        def find_reusable_package(self, **kwargs):
            _ = kwargs
            return None

    service = SkillEvolutionService(
        candidate_service=_CandidateService(),
        donor_package_service=_PackageService(),
    )

    resolution = service.resolve_candidate_path(
        candidate_kind="skill",
        candidate_source_kind="local_authored",
        candidate_source_ref="local://industry/private-gap",
        candidate_source_version="draft-v1",
        canonical_package_id=None,
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        target_capability_ids=["skill:private_gap"],
    )

    assert resolution["resolution_kind"] == "author_local_fallback"
    assert resolution["selected_candidate_id"] is None
    assert resolution["selected_package_id"] is None
    assert resolution["fallback_required"] is True


def test_capability_skill_service_reads_metadata_summary_with_scoped_activation(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_skill_dirs(monkeypatch, tmp_path)

    created = SkillService.create_skill(
        name="seat_research",
        content="""---
name: seat_research
description: Seat-scoped research skill
package_ref: https://example.com/skills/seat-research.zip
package_kind: hub-bundle
package_version: 2.0.0
target_scope: seat
target_role_id: researcher
target_seat_ref: seat-primary
---
# Seat Research
""",
    )

    assert created is True

    service = CapabilitySkillService()
    skill = service.find_skill("seat_research")

    summary = service.read_skill_metadata_summary(skill)

    assert summary["package_ref"] == "https://example.com/skills/seat-research.zip"
    assert summary["package_kind"] == "hub-bundle"
    assert summary["package_version"] == "2.0.0"
    assert summary["canonical_skill_root"] == str(
        (tmp_path / "customized" / "seat_research").resolve()
    )
    assert summary["target_scope"] == "seat"
    assert summary["target_role_id"] == "researcher"
    assert summary["target_seat_ref"] == "seat-primary"
    assert summary["activation_scope_key"] == "seat:researcher:seat-primary"
    assert summary["path_scoped_activation"] is True
    assert summary["package_bound"] is True


def test_skill_service_list_all_skills_reuses_inventory_cache_when_unchanged(
    monkeypatch,
    tmp_path,
) -> None:
    builtin_dir, customized_dir, active_dir = _patch_skill_dirs(monkeypatch, tmp_path)
    _ = active_dir
    (builtin_dir / "builtin_skill").mkdir()
    (builtin_dir / "builtin_skill" / "SKILL.md").write_text(
        "---\nname: builtin_skill\ndescription: Builtin skill\n---\n# Builtin\n",
        encoding="utf-8",
    )
    (customized_dir / "custom_skill").mkdir()
    (customized_dir / "custom_skill" / "SKILL.md").write_text(
        "---\nname: custom_skill\ndescription: Custom skill\n---\n# Custom\n",
        encoding="utf-8",
    )

    with (
        patch.object(
            skill_service_module,
            "sync_skills_from_active_to_customized",
            return_value=(0, 0),
        ),
        patch.object(
            skill_service_module,
            "_read_skills_from_dir",
            wraps=skill_service_module._read_skills_from_dir,
        ) as wrapped_read_dir,
    ):
        first = SkillService.list_all_skills()
        second = SkillService.list_all_skills()

    assert [skill.name for skill in first] == [skill.name for skill in second]
    assert wrapped_read_dir.call_count == 2


def test_skill_service_list_all_skills_invalidates_cache_when_inventory_changes(
    monkeypatch,
    tmp_path,
) -> None:
    builtin_dir, customized_dir, active_dir = _patch_skill_dirs(monkeypatch, tmp_path)
    _ = active_dir
    (builtin_dir / "builtin_skill").mkdir()
    (builtin_dir / "builtin_skill" / "SKILL.md").write_text(
        "---\nname: builtin_skill\ndescription: Builtin skill\n---\n# Builtin\n",
        encoding="utf-8",
    )

    with patch.object(
        skill_service_module,
        "sync_skills_from_active_to_customized",
        return_value=(0, 0),
    ):
        first = SkillService.list_all_skills()
        (customized_dir / "custom_skill").mkdir()
        (customized_dir / "custom_skill" / "SKILL.md").write_text(
            "---\nname: custom_skill\ndescription: Custom skill\n---\n# Custom\n",
            encoding="utf-8",
        )
        second = SkillService.list_all_skills()

    assert [skill.name for skill in first] == ["builtin_skill"]
    assert [skill.name for skill in second] == ["builtin_skill", "custom_skill"]
