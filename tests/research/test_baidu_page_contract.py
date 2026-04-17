# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.research.baidu_page_contract import detect_login_state, extract_answer_contract


def test_baidu_page_contract_detects_logged_out_state() -> None:
    html = "<main><button>登录</button><button>立即登录</button></main>"

    result = detect_login_state(html)

    assert result.state == "login-required"
    assert "登录" in result.reason


def test_baidu_page_contract_does_not_mark_authenticated_home_as_login_required() -> None:
    body_text = """
    开启新对话
    知识库
    对话历史
    Your current account is not eligible for Antigravity. Try signing in with an
    内容由AI生成，仅供参考查看使用规则
    """

    result = detect_login_state(body_text)

    assert result.state == "ready"


def test_baidu_page_contract_extracts_answer_and_links() -> None:
    html = """
    <main>
      <div class="answer">
        紫微斗数核心术语包括命宫、身宫、主星与四化。
      </div>
      <a href="https://example.com/guide">参考资料</a>
      <a href="https://example.com/report.pdf">PDF 下载</a>
    </main>
    """

    result = extract_answer_contract(html)

    assert result.login_state == "ready"
    assert "命宫" in result.answer_text
    assert [item.url for item in result.links] == [
        "https://example.com/guide",
        "https://example.com/report.pdf",
    ]
    assert result.links[1].kind == "pdf"


def test_baidu_page_contract_filters_internal_navigation_links() -> None:
    html = """
    <main>
      <div class="answer">A stable answer.</div>
      <a href="//www.baidu.com/my/index">个人中心</a>
      <a href="//passport.baidu.com">账号设置</a>
      <a href="https://example.com/source">Source</a>
    </main>
    """

    result = extract_answer_contract(html)

    assert [item.url for item in result.links] == ["https://example.com/source"]


def test_baidu_page_contract_extracts_answer_from_body_text_snapshot() -> None:
    snapshot = {
        "html": "<main><a href='https://example.com/guide'>Guide</a></main>",
        "bodyText": """
        开启新对话
        知识库
        对话历史
        What is Zi Wei Dou Shu? Give 3 beginner points.
        全球搜检索32篇资料
        1.
        Guide - example.com

        Zi Wei Dou Shu is a traditional Chinese astrology system that maps stars across twelve palaces to interpret life patterns.
        Three beginner points:
        Learn the twelve palaces first.
        Study the main stars and four transformations.
        Use an accurate birth time.

        内容由AI生成，仅供参考查看使用规则
        """,
    }

    result = extract_answer_contract(snapshot)

    assert result.login_state == "ready"
    assert "traditional Chinese astrology system" in result.answer_text
    assert "Learn the twelve palaces first." in result.answer_text
    assert result.links[0].url == "https://example.com/guide"


def test_baidu_page_contract_normalizes_provider_result_for_chat_snapshot() -> None:
    snapshot = {
        "html": "<main><a href='https://example.com/guide'>Guide</a></main>",
        "bodyText": """
        What is Zi Wei Dou Shu?
        Zi Wei Dou Shu is a traditional Chinese astrology system that maps stars across twelve palaces.
        """,
        "href": "https://chat.baidu.com/search",
        "title": "Baidu Chat",
    }

    result = extract_answer_contract(snapshot)

    assert result.adapter_result is not None
    assert result.adapter_result.adapter_kind == "baidu_page"
    assert result.adapter_result.collection_action == "interact"
    assert result.adapter_result.status == "succeeded"
    assert result.adapter_result.summary.startswith("Zi Wei Dou Shu is")
    assert result.adapter_result.findings[0].summary.startswith("Zi Wei Dou Shu is")
    assert result.adapter_result.collected_sources[0].source_ref == "https://example.com/guide"
    assert result.adapter_result.collected_sources[0].source_kind == "link"


def test_baidu_page_contract_marks_login_required_as_blocked_adapter_result() -> None:
    snapshot = {
        "html": "<main><button>login</button></main>",
        "bodyText": "login required",
        "href": "https://chat.baidu.com/search",
    }

    result = extract_answer_contract(snapshot)

    assert result.adapter_result is not None
    assert result.adapter_result.status == "blocked"
    assert result.adapter_result.collection_action == "interact"
    assert result.adapter_result.metadata["login_state"] == "login-required"
