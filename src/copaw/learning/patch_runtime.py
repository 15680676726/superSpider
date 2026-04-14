# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from ..state import DecisionRequestRecord
from .models import GrowthEvent, Patch, PatchStatus, Proposal
from .runtime_support import (
    LearningRuntimeDelegate,
    _MAIN_BRAIN_ACTOR,
    _parse_strategy_metadata,
    _patch_matches,
    _resolve_growth_agent_id,
    _strategy_target_layer,
)


class LearningPatchRuntimeService(LearningRuntimeDelegate):
    """Patch and strategy-cycle entrypoints extracted from the runtime core."""

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
        patches = self._engine.list_patches(
            status=status,
            created_since=created_since,
            limit=limit,
        )
        return [
            patch
            for patch in patches
            if _patch_matches(
                patch,
                goal_id=goal_id,
                task_id=task_id,
                agent_id=agent_id,
                evidence_id=evidence_id,
            )
        ]

    def get_patch(self, patch_id: str) -> Patch:
        return self._engine.get_patch(patch_id)

    def delete_patch(self, patch_id: str) -> bool:
        deleted = self._engine.delete_patch(patch_id)
        if deleted:
            self._publish_runtime_event(
                topic="patch",
                action="deleted",
                payload={"patch_id": patch_id},
            )
        return deleted

    def create_patch(
        self,
        *,
        kind: str,
        title: str,
        description: str,
        goal_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        workflow_template_id: str | None = None,
        workflow_run_id: str | None = None,
        workflow_step_id: str | None = None,
        diff_summary: str = "",
        patch_payload: dict[str, object] | None = None,
        proposal_id: str | None = None,
        evidence_refs: list[str] | None = None,
        source_evidence_id: str | None = None,
        risk_level: str = "auto",
        auto_apply: bool = False,
    ) -> dict[str, object]:
        resolved_links = self._resolve_learning_context(
            goal_id=goal_id,
            task_id=task_id,
            agent_id=agent_id,
            source_evidence_id=source_evidence_id,
            evidence_refs=evidence_refs or [],
        )
        patch = Patch(
            kind=kind,  # type: ignore[arg-type]
            proposal_id=proposal_id,
            goal_id=resolved_links["goal_id"],
            task_id=resolved_links["task_id"],
            agent_id=resolved_links["agent_id"],
            workflow_template_id=workflow_template_id,
            workflow_run_id=workflow_run_id,
            workflow_step_id=workflow_step_id,
            title=title,
            description=description,
            diff_summary=diff_summary,
            patch_payload=dict(patch_payload or {}),
            evidence_refs=resolved_links["evidence_refs"],
            source_evidence_id=resolved_links["source_evidence_id"],
            risk_level=risk_level,
        )
        patch = self._engine.create_patch(patch=patch)
        self._publish_runtime_event(
            topic="patch",
            action="created",
            payload={
                "patch_id": patch.id,
                "goal_id": patch.goal_id,
                "task_id": patch.task_id,
                "agent_id": patch.agent_id,
                "status": patch.status,
                "risk_level": patch.risk_level,
            },
        )
        decision_request: DecisionRequestRecord | None = None
        if patch.risk_level == "confirm":
            decision_request = self._ensure_patch_decision(patch)
        else:
            patch = self._ensure_main_brain_patch_adjudication(patch)

        applied_patch: Patch | None = None
        if auto_apply and patch.risk_level in {"auto", "guarded"}:
            applied_patch = self.apply_patch(
                patch.id,
                applied_by="learning:auto-apply",
            )
            patch = applied_patch

        return {
            "patch": patch,
            "decision_request": decision_request,
            "auto_applied": applied_patch is not None,
            "applied_patch": applied_patch,
        }

    def should_run_strategy_cycle(
        self,
        *,
        limit: int | None = None,
        failure_threshold: int = 2,
    ) -> tuple[bool, str]:
        if self._evidence_ledger is None:
            return (False, "evidence-ledger-unavailable")

        recent = self._collect_recent_evidence(limit=limit)
        if not recent:
            return (False, "no-recent-evidence")

        failure_groups = self._summarize_failures(recent)
        if not failure_groups:
            return (False, "no-failure-signals")

        existing_titles = {
            proposal.title
            for proposal in self._engine.list_proposals()
            if proposal.status in {"open", "accepted"}
        }
        for capability_ref, bucket in failure_groups.items():
            if int(bucket.get("count", 0) or 0) < failure_threshold:
                continue
            title = f"Reduce failure rate for {capability_ref}"
            if title in existing_titles:
                continue
            return (True, "actionable-failure-pattern")
        return (False, "no-actionable-failure-pattern")

    def approve_patch(self, patch_id: str, *, approved_by: str = "system") -> Patch:
        patch = self._engine.approve_patch(patch_id)
        resolution = f"Approved by {approved_by}."
        self._resolve_patch_decision(
            patch_id,
            status="approved",
            resolution=resolution,
        )
        self._record_patch_decision_if_missing(
            patch,
            status="approved",
            resolution=resolution,
            decision_type="patch-approval",
            requested_by=approved_by,
        )
        self._append_patch_evidence(
            patch,
            actor=approved_by,
            action="patch-approved",
            result=f"Approved patch {patch.title}.",
        )
        self._publish_runtime_event(
            topic="patch",
            action="approved",
            payload={"patch_id": patch.id, "status": patch.status},
        )
        return patch

    def reject_patch(self, patch_id: str, *, rejected_by: str = "system") -> Patch:
        patch = self._engine.reject_patch(patch_id)
        resolution = f"Rejected by {rejected_by}."
        self._resolve_patch_decision(
            patch_id,
            status="rejected",
            resolution=resolution,
        )
        self._record_patch_decision_if_missing(
            patch,
            status="rejected",
            resolution=resolution,
            decision_type="patch-rejection",
            requested_by=rejected_by,
        )
        self._append_patch_evidence(
            patch,
            actor=rejected_by,
            action="patch-rejected",
            result=f"Rejected patch {patch.title}.",
        )
        self._publish_runtime_event(
            topic="patch",
            action="rejected",
            payload={"patch_id": patch.id, "status": patch.status},
        )
        return patch

    def apply_patch(self, patch_id: str, *, applied_by: str = "system") -> Patch:
        patch = self._engine.get_patch(patch_id)
        patch = self._ensure_main_brain_patch_adjudication(patch)
        if patch.risk_level == "confirm" and patch.status == "proposed":
            raise ValueError(
                f"Patch {patch_id} requires approval before apply because risk_level=confirm.",
            )
        execution = self._patch_executor.apply(patch, actor=applied_by)
        if not execution.get("success", False):
            self._append_patch_evidence(
                patch,
                actor=applied_by,
                action="patch-apply-failed",
                result=execution.get("summary") or "Patch apply failed.",
                status="failed",
                metadata={"execution": execution},
            )
            raise RuntimeError(
                execution.get("error") or execution.get("summary") or "Patch apply failed.",
            )

        patch = self._engine.apply_patch(patch_id, applied_by=applied_by)
        resolution = f"Applied by {applied_by}."
        self._resolve_patch_decision(
            patch_id,
            status="approved",
            resolution=resolution,
        )
        self._record_patch_decision_if_missing(
            patch,
            status="approved",
            resolution=resolution,
            decision_type="patch-apply",
            requested_by=applied_by,
        )
        self._engine.record_growth(
            GrowthEvent(
                agent_id=_resolve_growth_agent_id(
                    patch,
                    execution=execution,
                    fallback=patch.applied_by or "copaw-agent-runner",
                ),
                goal_id=patch.goal_id,
                task_id=patch.task_id,
                change_type="patch_applied",
                description=f"Applied patch {patch.title}",
                source_patch_id=patch.id,
                source_evidence_id=patch.source_evidence_id,
                risk_level=patch.risk_level,
                result="applied",
            ),
        )
        self._append_patch_evidence(
            patch,
            actor=applied_by,
            action="patch-applied",
            result=f"Applied patch {patch.title}.",
            metadata={"execution": execution},
        )
        self._publish_runtime_event(
            topic="patch",
            action="applied",
            payload={"patch_id": patch.id, "status": patch.status},
        )
        self._publish_runtime_event(
            topic="growth",
            action="recorded",
            payload={
                "patch_id": patch.id,
                "goal_id": patch.goal_id,
                "task_id": patch.task_id,
                "agent_id": patch.agent_id,
            },
        )
        return patch

    def rollback_patch(self, patch_id: str, *, rolled_back_by: str = "system") -> Patch:
        patch = self._engine.get_patch(patch_id)
        execution = self._patch_executor.rollback(patch, actor=rolled_back_by)
        if not execution.get("success", False):
            self._append_patch_evidence(
                patch,
                actor=rolled_back_by,
                action="patch-rollback-failed",
                result=execution.get("summary") or "Patch rollback failed.",
                status="failed",
                metadata={"execution": execution},
            )
            raise RuntimeError(
                execution.get("error")
                or execution.get("summary")
                or "Patch rollback failed.",
            )
        patch = self._engine.rollback_patch(patch_id)
        resolution = f"Rolled back by {rolled_back_by}."
        self._resolve_patch_decision(
            patch_id,
            status="rejected",
            resolution=resolution,
        )
        self._record_patch_decision_if_missing(
            patch,
            status="rejected",
            resolution=resolution,
            decision_type="patch-rollback",
            requested_by=rolled_back_by,
        )
        self._append_patch_evidence(
            patch,
            actor=rolled_back_by,
            action="patch-rolled-back",
            result=f"Rolled back patch {patch.title}.",
            metadata={"execution": execution},
        )
        self._publish_runtime_event(
            topic="patch",
            action="rolled-back",
            payload={"patch_id": patch.id, "status": patch.status},
        )
        return patch

    def auto_apply_low_risk_patches(
        self,
        *,
        limit: int | None = None,
        actor: str = _MAIN_BRAIN_ACTOR,
    ) -> dict[str, object]:
        candidates = [
            patch
            for patch in self._engine.list_patches()
            if patch.status in {"proposed", "approved"}
            and patch.risk_level in {"auto", "guarded"}
        ]
        if limit is not None:
            candidates = candidates[: max(0, limit)]

        applied: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []
        for patch in candidates:
            try:
                self.apply_patch(patch.id, applied_by=actor)
                applied.append(patch.id)
            except Exception as exc:  # pragma: no cover - guardrail
                errors.append(f"{patch.id}: {exc}")
                skipped.append(patch.id)

        return {
            "success": True,
            "summary": f"Auto-applied {len(applied)} patches.",
            "applied": applied,
            "skipped": skipped,
            "errors": errors,
        }

    def run_strategy_cycle(
        self,
        *,
        actor: str = _MAIN_BRAIN_ACTOR,
        limit: int | None = None,
        auto_apply: bool = True,
        auto_rollback: bool = False,
        failure_threshold: int = 2,
        confirm_threshold: int = 6,
        max_proposals: int = 5,
    ) -> dict[str, object]:
        if self._evidence_ledger is None:
            return {
                "success": False,
                "summary": "Evidence ledger is unavailable, strategy cycle skipped.",
                "proposals": [],
                "patches": [],
                "auto_applied": [],
                "auto_rolled_back": [],
                "decisions": [],
            }

        recent = self._collect_recent_evidence(limit=limit)
        failure_groups = self._summarize_failures(recent)
        existing_titles = {
            proposal.title
            for proposal in self._engine.list_proposals()
            if proposal.status in {"open", "accepted"}
        }

        created_proposals: list[Proposal] = []
        created_patches: list[Patch] = []
        auto_applied: list[str] = []
        auto_rolled_back: list[str] = []
        decisions: list[DecisionRequestRecord] = []

        for capability_ref, bucket in failure_groups.items():
            if len(created_proposals) >= max_proposals:
                break
            if bucket["count"] < failure_threshold:
                continue
            title = f"Reduce failure rate for {capability_ref}"
            if title in existing_titles:
                continue
            description = (
                f"Observed {bucket['count']} recent failures for {capability_ref}. "
                f"Examples: {', '.join(bucket['samples']) or 'n/a'}."
            )
            proposal = self.create_proposal(
                title=title,
                description=description,
                source_agent_id=actor,
                target_layer=_strategy_target_layer(capability_ref),
                evidence_refs=bucket["evidence_ids"],
            )
            created_proposals.append(proposal)
            existing_titles.add(title)

            risk_level = self._risk_from_failure_count(
                bucket["count"],
                failure_threshold=failure_threshold,
                confirm_threshold=confirm_threshold,
            )
            diff_summary = (
                "strategy=auto; "
                f"upgrade_surface={_strategy_target_layer(capability_ref)}; "
                f"target_capability={capability_ref}; "
                f"failure_count={bucket['count']}"
            )
            patch_result = self.create_patch(
                kind="capability_patch",
                title=f"Stabilize {capability_ref}",
                description=(
                    f"Apply a capability patch to reduce recent failures on {capability_ref}."
                ),
                diff_summary=diff_summary,
                proposal_id=proposal.id,
                evidence_refs=bucket["evidence_ids"],
                source_evidence_id=bucket["evidence_ids"][0]
                if bucket["evidence_ids"]
                else None,
                risk_level=risk_level,
                auto_apply=auto_apply,
            )
            patch = (
                patch_result.get("applied_patch")
                if patch_result.get("auto_applied")
                else patch_result.get("patch")
            )
            if isinstance(patch, Patch):
                created_patches.append(patch)
                if patch_result.get("auto_applied"):
                    auto_applied.append(patch.id)
                    decision = self._record_patch_decision_if_missing(
                        patch,
                        status="approved",
                        resolution=f"Auto-applied by {actor}.",
                        decision_type="patch-auto-apply",
                        requested_by=actor,
                    )
                    if decision is not None:
                        decisions.append(decision)

        if auto_rollback and failure_groups:
            for patch in self._engine.list_patches(status="applied"):
                metadata = _parse_strategy_metadata(patch.diff_summary)
                if metadata.get("strategy") != "auto":
                    continue
                target_cap = metadata.get("target_capability")
                if not target_cap:
                    continue
                failures = failure_groups.get(target_cap, {}).get("count", 0)
                if failures < confirm_threshold:
                    continue
                try:
                    rolled = self.rollback_patch(patch.id, rolled_back_by=actor)
                except Exception:  # pragma: no cover - guardrail
                    continue
                auto_rolled_back.append(rolled.id)
                decision = self._record_patch_decision_if_missing(
                    rolled,
                    status="rejected",
                    resolution=f"Auto-rolled-back by {actor}.",
                    decision_type="patch-auto-rollback",
                    requested_by=actor,
                )
                if decision is not None:
                    decisions.append(decision)

        result = {
            "success": True,
            "summary": (
                f"Created {len(created_proposals)} proposals; "
                f"{len(created_patches)} patches; "
                f"auto-applied {len(auto_applied)}; "
                f"auto-rolled-back {len(auto_rolled_back)}."
            ),
            "observed_failures": {
                cap: info["count"] for cap, info in failure_groups.items()
            },
            "proposals_created": len(created_proposals),
            "patches_created": len(created_patches),
            "auto_applied": auto_applied,
            "auto_rolled_back": auto_rolled_back,
            "proposals": [p.model_dump(mode="json") for p in created_proposals],
            "patches": [p.model_dump(mode="json") for p in created_patches],
            "decisions": [d.model_dump(mode="json") for d in decisions],
        }
        self._publish_runtime_event(
            topic="learning",
            action="strategy",
            payload={
                "proposals_created": result["proposals_created"],
                "patches_created": result["patches_created"],
                "auto_applied": len(auto_applied),
                "auto_rolled_back": len(auto_rolled_back),
            },
        )
        return result

__all__ = ["LearningPatchRuntimeService"]
