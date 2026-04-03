from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import frontmatter
import pytest

from copaw.capabilities import CapabilityMount, CapabilityService, CapabilityRegistry
from copaw.capabilities.skill_service import CapabilitySkillService


class _StaticRegistry(CapabilityRegistry):
    def __init__(self, mounts: list[CapabilityMount]) -> None:
        self._mounts = mounts

    def list_capabilities(self) -> list[CapabilityMount]:
        return list(self._mounts)


class _FakeSkillService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def list_all_skills(self) -> list[object]:
        return [
            SimpleNamespace(
                name="research",
                content="# research",
                source="customized",
                path="/tmp/research",
                references={},
                scripts={},
            ),
        ]

    def list_available_skill_names(self) -> list[str]:
        return ["research"]

    def list_available_skills(self) -> list[object]:
        return self.list_all_skills()

    def find_skill(self, skill_name: str) -> object | None:
        for skill in self.list_all_skills():
            if skill.name == skill_name:
                return skill
        return None

    def read_skill_package_binding(self, skill: object) -> dict[str, str | None]:
        _ = skill
        return {
            "package_ref": None,
            "package_kind": None,
            "package_version": None,
        }

    def enable_skill(self, skill_name: str) -> None:
        self.calls.append(("enable", skill_name))

    def disable_skill(self, skill_name: str) -> None:
        self.calls.append(("disable", skill_name))

    def delete_skill(self, skill_name: str) -> bool:
        self.calls.append(("delete", skill_name))
        return True

    def create_skill(self, **kwargs: object) -> object:
        self.calls.append(("create", kwargs))
        return True

    def install_skill_from_hub(self, **kwargs: object) -> object:
        self.calls.append(("install", kwargs))
        return SimpleNamespace(
            name="research",
            enabled=True,
            source_url="https://example.com/research",
        )

    def load_skill_file(
        self,
        *,
        skill_name: str,
        file_path: str,
        source: str,
    ) -> str | None:
        self.calls.append(("load_file", (skill_name, file_path, source)))
        return "file-body"

    def sync_to_working_dir(
        self,
        *,
        skill_names: list[str] | None = None,
        force: bool = False,
    ) -> tuple[int, int]:
        self.calls.append(("sync", (skill_names, force)))
        return (1, 0)


def test_capability_service_skill_service_handles_skill_toggle_and_delete() -> None:
    skill_service = _FakeSkillService()
    service = CapabilityService(
        registry=_StaticRegistry(
            [
                CapabilityMount(
                    id="skill:research",
                    name="research",
                    summary="Research skill",
                    kind="skill-bundle",
                    source_kind="skill",
                    risk_level="guarded",
                    enabled=True,
                ),
            ],
        ),
        skill_service=skill_service,
    )

    toggle_result = service.set_capability_enabled("skill:research", enabled=False)
    delete_result = service.delete_capability("skill:research")

    assert toggle_result["enabled"] is False
    assert delete_result["deleted"] is True
    assert ("disable", "research") in skill_service.calls
    assert ("delete", "research") in skill_service.calls


def test_capability_service_skill_service_handles_file_load_and_sync() -> None:
    skill_service = _FakeSkillService()
    service = CapabilityService(skill_service=skill_service)

    content = service.load_skill_file(
        skill_name="research",
        file_path="references/brief.md",
        source="customized",
    )
    sync_result = service.sync_skills_to_working_dir(skill_names=["research"])

    assert content == "file-body"
    assert sync_result == (1, 0)
    assert ("load_file", ("research", "references/brief.md", "customized")) in skill_service.calls
    assert ("sync", (["research"], False)) in skill_service.calls


def test_capability_skill_service_install_hub_skill_persists_package_binding(
    monkeypatch,
    tmp_path,
) -> None:
    skill_dir = tmp_path / "research"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: research
description: Research skill
---
# Research
""",
        encoding="utf-8",
    )
    skill = SimpleNamespace(
        name="research",
        content=skill_md.read_text(encoding="utf-8"),
        source="customized",
        path=str(skill_dir),
        references={},
        scripts={},
    )

    monkeypatch.setattr(
        "copaw.capabilities.skill_service.install_skill_from_hub",
        lambda **_kwargs: SimpleNamespace(
            name="research",
            enabled=True,
            source_url="https://example.com/research-pack.zip",
        ),
    )

    service = CapabilitySkillService()
    monkeypatch.setattr(
        service,
        "find_skill",
        lambda skill_name: skill if skill_name == "research" else None,
    )

    result = service.install_skill_from_hub(
        bundle_url="https://example.com/research-pack.zip",
        version="1.2.3",
        enable=True,
    )
    updated = skill_md.read_text(encoding="utf-8")

    assert getattr(result, "source_url") == "https://example.com/research-pack.zip"
    assert "package_ref: https://example.com/research-pack.zip" in updated
    assert "package_kind: hub-bundle" in updated
    assert "package_version: 1.2.3" in updated


def test_capability_skill_service_bind_skill_package_metadata_canonicalizes_filesystem_binding(
    monkeypatch,
    tmp_path,
) -> None:
    skill_dir = tmp_path / "skills" / "research"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: research
description: Research skill
---
# Research
""",
        encoding="utf-8",
    )
    skill = SimpleNamespace(
        name="research",
        content=skill_md.read_text(encoding="utf-8"),
        source="customized",
        path=str(skill_dir),
        references={},
        scripts={},
    )
    non_canonical_ref = str(skill_dir.parent / "nested" / ".." / "research")

    service = CapabilitySkillService()
    monkeypatch.setattr(
        service,
        "find_skill",
        lambda skill_name: skill if skill_name == "research" else None,
    )

    assert (
        service.bind_skill_package_metadata(
            skill_name="research",
            package_ref=non_canonical_ref,
            package_kind=" Filesystem ",
            package_version=" 2026.04 ",
        )
        is True
    )

    updated = frontmatter.loads(skill_md.read_text(encoding="utf-8"))

    assert updated["package_ref"] == str(Path(non_canonical_ref).resolve())
    assert updated["package_kind"] == "filesystem"
    assert str(updated["package_version"]) == "2026.04"


def test_capability_skill_service_read_skill_package_binding_rejects_invalid_frontmatter() -> None:
    service = CapabilitySkillService()
    skill = SimpleNamespace(
        name="broken",
        content="---\nname: [broken\n---\n# Broken\n",
        source="customized",
        path="/tmp/broken",
        references={},
        scripts={},
    )

    try:
        service.read_skill_package_binding(skill)
    except ValueError as exc:
        assert "front matter" in str(exc).lower() or "frontmatter" in str(exc).lower()
    else:
        raise AssertionError("Expected invalid frontmatter to be rejected")


def test_capability_skill_service_bind_skill_package_metadata_rejects_duplicate_identity(
    monkeypatch,
    tmp_path,
) -> None:
    target_dir = tmp_path / "skills" / "target"
    target_dir.mkdir(parents=True)
    target_md = target_dir / "SKILL.md"
    target_md.write_text(
        """---
name: target
description: Target skill
---
# Target
""",
        encoding="utf-8",
    )
    existing_dir = tmp_path / "skills" / "existing"
    existing_dir.mkdir(parents=True)
    existing_md = existing_dir / "SKILL.md"
    existing_md.write_text(
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
    target_skill = SimpleNamespace(
        name="target",
        content=target_md.read_text(encoding="utf-8"),
        source="customized",
        path=str(target_dir),
        references={},
        scripts={},
    )
    existing_skill = SimpleNamespace(
        name="existing",
        content=existing_md.read_text(encoding="utf-8"),
        source="customized",
        path=str(existing_dir),
        references={},
        scripts={},
    )
    service = CapabilitySkillService()
    monkeypatch.setattr(
        service,
        "find_skill",
        lambda skill_name: target_skill if skill_name == "target" else None,
    )
    monkeypatch.setattr(
        service,
        "list_all_skills",
        lambda: [target_skill, existing_skill],
    )

    assert (
        service.bind_skill_package_metadata(
            skill_name="target",
            package_ref="https://github.com/acme/skills/tree/main/research",
            package_kind="hub-bundle",
            package_version="1.0.0",
        )
        is False
    )

    updated = frontmatter.loads(target_md.read_text(encoding="utf-8"))
    assert updated.get("package_ref") is None


def test_capability_skill_service_read_binding_rejects_invalid_frontmatter() -> None:
    service = CapabilitySkillService()
    skill = SimpleNamespace(
        name="broken",
        content="---\nname: broken\n: broken\n---\nbody\n",
        source="customized",
        path="/tmp/broken",
        references={},
        scripts={},
    )

    with pytest.raises(ValueError, match="Front Matter|front matter|description"):
        service.read_skill_package_binding(skill)


def test_capability_skill_service_read_skill_package_binding_reanchors_filesystem_identity(
    tmp_path,
) -> None:
    skill_dir = tmp_path / "skills" / "research"
    skill_dir.mkdir(parents=True)
    escaped_ref = str(tmp_path / "other-skill")
    skill = SimpleNamespace(
        name="research",
        content=(
            "---\n"
            "name: research\n"
            "description: Research skill\n"
            f"package_ref: {escaped_ref}\n"
            "package_kind: filesystem\n"
            "package_version: 2026.04\n"
            "---\n"
            "# Research\n"
        ),
        source="customized",
        path=str(skill_dir),
        references={},
        scripts={},
    )

    binding = CapabilitySkillService().read_skill_package_binding(skill)

    assert binding == {
        "package_ref": str(skill_dir.resolve()),
        "package_kind": "filesystem",
        "package_version": "2026.04",
    }
