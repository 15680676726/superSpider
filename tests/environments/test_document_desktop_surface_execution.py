# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib

from copaw.agents.tools.evidence_runtime import bind_file_evidence_sink
from copaw.environments.surface_execution.desktop import (
    DesktopExecutionResult,
    DesktopExecutionStep,
    DesktopObservation,
    DesktopSurfaceExecutionService,
    DesktopTargetCandidate,
)
from copaw.environments.surface_execution.document import (
    DocumentExecutionResult,
    DocumentObservation,
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


def _load_graph_symbol(name: str):
    try:
        module = importlib.import_module("copaw.environments.surface_execution.graph_compiler")
    except ImportError:
        return None
    return getattr(module, name, None)


def _load_probe_symbol(name: str):
    try:
        module = importlib.import_module("copaw.environments.surface_execution.probe_engine")
    except ImportError:
        return None
    return getattr(module, name, None)


def _load_transition_symbol(name: str):
    try:
        module = importlib.import_module("copaw.environments.surface_execution.transition_miner")
    except ImportError:
        return None
    return getattr(module, name, None)


def test_document_graph_snapshot_observation_exposes_surface_graph_contract() -> None:
    observation = DocumentObservation.model_validate(
        {
            "document_path": "D:/tmp/outline.txt",
            "document_family": "documents",
            "content_text": "draft outline",
            "revision_token": "rev-1",
            "surface_graph": {
                "surface_kind": "document",
                "regions": [{"node_id": "region:body"}],
                "controls": [],
                "results": [],
                "blockers": [],
                "entities": [],
                "relations": [],
                "confidence": 0.8,
            },
        }
    )

    payload = observation.model_dump(mode="json")

    assert "surface_graph" in payload
    assert payload["surface_graph"]["surface_kind"] == "document"


def test_document_graph_snapshot_execution_result_keeps_before_after_graph_contract() -> None:
    result = DocumentExecutionResult.model_validate(
        {
            "status": "succeeded",
            "intent_kind": "replace_text",
            "before_graph": {
                "surface_kind": "document",
                "regions": [{"node_id": "region:before"}],
                "controls": [],
                "results": [],
                "blockers": [],
                "entities": [],
                "relations": [],
                "confidence": 0.8,
            },
            "after_graph": {
                "surface_kind": "document",
                "regions": [{"node_id": "region:after"}],
                "controls": [],
                "results": [{"node_id": "result:after"}],
                "blockers": [],
                "entities": [],
                "relations": [{"edge_id": "edge:after"}],
                "confidence": 0.9,
            },
        }
    )

    payload = result.model_dump(mode="json")

    assert payload["before_graph"]["surface_kind"] == "document"
    assert payload["after_graph"]["results"]


def test_document_graph_snapshot_compile_observation_to_graph_returns_shared_snapshot() -> None:
    compile_document = _load_graph_symbol("compile_document_observation_to_graph")
    assert callable(compile_document)

    observation = DocumentObservation(
        document_path="D:/tmp/outline.txt",
        document_family="documents",
        content_text="chapter one draft",
        revision_token="rev-1",
    )

    graph = compile_document(observation)

    assert graph.surface_kind == "document"
    assert graph.regions
    assert graph.results
    assert graph.confidence > 0


def test_desktop_graph_snapshot_observation_exposes_surface_graph_contract() -> None:
    observation = DesktopObservation.model_validate(
        {
            "app_identity": "notepad",
            "window_title": "Research Notes",
            "surface_graph": {
                "surface_kind": "desktop",
                "regions": [{"node_id": "region:window"}],
                "controls": [{"node_id": "control:editor"}],
                "results": [],
                "blockers": [],
                "entities": [],
                "relations": [{"edge_id": "edge:contains"}],
                "confidence": 0.7,
            },
        }
    )

    payload = observation.model_dump(mode="json")

    assert "surface_graph" in payload
    assert payload["surface_graph"]["surface_kind"] == "desktop"


def test_desktop_graph_snapshot_execution_result_keeps_before_after_graph_contract() -> None:
    result = DesktopExecutionResult.model_validate(
        {
            "status": "succeeded",
            "intent_kind": "type_text",
            "target_slot": "primary_input",
            "before_graph": {
                "surface_kind": "desktop",
                "regions": [{"node_id": "region:before"}],
                "controls": [{"node_id": "control:before"}],
                "results": [],
                "blockers": [],
                "entities": [],
                "relations": [],
                "confidence": 0.6,
            },
            "after_graph": {
                "surface_kind": "desktop",
                "regions": [{"node_id": "region:after"}],
                "controls": [{"node_id": "control:after"}],
                "results": [{"node_id": "result:after"}],
                "blockers": [],
                "entities": [],
                "relations": [{"edge_id": "edge:after"}],
                "confidence": 0.9,
            },
        }
    )

    payload = result.model_dump(mode="json")

    assert payload["before_graph"]["surface_kind"] == "desktop"
    assert payload["after_graph"]["relations"]


def test_desktop_graph_snapshot_compile_observation_to_graph_returns_shared_snapshot() -> None:
    compile_desktop = _load_graph_symbol("compile_desktop_observation_to_graph")
    assert callable(compile_desktop)

    observation = DesktopObservation(
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
    )

    graph = compile_desktop(observation)

    assert graph.surface_kind == "desktop"
    assert graph.controls
    assert graph.relations
    assert graph.confidence > 0


def test_shared_probe_engine_requests_refresh_for_low_confidence_document_graph() -> None:
    decide_probe = _load_probe_symbol("decide_surface_probe")
    assert callable(decide_probe)

    graph = _load_graph_symbol("compile_document_observation_to_graph")(
        DocumentObservation(
            document_path="D:/tmp/outline.txt",
            document_family="documents",
            content_text="",
            revision_token="rev-1",
        )
    ).model_copy(update={"confidence": 0.2})

    decision = decide_probe(
        graph,
        intent_kind="replace_text",
        target_slot="document-body",
        target_resolved=True,
    )

    assert decision is not None
    assert decision.probe_action == "refresh-local-region"
    assert decision.target_region == "region:document:root"
    assert decision.reason == "low-confidence-graph"


def test_shared_probe_engine_requests_refresh_for_unresolved_desktop_target() -> None:
    decide_probe = _load_probe_symbol("decide_surface_probe")
    assert callable(decide_probe)

    graph = _load_graph_symbol("compile_desktop_observation_to_graph")(
        DesktopObservation(
            app_identity="notepad",
            window_title="Research Notes",
            slot_candidates={},
            readback={},
        )
    )

    decision = decide_probe(
        graph,
        intent_kind="type_text",
        target_slot="primary_input",
        target_resolved=False,
    )

    assert decision is not None
    assert decision.probe_action == "refresh-local-region"
    assert decision.target_region == "region:desktop:root"
    assert decision.reason == "target-unresolved"


def test_document_surface_service_before_after_graph_executes_replace_text_with_reread_verification() -> None:
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
    assert result.before_graph is not None
    assert result.after_graph is not None
    assert result.before_graph.surface_kind == "document"
    assert result.after_graph.surface_kind == "document"


def test_document_surface_service_emits_surface_probe_before_edit_when_graph_confidence_is_low() -> None:
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
    sink_payloads: list[dict[str, object]] = []

    def _sink(payload: dict[str, object]) -> dict[str, object]:
        sink_payloads.append(dict(payload))
        evidence_kind = str(payload.get("metadata", {}).get("evidence_kind") or "")
        if evidence_kind == "surface-probe":
            return {"evidence_id": "file-probe-1"}
        return {"evidence_id": "file-step-1"}

    before_observation = DocumentObservation(
        document_path="D:/tmp/outline.txt",
        document_family="documents",
        content_text="",
        revision_token="rev-before",
    )
    assert before_observation.surface_graph is None
    compile_document = _load_graph_symbol("compile_document_observation_to_graph")
    assert callable(compile_document)
    before_observation.surface_graph = compile_document(before_observation).model_copy(
        update={"confidence": 0.2},
    )

    with bind_file_evidence_sink(_sink):
        result = service.execute_step(
            session_mount_id="session-doc-1",
            document_path="D:/tmp/outline.txt",
            document_family="documents",
            intent_kind="replace_text",
            payload={"find_text": "draft", "replace_text": "final"},
            success_assertion={"contains_text": "final line"},
            before_observation=before_observation,
        )

    assert result.status == "succeeded"
    assert result.evidence_ids == ["file-probe-1", "file-step-1"]
    assert len(observe_calls) == 2
    assert sink_payloads[0]["metadata"]["evidence_kind"] == "surface-probe"
    assert sink_payloads[0]["metadata"]["probe_action"] == "refresh-local-region"
    assert sink_payloads[1]["action"] == "edit"
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


def test_document_surface_service_attaches_shared_transition_after_edit() -> None:
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
    sink_payloads: list[dict[str, object]] = []

    def _sink(payload: dict[str, object]) -> dict[str, object]:
        sink_payloads.append(dict(payload))
        evidence_kind = str(payload.get("metadata", {}).get("evidence_kind") or "")
        if evidence_kind == "surface-transition":
            return {"evidence_id": "document-transition-1"}
        return {"evidence_id": "document-other-1"}

    with bind_file_evidence_sink(_sink):
        result = service.execute_step(
            session_mount_id="session-doc-1",
            document_path="D:/tmp/outline.txt",
            document_family="documents",
            intent_kind="replace_text",
            payload={"find_text": "draft", "replace_text": "final"},
            success_assertion={"contains_text": "final line"},
        )

    assert result.status == "succeeded"
    assert result.transition is not None
    assert result.transition.changed_nodes == ["result:document:content"]
    assert result.transition.evidence_refs == ["document-transition-1"]


def test_desktop_surface_service_attaches_shared_transition_after_type_text() -> None:
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
            readback={"editor_text": "hello desktop"},
        ),
    ]

    def _observe_desktop(**_kwargs):
        return states.pop(0)

    service = DesktopSurfaceExecutionService(
        desktop_observer=_observe_desktop,
        desktop_runner=lambda **_kwargs: {"ok": True},
    )

    result = service.execute_step(
        session_mount_id="session-desktop-1",
        app_identity="notepad",
        target_slot="primary_input",
        intent_kind="type_text",
        payload={"text": "hello desktop"},
        success_assertion={"normalized_text": "hello desktop"},
    )

    assert result.status == "succeeded"
    assert result.transition is not None
    assert "result:desktop:editor_text" in result.transition.changed_nodes


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


def test_desktop_surface_service_before_after_graph_executes_focus_then_type_with_shared_slots() -> None:
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
    assert loop_result.steps[0].before_graph is not None
    assert loop_result.steps[0].after_graph is not None
    assert loop_result.steps[0].before_graph.surface_kind == "desktop"
    assert loop_result.steps[1].after_graph is not None
    assert loop_result.steps[1].after_graph.surface_kind == "desktop"


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


def test_document_guided_owner_replaces_existing_target_content() -> None:
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
        intent=GuidedDocumentSurfaceIntent(
            desired_content="final line",
            find_text="draft line",
            replace_text="final line",
        ),
    )

    loop_result = service.run_step_loop(
        session_mount_id="session-doc-1",
        document_path="D:/tmp/outline.txt",
        document_family="documents",
        owner=owner,
        max_steps=2,
    )

    assert [step.intent_kind for step in loop_result.steps] == ["replace_text"]
    assert action_calls[0]["action"] == "edit_document_file"


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


def test_desktop_guided_owner_stops_when_focus_is_required_but_window_target_missing() -> None:
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
            readback={"focused_window": ""},
        )
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
        max_steps=2,
    )

    assert loop_result.steps == []
    assert action_calls == []
