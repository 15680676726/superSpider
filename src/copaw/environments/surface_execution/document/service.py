# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import logging

from ....agents.tools.evidence_runtime import get_file_evidence_sink
from ..owner import ProfessionSurfaceOperationOwner, ProfessionSurfaceOperationPlan
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
            return DocumentObservation(**payload)
        return DocumentObservation(
            document_path=document_path,
            document_family=document_family,
            blockers=["observer-return-invalid"],
        )

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
        return DocumentExecutionResult(
            status="succeeded" if verification_passed else "failed",
            intent_kind=intent_kind,
            before_observation=before_observation,
            after_observation=after_observation,
            readback=readback,
            verification_passed=verification_passed,
            evidence_ids=evidence_ids,
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
