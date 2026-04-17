# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib


def test_runtime_center_overview_routes_live_in_overview_module() -> None:
    module = importlib.import_module("copaw.app.routers.runtime_center_routes_overview")

    assert hasattr(module, "get_runtime_surface")
    assert hasattr(module, "stream_runtime_events")


def test_runtime_center_memory_routes_live_in_memory_module() -> None:
    module = importlib.import_module("copaw.app.routers.runtime_center_routes_memory")

    assert hasattr(module, "list_memory_profiles")
    assert hasattr(module, "list_memory_episodes")
    assert hasattr(module, "list_memory_history")
    assert hasattr(module, "recall_memory")
    assert hasattr(module, "reflect_memory_scope")


def test_runtime_center_knowledge_routes_live_in_knowledge_module() -> None:
    module = importlib.import_module("copaw.app.routers.runtime_center_routes_knowledge")

    assert hasattr(module, "list_knowledge_documents")
    assert hasattr(module, "import_knowledge_document")
    assert hasattr(module, "delete_knowledge_chunk")


def test_runtime_center_reports_routes_live_in_reports_module() -> None:
    module = importlib.import_module("copaw.app.routers.runtime_center_routes_reports")

    assert hasattr(module, "list_runtime_reports")
    assert hasattr(module, "get_runtime_performance_overview")
    assert hasattr(module, "list_strategy_memory")


def test_runtime_center_research_routes_live_in_research_module() -> None:
    module = importlib.import_module("copaw.app.routers.runtime_center_routes_research")

    assert hasattr(module, "get_runtime_research")


def test_runtime_center_industry_routes_live_in_industry_module() -> None:
    module = importlib.import_module("copaw.app.routers.runtime_center_routes_industry")

    assert hasattr(module, "list_industry_instances")
    assert hasattr(module, "get_industry_instance_detail")


def test_runtime_center_facade_imports_domain_route_modules() -> None:
    module = importlib.import_module("copaw.app.routers.runtime_center")

    assert hasattr(module, "_runtime_center_routes_overview")
    assert hasattr(module, "_runtime_center_routes_memory")
    assert hasattr(module, "_runtime_center_routes_knowledge")
    assert hasattr(module, "_runtime_center_routes_reports")
    assert hasattr(module, "_runtime_center_routes_research")
    assert hasattr(module, "_runtime_center_routes_industry")


def test_runtime_center_facade_registers_research_route_on_shared_router() -> None:
    module = importlib.import_module("copaw.app.routers.runtime_center")

    matching_routes = [
        route
        for route in module.router.routes
        if getattr(route, "path", None) == "/runtime-center/research"
    ]

    assert len(matching_routes) == 1
    assert matching_routes[0].endpoint.__module__ == (
        "copaw.app.routers.runtime_center_routes_research"
    )
