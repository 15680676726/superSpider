# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from hashlib import sha1
import logging
from pathlib import Path
import re
from typing import Any, Mapping

from ..constant import WORKING_DIR
from ..environments.surface_execution.browser import (
    BrowserPageProfile,
    BrowserTargetCandidate,
)
from ..environments.surface_execution.browser.service import BrowserSurfaceExecutionService
from ..state import AgentReportRecord, ResearchSessionRecord, ResearchSessionRoundRecord
from .baidu_page_contract import extract_answer_contract
from .chat_continuation_owner import ResearchChatContinuationOwner
from .models import ResearchLink, ResearchSessionRunResult
from .source_collection.contracts import ResearchAdapterResult
from .surface_loop_owner import ResearchChatSurfaceLoopOwner

logger = logging.getLogger(__name__)
_LATIN_TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.IGNORECASE)
_CJK_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_SEMANTIC_STOPWORDS = {
    "about",
    "answer",
    "answers",
    "clarify",
    "common",
    "continue",
    "current",
    "detail",
    "details",
    "evidence",
    "follow",
    "goal",
    "give",
    "hint",
    "hints",
    "important",
    "into",
    "misunderstanding",
    "more",
    "most",
    "need",
    "please",
    "question",
    "research",
    "researching",
    "source",
    "sources",
    "that",
    "these",
    "this",
    "those",
    "what",
    "when",
    "where",
    "which",
    "with",
    "your",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: object | None) -> str:
    return str(value or "").strip()


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if value is not None and is_dataclass(value):
        payload = asdict(value)
        if isinstance(payload, dict):
            return dict(payload)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return dict(namespace)
    return {}


def _mapping_list(value: object | None) -> list[dict[str, Any]]:
    if isinstance(value, list):
        items = value
    elif value is None:
        items = []
    else:
        items = [value]
    normalized: list[dict[str, Any]] = []
    for item in items:
        mapping = _mapping(item)
        if mapping:
            normalized.append(mapping)
    return normalized


def _optional_bool(value: object | None) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    text = _text(value).lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def _repo_list_sessions(repository: object, **kwargs: Any) -> list[ResearchSessionRecord]:
    lister = getattr(repository, "list_research_sessions", None)
    if not callable(lister):
        return []
    try:
        return list(lister(**kwargs) or [])
    except TypeError:
        return list(lister() or [])


def _repo_list_rounds(repository: object, *, session_id: str) -> list[ResearchSessionRoundRecord]:
    lister = getattr(repository, "list_research_rounds", None)
    if not callable(lister):
        return []
    try:
        return list(lister(session_id=session_id) or [])
    except TypeError:
        return list(lister(session_id) or [])


def _unique_rounds(rounds: list[ResearchSessionRoundRecord]) -> list[ResearchSessionRoundRecord]:
    by_id: dict[str, ResearchSessionRoundRecord] = {}
    for round_record in rounds:
        by_id[round_record.id] = round_record
    return sorted(
        by_id.values(),
        key=lambda item: (item.round_index, item.updated_at or item.created_at),
    )


def _split_sentences(text: str) -> list[str]:
    normalized = _text(text)
    if not normalized:
        return []
    normalized = normalized.replace("\u200b", " ").replace("\u200c", " ")
    for marker in (".", "?", "!", ";", "。", "？", "！", "；"):
        normalized = normalized.replace(marker, "\n")
    return [
        sentence
        for sentence in (chunk.strip() for chunk in normalized.splitlines())
        if sentence
    ]


def _dedupe_texts(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _text(value)
        if not normalized:
            continue
        lowered = normalized.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(normalized)
    return deduped


def _link_payload(link: ResearchLink | Mapping[str, object]) -> dict[str, Any]:
    if isinstance(link, ResearchLink):
        return asdict(link)
    payload = dict(link)
    payload["url"] = _text(payload.get("url"))
    payload["label"] = _text(payload.get("label"))
    payload["kind"] = _text(payload.get("kind")) or "link"
    return payload


def _artifact_kind(item: Mapping[str, object]) -> str:
    path = _text(item.get("path") or item.get("suggested_filename"))
    if path.lower().endswith(".pdf"):
        return "pdf"
    return _text(item.get("kind")) or "artifact"


def _stable_id(prefix: str, *parts: object) -> str:
    normalized = "|".join(_text(part) for part in parts if _text(part))
    digest = sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _safe_path_token(value: object | None) -> str:
    raw = _text(value)
    if not raw:
        return "default"
    normalized = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in raw
    ).strip("-")
    return normalized or "default"


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= character <= "\u9fff" for character in text)


def _question_signature(value: object | None) -> str:
    normalized = _text(value).casefold()
    if not normalized:
        return ""
    return re.sub(r"\s+", " ", normalized)


def _semantic_tokens(text: object | None) -> set[str]:
    normalized = _text(text)
    if not normalized:
        return set()
    latin_tokens = {
        token
        for token in _LATIN_TOKEN_RE.findall(normalized.casefold())
        if token not in _SEMANTIC_STOPWORDS
    }
    cjk_tokens: set[str] = set()
    for chunk in _CJK_TOKEN_RE.findall(normalized):
        if len(chunk) <= 4:
            cjk_tokens.add(chunk)
            continue
        cjk_tokens.update(chunk[index : index + 2] for index in range(len(chunk) - 1))
    return {token for token in [*latin_tokens, *cjk_tokens] if token}


def _token_overlap_ratio(left: object | None, right: object | None) -> float:
    left_tokens = _semantic_tokens(left)
    right_tokens = _semantic_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))


def _is_semantic_duplicate(candidate: object | None, existing_values: list[str]) -> bool:
    candidate_signature = _question_signature(candidate)
    if not candidate_signature:
        return False
    for existing in existing_values:
        existing_signature = _question_signature(existing)
        if not existing_signature:
            continue
        if (
            candidate_signature == existing_signature
            or candidate_signature in existing_signature
            or existing_signature in candidate_signature
        ):
            return True
        if _token_overlap_ratio(candidate_signature, existing_signature) >= 0.8:
            return True
    return False


def _meaningful_new_findings(findings: list[str], existing_values: list[str]) -> list[str]:
    meaningful: list[str] = []
    baseline = list(existing_values)
    for item in findings:
        normalized = _text(item)
        if not normalized:
            continue
        if _is_semantic_duplicate(normalized, baseline):
            continue
        meaningful.append(normalized)
        baseline.append(normalized)
    return meaningful


def _tail_lines(previous_text: object | None, current_text: object | None) -> str:
    previous_lines = [line for line in (_text(item) for item in str(previous_text or "").splitlines()) if line]
    current_lines = [line for line in (_text(item) for item in str(current_text or "").splitlines()) if line]
    index = 0
    max_index = min(len(previous_lines), len(current_lines))
    while index < max_index and previous_lines[index] == current_lines[index]:
        index += 1
    if index >= len(current_lines):
        return str(current_text or "")
    return "\n".join(current_lines[index:])


def _strip_continuation_prefix(question: object | None) -> str:
    normalized = _text(question)
    if not normalized:
        return ""
    prefixes = (
        "continue researching this question:",
        "continue researching:",
        "continue this research question:",
        "继续把这个问题问清楚：",
        "继续研究这个问题：",
        "继续研究：",
    )
    lowered = normalized.casefold()
    for prefix in prefixes:
        if lowered.startswith(prefix.casefold()):
            return normalized[len(prefix) :].strip()
    return normalized


class BaiduPageResearchService:
    BAIDU_CHAT_URL = "https://chat.baidu.com/search"
    MAX_ROUNDS = 5
    MAX_LINK_DEPTH = 3
    MAX_DOWNLOADS = 2
    MAX_CONSECUTIVE_NO_NEW_FINDINGS = 2
    DEFAULT_RESPONSE_WAIT_SECONDS = 8

    def __init__(
        self,
        *,
        research_session_repository: object,
        browser_action_runner: object | None = None,
        browser_download_resolver: object | None = None,
        report_repository: object | None = None,
        knowledge_service: object | None = None,
        work_context_service: object | None = None,
        knowledge_writeback_service: object | None = None,
    ) -> None:
        self._research_session_repository = research_session_repository
        self._browser_action_runner = browser_action_runner
        self._browser_download_resolver = browser_download_resolver
        self._report_repository = report_repository
        self._knowledge_service = knowledge_service
        self._work_context_service = work_context_service
        self._knowledge_writeback_service = knowledge_writeback_service
        self._browser_surface_service = BrowserSurfaceExecutionService(
            browser_runner=self._browser_call,
        )

    def start_session(
        self,
        *,
        goal: str,
        trigger_source: str,
        owner_agent_id: str,
        industry_instance_id: str | None = None,
        work_context_id: str | None = None,
        supervisor_agent_id: str | None = "main-brain",
        metadata: dict[str, Any] | None = None,
    ) -> ResearchSessionRunResult:
        now = _utc_now()
        normalized_metadata = dict(metadata or {})
        brief_payload = _mapping(normalized_metadata.get("brief"))
        initial_question = _text(brief_payload.get("question")) or goal
        session = ResearchSessionRecord(
            id=_stable_id("research-session", owner_agent_id, goal, now.isoformat()),
            provider="baidu-page",
            industry_instance_id=_text(industry_instance_id) or None,
            work_context_id=_text(work_context_id) or None,
            owner_agent_id=owner_agent_id,
            supervisor_agent_id=_text(supervisor_agent_id) or None,
            trigger_source=trigger_source,
            goal=goal,
            status="queued",
            round_count=1,
            brief=brief_payload,
            metadata=normalized_metadata,
            created_at=now,
            updated_at=now,
        )
        first_round = ResearchSessionRoundRecord(
            id=self._round_id(session.id, 1),
            session_id=session.id,
            round_index=1,
            question=initial_question,
            generated_prompt=self._build_round_prompt(goal=goal, round_index=1),
            created_at=now,
            updated_at=now,
        )
        self._upsert_session(session)
        self._upsert_round(first_round)
        return ResearchSessionRunResult(session=session, rounds=[first_round])

    def resume_session(
        self,
        *,
        session_id: str,
        question: str,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchSessionRunResult:
        session = self._get_session(session_id)
        if session is None:
            raise KeyError(f"Unknown research session: {session_id}")
        rounds = _unique_rounds(_repo_list_rounds(self._research_session_repository, session_id=session.id))
        next_round_index = (rounds[-1].round_index if rounds else 0) + 1
        now = _utc_now()
        next_round = ResearchSessionRoundRecord(
            id=self._round_id(session.id, next_round_index),
            session_id=session.id,
            round_index=next_round_index,
            question=_text(question) or session.goal,
            generated_prompt=self._build_round_prompt(goal=session.goal, round_index=next_round_index),
            metadata={
                "entry_mode": "resume-followup",
                **dict(metadata or {}),
            },
            created_at=now,
            updated_at=now,
        )
        updated_brief = dict(session.brief)
        if _text(question):
            updated_brief["question"] = _text(question)
        updated_session = session.model_copy(
            update={
                "status": "queued",
                "round_count": max(session.round_count, next_round_index),
                "brief": updated_brief,
                "updated_at": now,
                "completed_at": None,
            },
        )
        self._upsert_session(updated_session)
        appended_round = self._upsert_round(next_round)
        return ResearchSessionRunResult(
            session=updated_session,
            rounds=[*rounds, appended_round],
        )

    def run_session(self, session_id: str) -> ResearchSessionRunResult:
        session = self._get_session(session_id)
        if session is None:
            raise KeyError(f"Unknown research session: {session_id}")
        rounds = _unique_rounds(_repo_list_rounds(self._research_session_repository, session_id=session.id))
        if not rounds:
            raise RuntimeError("Research session is missing its initial round")

        browser_session_id = self._ensure_browser_session(session)
        session = session.model_copy(
            update={
                "browser_session_id": browser_session_id,
                "status": "running",
                "updated_at": _utc_now(),
            },
        )
        self._upsert_session(session)

        deepened_links: list[dict[str, Any]] = []
        downloaded_artifacts: list[dict[str, Any]] = []
        visited_links: set[str] = set()
        consecutive_no_new_findings = 0
        stop_reason: str | None = None
        current_url = self.BAIDU_CHAT_URL
        chat_page_id = f"{session.id}:chat"
        chat_page_ready = False
        last_chat_snapshot: dict[str, Any] | None = None
        rounds_processed = 0

        while rounds_processed < self.MAX_ROUNDS:
            current_round = rounds[-1]
            rounds_processed += 1
            is_chat_round = _text(current_url) in {"", self.BAIDU_CHAT_URL}
            submission_metadata: dict[str, Any] = {}
            response_readback: dict[str, Any] | None = None
            if is_chat_round:
                if not chat_page_ready:
                    self._ensure_chat_page(
                        session_id=browser_session_id,
                        page_id=chat_page_id,
                    )
                    chat_page_ready = True
                submission_metadata = self._submit_chat_question(
                    session_id=browser_session_id,
                    page_id=chat_page_id,
                    question=current_round.question,
                )
                if bool(submission_metadata.get("pre_submit_login_required")):
                    response_readback = _mapping(submission_metadata.get("response_readback"))
                    updated_round = current_round.model_copy(
                        update={
                            "response_summary": "Login required before continuing research.",
                            "decision": "login_required",
                            "metadata": {
                                **current_round.metadata,
                                **submission_metadata,
                            },
                            "updated_at": _utc_now(),
                        },
                    )
                    rounds[-1] = self._upsert_round(updated_round)
                    session = session.model_copy(
                        update={
                            "status": "waiting-login",
                            "updated_at": _utc_now(),
                        },
                    )
                    self._upsert_session(session)
                    return ResearchSessionRunResult(
                        session=session,
                        rounds=_unique_rounds(rounds),
                        stop_reason="waiting-login",
                        deepened_links=deepened_links,
                        downloaded_artifacts=downloaded_artifacts,
                    )
                self._browser_call(
                    action="wait_for",
                    session_id=browser_session_id,
                    page_id=chat_page_id,
                    wait_time=self.DEFAULT_RESPONSE_WAIT_SECONDS,
                )
                snapshot = self._browser_call(
                    action="evaluate",
                    session_id=browser_session_id,
                    page_id=chat_page_id,
                    code=(
                        "({"
                        " html: document.documentElement.outerHTML || '',"
                        " bodyText: (document.body && document.body.innerText) ? "
                        "document.body.innerText : '',"
                        " href: location.href || '',"
                        " title: document.title || ''"
                        "})"
                    ),
                ).get("result")
                contract = self._extract_chat_contract(
                    previous_snapshot=last_chat_snapshot,
                    current_snapshot=snapshot,
                )
                response_readback = self._build_response_readback(
                    snapshot=snapshot,
                    contract=contract,
                )
                last_chat_snapshot = _mapping(snapshot)
            else:
                self._browser_call(
                    action="open",
                    session_id=browser_session_id,
                    page_id=current_round.id,
                    url=current_url,
                )
                self._browser_call(
                    action="wait_for",
                    session_id=browser_session_id,
                    page_id=current_round.id,
                    wait_time=self.DEFAULT_RESPONSE_WAIT_SECONDS,
                )
                snapshot = self._browser_call(
                    action="evaluate",
                    session_id=browser_session_id,
                    page_id=current_round.id,
                    code=(
                        "({"
                        " html: document.documentElement.outerHTML || '',"
                        " bodyText: (document.body && document.body.innerText) ? "
                        "document.body.innerText : '',"
                        " href: location.href || '',"
                        " title: document.title || ''"
                        "})"
                    ),
                ).get("result")
                contract = extract_answer_contract(snapshot)
                response_readback = self._build_response_readback(
                    snapshot=snapshot,
                    contract=contract,
                )
            if contract.login_state == "login-required":
                updated_round = current_round.model_copy(
                    update={
                        "response_summary": "Login required before continuing research.",
                        "decision": "login_required",
                        "metadata": {
                            **current_round.metadata,
                            **submission_metadata,
                            **({"response_readback": response_readback} if response_readback else {}),
                        },
                        "updated_at": _utc_now(),
                    },
                )
                rounds[-1] = self._upsert_round(updated_round)
                session = session.model_copy(
                    update={
                        "status": "waiting-login",
                        "updated_at": _utc_now(),
                    },
                )
                self._upsert_session(session)
                return ResearchSessionRunResult(
                    session=session,
                    rounds=_unique_rounds(rounds),
                    stop_reason="waiting-login",
                    deepened_links=deepened_links,
                    downloaded_artifacts=downloaded_artifacts,
                )

            findings = _dedupe_texts(_split_sentences(contract.answer_text))
            adapter_payload = _mapping(getattr(contract, "adapter_result", None))
            source_payloads = _mapping_list(adapter_payload.get("collected_sources"))
            finding_payloads = _mapping_list(adapter_payload.get("findings"))
            adapter_gaps = _dedupe_texts(
                [str(item).strip() for item in list(adapter_payload.get("gaps") or []) if str(item).strip()],
            )
            adapter_metadata = _mapping(adapter_payload.get("metadata"))
            adapter_conflicts = _dedupe_texts(
                [str(item).strip() for item in list(adapter_metadata.get("conflicts") or []) if str(item).strip()],
            )
            new_findings = _meaningful_new_findings(findings, session.stable_findings)
            if new_findings:
                stable_findings = _dedupe_texts([*session.stable_findings, *new_findings])
                consecutive_no_new_findings = 0
            else:
                stable_findings = list(session.stable_findings)
                consecutive_no_new_findings += 1

            round_downloads = self._resolve_downloads(
                session_id=browser_session_id,
                page_id=current_round.id,
            )
            if round_downloads:
                downloaded_artifacts.extend(round_downloads)

            raw_links = [_link_payload(link) for link in contract.links]
            selected_links = [
                payload
                for payload in raw_links
                if _text(payload.get("kind")) != "pdf"
            ][:1]

            updated_round = current_round.model_copy(
                update={
                    "response_excerpt": contract.answer_text[:240] or None,
                    "response_summary": findings[0] if findings else contract.answer_text[:160] or None,
                    "raw_links": raw_links,
                    "selected_links": selected_links,
                    "downloaded_artifacts": round_downloads,
                    "new_findings": new_findings,
                    "sources": source_payloads,
                    "findings": finding_payloads,
                    "conflicts": adapter_conflicts,
                    "gaps": adapter_gaps,
                    "remaining_gaps": (
                        []
                        if new_findings and not adapter_gaps
                        else adapter_gaps or [f"Need more evidence for: {session.goal}"]
                    ),
                    "decision": "continue",
                    "metadata": {
                        **current_round.metadata,
                        "findings": finding_payloads,
                        "collected_sources": source_payloads,
                        "gaps": adapter_gaps,
                        "conflicts": adapter_conflicts,
                        **submission_metadata,
                        **({"response_readback": response_readback} if response_readback else {}),
                    },
                    "updated_at": _utc_now(),
                },
            )
            rounds[-1] = self._upsert_round(updated_round)
            session = session.model_copy(
                update={
                    "stable_findings": stable_findings,
                    "conflicts": _dedupe_texts([*session.conflicts, *adapter_conflicts]),
                    "round_count": max(session.round_count, updated_round.round_index),
                    "download_count": len(downloaded_artifacts),
                    "updated_at": _utc_now(),
                },
            )

            next_link = next(
                (
                    payload
                    for payload in selected_links
                    if _text(payload.get("url")) and _text(payload.get("url")) not in visited_links
                ),
                None,
            )
            continuation_owner = ResearchChatContinuationOwner(
                build_followup_question=lambda: self._build_followup_question(
                    session=session,
                    round_record=updated_round,
                ),
                build_continuation_question=lambda: self._build_continuation_question(
                    session=session,
                    round_record=updated_round,
                ),
            )
            response_readback_payload = _mapping(response_readback)
            continuation_plan = continuation_owner.plan(
                page_kind=(
                    _text(response_readback_payload.get("page_kind"))
                    or ("login-wall" if _text(getattr(contract, "login_state", None)) == "login-required" else "content-page")
                ),
                blocker_hints=[
                    _text(item)
                    for item in list(response_readback_payload.get("blocker_hints") or [])
                    if _text(item)
                ],
                round_index=updated_round.round_index,
                entry_mode=_text(_mapping(updated_round.metadata).get("entry_mode")),
                has_structured_answer=bool(findings or _text(contract.answer_text)),
                findings_count=len(findings),
                new_findings_count=len(new_findings),
                has_adapter_gaps=bool(adapter_gaps),
                selected_links_count=len(selected_links),
                deepened_link_count=len(deepened_links),
                consecutive_no_new_findings=consecutive_no_new_findings,
                next_link_url=_text(next_link.get("url")) if next_link is not None else "",
                has_pdf_link=any(_text(item.get("kind")) == "pdf" for item in raw_links),
                raw_link_count=len(raw_links),
                current_link_depth=session.link_depth_count,
                max_link_depth=self.MAX_LINK_DEPTH,
                max_consecutive_no_new_findings=self.MAX_CONSECUTIVE_NO_NEW_FINDINGS,
            )
            if continuation_plan.action_kind == "deepen-link":
                link_url = _text(continuation_plan.next_link_url)
                visited_links.add(link_url)
                deepened_links.append(dict(next_link))
                session = session.model_copy(
                    update={
                        "status": "deepening",
                        "link_depth_count": (
                            session.link_depth_count + 1
                            if continuation_plan.increment_link_depth
                            else session.link_depth_count
                        ),
                        "updated_at": _utc_now(),
                    },
                )
                self._upsert_session(session)
                next_round = self._build_next_round(
                    session=session,
                    round_index=updated_round.round_index + 1,
                    question=continuation_plan.next_question,
                )
                rounds.append(self._upsert_round(next_round))
                current_url = link_url
                continue

            if continuation_plan.action_kind == "next-round":
                next_round = self._build_next_round(
                    session=session,
                    round_index=updated_round.round_index + 1,
                    question=continuation_plan.next_question,
                    metadata={"entry_mode": continuation_plan.next_round_mode},
                )
                rounds.append(self._upsert_round(next_round))
                current_url = (
                    continuation_plan.next_link_url
                    if continuation_plan.next_link_url
                    else self.BAIDU_CHAT_URL
                )
                continue

            stop_reason = continuation_plan.stop_reason or "planner-stop"
            break

        if stop_reason is None:
            stop_reason = "max-rounds"
        session = session.model_copy(
            update={
                "status": "completed",
                "round_count": max(session.round_count, rounds[-1].round_index),
                "download_count": len(downloaded_artifacts),
                "updated_at": _utc_now(),
                "completed_at": _utc_now(),
            },
        )
        self._upsert_session(session)
        return ResearchSessionRunResult(
            session=session,
            rounds=_unique_rounds(rounds),
            stop_reason=stop_reason,
            deepened_links=deepened_links,
            downloaded_artifacts=downloaded_artifacts[: self.MAX_DOWNLOADS],
        )

    def summarize_session(self, session_id: str) -> ResearchSessionRunResult:
        session = self._get_session(session_id)
        if session is None:
            raise KeyError(f"Unknown research session: {session_id}")
        rounds = _unique_rounds(_repo_list_rounds(self._research_session_repository, session_id=session_id))
        citations = self._collect_citations(rounds)
        summary_lines = _dedupe_texts(
            [*session.stable_findings]
            or [item for round_record in rounds for item in round_record.new_findings]
        )
        summary_text = "\n".join(summary_lines) if summary_lines else session.goal
        report_id: str | None = None
        industry_instance_id = _text(session.industry_instance_id)
        if self._report_repository is not None and industry_instance_id:
            report = AgentReportRecord(
                industry_instance_id=industry_instance_id,
                work_context_id=session.work_context_id,
                owner_agent_id=session.owner_agent_id,
                owner_role_id="researcher",
                report_kind="research-session",
                headline=f"Research brief: {session.goal[:64]}",
                summary=summary_text,
                findings=summary_lines,
                uncertainties=_dedupe_texts(
                    session.open_questions
                    or [item for round_record in rounds for item in round_record.remaining_gaps]
                ),
                recommendation="Review findings and decide whether to adopt them.",
                metadata={
                    "provider": session.provider,
                    "research_session_id": session.id,
                    "question_excerpt": session.goal[:120],
                    "citations": citations,
                },
            )
            upsert_report = getattr(self._report_repository, "upsert_report", None)
            if callable(upsert_report):
                try:
                    stored_report = upsert_report(report)
                except Exception:
                    logger.exception(
                        "Failed to persist research session report writeback",
                        extra={"research_session_id": session.id},
                    )
                else:
                    report_id = _text(getattr(stored_report, "id", None) or report.id)
        elif self._report_repository is not None:
            logger.warning(
                "Skip research session report writeback because industry_instance_id is missing",
                extra={"research_session_id": session.id},
            )

        work_context_chunk_ids: list[str] = []
        industry_document_id: str | None = None
        if self._knowledge_service is not None and summary_text:
            work_context_id = session.work_context_id
            if work_context_id is None and self._work_context_service is not None:
                ensure_context = getattr(self._work_context_service, "ensure_context", None)
                if callable(ensure_context):
                    context = ensure_context(
                        context_key=f"research-session:{session.id}",
                        title=session.goal,
                        summary="Research session summary",
                        context_type="research",
                        owner_agent_id=session.owner_agent_id,
                        industry_instance_id=session.industry_instance_id,
                        metadata={"research_session_id": session.id},
                    )
                    work_context_id = _text(getattr(context, "id", None))
            remember_fact = getattr(self._knowledge_service, "remember_fact", None)
            if callable(remember_fact) and work_context_id:
                chunk = remember_fact(
                    title=session.goal,
                    content=summary_text,
                    scope_type="work_context",
                    scope_id=work_context_id,
                    source_ref=f"research-session:{session.id}",
                    tags=["research", "summary"],
                )
                chunk_id = _text(getattr(chunk, "id", None))
                if chunk_id:
                    work_context_chunk_ids.append(chunk_id)
                session = session.model_copy(update={"work_context_id": work_context_id})
            if callable(remember_fact) and session.industry_instance_id:
                chunk = remember_fact(
                    title=session.goal,
                    content=summary_text,
                    scope_type="industry",
                    scope_id=session.industry_instance_id,
                    source_ref=f"research-session:{session.id}",
                    tags=["research", "summary"],
                )
                industry_document_id = _text(getattr(chunk, "document_id", None))

        node_ids: list[str] = []
        relation_ids: list[str] = []
        builder = getattr(
            self._knowledge_writeback_service,
            "build_research_session_writeback",
            None,
        )
        applier = getattr(self._knowledge_writeback_service, "apply_change", None)
        summarizer = getattr(
            self._knowledge_writeback_service,
            "summarize_change",
            None,
        )
        if callable(builder):
            change = builder(session=session, rounds=rounds)
            graph_result = _mapping(applier(change)) if callable(applier) else {}
            if not graph_result and callable(summarizer):
                graph_result = _mapping(summarizer(change))
            node_ids = _dedupe_texts(graph_result.get("node_ids") or [])
            relation_ids = _dedupe_texts(graph_result.get("relation_ids") or [])

        writeback_target = _mapping(_mapping(session.brief).get("writeback_target"))
        writeback_scope_type = (
            _text(writeback_target.get("scope_type"))
            or ("work_context" if _text(session.work_context_id) else "")
            or ("industry" if _text(session.industry_instance_id) else "")
        )
        writeback_scope_id = (
            _text(writeback_target.get("scope_id"))
            or _text(session.work_context_id)
            or _text(session.industry_instance_id)
        )
        writeback_truth = {
            "status": (
                "written"
                if any((report_id, work_context_chunk_ids, industry_document_id, node_ids, relation_ids))
                else "pending"
            ),
            "scope_type": writeback_scope_type or None,
            "scope_id": writeback_scope_id or None,
            "report_id": report_id,
            "work_context_chunk_ids": work_context_chunk_ids,
            "industry_document_id": industry_document_id,
            "node_ids": node_ids,
            "relation_ids": relation_ids,
        }

        session = session.model_copy(
            update={
                "status": "completed" if session.status != "waiting-login" else session.status,
                "final_report_id": report_id or session.final_report_id,
                "writeback_truth": writeback_truth,
                "updated_at": _utc_now(),
                "completed_at": session.completed_at or _utc_now(),
            },
        )
        self._upsert_session(session)
        return ResearchSessionRunResult(
            session=session,
            rounds=rounds,
            stop_reason="summarized",
            final_report_id=report_id,
            work_context_chunk_ids=work_context_chunk_ids,
            industry_document_id=industry_document_id,
        )

    def collect_via_baidu_page(self, session_id: str) -> ResearchAdapterResult:
        session = self._get_session(session_id)
        if session is None:
            raise KeyError(f"Unknown research session: {session_id}")
        rounds = _unique_rounds(
            _repo_list_rounds(self._research_session_repository, session_id=session_id),
        )
        latest_round = rounds[-1] if rounds else None
        round_metadata = _mapping(getattr(latest_round, "metadata", None))
        findings = _mapping_list(
            getattr(latest_round, "findings", None),
        ) or _mapping_list(round_metadata.get("findings"))
        sources = _mapping_list(
            getattr(latest_round, "sources", None),
        ) or _mapping_list(round_metadata.get("collected_sources"))
        latest_question = _text(getattr(latest_round, "question", None))
        fallback_source_ids = [
            _text(item.get("source_id"))
            for item in sources
            if _text(item.get("source_id")) is not None
        ]
        stable_findings = [
            {
                "finding_id": _stable_id("baidu-finding", session.id, summary),
                "finding_type": "answer",
                "summary": summary,
                "supporting_source_ids": fallback_source_ids,
                "supporting_evidence_ids": [],
                "conflicts": [],
                "gaps": [],
            }
            for summary in _dedupe_texts(session.stable_findings)
            if not _is_semantic_duplicate(summary, [latest_question, session.goal])
        ]
        filtered_findings = [
            item
            for item in findings
            if _text(item.get("summary"))
            and not _is_semantic_duplicate(item.get("summary"), [latest_question, session.goal])
        ]
        if stable_findings:
            findings = stable_findings
        elif filtered_findings:
            findings = filtered_findings
        elif not findings:
            findings = stable_findings
        conflicts = _dedupe_texts(
            getattr(latest_round, "conflicts", None)
            or round_metadata.get("conflicts")
            or getattr(session, "conflicts", None)
            or [],
        )
        gaps = _dedupe_texts(
            getattr(latest_round, "gaps", None)
            or getattr(latest_round, "remaining_gaps", None)
            or getattr(session, "open_questions", None)
            or [],
        )
        summary = (
            (findings[0].get("summary") if findings else "")
            or _text(getattr(latest_round, "response_summary", None))
            or _text(session.goal)
        )
        status = "blocked" if _text(session.status) == "waiting-login" else "partial"
        if summary or sources or findings:
            status = "succeeded"
        return ResearchAdapterResult.model_validate(
            {
                "adapter_kind": "baidu_page",
                "collection_action": "interact",
                "status": status,
                "session_id": session.id,
                "round_id": getattr(latest_round, "id", None),
                "collected_sources": sources,
                "findings": findings,
                "conflicts": conflicts,
                "gaps": gaps,
                "summary": summary,
                "metadata": {
                    "provider": session.provider,
                    "session_status": session.status,
                },
            },
        )

    def collect_provider_round_result(
        self,
        *,
        snapshot: Mapping[str, Any] | object,
        current_url: str,
        previous_snapshot: Mapping[str, Any] | None = None,
    ):
        payload = _mapping(snapshot)
        if not payload:
            raw_snapshot = str(snapshot or "")
            payload = {
                "html": raw_snapshot if "<" in raw_snapshot and ">" in raw_snapshot else "",
                "bodyText": "" if "<" in raw_snapshot and ">" in raw_snapshot else raw_snapshot,
            }
        payload.setdefault("href", current_url)
        if _text(payload.get("href")) in {"", self.BAIDU_CHAT_URL}:
            return self._extract_chat_contract(
                previous_snapshot=previous_snapshot,
                current_snapshot=payload,
            )
        return extract_answer_contract(payload)

    def _ensure_browser_session(self, session: ResearchSessionRecord) -> str:
        browser_session_id = _text(session.browser_session_id) or session.id
        payload = self._browser_call(
            action="start",
            session_id=browser_session_id,
            **self._browser_session_start_kwargs(session),
        )
        return _text(payload.get("session_id")) or browser_session_id

    def _browser_call(self, **payload: Any) -> dict[str, Any]:
        runner = self._browser_action_runner
        if not callable(runner):
            return {}
        result = runner(**payload)
        return dict(result) if isinstance(result, dict) else _mapping(result)

    def _browser_session_start_kwargs(self, session: ResearchSessionRecord) -> dict[str, Any]:
        browser_metadata = self._browser_session_metadata(session)
        persist_login_state = _optional_bool(
            browser_metadata.get("persist_login_state"),
        )
        effective_persist_login_state = (
            True if persist_login_state is None else persist_login_state
        )
        storage_state_path = _text(browser_metadata.get("storage_state_path"))
        if not storage_state_path and effective_persist_login_state:
            storage_state_path = self._default_storage_state_path(session)
        return {
            "persist_login_state": effective_persist_login_state,
            "storage_state_path": storage_state_path or "",
        }

    def _browser_session_metadata(self, session: ResearchSessionRecord) -> dict[str, Any]:
        metadata = _mapping(session.metadata)
        browser_metadata = _mapping(metadata.get("browser_session"))
        if browser_metadata:
            return browser_metadata
        direct_keys = {
            key: metadata[key]
            for key in ("persist_login_state", "storage_state_path")
            if key in metadata
        }
        return direct_keys

    def _default_storage_state_path(self, session: ResearchSessionRecord) -> str:
        directory = WORKING_DIR / "state" / "research_browser_storage"
        directory.mkdir(parents=True, exist_ok=True)
        owner_token = _safe_path_token(session.owner_agent_id)
        return str((directory / f"{owner_token}.json").resolve())

    def _resolve_downloads(self, **payload: Any) -> list[dict[str, Any]]:
        resolver = self._browser_download_resolver
        if not callable(resolver):
            return []
        result = resolver(**payload)
        downloads = list(result or []) if isinstance(result, list) else list(result or [])
        verified: list[dict[str, Any]] = []
        for item in downloads:
            mapping = _mapping(item)
            if not mapping:
                continue
            if not bool(mapping.get("verified") or mapping.get("exists")):
                continue
            normalized = dict(mapping)
            normalized["kind"] = _artifact_kind(normalized)
            verified.append(normalized)
            if len(verified) >= self.MAX_DOWNLOADS:
                break
        return verified

    def _get_session(self, session_id: str) -> ResearchSessionRecord | None:
        getter = getattr(self._research_session_repository, "get_research_session", None)
        if not callable(getter):
            return None
        return getter(session_id)

    def _upsert_session(self, session: ResearchSessionRecord) -> ResearchSessionRecord:
        return self._research_session_repository.upsert_research_session(session)

    def _upsert_round(self, round_record: ResearchSessionRoundRecord) -> ResearchSessionRoundRecord:
        return self._research_session_repository.upsert_research_round(round_record)

    def _round_id(self, session_id: str, round_index: int) -> str:
        return f"{session_id}:round:{round_index}"

    def _build_round_prompt(self, *, goal: str, round_index: int) -> str:
        return (
            f"Research goal: {goal}\n"
            f"Round: {round_index}\n"
            "Return a concise answer, key facts, uncertainty, and useful links."
        )

    def _build_next_round(
        self,
        *,
        session: ResearchSessionRecord,
        round_index: int,
        question: str,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchSessionRoundRecord:
        now = _utc_now()
        return ResearchSessionRoundRecord(
            id=self._round_id(session.id, round_index),
            session_id=session.id,
            round_index=round_index,
            question=question,
            generated_prompt=self._build_round_prompt(goal=session.goal, round_index=round_index),
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )

    def _build_followup_question(
        self,
        *,
        session: ResearchSessionRecord,
        round_record: ResearchSessionRoundRecord,
    ) -> str:
        summary = _text(round_record.response_summary or round_record.response_excerpt) or session.goal
        if _contains_cjk(f"{session.goal} {summary}"):
            return (
                f"继续追问这个研究目标：{session.goal}。"
                f"当前已知结论：{summary}。"
                "请补充最关键的遗漏细节、最值得继续核对的来源线索，以及一个最容易误解的点。"
            )
        return (
            f"Follow up on this research goal: {session.goal}. "
            f"Current answer: {summary}. "
            "Fill the most important missing details, the best sources to verify next, "
            "and one common misunderstanding."
        )

    def _build_continuation_question(
        self,
        *,
        session: ResearchSessionRecord,
        round_record: ResearchSessionRoundRecord,
    ) -> str:
        focus_question = (
            _strip_continuation_prefix(round_record.question)
            or _strip_continuation_prefix(_mapping(session.brief).get("question"))
            or session.goal
        )
        if _contains_cjk(f"{session.goal} {focus_question}"):
            return f"继续把这个问题问清楚：{focus_question}"
        return f"Continue researching this question: {focus_question}"

    def _ensure_chat_page(
        self,
        *,
        session_id: str,
        page_id: str,
    ) -> None:
        probe = self._browser_call(
            action="snapshot",
            session_id=session_id,
            page_id=page_id,
        )
        if bool(probe.get("ok")) and (
            _text(probe.get("snapshot"))
            or _text(probe.get("url"))
            or not _text(probe.get("error"))
        ):
            return
        self._browser_call(
            action="open",
            session_id=session_id,
            page_id=page_id,
            url=self.BAIDU_CHAT_URL,
        )

    def _submit_chat_question(
        self,
        *,
        session_id: str,
        page_id: str,
        question: str,
    ) -> dict[str, Any]:
        surface_context = self._build_baidu_surface_context(
            session_id=session_id,
            page_id=page_id,
        )
        initial_observation = surface_context.get("observation")
        if _text(getattr(initial_observation, "login_state", None)) == "login-required" or "login-required" in [
            _text(item)
            for item in list(getattr(initial_observation, "blockers", []) or [])
        ]:
            login_gate_payload = self._read_login_gate_payload(
                session_id=session_id,
                page_id=page_id,
                deep_think={
                    "requested": True,
                    "available": False,
                    "enabled_before": False,
                    "enabled_after": False,
                    "activated": False,
                    "selector": "",
                    "label": "",
                },
                input_readback={"matched": False},
            )
            if login_gate_payload is not None:
                return login_gate_payload
            readable_sections = list(getattr(initial_observation, "readable_sections", []) or [])
            blocker_excerpt = next(
                (
                    _text(section.get("text"))
                    for section in readable_sections
                    if isinstance(section, Mapping) and _text(section.get("text"))
                ),
                "",
            )
            return {
                "deep_think": {
                    "requested": True,
                    "available": False,
                    "enabled_before": False,
                    "enabled_after": False,
                    "activated": False,
                    "selector": "",
                    "label": "",
                },
                "input_readback": {"matched": False},
                "pre_submit_login_required": True,
                "response_readback": {
                    "page_href": _text(getattr(initial_observation, "page_url", None)),
                    "page_title": _text(getattr(initial_observation, "page_title", None)),
                    "login_state": "login-required",
                    "page_kind": "login-wall",
                    "blocker_hints": ["login-required"],
                    "answer_excerpt": blocker_excerpt,
                    "links": [],
                },
            }
        loop_owner = ResearchChatSurfaceLoopOwner(question=question)
        submission_loop = self._browser_surface_service.run_step_loop(
            session_id=session_id,
            page_id=page_id,
            planner=loop_owner.plan_step,
            initial_observation=initial_observation,
            snapshot_text=_text(surface_context.get("snapshot_text")),
            page_url=_text(surface_context.get("page_url")),
            page_title=_text(surface_context.get("page_title")),
            dom_probe=_mapping(surface_context.get("dom_probe")),
            page_profile=self._build_baidu_page_profile(),
            max_steps=3,
        )
        toggle_available = False
        toggle_enabled_before = False
        toggle_label = ""
        toggle_selector = ""
        if initial_observation is not None:
            toggle_candidate = self._resolve_surface_target(
                session_id=session_id,
                page_id=page_id,
                target_slot="reasoning_toggle",
                surface_context=surface_context,
            )
            if toggle_candidate is not None:
                toggle_available = True
                toggle_enabled_before = bool(toggle_candidate.metadata.get("enabled"))
                toggle_label = _text(toggle_candidate.metadata.get("label"))
                toggle_selector = _text(toggle_candidate.readback_selector or toggle_candidate.action_selector)
        toggle_result = next(
            (
                step
                for step in submission_loop.steps
                if _text(getattr(step, "intent_kind", None)) == "click"
                and _text(getattr(step, "target_slot", None)) == "reasoning_toggle"
            ),
            None,
        )
        deep_think = {
            "requested": True,
            "available": toggle_available,
            "enabled_before": toggle_enabled_before,
            "enabled_after": (
                str((getattr(toggle_result, "readback", {}) or {}).get("toggle_enabled") or "").strip().lower() == "true"
                if toggle_result is not None
                else toggle_enabled_before
            ),
            "activated": toggle_result is not None and _text(getattr(toggle_result, "status", None)) == "succeeded",
            "selector": "",
            "label": _text((getattr(toggle_result, "readback", {}) or {}).get("observed_text")) or toggle_label,
        }
        if not deep_think["selector"]:
            if toggle_result is not None and getattr(toggle_result, "resolved_target", None) is not None:
                resolved_toggle_target = getattr(toggle_result, "resolved_target", None)
                deep_think["selector"] = _text(
                    getattr(resolved_toggle_target, "readback_selector", None)
                    or getattr(resolved_toggle_target, "action_selector", None)
                )
            else:
                deep_think["selector"] = toggle_selector
        type_result = next(
            (
                step
                for step in submission_loop.steps
                if _text(getattr(step, "intent_kind", None)) == "type"
                and _text(getattr(step, "target_slot", None)) == "primary_input"
            ),
            None,
        )
        input_readback = dict(getattr(type_result, "readback", {}) or {})
        expected_signature = _question_signature(question)
        observed_signature = _question_signature(input_readback.get("normalized_text"))
        input_readback["matched"] = bool(
            expected_signature
            and observed_signature
            and expected_signature == observed_signature
            and bool(getattr(type_result, "verification_passed", False))
        )
        if not bool(input_readback.get("matched")):
            login_gate_payload = self._read_login_gate_payload(
                session_id=session_id,
                page_id=page_id,
                deep_think=deep_think,
                input_readback=input_readback,
            )
            if login_gate_payload is not None:
                return login_gate_payload
            raise RuntimeError("Chat input readback did not match submitted question.")
        submit_step = next(
            (
                step
                for step in submission_loop.steps
                if _text(getattr(step, "intent_kind", None)) == "press"
                and _text(getattr(step, "target_slot", None)) == "page"
            ),
            None,
        )
        if submit_step is None or _text(getattr(submit_step, "status", None)) != "succeeded":
            raise RuntimeError("Chat submit key press did not complete successfully.")
        return {
            "deep_think": deep_think,
            "input_readback": input_readback,
        }

    def _read_login_gate_payload(
        self,
        *,
        session_id: str,
        page_id: str,
        deep_think: Mapping[str, Any] | None,
        input_readback: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        snapshot = self._capture_page_snapshot(
            session_id=session_id,
            page_id=page_id,
        )
        contract = extract_answer_contract(snapshot)
        if _text(getattr(contract, "login_state", None)) != "login-required":
            return None
        return {
            "deep_think": dict(deep_think or {}),
            "input_readback": dict(input_readback or {}),
            "pre_submit_login_required": True,
            "response_readback": self._build_response_readback(
                snapshot=snapshot,
                contract=contract,
            ),
        }

    def _build_baidu_surface_context(
        self,
        *,
        session_id: str,
        page_id: str,
    ) -> dict[str, Any]:
        return self._browser_surface_service.capture_page_context(
            session_id=session_id,
            page_id=page_id,
            page_profile=self._build_baidu_page_profile(),
            page_url=self.BAIDU_CHAT_URL,
        )

    def _build_baidu_page_profile(
        self,
        *,
        include_reasoning_toggle: bool = True,
    ) -> BrowserPageProfile:
        return BrowserPageProfile(
            profile_id="baidu-chat",
            page_title="Baidu Chat",
            include_generic_live_probe=True,
            dom_probe_builder=lambda **kwargs: self._build_baidu_surface_dom_probe(
                include_reasoning_toggle=include_reasoning_toggle,
                **kwargs,
            ),
        )

    def _build_baidu_surface_dom_probe(
        self,
        *,
        browser_runner,
        session_id: str,
        page_id: str,
        snapshot_text: str,
        page_url: str,
        page_title: str,
        include_reasoning_toggle: bool = True,
    ) -> dict[str, Any]:
        _ = browser_runner, page_url, page_title
        dom_probe: dict[str, Any] = {
            "inputs": [],
            "control_groups": [],
        }
        seed_input_candidate = self._browser_surface_service.resolve_target(
            session_id=session_id,
            page_id=page_id,
            target_slot="primary_input",
            snapshot_text=snapshot_text,
            page_url=self.BAIDU_CHAT_URL,
            page_title="Baidu Chat",
        )
        if seed_input_candidate is not None and _text(seed_input_candidate.action_ref):
            dom_probe["inputs"].append(
                {
                    "target_kind": "input",
                    "action_ref": _text(seed_input_candidate.action_ref),
                    "action_selector": "",
                    "readback_selector": "#chat-textarea",
                    "element_kind": "textarea",
                    "scope_anchor": _text(seed_input_candidate.scope_anchor) or "composer",
                    "score": max(int(seed_input_candidate.score or 0), 10),
                    "reason": "baidu chat primary input via shared observer",
                }
            )
        if not include_reasoning_toggle:
            return dom_probe
        deep_think_probe = self._browser_call(
            action="evaluate",
            session_id=session_id,
            page_id=page_id,
            code=(
                "(() => {"
                " const input = document.querySelector('#chat-textarea, textarea, [contenteditable=\"true\"], [role=\"textbox\"]');"
                " if (!input) return { available: false, enabled: false, selector: '', label: '' };"
                " const scopeRoot = input.closest('form, footer, main, [class*=\"input\"], [class*=\"composer\"], [class*=\"send\"]') || input.parentElement || document.body;"
                " const candidates = Array.from(scopeRoot.querySelectorAll('button, [role=\"button\"], label'));"
                " const match = candidates.find((element) => {"
                "   const text = (element.innerText || element.textContent || '').replace(/\\s+/g, ' ').trim();"
                "   return text.includes('\\u6df1\\u5ea6\\u601d\\u8003');"
                " });"
                " if (!match) return { available: false, enabled: false, selector: '', label: '' };"
                " if (!match.hasAttribute('data-copaw-deep-think')) {"
                "   match.setAttribute('data-copaw-deep-think', '1');"
                " }"
                " const pressed = (match.getAttribute('aria-pressed') || '').toLowerCase();"
                " const className = (match.className || '').toString().toLowerCase();"
                " const text = (match.innerText || match.textContent || '').replace(/\\s+/g, ' ').trim();"
                " const enabled = pressed === 'true' || className.includes('active') || className.includes('selected') || className.includes('checked');"
                " return {"
                "   available: true,"
                "   enabled,"
                "   selector: '[data-copaw-deep-think=\"1\"]',"
                "   label: text"
                " };"
                "})()"
            ),
        ).get("result")
        deep_think_payload = _mapping(deep_think_probe)
        if bool(deep_think_payload.get("available")):
            dom_probe["control_groups"].append(
                {
                    "group_kind": "reasoning_toggle_group",
                    "scope_anchor": "composer",
                    "candidates": [
                        {
                            "target_kind": "toggle",
                            "action_ref": "",
                            "action_selector": _text(deep_think_payload.get("selector")),
                            "readback_selector": _text(deep_think_payload.get("selector")),
                            "element_kind": "button",
                            "scope_anchor": "composer",
                            "score": 8,
                            "reason": "baidu deep think toggle",
                            "metadata": {
                                "enabled": bool(deep_think_payload.get("enabled")),
                                "label": _text(deep_think_payload.get("label")),
                            },
                        }
                    ],
                }
            )
        return dom_probe

    def _target_from_mapping(
        self,
        payload: Mapping[str, Any] | None,
    ) -> BrowserTargetCandidate | None:
        mapping = _mapping(payload)
        if not mapping:
            return None
        return BrowserTargetCandidate(
            target_kind=_text(mapping.get("target_kind")) or "input",
            action_ref=_text(mapping.get("ref") or mapping.get("action_ref")),
            action_selector=_text(mapping.get("selector") or mapping.get("action_selector")),
            readback_selector=_text(mapping.get("readback_selector")),
            element_kind=_text(mapping.get("element_kind")) or "generic",
            scope_anchor=_text(mapping.get("scope_anchor")),
            score=int(mapping.get("score") or 0),
            reason=_text(mapping.get("reason")),
            metadata=dict(_mapping(mapping.get("metadata"))),
        )


    def _ensure_baidu_deep_think_enabled(
        self,
        *,
        session_id: str,
        page_id: str,
        surface_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = dict(surface_context or {})
        requested = True
        candidate = self._resolve_surface_target(
            session_id=session_id,
            page_id=page_id,
            target_slot="reasoning_toggle",
            surface_context=surface_context,
        )
        before = (
            {
                "available": True,
                "enabled": bool(candidate.metadata.get("enabled")),
                "selector": _text(candidate.readback_selector or candidate.action_selector),
                "label": _text(candidate.metadata.get("label")),
            }
            if candidate is not None
            else {
                "available": False,
                "enabled": False,
                "selector": "",
                "label": "",
            }
        )
        available = bool(before.get("available"))
        enabled_before = bool(before.get("enabled"))
        selector = _text(before.get("selector"))
        activated = False
        after = before
        if requested and available and not enabled_before:
            if candidate is not None:
                click_result = self._browser_surface_service.execute_step(
                    session_id=session_id,
                    page_id=page_id,
                    before_observation=context.get("observation"),
                    snapshot_text=_text(context.get("snapshot_text")),
                    page_url=_text(context.get("page_url")),
                    page_title=_text(context.get("page_title")),
                    dom_probe=_mapping(context.get("dom_probe")),
                    target_slot="reasoning_toggle",
                    intent_kind="click",
                    payload={},
                    success_assertion={"toggle_enabled": "true"},
                )
                activated = _text(click_result.status) == "succeeded"
                after = {
                    "available": True,
                    "enabled": str(click_result.readback.get("toggle_enabled") or "").strip().lower() == "true",
                    "selector": _text(click_result.readback.get("selector")) or selector,
                    "label": _text(click_result.readback.get("observed_text")) or _text(before.get("label")),
                }
        return {
            "requested": requested,
            "available": available,
            "enabled_before": enabled_before,
            "enabled_after": bool(after.get("enabled")),
            "activated": activated,
            "selector": _text(after.get("selector") or selector),
            "label": _text(after.get("label") or before.get("label")),
        }

    def _read_baidu_deep_think_state(
        self,
        *,
        session_id: str,
        page_id: str,
        surface_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        candidate = self._resolve_surface_target(
            session_id=session_id,
            page_id=page_id,
            target_slot="reasoning_toggle",
            surface_context=surface_context,
        )
        if candidate is None:
            return {
                "available": False,
                "enabled": False,
                "selector": "",
                "label": "",
            }
        payload = self._browser_surface_service.read_target_readback(
            session_id=session_id,
            page_id=page_id,
            target=candidate,
        )
        return {
            "available": True,
            "enabled": str(payload.get("toggle_enabled") or "").strip().lower() == "true",
            "selector": _text(candidate.readback_selector or candidate.action_selector),
            "label": _text(payload.get("observed_text")) or _text(candidate.metadata.get("label")),
        }

    def _read_chat_input_readback(
        self,
        *,
        session_id: str,
        page_id: str,
        question: str,
        target: Mapping[str, Any] | BrowserTargetCandidate | None = None,
        surface_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        candidate = (
            target
            if isinstance(target, BrowserTargetCandidate)
            else self._target_from_mapping(target)
        )
        if candidate is None:
            resolved = self._resolve_chat_input_target(
                session_id=session_id,
                page_id=page_id,
                surface_context=surface_context,
            )
            candidate = self._target_from_mapping(resolved)
        if candidate is None:
            observed_text = ""
            normalized_text = ""
        else:
            payload = self._browser_surface_service.read_target_readback(
                session_id=session_id,
                page_id=page_id,
                target=candidate,
            )
            observed_text = _text(payload.get("observed_text"))
            normalized_text = _text(payload.get("normalized_text")) or observed_text
        expected_signature = _question_signature(question)
        observed_signature = _question_signature(normalized_text or observed_text)
        return {
            "matched": bool(expected_signature and observed_signature and expected_signature == observed_signature),
            "observed_text": observed_text,
            "normalized_text": normalized_text,
        }

    def _resolve_chat_input_target(
        self,
        *,
        session_id: str,
        page_id: str,
        surface_context: Mapping[str, Any] | None = None,
    ) -> dict[str, str]:
        candidate = self._resolve_surface_target(
            session_id=session_id,
            page_id=page_id,
            target_slot="primary_input",
            surface_context=surface_context,
        )
        if candidate is None:
            return {}
        return {
            "ref": candidate.action_ref,
            "selector": candidate.action_selector,
            "readback_selector": candidate.readback_selector,
            "element_kind": candidate.element_kind,
        }

    def _resolve_surface_target(
        self,
        *,
        session_id: str,
        page_id: str,
        target_slot: str,
        surface_context: Mapping[str, Any] | None = None,
    ) -> BrowserTargetCandidate | None:
        context = dict(surface_context or {})
        if context:
            return self._browser_surface_service.resolve_target(
                session_id=session_id,
                page_id=page_id,
                target_slot=target_slot,
                snapshot_text=_text(context.get("snapshot_text")),
                page_url=_text(context.get("page_url")),
                page_title=_text(context.get("page_title")),
                dom_probe=_mapping(context.get("dom_probe")),
            )
        return self._browser_surface_service.resolve_target(
            session_id=session_id,
            page_id=page_id,
            target_slot=target_slot,
            page_profile=self._build_baidu_page_profile(),
            page_url=self.BAIDU_CHAT_URL,
        )

    def _extract_chat_contract(
        self,
        *,
        previous_snapshot: Mapping[str, Any] | None,
        current_snapshot: Mapping[str, Any] | object,
    ):
        payload = _mapping(current_snapshot)
        if not payload:
            raw_current = str(current_snapshot or "")
            if "<" in raw_current and ">" in raw_current:
                payload = {"html": raw_current, "bodyText": ""}
            else:
                payload = {"html": "", "bodyText": raw_current}
        previous_payload = _mapping(previous_snapshot)
        if previous_snapshot is not None and not previous_payload:
            raw_previous = str(previous_snapshot or "")
            if "<" in raw_previous and ">" in raw_previous:
                previous_payload = {"html": raw_previous, "bodyText": ""}
            else:
                previous_payload = {"html": "", "bodyText": raw_previous}
        current_body = payload.get("bodyText")
        previous_body = previous_payload.get("bodyText")
        incremental_payload = dict(payload)
        incremental_payload["bodyText"] = _tail_lines(previous_body, current_body) or current_body or ""
        return extract_answer_contract(incremental_payload)

    def _capture_page_snapshot(
        self,
        *,
        session_id: str,
        page_id: str,
    ) -> dict[str, Any]:
        snapshot = self._browser_call(
            action="evaluate",
            session_id=session_id,
            page_id=page_id,
            code=(
                "({"
                " html: document.documentElement.outerHTML || '',"
                " bodyText: (document.body && document.body.innerText) ? "
                "document.body.innerText : '',"
                " href: location.href || '',"
                " title: document.title || ''"
                "})"
            ),
        ).get("result")
        return _mapping(snapshot)

    def _build_response_readback(
        self,
        *,
        snapshot: Mapping[str, Any] | object,
        contract: object,
    ) -> dict[str, Any]:
        payload = _mapping(snapshot)
        answer_text = _text(getattr(contract, "answer_text", None))
        answer_excerpt = next(
            (
                line
                for line in (_text(item) for item in answer_text.splitlines())
                if line
            ),
            "",
        )
        links = list(getattr(contract, "links", None) or [])
        return {
            "page_href": _text(payload.get("href")),
            "page_title": _text(payload.get("title")),
            "login_state": _text(getattr(contract, "login_state", None)),
            "page_kind": (
                "login-wall"
                if _text(getattr(contract, "login_state", None)) == "login-required"
                else "content-page"
            ),
            "blocker_hints": (
                ["login-required"]
                if _text(getattr(contract, "login_state", None)) == "login-required"
                else []
            ),
            "answer_excerpt": answer_excerpt,
            "link_count": len(links),
        }

    def _collect_citations(
        self,
        rounds: list[ResearchSessionRoundRecord],
    ) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        seen: set[str] = set()
        for round_record in rounds:
            for payload in [*round_record.selected_links, *round_record.raw_links, *round_record.downloaded_artifacts]:
                mapping = _mapping(payload)
                ref = _text(mapping.get("url") or mapping.get("path") or mapping.get("artifact_id"))
                if not ref or ref in seen:
                    continue
                seen.add(ref)
                citation = {
                    "ref": ref,
                    "label": _text(mapping.get("label") or mapping.get("suggested_filename")) or ref,
                    "kind": _text(mapping.get("kind")) or "link",
                }
                citations.append(citation)
        return citations


__all__ = ["BaiduPageResearchService"]
