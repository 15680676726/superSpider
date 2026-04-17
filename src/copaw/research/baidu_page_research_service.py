# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha1
from typing import Any, Mapping

from ..state import AgentReportRecord, ResearchSessionRecord, ResearchSessionRoundRecord
from .baidu_page_contract import extract_answer_contract
from .models import ResearchLink, ResearchSessionRunResult


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: object | None) -> str:
    return str(value or "").strip()


def _mapping(value: object | None) -> dict[str, Any]:
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
    parts = []
    for chunk in normalized.replace("?", "。").replace("!", "。").replace("；", "。").split("。"):
        sentence = chunk.strip()
        if sentence:
            parts.append(sentence)
    return parts


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


class BaiduPageResearchService:
    BAIDU_CHAT_URL = "https://chat.baidu.com/search"
    MAX_ROUNDS = 5
    MAX_LINK_DEPTH = 3
    MAX_DOWNLOADS = 2
    MAX_CONSECUTIVE_NO_NEW_FINDINGS = 2

    def __init__(
        self,
        *,
        research_session_repository: object,
        browser_action_runner: object | None = None,
        browser_download_resolver: object | None = None,
        report_repository: object | None = None,
        knowledge_service: object | None = None,
        work_context_service: object | None = None,
    ) -> None:
        self._research_session_repository = research_session_repository
        self._browser_action_runner = browser_action_runner
        self._browser_download_resolver = browser_download_resolver
        self._report_repository = report_repository
        self._knowledge_service = knowledge_service
        self._work_context_service = work_context_service

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
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        first_round = ResearchSessionRoundRecord(
            id=self._round_id(session.id, 1),
            session_id=session.id,
            round_index=1,
            question=goal,
            generated_prompt=self._build_round_prompt(goal=goal, round_index=1),
            created_at=now,
            updated_at=now,
        )
        self._upsert_session(session)
        self._upsert_round(first_round)
        return ResearchSessionRunResult(session=session, rounds=[first_round])

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

        while len(rounds) <= self.MAX_ROUNDS:
            current_round = rounds[-1]
            self._browser_call(
                action="open",
                session_id=browser_session_id,
                page_id=current_round.id,
                url=current_url,
            )
            raw_html = _text(
                self._browser_call(
                    action="evaluate",
                    session_id=browser_session_id,
                    page_id=current_round.id,
                    code="document.documentElement.outerHTML",
                ).get("result"),
            )
            contract = extract_answer_contract(raw_html)
            if contract.login_state == "login-required":
                updated_round = current_round.model_copy(
                    update={
                        "response_summary": "Login required before continuing research.",
                        "decision": "login_required",
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
            new_findings = [
                item
                for item in findings
                if item.casefold() not in {value.casefold() for value in session.stable_findings}
            ]
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
                    "remaining_gaps": [] if new_findings else [f"Need more evidence for: {session.goal}"],
                    "decision": "continue",
                    "updated_at": _utc_now(),
                },
            )
            rounds[-1] = self._upsert_round(updated_round)
            session = session.model_copy(
                update={
                    "stable_findings": stable_findings,
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
            should_deepen = (
                next_link is not None
                and (
                    len(raw_links) > 1
                    or any(_text(item.get("kind")) == "pdf" for item in raw_links)
                )
            )
            if should_deepen and session.link_depth_count < self.MAX_LINK_DEPTH:
                link_url = _text(next_link.get("url"))
                visited_links.add(link_url)
                deepened_links.append(dict(next_link))
                session = session.model_copy(
                    update={
                        "status": "deepening",
                        "link_depth_count": session.link_depth_count + 1,
                        "updated_at": _utc_now(),
                    },
                )
                self._upsert_session(session)
                next_round = self._build_next_round(
                    session=session,
                    round_index=updated_round.round_index + 1,
                    question=f"Deepen source: {link_url}",
                )
                rounds.append(self._upsert_round(next_round))
                current_url = link_url
                continue

            if (
                raw_links
                and not should_deepen
                and not deepened_links
                and updated_round.round_index == 1
                and findings
            ):
                stop_reason = "initial-brief-complete"
                break

            if (
                not selected_links
                and not deepened_links
                and updated_round.round_index == 1
                and len(findings) >= 2
            ):
                stop_reason = "enough-findings"
                break

            if consecutive_no_new_findings >= self.MAX_CONSECUTIVE_NO_NEW_FINDINGS:
                stop_reason = "no-new-findings"
                break

            if deepened_links:
                stop_reason = "deepened-link-closed"
                break

            if updated_round.round_index >= 3:
                stop_reason = "completed"
                break

            next_round = self._build_next_round(
                session=session,
                round_index=updated_round.round_index + 1,
                question=f"Continue researching: {session.goal}",
            )
            rounds.append(self._upsert_round(next_round))
            current_url = self.BAIDU_CHAT_URL

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
        if self._report_repository is not None:
            report = AgentReportRecord(
                industry_instance_id=session.industry_instance_id or "research-runtime",
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
                stored_report = upsert_report(report)
                report_id = _text(getattr(stored_report, "id", None) or report.id)

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

        session = session.model_copy(
            update={
                "status": "completed" if session.status != "waiting-login" else session.status,
                "final_report_id": report_id or session.final_report_id,
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

    def _ensure_browser_session(self, session: ResearchSessionRecord) -> str:
        if session.browser_session_id:
            return session.browser_session_id
        payload = self._browser_call(action="start", session_id=session.id)
        return _text(payload.get("session_id")) or session.id

    def _browser_call(self, **payload: Any) -> dict[str, Any]:
        runner = self._browser_action_runner
        if not callable(runner):
            return {}
        result = runner(**payload)
        return dict(result) if isinstance(result, dict) else _mapping(result)

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
    ) -> ResearchSessionRoundRecord:
        now = _utc_now()
        return ResearchSessionRoundRecord(
            id=self._round_id(session.id, round_index),
            session_id=session.id,
            round_index=round_index,
            question=question,
            generated_prompt=self._build_round_prompt(goal=session.goal, round_index=round_index),
            created_at=now,
            updated_at=now,
        )

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
