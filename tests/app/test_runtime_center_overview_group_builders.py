# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from copaw.app.runtime_center.overview_groups import (
    RuntimeCenterControlCardsBuilder,
    RuntimeCenterLearningCardsBuilder,
    RuntimeCenterOperationsCardsBuilder,
)

from .runtime_center_api_parts.shared import (
    FakeAgentProfileService,
    FakeCapabilityService,
    FakeEvidenceQueryService,
    FakeGovernanceService,
    FakeIndustryService,
    FakeLearningService,
    FakePredictionService,
    FakeRoutineService,
    FakeStateQueryService,
    build_runtime_center_app,
)


def _build_runtime_state():
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    app.state.governance_service = FakeGovernanceService()
    app.state.routine_service = FakeRoutineService()
    app.state.prediction_service = FakePredictionService()
    app.state.query_execution_service = type(
        "_FakeQueryExecutionService",
        (),
        {"get_query_runtime_entropy_contract": staticmethod(lambda: None)},
    )()
    app.state.actor_worker_runtime_contract = {}
    app.state.actor_supervisor_runtime_contract = {}
    return app.state


def test_runtime_center_operations_cards_builder_groups_operator_cards():
    state = _build_runtime_state()
    builder = RuntimeCenterOperationsCardsBuilder(item_limit=5)

    cards = asyncio.run(builder.build_cards(state))

    assert [card.key for card in cards] == [
        "tasks",
        "work-contexts",
        "routines",
        "industry",
        "agents",
    ]


def test_runtime_center_control_cards_builder_groups_control_cards():
    state = _build_runtime_state()
    builder = RuntimeCenterControlCardsBuilder(item_limit=5)

    cards = asyncio.run(builder.build_cards(state))

    assert [card.key for card in cards] == [
        "predictions",
        "capabilities",
        "evidence",
        "governance",
        "decisions",
    ]


def test_runtime_center_learning_cards_builder_groups_learning_cards():
    state = _build_runtime_state()
    builder = RuntimeCenterLearningCardsBuilder(item_limit=5)

    cards = asyncio.run(builder.build_cards(state))

    assert [card.key for card in cards] == ["patches", "growth"]
