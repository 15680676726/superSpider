# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.evidence import ArtifactRecord, EvidenceRecord, ReplayPointer
from copaw.kernel import KernelTask, KernelToolBridge


def test_shell_replay_pointer_sanitizes_windows_unsafe_task_id(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("copaw.kernel.tool_bridge.WORKING_DIR", tmp_path)
    bridge = KernelToolBridge(task_store=object())

    pointer = bridge._build_shell_replay_pointer(
        task=KernelTask(
            id="ctask:cu:20260312070211912789-1d103753:1",
            title="Replay shell command",
            capability_ref="tool:execute_shell_command",
            owner_agent_id="ops-agent",
            risk_level="guarded",
        ),
        payload={"cwd": "D:/word/copaw", "timeout": 30},
        environment_ref="D:/word/copaw",
        command="echo hello",
    )

    assert pointer is not None
    replay_files = list((tmp_path / "evidence" / "replays").glob("*.json"))
    assert len(replay_files) == 1
    assert ":" not in replay_files[0].name


def test_shell_replay_pointer_truncates_overlong_task_id_for_windows_paths(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("copaw.kernel.tool_bridge.WORKING_DIR", tmp_path)
    bridge = KernelToolBridge(task_store=object())
    long_task_id = "query:" + ("industry-chat:buddy:demo:" * 18) + "tool:execute_shell_command:abcdef"

    pointer = bridge._build_shell_replay_pointer(
        task=KernelTask(
            id=long_task_id,
            title="Replay shell command",
            capability_ref="tool:execute_shell_command",
            owner_agent_id="ops-agent",
            risk_level="guarded",
        ),
        payload={"cwd": "D:/word/copaw", "timeout": 30},
        environment_ref="D:/word/copaw",
        command="echo hello",
    )

    assert pointer is not None
    replay_files = list((tmp_path / "evidence" / "replays").glob("*.json"))
    assert len(replay_files) == 1
    assert len(replay_files[0].name) < 180


def test_tool_bridge_preserves_blocked_status_and_contract_metadata() -> None:
    class _FakeTaskStore:
        def __init__(self) -> None:
            self.task = KernelTask(
                id="ktask:blocked-shell",
                title="Blocked shell evidence",
                capability_ref="tool:execute_shell_command",
                owner_agent_id="ops-agent",
                risk_level="guarded",
            )
            self.appended: list[dict[str, object]] = []
            self.upserts: list[dict[str, object]] = []

        def get(self, task_id: str) -> KernelTask | None:
            return self.task if task_id == self.task.id else None

        def append_evidence(self, task: KernelTask, **kwargs):
            self.appended.append(kwargs)
            return SimpleNamespace(id="evidence-1")

        def upsert(self, task: KernelTask, **kwargs) -> None:
            self.upserts.append(kwargs)

    store = _FakeTaskStore()
    bridge = KernelToolBridge(task_store=store)

    bridge.record_shell_event(
        "ktask:blocked-shell",
        {
            "status": "blocked",
            "command": "git reset --hard HEAD",
            "stderr": "Blocked by shell safety policy: git reset --hard HEAD",
            "tool_contract": "tool:execute_shell_command",
            "concurrency_class": "serial-write",
            "preflight_policy": "shell-safety",
            "outcome_kind": "blocked",
            "read_only": False,
        },
    )

    assert store.appended
    appended = store.appended[0]
    assert appended["status"] == "blocked"
    assert appended["metadata"]["tool_contract"] == "tool:execute_shell_command"
    assert appended["metadata"]["concurrency_class"] == "serial-write"
    assert appended["metadata"]["preflight_policy"] == "shell-safety"
    assert appended["metadata"]["outcome_kind"] == "blocked"
    assert store.upserts[0]["last_error_summary"].startswith("Shell command blocked")


def test_tool_bridge_builds_formal_file_result_items_from_recorded_evidence() -> None:
    class _FakeTaskStore:
        def __init__(self) -> None:
            self.task = KernelTask(
                id="ktask:file-result",
                title="File result evidence",
                capability_ref="tool:write_file",
                owner_agent_id="ops-agent",
                risk_level="auto",
            )

        def get(self, task_id: str) -> KernelTask | None:
            return self.task if task_id == self.task.id else None

        def append_evidence(self, task: KernelTask, **kwargs):
            artifacts = tuple(
                ArtifactRecord(
                    id=f"artifact-file-{index}",
                    artifact_type=artifact.artifact_type,
                    storage_uri=artifact.storage_uri,
                    summary=artifact.summary,
                    metadata=artifact.metadata,
                ).materialize(evidence_id="evidence-file-1")
                for index, artifact in enumerate(tuple(kwargs.get("artifacts") or ()), start=1)
            )
            replays = tuple(
                ReplayPointer(
                    id=f"replay-file-{index}",
                    replay_type=replay.replay_type,
                    storage_uri=replay.storage_uri,
                    summary=replay.summary,
                    metadata=replay.metadata,
                ).materialize(evidence_id="evidence-file-1")
                for index, replay in enumerate(tuple(kwargs.get("replay_pointers") or ()), start=1)
            )
            return EvidenceRecord(
                id="evidence-file-1",
                task_id=task.id,
                actor_ref=kwargs.get("actor_ref") or "tool:write_file",
                environment_ref=kwargs.get("environment_ref"),
                capability_ref=kwargs.get("capability_ref"),
                risk_level=task.risk_level,
                action_summary=kwargs["action_summary"],
                result_summary=kwargs["result_summary"],
                status=kwargs["status"],
                metadata=kwargs.get("metadata") or {},
                artifacts=artifacts,
                replay_pointers=replays,
            )

        def upsert(self, task: KernelTask, **kwargs) -> None:
            _ = (task, kwargs)

    bridge = KernelToolBridge(task_store=_FakeTaskStore())

    tool_use_summary = bridge.record_file_event(
        "ktask:file-result",
        {
            "tool_name": "write_file",
            "action": "write",
            "resolved_path": "D:/word/copaw/report.md",
            "status": "success",
            "result_summary": "saved report",
        },
    )

    assert tool_use_summary == {
        "evidence_id": "evidence-file-1",
        "summary": "saved report",
        "artifact_refs": ["D:/word/copaw/report.md"],
        "result_items": [
            {
                "ref": "D:/word/copaw/report.md",
                "kind": "file",
                "label": "文件",
                "summary": "saved report",
                "route": "/api/runtime-center/artifacts/artifact-file-1",
            },
        ],
    }


def test_tool_bridge_builds_formal_replay_result_items_from_recorded_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    class _FakeTaskStore:
        def __init__(self) -> None:
            self.task = KernelTask(
                id="ktask:shell-result",
                title="Shell result evidence",
                capability_ref="tool:execute_shell_command",
                owner_agent_id="ops-agent",
                risk_level="guarded",
            )

        def get(self, task_id: str) -> KernelTask | None:
            return self.task if task_id == self.task.id else None

        def append_evidence(self, task: KernelTask, **kwargs):
            replays = tuple(
                ReplayPointer(
                    id=f"replay-shell-{index}",
                    replay_type=replay.replay_type,
                    storage_uri=replay.storage_uri,
                    summary=replay.summary,
                    metadata=replay.metadata,
                ).materialize(evidence_id="evidence-shell-1")
                for index, replay in enumerate(tuple(kwargs.get("replay_pointers") or ()), start=1)
            )
            return EvidenceRecord(
                id="evidence-shell-1",
                task_id=task.id,
                actor_ref=kwargs.get("actor_ref") or "tool:execute_shell_command",
                environment_ref=kwargs.get("environment_ref"),
                capability_ref=kwargs.get("capability_ref"),
                risk_level=task.risk_level,
                action_summary=kwargs["action_summary"],
                result_summary=kwargs["result_summary"],
                status=kwargs["status"],
                metadata=kwargs.get("metadata") or {},
                replay_pointers=replays,
            )

        def upsert(self, task: KernelTask, **kwargs) -> None:
            _ = (task, kwargs)

    monkeypatch.setattr("copaw.kernel.tool_bridge.WORKING_DIR", tmp_path)
    bridge = KernelToolBridge(task_store=_FakeTaskStore())

    tool_use_summary = bridge.record_shell_event(
        "ktask:shell-result",
        {
            "command": "git status",
            "cwd": "D:/word/copaw",
            "status": "success",
            "stdout": "working tree clean",
            "stderr": "",
        },
    )

    assert tool_use_summary is not None
    assert len(tool_use_summary["artifact_refs"]) == 1
    assert str(tool_use_summary["artifact_refs"][0]).startswith("file:///")
    assert tool_use_summary["result_items"] == [
        {
            "ref": tool_use_summary["artifact_refs"][0],
            "kind": "replay",
            "label": "回放",
            "summary": "Replay shell command: git status",
            "route": "/api/runtime-center/replays/replay-shell-1",
        },
    ]
    assert tool_use_summary["summary"] == "Replay shell command: git status"


def test_tool_bridge_builds_formal_screenshot_result_items_from_browser_evidence() -> None:
    class _FakeTaskStore:
        def __init__(self) -> None:
            self.task = KernelTask(
                id="ktask:browser-screenshot",
                title="Browser screenshot evidence",
                capability_ref="tool:browser_use",
                owner_agent_id="ops-agent",
                risk_level="guarded",
            )

        def get(self, task_id: str) -> KernelTask | None:
            return self.task if task_id == self.task.id else None

        def append_evidence(self, task: KernelTask, **kwargs):
            artifacts = tuple(
                ArtifactRecord(
                    id=f"artifact-browser-{index}",
                    artifact_type=artifact.artifact_type,
                    storage_uri=artifact.storage_uri,
                    summary=artifact.summary,
                    metadata=artifact.metadata,
                ).materialize(evidence_id="evidence-browser-1")
                for index, artifact in enumerate(tuple(kwargs.get("artifacts") or ()), start=1)
            )
            return EvidenceRecord(
                id="evidence-browser-1",
                task_id=task.id,
                actor_ref=kwargs.get("actor_ref") or "tool:browser_use",
                environment_ref=kwargs.get("environment_ref"),
                capability_ref=kwargs.get("capability_ref"),
                risk_level=task.risk_level,
                action_summary=kwargs["action_summary"],
                result_summary=kwargs["result_summary"],
                status=kwargs["status"],
                metadata=kwargs.get("metadata") or {},
                artifacts=artifacts,
            )

        def upsert(self, task: KernelTask, **kwargs) -> None:
            _ = (task, kwargs)

    bridge = KernelToolBridge(task_store=_FakeTaskStore())

    tool_use_summary = bridge.record_browser_event(
        "ktask:browser-screenshot",
        {
            "action": "screenshot",
            "page_id": "page-1",
            "status": "success",
            "result_summary": "Saved screenshot for operator review",
            "metadata": {
                "path": "D:/word/copaw/artifacts/browser-shot.png",
                "verification": {
                    "kind": "artifact",
                    "artifact": {
                        "path": "D:/word/copaw/artifacts/browser-shot.png",
                        "exists": True,
                    },
                },
            },
        },
    )

    assert tool_use_summary is not None
    assert tool_use_summary["evidence_id"] == "evidence-browser-1"
    assert tool_use_summary["summary"] == "Saved screenshot for operator review"
    assert tool_use_summary["artifact_refs"] == [
        "D:/word/copaw/artifacts/browser-shot.png",
    ]
    assert len(tool_use_summary["result_items"]) == 1
    result_item = tool_use_summary["result_items"][0]
    assert result_item["ref"] == "D:/word/copaw/artifacts/browser-shot.png"
    assert result_item["kind"] == "screenshot"
    assert str(result_item["label"]).strip()
    assert result_item["summary"] == "Saved screenshot for operator review"
    assert result_item["route"] == "/api/runtime-center/artifacts/artifact-browser-1"


def test_tool_bridge_builds_formal_download_file_result_items_from_browser_evidence() -> None:
    class _FakeTaskStore:
        def __init__(self) -> None:
            self.task = KernelTask(
                id="ktask:browser-download",
                title="Browser download evidence",
                capability_ref="tool:browser_use",
                owner_agent_id="ops-agent",
                risk_level="guarded",
            )

        def get(self, task_id: str) -> KernelTask | None:
            return self.task if task_id == self.task.id else None

        def append_evidence(self, task: KernelTask, **kwargs):
            artifacts = tuple(
                ArtifactRecord(
                    id=f"artifact-download-{index}",
                    artifact_type=artifact.artifact_type,
                    storage_uri=artifact.storage_uri,
                    summary=artifact.summary,
                    metadata=artifact.metadata,
                ).materialize(evidence_id="evidence-download-1")
                for index, artifact in enumerate(tuple(kwargs.get("artifacts") or ()), start=1)
            )
            return EvidenceRecord(
                id="evidence-download-1",
                task_id=task.id,
                actor_ref=kwargs.get("actor_ref") or "tool:browser_use",
                environment_ref=kwargs.get("environment_ref"),
                capability_ref=kwargs.get("capability_ref"),
                risk_level=task.risk_level,
                action_summary=kwargs["action_summary"],
                result_summary=kwargs["result_summary"],
                status=kwargs["status"],
                metadata=kwargs.get("metadata") or {},
                artifacts=artifacts,
            )

        def upsert(self, task: KernelTask, **kwargs) -> None:
            _ = (task, kwargs)

    bridge = KernelToolBridge(task_store=_FakeTaskStore())

    tool_use_summary = bridge.record_browser_event(
        "ktask:browser-download",
        {
            "action": "click",
            "page_id": "page-1",
            "status": "success",
            "result_summary": "Downloaded operator report",
            "metadata": {
                "verification": {
                    "kind": "download",
                    "download": {
                        "path": "D:/word/copaw/artifacts/operator-report.csv",
                        "verified": True,
                        "status": "completed",
                    },
                },
            },
        },
    )

    assert tool_use_summary is not None
    assert tool_use_summary["summary"] == "Downloaded operator report"
    assert tool_use_summary["artifact_refs"] == [
        "D:/word/copaw/artifacts/operator-report.csv",
    ]
    assert len(tool_use_summary["result_items"]) == 1
    result_item = tool_use_summary["result_items"][0]
    assert result_item["ref"] == "D:/word/copaw/artifacts/operator-report.csv"
    assert result_item["kind"] == "file"
    assert str(result_item["label"]).strip()
    assert result_item["summary"] == "Downloaded operator report"
    assert result_item["route"] == "/api/runtime-center/artifacts/artifact-download-1"
