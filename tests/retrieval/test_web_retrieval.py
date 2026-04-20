# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.retrieval import RetrievalFacade


def test_facade_reads_direct_web_page_hit(monkeypatch) -> None:
    from copaw.retrieval.web import read as web_read_module

    monkeypatch.setattr(
        web_read_module,
        "summarize_html_page",
        lambda source_ref: {
            "url": source_ref,
            "title": "Runtime Center",
            "snippet": "Explains runtime center reads.",
            "summary": "Canonical runtime center overview.",
        },
    )

    run = RetrievalFacade(workspace_root=Path(__file__).resolve().parents[2]).retrieve(
        question="https://docs.example.com/runtime-center#overview",
        goal="read the runtime center overview",
        requested_sources=["web_page"],
    )

    assert run.selected_hits
    assert run.selected_hits[0].source_kind == "web_page"
    assert run.selected_hits[0].normalized_ref == "https://docs.example.com/runtime-center"


def test_facade_discovers_search_hits(monkeypatch) -> None:
    from copaw.retrieval.web import discover as web_discover_module

    monkeypatch.setattr(
        web_discover_module,
        "search_live_web",
        lambda query, limit=5: [
            {
                "title": "Official docs",
                "url": "https://docs.example.com/runtime-center",
                "snippet": f"query={query}; limit={limit}",
            }
        ],
    )

    run = RetrievalFacade(workspace_root=Path(__file__).resolve().parents[2]).retrieve(
        question="runtime center overview",
        goal="discover the official runtime center docs",
        requested_sources=["search"],
    )

    assert run.selected_hits
    assert run.selected_hits[0].source_kind == "search"
    assert run.selected_hits[0].metadata["rank"] == 1


def test_facade_prefers_web_page_metadata_url_over_natural_language_question(
    monkeypatch,
) -> None:
    from copaw.retrieval.web import read as web_read_module

    calls: list[str] = []

    def _fake_summarize(source_ref: str) -> dict[str, str]:
        calls.append(source_ref)
        return {
            "url": source_ref,
            "title": "Pricing",
            "snippet": "Base plan 299/month",
            "summary": "Base plan 299/month",
        }

    monkeypatch.setattr(web_read_module, "summarize_html_page", _fake_summarize)

    run = RetrievalFacade(workspace_root=Path(__file__).resolve().parents[2]).retrieve(
        question="官网定价是多少",
        goal="读取官网定价",
        requested_sources=["web_page"],
        metadata={
            "web_page": {
                "url": "https://example.com/pricing",
            }
        },
    )

    assert calls == ["https://example.com/pricing"]
    assert run.selected_hits
    assert run.selected_hits[0].normalized_ref == "https://example.com/pricing"


def test_facade_uses_web_page_metadata_payload_without_live_fetch(monkeypatch) -> None:
    from copaw.retrieval.web import read as web_read_module

    monkeypatch.setattr(
        web_read_module,
        "summarize_html_page",
        lambda source_ref: (_ for _ in ()).throw(
            AssertionError(f"should not live fetch {source_ref}")
        ),
    )

    run = RetrievalFacade(workspace_root=Path(__file__).resolve().parents[2]).retrieve(
        question="官网定价是多少",
        goal="读取官网定价",
        requested_sources=["web_page"],
        metadata={
            "web_page": {
                "url": "https://example.com/pricing",
                "title": "Pricing",
                "summary": "基础套餐 299 元 / 月",
            }
        },
    )

    assert run.selected_hits
    assert run.selected_hits[0].title == "Pricing"
    assert run.selected_hits[0].snippet == "基础套餐 299 元 / 月"
