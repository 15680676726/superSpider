# -*- coding: utf-8 -*-
from __future__ import annotations

from ..routines import RoutineReplayRequest
from ..sop_kernel import FixedSopRunRequest
from .execution_support import _string_value


def _bool_value(value: object | None) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


class SystemRoutineCapabilityFacade:
    def __init__(
        self,
        *,
        routine_service: object | None = None,
        fixed_sop_service: object | None = None,
    ) -> None:
        self._routine_service = routine_service
        self._fixed_sop_service = fixed_sop_service

    def set_routine_service(self, routine_service: object | None) -> None:
        self._routine_service = routine_service

    def set_fixed_sop_service(self, fixed_sop_service: object | None) -> None:
        self._fixed_sop_service = fixed_sop_service

    async def handle_replay_routine(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if self._routine_service is None:
            return {"success": False, "error": "Routine service is not available"}

        replay = getattr(self._routine_service, "replay_routine", None)
        if not callable(replay):
            return {
                "success": False,
                "error": "Routine service cannot replay routines",
            }

        routine_id = _string_value(resolved_payload.get("routine_id"))
        if not routine_id:
            return {"success": False, "error": "routine_id is required"}

        input_payload = resolved_payload.get("input_payload")
        if not isinstance(input_payload, dict):
            input_payload = {}
        request_context = resolved_payload.get("request_context")
        if not isinstance(request_context, dict):
            request_context = {}
        metadata = resolved_payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        payload = RoutineReplayRequest(
            source_type=_string_value(resolved_payload.get("source_type")) or "goal-task",
            source_ref=(
                _string_value(resolved_payload.get("source_ref"))
                or _string_value(resolved_payload.get("goal_id"))
                or _string_value(resolved_payload.get("task_id"))
            ),
            input_payload=dict(input_payload),
            owner_agent_id=_string_value(resolved_payload.get("owner_agent_id")),
            owner_scope=_string_value(resolved_payload.get("owner_scope")),
            session_id=_string_value(resolved_payload.get("session_id")),
            request_context=dict(request_context),
            metadata=dict(metadata),
        )

        response = await replay(routine_id, payload)
        run = response.run
        success = run.status == "completed"
        summary = (
            run.output_summary
            or (
                f"Routine '{routine_id}' replay completed."
                if success
                else f"Routine '{routine_id}' replay ended with status '{run.status}'."
            )
        )
        return {
            "success": success,
            "summary": summary,
            "error": None if success else summary,
            "output": {
                "routine_id": routine_id,
                "routine_run_id": run.id,
                "routine_status": run.status,
                "routine_result": run.deterministic_result,
                "routine_failure_class": run.failure_class,
                "routine_fallback_mode": run.fallback_mode,
                "routine_fallback_task_id": run.fallback_task_id,
                "routine_evidence_ids": list(run.evidence_ids or []),
                "routine_routes": dict(response.routes or {}),
            },
            "evidence_metadata": {
                "routine_id": routine_id,
                "routine_run_id": run.id,
                "routine_status": run.status,
                "routine_result": run.deterministic_result,
                "routine_failure_class": run.failure_class,
                "routine_fallback_mode": run.fallback_mode,
                "routine_fallback_task_id": run.fallback_task_id,
                "routine_evidence_ids": list(run.evidence_ids or []),
            },
        }

    async def handle_run_fixed_sop(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if self._fixed_sop_service is None:
            return {
                "success": False,
                "error": "Fixed SOP service is not available",
            }

        trigger = getattr(self._fixed_sop_service, "run_binding", None)
        if not callable(trigger):
            return {
                "success": False,
                "error": "Fixed SOP service cannot run bindings",
            }

        binding_id = _string_value(resolved_payload.get("binding_id"))
        if not binding_id:
            return {"success": False, "error": "binding_id is required"}

        input_payload = resolved_payload.get("input_payload")
        if not isinstance(input_payload, dict):
            input_payload = {}
        metadata = resolved_payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        payload = FixedSopRunRequest(
            input_payload=dict(input_payload),
            workflow_run_id=_string_value(resolved_payload.get("workflow_run_id")),
            owner_agent_id=_string_value(resolved_payload.get("owner_agent_id")),
            owner_scope=_string_value(resolved_payload.get("owner_scope")),
            dry_run=_bool_value(resolved_payload.get("dry_run")),
            metadata=dict(metadata),
        )

        response = await trigger(binding_id, payload)
        success = response.status == "success"
        summary = (
            response.summary
            or (
                f"Fixed SOP binding '{binding_id}' executed successfully."
                if success
                else f"Fixed SOP binding '{binding_id}' execution failed."
            )
        )
        return {
            "success": success,
            "summary": summary,
            "error": None if success else summary,
            "output": {
                "binding_id": binding_id,
                "workflow_run_id": response.workflow_run_id,
                "evidence_id": response.evidence_id,
                "routes": dict(response.routes or {}),
            },
            "evidence_metadata": {
                "fixed_sop_binding_id": binding_id,
                "workflow_run_id": response.workflow_run_id,
                "fixed_sop_run_id": response.workflow_run_id,
                "fixed_sop_evidence_id": response.evidence_id,
            },
        }
