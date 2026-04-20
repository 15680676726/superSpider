# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.retrieval import RetrievalFacade
from copaw.retrieval.local_repo.exact_search import search_local_repo_exact
from copaw.retrieval.local_repo.index_models import CodeSymbolRecord, RepositoryIndexSnapshot
from copaw.retrieval.local_repo.semantic_search import search_local_repo_semantic
from copaw.retrieval.local_repo.symbol_search import search_local_repo_symbols


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_exact_search_finds_frontdoor_path() -> None:
    hits = search_local_repo_exact(
        workspace_root=REPO_ROOT,
        query="run_source_collection_frontdoor",
    )
    assert any("runtime_bootstrap_domains.py" in hit.ref for hit in hits)


def test_symbol_search_finds_runtime_center_serializer() -> None:
    hits = search_local_repo_symbols(
        workspace_root=REPO_ROOT,
        query="serialize_runtime_research_sources",
    )
    assert any("runtime_center_payloads.py" in hit.ref for hit in hits)


def test_repository_index_snapshot_and_symbol_record_keep_structural_fields() -> None:
    snapshot = RepositoryIndexSnapshot(
        workspace_root=str(REPO_ROOT),
        file_count=10,
        chunk_count=20,
        symbol_count=5,
    )
    symbol = CodeSymbolRecord(
        symbol_name="serialize_runtime_research_sources",
        symbol_kind="function",
        file_path="src/copaw/app/routers/runtime_center_payloads.py",
        line=1,
        container_name="module",
        language="python",
        signature="serialize_runtime_research_sources(...)",
    )
    assert snapshot.symbol_count == 5
    assert symbol.symbol_kind == "function"


def test_semantic_search_finds_runtime_center_research_surface_context() -> None:
    hits = search_local_repo_semantic(
        workspace_root=REPO_ROOT,
        query="runtime center research surface reads which formal truth fields",
    )

    assert any("runtime_center_payloads.py" in hit.ref for hit in hits)


def test_retrieval_facade_repo_trace_selects_runtime_center_payload_surface_file() -> None:
    run = RetrievalFacade(workspace_root=REPO_ROOT).retrieve(
        question="runtime center research surface reads which formal truth fields",
        goal="trace runtime center research payload",
        requested_sources=["local_repo"],
    )

    assert any("runtime_center_payloads.py" in hit.ref for hit in run.selected_hits)
    assert "runtime_center_payloads.py" in run.selected_hits[0].ref
