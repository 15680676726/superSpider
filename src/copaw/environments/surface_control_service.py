# -*- coding: utf-8 -*-
"""Executable routing for cooperative/app-native/semantic surface control."""
from __future__ import annotations

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
        self._document_bridge_executors: dict[str, object] = {}
        self._windows_app_executors: dict[str, object] = {}
        self._semantic_surface_executors: dict[str, object] = {}

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
        result = await self._execute_selected_path(
            resolution.selected_path,
            cooperative_executor=cooperative_executor,
            semantic_executor=None,
            host_executor=host_executor,
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            document_family=resolved_family,
            snapshot=snapshot,
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
        await self._enforce_windows_app_guardrails(
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            snapshot=snapshot,
            selected_executor=selected_executor,
            app_identity=app_identity,
            control_channel=control_channel,
        )
        result = await self._execute_selected_path(
            resolution.selected_path,
            cooperative_executor=cooperative_executor,
            semantic_executor=semantic_executor,
            host_executor=host_executor,
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            snapshot=snapshot,
            app_identity=app_identity,
            control_channel=control_channel,
        )
        return self._decorate_result(result=result, resolution=resolution)

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
        runtime_guardrails = self._mapping(
            self._mapping(snapshot.get("windows_app_adapters")).get("execution_guardrails"),
        )
        explicit_guardrails = self._mapping(contract.get("guardrails"))
        guardrails = {
            **runtime_guardrails,
            **explicit_guardrails,
        }
        if "excluded_surface_refs" not in guardrails and "host_exclusion_refs" in guardrails:
            guardrails["excluded_surface_refs"] = guardrails.get("host_exclusion_refs")
        if not guardrails:
            return
        if bool(guardrails.get("operator_abort_requested")):
            self._publish_guardrail_event(
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
            raise RuntimeError("Windows app action blocked: operator abort is pending.")

        desktop_contract = self._mapping(snapshot.get("desktop_app_contract"))
        expected_frontmost_ref = self._normalize_string(guardrails.get("expected_frontmost_ref"))
        frontmost_verification_required = bool(
            guardrails.get("frontmost_verification_required"),
        ) or expected_frontmost_ref is not None
        if expected_frontmost_ref is None and frontmost_verification_required:
            expected_frontmost_ref = self._normalize_string(
                desktop_contract.get("active_window_ref"),
                desktop_contract.get("window_scope"),
            )
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
            app_identity=app_identity,
            control_channel=control_channel,
            frontmost_verification_required=frontmost_verification_required,
            clipboard_roundtrip_required=clipboard_roundtrip_required,
        )
        frontmost_window_ref = self._normalize_string(
            guardrail_snapshot.get("frontmost_window_ref"),
            desktop_contract.get("active_window_ref"),
            desktop_contract.get("window_scope"),
        )
        if (
            frontmost_window_ref is None
            and guardrail_snapshot.get("frontmost_verified") is True
            and expected_frontmost_ref is not None
        ):
            frontmost_window_ref = expected_frontmost_ref
        if excluded_surface_refs:
            if frontmost_window_ref is None:
                self._publish_guardrail_event(
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="host-exclusion-unverifiable",
                    payload={"excluded_surface_refs": excluded_surface_refs},
                )
                raise RuntimeError(
                    "Host exclusion guardrail blocked: current frontmost surface could not be verified.",
                )
            if frontmost_window_ref in excluded_surface_refs:
                self._publish_guardrail_event(
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="host-exclusion",
                    payload={
                        "frontmost_window_ref": frontmost_window_ref,
                        "excluded_surface_refs": excluded_surface_refs,
                    },
                )
                raise RuntimeError(
                    f"Host exclusion guardrail blocked: frontmost surface '{frontmost_window_ref}' is excluded.",
                )

        if frontmost_verification_required:
            if (
                bool(guardrail_snapshot.get("frontmost_verifier_missing"))
                and "frontmost_window_ref" not in guardrail_snapshot
                and guardrail_snapshot.get("frontmost_verified") is not True
            ):
                self._publish_guardrail_event(
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="frontmost-verifier-missing",
                    payload={"expected_frontmost_ref": expected_frontmost_ref},
                )
                raise RuntimeError(
                    "Windows app action blocked: frontmost verification requires a verifier before execution.",
                )
            if guardrail_snapshot.get("frontmost_verified") is False:
                self._publish_guardrail_event(
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="frontmost-failed",
                    payload={"expected_frontmost_ref": expected_frontmost_ref},
                )
                raise RuntimeError(
                    "Windows app action blocked: frontmost verification failed.",
                )
            if expected_frontmost_ref is not None and frontmost_window_ref is None:
                self._publish_guardrail_event(
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="frontmost-unverifiable",
                    payload={"expected_frontmost_ref": expected_frontmost_ref},
                )
                raise RuntimeError(
                    "Windows app action blocked: frontmost verification could not determine the active window.",
                )
            if (
                expected_frontmost_ref is not None
                and frontmost_window_ref is not None
                and frontmost_window_ref != expected_frontmost_ref
            ):
                self._publish_guardrail_event(
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="frontmost-mismatch",
                    payload={
                        "expected_frontmost_ref": expected_frontmost_ref,
                        "frontmost_window_ref": frontmost_window_ref,
                    },
                )
                raise RuntimeError(
                    f"Windows app action blocked: frontmost window '{frontmost_window_ref}' does not match expected '{expected_frontmost_ref}'.",
                )

        if clipboard_roundtrip_required:
            if (
                bool(guardrail_snapshot.get("clipboard_verifier_missing"))
                and "clipboard_roundtrip_ok" not in guardrail_snapshot
            ):
                self._publish_guardrail_event(
                    session_mount_id=session_mount_id,
                    action=action,
                    guardrail_kind="clipboard-verifier-missing",
                    payload={},
                )
                raise RuntimeError(
                    "Windows app action blocked: clipboard roundtrip verification requires a verifier before execution.",
                )
            if guardrail_snapshot.get("clipboard_roundtrip_ok") is not True:
                self._publish_guardrail_event(
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
                    "Windows app action blocked: clipboard roundtrip verification failed.",
                )

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
        provider = getattr(executor, "guardrail_snapshot", None)
        if callable(provider):
            payload.update(self._mapping(await self._invoke(provider, **kwargs)))
        if frontmost_verification_required:
            verifier = getattr(executor, "verify_frontmost", None)
            if callable(verifier):
                result = self._mapping(await self._invoke(verifier, **kwargs))
                if "verified" in result:
                    payload["frontmost_verified"] = bool(result.get("verified"))
                frontmost_window_ref = self._normalize_string(
                    result.get("frontmost_window_ref"),
                    result.get("window_ref"),
                    result.get("active_window_ref"),
                )
                if frontmost_window_ref is not None:
                    payload["frontmost_window_ref"] = frontmost_window_ref
            elif "frontmost_window_ref" not in payload:
                payload["frontmost_verifier_missing"] = True
        if clipboard_roundtrip_required:
            verifier = getattr(executor, "verify_clipboard_roundtrip", None)
            if callable(verifier):
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

    def _publish_guardrail_event(
        self,
        *,
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
        publisher(topic="desktop", action="guardrail-blocked", payload=event_payload)

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
