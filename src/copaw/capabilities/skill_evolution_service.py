# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object | None) -> list[str]:
    if not isinstance(value, list):
        return []
    resolved: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _string(item)
        if text is None:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        resolved.append(text)
    return resolved


def _candidate_is_reusable(candidate: object) -> bool:
    status = (_string(getattr(candidate, "status", None)) or "").lower()
    lifecycle_stage = (_string(getattr(candidate, "lifecycle_stage", None)) or "").lower()
    return status in {"active", "candidate", "trial"} or lifecycle_stage in {
        "active",
        "baseline",
        "trial",
    }


def _infer_package_form(
    *,
    candidate_kind: object | None,
    target_capability_ids: list[str] | None = None,
) -> str:
    normalized_kind = (_string(candidate_kind) or "skill").lower()
    capability_ids = _string_list(target_capability_ids)
    if normalized_kind == "mcp-bundle":
        return "mcp-bundle"
    if capability_ids and all(item.startswith("mcp:") for item in capability_ids):
        return "mcp-bundle"
    return normalized_kind or "skill"


class SkillEvolutionService:
    def __init__(
        self,
        *,
        candidate_service: object | None = None,
        donor_package_service: object | None = None,
    ) -> None:
        self._candidate_service = candidate_service
        self._donor_package_service = donor_package_service

    def resolve_candidate_path(
        self,
        *,
        candidate_kind: str,
        candidate_source_kind: str,
        candidate_source_ref: str | None,
        candidate_source_version: str | None,
        canonical_package_id: str | None = None,
        target_scope: str,
        target_role_id: str | None,
        target_seat_ref: str | None,
        target_capability_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        package_form = _infer_package_form(
            candidate_kind=candidate_kind,
            target_capability_ids=target_capability_ids,
        )
        reusable = self._find_reusable_candidate(
            candidate_source_ref=candidate_source_ref,
            candidate_source_version=candidate_source_version,
            canonical_package_id=canonical_package_id,
            target_scope=target_scope,
            target_role_id=target_role_id,
            target_seat_ref=target_seat_ref,
        )
        if reusable is not None:
            return {
                "resolution_kind": "reuse_existing_candidate",
                "selected_candidate_id": _string(getattr(reusable, "candidate_id", None)),
                "selected_donor_id": _string(getattr(reusable, "donor_id", None)),
                "selected_package_id": _string(getattr(reusable, "package_id", None)),
                "selected_scope": _string(getattr(reusable, "target_scope", None)),
                "package_form": package_form,
                "fallback_required": False,
            }

        reusable_package = self._find_reusable_package(
            candidate_source_ref=candidate_source_ref,
            candidate_source_version=candidate_source_version,
            canonical_package_id=canonical_package_id,
        )
        if reusable_package is not None:
            return {
                "resolution_kind": "adopt_registered_package",
                "selected_candidate_id": None,
                "selected_donor_id": _string(getattr(reusable_package, "donor_id", None)),
                "selected_package_id": _string(getattr(reusable_package, "package_id", None)),
                "selected_scope": target_scope,
                "package_form": package_form,
                "fallback_required": False,
            }

        normalized_source_kind = (_string(candidate_source_kind) or "local_authored").lower()
        if normalized_source_kind != "local_authored":
            return {
                "resolution_kind": "adopt_external_donor",
                "selected_candidate_id": None,
                "selected_donor_id": None,
                "selected_package_id": None,
                "selected_scope": target_scope,
                "package_form": package_form,
                "fallback_required": False,
            }

        return {
            "resolution_kind": "author_local_fallback",
            "selected_candidate_id": None,
            "selected_donor_id": None,
            "selected_package_id": None,
            "selected_scope": target_scope,
            "package_form": package_form,
            "fallback_required": True,
        }

    def _find_reusable_candidate(
        self,
        *,
        candidate_source_ref: str | None,
        candidate_source_version: str | None,
        canonical_package_id: str | None,
        target_scope: str,
        target_role_id: str | None,
        target_seat_ref: str | None,
    ) -> object | None:
        lister = getattr(self._candidate_service, "list_candidates", None)
        if not callable(lister):
            return None
        source_ref = _string(candidate_source_ref)
        source_version = _string(candidate_source_version)
        normalized_canonical = _string(canonical_package_id)
        for item in lister(limit=None):
            if not _candidate_is_reusable(item):
                continue
            if (_string(getattr(item, "target_scope", None)) or "seat") != target_scope:
                continue
            if _string(getattr(item, "target_role_id", None)) != _string(target_role_id):
                continue
            if _string(getattr(item, "target_seat_ref", None)) != _string(target_seat_ref):
                continue
            if normalized_canonical and _string(getattr(item, "canonical_package_id", None)) == normalized_canonical:
                return item
            if (
                _string(getattr(item, "candidate_source_ref", None)) == source_ref
                and _string(getattr(item, "candidate_source_version", None)) == source_version
            ):
                return item
        return None

    def _find_reusable_package(
        self,
        *,
        candidate_source_ref: str | None,
        candidate_source_version: str | None,
        canonical_package_id: str | None,
    ) -> object | None:
        finder = getattr(self._donor_package_service, "find_reusable_package", None)
        if not callable(finder):
            return None
        return finder(
            canonical_package_id=canonical_package_id,
            package_ref=candidate_source_ref,
            package_version=candidate_source_version,
        )


__all__ = ["SkillEvolutionService"]
