# -*- coding: utf-8 -*-
from __future__ import annotations

from ..skill_service import default_skill_service
from ..models import CapabilityMount


def build_skill_capabilities(skill_service: object) -> list[CapabilityMount]:
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
    return mounts


def list_skill_capabilities() -> list[CapabilityMount]:
    return build_skill_capabilities(default_skill_service)


def _skill_summary(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return "Skill bundle"


__all__ = ["build_skill_capabilities", "list_skill_capabilities"]
