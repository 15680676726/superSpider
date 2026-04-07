# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agentscope.tool import ToolResponse

from ..adapters.desktop.windows_host import (
    DesktopAutomationError,
    WindowSelector,
    WindowsDesktopHost,
)
from ..adapters.desktop.windows_uia import ControlSelector
from ..agents.tools.browser_control import browser_use
from ..agents.tools.evidence_runtime import bind_browser_evidence_sink
from ..capabilities.browser_runtime import (
    BrowserRuntimeService,
    BrowserSessionStartOptions,
)
from ..evidence import EvidenceLedger, EvidenceRecord
from ..industry.identity import is_execution_core_agent_id
from ..kernel import KernelTask
from ..kernel.decision_policy import MAIN_BRAIN_DECISION_ACTOR
from ..state import (
    ExecutionRoutineRecord,
    RoutineRunRecord,
    SQLiteStateStore,
)
from .models import (
    ROUTINE_FALLBACK_MODES,
    ROUTINE_RESOURCE_SCOPE_TYPES,
    SUPPORTED_BROWSER_ROUTINE_ACTIONS,
    SUPPORTED_DESKTOP_ROUTINE_ACTIONS,
    SUPPORTED_ROUTINE_EVIDENCE_ACTIONS,
    RoutineCreateFromEvidenceRequest,
    RoutineCreateRequest,
    RoutineDetail,
    RoutineDiagnosis,
    RoutineReplayRequest,
    RoutineReplayResponse,
    RoutineRunDetail,
)

SUPPORTED_ROUTINE_ENGINE_KINDS = ("browser", "desktop")
SUPPORTED_ROUTINE_ENVIRONMENT_KINDS = ("browser", "desktop")
_DESKTOP_DOCUMENT_FAMILY_BY_SUFFIX = {
    ".csv": "spreadsheets",
    ".doc": "documents",
    ".docx": "documents",
    ".ppt": "presentations",
    ".pptx": "presentations",
    ".tsv": "spreadsheets",
    ".xls": "spreadsheets",
    ".xlsm": "spreadsheets",
    ".xlsx": "spreadsheets",
}


class _DesktopHostExecutorAdapter:
    """Expose desktop host execution plus host-side hooks to EnvironmentService."""

    def __init__(self, *, host: WindowsDesktopHost, execute_action) -> None:
        self._host = host
        self._execute_action = execute_action

    def __call__(self, **kwargs):
        return self._execute_action(**kwargs)

    def prepare_execution_cleanup(self, **kwargs):
        hook = getattr(self._host, "prepare_execution_cleanup", None)
        if callable(hook):
            return hook(**kwargs)
        return {}

    def restore_foreground(self, **kwargs):
        hook = getattr(self._host, "restore_foreground", None)
        if callable(hook):
            return hook(**kwargs)
        return {}

    def verify_clipboard_restore(self, **kwargs):
        hook = getattr(self._host, "verify_clipboard_restore", None)
        if callable(hook):
            return hook(**kwargs)
        return {}

    def poll_operator_abort_signal(self, **kwargs):
        hook = getattr(self._host, "poll_operator_abort_signal", None)
        if callable(hook):
            return hook(**kwargs)
        return {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _canonical_browser_url(value: object | None) -> str | None:
    text = _string(value)
    if text is None:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return text
    normalized_path = parsed.path or ""
    if normalized_path == "/":
        normalized_path = ""
    return parsed._replace(path=normalized_path).geturl()


def _tool_response_text(response: ToolResponse | Any) -> str:
    content = getattr(response, "content", None)
    if not content:
        return ""
    block = content[0]
    if isinstance(block, dict):
        return str(block.get("text", ""))
    return str(getattr(block, "text", ""))


def _tool_response_json(response: ToolResponse | Any) -> dict[str, Any]:
    text = _tool_response_text(response)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "raw_text": text}
    return payload if isinstance(payload, dict) else {"ok": False, "raw_text": text}


def _safe_key(text: str, *, fallback: str) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "-"
        for character in (text or "").strip()
    ).strip("-")
    return normalized or fallback


def _serialize_evidence(record: EvidenceRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "task_id": record.task_id,
        "actor_ref": record.actor_ref,
        "environment_ref": record.environment_ref,
        "capability_ref": record.capability_ref,
        "risk_level": record.risk_level,
        "action_summary": record.action_summary,
        "result_summary": record.result_summary,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "status": record.status,
        "metadata": dict(record.metadata or {}),
        "artifact_refs": list(record.artifact_refs),
        "replay_refs": list(record.replay_refs),
    }


def _resource_scope_entry(
    scope_type: str | None,
    scope_value: str | None,
    *,
    reason: str | None = None,
) -> dict[str, Any] | None:
    normalized_type = _string(scope_type)
    normalized_value = _string(scope_value)
    if normalized_type is None or normalized_value is None:
        return None
    if normalized_type not in ROUTINE_RESOURCE_SCOPE_TYPES:
        return None
    payload = {"scope_type": normalized_type, "scope_value": normalized_value}
    if reason:
        payload["reason"] = reason
    return payload


def _verification_kinds(payload: dict[str, Any] | None) -> list[str]:
    kinds: list[str] = []
    for entry in list((payload or {}).get("checks") or []):
        if not isinstance(entry, dict):
            continue
        kind = _string(entry.get("kind"))
        if kind is not None:
            kinds.append(kind)
    return kinds


def _json_js(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class _RoutineFailure(RuntimeError):
    def __init__(
        self,
        failure_class: str,
        summary: str,
        *,
        metadata: dict[str, Any] | None = None,
        run_status: str = "failed",
        environment_id: str | None = None,
        session_id: str | None = None,
        lease_ref: str | None = None,
        evidence_ids: list[str] | None = None,
    ) -> None:
        super().__init__(summary)
        self.failure_class = failure_class
        self.summary = summary
        self.metadata = dict(metadata or {})
        self.run_status = run_status
        self.environment_id = environment_id
        self.session_id = session_id
        self.lease_ref = lease_ref
        self.evidence_ids = list(evidence_ids or [])


class RoutineService:
    """Formal routine definition, replay, diagnosis, and fallback service."""

    def __init__(
        self,
        *,
        routine_repository,
        routine_run_repository,
        evidence_ledger: EvidenceLedger,
        environment_service,
        kernel_dispatcher: object | None = None,
        browser_runtime_service: BrowserRuntimeService | None = None,
        state_store: SQLiteStateStore | None = None,
        memory_retain_service: object | None = None,
        learning_service: object | None = None,
    ) -> None:
        self._routine_repository = routine_repository
        self._routine_run_repository = routine_run_repository
        self._evidence_ledger = evidence_ledger
        self._environment_service = environment_service
        self._kernel_dispatcher = kernel_dispatcher
        self._browser_runtime_service = browser_runtime_service
        self._state_store = state_store
        self._memory_retain_service = memory_retain_service
        self._learning_service = learning_service

    def list_routines(
        self,
        *,
        status: str | None = None,
        owner_scope: str | None = None,
        owner_agent_id: str | None = None,
        engine_kind: str | None = None,
        limit: int | None = None,
    ) -> list[ExecutionRoutineRecord]:
        return self._routine_repository.list_routines(
            status=status,
            owner_scope=owner_scope,
            owner_agent_id=owner_agent_id,
            engine_kind=engine_kind,
            limit=limit,
        )

    def get_routine(self, routine_id: str) -> ExecutionRoutineRecord | None:
        return self._routine_repository.get_routine(routine_id)

    def list_runs(self, **kwargs: Any) -> list[RoutineRunRecord]:
        return self._routine_run_repository.list_runs(**kwargs)

    def get_run(self, run_id: str) -> RoutineRunRecord | None:
        return self._routine_run_repository.get_run(run_id)

    def create_routine(self, payload: RoutineCreateRequest) -> ExecutionRoutineRecord:
        self._validate_routine_definition(
            engine_kind=payload.engine_kind,
            environment_kind=payload.environment_kind,
        )
        record = ExecutionRoutineRecord(
            routine_key=payload.routine_key,
            name=payload.name,
            summary=payload.summary,
            status=payload.status,
            owner_scope=payload.owner_scope,
            owner_agent_id=payload.owner_agent_id,
            source_capability_id=payload.source_capability_id,
            trigger_kind=payload.trigger_kind,
            engine_kind=payload.engine_kind,
            environment_kind=payload.environment_kind,
            session_requirements=dict(payload.session_requirements or {}),
            isolation_policy=dict(payload.isolation_policy or {}),
            lock_scope=list(payload.lock_scope or []),
            input_schema=dict(payload.input_schema or {}),
            preconditions=list(payload.preconditions or []),
            expected_observations=list(payload.expected_observations or []),
            action_contract=list(payload.action_contract or []),
            success_signature=dict(payload.success_signature or {}),
            drift_signals=list(payload.drift_signals or []),
            replay_policy=dict(payload.replay_policy or {}),
            fallback_policy=dict(payload.fallback_policy or {}),
            risk_baseline=payload.risk_baseline,
            evidence_expectations=list(payload.evidence_expectations or []),
            source_evidence_ids=list(payload.source_evidence_ids or []),
            metadata=dict(payload.metadata or {}),
        )
        return self._routine_repository.upsert_routine(record)

    def create_routine_from_evidence(
        self,
        payload: RoutineCreateFromEvidenceRequest,
    ) -> ExecutionRoutineRecord:
        self._validate_routine_definition(
            engine_kind=payload.engine_kind,
            environment_kind=payload.environment_kind,
        )
        evidence_records = [
            record
            for record in (
                self._evidence_ledger.get_record(evidence_id)
                for evidence_id in payload.evidence_ids
            )
            if record is not None
        ]
        if not evidence_records:
            raise KeyError("No evidence records were found for extraction")
        evidence_records.sort(
            key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc),
        )
        for record in evidence_records:
            action = str(record.metadata.get("action") or "").strip().lower()
            if action not in SUPPORTED_ROUTINE_EVIDENCE_ACTIONS:
                raise ValueError(
                    "Routine auto extraction currently supports only open/navigate/click/screenshot",
                )
        action_contract: list[dict[str, Any]] = []
        summary_lines: list[str] = []
        expected_observations: list[dict[str, Any]] = []
        evidence_expectations: list[str] = []
        inferred_name = payload.name
        session_id: str | None = None
        source_capability_id = payload.source_capability_id
        for index, record in enumerate(evidence_records, start=1):
            metadata = dict(record.metadata or {})
            action = str(metadata.get("action") or "").strip().lower()
            session_id = session_id or _string(metadata.get("session_id"))
            source_capability_id = source_capability_id or _string(record.capability_ref)
            page_id = _string(metadata.get("page_id")) or "page_1"
            contract: dict[str, Any] = {"step": index, "action": action, "page_id": page_id}
            url = _string(metadata.get("url")) or _string(record.environment_ref)
            if action in {"open", "navigate"} and url is not None:
                contract["url"] = url
            selector = _string(metadata.get("selector"))
            ref = _string(metadata.get("ref"))
            path = _string(metadata.get("path"))
            if selector is not None:
                contract["selector"] = selector
            if ref is not None:
                contract["ref"] = ref
            if path is not None:
                contract["path"] = path
            if metadata.get("full_page") is not None:
                contract["full_page"] = bool(metadata.get("full_page"))
            button = _string(metadata.get("button"))
            if button is not None:
                contract["button"] = button
            action_contract.append(contract)
            evidence_expectations.append(action)
            expected_observations.append(
                {
                    "step": index,
                    "action": action,
                    "status": record.status,
                    "result_summary": record.result_summary,
                },
            )
            if record.result_summary:
                summary_lines.append(record.result_summary)
            if inferred_name is None and url is not None:
                parsed = urlparse(url)
                if parsed.netloc:
                    inferred_name = f"{parsed.netloc} {action} routine"
        record = ExecutionRoutineRecord(
            routine_key=payload.routine_key or _safe_key(
                inferred_name or "evidence-routine",
                fallback="evidence-routine",
            ),
            name=inferred_name or "Routine from evidence",
            summary=payload.summary or " | ".join(summary_lines[:3]),
            status="active",
            owner_scope=payload.owner_scope,
            owner_agent_id=payload.owner_agent_id,
            source_capability_id=source_capability_id,
            trigger_kind=payload.trigger_kind,
            engine_kind=payload.engine_kind,
            environment_kind=payload.environment_kind,
            session_requirements={
                **dict(payload.session_requirements or {}),
                **({"session_id": session_id} if session_id else {}),
            },
            isolation_policy=dict(payload.isolation_policy or {}),
            lock_scope=list(payload.lock_scope or []),
            input_schema=dict(payload.input_schema or {}),
            expected_observations=expected_observations,
            action_contract=action_contract,
            replay_policy=dict(payload.replay_policy or {}),
            fallback_policy=dict(payload.fallback_policy or {}),
            risk_baseline=payload.risk_baseline,
            evidence_expectations=list(dict.fromkeys(evidence_expectations)),
            source_evidence_ids=list(payload.evidence_ids or []),
            metadata={
                **dict(payload.metadata or {}),
                "extracted_from_evidence": list(payload.evidence_ids or []),
            },
        )
        return self._routine_repository.upsert_routine(record)

    def get_routine_detail(self, routine_id: str) -> RoutineDetail:
        routine = self._routine_repository.get_routine(routine_id)
        if routine is None:
            raise KeyError(f"Routine '{routine_id}' not found")
        recent_runs = self._routine_run_repository.list_runs(routine_id=routine_id, limit=10)
        last_run = recent_runs[0] if recent_runs else None
        recent_evidence = self._load_evidence_records(last_run.evidence_ids if last_run else [])
        diagnosis = self.get_diagnosis(routine_id)
        return RoutineDetail(
            routine=routine,
            last_run=last_run,
            recent_runs=recent_runs,
            recent_evidence=recent_evidence,
            diagnosis=diagnosis,
            routes={
                "detail": f"/api/routines/{routine.id}",
                "diagnosis": f"/api/routines/{routine.id}/diagnosis",
                "runs": f"/api/routines/runs?routine_id={routine.id}",
            },
        )

    def get_run_detail(self, run_id: str) -> RoutineRunDetail:
        run = self._routine_run_repository.get_run(run_id)
        if run is None:
            raise KeyError(f"Routine run '{run_id}' not found")
        routine = self._routine_repository.get_routine(run.routine_id)
        if routine is None:
            raise KeyError(f"Routine '{run.routine_id}' not found")
        return RoutineRunDetail(
            run=run,
            routine=routine,
            evidence=self._load_evidence_records(run.evidence_ids),
            routes={
                "detail": f"/api/routines/runs/{run.id}",
                "routine": f"/api/routines/{routine.id}",
                "diagnosis": f"/api/routines/{routine.id}/diagnosis",
            },
        )

    def get_diagnosis(self, routine_id: str) -> RoutineDiagnosis:
        routine = self._routine_repository.get_routine(routine_id)
        if routine is None:
            raise KeyError(f"Routine '{routine_id}' not found")
        recent_runs = self._routine_run_repository.list_runs(routine_id=routine_id, limit=10)
        last_run = recent_runs[0] if recent_runs else None
        verification_summary = self._resolve_run_verification_summary(
            routine=routine,
            run=last_run,
        )
        verification_status = _string(verification_summary.get("chain_status")) or "unknown"
        recent_failures: list[dict[str, Any]] = []
        resource_conflicts: list[dict[str, Any]] = []
        fallback_counts: dict[str, int] = {}
        lock_conflicts = 0
        page_drift_count = 0
        auth_failure_count = 0
        for run in recent_runs:
            if run.failure_class:
                recent_failures.append(
                    {
                        "run_id": run.id,
                        "failure_class": run.failure_class,
                        "status": run.status,
                        "output_summary": run.output_summary,
                        "fallback_mode": run.fallback_mode,
                        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                    },
                )
            if run.fallback_mode:
                fallback_counts[run.fallback_mode] = fallback_counts.get(run.fallback_mode, 0) + 1
            for conflict in list(run.metadata.get("resource_conflicts") or []):
                if isinstance(conflict, dict):
                    resource_conflicts.append(dict(conflict))
            if run.failure_class == "lock-conflict":
                lock_conflicts += 1
            if run.failure_class == "page-drift":
                page_drift_count += 1
            if run.failure_class == "auth-expired":
                auth_failure_count += 1
        drift_status = "drifted" if page_drift_count >= 2 else "suspect" if page_drift_count else "stable"
        selector_health = "degraded" if page_drift_count >= 2 else "watch" if page_drift_count else "healthy"
        session_health = "expired" if auth_failure_count >= 2 else "suspect" if auth_failure_count else "healthy"
        lock_health = "contended" if lock_conflicts else "healthy"
        expected_anchor_count = int(verification_summary.get("expected_anchor_count") or 0)
        actual_anchor_count = int(verification_summary.get("anchor_count") or 0)
        evidence_health = (
            "healthy"
            if (
                last_run is not None
                and verification_status == "verified"
                and actual_anchor_count >= expected_anchor_count
            )
            else "partial"
            if last_run is not None and last_run.evidence_ids
            else "missing"
        )
        recommended_actions: list[str] = []
        if drift_status != "stable":
            recommended_actions.append("Review selector/ref drift and refresh the action contract.")
        if session_health != "healthy":
            recommended_actions.append("Recover or refresh the bound session before replay.")
        if lock_health != "healthy":
            recommended_actions.append("Inspect current resource-slot holders before replay.")
        if evidence_health != "healthy":
            recommended_actions.append("Verify expected evidence capture coverage for the routine.")
        if verification_status != "verified":
            recommended_actions.append("Review the observe -> act -> verify chain before accepting this routine.")
        return RoutineDiagnosis(
            routine_id=routine.id,
            last_run_id=last_run.id if last_run else None,
            status=routine.status,
            drift_status=drift_status,
            selector_health=selector_health,
            session_health=session_health,
            lock_health=lock_health,
            evidence_health=evidence_health,
            verification_status=verification_status,
            verification_summary=verification_summary,
            recent_failures=recent_failures,
            fallback_summary={
                "counts": fallback_counts,
                "last_fallback": last_run.fallback_mode if last_run else None,
            },
            resource_conflicts=resource_conflicts,
            recommended_actions=recommended_actions,
            last_verified_at=routine.last_verified_at.isoformat() if routine.last_verified_at else None,
        )

    def get_runtime_center_overview(self, *, limit: int = 5) -> dict[str, Any]:
        all_routines = self._routine_repository.list_routines(limit=None)
        visible_routines = self._routine_repository.list_routines(limit=limit)
        recent_runs = self._routine_run_repository.list_runs(limit=50)
        latest_runs_by_routine: dict[str, RoutineRunRecord] = {}
        for run in recent_runs:
            latest_runs_by_routine.setdefault(run.routine_id, run)
        terminal_runs = [run for run in recent_runs if run.status in {"completed", "failed", "fallback", "blocked"}]
        success_count = sum(1 for run in terminal_runs if run.status == "completed")
        entries = [
            {
                "id": routine.id,
                "title": routine.name,
                "kind": "routine",
                "status": routine.status,
                "summary": routine.summary,
                "updated_at": routine.updated_at,
                "route": f"/api/routines/{routine.id}",
                "actions": {
                    "diagnosis": f"/api/routines/{routine.id}/diagnosis",
                },
                "meta": {
                    "engine_kind": routine.engine_kind,
                    "trigger_kind": routine.trigger_kind,
                    "success_rate": routine.success_rate,
                    "last_verified_at": routine.last_verified_at.isoformat() if routine.last_verified_at else None,
                    "verification_status": self._resolve_run_verification_summary(
                        routine=routine,
                        run=latest_runs_by_routine.get(routine.id),
                    ).get("chain_status"),
                },
            }
            for routine in visible_routines
        ]
        return {
            "total": len(all_routines),
            "active": sum(1 for routine in all_routines if routine.status == "active"),
            "degraded": sum(1 for routine in all_routines if routine.status == "degraded"),
            "recent_success_rate": round(success_count / len(terminal_runs), 3) if terminal_runs else 0.0,
            "last_verified_at": next(
                (
                    routine.last_verified_at.isoformat()
                    for routine in sorted(
                        all_routines,
                        key=lambda item: item.last_verified_at or datetime.min.replace(tzinfo=timezone.utc),
                        reverse=True,
                    )
                    if routine.last_verified_at is not None
                ),
                None,
            ),
            "last_failure_class": next((run.failure_class for run in recent_runs if run.failure_class), None),
            "last_fallback": next((run.fallback_mode for run in recent_runs if run.fallback_mode), None),
            "resource_conflicts": sum(1 for run in recent_runs if run.failure_class == "lock-conflict"),
            "entries": entries,
        }

    def _resolve_run_verification_summary(
        self,
        *,
        routine: ExecutionRoutineRecord,
        run: RoutineRunRecord | None,
    ) -> dict[str, Any]:
        expected_anchor_count = max(
            len(list(routine.action_contract or [])),
            len(list(routine.evidence_expectations or [])),
        )
        summary = dict((run.metadata or {}).get("verification_summary") or {}) if run else {}
        if summary:
            if "expected_anchor_count" not in summary:
                summary["expected_anchor_count"] = expected_anchor_count
            if "anchor_count" not in summary:
                summary["anchor_count"] = len(list(summary.get("evidence_anchors") or []))
            return summary
        if run is None:
            return {
                "chain_status": "unknown",
                "total_steps": len(list(routine.action_contract or [])),
                "observed_steps": 0,
                "verified_steps": 0,
                "failed_steps": 0,
                "total_checks": 0,
                "evidence_anchors": [],
                "anchor_count": 0,
                "expected_anchor_count": expected_anchor_count,
            }
        inferred_status = "verified" if run.status == "completed" else "failed"
        anchor_count = len(list(run.evidence_ids or []))
        return {
            "chain_status": inferred_status,
            "total_steps": len(list(routine.action_contract or [])),
            "observed_steps": anchor_count,
            "verified_steps": anchor_count if inferred_status == "verified" else 0,
            "failed_steps": 0 if inferred_status == "verified" else 1,
            "total_checks": 0,
            "evidence_anchors": [],
            "anchor_count": anchor_count,
            "expected_anchor_count": expected_anchor_count,
        }

    def _build_verification_summary(
        self,
        *,
        routine: ExecutionRoutineRecord,
        verification_chain: list[dict[str, Any]],
        status: str,
        failure_class: str | None = None,
    ) -> dict[str, Any]:
        total_steps = len(list(routine.action_contract or []))
        verified_steps = sum(1 for entry in verification_chain if bool(entry.get("verified", True)))
        observed_steps = len(verification_chain)
        failed_steps = max(observed_steps - verified_steps, 0)
        total_checks = sum(int(entry.get("check_count") or 0) for entry in verification_chain)
        return {
            "chain_status": status,
            "total_steps": total_steps,
            "observed_steps": observed_steps,
            "verified_steps": verified_steps,
            "failed_steps": failed_steps,
            "total_checks": total_checks,
            "failure_class": failure_class,
            "expected_anchor_count": max(
                total_steps,
                len(list(routine.evidence_expectations or [])),
            ),
            "anchor_count": len(verification_chain),
            "evidence_anchors": [dict(entry) for entry in verification_chain],
        }

    async def replay_routine(
        self,
        routine_id: str,
        payload: RoutineReplayRequest | None = None,
    ) -> RoutineReplayResponse:
        request_payload = payload or RoutineReplayRequest()
        routine = self._routine_repository.get_routine(routine_id)
        if routine is None:
            raise KeyError(f"Routine '{routine_id}' not found")
        run = RoutineRunRecord(
            routine_id=routine.id,
            source_type=request_payload.source_type,
            source_ref=request_payload.source_ref,
            status="running",
            input_payload=dict(request_payload.input_payload or {}),
            owner_agent_id=request_payload.owner_agent_id or routine.owner_agent_id,
            owner_scope=request_payload.owner_scope or routine.owner_scope,
            session_id=request_payload.session_id,
            metadata={
                **dict(request_payload.metadata or {}),
                "replay_request_context": dict(request_payload.request_context or {}),
            },
        )
        run = self._routine_run_repository.upsert_run(run)
        attempt = 0
        force_recover_session = False
        while True:
            attempt += 1
            try:
                if routine.engine_kind == "browser":
                    outcome = await self._replay_browser_routine(
                        routine=routine,
                        run=run,
                        request=request_payload,
                        force_recover_session=force_recover_session,
                    )
                elif routine.engine_kind == "desktop":
                    outcome = await self._replay_desktop_routine(
                        routine=routine,
                        run=run,
                        request=request_payload,
                    )
                else:
                    raise _RoutineFailure(
                        "executor-unavailable",
                        f"Routine engine '{routine.engine_kind}' is not supported",
                    )
            except _RoutineFailure as exc:
                replay_context = dict(run.metadata.get("replay_request_context") or {})
                fallback_context = dict(routine.metadata.get("fallback_request_context") or {})
                fallback_mode = self._resolve_fallback_mode(
                    failure_class=exc.failure_class,
                    routine=routine,
                    run=run,
                )
                missing_fallback_context: list[str] = []
                failure_summary = exc.summary
                if (
                    fallback_mode == "hard-fail"
                    and exc.failure_class in {"page-drift", "precondition-miss"}
                ):
                    missing_fallback_context = self._missing_replan_context(
                        request_context=replay_context,
                        fallback_context=fallback_context,
                    )
                    if missing_fallback_context:
                        failure_summary = (
                            f"{exc.summary} Missing fallback context: "
                            f"{', '.join(missing_fallback_context)}"
                        )
                if fallback_mode == "retry-same-session" and attempt < 2:
                    continue
                if fallback_mode == "reattach-or-recover-session" and attempt < 2:
                    force_recover_session = True
                    continue
                fallback_task_id: str | None = None
                final_status = exc.run_status
                if fallback_mode == "return-to-llm-replan":
                    fallback_task_id = self._dispatch_kernel_fallback(
                        routine=routine,
                        run=run,
                        failure_class=exc.failure_class,
                        summary=failure_summary,
                    )
                    final_status = "fallback" if fallback_task_id is not None else "failed"
                    if fallback_task_id is None:
                        fallback_mode = "hard-fail"
                elif fallback_mode == "pause-for-confirm":
                    final_status = "blocked"
                else:
                    final_status = "failed"
                run = self._routine_run_repository.upsert_run(
                    run.model_copy(
                        update={
                            "status": final_status,
                            "failure_class": exc.failure_class,
                            "fallback_mode": fallback_mode,
                            "fallback_task_id": fallback_task_id,
                            "output_summary": failure_summary,
                            "environment_id": exc.environment_id or run.environment_id,
                            "session_id": exc.session_id or run.session_id,
                            "lease_ref": exc.lease_ref or run.lease_ref,
                            "evidence_ids": list(dict.fromkeys([*run.evidence_ids, *exc.evidence_ids])),
                            "metadata": {
                                **dict(run.metadata or {}),
                                **dict(exc.metadata or {}),
                                **(
                                    {"missing_fallback_context": missing_fallback_context}
                                    if missing_fallback_context
                                    else {}
                                ),
                            },
                            "completed_at": _utc_now(),
                            "updated_at": _utc_now(),
                        },
                    ),
                )
                self._record_run_learning_outcome(run=run, routine=routine)
                self._retain_run_memory(run=run, routine=routine)
                routine = self._refresh_routine_health(routine=routine, latest_run=run)
                diagnosis = self.get_diagnosis(routine.id)
                return RoutineReplayResponse(
                    run=run,
                    diagnosis=diagnosis,
                    routes={
                        "run": f"/api/routines/runs/{run.id}",
                        "routine": f"/api/routines/{routine.id}",
                        "diagnosis": f"/api/routines/{routine.id}/diagnosis",
                    },
                )
            else:
                run = self._routine_run_repository.upsert_run(
                    run.model_copy(
                        update={
                            "status": "completed",
                            "deterministic_result": str(outcome.get("deterministic_result") or "replay-complete"),
                            "output_summary": _string(outcome.get("output_summary")),
                            "environment_id": _string(outcome.get("environment_id")),
                            "session_id": _string(outcome.get("session_id")),
                            "lease_ref": _string(outcome.get("lease_ref")),
                            "evidence_ids": list(outcome.get("evidence_ids") or []),
                            "metadata": {**dict(run.metadata or {}), **dict(outcome.get("metadata") or {})},
                            "completed_at": _utc_now(),
                            "updated_at": _utc_now(),
                        },
                    ),
                )
                self._record_run_learning_outcome(run=run, routine=routine)
                self._retain_run_memory(run=run, routine=routine)
                routine = self._refresh_routine_health(routine=routine, latest_run=run)
                diagnosis = self.get_diagnosis(routine.id)
                return RoutineReplayResponse(
                    run=run,
                    diagnosis=diagnosis,
                    routes={
                        "run": f"/api/routines/runs/{run.id}",
                        "routine": f"/api/routines/{routine.id}",
                        "diagnosis": f"/api/routines/{routine.id}/diagnosis",
                    },
                )

    def _retain_run_memory(self, *, run: RoutineRunRecord, routine: ExecutionRoutineRecord) -> None:
        retain = getattr(self._memory_retain_service, "retain_routine_run", None)
        if not callable(retain):
            return
        try:
            retain(run, routine=routine)
        except Exception:
            return

    def _record_run_learning_outcome(
        self,
        *,
        run: RoutineRunRecord,
        routine: ExecutionRoutineRecord,
    ) -> None:
        owner_agent_id = _string(run.owner_agent_id) or _string(routine.owner_agent_id)
        if owner_agent_id is None:
            return
        if (
            owner_agent_id != MAIN_BRAIN_DECISION_ACTOR
            and not is_execution_core_agent_id(owner_agent_id)
        ):
            return
        recorder = getattr(self._learning_service, "record_agent_outcome", None)
        if not callable(recorder):
            return
        context = self._resolve_learning_context(routine=routine, run=run)
        description = (
            _string(run.output_summary)
            or f"Routine '{routine.name}' finished with status {run.status}."
        )
        try:
            recorder(
                agent_id=owner_agent_id,
                title=routine.name,
                status=run.status,
                change_type=_routine_change_type(run.status),
                description=description,
                capability_ref=_string(routine.source_capability_id) or "system:replay_routine",
                task_id=run.id,
                source_evidence_id=run.evidence_ids[0] if run.evidence_ids else None,
                risk_level=routine.risk_baseline,
                source_agent_id=context["source_agent_id"],
                industry_instance_id=context["industry_instance_id"],
                industry_role_id=context["industry_role_id"],
                role_name=context["role_name"],
                owner_scope=_string(run.owner_scope) or _string(routine.owner_scope),
                error_summary=run.output_summary if run.status != "completed" else None,
                metadata={
                    "routine_id": routine.id,
                    "routine_key": routine.routine_key,
                    "engine_kind": routine.engine_kind,
                    "trigger_kind": routine.trigger_kind,
                    "failure_class": run.failure_class,
                    "fallback_mode": run.fallback_mode,
                    "fallback_task_id": run.fallback_task_id,
                    "decision_request_id": run.decision_request_id,
                    "environment_id": run.environment_id,
                    "session_id": run.session_id,
                    "lease_ref": run.lease_ref,
                },
            )
        except Exception:
            return

    def _resolve_learning_context(
        self,
        *,
        routine: ExecutionRoutineRecord,
        run: RoutineRunRecord,
    ) -> dict[str, str | None]:
        run_metadata = dict(run.metadata or {})
        replay_context = dict(run_metadata.get("replay_request_context") or {})
        fallback_context = dict(routine.metadata.get("fallback_request_context") or {})
        owner_agent_id = _string(run.owner_agent_id) or _string(routine.owner_agent_id)
        role_name = None
        if is_execution_core_agent_id(owner_agent_id):
            role_name = "execution-core"
        elif owner_agent_id == MAIN_BRAIN_DECISION_ACTOR:
            role_name = "main-brain"
        return {
            "source_agent_id": _string(
                replay_context.get("source_agent_id")
                or run_metadata.get("source_agent_id")
                or fallback_context.get("source_agent_id")
            )
            or (
                MAIN_BRAIN_DECISION_ACTOR
                if is_execution_core_agent_id(owner_agent_id)
                else None
            ),
            "industry_instance_id": _string(
                replay_context.get("industry_instance_id")
                or run_metadata.get("industry_instance_id")
                or fallback_context.get("industry_instance_id")
                or routine.metadata.get("industry_instance_id")
            ),
            "industry_role_id": _string(
                replay_context.get("industry_role_id")
                or run_metadata.get("industry_role_id")
                or fallback_context.get("industry_role_id")
                or routine.metadata.get("industry_role_id")
            ),
            "role_name": role_name,
        }

    async def _replay_browser_routine(
        self,
        *,
        routine: ExecutionRoutineRecord,
        run: RoutineRunRecord,
        request: RoutineReplayRequest,
        force_recover_session: bool = False,
    ) -> dict[str, Any]:
        browser_runtime = self._get_browser_runtime_service()
        if browser_runtime is None:
            raise _RoutineFailure("executor-unavailable", "Browser runtime service is not available")
        session_requirements = dict(routine.session_requirements or {})
        resolved_session_id = (
            request.session_id
            or _string(request.input_payload.get("session_id"))
            or _string(session_requirements.get("session_id"))
            or f"routine-{routine.id[:12]}"
        )
        if force_recover_session and resolved_session_id:
            try:
                await browser_runtime.stop_session(resolved_session_id)
            except Exception:
                pass
        start_payload = await browser_runtime.start_session(
            BrowserSessionStartOptions(
                session_id=resolved_session_id or "default",
                profile_id=_string(session_requirements.get("profile_id")),
                headed=bool(session_requirements.get("headed")) if session_requirements.get("headed") is not None else None,
                entry_url=_string(session_requirements.get("entry_url")),
                reuse_running_session=False if force_recover_session else session_requirements.get("reuse_running_session"),
                persist_login_state=session_requirements.get("persist_login_state"),
            ),
        )
        result_payload = start_payload.get("result") if isinstance(start_payload, dict) else {}
        if isinstance(result_payload, dict) and result_payload.get("ok") is False:
            raise _RoutineFailure(
                "executor-unavailable",
                str(result_payload.get("error") or "Browser session could not be started"),
            )
        session_lease = self._environment_service.acquire_session_lease(
            channel="browser-local",
            session_id=resolved_session_id or "default",
            user_id=_string(session_requirements.get("user_id")),
            owner=f"routine:{run.id}",
            handle={"browser_session_id": resolved_session_id, "routine_id": routine.id},
            metadata={"routine_id": routine.id, "routine_run_id": run.id, "engine_kind": routine.engine_kind},
        )
        lock_leases: list[Any] = []
        evidence_ids: list[str] = []
        verification_chain: list[dict[str, Any]] = []
        environment_ref = f"session:browser-local:{resolved_session_id}"
        try:
            lock_leases = self._acquire_resource_locks(
                routine=routine,
                run=run,
                session_id=resolved_session_id or "default",
                input_payload=request.input_payload,
            )
            output_lines: list[str] = []
            for index, contract in enumerate(list(routine.action_contract or []), start=1):
                action = str(contract.get("action") or "").strip().lower()
                if contract.get("requires_confirmation"):
                    raise _RoutineFailure(
                        "confirmation-required",
                        f"Routine step {index} requires confirmation",
                        run_status="blocked",
                        environment_id=session_lease.environment_id,
                        session_id=resolved_session_id,
                        lease_ref=session_lease.id,
                        evidence_ids=evidence_ids,
                    )
                browser_kwargs = self._build_browser_step_kwargs(
                    action=action,
                    contract=contract,
                    session_id=resolved_session_id or "default",
                )
                with bind_browser_evidence_sink(None):
                    response = await browser_use(**browser_kwargs)
                response_payload = _tool_response_json(response)
                verification = await self._verify_browser_step(
                    action=action,
                    contract=contract,
                    browser_kwargs=browser_kwargs,
                    response_payload=response_payload,
                    session_id=resolved_session_id or "default",
                )
                result_summary = str(
                    response_payload.get("message")
                    or response_payload.get("error")
                    or response_payload.get("raw_text")
                    or f"Browser action {action} completed"
                )
                if not verification.get("verified", True):
                    detail = _string(verification.get("summary"))
                    if detail:
                        result_summary = f"{result_summary} | {detail}"
                persisted = self._append_evidence(
                    routine=routine,
                    run=run,
                    capability_ref="routine:browser-replay",
                    environment_ref=environment_ref,
                    action_summary=f"Replay browser routine step {index}: {action}",
                    result_summary=result_summary,
                    metadata={
                        "routine_id": routine.id,
                        "routine_run_id": run.id,
                        "engine_kind": "browser",
                        "step": index,
                        "action": action,
                        "page_id": browser_kwargs.get("page_id"),
                        "url": browser_kwargs.get("url"),
                        "request": browser_kwargs,
                        "response": response_payload,
                        "verification": verification,
                    },
                )
                if persisted.id is not None:
                    evidence_ids.append(persisted.id)
                verification_chain.append(
                    {
                        "step": index,
                        "action": action,
                        "page_id": browser_kwargs.get("page_id"),
                        "verified": bool(verification.get("verified", True)),
                        "check_count": len(list(verification.get("checks") or [])),
                        "verification_kinds": _verification_kinds(verification),
                        "summary": _string(verification.get("summary")) or result_summary,
                        "evidence_id": persisted.id,
                        "artifact_refs": list(getattr(persisted, "artifact_refs", []) or []),
                        "artifact_path": _string(browser_kwargs.get("path")),
                    },
                )
                if not bool(response_payload.get("ok")):
                    raise _RoutineFailure(
                        self._classify_browser_failure(action=action, response_payload=response_payload),
                        result_summary,
                        metadata={
                            "response": response_payload,
                            "verification_summary": self._build_verification_summary(
                                routine=routine,
                                verification_chain=verification_chain,
                                status="failed",
                                failure_class=self._classify_browser_failure(
                                    action=action,
                                    response_payload=response_payload,
                                ),
                            ),
                        },
                        environment_id=session_lease.environment_id,
                        session_id=resolved_session_id,
                        lease_ref=session_lease.id,
                        evidence_ids=evidence_ids,
                    )
                if not verification.get("verified", True):
                    raise _RoutineFailure(
                        str(verification.get("failure_class") or "page-drift"),
                        result_summary,
                        metadata={
                            "response": response_payload,
                            "verification": verification,
                            "verification_summary": self._build_verification_summary(
                                routine=routine,
                                verification_chain=verification_chain,
                                status="failed",
                                failure_class=str(verification.get("failure_class") or "page-drift"),
                            ),
                        },
                        environment_id=session_lease.environment_id,
                        session_id=resolved_session_id,
                        lease_ref=session_lease.id,
                        evidence_ids=evidence_ids,
                    )
                output_lines.append(result_summary)
            return {
                "output_summary": " | ".join(output_lines[-3:]) if output_lines else "Routine replay completed",
                "environment_id": session_lease.environment_id,
                "session_id": resolved_session_id,
                "lease_ref": session_lease.id,
                "evidence_ids": evidence_ids,
                "deterministic_result": "replay-complete",
                "metadata": {
                    "start_payload": start_payload,
                    "verification_summary": self._build_verification_summary(
                        routine=routine,
                        verification_chain=verification_chain,
                        status="verified",
                    ),
                },
            }
        except _RoutineFailure:
            raise
        except Exception as exc:
            raise _RoutineFailure(
                "execution-error",
                str(exc) or "Browser routine replay failed",
                metadata={
                    "verification_summary": self._build_verification_summary(
                        routine=routine,
                        verification_chain=verification_chain,
                        status="failed",
                        failure_class="execution-error",
                    ),
                },
                environment_id=session_lease.environment_id,
                session_id=resolved_session_id,
                lease_ref=session_lease.id,
                evidence_ids=evidence_ids,
            ) from exc
        finally:
            self._release_resource_locks(lock_leases)
            self._environment_service.release_session_lease(
                session_lease.id,
                lease_token=session_lease.lease_token,
                reason="routine browser replay completed",
            )

    async def _replay_desktop_routine(
        self,
        *,
        routine: ExecutionRoutineRecord,
        run: RoutineRunRecord,
        request: RoutineReplayRequest,
    ) -> dict[str, Any]:
        if sys.platform != "win32":
            raise _RoutineFailure(
                "host-unsupported",
                "Desktop routine replay is only available on Windows hosts",
            )
        session_id = request.session_id or f"desktop-{routine.id[:12]}"
        session_lease = self._environment_service.acquire_session_lease(
            channel="desktop",
            session_id=session_id,
            owner=f"routine:{run.id}",
            metadata={"routine_id": routine.id, "routine_run_id": run.id, "engine_kind": "desktop"},
        )
        host = WindowsDesktopHost()
        evidence_ids: list[str] = []
        verification_chain: list[dict[str, Any]] = []
        execution_path_chain: list[dict[str, Any]] = []
        lock_leases: list[Any] = []
        try:
            lock_leases = self._acquire_desktop_locks(routine=routine, run=run)
            output_lines: list[str] = []
            for index, contract in enumerate(list(routine.action_contract or []), start=1):
                action = str(contract.get("action") or "").strip()
                result = await self._execute_desktop_action_with_environment_path(
                    host=host,
                    action=action,
                    contract=contract,
                    routine=routine,
                    run=run,
                    session_mount_id=session_lease.id,
                )
                verification = self._verify_desktop_step(
                    action=action,
                    contract=contract,
                    result=result,
                )
                execution_path = self._mapping(result.get("execution_path"))
                result_summary = str(
                    result.get("message")
                    or result.get("summary")
                    or result.get("window", {}).get("title")
                    or f"Desktop action {action} completed"
                )
                if not verification.get("verified", True):
                    detail = _string(verification.get("summary"))
                    if detail:
                        result_summary = f"{result_summary} | {detail}"
                persisted = self._append_evidence(
                    routine=routine,
                    run=run,
                    capability_ref="routine:desktop-replay",
                    environment_ref=f"session:desktop:{session_id}",
                    action_summary=f"Replay desktop routine step {index}: {action}",
                    result_summary=result_summary,
                    metadata={
                        "routine_id": routine.id,
                        "routine_run_id": run.id,
                        "engine_kind": "desktop",
                        "step": index,
                        "action": action,
                        "result": result,
                        "verification": verification,
                    },
                )
                if persisted.id is not None:
                    evidence_ids.append(persisted.id)
                execution_path_chain.append(
                    {
                        "step": index,
                        "action": action,
                        **execution_path,
                    },
                )
                verification_chain.append(
                    {
                        "step": index,
                        "action": action,
                        "verified": bool(verification.get("verified", True)),
                        "check_count": len(list(verification.get("checks") or [])),
                        "verification_kinds": _verification_kinds(verification),
                        "summary": _string(verification.get("summary")) or result_summary,
                        "evidence_id": persisted.id,
                        "artifact_refs": list(getattr(persisted, "artifact_refs", []) or []),
                        "artifact_path": _string(contract.get("path")),
                    },
                )
                if not verification.get("verified", True):
                    failure_class = str(verification.get("failure_class") or "execution-error")
                    raise _RoutineFailure(
                        failure_class,
                        result_summary,
                        metadata={
                            "result": result,
                            "verification": verification,
                            "verification_summary": self._build_verification_summary(
                                routine=routine,
                                verification_chain=verification_chain,
                                status="failed",
                                failure_class=failure_class,
                            ),
                        },
                        environment_id=session_lease.environment_id,
                        session_id=session_id,
                        lease_ref=session_lease.id,
                        evidence_ids=evidence_ids,
                    )
                output_lines.append(result_summary)
            return {
                "output_summary": " | ".join(output_lines[-3:]) if output_lines else "Desktop routine replay completed",
                "environment_id": session_lease.environment_id,
                "session_id": session_id,
                "lease_ref": session_lease.id,
                "evidence_ids": evidence_ids,
                "deterministic_result": "desktop-replay-complete",
                "metadata": {
                    "lock_scope": self._derive_desktop_lock_scope(routine),
                    "execution_paths": execution_path_chain,
                    "verification_summary": self._build_verification_summary(
                        routine=routine,
                        verification_chain=verification_chain,
                        status="verified",
                    ),
                },
            }
        except DesktopAutomationError as exc:
            failure_class = self._classify_desktop_exception(exc)
            raise _RoutineFailure(
                failure_class,
                str(exc),
                metadata={
                    "verification_summary": self._build_verification_summary(
                        routine=routine,
                        verification_chain=verification_chain,
                        status="failed",
                        failure_class=failure_class,
                    ),
                },
                environment_id=session_lease.environment_id,
                session_id=session_id,
                lease_ref=session_lease.id,
                evidence_ids=evidence_ids,
            ) from exc
        finally:
            self._release_resource_locks(lock_leases)
            self._environment_service.release_session_lease(
                session_lease.id,
                lease_token=session_lease.lease_token,
                reason="routine desktop replay completed",
            )

    def _build_browser_step_kwargs(
        self,
        *,
        action: str,
        contract: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        if not action:
            raise _RoutineFailure("precondition-miss", "Routine step is missing an action")
        if action not in SUPPORTED_BROWSER_ROUTINE_ACTIONS:
            supported = ", ".join(SUPPORTED_BROWSER_ROUTINE_ACTIONS)
            raise _RoutineFailure(
                "executor-unavailable",
                f"Browser routine action '{action}' is not supported. Expected one of: {supported}",
            )
        page_id = _string(contract.get("page_id")) or "page_1"
        payload: dict[str, Any] = {"action": action, "page_id": page_id, "session_id": session_id}
        if action in {"open", "navigate"}:
            url = _string(contract.get("url"))
            if url is None:
                raise _RoutineFailure("precondition-miss", f"Browser action '{action}' requires a url")
            payload["url"] = url
        if action == "click":
            selector = _string(contract.get("selector"))
            ref = _string(contract.get("ref"))
            if selector is None and ref is None:
                raise _RoutineFailure("precondition-miss", "Browser click action requires selector or ref")
            if selector is not None:
                payload["selector"] = selector
            if ref is not None:
                payload["ref"] = ref
            button = _string(contract.get("button"))
            if button is not None:
                payload["button"] = button
            if contract.get("double_click") is not None:
                payload["double_click"] = bool(contract.get("double_click"))
        if action == "type":
            selector = _string(contract.get("selector"))
            ref = _string(contract.get("ref"))
            if selector is None and ref is None:
                raise _RoutineFailure("precondition-miss", "Browser type action requires selector or ref")
            if selector is not None:
                payload["selector"] = selector
            if ref is not None:
                payload["ref"] = ref
            text = contract.get("text")
            if text in (None, ""):
                raise _RoutineFailure("precondition-miss", "Browser type action requires text")
            payload["text"] = text
            if contract.get("submit") is not None:
                payload["submit"] = bool(contract.get("submit"))
            if contract.get("slowly") is not None:
                payload["slowly"] = bool(contract.get("slowly"))
        if action == "wait_for":
            text = _string(contract.get("text"))
            text_gone = _string(contract.get("text_gone"))
            wait_time = contract.get("wait_time")
            if text is None and text_gone is None and wait_time in (None, "", 0, 0.0):
                raise _RoutineFailure(
                    "precondition-miss",
                    "Browser wait_for action requires text, text_gone, or wait_time",
                )
            if text is not None:
                payload["text"] = text
            if text_gone is not None:
                payload["text_gone"] = text_gone
            if wait_time not in (None, ""):
                payload["wait_time"] = wait_time
        if action == "tabs":
            tab_action = _string(contract.get("tab_action"))
            if tab_action is None:
                raise _RoutineFailure("precondition-miss", "Browser tabs action requires tab_action")
            payload["tab_action"] = tab_action
            if contract.get("index") not in (None, ""):
                payload["index"] = int(contract.get("index"))
        if action == "file_upload":
            paths = contract.get("paths")
            if paths in (None, "", []):
                raise _RoutineFailure("precondition-miss", "Browser file_upload action requires paths")
            payload["paths_json"] = json.dumps(paths)
        if action == "fill_form":
            fields = contract.get("fields")
            if fields in (None, "", []):
                raise _RoutineFailure("precondition-miss", "Browser fill_form action requires fields")
            payload["fields_json"] = json.dumps(fields)
        if action == "screenshot":
            if contract.get("path") not in (None, ""):
                payload["path"] = contract.get("path")
            if contract.get("full_page") is not None:
                payload["full_page"] = bool(contract.get("full_page"))
            selector = _string(contract.get("selector"))
            ref = _string(contract.get("ref"))
            if selector is not None:
                payload["selector"] = selector
            if ref is not None:
                payload["ref"] = ref
        if action == "pdf":
            path = _string(contract.get("path"))
            if path is None:
                raise _RoutineFailure("precondition-miss", "Browser pdf action requires path")
            payload["path"] = path
        for source_key, target_key in (
            ("text", "text"),
            ("code", "code"),
            ("key", "key"),
            ("wait", "wait"),
            ("width", "width"),
            ("height", "height"),
            ("frame_selector", "frame_selector"),
        ):
            value = contract.get(source_key)
            if value not in (None, ""):
                payload[target_key] = value
        for source_key, target_key in (
            ("fields", "fields_json"),
            ("values", "values_json"),
            ("paths", "paths_json"),
            ("modifiers", "modifiers_json"),
        ):
            value = contract.get(source_key)
            if value not in (None, ""):
                payload[target_key] = json.dumps(value)
        return payload

    async def _verify_browser_step(
        self,
        *,
        action: str,
        contract: dict[str, Any],
        browser_kwargs: dict[str, Any],
        response_payload: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        verification_entries: list[dict[str, Any]] = []
        response_verification = response_payload.get("verification")
        if isinstance(response_verification, dict) and response_verification:
            verified = bool(response_verification.get("verified", True))
            verification_entries.append(
                {
                    "kind": "tool",
                    "verified": verified,
                    "details": response_verification,
                },
            )
            if not verified:
                return {
                    "verified": False,
                    "failure_class": "page-drift",
                    "summary": "Tool-level browser verification reported an unverified state change.",
                    "checks": verification_entries,
                }

        verification_spec = contract.get("verification")
        effective_verification: dict[str, Any] = (
            dict(verification_spec) if isinstance(verification_spec, dict) else {}
        )
        target_url = _string(browser_kwargs.get("url"))
        if action in {"open", "navigate"} and target_url is not None:
            effective_verification.setdefault("url_equals", target_url)
        if action == "type":
            selector = _string(browser_kwargs.get("selector"))
            if selector is not None and "element_value_equals" not in effective_verification:
                effective_verification["element_value_equals"] = browser_kwargs.get("text")
        if action in {"screenshot", "pdf"}:
            path = _string(browser_kwargs.get("path"))
            if path is not None:
                effective_verification.setdefault("file_exists", path)
        if not effective_verification:
            return {"verified": True, "checks": verification_entries}

        page_id = _string(browser_kwargs.get("page_id")) or "page_1"
        if "url_contains" in effective_verification or "url_equals" in effective_verification:
            current_url = self._browser_verification_url(
                action=action,
                response_payload=response_payload,
            )
            url_channel = "tool-response"
            if current_url is None:
                current_url_result = await self._browser_eval(
                    session_id=session_id,
                    page_id=page_id,
                    code="window.location.href",
                )
                current_url = _string(current_url_result.get("result"))
                url_channel = "browser-evaluate"
            expected_contains = _string(effective_verification.get("url_contains"))
            expected_equals = _string(effective_verification.get("url_equals"))
            normalized_current_url = _canonical_browser_url(current_url)
            normalized_expected_equals = _canonical_browser_url(expected_equals)
            url_verified = True
            if expected_contains is not None:
                url_verified = current_url is not None and expected_contains in current_url
            if url_verified and expected_equals is not None:
                url_verified = current_url == expected_equals or (
                    normalized_current_url is not None
                    and normalized_current_url == normalized_expected_equals
                )
            verification_entries.append(
                {
                    "kind": "url",
                    "verified": url_verified,
                    "current_url": current_url,
                    "normalized_current_url": normalized_current_url,
                    "expected_contains": expected_contains,
                    "expected_equals": expected_equals,
                    "normalized_expected_equals": normalized_expected_equals,
                    "channel": url_channel,
                },
            )
            if not url_verified:
                expectation = expected_equals or expected_contains or "requested URL state"
                return {
                    "verified": False,
                    "failure_class": "page-drift",
                    "summary": f"Browser URL verification failed; expected {expectation}, got {current_url or 'none'}.",
                    "checks": verification_entries,
                }

        if "tab_count" in effective_verification:
            tabs_payload = await self._browser_tabs_list(
                session_id=session_id,
                page_id=page_id,
            )
            expected_tab_count = int(effective_verification.get("tab_count") or 0)
            actual_tab_count = int(tabs_payload.get("count") or 0)
            tabs_verified = actual_tab_count == expected_tab_count
            verification_entries.append(
                {
                    "kind": "tabs",
                    "verified": tabs_verified,
                    "expected_count": expected_tab_count,
                    "actual_count": actual_tab_count,
                    "tabs": list(tabs_payload.get("tabs") or []),
                },
            )
            if not tabs_verified:
                return {
                    "verified": False,
                    "failure_class": "page-drift",
                    "summary": f"Browser tab verification failed; expected {expected_tab_count}, got {actual_tab_count}.",
                    "checks": verification_entries,
                }

        if "text_present" in effective_verification:
            text = _string(effective_verification.get("text_present"))
            if text is not None:
                wait_payload = await self._browser_wait_for(
                    session_id=session_id,
                    page_id=page_id,
                    text=text,
                    wait_time=float(effective_verification.get("wait_time") or 1.5),
                )
                text_verified = bool(wait_payload.get("ok"))
                verification_entries.append(
                    {
                        "kind": "text_present",
                        "verified": text_verified,
                        "text": text,
                        "response": wait_payload,
                    },
                )
                if not text_verified:
                    return {
                        "verified": False,
                        "failure_class": "page-drift",
                        "summary": f"Browser text verification failed; '{text}' did not appear.",
                        "checks": verification_entries,
                    }

        if "element_value_equals" in effective_verification:
            selector = _string(browser_kwargs.get("selector"))
            expected_value = browser_kwargs.get("text")
            if selector is not None:
                element_payload = await self._browser_eval(
                    session_id=session_id,
                    page_id=page_id,
                    code=(
                        "(() => {"
                        f"const node = document.querySelector({_json_js(selector)});"
                        "if (!node) { return null; }"
                        "const value = typeof node.value === 'string' ? node.value : (node.textContent || '');"
                        "return value;"
                        "})()"
                    ),
                )
                actual_value = element_payload.get("result")
                value_verified = actual_value == expected_value
                verification_entries.append(
                    {
                        "kind": "element_value",
                        "verified": value_verified,
                        "selector": selector,
                        "expected_value": expected_value,
                        "actual_value": actual_value,
                    },
                )
                if not value_verified:
                    return {
                        "verified": False,
                        "failure_class": "page-drift",
                        "summary": (
                            f"Browser element value verification failed for {selector}; "
                            f"expected {expected_value!r}, got {actual_value!r}."
                        ),
                        "checks": verification_entries,
                    }

        for key in ("file_exists", "path_exists"):
            path = _string(effective_verification.get(key))
            if path is None:
                continue
            exists = os.path.exists(path)
            verification_entries.append(
                {
                    "kind": "path",
                    "verified": exists,
                    "path": path,
                },
            )
            if not exists:
                return {
                    "verified": False,
                    "failure_class": "execution-error",
                    "summary": f"Browser artifact verification failed; path does not exist: {path}",
                    "checks": verification_entries,
                }

        return {"verified": True, "checks": verification_entries}

    def _browser_verification_url(
        self,
        *,
        action: str,
        response_payload: dict[str, Any],
    ) -> str | None:
        verification = response_payload.get("verification")
        if isinstance(verification, dict):
            observed_after = verification.get("observed_after")
            if isinstance(observed_after, dict):
                observed_url = _string(observed_after.get("url"))
                if observed_url is not None:
                    return observed_url
        if action in {"open", "navigate"}:
            return _string(response_payload.get("url"))
        return None

    def _verify_desktop_step(
        self,
        *,
        action: str,
        contract: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        verification_entries: list[dict[str, Any]] = [
            {
                "kind": "result",
                "verified": bool(result.get("success", True)),
                "details": result,
            }
        ]
        if result.get("success") is False:
            return {
                "verified": False,
                "failure_class": "execution-error",
                "summary": str(
                    result.get("message")
                    or result.get("error")
                    or f"Desktop action {action} reported failure."
                ),
                "checks": verification_entries,
            }
        if action == "verify_window_focus":
            focus_verified = bool(result.get("is_foreground"))
            verification_entries.append(
                {
                    "kind": "window_focus",
                    "verified": focus_verified,
                    "window": result.get("window"),
                    "foreground_window": result.get("foreground_window"),
                }
            )
            if not focus_verified:
                return {
                    "verified": False,
                    "failure_class": "execution-error",
                    "summary": "Focused-window verification failed after desktop action.",
                    "checks": verification_entries,
                }
        elif action == "write_document_file":
            path = _string(result.get("path")) or _string(contract.get("path"))
            expected_content = str(contract.get("content"))
            actual_content = result.get("verified_content")
            reread_verified = bool(result.get("reopened")) and actual_content == expected_content
            verification_entries.append(
                {
                    "kind": "document_reread",
                    "verified": reread_verified,
                    "path": path,
                    "reopened": bool(result.get("reopened")),
                    "expected_content": expected_content,
                    "actual_content": actual_content,
                }
            )
            if not reread_verified:
                return {
                    "verified": False,
                    "failure_class": "execution-error",
                    "summary": "Desktop document write did not verify exact reread content after reopen.",
                    "checks": verification_entries,
                }
            if path is not None:
                path_exists = os.path.exists(path)
                verification_entries.append(
                    {
                        "kind": "path",
                        "verified": path_exists,
                        "path": path,
                    }
                )
                if not path_exists:
                    return {
                        "verified": False,
                        "failure_class": "execution-error",
                        "summary": f"Desktop document verification failed; path does not exist: {path}",
                        "checks": verification_entries,
                    }
        elif action == "edit_document_file":
            path = _string(result.get("path")) or _string(contract.get("path"))
            replace_text = str(contract.get("replace_text"))
            actual_content = _string(result.get("verified_content")) or ""
            reread_verified = (
                bool(result.get("reopened"))
                and int(result.get("replacements") or 0) > 0
                and replace_text in actual_content
            )
            verification_entries.append(
                {
                    "kind": "document_reread",
                    "verified": reread_verified,
                    "path": path,
                    "reopened": bool(result.get("reopened")),
                    "replacements": int(result.get("replacements") or 0),
                    "expected_contains": replace_text,
                    "actual_content": actual_content,
                }
            )
            if not reread_verified:
                return {
                    "verified": False,
                    "failure_class": "execution-error",
                    "summary": "Desktop document edit did not verify updated content after reopen.",
                    "checks": verification_entries,
                }
            if path is not None:
                path_exists = os.path.exists(path)
                verification_entries.append(
                    {
                        "kind": "path",
                        "verified": path_exists,
                        "path": path,
                    }
                )
                if not path_exists:
                    return {
                        "verified": False,
                        "failure_class": "execution-error",
                        "summary": f"Desktop document verification failed; path does not exist: {path}",
                        "checks": verification_entries,
                    }
        return {"verified": True, "checks": verification_entries}

    def _classify_desktop_exception(self, exc: Exception) -> str:
        message = str(exc).strip().lower()
        if "modal interruption" in message or "lost focus" in message or "focus theft" in message:
            return "modal-interruption"
        return "execution-error"

    async def _browser_eval(
        self,
        *,
        session_id: str,
        page_id: str,
        code: str,
    ) -> dict[str, Any]:
        response = await browser_use(
            action="evaluate",
            session_id=session_id,
            page_id=page_id,
            code=code,
        )
        return _tool_response_json(response)

    async def _browser_tabs_list(
        self,
        *,
        session_id: str,
        page_id: str,
    ) -> dict[str, Any]:
        response = await browser_use(
            action="tabs",
            session_id=session_id,
            page_id=page_id,
            tab_action="list",
        )
        return _tool_response_json(response)

    async def _browser_wait_for(
        self,
        *,
        session_id: str,
        page_id: str,
        text: str,
        wait_time: float,
    ) -> dict[str, Any]:
        response = await browser_use(
            action="wait_for",
            session_id=session_id,
            page_id=page_id,
            text=text,
            wait_time=wait_time,
        )
        return _tool_response_json(response)

    def _classify_browser_failure(
        self,
        *,
        action: str,
        response_payload: dict[str, Any],
    ) -> str:
        error_text = str(
            response_payload.get("error")
            or response_payload.get("message")
            or response_payload.get("raw_text")
            or ""
        ).lower()
        if "confirm" in error_text:
            return "confirmation-required"
        if "already leased" in error_text or "lock" in error_text:
            return "lock-conflict"
        if "auth" in error_text or "login" in error_text or "expired" in error_text:
            return "auth-expired"
        if "not found" in error_text and action in {"click", "screenshot", "hover", "type"}:
            return "page-drift"
        if "browser" in error_text and ("failed" in error_text or "not started" in error_text):
            return "executor-unavailable"
        if "required" in error_text:
            return "precondition-miss"
        if action in {"click", "screenshot"} and "page" in error_text:
            return "page-drift"
        return "execution-error"

    def _append_evidence(
        self,
        *,
        routine: ExecutionRoutineRecord,
        run: RoutineRunRecord,
        capability_ref: str,
        environment_ref: str | None,
        action_summary: str,
        result_summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceRecord:
        return self._evidence_ledger.append(
            EvidenceRecord(
                task_id=f"routine-run:{run.id}",
                actor_ref=run.owner_agent_id or routine.owner_agent_id or "routine-service",
                environment_ref=environment_ref,
                capability_ref=capability_ref,
                risk_level=routine.risk_baseline,
                action_summary=action_summary,
                result_summary=result_summary,
                status="recorded",
                metadata={"routine_id": routine.id, "routine_key": routine.routine_key, "routine_run_id": run.id, **dict(metadata or {})},
            ),
        )

    def _derive_lock_scope(
        self,
        *,
        routine: ExecutionRoutineRecord,
        session_id: str,
        input_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for entry in list(routine.lock_scope or []):
            if isinstance(entry, dict):
                scope = _resource_scope_entry(
                    _string(entry.get("scope_type") or entry.get("type")),
                    _string(entry.get("scope_value") or entry.get("value")),
                    reason=_string(entry.get("reason")),
                )
                if scope is not None:
                    items.append(scope)
        session_requirements = dict(routine.session_requirements or {})
        profile_id = _string(input_payload.get("profile_id")) or _string(session_requirements.get("profile_id"))
        if profile_id is not None:
            scope = _resource_scope_entry("browser-profile", profile_id, reason="browser profile")
            if scope is not None:
                items.append(scope)
        scope = _resource_scope_entry("browser-session", session_id, reason="browser session")
        if scope is not None:
            items.append(scope)
        urls = [_string(entry.get("url")) for entry in list(routine.action_contract or []) if isinstance(entry, dict)]
        entry_url = _string(session_requirements.get("entry_url"))
        if entry_url is not None:
            urls.insert(0, entry_url)
        for url in urls:
            if url is None:
                continue
            parsed = urlparse(url)
            if parsed.netloc:
                scope = _resource_scope_entry("domain-account", parsed.netloc, reason="target host")
                if scope is not None:
                    items.append(scope)
                break
        for entry in list(routine.action_contract or []):
            if not isinstance(entry, dict):
                continue
            page_id = _string(entry.get("page_id"))
            if page_id is not None:
                scope = _resource_scope_entry("page-tab", page_id, reason="page tab")
                if scope is not None:
                    items.append(scope)
            if str(entry.get("action") or "").strip().lower() == "screenshot":
                path = _string(entry.get("path"))
                if path is not None:
                    scope = _resource_scope_entry("artifact-target", path, reason="artifact target")
                    if scope is not None:
                        items.append(scope)
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for entry in items:
            key = (str(entry["scope_type"]), str(entry["scope_value"]))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped

    def _acquire_resource_locks(
        self,
        *,
        routine: ExecutionRoutineRecord,
        run: RoutineRunRecord,
        session_id: str,
        input_payload: dict[str, Any],
    ) -> list[Any]:
        lock_scope = self._derive_lock_scope(routine=routine, session_id=session_id, input_payload=input_payload)
        leases: list[Any] = []
        for scope in lock_scope:
            scope_type = str(scope["scope_type"])
            scope_value = str(scope["scope_value"])
            try:
                lease = self._environment_service.acquire_resource_slot_lease(
                    scope_type=scope_type,
                    scope_value=scope_value,
                    owner=f"routine:{run.id}",
                    metadata={"routine_id": routine.id, "routine_run_id": run.id, "reason": scope.get("reason")},
                )
            except Exception as exc:
                holder = self._environment_service.get_resource_slot_lease(scope_type=scope_type, scope_value=scope_value)
                raise _RoutineFailure(
                    "lock-conflict",
                    f"Resource slot {scope_type}:{scope_value} is already leased",
                    metadata={"resource_conflicts": [{"scope_type": scope_type, "scope_value": scope_value, "holder": holder.model_dump(mode='json') if hasattr(holder, 'model_dump') else None}], "lock_scope": lock_scope},
                ) from exc
            else:
                leases.append(lease)
        return leases

    def _release_resource_locks(self, leases: list[Any]) -> None:
        for lease in reversed(list(leases or [])):
            try:
                self._environment_service.release_resource_slot_lease(
                    lease_id=lease.id,
                    lease_token=getattr(lease, "lease_token", None),
                    reason="routine replay completed",
                )
            except Exception:
                continue

    def _derive_desktop_lock_scope(self, routine: ExecutionRoutineRecord) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for entry in list(routine.action_contract or []):
            if not isinstance(entry, dict):
                continue
            selector = entry.get("selector") or entry.get("window_selector")
            if isinstance(selector, dict):
                selector_value = (
                    _string(selector.get("handle"))
                    or _string(selector.get("title"))
                    or _string(selector.get("title_contains"))
                    or _string(selector.get("title_regex"))
                    or _string(selector.get("process_id"))
                )
                scope = _resource_scope_entry("page-tab", selector_value, reason="desktop target window")
                if scope is not None:
                    items.append(scope)
                    break
        return items

    def _acquire_desktop_locks(
        self,
        *,
        routine: ExecutionRoutineRecord,
        run: RoutineRunRecord,
    ) -> list[Any]:
        leases: list[Any] = []
        for scope in self._derive_desktop_lock_scope(routine):
            scope_type = str(scope["scope_type"])
            scope_value = str(scope["scope_value"])
            try:
                lease = self._environment_service.acquire_resource_slot_lease(
                    scope_type=scope_type,
                    scope_value=scope_value,
                    owner=f"routine:{run.id}",
                    metadata={"routine_id": routine.id, "routine_run_id": run.id, "reason": scope.get("reason")},
                )
            except Exception as exc:
                holder = self._environment_service.get_resource_slot_lease(
                    scope_type=scope_type,
                    scope_value=scope_value,
                )
                raise _RoutineFailure(
                    "lock-conflict",
                    f"Resource slot {scope_type}:{scope_value} is already leased",
                    metadata={
                        "resource_conflicts": [
                            {
                                "scope_type": scope_type,
                                "scope_value": scope_value,
                                "holder": holder.model_dump(mode="json") if hasattr(holder, "model_dump") else None,
                            },
                        ],
                    },
                ) from exc
            else:
                leases.append(lease)
        return leases

    def _execute_desktop_action(self, *, host: WindowsDesktopHost, action: str, contract: dict[str, Any]) -> dict[str, Any]:
        if action not in SUPPORTED_DESKTOP_ROUTINE_ACTIONS:
            supported = ", ".join(SUPPORTED_DESKTOP_ROUTINE_ACTIONS)
            raise _RoutineFailure(
                "executor-unavailable",
                f"Desktop routine action '{action}' is not supported. Expected one of: {supported}",
            )
        selector = contract.get("selector") or contract.get("window_selector")
        window_selector = self._window_selector_from_payload(selector)
        control_payload = contract.get("control") or contract.get("control_selector")
        control_selector = self._control_selector_from_payload(control_payload)
        if action == "list_windows":
            return host.list_windows(selector=window_selector if window_selector is not None else None)
        if action == "get_foreground_window":
            return host.get_foreground_window()
        if action == "launch_application":
            executable = _string(contract.get("executable"))
            if executable is None:
                raise _RoutineFailure("precondition-miss", "desktop launch_application requires executable")
            return host.launch_application(executable=executable, args=list(contract.get("args") or []), cwd=_string(contract.get("cwd")))
        if action == "wait_for_window":
            if window_selector is None:
                raise _RoutineFailure("precondition-miss", "desktop wait_for_window requires selector")
            return host.wait_for_window(
                selector=window_selector,
                timeout_seconds=float(contract.get("timeout_seconds") or 10.0),
                poll_interval_seconds=float(contract.get("poll_interval_seconds") or 0.25),
                include_hidden=bool(contract.get("include_hidden", False)),
            )
        if action == "focus_window":
            if window_selector is None:
                raise _RoutineFailure("precondition-miss", "desktop focus_window requires selector")
            return host.focus_window(selector=window_selector)
        if action == "verify_window_focus":
            if window_selector is None:
                raise _RoutineFailure("precondition-miss", "desktop verify_window_focus requires selector")
            return host.verify_window_focus(selector=window_selector)
        if action == "list_controls":
            if window_selector is None:
                raise _RoutineFailure("precondition-miss", "desktop list_controls requires selector")
            return host.list_controls(
                selector=window_selector,
                control_selector=control_selector,
                include_descendants=bool(contract.get("include_descendants", True)),
                max_depth=int(contract.get("max_depth") or 4),
                limit=int(contract.get("limit") or 100),
            )
        if action == "click":
            return host.click(
                x=contract.get("x"),
                y=contract.get("y"),
                selector=window_selector,
                relative_to_window=bool(contract.get("relative_to_window", False)),
                click_count=int(contract.get("click_count") or 1),
                button=str(contract.get("button") or "left"),
                focus_target=bool(contract.get("focus_target", True)),
            )
        if action == "type_text":
            text = _string(contract.get("text"))
            if text is None:
                raise _RoutineFailure("precondition-miss", "desktop type_text requires text")
            return host.type_text(text=text, selector=window_selector, focus_target=bool(contract.get("focus_target", True)))
        if action == "press_keys":
            keys = contract.get("keys")
            if keys in (None, "", []):
                raise _RoutineFailure("precondition-miss", "desktop press_keys requires keys")
            return host.press_keys(keys=keys, selector=window_selector, focus_target=bool(contract.get("focus_target", True)))
        if action == "set_control_text":
            text = _string(contract.get("text"))
            if window_selector is None:
                raise _RoutineFailure("precondition-miss", "desktop set_control_text requires selector")
            if control_selector is None:
                raise _RoutineFailure("precondition-miss", "desktop set_control_text requires control_selector")
            if text is None:
                raise _RoutineFailure("precondition-miss", "desktop set_control_text requires text")
            return host.set_control_text(
                selector=window_selector,
                control_selector=control_selector,
                text=text,
                append=bool(contract.get("append", False)),
                focus_target=bool(contract.get("focus_target", True)),
            )
        if action == "invoke_control":
            if window_selector is None:
                raise _RoutineFailure("precondition-miss", "desktop invoke_control requires selector")
            if control_selector is None:
                raise _RoutineFailure("precondition-miss", "desktop invoke_control requires control_selector")
            return host.invoke_control(
                selector=window_selector,
                control_selector=control_selector,
                action=_string(contract.get("control_action")) or _string(contract.get("action_name")) or "invoke",
                focus_target=bool(contract.get("focus_target", True)),
            )
        if action == "invoke_dialog_action":
            dialog_action = _string(contract.get("dialog_action")) or _string(contract.get("semantic_action"))
            if window_selector is None:
                raise _RoutineFailure("precondition-miss", "desktop invoke_dialog_action requires selector")
            if dialog_action is None:
                raise _RoutineFailure("precondition-miss", "desktop invoke_dialog_action requires dialog_action")
            return host.invoke_dialog_action(
                selector=window_selector,
                action=dialog_action,
                control_selector=control_selector,
                focus_target=bool(contract.get("focus_target", True)),
            )
        if action == "close_window":
            if window_selector is None:
                raise _RoutineFailure("precondition-miss", "desktop close_window requires selector")
            return host.close_window(selector=window_selector)
        if action == "write_document_file":
            path = _string(contract.get("path"))
            content = contract.get("content")
            if path is None:
                raise _RoutineFailure("precondition-miss", "desktop write_document_file requires path")
            if content is None:
                raise _RoutineFailure("precondition-miss", "desktop write_document_file requires content")
            return host.write_document_file(
                path=path,
                content=str(content),
                encoding=_string(contract.get("encoding")) or "utf-8",
                create_parent_dirs=bool(contract.get("create_parent_dirs", True)),
            )
        if action == "edit_document_file":
            path = _string(contract.get("path"))
            find_text = _string(contract.get("find_text"))
            replace_text = contract.get("replace_text")
            if path is None:
                raise _RoutineFailure("precondition-miss", "desktop edit_document_file requires path")
            if find_text is None:
                raise _RoutineFailure("precondition-miss", "desktop edit_document_file requires find_text")
            if replace_text is None:
                raise _RoutineFailure("precondition-miss", "desktop edit_document_file requires replace_text")
            return host.edit_document_file(
                path=path,
                find_text=find_text,
                replace_text=str(replace_text),
                encoding=_string(contract.get("encoding")) or "utf-8",
            )
        raise _RoutineFailure("executor-unavailable", f"Desktop routine action '{action}' is not supported")

    async def _execute_desktop_action_with_environment_path(
        self,
        *,
        host: WindowsDesktopHost,
        action: str,
        contract: dict[str, Any],
        routine: ExecutionRoutineRecord,
        run: RoutineRunRecord,
        session_mount_id: str,
    ) -> dict[str, Any]:
        is_document_action = action in {"write_document_file", "edit_document_file"}
        document_family = self._desktop_document_family(contract) if is_document_action else None
        host_executor = _DesktopHostExecutorAdapter(
            host=host,
            execute_action=lambda **_kwargs: self._execute_desktop_action(
                host=host,
                action=action,
                contract=contract,
            ),
        )
        if is_document_action:
            executor = getattr(self._environment_service, "execute_document_action", None)
            if callable(executor):
                return await self._execute_environment_desktop_action(
                    executor=executor,
                    action=action,
                    contract=contract,
                    routine=routine,
                    run=run,
                    session_mount_id=session_mount_id,
                    host_executor=host_executor,
                    document_family=document_family,
                )
        else:
            executor = getattr(self._environment_service, "execute_windows_app_action", None)
            if callable(executor):
                return await self._execute_environment_desktop_action(
                    executor=executor,
                    action=action,
                    contract=contract,
                    routine=routine,
                    run=run,
                    session_mount_id=session_mount_id,
                    host_executor=host_executor,
                    document_family=None,
                )
        execution_path = self._desktop_execution_path_ui_fallback(
            self._resolve_desktop_execution_path(
                action=action,
                contract=contract,
                session_mount_id=session_mount_id,
            ),
            reason="EnvironmentService executable surface control is not available.",
        )
        result = self._execute_desktop_action(host=host, action=action, contract=contract)
        return self._desktop_result_with_execution_path(
            result=result,
            execution_path=execution_path,
        )

    async def _execute_environment_desktop_action(
        self,
        *,
        executor: object,
        action: str,
        contract: dict[str, Any],
        routine: ExecutionRoutineRecord,
        run: RoutineRunRecord,
        session_mount_id: str,
        host_executor: object,
        document_family: str | None,
    ) -> dict[str, Any]:
        try:
            executor_kwargs = {
                "session_mount_id": session_mount_id,
                "action": action,
                "contract": dict(contract),
                "host_executor": host_executor,
            }
            if document_family is not None:
                executor_kwargs["document_family"] = document_family
            result = executor(**executor_kwargs)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            failing_execution_path = self._resolve_desktop_execution_path(
                action=action,
                contract=contract,
                session_mount_id=session_mount_id,
            )
            summary = _string(exc) or exc.__class__.__name__
            failure_class = (
                self._classify_desktop_exception(exc)
                if isinstance(exc, DesktopAutomationError)
                else "execution-error"
            )
            failure_metadata: dict[str, Any] = {
                "execution_path": failing_execution_path,
            }
            if isinstance(exc, DesktopAutomationError):
                failure_metadata["verification_summary"] = self._build_verification_summary(
                    routine=routine,
                    verification_chain=[],
                    status="failed",
                    failure_class=failure_class,
                )
            raise _RoutineFailure(
                failure_class,
                summary,
                metadata=failure_metadata,
            ) from exc
        if not isinstance(result, dict):
            result = {"value": result}
        execution_path = self._mapping(result.get("execution_path"))
        if execution_path:
            return result
        return self._desktop_result_with_execution_path(
            result=result,
            execution_path=self._resolve_desktop_execution_path(
                action=action,
                contract=contract,
                session_mount_id=session_mount_id,
            ),
        )

    def _resolve_desktop_execution_path(
        self,
        *,
        action: str,
        contract: dict[str, Any],
        session_mount_id: str,
    ) -> dict[str, Any]:
        is_document_action = action in {"write_document_file", "edit_document_file"}
        document_family = self._desktop_document_family(contract) if is_document_action else None
        document_snapshot = (
            self._desktop_document_bridge_snapshot(
                session_mount_id=session_mount_id,
                document_family=document_family,
            )
            if is_document_action
            else {}
        )
        app_snapshot = self._desktop_windows_app_snapshot(session_mount_id=session_mount_id)
        document_bridge = self._mapping(document_snapshot.get("document_bridge"))
        app_adapters = self._mapping(app_snapshot.get("windows_app_adapters"))
        preferred_execution_path = self._first_string(
            document_snapshot.get("preferred_execution_path"),
            app_snapshot.get("preferred_execution_path"),
            "cooperative-native-first",
        )
        ui_fallback_mode = self._first_string(
            document_snapshot.get("ui_fallback_mode"),
            app_snapshot.get("ui_fallback_mode"),
            "ui-fallback-last",
        )
        current_gap_or_blocker = self._first_string(
            document_snapshot.get("adapter_gap_or_blocker"),
            app_snapshot.get("adapter_gap_or_blocker"),
        )
        resolution = self._environment_service.resolve_execution_path(
            surface_kind="document" if is_document_action else "desktop-app",
            cooperative_available=bool(document_bridge.get("available")),
            cooperative_refs=[document_bridge.get("bridge_ref")],
            cooperative_blocker=current_gap_or_blocker,
            semantic_available=bool(app_adapters.get("available"))
            and self._first_string(app_adapters.get("control_channel")) is not None,
            semantic_channel=self._first_string(
                app_adapters.get("control_channel"),
                "semantic-operator",
            ) or "semantic-operator",
            semantic_ref=self._first_string(
                app_adapters.get("control_channel"),
            ),
            ui_available=True,
            ui_ref=f"session:desktop:{session_mount_id}",
            preferred_execution_path=preferred_execution_path or "cooperative-native-first",
            ui_fallback_mode=ui_fallback_mode or "ui-fallback-last",
        )
        execution_path = self._desktop_execution_path_metadata(resolution)
        if document_family is not None:
            execution_path["document_family"] = document_family
        return execution_path

    def _desktop_document_bridge_snapshot(
        self,
        *,
        session_mount_id: str,
        document_family: str | None,
    ) -> dict[str, Any]:
        getter = getattr(self._environment_service, "document_bridge_snapshot", None)
        if not callable(getter):
            return {}
        try:
            snapshot = getter(
                session_mount_id=session_mount_id,
                document_family=document_family,
            )
        except Exception:
            return {}
        return snapshot if isinstance(snapshot, dict) else {}

    def _desktop_windows_app_snapshot(
        self,
        *,
        session_mount_id: str,
    ) -> dict[str, Any]:
        getter = getattr(self._environment_service, "windows_app_adapter_snapshot", None)
        if not callable(getter):
            return {}
        try:
            snapshot = getter(session_mount_id=session_mount_id)
        except Exception:
            return {}
        return snapshot if isinstance(snapshot, dict) else {}

    def _desktop_result_with_execution_path(
        self,
        *,
        result: dict[str, Any],
        execution_path: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(result)
        payload["execution_path"] = dict(execution_path)
        return payload

    def _desktop_execution_path_metadata(self, resolution: object) -> dict[str, Any]:
        if resolution is None:
            return {}
        payload = {
            "surface_kind": getattr(resolution, "surface_kind", None),
            "preferred_execution_path": getattr(resolution, "preferred_execution_path", None),
            "ui_fallback_mode": getattr(resolution, "ui_fallback_mode", None),
            "selected_path": getattr(resolution, "selected_path", None),
            "selected_channel": getattr(resolution, "selected_channel", None),
            "selected_ref": getattr(resolution, "selected_ref", None),
            "blocked": bool(getattr(resolution, "blocked", False)),
            "fallback_applied": bool(getattr(resolution, "fallback_applied", False)),
            "current_gap_or_blocker": getattr(resolution, "current_gap_or_blocker", None),
            "attempted_paths": list(getattr(resolution, "attempted_paths", ()) or ()),
            "resolution_reason": getattr(resolution, "resolution_reason", None),
        }
        return payload

    def _desktop_execution_path_ui_fallback(
        self,
        execution_path: dict[str, Any],
        *,
        reason: str,
    ) -> dict[str, Any]:
        updated = dict(execution_path)
        initial_selected_path = self._first_string(updated.get("selected_path"))
        if initial_selected_path is not None:
            updated["initial_selected_path"] = initial_selected_path
        updated["selected_path"] = "ui-fallback"
        updated["selected_channel"] = "ui-fallback"
        updated["selected_ref"] = updated.get("selected_ref") or "ui-fallback"
        updated["fallback_applied"] = True
        updated["blocked"] = False
        prior_reason = self._first_string(updated.get("resolution_reason"))
        updated["resolution_reason"] = (
            f"{prior_reason} {reason}".strip() if prior_reason else reason
        )
        return updated

    def _desktop_document_family(self, contract: dict[str, Any]) -> str | None:
        explicit = self._first_string(
            contract.get("document_family"),
            contract.get("family"),
        )
        if explicit is not None:
            normalized = explicit.lower()
            if normalized.endswith("s"):
                return normalized
            if normalized == "document":
                return "documents"
            if normalized == "presentation":
                return "presentations"
            if normalized == "spreadsheet":
                return "spreadsheets"
            return normalized
        path = _string(contract.get("path"))
        if path is None:
            return None
        return _DESKTOP_DOCUMENT_FAMILY_BY_SUFFIX.get(Path(path).suffix.lower())

    @staticmethod
    def _mapping(value: object) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _first_string(*values: object) -> str | None:
        for value in values:
            normalized = _string(value)
            if normalized is not None:
                return normalized
        return None

    def _window_selector_from_payload(self, payload: Any) -> WindowSelector | None:
        if not isinstance(payload, dict):
            return None
        selector = WindowSelector(
            handle=payload.get("handle"),
            title=_string(payload.get("title")),
            title_contains=_string(payload.get("title_contains")),
            title_regex=_string(payload.get("title_regex")),
            process_id=payload.get("process_id"),
        )
        return None if selector.is_empty() else selector

    def _control_selector_from_payload(self, payload: Any) -> ControlSelector | None:
        if not isinstance(payload, dict):
            return None
        selector = ControlSelector(
            handle=payload.get("handle"),
            automation_id=_string(payload.get("automation_id")),
            title=_string(payload.get("title")),
            title_contains=_string(payload.get("title_contains")),
            title_regex=_string(payload.get("title_regex")),
            control_type=_string(payload.get("control_type")),
            class_name=_string(payload.get("class_name")),
            found_index=payload.get("found_index"),
        )
        return None if selector.is_empty() else selector

    def _resolve_fallback_mode(self, *, failure_class: str, routine: ExecutionRoutineRecord, run: RoutineRunRecord) -> str:
        configured = _string((routine.fallback_policy or {}).get(failure_class))
        if configured in ROUTINE_FALLBACK_MODES:
            return configured
        if failure_class == "execution-error":
            return "retry-same-session"
        if failure_class == "auth-expired":
            return "reattach-or-recover-session"
        if failure_class == "confirmation-required":
            return "pause-for-confirm"
        if failure_class == "modal-interruption":
            return "pause-for-confirm"
        if failure_class in {"page-drift", "precondition-miss"} and self._can_dispatch_replan(
            request_context=dict(run.metadata.get("replay_request_context") or {}),
            fallback_context=dict(routine.metadata.get("fallback_request_context") or {}),
        ):
            return "return-to-llm-replan"
        return "hard-fail"

    def _dispatch_kernel_fallback(self, *, routine: ExecutionRoutineRecord, run: RoutineRunRecord, failure_class: str, summary: str) -> str | None:
        if self._kernel_dispatcher is None:
            return None
        replay_context = dict(run.metadata.get("replay_request_context") or {})
        fallback_context = dict(routine.metadata.get("fallback_request_context") or {})
        if not self._can_dispatch_replan(request_context=replay_context, fallback_context=fallback_context):
            return None
        channel = _string(replay_context.get("channel")) or _string(fallback_context.get("channel"))
        user_id = _string(replay_context.get("user_id")) or _string(fallback_context.get("user_id"))
        session_id = _string(replay_context.get("session_id")) or _string(fallback_context.get("session_id"))
        query_preview = _string(replay_context.get("query_preview")) or _string(fallback_context.get("query_preview"))
        if query_preview is None:
            return None
        request_context = {**dict(fallback_context.get("request_context") or {}), **dict(replay_context.get("request_context") or {})}
        request_payload = replay_context.get("request") or fallback_context.get("request") or request_context
        task_payload: dict[str, Any] = {
            "channel": channel,
            "user_id": user_id,
            "session_id": session_id,
            "query_preview": query_preview,
            "dispatch_events": False,
            "resume_kind": "routine-replay-fallback",
            "routine_id": routine.id,
            "routine_run_id": run.id,
            "failure_class": failure_class,
            "failure_summary": summary,
        }
        if request_payload:
            task_payload["request"] = request_payload
        if request_context:
            task_payload["request_context"] = request_context
        admitted = self._kernel_dispatcher.submit(
            KernelTask(
                title=query_preview,
                capability_ref="system:dispatch_query",
                environment_ref=f"session:{channel}:{session_id}",
                owner_agent_id=run.owner_agent_id or routine.owner_agent_id or "copaw-agent-runner",
                risk_level="auto",
                payload=task_payload,
            ),
        )
        return _string(getattr(admitted, "task_id", None))

    def _can_dispatch_replan(self, *, request_context: dict[str, Any], fallback_context: dict[str, Any]) -> bool:
        merged = {**fallback_context, **request_context}
        return all(_string(merged.get(key)) for key in ("channel", "user_id", "session_id", "query_preview"))

    def _missing_replan_context(self, *, request_context: dict[str, Any], fallback_context: dict[str, Any]) -> list[str]:
        merged = {**fallback_context, **request_context}
        return [
            key
            for key in ("channel", "user_id", "session_id", "query_preview")
            if _string(merged.get(key)) is None
        ]

    def _refresh_routine_health(self, *, routine: ExecutionRoutineRecord, latest_run: RoutineRunRecord) -> ExecutionRoutineRecord:
        recent_runs = self._routine_run_repository.list_runs(routine_id=routine.id, limit=20)
        terminal_runs = [run for run in recent_runs if run.status in {"completed", "failed", "fallback", "blocked"}]
        completed_runs = [run for run in terminal_runs if run.status == "completed"]
        success_rate = len(completed_runs) / len(terminal_runs) if terminal_runs else routine.success_rate
        updated = routine.model_copy(
            update={
                "status": "active" if latest_run.status == "completed" and success_rate >= 0.5 else "degraded" if routine.status != "archived" else routine.status,
                "success_rate": max(0.0, min(1.0, success_rate)),
                "last_verified_at": latest_run.completed_at if latest_run.status == "completed" else routine.last_verified_at,
                "updated_at": _utc_now(),
            },
        )
        return self._routine_repository.upsert_routine(updated)

    def _load_evidence_records(self, evidence_ids: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for evidence_id in evidence_ids or ():
            record = self._evidence_ledger.get_record(str(evidence_id))
            if record is not None:
                payload.append(_serialize_evidence(record))
        return payload

    def _get_browser_runtime_service(self) -> BrowserRuntimeService | None:
        if self._browser_runtime_service is None and self._state_store is not None:
            self._browser_runtime_service = BrowserRuntimeService(self._state_store)
        return self._browser_runtime_service

    def _validate_routine_definition(
        self,
        *,
        engine_kind: str | None,
        environment_kind: str | None,
    ) -> None:
        normalized_engine_kind = _string(engine_kind)
        normalized_environment_kind = _string(environment_kind)
        if (
            normalized_engine_kind is not None
            and normalized_engine_kind not in SUPPORTED_ROUTINE_ENGINE_KINDS
        ):
            supported = ", ".join(SUPPORTED_ROUTINE_ENGINE_KINDS)
            raise ValueError(f"Routine engine_kind must be one of: {supported}")
        if (
            normalized_environment_kind is not None
            and normalized_environment_kind not in SUPPORTED_ROUTINE_ENVIRONMENT_KINDS
        ):
            supported = ", ".join(SUPPORTED_ROUTINE_ENVIRONMENT_KINDS)
            raise ValueError(f"Routine environment_kind must be one of: {supported}")


def _routine_change_type(status: str | None) -> str:
    normalized_status = _string(status) or "completed"
    if normalized_status == "completed":
        return "routine_completed"
    if normalized_status == "fallback":
        return "routine_fallback"
    if normalized_status == "blocked":
        return "routine_blocked"
    return "routine_failed"
