# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from types import SimpleNamespace

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ...adapters.desktop.windows_host import DesktopAutomationError, WindowSelector, WindowsDesktopHost
from ...adapters.desktop.windows_uia import ControlSelector
from ...environments.surface_execution.desktop import (
    DesktopObservation,
    DesktopTargetCandidate,
)
from ...environments.surface_execution.owner import (
    GuidedDesktopSurfaceIntent,
    build_guided_desktop_surface_owner,
)


def _tool_response(payload: dict[str, object]) -> ToolResponse:
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=json.dumps(payload, ensure_ascii=False, indent=2),
            ),
        ],
    )


def _get_windows_host() -> WindowsDesktopHost:
    return WindowsDesktopHost()


def _window_selector_from_payload(
    *,
    handle: int | None = None,
    title: str = "",
    title_contains: str = "",
    title_regex: str = "",
    process_id: int | None = None,
    app_identity: str = "",
) -> WindowSelector:
    normalized_title_contains = str(title_contains or "").strip() or str(app_identity or "").strip() or None
    return WindowSelector(
        handle=handle,
        title=str(title or "").strip() or None,
        title_contains=normalized_title_contains,
        title_regex=str(title_regex or "").strip() or None,
        process_id=process_id,
    )


def _control_selector_from_payload(
    *,
    control_handle: int | None = None,
    control_automation_id: str = "",
    control_title: str = "",
    control_title_contains: str = "",
    control_title_regex: str = "",
    control_type: str = "",
    control_class_name: str = "",
    control_found_index: int | None = None,
) -> ControlSelector:
    return ControlSelector(
        handle=control_handle,
        automation_id=str(control_automation_id or "").strip() or None,
        title=str(control_title or "").strip() or None,
        title_contains=str(control_title_contains or "").strip() or None,
        title_regex=str(control_title_regex or "").strip() or None,
        control_type=str(control_type or "").strip() or None,
        class_name=str(control_class_name or "").strip() or None,
        found_index=control_found_index,
    )


def _window_action_selector(handle: int) -> str:
    return f"handle:{int(handle)}"


def _window_selector_from_action_selector(action_selector: str) -> WindowSelector:
    text = str(action_selector or "").strip()
    if text.startswith("handle:"):
        try:
            return WindowSelector(handle=int(text.split(":", 1)[1]))
        except Exception:
            return WindowSelector()
    return WindowSelector()


def _best_input_candidate(
    controls: list[dict[str, object]],
    *,
    window_handle: int,
) -> DesktopTargetCandidate | None:
    prioritized = []
    for item in controls:
        control_type = str(item.get("control_type") or "").strip().lower()
        if control_type not in {"edit", "document"}:
            continue
        prioritized.append(item)
    if not prioritized:
        return None
    best = prioritized[0]
    label = (
        str(best.get("title") or "").strip()
        or str(best.get("automation_id") or "").strip()
        or str(best.get("control_type") or "").strip()
        or "Primary input"
    )
    return DesktopTargetCandidate(
        target_kind="input",
        action_selector=_window_action_selector(window_handle),
        readback_key="",
        scope_anchor="window",
        score=10,
        label=label,
    )


def _observe_guided_desktop_surface(
    *,
    session_mount_id: str,
    app_identity: str = "",
    handle: int | None = None,
    title: str = "",
    title_contains: str = "",
    title_regex: str = "",
    process_id: int | None = None,
) -> DesktopObservation:
    _ = session_mount_id
    host = _get_windows_host()
    selector = _window_selector_from_payload(
        handle=handle,
        title=title,
        title_contains=title_contains,
        title_regex=title_regex,
        process_id=process_id,
        app_identity=app_identity,
    )
    blockers: list[str] = []
    windows: list[dict[str, object]] = []
    try:
        result = host.list_windows(selector=selector, include_hidden=False, limit=10)
        windows = list(result.get("windows") or [])
    except Exception as exc:
        blockers.append(f"window-observe-failed:{exc}")
    slot_candidates: dict[str, list[DesktopTargetCandidate]] = {}
    if windows:
        window_targets = [
            DesktopTargetCandidate(
                target_kind="window",
                action_selector=_window_action_selector(int(item["handle"])),
                readback_key="focused_window",
                scope_anchor="window",
                score=max(1, 100 - index),
                label=str(item.get("title") or item.get("class_name") or item["handle"]),
            )
            for index, item in enumerate(windows)
        ]
        slot_candidates["window_target"] = window_targets
        try:
            controls_result = host.list_controls(
                selector=WindowSelector(handle=int(windows[0]["handle"])),
                include_descendants=True,
                limit=50,
            )
            best_input = _best_input_candidate(
                list(controls_result.get("controls") or []),
                window_handle=int(windows[0]["handle"]),
            )
        except Exception:
            best_input = None
        if best_input is None:
            best_input = DesktopTargetCandidate(
                target_kind="input",
                action_selector=_window_action_selector(int(windows[0]["handle"])),
                readback_key="",
                scope_anchor="window",
                score=5,
                label="Focused window input",
            )
        slot_candidates["primary_input"] = [best_input]
    elif not blockers:
        blockers.append("window-not-found")
    readback: dict[str, str] = {}
    try:
        foreground = host.get_foreground_window().get("window") or host.get_foreground_window()
    except Exception:
        foreground = None
    if isinstance(foreground, dict) and foreground.get("handle") is not None:
        readback["focused_window"] = _window_action_selector(int(foreground["handle"]))
    resolved_app_identity = str(app_identity or "").strip() or (
        str(windows[0].get("title") or "").strip() if windows else ""
    )
    return DesktopObservation(
        app_identity=resolved_app_identity,
        window_title=str(windows[0].get("title") or "").strip() if windows else "",
        slot_candidates=slot_candidates,
        readback=readback,
        blockers=blockers,
    )


def _run_guided_desktop_action(
    *,
    action: str,
    session_mount_id: str,
    app_identity: str = "",
    selector: str = "",
    text: str = "",
    keys: str = "",
    executable: str = "",
    args: list[str] | None = None,
    cwd: str = "",
    x: int | None = None,
    y: int | None = None,
    relative_to_window: bool = False,
    click_count: int = 1,
    button: str = "left",
    title: str = "",
    title_contains: str = "",
    title_regex: str = "",
    process_id: int | None = None,
    handle: int | None = None,
    control_handle: int | None = None,
    control_automation_id: str = "",
    control_title: str = "",
    control_title_contains: str = "",
    control_title_regex: str = "",
    control_type: str = "",
    control_class_name: str = "",
    control_found_index: int | None = None,
    dialog_action: str = "",
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    _ = session_mount_id
    host = _get_windows_host()
    selector_payload = _window_selector_from_action_selector(selector)
    if selector_payload.is_empty():
        selector_payload = _window_selector_from_payload(
            handle=handle,
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
            app_identity=app_identity,
        )
    control_selector = _control_selector_from_payload(
        control_handle=control_handle,
        control_automation_id=control_automation_id,
        control_title=control_title,
        control_title_contains=control_title_contains,
        control_title_regex=control_title_regex,
        control_type=control_type,
        control_class_name=control_class_name,
        control_found_index=control_found_index,
    )
    try:
        if action == "launch_application":
            result = host.launch_application(executable=executable, args=args or [], cwd=cwd or None)
        elif action == "wait_for_window":
            result = host.wait_for_window(
                selector=selector_payload,
                timeout_seconds=timeout_seconds,
            )
        elif action == "focus_window":
            result = host.focus_window(selector=selector_payload)
        elif action == "click":
            result = host.click(
                x=x,
                y=y,
                selector=selector_payload,
                relative_to_window=relative_to_window,
                click_count=click_count,
                button=button,
            )
        elif action == "type_text":
            result = host.type_text(text=text, selector=selector_payload)
        elif action == "press_keys":
            result = host.press_keys(keys=keys, selector=selector_payload)
        elif action == "list_controls":
            result = host.list_controls(selector=selector_payload, control_selector=control_selector)
        elif action == "set_control_text":
            result = host.set_control_text(
                selector=selector_payload,
                control_selector=control_selector,
                text=text,
            )
        elif action == "invoke_control":
            result = host.invoke_control(
                selector=selector_payload,
                control_selector=control_selector,
            )
        elif action == "invoke_dialog_action":
            result = host.invoke_dialog_action(
                selector=selector_payload,
                action=dialog_action,
                control_selector=None if control_selector.is_empty() else control_selector,
            )
        elif action == "close_window":
            result = host.close_window(selector=selector_payload)
        elif action == "verify_window_focus":
            result = host.verify_window_focus(selector=selector_payload)
        else:
            return {"ok": False, "error": f"Unsupported desktop action: {action}"}
    except DesktopAutomationError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "error_code": exc.code,
            "details": dict(exc.details),
            "action": action,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "action": action,
        }
    return {
        "ok": True,
        "action": action,
        **dict(result),
    }


async def _action_guided_surface(
    *,
    session_mount_id: str,
    app_identity: str,
    text: str,
    title: str = "",
    title_contains: str = "",
    title_regex: str = "",
    process_id: int | None = None,
    handle: int | None = None,
    require_focus: bool = True,
    max_steps: int = 4,
) -> ToolResponse:
    observation = _observe_guided_desktop_surface(
        session_mount_id=session_mount_id,
        app_identity=app_identity,
        handle=handle,
        title=title,
        title_contains=title_contains,
        title_regex=title_regex,
        process_id=process_id,
    )
    owner = build_guided_desktop_surface_owner(
        formal_session_id=session_mount_id or "default",
        surface_thread_id=str(app_identity or title or title_contains or handle or "desktop"),
        intent=GuidedDesktopSurfaceIntent(
            desired_text=text,
            require_focus=require_focus,
        ),
    )
    history: list[object] = []
    stop_reason = "planner-stop"
    blocker_kind = ""
    for _ in range(max(1, int(max_steps or 0))):
        checkpoint = owner.build_checkpoint(
            surface_kind="desktop",
            step_index=len(history),
            history=history,
        )
        step = owner.plan(
            observation=observation,
            history=history,
            checkpoint=checkpoint,
        )
        if step is None:
            if observation.blockers:
                stop_reason = "blocker-stop"
                blocker_kind = str(observation.blockers[0])
            break
        target_candidates = list((observation.slot_candidates or {}).get(step.target_slot) or [])
        selector = str(target_candidates[0].action_selector or "") if target_candidates else ""
        if step.intent_kind == "focus_window":
            result = _run_guided_desktop_action(
                action="focus_window",
                session_mount_id=session_mount_id,
                app_identity=app_identity,
                selector=selector,
                title=title,
                title_contains=title_contains,
                title_regex=title_regex,
                process_id=process_id,
                handle=handle,
            )
        elif step.intent_kind == "type_text":
            result = _run_guided_desktop_action(
                action="type_text",
                session_mount_id=session_mount_id,
                app_identity=app_identity,
                selector=selector,
                text=str(step.payload.get("text") or text),
                title=title,
                title_contains=title_contains,
                title_regex=title_regex,
                process_id=process_id,
                handle=handle,
            )
        else:
            result = {
                "ok": False,
                "error": f"Unsupported guided desktop step: {step.intent_kind}",
            }
        if not bool(result.get("ok")):
            stop_reason = "step-failed"
            blocker_kind = str(result.get("error") or "desktop-action-failed").strip()
            history.append(
                SimpleNamespace(
                    intent_kind=step.intent_kind,
                    target_slot=step.target_slot,
                    status="failed",
                    blocker_kind=blocker_kind,
                    readback={},
                )
            )
            break
        observation = _observe_guided_desktop_surface(
            session_mount_id=session_mount_id,
            app_identity=app_identity,
            handle=handle,
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
        )
        readback = {}
        verification_passed = True
        if step.intent_kind == "focus_window":
            expected = str(step.success_assertion.get("focused_selector") or "")
            observed = str((observation.readback or {}).get("focused_window") or "")
            verification_passed = not expected or observed == expected
            readback = {"focused_window": observed}
        elif step.intent_kind == "type_text":
            readback = {
                "observed_text": str(result.get("text") or text),
                "normalized_text": str(result.get("text") or text).strip(),
            }
            expected = str(step.success_assertion.get("normalized_text") or "")
            verification_passed = not expected or readback["normalized_text"] == expected
        if not verification_passed:
            stop_reason = "step-failed"
            blocker_kind = "verification-failed"
        history.append(
            SimpleNamespace(
                intent_kind=step.intent_kind,
                target_slot=step.target_slot,
                status="succeeded" if verification_passed else "failed",
                blocker_kind="" if verification_passed else blocker_kind,
                readback=readback,
            )
        )
        if not verification_passed:
            break
    operation_checkpoint = owner.build_checkpoint(
        surface_kind="desktop",
        step_index=len(history),
        history=history,
    )
    ok = stop_reason in {"planner-stop", "max-steps"} and not blocker_kind
    if not history and not observation.blockers:
        ok = True
    payload = {
        "ok": ok,
        "action": "guided_surface",
        "session_mount_id": session_mount_id,
        "app_identity": str(app_identity or "").strip(),
        "steps": [str(getattr(item, "intent_kind", "") or "") for item in history],
        "stop_reason": stop_reason,
        "blocker_kind": blocker_kind,
        "operation_checkpoint": operation_checkpoint.model_dump(mode="json"),
        "final_observation": observation.model_dump(mode="json"),
    }
    if not ok:
        payload["error"] = blocker_kind or stop_reason
    return _tool_response(payload)


async def desktop_actuation(
    *,
    action: str = "guided_surface",
    session_mount_id: str = "",
    app_identity: str = "",
    title: str = "",
    title_contains: str = "",
    title_regex: str = "",
    process_id: int | None = None,
    handle: int | None = None,
    text: str = "",
    keys: str = "",
    executable: str = "",
    args: list[str] | None = None,
    cwd: str = "",
    x: int | None = None,
    y: int | None = None,
    relative_to_window: bool = False,
    click_count: int = 1,
    button: str = "left",
    control_handle: int | None = None,
    control_automation_id: str = "",
    control_title: str = "",
    control_title_contains: str = "",
    control_title_regex: str = "",
    control_type: str = "",
    control_class_name: str = "",
    control_found_index: int | None = None,
    dialog_action: str = "",
    timeout_seconds: float = 10.0,
    require_focus: bool = True,
    max_steps: int = 4,
) -> ToolResponse:
    """Operate a desktop window through a guided or direct desktop frontdoor."""
    normalized_action = str(action or "").strip().lower() or "guided_surface"
    if normalized_action == "observe":
        observation = _observe_guided_desktop_surface(
            session_mount_id=session_mount_id,
            app_identity=app_identity,
            handle=handle,
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
        )
        return _tool_response(
            {
                "ok": not bool(observation.blockers),
                "action": normalized_action,
                "observation": observation.model_dump(mode="json"),
            }
        )
    if normalized_action == "guided_surface":
        return await _action_guided_surface(
            session_mount_id=session_mount_id,
            app_identity=app_identity,
            text=text,
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
            handle=handle,
            require_focus=require_focus,
            max_steps=max_steps,
        )
    result = _run_guided_desktop_action(
        action=normalized_action,
        session_mount_id=session_mount_id,
        app_identity=app_identity,
        text=text,
        keys=keys,
        executable=executable,
        args=args or [],
        cwd=cwd,
        x=x,
        y=y,
        relative_to_window=relative_to_window,
        click_count=click_count,
        button=button,
        title=title,
        title_contains=title_contains,
        title_regex=title_regex,
        process_id=process_id,
        handle=handle,
        control_handle=control_handle,
        control_automation_id=control_automation_id,
        control_title=control_title,
        control_title_contains=control_title_contains,
        control_title_regex=control_title_regex,
        control_type=control_type,
        control_class_name=control_class_name,
        control_found_index=control_found_index,
        dialog_action=dialog_action,
        timeout_seconds=timeout_seconds,
    )
    return _tool_response(result)


__all__ = ["desktop_actuation"]
