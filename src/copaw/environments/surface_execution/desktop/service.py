# -*- coding: utf-8 -*-
from __future__ import annotations

from ..graph_compiler import compile_desktop_observation_to_graph
from ..owner import ProfessionSurfaceOperationOwner, ProfessionSurfaceOperationPlan
from ..probe_engine import decide_surface_probe
from ..transition_miner import mine_transition
from .contracts import (
    DesktopExecutionLoopResult,
    DesktopExecutionResult,
    DesktopObservation,
    DesktopTargetCandidate,
)


class DesktopSurfaceExecutionService:
    def __init__(
        self,
        *,
        desktop_observer,
        desktop_runner,
    ) -> None:
        self._desktop_observer = desktop_observer
        self._desktop_runner = desktop_runner

    @staticmethod
    def _coerce_step(
        step: ProfessionSurfaceOperationPlan | object | None,
    ):
        if step is None:
            return None
        if isinstance(step, ProfessionSurfaceOperationPlan):
            return step
        return step

    def observe_surface(
        self,
        *,
        session_mount_id: str,
        app_identity: str = "",
    ) -> DesktopObservation:
        payload = self._desktop_observer(
            session_mount_id=session_mount_id,
            app_identity=app_identity,
        )
        if isinstance(payload, DesktopObservation):
            observation = payload
        elif isinstance(payload, dict):
            observation = DesktopObservation(**payload)
        else:
            observation = DesktopObservation(
                app_identity=app_identity,
                blockers=["observer-return-invalid"],
            )
        if observation.surface_graph is None:
            observation.surface_graph = compile_desktop_observation_to_graph(observation)
        return observation

    def resolve_target(
        self,
        observation: DesktopObservation,
        *,
        target_slot: str,
    ) -> DesktopTargetCandidate | None:
        candidates = list(observation.slot_candidates.get(target_slot) or [])
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: item.score, reverse=True)[0]

    def execute_step(
        self,
        *,
        session_mount_id: str,
        app_identity: str = "",
        target_slot: str,
        intent_kind: str,
        payload: dict[str, str],
        success_assertion: dict[str, str] | None = None,
        before_observation: DesktopObservation | None = None,
    ) -> DesktopExecutionResult:
        if before_observation is None:
            before_observation = self.observe_surface(
                session_mount_id=session_mount_id,
                app_identity=app_identity,
            )
        target = self.resolve_target(before_observation, target_slot=target_slot)
        before_observation, target = self._maybe_probe_before_action(
            session_mount_id=session_mount_id,
            app_identity=app_identity,
            before_observation=before_observation,
            intent_kind=intent_kind,
            target_slot=target_slot,
            target=target,
        )
        if target is None:
            return DesktopExecutionResult(
                status="failed",
                intent_kind=intent_kind,
                target_slot=target_slot,
                before_observation=before_observation,
                after_observation=before_observation,
                before_graph=before_observation.surface_graph,
                after_graph=before_observation.surface_graph,
                blocker_kind="target-unresolved",
            )
        action_payload = {
            "action": intent_kind,
            "session_mount_id": session_mount_id,
            "app_identity": app_identity,
            "selector": target.action_selector,
        }
        if intent_kind == "type_text":
            action_payload["text"] = str(payload.get("text") or "")
        self._desktop_runner(**action_payload)
        after_observation = self.observe_surface(
            session_mount_id=session_mount_id,
            app_identity=app_identity,
        )
        readback_key = target.readback_key
        readback = {}
        if readback_key:
            readback_value = str(after_observation.readback.get(readback_key) or "")
            readback = {
                "observed_text": readback_value,
                "normalized_text": readback_value.strip(),
            }
        verification_passed = True
        expected_focused_selector = str((success_assertion or {}).get("focused_selector") or "")
        expected_normalized = str((success_assertion or {}).get("normalized_text") or "")
        if expected_focused_selector:
            verification_passed = (
                str(after_observation.readback.get("focused_window") or "") == expected_focused_selector
            )
        if expected_normalized:
            verification_passed = (
                verification_passed
                and readback.get("normalized_text") == expected_normalized
            )
        transition = mine_transition(
            before_observation.surface_graph,
            after_observation.surface_graph,
            action_kind=intent_kind,
        )
        return DesktopExecutionResult(
            status="succeeded" if verification_passed else "failed",
            intent_kind=intent_kind,
            target_slot=target_slot,
            resolved_target=target,
            before_observation=before_observation,
            after_observation=after_observation,
            before_graph=before_observation.surface_graph,
            after_graph=after_observation.surface_graph,
            transition=transition,
            readback=readback,
            verification_passed=verification_passed,
        )

    def run_step_loop(
        self,
        *,
        session_mount_id: str,
        planner=None,
        owner: ProfessionSurfaceOperationOwner | None = None,
        initial_observation: DesktopObservation | None = None,
        app_identity: str = "",
        max_steps: int = 5,
    ) -> DesktopExecutionLoopResult:
        history: list[DesktopExecutionResult] = []
        observation = initial_observation
        operation_checkpoint = None
        if observation is None:
            observation = self.observe_surface(
                session_mount_id=session_mount_id,
                app_identity=app_identity,
            )
        for _ in range(max(0, max_steps)):
            if owner is not None:
                operation_checkpoint = owner.build_checkpoint(
                    surface_kind="desktop",
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
                return DesktopExecutionLoopResult(
                    steps=history,
                    final_observation=observation,
                    stop_reason="planner-stop",
                    operation_checkpoint=operation_checkpoint,
                )
            result = self.execute_step(
                session_mount_id=session_mount_id,
                app_identity=app_identity,
                target_slot=step.target_slot,
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
                        surface_kind="desktop",
                        step_index=len(history),
                        history=history,
                    )
                    if owner is not None
                    else operation_checkpoint
                )
                return DesktopExecutionLoopResult(
                    steps=history,
                    final_observation=observation,
                    stop_reason="step-failed",
                    operation_checkpoint=operation_checkpoint,
                )
        operation_checkpoint = (
            owner.build_checkpoint(
                surface_kind="desktop",
                step_index=len(history),
                history=history,
            )
            if owner is not None
            else operation_checkpoint
        )
        return DesktopExecutionLoopResult(
            steps=history,
            final_observation=observation,
            stop_reason="max-steps",
            operation_checkpoint=operation_checkpoint,
        )

    def _maybe_probe_before_action(
        self,
        *,
        session_mount_id: str,
        app_identity: str,
        before_observation: DesktopObservation,
        intent_kind: str,
        target_slot: str,
        target: DesktopTargetCandidate | None,
    ) -> tuple[DesktopObservation, DesktopTargetCandidate | None]:
        decision = decide_surface_probe(
            before_observation.surface_graph,
            intent_kind=intent_kind,
            target_slot=target_slot,
            target_resolved=target is not None,
        )
        if decision is None:
            return before_observation, target
        probed_observation = self.observe_surface(
            session_mount_id=session_mount_id,
            app_identity=app_identity,
        )
        refreshed_target = self.resolve_target(
            probed_observation,
            target_slot=target_slot,
        )
        return probed_observation, refreshed_target


__all__ = ["DesktopSurfaceExecutionService"]
