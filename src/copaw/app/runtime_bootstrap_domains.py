# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from ..capabilities import CapabilityService
from ..compiler import (
    AssignmentPlanningCompiler,
    CyclePlanningCompiler,
    ReportReplanEngine,
    StrategyPlanningCompiler,
)
from ..evidence import EvidenceLedger, EvidenceRecord
from ..environments import EnvironmentService
from ..goals import GoalService
from ..industry import IndustryDraftGenerator, IndustryService
from ..industry.service_context import build_industry_service_runtime_bindings
from ..kernel import (
    ActorMailboxService,
    ActorSupervisor,
    AgentProfileService,
    KernelDispatcher,
    KernelQueryExecutionService,
    KernelToolBridge,
    MainBrainChatService,
    MainBrainOrchestrator,
)
from ..kernel.main_brain_execution_planner import MainBrainExecutionPlanner
from ..kernel.main_brain_intake import resolve_request_main_brain_intake_contract
from ..kernel.runtime_coordination import AssignmentExecutorRuntimeCoordinator
from ..learning import LearningService
from ..learning.runtime_bindings import LearningRuntimeBindings
from ..media import MediaService
from ..memory import (
    DerivedMemoryIndexService,
    KnowledgeGraphService,
    MemoryActivationService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
    MemorySurfaceService,
    MemorySleepService,
)
from ..memory.knowledge_writeback_service import KnowledgeWritebackService
from ..predictions import PredictionService
from ..research import BaiduPageResearchService
from ..research.source_collection import SourceCollectionService
from ..research.source_collection.adapters import build_source_collection_adapters
from ..research.source_collection.contracts import ResearchBrief
from ..research.source_collection.routing import route_collection_mode
from ..retrieval import RetrievalFacade
from ..providers.runtime_provider_facade import ProviderRuntimeSurface
from ..routines import RoutineService
from ..sop_kernel import FixedSopService
from ..state import (
    AgentReportRecord,
    ResearchSessionRecord,
    ResearchSessionRoundRecord,
    SQLiteStateStore,
)
from ..state.agent_experience_service import AgentExperienceMemoryService
from ..state.knowledge_service import StateKnowledgeService
from ..state.main_brain_service import (
    AgentReportService,
    AssignmentService,
    BacklogService,
    OperatingCycleService,
    OperatingLaneService,
)
from ..state.reporting_service import StateReportingService
from ..state.strategy_memory_service import StateStrategyMemoryService
from ..state.work_context_service import WorkContextService
from ..workflows import WorkflowTemplateService
from ..agents.tools.browser_control import list_browser_downloads, run_browser_use_json
from .mcp import MCPClientManager
from .runtime_bootstrap_models import (
    RuntimeRepositories,
    SourceCollectionFrontdoorResult,
)
from .runtime_center import RuntimeCenterStateQueryService
from .runtime_events import RuntimeEventBus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _string(value: object | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _string_list(value: object | None) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    for item in items:
        text = _string(item)
        if text is None or text in normalized:
            continue
        normalized.append(text)
    return normalized


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


def _preferred_session_id(
    preferred_session_id: object | None,
    metadata: object | None,
) -> str | None:
    explicit = _string(preferred_session_id)
    if explicit is not None:
        return explicit
    normalized_metadata = _mapping(metadata)
    return _string(
        normalized_metadata.get("preferred_session_id")
        or _mapping(normalized_metadata.get("continuation")).get("preferred_session_id")
        or _mapping(normalized_metadata.get("continuation")).get("research_session_id")
    )


def _signature(value: object | None) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _looks_like_followup_question(value: object | None) -> bool:
    normalized = _signature(value)
    if not normalized:
        return False
    markers = (
        "follow up",
        "follow-up",
        "continue",
        "add ",
        "clarify",
        "expand",
        "more",
        "next",
        "resume",
        "再",
        "继续",
        "补充",
        "还有",
        "顺便",
        "进一步",
        "接着",
        "然后",
        "上面",
        "刚才",
    )
    return any(marker in normalized for marker in markers)


def _research_overlap_tokens(*values: object | None) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        normalized = _string(value)
        if normalized is None:
            continue
        for token in re.findall(r"[0-9A-Za-z\u4e00-\u9fff]+", normalized.casefold()):
            if len(token) >= 2:
                tokens.add(token)
    return tokens


def _research_session_match_score(
    *,
    brief: ResearchBrief,
    candidate: ResearchSessionRecord,
) -> int:
    candidate_brief = _mapping(getattr(candidate, "brief", None))
    brief_values = [brief.goal, brief.question, brief.why_needed]
    candidate_values = [
        _string(getattr(candidate, "goal", None)),
        _string(candidate_brief.get("goal")),
        _string(candidate_brief.get("question")),
    ]
    score = 0
    for left in brief_values:
        left_text = _string(left)
        if left_text is None:
            continue
        for right in candidate_values:
            right_text = _string(right)
            if right_text is None:
                continue
            if left_text == right_text:
                score = max(score, 100)
            elif left_text in right_text or right_text in left_text:
                score = max(score, 60)
    overlap = _research_overlap_tokens(*brief_values) & _research_overlap_tokens(
        *candidate_values,
    )
    return score + len(overlap) * 5


def _allow_strong_overlap_reuse(
    *,
    brief: ResearchBrief,
    candidate: ResearchSessionRecord,
) -> bool:
    return _research_session_match_score(brief=brief, candidate=candidate) >= 60


class SourceCollectionFrontdoorService:
    def __init__(
        self,
        *,
        heavy_research_service: object,
        research_session_repository: object,
        report_repository: object | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        knowledge_service: object | None = None,
        knowledge_writeback_service: object | None = None,
    ) -> None:
        self._heavy_research_service = heavy_research_service
        self._source_collection_service = SourceCollectionService(
            adapters=build_source_collection_adapters(),
            retrieval_facade=RetrievalFacade(
                workspace_root=Path(__file__).resolve().parents[3],
            ),
        )
        self.research_session_repository = research_session_repository
        self.report_repository = report_repository
        self._evidence_ledger = evidence_ledger
        self._knowledge_service = knowledge_service
        self._knowledge_writeback_service = knowledge_writeback_service

    def run_source_collection_frontdoor(
        self,
        *,
        goal: str,
        question: str | None = None,
        why_needed: str | None = None,
        done_when: str | None = None,
        trigger_source: str,
        owner_agent_id: str,
        preferred_researcher_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        work_context_id: str | None = None,
        assignment_id: str | None = None,
        task_id: str | None = None,
        supervisor_agent_id: str | None = None,
        collection_mode_hint: str = "auto",
        requested_sources: list[str] | None = None,
        writeback_target: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        preferred_session_id: str | None = None,
    ) -> SourceCollectionFrontdoorResult:
        normalized_goal = _string(goal)
        if normalized_goal is None:
            raise ValueError("goal is required")
        normalized_owner_agent_id = _string(owner_agent_id)
        if normalized_owner_agent_id is None:
            raise ValueError("owner_agent_id is required")
        normalized_question = _string(question) or normalized_goal
        normalized_requested_sources = _string_list(requested_sources)
        normalized_metadata = _mapping(metadata)
        normalized_preferred_session_id = _preferred_session_id(
            preferred_session_id,
            normalized_metadata,
        )
        normalized_writeback_target = _mapping(writeback_target) or None
        brief = ResearchBrief(
            owner_agent_id=normalized_owner_agent_id,
            supervisor_agent_id=_string(supervisor_agent_id),
            industry_instance_id=_string(industry_instance_id),
            work_context_id=_string(work_context_id),
            assignment_id=_string(assignment_id),
            task_id=_string(task_id),
            goal=normalized_goal,
            question=normalized_question,
            why_needed=_string(why_needed) or "",
            done_when=_string(done_when) or "",
            writeback_target=normalized_writeback_target,
            collection_mode_hint=(
                _string(collection_mode_hint) or "auto"
            ),
            metadata=normalized_metadata,
        )
        route = route_collection_mode(
            brief,
            requested_sources=normalized_requested_sources,
            preferred_researcher_agent_id=_string(preferred_researcher_agent_id),
        )
        brief_payload = {
            "goal": brief.goal,
            "question": brief.question,
            "why_needed": _string(why_needed),
            "done_when": _string(done_when),
            "collection_mode_hint": brief.collection_mode_hint,
            "requested_sources": normalized_requested_sources,
            "writeback_target": normalized_writeback_target,
        }
        route_payload = route.model_dump(mode="json")
        entry_metadata = {
            **normalized_metadata,
            "brief": brief_payload,
            "route": route_payload,
        }
        if normalized_preferred_session_id is not None:
            entry_metadata["preferred_session_id"] = normalized_preferred_session_id
        if route.mode == "heavy":
            return self._run_heavy_path(
                brief=brief,
                route_payload=route_payload,
                metadata=entry_metadata,
                trigger_source=trigger_source,
                preferred_session_id=normalized_preferred_session_id,
            )
        return self._run_light_path(
            brief=brief,
            requested_sources=normalized_requested_sources,
            route_payload=route_payload,
            metadata=entry_metadata,
            trigger_source=trigger_source,
        )

    def _run_heavy_path(
        self,
        *,
        brief: ResearchBrief,
        route_payload: dict[str, Any],
        metadata: dict[str, Any],
        trigger_source: str,
        preferred_session_id: str | None = None,
    ) -> SourceCollectionFrontdoorResult:
        service = self._heavy_research_service
        starter = getattr(service, "start_session", None)
        resumer = getattr(service, "resume_session", None)
        if not callable(starter):
            raise RuntimeError("Heavy research service is missing start_session")
        reusable_session = self._find_reusable_heavy_session(
            brief=brief,
            execution_agent_id=str(route_payload.get("execution_agent_id") or brief.owner_agent_id),
            trigger_source=trigger_source,
            preferred_session_id=preferred_session_id,
        )
        if reusable_session is not None and callable(resumer):
            session_result = resumer(
                session_id=reusable_session.id,
                question=brief.question,
                metadata=metadata,
            )
        else:
            session_result = starter(
                goal=brief.goal,
                trigger_source=trigger_source,
                owner_agent_id=str(route_payload.get("execution_agent_id") or brief.owner_agent_id),
                industry_instance_id=brief.industry_instance_id,
                work_context_id=brief.work_context_id,
                supervisor_agent_id=brief.supervisor_agent_id,
                metadata=metadata,
            )
        session_id = _string(
            getattr(session_result, "session_id", None)
            or (reusable_session.id if reusable_session is not None else None)
            or _mapping(_mapping(session_result).get("session")).get("id")
            or getattr(getattr(session_result, "session", None), "id", None)
        )
        status = _string(
            getattr(getattr(session_result, "session", None), "status", None)
        ) or "queued"
        runner = getattr(service, "run_session", None)
        if callable(runner) and session_id is not None:
            run_result = runner(session_id)
            status = (
                _string(getattr(getattr(run_result, "session", None), "status", None))
                or status
            )
            session_result = run_result
        summarizer = getattr(service, "summarize_session", None)
        if callable(summarizer) and session_id is not None:
            summary_result = summarizer(session_id)
            summary_payload = _mapping(summary_result)
        else:
            summary_payload = {}
        findings_payload: list[dict[str, Any]] = []
        sources_payload: list[dict[str, Any]] = []
        conflicts: list[str] = []
        gaps: list[str] = []
        adapter_collector = getattr(service, "collect_via_baidu_page", None)
        if callable(adapter_collector) and session_id is not None:
            adapter_result = adapter_collector(session_id)
            findings_payload = [
                _mapping(item)
                for item in list(_mapping(adapter_result).get("findings") or [])
                if _mapping(item)
            ]
            sources_payload = [
                _mapping(item)
                for item in list(_mapping(adapter_result).get("collected_sources") or [])
                if _mapping(item)
            ]
            conflicts = _string_list(_mapping(adapter_result).get("conflicts"))
            gaps = _string_list(_mapping(adapter_result).get("gaps"))
        stop_reason = _string(
            _mapping(summary_payload).get("stop_reason")
            or getattr(session_result, "stop_reason", None)
        )
        final_report_id = _string(
            _mapping(summary_payload).get("final_report_id")
            or getattr(summary_result, "final_report_id", None)
            if "summary_result" in locals()
            else None
        )
        return SourceCollectionFrontdoorResult(
            session_id=session_id,
            status=status,
            route_mode="heavy",
            execution_agent_id=str(route_payload.get("execution_agent_id") or brief.owner_agent_id),
            trigger_source=trigger_source,
            goal=brief.goal,
            stop_reason=stop_reason,
            findings=findings_payload,
            collected_sources=sources_payload,
            conflicts=conflicts,
            gaps=gaps,
            final_report_id=final_report_id,
        )

    def _find_reusable_heavy_session(
        self,
        *,
        brief: ResearchBrief,
        execution_agent_id: str,
        trigger_source: str,
        preferred_session_id: str | None = None,
    ) -> ResearchSessionRecord | None:
        followup_like = _looks_like_followup_question(brief.question)
        normalized_trigger_source = _string(trigger_source) or ""
        normalized_preferred_session_id = _string(preferred_session_id)
        getter = getattr(self.research_session_repository, "get_research_session", None)
        if normalized_preferred_session_id is not None and callable(getter):
            preferred_session = getter(normalized_preferred_session_id)
            if (
                preferred_session is not None
                and str(getattr(preferred_session, "provider", "") or "").strip() == "baidu-page"
                and str(getattr(preferred_session, "owner_agent_id", "") or "").strip() == execution_agent_id
                and str(getattr(preferred_session, "status", "") or "").strip()
                not in {"failed", "cancelled"}
            ):
                return preferred_session
        lister = getattr(self.research_session_repository, "list_research_sessions", None)
        if not callable(lister):
            return None
        candidates = list(
            lister(
                provider="baidu-page",
                owner_agent_id=execution_agent_id,
                industry_instance_id=brief.industry_instance_id,
                work_context_id=brief.work_context_id,
                limit=12,
            )
            or []
        )
        reusable_candidates = [
            candidate
            for candidate in candidates
            if candidate is not None
            and str(getattr(candidate, "status", "") or "").strip()
            not in {"failed", "cancelled"}
        ]
        if not reusable_candidates:
            return None
        active_candidates = [
            candidate
            for candidate in reusable_candidates
            if str(getattr(candidate, "status", "") or "").strip()
            in {"queued", "running", "waiting-login"}
        ]
        if active_candidates:
            return max(
                active_candidates,
                key=lambda item: getattr(item, "updated_at", None) or getattr(item, "created_at", None),
            )
        latest_reusable_candidate = max(
            reusable_candidates,
            key=lambda item: getattr(item, "updated_at", None) or getattr(item, "created_at", None),
        )
        if normalized_trigger_source == "main-brain-followup":
            if len(reusable_candidates) == 1:
                return latest_reusable_candidate
        if len(reusable_candidates) == 1:
            candidate = reusable_candidates[0]
            if followup_like or _allow_strong_overlap_reuse(brief=brief, candidate=candidate):
                return candidate
            return None
        best_candidate: ResearchSessionRecord | None = None
        best_score = 0
        for candidate in reusable_candidates:
            score = _research_session_match_score(brief=brief, candidate=candidate)
            if score > best_score:
                best_score = score
                best_candidate = candidate
        if best_candidate is None:
            return None
        if normalized_trigger_source == "main-brain-followup" and best_score < 60:
            return latest_reusable_candidate
        if followup_like and best_score > 0:
            return best_candidate
        return best_candidate if best_score >= 60 else None

    def _run_light_path(
        self,
        *,
        brief: ResearchBrief,
        requested_sources: list[str],
        route_payload: dict[str, Any],
        metadata: dict[str, Any],
        trigger_source: str,
    ) -> SourceCollectionFrontdoorResult:
        collection = self._source_collection_service.collect(
            brief=brief,
            owner_agent_id=brief.owner_agent_id,
            requested_sources=requested_sources,
        )
        brief_payload = {
            "goal": brief.goal,
            "question": brief.question,
            "why_needed": brief.why_needed,
            "done_when": brief.done_when,
            "collection_mode_hint": brief.collection_mode_hint,
            "requested_sources": requested_sources,
            "writeback_target": _mapping(getattr(brief, "writeback_target", None)) or None,
        }
        findings_payload = [
            finding.model_dump(mode="json")
            for finding in list(collection.findings or [])
        ]
        sources_payload = [
            source.model_dump(mode="json")
            for source in list(collection.collected_sources or [])
        ]
        retrieval_payloads = [
            self._serialize_retrieval_run_payload(run)
            for run in list(collection.retrieval_runs or [])
        ]
        retrieval_payloads = [payload for payload in retrieval_payloads if payload]
        now = _utc_now()
        session_id = f"research-session:{uuid4().hex}"
        round_evidence_ids: list[str] = []
        evidence_id = self._append_light_evidence(
            session_id=session_id,
            brief=brief,
            trigger_source=trigger_source,
            route_payload=route_payload,
            findings_payload=findings_payload,
            sources_payload=sources_payload,
            conflicts=list(collection.conflicts or []),
            gaps=list(collection.gaps or []),
        )
        if evidence_id is not None:
            round_evidence_ids = [evidence_id]
            sources_payload = self._attach_evidence_to_sources(
                sources_payload=sources_payload,
                evidence_id=evidence_id,
            )
        session_metadata = dict(metadata)
        round_metadata: dict[str, Any] = {}
        if retrieval_payloads:
            session_metadata["retrieval"] = retrieval_payloads[0]
            round_metadata["retrieval"] = retrieval_payloads[0]
        session = ResearchSessionRecord(
            id=session_id,
            provider="source-collection",
            industry_instance_id=brief.industry_instance_id,
            work_context_id=brief.work_context_id,
            owner_agent_id=str(route_payload.get("execution_agent_id") or brief.owner_agent_id),
            supervisor_agent_id=brief.supervisor_agent_id,
            trigger_source=trigger_source,
            goal=brief.goal,
            status="completed",
            round_count=1,
            stable_findings=[
                str(item.get("summary") or "").strip()
                for item in findings_payload
                if str(item.get("summary") or "").strip()
            ],
            open_questions=list(collection.gaps or []),
            brief=brief_payload,
            conflicts=list(collection.conflicts or []),
            metadata=session_metadata,
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
        links_payload = [
            {
                "url": str(item.get("source_ref") or "").strip(),
                "title": str(item.get("title") or "").strip(),
                "kind": str(item.get("source_kind") or "").strip() or "source",
            }
            for item in sources_payload
            if str(item.get("source_ref") or "").strip()
        ]
        round_record = ResearchSessionRoundRecord(
            id=f"{session_id}:round:1",
            session_id=session_id,
            round_index=1,
            question=brief.question,
            response_summary=(
                str(findings_payload[0].get("summary") or "").strip()
                if findings_payload
                else None
            ),
            raw_links=links_payload,
            selected_links=links_payload,
            new_findings=[
                str(item.get("summary") or "").strip()
                for item in findings_payload
                if str(item.get("summary") or "").strip()
            ],
            sources=sources_payload,
            findings=findings_payload,
            conflicts=list(collection.conflicts or []),
            gaps=list(collection.gaps or []),
            remaining_gaps=list(collection.gaps or []),
            decision="stop",
            evidence_ids=round_evidence_ids,
            metadata=round_metadata,
            created_at=now,
            updated_at=now,
        )
        report_id = self._write_light_report(
            session=session,
            round_record=round_record,
            findings_payload=findings_payload,
            sources_payload=sources_payload,
            evidence_ids=round_evidence_ids,
            conflicts=list(collection.conflicts or []),
            gaps=list(collection.gaps or []),
        )
        session = session.model_copy(
            update={
                "final_report_id": report_id,
            },
        )
        writeback_truth = self._apply_light_writeback(
            session=session,
            round_record=round_record,
            report_id=report_id,
        )
        session = session.model_copy(
            update={
                "writeback_truth": writeback_truth,
            },
        )
        round_record = round_record.model_copy(
            update={
                "writeback_truth": writeback_truth,
            },
        )
        upsert_session = getattr(
            self.research_session_repository,
            "upsert_research_session",
            None,
        )
        upsert_round = getattr(
            self.research_session_repository,
            "upsert_research_round",
            None,
        )
        if callable(upsert_session):
            upsert_session(session)
        if callable(upsert_round):
            upsert_round(round_record)
        return SourceCollectionFrontdoorResult(
            session_id=session_id,
            status="completed",
            route_mode="light",
            execution_agent_id=str(route_payload.get("execution_agent_id") or brief.owner_agent_id),
            trigger_source=trigger_source,
            goal=brief.goal,
            stop_reason="light-collection-complete",
            findings=findings_payload,
            collected_sources=sources_payload,
            conflicts=list(collection.conflicts or []),
            gaps=list(collection.gaps or []),
            final_report_id=report_id,
        )

    def _serialize_retrieval_run_payload(
        self,
        run: object | None,
    ) -> dict[str, Any]:
        if run is None:
            return {}
        model_dump = getattr(run, "model_dump", None)
        payload = model_dump(mode="json") if callable(model_dump) else {}
        if not isinstance(payload, dict):
            return {}
        return {
            "query": _mapping(payload.get("query")),
            "plan": _mapping(payload.get("plan")),
            "selected_hits": [
                _mapping(item)
                for item in list(payload.get("selected_hits") or [])
                if _mapping(item)
            ],
            "dropped_hits": [
                _mapping(item)
                for item in list(payload.get("dropped_hits") or [])
                if _mapping(item)
            ],
            "coverage_summary": _mapping(payload.get("coverage_summary")),
            "trace": [
                _mapping(item)
                for item in list(payload.get("trace") or [])
                if _mapping(item)
            ],
        }

    def _append_light_evidence(
        self,
        *,
        session_id: str,
        brief: ResearchBrief,
        trigger_source: str,
        route_payload: dict[str, Any],
        findings_payload: list[dict[str, Any]],
        sources_payload: list[dict[str, Any]],
        conflicts: list[str],
        gaps: list[str],
    ) -> str | None:
        if self._evidence_ledger is None:
            return None
        top_finding = next(
            (
                str(item.get("summary") or "").strip()
                for item in findings_payload
                if str(item.get("summary") or "").strip()
            ),
            "",
        )
        record = self._evidence_ledger.append(
            EvidenceRecord(
                task_id=session_id,
                actor_ref=str(route_payload.get("execution_agent_id") or brief.owner_agent_id),
                risk_level="auto",
                action_summary=f"Light source collection: {brief.goal}",
                result_summary=top_finding or f"Collected {len(sources_payload)} source(s).",
                capability_ref="source-collection:light",
                environment_ref="source-collection",
                metadata={
                    "research_session_id": session_id,
                    "trigger_source": trigger_source,
                    "brief": {
                        "goal": brief.goal,
                        "question": brief.question,
                        "why_needed": brief.why_needed,
                        "done_when": brief.done_when,
                    },
                    "sources": list(sources_payload),
                    "findings": list(findings_payload),
                    "conflicts": list(conflicts),
                    "gaps": list(gaps),
                },
            ),
        )
        return _string(record.id)

    def _attach_evidence_to_sources(
        self,
        *,
        sources_payload: list[dict[str, Any]],
        evidence_id: str,
    ) -> list[dict[str, Any]]:
        attached: list[dict[str, Any]] = []
        for item in sources_payload:
            payload = dict(item)
            payload["evidence_id"] = _string(payload.get("evidence_id")) or evidence_id
            attached.append(payload)
        return attached

    def _write_light_report(
        self,
        *,
        session: ResearchSessionRecord,
        round_record: ResearchSessionRoundRecord,
        findings_payload: list[dict[str, Any]],
        sources_payload: list[dict[str, Any]],
        evidence_ids: list[str],
        conflicts: list[str],
        gaps: list[str],
    ) -> str | None:
        upsert_report = getattr(self.report_repository, "upsert_report", None)
        if not callable(upsert_report) or _string(session.industry_instance_id) is None:
            return None
        findings = [
            str(item.get("summary") or "").strip()
            for item in findings_payload
            if str(item.get("summary") or "").strip()
        ]
        summary = findings[0] if findings else (_string(round_record.response_summary) or session.goal)
        report = AgentReportRecord(
            industry_instance_id=str(session.industry_instance_id),
            work_context_id=session.work_context_id,
            owner_agent_id=session.owner_agent_id,
            owner_role_id="source-collection",
            report_kind="source-collection",
            headline=f"Source collection: {session.goal[:64]}",
            summary=summary,
            findings=findings,
            uncertainties=list(gaps),
            recommendation="Review collected sources and decide whether to adopt them.",
            evidence_ids=list(evidence_ids),
            metadata={
                "provider": session.provider,
                "research_session_id": session.id,
                "conflicts": list(conflicts),
                "source_refs": [
                    _string(item.get("source_ref"))
                    for item in sources_payload
                    if _string(item.get("source_ref")) is not None
                ],
            },
        )
        stored_report = upsert_report(report)
        return _string(getattr(stored_report, "id", None) or report.id)

    def _apply_light_writeback(
        self,
        *,
        session: ResearchSessionRecord,
        round_record: ResearchSessionRoundRecord,
        report_id: str | None,
    ) -> dict[str, Any]:
        work_context_chunk_ids: list[str] = []
        industry_document_id: str | None = None
        knowledge_ingest = getattr(self._knowledge_service, "ingest_research_session", None)
        if callable(knowledge_ingest):
            ingestion = _mapping(
                knowledge_ingest(session=session, rounds=[round_record]),
            )
            work_context_chunk_ids = _string_list(ingestion.get("work_context_chunk_ids"))
            industry_document_id = _string(ingestion.get("industry_document_id"))
        node_ids: list[str] = []
        relation_ids: list[str] = []
        summarizer = getattr(self._knowledge_writeback_service, "summarize_change", None)
        applier = getattr(self._knowledge_writeback_service, "apply_change", None)
        builder = getattr(
            self._knowledge_writeback_service,
            "build_research_session_writeback",
            None,
        )
        if callable(builder):
            change = builder(session=session, rounds=[round_record])
            graph_result = _mapping(applier(change)) if callable(applier) else {}
            if not graph_result and callable(summarizer):
                graph_result = _mapping(summarizer(change))
            node_ids = _string_list(graph_result.get("node_ids"))
            relation_ids = _string_list(graph_result.get("relation_ids"))
        writeback_target = _mapping(session.brief.get("writeback_target"))
        scope_type = (
            _string(writeback_target.get("scope_type"))
            or ("work_context" if _string(session.work_context_id) is not None else None)
            or ("industry" if _string(session.industry_instance_id) is not None else None)
        )
        scope_id = (
            _string(writeback_target.get("scope_id"))
            or _string(session.work_context_id)
            or _string(session.industry_instance_id)
        )
        status = "written" if any(
            (report_id, work_context_chunk_ids, industry_document_id, node_ids, relation_ids),
        ) else "pending"
        return {
            "status": status,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "report_id": report_id,
            "work_context_chunk_ids": work_context_chunk_ids,
            "industry_document_id": industry_document_id,
            "node_ids": node_ids,
            "relation_ids": relation_ids,
        }


@dataclass(slots=True)
class RuntimeDomainServices:
    goal_service: GoalService
    agent_profile_service: AgentProfileService
    reporting_service: StateReportingService
    operating_lane_service: OperatingLaneService
    backlog_service: BacklogService
    operating_cycle_service: OperatingCycleService
    assignment_service: AssignmentService
    agent_report_service: AgentReportService
    media_service: MediaService
    industry_service: IndustryService
    workflow_template_service: WorkflowTemplateService
    fixed_sop_service: FixedSopService
    routine_service: RoutineService
    prediction_service: PredictionService
    query_execution_service: KernelQueryExecutionService
    main_brain_chat_service: MainBrainChatService
    main_brain_orchestrator: MainBrainOrchestrator
    report_replan_engine: ReportReplanEngine
    research_session_service: BaiduPageResearchService | None = None


def _build_goal_service(
    *,
    assignment_planner: AssignmentPlanningCompiler,
    **kwargs: Any,
) -> GoalService:
    try:
        return GoalService(
            assignment_planner=assignment_planner,
            **kwargs,
        )
    except TypeError as exc:
        if "assignment_planner" not in str(exc):
            raise
        return GoalService(**kwargs)


def build_runtime_domain_services(
    *,
    session_backend: Any,
    conversation_compaction_service: Any,
    mcp_manager: MCPClientManager,
    state_store: SQLiteStateStore,
    repositories: RuntimeRepositories,
    evidence_ledger: EvidenceLedger,
    environment_service: EnvironmentService,
    runtime_event_bus: RuntimeEventBus,
    runtime_provider: ProviderRuntimeSurface,
    state_query_service: RuntimeCenterStateQueryService,
    strategy_memory_service: StateStrategyMemoryService,
    knowledge_service: StateKnowledgeService,
    derived_memory_index_service: DerivedMemoryIndexService,
    memory_reflection_service: MemoryReflectionService,
    memory_recall_service: MemoryRecallService,
    memory_retain_service: MemoryRetainService,
    memory_sleep_service: MemorySleepService | None = None,
    memory_activation_service: MemoryActivationService | None = None,
    knowledge_graph_service: KnowledgeGraphService | None = None,
    agent_experience_service: AgentExperienceMemoryService | None = None,
    work_context_service: WorkContextService | None = None,
    learning_service: LearningService | None = None,
    capability_service: CapabilityService | None = None,
    capability_candidate_service: object | None = None,
    capability_donor_service: object | None = None,
    capability_portfolio_service: object | None = None,
    skill_trial_service: object | None = None,
    skill_lifecycle_decision_service: object | None = None,
    kernel_dispatcher: KernelDispatcher | None = None,
    kernel_tool_bridge: KernelToolBridge | None = None,
    actor_mailbox_service: ActorMailboxService | None = None,
    actor_supervisor: ActorSupervisor | None = None,
    executor_runtime_coordinator: AssignmentExecutorRuntimeCoordinator | None = None,
) -> RuntimeDomainServices:
    strategy_planning_compiler = StrategyPlanningCompiler()
    cycle_planner = CyclePlanningCompiler()
    assignment_planner = AssignmentPlanningCompiler()
    report_replan_engine = ReportReplanEngine()

    goal_service = _build_goal_service(
        assignment_planner=assignment_planner,
        repository=repositories.goal_repository,
        override_repository=repositories.goal_override_repository,
        dispatcher=kernel_dispatcher,
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        runtime_frame_repository=repositories.runtime_frame_repository,
        decision_request_repository=repositories.decision_request_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
        strategy_memory_service=strategy_memory_service,
        knowledge_service=knowledge_service,
        memory_recall_service=memory_recall_service,
        memory_activation_service=memory_activation_service,
        industry_instance_repository=repositories.industry_instance_repository,
        runtime_event_bus=runtime_event_bus,
    )
    capability_service.set_goal_service(goal_service)
    state_query_service.set_goal_service(goal_service)

    agent_profile_service = AgentProfileService(
        override_repository=repositories.agent_profile_override_repository,
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        agent_runtime_repository=repositories.agent_runtime_repository,
        agent_mailbox_repository=repositories.agent_mailbox_repository,
        agent_checkpoint_repository=repositories.agent_checkpoint_repository,
        agent_lease_repository=repositories.agent_lease_repository,
        agent_thread_binding_repository=repositories.agent_thread_binding_repository,
        decision_request_repository=repositories.decision_request_repository,
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
        capability_service=capability_service,
        learning_service=learning_service,
        goal_service=goal_service,
        industry_instance_repository=repositories.industry_instance_repository,
    )
    agent_profile_service.backfill_industry_baseline_capabilities()
    goal_service.set_agent_profile_service(agent_profile_service)
    state_query_service.set_learning_service(learning_service)
    state_query_service.set_agent_profile_service(agent_profile_service)
    capability_service.set_agent_profile_service(agent_profile_service)

    reporting_service = StateReportingService(
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        goal_repository=repositories.goal_repository,
        decision_request_repository=repositories.decision_request_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
        industry_instance_repository=repositories.industry_instance_repository,
        agent_profile_service=agent_profile_service,
        prediction_case_repository=repositories.prediction_case_repository,
        prediction_recommendation_repository=repositories.prediction_recommendation_repository,
        prediction_review_repository=repositories.prediction_review_repository,
    )
    derived_memory_index_service.set_reporting_service(reporting_service)
    derived_memory_index_service.set_learning_service(learning_service)
    memory_reflection_service.set_learning_service(learning_service)

    operating_lane_service = OperatingLaneService(
        repository=repositories.operating_lane_repository,
    )
    backlog_service = BacklogService(
        repository=repositories.backlog_item_repository,
    )
    set_backlog_graph_projection = getattr(backlog_service, "set_graph_projection_service", None)
    if callable(set_backlog_graph_projection):
        set_backlog_graph_projection(knowledge_graph_service)
    operating_cycle_service = OperatingCycleService(
        repository=repositories.operating_cycle_repository,
    )
    set_cycle_graph_projection = getattr(
        operating_cycle_service,
        "set_graph_projection_service",
        None,
    )
    if callable(set_cycle_graph_projection):
        set_cycle_graph_projection(knowledge_graph_service)
    assignment_service = AssignmentService(
        repository=repositories.assignment_repository,
    )
    set_assignment_graph_projection = getattr(
        assignment_service,
        "set_graph_projection_service",
        None,
    )
    if callable(set_assignment_graph_projection):
        set_assignment_graph_projection(knowledge_graph_service)
    agent_report_service = AgentReportService(
        repository=repositories.agent_report_repository,
        memory_retain_service=memory_retain_service,
    )
    set_report_graph_projection = getattr(
        agent_report_service,
        "set_graph_projection_service",
        None,
    )
    if callable(set_report_graph_projection):
        set_report_graph_projection(knowledge_graph_service)
    if work_context_service is not None:
        set_work_context_graph_projection = getattr(
            work_context_service,
            "set_graph_projection_service",
            None,
        )
        if callable(set_work_context_graph_projection):
            set_work_context_graph_projection(knowledge_graph_service)
    media_service = MediaService(
        repository=repositories.media_analysis_repository,
        evidence_ledger=evidence_ledger,
        knowledge_service=knowledge_service,
        strategy_memory_service=strategy_memory_service,
        backlog_service=backlog_service,
        operating_lane_service=operating_lane_service,
        industry_instance_repository=repositories.industry_instance_repository,
        memory_retain_service=memory_retain_service,
    )
    industry_runtime_bindings = build_industry_service_runtime_bindings(
        kernel_dispatcher=kernel_dispatcher,
        operating_lane_repository=repositories.operating_lane_repository,
        backlog_item_repository=repositories.backlog_item_repository,
        operating_cycle_repository=repositories.operating_cycle_repository,
        assignment_repository=repositories.assignment_repository,
        agent_report_repository=repositories.agent_report_repository,
        agent_runtime_repository=repositories.agent_runtime_repository,
        agent_thread_binding_repository=repositories.agent_thread_binding_repository,
        schedule_repository=repositories.schedule_repository,
        agent_mailbox_repository=repositories.agent_mailbox_repository,
        agent_checkpoint_repository=repositories.agent_checkpoint_repository,
        agent_lease_repository=repositories.agent_lease_repository,
        strategy_memory_repository=repositories.strategy_memory_repository,
        workflow_run_repository=repositories.workflow_run_repository,
        prediction_case_repository=repositories.prediction_case_repository,
        prediction_scenario_repository=repositories.prediction_scenario_repository,
        prediction_signal_repository=repositories.prediction_signal_repository,
        prediction_recommendation_repository=repositories.prediction_recommendation_repository,
        prediction_review_repository=repositories.prediction_review_repository,
        operating_lane_service=operating_lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=operating_cycle_service,
        assignment_service=assignment_service,
        agent_report_service=agent_report_service,
        strategy_planning_compiler=strategy_planning_compiler,
        cycle_planner=cycle_planner,
        assignment_planner=assignment_planner,
        report_replan_engine=report_replan_engine,
        state_store=state_store,
        memory_retain_service=memory_retain_service,
        memory_activation_service=memory_activation_service,
        knowledge_service=knowledge_service,
        knowledge_graph_service=knowledge_graph_service,
    )
    industry_service = IndustryService(
        goal_service=goal_service,
        industry_instance_repository=repositories.industry_instance_repository,
        session_backend=session_backend,
        media_service=media_service,
        goal_override_repository=repositories.goal_override_repository,
        agent_profile_override_repository=repositories.agent_profile_override_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
        agent_profile_service=agent_profile_service,
        capability_service=capability_service,
        strategy_memory_service=strategy_memory_service,
        state_store=state_store,
        draft_generator=IndustryDraftGenerator(provider_manager=runtime_provider),
        runtime_bindings=industry_runtime_bindings,
        memory_retain_service=memory_retain_service,
        memory_activation_service=memory_activation_service,
        knowledge_service=knowledge_service,
        work_context_service=work_context_service,
        actor_mailbox_service=actor_mailbox_service,
    )
    capability_service.set_industry_service(industry_service)

    workflow_template_service = WorkflowTemplateService(
        workflow_template_repository=repositories.workflow_template_repository,
        workflow_run_repository=repositories.workflow_run_repository,
        workflow_preset_repository=repositories.workflow_preset_repository,
        goal_service=goal_service,
        goal_override_repository=repositories.goal_override_repository,
        schedule_repository=repositories.schedule_repository,
        industry_instance_repository=repositories.industry_instance_repository,
        strategy_memory_service=strategy_memory_service,
        task_repository=repositories.task_repository,
        decision_request_repository=repositories.decision_request_repository,
        agent_profile_override_repository=repositories.agent_profile_override_repository,
        agent_profile_service=agent_profile_service,
        evidence_ledger=evidence_ledger,
        capability_service=capability_service,
        environment_service=environment_service,
    )
    fixed_sop_service = FixedSopService(
        template_repository=repositories.fixed_sop_template_repository,
        binding_repository=repositories.fixed_sop_binding_repository,
        workflow_run_repository=repositories.workflow_run_repository,
        agent_report_repository=repositories.agent_report_repository,
        evidence_ledger=evidence_ledger,
        routine_service=None,
        environment_service=environment_service,
    )
    routine_service = RoutineService(
        routine_repository=repositories.routine_repository,
        routine_run_repository=repositories.routine_run_repository,
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
        kernel_dispatcher=kernel_dispatcher,
        state_store=state_store,
        memory_retain_service=memory_retain_service,
        learning_service=learning_service,
        capability_service=capability_service,
        agent_profile_service=agent_profile_service,
    )
    fixed_sop_service.set_routine_service(routine_service)
    capability_service.set_routine_service(routine_service)
    capability_service.set_fixed_sop_service(fixed_sop_service)
    capability_service.get_discovery_service().set_fixed_sop_service(fixed_sop_service)
    learning_service.configure_bindings(
        LearningRuntimeBindings(
            industry_service=industry_service,
            capability_service=capability_service,
            kernel_dispatcher=kernel_dispatcher,
            fixed_sop_service=fixed_sop_service,
            agent_profile_service=agent_profile_service,
            experience_memory_service=agent_experience_service,
        ),
    )

    prediction_service = PredictionService(
        case_repository=repositories.prediction_case_repository,
        scenario_repository=repositories.prediction_scenario_repository,
        signal_repository=repositories.prediction_signal_repository,
        recommendation_repository=repositories.prediction_recommendation_repository,
        review_repository=repositories.prediction_review_repository,
        evidence_ledger=evidence_ledger,
        reporting_service=reporting_service,
        goal_repository=repositories.goal_repository,
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        decision_request_repository=repositories.decision_request_repository,
        industry_instance_repository=repositories.industry_instance_repository,
        workflow_run_repository=repositories.workflow_run_repository,
        strategy_memory_service=strategy_memory_service,
        capability_service=capability_service,
        capability_candidate_service=capability_candidate_service,
        capability_donor_service=capability_donor_service,
        capability_portfolio_service=capability_portfolio_service,
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
        agent_profile_service=agent_profile_service,
        kernel_dispatcher=kernel_dispatcher,
    )
    industry_service.set_prediction_service(prediction_service)

    environment_service.set_kernel_dispatcher(kernel_dispatcher)
    memory_surface_service = MemorySurfaceService(
        memory_recall_service=memory_recall_service,
        conversation_compaction_service=conversation_compaction_service,
        surface_learning_provider=learning_service,
    )

    query_execution_service = KernelQueryExecutionService(
        session_backend=session_backend,
        conversation_compaction_service=conversation_compaction_service,
        mcp_manager=mcp_manager,
        tool_bridge=kernel_tool_bridge,
        environment_service=environment_service,
        capability_service=capability_service,
        kernel_dispatcher=kernel_dispatcher,
        agent_profile_service=agent_profile_service,
        delegation_service=None,
        industry_service=industry_service,
        strategy_memory_service=strategy_memory_service,
        prediction_service=prediction_service,
        knowledge_service=knowledge_service,
        memory_recall_service=memory_recall_service,
        memory_surface_service=memory_surface_service,
        memory_activation_service=memory_activation_service,
        agent_checkpoint_repository=repositories.agent_checkpoint_repository,
        agent_runtime_repository=repositories.agent_runtime_repository,
        governance_control_repository=repositories.governance_control_repository,
        task_repository=repositories.task_repository,
        task_runtime_repository=repositories.task_runtime_repository,
        evidence_ledger=evidence_ledger,
        provider_manager=runtime_provider,
    )
    main_brain_chat_service = MainBrainChatService(
        session_backend=session_backend,
        industry_service=industry_service,
        agent_profile_service=agent_profile_service,
        memory_recall_service=memory_recall_service,
        memory_surface_service=memory_surface_service,
        model_factory=runtime_provider.get_active_chat_model,
    )
    main_brain_orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        session_backend=session_backend,
        environment_service=environment_service,
        intake_contract_resolver=resolve_request_main_brain_intake_contract,
        execution_planner=MainBrainExecutionPlanner(
            knowledge_graph_service=knowledge_graph_service,
        ),
        executor_runtime_coordinator=executor_runtime_coordinator,
    )
    heavy_research_session_service = BaiduPageResearchService(
        research_session_repository=repositories.research_session_repository,
        browser_action_runner=run_browser_use_json,
        browser_download_resolver=list_browser_downloads,
        report_repository=repositories.agent_report_repository,
        knowledge_service=knowledge_service,
        work_context_service=work_context_service,
        knowledge_writeback_service=KnowledgeWritebackService(
            knowledge_service=knowledge_service,
            derived_index_service=derived_memory_index_service,
            reflection_service=memory_reflection_service,
            memory_sleep_service=memory_sleep_service,
        ),
    )
    research_session_service = SourceCollectionFrontdoorService(
        heavy_research_service=heavy_research_session_service,
        research_session_repository=repositories.research_session_repository,
        report_repository=repositories.agent_report_repository,
        evidence_ledger=evidence_ledger,
        knowledge_service=knowledge_service,
        knowledge_writeback_service=KnowledgeWritebackService(
            knowledge_service=knowledge_service,
            derived_index_service=derived_memory_index_service,
            reflection_service=memory_reflection_service,
            memory_sleep_service=memory_sleep_service,
        ),
    )
    set_research_session_service = getattr(
        main_brain_chat_service,
        "set_research_session_service",
        None,
    )
    if callable(set_research_session_service):
        set_research_session_service(research_session_service)
    try:
        setattr(query_execution_service, "_source_collection_frontdoor", research_session_service)
    except Exception:
        pass

    return RuntimeDomainServices(
        goal_service=goal_service,
        agent_profile_service=agent_profile_service,
        reporting_service=reporting_service,
        operating_lane_service=operating_lane_service,
        backlog_service=backlog_service,
        operating_cycle_service=operating_cycle_service,
        assignment_service=assignment_service,
        agent_report_service=agent_report_service,
        media_service=media_service,
        industry_service=industry_service,
        workflow_template_service=workflow_template_service,
        fixed_sop_service=fixed_sop_service,
        routine_service=routine_service,
        prediction_service=prediction_service,
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
        report_replan_engine=report_replan_engine,
        research_session_service=research_session_service,
    )
