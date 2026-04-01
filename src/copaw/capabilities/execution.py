# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from ..agents.tools import (
    bind_browser_evidence_sink,
    bind_file_evidence_sink,
    bind_shell_evidence_sink,
    browser_use,
    desktop_screenshot,
    edit_file,
    execute_shell_command,
    get_current_time,
    read_file,
    send_file_to_user,
    write_file,
)
from ..kernel.runtime_outcome import (
    classify_runtime_outcome,
    evidence_status_for_outcome,
)
from .execution_context import CapabilityExecutionContext
from .execution_support import (
    _build_script_command,
    _capability_name_from_id,
    _filter_executor_kwargs,
    _json_safe,
    _json_tool_response,
    _normalize_script_args,
    _resolve_script_cwd,
    _resolve_skill_script_path,
    _tool_response_payload,
    _tool_response_success,
    _tool_response_summary,
)
from .skill_service import CapabilitySkillService

if TYPE_CHECKING:
    from ..kernel import KernelToolBridge
    from ..kernel.models import KernelTask
    from .models import CapabilityMount
    from .system_handlers import SystemCapabilityHandler


_TOOL_EXECUTORS = {
    "tool:browser_use": browser_use,
    "tool:desktop_screenshot": desktop_screenshot,
    "tool:edit_file": edit_file,
    "tool:execute_shell_command": execute_shell_command,
    "tool:get_current_time": get_current_time,
    "tool:read_file": read_file,
    "tool:send_file_to_user": send_file_to_user,
    "tool:write_file": write_file,
}


class CapabilityExecutionFacade:
    def __init__(
        self,
        *,
        get_capability_fn: Callable[[str], "CapabilityMount | None"],
        resolve_agent_profile_fn: Callable[[str | None], object | None],
        resolve_explicit_capability_allowlist_fn: Callable[[str | None], set[str] | None],
        is_mount_accessible_fn: Callable[..., bool],
        append_execution_evidence_fn: Callable[..., str | None],
        skill_service: CapabilitySkillService,
        tool_bridge: "KernelToolBridge | None" = None,
        mcp_manager: object | None = None,
        system_handler: "SystemCapabilityHandler | None" = None,
    ) -> None:
        self._get_capability = get_capability_fn
        self._resolve_agent_profile = resolve_agent_profile_fn
        self._resolve_explicit_capability_allowlist = (
            resolve_explicit_capability_allowlist_fn
        )
        self._is_mount_accessible = is_mount_accessible_fn
        self._append_execution_evidence = append_execution_evidence_fn
        self._skill_service = skill_service
        self._tool_bridge = tool_bridge
        self._mcp_manager = mcp_manager
        self._system_handler = system_handler

    def set_tool_bridge(self, tool_bridge: "KernelToolBridge | None") -> None:
        self._tool_bridge = tool_bridge

    def set_mcp_manager(self, mcp_manager: object | None) -> None:
        self._mcp_manager = mcp_manager

    def set_system_handler(self, system_handler: "SystemCapabilityHandler | None") -> None:
        self._system_handler = system_handler

    def resolve_executor(self, capability_id: str):
        executor = _TOOL_EXECUTORS.get(capability_id)
        if executor is not None:
            return executor

        if capability_id.startswith("skill:"):
            skill_name = _capability_name_from_id(capability_id, prefix="skill:")

            async def _skill_executor(
                action: str | None = None,
                file_path: str | None = None,
                script_path: str | None = None,
                source: str | None = None,
                args: list[str] | None = None,
                timeout: int | None = None,
                cwd: str | None = None,
                interpreter: str | None = None,
                payload: dict[str, object] | None = None,
            ):
                return await self._execute_skill(
                    skill_name,
                    action=action,
                    file_path=file_path,
                    script_path=script_path,
                    source=source,
                    args=args,
                    timeout=timeout,
                    cwd=cwd,
                    interpreter=interpreter,
                    payload=payload,
                )

            return _skill_executor

        if capability_id.startswith("mcp:"):
            client_key = _capability_name_from_id(capability_id, prefix="mcp:")

            async def _mcp_executor(
                tool_name: str | None = None,
                tool_args: dict[str, object] | None = None,
                timeout: float | None = None,
                payload: dict[str, object] | None = None,
            ):
                return await self._execute_mcp(
                    client_key,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    timeout=timeout,
                    payload=payload,
                )

            return _mcp_executor

        if capability_id.startswith("system:"):

            async def _system_executor(
                payload: dict[str, object] | None = None,
                **kwargs,
            ):
                return await self._execute_system(
                    capability_id,
                    payload=payload,
                    **kwargs,
                )

            return _system_executor

        return None

    async def execute_task(self, task: "KernelTask") -> dict[str, object]:
        capability_id = task.capability_ref or ""
        payload = dict(task.payload or {})
        if capability_id.startswith("system:"):
            payload.setdefault("task_id", task.id)
            payload.setdefault("owner_agent_id", task.owner_agent_id)
            payload.setdefault("goal_id", task.goal_id)
            payload.setdefault("environment_ref", task.environment_ref)
        execution_context = self._build_execution_context(task, payload=payload)

        mount = self._get_capability(capability_id)
        if mount is None:
            summary = f"Capability '{capability_id}' not found"
            return self._build_execution_result(
                execution_context=execution_context,
                mount=None,
                payload=_json_safe(execution_context.payload),
                success=False,
                summary=summary,
                error_kind="failed",
            )
        if not mount.enabled:
            summary = f"Capability '{capability_id}' is disabled"
            return self._build_execution_result(
                execution_context=execution_context,
                mount=mount,
                payload=_json_safe(execution_context.payload),
                success=False,
                summary=summary,
                error_kind="failed",
            )

        profile = self._resolve_agent_profile(task.owner_agent_id)
        explicit_allowlist = self._resolve_explicit_capability_allowlist(
            task.owner_agent_id,
        )
        if not self._is_mount_accessible(
            mount,
            agent_id=task.owner_agent_id,
            profile=profile,
            explicit_allowlist=explicit_allowlist,
        ):
            summary = (
                f"Capability '{capability_id}' is not authorized for "
                f"agent '{task.owner_agent_id}'"
            )
            return self._build_execution_result(
                execution_context=execution_context,
                mount=mount,
                payload=_json_safe(execution_context.payload),
                success=False,
                summary=summary,
                error_kind="failed",
            )

        executor = self.resolve_executor(capability_id)
        if executor is None:
            summary = (
                f"Capability '{capability_id}' does not have a unified executor yet"
            )
            return self._build_execution_result(
                execution_context=execution_context,
                mount=mount,
                payload=_json_safe(execution_context.payload),
                success=False,
                summary=summary,
                error_kind="failed",
            )

        kwargs = _filter_executor_kwargs(executor, execution_context.payload)
        json_safe_kwargs = _json_safe(kwargs)
        evidence_emitted = False
        metadata = {
            "trace_id": execution_context.trace_id,
            "trace_stage": "capability.execute",
            "trace_component": "capability.execution",
            "capability_kind": mount.kind,
            "source_kind": mount.source_kind,
            "executor_ref": mount.executor_ref,
            "evidence_contract": list(mount.evidence_contract),
            "environment_requirements": list(mount.environment_requirements),
            "payload": json_safe_kwargs,
            "task_owner_agent_id": execution_context.owner_agent_id,
            "task_risk_level": execution_context.risk_level,
            "mount_risk_level": mount.risk_level,
            "goal_id": execution_context.goal_id,
            "work_context_id": execution_context.work_context_id,
            "action_mode": execution_context.action_mode,
            "read_only": execution_context.is_read_only,
        }

        with bind_shell_evidence_sink(self._make_shell_evidence_sink(task.id)):
            with bind_file_evidence_sink(self._make_file_evidence_sink(task.id)):
                with bind_browser_evidence_sink(
                    self._make_browser_evidence_sink(task.id),
                ):
                    try:
                        response = await executor(**kwargs)
                    except Exception as exc:
                        summary = f"{exc.__class__.__name__}: {exc}"
                        error_kind = classify_runtime_outcome(summary, success=False)
                        evidence_id = self._append_execution_evidence(
                            task=task,
                            mount=mount,
                            result_summary=summary,
                            status=evidence_status_for_outcome(error_kind),
                            metadata={
                                **metadata,
                                "error_class": exc.__class__.__name__,
                                "error_kind": error_kind,
                            },
                        )
                        return self._build_execution_result(
                            execution_context=execution_context,
                            mount=mount,
                            payload=json_safe_kwargs,
                            success=False,
                            summary=summary,
                            error_kind=error_kind,
                            evidence_id=evidence_id,
                        )

        summary = _tool_response_summary(response)
        output_payload = _tool_response_payload(response)
        output_dict = output_payload if isinstance(output_payload, dict) else None
        error_kind = classify_runtime_outcome(
            summary,
            success=_tool_response_success(response),
            phase=self._response_phase(output_dict),
            timed_out=self._response_timed_out(output_dict),
        )
        success = error_kind == "completed"
        extra_evidence_metadata = {}
        if isinstance(output_dict, dict):
            candidate = output_dict.get("evidence_metadata")
            if isinstance(candidate, dict):
                extra_evidence_metadata = _json_safe(candidate)
        handled_by_tool_bridge = self._tool_bridge is not None and capability_id in {
            "tool:browser_use",
            "tool:edit_file",
            "tool:execute_shell_command",
            "tool:write_file",
        }
        if not handled_by_tool_bridge:
            evidence_id = self._append_execution_evidence(
                task=task,
                mount=mount,
                result_summary=summary,
                status=evidence_status_for_outcome(error_kind),
                metadata={
                    **metadata,
                    **extra_evidence_metadata,
                    "error_kind": error_kind,
                },
            )
            evidence_emitted = evidence_id is not None
        else:
            evidence_id = None

        return self._build_execution_result(
            execution_context=execution_context,
            mount=mount,
            payload=json_safe_kwargs,
            success=success,
            summary=summary,
            error_kind=error_kind,
            evidence_id=evidence_id,
            evidence_emitted=evidence_emitted or handled_by_tool_bridge,
            output=_json_safe(output_payload) if output_payload is not None else None,
        )

    def _build_execution_context(
        self,
        task: "KernelTask",
        *,
        payload: dict[str, object],
    ) -> CapabilityExecutionContext:
        return CapabilityExecutionContext.from_kernel_task(
            task,
            action_mode=self._resolve_action_mode(task.capability_ref),
            payload=payload,
        )

    @staticmethod
    def _resolve_action_mode(capability_ref: str | None) -> str | None:
        if capability_ref in {
            "tool:desktop_screenshot",
            "tool:get_current_time",
            "tool:read_file",
        }:
            return "read"
        if capability_ref in {
            "tool:browser_use",
            "tool:edit_file",
            "tool:execute_shell_command",
            "tool:send_file_to_user",
            "tool:write_file",
        }:
            return "write"
        return None

    @staticmethod
    def _response_timed_out(output_payload: dict[str, object] | None) -> bool:
        if not isinstance(output_payload, dict):
            return False
        if bool(output_payload.get("timed_out")):
            return True
        status = str(output_payload.get("status") or "").strip().lower()
        return status == "timeout"

    @staticmethod
    def _response_phase(output_payload: dict[str, object] | None) -> str | None:
        if not isinstance(output_payload, dict):
            return None
        phase = str(output_payload.get("phase") or "").strip().lower()
        if phase in {"waiting-confirm", "blocked", "cancelled", "timeout"}:
            return phase
        status = str(output_payload.get("status") or "").strip().lower()
        if status in {"blocked", "cancelled", "timeout"}:
            return status
        return None

    @staticmethod
    def _build_execution_result(
        *,
        execution_context: CapabilityExecutionContext,
        mount: "CapabilityMount | None",
        payload: object,
        success: bool,
        summary: str,
        error_kind: str,
        evidence_id: str | None = None,
        evidence_emitted: bool = False,
        output: object | None = None,
    ) -> dict[str, object]:
        return {
            "success": success,
            "summary": summary,
            "trace_id": execution_context.trace_id,
            "capability_id": execution_context.capability_ref,
            "kind": mount.kind if mount is not None else None,
            "payload": payload,
            "risk_level": (
                mount.risk_level if mount is not None else execution_context.risk_level
            ),
            "risk_description": mount.risk_description if mount is not None else None,
            "evidence_contract": list(mount.evidence_contract) if mount is not None else [],
            "environment_requirements": (
                list(mount.environment_requirements) if mount is not None else []
            ),
            "environment_ref": execution_context.environment_ref,
            "work_context_id": execution_context.work_context_id,
            "action_mode": execution_context.action_mode,
            "evidence_id": evidence_id,
            "evidence_emitted": evidence_emitted,
            "output": output,
            "error_kind": error_kind,
            "error": None if success else summary,
        }

    def _make_shell_evidence_sink(self, task_id: str):
        if self._tool_bridge is None:
            return None
        return lambda payload: self._tool_bridge.record_shell_event(task_id, payload)

    def _make_file_evidence_sink(self, task_id: str):
        if self._tool_bridge is None:
            return None
        return lambda payload: self._tool_bridge.record_file_event(task_id, payload)

    def _make_browser_evidence_sink(self, task_id: str):
        if self._tool_bridge is None:
            return None
        return lambda payload: self._tool_bridge.record_browser_event(task_id, payload)

    async def _execute_skill(
        self,
        skill_name: str,
        *,
        action: str | None = None,
        file_path: str | None = None,
        script_path: str | None = None,
        source: str | None = None,
        args: list[str] | None = None,
        timeout: int | None = None,
        cwd: str | None = None,
        interpreter: str | None = None,
        payload: dict[str, object] | None = None,
    ):
        skill = self._skill_service.find_skill(skill_name)
        if skill is None:
            return _json_tool_response(
                {"success": False, "error": f"Skill '{skill_name}' not found"},
            )

        resolved_payload = payload or {}
        action = action or str(resolved_payload.get("action") or "describe")

        if action == "describe":
            return _json_tool_response(
                {
                    "success": True,
                    "summary": f"Skill '{skill_name}' description loaded.",
                    "skill": {
                        "name": skill.name,
                        "source": skill.source,
                        "path": skill.path,
                        "content": skill.content,
                        "references": skill.references,
                        "scripts": skill.scripts,
                    },
                },
            )

        if action == "load_file":
            target_path = file_path or str(resolved_payload.get("file_path") or "")
            if not target_path:
                return _json_tool_response(
                    {
                        "success": False,
                        "error": "file_path is required to load a skill file",
                    },
                )
            source = source or str(resolved_payload.get("source") or skill.source)
            content = self._skill_service.load_skill_file(
                skill_name=skill_name,
                file_path=target_path,
                source=source,
            )
            if content is None:
                return _json_tool_response(
                    {
                        "success": False,
                        "error": (
                            f"Failed to load '{target_path}' from skill "
                            f"'{skill_name}' ({source})"
                        ),
                    },
                )
            return _json_tool_response(
                {
                    "success": True,
                    "summary": f"Loaded skill file '{target_path}' ({source}).",
                    "file_path": target_path,
                    "source": source,
                    "content": content,
                },
            )

        if action == "run_script":
            script_path = (
                script_path
                or str(resolved_payload.get("script_path") or "")
                or str(resolved_payload.get("file_path") or "")
            )
            if not script_path:
                return _json_tool_response(
                    {
                        "success": False,
                        "error": "script_path is required to run a skill script",
                    },
                )
            resolved_script = _resolve_skill_script_path(skill, script_path)
            if resolved_script is None:
                return _json_tool_response(
                    {
                        "success": False,
                        "error": (
                            f"Script '{script_path}' not found under skill "
                            f"'{skill_name}' scripts/"
                        ),
                    },
                )
            args = _normalize_script_args(
                args or resolved_payload.get("args") or resolved_payload.get("argv"),
            )
            interpreter = (
                interpreter
                or str(resolved_payload.get("interpreter") or "")
                or None
            )
            command = _build_script_command(
                resolved_script,
                args=args,
                interpreter=interpreter,
            )
            if not command:
                return _json_tool_response(
                    {
                        "success": False,
                        "error": (
                            "Unsupported script type; specify interpreter explicitly"
                        ),
                    },
                )
            timeout_value = timeout or resolved_payload.get("timeout")
            timeout_value = (
                int(timeout_value)
                if isinstance(timeout_value, int) and timeout_value > 0
                else 120
            )
            cwd_value = cwd or str(resolved_payload.get("cwd") or "")
            cwd_path = _resolve_script_cwd(
                skill,
                resolved_script,
                cwd_value if cwd_value else None,
            )
            response = await execute_shell_command(
                command=command,
                timeout=timeout_value,
                cwd=cwd_path,
            )
            summary = _tool_response_summary(response)
            success = _tool_response_success(response)
            return _json_tool_response(
                {
                    "success": success,
                    "summary": summary,
                    "script_path": str(resolved_script),
                    "command": command,
                    "cwd": str(cwd_path) if cwd_path is not None else None,
                    "args": args,
                    "error": None if success else summary,
                },
            )

        return _json_tool_response(
            {
                "success": False,
                "error": f"Unsupported skill action '{action}'",
            },
        )

    async def _execute_mcp(
        self,
        client_key: str,
        *,
        tool_name: str | None = None,
        tool_args: dict[str, object] | None = None,
        timeout: float | None = None,
        payload: dict[str, object] | None = None,
    ):
        if self._mcp_manager is None:
            return _json_tool_response(
                {"success": False, "error": "MCP manager is not available"},
            )

        resolved_payload = payload or {}
        tool_name = tool_name or str(resolved_payload.get("tool_name") or "")
        if not tool_name:
            return _json_tool_response(
                {
                    "success": False,
                    "error": "tool_name is required to execute an MCP tool",
                },
            )

        tool_args = tool_args or resolved_payload.get("tool_args")
        if tool_args is None:
            tool_args = {}
        if not isinstance(tool_args, dict):
            return _json_tool_response(
                {
                    "success": False,
                    "error": "tool_args must be an object",
                },
            )
        timeout = timeout or resolved_payload.get("timeout")

        client = await self._mcp_manager.get_client(client_key)
        if client is None:
            return _json_tool_response(
                {
                    "success": False,
                    "error": f"MCP client '{client_key}' not found or not connected",
                },
            )

        callable_fn = await client.get_callable_function(
            tool_name,
            wrap_tool_result=True,
            execution_timeout=float(timeout) if timeout else None,
        )
        response = await callable_fn(**tool_args)
        summary = _tool_response_summary(response)
        success = _tool_response_success(response)
        response_payload = _tool_response_payload(response)
        if response_payload is None and not success:
            response_payload = {
                "success": False,
                "error": summary,
            }
        return _json_tool_response(
            {
                "success": success,
                "summary": summary,
                "client_key": client_key,
                "tool_name": tool_name,
                "payload": tool_args,
                "tool_output": response_payload,
                "error": None if success else summary,
            },
        )

    async def _execute_system(
        self,
        capability_id: str,
        *,
        payload: dict[str, object] | None = None,
        **kwargs,
    ) -> dict[str, object]:
        if self._system_handler is None:
            return {
                "success": False,
                "error": "System capability handler is not available",
            }
        return await self._system_handler.execute(
            capability_id,
            payload=payload,
            **kwargs,
        )
