# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field


class ProfessionSurfaceOperationPlan(BaseModel):
    intent_kind: str
    target_slot: str = ""
    payload: dict[str, str] = Field(default_factory=dict)
    success_assertion: dict[str, str] = Field(default_factory=dict)
    fallback_policy: str = ""


class ProfessionSurfaceOperationCheckpoint(BaseModel):
    formal_session_id: str
    surface_kind: str
    surface_thread_id: str
    step_index: int = 0
    last_status: str = ""
    last_blocker_kind: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProfessionSurfaceOperationOwner:
    def __init__(
        self,
        *,
        formal_session_id: str,
        surface_thread_id: str,
        planner: Callable[..., ProfessionSurfaceOperationPlan | None],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._formal_session_id = str(formal_session_id or "").strip()
        self._surface_thread_id = str(surface_thread_id or "").strip()
        self._planner = planner
        self._metadata = dict(metadata or {})

    def build_checkpoint(
        self,
        *,
        surface_kind: str,
        step_index: int,
        history: list[object],
    ) -> ProfessionSurfaceOperationCheckpoint:
        last_status = ""
        last_blocker_kind = ""
        if history:
            last_step = history[-1]
            last_status = str(getattr(last_step, "status", "") or "").strip()
            last_blocker_kind = str(getattr(last_step, "blocker_kind", "") or "").strip()
        return ProfessionSurfaceOperationCheckpoint(
            formal_session_id=self._formal_session_id,
            surface_kind=str(surface_kind or "").strip(),
            surface_thread_id=self._surface_thread_id,
            step_index=max(0, int(step_index)),
            last_status=last_status,
            last_blocker_kind=last_blocker_kind,
            metadata=dict(self._metadata),
        )

    def plan(
        self,
        *,
        observation: object,
        history: list[object],
        checkpoint: ProfessionSurfaceOperationCheckpoint,
    ) -> ProfessionSurfaceOperationPlan | None:
        return self._planner(
            observation=observation,
            history=list(history),
            checkpoint=checkpoint,
        )


class GuidedBrowserSurfaceIntent(BaseModel):
    desired_text: str = ""
    request_submit: bool = False
    input_slot: str = "primary_input"
    submit_slot: str = "submit_button"
    pause_on_login: bool = True
    fallback_to_enter: bool = True


class GuidedDocumentSurfaceIntent(BaseModel):
    desired_content: str = ""
    find_text: str = ""
    replace_text: str = ""
    pause_on_blockers: bool = True


class GuidedDesktopSurfaceIntent(BaseModel):
    desired_text: str = ""
    require_focus: bool = True
    window_slot: str = "window_target"
    input_slot: str = "primary_input"
    pause_on_blockers: bool = True


def build_guided_browser_surface_owner(
    *,
    formal_session_id: str,
    surface_thread_id: str,
    intent: GuidedBrowserSurfaceIntent | dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProfessionSurfaceOperationOwner:
    normalized_intent = (
        intent
        if isinstance(intent, GuidedBrowserSurfaceIntent)
        else GuidedBrowserSurfaceIntent.model_validate(intent or {})
    )

    def _planner(*, observation, history, checkpoint):
        _ = checkpoint
        login_state = str(getattr(observation, "login_state", "") or "").strip()
        blockers = [str(item or "").strip() for item in list(getattr(observation, "blockers", []) or [])]
        page_summary = getattr(observation, "page_summary", None)
        blocker_hints = [
            str(item or "").strip()
            for item in list(getattr(page_summary, "blocker_hints", []) or [])
        ]
        if normalized_intent.pause_on_login and (
            login_state == "login-required"
            or "login-required" in blockers
            or "login-required" in blocker_hints
        ):
            return None
        typed = any(
            str(getattr(step, "intent_kind", "") or "").strip() == "type"
            and str(getattr(step, "target_slot", "") or "").strip() == normalized_intent.input_slot
            and str(getattr(step, "status", "") or "").strip() == "succeeded"
            for step in history
        )
        if normalized_intent.desired_text and not typed:
            return ProfessionSurfaceOperationPlan(
                intent_kind="type",
                target_slot=normalized_intent.input_slot,
                payload={"text": normalized_intent.desired_text},
                success_assertion={"normalized_text": normalized_intent.desired_text},
            )
        submitted = any(
            str(getattr(step, "intent_kind", "") or "").strip() in {"click", "press"}
            and str(getattr(step, "status", "") or "").strip() == "succeeded"
            and str(getattr(step, "target_slot", "") or "").strip() in {
                normalized_intent.submit_slot,
                "page",
            }
            for step in history
        )
        if normalized_intent.request_submit and not submitted:
            slot_candidates = getattr(observation, "slot_candidates", {}) or {}
            submit_candidates = list(slot_candidates.get(normalized_intent.submit_slot) or [])
            if submit_candidates:
                return ProfessionSurfaceOperationPlan(
                    intent_kind="click",
                    target_slot=normalized_intent.submit_slot,
                )
            action_hints = [
                str(item or "").strip()
                for item in list(getattr(page_summary, "action_hints", []) or [])
            ]
            primary_input_candidates = list(getattr(observation, "primary_input_candidates", []) or [])
            if normalized_intent.fallback_to_enter and (
                "submit" in action_hints
                or ("submit" in str(getattr(page_summary, "page_kind", "") or "").strip().lower() and primary_input_candidates)
            ):
                return ProfessionSurfaceOperationPlan(
                    intent_kind="press",
                    target_slot="page",
                    payload={"key": "Enter"},
                )
        return None

    return ProfessionSurfaceOperationOwner(
        formal_session_id=formal_session_id,
        surface_thread_id=surface_thread_id,
        planner=_planner,
        metadata=metadata,
    )


def build_guided_document_surface_owner(
    *,
    formal_session_id: str,
    surface_thread_id: str,
    intent: GuidedDocumentSurfaceIntent | dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProfessionSurfaceOperationOwner:
    normalized_intent = (
        intent
        if isinstance(intent, GuidedDocumentSurfaceIntent)
        else GuidedDocumentSurfaceIntent.model_validate(intent or {})
    )

    def _planner(*, observation, history, checkpoint):
        _ = history, checkpoint
        blockers = [str(item or "").strip() for item in list(getattr(observation, "blockers", []) or [])]
        if normalized_intent.pause_on_blockers and blockers:
            return None
        content_text = str(getattr(observation, "content_text", "") or "")
        desired_content = str(normalized_intent.desired_content or "").strip()
        if desired_content and desired_content in content_text:
            return None
        find_text = str(normalized_intent.find_text or "")
        replace_text = str(normalized_intent.replace_text or "")
        if find_text and replace_text and find_text in content_text:
            return ProfessionSurfaceOperationPlan(
                intent_kind="replace_text",
                payload={"find_text": find_text, "replace_text": replace_text},
                success_assertion={"contains_text": desired_content or replace_text},
            )
        if desired_content:
            return ProfessionSurfaceOperationPlan(
                intent_kind="write_document",
                payload={"content": desired_content},
                success_assertion={"contains_text": desired_content},
            )
        return None

    return ProfessionSurfaceOperationOwner(
        formal_session_id=formal_session_id,
        surface_thread_id=surface_thread_id,
        planner=_planner,
        metadata=metadata,
    )


def build_guided_desktop_surface_owner(
    *,
    formal_session_id: str,
    surface_thread_id: str,
    intent: GuidedDesktopSurfaceIntent | dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProfessionSurfaceOperationOwner:
    normalized_intent = (
        intent
        if isinstance(intent, GuidedDesktopSurfaceIntent)
        else GuidedDesktopSurfaceIntent.model_validate(intent or {})
    )

    def _planner(*, observation, history, checkpoint):
        _ = checkpoint
        blockers = [str(item or "").strip() for item in list(getattr(observation, "blockers", []) or [])]
        if normalized_intent.pause_on_blockers and blockers:
            return None
        slot_candidates = getattr(observation, "slot_candidates", {}) or {}
        readback = getattr(observation, "readback", {}) or {}
        window_candidates = list(slot_candidates.get(normalized_intent.window_slot) or [])
        focused_window = str(readback.get("focused_window") or "").strip()
        expected_window_selector = (
            str(getattr(window_candidates[0], "action_selector", "") or "").strip()
            if window_candidates
            else ""
        )
        focus_done = any(
            str(getattr(step, "intent_kind", "") or "").strip() == "focus_window"
            and str(getattr(step, "status", "") or "").strip() == "succeeded"
            for step in history
        )
        if normalized_intent.require_focus and not expected_window_selector and not focus_done:
            return None
        if (
            normalized_intent.require_focus
            and expected_window_selector
            and focused_window != expected_window_selector
            and not focus_done
        ):
            return ProfessionSurfaceOperationPlan(
                intent_kind="focus_window",
                target_slot=normalized_intent.window_slot,
                success_assertion={"focused_selector": expected_window_selector},
            )
        desired_text = str(normalized_intent.desired_text or "").strip()
        if desired_text:
            input_candidates = list(slot_candidates.get(normalized_intent.input_slot) or [])
            current_text = ""
            if input_candidates:
                readback_key = str(getattr(input_candidates[0], "readback_key", "") or "").strip()
                if readback_key:
                    current_text = str(readback.get(readback_key) or "").strip()
            typed = any(
                str(getattr(step, "intent_kind", "") or "").strip() == "type_text"
                and str(getattr(step, "status", "") or "").strip() == "succeeded"
                and str(getattr(getattr(step, "readback", {}), "get", lambda _k, _d=None: "")("normalized_text", "") or "").strip() == desired_text
                for step in history
            )
            if current_text != desired_text and not typed:
                return ProfessionSurfaceOperationPlan(
                    intent_kind="type_text",
                    target_slot=normalized_intent.input_slot,
                    payload={"text": desired_text},
                    success_assertion={"normalized_text": desired_text},
                )
        return None

    return ProfessionSurfaceOperationOwner(
        formal_session_id=formal_session_id,
        surface_thread_id=surface_thread_id,
        planner=_planner,
        metadata=metadata,
    )


__all__ = [
    "GuidedBrowserSurfaceIntent",
    "GuidedDesktopSurfaceIntent",
    "GuidedDocumentSurfaceIntent",
    "ProfessionSurfaceOperationCheckpoint",
    "ProfessionSurfaceOperationOwner",
    "ProfessionSurfaceOperationPlan",
    "build_guided_browser_surface_owner",
    "build_guided_desktop_surface_owner",
    "build_guided_document_surface_owner",
]
