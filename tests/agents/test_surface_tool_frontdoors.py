# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import importlib
import json

from copaw.agents.react_agent import _BUILTIN_TOOL_FUNCTIONS
from copaw.capabilities.sources.tools import list_tool_capabilities
from copaw.capabilities.tool_execution_contracts import get_tool_execution_contract
from copaw.environments.surface_execution.desktop import (
    DesktopObservation,
    DesktopTargetCandidate,
)
from copaw.environments.surface_execution.document import DocumentObservation

document_surface_module = importlib.import_module("copaw.agents.tools.document_surface")
desktop_actuation_module = importlib.import_module("copaw.agents.tools.desktop_actuation")
document_surface = document_surface_module.document_surface
desktop_actuation = desktop_actuation_module.desktop_actuation


def _tool_payload(response) -> dict[str, object]:
    return json.loads(response.content[0]["text"])


def test_surface_tool_frontdoors_are_registered_as_builtin_tools() -> None:
    builtins = {tool_fn.__name__ for tool_fn in _BUILTIN_TOOL_FUNCTIONS}
    capability_ids = {mount.id for mount in list_tool_capabilities()}

    assert "document_surface" in builtins
    assert "desktop_actuation" in builtins
    assert "tool:document_surface" in capability_ids
    assert "tool:desktop_actuation" in capability_ids
    assert get_tool_execution_contract("tool:document_surface") is not None
    assert get_tool_execution_contract("tool:desktop_actuation") is not None


def test_document_surface_guided_surface_keeps_same_document_thread(monkeypatch) -> None:
    action_calls: list[dict[str, object]] = []
    observations = [
        DocumentObservation(
            document_path="D:/tmp/story.txt",
            document_family="documents",
            content_text="第一版大纲",
            revision_token="rev-1",
        ),
        DocumentObservation(
            document_path="D:/tmp/story.txt",
            document_family="documents",
            content_text="最终版大纲",
            revision_token="rev-2",
        ),
    ]

    def _observe_document(*, session_mount_id: str, document_path: str, document_family: str = ""):
        _ = session_mount_id, document_path, document_family
        return observations.pop(0)

    def _run_document_action(**kwargs):
        action_calls.append(dict(kwargs))
        return {"ok": True}

    monkeypatch.setattr(document_surface_module, "_observe_guided_document_surface", _observe_document)
    monkeypatch.setattr(document_surface_module, "_run_guided_document_action", _run_document_action)

    payload = _tool_payload(
        asyncio.run(
            document_surface(
                action="guided_surface",
                session_mount_id="session-doc-1",
                document_path="D:/tmp/story.txt",
                content="最终版大纲",
            ),
        )
    )

    assert payload["ok"] is True
    assert payload["steps"] == ["write_document"]
    assert str(payload["document_path"]).replace("\\", "/") == "D:/tmp/story.txt"
    assert payload["operation_checkpoint"]["surface_kind"] == "document"
    assert str(payload["operation_checkpoint"]["surface_thread_id"]).replace("\\", "/") == "D:/tmp/story.txt"
    assert action_calls[0]["action"] == "write_document_file"
    assert action_calls[0]["session_mount_id"] == "session-doc-1"
    assert str(action_calls[0]["document_path"]).replace("\\", "/") == "D:/tmp/story.txt"
    assert action_calls[0]["document_family"] == "documents"
    assert action_calls[0]["content"] == "最终版大纲"


def test_desktop_actuation_guided_surface_keeps_same_window_thread(monkeypatch) -> None:
    action_calls: list[dict[str, object]] = []
    observations = [
        DesktopObservation(
            app_identity="notepad",
            window_title="Research Notes",
            slot_candidates={
                "window_target": [
                    DesktopTargetCandidate(
                        target_kind="window",
                        action_selector="window:notepad",
                        readback_key="focused_window",
                        scope_anchor="window",
                        score=10,
                        label="Research Notes",
                    )
                ],
                "primary_input": [
                    DesktopTargetCandidate(
                        target_kind="input",
                        action_selector="window:notepad/editor",
                        readback_key="editor_text",
                        scope_anchor="editor",
                        score=10,
                        label="Editor",
                    )
                ],
            },
            readback={},
        ),
        DesktopObservation(
            app_identity="notepad",
            window_title="Research Notes",
            slot_candidates={
                "primary_input": [
                    DesktopTargetCandidate(
                        target_kind="input",
                        action_selector="window:notepad/editor",
                        readback_key="editor_text",
                        scope_anchor="editor",
                        score=10,
                        label="Editor",
                    )
                ]
            },
            readback={"focused_window": "window:notepad"},
        ),
        DesktopObservation(
            app_identity="notepad",
            window_title="Research Notes",
            slot_candidates={},
            readback={
                "focused_window": "window:notepad",
                "editor_text": "继续同一个桌面窗口",
            },
        ),
    ]

    def _observe_desktop(*, session_mount_id: str, app_identity: str = "", **_kwargs):
        _ = session_mount_id, app_identity
        return observations.pop(0)

    def _run_desktop_action(**kwargs):
        action_calls.append(dict(kwargs))
        return {"ok": True}

    monkeypatch.setattr(desktop_actuation_module, "_observe_guided_desktop_surface", _observe_desktop)
    monkeypatch.setattr(desktop_actuation_module, "_run_guided_desktop_action", _run_desktop_action)

    payload = _tool_payload(
        asyncio.run(
            desktop_actuation(
                action="guided_surface",
                session_mount_id="session-desktop-1",
                app_identity="notepad",
                text="继续同一个桌面窗口",
            ),
        )
    )

    assert payload["ok"] is True
    assert payload["steps"] == ["focus_window", "type_text"]
    assert payload["app_identity"] == "notepad"
    assert payload["operation_checkpoint"]["surface_kind"] == "desktop"
    assert payload["operation_checkpoint"]["surface_thread_id"] == "notepad"
    assert action_calls[0]["action"] == "focus_window"
    assert action_calls[0]["session_mount_id"] == "session-desktop-1"
    assert action_calls[0]["app_identity"] == "notepad"
    assert action_calls[0]["selector"] == "window:notepad"
    assert action_calls[1]["action"] == "type_text"
    assert action_calls[1]["session_mount_id"] == "session-desktop-1"
    assert action_calls[1]["app_identity"] == "notepad"
    assert action_calls[1]["selector"] == "window:notepad/editor"
    assert action_calls[1]["text"] == "继续同一个桌面窗口"
