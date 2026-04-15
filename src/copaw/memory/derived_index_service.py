# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any, Iterable

from .models import MemoryRebuildSummary, MemoryScopeSelector, utc_now
from ..state import (
    AgentReportRecord,
    KnowledgeChunkRecord,
    MemoryEntityViewRecord,
    MemoryFactIndexRecord,
    MemoryOpinionViewRecord,
    MemoryReflectionRunRecord,
    ReportRecord,
    RoutineRunRecord,
    StrategyMemoryRecord,
)
from ..state.models_memory import MemoryRelationViewRecord

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}")
_SENTENCE_SPLIT_RE = re.compile(r"(?:\r?\n)+|(?<=[.!?])\s+|(?<=[。！？；])")
_MEMORY_DOCUMENT_PREFIX = "memory:"
_STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "over",
    "after",
    "before",
    "should",
    "must",
    "need",
    "have",
    "has",
    "only",
    "never",
    "always",
    "task",
    "goal",
    "agent",
    "approve",
    "report",
    "memory",
    "summary",
    "evidence",
    "runtime",
    "status",
    "result",
    "industry",
    "global",
    "scope",
    "record",
    "any",
    "wait",
    "message",
    "sent",
    "own",
    "owns",
    "clear",
    "clears",
    "verified",
    "verify",
    "using",
    "used",
    "use",
    "being",
    "becomes",
    "become",
    "just",
    "still",
    "action",
    "auto",
    "blocker",
    "blocked",
    "completed",
    "discipline",
    "execution",
    "holding",
    "keep",
    "night",
    "operator",
    "protect",
    "recorded",
    "refreshed",
    "recommends",
    "resolve",
    "retain",
    "risk",
    "quality",
    "blockers",
    "until",
}
_INTERNAL_ENTITY_ID_PARTS = {
    "agent",
    "assignment",
    "brain",
    "chunk",
    "context",
    "cycle",
    "fact",
    "global",
    "goal",
    "industry",
    "lane",
    "memory",
    "record",
    "report",
    "runtime",
    "scope",
    "task",
    "work",
    "main",
    "ctx",
}
_CJK_SEGMENT_SPLIT_RE = re.compile(
    r"[，。；、：！？\s]+|必须|需要|应该|建议|避免|不要|不能|只能|先|再|才可以|才能|并且|以及|确认后|完成后|之后|以后"
)
_CJK_LOW_SIGNAL_WORDS = {
    "规则",
    "内容",
    "信息",
    "情况",
    "东西",
    "问题",
    "系统",
    "任务",
    "目标",
    "工作",
    "处理",
    "完成",
    "发送",
    "确认",
    "继续",
    "通过",
    "进行",
    "记忆",
    "共享记忆",
}
_CJK_TRIM_PREFIXES = (
    "完成",
    "发送",
    "确认",
    "进行",
    "执行",
    "推进",
    "开展",
    "处理",
    "启动",
    "安排",
    "等待",
    "进入",
    "发出",
    "提交",
)
_CJK_TRIM_SUFFIXES = (
    "规则",
    "内容",
    "信息",
    "情况",
    "之后",
    "以后",
    "之前",
    "才能",
    "才可以",
)
_OPINION_CUES: tuple[tuple[str, str], ...] = (
    ("do not", "caution"),
    ("don't", "caution"),
    ("must", "requirement"),
    ("need to", "requirement"),
    ("needs to", "requirement"),
    ("requires", "requirement"),
    ("required", "requirement"),
    ("prefer", "preference"),
    ("preferred", "preference"),
    ("avoid", "caution"),
    ("never", "caution"),
    ("only", "requirement"),
    ("should", "recommendation"),
    ("不要", "caution"),
    ("避免", "caution"),
    ("必须", "requirement"),
    ("需要", "requirement"),
    ("只能", "requirement"),
    ("应该", "recommendation"),
    ("建议", "recommendation"),
)


def normalize_memory_scope_type(scope_type: str | None) -> str:
    normalized = str(scope_type or "").strip().lower()
    return (
        normalized
        if normalized in {"global", "industry", "agent", "task", "work_context"}
        else "global"
    )


def normalize_scope_id(scope_id: str | None) -> str:
    normalized = str(scope_id or "").strip()
    return normalized or "runtime"


def normalize_optional_text(value: object | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def parse_memory_document_id(document_id: str | None) -> tuple[str, str] | None:
    if not isinstance(document_id, str) or not document_id.startswith(_MEMORY_DOCUMENT_PREFIX):
        return None
    remainder = document_id[len(_MEMORY_DOCUMENT_PREFIX) :]
    scope_type, separator, scope_id = remainder.partition(":")
    if not separator:
        return None
    normalized_scope_type = normalize_memory_scope_type(scope_type)
    normalized_scope_id = normalize_scope_id(scope_id)
    if normalized_scope_type == "global" and normalized_scope_id == "runtime":
        return None
    return normalized_scope_type, normalized_scope_id


def build_scope_candidates(selector: MemoryScopeSelector) -> set[tuple[str, str]]:
    candidates: set[tuple[str, str]] = set()
    if selector.scope_type and selector.scope_id:
        candidates.add(
            (
                normalize_memory_scope_type(selector.scope_type),
                normalize_scope_id(selector.scope_id),
            ),
        )
        if not selector.include_related_scopes:
            return candidates
    if not selector.include_related_scopes:
        return candidates
    for scope_type, scope_id in (
        ("task", selector.task_id),
        ("work_context", selector.work_context_id),
        ("agent", selector.agent_id),
        ("industry", selector.industry_instance_id),
        ("global", selector.global_scope_id),
    ):
        normalized_scope_id = str(scope_id or "").strip()
        if normalized_scope_id:
            candidates.add((scope_type, normalized_scope_id))
    return candidates


def selector_matches_scope(
    *,
    selector: MemoryScopeSelector,
    scope_type: str,
    scope_id: str,
) -> bool:
    candidates = build_scope_candidates(selector)
    if not candidates:
        return True
    return (normalize_memory_scope_type(scope_type), normalize_scope_id(scope_id)) in candidates


def source_route_for_entry(entry: MemoryFactIndexRecord) -> str | None:
    metadata = dict(entry.metadata or {})
    media_analysis_ref = _normalize_media_analysis_ref(
        metadata.get("source_ref"),
    ) or _normalize_media_analysis_ref(entry.source_ref)
    if media_analysis_ref:
        return f"/api/media/analyses/{media_analysis_ref}"
    route = metadata.get("source_route")
    if isinstance(route, str) and route.strip():
        return route.strip()
    if entry.source_type == "knowledge_chunk":
        return f"/api/runtime-center/knowledge/{entry.source_ref}"
    if entry.source_type == "strategy_memory":
        return "/api/runtime-center/strategy-memory"
    if entry.source_type == "routine_run":
        return f"/api/routines/runs/{entry.source_ref}"
    if entry.source_type == "evidence":
        return f"/api/runtime-center/evidence/{entry.source_ref}"
    if entry.source_type == "learning_patch":
        return f"/api/runtime-center/learning/patches/{entry.source_ref}"
    if entry.source_type == "learning_growth":
        return f"/api/runtime-center/learning/growth/{entry.source_ref}"
    if entry.source_type == "agent_report" and entry.industry_instance_id:
        return f"/api/runtime-center/industry/{entry.industry_instance_id}"
    return None


def _normalize_media_analysis_ref(value: object | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    prefix = "media-analysis:"
    if prefix not in text:
        return None
    while text.startswith(f"{prefix}{prefix}"):
        text = text[len(prefix) :]
    return text if text.startswith(prefix) else None


def slugify(value: object, *, fallback: str = "memory") -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "-"
        for character in str(value or "").strip()
    ).strip("-")
    return normalized or fallback


def truncate_text(value: object, *, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def _contains_cjk(text: object | None) -> bool:
    return any("\u4e00" <= character <= "\u9fff" for character in str(text or ""))


def _normalize_cjk_phrase(value: str) -> str:
    normalized = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(value or "").strip())
    changed = True
    while changed and len(normalized) >= 2:
        changed = False
        for prefix in _CJK_TRIM_PREFIXES:
            if normalized.startswith(prefix) and len(normalized) - len(prefix) >= 2:
                normalized = normalized[len(prefix) :]
                changed = True
        for suffix in _CJK_TRIM_SUFFIXES:
            if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 2:
                normalized = normalized[: -len(suffix)]
                changed = True
    return normalized


def _tokenize_cjk_phrases(text: str | None) -> list[str]:
    if not isinstance(text, str) or not text.strip() or not _contains_cjk(text):
        return []
    tokens: list[str] = []
    seen: set[str] = set()
    for sentence in _split_sentences(text):
        for segment in _CJK_SEGMENT_SPLIT_RE.split(sentence):
            normalized = _normalize_cjk_phrase(segment)
            if (
                len(normalized) < 2
                or len(normalized) > 12
                or normalized in _CJK_LOW_SIGNAL_WORDS
                or normalized in seen
            ):
                continue
            seen.add(normalized)
            tokens.append(normalized)
    return tokens


def tokenize(text: str | None) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    latin_tokens = [token.lower() for token in _TOKEN_RE.findall(text)]
    return [*latin_tokens, *_tokenize_cjk_phrases(text)]


def _split_entity_parts(value: str) -> list[str]:
    return [
        part
        for part in re.split(r"[-_:/.]+", str(value or "").strip().lower())
        if part
    ]


def _is_low_signal_entity_token(token: str) -> bool:
    normalized = str(token or "").strip().lower()
    return (
        not normalized
        or normalized in _STOP_WORDS
        or normalized in _INTERNAL_ENTITY_ID_PARTS
        or normalized in _CJK_LOW_SIGNAL_WORDS
        or normalized.isdigit()
    )


def _is_noisy_explicit_entity(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    normalized = text.lower()
    if " " not in normalized and _is_low_signal_entity_token(normalized):
        return True
    parts = _split_entity_parts(normalized)
    if not parts:
        return True
    if any(part.isdigit() for part in parts):
        return True
    if len(parts) > 1 and any(part in _INTERNAL_ENTITY_ID_PARTS for part in parts):
        return True
    return False


def _split_sentences(text: str | None) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    return [
        sentence.strip()
        for sentence in _SENTENCE_SPLIT_RE.split(text)
        if sentence and sentence.strip()
    ]


def _parse_opinion_key(opinion_key: str) -> tuple[str, str, str]:
    subject_key, first_sep, remainder = str(opinion_key or "").partition(":")
    if not first_sep:
        return "general", "neutral", str(opinion_key or "").strip()
    stance, second_sep, label = remainder.partition(":")
    if not second_sep:
        return subject_key or "general", stance or "neutral", remainder
    return subject_key or "general", stance or "neutral", label or opinion_key


def humanize_opinion_key(opinion_key: str) -> str:
    subject_key, stance, label = _parse_opinion_key(opinion_key)
    normalized_subject = subject_key.replace("-", " ").strip()
    normalized_stance = stance.replace("-", " ").strip()
    normalized_label = label.replace("-", " ").strip()
    if _contains_cjk(normalized_subject) or _contains_cjk(normalized_label):
        has_subject = bool(normalized_subject and normalized_subject != "general")
        if normalized_stance == "requirement":
            return (
                f"{normalized_subject}需要{normalized_label}"
                if has_subject and normalized_label
                else f"需要{normalized_label}"
                if normalized_label
                else opinion_key
            )
        if normalized_stance == "preference":
            return (
                f"{normalized_subject}偏好{normalized_label}"
                if has_subject and normalized_label
                else f"偏好{normalized_label}"
                if normalized_label
                else opinion_key
            )
        if normalized_stance == "recommendation":
            return (
                f"{normalized_subject}建议{normalized_label}"
                if has_subject and normalized_label
                else f"建议{normalized_label}"
                if normalized_label
                else opinion_key
            )
        if normalized_stance == "caution":
            return (
                f"{normalized_subject}注意{normalized_label}"
                if has_subject and normalized_label
                else f"注意{normalized_label}"
                if normalized_label
                else opinion_key
            )
    has_subject = bool(normalized_subject and normalized_subject != "general")
    if normalized_stance == "requirement":
        if has_subject and normalized_label:
            return f"{normalized_subject} requires {normalized_label}"
        if normalized_label:
            return f"requires {normalized_label}"
    if normalized_stance == "preference":
        if has_subject and normalized_label:
            return f"{normalized_subject} prefers {normalized_label}"
        if normalized_label:
            return f"prefers {normalized_label}"
    if normalized_stance == "recommendation":
        if has_subject and normalized_label:
            return f"{normalized_subject} recommends {normalized_label}"
        if normalized_label:
            return f"recommends {normalized_label}"
    if normalized_stance == "caution":
        if has_subject and normalized_label:
            return f"{normalized_subject} caution: {normalized_label}"
        if normalized_label:
            return f"caution: {normalized_label}"
    pieces: list[str] = []
    if has_subject:
        pieces.append(normalized_subject)
    if normalized_stance and normalized_stance != "neutral":
        pieces.append(normalized_stance)
    if normalized_label and normalized_label not in {normalized_subject, normalized_stance}:
        pieces.append(normalized_label)
    return " ".join(piece for piece in pieces if piece).strip() or opinion_key


def _looks_like_opinion_summary(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    if _contains_cjk(normalized):
        return any(marker in normalized for marker in ("需要", "偏好", "建议", "注意"))
    lowered = normalized.lower()
    return any(
        marker in lowered
        for marker in (" requires ", " prefers ", " recommends ", "caution:")
    )


def present_relation_summary(*, source_text: str, relation_kind: str, target_text: str) -> str:
    source = str(source_text or "").strip()
    target = str(target_text or "").strip()
    kind = str(relation_kind or "").strip().lower() or "references"
    if _looks_like_opinion_summary(source) and target:
        if (_contains_cjk(source) and target in source) or (
            not _contains_cjk(source) and target.lower() in source.lower()
        ):
            return source
    if _contains_cjk(source) or _contains_cjk(target):
        verb = {
            "mentions": "提到",
            "supports": "支持",
            "contradicts": "与",
            "depends_on": "依赖",
            "references": "关联",
        }.get(kind, "关联")
        if kind == "contradicts":
            return f"{source}与{target}冲突".strip()
        return f"{source}{verb}{target}".strip()
    verb = {
        "mentions": "mentions",
        "supports": "supports",
        "contradicts": "contradicts",
        "depends_on": "depends on",
        "references": "references",
    }.get(kind, kind)
    return f"{source} {verb} {target}".strip()


def _sentence_case(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized or _contains_cjk(normalized):
        return normalized
    return normalized[:1].upper() + normalized[1:]


def present_fact_opinion_summary(
    *,
    source_text: str,
    relation_kind: str,
    opinion_key: str,
) -> str:
    _ = source_text
    opinion_summary = _sentence_case(humanize_opinion_key(opinion_key))
    normalized_kind = str(relation_kind or "").strip().lower()
    if normalized_kind == "supports":
        return opinion_summary
    if normalized_kind == "contradicts":
        if _contains_cjk(opinion_summary):
            return f"与{opinion_summary}冲突"
        return f"Conflicts with {opinion_summary}"
    return present_relation_summary(
        source_text=source_text,
        relation_kind=relation_kind,
        target_text=opinion_summary,
    )


def _derive_opinion_subject(*, sentence: str, entity_keys: list[str]) -> str:
    sentence_tokens = set(tokenize(sentence))
    for entity_key in entity_keys:
        normalized_key = str(entity_key or "").strip().lower()
        if normalized_key and normalized_key in sentence_tokens:
            return normalized_key
    return entity_keys[0] if entity_keys else "general"


def _derive_cjk_opinion_label(
    *,
    sentence_text: str,
    tail_text: str,
    subject_key: str,
    entity_keys: list[str],
) -> str | None:
    ordered_entity_keys = list(dict.fromkeys(str(item or "").strip().lower() for item in entity_keys))
    candidates: list[tuple[int, int, str]] = []
    for entity_key in ordered_entity_keys:
        if (
            not entity_key
            or entity_key == subject_key
            or _is_low_signal_entity_token(entity_key)
        ):
            continue
        position = tail_text.find(entity_key)
        if position >= 0:
            candidates.append((position, -len(entity_key), entity_key))
    if candidates:
        candidates.sort()
        return candidates[0][2]

    label_tokens = [
        token
        for token in tokenize(tail_text or sentence_text)
        if not _is_low_signal_entity_token(token) and token != subject_key
    ]
    return label_tokens[0] if label_tokens else None


def _derive_opinion_label(
    *,
    sentence: str,
    cue: str,
    subject_key: str,
    fallback: str,
    entity_keys: list[str],
) -> str:
    sentence_text = str(sentence or "").strip().lower()
    if not sentence_text:
        return fallback
    tail_text = sentence_text.split(cue, 1)[1] if cue in sentence_text else sentence_text
    if _contains_cjk(sentence_text):
        cjk_label = _derive_cjk_opinion_label(
            sentence_text=sentence_text,
            tail_text=tail_text,
            subject_key=subject_key,
            entity_keys=entity_keys,
        )
        if cjk_label:
            return slugify(cjk_label, fallback=fallback)
    label_tokens = [
        token
        for token in tokenize(tail_text)
        if not _is_low_signal_entity_token(token) and token != subject_key
    ]
    if not label_tokens:
        label_tokens = [
            token
            for token in tokenize(sentence_text)
            if not _is_low_signal_entity_token(token) and token != subject_key
        ]
    return slugify("-".join(label_tokens[:3]), fallback=fallback)


def dedupe_texts(values: Iterable[object]) -> list[str]:
    collected: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in collected:
            continue
        collected.append(text)
    return collected


def extract_entity_candidates(
    *,
    title: str,
    summary: str,
    content_text: str,
    explicit: Iterable[str] = (),
) -> tuple[list[str], dict[str, str]]:
    entity_labels: dict[str, str] = {}
    ordered_keys: list[str] = []

    def add(value: object, *, label: str | None = None) -> None:
        text = str(value or "").strip()
        if not text:
            return
        if _is_noisy_explicit_entity(text):
            return
        key = slugify(text, fallback="entity")
        if key in entity_labels:
            return
        entity_labels[key] = truncate_text(label or text, max_length=80) or key
        ordered_keys.append(key)

    for item in explicit:
        add(item)

    token_counts = Counter(
        token
        for token in tokenize("\n".join(part for part in (title, summary, content_text) if part))
        if not _is_low_signal_entity_token(token)
    )
    for token, _count in token_counts.most_common(6):
        add(token, label=token.replace("-", " "))
    return ordered_keys[:8], entity_labels


def extract_opinion_keys(text: str | None, *, entity_keys: list[str]) -> list[str]:
    normalized_text = str(text or "").strip().lower()
    if not normalized_text:
        return []
    collected: list[str] = []
    sentences = _split_sentences(normalized_text) or [normalized_text]
    for sentence in sentences:
        for cue, stance in _OPINION_CUES:
            if cue not in sentence:
                continue
            subject = _derive_opinion_subject(sentence=sentence, entity_keys=entity_keys)
            label = _derive_opinion_label(
                sentence=sentence,
                cue=cue,
                subject_key=subject,
                fallback=slugify(cue, fallback=stance),
                entity_keys=entity_keys,
            )
            collected.append(f"{subject}:{stance}:{label}")
    return list(dict.fromkeys(collected))[:8]


def derive_quality_score(
    *,
    content_text: str,
    summary: str,
    evidence_refs: list[str],
    entity_keys: list[str],
) -> float:
    score = 0.25
    if summary:
        score += 0.15
    score += min(len(content_text), 640) / 1280.0
    score += min(len(evidence_refs), 3) * 0.07
    score += min(len(entity_keys), 5) * 0.03
    return max(0.05, min(1.0, score))


def derive_confidence(
    *,
    source_type: str,
    status: str | None = None,
    processed: bool | None = None,
    evidence_refs: list[str] | None = None,
) -> float:
    base = {
        "strategy_memory": 0.9,
        "knowledge_chunk": 0.72,
        "agent_report": 0.8,
        "routine_run": 0.78,
        "report_snapshot": 0.76,
        "evidence": 0.68,
        "learning_patch": 0.78,
        "learning_growth": 0.8,
    }.get(source_type, 0.65)
    normalized_status = str(status or "").strip().lower()
    if normalized_status in {"failed", "rejected", "rolled_back"}:
        base -= 0.12
    elif normalized_status in {"completed", "approved", "applied", "processed", "active"}:
        base += 0.05
    if processed:
        base += 0.04
    if evidence_refs:
        base += min(len(evidence_refs), 3) * 0.02
    return max(0.05, min(0.99, base))


def derive_memory_type(*, source_type: str, tags: Iterable[str] = (), evidence_refs: Iterable[str] = ()) -> str:
    normalized_tags = {str(item or "").strip().lower() for item in tags if str(item or "").strip()}
    if "temporary" in normalized_tags:
        return "temporary"
    if "preference" in normalized_tags:
        return "preference"
    if source_type == "report_snapshot":
        return "episode"
    if source_type == "agent_report":
        return "fact" if list(evidence_refs) else "inference"
    return "fact"


def derive_confidence_tier(confidence: float) -> str:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.65:
        return "medium"
    return "low"


def derive_subject_key(
    *,
    source_type: str,
    scope_type: str,
    scope_id: str,
    title: str,
    explicit: object | None = None,
) -> str:
    normalized_explicit = str(explicit or "").strip()
    if normalized_explicit:
        return normalized_explicit
    normalized_title = slugify(title, fallback=source_type)
    return f"{scope_type}:{scope_id}:{normalized_title}"


def _safe_getattr(target: object | None, name: str) -> Any:
    if target is None:
        return None
    return getattr(target, name, None)


class DerivedMemoryIndexService:
    """Maintain rebuildable fact index entries derived from canonical sources."""

    def __init__(
        self,
        *,
        fact_index_repository,
        entity_view_repository=None,
        opinion_view_repository=None,
        relation_view_repository=None,
        reflection_run_repository=None,
        knowledge_repository=None,
        strategy_repository=None,
        agent_report_repository=None,
        routine_repository=None,
        routine_run_repository=None,
        industry_instance_repository=None,
        evidence_ledger=None,
        reporting_service: object | None = None,
        learning_service: object | None = None,
        sidecar_backends: list[object] | None = None,
    ) -> None:
        self._fact_index_repository = fact_index_repository
        self._entity_view_repository = entity_view_repository
        self._opinion_view_repository = opinion_view_repository
        self._relation_view_repository = relation_view_repository
        self._reflection_run_repository = reflection_run_repository
        self._knowledge_repository = knowledge_repository
        self._strategy_repository = strategy_repository
        self._agent_report_repository = agent_report_repository
        self._routine_repository = routine_repository
        self._routine_run_repository = routine_run_repository
        self._industry_instance_repository = industry_instance_repository
        self._evidence_ledger = evidence_ledger
        self._reporting_service = reporting_service
        self._learning_service = learning_service
        self._sidecar_backends = list(sidecar_backends or [])

    def set_reporting_service(self, reporting_service: object | None) -> None:
        self._reporting_service = reporting_service

    def set_learning_service(self, learning_service: object | None) -> None:
        self._learning_service = learning_service

    def set_sidecar_backends(self, sidecar_backends: list[object] | None) -> None:
        self._sidecar_backends = list(sidecar_backends or [])

    def list_fact_entries(self, **kwargs: Any) -> list[MemoryFactIndexRecord]:
        include_inactive = bool(kwargs.pop("include_inactive", False))
        entries = self._fact_index_repository.list_entries(**kwargs)
        if include_inactive:
            return entries
        return [entry for entry in entries if self._is_active_fact_entry(entry)]

    def list_entity_views(self, **kwargs: Any) -> list[MemoryEntityViewRecord]:
        if self._entity_view_repository is None:
            return []
        return self._entity_view_repository.list_views(**kwargs)

    def list_opinion_views(self, **kwargs: Any) -> list[MemoryOpinionViewRecord]:
        if self._opinion_view_repository is None:
            return []
        return self._opinion_view_repository.list_views(**kwargs)

    def list_relation_views(self, **kwargs: Any) -> list[MemoryRelationViewRecord]:
        if self._relation_view_repository is None:
            return []
        list_kwargs = dict(kwargs)
        include_inactive = bool(list_kwargs.pop("include_inactive", False))
        scope_type = normalize_optional_text(list_kwargs.get("scope_type"))
        scope_id = normalize_optional_text(list_kwargs.get("scope_id"))
        if scope_type is not None:
            list_kwargs["scope_type"] = normalize_memory_scope_type(scope_type)
        if scope_id is not None:
            list_kwargs["scope_id"] = normalize_scope_id(scope_id)
        for field in (
            "owner_agent_id",
            "industry_instance_id",
            "relation_kind",
            "source_node_id",
            "target_node_id",
        ):
            normalized = normalize_optional_text(list_kwargs.get(field))
            if normalized is not None:
                list_kwargs[field] = normalized
        relations = self._relation_view_repository.list_views(**list_kwargs)
        if include_inactive:
            return relations
        return [relation for relation in relations if self._is_active_relation_view(relation)]

    def list_reflection_runs(self, **kwargs: Any) -> list[MemoryReflectionRunRecord]:
        if self._reflection_run_repository is None:
            return []
        return self._reflection_run_repository.list_runs(**kwargs)

    def clear_compiled_views(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> None:
        if self._entity_view_repository is not None:
            self._entity_view_repository.clear(scope_type=scope_type, scope_id=scope_id)
        if self._opinion_view_repository is not None:
            self._opinion_view_repository.clear(scope_type=scope_type, scope_id=scope_id)
        if self._relation_view_repository is not None:
            self._relation_view_repository.clear(scope_type=scope_type, scope_id=scope_id)

    def rebuild_relation_views(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
    ) -> list[MemoryRelationViewRecord]:
        if self._relation_view_repository is None:
            return []
        normalized_scope_type = (
            normalize_memory_scope_type(scope_type)
            if isinstance(scope_type, str) and scope_type.strip()
            else None
        )
        normalized_scope_id = (
            normalize_scope_id(scope_id)
            if isinstance(scope_id, str) and scope_id.strip()
            else None
        )
        relation_owner_agent_id = owner_agent_id or (
            normalized_scope_id if normalized_scope_type == "agent" else None
        )
        relation_industry_instance_id = industry_instance_id or (
            normalized_scope_id if normalized_scope_type == "industry" else None
        )
        input_list_kwargs: dict[str, Any] = {
            "scope_type": normalized_scope_type,
            "scope_id": normalized_scope_id,
            "limit": None,
        }
        fact_entries = self.list_fact_entries(**input_list_kwargs)
        entity_views = self.list_entity_views(**input_list_kwargs)
        opinion_views = self.list_opinion_views(**input_list_kwargs)
        self._relation_view_repository.clear(
            scope_type=normalized_scope_type,
            scope_id=normalized_scope_id,
        )
        relation_views = self._build_relation_views(
            fact_entries=fact_entries,
            entity_views=entity_views,
            opinion_views=opinion_views,
            scope_type=normalized_scope_type,
            scope_id=normalized_scope_id,
            owner_agent_id=relation_owner_agent_id,
            industry_instance_id=relation_industry_instance_id,
        )
        for relation_view in relation_views:
            self._relation_view_repository.upsert_view(relation_view)
        result_list_kwargs = dict(input_list_kwargs)
        if relation_owner_agent_id is not None:
            result_list_kwargs["owner_agent_id"] = relation_owner_agent_id
        if relation_industry_instance_id is not None:
            result_list_kwargs["industry_instance_id"] = relation_industry_instance_id
        return self.list_relation_views(**result_list_kwargs)

    def delete_source(self, *, source_type: str, source_ref: str) -> int:
        existing_entries = self._fact_index_repository.list_entries(
            source_type=source_type,
            source_ref=source_ref,
            limit=None,
        )
        deleted = self._fact_index_repository.delete_by_source(
            source_type=source_type,
            source_ref=source_ref,
        )
        if deleted > 0:
            self._notify_sidecar_delete_entries(entry_ids=[entry.id for entry in existing_entries])
        return deleted

    def rebuild_all(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        include_reporting: bool = True,
        include_learning: bool = True,
        evidence_limit: int = 200,
    ) -> MemoryRebuildSummary:
        started_at = utc_now()
        normalized_scope_type = (
            normalize_memory_scope_type(scope_type)
            if isinstance(scope_type, str) and scope_type.strip()
            else None
        )
        normalized_scope_id = (
            normalize_scope_id(scope_id)
            if isinstance(scope_id, str) and scope_id.strip()
            else None
        )
        self._fact_index_repository.clear(
            scope_type=normalized_scope_type,
            scope_id=normalized_scope_id,
        )
        source_counts: Counter[str] = Counter()

        if self._strategy_repository is not None:
            for strategy in self._strategy_repository.list_strategies(
                scope_type=normalized_scope_type,
                scope_id=normalized_scope_id,
                limit=None,
            ):
                self.upsert_strategy_memory(strategy)
                source_counts["strategy_memory"] += 1

        if self._knowledge_repository is not None:
            for chunk in self._knowledge_repository.list_chunks():
                if not self._matches_chunk_scope(
                    chunk,
                    scope_type=normalized_scope_type,
                    scope_id=normalized_scope_id,
                ):
                    continue
                self.upsert_knowledge_chunk(chunk)
                source_counts["knowledge_chunk"] += 1

        if self._agent_report_repository is not None:
            report_filters: dict[str, Any] = {"limit": None}
            if normalized_scope_type == "work_context" and normalized_scope_id:
                report_filters["work_context_id"] = normalized_scope_id
            if normalized_scope_type == "industry" and normalized_scope_id:
                report_filters["industry_instance_id"] = normalized_scope_id
            for report in self._agent_report_repository.list_reports(**report_filters):
                if not self._matches_record_scope(
                    record_scope_type=(
                        "work_context"
                        if report.work_context_id
                        else "industry"
                    ),
                    record_scope_id=report.work_context_id or report.industry_instance_id,
                    scope_type=normalized_scope_type,
                    scope_id=normalized_scope_id,
                ):
                    continue
                self.upsert_agent_report(report)
                source_counts["agent_report"] += 1

        routine_by_id: dict[str, Any] = {}
        if self._routine_repository is not None:
            routine_by_id = {
                routine.id: routine
                for routine in self._routine_repository.list_routines(limit=None)
            }
        if self._routine_run_repository is not None:
            for run in self._routine_run_repository.list_runs(limit=None):
                routine = routine_by_id.get(run.routine_id)
                if not self._matches_routine_scope(
                    run=run,
                    routine=routine,
                    scope_type=normalized_scope_type,
                    scope_id=normalized_scope_id,
                ):
                    continue
                self.upsert_routine_run(run, routine=routine)
                source_counts["routine_run"] += 1

        if include_reporting:
            for report in self._iter_report_snapshots(
                scope_type=normalized_scope_type,
                scope_id=normalized_scope_id,
            ):
                self.upsert_report_snapshot(report)
                source_counts["report_snapshot"] += 1

        if include_learning:
            for patch in self._iter_learning_patches(
                scope_type=normalized_scope_type,
                scope_id=normalized_scope_id,
            ):
                self.upsert_learning_patch(patch)
                source_counts["learning_patch"] += 1
            for growth in self._iter_learning_growth(
                scope_type=normalized_scope_type,
                scope_id=normalized_scope_id,
            ):
                self.upsert_learning_growth(growth)
                source_counts["learning_growth"] += 1

        if self._evidence_ledger is not None:
            for evidence in self._iter_evidence_records(
                scope_type=normalized_scope_type,
                scope_id=normalized_scope_id,
                limit=evidence_limit,
            ):
                self.upsert_evidence(evidence)
                source_counts["evidence"] += 1

        completed_at = utc_now()
        all_entries = self._fact_index_repository.list_entries(limit=None)
        fact_index_count = len(
            [
                entry
                for entry in all_entries
                if self._matches_record_scope(
                    record_scope_type=entry.scope_type,
                    record_scope_id=entry.scope_id,
                    scope_type=normalized_scope_type,
                    scope_id=normalized_scope_id,
                )
            ]
        )
        self._notify_sidecar_replace(entries=all_entries)
        metadata = {
            "include_reporting": include_reporting,
            "include_learning": include_learning,
            "evidence_limit": evidence_limit,
        }
        return MemoryRebuildSummary(
            scope_type=normalized_scope_type,
            scope_id=normalized_scope_id,
            fact_index_count=fact_index_count,
            source_counts=dict(source_counts),
            started_at=started_at,
            completed_at=completed_at,
            metadata=metadata,
        )

    def upsert_knowledge_chunk(self, chunk: KnowledgeChunkRecord) -> MemoryFactIndexRecord:
        parsed_scope = parse_memory_document_id(chunk.document_id)
        scope_type, scope_id = (
            parsed_scope
            if parsed_scope is not None
            else ("global", normalize_scope_id(chunk.document_id))
        )
        title = truncate_text(chunk.title or chunk.document_id, max_length=160) or "Knowledge Chunk"
        summary = truncate_text(chunk.summary or chunk.content, max_length=320)
        content_excerpt = truncate_text(chunk.content, max_length=320)
        content_text = "\n".join(part for part in (chunk.title, chunk.summary, chunk.content) if part).strip()
        explicit_entities = [
            scope_id,
            *(chunk.tags or []),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=title,
            summary=summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        opinion_keys = extract_opinion_keys(content_text, entity_keys=entity_keys)
        evidence_refs = [chunk.source_ref] if chunk.source_ref else []
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("knowledge_chunk", chunk.id),
            source_type="knowledge_chunk",
            source_ref=chunk.id,
            scope_type=scope_type,
            scope_id=scope_id,
            title=title,
            summary=summary,
            content_excerpt=content_excerpt,
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=opinion_keys,
            tags=list(dict.fromkeys(["knowledge", *(chunk.tags or [])])),
            role_bindings=list(chunk.role_bindings or []),
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="knowledge_chunk",
                status="active" if parsed_scope is not None else None,
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=chunk.updated_at or chunk.created_at,
            metadata={
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "source_ref": chunk.source_ref,
                "entity_labels": entity_labels,
                "source_route": f"/api/runtime-center/knowledge/{chunk.id}",
                "memory_type": derive_memory_type(
                    source_type="knowledge_chunk",
                    tags=chunk.tags or [],
                    evidence_refs=evidence_refs,
                ),
                "relation_kind": "references",
                "subject_key": derive_subject_key(
                    source_type="knowledge_chunk",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    title=title,
                    explicit=None,
                ),
                "is_latest": True,
                "valid_from": (chunk.created_at or utc_now()).isoformat(),
                "expires_at": None,
                "confidence_tier": derive_confidence_tier(
                    derive_confidence(
                        source_type="knowledge_chunk",
                        status="active" if parsed_scope is not None else None,
                        evidence_refs=evidence_refs,
                    ),
                ),
            },
            created_at=chunk.created_at,
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def upsert_strategy_memory(self, strategy: StrategyMemoryRecord) -> MemoryFactIndexRecord:
        content_text = "\n".join(
            part
            for part in (
                strategy.summary,
                strategy.mission,
                strategy.north_star,
                *strategy.priority_order,
                *strategy.delegation_policy,
                *strategy.direct_execution_policy,
                *strategy.execution_constraints,
                *strategy.evidence_requirements,
                *strategy.current_focuses,
            )
            if part
        ).strip()
        explicit_entities = [
            strategy.scope_id,
            strategy.industry_instance_id,
            *(strategy.paused_lane_ids or []),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=strategy.title,
            summary=strategy.summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = [strategy.source_ref] if strategy.source_ref else []
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("strategy_memory", strategy.strategy_id),
            source_type="strategy_memory",
            source_ref=strategy.strategy_id,
            scope_type=normalize_memory_scope_type(strategy.scope_type),
            scope_id=normalize_scope_id(strategy.scope_id),
            owner_agent_id=strategy.owner_agent_id,
            owner_scope=strategy.owner_scope,
            industry_instance_id=strategy.industry_instance_id,
            title=truncate_text(strategy.title, max_length=160) or "Strategy Memory",
            summary=truncate_text(strategy.summary or strategy.north_star, max_length=320),
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=["strategy", strategy.status],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="strategy_memory",
                status=strategy.status,
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=strategy.summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=strategy.updated_at or strategy.created_at,
            metadata={
                "entity_labels": entity_labels,
                "strategy_id": strategy.strategy_id,
                "source_ref": strategy.source_ref,
                "source_route": "/api/runtime-center/strategy-memory",
                "status": strategy.status,
                "memory_type": "fact",
                "relation_kind": "derives",
                "subject_key": derive_subject_key(
                    source_type="strategy_memory",
                    scope_type=normalize_memory_scope_type(strategy.scope_type),
                    scope_id=normalize_scope_id(strategy.scope_id),
                    title=strategy.title,
                    explicit=strategy.strategy_id,
                ),
                "is_latest": strategy.status == "active",
                "valid_from": (strategy.created_at or utc_now()).isoformat(),
                "expires_at": None,
                "confidence_tier": derive_confidence_tier(
                    derive_confidence(
                        source_type="strategy_memory",
                        status=strategy.status,
                        evidence_refs=evidence_refs,
                    ),
                ),
                "mission": strategy.mission,
                "execution_constraints": list(strategy.execution_constraints or []),
                "evidence_requirements": list(strategy.evidence_requirements or []),
                "current_focuses": list(strategy.current_focuses or []),
            },
            created_at=strategy.created_at,
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def upsert_agent_report(self, report: AgentReportRecord) -> MemoryFactIndexRecord:
        content_text = "\n".join(
            part
            for part in (
                report.headline,
                report.summary,
                str(report.metadata or ""),
            )
            if part
        ).strip()
        explicit_entities: list[str] = []
        entity_keys, entity_labels = extract_entity_candidates(
            title=report.headline,
            summary=report.summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = list(report.evidence_ids or [])
        scope_type = "work_context" if report.work_context_id else "industry"
        scope_id = normalize_scope_id(report.work_context_id or report.industry_instance_id)
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("agent_report", report.id),
            source_type="agent_report",
            source_ref=report.id,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=report.owner_agent_id,
            industry_instance_id=report.industry_instance_id,
            title=truncate_text(report.headline, max_length=160) or "Agent Report",
            summary=truncate_text(report.summary or report.headline, max_length=320),
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=[
                "agent-report",
                str(report.report_kind or "task-terminal"),
                str(report.status or "recorded"),
                str(report.result or "unknown"),
            ],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="agent_report",
                status=report.result or report.status,
                processed=report.processed,
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=report.summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=report.updated_at or report.created_at,
            metadata={
                "entity_labels": entity_labels,
                "goal_id": report.goal_id,
                "task_id": report.task_id,
                "work_context_id": report.work_context_id,
                "assignment_id": report.assignment_id,
                "lane_id": report.lane_id,
                "result": report.result,
                "status": report.status,
                "source_route": (
                    f"/api/runtime-center/industry/{report.industry_instance_id}"
                    if report.industry_instance_id
                    else None
                ),
                "memory_type": derive_memory_type(
                    source_type="agent_report",
                    evidence_refs=evidence_refs,
                ),
                "relation_kind": "derives",
                "subject_key": derive_subject_key(
                    source_type="agent_report",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    title=report.headline,
                    explicit=report.task_id or report.work_context_id or report.goal_id,
                ),
                "is_latest": True,
                "valid_from": (report.created_at or utc_now()).isoformat(),
                "expires_at": None,
                "confidence_tier": derive_confidence_tier(
                    derive_confidence(
                        source_type="agent_report",
                        status=report.result or report.status,
                        processed=report.processed,
                        evidence_refs=evidence_refs,
                    ),
                ),
            },
            created_at=report.created_at,
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def _resolve_routine_scope(
        self,
        *,
        run: RoutineRunRecord,
        routine: object | None = None,
    ) -> tuple[str, str, str | None]:
        routine_owner_scope = _safe_getattr(routine, "owner_scope")
        routine_owner_agent_id = _safe_getattr(routine, "owner_agent_id")
        industry_instance_id = (
            str(run.metadata.get("industry_instance_id") or "").strip()
            if isinstance(run.metadata, dict)
            else ""
        ) or None
        if industry_instance_id:
            return "industry", industry_instance_id, industry_instance_id
        if run.owner_agent_id or routine_owner_agent_id:
            return "agent", normalize_scope_id(run.owner_agent_id or routine_owner_agent_id), None
        if run.source_ref:
            prefix = str(run.source_ref).split(":", 1)[0].strip().lower()
            if prefix == "task":
                return "task", normalize_scope_id(run.source_ref.split(":", 1)[-1]), None
        return "global", normalize_scope_id(run.owner_scope or routine_owner_scope), None

    def upsert_routine_run(
        self,
        run: RoutineRunRecord,
        *,
        routine: object | None = None,
    ) -> MemoryFactIndexRecord:
        routine_owner_scope = _safe_getattr(routine, "owner_scope")
        routine_owner_agent_id = _safe_getattr(routine, "owner_agent_id")
        routine_summary = _safe_getattr(routine, "summary")
        routine_name = _safe_getattr(routine, "name")
        scope_type, scope_id, industry_instance_id = self._resolve_routine_scope(
            run=run,
            routine=routine,
        )
        title = truncate_text(
            f"{routine_name or 'Routine'} {run.status}",
            max_length=160,
        ) or "Routine Run"
        summary = truncate_text(
            run.output_summary or routine_summary or title,
            max_length=320,
        )
        content_text = "\n".join(
            part
            for part in (
                routine_name,
                routine_summary,
                run.output_summary,
                run.failure_class,
                run.fallback_mode,
                run.deterministic_result,
                str(run.metadata or ""),
            )
            if part
        ).strip()
        explicit_entities = [
            scope_id,
            run.owner_agent_id,
            run.routine_id,
            run.session_id,
            run.environment_id,
            run.failure_class,
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=title,
            summary=summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = list(run.evidence_ids or [])
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("routine_run", run.id),
            source_type="routine_run",
            source_ref=run.id,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=run.owner_agent_id or routine_owner_agent_id,
            owner_scope=run.owner_scope or routine_owner_scope,
            industry_instance_id=industry_instance_id,
            title=title,
            summary=summary,
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=[
                "routine-run",
                str(run.status or "unknown"),
                str(run.source_type or "manual"),
                str(_safe_getattr(routine, "engine_kind") or "engine"),
            ],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="routine_run",
                status=run.status,
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=run.completed_at or run.updated_at or run.created_at,
            metadata={
                "entity_labels": entity_labels,
                "routine_id": run.routine_id,
                "failure_class": run.failure_class,
                "fallback_mode": run.fallback_mode,
                "deterministic_result": run.deterministic_result,
                "source_route": f"/api/routines/runs/{run.id}",
                "memory_type": "episode",
                "relation_kind": "references",
                "subject_key": derive_subject_key(
                    source_type="routine_run",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    title=title,
                    explicit=run.routine_id or run.id,
                ),
                "is_latest": True,
                "valid_from": (run.created_at or utc_now()).isoformat(),
                "expires_at": None,
                "confidence_tier": derive_confidence_tier(
                    derive_confidence(
                        source_type="routine_run",
                        status=run.status,
                        evidence_refs=evidence_refs,
                    ),
                ),
            },
            created_at=run.created_at,
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def upsert_report_snapshot(self, report: ReportRecord) -> MemoryFactIndexRecord:
        scope_type = normalize_memory_scope_type(report.scope_type)
        scope_id = normalize_scope_id(report.scope_id)
        content_text = "\n".join(
            [
                report.summary,
                *list(report.highlights or []),
                *[
                    f"{metric.label}: {metric.display_value or metric.value}"
                    for metric in list(report.metrics or [])[:8]
                ],
            ]
        ).strip()
        explicit_entities = [
            scope_id,
            *(report.task_ids or []),
            *(report.agent_ids or []),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=report.title,
            summary=report.summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = list(report.evidence_ids or [])
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("report_snapshot", report.id),
            source_type="report_snapshot",
            source_ref=report.id,
            scope_type=scope_type,
            scope_id=scope_id,
            title=truncate_text(report.title, max_length=160) or "Report Snapshot",
            summary=truncate_text(report.summary, max_length=320),
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=["report", report.window, report.scope_type],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="report_snapshot",
                status=report.status,
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=report.summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=report.until or report.created_at,
            metadata={
                "entity_labels": entity_labels,
                "window": report.window,
                "routes": dict(report.routes or {}),
                "source_route": (
                    f"/api/runtime-center/reports?window={report.window}"
                    f"&scope_type={report.scope_type}&scope_id={scope_id}"
                ),
                "memory_type": "episode",
                "relation_kind": "derives",
                "subject_key": derive_subject_key(
                    source_type="report_snapshot",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    title=report.title,
                    explicit=report.id,
                ),
                "is_latest": True,
                "valid_from": (report.created_at or utc_now()).isoformat(),
                "expires_at": None,
                "confidence_tier": derive_confidence_tier(
                    derive_confidence(
                        source_type="report_snapshot",
                        status=report.status,
                        evidence_refs=evidence_refs,
                    ),
                ),
            },
            created_at=report.created_at,
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def upsert_evidence(self, evidence: object) -> MemoryFactIndexRecord:
        task_id = _safe_getattr(evidence, "task_id")
        evidence_id = str(_safe_getattr(evidence, "id") or "").strip()
        title = truncate_text(
            _safe_getattr(evidence, "action_summary") or evidence_id or "Evidence",
            max_length=160,
        ) or "Evidence"
        summary = truncate_text(_safe_getattr(evidence, "result_summary") or title, max_length=320)
        metadata = _safe_getattr(evidence, "metadata") or {}
        work_context_id = (
            str(metadata.get("work_context_id") or "").strip()
            if isinstance(metadata, dict)
            else ""
        ) or None
        scope_type = (
            "work_context"
            if work_context_id
            else "task"
            if task_id
            else "global"
        )
        scope_id = normalize_scope_id(work_context_id or task_id)
        content_text = "\n".join(
            part
            for part in (
                _safe_getattr(evidence, "action_summary"),
                _safe_getattr(evidence, "result_summary"),
                _safe_getattr(evidence, "capability_ref"),
                _safe_getattr(evidence, "actor_ref"),
                str(metadata),
            )
            if part
        ).strip()
        explicit_entities = [
            task_id,
            work_context_id,
            _safe_getattr(evidence, "actor_ref"),
            _safe_getattr(evidence, "capability_ref"),
            _safe_getattr(evidence, "environment_ref"),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=title,
            summary=summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = [evidence_id] if evidence_id else []
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("evidence", evidence_id),
            source_type="evidence",
            source_ref=evidence_id,
            scope_type=scope_type,
            scope_id=scope_id,
            title=title,
            summary=summary,
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=[
                "evidence",
                str(_safe_getattr(evidence, "status") or "recorded"),
                str(_safe_getattr(evidence, "risk_level") or "auto"),
            ],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="evidence",
                status=_safe_getattr(evidence, "status"),
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=_safe_getattr(evidence, "created_at"),
            metadata={
                "entity_labels": entity_labels,
                "actor_ref": _safe_getattr(evidence, "actor_ref"),
                "capability_ref": _safe_getattr(evidence, "capability_ref"),
                "environment_ref": _safe_getattr(evidence, "environment_ref"),
                "work_context_id": work_context_id,
                "source_route": (
                    f"/api/runtime-center/evidence/{evidence_id}"
                    if evidence_id
                    else None
                ),
                "memory_type": "fact",
                "relation_kind": "references",
                "subject_key": derive_subject_key(
                    source_type="evidence",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    title=title,
                    explicit=evidence_id or task_id,
                ),
                "is_latest": True,
                "valid_from": (_safe_getattr(evidence, "created_at") or utc_now()).isoformat(),
                "expires_at": None,
                "confidence_tier": derive_confidence_tier(
                    derive_confidence(
                        source_type="evidence",
                        status=_safe_getattr(evidence, "status"),
                        evidence_refs=evidence_refs,
                    ),
                ),
            },
            created_at=_safe_getattr(evidence, "created_at") or utc_now(),
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def _scope_from_learning_object(self, item: object) -> tuple[str, str]:
        task_id = _safe_getattr(item, "task_id")
        agent_id = _safe_getattr(item, "agent_id")
        goal_id = _safe_getattr(item, "goal_id")
        if task_id:
            return "task", normalize_scope_id(task_id)
        if agent_id:
            return "agent", normalize_scope_id(agent_id)
        if goal_id:
            return "global", normalize_scope_id(goal_id)
        return "global", "runtime"

    def upsert_learning_patch(self, patch: object) -> MemoryFactIndexRecord:
        source_ref = str(_safe_getattr(patch, "id") or "").strip()
        title = truncate_text(_safe_getattr(patch, "title") or "Learning Patch", max_length=160)
        summary = truncate_text(
            _safe_getattr(patch, "description") or _safe_getattr(patch, "diff_summary") or title,
            max_length=320,
        )
        content_text = "\n".join(
            part
            for part in (
                _safe_getattr(patch, "description"),
                _safe_getattr(patch, "diff_summary"),
                _safe_getattr(patch, "kind"),
                _safe_getattr(patch, "status"),
            )
            if part
        ).strip()
        scope_type, scope_id = self._scope_from_learning_object(patch)
        explicit_entities = [
            scope_id,
            _safe_getattr(patch, "agent_id"),
            _safe_getattr(patch, "goal_id"),
            _safe_getattr(patch, "task_id"),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=title,
            summary=summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = list(_safe_getattr(patch, "evidence_refs") or [])
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("learning_patch", source_ref),
            source_type="learning_patch",
            source_ref=source_ref,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=_safe_getattr(patch, "agent_id"),
            title=title or "Learning Patch",
            summary=summary,
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=[
                "learning",
                "patch",
                str(_safe_getattr(patch, "kind") or "patch"),
                str(_safe_getattr(patch, "status") or "proposed"),
            ],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="learning_patch",
                status=_safe_getattr(patch, "status"),
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=_safe_getattr(patch, "applied_at") or _safe_getattr(patch, "created_at"),
            metadata={
                "entity_labels": entity_labels,
                "kind": _safe_getattr(patch, "kind"),
                "status": _safe_getattr(patch, "status"),
                "source_route": f"/api/runtime-center/learning/patches/{source_ref}",
            },
            created_at=_safe_getattr(patch, "created_at") or utc_now(),
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def upsert_learning_growth(self, growth: object) -> MemoryFactIndexRecord:
        source_ref = str(_safe_getattr(growth, "id") or "").strip()
        title = truncate_text(_safe_getattr(growth, "description") or "Growth Event", max_length=160)
        summary = truncate_text(
            _safe_getattr(growth, "result") or _safe_getattr(growth, "description") or title,
            max_length=320,
        )
        content_text = "\n".join(
            part
            for part in (
                _safe_getattr(growth, "description"),
                _safe_getattr(growth, "result"),
                _safe_getattr(growth, "change_type"),
            )
            if part
        ).strip()
        scope_type, scope_id = self._scope_from_learning_object(growth)
        explicit_entities = [
            scope_id,
            _safe_getattr(growth, "agent_id"),
            _safe_getattr(growth, "goal_id"),
            _safe_getattr(growth, "task_id"),
        ]
        entity_keys, entity_labels = extract_entity_candidates(
            title=title,
            summary=summary,
            content_text=content_text,
            explicit=explicit_entities,
        )
        evidence_refs = [
            ref
            for ref in [_safe_getattr(growth, "source_evidence_id")]
            if isinstance(ref, str) and ref.strip()
        ]
        record = MemoryFactIndexRecord(
            id=self._stable_entry_id("learning_growth", source_ref),
            source_type="learning_growth",
            source_ref=source_ref,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=_safe_getattr(growth, "agent_id"),
            title=title or "Growth Event",
            summary=summary,
            content_excerpt=truncate_text(content_text, max_length=320),
            content_text=content_text,
            entity_keys=entity_keys,
            opinion_keys=extract_opinion_keys(content_text, entity_keys=entity_keys),
            tags=[
                "learning",
                "growth",
                str(_safe_getattr(growth, "change_type") or "growth"),
            ],
            evidence_refs=evidence_refs,
            confidence=derive_confidence(
                source_type="learning_growth",
                status="recorded",
                evidence_refs=evidence_refs,
            ),
            quality_score=derive_quality_score(
                content_text=content_text,
                summary=summary,
                evidence_refs=evidence_refs,
                entity_keys=entity_keys,
            ),
            source_updated_at=_safe_getattr(growth, "created_at"),
            metadata={
                "entity_labels": entity_labels,
                "change_type": _safe_getattr(growth, "change_type"),
                "source_patch_id": _safe_getattr(growth, "source_patch_id"),
                "source_route": f"/api/runtime-center/learning/growth/{source_ref}",
            },
            created_at=_safe_getattr(growth, "created_at") or utc_now(),
            updated_at=utc_now(),
        )
        stored = self._fact_index_repository.upsert_entry(record)
        self._notify_sidecar_upsert(stored)
        return stored

    def _notify_sidecar_replace(self, *, entries: list[MemoryFactIndexRecord]) -> None:
        for backend in self._sidecar_backends:
            replacer = getattr(backend, "replace_entries", None)
            if not callable(replacer):
                continue
            try:
                replacer(entries)
            except Exception:
                continue

    def _notify_sidecar_upsert(self, entry: MemoryFactIndexRecord) -> None:
        for backend in self._sidecar_backends:
            upsert = getattr(backend, "upsert_entry", None)
            if not callable(upsert):
                continue
            try:
                upsert(entry)
            except Exception:
                continue

    def _notify_sidecar_delete_entries(self, *, entry_ids: list[str]) -> None:
        if not entry_ids:
            return
        for backend in self._sidecar_backends:
            delete = getattr(backend, "delete_entries", None)
            if not callable(delete):
                continue
            try:
                delete(entry_ids)
            except Exception:
                continue

    def _iter_report_snapshots(
        self,
        *,
        scope_type: str | None,
        scope_id: str | None,
    ) -> Iterable[ReportRecord]:
        service = self._reporting_service
        getter = getattr(service, "get_report", None)
        if not callable(getter):
            return []
        windows = ("daily", "weekly", "monthly")
        reports: list[ReportRecord] = []
        if scope_type is not None and scope_id is not None:
            for window in windows:
                try:
                    report = getter(window=window, scope_type=scope_type, scope_id=scope_id)
                except Exception:
                    continue
                if report is not None:
                    reports.append(report)
            return reports

        for window in windows:
            try:
                report = getter(window=window, scope_type="global", scope_id=None)
            except Exception:
                continue
            if report is not None:
                reports.append(report)
        if self._industry_instance_repository is not None:
            for instance in self._industry_instance_repository.list_instances(limit=None):
                try:
                    report = getter(
                        window="weekly",
                        scope_type="industry",
                        scope_id=instance.instance_id,
                    )
                except Exception:
                    continue
                if report is not None:
                    reports.append(report)
        return reports

    def _iter_learning_patches(
        self,
        *,
        scope_type: str | None,
        scope_id: str | None,
    ) -> Iterable[object]:
        service = self._learning_service
        lister = getattr(service, "list_patches", None)
        if not callable(lister):
            return []
        try:
            patches = lister(limit=None)
        except Exception:
            return []
        return [
            patch
            for patch in patches
            if self._matches_learning_object_scope(
                patch,
                scope_type=scope_type,
                scope_id=scope_id,
            )
        ]

    def _iter_learning_growth(
        self,
        *,
        scope_type: str | None,
        scope_id: str | None,
    ) -> Iterable[object]:
        service = self._learning_service
        lister = getattr(service, "list_growth", None)
        if not callable(lister):
            return []
        try:
            growth_events = lister(limit=None)
        except Exception:
            return []
        return [
            growth
            for growth in growth_events
            if self._matches_learning_object_scope(
                growth,
                scope_type=scope_type,
                scope_id=scope_id,
            )
        ]

    def _iter_evidence_records(
        self,
        *,
        scope_type: str | None,
        scope_id: str | None,
        limit: int,
    ) -> Iterable[object]:
        if self._evidence_ledger is None:
            return []
        try:
            if scope_type == "task" and scope_id:
                return list(self._evidence_ledger.query_by_task(scope_id))
            records = self._evidence_ledger.list_records(limit=limit)
        except Exception:
            return []
        if scope_type is None or scope_id is None:
            return records
        if scope_type == "global":
            return records
        if scope_type == "agent":
            return [
                record
                for record in records
                if scope_id in str(_safe_getattr(record, "actor_ref") or "")
            ]
        return []

    def _matches_learning_object_scope(
        self,
        item: object,
        *,
        scope_type: str | None,
        scope_id: str | None,
    ) -> bool:
        if scope_type is None or scope_id is None:
            return True
        derived_scope_type, derived_scope_id = self._scope_from_learning_object(item)
        return self._matches_record_scope(
            record_scope_type=derived_scope_type,
            record_scope_id=derived_scope_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def _matches_chunk_scope(
        self,
        chunk: KnowledgeChunkRecord,
        *,
        scope_type: str | None,
        scope_id: str | None,
    ) -> bool:
        if scope_type is None or scope_id is None:
            return True
        parsed_scope = parse_memory_document_id(chunk.document_id)
        if parsed_scope is None:
            return scope_type == "global"
        return self._matches_record_scope(
            record_scope_type=parsed_scope[0],
            record_scope_id=parsed_scope[1],
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def _matches_routine_scope(
        self,
        *,
        run: RoutineRunRecord,
        routine: object | None,
        scope_type: str | None,
        scope_id: str | None,
    ) -> bool:
        if scope_type is None or scope_id is None:
            return True
        derived_scope_type, derived_scope_id, _industry_instance_id = self._resolve_routine_scope(
            run=run,
            routine=routine,
        )
        return self._matches_record_scope(
            record_scope_type=derived_scope_type,
            record_scope_id=derived_scope_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def _matches_record_scope(
        self,
        *,
        record_scope_type: str | None,
        record_scope_id: str | None,
        scope_type: str | None,
        scope_id: str | None,
    ) -> bool:
        if scope_type is None or scope_id is None:
            return True
        return (
            normalize_memory_scope_type(record_scope_type) == normalize_memory_scope_type(scope_type)
            and normalize_scope_id(record_scope_id) == normalize_scope_id(scope_id)
        )

    def _is_active_fact_entry(self, entry: MemoryFactIndexRecord) -> bool:
        if not bool(getattr(entry, "is_latest", True)):
            return False
        metadata = dict(getattr(entry, "metadata", {}) or {})
        status = str(
            metadata.get("knowledge_graph_status")
            or metadata.get("status")
            or "active",
        ).strip().lower()
        if status in {"superseded", "expired"}:
            return False
        expires_at = getattr(entry, "expires_at", None)
        if expires_at is not None and expires_at <= utc_now():
            return False
        return True

    def _is_active_relation_view(self, relation: MemoryRelationViewRecord) -> bool:
        metadata = dict(getattr(relation, "metadata", {}) or {})
        status = str(metadata.get("status") or "active").strip().lower()
        if status in {"superseded", "expired"}:
            return False
        valid_to = normalize_optional_text(metadata.get("valid_to"))
        if valid_to:
            try:
                if datetime.fromisoformat(valid_to) <= utc_now():
                    return False
            except ValueError:
                return False
        return True

    def _stable_entry_id(self, source_type: str, source_ref: object) -> str:
        return f"memory-index:{source_type}:{slugify(source_ref, fallback='entry')}"

    def _relation_scope_matches(
        self,
        *,
        candidate_scope_type: str | None,
        candidate_scope_id: str | None,
        relation_scope_type: str | None,
        relation_scope_id: str | None,
    ) -> bool:
        return self._matches_record_scope(
            record_scope_type=candidate_scope_type,
            record_scope_id=candidate_scope_id,
            scope_type=relation_scope_type,
            scope_id=relation_scope_id,
        )

    def _build_relation_views(
        self,
        *,
        fact_entries: list[MemoryFactIndexRecord],
        entity_views: list[MemoryEntityViewRecord],
        opinion_views: list[MemoryOpinionViewRecord],
        scope_type: str | None,
        scope_id: str | None,
        owner_agent_id: str | None,
        industry_instance_id: str | None,
    ) -> list[MemoryRelationViewRecord]:
        entities_by_key: dict[str, list[MemoryEntityViewRecord]] = {}
        for entity_view in entity_views:
            entity_key = str(getattr(entity_view, "entity_key", "") or "").strip()
            if not entity_key:
                continue
            entities_by_key.setdefault(entity_key, []).append(entity_view)

        opinions_by_key: dict[str, list[MemoryOpinionViewRecord]] = {}
        for opinion_view in opinion_views:
            opinion_key = str(getattr(opinion_view, "opinion_key", "") or "").strip()
            if not opinion_key:
                continue
            opinions_by_key.setdefault(opinion_key, []).append(opinion_view)

        relation_views: dict[str, MemoryRelationViewRecord] = {}
        for entry in fact_entries:
            fact_id = str(getattr(entry, "id"))
            fact_scope_type = normalize_memory_scope_type(
                scope_type or str(getattr(entry, "scope_type", "global"))
            )
            fact_scope_id = normalize_scope_id(scope_id or str(getattr(entry, "scope_id", "runtime")))
            fact_refs = set(
                dedupe_texts(
                    [
                        fact_id,
                        getattr(entry, "source_ref", None),
                        *list(getattr(entry, "evidence_refs", []) or []),
                    ],
                )
            )
            for entity_key in list(getattr(entry, "entity_keys", []) or []):
                for entity_view in entities_by_key.get(str(entity_key), []):
                    if not self._relation_scope_matches(
                        candidate_scope_type=_safe_getattr(entity_view, "scope_type"),
                        candidate_scope_id=_safe_getattr(entity_view, "scope_id"),
                        relation_scope_type=fact_scope_type,
                        relation_scope_id=fact_scope_id,
                    ):
                        continue
                    relation = self._make_relation_view(
                        source_node_id=fact_id,
                        target_node_id=str(getattr(entity_view, "entity_id")),
                        relation_kind="mentions",
                        scope_type=fact_scope_type,
                        scope_id=fact_scope_id,
                        owner_agent_id=owner_agent_id
                        or _safe_getattr(entry, "owner_agent_id")
                        or _safe_getattr(entity_view, "owner_agent_id"),
                        industry_instance_id=industry_instance_id
                        or _safe_getattr(entry, "industry_instance_id")
                        or _safe_getattr(entity_view, "industry_instance_id"),
                        summary=present_relation_summary(
                            source_text=getattr(entry, "title", "") or getattr(entry, "summary", ""),
                            relation_kind="mentions",
                            target_text=(
                                getattr(entity_view, "display_name", "")
                                or getattr(entity_view, "entity_key", "")
                            ),
                        ),
                        confidence=(
                            float(getattr(entry, "confidence", 0.0) or 0.0)
                            + float(getattr(entity_view, "confidence", 0.0) or 0.0)
                        )
                        / 2.0,
                        source_refs=dedupe_texts(
                            [
                                getattr(entry, "source_ref", None),
                                *list(getattr(entry, "evidence_refs", []) or []),
                                *list(getattr(entity_view, "source_refs", []) or []),
                                *list(getattr(entity_view, "supporting_refs", []) or []),
                            ],
                        ),
                        metadata={
                            "source_kind": "fact",
                            "target_kind": "entity",
                            "entity_key": getattr(entity_view, "entity_key", None),
                            "fact_source_type": getattr(entry, "source_type", None),
                        },
                    )
                    relation_views[relation.relation_id] = relation

            for opinion_key in list(getattr(entry, "opinion_keys", []) or []):
                for opinion_view in opinions_by_key.get(str(opinion_key), []):
                    if not self._relation_scope_matches(
                        candidate_scope_type=_safe_getattr(opinion_view, "scope_type"),
                        candidate_scope_id=_safe_getattr(opinion_view, "scope_id"),
                        relation_scope_type=fact_scope_type,
                        relation_scope_id=fact_scope_id,
                    ):
                        continue
                    opinion_support_refs = set(
                        dedupe_texts(getattr(opinion_view, "supporting_refs", []) or [])
                    )
                    opinion_contradiction_refs = set(
                        dedupe_texts(getattr(opinion_view, "contradicting_refs", []) or [])
                    )
                    relation_kind = "mentions"
                    if fact_refs.intersection(opinion_support_refs):
                        relation_kind = "supports"
                    elif fact_refs.intersection(opinion_contradiction_refs):
                        relation_kind = "contradicts"
                    relation = self._make_relation_view(
                        source_node_id=fact_id,
                        target_node_id=str(getattr(opinion_view, "opinion_id")),
                        relation_kind=relation_kind,
                        scope_type=fact_scope_type,
                        scope_id=fact_scope_id,
                        owner_agent_id=owner_agent_id
                        or _safe_getattr(entry, "owner_agent_id")
                        or _safe_getattr(opinion_view, "owner_agent_id"),
                        industry_instance_id=industry_instance_id
                        or _safe_getattr(entry, "industry_instance_id")
                        or _safe_getattr(opinion_view, "industry_instance_id"),
                        summary=present_fact_opinion_summary(
                            source_text=getattr(entry, "title", "") or getattr(entry, "summary", ""),
                            relation_kind=relation_kind,
                            opinion_key=str(getattr(opinion_view, "opinion_key", "") or ""),
                        ),
                        confidence=(
                            float(getattr(entry, "confidence", 0.0) or 0.0)
                            + float(getattr(opinion_view, "confidence", 0.0) or 0.0)
                        )
                        / 2.0,
                        source_refs=dedupe_texts(
                            [
                                getattr(entry, "source_ref", None),
                                *list(getattr(entry, "evidence_refs", []) or []),
                                *list(getattr(opinion_view, "source_refs", []) or []),
                                *list(getattr(opinion_view, "supporting_refs", []) or []),
                                *list(getattr(opinion_view, "contradicting_refs", []) or []),
                            ],
                        ),
                        metadata={
                            "source_kind": "fact",
                            "target_kind": "opinion",
                            "opinion_key": getattr(opinion_view, "opinion_key", None),
                            "subject_key": getattr(opinion_view, "subject_key", None),
                        },
                    )
                    relation_views[relation.relation_id] = relation

        for opinion_view in opinion_views:
            opinion_scope_type = normalize_memory_scope_type(
                scope_type or str(getattr(opinion_view, "scope_type", "global"))
            )
            opinion_scope_id = normalize_scope_id(
                scope_id or str(getattr(opinion_view, "scope_id", "runtime"))
            )
            opinion_support_refs = set(
                dedupe_texts(getattr(opinion_view, "supporting_refs", []) or [])
            )
            opinion_contradiction_refs = set(
                dedupe_texts(getattr(opinion_view, "contradicting_refs", []) or [])
            )
            for entity_key in dedupe_texts(
                [
                    getattr(opinion_view, "subject_key", None),
                    *list(getattr(opinion_view, "entity_keys", []) or []),
                ],
            ):
                for entity_view in entities_by_key.get(entity_key, []):
                    if not self._relation_scope_matches(
                        candidate_scope_type=_safe_getattr(entity_view, "scope_type"),
                        candidate_scope_id=_safe_getattr(entity_view, "scope_id"),
                        relation_scope_type=opinion_scope_type,
                        relation_scope_id=opinion_scope_id,
                    ):
                        continue
                    entity_support_refs = set(
                        dedupe_texts(getattr(entity_view, "supporting_refs", []) or [])
                    )
                    entity_contradiction_refs = set(
                        dedupe_texts(getattr(entity_view, "contradicting_refs", []) or [])
                    )
                    relation_kind = "mentions"
                    if opinion_support_refs.intersection(entity_support_refs):
                        relation_kind = "supports"
                    elif (
                        opinion_contradiction_refs.intersection(entity_support_refs)
                        or opinion_support_refs.intersection(entity_contradiction_refs)
                    ):
                        relation_kind = "contradicts"
                    relation = self._make_relation_view(
                        source_node_id=str(getattr(opinion_view, "opinion_id")),
                        target_node_id=str(getattr(entity_view, "entity_id")),
                        relation_kind=relation_kind,
                        scope_type=opinion_scope_type,
                        scope_id=opinion_scope_id,
                        owner_agent_id=owner_agent_id
                        or _safe_getattr(opinion_view, "owner_agent_id")
                        or _safe_getattr(entity_view, "owner_agent_id"),
                        industry_instance_id=industry_instance_id
                        or _safe_getattr(opinion_view, "industry_instance_id")
                        or _safe_getattr(entity_view, "industry_instance_id"),
                        summary=present_relation_summary(
                            source_text=humanize_opinion_key(getattr(opinion_view, "opinion_key", "")),
                            relation_kind=relation_kind,
                            target_text=(
                                getattr(entity_view, "display_name", "")
                                or getattr(entity_view, "entity_key", "")
                            ),
                        ),
                        confidence=(
                            float(getattr(opinion_view, "confidence", 0.0) or 0.0)
                            + float(getattr(entity_view, "confidence", 0.0) or 0.0)
                        )
                        / 2.0,
                        source_refs=dedupe_texts(
                            [
                                *list(getattr(opinion_view, "source_refs", []) or []),
                                *list(getattr(opinion_view, "supporting_refs", []) or []),
                                *list(getattr(opinion_view, "contradicting_refs", []) or []),
                                *list(getattr(entity_view, "source_refs", []) or []),
                            ],
                        ),
                        metadata={
                            "source_kind": "opinion",
                            "target_kind": "entity",
                            "entity_key": getattr(entity_view, "entity_key", None),
                            "opinion_key": getattr(opinion_view, "opinion_key", None),
                        },
                    )
                    relation_views[relation.relation_id] = relation

        return list(relation_views.values())

    def _make_relation_view(
        self,
        *,
        source_node_id: str,
        target_node_id: str,
        relation_kind: str,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None,
        industry_instance_id: str | None,
        summary: str,
        confidence: float,
        source_refs: list[str],
        metadata: dict[str, Any],
    ) -> MemoryRelationViewRecord:
        normalized_scope_type = normalize_memory_scope_type(scope_type)
        normalized_scope_id = normalize_scope_id(scope_id)
        normalized_relation_kind = str(relation_kind or "references").strip().lower() or "references"
        return MemoryRelationViewRecord(
            relation_id=(
                f"memory-relation:{slugify(normalized_scope_type)}:{slugify(normalized_scope_id)}:"
                f"{slugify(source_node_id)}:{slugify(normalized_relation_kind)}:{slugify(target_node_id)}"
            ),
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relation_kind=normalized_relation_kind,
            scope_type=normalized_scope_type,
            scope_id=normalized_scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            summary=truncate_text(summary, max_length=320),
            confidence=max(0.0, min(round(confidence, 4), 1.0)),
            source_refs=source_refs,
            metadata=metadata,
            updated_at=utc_now(),
        )
