# -*- coding: utf-8 -*-
"""Buddy current-focus resolver helpers."""
from __future__ import annotations

def build_buddy_current_focus_resolver(
    *,
    agent_profile_service: object,
    growth_target_repository: object,
    industry_instance_repository: object,
    assignment_service: object,
    backlog_service: object,
) -> object:
    def _single_next_action(summary: str) -> str:
        text = str(summary or "").strip()
        if not text:
            return ""
        return f"现在先完成这一步：{text}"

    def _resolve(profile_id: str) -> dict[str, str] | None:
        get_active_target = getattr(growth_target_repository, "get_active_target", None)
        target = get_active_target(profile_id) if callable(get_active_target) else None
        why_now = str(getattr(target, "why_it_matters", "") or "").strip() if target is not None else ""
        get_instance = getattr(industry_instance_repository, "get_instance", None)
        instance = get_instance(f"buddy:{profile_id}") if callable(get_instance) else None
        if instance is not None:
            list_assignments = getattr(assignment_service, "list_assignments", None)
            if callable(list_assignments):
                for assignment in list_assignments(
                    industry_instance_id=instance.instance_id,
                    cycle_id=getattr(instance, "current_cycle_id", None),
                    limit=20,
                ):
                    status = str(getattr(assignment, "status", "") or "").strip().lower()
                    if status in {"completed", "failed", "cancelled"}:
                        continue
                    summary = str(
                        getattr(assignment, "summary", None)
                        or getattr(assignment, "title", None)
                        or ""
                    ).strip()
                    if summary:
                        return {
                            "current_task_summary": summary,
                            "why_now_summary": why_now,
                            "single_next_action_summary": _single_next_action(summary),
                        }
            list_open_items = getattr(backlog_service, "list_open_items", None)
            if callable(list_open_items):
                for item in list_open_items(industry_instance_id=instance.instance_id, limit=20):
                    summary = str(
                        getattr(item, "summary", None)
                        or getattr(item, "title", None)
                        or ""
                    ).strip()
                    if summary:
                        return {
                            "current_task_summary": summary,
                            "why_now_summary": why_now,
                            "single_next_action_summary": _single_next_action(summary),
                        }
        return {"why_now_summary": why_now} if why_now else None

    return _resolve


__all__ = ["build_buddy_current_focus_resolver"]
