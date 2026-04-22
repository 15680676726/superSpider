# -*- coding: utf-8 -*-
from __future__ import annotations

from .main_brain_intake import normalize_main_brain_runtime_context
from .query_execution_shared import *  # noqa: F401,F403
from .runtime_outcome import build_execution_diagnostics


class _QueryExecutionContextRuntimeMixin:
    def _merge_main_brain_runtime_contexts(
        self,
        *values: Any,
    ) -> dict[str, Any] | None:
        merged: dict[str, Any] = {}
        for value in values:
            normalized = normalize_main_brain_runtime_context(value)
            if not normalized:
                continue
            work_context_id = _first_non_empty(normalized.get("work_context_id"))
            if work_context_id is not None:
                merged["work_context_id"] = work_context_id
            for section in ("intent", "environment", "recovery", "knowledge_graph"):
                payload = _mapping_value(normalized.get(section))
                if not payload:
                    continue
                existing = _mapping_value(merged.get(section))
                merged[section] = {
                    **existing,
                    **payload,
                }
        return merged or None

    def _resolve_request_main_brain_runtime_context(
        self,
        *,
        request: Any | None,
    ) -> dict[str, Any] | None:
        if request is None:
            return None
        return self._merge_main_brain_runtime_contexts(
            getattr(request, "_copaw_main_brain_runtime_context", None),
            getattr(request, "main_brain_runtime", None),
        )

    def _resolve_execution_task_context(
        self,
        *,
        request: Any | None = None,
        agent_id: str,
        kernel_task_id: str | None,
        conversation_thread_id: str | None,
    ) -> dict[str, Any]:
        context: dict[str, Any] = {}
        runtime_repository = self._agent_runtime_repository

        def _merge_capability_trial_attribution(value: Any) -> None:
            payload = _mapping_value(value)
            if not payload:
                return
            existing = _mapping_value(context.get("capability_trial_attribution"))
            merged = dict(existing)
            merged = {
                **merged,
                "candidate_id": _first_non_empty(
                    payload.get("candidate_id"),
                    payload.get("skill_candidate_id"),
                    merged.get("candidate_id"),
                ),
                "skill_candidate_id": _first_non_empty(
                    payload.get("skill_candidate_id"),
                    payload.get("candidate_id"),
                    merged.get("skill_candidate_id"),
                ),
                "skill_trial_id": _first_non_empty(
                    payload.get("skill_trial_id"),
                    payload.get("trial_id"),
                    merged.get("skill_trial_id"),
                ),
                "skill_lifecycle_stage": _first_non_empty(
                    payload.get("skill_lifecycle_stage"),
                    payload.get("lifecycle_stage"),
                    merged.get("skill_lifecycle_stage"),
                ),
                "selected_scope": _first_non_empty(
                    payload.get("selected_scope"),
                    payload.get("scope_type"),
                    payload.get("trial_scope"),
                    merged.get("selected_scope"),
                ),
                "selected_seat_ref": _first_non_empty(
                    payload.get("selected_seat_ref"),
                    merged.get("selected_seat_ref"),
                ),
                "donor_id": _first_non_empty(
                    payload.get("donor_id"),
                    merged.get("donor_id"),
                ),
                "package_id": _first_non_empty(
                    payload.get("package_id"),
                    merged.get("package_id"),
                ),
                "source_profile_id": _first_non_empty(
                    payload.get("source_profile_id"),
                    merged.get("source_profile_id"),
                ),
                "candidate_source_kind": _first_non_empty(
                    payload.get("candidate_source_kind"),
                    merged.get("candidate_source_kind"),
                ),
                "resolution_kind": _first_non_empty(
                    payload.get("resolution_kind"),
                    merged.get("resolution_kind"),
                ),
            }
            for key in ("replacement_target_ids", "rollback_target_ids", "capability_ids"):
                resolved_items = _string_list(payload.get(key))
                if resolved_items:
                    merged[key] = resolved_items
            merged = {
                key: value
                for key, value in merged.items()
                if value is not None and value != "" and value != []
            }
            if merged:
                context["capability_trial_attribution"] = merged

        def _merge_main_brain_runtime(value: Any) -> None:
            merged = self._merge_main_brain_runtime_contexts(
                context.get("main_brain_runtime"),
                value,
            )
            if merged is not None:
                context["main_brain_runtime"] = merged

        if kernel_task_id and self._kernel_dispatcher is not None:
            task = self._kernel_dispatcher.lifecycle.get_task(kernel_task_id)
            if task is not None:
                if isinstance(task.task_segment, dict) and task.task_segment:
                    context["task_segment"] = dict(task.task_segment)
                if isinstance(task.resume_point, dict) and task.resume_point:
                    context["resume_point"] = dict(task.resume_point)
                if isinstance(task.actor_owner_id, str) and task.actor_owner_id:
                    context["actor_owner_id"] = task.actor_owner_id
                if isinstance(getattr(task, "work_context_id", None), str) and task.work_context_id:
                    context["work_context_id"] = task.work_context_id
                payload = task.payload if isinstance(task.payload, dict) else {}
                _merge_main_brain_runtime(payload.get("main_brain_runtime"))
                _merge_capability_trial_attribution(payload.get("capability_trial_attribution"))
                task_request_context = _mapping_value(payload.get("request_context"))
                if task_request_context:
                    _merge_main_brain_runtime(task_request_context.get("main_brain_runtime"))
                    _merge_capability_trial_attribution(
                        task_request_context.get("capability_trial_attribution"),
                    )
                task_request = _mapping_value(payload.get("request"))
                if task_request:
                    _merge_main_brain_runtime(task_request.get("main_brain_runtime"))
                    _merge_capability_trial_attribution(
                        task_request.get("capability_trial_attribution"),
                    )
        runtime = runtime_repository.get_runtime(agent_id) if runtime_repository is not None else None
        if runtime is not None:
            runtime_metadata = _mapping_value(getattr(runtime, "metadata", None))
            if runtime_metadata:
                _merge_main_brain_runtime(runtime_metadata.get("main_brain_runtime"))
                _merge_capability_trial_attribution(
                    runtime_metadata.get("current_capability_trial"),
                )
        checkpoint_repository = getattr(self, "_agent_checkpoint_repository", None)
        if checkpoint_repository is not None:
            checkpoints = checkpoint_repository.list_checkpoints(
                agent_id=agent_id,
                task_id=kernel_task_id,
                limit=10,
            )
            if conversation_thread_id is not None:
                checkpoints = [
                    checkpoint
                    for checkpoint in checkpoints
                    if _first_non_empty(getattr(checkpoint, "conversation_thread_id", None))
                    == _first_non_empty(conversation_thread_id)
                ]
            if checkpoints:
                latest_checkpoint = checkpoints[0]
                context["resume_checkpoint"] = latest_checkpoint.model_dump(mode="json")
                checkpoint_resume = _mapping_value(latest_checkpoint.resume_payload)
                if checkpoint_resume:
                    context["resume_payload"] = checkpoint_resume
                    embedded_resume = _mapping_value(checkpoint_resume.get("resume_point"))
                    if embedded_resume and "resume_point" not in context:
                        context["resume_point"] = embedded_resume
                    _merge_main_brain_runtime(checkpoint_resume.get("main_brain_runtime"))
                checkpoint_snapshot = _mapping_value(latest_checkpoint.snapshot_payload)
                if checkpoint_snapshot:
                    context["resume_snapshot"] = checkpoint_snapshot
        _merge_main_brain_runtime(
            self._resolve_request_main_brain_runtime_context(request=request),
        )
        if request is not None:
            _merge_capability_trial_attribution(
                getattr(request, "capability_trial_attribution", None),
            )
            _merge_capability_trial_attribution(
                getattr(request, "_copaw_capability_trial_attribution", None),
            )
        degradation = self._resolve_execution_degradation_context(
            request=request,
            agent_id=agent_id,
        )
        runtime_entropy = self._build_runtime_entropy_contract(
            degradation=degradation,
        )
        context["runtime_entropy"] = runtime_entropy
        context["query_runtime_entropy"] = self._build_query_runtime_entropy_contract(
            degradation=degradation,
            runtime_entropy=runtime_entropy,
        )
        if degradation:
            context["degradation"] = degradation
        return context

    def _resolve_execution_degradation_context(
        self,
        *,
        request: Any | None,
        agent_id: str,
    ) -> dict[str, Any]:
        degradation: dict[str, Any] = {}
        if self._conversation_compaction_service is None:
            degradation["sidecar_memory"] = build_execution_diagnostics(
                failure_source="sidecar-memory",
                remediation_summary=(
                    "The private compaction memory sidecar is unavailable; "
                    "runtime continues on canonical state only."
                ),
            )
        requested_candidates = self._request_agent_candidates(request) if request is not None else []
        if agent_id == EXECUTION_CORE_AGENT_ID:
            for candidate in requested_candidates:
                if candidate == EXECUTION_CORE_AGENT_ID:
                    break
                if self._get_agent_profile(candidate) is not None:
                    break
                degradation["owner_fallback"] = {
                    **build_execution_diagnostics(
                        failure_source="degraded-runtime",
                        remediation_summary=(
                            f"Requested agent '{candidate}' is unavailable; "
                            "runtime fell back to execution core."
                        ),
                    ),
                    "requested_agent_id": candidate,
                    "resolved_agent_id": agent_id,
                }
                break
        return degradation


__all__ = [
    "_QueryExecutionContextRuntimeMixin",
]
