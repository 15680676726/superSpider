# -*- coding: utf-8 -*-
from __future__ import annotations

EXECUTION_CORE_AGENT_ID = "copaw-agent-runner"
EXECUTION_CORE_ROLE_ID = "execution-core"
EXECUTION_CORE_NAME = "Spider Mesh 执行中枢"
EXECUTION_CORE_LEGACY_NAMES = ("白泽执行中枢",)


def normalize_industry_role_id(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    return text


def is_execution_core_role_id(value: object | None) -> bool:
    return normalize_industry_role_id(value) == EXECUTION_CORE_ROLE_ID


def is_execution_core_agent_id(value: object | None) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    return text == EXECUTION_CORE_AGENT_ID


def is_execution_core_reference(value: object | None) -> bool:
    if is_execution_core_role_id(value) or is_execution_core_agent_id(value):
        return True
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    if text == EXECUTION_CORE_NAME or text in EXECUTION_CORE_LEGACY_NAMES:
        return True
    return text.lower() == "execution core"


def execution_core_role_aliases() -> tuple[str]:
    return (EXECUTION_CORE_ROLE_ID,)
