# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import logging

from ....agents.tools.evidence_runtime import get_browser_evidence_sink
from ..owner import ProfessionSurfaceOperationOwner, ProfessionSurfaceOperationPlan
from ..probe_engine import collect_surface_discoveries, decide_surface_probe
from ..transition_miner import mine_transition
from .contracts import BrowserExecutionLoopResult, BrowserExecutionResult
from .observer import observe_browser_page
from .profiles import (
    BrowserPageProfile,
    capture_live_browser_page_context,
)
from .resolver import resolve_browser_target
from .verifier import read_browser_target_readback

logger = logging.getLogger(__name__)


class BrowserSurfaceExecutionService:
    def __init__(self, *, browser_runner) -> None:
        self._browser_runner = browser_runner
        self._seen_surface_discoveries: set[tuple[str, str]] = set()

    def capture_page_context(
        self,
        *,
        session_id: str,
        page_id: str,
        snapshot_text: str = "",
        page_url: str = "",
        page_title: str = "",
        dom_probe: dict[str, object] | None = None,
        page_profile: BrowserPageProfile | None = None,
    ) -> dict[str, object]:
        if page_profile is not None:
            return capture_live_browser_page_context(
                browser_runner=self._browser_runner,
                session_id=session_id,
                page_id=page_id,
                profile=page_profile,
                page_url=page_url,
                page_title=page_title,
            )
        observation = observe_browser_page(
            snapshot_text=snapshot_text,
            page_url=page_url,
            page_title=page_title,
            dom_probe=dom_probe,
        )
        return {
            "snapshot_text": snapshot_text,
            "page_url": page_url,
            "page_title": page_title,
            "dom_probe": dict(dom_probe or {}),
            "observation": observation,
        }

    def observe_page(
        self,
        *,
        session_id: str,
        page_id: str,
        snapshot_text: str = "",
        page_url: str = "",
        page_title: str = "",
        dom_probe: dict[str, object] | None = None,
        page_profile: BrowserPageProfile | None = None,
    ):
        context = self.capture_page_context(
            session_id=session_id,
            page_id=page_id,
            snapshot_text=snapshot_text,
            page_url=page_url,
            page_title=page_title,
            dom_probe=dom_probe,
            page_profile=page_profile,
        )
        return context["observation"]

    def resolve_target(
        self,
        *,
        session_id: str,
        page_id: str,
        target_slot: str,
        snapshot_text: str = "",
        page_url: str = "",
        page_title: str = "",
        dom_probe: dict[str, object] | None = None,
        page_profile: BrowserPageProfile | None = None,
    ):
        observation = self.observe_page(
            session_id=session_id,
            page_id=page_id,
            snapshot_text=snapshot_text,
            page_url=page_url,
            page_title=page_title,
            dom_probe=dom_probe,
            page_profile=page_profile,
        )
        return resolve_browser_target(observation, target_slot=target_slot)

    def read_target_readback(
        self,
        *,
        session_id: str,
        page_id: str,
        target,
    ) -> dict[str, str]:
        return read_browser_target_readback(
            browser_runner=self._browser_runner,
            session_id=session_id,
            page_id=page_id,
            candidate=target,
        )

    def execute_step(
        self,
        *,
        session_id: str,
        page_id: str,
        before_observation=None,
        snapshot_text: str = "",
        page_url: str = "",
        page_title: str = "",
        dom_probe: dict[str, object] | None = None,
        target_slot: str,
        intent_kind: str,
        payload: dict[str, str],
        success_assertion: dict[str, str] | None = None,
        page_profile: BrowserPageProfile | None = None,
    ) -> BrowserExecutionResult:
        if before_observation is None:
            before_observation = self.observe_page(
                session_id=session_id,
                page_id=page_id,
                snapshot_text=snapshot_text,
                page_url=page_url,
                page_title=page_title,
                dom_probe=dom_probe,
                page_profile=page_profile,
            )
        probe_evidence_ids: list[str] = []
        expected_text = str((success_assertion or {}).get("normalized_text") or "")
        expected_toggle_enabled = str((success_assertion or {}).get("toggle_enabled") or "").strip().lower()
        target = None if intent_kind == "press" else resolve_browser_target(before_observation, target_slot=target_slot)
        before_observation, probe_evidence_ids, target = self._maybe_probe_before_action(
            session_id=session_id,
            page_id=page_id,
            before_observation=before_observation,
            page_url=page_url,
            page_title=page_title,
            dom_probe=dom_probe,
            page_profile=page_profile,
            target_slot=target_slot,
            intent_kind=intent_kind,
            target=target,
        )
        readback: dict[str, str] = {}
        verification_kind = "readback"
        if intent_kind == "press":
            verification_kind = "key-press"
            self._browser_runner(
                action="press_key",
                session_id=session_id,
                page_id=page_id,
                key=str(payload.get("key") or "Enter"),
            )
        else:
            if target is None:
                evidence_ids = self._emit_browser_evidence(
                    action=intent_kind,
                    page_id=page_id,
                    status="error",
                    result_summary=f"Browser {intent_kind} could not resolve slot {target_slot}",
                    url=before_observation.page_url or page_url,
                    metadata={
                        "target_slot": target_slot,
                        "blocker_kind": "target-unresolved",
                        "verification": {
                            "verified": False,
                            "kind": "target-resolution",
                            "expected_normalized_text": expected_text,
                            "observed_normalized_text": "",
                            "observed_text": "",
                        },
                        "observation": {
                            "before_url": before_observation.page_url,
                            "after_url": before_observation.page_url,
                        },
                    },
                )
                return BrowserExecutionResult(
                    status="failed",
                    intent_kind=intent_kind,
                    target_slot=target_slot,
                    before_observation=before_observation,
                    after_observation=before_observation,
                    before_graph=before_observation.surface_graph,
                    after_graph=before_observation.surface_graph,
                    verification_passed=False,
                    blocker_kind="target-unresolved",
                    evidence_ids=[*probe_evidence_ids, *evidence_ids],
                )
            action_payload = {
                "action": "type" if intent_kind == "type" else "click",
                "session_id": session_id,
                "page_id": page_id,
            }
            if target.action_ref:
                action_payload["ref"] = target.action_ref
                action_payload["selector"] = ""
            else:
                action_payload["selector"] = target.action_selector
            if intent_kind == "type":
                action_payload["text"] = payload.get("text", "")
                action_payload["submit"] = False
            self._browser_runner(**action_payload)
            readback = self.read_target_readback(
                session_id=session_id,
                page_id=page_id,
                target=target,
            )
        verification_passed = True
        if expected_text:
            verification_passed = readback.get("normalized_text") == expected_text
        if expected_toggle_enabled:
            verification_kind = "toggle-state"
            verification_passed = (
                verification_passed
                and str(readback.get("toggle_enabled") or "").strip().lower() == expected_toggle_enabled
            )
        after_observation = self.observe_page(
            session_id=session_id,
            page_id=page_id,
            snapshot_text=snapshot_text,
            page_url=page_url,
            page_title=page_title,
            dom_probe=dom_probe,
            page_profile=page_profile,
        )
        transition = mine_transition(
            before_observation.surface_graph,
            after_observation.surface_graph,
            action_kind=intent_kind,
        )
        evidence_ids = self._emit_browser_evidence(
            action=intent_kind,
            page_id=page_id,
            status="success" if verification_passed else "error",
            result_summary=transition.result_summary,
            url=after_observation.page_url or before_observation.page_url or page_url,
            metadata={
                "evidence_kind": "surface-transition",
                "target_slot": target_slot,
                "target": {
                    "action_ref": target.action_ref if target is not None else "",
                    "action_selector": target.action_selector if target is not None else "",
                    "readback_selector": target.readback_selector if target is not None else "",
                    "element_kind": target.element_kind if target is not None else "",
                    "scope_anchor": target.scope_anchor if target is not None else "",
                },
                "verification": {
                    "verified": verification_passed,
                    "kind": verification_kind,
                    "expected_normalized_text": expected_text,
                    "observed_normalized_text": readback.get("normalized_text", ""),
                    "observed_text": readback.get("observed_text", ""),
                    "expected_toggle_enabled": expected_toggle_enabled,
                    "observed_toggle_enabled": readback.get("toggle_enabled", ""),
                },
                "observation": {
                    "before_url": before_observation.page_url,
                    "after_url": after_observation.page_url,
                },
                "transition": transition.model_dump(mode="json"),
            },
        )
        transition = transition.model_copy(update={"evidence_refs": list(evidence_ids)})
        discovery_evidence_ids = self._emit_surface_discovery_evidence(
            surface_thread_id=page_id,
            page_id=page_id,
            url=after_observation.page_url or before_observation.page_url or page_url,
            before_graph=before_observation.surface_graph,
            after_graph=after_observation.surface_graph,
            candidate_capability=target_slot or intent_kind,
        )
        return BrowserExecutionResult(
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
            evidence_ids=[*probe_evidence_ids, *evidence_ids, *discovery_evidence_ids],
        )

    @staticmethod
    def _coerce_step(
        step: ProfessionSurfaceOperationPlan | object | None,
    ):
        if step is None:
            return None
        if isinstance(step, ProfessionSurfaceOperationPlan):
            return step
        return step

    def run_step_loop(
        self,
        *,
        session_id: str,
        page_id: str,
        planner=None,
        owner: ProfessionSurfaceOperationOwner | None = None,
        initial_observation=None,
        snapshot_text: str = "",
        page_url: str = "",
        page_title: str = "",
        dom_probe: dict[str, object] | None = None,
        page_profile: BrowserPageProfile | None = None,
        max_steps: int = 5,
    ) -> BrowserExecutionLoopResult:
        history: list[BrowserExecutionResult] = []
        observation = initial_observation
        operation_checkpoint = None
        if observation is None:
            observation = self.observe_page(
                session_id=session_id,
                page_id=page_id,
                snapshot_text=snapshot_text,
                page_url=page_url,
                page_title=page_title,
                dom_probe=dom_probe,
                page_profile=page_profile,
            )
        for _ in range(max(0, max_steps)):
            if owner is not None:
                operation_checkpoint = owner.build_checkpoint(
                    surface_kind="browser",
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
                return BrowserExecutionLoopResult(
                    steps=history,
                    final_observation=observation,
                    stop_reason="planner-stop",
                    operation_checkpoint=operation_checkpoint,
                )
            result = self.execute_step(
                session_id=session_id,
                page_id=page_id,
                before_observation=observation,
                snapshot_text=snapshot_text,
                page_url=page_url,
                page_title=page_title,
                dom_probe=dom_probe,
                target_slot=step.target_slot,
                intent_kind=step.intent_kind,
                payload=dict(step.payload),
                success_assertion=dict(step.success_assertion),
                page_profile=page_profile,
            )
            history.append(result)
            observation = result.after_observation or result.before_observation or observation
            if result.status != "succeeded":
                operation_checkpoint = (
                    owner.build_checkpoint(
                        surface_kind="browser",
                        step_index=len(history),
                        history=history,
                    )
                    if owner is not None
                    else operation_checkpoint
                )
                return BrowserExecutionLoopResult(
                    steps=history,
                    final_observation=observation,
                    stop_reason="step-failed",
                    operation_checkpoint=operation_checkpoint,
                )
        operation_checkpoint = (
            owner.build_checkpoint(
                surface_kind="browser",
                step_index=len(history),
                history=history,
            )
            if owner is not None
            else operation_checkpoint
        )
        return BrowserExecutionLoopResult(
            steps=history,
            final_observation=observation,
            stop_reason="max-steps",
            operation_checkpoint=operation_checkpoint,
        )

    def _emit_browser_evidence(
        self,
        *,
        action: str,
        page_id: str,
        status: str,
        result_summary: str,
        url: str,
        metadata: dict[str, object],
    ) -> list[str]:
        sink = get_browser_evidence_sink()
        if sink is None:
            return []
        try:
            result = sink(
                {
                    "tool_name": "browser_surface_execution",
                    "action": action,
                    "page_id": page_id,
                    "status": status,
                    "url": url,
                    "result_summary": result_summary,
                    "metadata": dict(metadata),
                }
            )
            if inspect.isawaitable(result):
                logger.warning(
                    "browser surface execution evidence sink returned awaitable; ignoring in sync path",
                )
                return []
            return self._extract_evidence_ids(result)
        except Exception:
            logger.warning(
                "browser surface execution evidence sink failed; keeping result unchanged",
                exc_info=True,
            )
            return []

    def _maybe_probe_before_action(
        self,
        *,
        session_id: str,
        page_id: str,
        before_observation,
        page_url: str,
        page_title: str,
        dom_probe: dict[str, object] | None,
        page_profile: BrowserPageProfile | None,
        target_slot: str,
        intent_kind: str,
        target,
    ):
        decision = decide_surface_probe(
            before_observation.surface_graph,
            intent_kind=intent_kind,
            target_slot=target_slot,
            target_resolved=(intent_kind == "press" or target is not None),
        )
        if decision is None or page_profile is None:
            return before_observation, [], target
        probed_observation = self.observe_page(
            session_id=session_id,
            page_id=page_id,
            snapshot_text=before_observation.snapshot_text,
            page_url=page_url,
            page_title=page_title,
            dom_probe=dom_probe,
            page_profile=page_profile,
        )
        refreshed_target = (
            target
            if intent_kind == "press"
            else resolve_browser_target(probed_observation, target_slot=target_slot)
        )
        old_confidence = float(getattr(before_observation.surface_graph, "confidence", 0.0) or 0.0)
        new_confidence = float(getattr(probed_observation.surface_graph, "confidence", 0.0) or 0.0)
        evidence_ids = self._emit_browser_evidence(
            action="probe",
            page_id=page_id,
            status="success",
            result_summary=f"Browser probe {decision.probe_action} refreshed current surface state",
            url=probed_observation.page_url or before_observation.page_url or page_url,
            metadata={
                "evidence_kind": "surface-probe",
                "probe_action": decision.probe_action,
                "target_region": decision.target_region,
                "reason": decision.reason,
                "intent_kind": intent_kind,
                "target_slot": target_slot,
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
                "resolved_uncertainty": (
                    new_confidence > old_confidence
                    or (intent_kind != "press" and refreshed_target is not None)
                ),
            },
        )
        discovery_ids = self._emit_surface_discovery_evidence(
            surface_thread_id=page_id,
            page_id=page_id,
            url=probed_observation.page_url or before_observation.page_url or page_url,
            before_graph=before_observation.surface_graph,
            after_graph=probed_observation.surface_graph,
            candidate_capability=target_slot or intent_kind,
        )
        return probed_observation, [*evidence_ids, *discovery_ids], refreshed_target

    def _emit_surface_discovery_evidence(
        self,
        *,
        surface_thread_id: str,
        page_id: str,
        url: str,
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
                self._emit_browser_evidence(
                    action="discovery",
                    page_id=page_id,
                    status="success",
                    result_summary=f"Discovered {discovery.discovery_kind} on current browser surface",
                    url=url,
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
        evidence_id = str(result.get("evidence_id") or "").strip()
        if evidence_id:
            return [evidence_id]
        raw_ids = result.get("evidence_ids")
        if not isinstance(raw_ids, list):
            return []
        evidence_ids: list[str] = []
        for item in raw_ids:
            normalized = str(item or "").strip()
            if normalized:
                evidence_ids.append(normalized)
        return evidence_ids

__all__ = ["BrowserSurfaceExecutionService"]
