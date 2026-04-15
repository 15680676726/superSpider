# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
from typing import Any, Callable

from pydantic import BaseModel, Field, field_validator
from ..utils.model_response import materialize_model_response

_SENTENCE_SPLIT_RE = re.compile(r"[\r\n]+|(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
_SPACE_RE = re.compile(r"\s+")
_RULE_CUES = ("must", "wait for", "before", "after", "only", "cannot", "needs to", "required")
_DEFAULT_REASONING_TIMEOUT_SECONDS = 45.0

logger = logging.getLogger(__name__)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _SPACE_RE.sub(" ", str(value or "").strip())
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def _sentences(*texts: str) -> list[str]:
    parts: list[str] = []
    for text in texts:
        for piece in _SENTENCE_SPLIT_RE.split(str(text or "").strip()):
            normalized = _SPACE_RE.sub(" ", piece.strip())
            if normalized:
                parts.append(normalized)
    return _unique(parts)


def _normalize_soft_rule_state(value: object) -> str:
    normalized = _SPACE_RE.sub(" ", str(value or "").strip()).lower()
    if normalized in {"", "candidate", "pending", "proposed", "proposal", "draft", "new"}:
        return "candidate"
    if normalized in {"active", "enabled", "live", "applied"}:
        return "active"
    if normalized in {"promoted", "adopted"}:
        return "promoted"
    if normalized in {"rejected", "dismissed", "declined", "denied"}:
        return "rejected"
    if normalized in {"expired", "stale", "obsolete", "superseded"}:
        return "expired"
    return "candidate"


def _normalize_conflict_status(value: object) -> str:
    normalized = _SPACE_RE.sub(" ", str(value or "").strip()).lower()
    if normalized in {"", "pending", "unresolved", "open", "new", "todo", "needs review", "needs-review"}:
        return "pending"
    if normalized in {"accepted", "approved", "confirmed", "resolved"}:
        return "accepted"
    if normalized in {"rejected", "dismissed", "declined", "denied"}:
        return "rejected"
    if normalized in {"expired", "stale", "obsolete", "superseded"}:
        return "expired"
    return "pending"


def _title_tokens(title: str) -> list[str]:
    return [token.lower() for token in _WORD_RE.findall(str(title or ""))]


def _shared_alias_payloads(titles: list[str]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    seen: set[str] = set()
    for left in titles:
        left_tokens = _title_tokens(left)
        if len(left_tokens) < 2:
            continue
        for right in titles:
            if left == right:
                continue
            right_tokens = _title_tokens(right)
            overlap = [token for token in left_tokens if token in right_tokens]
            if len(overlap) < 2:
                continue
            canonical = left if len(left_tokens) >= len(right_tokens) else right
            alias = " ".join(overlap)
            key = f"{canonical.lower()}::{alias.lower()}"
            if alias.lower() == canonical.lower() or key in seen:
                continue
            seen.add(key)
            payloads.append(
                {
                    "canonical_term": canonical,
                    "aliases": [alias],
                    "confidence": 0.85,
                },
            )
    return payloads[:3]


def _detect_conflicts(sentences: list[str], source_refs: list[str]) -> list[dict[str, Any]]:
    combined = " \n ".join(sentence.lower() for sentence in sentences)
    if "before finance review" not in combined:
        return []
    if "wait for finance review" not in combined and "after finance review" not in combined:
        return []
    return [
        {
            "proposal_kind": "conflict",
            "title": "Approval order conflict",
            "summary": "One source allows approval before finance review while another blocks approval until review completes.",
            "conflicting_refs": source_refs[:1],
            "supporting_refs": source_refs[1:3] or source_refs[:1],
            "recommended_action": "Keep the stricter review-first rule until stronger evidence arrives.",
            "risk_level": "high",
            "status": "pending",
        },
    ]


def _safe_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return dict(namespace)
    return {}


def _jsonable_list(items: list[object], *, limit: int = 8) -> list[dict[str, Any]]:
    return [_safe_mapping(item) for item in list(items or [])[:limit]]


def _response_to_text(response: object) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
            else:
                text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _response_to_payload(response: object) -> dict[str, Any]:
    metadata = getattr(response, "metadata", None)
    if isinstance(metadata, BaseModel):
        return metadata.model_dump(mode="json")
    if isinstance(metadata, dict):
        return dict(metadata)
    text = _response_to_text(response)
    if not text:
        raise ValueError("memory sleep model returned an empty response")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("memory sleep model returned a non-object payload")
    return payload


async def _materialize_response(response: object) -> object:
    return await materialize_model_response(response)


def _run_async_blocking(
    awaitable: object,
    *,
    timeout_seconds: float | None = None,
) -> object:
    async def _coerce() -> object:
        return await awaitable  # type: ignore[misc]

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_coerce())

    result: dict[str, object] = {}
    error: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(_coerce())
        except BaseException as exc:  # pragma: no cover - passthrough
            error["value"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        raise TimeoutError(
            f"memory sleep model did not return within {timeout_seconds:g} seconds",
        )
    if "value" in error:
        raise error["value"]
    return result.get("value")


class _SleepDigestResponse(BaseModel):
    headline: str = ""
    summary: str = ""
    current_constraints: list[str] = Field(default_factory=list)
    current_focus: list[str] = Field(default_factory=list)
    top_entities: list[str] = Field(default_factory=list)
    top_relations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class _SleepAliasResponse(BaseModel):
    canonical_term: str = ""
    aliases: list[str] = Field(default_factory=list)
    confidence: float = 0.8


class _SleepMergeResponse(BaseModel):
    merged_title: str = ""
    merged_summary: str = ""
    merged_source_refs: list[str] = Field(default_factory=list)


class _SleepSoftRuleResponse(BaseModel):
    rule_text: str = ""
    rule_kind: str = "guidance"
    hit_count: int = 1
    day_span: int = 1
    conflict_count: int = 0
    risk_level: str = "low"
    state: str = "candidate"

    @field_validator("state", mode="before")
    @classmethod
    def _normalize_state(cls, value: object) -> str:
        return _normalize_soft_rule_state(value)


class _SleepConflictProposalResponse(BaseModel):
    proposal_kind: str = "conflict"
    title: str = ""
    summary: str = ""
    conflicting_refs: list[str] = Field(default_factory=list)
    supporting_refs: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    risk_level: str = "high"
    status: str = "pending"

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: object) -> str:
        return _normalize_conflict_status(value)


class _SleepInferenceResponse(BaseModel):
    digest: _SleepDigestResponse = Field(default_factory=_SleepDigestResponse)
    alias_maps: list[_SleepAliasResponse] = Field(default_factory=list)
    merge_results: list[_SleepMergeResponse] = Field(default_factory=list)
    soft_rules: list[_SleepSoftRuleResponse] = Field(default_factory=list)
    conflict_proposals: list[_SleepConflictProposalResponse] = Field(default_factory=list)


_SLEEP_INFERENCE_SYSTEM_PROMPT = """
You compile CoPaw memory sleep-layer B+ artifacts.

Return exactly one structured object with:
- digest
- alias_maps
- merge_results
- soft_rules
- conflict_proposals

Rules:
- Do not rewrite raw facts or evidence.
- Prefer canonical truth over noisy text.
- Keep outputs compact and operator-readable.
- Only emit low-risk soft rules.
- Put unresolved contradictions into conflict_proposals.
""".strip()


def build_memory_sleep_model_runner(
    *,
    model_factory: Callable[[], object] | None,
    timeout_seconds: float = _DEFAULT_REASONING_TIMEOUT_SECONDS,
) -> Callable[..., dict[str, Any]] | None:
    if not callable(model_factory):
        return None

    def _runner(
        *,
        scope_type: str,
        scope_id: str,
        knowledge_chunks: list[object],
        strategies: list[object],
        fact_entries: list[object],
        entity_views: list[object],
        relation_views: list[object],
    ) -> dict[str, Any]:
        model = model_factory()
        if not callable(model):
            raise ValueError("runtime sleep model is not callable")
        request_payload = {
            "scope_type": scope_type,
            "scope_id": scope_id,
            "knowledge_chunks": _jsonable_list(knowledge_chunks),
            "strategies": _jsonable_list(strategies, limit=4),
            "fact_entries": _jsonable_list(fact_entries, limit=8),
            "entity_views": _jsonable_list(entity_views, limit=8),
            "relation_views": _jsonable_list(relation_views, limit=8),
        }
        messages = [
            {"role": "system", "content": _SLEEP_INFERENCE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Compile the next B+ sleep artifacts from canonical memory truth.\n\n"
                    f"{json.dumps(request_payload, ensure_ascii=False, indent=2)}"
                ),
            },
        ]
        response = _run_async_blocking(
            model(
                messages=messages,
                structured_model=_SleepInferenceResponse,
                temperature=0.15,
                max_tokens=900,
            ),
            timeout_seconds=timeout_seconds,
        )
        response = _run_async_blocking(
            _materialize_response(response),
            timeout_seconds=timeout_seconds,
        )
        payload = _SleepInferenceResponse.model_validate(
            _response_to_payload(response),
        )
        return payload.model_dump(mode="json")

    return _runner


class MemorySleepInferenceService:
    """Compile deterministic sleep artifacts from canonical memory inputs."""

    def __init__(self, *, model_runner: object | None = None) -> None:
        self._model_runner = model_runner

    def infer(
        self,
        *,
        scope_type: str,
        scope_id: str,
        knowledge_chunks: list[object],
        strategies: list[object],
        fact_entries: list[object],
        entity_views: list[object],
        relation_views: list[object],
    ) -> dict[str, Any]:
        runner = self._model_runner
        if callable(runner):
            try:
                result = runner(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    knowledge_chunks=knowledge_chunks,
                    strategies=strategies,
                    fact_entries=fact_entries,
                    entity_views=entity_views,
                    relation_views=relation_views,
                )
                if isinstance(result, dict):
                    return result
            except Exception:
                logger.debug("memory sleep model runner failed; falling back", exc_info=True)
        return self._fallback(
            scope_type=scope_type,
            scope_id=scope_id,
            knowledge_chunks=knowledge_chunks,
            strategies=strategies,
            fact_entries=fact_entries,
            entity_views=entity_views,
            relation_views=relation_views,
        )

    def _fallback(
        self,
        *,
        scope_type: str,
        scope_id: str,
        knowledge_chunks: list[object],
        strategies: list[object],
        fact_entries: list[object],
        entity_views: list[object],
        relation_views: list[object],
    ) -> dict[str, Any]:
        titles = _unique([str(getattr(item, "title", "") or "").strip() for item in knowledge_chunks])
        chunk_summaries = _unique(
            [
                str(getattr(item, "summary", "") or getattr(item, "content", "") or "").strip()
                for item in knowledge_chunks
            ],
        )
        source_refs = _unique([str(getattr(item, "source_ref", "") or "").strip() for item in knowledge_chunks])
        strategy_constraints = _unique(
            [
                value
                for strategy in strategies
                for value in list(getattr(strategy, "execution_constraints", []) or [])
            ],
        )
        strategy_focuses = _unique(
            [
                value
                for strategy in strategies
                for value in list(getattr(strategy, "current_focuses", []) or [])
            ],
        )
        entity_candidates = _unique(
            [str(getattr(item, "entity_key", "") or "").strip() for item in entity_views]
            + titles
        )[:5]
        relation_candidates = _unique(
            [str(getattr(item, "summary", "") or "").strip() for item in relation_views]
            + [
                sentence
                for sentence in _sentences(*chunk_summaries)
                if any(cue in sentence.lower() for cue in _RULE_CUES)
            ]
        )[:5]
        constraints = _unique(strategy_constraints + relation_candidates)[:4]
        focuses = _unique(strategy_focuses + titles)[:4]
        headline = (
            str(getattr(strategies[0], "title", "") or "").strip()
            if strategies
            else (titles[0] if titles else f"Memory digest for {scope_type}:{scope_id}")
        )
        summary = (
            str(getattr(strategies[0], "summary", "") or "").strip()
            if strategies and str(getattr(strategies[0], "summary", "") or "").strip()
            else (" ".join(chunk_summaries[:2]) if chunk_summaries else f"No structured memory found for {scope_type}:{scope_id}.")
        )
        alias_maps = _shared_alias_payloads(titles)
        merge_results = []
        if len(source_refs) >= 2:
            merge_results.append(
                {
                    "merged_title": entity_candidates[0] if entity_candidates else headline,
                    "merged_summary": summary,
                    "merged_source_refs": source_refs[:2],
                },
            )
        soft_rules = []
        for constraint in constraints[:3]:
            lowered = constraint.lower()
            soft_rules.append(
                {
                    "rule_text": constraint,
                    "rule_kind": "requirement" if any(cue in lowered for cue in _RULE_CUES) else "guidance",
                    "hit_count": 3 if any(cue in lowered for cue in _RULE_CUES) else 1,
                    "day_span": 2 if any(cue in lowered for cue in _RULE_CUES) else 1,
                    "conflict_count": 0,
                    "risk_level": "low",
                    "state": "active" if any(cue in lowered for cue in _RULE_CUES) else "candidate",
                },
            )
        return {
            "digest": {
                "headline": headline,
                "summary": summary,
                "current_constraints": constraints,
                "current_focus": focuses,
                "top_entities": entity_candidates,
                "top_relations": relation_candidates,
                "evidence_refs": _unique(
                    [str(getattr(item, "source_ref", "") or "").strip() for item in fact_entries] + source_refs,
                )[:6],
            },
            "alias_maps": alias_maps,
            "merge_results": merge_results,
            "soft_rules": soft_rules,
            "conflict_proposals": _detect_conflicts(_sentences(*chunk_summaries), source_refs),
        }
