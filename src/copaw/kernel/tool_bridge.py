# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..constant import WORKING_DIR
from ..evidence import ReplayPointer
from ..environments import EnvironmentService
from .models import KernelTask
from .persistence import KernelTaskStore

logger = logging.getLogger(__name__)
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


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

    def record_shell_event(self, task_id: str, payload: dict[str, object]) -> None:
        task = self._get_task(task_id)
        if task is None:
            return
        status = self._string(payload.get("status")) or "success"
        command = self._string(payload.get("command")) or "shell"
        stdout = self._string(payload.get("stdout"))
        stderr = self._string(payload.get("stderr"))
        environment_ref = self._string(payload.get("cwd"))
        summary = self._shell_summary(status, command, stdout, stderr)
        replay_pointer = self._build_shell_replay_pointer(
            task=task,
            payload=payload,
            environment_ref=environment_ref,
            command=command,
        )
        evidence = self._append_evidence(
            task,
            action_summary=f"shell {status}",
            result_summary=summary,
            environment_ref=environment_ref,
            capability_ref="tool:execute_shell_command",
            actor_ref="tool:execute_shell_command",
            metadata=payload,
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

    def record_file_event(self, task_id: str, payload: dict[str, object]) -> None:
        task = self._get_task(task_id)
        if task is None:
            return
        status = self._string(payload.get("status")) or "success"
        action = self._string(payload.get("action")) or "write"
        tool_name = self._string(payload.get("tool_name")) or "file_io"
        resolved_path = self._string(payload.get("resolved_path"))
        result_summary = self._string(payload.get("result_summary"))
        summary = self._file_summary(status, action, resolved_path, result_summary)
        evidence = self._append_evidence(
            task,
            action_summary=f"file {action} {status}",
            result_summary=summary,
            environment_ref=resolved_path,
            capability_ref=f"tool:{tool_name}",
            actor_ref=f"tool:{tool_name}",
            metadata=payload,
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

    def record_browser_event(self, task_id: str, payload: dict[str, object]) -> None:
        task = self._get_task(task_id)
        if task is None:
            return
        status = self._string(payload.get("status")) or "success"
        action = self._string(payload.get("action")) or "browser"
        url = self._string(payload.get("url"))
        page_id = self._string(payload.get("page_id"))
        environment_ref = url or page_id
        result_summary = self._string(payload.get("result_summary"))
        summary = self._browser_summary(status, action, environment_ref, result_summary)
        evidence = self._append_evidence(
            task,
            action_summary=f"browser {action} {status}",
            result_summary=summary,
            environment_ref=environment_ref,
            capability_ref="tool:browser_use",
            actor_ref="tool:browser_use",
            metadata=payload,
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
        action_summary: str,
        result_summary: str,
        environment_ref: str | None,
        capability_ref: str | None,
        actor_ref: str | None,
        metadata: dict[str, object],
        replay_pointers: tuple[ReplayPointer, ...] | None = None,
    ):
        return self._task_store.append_evidence(
            task,
            action_summary=action_summary,
            result_summary=result_summary,
            metadata={
                **metadata,
                "environment_ref": environment_ref,
                "capability_ref": capability_ref,
                "actor_ref": actor_ref,
            },
            environment_ref=environment_ref,
            capability_ref=capability_ref,
            actor_ref=actor_ref,
            replay_pointers=replay_pointers,
        )

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
    ) -> str:
        if status == "success":
            suffix = stdout or "command completed without output"
            return f"Shell command succeeded: {command} -> {suffix}"
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
        return cleaned or "replay"


__all__ = ["KernelToolBridge"]
