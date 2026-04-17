# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re

from ..state import (
    IndustryMemoryProfileRecord,
    MemoryStructureProposalRecord,
    WorkContextMemoryOverlayRecord,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _first_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _tokens(value: object | None) -> set[str]:
    return {token for token in _TOKEN_RE.findall(str(value or "").lower()) if len(token) > 1}


def _dedupe(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(text)
    return ordered


def _proposal_metadata(base: dict[str, object] | None, *, proposal_id: str, applied_at: datetime) -> dict[str, object]:
    metadata = dict(base or {})
    applied_ids = _dedupe(
        [*list(metadata.get("applied_proposal_ids") or []), proposal_id],
    )
    metadata["applied_proposal_ids"] = applied_ids
    metadata["last_applied_proposal_id"] = proposal_id
    metadata["last_applied_at"] = applied_at.isoformat()
    return metadata


def _prioritize_entries(entries: list[str], proposal: MemoryStructureProposalRecord) -> list[str]:
    proposal_text = " ".join(
        [
            str(proposal.title or ""),
            str(proposal.summary or ""),
            str(proposal.recommended_action or ""),
        ]
    ).lower()
    proposal_tokens = _tokens(proposal_text)
    if not proposal_text:
        return list(entries)

    scored: list[tuple[int, int, str]] = []
    for index, entry in enumerate(list(entries or [])):
        text = str(entry or "").strip()
        if not text:
            continue
        lowered = text.lower()
        entry_tokens = _tokens(lowered)
        score = 0
        if lowered and lowered in proposal_text:
            score += 10
        if entry_tokens:
            score += len(entry_tokens.intersection(proposal_tokens)) * 3
        if "top" in proposal_text or "primary" in proposal_text or "first" in proposal_text:
            score += 2 if entry_tokens.intersection({"top", "primary", "first"}) else 0
        scored.append((-score, index, text))
    scored.sort()
    return [text for _score, _index, text in scored]


@dataclass(slots=True)
class StructureProposalExecutionResult:
    proposal: MemoryStructureProposalRecord
    applied_profile: IndustryMemoryProfileRecord | None = None
    applied_overlay: WorkContextMemoryOverlayRecord | None = None


class StructureProposalExecutor:
    """Materialize accepted memory structure proposals into new active truth records."""

    def __init__(self, *, repository) -> None:
        self._repository = repository

    def apply(
        self,
        proposal: MemoryStructureProposalRecord,
        *,
        decided_by: str | None = None,
        note: str | None = None,
    ) -> StructureProposalExecutionResult:
        now = _utc_now()
        applied_profile: IndustryMemoryProfileRecord | None = None
        applied_overlay: WorkContextMemoryOverlayRecord | None = None

        if proposal.scope_type == "industry":
            applied_profile = self._apply_industry_profile(proposal, applied_at=now)
        elif proposal.scope_type == "work_context":
            applied_overlay = self._apply_work_context_overlay(proposal, applied_at=now)

        metadata = dict(proposal.metadata or {})
        metadata["decision"] = "accepted"
        metadata["decided_by"] = str(decided_by or "").strip() or None
        metadata["decision_note"] = str(note or "").strip() or None
        metadata["decided_at"] = now.isoformat()
        metadata["applied_at"] = now.isoformat()
        if applied_profile is not None:
            metadata["applied_profile_id"] = applied_profile.profile_id
        if applied_overlay is not None:
            metadata["applied_overlay_id"] = applied_overlay.overlay_id

        persisted = self._repository.upsert_structure_proposal(
            proposal.model_copy(
                update={
                    "status": "accepted",
                    "candidate_profile_id": applied_profile.profile_id if applied_profile is not None else proposal.candidate_profile_id,
                    "candidate_overlay_id": applied_overlay.overlay_id if applied_overlay is not None else proposal.candidate_overlay_id,
                    "metadata": metadata,
                    "updated_at": now,
                }
            )
        )
        return StructureProposalExecutionResult(
            proposal=persisted,
            applied_profile=applied_profile,
            applied_overlay=applied_overlay,
        )

    def _apply_industry_profile(
        self,
        proposal: MemoryStructureProposalRecord,
        *,
        applied_at: datetime,
    ) -> IndustryMemoryProfileRecord:
        industry_instance_id = str(proposal.industry_instance_id or proposal.scope_id or "").strip()
        current = self._repository.get_active_industry_profile(industry_instance_id)
        if current is None:
            raise KeyError(industry_instance_id)
        version = len(self._repository.list_industry_profiles(industry_instance_id=industry_instance_id, limit=None)) + 1
        prioritized_constraints = _prioritize_entries(list(current.active_constraints or []), proposal)
        prioritized_focuses = _prioritize_entries(list(current.active_focuses or []), proposal)
        prioritized_relations = _prioritize_entries(list(current.key_relations or []), proposal)
        return self._repository.upsert_industry_profile(
            current.model_copy(
                update={
                    "profile_id": f"industry-profile:{industry_instance_id}:v{version}",
                    "strategic_direction": _first_text(
                        prioritized_focuses[0] if prioritized_focuses else None,
                        current.strategic_direction,
                        current.headline,
                    ),
                    "active_constraints": prioritized_constraints,
                    "active_focuses": prioritized_focuses,
                    "key_relations": prioritized_relations,
                    "version": version,
                    "status": "active",
                    "created_at": applied_at,
                    "updated_at": applied_at,
                    "metadata": _proposal_metadata(
                        current.metadata,
                        proposal_id=proposal.proposal_id,
                        applied_at=applied_at,
                    ),
                }
            )
        )

    def _apply_work_context_overlay(
        self,
        proposal: MemoryStructureProposalRecord,
        *,
        applied_at: datetime,
    ) -> WorkContextMemoryOverlayRecord:
        work_context_id = str(proposal.work_context_id or proposal.scope_id or "").strip()
        current = self._repository.get_active_work_context_overlay(work_context_id)
        if current is None:
            raise KeyError(work_context_id)
        version = len(self._repository.list_work_context_overlays(work_context_id=work_context_id, limit=None)) + 1
        prioritized_constraints = _prioritize_entries(list(current.active_constraints or []), proposal)
        prioritized_focuses = _prioritize_entries(list(current.active_focuses or []), proposal)
        prioritized_relations = _prioritize_entries(list(current.active_relations or []), proposal)
        focus_summary = _first_text(
            prioritized_focuses[0] if prioritized_focuses else None,
            current.focus_summary,
            current.summary,
        )
        return self._repository.upsert_work_context_overlay(
            current.model_copy(
                update={
                    "overlay_id": f"overlay:{work_context_id}:v{version}",
                    "focus_summary": focus_summary,
                    "active_constraints": prioritized_constraints,
                    "active_focuses": prioritized_focuses,
                    "active_relations": prioritized_relations,
                    "version": version,
                    "status": "active",
                    "created_at": applied_at,
                    "updated_at": applied_at,
                    "metadata": _proposal_metadata(
                        current.metadata,
                        proposal_id=proposal.proposal_id,
                        applied_at=applied_at,
                    ),
                }
            )
        )
