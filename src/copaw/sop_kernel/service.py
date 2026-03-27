# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter
from typing import Any

from ..evidence import EvidenceLedger, EvidenceRecord
from ..state import FixedSopBindingRecord, FixedSopTemplateRecord, WorkflowRunRecord
from ..state.repositories import (
    SqliteAgentReportRepository,
    SqliteFixedSopBindingRepository,
    SqliteFixedSopTemplateRepository,
    SqliteWorkflowRunRepository,
)
from .builtin_templates import builtin_fixed_sop_templates
from .models import (
    FixedSopBindingCreateRequest,
    FixedSopBindingDetail,
    FixedSopDoctorCheck,
    FixedSopDoctorReport,
    FixedSopNodeKind,
    FixedSopRunDetail,
    FixedSopRunRequest,
    FixedSopRunResponse,
    FixedSopTemplateListResponse,
    FixedSopTemplateSummary,
)


class FixedSopService:
    def __init__(
        self,
        *,
        template_repository: SqliteFixedSopTemplateRepository,
        binding_repository: SqliteFixedSopBindingRepository,
        workflow_run_repository: SqliteWorkflowRunRepository,
        agent_report_repository: SqliteAgentReportRepository,
        evidence_ledger: EvidenceLedger,
        routine_service: object | None = None,
        environment_service: object | None = None,
    ) -> None:
        self._template_repository = template_repository
        self._binding_repository = binding_repository
        self._workflow_run_repository = workflow_run_repository
        self._agent_report_repository = agent_report_repository
        self._evidence_ledger = evidence_ledger
        self._routine_service = routine_service
        self._environment_service = environment_service
        self._seed_builtin_templates()

    def set_routine_service(self, routine_service: object | None) -> None:
        self._routine_service = routine_service

    def set_environment_service(self, environment_service: object | None) -> None:
        self._environment_service = environment_service

    def validate_node_graph(self, node_graph: list[dict[str, Any]]) -> None:
        allowed = {kind.value for kind in FixedSopNodeKind}
        for node in node_graph:
            kind = str(node.get("kind") or "").strip()
            if kind not in allowed:
                raise ValueError(f"unknown fixed SOP node kind: {kind or '<empty>'}")

    def list_templates(self, *, status: str | None = "active") -> list[FixedSopTemplateRecord]:
        return self._template_repository.list_templates(status=status)

    def search_templates(
        self,
        *,
        query: str,
        owner_role_id: str | None = None,
        industry_tags: list[str] | None = None,
        capability_tags: list[str] | None = None,
        limit: int = 8,
    ) -> list[FixedSopTemplateRecord]:
        tokens = [item.strip().lower() for item in query.split() if item.strip()]
        normalized_owner = (owner_role_id or "").strip()
        required_industry_tags = {
            str(item).strip().lower()
            for item in (industry_tags or [])
            if str(item).strip()
        }
        required_capability_tags = {
            str(item).strip().lower()
            for item in (capability_tags or [])
            if str(item).strip()
        }
        scored: list[tuple[int, FixedSopTemplateRecord]] = []
        for template in self.list_templates(status="active"):
            haystack = " ".join(
                [
                    template.template_id,
                    template.name,
                    template.summary,
                    template.description,
                    " ".join(template.industry_tags or []),
                    " ".join(template.capability_tags or []),
                ]
            ).lower()
            owner_match = (
                not normalized_owner
                or template.owner_role_id == normalized_owner
                or normalized_owner in set(template.suggested_role_ids or [])
            )
            if not owner_match:
                continue
            template_industry_tags = {
                str(item).strip().lower()
                for item in (template.industry_tags or [])
                if str(item).strip()
            }
            template_capability_tags = {
                str(item).strip().lower()
                for item in (template.capability_tags or [])
                if str(item).strip()
            }
            if required_industry_tags and required_industry_tags.isdisjoint(
                template_industry_tags,
            ):
                continue
            if required_capability_tags and required_capability_tags.isdisjoint(
                template_capability_tags,
            ):
                continue
            score = sum(2 for token in tokens if token in template.name.lower())
            score += sum(1 for token in tokens if token in haystack)
            if tokens and score == 0:
                continue
            scored.append((score, template))
        scored.sort(
            key=lambda item: (
                -item[0],
                item[1].updated_at,
                item[1].template_id,
            ),
            reverse=False,
        )
        return [template for _, template in scored[: max(limit, 0)]]

    def list_template_catalog(
        self,
        *,
        status: str | None = "active",
    ) -> FixedSopTemplateListResponse:
        templates = self.list_templates(status=status)
        bindings = self._binding_repository.list_bindings(limit=1000)
        binding_counts = Counter(binding.template_id for binding in bindings)
        items = [
            FixedSopTemplateSummary(
                template=template,
                binding_count=binding_counts.get(template.template_id, 0),
                routes={
                    "detail": f"/api/fixed-sops/templates/{template.template_id}",
                    "bindings": f"/api/fixed-sops/bindings?template_id={template.template_id}",
                },
            )
            for template in templates
        ]
        return FixedSopTemplateListResponse(items=items, total=len(items))

    def get_template(self, template_id: str) -> FixedSopTemplateRecord | None:
        return self._template_repository.get_template(template_id)

    def list_binding_details(
        self,
        *,
        template_id: str | None = None,
        status: str | None = None,
        industry_instance_id: str | None = None,
        owner_agent_id: str | None = None,
        limit: int | None = 50,
    ) -> list[FixedSopBindingDetail]:
        bindings = self._binding_repository.list_bindings(
            template_id=template_id,
            status=status,
            industry_instance_id=industry_instance_id,
            owner_agent_id=owner_agent_id,
            limit=limit,
        )
        details: list[FixedSopBindingDetail] = []
        for binding in bindings:
            template = self.get_template(binding.template_id)
            if template is None:
                continue
            details.append(
                FixedSopBindingDetail(
                    binding=binding,
                    template=template,
                    routes={
                        "detail": f"/api/fixed-sops/bindings/{binding.binding_id}",
                        "run": f"/api/fixed-sops/bindings/{binding.binding_id}/run",
                    },
                )
            )
        return details

    def get_binding(self, binding_id: str) -> FixedSopBindingDetail:
        binding = self._binding_repository.get_binding(binding_id)
        if binding is None:
            raise KeyError(f"Fixed SOP binding '{binding_id}' not found")
        template = self.get_template(binding.template_id)
        if template is None:
            raise KeyError(f"Fixed SOP template '{binding.template_id}' not found")
        return FixedSopBindingDetail(
            binding=binding,
            template=template,
            routes={
                "detail": f"/api/fixed-sops/bindings/{binding.binding_id}",
                "run": f"/api/fixed-sops/bindings/{binding.binding_id}/run",
            },
        )

    def create_binding(self, payload: FixedSopBindingCreateRequest) -> FixedSopBindingDetail:
        template = self.get_template(payload.template_id)
        if template is None:
            raise KeyError(f"Fixed SOP template '{payload.template_id}' not found")
        binding = FixedSopBindingRecord(
            template_id=payload.template_id,
            binding_name=payload.binding_name or template.name,
            status=payload.status,
            owner_scope=payload.owner_scope,
            owner_agent_id=payload.owner_agent_id,
            industry_instance_id=payload.industry_instance_id,
            workflow_template_id=payload.workflow_template_id,
            trigger_mode=payload.trigger_mode,
            trigger_ref=payload.trigger_ref,
            input_mapping=dict(payload.input_mapping or {}),
            output_mapping=dict(payload.output_mapping or {}),
            timeout_policy=dict(payload.timeout_policy or {}),
            retry_policy=dict(payload.retry_policy or {}),
            risk_baseline=payload.risk_baseline or template.risk_baseline,
            metadata=dict(payload.metadata or {}),
        )
        self._binding_repository.upsert_binding(binding)
        return self.get_binding(binding.binding_id)

    def update_binding(
        self,
        binding_id: str,
        payload: FixedSopBindingCreateRequest,
    ) -> FixedSopBindingDetail:
        existing = self._binding_repository.get_binding(binding_id)
        if existing is None:
            raise KeyError(f"Fixed SOP binding '{binding_id}' not found")
        template = self.get_template(payload.template_id)
        if template is None:
            raise KeyError(f"Fixed SOP template '{payload.template_id}' not found")
        updated = existing.model_copy(
            update={
                "template_id": payload.template_id,
                "binding_name": payload.binding_name or existing.binding_name,
                "status": payload.status,
                "owner_scope": payload.owner_scope,
                "owner_agent_id": payload.owner_agent_id,
                "industry_instance_id": payload.industry_instance_id,
                "workflow_template_id": payload.workflow_template_id,
                "trigger_mode": payload.trigger_mode,
                "trigger_ref": payload.trigger_ref,
                "input_mapping": dict(payload.input_mapping or {}),
                "output_mapping": dict(payload.output_mapping or {}),
                "timeout_policy": dict(payload.timeout_policy or {}),
                "retry_policy": dict(payload.retry_policy or {}),
                "risk_baseline": payload.risk_baseline or template.risk_baseline,
                "metadata": dict(payload.metadata or {}),
            }
        )
        self._binding_repository.upsert_binding(updated)
        return self.get_binding(binding_id)

    def run_doctor(self, binding_id: str) -> FixedSopDoctorReport:
        detail = self.get_binding(binding_id)
        host_context = self._resolve_binding_host_context(detail)
        host_preflight = self._resolve_host_preflight(
            environment_id=host_context["environment_id"],
            session_mount_id=host_context["session_mount_id"],
        )
        host_requirement = host_context["host_requirement"]
        checks = [
            FixedSopDoctorCheck(
                key="template",
                label="Template Installed",
                status="pass",
                message=f"Using template '{detail.template.template_id}'.",
            ),
            FixedSopDoctorCheck(
                key="binding-status",
                label="Binding Status",
                status="pass" if detail.binding.status == "active" else "warn",
                message=f"Binding status is '{detail.binding.status}'.",
            ),
        ]
        host_check = self._evaluate_host_preflight(
            host_preflight=host_preflight,
            host_requirement=host_requirement,
        )
        if host_check is not None:
            checks.append(host_check)
        status = "ready" if detail.binding.status == "active" else "degraded"
        if host_check is not None and host_check.status == "fail":
            status = "blocked"
        return FixedSopDoctorReport(
            binding_id=detail.binding.binding_id,
            template_id=detail.template.template_id,
            status=status,
            summary=(
                "Fixed SOP binding is blocked by host preflight."
                if status == "blocked"
                else "Fixed SOP binding is ready."
                if status == "ready"
                else "Binding can run but is not marked active."
            ),
            checks=checks,
            environment_id=host_context["environment_id"],
            session_mount_id=host_context["session_mount_id"],
            host_requirement=dict(host_requirement or {}),
            host_preflight=host_preflight,
            routes={
                "binding": f"/api/fixed-sops/bindings/{detail.binding.binding_id}",
                "run": f"/api/fixed-sops/bindings/{detail.binding.binding_id}/run",
            },
        )

    async def run_binding(
        self,
        binding_id: str,
        payload: FixedSopRunRequest,
    ) -> FixedSopRunResponse:
        detail = self.get_binding(binding_id)
        host_context = self._resolve_binding_host_context(detail, payload)
        host_preflight = self._resolve_host_preflight(
            environment_id=host_context["environment_id"],
            session_mount_id=host_context["session_mount_id"],
        )
        host_check = self._evaluate_host_preflight(
            host_preflight=host_preflight,
            host_requirement=host_context["host_requirement"],
        )
        if host_check is not None and host_check.status == "fail":
            raise ValueError(
                host_check.message or "host preflight blocked fixed SOP execution",
            )
        workflow_run_id = payload.workflow_run_id or f"fixed-sop-run:{binding_id}"
        existing = self._workflow_run_repository.get_run(workflow_run_id)
        if existing is None:
            run = WorkflowRunRecord(
                run_id=workflow_run_id,
                template_id=detail.template.template_id,
                title=detail.binding.binding_name,
                summary=detail.template.summary,
                status="completed" if not payload.dry_run else "planned",
                owner_scope=payload.owner_scope or detail.binding.owner_scope,
                owner_agent_id=payload.owner_agent_id or detail.binding.owner_agent_id,
                industry_instance_id=detail.binding.industry_instance_id,
                parameter_payload=dict(payload.input_payload or {}),
                metadata={
                    "fixed_sop_binding_id": binding_id,
                    "trigger_mode": detail.binding.trigger_mode,
                    "dry_run": payload.dry_run,
                    "environment_id": host_context["environment_id"],
                    "session_mount_id": host_context["session_mount_id"],
                    "host_requirement": dict(host_context["host_requirement"] or {}),
                    "host_preflight": dict(host_preflight or {}),
                },
            )
        else:
            run = existing.model_copy(
                update={
                    "status": "completed" if not payload.dry_run else "planned",
                    "parameter_payload": dict(payload.input_payload or {}),
                    "metadata": {
                        **dict(existing.metadata or {}),
                        "environment_id": host_context["environment_id"],
                        "session_mount_id": host_context["session_mount_id"],
                        "host_requirement": dict(host_context["host_requirement"] or {}),
                        "host_preflight": dict(host_preflight or {}),
                    },
                }
            )
        self._workflow_run_repository.upsert_run(run)
        binding = detail.binding.model_copy(update={"last_run_id": run.run_id})
        self._binding_repository.upsert_binding(binding)
        evidence_id = None
        if not payload.dry_run:
            evidence = self._evidence_ledger.append(
                EvidenceRecord(
                    actor_ref="fixed-sop-kernel",
                    environment_ref=host_context["environment_id"],
                    capability_ref="system:run_fixed_sop",
                    task_id=run.run_id,
                    risk_level=detail.binding.risk_baseline,
                    action_summary=f"Run fixed SOP binding {binding_id}",
                    result_summary=f"Fixed SOP '{detail.binding.binding_name}' completed.",
                    status="recorded",
                    metadata={
                        "fixed_sop_binding_id": binding_id,
                        "fixed_sop_template_id": detail.template.template_id,
                        "environment_id": host_context["environment_id"],
                        "session_mount_id": host_context["session_mount_id"],
                        "host_requirement": dict(host_context["host_requirement"] or {}),
                        "host_preflight": dict(host_preflight or {}),
                    },
                )
            )
            evidence_id = evidence.id
        return FixedSopRunResponse(
            binding_id=binding_id,
            status="success",
            summary=f"Fixed SOP binding '{detail.binding.binding_name}' executed.",
            workflow_run_id=run.run_id,
            evidence_id=evidence_id,
            routes={
                "binding": f"/api/fixed-sops/bindings/{binding_id}",
                "run": f"/api/fixed-sops/runs/{run.run_id}",
            },
        )

    def get_run(self, run_id: str) -> FixedSopRunDetail:
        run = self._workflow_run_repository.get_run(run_id)
        if run is None:
            raise KeyError(f"Fixed SOP run '{run_id}' not found")
        binding_id = str(run.metadata.get("fixed_sop_binding_id") or "").strip()
        binding = self._binding_repository.get_binding(binding_id) if binding_id else None
        template = self.get_template(run.template_id)
        return FixedSopRunDetail(
            run=run,
            binding=binding,
            template=template,
            environment_id=str(run.metadata.get("environment_id") or "").strip() or None,
            session_mount_id=str(run.metadata.get("session_mount_id") or "").strip() or None,
            host_requirement=dict(run.metadata.get("host_requirement") or {}),
            host_preflight=dict(run.metadata.get("host_preflight") or {}),
        )

    def _resolve_binding_host_context(
        self,
        detail: FixedSopBindingDetail,
        payload: FixedSopRunRequest | None = None,
    ) -> dict[str, Any]:
        binding_metadata = dict(detail.binding.metadata or {})
        payload_metadata = dict(payload.metadata or {}) if payload is not None else {}
        host_requirement = payload_metadata.get("host_requirement")
        if not isinstance(host_requirement, dict):
            host_requirement = binding_metadata.get("host_requirement")
        return {
            "environment_id": (
                payload.environment_id
                if payload is not None and payload.environment_id
                else binding_metadata.get("environment_id")
            ),
            "session_mount_id": (
                payload.session_mount_id
                if payload is not None and payload.session_mount_id
                else binding_metadata.get("session_mount_id")
            ),
            "host_requirement": dict(host_requirement or {}),
        }

    def _resolve_host_preflight(
        self,
        *,
        environment_id: str | None,
        session_mount_id: str | None,
    ) -> dict[str, Any]:
        service = self._environment_service
        if service is None:
            return {}
        if session_mount_id:
            getter = getattr(service, "get_session_detail", None)
            if callable(getter):
                detail = getter(session_mount_id, limit=20)
                if isinstance(detail, dict):
                    return dict(detail.get("host_twin") or {})
        if environment_id:
            getter = getattr(service, "get_environment_detail", None)
            if callable(getter):
                detail = getter(environment_id, limit=20)
                if isinstance(detail, dict):
                    return dict(detail.get("host_twin") or {})
        return {}

    def _evaluate_host_preflight(
        self,
        *,
        host_preflight: dict[str, Any],
        host_requirement: dict[str, Any],
    ) -> FixedSopDoctorCheck | None:
        if not bool(host_requirement.get("mutating")):
            return None
        continuity = dict(host_preflight.get("continuity") or {})
        execution_mutation_ready = dict(host_preflight.get("execution_mutation_ready") or {})
        coordination = dict(host_preflight.get("coordination") or {})
        surface_kind = str(host_requirement.get("surface_kind") or "").strip() or "desktop"
        surface_key = "desktop_app" if surface_kind == "desktop" else "browser"
        continuity_valid = bool(
            continuity.get("valid")
            or str(continuity.get("status") or "").strip() in {"attached", "restorable"}
        )
        writable = bool(execution_mutation_ready.get(surface_key))
        recommended_action = str(
            coordination.get("recommended_scheduler_action") or "",
        ).strip()
        reason = (
            str(dict(coordination.get("contention_forecast") or {}).get("reason") or "").strip()
            or "host preflight could not confirm a legal writable path"
        )
        blocked = (
            not host_preflight
            or not continuity_valid
            or not writable
            or recommended_action in {"handoff", "recover", "retry"}
        )
        return FixedSopDoctorCheck(
            key="host-preflight",
            label="Host Preflight",
            status="fail" if blocked else "pass",
            message=(
                f"host preflight blocked fixed SOP execution: {reason}"
                if blocked
                else "Host preflight confirms a legal writable path."
            ),
        )

    def _seed_builtin_templates(self) -> None:
        for template in builtin_fixed_sop_templates():
            self.validate_node_graph(template.node_graph)
            self._template_repository.upsert_template(template)
