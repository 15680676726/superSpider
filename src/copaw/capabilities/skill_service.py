# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter

from ..agents.skills_hub import install_skill_from_hub as _install_skill_from_hub
from ..skill_service import (
    SkillService,
    SkillFrontmatterError,
    find_skill_package_identity_conflict,
    list_available_skills,
    parse_skill_frontmatter,
    sync_skills_to_working_dir as sync_skills_to_working_dir_fn,
)


def install_skill_from_hub(**kwargs: object) -> object:
    return _install_skill_from_hub(**kwargs)


def _normalize_text(value: object | None) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_package_kind(value: object | None) -> str:
    return _normalize_text(value).lower()


def _normalize_package_version(value: object | None) -> str:
    return _normalize_text(value)


def _skill_package_kind_from_ref(package_ref: str) -> str:
    normalized = _normalize_text(package_ref).lower()
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return "hub-bundle"
    if normalized:
        return "filesystem"
    return ""


def _normalize_package_ref(
    package_ref: object | None,
    *,
    package_kind: object | None = None,
) -> str:
    normalized = _normalize_text(package_ref)
    if not normalized:
        return ""
    normalized_kind = _normalize_package_kind(package_kind)
    if not normalized_kind:
        normalized_kind = _skill_package_kind_from_ref(normalized)
    if normalized_kind == "filesystem":
        try:
            return str(Path(normalized).expanduser().resolve())
        except Exception:
            return str(Path(normalized).expanduser())
    return normalized


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

    def _has_package_identity_conflict(
        self,
        *,
        skill_name: str,
        package_ref: str,
        package_kind: str,
        package_version: str,
    ) -> bool:
        candidate_identity = (
            package_ref,
            package_kind or None,
            package_version or None,
        )
        for existing_skill in self.list_all_skills():
            existing_name = _normalize_text(getattr(existing_skill, "name", None))
            if not existing_name or existing_name == skill_name:
                continue
            binding = self.read_skill_package_binding(existing_skill)
            existing_identity = (
                _normalize_package_ref(
                    binding.get("package_ref"),
                    package_kind=binding.get("package_kind"),
                ),
                _normalize_package_kind(binding.get("package_kind")) or None,
                _normalize_package_version(binding.get("package_version")) or None,
            )
            if existing_identity == candidate_identity:
                return True
        return False

    def read_skill_package_binding(self, skill: Any) -> dict[str, str | None]:
        content = getattr(skill, "content", "")
        package_ref = ""
        package_kind = ""
        package_version = ""
        if isinstance(content, str) and content.strip():
            try:
                post = parse_skill_frontmatter(content)
            except SkillFrontmatterError as exc:
                raise ValueError(str(exc)) from exc
            package_kind = _normalize_package_kind(post.get("package_kind"))
            package_ref = _normalize_package_ref(
                post.get("package_ref"),
                package_kind=package_kind,
            )
            package_version = _normalize_package_version(post.get("package_version"))
        if not package_ref:
            package_ref = _normalize_package_ref(
                getattr(skill, "path", None),
                package_kind="filesystem",
            )
        if not package_kind:
            package_kind = _skill_package_kind_from_ref(package_ref)
        return {
            "package_ref": package_ref or None,
            "package_kind": package_kind or None,
            "package_version": package_version or None,
        }

    def bind_skill_package_metadata(
        self,
        *,
        skill_name: str,
        package_ref: str,
        package_kind: str,
        package_version: str,
    ) -> bool:
        skill = self.find_skill(skill_name)
        if skill is None:
            return False
        skill_path = Path(str(getattr(skill, "path", "") or "")).expanduser()
        skill_md_path = skill_path / "SKILL.md"
        if not skill_md_path.exists():
            return False
        try:
            content = skill_md_path.read_text(encoding="utf-8")
            post = parse_skill_frontmatter(content)
        except Exception:
            return False
        normalized_package_kind = _normalize_package_kind(package_kind)
        normalized_package_ref = _normalize_package_ref(
            package_ref,
            package_kind=normalized_package_kind,
        )
        if not normalized_package_kind:
            normalized_package_kind = _skill_package_kind_from_ref(normalized_package_ref)
        conflict = find_skill_package_identity_conflict(
            skill_name=skill_name,
            package_identity=(
                normalized_package_ref,
                normalized_package_kind or None,
                _normalize_package_version(package_version) or None,
            ),
        )
        if conflict is not None or self._has_package_identity_conflict(
            skill_name=skill_name,
            package_ref=normalized_package_ref,
            package_kind=normalized_package_kind,
            package_version=_normalize_package_version(package_version),
        ):
            return False
        package_fields = {
            "package_ref": normalized_package_ref,
            "package_kind": normalized_package_kind,
            "package_version": _normalize_package_version(package_version),
        }
        for key, value in package_fields.items():
            if value:
                post[key] = value
            else:
                post.metadata.pop(key, None)
        skill_md_path.write_text(frontmatter.dumps(post), encoding="utf-8")
        return True

    def enable_skill(self, skill_name: str) -> None:
        SkillService.enable_skill(skill_name)

    def disable_skill(self, skill_name: str) -> None:
        SkillService.disable_skill(skill_name)

    def delete_skill(self, skill_name: str) -> bool:
        return SkillService.delete_skill(skill_name)

    def create_skill(self, **kwargs: object) -> object:
        return SkillService.create_skill(**kwargs)

    def install_skill_from_hub(self, **kwargs: object) -> object:
        result = install_skill_from_hub(**kwargs)
        skill_name = _normalize_text(getattr(result, "name", None))
        package_ref = _normalize_text(
            kwargs.get("bundle_url") or getattr(result, "source_url", None),
        )
        package_kind = _skill_package_kind_from_ref(package_ref)
        package_version = _normalize_text(kwargs.get("version"))
        if skill_name and package_ref:
            bound = self.bind_skill_package_metadata(
                skill_name=skill_name,
                package_ref=package_ref,
                package_kind=package_kind,
                package_version=package_version,
            )
            if not bound:
                raise RuntimeError(
                    f"Failed to bind package metadata for skill '{skill_name}'.",
                )
            for key, value in (
                ("package_ref", package_ref),
                ("package_kind", package_kind),
                ("package_version", package_version or None),
            ):
                try:
                    setattr(result, key, value)
                except Exception:
                    pass
        return result

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
