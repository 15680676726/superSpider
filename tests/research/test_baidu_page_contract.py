# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.research.baidu_page_contract import detect_login_state, extract_answer_contract


def test_baidu_page_contract_detects_logged_out_state() -> None:
    html = "<main><button>登录</button><button>立即登录</button></main>"

    result = detect_login_state(html)

    assert result.state == "login-required"
    assert "登录" in result.reason


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
