# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import shlex
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..agents.tools import (
    bind_browser_evidence_sink,
    bind_desktop_evidence_sink,
    bind_file_evidence_sink,
    bind_shell_evidence_sink,
    browser_use,
    desktop_actuation,
    desktop_screenshot,
    document_surface,
    edit_file,
    execute_shell_command,
    get_current_time,
    read_file,
    send_file_to_user,
    write_file,
)
from ..kernel.child_run_shell import (
    ChildRunWriterContract,
    ChildRunWriterLeaseConflict,
    run_child_task_with_writer_lease,
)
from ..kernel.runtime_outcome import (
    classify_runtime_outcome,
    evidence_status_for_outcome,
)
from ..app.mcp.runtime_contract import infer_mcp_activation_class
from .activation_models import ActivationRequest
from .activation_runtime import ActivationRuntime
from .activation_strategies import build_mcp_activation_strategy
from .browser_runtime import BrowserRuntimeService
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
from .external_runtime_actions import parse_external_runtime_action_payload
from .external_adapter_execution import ExternalAdapterExecution
from .external_runtime_execution import ExternalRuntimeExecution
from .install_templates import (
    resolve_install_template_ids_for_capability,
    run_install_template_activate,
)
from .skill_service import CapabilitySkillService
from .tool_execution_contracts import ToolExecutionContract, get_tool_execution_contract

if TYPE_CHECKING:
    from ..kernel import KernelToolBridge
    from ..kernel.models import KernelTask
    from .models import CapabilityMount
    from .system_handlers import SystemCapabilityHandler


_TOOL_EXECUTORS = {
    "tool:browser_use": browser_use,
    "tool:desktop_actuation": desktop_actuation,
    "tool:desktop_screenshot": desktop_screenshot,
    "tool:document_surface": document_surface,
    "tool:edit_file": edit_file,
    "tool:execute_shell_command": execute_shell_command,
    "tool:get_current_time": get_current_time,
    "tool:read_file": read_file,
    "tool:send_file_to_user": send_file_to_user,
    "tool:write_file": write_file,
}

_READ_ONLY_EVIDENCE_CONTRACTS = frozenset(
    {
        "call-record",
        "file-read",
        "screenshot-artifact",
    },
)
_WRITE_EVIDENCE_CONTRACTS = frozenset(
    {
        "browser-action",
        "browser-artifact",
        "file-edit",
        "file-transfer",
        "file-write",
        "shell-command",
    },
)
_SHARED_WRITER_SCOPE_EVIDENCE_CONTRACTS = frozenset(
    {
        "file-edit",
        "file-transfer",
        "file-write",
    },
)
_TOOL_BRIDGE_EVIDENCE_CONTRACTS = frozenset(
    {
        "browser-action",
        "browser-artifact",
        "file-edit",
        "file-write",
        "shell-command",
    },
)
_DIRECT_WRITER_LEASE_TTL_SECONDS = 60
_DIRECT_WRITER_LEASE_HEARTBEAT_SECONDS = 20.0


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
        external_adapter_execution: ExternalAdapterExecution | None = None,
        external_runtime_execution: ExternalRuntimeExecution | None = None,
        tool_bridge: "KernelToolBridge | None" = None,
        capability_service: object | None = None,
        state_store: object | None = None,
        environment_service: object | None = None,
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
        self._external_adapter_execution = external_adapter_execution
        self._external_runtime_execution = external_runtime_execution
        self._tool_bridge = tool_bridge
        self._capability_service = capability_service
        self._state_store = state_store
        self._browser_runtime_service: BrowserRuntimeService | None = None
        self._environment_service = environment_service
        self._mcp_manager = mcp_manager
        self._system_handler = system_handler

    def set_tool_bridge(self, tool_bridge: "KernelToolBridge | None") -> None:
        self._tool_bridge = tool_bridge

    def set_environment_service(self, environment_service: object | None) -> None:
        self._environment_service = environment_service
        if self._browser_runtime_service is not None:
            setattr(
                self._browser_runtime_service,
                "_environment_service",
                environment_service,
            )
        if self._external_adapter_execution is not None:
            self._external_adapter_execution.set_environment_service(environment_service)

    def set_mcp_manager(self, mcp_manager: object | None) -> None:
        self._mcp_manager = mcp_manager
        if self._external_adapter_execution is not None:
            self._external_adapter_execution.set_mcp_manager(mcp_manager)

    def set_runtime_provider(self, runtime_provider: object | None) -> None:
        if self._external_adapter_execution is not None:
            self._external_adapter_execution.set_provider_runtime_facade(
                runtime_provider,
            )

    def set_system_handler(self, system_handler: "SystemCapabilityHandler | None") -> None:
        self._system_handler = system_handler

    def _get_browser_runtime_service(self) -> BrowserRuntimeService | None:
        if self._browser_runtime_service is None and self._state_store is not None:
            self._browser_runtime_service = BrowserRuntimeService(self._state_store)
        if self._browser_runtime_service is None:
            return None
        setattr(
            self._browser_runtime_service,
            "_environment_service",
            self._environment_service,
        )
        return self._browser_runtime_service

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
                kwargs.pop("capability_id", None)
                return await self._execute_system(
                    capability_id,
                    payload=payload,
                    **kwargs,
                )

            return _system_executor

        if capability_id.startswith(("project:", "adapter:", "runtime:")):

            async def _external_package_executor(
                action: str | None = None,
                timeout: int | None = None,
                payload: dict[str, object] | None = None,
            ):
                return await self._execute_external_package(
                    capability_id,
                    action=action,
                    timeout=timeout,
                    payload=payload,
                )

            return _external_package_executor

        return None

    async def execute_task(self, task: "KernelTask") -> dict[str, object]:
        capability_id = task.capability_ref or ""
        payload = self._hydrate_builtin_tool_payload(
            capability_id,
            payload=dict(task.payload or {}),
        )
        if capability_id.startswith(("project:", "adapter:", "runtime:")):
            payload.setdefault("owner_agent_id", task.owner_agent_id)
            payload.setdefault("environment_ref", task.environment_ref)
            payload.setdefault("work_context_id", task.work_context_id)
        tool_contract = get_tool_execution_contract(capability_id)
        if capability_id.startswith("system:"):
            payload.setdefault("task_id", task.id)
            payload.setdefault("owner_agent_id", task.owner_agent_id)
            payload.setdefault("goal_id", task.goal_id)
            payload.setdefault("environment_ref", task.environment_ref)
        mount = self._get_capability(capability_id)
        execution_context = self._build_execution_context(
            task,
            payload=payload,
            mount=mount,
            tool_contract=tool_contract,
        )
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

        if tool_contract is not None:
            validation_error = tool_contract.validate_payload(payload)
            if validation_error is not None:
                return self._build_execution_result(
                    execution_context=execution_context,
                    mount=mount,
                    payload=_json_safe(execution_context.payload),
                    success=False,
                    summary=validation_error,
                    error_kind="failed",
                    read_only=execution_context.is_read_only,
                    concurrency_class=execution_context.concurrency_class,
                    preflight_policy=execution_context.preflight_policy,
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

        kwargs = _filter_executor_kwargs(
            executor,
            execution_context.payload,
            normalization_signature_source=tool_contract.executor if tool_contract is not None else executor,
        )
        json_safe_kwargs = _json_safe(kwargs)
        evidence_emitted = False
        concurrency_class = execution_context.concurrency_class
        preflight_policy = execution_context.preflight_policy
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
            "concurrency_class": concurrency_class,
            "preflight_policy": preflight_policy,
            "tool_contract": capability_id if tool_contract is not None else None,
        }

        with bind_shell_evidence_sink(
            self._make_shell_evidence_sink(task.id, execution_metadata=metadata),
        ):
            with bind_file_evidence_sink(
                self._make_file_evidence_sink(task.id, execution_metadata=metadata),
            ):
                with bind_desktop_evidence_sink(
                    self._make_desktop_evidence_sink(task.id, execution_metadata=metadata),
                ):
                    with bind_browser_evidence_sink(
                        self._make_browser_evidence_sink(task.id, execution_metadata=metadata),
                    ):
                        try:
                            response = await self._execute_direct_path(
                                executor=executor,
                                kwargs=kwargs,
                                execution_context=execution_context,
                                mount=mount,
                            )
                        except ChildRunWriterLeaseConflict as exc:
                            summary = str(exc)
                            error_kind = "blocked"
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
                                read_only=execution_context.is_read_only,
                                concurrency_class=concurrency_class,
                                preflight_policy=preflight_policy,
                            )
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
                                read_only=execution_context.is_read_only,
                                concurrency_class=concurrency_class,
                                preflight_policy=preflight_policy,
                            )

        summary = _tool_response_summary(response)
        output_payload = (
            tool_contract.normalize_output(response)
            if tool_contract is not None
            else _tool_response_payload(response)
        )
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
        handled_by_tool_bridge = (
            self._tool_bridge is not None
            and self._resolve_evidence_owner(mount) == "tool-bridge"
        )
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
            read_only=execution_context.is_read_only,
            concurrency_class=concurrency_class,
            preflight_policy=preflight_policy,
        )

    async def execute_task_batch(
        self,
        tasks: list["KernelTask"],
    ) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for concurrency_class, batch in self.partition_execution_batch(tasks):
            if concurrency_class == "parallel-read":
                results.extend(await asyncio.gather(*(self.execute_task(task) for task in batch)))
                continue
            for task in batch:
                results.append(await self.execute_task(task))
        return results

    def partition_execution_batch(
        self,
        tasks: list["KernelTask"],
    ) -> list[tuple[str, list["KernelTask"]]]:
        partitions: list[tuple[str, list["KernelTask"]]] = []
        current_reads: list["KernelTask"] = []
        for task in tasks:
            payload = dict(task.payload or {})
            mount = self._get_capability(task.capability_ref or "")
            tool_contract = get_tool_execution_contract(task.capability_ref or "")
            action_mode = self._resolve_action_mode(
                mount,
                tool_contract=tool_contract,
                payload=payload,
            )
            concurrency_class = self._resolve_concurrency_class(
                mount,
                tool_contract=tool_contract,
                action_mode=action_mode,
                payload=payload,
            ) or "serial-write"
            if concurrency_class == "parallel-read":
                current_reads.append(task)
                continue
            if current_reads:
                partitions.append(("parallel-read", list(current_reads)))
                current_reads.clear()
            partitions.append(("serial-write", [task]))
        if current_reads:
            partitions.append(("parallel-read", list(current_reads)))
        return partitions

    def _build_execution_context(
        self,
        task: "KernelTask",
        *,
        payload: dict[str, object],
        mount: "CapabilityMount | None",
        tool_contract: ToolExecutionContract | None = None,
    ) -> CapabilityExecutionContext:
        action_mode = self._resolve_action_mode(
            mount,
            tool_contract=tool_contract,
            payload=payload,
        )
        writer_lock_required = self._requires_writer_lock_scope(
            mount,
            action_mode=action_mode,
        )
        writer_lock_scope = (
            self._resolve_writer_lock_scope(
                mount=mount,
                payload=payload,
                environment_ref=task.environment_ref,
            )
            if mount is not None and writer_lock_required
            else None
        )
        return CapabilityExecutionContext.from_kernel_task(
            task,
            action_mode=action_mode,
            concurrency_class=self._resolve_concurrency_class(
                mount,
                tool_contract=tool_contract,
                action_mode=action_mode,
                payload=payload,
            ),
            writer_lock_scope=writer_lock_scope,
            writer_lock_required=writer_lock_required,
            preflight_policy=self._resolve_preflight_policy(
                mount,
                tool_contract=tool_contract,
            ),
            evidence_mode=self._resolve_evidence_owner(mount),
            payload=payload,
        )

    async def _execute_direct_path(
        self,
        *,
        executor: object,
        kwargs: dict[str, object],
        execution_context: CapabilityExecutionContext,
        mount: "CapabilityMount",
    ) -> object:
        writer_contract = self._resolve_writer_contract(
            mount=mount,
            execution_context=execution_context,
        )
        if execution_context.action_mode == "write" and execution_context.writer_lock_required:
            if execution_context.writer_lock_scope is None:
                raise ChildRunWriterLeaseConflict(
                    "Write mount is blocked because no writer lock scope could be resolved.",
                )
        return await run_child_task_with_writer_lease(
            label="capability-direct-execution",
            execute=lambda: self._invoke_executor(executor, **kwargs),
            environment_service=self._environment_service,
            owner_agent_id=execution_context.owner_agent_id,
            worker_id=execution_context.owner_agent_id,
            contract=writer_contract,
            mcp_manager=None,
            mcp_overlay_contract=None,
            ttl_seconds=_DIRECT_WRITER_LEASE_TTL_SECONDS,
            heartbeat_interval_seconds=_DIRECT_WRITER_LEASE_HEARTBEAT_SECONDS,
        )

    @staticmethod
    def _hydrate_builtin_tool_payload(
        capability_id: str,
        *,
        payload: dict[str, object],
    ) -> dict[str, object]:
        if capability_id != "tool:browser_use":
            return payload
        if isinstance(payload.get("session_id"), str) and str(payload["session_id"]).strip():
            return payload
        request_context = payload.get("request_context")
        if not isinstance(request_context, dict):
            return payload
        main_brain_runtime = request_context.get("main_brain_runtime")
        runtime_environment = (
            dict(main_brain_runtime.get("environment"))
            if isinstance(main_brain_runtime, dict)
            and isinstance(main_brain_runtime.get("environment"), dict)
            else {}
        )
        resolved_session_id = None
        for candidate in (
            runtime_environment.get("session_id"),
            request_context.get("session_id"),
        ):
            if isinstance(candidate, str) and candidate.strip():
                resolved_session_id = candidate.strip()
                break
        if resolved_session_id is None:
            return payload
        hydrated = dict(payload)
        hydrated["session_id"] = resolved_session_id
        return hydrated

    async def _invoke_executor(self, executor: object, **kwargs) -> object:
        result = executor(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def _resolve_writer_contract(
        self,
        *,
        mount: "CapabilityMount | None",
        execution_context: CapabilityExecutionContext,
    ) -> ChildRunWriterContract | None:
        if mount is None or execution_context.action_mode != "write":
            return None
        writer_lock_scope = execution_context.writer_lock_scope
        if writer_lock_scope is None:
            return None
        return ChildRunWriterContract(
            access_mode="writer",
            lease_class="exclusive-writer",
            writer_lock_scope=writer_lock_scope,
            environment_ref=execution_context.environment_ref,
        )

    @classmethod
    def _requires_writer_lock_scope(
        cls,
        mount: "CapabilityMount | None",
        *,
        action_mode: str | None,
    ) -> bool:
        if mount is None or action_mode != "write":
            return False
        declared_scope = cls._execution_policy_value(mount, "writer_lock_scope")
        if cls._normalize_writer_scope(declared_scope) is not None:
            return True
        declared_scope_source = cls._normalize_writer_scope(
            cls._execution_policy_value(mount, "writer_scope_source")
        )
        if declared_scope_source is not None:
            return True
        return bool(
            set(mount.evidence_contract) & _SHARED_WRITER_SCOPE_EVIDENCE_CONTRACTS
        )

    @classmethod
    def _resolve_writer_lock_scope(
        cls,
        *,
        mount: "CapabilityMount",
        payload: dict[str, object],
        environment_ref: str | None,
    ) -> str | None:
        declared_scope = cls._normalize_writer_scope(
            cls._execution_policy_value(mount, "writer_lock_scope")
        )
        if declared_scope is not None:
            return declared_scope
        scope_source = cls._execution_policy_value(mount, "writer_scope_source")
        if scope_source == "file_path":
            return cls._file_writer_lock_scope(payload.get("file_path"))
        if scope_source == "environment_ref":
            return cls._normalize_writer_scope(environment_ref)
        return None

    @staticmethod
    def _file_writer_lock_scope(value: object | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return f"file:{Path(text).resolve()}"

    @staticmethod
    def _normalize_writer_scope(value: object | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _resolve_action_mode(
        mount: "CapabilityMount | None",
        *,
        tool_contract: ToolExecutionContract | None = None,
        payload: dict[str, object] | None = None,
    ) -> str | None:
        if mount is not None:
            declared = CapabilityExecutionFacade._execution_policy_value(
                mount,
                "action_mode",
            )
            if declared in {"read", "write"}:
                return declared
        if tool_contract is not None:
            resolved = tool_contract.resolve_action_mode(payload or {})
            if resolved in {"read", "write"}:
                return resolved
        if mount is None:
            return None
        contracts = set(mount.evidence_contract)
        if contracts & _READ_ONLY_EVIDENCE_CONTRACTS:
            return "read"
        if contracts & _WRITE_EVIDENCE_CONTRACTS:
            return "write"
        return None

    @staticmethod
    def _resolve_concurrency_class(
        mount: "CapabilityMount | None",
        *,
        tool_contract: ToolExecutionContract | None,
        action_mode: str | None,
        payload: dict[str, object] | None = None,
    ) -> str | None:
        if mount is not None:
            declared = CapabilityExecutionFacade._execution_policy_value(
                mount,
                "concurrency_class",
            )
            if declared in {"parallel-read", "serial-write"}:
                return declared
        if tool_contract is not None:
            return tool_contract.resolve_concurrency_class(
                payload or {},
                action_mode=action_mode if action_mode in {"read", "write"} else None,
            )
        if action_mode == "read":
            return "parallel-read"
        if action_mode == "write":
            return "serial-write"
        return None

    @staticmethod
    def _resolve_preflight_policy(
        mount: "CapabilityMount | None",
        *,
        tool_contract: ToolExecutionContract | None,
    ) -> str | None:
        if mount is not None:
            declared = CapabilityExecutionFacade._execution_policy_value(
                mount,
                "preflight_policy",
            )
            if declared is not None:
                return declared
        if tool_contract is not None:
            return tool_contract.preflight_policy
        return None

    @staticmethod
    def _resolve_evidence_owner(mount: "CapabilityMount | None") -> str:
        if mount is None:
            return "execution-facade"
        declared = CapabilityExecutionFacade._execution_policy_value(
            mount,
            "evidence_owner",
        )
        if declared in {"execution-facade", "tool-bridge"}:
            return declared
        contracts = set(mount.evidence_contract)
        if mount.source_kind == "tool" and contracts & _TOOL_BRIDGE_EVIDENCE_CONTRACTS:
            return "tool-bridge"
        return "execution-facade"

    @staticmethod
    def _execution_policy_value(
        mount: "CapabilityMount",
        key: str,
    ) -> str | None:
        policy = mount.metadata.get("execution_policy")
        if not isinstance(policy, dict):
            return None
        value = policy.get(key)
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None
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
        dispatch_status = str(output_payload.get("dispatch_status") or "").strip().lower()
        if dispatch_status == "canceled":
            dispatch_status = "cancelled"
        if dispatch_status in {"waiting-confirm", "blocked", "cancelled", "timeout"}:
            return dispatch_status
        phase = str(output_payload.get("phase") or "").strip().lower()
        if phase == "canceled":
            phase = "cancelled"
        if phase in {"waiting-confirm", "blocked", "cancelled", "timeout"}:
            return phase
        status = str(output_payload.get("status") or "").strip().lower()
        if status == "canceled":
            status = "cancelled"
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
        read_only: bool = False,
        concurrency_class: str | None = None,
        preflight_policy: str | None = None,
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
            "read_only": read_only,
            "concurrency_class": concurrency_class,
            "preflight_policy": preflight_policy,
            "evidence_id": evidence_id,
            "evidence_emitted": evidence_emitted,
            "output": output,
            "error_kind": error_kind,
            "error": None if success else summary,
            "execution_contract": {
                "read_only": read_only,
                "concurrency_class": concurrency_class,
                "preflight_policy": preflight_policy,
            },
        }

    def _make_shell_evidence_sink(
        self,
        task_id: str,
        *,
        execution_metadata: dict[str, object] | None = None,
    ):
        if self._tool_bridge is None:
            return None
        return lambda payload: self._tool_bridge.record_shell_event(
            task_id,
            {
                **dict(execution_metadata or {}),
                **dict(payload or {}),
            },
        )

    def _make_file_evidence_sink(
        self,
        task_id: str,
        *,
        execution_metadata: dict[str, object] | None = None,
    ):
        if self._tool_bridge is None:
            return None
        return lambda payload: self._tool_bridge.record_file_event(
            task_id,
            {
                **dict(execution_metadata or {}),
                **dict(payload or {}),
            },
        )

    def _make_browser_evidence_sink(
        self,
        task_id: str,
        *,
        execution_metadata: dict[str, object] | None = None,
    ):
        if self._tool_bridge is None:
            return None
        return lambda payload: self._tool_bridge.record_browser_event(
            task_id,
            {
                **dict(execution_metadata or {}),
                **dict(payload or {}),
            },
        )

    def _make_desktop_evidence_sink(
        self,
        task_id: str,
        *,
        execution_metadata: dict[str, object] | None = None,
    ):
        if self._tool_bridge is None:
            return None
        return lambda payload: self._tool_bridge.record_desktop_event(
            task_id,
            {
                **dict(execution_metadata or {}),
                **dict(payload or {}),
            },
        )

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
        scope_ref = self._resolve_mcp_scope_ref(resolved_payload)
        activation_result = await self._ensure_mcp_activation(
            client_key,
            payload=resolved_payload,
            scope_ref=scope_ref,
        )
        if activation_result is not None and activation_result.status != "ready":
            return _json_tool_response(
                {
                    "success": False,
                    "summary": activation_result.summary or f"MCP client '{client_key}' is blocked.",
                    "client_key": client_key,
                    "activation": activation_result.model_dump(mode="json"),
                    "error": activation_result.summary or f"MCP client '{client_key}' is blocked.",
                },
            )

        client = await self._get_mcp_client(client_key, scope_ref=scope_ref)
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
                "scope_ref": scope_ref,
                "tool_name": tool_name,
                "payload": tool_args,
                "tool_output": response_payload,
                "activation": (
                    activation_result.model_dump(mode="json")
                    if activation_result is not None
                    else None
                ),
                "error": None if success else summary,
            },
        )

    async def _ensure_mcp_activation(
        self,
        client_key: str,
        *,
        payload: dict[str, object],
        scope_ref: str | None,
    ):
        if self._mcp_manager is None:
            return None
        runtime_getter = getattr(self._mcp_manager, "get_runtime_record", None)
        if not callable(runtime_getter):
            return None
        scoped_record = await self._get_mcp_runtime_record(client_key, scope_ref=scope_ref)
        base_record = (
            await self._get_mcp_runtime_record(client_key)
            if scope_ref is not None
            else scoped_record
        )
        activation_class = infer_mcp_activation_class(
            scoped_record or base_record,
            requested_scope_ref=scope_ref,
        )
        strategy = build_mcp_activation_strategy(
            activation_class=activation_class,
            client_key=client_key,
            mcp_manager=self._mcp_manager,
            capability_service=self._capability_service,
            config=payload,
        )
        return await ActivationRuntime().activate(
            ActivationRequest(
                subject_id=f"mcp:{client_key}",
                activation_class=activation_class,
                metadata=dict(payload),
            ),
            strategy,
        )

    async def _get_mcp_runtime_record(
        self,
        client_key: str,
        *,
        scope_ref: str | None = None,
    ):
        if self._mcp_manager is None:
            return None
        getter = getattr(self._mcp_manager, "get_runtime_record", None)
        if not callable(getter):
            return None
        try:
            return await getter(client_key, scope_ref=scope_ref)
        except TypeError:
            return await getter(client_key)

    async def _get_mcp_client(
        self,
        client_key: str,
        *,
        scope_ref: str | None = None,
    ):
        if self._mcp_manager is None:
            return None
        getter = getattr(self._mcp_manager, "get_client", None)
        if not callable(getter):
            return None
        try:
            return await getter(client_key, scope_ref=scope_ref)
        except TypeError:
            return await getter(client_key)

    @staticmethod
    def _resolve_mcp_scope_ref(payload: dict[str, object]) -> str | None:
        overlay = payload.get("mcp_scope_overlay")
        overlay_payload = overlay if isinstance(overlay, dict) else {}
        for candidate in (
            payload.get("scope_ref"),
            overlay_payload.get("scope_ref"),
            overlay_payload.get("session_scope_ref"),
            overlay_payload.get("seat_scope_ref"),
        ):
            value = str(candidate or "").strip()
            if value:
                return value
        return None

    async def _execute_external_package(
        self,
        capability_id: str,
        *,
        action: str | None = None,
        timeout: int | None = None,
        payload: dict[str, object] | None = None,
    ):
        mount = self._get_capability(capability_id)
        if mount is None:
            return _json_tool_response(
                {"success": False, "error": f"Capability '{capability_id}' not found"},
            )
        resolved_payload = payload or {}
        resolved_action = str(
            action or resolved_payload.get("action") or "run",
        ).strip().lower()
        metadata = dict(mount.metadata or {})
        adapter_contract = dict(metadata.get("adapter_contract") or {})
        runtime_contract = dict(metadata.get("runtime_contract") or {})
        if resolved_action == "describe":
            return _json_tool_response(
                {
                    "success": True,
                    "summary": f"Loaded external capability '{capability_id}'.",
                    "capability": mount.model_dump(mode="json"),
                },
            )
        if adapter_contract:
            if self._external_adapter_execution is None:
                message = "External adapter execution service is not available."
                return _json_tool_response(
                    {
                        "success": False,
                        "error": message,
                        "summary": message,
                    },
                )
            response = await self._external_adapter_execution.execute_action(
                mount=mount,
                action_id=resolved_action,
                payload=resolved_payload,
            )
            return _json_tool_response(response)
        if runtime_contract.get("runtime_kind") in {"cli", "service"}:
            supported_runtime_actions = {
                str(item).strip().lower()
                for item in list(runtime_contract.get("supported_actions") or [])
                if str(item).strip()
            }
            if resolved_action not in supported_runtime_actions | {"describe"}:
                message = (
                    f"External capability '{capability_id}' is not a formal adapter and does not expose business action '{resolved_action}'."
                )
                return _json_tool_response(
                    {
                        "success": False,
                        "error": message,
                        "summary": message,
                    },
                )
            typed_payload, validation_error = parse_external_runtime_action_payload(
                mount=mount,
                action=resolved_action,
                payload=resolved_payload,
            )
            if validation_error is not None:
                return _json_tool_response(
                    {
                        "success": False,
                        "error": validation_error,
                        "summary": validation_error,
                    },
                )
            if self._external_runtime_execution is None:
                if runtime_contract.get("runtime_kind") == "cli" and resolved_action == "run":
                    command = str(metadata.get("execute_command") or "").strip()
                    if not command:
                        return _json_tool_response(
                            {
                                "success": False,
                                "error": (
                                    f"External capability '{capability_id}' does not declare an executable command"
                                ),
                            },
                        )
                    cli_args = [
                        shlex.quote(str(item))
                        for item in getattr(typed_payload, "args", [])
                        if str(item).strip()
                    ]
                    if cli_args:
                        command = f"{command} {' '.join(cli_args)}"
                    timeout_value = int(
                        getattr(typed_payload, "timeout_sec", None) or timeout or 180,
                    )
                    response = await execute_shell_command(
                        command=command,
                        timeout=timeout_value,
                        cwd=str(metadata.get("cwd") or "").strip() or None,
                    )
                    summary = _tool_response_summary(response)
                    success = _tool_response_success(response)
                    return _json_tool_response(
                        {
                            "success": success,
                            "summary": summary,
                            "command": command,
                            "cwd": str(metadata.get("cwd") or "").strip() or None,
                            "error": None if success else summary,
                            "output": _tool_response_payload(response),
                        },
                    )
                message = "External runtime execution service is not available."
                return _json_tool_response(
                    {
                        "success": False,
                        "error": message,
                        "summary": message,
                    },
                )
            if runtime_contract.get("runtime_kind") == "cli":
                response = await self._external_runtime_execution.run_cli(
                    mount,
                    typed_payload,
                )
            elif resolved_action == "start":
                response = await self._external_runtime_execution.start_service(
                    mount,
                    typed_payload,
                )
            elif resolved_action == "healthcheck":
                response = await self._external_runtime_execution.healthcheck_service(
                    mount,
                    typed_payload,
                )
            elif resolved_action == "stop":
                response = await self._external_runtime_execution.stop_service(
                    mount,
                    typed_payload,
                )
            elif resolved_action == "restart":
                response = await self._external_runtime_execution.restart_service(
                    mount,
                    typed_payload,
                )
            else:
                response = {
                    "success": False,
                    "summary": (
                        f"External capability '{capability_id}' does not support typed action '{resolved_action}'."
                    ),
                }
            return _json_tool_response(response)
        command = ""
        if resolved_action in {"healthcheck", "doctor"}:
            command = str(metadata.get("healthcheck_command") or "").strip()
        if not command:
            command = str(
                resolved_payload.get("command")
                or metadata.get("execute_command")
                or metadata.get("healthcheck_command")
                or ""
            ).strip()
        if not command:
            return _json_tool_response(
                {
                    "success": False,
                    "error": (
                        f"External capability '{capability_id}' does not declare an executable command"
                    ),
                },
            )
        timeout_value = timeout or resolved_payload.get("timeout")
        timeout_value = (
            int(timeout_value)
            if isinstance(timeout_value, int) and timeout_value > 0
            else 180
        )
        cwd_value = str(resolved_payload.get("cwd") or metadata.get("cwd") or "").strip()
        response = await execute_shell_command(
            command=command,
            timeout=timeout_value,
            cwd=cwd_value or None,
        )
        summary = _tool_response_summary(response)
        success = _tool_response_success(response)
        return _json_tool_response(
            {
                "success": success,
                "summary": summary,
                "command": command,
                "cwd": cwd_value or None,
                "error": None if success else summary,
                "output": _tool_response_payload(response),
            },
        )

    async def _execute_system(
        self,
        capability_id: str,
        *,
        payload: dict[str, object] | None = None,
        **kwargs,
    ) -> dict[str, object]:
        activation_response = await self._execute_install_template_activation_frontdoor(
            capability_id,
            payload=payload,
        )
        if activation_response is not None:
            return activation_response
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

    async def _execute_install_template_activation_frontdoor(
        self,
        capability_id: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        template_ids = resolve_install_template_ids_for_capability(capability_id)
        if not template_ids:
            return None
        if not capability_id.startswith("system:"):
            return None
        for template_id in template_ids:
            result = await run_install_template_activate(
                template_id,
                capability_service=self._capability_service,
                browser_runtime_service=self._get_browser_runtime_service(),
                environment_service=self._environment_service,
                config=dict(payload or {}),
            )
            if result is None:
                continue
            activation_payload = result.model_dump(mode="json")
            success = result.status == "ready"
            return _json_tool_response(
                {
                    "success": success,
                    "summary": result.summary,
                    "template_id": template_id,
                    "activation": activation_payload,
                    "error": None if success else result.summary,
                },
            )
        return None
