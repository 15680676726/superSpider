# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import logging

from ....agents.tools.evidence_runtime import get_file_evidence_sink
from ..graph_compiler import compile_document_observation_to_graph
from ..owner import ProfessionSurfaceOperationOwner, ProfessionSurfaceOperationPlan
from ..probe_engine import collect_surface_discoveries, decide_surface_probe
from .contracts import (
    DocumentExecutionLoopResult,
    DocumentExecutionResult,
    DocumentObservation,
)

logger = logging.getLogger(__name__)


class DocumentSurfaceExecutionService:
    def __init__(
        self,
        *,
        document_observer,
        document_runner,
    ) -> None:
        self._document_observer = document_observer
        self._document_runner = document_runner
        self._seen_surface_discoveries: set[tuple[str, str]] = set()

    @staticmethod
    def _coerce_step(
        step: ProfessionSurfaceOperationPlan | object | None,
    ):
        if step is None:
            return None
        if isinstance(step, ProfessionSurfaceOperationPlan):
            return step
        return step

    def observe_document(
        self,
        *,
        session_mount_id: str,
        document_path: str,
        document_family: str = "",
    ) -> DocumentObservation:
        payload = self._document_observer(
            session_mount_id=session_mount_id,
            document_path=document_path,
            document_family=document_family,
        )
        if isinstance(payload, DocumentObservation):
            return payload
        if isinstance(payload, dict):
            observation = DocumentObservation(**payload)
        else:
            observation = DocumentObservation(
                document_path=document_path,
                document_family=document_family,
                blockers=["observer-return-invalid"],
            )
        if observation.surface_graph is None:
            observation.surface_graph = compile_document_observation_to_graph(observation)
        return observation

    def execute_step(
        self,
        *,
        session_mount_id: str,
        document_path: str,
        document_family: str = "",
        intent_kind: str,
        payload: dict[str, str],
        success_assertion: dict[str, str] | None = None,
        before_observation: DocumentObservation | None = None,
    ) -> DocumentExecutionResult:
        if before_observation is None:
            before_observation = self.observe_document(
                session_mount_id=session_mount_id,
                document_path=document_path,
                document_family=document_family,
            )
        before_observation, probe_evidence_ids = self._maybe_probe_before_action(
            session_mount_id=session_mount_id,
            document_path=document_path,
            document_family=document_family,
            intent_kind=intent_kind,
            before_observation=before_observation,
        )
        if intent_kind == "replace_text":
            self._document_runner(
                action="edit_document_file",
                session_mount_id=session_mount_id,
                document_path=document_path,
                document_family=document_family,
                find_text=str(payload.get("find_text") or ""),
                replace_text=str(payload.get("replace_text") or ""),
            )
            evidence_action = "edit"
        elif intent_kind == "write_document":
            self._document_runner(
                action="write_document_file",
                session_mount_id=session_mount_id,
                document_path=document_path,
                document_family=document_family,
                content=str(payload.get("content") or ""),
            )
            evidence_action = "write"
        else:
            return DocumentExecutionResult(
                status="failed",
                intent_kind=intent_kind,
                before_observation=before_observation,
                after_observation=before_observation,
                before_graph=before_observation.surface_graph,
                after_graph=before_observation.surface_graph,
                blocker_kind="unsupported-intent",
            )
        after_observation = self.observe_document(
            session_mount_id=session_mount_id,
            document_path=document_path,
            document_family=document_family,
        )
        readback = {
            "observed_text": after_observation.content_text,
            "normalized_text": after_observation.content_text.strip(),
        }
        expected_contains = str((success_assertion or {}).get("contains_text") or "")
        expected_normalized = str((success_assertion or {}).get("normalized_text") or "")
        verification_passed = True
        if expected_contains:
            verification_passed = expected_contains in after_observation.content_text
        if expected_normalized:
            verification_passed = (
                verification_passed
                and readback.get("normalized_text") == expected_normalized
            )
        evidence_ids = self._emit_file_evidence(
            action=evidence_action,
            file_path=document_path,
            status="success" if verification_passed else "error",
            result_summary=(
                f"Document {intent_kind} completed for {document_path}"
                if verification_passed
                else f"Document {intent_kind} failed verification for {document_path}"
            ),
            metadata={
                "document_family": document_family,
                "intent_kind": intent_kind,
                "verification": {
                    "verified": verification_passed,
                    "expected_contains": expected_contains,
                    "expected_normalized_text": expected_normalized,
                    "observed_normalized_text": readback.get("normalized_text", ""),
                },
                "revision": {
                    "before": before_observation.revision_token,
                    "after": after_observation.revision_token,
                },
            },
        )
        discovery_evidence_ids = self._emit_surface_discovery_evidence(
            surface_thread_id=document_path,
            file_path=document_path,
            before_graph=before_observation.surface_graph,
            after_graph=after_observation.surface_graph,
            candidate_capability=intent_kind,
        )
        return DocumentExecutionResult(
            status="succeeded" if verification_passed else "failed",
            intent_kind=intent_kind,
            before_observation=before_observation,
            after_observation=after_observation,
            before_graph=before_observation.surface_graph,
            after_graph=after_observation.surface_graph,
            readback=readback,
            verification_passed=verification_passed,
            evidence_ids=[*probe_evidence_ids, *evidence_ids, *discovery_evidence_ids],
        )

    def run_step_loop(
        self,
        *,
        session_mount_id: str,
        document_path: str,
        planner=None,
        owner: ProfessionSurfaceOperationOwner | None = None,
        initial_observation: DocumentObservation | None = None,
        document_family: str = "",
        max_steps: int = 5,
    ) -> DocumentExecutionLoopResult:
        history: list[DocumentExecutionResult] = []
        observation = initial_observation
        operation_checkpoint = None
        if observation is None:
            observation = self.observe_document(
                session_mount_id=session_mount_id,
                document_path=document_path,
                document_family=document_family,
            )
        for _ in range(max(0, max_steps)):
            if owner is not None:
                operation_checkpoint = owner.build_checkpoint(
                    surface_kind="document",
                    step_index=len(history),
                    history=history,
                )
                step = owner.plan(
                    observation=observation,
                    history=history,
                    checkpoint=operation_checkpoint,
                )
            else:
                step = planner(observation, list(history))
            step = self._coerce_step(step)
            if step is None:
                return DocumentExecutionLoopResult(
                    steps=history,
                    final_observation=observation,
                    stop_reason="planner-stop",
                    operation_checkpoint=operation_checkpoint,
                )
            result = self.execute_step(
                session_mount_id=session_mount_id,
                document_path=document_path,
                document_family=document_family,
                intent_kind=step.intent_kind,
                payload=dict(step.payload),
                success_assertion=dict(step.success_assertion),
                before_observation=observation,
            )
            history.append(result)
            observation = result.after_observation or result.before_observation or observation
            if result.status != "succeeded":
                operation_checkpoint = (
                    owner.build_checkpoint(
                        surface_kind="document",
                        step_index=len(history),
                        history=history,
                    )
                    if owner is not None
                    else operation_checkpoint
                )
                return DocumentExecutionLoopResult(
                    steps=history,
                    final_observation=observation,
                    stop_reason="step-failed",
                    operation_checkpoint=operation_checkpoint,
                )
        operation_checkpoint = (
            owner.build_checkpoint(
                surface_kind="document",
                step_index=len(history),
                history=history,
            )
            if owner is not None
            else operation_checkpoint
        )
        return DocumentExecutionLoopResult(
            steps=history,
            final_observation=observation,
            stop_reason="max-steps",
            operation_checkpoint=operation_checkpoint,
        )

    def _emit_file_evidence(
        self,
        *,
        action: str,
        file_path: str,
        status: str,
        result_summary: str,
        metadata: dict[str, object],
    ) -> list[str]:
        sink = get_file_evidence_sink()
        if sink is None:
            return []
        try:
            result = sink(
                {
                    "tool_name": "document_surface_execution",
                    "action": action,
                    "file_path": file_path,
                    "resolved_path": file_path,
                    "status": status,
                    "result_summary": result_summary,
                    "metadata": dict(metadata),
                }
            )
            if inspect.isawaitable(result):
                logger.warning(
                    "document surface execution evidence sink returned awaitable; ignoring in sync path",
                )
                return []
            return self._extract_evidence_ids(result)
        except Exception:
            logger.warning(
                "document surface execution evidence sink failed; keeping result unchanged",
                exc_info=True,
            )
            return []

    def _maybe_probe_before_action(
        self,
        *,
        session_mount_id: str,
        document_path: str,
        document_family: str,
        intent_kind: str,
        before_observation: DocumentObservation,
    ) -> tuple[DocumentObservation, list[str]]:
        decision = decide_surface_probe(
            before_observation.surface_graph,
            intent_kind=intent_kind,
            target_slot="document-body",
            target_resolved=True,
        )
        if decision is None:
            return before_observation, []
        probed_observation = self.observe_document(
            session_mount_id=session_mount_id,
            document_path=document_path,
            document_family=document_family,
        )
        old_confidence = float(getattr(before_observation.surface_graph, "confidence", 0.0) or 0.0)
        new_confidence = float(getattr(probed_observation.surface_graph, "confidence", 0.0) or 0.0)
        evidence_ids = self._emit_file_evidence(
            action="probe",
            file_path=document_path,
            status="success",
            result_summary=f"Document probe {decision.probe_action} refreshed current surface state",
            metadata={
                "evidence_kind": "surface-probe",
                "probe_action": decision.probe_action,
                "target_region": decision.target_region,
                "reason": decision.reason,
                "intent_kind": intent_kind,
                "before_graph": (
                    before_observation.surface_graph.model_dump(mode="json")
                    if before_observation.surface_graph is not None
                    else None
                ),
                "after_graph": (
                    probed_observation.surface_graph.model_dump(mode="json")
                    if probed_observation.surface_graph is not None
                    else None
                ),
                "resolved_uncertainty": new_confidence > old_confidence,
            },
        )
        return probed_observation, evidence_ids

    def _emit_surface_discovery_evidence(
        self,
        *,
        surface_thread_id: str,
        file_path: str,
        before_graph,
        after_graph,
        candidate_capability: str,
    ) -> list[str]:
        evidence_ids: list[str] = []
        discoveries = collect_surface_discoveries(
            before_graph,
            after_graph,
            candidate_capability=candidate_capability,
        )
        for discovery in discoveries:
            seen_key = (surface_thread_id, discovery.discovery_fingerprint)
            if seen_key in self._seen_surface_discoveries:
                continue
            self._seen_surface_discoveries.add(seen_key)
            evidence_ids.extend(
                self._emit_file_evidence(
                    action="discovery",
                    file_path=file_path,
                    status="success",
                    result_summary=f"Discovered {discovery.discovery_kind} on current document surface",
                    metadata={
                        "evidence_kind": "surface-discovery",
                        "discovery_kind": discovery.discovery_kind,
                        "discovery_fingerprint": discovery.discovery_fingerprint,
                        "region_ref": discovery.region_ref,
                        "candidate_capability": discovery.candidate_capability,
                        "node_id": discovery.node_id,
                        "node_kind": discovery.node_kind,
                        "label": discovery.label,
                    },
                )
            )
        return evidence_ids

    @staticmethod
    def _extract_evidence_ids(result: object) -> list[str]:
        if isinstance(result, str):
            normalized = result.strip()
            return [normalized] if normalized else []
        if not isinstance(result, dict):
            return []
        if isinstance(result.get("evidence_ids"), list):
            return [str(item).strip() for item in result["evidence_ids"] if str(item).strip()]
        evidence_id = str(result.get("evidence_id") or "").strip()
        return [evidence_id] if evidence_id else []


__all__ = ["DocumentSurfaceExecutionService"]
