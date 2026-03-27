# -*- coding: utf-8 -*-
"""Automatic agent experience write-back into long-term memory."""
from __future__ import annotations

from typing import Any


class AgentExperienceMemoryService:
    """Write task outcomes back into agent-scoped long-term memory."""

    def __init__(self, *, knowledge_service: object | None) -> None:
        self._knowledge_service = knowledge_service

    def remember_outcome(
        self,
        *,
        agent_id: str,
        title: str,
        status: str,
        summary: str | None = None,
        error_summary: str | None = None,
        capability_ref: str | None = None,
        mailbox_id: str | None = None,
        task_id: str | None = None,
        source_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        industry_role_id: str | None = None,
        role_name: str | None = None,
        owner_scope: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> object | None:
        remember_fact = getattr(self._knowledge_service, "remember_fact", None)
        normalized_agent_id = str(agent_id).strip()
        normalized_title = str(title).strip()
        normalized_status = str(status).strip()
        if not callable(remember_fact) or not normalized_agent_id or not normalized_title:
            return None

        summary_text = str(summary or "").strip()
        error_text = str(error_summary or "").strip()
        capability_text = str(capability_ref or "").strip()
        mailbox_text = str(mailbox_id or "").strip()
        task_text = str(task_id or "").strip()
        source_agent_text = str(source_agent_id or "").strip()
        industry_text = str(industry_instance_id or "").strip()
        role_id_text = str(industry_role_id or "").strip()
        role_name_text = str(role_name or "").strip()
        owner_scope_text = str(owner_scope or "").strip()

        lines = [
            f"状态: {normalized_status}",
            f"任务标题: {normalized_title}",
        ]
        if summary_text:
            lines.append(f"结果摘要: {summary_text}")
        if error_text:
            lines.append(f"错误摘要: {error_text}")
        if capability_text:
            lines.append(f"能力引用: {capability_text}")
        if task_text:
            lines.append(f"任务ID: {task_text}")
        if mailbox_text:
            lines.append(f"邮箱ID: {mailbox_text}")
        if source_agent_text:
            lines.append(f"来源智能体: {source_agent_text}")
        if industry_text:
            lines.append(f"行业实例: {industry_text}")
        if role_id_text:
            lines.append(f"行业角色ID: {role_id_text}")
        if role_name_text:
            lines.append(f"角色名称: {role_name_text}")
        if owner_scope_text:
            lines.append(f"OwnerScope: {owner_scope_text}")
        if metadata:
            compact_metadata = {
                str(key): value
                for key, value in metadata.items()
                if value not in (None, "", [], {})
            }
            if compact_metadata:
                lines.append(f"附加上下文: {compact_metadata}")

        tags = ["memory", "experience", normalized_status]
        if capability_text:
            tags.append(f"capability:{capability_text}")
        if industry_text:
            tags.append(f"industry:{industry_text}")

        role_bindings = [role_id_text] if role_id_text else None
        source_ref = (
            f"actor-mailbox:{mailbox_text}"
            if mailbox_text
            else f"kernel-task:{task_text}"
            if task_text
            else None
        )
        experience_title = (
            f"{role_name_text or normalized_agent_id} {normalized_status}经验 / {normalized_title}"
        )
        agent_memory = remember_fact(
            title=experience_title,
            content="\n".join(lines).strip(),
            scope_type="agent",
            scope_id=normalized_agent_id,
            source_ref=source_ref,
            role_bindings=role_bindings,
            tags=tags,
        )
        task_memory = None
        if task_text:
            task_memory = remember_fact(
                title=f"{normalized_title} / task record",
                content="\n".join(lines).strip(),
                scope_type="task",
                scope_id=task_text,
                source_ref=source_ref,
                role_bindings=role_bindings,
                tags=[*tags, "task-memory"],
            )
        return agent_memory or task_memory
