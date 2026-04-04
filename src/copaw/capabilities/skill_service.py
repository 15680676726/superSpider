# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any, get_args

import frontmatter

from ..agents.skills_hub import install_skill_from_hub as _install_skill_from_hub
from .skill_evolution_service import SkillEvolutionService
from .remote_skill_contract import RemoteSkillLifecycleStage, RemoteSkillRolloutScope
from ..skill_service import (
    SkillService,
    SkillFrontmatterError,
    find_skill_package_identity_conflict,
    list_available_skills,
    parse_skill_frontmatter,
    sync_skills_to_working_dir as sync_skills_to_working_dir_fn,
)

_REMOTE_SKILL_LIFECYCLE_STAGES = set(get_args(RemoteSkillLifecycleStage))
_REMOTE_SKILL_ROLLOUT_SCOPES = set(get_args(RemoteSkillRolloutScope))
_INSTALL_FROM_HUB_KEYS = {
    "bundle_url",
    "version",
    "enable",
    "overwrite",
}
_SKILL_UPGRADE_METADATA_KEYS = (
    "lifecycle_stage",
    "next_lifecycle_stage",
    "replacement_target_ids",
    "rollback_target_ids",
    "target_agent_id",
    "target_role_id",
    "target_seat_ref",
    "rollout_scope",
    "role_budget_limit",
    "seat_budget_limit",
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

def _normalize_skill_root(skill: Any) -> str:
    return _normalize_package_ref(
        getattr(skill, "path", None),
        package_kind="filesystem",
    )


def _canonical_skill_package_binding(
    skill: Any,
    *,
    package_ref: object | None,
    package_kind: object | None,
    package_version: object | None,
) -> dict[str, str | None]:
    normalized_kind = _normalize_package_kind(package_kind)
    normalized_ref = _normalize_package_ref(
        package_ref,
        package_kind=normalized_kind,
    )
    if not normalized_ref:
        normalized_ref = _normalize_skill_root(skill)
    if not normalized_kind:
        normalized_kind = _skill_package_kind_from_ref(normalized_ref)
    if normalized_kind == "filesystem":
        normalized_ref = _normalize_skill_root(skill) or normalized_ref
    return {
        "package_ref": normalized_ref or None,
        "package_kind": normalized_kind or None,
        "package_version": _normalize_package_version(package_version) or None,
    }
def _normalize_optional_text(value: object | None) -> str | None:
    normalized = _normalize_text(value)
    return normalized or None


def _normalize_string_list(value: object | None) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        normalized = _normalize_text(item)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _normalize_upgrade_stage(
    value: object | None,
    *,
    field_name: str,
) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if lowered not in _REMOTE_SKILL_LIFECYCLE_STAGES:
        raise ValueError(f"Invalid {field_name}: {normalized}")
    return lowered


def _normalize_rollout_scope(value: object | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if lowered not in _REMOTE_SKILL_ROLLOUT_SCOPES:
        raise ValueError(f"Invalid rollout_scope: {normalized}")
    return lowered


def _normalize_optional_int(
    value: object | None,
    *,
    field_name: str,
) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}: {value}") from exc


def _normalize_skill_upgrade_metadata(
    **kwargs: object,
) -> dict[str, object]:
    return {
        "lifecycle_stage": _normalize_upgrade_stage(
            kwargs.get("lifecycle_stage"),
            field_name="lifecycle_stage",
        ),
        "next_lifecycle_stage": _normalize_upgrade_stage(
            kwargs.get("next_lifecycle_stage"),
            field_name="next_lifecycle_stage",
        ),
        "replacement_target_ids": _normalize_string_list(
            kwargs.get("replacement_target_ids"),
        ),
        "rollback_target_ids": _normalize_string_list(
            kwargs.get("rollback_target_ids"),
        ),
        "target_agent_id": _normalize_optional_text(kwargs.get("target_agent_id")),
        "target_role_id": _normalize_optional_text(kwargs.get("target_role_id")),
        "target_seat_ref": _normalize_optional_text(kwargs.get("target_seat_ref")),
        "rollout_scope": _normalize_rollout_scope(kwargs.get("rollout_scope")),
        "role_budget_limit": _normalize_optional_int(
            kwargs.get("role_budget_limit"),
            field_name="role_budget_limit",
        ),
        "seat_budget_limit": _normalize_optional_int(
            kwargs.get("seat_budget_limit"),
            field_name="seat_budget_limit",
        ),
    }


def _has_skill_upgrade_metadata(metadata: dict[str, object]) -> bool:
    for value in metadata.values():
        if isinstance(value, list):
            if value:
                return True
            continue
        if value is not None:
            return True
    return False
class CapabilitySkillService:
    """Canonical skill service for the capability system.

    Delete condition:
    - hub install/create/load/sync are modeled in first-class state instead of
      filesystem-backed skill bundles
    - capability execution no longer needs SKILL.md/script/reference disk reads
    """

    def __init__(
        self,
        *,
        skill_evolution_service: object | None = None,
        candidate_service: object | None = None,
        donor_package_service: object | None = None,
    ) -> None:
        self._skill_evolution_service = (
            skill_evolution_service
            if skill_evolution_service is not None
            else SkillEvolutionService(
                candidate_service=candidate_service,
                donor_package_service=donor_package_service,
            )
        )

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
        package_ref: object | None = None
        package_kind: object | None = None
        package_version: object | None = None
        if isinstance(content, str) and content.strip():
            try:
                post = parse_skill_frontmatter(content)
            except SkillFrontmatterError as exc:
                raise ValueError(str(exc)) from exc
            package_kind = post.get("package_kind")
            package_ref = post.get("package_ref")
            package_version = post.get("package_version")
        return _canonical_skill_package_binding(
            skill,
            package_ref=package_ref,
            package_kind=package_kind,
            package_version=package_version,
        )

    def read_skill_upgrade_metadata(self, skill: Any) -> dict[str, object]:
        content = getattr(skill, "content", "")
        if (not isinstance(content, str) or not content.strip()) and getattr(skill, "path", None):
            skill_md_path = Path(str(getattr(skill, "path", "") or "")).expanduser() / "SKILL.md"
            if skill_md_path.exists():
                content = skill_md_path.read_text(encoding="utf-8")
        if not isinstance(content, str) or not content.strip():
            return _normalize_skill_upgrade_metadata()
        try:
            post = parse_skill_frontmatter(content)
        except SkillFrontmatterError as exc:
            raise ValueError(str(exc)) from exc
        return _normalize_skill_upgrade_metadata(
            lifecycle_stage=post.get("lifecycle_stage"),
            next_lifecycle_stage=post.get("next_lifecycle_stage"),
            replacement_target_ids=post.get("replacement_target_ids"),
            rollback_target_ids=post.get("rollback_target_ids"),
            target_agent_id=post.get("target_agent_id"),
            target_role_id=post.get("target_role_id"),
            target_seat_ref=post.get("target_seat_ref"),
            rollout_scope=post.get("rollout_scope"),
            role_budget_limit=post.get("role_budget_limit"),
            seat_budget_limit=post.get("seat_budget_limit"),
        )

    def _resolve_skill_md_path(self, skill_name: str) -> Path | None:
        skill = self.find_skill(skill_name)
        if skill is None:
            return None
        skill_path = Path(str(getattr(skill, "path", "") or "")).expanduser()
        skill_md_path = skill_path / "SKILL.md"
        if not skill_md_path.exists():
            return None
        return skill_md_path

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
        skill_md_path = self._resolve_skill_md_path(skill_name)
        if skill_md_path is None:
            return False
        try:
            content = skill_md_path.read_text(encoding="utf-8")
            post = parse_skill_frontmatter(content)
        except Exception:
            return False
        binding = _canonical_skill_package_binding(
            skill,
            package_ref=package_ref,
            package_kind=package_kind,
            package_version=package_version,
        )
        normalized_package_ref = binding["package_ref"] or ""
        normalized_package_kind = binding["package_kind"] or ""
        normalized_package_version = binding["package_version"] or ""
        conflict = find_skill_package_identity_conflict(
            skill_name=skill_name,
            package_identity=(
                normalized_package_ref,
                normalized_package_kind or None,
                normalized_package_version or None,
            ),
        )
        if conflict is not None or self._has_package_identity_conflict(
            skill_name=skill_name,
            package_ref=normalized_package_ref,
            package_kind=normalized_package_kind,
            package_version=normalized_package_version,
        ):
            return False
        package_fields = {
            "package_ref": normalized_package_ref,
            "package_kind": normalized_package_kind,
            "package_version": normalized_package_version,
        }
        for key, value in package_fields.items():
            if value:
                post[key] = value
            else:
                post.metadata.pop(key, None)
        skill_md_path.write_text(frontmatter.dumps(post), encoding="utf-8")
        return True

    def bind_skill_upgrade_metadata(
        self,
        *,
        skill_name: str,
        **kwargs: object,
    ) -> bool:
        skill_md_path = self._resolve_skill_md_path(skill_name)
        if skill_md_path is None:
            return False
        try:
            content = skill_md_path.read_text(encoding="utf-8")
            post = parse_skill_frontmatter(content)
            metadata = _normalize_skill_upgrade_metadata(**kwargs)
        except Exception:
            return False
        for key, value in metadata.items():
            if isinstance(value, list):
                if value:
                    post[key] = list(value)
                else:
                    post.metadata.pop(key, None)
                continue
            if value is None:
                post.metadata.pop(key, None)
                continue
            post[key] = value
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

    def resolve_candidate_materialization(
        self,
        **kwargs: object,
    ) -> dict[str, object]:
        resolver = getattr(self, "_skill_evolution_service", None)
        resolve = getattr(resolver, "resolve_candidate_path", None)
        if not callable(resolve):
            return {
                "resolution_kind": "author_local_fallback",
                "fallback_required": True,
                "package_form": _normalize_package_kind(kwargs.get("candidate_kind")) or "skill",
            }
        return dict(resolve(**kwargs))

    def materialize_fallback_skill_artifact(
        self,
        *,
        candidate_kind: str,
        candidate_source_kind: str,
        candidate_source_ref: str | None,
        candidate_source_version: str | None,
        skill_name: str,
        content: str,
        canonical_package_id: str | None = None,
        target_scope: str = "seat",
        target_role_id: str | None = None,
        target_seat_ref: str | None = None,
        target_capability_ids: list[str] | None = None,
    ) -> dict[str, object]:
        resolution = self.resolve_candidate_materialization(
            candidate_kind=candidate_kind,
            candidate_source_kind=candidate_source_kind,
            candidate_source_ref=candidate_source_ref,
            candidate_source_version=candidate_source_version,
            canonical_package_id=canonical_package_id,
            target_scope=target_scope,
            target_role_id=target_role_id,
            target_seat_ref=target_seat_ref,
            target_capability_ids=target_capability_ids,
        )
        if not bool(resolution.get("fallback_required")):
            return {
                **resolution,
                "created": False,
            }
        created = SkillService.create_skill(
            name=skill_name,
            content=content,
            overwrite=False,
        )
        return {
            **resolution,
            "created": bool(created),
            "skill_name": skill_name,
        }

    def install_skill_from_hub(self, **kwargs: object) -> object:
        install_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key in _INSTALL_FROM_HUB_KEYS
        }
        upgrade_metadata = _normalize_skill_upgrade_metadata(
            **{
                key: kwargs.get(key)
                for key in _SKILL_UPGRADE_METADATA_KEYS
            },
        )
        result = install_skill_from_hub(**install_kwargs)
        skill_name = _normalize_text(getattr(result, "name", None))
        package_ref = _normalize_text(
            kwargs.get("bundle_url") or getattr(result, "source_url", None),
        )
        package_kind = _skill_package_kind_from_ref(package_ref)
        package_version = _normalize_text(kwargs.get("version"))
        skill_md_exists = bool(skill_name and self._resolve_skill_md_path(skill_name) is not None)
        if skill_name and package_ref:
            if skill_md_exists:
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
            for key, value in upgrade_metadata.items():
                try:
                    setattr(result, key, value)
                except Exception:
                    pass
        if skill_name and _has_skill_upgrade_metadata(upgrade_metadata):
            if skill_md_exists:
                bound = self.bind_skill_upgrade_metadata(
                    skill_name=skill_name,
                    **upgrade_metadata,
                )
                if not bound:
                    raise RuntimeError(
                        f"Failed to bind upgrade metadata for skill '{skill_name}'.",
                    )
            for key, value in upgrade_metadata.items():
                try:
                    setattr(
                        result,
                        key,
                        list(value) if isinstance(value, list) else value,
                    )
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
