# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.agents.tools.evidence_runtime import bind_file_evidence_sink
from copaw.environments.surface_execution.desktop import (
    DesktopExecutionStep,
    DesktopObservation,
    DesktopSurfaceExecutionService,
    DesktopTargetCandidate,
)
from copaw.environments.surface_execution.document import (
    DocumentExecutionStep,
    DocumentSurfaceExecutionService,
)
from copaw.environments.surface_execution.owner import (
    GuidedDesktopSurfaceIntent,
    GuidedDocumentSurfaceIntent,
    ProfessionSurfaceOperationOwner,
    ProfessionSurfaceOperationPlan,
    build_guided_desktop_surface_owner,
    build_guided_document_surface_owner,
)


def test_document_surface_service_executes_replace_text_with_reread_verification() -> None:
    observe_calls: list[dict[str, object]] = []
    action_calls: list[dict[str, object]] = []
    contents = ["draft line", "final line"]

    def _observe_document(**kwargs):
        observe_calls.append(dict(kwargs))
        return {
            "document_path": str(kwargs["document_path"]),
            "document_family": str(kwargs.get("document_family") or "documents"),
            "content_text": contents.pop(0),
            "revision_token": f"rev-{len(observe_calls)}",
        }

    def _run_document_action(**kwargs):
        action_calls.append(dict(kwargs))
        return {"ok": True}

    service = DocumentSurfaceExecutionService(
        document_observer=_observe_document,
        document_runner=_run_document_action,
    )
    evidence_payloads: list[dict[str, object]] = []
    with bind_file_evidence_sink(lambda payload: evidence_payloads.append(dict(payload)) or {"evidence_id": "file-ev-1"}):
        result = service.execute_step(
            session_mount_id="session-doc-1",
            document_path="D:/tmp/outline.txt",
            document_family="documents",
            intent_kind="replace_text",
            payload={"find_text": "draft", "replace_text": "final"},
            success_assertion={"contains_text": "final line"},
        )

    assert result.status == "succeeded"
    assert result.verification_passed is True
    assert result.before_observation is not None
    assert result.after_observation is not None
    assert result.after_observation.content_text == "final line"
    assert result.evidence_ids == ["file-ev-1"]
    assert len(observe_calls) == 2
    assert action_calls == [
        {
            "action": "edit_document_file",
            "session_mount_id": "session-doc-1",
            "document_path": "D:/tmp/outline.txt",
            "document_family": "documents",
            "find_text": "draft",
            "replace_text": "final",
        }
    ]
    assert evidence_payloads[0]["action"] == "edit"


def test_document_surface_service_run_step_loop_reuses_initial_observation() -> None:
    observe_calls: list[dict[str, object]] = []
    contents = ["draft line", "final line"]

    def _observe_document(**kwargs):
        observe_calls.append(dict(kwargs))
        return {
            "document_path": str(kwargs["document_path"]),
            "document_family": str(kwargs.get("document_family") or "documents"),
            "content_text": contents.pop(0),
            "revision_token": f"rev-{len(observe_calls)}",
        }

    service = DocumentSurfaceExecutionService(
        document_observer=_observe_document,
        document_runner=lambda **_kwargs: {"ok": True},
    )
    initial_observation = service.observe_document(
        session_mount_id="session-doc-1",
        document_path="D:/tmp/outline.txt",
        document_family="documents",
    )
    observe_calls.clear()

    def _planner(_observation, history):
        if history:
            return None
        return DocumentExecutionStep(
            intent_kind="replace_text",
            payload={"find_text": "draft", "replace_text": "final"},
            success_assertion={"contains_text": "final line"},
        )

    loop_result = service.run_step_loop(
        session_mount_id="session-doc-1",
        document_path="D:/tmp/outline.txt",
        document_family="documents",
        planner=_planner,
        initial_observation=initial_observation,
        max_steps=2,
    )

    assert loop_result.stop_reason == "planner-stop"
    assert len(loop_result.steps) == 1
    assert len(observe_calls) == 1


def test_document_surface_service_run_step_loop_accepts_shared_profession_owner_checkpoint() -> None:
    contents = ["draft line", "final line"]

    def _observe_document(**kwargs):
        return {
            "document_path": str(kwargs["document_path"]),
            "document_family": str(kwargs.get("document_family") or "documents"),
            "content_text": contents.pop(0),
            "revision_token": f"rev-{len(contents)}",
        }

    service = DocumentSurfaceExecutionService(
        document_observer=_observe_document,
        document_runner=lambda **_kwargs: {"ok": True},
    )
    checkpoints: list[tuple[str, str, str, int]] = []

    def _planner(*, observation, history, checkpoint):
        checkpoints.append(
            (
                checkpoint.formal_session_id,
                checkpoint.surface_kind,
                checkpoint.surface_thread_id,
                checkpoint.step_index,
            )
        )
        if history:
            return None
        return ProfessionSurfaceOperationPlan(
            intent_kind="replace_text",
            payload={"find_text": "draft", "replace_text": "final"},
            success_assertion={"contains_text": "final line"},
        )

    owner = ProfessionSurfaceOperationOwner(
        formal_session_id="research-session-1",
        surface_thread_id="D:/tmp/outline.txt",
        planner=_planner,
    )

    loop_result = service.run_step_loop(
        session_mount_id="session-doc-1",
        document_path="D:/tmp/outline.txt",
        document_family="documents",
        owner=owner,
        max_steps=2,
    )

    assert checkpoints == [
        ("research-session-1", "document", "D:/tmp/outline.txt", 0),
        ("research-session-1", "document", "D:/tmp/outline.txt", 1),
    ]
    assert loop_result.stop_reason == "planner-stop"
    assert loop_result.operation_checkpoint is not None
    assert loop_result.operation_checkpoint.surface_kind == "document"
    assert loop_result.operation_checkpoint.surface_thread_id == "D:/tmp/outline.txt"
    assert loop_result.operation_checkpoint.last_status == "succeeded"


def test_desktop_surface_service_executes_focus_then_type_with_shared_slots() -> None:
    observe_calls: list[dict[str, object]] = []
    action_calls: list[dict[str, object]] = []
    states = [
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
                "editor_text": "hello desktop",
            },
        ),
    ]

    def _observe_desktop(**kwargs):
        observe_calls.append(dict(kwargs))
        return states.pop(0)

    def _run_desktop_action(**kwargs):
        action_calls.append(dict(kwargs))
        return {"ok": True}

    service = DesktopSurfaceExecutionService(
        desktop_observer=_observe_desktop,
        desktop_runner=_run_desktop_action,
    )

    def _planner(_observation, history):
        if not history:
            return DesktopExecutionStep(
                intent_kind="focus_window",
                target_slot="window_target",
                success_assertion={"focused_selector": "window:notepad"},
            )
        if len(history) == 1:
            return DesktopExecutionStep(
                intent_kind="type_text",
                target_slot="primary_input",
                payload={"text": "hello desktop"},
                success_assertion={"normalized_text": "hello desktop"},
            )
        return None

    loop_result = service.run_step_loop(
        session_mount_id="session-desktop-1",
        app_identity="notepad",
        planner=_planner,
        max_steps=3,
    )

    assert loop_result.stop_reason == "planner-stop"
    assert [step.intent_kind for step in loop_result.steps] == ["focus_window", "type_text"]
    assert all(step.status == "succeeded" for step in loop_result.steps)
    assert action_calls == [
        {
            "action": "focus_window",
            "session_mount_id": "session-desktop-1",
            "app_identity": "notepad",
            "selector": "window:notepad",
        },
        {
            "action": "type_text",
            "session_mount_id": "session-desktop-1",
            "app_identity": "notepad",
            "selector": "window:notepad/editor",
            "text": "hello desktop",
        },
    ]
    assert len(observe_calls) == 3


def test_desktop_surface_service_run_step_loop_accepts_shared_profession_owner_checkpoint() -> None:
    states = [
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
            readback={},
        ),
        DesktopObservation(
            app_identity="notepad",
            window_title="Research Notes",
            slot_candidates={},
            readback={"editor_text": "resume same desktop thread"},
        ),
    ]

    def _observe_desktop(**_kwargs):
        return states.pop(0)

    service = DesktopSurfaceExecutionService(
        desktop_observer=_observe_desktop,
        desktop_runner=lambda **_kwargs: {"ok": True},
    )
    checkpoints: list[tuple[str, str, str, int]] = []

    def _planner(*, observation, history, checkpoint):
        checkpoints.append(
            (
                checkpoint.formal_session_id,
                checkpoint.surface_kind,
                checkpoint.surface_thread_id,
                checkpoint.step_index,
            )
        )
        if history:
            return None
        return ProfessionSurfaceOperationPlan(
            intent_kind="type_text",
            target_slot="primary_input",
            payload={"text": "resume same desktop thread"},
            success_assertion={"normalized_text": "resume same desktop thread"},
        )

    owner = ProfessionSurfaceOperationOwner(
        formal_session_id="research-session-1",
        surface_thread_id="notepad",
        planner=_planner,
    )

    loop_result = service.run_step_loop(
        session_mount_id="session-desktop-1",
        app_identity="notepad",
        owner=owner,
        max_steps=2,
    )

    assert checkpoints == [
        ("research-session-1", "desktop", "notepad", 0),
        ("research-session-1", "desktop", "notepad", 1),
    ]
    assert loop_result.stop_reason == "planner-stop"
    assert loop_result.operation_checkpoint is not None
    assert loop_result.operation_checkpoint.surface_kind == "desktop"
    assert loop_result.operation_checkpoint.surface_thread_id == "notepad"
    assert loop_result.operation_checkpoint.last_status == "succeeded"


def test_document_guided_owner_writes_missing_target_content() -> None:
    action_calls: list[dict[str, object]] = []
    contents = ["draft line", "final line"]

    def _observe_document(**kwargs):
        return {
            "document_path": str(kwargs["document_path"]),
            "document_family": str(kwargs.get("document_family") or "documents"),
            "content_text": contents.pop(0),
            "revision_token": f"rev-{len(contents)}",
        }

    def _run_document_action(**kwargs):
        action_calls.append(dict(kwargs))
        return {"ok": True}

    service = DocumentSurfaceExecutionService(
        document_observer=_observe_document,
        document_runner=_run_document_action,
    )
    owner = build_guided_document_surface_owner(
        formal_session_id="profession-session-1",
        surface_thread_id="D:/tmp/outline.txt",
        intent=GuidedDocumentSurfaceIntent(desired_content="final line"),
    )

    loop_result = service.run_step_loop(
        session_mount_id="session-doc-1",
        document_path="D:/tmp/outline.txt",
        document_family="documents",
        owner=owner,
        max_steps=2,
    )

    assert [step.intent_kind for step in loop_result.steps] == ["write_document"]
    assert action_calls[0]["action"] == "write_document_file"


def test_desktop_guided_owner_focuses_then_types() -> None:
    states = [
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
                "editor_text": "hello guided desktop",
            },
        ),
    ]
    action_calls: list[dict[str, object]] = []

    def _observe_desktop(**_kwargs):
        return states.pop(0)

    def _run_desktop_action(**kwargs):
        action_calls.append(dict(kwargs))
        return {"ok": True}

    service = DesktopSurfaceExecutionService(
        desktop_observer=_observe_desktop,
        desktop_runner=_run_desktop_action,
    )
    owner = build_guided_desktop_surface_owner(
        formal_session_id="profession-session-1",
        surface_thread_id="notepad",
        intent=GuidedDesktopSurfaceIntent(desired_text="hello guided desktop"),
    )

    loop_result = service.run_step_loop(
        session_mount_id="session-desktop-1",
        app_identity="notepad",
        owner=owner,
        max_steps=3,
    )

    assert [step.intent_kind for step in loop_result.steps] == ["focus_window", "type_text"]
    assert action_calls[0]["action"] == "focus_window"
    assert action_calls[1]["action"] == "type_text"
