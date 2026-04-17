# -*- coding: utf-8 -*-
from __future__ import annotations

from .baidu_page_contract import detect_login_state, extract_answer_contract
from .baidu_page_research_service import BaiduPageResearchService
from .models import (
    BaiduAdapterResult,
    BaiduCollectedSource,
    BaiduPageContractResult,
    BaiduFinding,
    LoginStateResult,
    ResearchLink,
    ResearchSessionRunResult,
)

__all__ = [
    "BaiduAdapterResult",
    "BaiduCollectedSource",
    "BaiduPageContractResult",
    "BaiduPageResearchService",
    "BaiduFinding",
    "LoginStateResult",
    "ResearchLink",
    "ResearchSessionRunResult",
    "detect_login_state",
    "extract_answer_contract",
]
