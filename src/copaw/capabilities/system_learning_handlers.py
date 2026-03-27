# -*- coding: utf-8 -*-
from __future__ import annotations


class SystemLearningCapabilityFacade:
    def __init__(self, *, learning_service: object | None = None) -> None:
        self._learning_service = learning_service

    def set_learning_service(self, learning_service: object | None) -> None:
        self._learning_service = learning_service

    def execute(
        self,
        capability_id: str,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if self._learning_service is None:
            return {"success": False, "error": "Learning service is not available"}

        default_actor = (
            "copaw-main-brain"
            if capability_id in {"system:run_learning_strategy", "system:auto_apply_patches"}
            else "system"
        )
        actor = str(
            resolved_payload.get("actor")
            or resolved_payload.get("applied_by")
            or default_actor,
        )

        if capability_id == "system:run_learning_strategy":
            limit = resolved_payload.get("limit")
            auto_apply = bool(resolved_payload.get("auto_apply", True))
            auto_rollback = bool(resolved_payload.get("auto_rollback", False))
            failure_threshold = resolved_payload.get("failure_threshold")
            confirm_threshold = resolved_payload.get("confirm_threshold")
            max_proposals = resolved_payload.get("max_proposals")
            return self._learning_service.run_strategy_cycle(
                actor=actor,
                limit=limit if isinstance(limit, int) else None,
                auto_apply=auto_apply,
                auto_rollback=auto_rollback,
                failure_threshold=(
                    int(failure_threshold) if isinstance(failure_threshold, int) else 2
                ),
                confirm_threshold=(
                    int(confirm_threshold) if isinstance(confirm_threshold, int) else 6
                ),
                max_proposals=(
                    int(max_proposals) if isinstance(max_proposals, int) else 5
                ),
            )

        if capability_id == "system:auto_apply_patches":
            limit = resolved_payload.get("limit")
            return self._learning_service.auto_apply_low_risk_patches(
                limit=limit if isinstance(limit, int) else None,
                actor=actor,
            )

        patch_id = str(resolved_payload.get("patch_id") or "")
        if not patch_id:
            return {"success": False, "error": "patch_id is required"}

        if capability_id == "system:apply_patch":
            patch = self._learning_service.apply_patch(
                patch_id,
                applied_by=actor,
            )
            return {
                "success": True,
                "summary": f"Applied patch '{patch_id}'.",
                "patch": patch.model_dump(mode="json"),
            }

        if capability_id == "system:approve_patch":
            patch = self._learning_service.approve_patch(
                patch_id,
                approved_by=actor,
            )
            return {
                "success": True,
                "summary": f"Approved patch '{patch_id}'.",
                "patch": patch.model_dump(mode="json"),
            }

        if capability_id == "system:reject_patch":
            patch = self._learning_service.reject_patch(
                patch_id,
                rejected_by=actor,
            )
            return {
                "success": True,
                "summary": f"Rejected patch '{patch_id}'.",
                "patch": patch.model_dump(mode="json"),
            }

        if capability_id == "system:rollback_patch":
            patch = self._learning_service.rollback_patch(
                patch_id,
                rolled_back_by=actor,
            )
            return {
                "success": True,
                "summary": f"Rolled back patch '{patch_id}'.",
                "patch": patch.model_dump(mode="json"),
            }

        return {
            "success": False,
            "error": f"Unsupported system capability '{capability_id}'",
        }
