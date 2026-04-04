# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from .models import (
    DiscoveryActionRequest,
    DiscoveryHit,
    OpportunityRadarItem,
    ScoutRequest,
    ScoutRunResult,
)
from .source_chain import execute_discovery_action


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class DonorScoutService:
    def __init__(
        self,
        *,
        source_service: object,
        candidate_service: object,
        opportunity_radar_service: object | None = None,
        discovery_executor: Callable[[object, DiscoveryActionRequest], Iterable[DiscoveryHit]],
    ) -> None:
        self._source_service = source_service
        self._candidate_service = candidate_service
        self._opportunity_radar_service = opportunity_radar_service
        self._discovery_executor = discovery_executor
        self._latest_run: ScoutRunResult | None = None

    def get_latest_summary(self) -> dict[str, Any]:
        run = self._latest_run
        if run is None:
            return {
                "status": "idle",
                "last_mode": None,
                "imported_candidate_count": 0,
                "attempted_queries": [],
            }
        return {
            "status": run.status,
            "last_mode": run.mode,
            "imported_candidate_count": run.imported_candidate_count,
            "attempted_queries": list(run.attempted_queries),
            **dict(run.metadata),
        }

    def run_scout(
        self,
        *,
        request: ScoutRequest,
    ) -> ScoutRunResult:
        radar_items = self._collect_radar_items(request)
        attempted_queries = self._resolve_queries(request=request, radar_items=radar_items)
        imported_candidate_ids: list[str] = []
        source_run_count = 0
        remaining_budget = max(1, int(request.budget.max_candidates))
        importer = getattr(self._candidate_service, "import_discovery_hits", None)

        for index, query in enumerate(attempted_queries[: max(1, int(request.budget.max_queries))]):
            discovery_request = DiscoveryActionRequest(
                action_id=f"{request.scout_id}:{index}",
                query=query,
                source_profile=request.source_profile,
                discovery_mode=request.mode,
                limit=remaining_budget,
                metadata=dict(request.metadata),
            )
            result = execute_discovery_action(
                request=discovery_request,
                source_service=self._source_service,
                executor=self._discovery_executor,
            )
            source_run_count += 1
            if not callable(importer):
                continue
            discovery_hits = list(result.discovery_hits or [])[:remaining_budget]
            if not discovery_hits:
                continue
            imported = importer(
                discovery_hits=discovery_hits,
                target_scope=request.target_scope,
                target_role_id=request.target_role_id,
                target_seat_ref=request.target_seat_ref,
                industry_instance_id=request.industry_instance_id,
                ingestion_mode=f"scout:{request.mode}",
                status="candidate",
                lifecycle_stage="candidate",
            )
            imported_candidate_ids.extend(
                candidate_id
                for item in list(imported or [])
                if (candidate_id := _string(getattr(item, "candidate_id", None))) is not None
            )
            remaining_budget = max(0, remaining_budget - len(imported))
            if remaining_budget <= 0:
                break

        status = "ready" if imported_candidate_ids else "idle"
        result = ScoutRunResult(
            scout_id=request.scout_id,
            mode=request.mode,
            status=status,
            attempted_queries=tuple(attempted_queries[: max(1, int(request.budget.max_queries))]),
            source_run_count=source_run_count,
            radar_item_count=len(radar_items),
            imported_candidate_ids=tuple(imported_candidate_ids),
            metadata={
                "source_profile": request.source_profile,
                "target_scope": request.target_scope,
            },
        )
        self._latest_run = result
        return result

    def _collect_radar_items(self, request: ScoutRequest) -> list[OpportunityRadarItem]:
        if request.mode != "opportunity":
            return []
        collector = getattr(self._opportunity_radar_service, "collect", None)
        if not callable(collector):
            return []
        return list(collector(limit=max(1, int(request.budget.max_queries))) or [])

    def _resolve_queries(
        self,
        *,
        request: ScoutRequest,
        radar_items: list[OpportunityRadarItem],
    ) -> list[str]:
        queries: list[str] = []
        if request.mode == "opportunity":
            for item in radar_items:
                query = _string(item.query_hint) or _string(item.title)
                if query is not None and query not in queries:
                    queries.append(query)
        else:
            seed_values = [request.query, *list(request.queries)]
            for value in seed_values:
                query = _string(value)
                if query is not None and query not in queries:
                    queries.append(query)
        return queries


__all__ = ["DonorScoutService"]
