# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from ..agents.skills_hub import install_skill_from_hub as _install_skill_from_hub
from ..skill_service import (
    SkillService,
    list_available_skills,
    sync_skills_to_working_dir as sync_skills_to_working_dir_fn,
)


def install_skill_from_hub(**kwargs: object) -> object:
    return _install_skill_from_hub(**kwargs)


class CapabilitySkillService:
    """Canonical skill service for the capability system.

    Delete condition:
    - hub install/create/load/sync are modeled in first-class state instead of
      filesystem-backed skill bundles
    - capability execution no longer needs SKILL.md/script/reference disk reads
    """

    def list_all_skills(self) -> list[Any]:
        return SkillService.list_all_skills()

    def list_available_skill_names(self) -> list[str]:
        return list_available_skills()

    def list_available_skills(self) -> list[Any]:
        return SkillService.list_available_skills()

    def find_skill(self, skill_name: str) -> Any | None:
        for skill in self.list_all_skills():
            if getattr(skill, "name", None) == skill_name:
                return skill
        return None

    def enable_skill(self, skill_name: str) -> None:
        SkillService.enable_skill(skill_name)

    def disable_skill(self, skill_name: str) -> None:
        SkillService.disable_skill(skill_name)

    def delete_skill(self, skill_name: str) -> bool:
        return SkillService.delete_skill(skill_name)

    def create_skill(self, **kwargs: object) -> object:
        return SkillService.create_skill(**kwargs)

    def install_skill_from_hub(self, **kwargs: object) -> object:
        return install_skill_from_hub(**kwargs)

    def load_skill_file(
        self,
        *,
        skill_name: str,
        file_path: str,
        source: str,
    ) -> str | None:
        return SkillService.load_skill_file(
            skill_name=skill_name,
            file_path=file_path,
            source=source,
        )

    def sync_to_working_dir(
        self,
        *,
        skill_names: list[str] | None = None,
        force: bool = False,
    ) -> tuple[int, int]:
        return sync_skills_to_working_dir_fn(
            skill_names=skill_names,
            force=force,
        )


default_skill_service = CapabilitySkillService()


__all__ = [
    "CapabilitySkillService",
    "default_skill_service",
    "install_skill_from_hub",
]
