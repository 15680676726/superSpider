# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from datetime import datetime, timezone

from ..state.repositories import (
    SqliteAssignmentRepository,
    SqliteOperatingLaneRepository,
    SqliteStrategyMemoryRepository,
    SqliteSurfaceCapabilityTwinRepository,
    SqliteSurfacePlaybookRepository,
)
from .models import SurfaceRewardProjection, SurfaceRewardRankItem

_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]+|[a-z0-9]+")


class SurfaceRewardService:
    """Build formal, goal-conditioned reward ranking for one surface scope."""

    def __init__(
        self,
        *,
        surface_capability_twin_repository: SqliteSurfaceCapabilityTwinRepository,
        surface_playbook_repository: SqliteSurfacePlaybookRepository,
        strategy_memory_repository: SqliteStrategyMemoryRepository,
        operating_lane_repository: SqliteOperatingLaneRepository,
        assignment_repository: SqliteAssignmentRepository,
        agent_profile_service: object | None = None,
    ) -> None:
        self._surface_capability_twin_repository = surface_capability_twin_repository
        self._surface_playbook_repository = surface_playbook_repository
        self._strategy_memory_repository = strategy_memory_repository
        self._operating_lane_repository = operating_lane_repository
        self._assignment_repository = assignment_repository
        self._agent_profile_service = agent_profile_service

    def set_agent_profile_service(self, service: object | None) -> None:
        self._agent_profile_service = service

    def refresh_reward_ranking(
        self,
        *,
        scope_level: str,
        scope_id: str,
        industry_instance_id: str | None = None,
        lane_id: str | None = None,
        assignment_id: str | None = None,
        owner_agent_id: str | None = None,
    ) -> SurfaceRewardProjection:
        active_twins = self._surface_capability_twin_repository.get_active_twins(
            scope_level=scope_level,
            scope_id=scope_id,
        )
        active_playbook = self._surface_playbook_repository.get_active_playbook(
            scope_level=scope_level,
            scope_id=scope_id,
        )
        metadata = dict(active_playbook.metadata if active_playbook is not None else {})
        if active_twins:
            metadata = {
                **active_twins[0].metadata,
                **metadata,
            }
        industry_instance_id = self._non_empty_str(
            industry_instance_id,
            metadata.get("industry_instance_id"),
            scope_id if scope_level in {"industry", "industry_scope"} else None,
        )
        lane_id = self._non_empty_str(lane_id, metadata.get("lane_id"))
        assignment_id = self._non_empty_str(assignment_id, metadata.get("assignment_id"))
        owner_agent_id = self._non_empty_str(owner_agent_id, metadata.get("owner_agent_id"))
        strategy = self._resolve_strategy(industry_instance_id=industry_instance_id)
        lane = self._operating_lane_repository.get_lane(lane_id) if lane_id else None
        assignment = (
            self._assignment_repository.get_assignment(assignment_id)
            if assignment_id
            else None
        )
        agent = self._resolve_agent(owner_agent_id)
        contexts = self._build_contexts(
            strategy=strategy,
            lane=lane,
            assignment=assignment,
            agent=agent,
        )
        ranking = [
            self._build_rank_item(twin=twin, contexts=contexts)
            for twin in active_twins
        ]
        ranking.sort(
            key=lambda item: (
                item.score,
                item.updated_at or datetime.min.replace(tzinfo=timezone.utc),
                item.capability_name,
            ),
            reverse=True,
        )
        version_candidates = [record.version for record in active_twins]
        updated_candidates = [record.updated_at for record in active_twins]
        if active_playbook is not None:
            version_candidates.append(active_playbook.version)
            updated_candidates.append(active_playbook.updated_at)
        return SurfaceRewardProjection(
            scope_level=scope_level,
            scope_id=scope_id,
            version=max(version_candidates) if version_candidates else None,
            updated_at=self._latest_datetime(updated_candidates),
            ranking=ranking,
            context_signals=[
                signal
                for signal in (
                    *(contexts["strategy"]["items"]),
                    *(contexts["lane"]["items"]),
                    *(contexts["assignment"]["items"]),
                    *(contexts["agent"]["items"]),
                )
                if signal
            ],
        )

    def _resolve_strategy(self, *, industry_instance_id: str | None):
        if industry_instance_id is None:
            return None
        matches = self._strategy_memory_repository.list_strategies(
            industry_instance_id=industry_instance_id,
            status="active",
            limit=1,
        )
        return matches[0] if matches else None

    def _resolve_agent(self, owner_agent_id: str | None):
        if owner_agent_id is None or self._agent_profile_service is None:
            return None
        getter = getattr(self._agent_profile_service, "get_agent", None)
        if not callable(getter):
            return None
        try:
            return getter(owner_agent_id)
        except Exception:
            return None

    def _build_contexts(
        self,
        *,
        strategy,
        lane,
        assignment,
        agent,
    ) -> dict[str, dict[str, object]]:
        return {
            "strategy": {
                "weight": 5.0,
                "items": self._collect_context_items(
                    getattr(strategy, "mission", None),
                    getattr(strategy, "current_focuses", []),
                    getattr(strategy, "priority_order", []),
                    getattr(strategy, "evidence_requirements", []),
                ),
            },
            "lane": {
                "weight": 3.0,
                "items": self._collect_context_items(
                    getattr(lane, "title", None),
                    getattr(lane, "summary", None),
                    getattr(getattr(lane, "metadata", {}), "get", lambda *_: None)(
                        "evidence_expectations",
                    ),
                ),
            },
            "assignment": {
                "weight": 6.0,
                "items": self._collect_context_items(
                    getattr(assignment, "title", None),
                    getattr(assignment, "summary", None),
                    getattr(getattr(assignment, "metadata", {}), "get", lambda *_: None)(
                        "success_criteria",
                    ),
                ),
            },
            "agent": {
                "weight": 2.0,
                "items": self._collect_context_items(
                    getattr(agent, "role_name", None),
                    getattr(agent, "role_summary", None),
                    getattr(agent, "mission", None),
                    getattr(agent, "evidence_expectations", []),
                ),
            },
        }

    def _build_rank_item(
        self,
        *,
        twin,
        contexts: dict[str, dict[str, object]],
    ) -> SurfaceRewardRankItem:
        phrases = self._collect_context_items(
            twin.capability_name.replace("_", " "),
            twin.summary,
            twin.execution_steps,
            twin.result_signals,
        )
        twin_tokens = set(self._tokenize(phrases))
        score = 0.0
        reasons: list[str] = []
        for label, bucket in contexts.items():
            context_items = bucket["items"]
            if not isinstance(context_items, list) or not context_items:
                continue
            phrase_hits = 0
            token_hits = 0
            for item in context_items:
                normalized_item = self._normalize_text(item)
                if not normalized_item:
                    continue
                if any(
                    phrase and phrase in normalized_item
                    for phrase in (self._normalize_text(phrase) for phrase in phrases)
                ):
                    phrase_hits += 1
                context_tokens = set(self._tokenize(item))
                token_hits += len(twin_tokens.intersection(context_tokens))
            if phrase_hits == 0 and token_hits == 0:
                continue
            bucket_score = float(bucket["weight"]) * phrase_hits + float(token_hits)
            score += bucket_score
            reasons.append(f"{label}+{bucket_score:.1f}")
        if score == 0:
            reasons.append("no-formal-match")
        return SurfaceRewardRankItem(
            twin_id=twin.twin_id,
            capability_name=twin.capability_name,
            surface_kind=twin.surface_kind,
            summary=twin.summary,
            score=score,
            reasons=reasons,
            version=twin.version,
            updated_at=twin.updated_at,
        )

    @staticmethod
    def _collect_context_items(*values: object) -> list[str]:
        items: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value is None:
                continue
            raw_items = value if isinstance(value, list) else [value]
            for item in raw_items:
                text = str(item or "").strip()
                if not text:
                    continue
                lowered = text.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                items.append(text)
        return items

    @staticmethod
    def _normalize_text(value: object) -> str:
        return " ".join(SurfaceRewardService._tokenize(value))

    @staticmethod
    def _tokenize(value: object) -> list[str]:
        text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
        return _TOKEN_PATTERN.findall(text)

    @staticmethod
    def _latest_datetime(values: list[datetime | None]) -> datetime | None:
        candidates = [value for value in values if value is not None]
        return max(candidates) if candidates else None

    @staticmethod
    def _non_empty_str(*values: object) -> str | None:
        for value in values:
            if not isinstance(value, str):
                continue
            candidate = value.strip()
            if candidate:
                return candidate
        return None


__all__ = ["SurfaceRewardService"]
