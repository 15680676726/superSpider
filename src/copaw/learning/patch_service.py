# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from .models import Patch, PatchStatus
from .patch_runtime import LearningPatchRuntimeService
from .runtime_core import LearningRuntimeCore


class LearningPatchService:
    """Patch and strategy-cycle learning operations."""

    def __init__(self, core: LearningRuntimeCore) -> None:
        self._core = core
        self._runtime = LearningPatchRuntimeService(core)

    def should_run_strategy_cycle(
        self,
        *,
        limit: int | None = None,
        failure_threshold: int = 2,
    ) -> tuple[bool, str]:
        return self._runtime.should_run_strategy_cycle(
            limit=limit,
            failure_threshold=failure_threshold,
        )

    def list_patches(
        self,
        *,
        status: PatchStatus | str | None = None,
        goal_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        evidence_id: str | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Patch]:
        return self._runtime.list_patches(
            status=status,
            goal_id=goal_id,
            task_id=task_id,
            agent_id=agent_id,
            evidence_id=evidence_id,
            created_since=created_since,
            limit=limit,
        )

    def get_patch(self, patch_id: str) -> Patch:
        return self._runtime.get_patch(patch_id)

    def delete_patch(self, patch_id: str) -> bool:
        return self._runtime.delete_patch(patch_id)

    def create_patch(self, **kwargs) -> dict[str, object]:
        return self._runtime.create_patch(**kwargs)

    def approve_patch(self, patch_id: str, *, approved_by: str = "system") -> Patch:
        return self._runtime.approve_patch(patch_id, approved_by=approved_by)

    def reject_patch(self, patch_id: str, *, rejected_by: str = "system") -> Patch:
        return self._runtime.reject_patch(patch_id, rejected_by=rejected_by)

    def apply_patch(self, patch_id: str, *, applied_by: str = "system") -> Patch:
        return self._runtime.apply_patch(patch_id, applied_by=applied_by)

    def rollback_patch(
        self,
        patch_id: str,
        *,
        rolled_back_by: str = "system",
    ) -> Patch:
        return self._runtime.rollback_patch(
            patch_id,
            rolled_back_by=rolled_back_by,
        )

    def auto_apply_low_risk_patches(
        self,
        *,
        limit: int | None = None,
        max_items: int = 20,
        actor: str = "system",
    ) -> dict[str, object]:
        return self._runtime.auto_apply_low_risk_patches(
            limit=limit if limit is not None else max_items,
            actor=actor,
        )

    def run_strategy_cycle(
        self,
        *,
        actor: str = "copaw-main-brain",
        limit: int | None = None,
        auto_apply: bool = True,
        auto_rollback: bool = False,
        failure_threshold: int = 2,
        confirm_threshold: int = 6,
        max_proposals: int = 5,
    ) -> dict[str, object]:
        return self._runtime.run_strategy_cycle(
            actor=actor,
            limit=limit,
            auto_apply=auto_apply,
            auto_rollback=auto_rollback,
            failure_threshold=failure_threshold,
            confirm_threshold=confirm_threshold,
            max_proposals=max_proposals,
        )


__all__ = ["LearningPatchService"]
