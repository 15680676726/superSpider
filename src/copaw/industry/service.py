# -*- coding: utf-8 -*-
from __future__ import annotations

from ..agents.skills_hub import HubSkillResult, search_hub_skills
from ..capabilities.remote_skill_catalog import (
    CuratedSkillCatalogEntry,
    search_curated_skill_catalog,
)
from .bootstrap_service import IndustryBootstrapService
from .service_context import *  # noqa: F401,F403
from .service_recommendation_search import (  # noqa: F401
    _build_skillhub_query_candidates,
    _role_capability_family_ids,
)
from .service_recommendation_pack import _standardize_recommendation_items  # noqa: F401
from .service_lifecycle import _IndustryLifecycleMixin
from .service_activation import _IndustryActivationMixin
from .service_team_runtime import _IndustryTeamRuntimeMixin
from .service_strategy import _IndustryStrategyMixin
from .service_runtime_views import _IndustryRuntimeViewsMixin
from .service_cleanup import _IndustryCleanupMixin
from .team_service import IndustryTeamService
from .view_service import IndustryViewService


class IndustryService(
    _IndustryLifecycleMixin,
    _IndustryActivationMixin,
    _IndustryTeamRuntimeMixin,
    _IndustryStrategyMixin,
    _IndustryRuntimeViewsMixin,
    _IndustryCleanupMixin,
):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._bootstrap_service = IndustryBootstrapService(self)
        self._team_service = IndustryTeamService(self)
        self._view_service = IndustryViewService(self)

    async def preview_v1(self, request):
        return await self._bootstrap_service.preview_v1(request)

    async def bootstrap_v1(self, request):
        return await self._bootstrap_service.bootstrap_v1(request)

    async def update_instance_team(
        self,
        instance_id: str,
        request,
        *,
        public_contract: bool = True,
    ):
        return await self._team_service.update_instance_team(
            instance_id,
            request,
            public_contract=public_contract,
        )

    def list_instances(
        self,
        *,
        status: str | None = "active",
        limit: int | None = None,
    ):
        return self._view_service.list_instances(status=status, limit=limit)

    def count_instances(self) -> int:
        return self._view_service.count_instances()

    def get_instance_record(self, instance_id: str):
        return self._view_service.get_instance_record(instance_id)

    def get_instance_detail(self, instance_id: str):
        return self._view_service.get_instance_detail(instance_id)

    def reconcile_instance_status(self, instance_id: str):
        return self._view_service.reconcile_instance_status(instance_id)

    def reconcile_instance_status_for_goal(self, goal_id: str) -> None:
        self._view_service.reconcile_instance_status_for_goal(goal_id)
