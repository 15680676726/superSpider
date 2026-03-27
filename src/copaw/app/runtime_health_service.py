# -*- coding: utf-8 -*-
"""Runtime health surfaces for the hard-cut autonomy runtime."""
from __future__ import annotations

from typing import Any

from ..capabilities.install_templates import build_install_template_doctor


class RuntimeHealthService:
    """Build structured runtime health checks for system surfaces."""

    def __init__(
        self,
        *,
        state_store: object | None = None,
        evidence_ledger: object | None = None,
        environment_service: object | None = None,
        capability_service: object | None = None,
        kernel_dispatcher: object | None = None,
        governance_service: object | None = None,
        runtime_event_bus: object | None = None,
        memory_manager: object | None = None,
        browser_runtime_service: object | None = None,
    ) -> None:
        self._core_services = {
            "state_store": state_store,
            "evidence_ledger": evidence_ledger,
            "environment_service": environment_service,
            "capability_service": capability_service,
            "kernel_dispatcher": kernel_dispatcher,
            "governance_service": governance_service,
            "runtime_event_bus": runtime_event_bus,
        }
        self._capability_service = capability_service
        self._memory_manager = memory_manager
        self._browser_runtime_service = browser_runtime_service

    @classmethod
    def from_app_state(cls, app_state: Any) -> "RuntimeHealthService":
        return cls(
            state_store=getattr(app_state, "state_store", None),
            evidence_ledger=getattr(app_state, "evidence_ledger", None),
            environment_service=getattr(app_state, "environment_service", None),
            capability_service=getattr(app_state, "capability_service", None),
            kernel_dispatcher=getattr(app_state, "kernel_dispatcher", None),
            governance_service=getattr(app_state, "governance_service", None),
            runtime_event_bus=getattr(app_state, "runtime_event_bus", None),
            memory_manager=getattr(app_state, "memory_manager", None),
            browser_runtime_service=getattr(
                app_state,
                "browser_runtime_service",
                None,
            ),
        )

    def build_checks(self) -> list[dict[str, object]]:
        return [
            self.build_core_runtime_ready_check(),
            self.build_memory_vector_ready_check(),
            self.build_memory_embedding_config_check(),
            self.build_surface_ready_check(
                name="browser_surface_ready",
                template_id="browser-local",
                ready_summary="Browser surface is ready for delegated execution.",
                degraded_summary=(
                    "Browser surface needs capability or host attention."
                ),
            ),
            self.build_surface_ready_check(
                name="desktop_surface_ready",
                template_id="desktop-windows",
                ready_summary="Desktop surface is ready for delegated execution.",
                degraded_summary=(
                    "Desktop surface needs host or install attention."
                ),
            ),
        ]

    def build_core_runtime_ready_check(self) -> dict[str, object]:
        missing_services = [
            name
            for name, service in self._core_services.items()
            if service is None
        ]
        status = "pass" if not missing_services else "warn"
        summary = (
            "Core runtime services are wired."
            if not missing_services
            else "Core runtime is degraded; missing "
            + ", ".join(missing_services)
            + "."
        )
        return {
            "name": "core_runtime_ready",
            "status": status,
            "summary": summary,
            "meta": {
                "missing_services": missing_services,
                "required_services": list(self._core_services.keys()),
            },
        }

    def build_memory_vector_ready_check(self) -> dict[str, object]:
        payload = self._memory_runtime_payload()
        vector_enabled = bool(payload.get("vector_enabled"))
        summary = (
            "Memory vector search is ready."
            if vector_enabled
            else str(
                payload.get("vector_disable_reason")
                or "Memory vector search is degraded."
            )
        )
        return {
            "name": "memory_vector_ready",
            "status": "pass" if vector_enabled else "warn",
            "summary": summary,
            "meta": {
                "vector_enabled": vector_enabled,
                "vector_disable_reason_code": payload.get(
                    "vector_disable_reason_code",
                ),
                "vector_disable_reason": payload.get("vector_disable_reason"),
                "fts_enabled": payload.get("fts_enabled"),
                "memory_store_backend": payload.get("memory_store_backend"),
            },
        }

    def build_memory_embedding_config_check(self) -> dict[str, object]:
        payload = self._memory_runtime_payload()
        vector_enabled = bool(payload.get("vector_enabled"))
        embedding_model_name = str(payload.get("embedding_model_name") or "").strip()
        if vector_enabled and embedding_model_name:
            summary = f"Embedding model resolved to '{embedding_model_name}'."
            status = "pass"
        else:
            summary = str(
                payload.get("vector_disable_reason")
                or "Embedding model configuration is incomplete."
            )
            status = "warn"
        return {
            "name": "memory_embedding_config",
            "status": status,
            "summary": summary,
            "meta": dict(payload),
        }

    def build_surface_ready_check(
        self,
        *,
        name: str,
        template_id: str,
        ready_summary: str,
        degraded_summary: str,
    ) -> dict[str, object]:
        report = build_install_template_doctor(
            template_id,
            capability_service=self._capability_service,
            browser_runtime_service=self._browser_runtime_service,
        )
        if report is None:
            return {
                "name": name,
                "status": "warn",
                "summary": degraded_summary,
                "meta": {
                    "template_id": template_id,
                    "doctor_status": "missing",
                },
            }
        report_payload = (
            report.model_dump(mode="json")
            if hasattr(report, "model_dump")
            else {}
        )
        doctor_status = str(getattr(report, "status", "") or "").strip().lower()
        return {
            "name": name,
            "status": "pass" if doctor_status == "ready" else "warn",
            "summary": ready_summary if doctor_status == "ready" else getattr(report, "summary", degraded_summary),
            "meta": {
                "template_id": template_id,
                "doctor_status": doctor_status or "unknown",
                **(report_payload if isinstance(report_payload, dict) else {}),
            },
        }

    def _memory_runtime_payload(self) -> dict[str, object]:
        memory_manager = self._memory_manager
        if memory_manager is None:
            return {
                "vector_enabled": False,
                "vector_disable_reason_code": "memory_manager_unavailable",
                "vector_disable_reason": (
                    "Memory manager is not attached to runtime state."
                ),
                "embedding_model_name": "",
                "embedding_model_inferred": False,
                "embedding_base_url": "",
                "embedding_api_key_configured": False,
                "embedding_follow_active_provider": False,
                "embedding_provider_inherited": False,
                "fts_enabled": False,
                "memory_store_backend": None,
            }
        getter = getattr(memory_manager, "runtime_health_payload", None)
        if not callable(getter):
            return {
                "vector_enabled": False,
                "vector_disable_reason_code": "runtime_health_unavailable",
                "vector_disable_reason": (
                    "Memory manager does not expose runtime health payload."
                ),
                "embedding_model_name": "",
                "embedding_model_inferred": False,
                "embedding_base_url": "",
                "embedding_api_key_configured": False,
                "embedding_follow_active_provider": False,
                "embedding_provider_inherited": False,
                "fts_enabled": False,
                "memory_store_backend": None,
            }
        payload = getter()
        return dict(payload) if isinstance(payload, dict) else {}
