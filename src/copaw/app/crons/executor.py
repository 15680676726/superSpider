# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import Any, Dict, TYPE_CHECKING

from ..runtime_center.execution_runtime_projection import resolve_canonical_host_identity
from ..runtime_launch_contract import build_runtime_launch_contract
from ..runtime_commands import infer_turn_capability_and_risk
from ...kernel.runtime_coordination import build_durable_runtime_coordination
from .models import CronJobSpec

if TYPE_CHECKING:
    from ...kernel import KernelDispatcher

logger = logging.getLogger(__name__)


def _log_non_executing_admission(prefix: str, job_id: str, admission: object) -> None:
    phase = getattr(admission, "phase", None)
    task_id = getattr(admission, "task_id", None)
    summary = getattr(admission, "summary", None) or getattr(admission, "error", None)
    if phase == "waiting-confirm":
        logger.warning(
            "%s held for confirmation: job_id=%s task_id=%s",
            prefix,
            job_id,
            task_id,
        )
        return
    logger.warning(
        "%s blocked before execution: job_id=%s task_id=%s phase=%s summary=%s",
        prefix,
        job_id,
        task_id,
        phase,
        summary,
    )


class CronExecutor:
    def __init__(
        self,
        *,
        kernel_dispatcher: "KernelDispatcher | None" = None,
    ):
        self._kernel_dispatcher = kernel_dispatcher

    def set_kernel_dispatcher(self, dispatcher: "KernelDispatcher | None") -> None:
        self._kernel_dispatcher = dispatcher

    async def execute(self, job: CronJobSpec) -> None:
        """Execute one job once.

        - task_type text: send fixed text to channel
        - task_type agent: dispatch kernel task (system:dispatch_query) and
            stream replies via the channel manager
        """
        if self._kernel_dispatcher is None:
            raise RuntimeError("Kernel dispatcher is required for cron execution")
        target_user_id = job.dispatch.target.user_id
        target_session_id = job.dispatch.target.session_id
        dispatch_meta: Dict[str, Any] = dict(job.dispatch.meta or {})

        override_capability_ref = _string_value(
            (job.meta or {}).get("capability_ref") if isinstance(job.meta, dict) else None,
        )
        if override_capability_ref:
            override_payload = (
                (job.meta or {}).get("payload")
                if isinstance(job.meta, dict)
                else None
            )
            override_risk_level = _string_value(
                (job.meta or {}).get("risk_level") if isinstance(job.meta, dict) else None,
            )
            await self._dispatch_capability_via_kernel(
                job,
                capability_ref=override_capability_ref,
                payload=override_payload if isinstance(override_payload, dict) else {},
                risk_level=override_risk_level,
                target_user_id=target_user_id,
                target_session_id=target_session_id,
                dispatch_meta=dispatch_meta,
            )
            return
        logger.info(
            "cron execute: job_id=%s channel=%s task_type=%s "
            "target_user_id=%s target_session_id=%s",
            job.id,
            job.dispatch.channel,
            job.task_type,
            target_user_id[:40] if target_user_id else "",
            target_session_id[:40] if target_session_id else "",
        )

        if job.task_type == "text" and job.text:
            logger.info(
                "cron send_text: job_id=%s channel=%s len=%s",
                job.id,
                job.dispatch.channel,
                len(job.text or ""),
            )
            await self._dispatch_text_via_kernel(
                job,
                target_user_id=target_user_id,
                target_session_id=target_session_id,
                dispatch_meta=dispatch_meta,
            )
            return

        # agent: run request as the dispatch target user so context matches
        logger.info(
            "cron agent: job_id=%s channel=%s stream_query then send_event",
            job.id,
            job.dispatch.channel,
        )
        assert job.request is not None
        req: Dict[str, Any] = job.request.model_dump(mode="json")
        req["user_id"] = target_user_id or "cron"
        req["session_id"] = target_session_id or f"cron:{job.id}"

        await self._dispatch_agent_via_kernel(
            job,
            request_payload=req,
            target_user_id=target_user_id,
            target_session_id=target_session_id,
            dispatch_meta=dispatch_meta,
        )

    async def _dispatch_capability_via_kernel(
        self,
        job: CronJobSpec,
        *,
        capability_ref: str,
        payload: Dict[str, Any],
        risk_level: str | None,
        target_user_id: str,
        target_session_id: str,
        dispatch_meta: Dict[str, Any],
    ) -> None:
        from ...kernel import KernelTask

        if self._kernel_dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not configured for cron")
        normalized_risk = (
            risk_level
            if risk_level in {"auto", "guarded", "confirm"}
            else "guarded"
        )
        environment_ref = self._resolve_environment_ref(
            job=job,
            target_session_id=target_session_id,
        )
        task = KernelTask(
            title=f"Cron capability: {job.name}",
            capability_ref=capability_ref,
            environment_ref=environment_ref,
            owner_agent_id="copaw-cron",
            risk_level=normalized_risk,
            payload={
                **dict(payload or {}),
                "job_id": job.id,
                "dispatch": {
                    "channel": job.dispatch.channel,
                    "user_id": target_user_id,
                    "session_id": target_session_id,
                    "meta": {
                        **dispatch_meta,
                        **self._host_meta(job),
                    },
                },
                "environment_ref": environment_ref,
            },
        )
        admitted = self._kernel_dispatcher.submit(task)
        if admitted.phase != "executing":
            _log_non_executing_admission("cron capability", job.id, admitted)
            return
        result = await asyncio.wait_for(
            self._kernel_dispatcher.execute_task(task.id),
            timeout=job.runtime.timeout_seconds,
        )
        if not result.success:
            raise RuntimeError(
                result.error or result.summary or "cron capability execution failed",
            )

    async def _dispatch_text_via_kernel(
        self,
        job: CronJobSpec,
        *,
        target_user_id: str,
        target_session_id: str,
        dispatch_meta: Dict[str, Any],
    ) -> None:
        from ...kernel import KernelTask

        if self._kernel_dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not configured for cron")
        environment_ref = self._resolve_environment_ref(
            job=job,
            target_session_id=target_session_id,
        )
        task = KernelTask(
            title=f"Cron send_text: {job.name}",
            capability_ref="system:send_channel_text",
            environment_ref=environment_ref,
            owner_agent_id="copaw-cron",
            risk_level="guarded",
            payload={
                "channel": job.dispatch.channel,
                "user_id": target_user_id,
                "session_id": target_session_id,
                "text": job.text.strip() if job.text else "",
                "meta": {
                    **dispatch_meta,
                    **self._host_meta(job),
                },
                "job_id": job.id,
                "environment_ref": environment_ref,
            },
        )
        admitted = self._kernel_dispatcher.submit(task)
        if admitted.phase != "executing":
            _log_non_executing_admission("cron send_text", job.id, admitted)
            return
        result = await self._kernel_dispatcher.execute_task(task.id)
        if not result.success:
            raise RuntimeError(result.error or result.summary or "cron send_text failed")

    async def _dispatch_agent_via_kernel(
        self,
        job: CronJobSpec,
        *,
        request_payload: Dict[str, Any],
        target_user_id: str,
        target_session_id: str,
        dispatch_meta: Dict[str, Any],
    ) -> None:
        from ...kernel import KernelTask
        from ...kernel.query_execution_confirmation import (
            query_confirmation_request_context,
        )

        if self._kernel_dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not configured for cron")
        environment_ref = self._resolve_environment_ref(
            job=job,
            target_session_id=target_session_id,
        )
        normalized_request = self._normalized_agent_request_payload(
            job=job,
            request_payload=request_payload,
            target_user_id=target_user_id,
            target_session_id=target_session_id,
            environment_ref=environment_ref,
        )
        request_context = query_confirmation_request_context(
            SimpleNamespace(**normalized_request),
        )
        main_brain_runtime = _mapping_value(
            normalized_request.get("main_brain_runtime"),
        )
        if main_brain_runtime:
            request_context["main_brain_runtime"] = dict(main_brain_runtime)
        work_context_id = _string_value(
            normalized_request.get("work_context_id"),
        ) or _string_value(request_context.get("work_context_id"))
        task = KernelTask(
            title=f"Cron dispatch agent: {job.name}",
            capability_ref=infer_turn_capability_and_risk(
                _request_text(normalized_request),
            )[0],
            environment_ref=environment_ref,
            owner_agent_id="copaw-cron",
            work_context_id=work_context_id,
            risk_level=infer_turn_capability_and_risk(_request_text(normalized_request))[1],
            payload={
                "request": normalized_request,
                "request_context": request_context,
                "main_brain_runtime": dict(main_brain_runtime) if main_brain_runtime else {},
                "channel": job.dispatch.channel,
                "user_id": target_user_id,
                "session_id": target_session_id,
                "meta": {
                    **dispatch_meta,
                    **self._host_meta(job),
                },
                "mode": job.dispatch.mode,
                "job_id": job.id,
                "environment_ref": environment_ref,
            },
        )
        task.payload["task_id"] = task.id
        admitted = self._kernel_dispatcher.submit(task)
        if admitted.phase != "executing":
            _log_non_executing_admission("cron agent", job.id, admitted)
            return
        result = await asyncio.wait_for(
            self._kernel_dispatcher.execute_task(task.id),
            timeout=job.runtime.timeout_seconds,
        )
        if not result.success:
            raise RuntimeError(result.error or result.summary or "cron agent dispatch failed")

    def _normalized_agent_request_payload(
        self,
        *,
        job: CronJobSpec,
        request_payload: Dict[str, Any],
        target_user_id: str,
        target_session_id: str,
        environment_ref: str | None,
    ) -> Dict[str, Any]:
        normalized = dict(request_payload or {})
        normalized.update(
            {
                key: value
                for key, value in build_runtime_launch_contract(
                    entry_source="cron-job",
                    coordinator_id=job.id,
                ).items()
                if key not in normalized
            },
        )
        control_thread_id = _string_value(
            normalized.get("control_thread_id"),
        ) or _string_value(target_session_id)
        main_brain_runtime = _merge_main_brain_runtime_contexts(
            normalized.get("main_brain_runtime"),
            {
                "work_context_id": normalized.get("work_context_id"),
                "environment": {
                    "ref": environment_ref,
                    "session_id": target_session_id,
                    "continuity_source": "cron-job",
                    "resume_ready": True,
                },
            },
        )
        work_context_id = _string_value(normalized.get("work_context_id")) or _string_value(
            main_brain_runtime.get("work_context_id")
            if isinstance(main_brain_runtime, dict)
            else None,
        )
        normalized["user_id"] = target_user_id or "cron"
        normalized["session_id"] = target_session_id or f"cron:{job.id}"
        normalized["channel"] = job.dispatch.channel
        if environment_ref is not None:
            normalized["environment_ref"] = environment_ref
        if control_thread_id is not None:
            normalized["control_thread_id"] = control_thread_id
        if work_context_id is not None:
            normalized["work_context_id"] = work_context_id
        if main_brain_runtime is not None:
            normalized["main_brain_runtime"] = main_brain_runtime
        return normalized

    def _resolve_environment_ref(
        self,
        *,
        job: CronJobSpec,
        target_session_id: str,
    ) -> str | None:
        host_meta = self._host_meta(job)
        return _string_value(host_meta.get("environment_ref")) or (
            f"session:{job.dispatch.channel}:{target_session_id}"
            if target_session_id
            else None
        )

    def _host_meta(self, job: CronJobSpec) -> Dict[str, Any]:
        meta = dict(job.meta or {})
        host_snapshot = (
            dict(meta.get("host_snapshot"))
            if isinstance(meta.get("host_snapshot"), dict)
            else {}
        )
        scheduler_inputs = (
            dict(host_snapshot.get("scheduler_inputs"))
            if isinstance(host_snapshot.get("scheduler_inputs"), dict)
            else {}
        )
        environment_ref, environment_id, session_mount_id = resolve_canonical_host_identity(
            host_snapshot,
            metadata=meta,
        )
        host_meta: Dict[str, Any] = {}
        if environment_ref is not None:
            host_meta["environment_ref"] = environment_ref
        if environment_id is not None:
            host_meta["environment_id"] = environment_id
        if session_mount_id is not None:
            host_meta["session_mount_id"] = session_mount_id
        host_requirement = meta.get("host_requirement")
        if isinstance(host_requirement, dict):
            host_meta["host_requirement"] = dict(host_requirement)
        if host_snapshot:
            host_meta["host_snapshot"] = host_snapshot
        if scheduler_inputs:
            host_meta["scheduler_inputs"] = scheduler_inputs
        host_meta.update(
            build_durable_runtime_coordination(
                entrypoint="cron-job",
                coordinator_id=job.id,
            )
        )
        return host_meta


def _request_text(request_payload: Dict[str, Any]) -> str | None:
    input_payload = request_payload.get("input")
    if not isinstance(input_payload, list) or not input_payload:
        return None
    first = input_payload[0]
    if not isinstance(first, dict):
        return None
    content = first.get("content")
    if not isinstance(content, list):
        return None
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = str(item.get("text") or "").strip()
            if text:
                return text
    return None


def _string_value(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping_value(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _merge_main_brain_runtime_contexts(
    *values: object,
) -> dict[str, Any] | None:
    from ...kernel.main_brain_intake import normalize_main_brain_runtime_context

    merged: dict[str, Any] = {}
    for value in values:
        normalized = normalize_main_brain_runtime_context(value)
        if not normalized:
            continue
        work_context_id = _string_value(normalized.get("work_context_id"))
        if work_context_id is not None:
            merged["work_context_id"] = work_context_id
        for section in ("intent", "environment", "recovery"):
            payload = _mapping_value(normalized.get(section))
            if not payload:
                continue
            merged[section] = {
                **_mapping_value(merged.get(section)),
                **payload,
            }
    return merged or None
