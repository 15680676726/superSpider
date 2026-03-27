# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "copaw"

STRATEGY_CONSUMER_MODULES = (
    SRC_ROOT / "goals" / "service_compiler.py",
    SRC_ROOT / "workflows" / "service_context.py",
    SRC_ROOT / "predictions" / "service_context.py",
    SRC_ROOT / "kernel" / "query_execution_prompt.py",
)

ALLOWED_DIRECT_STRATEGY_READERS = {
    SRC_ROOT / "state" / "strategy_memory_service.py",
    SRC_ROOT / "industry" / "service.py",
}


def _parse_module(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def _calls_named_function(tree: ast.AST, function_name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == function_name:
            return True
    return False


def _calls_attribute(tree: ast.AST, attribute_name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr == attribute_name:
            return True
    return False


def _repo_relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def test_strategy_consumers_must_use_shared_strategy_resolver() -> None:
    missing_resolver: list[str] = []
    direct_strategy_reads: list[str] = []

    for path in STRATEGY_CONSUMER_MODULES:
        tree = _parse_module(path)
        if not _calls_named_function(tree, "resolve_strategy_payload"):
            missing_resolver.append(_repo_relative(path))
        if _calls_attribute(tree, "get_active_strategy"):
            direct_strategy_reads.append(_repo_relative(path))

    assert not missing_resolver, (
        "Strategic consumers must resolve strategy memory via "
        "state.strategy_memory_service.resolve_strategy_payload(): "
        + ", ".join(missing_resolver)
    )
    assert not direct_strategy_reads, (
        "Strategic consumers must not directly call get_active_strategy(); "
        "producer-side sync is the only allowed exception: "
        + ", ".join(direct_strategy_reads)
    )


def test_direct_get_active_strategy_calls_are_restricted_to_producer_side_modules() -> None:
    violations: list[str] = []

    for path in SRC_ROOT.rglob("*.py"):
        if path in ALLOWED_DIRECT_STRATEGY_READERS:
            continue
        tree = _parse_module(path)
        if _calls_attribute(tree, "get_active_strategy"):
            violations.append(_repo_relative(path))

    assert not violations, (
        "Direct get_active_strategy() calls are reserved for strategy producer/service "
        "boundaries. Route consumer reads through resolve_strategy_payload(): "
        + ", ".join(sorted(violations))
    )
