# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os
import shlex
import signal
import socket
import subprocess
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from ..agents.tools import execute_shell_command
from ..state.external_runtime_service import ExternalCapabilityRuntimeService
from .execution_support import (
    _tool_response_payload,
    _tool_response_success,
    _tool_response_summary,
)
from .external_runtime_actions import (
    HealthcheckExternalRuntimePayload,
    RestartExternalRuntimePayload,
    RunExternalRuntimePayload,
    StartExternalRuntimePayload,
    StopExternalRuntimePayload,
)
from .models import CapabilityMount


def _runtime_contract(mount: CapabilityMount) -> dict[str, Any]:
    contract = dict((mount.metadata or {}).get("runtime_contract") or {})
    contract["ready_probe_config"] = dict(contract.get("ready_probe_config") or {})
    return contract


def _package_command(mount: CapabilityMount, *, key: str) -> str:
    return str((mount.metadata or {}).get(key) or "").strip()


def _append_args(command: str, args: list[str]) -> str:
    if not args:
        return command
    rendered = " ".join(shlex.quote(str(item)) for item in args if str(item).strip())
    return f"{command} {rendered}".strip()


def _spawn_process(command: str) -> tuple[int | None, str | None]:
    kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "shell": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(command, **kwargs)
    except OSError as exc:
        return None, str(exc)
    return process.pid, None


def _http_check(url: str, timeout: float) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
            if 200 <= status < 500:
                return True, f"HTTP readiness probe succeeded ({status})"
            return False, f"HTTP readiness probe failed ({status})"
    except URLError as exc:
        return False, str(exc)


def _port_check(host: str, port: int, timeout: float) -> tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True, f"Port probe succeeded on {host}:{port}"
    except OSError as exc:
        return False, str(exc)
    finally:
        sock.close()


def _terminate_process(pid: int) -> tuple[bool, str]:
    if os.name == "nt":
        completed = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output = (completed.stdout or completed.stderr or "").strip()
        return completed.returncode == 0, output or f"taskkill exited {completed.returncode}"
    try:
        os.kill(pid, signal.SIGTERM)
        return True, f"Sent SIGTERM to {pid}"
    except OSError as exc:
        return False, str(exc)


def _process_exists(pid: int | None) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output = f"{completed.stdout or ''}\n{completed.stderr or ''}"
        return str(pid) in output and "No tasks are running" not in output
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _float_config(
    value: object,
    default: float,
    *,
    minimum: float,
) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        return default
    if resolved < minimum:
        return default
    return resolved


class ExternalRuntimeExecution:
    def __init__(
        self,
        *,
        runtime_service: ExternalCapabilityRuntimeService,
    ) -> None:
        self._runtime_service = runtime_service

    async def _probe_runtime_readiness(
        self,
        mount: CapabilityMount,
        runtime_id: str,
    ) -> tuple[bool, str, str | None]:
        runtime = self._runtime_service.get_runtime(runtime_id)
        if runtime is None:
            return False, f"Runtime '{runtime_id}' not found.", None
        if runtime.process_id is not None and not _process_exists(runtime.process_id):
            return (
                False,
                f"Runtime process {runtime.process_id} is no longer running.",
                "orphaned",
            )
        contract = _runtime_contract(mount)
        probe_kind = str(contract.get("ready_probe_kind") or "none").strip().lower()
        ready_probe_config = dict(contract.get("ready_probe_config") or {})
        success = True
        summary = "Runtime is ready."
        if probe_kind == "command":
            command = str(
                ready_probe_config.get("command")
                or _package_command(mount, key="healthcheck_command")
            ).strip()
            response = await execute_shell_command(
                command=command,
                timeout=30,
                cwd=None,
            )
            success = _tool_response_success(response)
            summary = _tool_response_summary(response)
        elif probe_kind == "http":
            health_url = runtime.health_url or str(ready_probe_config.get("url") or "").strip()
            success, summary = await asyncio.to_thread(_http_check, health_url, 3.0)
        elif probe_kind == "port":
            host = str(ready_probe_config.get("host") or "127.0.0.1")
            port = runtime.port or ready_probe_config.get("port")
            if not isinstance(port, int):
                success, summary = False, "Port readiness probe requires runtime port."
            else:
                success, summary = await asyncio.to_thread(_port_check, host, port, 3.0)
        return success, summary, None

    async def _wait_for_service_ready(
        self,
        mount: CapabilityMount,
        *,
        runtime_id: str,
    ) -> dict[str, object]:
        contract = _runtime_contract(mount)
        ready_probe_config = dict(contract.get("ready_probe_config") or {})
        startup_timeout_sec = _float_config(
            ready_probe_config.get("startup_timeout_sec"),
            6.0,
            minimum=0.0,
        )
        probe_interval_sec = _float_config(
            ready_probe_config.get("probe_interval_sec"),
            0.25,
            minimum=0.0,
        )
        deadline = time.monotonic() + startup_timeout_sec
        last_summary = "Runtime failed readiness check."
        while True:
            runtime = self._runtime_service.get_runtime(runtime_id)
            if runtime is None:
                return {
                    "success": False,
                    "summary": f"Runtime '{runtime_id}' not found.",
                    "error": f"Runtime '{runtime_id}' not found.",
                }
            success, summary, terminal_status = await self._probe_runtime_readiness(
                mount,
                runtime.runtime_id,
            )
            last_summary = summary or last_summary
            if terminal_status == "orphaned":
                orphaned = self._runtime_service.mark_runtime_stopped(
                    runtime.runtime_id,
                    status="orphaned",
                    last_error=last_summary,
                )
                return {
                    "success": False,
                    "summary": orphaned.last_error or "Runtime process is no longer running.",
                    "status": orphaned.status,
                    "runtime_id": orphaned.runtime_id,
                    "error": orphaned.last_error,
                    "evidence_metadata": {
                        "runtime_id": orphaned.runtime_id,
                        "runtime_status": orphaned.status,
                        "runtime_kind": orphaned.runtime_kind,
                    },
                }
            if success:
                ready = self._runtime_service.mark_runtime_ready(
                    runtime.runtime_id,
                    process_id=runtime.process_id,
                    port=runtime.port,
                    health_url=runtime.health_url,
                    metadata={"action": "healthcheck"},
                )
                return {
                    "success": True,
                    "summary": last_summary or f"Runtime '{ready.runtime_id}' is ready.",
                    "status": ready.status,
                    "runtime_id": ready.runtime_id,
                    "output": ready.model_dump(mode="json"),
                    "evidence_metadata": {
                        "runtime_id": ready.runtime_id,
                        "runtime_status": ready.status,
                        "runtime_kind": ready.runtime_kind,
                    },
                }
            if time.monotonic() >= deadline:
                return {
                    "success": False,
                    "summary": last_summary,
                    "status": "degraded",
                    "runtime_id": runtime.runtime_id,
                    "error": last_summary,
                    "evidence_metadata": {
                        "runtime_id": runtime.runtime_id,
                        "runtime_status": runtime.status,
                        "runtime_kind": runtime.runtime_kind,
                    },
                }
            await asyncio.sleep(probe_interval_sec)

    async def run_cli(
        self,
        mount: CapabilityMount,
        payload: RunExternalRuntimePayload,
    ) -> dict[str, object]:
        command = _append_args(_package_command(mount, key="execute_command"), payload.args)
        response = await execute_shell_command(
            command=command,
            timeout=int(payload.timeout_sec or 180),
            cwd=None,
        )
        success = _tool_response_success(response)
        runtime = self._runtime_service.record_cli_run(
            capability_id=mount.id,
            scope_kind="session",
            session_mount_id=payload.session_mount_id or "session:adhoc",
            work_context_id=payload.work_context_id,
            environment_ref=payload.environment_ref,
            owner_agent_id=payload.owner_agent_id,
            command=command,
            success=success,
            last_error=None if success else _tool_response_summary(response),
            metadata={"action": "run"},
        )
        return {
            "success": success,
            "summary": _tool_response_summary(response),
            "status": runtime.status,
            "runtime_id": runtime.runtime_id,
            "output": _tool_response_payload(response),
            "evidence_metadata": {
                "runtime_id": runtime.runtime_id,
                "runtime_status": runtime.status,
                "runtime_kind": runtime.runtime_kind,
            },
        }

    async def start_service(
        self,
        mount: CapabilityMount,
        payload: StartExternalRuntimePayload,
    ) -> dict[str, object]:
        contract = _runtime_contract(mount)
        scope_kind = str(contract.get("scope_policy") or "session").strip() or "session"
        existing = self._runtime_service.resolve_active_service_instance(
            capability_id=mount.id,
            scope_kind=scope_kind,
            session_mount_id=payload.session_mount_id,
            work_context_id=payload.work_context_id,
            environment_ref=payload.environment_ref,
        )
        if existing is not None and existing.process_id:
            return {
                "success": True,
                "summary": f"Reusing active runtime '{existing.runtime_id}'.",
                "status": existing.status,
                "runtime_id": existing.runtime_id,
                "output": existing.model_dump(mode="json"),
                "evidence_metadata": {
                    "runtime_id": existing.runtime_id,
                    "runtime_status": existing.status,
                    "runtime_kind": existing.runtime_kind,
                },
            }
        runtime = self._runtime_service.create_or_reuse_service_runtime(
            capability_id=mount.id,
            scope_kind=scope_kind,
            session_mount_id=payload.session_mount_id,
            work_context_id=payload.work_context_id,
            environment_ref=payload.environment_ref,
            owner_agent_id=payload.owner_agent_id,
            command=_append_args(_package_command(mount, key="execute_command"), payload.args),
            retention_policy=payload.retention_policy or "until-stop",
            metadata={"action": "start"},
        )
        pid, error = await asyncio.to_thread(_spawn_process, runtime.command)
        if error is not None or pid is None:
            failed = self._runtime_service.mark_runtime_stopped(
                runtime.runtime_id,
                status="failed",
                last_error=error or "Failed to start runtime process.",
            )
            return {
                "success": False,
                "summary": failed.last_error or "Failed to start runtime process.",
                "status": failed.status,
                "runtime_id": failed.runtime_id,
                "error": failed.last_error,
                "evidence_metadata": {
                    "runtime_id": failed.runtime_id,
                    "runtime_status": failed.status,
                    "runtime_kind": failed.runtime_kind,
                },
            }
        port = payload.port_override or contract.get("predicted_default_port")
        health_path = (
            str(payload.health_path_override or "").strip()
            or str(contract.get("predicted_health_path") or "").strip()
            or None
        )
        health_url = None
        if isinstance(port, int) and health_path:
            health_url = f"http://127.0.0.1:{port}{health_path}"
        if not health_url:
            contract_url = str(
                dict(contract.get("ready_probe_config") or {}).get("url") or "",
            ).strip()
            if contract_url:
                health_url = contract_url
        runtime = self._runtime_service.update_runtime(
            runtime.runtime_id,
            process_id=pid,
            port=port,
            health_url=health_url,
            metadata={"action": "start", "pid": pid},
        )
        result = await self._wait_for_service_ready(
            mount,
            runtime_id=runtime.runtime_id,
        )
        if result.get("success"):
            result["summary"] = f"Started runtime '{runtime.runtime_id}' (pid={pid})."
            return result
        if result.get("status") == "orphaned":
            return result
        degraded = self._runtime_service.update_runtime(
            runtime.runtime_id,
            status="degraded",
            last_error=str(result.get("summary") or ""),
            metadata={"action": "start", "health_status": "degraded"},
        )
        return {
            "success": False,
            "summary": degraded.last_error or "Runtime failed readiness check.",
            "status": degraded.status,
            "runtime_id": degraded.runtime_id,
            "error": degraded.last_error,
            "evidence_metadata": {
                "runtime_id": degraded.runtime_id,
                "runtime_status": degraded.status,
                "runtime_kind": degraded.runtime_kind,
            },
        }

    async def healthcheck_service(
        self,
        mount: CapabilityMount,
        payload: HealthcheckExternalRuntimePayload,
    ) -> dict[str, object]:
        runtime = self._runtime_service.get_runtime(payload.runtime_id)
        if runtime is None:
            return {
                "success": False,
                "summary": f"Runtime '{payload.runtime_id}' not found.",
                "error": f"Runtime '{payload.runtime_id}' not found.",
            }
        success, summary, terminal_status = await self._probe_runtime_readiness(
            mount,
            runtime.runtime_id,
        )
        if terminal_status == "orphaned":
            orphaned = self._runtime_service.mark_runtime_stopped(
                runtime.runtime_id,
                status="orphaned",
                last_error=summary,
            )
            return {
                "success": False,
                "summary": orphaned.last_error or "Runtime process is no longer running.",
                "status": orphaned.status,
                "runtime_id": orphaned.runtime_id,
                "error": orphaned.last_error,
                "evidence_metadata": {
                    "runtime_id": orphaned.runtime_id,
                    "runtime_status": orphaned.status,
                    "runtime_kind": orphaned.runtime_kind,
                },
            }
        if success:
            ready = self._runtime_service.mark_runtime_ready(
                runtime.runtime_id,
                process_id=runtime.process_id,
                port=runtime.port,
                health_url=runtime.health_url,
                metadata={"action": "healthcheck"},
            )
            return {
                "success": True,
                "summary": summary or f"Runtime '{ready.runtime_id}' is ready.",
                "status": ready.status,
                "runtime_id": ready.runtime_id,
                "output": ready.model_dump(mode="json"),
                "evidence_metadata": {
                    "runtime_id": ready.runtime_id,
                    "runtime_status": ready.status,
                    "runtime_kind": ready.runtime_kind,
                },
            }
        degraded = self._runtime_service.update_runtime(
            runtime.runtime_id,
            status="degraded",
            last_error=summary,
            metadata={"action": "healthcheck", "probe_kind": probe_kind},
        )
        return {
            "success": False,
            "summary": summary,
            "status": degraded.status,
            "runtime_id": degraded.runtime_id,
            "error": summary,
            "evidence_metadata": {
                "runtime_id": degraded.runtime_id,
                "runtime_status": degraded.status,
                "runtime_kind": degraded.runtime_kind,
            },
        }

    async def stop_service(
        self,
        mount: CapabilityMount,
        payload: StopExternalRuntimePayload,
    ) -> dict[str, object]:
        _ = mount
        runtime = self._runtime_service.get_runtime(payload.runtime_id)
        if runtime is None:
            return {
                "success": False,
                "summary": f"Runtime '{payload.runtime_id}' not found.",
                "error": f"Runtime '{payload.runtime_id}' not found.",
            }
        pid = runtime.process_id
        if not isinstance(pid, int):
            stopped = self._runtime_service.mark_runtime_stopped(
                runtime.runtime_id,
                status="stopped",
                last_error="Runtime has no active process id.",
            )
            return {
                "success": True,
                "summary": "Runtime already has no active process.",
                "status": stopped.status,
                "runtime_id": stopped.runtime_id,
                "output": stopped.model_dump(mode="json"),
                "evidence_metadata": {
                    "runtime_id": stopped.runtime_id,
                    "runtime_status": stopped.status,
                    "runtime_kind": stopped.runtime_kind,
                },
            }
        success, summary = await asyncio.to_thread(_terminate_process, pid)
        stopped = self._runtime_service.mark_runtime_stopped(
            runtime.runtime_id,
            status="stopped" if success else "failed",
            last_error=None if success else summary,
        )
        return {
            "success": success,
            "summary": summary or f"Stopped runtime '{stopped.runtime_id}'.",
            "status": stopped.status,
            "runtime_id": stopped.runtime_id,
            "output": stopped.model_dump(mode="json"),
            "error": None if success else summary,
            "evidence_metadata": {
                "runtime_id": stopped.runtime_id,
                "runtime_status": stopped.status,
                "runtime_kind": stopped.runtime_kind,
            },
        }

    async def restart_service(
        self,
        mount: CapabilityMount,
        payload: RestartExternalRuntimePayload,
    ) -> dict[str, object]:
        runtime = self._runtime_service.get_runtime(payload.runtime_id)
        if runtime is None:
            return {
                "success": False,
                "summary": f"Runtime '{payload.runtime_id}' not found.",
                "error": f"Runtime '{payload.runtime_id}' not found.",
            }
        await self.stop_service(
            mount,
            StopExternalRuntimePayload(
                action="stop",
                runtime_id=runtime.runtime_id,
                owner_agent_id=payload.owner_agent_id,
                session_mount_id=runtime.session_mount_id,
                work_context_id=runtime.work_context_id,
                environment_ref=runtime.environment_ref,
            ),
        )
        return await self.start_service(
            mount,
            StartExternalRuntimePayload(
                action="start",
                owner_agent_id=payload.owner_agent_id or runtime.owner_agent_id,
                session_mount_id=runtime.session_mount_id,
                work_context_id=runtime.work_context_id,
                environment_ref=runtime.environment_ref,
                args=payload.args,
                retention_policy=payload.retention_policy or runtime.retention_policy,
                port_override=payload.port_override or runtime.port,
                health_path_override=payload.health_path_override,
                metadata=payload.metadata,
            ),
        )
