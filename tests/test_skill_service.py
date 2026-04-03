from __future__ import annotations

from pathlib import Path

from copaw.capabilities.skill_service import CapabilitySkillService
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
