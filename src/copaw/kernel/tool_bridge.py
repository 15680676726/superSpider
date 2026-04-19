# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..constant import WORKING_DIR
from ..evidence import ArtifactRecord, ReplayPointer, serialize_evidence_record
from ..environments import EnvironmentService
from .runtime_outcome import classify_runtime_outcome
from .models import KernelTask
from .persistence import KernelTaskStore

logger = logging.getLogger(__name__)
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_VISIBILITY_MAX_ITEMS = 6
_SCREENSHOT_TOKENS = (
    "screenshot",
    "screen-shot",
    "screen_capture",
    "screencap",
    "snapshot",
)


class KernelToolBridge:
    """Record tool evidence against kernel tasks and environment mounts."""

    def __init__(
        self,
        *,
        task_store: KernelTaskStore,
        environment_service: EnvironmentService | None = None,
    ) -> None:
        self._task_store = task_store
        self._environment_service = environment_service

    def record_shell_event(
        self,
        task_id: str,
        payload: dict[str, object],
    ) -> dict[str, object] | None:
        task = self._get_task(task_id)
        if task is None:
            return None
        payload_metadata = self._payload_metadata(payload)
        status = self._string(payload_metadata.get("status")) or "success"
        command = self._string(payload.get("command")) or "shell"
        stdout = self._string(payload.get("stdout"))
        stderr = self._string(payload.get("stderr"))
        rule_id = self._string(payload.get("rule_id"))
        environment_ref = self._string(payload.get("cwd"))
        summary = self._shell_summary(status, command, stdout, stderr, rule_id)
        outcome_kind = self._string(payload_metadata.get("outcome_kind")) or classify_runtime_outcome(
            summary,
            success=status == "success",
            phase=self._string(payload_metadata.get("phase")) or status,
            timed_out=bool(payload_metadata.get("timed_out")),
        )
        replay_pointer = None
        if status != "blocked":
            replay_pointer = self._build_shell_replay_pointer(
                task=task,
                payload=payload,
                environment_ref=environment_ref,
                command=command,
            )
        evidence = self._append_evidence(
            task,
            kind=None,
            action_summary=f"shell {status}",
            result_summary=summary,
            status=self._tool_evidence_status(status),
            environment_ref=environment_ref,
            capability_ref="tool:execute_shell_command",
            actor_ref="tool:execute_shell_command",
            metadata={
                **payload_metadata,
                "outcome_kind": outcome_kind,
            },
            replay_pointers=(replay_pointer,) if replay_pointer is not None else None,
        )
        self._touch_environment(
            ref=environment_ref,
            metadata={
                "source": "shell",
                "command": command,
                "status": status,
            },
            last_active_at=self._coerce_datetime(payload.get("finished_at")),
        )
        self._update_task(task, status=status, summary=summary, evidence_id=evidence.id if evidence else None)
        return self._build_tool_use_summary(evidence)

    def record_file_event(
        self,
        task_id: str,
        payload: dict[str, object],
    ) -> dict[str, object] | None:
        task = self._get_task(task_id)
        if task is None:
            return None
        payload_metadata = self._payload_metadata(payload)
        status = self._string(payload_metadata.get("status")) or "success"
        action = self._string(payload.get("action")) or "write"
        tool_name = self._string(payload.get("tool_name")) or "file_io"
        resolved_path = self._string(payload.get("resolved_path"))
        result_summary = self._string(payload.get("result_summary"))
        summary = self._file_summary(status, action, resolved_path, result_summary)
        outcome_kind = self._string(payload_metadata.get("outcome_kind")) or classify_runtime_outcome(
            summary,
            success=status == "success",
            phase=self._string(payload_metadata.get("phase")) or status,
        )
        artifacts = self._build_file_artifacts(
            status=status,
            action=action,
            resolved_path=resolved_path,
            summary=result_summary or summary,
        )
        evidence = self._append_evidence(
            task,
            kind=self._tool_evidence_kind(payload_metadata),
            action_summary=f"file {action} {status}",
            result_summary=summary,
            status=self._tool_evidence_status(status),
            environment_ref=resolved_path,
            capability_ref=f"tool:{tool_name}",
            actor_ref=f"tool:{tool_name}",
            metadata={
                **payload_metadata,
                "outcome_kind": outcome_kind,
            },
            artifacts=artifacts,
        )
        self._touch_environment(
            ref=resolved_path,
            metadata={
                "source": "file",
                "action": action,
                "status": status,
            },
            last_active_at=self._coerce_datetime(payload.get("finished_at")),
        )
        self._update_task(task, status=status, summary=summary, evidence_id=evidence.id if evidence else None)
        return self._build_tool_use_summary(evidence)

    def record_browser_event(
        self,
        task_id: str,
        payload: dict[str, object],
    ) -> dict[str, object] | None:
        task = self._get_task(task_id)
        if task is None:
            return None
        payload_metadata = self._payload_metadata(payload)
        status = self._string(payload_metadata.get("status")) or "success"
        action = self._string(payload.get("action")) or "browser"
        url = self._string(payload.get("url"))
        page_id = self._string(payload.get("page_id"))
        environment_ref = url or page_id
        result_summary = self._string(payload.get("result_summary"))
        summary = self._browser_summary(status, action, environment_ref, result_summary)
        outcome_kind = self._string(payload_metadata.get("outcome_kind")) or classify_runtime_outcome(
            summary,
            success=status == "success",
            phase=self._string(payload_metadata.get("phase")) or status,
        )
        artifacts = self._build_browser_artifacts(
            status=status,
            action=action,
            payload=payload,
            payload_metadata=payload_metadata,
            summary=result_summary or summary,
        )
        evidence = self._append_evidence(
            task,
            kind=self._tool_evidence_kind(payload_metadata),
            action_summary=f"browser {action} {status}",
            result_summary=summary,
            status=self._tool_evidence_status(status),
            environment_ref=environment_ref,
            capability_ref="tool:browser_use",
            actor_ref="tool:browser_use",
            metadata={
                **payload_metadata,
                "outcome_kind": outcome_kind,
            },
            artifacts=artifacts,
        )
        self._touch_environment(
            ref=environment_ref,
            kind="browser",
            metadata={
                "source": "browser",
                "action": action,
                "status": status,
                "page_id": page_id,
                "url": url,
            },
            last_active_at=self._coerce_datetime(payload.get("finished_at")),
        )
        self._update_task(task, status=status, summary=summary, evidence_id=evidence.id if evidence else None)
        return self._build_tool_use_summary(evidence)

    def record_desktop_event(
        self,
        task_id: str,
        payload: dict[str, object],
    ) -> dict[str, object] | None:
        task = self._get_task(task_id)
        if task is None:
            return None
        payload_metadata = self._payload_metadata(payload)
        status = self._string(payload_metadata.get("status")) or "success"
        action = self._string(payload.get("action")) or "desktop"
        app_identity = self._string(payload.get("app_identity"))
        session_mount_id = self._string(payload.get("session_mount_id"))
        selector = self._string(payload.get("selector"))
        environment_ref = app_identity or session_mount_id or selector
        result_summary = self._string(payload.get("result_summary"))
        summary = self._desktop_summary(status, action, environment_ref, result_summary)
        outcome_kind = self._string(payload_metadata.get("outcome_kind")) or classify_runtime_outcome(
            summary,
            success=status == "success",
            phase=self._string(payload_metadata.get("phase")) or status,
        )
        evidence = self._append_evidence(
            task,
            kind=self._tool_evidence_kind(payload_metadata),
            action_summary=f"desktop {action} {status}",
            result_summary=summary,
            status=self._tool_evidence_status(status),
            environment_ref=environment_ref,
            capability_ref="tool:desktop_actuation",
            actor_ref="tool:desktop_actuation",
            metadata={
                **payload_metadata,
                "outcome_kind": outcome_kind,
            },
        )
        self._touch_environment(
            ref=environment_ref,
            kind="desktop",
            metadata={
                "source": "desktop",
                "action": action,
                "status": status,
                "app_identity": app_identity,
                "session_mount_id": session_mount_id,
                "selector": selector,
            },
            last_active_at=self._coerce_datetime(payload.get("finished_at")),
        )
        self._update_task(task, status=status, summary=summary, evidence_id=evidence.id if evidence else None)
        return self._build_tool_use_summary(evidence)

    def _get_task(self, task_id: str) -> KernelTask | None:
        try:
            return self._task_store.get(task_id)
        except Exception:
            logger.exception("Kernel tool bridge failed to load task %s", task_id)
            return None

    def _append_evidence(
        self,
        task: KernelTask,
        *,
        kind: str | None,
        action_summary: str,
        result_summary: str,
        status: str,
        environment_ref: str | None,
        capability_ref: str | None,
        actor_ref: str | None,
        metadata: dict[str, object],
        artifacts: tuple[ArtifactRecord, ...] | None = None,
        replay_pointers: tuple[ReplayPointer, ...] | None = None,
    ):
        return self._task_store.append_evidence(
            task,
            kind=kind,
            action_summary=action_summary,
            result_summary=result_summary,
            status=status,
            metadata={
                **metadata,
                "environment_ref": environment_ref,
                "capability_ref": capability_ref,
                "actor_ref": actor_ref,
            },
            environment_ref=environment_ref,
            capability_ref=capability_ref,
            actor_ref=actor_ref,
            artifacts=artifacts,
            replay_pointers=replay_pointers,
        )

    @classmethod
    def _build_tool_use_summary(
        cls,
        evidence: object | None,
    ) -> dict[str, object] | None:
        if evidence is None:
            return None
        try:
            serialized = serialize_evidence_record(evidence)
        except Exception:
            return None
        artifact_refs: list[str] = []
        result_items: list[dict[str, str]] = []
        seen_refs: set[str] = set()
        seen_signatures: set[tuple[str, str, str, str, str]] = set()
        for artifact in serialized.get("artifacts", []):
            if not isinstance(artifact, dict):
                continue
            ref = cls._string(artifact.get("storage_uri"))
            if not ref:
                continue
            if ref not in seen_refs:
                artifact_refs.append(ref)
                seen_refs.add(ref)
            kind, label = cls._artifact_result_kind(
                artifact_type=cls._string(artifact.get("artifact_type")),
                storage_uri=ref,
                summary=cls._string(artifact.get("summary")),
            )
            result_item = cls._build_result_item(
                ref=ref,
                kind=kind,
                label=label,
                summary=cls._string(artifact.get("summary")),
                route=cls._artifact_route(cls._string(artifact.get("id"))),
            )
            if result_item is None:
                continue
            signature = (
                result_item.get("ref", ""),
                result_item.get("kind", ""),
                result_item.get("label", ""),
                result_item.get("summary", ""),
                result_item.get("route", ""),
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            result_items.append(result_item)
            if len(result_items) >= _VISIBILITY_MAX_ITEMS:
                break
        if len(result_items) < _VISIBILITY_MAX_ITEMS:
            for replay in serialized.get("replay_pointers", []):
                if not isinstance(replay, dict):
                    continue
                ref = cls._string(replay.get("storage_uri"))
                if not ref:
                    continue
                if ref not in seen_refs:
                    artifact_refs.append(ref)
                    seen_refs.add(ref)
                result_item = cls._build_result_item(
                    ref=ref,
                    kind="replay",
                    label="回放",
                    summary=cls._string(replay.get("summary")),
                    route=cls._replay_route(cls._string(replay.get("id"))),
                )
                if result_item is None:
                    continue
                signature = (
                    result_item.get("ref", ""),
                    result_item.get("kind", ""),
                    result_item.get("label", ""),
                    result_item.get("summary", ""),
                    result_item.get("route", ""),
                )
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                result_items.append(result_item)
                if len(result_items) >= _VISIBILITY_MAX_ITEMS:
                    break
        if not artifact_refs and not result_items:
            return None
        payload: dict[str, object] = {
            "artifact_refs": artifact_refs[:_VISIBILITY_MAX_ITEMS],
        }
        evidence_id = cls._string(serialized.get("id"))
        if evidence_id:
            payload["evidence_id"] = evidence_id
        if result_items:
            payload["result_items"] = result_items[:_VISIBILITY_MAX_ITEMS]
        summary = cls._first_non_empty(
            next(
                (
                    item.get("summary")
                    for item in result_items
                    if isinstance(item, dict) and cls._string(item.get("summary"))
                ),
                None,
            ),
            cls._string(serialized.get("result_summary")),
        )
        if summary is not None:
            payload["summary"] = summary
        return payload

    @classmethod
    def _artifact_result_kind(
        cls,
        *,
        artifact_type: str | None,
        storage_uri: str | None,
        summary: str | None,
    ) -> tuple[str, str]:
        normalized_type = str(artifact_type or "").strip().lower()
        if normalized_type == "screenshot":
            return "screenshot", "截图"
        if normalized_type in {"image", "snapshot"} and cls._looks_like_screenshot(
            storage_uri,
            summary,
            artifact_type,
        ):
            return "screenshot", "截图"
        if cls._looks_like_screenshot(storage_uri, summary, artifact_type):
            return "screenshot", "截图"
        return "file", "文件"

    @classmethod
    def _looks_like_screenshot(cls, *values: str | None) -> bool:
        for value in values:
            normalized = str(value or "").strip().lower()
            if any(token in normalized for token in _SCREENSHOT_TOKENS):
                return True
        return False

    @staticmethod
    def _artifact_route(artifact_id: str | None) -> str | None:
        if not artifact_id:
            return None
        return f"/api/runtime-center/artifacts/{artifact_id}"

    @staticmethod
    def _replay_route(replay_id: str | None) -> str | None:
        if not replay_id:
            return None
        return f"/api/runtime-center/replays/{replay_id}"

    @classmethod
    def _build_result_item(
        cls,
        *,
        ref: str | None,
        kind: str | None,
        label: str | None,
        summary: str | None = None,
        route: str | None = None,
    ) -> dict[str, str] | None:
        resolved_ref = cls._string(ref)
        resolved_kind = cls._string(kind)
        resolved_label = cls._string(label)
        if not resolved_ref or not resolved_kind or not resolved_label:
            return None
        payload: dict[str, str] = {
            "ref": resolved_ref,
            "kind": resolved_kind,
            "label": resolved_label,
        }
        resolved_summary = cls._string(summary)
        if resolved_summary is not None:
            payload["summary"] = resolved_summary
        resolved_route = cls._string(route)
        if resolved_route is not None:
            payload["route"] = resolved_route
        return payload

    @staticmethod
    def _first_non_empty(*values: object | None) -> str | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def _update_task(
        self,
        task: KernelTask,
        *,
        status: str,
        summary: str,
        evidence_id: str | None,
    ) -> None:
        updated_task = task.model_copy(update={"updated_at": self._now()})
        if status == "success":
            self._task_store.upsert(
                updated_task,
                last_result_summary=summary,
                last_evidence_id=evidence_id,
            )
        else:
            self._task_store.upsert(
                updated_task,
                last_error_summary=summary,
                last_evidence_id=evidence_id,
            )

    def _touch_environment(
        self,
        *,
        ref: str | None,
        kind: str | None = None,
        metadata: dict[str, Any] | None = None,
        last_active_at: datetime | None = None,
    ) -> None:
        if self._environment_service is None or not ref:
            return
        try:
            self._environment_service.touch_environment(
                ref=ref,
                kind=kind,
                metadata=metadata,
                last_active_at=last_active_at,
                evidence_delta=1,
            )
        except Exception:
            logger.exception("Kernel tool bridge failed to update environment mount")

    @staticmethod
    def _build_file_artifacts(
        *,
        status: str,
        action: str,
        resolved_path: str | None,
        summary: str,
    ) -> tuple[ArtifactRecord, ...]:
        if status != "success" or not resolved_path:
            return ()
        if action not in {"write", "edit", "append"}:
            return ()
        return (
            ArtifactRecord(
                artifact_type="file",
                storage_uri=resolved_path,
                summary=summary,
                metadata={
                    "source": "tool-bridge",
                    "action": action,
                    "status": status,
                },
            ),
        )

    @classmethod
    def _build_browser_artifacts(
        cls,
        *,
        status: str,
        action: str,
        payload: dict[str, object],
        payload_metadata: dict[str, object],
        summary: str,
    ) -> tuple[ArtifactRecord, ...]:
        if status != "success":
            return ()
        normalized_action = str(action or "").strip().lower()
        artifact_type, resolved_path = cls._resolve_browser_artifact_target(
            action=normalized_action,
            payload=payload,
            payload_metadata=payload_metadata,
        )
        if not artifact_type or not resolved_path:
            return ()
        return (
            ArtifactRecord(
                artifact_type=artifact_type,
                storage_uri=resolved_path,
                summary=summary,
                metadata={
                    "source": "tool-bridge",
                    "action": normalized_action,
                    "status": status,
                },
            ),
        )

    @classmethod
    def _resolve_browser_artifact_path(
        cls,
        *,
        payload: dict[str, object],
        payload_metadata: dict[str, object],
    ) -> str | None:
        direct_path = cls._string(payload.get("path")) or cls._string(payload_metadata.get("path"))
        if direct_path:
            return direct_path
        verification = payload_metadata.get("verification")
        if not isinstance(verification, dict):
            return None
        artifact = verification.get("artifact")
        if not isinstance(artifact, dict):
            return None
        return cls._string(artifact.get("path"))

    @classmethod
    def _resolve_browser_artifact_target(
        cls,
        *,
        action: str,
        payload: dict[str, object],
        payload_metadata: dict[str, object],
    ) -> tuple[str | None, str | None]:
        if action in {"screenshot", "take_screenshot"}:
            return (
                "screenshot",
                cls._resolve_browser_artifact_path(
                    payload=payload,
                    payload_metadata=payload_metadata,
                ),
            )
        verification = payload_metadata.get("verification")
        if not isinstance(verification, dict):
            return (None, None)
        if str(verification.get("kind") or "").strip().lower() != "download":
            return (None, None)
        download = verification.get("download")
        if not isinstance(download, dict):
            return (None, None)
        if not bool(download.get("verified")):
            return (None, None)
        return ("file", cls._string(download.get("path")))

    @staticmethod
    def _string(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _shell_summary(
        status: str,
        command: str,
        stdout: str | None,
        stderr: str | None,
        rule_id: str | None = None,
    ) -> str:
        if status == "success":
            suffix = stdout or "command completed without output"
            return f"Shell command succeeded: {command} -> {suffix}"
        if status == "blocked":
            prefix = "Shell command blocked"
            if rule_id:
                prefix = f"{prefix} ({rule_id})"
            suffix = stderr or stdout or "command blocked by policy"
            return f"{prefix}: {command} -> {suffix}"
        suffix = stderr or stdout or "command failed without diagnostic output"
        return f"Shell command {status}: {command} -> {suffix}"

    @staticmethod
    def _file_summary(
        status: str,
        action: str,
        resolved_path: str | None,
        result_summary: str | None,
    ) -> str:
        prefix = f"File {action} {status}"
        if resolved_path:
            prefix = f"{prefix}: {resolved_path}"
        if result_summary:
            return f"{prefix} -> {result_summary}"
        return prefix

    @staticmethod
    def _browser_summary(
        status: str,
        action: str,
        target: str | None,
        result_summary: str | None,
    ) -> str:
        prefix = f"Browser {action} {status}"
        if target:
            prefix = f"{prefix}: {target}"
        if result_summary:
            return f"{prefix} -> {result_summary}"
        return prefix

    @staticmethod
    def _desktop_summary(
        status: str,
        action: str,
        target: str | None,
        result_summary: str | None,
    ) -> str:
        prefix = f"Desktop {action} {status}"
        if target:
            prefix = f"{prefix}: {target}"
        if result_summary:
            return f"{prefix} -> {result_summary}"
        return prefix

    @staticmethod
    def _tool_evidence_status(status: str) -> str:
        normalized = str(status or "").strip().lower()
        if normalized == "success":
            return "succeeded"
        if normalized == "blocked":
            return "blocked"
        if normalized == "timeout":
            return "timeout"
        if normalized == "cancelled":
            return "cancelled"
        return "failed"

    @staticmethod
    def _tool_evidence_kind(payload_metadata: dict[str, object]) -> str | None:
        evidence_kind = str(payload_metadata.get("evidence_kind") or "").strip()
        return evidence_kind or None

    @staticmethod
    def _payload_metadata(payload: dict[str, object]) -> dict[str, object]:
        metadata = dict(payload or {})
        nested = metadata.pop("metadata", None)
        if isinstance(nested, dict):
            metadata = {
                **nested,
                **metadata,
            }
        return metadata

    @staticmethod
    def _coerce_datetime(value: object) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            if raw.endswith("Z"):
                raw = f"{raw[:-1]}+00:00"
            try:
                parsed = datetime.fromisoformat(raw)
            except ValueError:
                return None
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _build_shell_replay_pointer(
        self,
        *,
        task: KernelTask,
        payload: dict[str, object],
        environment_ref: str | None,
        command: str,
    ) -> ReplayPointer | None:
        replay_payload = {
            "task_id": task.id,
            "capability_ref": "tool:execute_shell_command",
            "environment_ref": environment_ref,
            "risk_level": task.risk_level,
            "payload": {
                "command": command,
                "cwd": self._string(payload.get("cwd")),
                "timeout": payload.get("timeout"),
            },
            "observed": dict(payload),
            "recorded_at": self._now().isoformat(),
        }
        replay_dir = WORKING_DIR / "evidence" / "replays"
        try:
            replay_dir.mkdir(parents=True, exist_ok=True)
            safe_task_id = self._safe_filename_segment(task.id)
            replay_path = (
                replay_dir
                / f"{safe_task_id}-{self._now().strftime('%Y%m%d%H%M%S%f')}.json"
            )
            replay_path.write_text(
                json.dumps(replay_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Kernel tool bridge failed to persist shell replay pointer")
            return None
        return ReplayPointer(
            replay_type="shell",
            storage_uri=Path(replay_path).resolve().as_uri(),
            summary=f"Replay shell command: {command}",
            metadata={
                "capability_ref": "tool:execute_shell_command",
                "environment_ref": environment_ref,
                "risk_level": task.risk_level,
                "payload": replay_payload["payload"],
            },
        )

    @staticmethod
    def _safe_filename_segment(value: str) -> str:
        cleaned = _INVALID_FILENAME_CHARS.sub("-", str(value or "")).strip(" .-")
        cleaned = cleaned or "replay"
        if len(cleaned) <= 96:
            return cleaned
        digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:12]
        return f"{cleaned[:80].rstrip('-')}-{digest}"


__all__ = ["KernelToolBridge"]
