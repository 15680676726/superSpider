# -*- coding: utf-8 -*-
from __future__ import annotations

from .baidu_page_contract import detect_login_state, extract_answer_contract
from .baidu_page_research_service import BaiduPageResearchService
from .models import (
    BaiduPageContractResult,
    LoginStateResult,
    ResearchLink,
    ResearchSessionRunResult,
)

__all__ = [
    "BaiduPageContractResult",
    "BaiduPageResearchService",
    "LoginStateResult",
    "ResearchLink",
    "ResearchSessionRunResult",
    "detect_login_state",
    "extract_answer_contract",
]
