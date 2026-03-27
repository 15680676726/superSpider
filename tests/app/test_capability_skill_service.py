from __future__ import annotations

from types import SimpleNamespace

from copaw.capabilities import CapabilityMount, CapabilityService, CapabilityRegistry


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
