# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import re
from typing import Any

from ..state import MemoryContinuityDetailRecord

_DETAIL_TOKEN_RE = re.compile(r"[^a-z0-9]+")
_STRONG_HINTS = ("must", "cannot", "never", "blocker", "risk", "proof", "constraint")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_detail_key(value: object | None) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    return _DETAIL_TOKEN_RE.sub("-", raw).strip("-")


def _detail_label(detail_key: str) -> str:
    return str(detail_key or "").replace("-", " ").strip().title()


def _detail_id(*, scope_type: str, scope_id: str, detail_key: str) -> str:
    return f"continuity:{scope_type}:{scope_id}:{detail_key}"


def _dedupe_texts(values: list[str]) -> list[str]:
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


@dataclass(slots=True)
class ContinuityDetailSelectionResult:
    selected_details: list[MemoryContinuityDetailRecord] = field(default_factory=list)
    pinned_details: list[MemoryContinuityDetailRecord] = field(default_factory=list)


class ContinuityDetailService:
    """Persist and surface continuity anchors that must survive later rounds."""

    def __init__(
        self,
        *,
        repository,
        selection_limit: int = 6,
    ) -> None:
        self._repository = repository
        self._selection_limit = max(1, int(selection_limit or 1))

    def upsert_manual_pin(
        self,
        *,
        scope_type: str,
        scope_id: str,
        detail_key: str,
        detail_text: str,
        industry_instance_id: str | None = None,
        work_context_id: str | None = None,
        pinned_until_phase: str | None = None,
        detail_label: str | None = None,
    ) -> MemoryContinuityDetailRecord:
        normalized_key = _normalize_detail_key(detail_key)
        if not normalized_key:
            raise ValueError("detail_key is required")
        now = _utc_now()
        existing = self._find_existing(scope_type=scope_type, scope_id=scope_id, detail_key=normalized_key)
        record = (existing or MemoryContinuityDetailRecord(
            detail_id=_detail_id(scope_type=scope_type, scope_id=scope_id, detail_key=normalized_key),
            scope_type=scope_type,
            scope_id=scope_id,
            industry_instance_id=industry_instance_id,
            work_context_id=work_context_id,
            detail_key=normalized_key,
            detail_label=detail_label or _detail_label(normalized_key),
            detail_text=detail_text,
            source_kind="manual",
            source_ref="manual-pin",
            pinned=True,
            pinned_until_phase=pinned_until_phase,
            status="active",
        )).model_copy(
            update={
                "industry_instance_id": industry_instance_id or getattr(existing, "industry_instance_id", None),
                "work_context_id": work_context_id or getattr(existing, "work_context_id", None),
                "detail_label": detail_label or _detail_label(normalized_key),
                "detail_text": str(detail_text or "").strip(),
                "source_kind": "manual",
                "source_ref": "manual-pin",
                "pinned": True,
                "pinned_until_phase": pinned_until_phase,
                "status": "active",
                "updated_at": now,
                "metadata": {
                    **dict(getattr(existing, "metadata", {}) or {}),
                    "manual_pin": True,
                },
            }
        )
        return self._repository.upsert_continuity_detail(record)

    def select_strong_details(
        self,
        *,
        scope_type: str,
        scope_id: str,
        graph_signals: dict[str, Any] | None,
        candidate_details: list[dict[str, Any] | str] | None = None,
        industry_instance_id: str | None = None,
        work_context_id: str | None = None,
        persist: bool = False,
        source_kind: str = "model",
    ) -> ContinuityDetailSelectionResult:
        pinned_details = self._repository.list_continuity_details(
            scope_type=scope_type,
            scope_id=scope_id,
            status="active",
            pinned_only=True,
            limit=None,
        )
        selection = ContinuityDetailSelectionResult(
            selected_details=list(pinned_details),
            pinned_details=list(pinned_details),
        )
        if len(selection.selected_details) >= self._selection_limit:
            return selection

        candidates: list[tuple[str, str]] = []
        for item in list(candidate_details or []):
            if isinstance(item, dict):
                detail_key = _normalize_detail_key(item.get("detail_key") or item.get("key"))
                detail_text = str(item.get("detail_text") or item.get("text") or "").strip()
            else:
                detail_text = str(item or "").strip()
                detail_key = _normalize_detail_key(detail_text[:48])
            if detail_key and detail_text:
                candidates.append((detail_key, detail_text))

        mapping = dict(graph_signals or {})
        for value in [
            *list(mapping.get("continuity_anchors") or []),
            *list(mapping.get("top_relations") or []),
            *list(mapping.get("blocker_paths") or []),
            *list(mapping.get("dependency_paths") or []),
        ]:
            text = str(value or "").strip()
            if not text:
                continue
            if not any(hint in text.lower() for hint in _STRONG_HINTS):
                continue
            detail_key = _normalize_detail_key(text[:48])
            if detail_key:
                candidates.append((detail_key, text))

        selected_keys = {item.detail_key for item in selection.selected_details}
        now = _utc_now()
        for detail_key, detail_text in candidates:
            if detail_key in selected_keys:
                continue
            existing = self._find_existing(scope_type=scope_type, scope_id=scope_id, detail_key=detail_key)
            record = existing
            if persist:
                record = self._repository.upsert_continuity_detail(
                    (existing or MemoryContinuityDetailRecord(
                        detail_id=_detail_id(scope_type=scope_type, scope_id=scope_id, detail_key=detail_key),
                        scope_type=scope_type,
                        scope_id=scope_id,
                        industry_instance_id=industry_instance_id,
                        work_context_id=work_context_id,
                        detail_key=detail_key,
                        detail_label=_detail_label(detail_key),
                        detail_text=detail_text,
                        source_kind=source_kind,
                        source_ref=f"{source_kind}:{scope_id}",
                        status="active",
                    )).model_copy(
                        update={
                            "industry_instance_id": industry_instance_id or getattr(existing, "industry_instance_id", None),
                            "work_context_id": work_context_id or getattr(existing, "work_context_id", None),
                            "detail_label": _detail_label(detail_key),
                            "detail_text": detail_text,
                            "source_kind": source_kind,
                            "source_ref": f"{source_kind}:{scope_id}",
                            "importance_score": max(float(getattr(existing, "importance_score", 0.0) or 0.0), 0.75),
                            "status": "active",
                            "updated_at": now,
                        }
                    )
                )
            if record is None:
                record = MemoryContinuityDetailRecord(
                    detail_id=_detail_id(scope_type=scope_type, scope_id=scope_id, detail_key=detail_key),
                    scope_type=scope_type,
                    scope_id=scope_id,
                    industry_instance_id=industry_instance_id,
                    work_context_id=work_context_id,
                    detail_key=detail_key,
                    detail_label=_detail_label(detail_key),
                    detail_text=detail_text,
                    source_kind=source_kind,
                    source_ref=f"{source_kind}:{scope_id}",
                    importance_score=0.75,
                    status="active",
                )
            selection.selected_details.append(record)
            selected_keys.add(detail_key)
            if len(selection.selected_details) >= self._selection_limit:
                break

        return selection

    def _find_existing(
        self,
        *,
        scope_type: str,
        scope_id: str,
        detail_key: str,
    ) -> MemoryContinuityDetailRecord | None:
        records = self._repository.list_continuity_details(
            scope_type=scope_type,
            scope_id=scope_id,
            detail_key=detail_key,
            limit=1,
        )
        return records[0] if records else None
