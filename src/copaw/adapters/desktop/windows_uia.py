# -*- coding: utf-8 -*-
"""UI Automation helpers for semantic Windows dialog/control actions."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Any, Callable

if sys.platform == "win32":  # pragma: no branch
    from pywinauto import Desktop
else:  # pragma: no cover - guarded by platform checks
    Desktop = None


class UIAControlError(RuntimeError):
    """Raised when UIA control discovery or invocation fails."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "uia_control_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class ControlSelector:
    """Stable selector for a control inside a top-level window."""

    handle: int | None = None
    automation_id: str | None = None
    title: str | None = None
    title_contains: str | None = None
    title_regex: str | None = None
    control_type: str | None = None
    class_name: str | None = None
    found_index: int | None = None

    def is_empty(self) -> bool:
        return not any(
            (
                self.handle is not None,
                self.automation_id,
                self.title,
                self.title_contains,
                self.title_regex,
                self.control_type,
                self.class_name,
                self.found_index is not None,
            ),
        )


_DIALOG_ACTION_CANDIDATES: dict[str, tuple[dict[str, str], ...]] = {
    "confirm": (
        {"automation_id": "1", "control_type": "Button"},
        {"title": "OK", "control_type": "Button"},
        {"title_contains": "Yes", "control_type": "Button"},
        {"title_contains": "Continue", "control_type": "Button"},
        {"title_contains": "Save", "control_type": "Button"},
        {"title_contains": "\u786e\u5b9a", "control_type": "Button"},
        {"title_contains": "\u786e\u8ba4", "control_type": "Button"},
        {"title_contains": "\u662f", "control_type": "Button"},
        {"title_contains": "\u7ee7\u7eed", "control_type": "Button"},
        {"title_contains": "\u4fdd\u5b58", "control_type": "Button"},
    ),
    "cancel": (
        {"automation_id": "2", "control_type": "Button"},
        {"title_contains": "Cancel", "control_type": "Button"},
        {"title_contains": "No", "control_type": "Button"},
        {"title_contains": "\u53d6\u6d88", "control_type": "Button"},
        {"title_contains": "\u5426", "control_type": "Button"},
        {"title_contains": "\u5173\u95ed", "control_type": "Button"},
    ),
    "save": (
        {"title_contains": "Save", "control_type": "Button"},
        {"title_contains": "\u4fdd\u5b58", "control_type": "Button"},
        {"automation_id": "1", "control_type": "Button"},
    ),
    "replace": (
        {"title_contains": "Replace", "control_type": "Button"},
        {"title_contains": "\u66ff\u6362", "control_type": "Button"},
    ),
    "dont_save": (
        {"title_contains": "Don't Save", "control_type": "Button"},
        {"title_contains": "Don\u2019t Save", "control_type": "Button"},
        {"title_contains": "Dont Save", "control_type": "Button"},
        {"title_contains": "\u4e0d\u4fdd\u5b58", "control_type": "Button"},
    ),
    "yes": (
        {"title_contains": "Yes", "control_type": "Button"},
        {"title_contains": "\u662f", "control_type": "Button"},
    ),
    "no": (
        {"title_contains": "No", "control_type": "Button"},
        {"title_contains": "\u5426", "control_type": "Button"},
    ),
    "ok": (
        {"title": "OK", "control_type": "Button"},
        {"title_contains": "\u786e\u5b9a", "control_type": "Button"},
        {"title_contains": "\u786e\u8ba4", "control_type": "Button"},
        {"automation_id": "1", "control_type": "Button"},
    ),
}


class WindowsUIAAdapter:
    """Thin pywinauto-backed adapter for semantic control access."""

    def __init__(
        self,
        *,
        platform_name: str | None = None,
        desktop_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._platform_name = platform_name or sys.platform
        self._desktop_factory = desktop_factory or Desktop

    def list_controls(
        self,
        *,
        window_handle: int,
        selector: ControlSelector | None = None,
        include_descendants: bool = True,
        max_depth: int = 4,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        _ = max_depth
        selector = selector or ControlSelector()
        matches: list[dict[str, Any]] = []
        seen: set[tuple[object, ...]] = set()
        for backend in self._backend_names():
            for wrapper, depth in self._backend_controls(
                window_handle=window_handle,
                backend=backend,
                include_descendants=include_descendants,
            ):
                try:
                    if not self._control_matches(wrapper, selector):
                        continue
                    info = self._control_info(wrapper, depth=depth, backend=backend)
                except Exception:
                    continue
                identity = (
                    info["handle"],
                    info["title"],
                    info["automation_id"],
                    info["control_type"],
                    info["class_name"],
                )
                if identity in seen:
                    continue
                seen.add(identity)
                matches.append(info)
        if limit > 0:
            matches = matches[:limit]
        return matches

    def set_control_text(
        self,
        *,
        window_handle: int,
        selector: ControlSelector,
        text: str,
        append: bool = False,
    ) -> dict[str, Any]:
        control = self._resolve_control(window_handle=window_handle, selector=selector)
        if hasattr(control, "set_edit_text"):
            if append:
                existing = control.window_text() or ""
                control.set_edit_text(f"{existing}{text}")
            else:
                control.set_edit_text(text)
        else:
            control.click_input()
            if not append:
                control.type_keys("^a{BACKSPACE}", with_spaces=True, set_foreground=True)
            if text:
                control.type_keys(text, with_spaces=True, set_foreground=True)
        return {
            "control": self._control_info(control),
            "text": text,
            "append": bool(append),
        }

    def invoke_control(
        self,
        *,
        window_handle: int,
        selector: ControlSelector,
        action: str = "invoke",
    ) -> dict[str, Any]:
        control = self._resolve_control(window_handle=window_handle, selector=selector)
        normalized = str(action or "invoke").strip().lower()
        if normalized == "invoke":
            if hasattr(control, "invoke"):
                control.invoke()
            else:
                control.click_input()
        elif normalized == "click":
            control.click_input()
        elif normalized == "double_click":
            control.click_input(double=True)
        else:
            raise UIAControlError(
                f"Unsupported control action: {action}",
                code="unsupported_control_action",
                details={"action": action},
            )
        return {
            "control": self._control_info(control),
            "action": normalized,
        }

    def invoke_dialog_action(
        self,
        *,
        window_handle: int,
        action: str,
        selector: ControlSelector | None = None,
    ) -> dict[str, Any]:
        normalized = str(action or "").strip().lower()
        if not normalized:
            raise UIAControlError("dialog action is required", code="dialog_action_required")
        control_selector = selector
        if control_selector is None or control_selector.is_empty():
            control_selector = self._resolve_semantic_dialog_selector(
                window_handle=window_handle,
                action=normalized,
            )
        result = self.invoke_control(
            window_handle=window_handle,
            selector=control_selector,
            action="invoke",
        )
        return {
            **result,
            "dialog_action": normalized,
        }

    def _resolve_control(
        self,
        *,
        window_handle: int,
        selector: ControlSelector,
    ):
        if selector.is_empty():
            raise UIAControlError("control selector is required", code="control_selector_required")
        query_error: UIAControlError | None = None
        for backend in self._backend_names():
            try:
                return self._query_control(
                    window_handle=window_handle,
                    selector=selector,
                    backend=backend,
                )
            except UIAControlError as exc:
                if exc.code in {
                    "control_not_found",
                    "ambiguous_control_selector",
                    "control_selector_index_out_of_range",
                }:
                    query_error = exc
                    continue
                raise
        matches: list[Any] = []
        seen: set[tuple[object, ...]] = set()
        for backend in self._backend_names():
            for wrapper, _depth in self._backend_controls(
                window_handle=window_handle,
                backend=backend,
                include_descendants=True,
            ):
                if self._control_matches(wrapper, selector):
                    identity = self._control_identity(wrapper)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    matches.append(wrapper)
        if selector.found_index is not None:
            if selector.found_index < 0 or selector.found_index >= len(matches):
                raise UIAControlError(
                    "control selector index is out of range",
                    code="control_selector_index_out_of_range",
                    details={
                        "found_index": selector.found_index,
                        "matched_count": len(matches),
                    },
                )
            return matches[selector.found_index]
        if not matches:
            if query_error is not None:
                raise query_error
            raise UIAControlError(
                "no control matched selector",
                code="control_not_found",
                details={"selector": self._selector_payload(selector)},
            )
        if len(matches) > 1:
            raise UIAControlError(
                "control selector is ambiguous",
                code="ambiguous_control_selector",
                details={
                    "selector": self._selector_payload(selector),
                    "matched_controls": [self._control_info(wrapper) for wrapper in matches[:10]],
                    "matched_count": len(matches),
                },
            )
        return matches[0]

    def _resolve_semantic_dialog_selector(
        self,
        *,
        window_handle: int,
        action: str,
    ) -> ControlSelector:
        candidates = _DIALOG_ACTION_CANDIDATES.get(action)
        if not candidates:
            raise UIAControlError(
                f"Unsupported dialog action: {action}",
                code="unsupported_dialog_action",
                details={"action": action},
            )
        for candidate in candidates:
            try:
                self._resolve_control(
                    window_handle=window_handle,
                    selector=ControlSelector(**candidate),
                )
            except UIAControlError:
                continue
            return ControlSelector(**candidate)
        raise UIAControlError(
            f"No semantic dialog control matched action '{action}'",
            code="dialog_action_not_found",
            details={"action": action},
        )

    def _backend_names(self) -> tuple[str, ...]:
        return ("uia", "win32")

    def _backend_controls(
        self,
        *,
        window_handle: int,
        backend: str,
        include_descendants: bool,
    ) -> list[tuple[Any, int]]:
        try:
            spec = self._desktop_factory(backend=backend).window(handle=int(window_handle))
        except Exception:
            return []
        if include_descendants:
            try:
                descendants = list(spec.descendants())
            except Exception:
                descendants = []
            if descendants:
                return [(wrapper, 1) for wrapper in descendants]
        try:
            wrapper = spec.wrapper_object()
        except Exception:
            return []
        return self._iter_controls(wrapper, include_descendants=include_descendants)

    def _iter_controls(
        self,
        wrapper,
        *,
        include_descendants: bool,
    ) -> list[tuple[Any, int]]:
        controls: list[tuple[Any, int]] = []
        queue: list[tuple[Any, int]] = [(child, 1) for child in list(wrapper.children() or [])]
        while queue:
            current, depth = queue.pop(0)
            controls.append((current, depth))
            if include_descendants:
                queue.extend((child, depth + 1) for child in list(current.children() or []))
        return controls

    def _query_control(
        self,
        *,
        window_handle: int,
        selector: ControlSelector,
        backend: str,
    ):
        criteria = self._query_criteria(selector)
        if not criteria:
            raise UIAControlError(
                "no control matched selector",
                code="control_not_found",
                details={"selector": self._selector_payload(selector), "backend": backend},
            )
        try:
            spec = self._desktop_factory(backend=backend).window(handle=int(window_handle))
            return spec.child_window(**criteria).wrapper_object()
        except Exception as exc:
            message = str(exc).lower()
            code = "control_not_found"
            if "ambiguous" in message or "there are" in message:
                code = "ambiguous_control_selector"
            elif "found_index" in message:
                code = "control_selector_index_out_of_range"
            raise UIAControlError(
                "no control matched selector" if code == "control_not_found" else str(exc),
                code=code,
                details={"selector": self._selector_payload(selector), "backend": backend},
            ) from exc

    def _query_criteria(self, selector: ControlSelector) -> dict[str, Any]:
        criteria: dict[str, Any] = {}
        if selector.handle is not None:
            criteria["handle"] = int(selector.handle)
        if selector.automation_id:
            criteria["auto_id"] = selector.automation_id
        if selector.title:
            criteria["name"] = selector.title
        elif selector.title_contains:
            criteria["name_re"] = f".*{re.escape(selector.title_contains)}.*"
        elif selector.title_regex:
            criteria["name_re"] = selector.title_regex
        if selector.control_type:
            criteria["control_type"] = selector.control_type
        if selector.class_name:
            criteria["class_name"] = selector.class_name
        if selector.found_index is not None:
            criteria["found_index"] = int(selector.found_index)
        return criteria

    def _control_matches(self, wrapper, selector: ControlSelector) -> bool:
        if selector.is_empty():
            return True
        info = self._raw_control_info(wrapper)
        if selector.handle is not None and int(info["handle"] or 0) != int(selector.handle):
            return False
        if selector.automation_id and info["automation_id"] != selector.automation_id:
            return False
        if selector.title and info["title"] != selector.title:
            return False
        if selector.title_contains and selector.title_contains.casefold() not in info["title"].casefold():
            return False
        if selector.title_regex:
            try:
                if re.search(selector.title_regex, info["title"]) is None:
                    return False
            except re.error as exc:
                raise UIAControlError(
                    f"Invalid control title regex: {selector.title_regex}",
                    code="invalid_control_title_regex",
                    details={"title_regex": selector.title_regex},
                ) from exc
        if selector.control_type and info["control_type"].casefold() != selector.control_type.casefold():
            return False
        if selector.class_name and info["class_name"].casefold() != selector.class_name.casefold():
            return False
        return True

    def _raw_control_info(self, wrapper) -> dict[str, Any]:
        element = getattr(wrapper, "element_info", None)
        title = ""
        try:
            title = str(wrapper.window_text() or "")
        except Exception:  # pragma: no cover - defensive
            title = self._safe_element_attr(element, "name")
        return {
            "handle": int(self._safe_element_attr(element, "handle", default=0) or 0),
            "title": title or self._safe_element_attr(element, "name"),
            "automation_id": self._safe_element_attr(element, "automation_id"),
            "control_type": self._safe_element_attr(element, "control_type"),
            "class_name": self._safe_element_attr(element, "class_name"),
        }

    def _safe_element_attr(self, element, name: str, default: object = "") -> str | object:
        try:
            value = getattr(element, name, default)
        except Exception:
            value = default
        return str(value or "") if default == "" else value

    def _control_identity(self, wrapper) -> tuple[object, ...]:
        raw = self._raw_control_info(wrapper)
        return (
            raw["handle"],
            raw["title"],
            raw["automation_id"],
            raw["control_type"],
            raw["class_name"],
        )

    def _control_info(self, wrapper, *, depth: int | None = None, backend: str = "uia") -> dict[str, Any]:
        raw = self._raw_control_info(wrapper)
        rect_payload = {"left": 0, "top": 0, "right": 0, "bottom": 0}
        try:
            rect = wrapper.rectangle()
            rect_payload = {
                "left": int(getattr(rect, "left", 0) or 0),
                "top": int(getattr(rect, "top", 0) or 0),
                "right": int(getattr(rect, "right", 0) or 0),
                "bottom": int(getattr(rect, "bottom", 0) or 0),
            }
        except Exception:  # pragma: no cover - defensive
            pass
        return {
            **raw,
            "backend": backend,
            "friendly_class_name": str(
                getattr(wrapper, "friendly_class_name", lambda: raw["control_type"])()
                or raw["control_type"]
            ),
            "enabled": bool(getattr(wrapper, "is_enabled", lambda: True)()),
            "visible": bool(getattr(wrapper, "is_visible", lambda: True)()),
            "rect": rect_payload,
            "depth": int(depth or 0),
        }

    def _selector_payload(self, selector: ControlSelector) -> dict[str, Any]:
        return {
            "handle": selector.handle,
            "automation_id": selector.automation_id,
            "title": selector.title,
            "title_contains": selector.title_contains,
            "title_regex": selector.title_regex,
            "control_type": selector.control_type,
            "class_name": selector.class_name,
            "found_index": selector.found_index,
        }

    def _ensure_supported(self) -> None:
        if self._platform_name != "win32":
            raise UIAControlError(
                "UIA desktop adapter is only available on Windows hosts",
                code="uia_host_unsupported",
            )
        if self._desktop_factory is None:
            raise UIAControlError(
                "pywinauto Desktop is not available on this host",
                code="uia_runtime_unavailable",
            )
