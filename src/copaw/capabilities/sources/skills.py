# -*- coding: utf-8 -*-
from __future__ import annotations

from threading import Lock

from ..skill_service import default_skill_service
from ..models import CapabilityMount

_SKILL_CAPABILITY_CACHE_LOCK = Lock()
_SKILL_CAPABILITY_CACHE: dict[int, tuple[object, tuple[CapabilityMount, ...]]] = {}


def build_skill_capabilities(skill_service: object) -> list[CapabilityMount]:
    cache_key = _skill_inventory_signature(skill_service)
    service_key = id(skill_service)
    if cache_key is not None:
        with _SKILL_CAPABILITY_CACHE_LOCK:
            cached = _SKILL_CAPABILITY_CACHE.get(service_key)
            if cached is not None and cached[0] == cache_key:
                return _clone_mounts(cached[1])

    enabled = set(skill_service.list_available_skill_names())
    mounts: list[CapabilityMount] = []
    for skill in skill_service.list_all_skills():
        environment_requirements: list[str] = []
        if skill.references:
            environment_requirements.append("workspace")
        if skill.scripts:
            environment_requirements.extend(["workspace", "file-view"])
        env_reqs = sorted(set(environment_requirements))

        has_scripts = bool(skill.scripts)
        has_refs = bool(skill.references)
        env_desc_parts: list[str] = []
        if has_refs:
            env_desc_parts.append("引用文件")
        if has_scripts:
            env_desc_parts.append("脚本")
        env_description = (
            f"需要工作目录来访问{'/'.join(env_desc_parts)}"
            if env_desc_parts
            else "无特殊环境要求"
        )

        summary = _skill_summary(skill.content)
        is_enabled = skill.name in enabled

        tags: list[str] = ["skill"]
        if has_scripts:
            tags.append("scripted")
        if has_refs:
            tags.append("referenced")

        evidence_contract = ["capability-call", "workspace-trace"]
        if has_scripts:
            evidence_contract.append("script-execution")

        mounts.append(
            CapabilityMount(
                id=f"skill:{skill.name}",
                name=skill.name,
                summary=summary,
                kind="skill-bundle",
                source_kind="skill",
                risk_level="guarded",
                risk_description="技能包可能执行脚本或访问外部资源",
                environment_requirements=env_reqs,
                environment_description=env_description,
                role_access_policy=["skill-enabled"] if is_enabled else ["skill-available"],
                evidence_contract=evidence_contract,
                evidence_description="记录技能调用和工作目录变更轨迹",
                executor_ref=skill.path,
                provider_ref=skill.source,
                replay_support=has_scripts,
                enabled=is_enabled,
                tags=tags,
                metadata={
                    "source": skill.source,
                    "references_count": len(skill.references or {}),
                    "scripts_count": len(skill.scripts or {}),
                },
            ),
        )
    mounts.sort(key=lambda item: item.id)
    if cache_key is not None:
        cached_mounts = tuple(mount.model_copy(deep=True) for mount in mounts)
        with _SKILL_CAPABILITY_CACHE_LOCK:
            _SKILL_CAPABILITY_CACHE[service_key] = (cache_key, cached_mounts)
        return _clone_mounts(cached_mounts)
    return mounts


def list_skill_capabilities() -> list[CapabilityMount]:
    return build_skill_capabilities(default_skill_service)


def _skill_summary(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return "Skill bundle"


def _skill_inventory_signature(skill_service: object) -> object | None:
    reader = getattr(skill_service, "list_inventory_signature", None)
    if not callable(reader):
        return None
    return reader()


def _clone_mounts(mounts: tuple[CapabilityMount, ...]) -> list[CapabilityMount]:
    return [mount.model_copy(deep=True) for mount in mounts]


__all__ = ["build_skill_capabilities", "list_skill_capabilities"]
