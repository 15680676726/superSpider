from __future__ import annotations

from types import SimpleNamespace

import pytest

from copaw.adapters.desktop.windows_uia import ControlSelector, UIAControlError, WindowsUIAAdapter


class _FakeElementInfo:
    def __init__(
        self,
        *,
        handle: int,
        name: str = "",
        automation_id: str = "",
        control_type: str = "",
        class_name: str = "",
    ) -> None:
        self.handle = handle
        self.name = name
        self.automation_id = automation_id
        self.control_type = control_type
        self.class_name = class_name


class _FakeWrapper:
    def __init__(
        self,
        *,
        handle: int,
        name: str = "",
        automation_id: str = "",
        control_type: str = "",
        class_name: str = "",
        children: list["_FakeWrapper"] | None = None,
        enabled: bool = True,
        visible: bool = True,
        support_edit: bool = False,
    ) -> None:
        self.element_info = _FakeElementInfo(
            handle=handle,
            name=name,
            automation_id=automation_id,
            control_type=control_type,
            class_name=class_name,
        )
        self._children = list(children or [])
        self._enabled = enabled
        self._visible = visible
        self._support_edit = support_edit
        self.invoked = 0
        self.clicked = 0
        self.typed: list[str] = []
        self.edit_values: list[str] = []

    def children(self, **_kwargs):
        return list(self._children)

    def window_text(self) -> str:
        return self.element_info.name

    def texts(self) -> list[str]:
        return [self.element_info.name] if self.element_info.name else []

    def rectangle(self):
        return SimpleNamespace(left=1, top=2, right=101, bottom=32)

    def is_enabled(self) -> bool:
        return self._enabled

    def is_visible(self) -> bool:
        return self._visible

    def friendly_class_name(self) -> str:
        return self.element_info.control_type or self.element_info.class_name

    def invoke(self) -> None:
        self.invoked += 1

    def click_input(self, **_kwargs) -> None:
        self.clicked += 1

    def type_keys(self, keys: str, **_kwargs) -> None:
        self.typed.append(keys)

    def set_edit_text(self, text: str, pos_start=None, pos_end=None) -> None:
        if not self._support_edit:
            raise AttributeError("edit pattern not supported")
        _ = (pos_start, pos_end)
        self.edit_values.append(text)


class _FakeWindowSpec:
    def __init__(self, root: _FakeWrapper) -> None:
        self._root = root

    def wrapper_object(self) -> _FakeWrapper:
        return self._root


class _FakeDesktop:
    def __init__(self, root: _FakeWrapper) -> None:
        self._root = root

    def window(self, **kwargs):
        assert kwargs["handle"] == self._root.element_info.handle
        return _FakeWindowSpec(self._root)


def _build_adapter():
    replace_button = _FakeWrapper(
        handle=14,
        name="Replace",
        automation_id="replace",
        control_type="Button",
        class_name="Button",
    )
    ok_button = _FakeWrapper(
        handle=12,
        name="OK",
        automation_id="1",
        control_type="Button",
        class_name="Button",
    )
    cancel_button = _FakeWrapper(
        handle=13,
        name="Cancel",
        automation_id="2",
        control_type="Button",
        class_name="Button",
    )
    edit = _FakeWrapper(
        handle=11,
        name="File name:",
        automation_id="FileNameControlHost",
        control_type="Edit",
        class_name="Edit",
        support_edit=True,
    )
    footer = _FakeWrapper(
        handle=15,
        name="Footer",
        automation_id="footer",
        control_type="Pane",
        class_name="Pane",
        children=[replace_button],
    )
    root = _FakeWrapper(
        handle=10,
        name="Dialog",
        automation_id="root",
        control_type="Window",
        class_name="#32770",
        children=[edit, ok_button, cancel_button, footer],
    )
    adapter = WindowsUIAAdapter(
        platform_name="win32",
        desktop_factory=lambda backend=None: _FakeDesktop(root),
    )
    return adapter, root, edit, ok_button, cancel_button, replace_button


def test_list_controls_filters_controls_by_selector_and_limit() -> None:
    adapter, _root, _edit, ok_button, cancel_button, _replace_button = _build_adapter()

    controls = adapter.list_controls(
        window_handle=10,
        selector=ControlSelector(control_type="Button"),
        limit=2,
    )

    assert [control["handle"] for control in controls] == [
        ok_button.element_info.handle,
        cancel_button.element_info.handle,
    ]


def test_set_control_text_prefers_edit_pattern_when_available() -> None:
    adapter, _root, edit, _ok_button, _cancel_button, _replace_button = _build_adapter()

    result = adapter.set_control_text(
        window_handle=10,
        selector=ControlSelector(automation_id="FileNameControlHost"),
        text=r"C:\tmp\artifact.txt",
    )

    assert result["control"]["handle"] == edit.element_info.handle
    assert edit.edit_values == [r"C:\tmp\artifact.txt"]
    assert edit.typed == []


def test_invoke_dialog_action_resolves_semantic_replace_button() -> None:
    adapter, _root, _edit, _ok_button, _cancel_button, replace_button = _build_adapter()

    result = adapter.invoke_dialog_action(window_handle=10, action="replace")

    assert result["dialog_action"] == "replace"
    assert result["control"]["handle"] == replace_button.element_info.handle
    assert replace_button.invoked == 1


def test_invoke_control_rejects_ambiguous_control_selector() -> None:
    adapter, _root, _edit, _ok_button, _cancel_button, _replace_button = _build_adapter()

    with pytest.raises(UIAControlError) as exc_info:
        adapter.invoke_control(
            window_handle=10,
            selector=ControlSelector(control_type="Button"),
            action="invoke",
        )

    assert exc_info.value.code == "ambiguous_control_selector"
