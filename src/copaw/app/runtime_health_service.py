# -*- coding: utf-8 -*-
"""Runtime health surfaces for the hard-cut autonomy runtime."""
from __future__ import annotations

from typing import Any

from ..capabilities.install_templates import build_install_template_doctor
from .runtime_center.overview_cards import _RuntimeCenterOverviewCardsSupport


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
        browser_runtime_service: object | None = None,
        app_state: Any | None = None,
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
        self._browser_runtime_service = browser_runtime_service
        self._app_state = app_state

    def bind_app_state(self, app_state: Any) -> "RuntimeHealthService":
        self._app_state = app_state
        return self

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
            browser_runtime_service=getattr(
                app_state,
                "browser_runtime_service",
                None,
            ),
            app_state=app_state,
        )

    def build_checks(self) -> list[dict[str, object]]:
        return [
            self.build_core_runtime_ready_check(),
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

    async def build_runtime_summary(self) -> dict[str, object]:
        app_state = self._app_state
        if app_state is None:
            return {
                "status": "unavailable",
                "summary": "Runtime health service is not bound to app.state.",
                "automation": {
                    "status": "unavailable",
                    "summary": "Automation runtime summary is unavailable.",
                },
                "startup_recovery": {
                    "available": False,
                    "status": "unavailable",
                    "summary": "Startup recovery summary is not available.",
                },
            }

        support = _RuntimeCenterOverviewCardsSupport()
        automation = await support._build_main_brain_automation_payload(app_state)
        startup_recovery = support._build_main_brain_recovery_payload(app_state)
        automation_status = str(automation.get("status") or "unavailable").strip().lower()
        recovery_status = str(startup_recovery.get("status") or "unavailable").strip().lower()
        summary_status = "idle"
        if automation_status == "degraded":
            summary_status = "degraded"
        elif automation_status == "active":
            summary_status = "active"
        elif recovery_status == "ready":
            summary_status = "ready"
        elif automation_status == "unavailable" and recovery_status == "unavailable":
            summary_status = "unavailable"
        return {
            "status": summary_status,
            "summary": " ".join(
                part
                for part in (
                    str(automation.get("summary") or "").strip(),
                    str(startup_recovery.get("summary") or "").strip(),
                )
                if part
            ),
            "automation": automation,
            "startup_recovery": startup_recovery,
        }
