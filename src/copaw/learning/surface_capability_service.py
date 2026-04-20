# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..evidence import EvidenceRecord
from ..kernel import KernelTask
from ..state.models_surface_learning import (
    SurfaceCapabilityTwinRecord,
    SurfacePlaybookRecord,
)
from ..state.repositories import (
    SqliteSurfaceCapabilityTwinRepository,
    SqliteSurfacePlaybookRepository,
)
from .models import SurfaceLearningIngestResult, SurfaceLearningScopeProjection


@dataclass(slots=True)
class SurfaceLearningScopeContext:
    scope_level: str
    scope_id: str
    industry_instance_id: str | None = None
    lane_id: str | None = None
    assignment_id: str | None = None
    owner_agent_id: str | None = None


class SurfaceCapabilityService:
    """Merge surface evidence into formal twins and project the active playbook."""

    def __init__(
        self,
        *,
        surface_capability_twin_repository: SqliteSurfaceCapabilityTwinRepository,
        surface_playbook_repository: SqliteSurfacePlaybookRepository,
    ) -> None:
        self._twin_repository = surface_capability_twin_repository
        self._playbook_repository = surface_playbook_repository

    def ingest_surface_evidence(
        self,
        *,
        task: KernelTask,
        evidence: EvidenceRecord,
    ) -> SurfaceLearningIngestResult:
        context = self.resolve_scope_context(task=task, evidence=evidence)
        capability_name = self._resolve_capability_name(task=task, evidence=evidence)
        existing = self._find_active_twin(
            scope_level=context.scope_level,
            scope_id=context.scope_id,
            capability_name=capability_name,
        )
        active_twin = self._persist_twin(
            task=task,
            evidence=evidence,
            context=context,
            capability_name=capability_name,
            existing=existing,
        )
        active_playbook = self.project_active_playbook(
            scope_level=context.scope_level,
            scope_id=context.scope_id,
            context=context,
        )
        version_candidates = [active_twin.version]
        updated_candidates = [active_twin.updated_at]
        if active_playbook is not None:
            version_candidates.append(active_playbook.version)
            updated_candidates.append(active_playbook.updated_at)
        return SurfaceLearningIngestResult(
            scope_level=context.scope_level,
            scope_id=context.scope_id,
            version=max(version_candidates) if version_candidates else None,
            updated_at=self._latest_datetime(updated_candidates),
            active_twin=active_twin,
            active_playbook=active_playbook,
        )

    def build_scope_projection(
        self,
        *,
        scope_level: str,
        scope_id: str,
    ) -> SurfaceLearningScopeProjection | None:
        active_twins = self._twin_repository.get_active_twins(
            scope_level=scope_level,
            scope_id=scope_id,
        )
        active_playbook = self._playbook_repository.get_active_playbook(
            scope_level=scope_level,
            scope_id=scope_id,
        )
        if not active_twins and active_playbook is None:
            return None
        version_candidates = [record.version for record in active_twins]
        updated_candidates = [record.updated_at for record in active_twins]
        if active_playbook is not None:
            version_candidates.append(active_playbook.version)
            updated_candidates.append(active_playbook.updated_at)
        return SurfaceLearningScopeProjection(
            scope_level=scope_level,
            scope_id=scope_id,
            version=max(version_candidates) if version_candidates else None,
            updated_at=self._latest_datetime(updated_candidates),
            active_twins=active_twins,
            active_playbook=active_playbook,
        )

    def project_active_playbook(
        self,
        *,
        scope_level: str,
        scope_id: str,
        context: SurfaceLearningScopeContext | None = None,
    ) -> SurfacePlaybookRecord | None:
        active_twins = self._sorted_twins(
            self._twin_repository.get_active_twins(
                scope_level=scope_level,
                scope_id=scope_id,
            ),
        )
        if not active_twins:
            return None
        existing = self._playbook_repository.get_active_playbook(
            scope_level=scope_level,
            scope_id=scope_id,
        )
        recommended_steps = self._merge_texts(
            *[record.probe_steps for record in active_twins],
            *[record.execution_steps for record in active_twins],
        )
        execution_steps = self._merge_texts(
            *[record.execution_steps for record in active_twins],
        )
        success_signals = self._merge_texts(
            *[record.result_signals for record in active_twins],
        )
        blocker_signals = self._merge_texts(
            *[record.failure_modes for record in active_twins],
            *[record.required_state_signals for record in active_twins],
        )
        evidence_refs = self._merge_texts(
            *[record.evidence_refs for record in active_twins],
        )
        playbook = SurfacePlaybookRecord(
            scope_level=scope_level,
            scope_id=scope_id,
            playbook_id=(
                existing.playbook_id
                if existing is not None and existing.status != "active"
                else SurfacePlaybookRecord(scope_level=scope_level, scope_id=scope_id).playbook_id
            ),
            twin_id=active_twins[0].twin_id if len(active_twins) == 1 else None,
            summary=self._build_playbook_summary(scope_id=scope_id, twins=active_twins),
            capability_names=[record.capability_name for record in active_twins],
            recommended_steps=recommended_steps or [record.capability_name for record in active_twins],
            probe_steps=self._merge_texts(*[record.probe_steps for record in active_twins]),
            execution_steps=execution_steps or [record.capability_name for record in active_twins],
            success_signals=success_signals,
            blocker_signals=blocker_signals,
            evidence_refs=evidence_refs,
            version=(existing.version + 1) if existing is not None else 1,
            status="active",
            metadata=self._scope_metadata(
                context=context or self._context_from_records(active_twins),
                evidence=None,
                existing_metadata=existing.metadata if existing is not None else None,
            ),
        )
        return self._playbook_repository.upsert_playbook(playbook)

    def resolve_scope_context(
        self,
        *,
        task: KernelTask,
        evidence: EvidenceRecord | None = None,
    ) -> SurfaceLearningScopeContext:
        payload = task.payload if isinstance(task.payload, dict) else {}
        evidence_metadata = dict(evidence.metadata or {}) if evidence is not None else {}
        work_context_id = self._non_empty_str(task.work_context_id)
        if work_context_id is not None:
            return SurfaceLearningScopeContext(
                scope_level="work_context",
                scope_id=work_context_id,
                industry_instance_id=self._non_empty_str(
                    payload.get("industry_instance_id"),
                    evidence_metadata.get("industry_instance_id"),
                ),
                lane_id=self._non_empty_str(payload.get("lane_id"), evidence_metadata.get("lane_id")),
                assignment_id=self._non_empty_str(
                    payload.get("assignment_id"),
                    evidence_metadata.get("assignment_id"),
                ),
                owner_agent_id=self._non_empty_str(task.owner_agent_id),
            )
        industry_scope = self._non_empty_str(
            payload.get("industry_instance_id"),
            evidence_metadata.get("industry_instance_id"),
        )
        if industry_scope is not None:
            return SurfaceLearningScopeContext(
                scope_level="industry_scope",
                scope_id=industry_scope,
                industry_instance_id=industry_scope,
                lane_id=self._non_empty_str(payload.get("lane_id"), evidence_metadata.get("lane_id")),
                assignment_id=self._non_empty_str(
                    payload.get("assignment_id"),
                    evidence_metadata.get("assignment_id"),
                ),
                owner_agent_id=self._non_empty_str(task.owner_agent_id),
            )
        return SurfaceLearningScopeContext(
            scope_level="session",
            scope_id=task.id,
            owner_agent_id=self._non_empty_str(task.owner_agent_id),
        )

    def _persist_twin(
        self,
        *,
        task: KernelTask,
        evidence: EvidenceRecord,
        context: SurfaceLearningScopeContext,
        capability_name: str,
        existing: SurfaceCapabilityTwinRecord | None,
    ) -> SurfaceCapabilityTwinRecord:
        metadata = dict(evidence.metadata or {})
        transition_payload = (
            metadata.get("transition")
            if isinstance(metadata.get("transition"), dict)
            else {}
        )
        verification_payload = (
            metadata.get("verification")
            if isinstance(metadata.get("verification"), dict)
            else {}
        )
        twin = SurfaceCapabilityTwinRecord(
            scope_level=context.scope_level,
            scope_id=context.scope_id,
            capability_name=capability_name,
            capability_kind=self._non_empty_str(
                metadata.get("capability_kind"),
                existing.capability_kind if existing is not None else None,
            )
            or "action",
            surface_kind=self._non_empty_str(
                metadata.get("surface_kind"),
                existing.surface_kind if existing is not None else None,
            )
            or "",
            summary=self._build_twin_summary(
                capability_name=capability_name,
                evidence=evidence,
                existing=existing,
            ),
            entry_conditions=self._merge_texts(
                existing.entry_conditions if existing is not None else [],
                metadata.get("blocker_kind"),
            ),
            entry_regions=self._merge_texts(
                existing.entry_regions if existing is not None else [],
                metadata.get("region_ref"),
                metadata.get("scope_anchor"),
            ),
            required_state_signals=self._merge_texts(
                existing.required_state_signals if existing is not None else [],
                transition_payload.get("changed_nodes"),
                transition_payload.get("new_blockers"),
                transition_payload.get("resolved_blockers"),
            ),
            probe_steps=self._merge_texts(
                existing.probe_steps if existing is not None else [],
                self._build_probe_hint(evidence=evidence),
            ),
            execution_steps=self._merge_texts(
                existing.execution_steps if existing is not None else [],
                task.title,
                evidence.action_summary,
            ),
            result_signals=self._merge_texts(
                existing.result_signals if existing is not None else [],
                evidence.result_summary,
                transition_payload.get("result_summary"),
                verification_payload.get("expected_normalized_text"),
                verification_payload.get("observed_normalized_text"),
                verification_payload.get("observed_text"),
            ),
            failure_modes=self._merge_texts(
                existing.failure_modes if existing is not None else [],
                metadata.get("blocker_kind"),
                [] if verification_payload.get("verified", True) else "verification-failed",
            ),
            risk_level=evidence.risk_level if evidence.risk_level in {"auto", "guarded", "confirm"} else "auto",
            evidence_refs=self._merge_texts(
                existing.evidence_refs if existing is not None else [],
                evidence.id,
            ),
            source_transition_refs=self._merge_texts(
                existing.source_transition_refs if existing is not None else [],
                evidence.id if evidence.kind == "surface-transition" else None,
            ),
            source_discovery_refs=self._merge_texts(
                existing.source_discovery_refs if existing is not None else [],
                evidence.id if evidence.kind == "surface-discovery" else None,
            ),
            version=(existing.version + 1) if existing is not None else 1,
            status="active",
            metadata=self._scope_metadata(
                context=context,
                evidence=evidence,
                existing_metadata=existing.metadata if existing is not None else None,
            ),
        )
        return self._twin_repository.upsert_twin(twin)

    def _find_active_twin(
        self,
        *,
        scope_level: str,
        scope_id: str,
        capability_name: str,
    ) -> SurfaceCapabilityTwinRecord | None:
        active = self._twin_repository.list_twins(
            scope_level=scope_level,
            scope_id=scope_id,
            capability_name=capability_name,
            status="active",
            limit=1,
        )
        return active[0] if active else None

    @staticmethod
    def _sorted_twins(
        records: list[SurfaceCapabilityTwinRecord],
    ) -> list[SurfaceCapabilityTwinRecord]:
        return sorted(
            records,
            key=lambda item: (
                item.updated_at or item.created_at,
                item.capability_name,
            ),
            reverse=True,
        )

    def _build_twin_summary(
        self,
        *,
        capability_name: str,
        evidence: EvidenceRecord,
        existing: SurfaceCapabilityTwinRecord | None,
    ) -> str:
        metadata = dict(evidence.metadata or {})
        label = self._non_empty_str(metadata.get("label"))
        if label is not None:
            return label
        if evidence.kind == "surface-transition":
            transition_payload = metadata.get("transition")
            if isinstance(transition_payload, dict):
                transition_summary = self._non_empty_str(transition_payload.get("result_summary"))
                if transition_summary is not None:
                    return transition_summary
        if existing is not None and existing.summary:
            return existing.summary
        return self._non_empty_str(evidence.result_summary, evidence.action_summary) or capability_name.replace("_", " ")

    def _build_playbook_summary(
        self,
        *,
        scope_id: str,
        twins: list[SurfaceCapabilityTwinRecord],
    ) -> str:
        if len(twins) == 1 and twins[0].summary:
            return twins[0].summary
        return f"{scope_id} active surface playbook"

    def _build_probe_hint(self, *, evidence: EvidenceRecord) -> str | None:
        metadata = dict(evidence.metadata or {})
        region_ref = self._non_empty_str(metadata.get("region_ref"))
        label = self._non_empty_str(metadata.get("label"))
        if region_ref and label:
            return f"inspect {region_ref} for {label}"
        if label:
            return f"inspect {label}"
        return None

    def _context_from_records(
        self,
        records: list[SurfaceCapabilityTwinRecord],
    ) -> SurfaceLearningScopeContext:
        metadata = records[0].metadata if records else {}
        return SurfaceLearningScopeContext(
            scope_level=records[0].scope_level if records else "session",
            scope_id=records[0].scope_id if records else "",
            industry_instance_id=self._non_empty_str(metadata.get("industry_instance_id")),
            lane_id=self._non_empty_str(metadata.get("lane_id")),
            assignment_id=self._non_empty_str(metadata.get("assignment_id")),
            owner_agent_id=self._non_empty_str(metadata.get("owner_agent_id")),
        )

    def _scope_metadata(
        self,
        *,
        context: SurfaceLearningScopeContext,
        evidence: EvidenceRecord | None,
        existing_metadata: dict[str, object] | None,
    ) -> dict[str, object]:
        payload = dict(existing_metadata or {})
        if context.industry_instance_id is not None:
            payload["industry_instance_id"] = context.industry_instance_id
        if context.lane_id is not None:
            payload["lane_id"] = context.lane_id
        if context.assignment_id is not None:
            payload["assignment_id"] = context.assignment_id
        if context.owner_agent_id is not None:
            payload["owner_agent_id"] = context.owner_agent_id
        if evidence is not None:
            metadata = dict(evidence.metadata or {})
            surface_kind = self._non_empty_str(metadata.get("surface_kind"))
            if surface_kind is not None:
                payload["surface_kind"] = surface_kind
            if evidence.kind:
                payload["last_evidence_kind"] = evidence.kind
            if evidence.id is not None:
                payload["last_evidence_id"] = evidence.id
        return payload

    @staticmethod
    def _resolve_capability_name(
        *,
        task: KernelTask,
        evidence: EvidenceRecord,
    ) -> str:
        metadata = dict(evidence.metadata or {})
        capability_name = SurfaceCapabilityService._non_empty_str(
            metadata.get("candidate_capability"),
            metadata.get("target_slot"),
            metadata.get("capability_name"),
            task.capability_ref,
        )
        if capability_name is None:
            return "surface_action"
        return capability_name.replace("tool:", "").strip()

    @staticmethod
    def _latest_datetime(values: list[datetime | None]) -> datetime | None:
        candidates = [value for value in values if value is not None]
        return max(candidates) if candidates else None

    @staticmethod
    def _merge_texts(*values: object) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value is None:
                continue
            items = value if isinstance(value, list) else [value]
            for item in items:
                text = str(item or "").strip()
                if not text:
                    continue
                lowered = text.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                merged.append(text)
        return merged

    @staticmethod
    def _non_empty_str(*values: object) -> str | None:
        for value in values:
            if not isinstance(value, str):
                continue
            candidate = value.strip()
            if candidate:
                return candidate
        return None


__all__ = [
    "SurfaceCapabilityService",
    "SurfaceLearningScopeContext",
]
