# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from ..app.crons.models import CronJobSpec


class SystemScheduleCapabilityFacade:
    def __init__(self, *, cron_manager: object | None = None) -> None:
        self._cron_manager = cron_manager

    def set_cron_manager(self, cron_manager: object | None) -> None:
        self._cron_manager = cron_manager

    async def execute(
        self,
        capability_id: str,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        manager = self._cron_manager
        if manager is None:
            return {"success": False, "error": "Cron manager is not available"}

        if capability_id == "system:create_schedule":
            spec = self._resolve_job_spec(resolved_payload)
            if isinstance(spec, dict):
                return spec
            existing = await manager.get_job(spec.id)
            if existing is not None:
                return {
                    "success": False,
                    "error": f"Schedule '{spec.id}' already exists",
                    "error_code": "already_exists",
                }
            try:
                await manager.create_or_replace_job(spec)
            except Exception as exc:
                return {"success": False, "error": str(exc), "error_code": "invalid"}
            return {
                "success": True,
                "summary": f"Created schedule '{spec.id}'.",
                "job": spec.model_dump(mode="json"),
            }

        if capability_id == "system:update_schedule":
            schedule_id = self._normalize_id(resolved_payload.get("schedule_id"))
            spec = self._resolve_job_spec(resolved_payload)
            if isinstance(spec, dict):
                return spec
            if schedule_id is not None and spec.id != schedule_id:
                return {"success": False, "error": "schedule_id mismatch", "error_code": "invalid"}
            existing = await manager.get_job(spec.id)
            if existing is None:
                return {
                    "success": False,
                    "error": f"Schedule '{spec.id}' not found",
                    "error_code": "not_found",
                }
            try:
                await manager.create_or_replace_job(spec)
            except Exception as exc:
                return {"success": False, "error": str(exc), "error_code": "invalid"}
            return {
                "success": True,
                "summary": f"Updated schedule '{spec.id}'.",
                "job": spec.model_dump(mode="json"),
            }

        schedule_id = self._normalize_id(
            resolved_payload.get("schedule_id") or resolved_payload.get("job_id")
        )
        if schedule_id is None:
            return {"success": False, "error": "schedule_id is required", "error_code": "invalid"}
        existing = await manager.get_job(schedule_id)
        if existing is None:
            return {
                "success": False,
                "error": f"Schedule '{schedule_id}' not found",
                "error_code": "not_found",
            }

        if capability_id == "system:delete_schedule":
            deleted = await manager.delete_job(schedule_id)
            if not deleted:
                return {
                    "success": False,
                    "error": f"Schedule '{schedule_id}' not found",
                    "error_code": "not_found",
                }
            return {
                "success": True,
                "summary": f"Deleted schedule '{schedule_id}'.",
                "schedule_id": schedule_id,
            }

        try:
            if capability_id == "system:pause_schedule":
                await manager.pause_job(schedule_id)
                action = "Paused"
            elif capability_id == "system:resume_schedule":
                await manager.resume_job(schedule_id)
                action = "Resumed"
            elif capability_id == "system:run_schedule":
                await manager.run_job(schedule_id)
                action = "Started"
            else:
                return {
                    "success": False,
                    "error": f"Unsupported schedule capability '{capability_id}'",
                }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        refreshed = await manager.get_job(schedule_id)
        return {
            "success": True,
            "summary": f"{action} schedule '{schedule_id}'.",
            "job": refreshed.model_dump(mode="json") if refreshed is not None else None,
            "schedule_id": schedule_id,
        }

    def _resolve_job_spec(
        self,
        resolved_payload: dict[str, object],
    ) -> CronJobSpec | dict[str, object]:
        payload = (
            resolved_payload.get("job")
            or resolved_payload.get("schedule")
            or resolved_payload.get("spec")
            or resolved_payload
        )
        try:
            return CronJobSpec.model_validate(payload)
        except Exception as exc:
            return {"success": False, "error": str(exc), "error_code": "invalid"}

    @staticmethod
    def _normalize_id(value: object | None) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None
