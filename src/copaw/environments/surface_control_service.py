# -*- coding: utf-8 -*-
"""Executable routing for cooperative/app-native/semantic surface control."""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .cooperative import (
    COOPERATIVE_NATIVE_PATH,
    SEMANTIC_OPERATOR_PATH,
    UI_FALLBACK_PATH,
)

_DOCUMENT_FAMILY_BY_SUFFIX = {
    ".csv": "spreadsheets",
    ".doc": "documents",
    ".docx": "documents",
    ".md": "documents",
    ".ppt": "presentations",
    ".pptx": "presentations",
    ".rtf": "documents",
    ".tsv": "spreadsheets",
    ".txt": "documents",
    ".xls": "spreadsheets",
    ".xlsx": "spreadsheets",
}


class SurfaceControlService:
    """Routes surface actions through cooperative-native, semantic, then UI fallback."""

    def __init__(self, environment_service) -> None:
        self._service = environment_service
        self._browser_companion_executors: dict[str, object] = {}
        self._document_bridge_executors: dict[str, object] = {}
        self._windows_app_executors: dict[str, object] = {}
        self._semantic_surface_executors: dict[str, object] = {}

    def register_browser_companion_executor(
        self,
        companion_ref: str,
        executor: object | None,
    ) -> None:
        normalized = self._normalize_string(companion_ref)
        if normalized is None:
            raise ValueError("companion_ref is required")
        if executor is None:
            self._browser_companion_executors.pop(normalized, None)
            return
        self._browser_companion_executors[normalized] = executor

    def register_document_bridge_executor(
        self,
        bridge_ref: str,
        executor: object | None,
    ) -> None:
        normalized = self._normalize_string(bridge_ref)
        if normalized is None:
            raise ValueError("bridge_ref is required")
        if executor is None:
            self._document_bridge_executors.pop(normalized, None)
            return
        self._document_bridge_executors[normalized] = executor

    def register_windows_app_executor(
        self,
        app_identity: str,
        executor: object | None,
    ) -> None:
        normalized = self._normalize_string(app_identity)
        if normalized is None:
            raise ValueError("app_identity is required")
        if executor is None:
            self._windows_app_executors.pop(normalized, None)
            return
        self._windows_app_executors[normalized] = executor

    def register_semantic_surface_executor(
        self,
        control_channel: str,
        executor: object | None,
    ) -> None:
        normalized = self._normalize_string(control_channel)
        if normalized is None:
            raise ValueError("control_channel is required")
        if executor is None:
            self._semantic_surface_executors.pop(normalized, None)
            return
        self._semantic_surface_executors[normalized] = executor

    async def execute_browser_action(
        self,
        *,
        session_mount_id: str,
        action: str,
        contract: dict[str, Any],
        host_executor: object | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        snapshot = self._service.browser_companion_snapshot(
            session_mount_id=session_mount_id,
        )
        detail = self._service.get_session_detail(session_mount_id, limit=limit) or {}
        companion = self._mapping(snapshot.get("browser_companion"))
        transport_ref = self._normalize_string(companion.get("transport_ref"))
        provider_session_ref = self._normalize_string(
            companion.get("provider_session_ref"),
        )
        cooperative_executor = self._resolve_browser_companion_executor(
            transport_ref=transport_ref,
            provider_session_ref=provider_session_ref,
        )
        blocker = self._normalize_string(snapshot.get("adapter_gap_or_blocker"))
        if (
            transport_ref is not None or provider_session_ref is not None
        ) and cooperative_executor is None:
            blocker = blocker or (
                "Browser companion executor is not registered for the active transport."
            )
        cooperative_refs = [
            ref
            for ref in (transport_ref, provider_session_ref)
            if ref is not None
        ]
        resolution = self._service.resolve_execution_path(
            surface_kind="browser",
            cooperative_available=bool(companion.get("available")) and callable(cooperative_executor),
            cooperative_refs=cooperative_refs or None,
            cooperative_blocker=blocker,
            semantic_available=False,
            ui_available=callable(host_executor),
            ui_ref="browser-ui-host",
        )
        selected_executor = self._resolve_selected_executor(
            resolution.selected_path,
            cooperative_executor=cooperative_executor,
            semantic_executor=None,
            host_executor=host_executor,
        )
        browser_site_contract = self._mapping(detail.get("browser_site_contract"))
        result = await self._execute_live_action(
            surface_kind="browser",
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            snapshot=snapshot,
            detail=detail,
            resolution_selected_path=resolution.selected_path,
            cooperative_executor=cooperative_executor,
            semantic_executor=None,
            host_executor=host_executor,
            selected_executor=selected_executor,
            guardrail_runner=self._enforce_browser_guardrails,
            guardrail_kwargs={
                "session_mount_id": session_mount_id,
                "action": action,
                "contract": contract,
                "snapshot": snapshot,
                "selected_executor": selected_executor,
                "transport_ref": transport_ref,
                "provider_session_ref": provider_session_ref,
                "default_expected_frontmost_ref": self._normalize_string(
                    browser_site_contract.get("active_tab_ref"),
                    browser_site_contract.get("site_contract_ref"),
                ),
            },
            execution_kwargs={
                "session_mount_id": session_mount_id,
                "action": action,
                "contract": contract,
                "snapshot": snapshot,
                "transport_ref": transport_ref,
                "provider_session_ref": provider_session_ref,
            },
        )
        return self._decorate_result(result=result, resolution=resolution)

    async def execute_document_action(
        self,
        *,
        session_mount_id: str,
        action: str,
        contract: dict[str, Any],
        host_executor: object | None = None,
        document_family: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        resolved_family = self._resolve_document_family(contract, explicit=document_family)
        snapshot = self._service.document_bridge_snapshot(
            session_mount_id=session_mount_id,
            document_family=resolved_family,
            limit=limit,
        )
        bridge = self._mapping(snapshot.get("document_bridge"))
        bridge_ref = self._normalize_string(bridge.get("bridge_ref"))
        cooperative_executor = (
            self._document_bridge_executors.get(bridge_ref)
            if bridge_ref is not None
            else None
        )
        blocker = self._normalize_string(snapshot.get("adapter_gap_or_blocker"))
        if bridge_ref is not None and cooperative_executor is None:
            blocker = blocker or f"Document bridge executor is not registered for '{bridge_ref}'."
        resolution = self._service.resolve_execution_path(
            surface_kind="document",
            cooperative_available=bool(bridge.get("available")) and callable(cooperative_executor),
            cooperative_refs=[bridge_ref] if bridge_ref is not None else None,
            cooperative_blocker=blocker,
            semantic_available=False,
            ui_available=callable(host_executor),
            ui_ref="windows-desktop-host",
        )
        selected_executor = self._resolve_selected_executor(
            resolution.selected_path,
            cooperative_executor=cooperative_executor,
            semantic_executor=None,
            host_executor=host_executor,
        )
        detail = self._service.get_session_detail(session_mount_id, limit=limit) or {}
        result = await self._execute_live_action(
            surface_kind="document",
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            snapshot=snapshot,
            detail=detail,
            resolution_selected_path=resolution.selected_path,
            cooperative_executor=cooperative_executor,
            semantic_executor=None,
            host_executor=host_executor,
            selected_executor=selected_executor,
            guardrail_runner=self._enforce_document_guardrails,
            guardrail_kwargs={
                "session_mount_id": session_mount_id,
                "action": action,
                "contract": contract,
                "snapshot": snapshot,
                "selected_executor": selected_executor,
                "bridge_ref": bridge_ref,
                "document_family": resolved_family,
            },
            execution_kwargs={
                "session_mount_id": session_mount_id,
                "action": action,
                "contract": contract,
                "document_family": resolved_family,
                "snapshot": snapshot,
            },
        )
        return self._decorate_result(result=result, resolution=resolution)

    async def execute_windows_app_action(
        self,
        *,
        session_mount_id: str,
        action: str,
        contract: dict[str, Any],
        host_executor: object | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        snapshot = self._service.windows_app_adapter_snapshot(
            session_mount_id=session_mount_id,
            limit=limit,
        )
        adapters = self._mapping(snapshot.get("windows_app_adapters"))
        adapter_refs = self._string_list(adapters.get("adapter_refs"))
        app_identity = self._normalize_string(
            adapters.get("app_identity"),
        ) or self._normalize_string(contract.get("app_identity"))
        control_channel = self._normalize_string(
            adapters.get("control_channel"),
        ) or self._normalize_string(contract.get("control_channel"))
        cooperative_executor = self._resolve_windows_app_executor(
            app_identity=app_identity,
            adapter_refs=adapter_refs,
        )
        semantic_executor = (
            self._semantic_surface_executors.get(control_channel)
            if control_channel is not None
            else None
        )
        blocker = self._normalize_string(snapshot.get("adapter_gap_or_blocker"))
        if adapter_refs and cooperative_executor is None:
            blocker = blocker or (
                f"Windows app executor is not registered for '{app_identity or adapter_refs[0]}'."
            )
        resolution = self._service.resolve_execution_path(
            surface_kind="windows-app",
            cooperative_available=callable(cooperative_executor),
            cooperative_refs=adapter_refs,
            cooperative_blocker=blocker,
            semantic_available=callable(semantic_executor),
            semantic_channel=control_channel or SEMANTIC_OPERATOR_PATH,
            semantic_ref=control_channel,
            ui_available=callable(host_executor),
            ui_ref="windows-desktop-host",
        )
        selected_executor = self._resolve_selected_executor(
            resolution.selected_path,
            cooperative_executor=cooperative_executor,
            semantic_executor=semantic_executor,
            host_executor=host_executor,
        )
        result = await self._execute_live_action(
            surface_kind="windows-app",
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            snapshot=snapshot,
            detail=snapshot,
            resolution_selected_path=resolution.selected_path,
            cooperative_executor=cooperative_executor,
            semantic_executor=semantic_executor,
            host_executor=host_executor,
            selected_executor=selected_executor,
            guardrail_runner=self._enforce_windows_app_guardrails,
            guardrail_kwargs={
                "session_mount_id": session_mount_id,
                "action": action,
                "contract": contract,
                "snapshot": snapshot,
                "selected_executor": selected_executor,
                "app_identity": app_identity,
                "control_channel": control_channel,
            },
            execution_kwargs={
                "session_mount_id": session_mount_id,
                "action": action,
                "contract": contract,
                "snapshot": snapshot,
                "app_identity": app_identity,
                "control_channel": control_channel,
            },
        )
        return self._decorate_result(result=result, resolution=resolution)

    async def _execute_live_action(
        self,
        *,
        surface_kind: str,
        session_mount_id: str,
        action: str,
        contract: dict[str, Any],
        snapshot: dict[str, Any],
        detail: dict[str, Any],
        resolution_selected_path: str | None,
        cooperative_executor: object | None,
        semantic_executor: object | None,
        host_executor: object | None,
        selected_executor: object | None,
        guardrail_runner,
        guardrail_kwargs: dict[str, Any],
        execution_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        cleanup_executors = self._cleanup_executors(
            selected_executor=selected_executor,
            host_executor=host_executor,
        )
        await self._poll_host_operator_abort(
            host_executor,
            **execution_kwargs,
        )
        cleanup_state = await self._prepare_execution_cleanup(
            cleanup_executors,
            **execution_kwargs,
        )
        execution_started = False
        failure: BaseException | None = None
        result: dict[str, Any] | None = None
        try:
            await self._invoke(guardrail_runner, **guardrail_kwargs)
            acquire = getattr(self._service, "acquire_shared_writer_lease", None)
            release = getattr(self._service, "release_shared_writer_lease", None)
            if resolution_selected_path is None or not callable(acquire) or not callable(release):
                execution_started = True
                result = await self._execute_selected_path(
                    resolution_selected_path,
                    cooperative_executor=cooperative_executor,
                    semantic_executor=semantic_executor,
                    host_executor=host_executor,
                    **execution_kwargs,
                )
            else:
                writer_lock_scope = self._resolve_live_surface_writer_scope(
                    session_mount_id=session_mount_id,
                    contract=contract,
                    snapshot=snapshot,
                    detail=detail,
                )
                writer_owner, lease_metadata = self._build_live_surface_writer_lease_payload(
                    surface_kind=surface_kind,
                    session_mount_id=session_mount_id,
                    action=action,
                    writer_lock_scope=writer_lock_scope,
                    contract=contract,
                    snapshot=snapshot,
                    detail=detail,
                )
                try:
                    lease = acquire(
                        writer_lock_scope=writer_lock_scope,
                        owner=writer_owner,
                        metadata=lease_metadata,
                    )
                except RuntimeError as exc:
                    message = str(exc).lower()
                    if "already leased by" in message:
                        raise RuntimeError(
                            f"Writer scope '{writer_lock_scope}' is already reserved.",
                        ) from exc
                    raise

                release_reason = f"{surface_kind} action completed"
                execution_started = True
                try:
                    result = await self._execute_selected_path(
                        resolution_selected_path,
                        cooperative_executor=cooperative_executor,
                        semantic_executor=semantic_executor,
                        host_executor=host_executor,
                        **execution_kwargs,
                    )
                except asyncio.CancelledError:
                    release_reason = f"{surface_kind} action cancelled"
                    raise
                except Exception:
                    release_reason = f"{surface_kind} action failed"
                    raise
                finally:
                    release(
                        lease_id=lease.id,
                        lease_token=lease.lease_token,
                        reason=release_reason,
                    )
        except BaseException as exc:  # includes asyncio.CancelledError
            failure = exc

        cleanup_error = await self._run_execution_cleanup(
            cleanup_executors,
            cleanup_state=cleanup_state,
            execution_started=execution_started,
            execution_outcome=self._execution_outcome(
                execution_started=execution_started,
                failure=failure,
            ),
            execution_error=failure,
            **execution_kwargs,
        )
        if failure is not None:
            raise failure.with_traceback(failure.__traceback__)
        if cleanup_error is not None:
            raise cleanup_error.with_traceback(cleanup_error.__traceback__)
        return result or {}

    def _resolve_live_surface_writer_scope(
        self,
        *,
        session_mount_id: str,
        contract: dict[str, Any],
        snapshot: dict[str, Any],
        detail: dict[str, Any],
    ) -> str:
        session = self._service.get_session(session_mount_id)
        session_metadata = self._mapping(getattr(session, "metadata", None))
        snapshot_mapping = self._mapping(snapshot)
        detail_mapping = self._mapping(detail)
        contract_surface = self._mapping(contract.get("surface_contract"))
        desktop_from_snapshot = self._mapping(snapshot_mapping.get("desktop_app_contract"))
        desktop_from_detail = self._mapping(detail_mapping.get("desktop_app_contract"))
        return self._normalize_string(
            contract.get("writer_lock_scope"),
            contract.get("lock_scope_ref"),
            contract.get("scope_ref"),
            contract_surface.get("writer_lock_scope"),
            desktop_from_snapshot.get("writer_lock_scope"),
            desktop_from_detail.get("writer_lock_scope"),
            session_metadata.get("writer_lock_scope"),
            session_mount_id,
        ) or session_mount_id

    def _build_live_surface_writer_lease_payload(
        self,
        *,
        surface_kind: str,
        session_mount_id: str,
        action: str,
        writer_lock_scope: str,
        contract: dict[str, Any],
        snapshot: dict[str, Any],
        detail: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        session = self._service.get_session(session_mount_id)
        environment = None
        environment_id = self._normalize_string(getattr(session, "environment_id", None))
        if environment_id is not None:
            environment = self._service.get_environment(environment_id)
        session_metadata = self._mapping(getattr(session, "metadata", None))
        environment_metadata = self._mapping(
            getattr(environment, "metadata", None) if environment is not None else None,
        )
        detail_mapping = self._mapping(detail)
        snapshot_mapping = self._mapping(snapshot)
        owner = self._normalize_string(
            getattr(session, "lease_owner", None),
            contract.get("owner_agent_id"),
            contract.get("owner"),
            session_metadata.get("lease_owner"),
            "live-surface",
        ) or "live-surface"
        metadata = {
            "access_mode": "writer",
            "lease_class": "exclusive-writer",
            "writer_lock_scope": writer_lock_scope,
            "surface_kind": surface_kind,
            "action_name": action,
            "session_mount_id": session_mount_id,
            "environment_ref": self._normalize_string(
                contract.get("environment_ref"),
                detail_mapping.get("environment_id"),
                snapshot_mapping.get("environment_id"),
                environment_id,
                session_metadata.get("environment_ref"),
                environment_metadata.get("environment_ref"),
            ) or f"resource-slot:shared-writer:{writer_lock_scope}",
        }
        return owner, metadata

    async def _execute_selected_path(
        self,
        selected_path: str | None,
        *,
        cooperative_executor: object | None,
        semantic_executor: object | None,
        host_executor: object | None,
        **kwargs,
    ) -> dict[str, Any]:
        if selected_path == COOPERATIVE_NATIVE_PATH:
            if not callable(cooperative_executor):
                raise RuntimeError("Cooperative/native executor is not available.")
            return self._coerce_result(await self._invoke(cooperative_executor, **kwargs))
        if selected_path == SEMANTIC_OPERATOR_PATH:
            if not callable(semantic_executor):
                raise RuntimeError("Semantic surface executor is not available.")
            return self._coerce_result(await self._invoke(semantic_executor, **kwargs))
        if selected_path == UI_FALLBACK_PATH:
            if not callable(host_executor):
                raise RuntimeError("UI fallback executor is not available.")
            return self._coerce_result(await self._invoke(host_executor, **kwargs))
        raise RuntimeError("No executable path is available for the requested surface action.")

    async def _invoke(self, executor: object, **kwargs):
        result = executor(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def _decorate_result(
        self,
        *,
        result: dict[str, Any],
        resolution,
    ) -> dict[str, Any]:
        payload = dict(result)
        payload["execution_path"] = asdict(resolution)
        return payload

    async def _enforce_windows_app_guardrails(
        self,
        *,
        session_mount_id: str,
        action: str,
        contract: dict[str, Any],
        snapshot: dict[str, Any],
        selected_executor: object | None,
        app_identity: str | None,
        control_channel: str | None,
    ) -> None:
        desktop_contract = self._mapping(snapshot.get("desktop_app_contract"))
        await self._enforce_live_execution_guardrails(
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            snapshot=snapshot,
            selected_executor=selected_executor,
            runtime_guardrails=self._mapping(
                self._mapping(snapshot.get("windows_app_adapters")).get("execution_guardrails"),
            ),
            surface_label="Windows app",
            event_topic="desktop",
            default_expected_frontmost_ref=self._normalize_string(
                desktop_contract.get("active_window_ref"),
                desktop_contract.get("window_scope"),
            ),
            app_identity=app_identity,
            control_channel=control_channel,
        )

    async def _enforce_browser_guardrails(
        self,
        *,
        session_mount_id: str,
        action: str,
        contract: dict[str, Any],
        snapshot: dict[str, Any],
        selected_executor: object | None,
        transport_ref: str | None,
        provider_session_ref: str | None,
        default_expected_frontmost_ref: str | None,
    ) -> None:
        await self._enforce_live_execution_guardrails(
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            snapshot=snapshot,
            selected_executor=selected_executor,
            runtime_guardrails=self._mapping(
                self._mapping(snapshot.get("browser_companion")).get("execution_guardrails"),
            ),
            surface_label="Browser",
            event_topic="browser",
            default_expected_frontmost_ref=default_expected_frontmost_ref,
            transport_ref=transport_ref,
            provider_session_ref=provider_session_ref,
        )

    async def _enforce_document_guardrails(
        self,
        *,
        session_mount_id: str,
        action: str,
        contract: dict[str, Any],
        snapshot: dict[str, Any],
        selected_executor: object | None,
        bridge_ref: str | None,
        document_family: str | None,
    ) -> None:
        await self._enforce_live_execution_guardrails(
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            snapshot=snapshot,
            selected_executor=selected_executor,
            runtime_guardrails=self._mapping(
                self._mapping(snapshot.get("document_bridge")).get("execution_guardrails"),
            ),
            surface_label="Document",
            event_topic="document",
            bridge_ref=bridge_ref,
            document_family=document_family,
        )

    async def _enforce_live_execution_guardrails(
        self,
        *,
        session_mount_id: str,
        action: str,
        contract: dict[str, Any],
        snapshot: dict[str, Any],
        selected_executor: object | None,
        runtime_guardrails: dict[str, Any],
        surface_label: str,
        event_topic: str,
        default_expected_frontmost_ref: str | None = None,
        **executor_kwargs,
    ) -> None:
        explicit_guardrails = self._mapping(contract.get("guardrails"))
        guardrails = {
            **runtime_guardrails,
            **explicit_guardrails,
        }
        guardrails = self._merge_shared_operator_abort_guardrails(
            session_mount_id=session_mount_id,
            guardrails=guardrails,
        )
        if "excluded_surface_refs" not in guardrails and "host_exclusion_refs" in guardrails:
            guardrails["excluded_surface_refs"] = guardrails.get("host_exclusion_refs")
        if not guardrails:
            return
        if bool(guardrails.get("operator_abort_requested")):
            self._publish_guardrail_event(
                topic=event_topic,
                session_mount_id=session_mount_id,
                action=action,
                guardrail_kind="operator-abort",
                payload={
                    "reason": self._normalize_string(
                        guardrails.get("abort_reason"),
                        guardrails.get("operator_abort_channel"),
                    ),
                },
            )
            raise RuntimeError(f"{surface_label} action blocked: operator abort is pending.")

        expected_frontmost_ref = self._normalize_string(
            guardrails.get("expected_frontmost_ref"),
            default_expected_frontmost_ref,
        )
        frontmost_verification_required = bool(
            guardrails.get("frontmost_verification_required"),
        ) or expected_frontmost_ref is not None
        excluded_surface_refs = self._string_list(guardrails.get("excluded_surface_refs"))
        if not excluded_surface_refs:
            excluded_surface_refs = self._string_list(guardrails.get("host_exclusion_refs"))
        clipboard_roundtrip_required = bool(guardrails.get("clipboard_roundtrip_required"))

        guardrail_snapshot = await self._collect_guardrail_snapshot(
            selected_executor,
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            snapshot=snapshot,
            frontmost_verification_required=frontmost_verification_required,
            clipboard_roundtrip_required=clipboard_roundtrip_required,
            **executor_kwargs,
        )
        frontmost_surface_ref = self._normalize_string(
            guardrail_snapshot.get("frontmost_surface_ref"),
            guardrail_snapshot.get("frontmost_window_ref"),
            guardrail_snapshot.get("active_surface_ref"),
            guardrail_snapshot.get("active_tab_ref"),
        )
        if (
            frontmost_surface_ref is None
            and guardrail_snapshot.get("frontmost_verified") is True
            and expected_frontmost_ref is not None
        ):
            frontmost_surface_ref = expected_frontmost_ref
        if excluded_surface_refs:
            if frontmost_surface_ref is None:
                self._publish_guardrail_event(
                    topic=event_topic,
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="host-exclusion-unverifiable",
                    payload={"excluded_surface_refs": excluded_surface_refs},
                )
                raise RuntimeError(
                    "Host exclusion guardrail blocked: current frontmost surface could not be verified.",
                )
            if frontmost_surface_ref in excluded_surface_refs:
                self._publish_guardrail_event(
                    topic=event_topic,
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="host-exclusion",
                    payload={
                        "frontmost_surface_ref": frontmost_surface_ref,
                        "excluded_surface_refs": excluded_surface_refs,
                    },
                )
                raise RuntimeError(
                    f"Host exclusion guardrail blocked: frontmost surface '{frontmost_surface_ref}' is excluded.",
                )

        if frontmost_verification_required:
            if (
                bool(guardrail_snapshot.get("frontmost_verifier_missing"))
                and "frontmost_window_ref" not in guardrail_snapshot
                and "frontmost_surface_ref" not in guardrail_snapshot
                and guardrail_snapshot.get("frontmost_verified") is not True
            ):
                self._publish_guardrail_event(
                    topic=event_topic,
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="frontmost-verifier-missing",
                    payload={"expected_frontmost_ref": expected_frontmost_ref},
                )
                raise RuntimeError(
                    f"{surface_label} action blocked: frontmost verification requires a verifier before execution.",
                )
            if guardrail_snapshot.get("frontmost_verified") is False:
                self._publish_guardrail_event(
                    topic=event_topic,
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="frontmost-failed",
                    payload={"expected_frontmost_ref": expected_frontmost_ref},
                )
                raise RuntimeError(
                    f"{surface_label} action blocked: frontmost verification failed.",
                )
            if expected_frontmost_ref is not None and frontmost_surface_ref is None:
                self._publish_guardrail_event(
                    topic=event_topic,
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="frontmost-unverifiable",
                    payload={"expected_frontmost_ref": expected_frontmost_ref},
                )
                raise RuntimeError(
                    f"{surface_label} action blocked: frontmost verification could not determine the active surface.",
                )
            if (
                expected_frontmost_ref is not None
                and frontmost_surface_ref is not None
                and frontmost_surface_ref != expected_frontmost_ref
            ):
                self._publish_guardrail_event(
                    topic=event_topic,
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="frontmost-mismatch",
                    payload={
                        "expected_frontmost_ref": expected_frontmost_ref,
                        "frontmost_surface_ref": frontmost_surface_ref,
                    },
                )
                raise RuntimeError(
                    f"{surface_label} action blocked: frontmost surface '{frontmost_surface_ref}' does not match expected '{expected_frontmost_ref}'.",
                )

        if clipboard_roundtrip_required:
            if (
                bool(guardrail_snapshot.get("clipboard_verifier_missing"))
                and "clipboard_roundtrip_ok" not in guardrail_snapshot
            ):
                self._publish_guardrail_event(
                    topic=event_topic,
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="clipboard-verifier-missing",
                    payload={},
                )
                raise RuntimeError(
                    f"{surface_label} action blocked: clipboard roundtrip verification requires a verifier before execution.",
                )
            if guardrail_snapshot.get("clipboard_roundtrip_ok") is not True:
                self._publish_guardrail_event(
                    topic=event_topic,
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="clipboard-roundtrip",
                    payload={
                        "clipboard_roundtrip_ok": bool(
                            guardrail_snapshot.get("clipboard_roundtrip_ok"),
                        ),
                    },
                )
                raise RuntimeError(
                    f"{surface_label} action blocked: clipboard roundtrip verification failed.",
                )

    def _merge_shared_operator_abort_guardrails(
        self,
        *,
        session_mount_id: str,
        guardrails: dict[str, Any],
    ) -> dict[str, Any]:
        shared_abort_state = self._resolve_shared_operator_abort_state(
            session_mount_id=session_mount_id,
        )
        if not shared_abort_state.get("requested"):
            return dict(guardrails)
        merged = dict(guardrails)
        shared_channel = self._normalize_string(shared_abort_state.get("channel"))
        if shared_channel is not None:
            merged["operator_abort_channel"] = shared_channel
        elif self._normalize_string(merged.get("operator_abort_channel")) is None:
            merged.pop("operator_abort_channel", None)
        merged["operator_abort_requested"] = True
        reason = self._normalize_string(
            merged.get("abort_reason"),
            shared_abort_state.get("reason"),
        )
        if reason is not None:
            merged["abort_reason"] = reason
        if shared_abort_state.get("requested_at") is not None:
            merged.setdefault("operator_abort_requested_at", shared_abort_state["requested_at"])
        return merged

    def _resolve_shared_operator_abort_state(
        self,
        *,
        session_mount_id: str,
    ) -> dict[str, Any]:
        session = self._service.get_session(session_mount_id)
        if session is None:
            return {}
        environment = None
        environment_id = self._normalize_string(getattr(session, "environment_id", None))
        if environment_id is not None:
            environment = self._service.get_environment(environment_id)
        session_metadata = self._mapping(getattr(session, "metadata", None))
        environment_metadata = self._mapping(
            getattr(environment, "metadata", None) if environment is not None else None,
        )
        raw = session_metadata.get("operator_abort_state")
        if not isinstance(raw, dict):
            raw = environment_metadata.get("operator_abort_state")
        if not isinstance(raw, dict):
            return {}
        channel = self._normalize_string(
            raw.get("channel"),
            raw.get("operator_abort_channel"),
        )
        reason = self._normalize_string(
            raw.get("reason"),
            raw.get("abort_reason"),
            channel,
        )
        requested_at = self._normalize_string(raw.get("requested_at"))
        requested = bool(
            raw.get("requested")
            if "requested" in raw
            else raw.get("operator_abort_requested"),
        )
        state: dict[str, Any] = {}
        if channel is not None:
            state["channel"] = channel
        if requested:
            state["requested"] = True
        if reason is not None:
            state["reason"] = reason
        if requested_at is not None:
            state["requested_at"] = requested_at
        return state

    def _abort_channels_match(
        self,
        *,
        guardrail_channel: object,
        shared_channel: object,
    ) -> bool:
        normalized_guardrail_channel = self._normalize_string(guardrail_channel)
        normalized_shared_channel = self._normalize_string(shared_channel)
        if normalized_guardrail_channel is None or normalized_shared_channel is None:
            return True
        return normalized_guardrail_channel == normalized_shared_channel

    async def _collect_guardrail_snapshot(
        self,
        executor: object | None,
        *,
        frontmost_verification_required: bool = False,
        clipboard_roundtrip_required: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        if executor is None:
            return {}
        payload: dict[str, Any] = {}
        provider = self._resolve_executor_hook(executor, "guardrail_snapshot")
        if provider is not None:
            payload.update(self._mapping(await self._invoke(provider, **kwargs)))
        if frontmost_verification_required:
            verifier = self._resolve_executor_hook(executor, "verify_frontmost")
            if verifier is not None:
                result = self._mapping(await self._invoke(verifier, **kwargs))
                if "verified" in result:
                    payload["frontmost_verified"] = bool(result.get("verified"))
                frontmost_surface_ref = self._normalize_string(
                    result.get("frontmost_surface_ref"),
                    result.get("frontmost_window_ref"),
                    result.get("window_ref"),
                    result.get("active_window_ref"),
                    result.get("active_surface_ref"),
                    result.get("active_tab_ref"),
                )
                if frontmost_surface_ref is not None:
                    payload["frontmost_surface_ref"] = frontmost_surface_ref
            elif (
                "frontmost_window_ref" not in payload
                and "frontmost_surface_ref" not in payload
            ):
                payload["frontmost_verifier_missing"] = True
        if clipboard_roundtrip_required:
            verifier = self._resolve_executor_hook(
                executor,
                "verify_clipboard_roundtrip",
            )
            if verifier is not None:
                result = self._mapping(await self._invoke(verifier, **kwargs))
                if "verified" in result:
                    payload["clipboard_roundtrip_ok"] = bool(result.get("verified"))
                elif "clipboard_roundtrip_ok" in result:
                    payload["clipboard_roundtrip_ok"] = bool(
                        result.get("clipboard_roundtrip_ok"),
                    )
            elif "clipboard_roundtrip_ok" not in payload:
                payload["clipboard_verifier_missing"] = True
        return payload

    def _cleanup_executors(
        self,
        *,
        selected_executor: object | None,
        host_executor: object | None,
    ) -> list[object]:
        executors: list[object] = []
        for executor in (host_executor, selected_executor):
            if executor is None:
                continue
            if any(existing is executor for existing in executors):
                continue
            executors.append(executor)
        return executors

    async def _poll_host_operator_abort(
        self,
        executor: object | None,
        **kwargs,
    ) -> dict[str, Any]:
        hook = self._resolve_executor_hook(executor, "poll_operator_abort_signal")
        if hook is None:
            return {}
        return self._mapping(await self._invoke(hook, **kwargs))

    async def _prepare_execution_cleanup(
        self,
        executors: list[object],
        **kwargs,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for executor in executors:
            hook = self._resolve_executor_hook(executor, "prepare_execution_cleanup")
            if hook is None:
                continue
            payload.update(self._mapping(await self._invoke(hook, **kwargs)))
        return payload

    async def _run_execution_cleanup(
        self,
        executors: list[object],
        *,
        cleanup_state: dict[str, Any],
        execution_started: bool,
        execution_outcome: str,
        execution_error: BaseException | None,
        **kwargs,
    ) -> BaseException | None:
        cleanup_error: BaseException | None = None
        for hook_name in (
            "restore_foreground",
            "verify_clipboard_restore",
            "cleanup_execution",
        ):
            for executor in executors:
                hook = self._resolve_executor_hook(executor, hook_name)
                if hook is None:
                    continue
                try:
                    result = await self._invoke(
                        hook,
                        cleanup_state=cleanup_state,
                        execution_started=execution_started,
                        execution_outcome=execution_outcome,
                        execution_error=execution_error,
                        **kwargs,
                    )
                    if hook_name == "verify_clipboard_restore":
                        verification = self._mapping(result)
                        verified = verification.get("verified")
                        clipboard_restore_ok = verification.get("clipboard_restore_ok")
                        if verified is False or (
                            clipboard_restore_ok is not None
                            and not bool(clipboard_restore_ok)
                        ):
                            raise RuntimeError(
                                "Clipboard restore verification failed after execution cleanup.",
                            )
                except BaseException as exc:  # includes asyncio.CancelledError
                    if cleanup_error is None:
                        cleanup_error = exc
        return cleanup_error

    @staticmethod
    def _execution_outcome(
        *,
        execution_started: bool,
        failure: BaseException | None,
    ) -> str:
        if failure is None:
            return "completed"
        if isinstance(failure, asyncio.CancelledError):
            return "cancelled"
        if execution_started:
            return "failed"
        return "blocked"

    @staticmethod
    def _resolve_executor_hook(
        executor: object | None,
        hook_name: str,
    ):
        if executor is None:
            return None
        for candidate in (executor, getattr(executor, "__self__", None)):
            if candidate is None:
                continue
            hook = getattr(candidate, hook_name, None)
            if callable(hook):
                return hook
        return None

    def _publish_guardrail_event(
        self,
        *,
        topic: str = "desktop",
        session_mount_id: str,
        action: str,
        guardrail_kind: str,
        payload: dict[str, Any],
    ) -> None:
        bus = getattr(self._service, "_runtime_event_bus", None)
        publisher = getattr(bus, "publish", None) if bus is not None else None
        if not callable(publisher):
            return
        event_payload = {
            "session_mount_id": session_mount_id,
            "action_name": action,
            "guardrail_kind": guardrail_kind,
            **{key: value for key, value in payload.items() if value is not None},
        }
        publisher(topic=topic, action="guardrail-blocked", payload=event_payload)

    @staticmethod
    def _resolve_selected_executor(
        selected_path: str | None,
        *,
        cooperative_executor: object | None,
        semantic_executor: object | None,
        host_executor: object | None,
    ) -> object | None:
        if selected_path == COOPERATIVE_NATIVE_PATH:
            return cooperative_executor
        if selected_path == SEMANTIC_OPERATOR_PATH:
            return semantic_executor
        if selected_path == UI_FALLBACK_PATH:
            return host_executor
        return None

    def _resolve_windows_app_executor(
        self,
        *,
        app_identity: str | None,
        adapter_refs: list[str],
    ) -> object | None:
        if app_identity is not None:
            executor = self._windows_app_executors.get(app_identity)
            if executor is not None:
                return executor
        for ref in adapter_refs:
            normalized = self._normalize_string(ref)
            if normalized is None:
                continue
            executor = self._windows_app_executors.get(normalized)
            if executor is not None:
                return executor
        return None

    def _resolve_browser_companion_executor(
        self,
        *,
        transport_ref: str | None,
        provider_session_ref: str | None,
    ) -> object | None:
        for ref in (transport_ref, provider_session_ref):
            normalized = self._normalize_string(ref)
            if normalized is None:
                continue
            executor = self._browser_companion_executors.get(normalized)
            if executor is not None:
                return executor
        return None

    def _resolve_document_family(
        self,
        contract: dict[str, Any],
        *,
        explicit: str | None,
    ) -> str | None:
        if explicit is not None:
            return explicit
        direct = self._normalize_string(contract.get("document_family"))
        if direct is not None:
            return direct
        path = self._normalize_string(contract.get("path"))
        if path is None:
            return None
        suffix = Path(path).suffix.lower()
        return _DOCUMENT_FAMILY_BY_SUFFIX.get(suffix)

    @staticmethod
    def _coerce_result(result: object) -> dict[str, Any]:
        if isinstance(result, dict):
            return dict(result)
        return {
            "success": bool(result),
            "value": result,
        }

    @staticmethod
    def _mapping(value: object) -> dict[str, object]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if normalized:
                result.append(normalized)
        return result

    @staticmethod
    def _normalize_string(*values: object) -> str | None:
        for value in values:
            if isinstance(value, str):
                normalized = value.strip()
                if normalized:
                    return normalized
        return None
