# -*- coding: utf-8 -*-
"""SQLite persistence for the learning layer."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import (
    CapabilityAcquisitionProposal,
    GrowthEvent,
    InstallBindingPlan,
    OnboardingRun,
    Patch,
    Proposal,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_proposals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    source_agent_id TEXT NOT NULL,
    target_layer TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_learning_proposals_status_created_at
    ON learning_proposals(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_proposals_created_at
    ON learning_proposals(created_at DESC);

CREATE TABLE IF NOT EXISTS learning_patches (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    proposal_id TEXT,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    created_at TEXT NOT NULL,
    applied_at TEXT,
    applied_by TEXT,
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    source_evidence_id TEXT,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_learning_patches_status_created_at
    ON learning_patches(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_patches_created_at
    ON learning_patches(created_at DESC);

CREATE TABLE IF NOT EXISTS learning_growth_events (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    source_patch_id TEXT,
    source_evidence_id TEXT,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_learning_growth_agent_created_at
    ON learning_growth_events(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_growth_created_at
    ON learning_growth_events(created_at DESC);

CREATE TABLE IF NOT EXISTS learning_acquisition_proposals (
    id TEXT PRIMARY KEY,
    proposal_key TEXT NOT NULL UNIQUE,
    acquisition_kind TEXT NOT NULL,
    industry_instance_id TEXT NOT NULL,
    target_agent_id TEXT,
    target_role_id TEXT,
    status TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_learning_acq_proposals_instance_status
    ON learning_acquisition_proposals(industry_instance_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_acq_proposals_target
    ON learning_acquisition_proposals(target_agent_id, target_role_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS learning_install_binding_plans (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    industry_instance_id TEXT NOT NULL,
    target_agent_id TEXT,
    target_role_id TEXT,
    status TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    binding_id TEXT,
    doctor_status TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    applied_at TEXT,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_learning_install_binding_plans_proposal
    ON learning_install_binding_plans(proposal_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_install_binding_plans_instance_status
    ON learning_install_binding_plans(industry_instance_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS learning_onboarding_runs (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    industry_instance_id TEXT NOT NULL,
    target_agent_id TEXT,
    target_role_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_learning_onboarding_runs_plan
    ON learning_onboarding_runs(plan_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_onboarding_runs_instance_status
    ON learning_onboarding_runs(industry_instance_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS learning_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_ref TEXT,
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    source_evidence_id TEXT,
    source_patch_id TEXT,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_learning_audit_entity_created_at
    ON learning_audit_log(entity_type, entity_id, created_at DESC);
"""


class LearningStorageError(RuntimeError):
    """Raised when learning persistence is unavailable."""


class SqliteLearningStore:
    """SQLite-backed storage for learning proposals, patches, and growth."""

    def __init__(self, database_path: str | Path) -> None:
        if str(database_path).strip() == ":memory:":
            raise LearningStorageError(
                "Learning storage must be persistent; ':memory:' is not allowed.",
            )
        self._database_path = Path(database_path).expanduser().resolve()
        self._schema_verified = False
        try:
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
            with self.connection() as conn:
                _ensure_learning_schema_ready(conn)
                self._schema_verified = True
        except (OSError, sqlite3.Error) as exc:
            raise LearningStorageError(
                f"Unable to initialize learning storage at '{self._database_path}': {exc}",
            ) from exc

    @property
    def database_path(self) -> Path:
        return self._database_path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        try:
            schema_check_required = (
                not self._schema_verified
                or not self._database_path.exists()
                or self._database_path.stat().st_size == 0
            )
            conn = sqlite3.connect(self._database_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error as exc:
            raise LearningStorageError(
                f"Unable to open learning storage '{self._database_path}': {exc}",
            ) from exc
        try:
            if schema_check_required:
                _ensure_learning_schema_ready(conn)
                self._schema_verified = True
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_proposal(self, proposal: Proposal, *, action: str) -> Proposal:
        payload_json = _dump_model(proposal)
        try:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO learning_proposals (
                        id,
                        title,
                        status,
                        source_agent_id,
                        target_layer,
                        created_at,
                        evidence_refs_json,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title,
                        status = excluded.status,
                        source_agent_id = excluded.source_agent_id,
                        target_layer = excluded.target_layer,
                        created_at = excluded.created_at,
                        evidence_refs_json = excluded.evidence_refs_json,
                        payload_json = excluded.payload_json
                    """,
                    (
                        proposal.id,
                        proposal.title,
                        proposal.status,
                        proposal.source_agent_id,
                        proposal.target_layer,
                        _encode_datetime(proposal.created_at),
                        _encode_json(proposal.evidence_refs),
                        payload_json,
                    ),
                )
                self._append_audit(
                    conn,
                    entity_type="proposal",
                    entity_id=proposal.id,
                    action=action,
                    actor_ref=proposal.source_agent_id,
                    evidence_refs=proposal.evidence_refs,
                    source_evidence_id=None,
                    source_patch_id=None,
                    payload_json=payload_json,
                )
        except sqlite3.Error as exc:
            raise LearningStorageError(
                f"Unable to persist proposal '{proposal.id}': {exc}",
            ) from exc
        return proposal

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        row = self._fetch_one(
            "SELECT payload_json FROM learning_proposals WHERE id = ?",
            (proposal_id,),
        )
        return _load_model(Proposal, row["payload_json"]) if row is not None else None

    def list_proposals(
        self,
        *,
        status: str | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Proposal]:
        query = "SELECT payload_json FROM learning_proposals"
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if created_since is not None:
            clauses.append("created_at >= ?")
            params.append(_encode_datetime(created_since))
        if clauses:
            query += f" WHERE {' AND '.join(clauses)}"
        query += " ORDER BY created_at DESC, rowid DESC"
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params.append(limit)
        rows = self._fetch_all(query, tuple(params))
        return [_load_model(Proposal, row["payload_json"]) for row in rows]

    def delete_proposal(self, proposal_id: str) -> bool:
        return self._delete_entity(
            table_name="learning_proposals",
            entity_type="proposal",
            entity_id=proposal_id,
        )

    def save_patch(self, patch: Patch, *, action: str) -> Patch:
        payload_json = _dump_model(patch)
        try:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO learning_patches (
                        id,
                        kind,
                        proposal_id,
                        title,
                        status,
                        risk_level,
                        created_at,
                        applied_at,
                        applied_by,
                        evidence_refs_json,
                        source_evidence_id,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        kind = excluded.kind,
                        proposal_id = excluded.proposal_id,
                        title = excluded.title,
                        status = excluded.status,
                        risk_level = excluded.risk_level,
                        created_at = excluded.created_at,
                        applied_at = excluded.applied_at,
                        applied_by = excluded.applied_by,
                        evidence_refs_json = excluded.evidence_refs_json,
                        source_evidence_id = excluded.source_evidence_id,
                        payload_json = excluded.payload_json
                    """,
                    (
                        patch.id,
                        patch.kind,
                        patch.proposal_id,
                        patch.title,
                        patch.status,
                        patch.risk_level,
                        _encode_datetime(patch.created_at),
                        _encode_optional_datetime(patch.applied_at),
                        patch.applied_by,
                        _encode_json(patch.evidence_refs),
                        patch.source_evidence_id,
                        payload_json,
                    ),
                )
                self._append_audit(
                    conn,
                    entity_type="patch",
                    entity_id=patch.id,
                    action=action,
                    actor_ref=patch.applied_by,
                    evidence_refs=patch.evidence_refs,
                    source_evidence_id=patch.source_evidence_id,
                    source_patch_id=patch.id,
                    payload_json=payload_json,
                )
        except sqlite3.Error as exc:
            raise LearningStorageError(
                f"Unable to persist patch '{patch.id}': {exc}",
            ) from exc
        return patch

    def get_patch(self, patch_id: str) -> Patch | None:
        row = self._fetch_one(
            "SELECT payload_json FROM learning_patches WHERE id = ?",
            (patch_id,),
        )
        return _load_model(Patch, row["payload_json"]) if row is not None else None

    def list_patches(
        self,
        *,
        status: str | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Patch]:
        query = "SELECT payload_json FROM learning_patches"
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if created_since is not None:
            clauses.append("created_at >= ?")
            params.append(_encode_datetime(created_since))
        if clauses:
            query += f" WHERE {' AND '.join(clauses)}"
        query += " ORDER BY created_at DESC, rowid DESC"
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params.append(limit)
        rows = self._fetch_all(query, tuple(params))
        return [_load_model(Patch, row["payload_json"]) for row in rows]

    def delete_patch(self, patch_id: str) -> bool:
        return self._delete_entity(
            table_name="learning_patches",
            entity_type="patch",
            entity_id=patch_id,
        )

    def save_growth_event(
        self,
        event: GrowthEvent,
        *,
        action: str,
    ) -> GrowthEvent:
        payload_json = _dump_model(event)
        try:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO learning_growth_events (
                        id,
                        agent_id,
                        change_type,
                        risk_level,
                        source_patch_id,
                        source_evidence_id,
                        created_at,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        agent_id = excluded.agent_id,
                        change_type = excluded.change_type,
                        risk_level = excluded.risk_level,
                        source_patch_id = excluded.source_patch_id,
                        source_evidence_id = excluded.source_evidence_id,
                        created_at = excluded.created_at,
                        payload_json = excluded.payload_json
                    """,
                    (
                        event.id,
                        event.agent_id,
                        event.change_type,
                        event.risk_level,
                        event.source_patch_id,
                        event.source_evidence_id,
                        _encode_datetime(event.created_at),
                        payload_json,
                    ),
                )
                self._append_audit(
                    conn,
                    entity_type="growth",
                    entity_id=event.id,
                    action=action,
                    actor_ref=event.agent_id,
                    evidence_refs=[],
                    source_evidence_id=event.source_evidence_id,
                    source_patch_id=event.source_patch_id,
                    payload_json=payload_json,
                )
        except sqlite3.Error as exc:
            raise LearningStorageError(
                f"Unable to persist growth event '{event.id}': {exc}",
            ) from exc
        return event

    def get_growth_event(self, event_id: str) -> GrowthEvent | None:
        row = self._fetch_one(
            "SELECT payload_json FROM learning_growth_events WHERE id = ?",
            (event_id,),
        )
        return _load_model(GrowthEvent, row["payload_json"]) if row is not None else None

    def list_growth_events(
        self,
        *,
        agent_id: str | None = None,
        created_since: datetime | None = None,
        limit: int | None = 50,
    ) -> list[GrowthEvent]:
        query = "SELECT payload_json FROM learning_growth_events"
        clauses: list[str] = []
        params: list[Any] = []
        if agent_id:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if created_since is not None:
            clauses.append("created_at >= ?")
            params.append(_encode_datetime(created_since))
        if clauses:
            query += f" WHERE {' AND '.join(clauses)}"
        query += " ORDER BY created_at DESC, rowid DESC"
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params.append(limit)
        rows = self._fetch_all(query, tuple(params))
        return [_load_model(GrowthEvent, row["payload_json"]) for row in rows]

    def delete_growth_event(self, event_id: str) -> bool:
        return self._delete_entity(
            table_name="learning_growth_events",
            entity_type="growth",
            entity_id=event_id,
        )

    def save_acquisition_proposal(
        self,
        proposal: CapabilityAcquisitionProposal,
        *,
        action: str,
    ) -> CapabilityAcquisitionProposal:
        payload_json = _dump_model(proposal)
        try:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO learning_acquisition_proposals (
                        id,
                        proposal_key,
                        acquisition_kind,
                        industry_instance_id,
                        target_agent_id,
                        target_role_id,
                        status,
                        risk_level,
                        created_at,
                        updated_at,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        proposal_key = excluded.proposal_key,
                        acquisition_kind = excluded.acquisition_kind,
                        industry_instance_id = excluded.industry_instance_id,
                        target_agent_id = excluded.target_agent_id,
                        target_role_id = excluded.target_role_id,
                        status = excluded.status,
                        risk_level = excluded.risk_level,
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at,
                        payload_json = excluded.payload_json
                    """,
                    (
                        proposal.id,
                        proposal.proposal_key,
                        proposal.acquisition_kind,
                        proposal.industry_instance_id,
                        proposal.target_agent_id,
                        proposal.target_role_id,
                        proposal.status,
                        proposal.risk_level,
                        _encode_datetime(proposal.created_at),
                        _encode_datetime(proposal.updated_at),
                        payload_json,
                    ),
                )
                self._append_audit(
                    conn,
                    entity_type="acquisition-proposal",
                    entity_id=proposal.id,
                    action=action,
                    actor_ref=proposal.target_agent_id,
                    evidence_refs=proposal.evidence_refs,
                    source_evidence_id=proposal.evidence_refs[0] if proposal.evidence_refs else None,
                    source_patch_id=None,
                    payload_json=payload_json,
                )
        except sqlite3.Error as exc:
            raise LearningStorageError(
                f"Unable to persist acquisition proposal '{proposal.id}': {exc}",
            ) from exc
        return proposal

    def get_acquisition_proposal(
        self,
        proposal_id: str,
    ) -> CapabilityAcquisitionProposal | None:
        row = self._fetch_one(
            "SELECT payload_json FROM learning_acquisition_proposals WHERE id = ?",
            (proposal_id,),
        )
        if row is None:
            return None
        return _load_model(CapabilityAcquisitionProposal, row["payload_json"])

    def list_acquisition_proposals(
        self,
        *,
        industry_instance_id: str | None = None,
        status: str | None = None,
        target_agent_id: str | None = None,
        target_role_id: str | None = None,
        acquisition_kind: str | None = None,
        limit: int | None = None,
    ) -> list[CapabilityAcquisitionProposal]:
        query = "SELECT payload_json FROM learning_acquisition_proposals"
        clauses: list[str] = []
        params: list[Any] = []
        if industry_instance_id:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if target_agent_id:
            clauses.append("target_agent_id = ?")
            params.append(target_agent_id)
        if target_role_id:
            clauses.append("target_role_id = ?")
            params.append(target_role_id)
        if acquisition_kind:
            clauses.append("acquisition_kind = ?")
            params.append(acquisition_kind)
        if clauses:
            query += f" WHERE {' AND '.join(clauses)}"
        query += " ORDER BY updated_at DESC, rowid DESC"
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params.append(limit)
        rows = self._fetch_all(query, tuple(params))
        return [
            _load_model(CapabilityAcquisitionProposal, row["payload_json"])
            for row in rows
        ]

    def delete_acquisition_proposal(self, proposal_id: str) -> bool:
        return self._delete_entity(
            table_name="learning_acquisition_proposals",
            entity_type="acquisition-proposal",
            entity_id=proposal_id,
        )

    def save_install_binding_plan(
        self,
        plan: InstallBindingPlan,
        *,
        action: str,
    ) -> InstallBindingPlan:
        payload_json = _dump_model(plan)
        try:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO learning_install_binding_plans (
                        id,
                        proposal_id,
                        industry_instance_id,
                        target_agent_id,
                        target_role_id,
                        status,
                        risk_level,
                        binding_id,
                        doctor_status,
                        created_at,
                        updated_at,
                        applied_at,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        proposal_id = excluded.proposal_id,
                        industry_instance_id = excluded.industry_instance_id,
                        target_agent_id = excluded.target_agent_id,
                        target_role_id = excluded.target_role_id,
                        status = excluded.status,
                        risk_level = excluded.risk_level,
                        binding_id = excluded.binding_id,
                        doctor_status = excluded.doctor_status,
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at,
                        applied_at = excluded.applied_at,
                        payload_json = excluded.payload_json
                    """,
                    (
                        plan.id,
                        plan.proposal_id,
                        plan.industry_instance_id,
                        plan.target_agent_id,
                        plan.target_role_id,
                        plan.status,
                        plan.risk_level,
                        plan.binding_id,
                        plan.doctor_status,
                        _encode_datetime(plan.created_at),
                        _encode_datetime(plan.updated_at),
                        _encode_optional_datetime(plan.applied_at),
                        payload_json,
                    ),
                )
                self._append_audit(
                    conn,
                    entity_type="install-binding-plan",
                    entity_id=plan.id,
                    action=action,
                    actor_ref=plan.target_agent_id,
                    evidence_refs=plan.evidence_refs,
                    source_evidence_id=plan.evidence_refs[0] if plan.evidence_refs else None,
                    source_patch_id=None,
                    payload_json=payload_json,
                )
        except sqlite3.Error as exc:
            raise LearningStorageError(
                f"Unable to persist install/binding plan '{plan.id}': {exc}",
            ) from exc
        return plan

    def get_install_binding_plan(self, plan_id: str) -> InstallBindingPlan | None:
        row = self._fetch_one(
            "SELECT payload_json FROM learning_install_binding_plans WHERE id = ?",
            (plan_id,),
        )
        return _load_model(InstallBindingPlan, row["payload_json"]) if row is not None else None

    def list_install_binding_plans(
        self,
        *,
        proposal_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        target_agent_id: str | None = None,
        target_role_id: str | None = None,
        limit: int | None = None,
    ) -> list[InstallBindingPlan]:
        query = "SELECT payload_json FROM learning_install_binding_plans"
        clauses: list[str] = []
        params: list[Any] = []
        if proposal_id:
            clauses.append("proposal_id = ?")
            params.append(proposal_id)
        if industry_instance_id:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if target_agent_id:
            clauses.append("target_agent_id = ?")
            params.append(target_agent_id)
        if target_role_id:
            clauses.append("target_role_id = ?")
            params.append(target_role_id)
        if clauses:
            query += f" WHERE {' AND '.join(clauses)}"
        query += " ORDER BY updated_at DESC, rowid DESC"
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params.append(limit)
        rows = self._fetch_all(query, tuple(params))
        return [_load_model(InstallBindingPlan, row["payload_json"]) for row in rows]

    def delete_install_binding_plan(self, plan_id: str) -> bool:
        return self._delete_entity(
            table_name="learning_install_binding_plans",
            entity_type="install-binding-plan",
            entity_id=plan_id,
        )

    def save_onboarding_run(
        self,
        run: OnboardingRun,
        *,
        action: str,
    ) -> OnboardingRun:
        payload_json = _dump_model(run)
        try:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO learning_onboarding_runs (
                        id,
                        plan_id,
                        proposal_id,
                        industry_instance_id,
                        target_agent_id,
                        target_role_id,
                        status,
                        created_at,
                        updated_at,
                        completed_at,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        plan_id = excluded.plan_id,
                        proposal_id = excluded.proposal_id,
                        industry_instance_id = excluded.industry_instance_id,
                        target_agent_id = excluded.target_agent_id,
                        target_role_id = excluded.target_role_id,
                        status = excluded.status,
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at,
                        completed_at = excluded.completed_at,
                        payload_json = excluded.payload_json
                    """,
                    (
                        run.id,
                        run.plan_id,
                        run.proposal_id,
                        run.industry_instance_id,
                        run.target_agent_id,
                        run.target_role_id,
                        run.status,
                        _encode_datetime(run.created_at),
                        _encode_datetime(run.updated_at),
                        _encode_optional_datetime(run.completed_at),
                        payload_json,
                    ),
                )
                self._append_audit(
                    conn,
                    entity_type="onboarding-run",
                    entity_id=run.id,
                    action=action,
                    actor_ref=run.target_agent_id,
                    evidence_refs=run.evidence_refs,
                    source_evidence_id=run.evidence_refs[0] if run.evidence_refs else None,
                    source_patch_id=None,
                    payload_json=payload_json,
                )
        except sqlite3.Error as exc:
            raise LearningStorageError(
                f"Unable to persist onboarding run '{run.id}': {exc}",
            ) from exc
        return run

    def get_onboarding_run(self, run_id: str) -> OnboardingRun | None:
        row = self._fetch_one(
            "SELECT payload_json FROM learning_onboarding_runs WHERE id = ?",
            (run_id,),
        )
        return _load_model(OnboardingRun, row["payload_json"]) if row is not None else None

    def list_onboarding_runs(
        self,
        *,
        plan_id: str | None = None,
        proposal_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        target_agent_id: str | None = None,
        target_role_id: str | None = None,
        limit: int | None = None,
    ) -> list[OnboardingRun]:
        query = "SELECT payload_json FROM learning_onboarding_runs"
        clauses: list[str] = []
        params: list[Any] = []
        if plan_id:
            clauses.append("plan_id = ?")
            params.append(plan_id)
        if proposal_id:
            clauses.append("proposal_id = ?")
            params.append(proposal_id)
        if industry_instance_id:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if target_agent_id:
            clauses.append("target_agent_id = ?")
            params.append(target_agent_id)
        if target_role_id:
            clauses.append("target_role_id = ?")
            params.append(target_role_id)
        if clauses:
            query += f" WHERE {' AND '.join(clauses)}"
        query += " ORDER BY updated_at DESC, rowid DESC"
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params.append(limit)
        rows = self._fetch_all(query, tuple(params))
        return [_load_model(OnboardingRun, row["payload_json"]) for row in rows]

    def delete_onboarding_run(self, run_id: str) -> bool:
        return self._delete_entity(
            table_name="learning_onboarding_runs",
            entity_type="onboarding-run",
            entity_id=run_id,
        )

    def _fetch_one(
        self,
        query: str,
        params: tuple[Any, ...],
    ) -> sqlite3.Row | None:
        try:
            with self.connection() as conn:
                return conn.execute(query, params).fetchone()
        except sqlite3.Error as exc:
            raise LearningStorageError(
                f"Unable to read from learning storage '{self._database_path}': {exc}",
            ) from exc

    def _fetch_all(
        self,
        query: str,
        params: tuple[Any, ...],
    ) -> list[sqlite3.Row]:
        try:
            with self.connection() as conn:
                rows = conn.execute(query, params).fetchall()
        except sqlite3.Error as exc:
            raise LearningStorageError(
                f"Unable to read from learning storage '{self._database_path}': {exc}",
            ) from exc
        return list(rows)

    def _append_audit(
        self,
        conn: sqlite3.Connection,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_ref: str | None,
        evidence_refs: list[str],
        source_evidence_id: str | None,
        source_patch_id: str | None,
        payload_json: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO learning_audit_log (
                entity_type,
                entity_id,
                action,
                actor_ref,
                evidence_refs_json,
                source_evidence_id,
                source_patch_id,
                created_at,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_type,
                entity_id,
                action,
                actor_ref,
                _encode_json(evidence_refs),
                source_evidence_id,
                source_patch_id,
                _encode_datetime(datetime.now(timezone.utc)),
                payload_json,
            ),
        )

    def _delete_entity(
        self,
        *,
        table_name: str,
        entity_type: str,
        entity_id: str,
    ) -> bool:
        normalized_entity_id = entity_id.strip() if isinstance(entity_id, str) else ""
        if not normalized_entity_id:
            return False
        try:
            with self.connection() as conn:
                cursor = conn.execute(
                    f"DELETE FROM {table_name} WHERE id = ?",
                    (normalized_entity_id,),
                )
                if int(cursor.rowcount or 0) <= 0:
                    return False
                conn.execute(
                    """
                    DELETE FROM learning_audit_log
                    WHERE entity_type = ? AND entity_id = ?
                    """,
                    (entity_type, normalized_entity_id),
                )
        except sqlite3.Error as exc:
            raise LearningStorageError(
                f"Unable to delete {entity_type} '{normalized_entity_id}': {exc}",
            ) from exc
        return True


def _ensure_learning_schema_ready(conn: sqlite3.Connection) -> None:
    existing_tables = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        ).fetchall()
    }
    required_tables = {
        "learning_proposals",
        "learning_patches",
        "learning_growth_events",
        "learning_acquisition_proposals",
        "learning_install_binding_plans",
        "learning_onboarding_runs",
        "learning_audit_log",
    }
    if required_tables.issubset(existing_tables):
        return
    conn.executescript(_SCHEMA)


def _dump_model(
    model: Proposal
    | Patch
    | GrowthEvent
    | CapabilityAcquisitionProposal
    | InstallBindingPlan
    | OnboardingRun,
) -> str:
    return json.dumps(model.model_dump(mode="json"), sort_keys=True)


def _load_model(
    model_type: type[Proposal]
    | type[Patch]
    | type[GrowthEvent]
    | type[CapabilityAcquisitionProposal]
    | type[InstallBindingPlan]
    | type[OnboardingRun],
    payload_json: str,
):
    payload = json.loads(payload_json)
    return model_type.model_validate(payload)


def _encode_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _encode_optional_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _encode_datetime(value)


def _encode_json(value: Any) -> str:
    return json.dumps(value or [], sort_keys=True)
