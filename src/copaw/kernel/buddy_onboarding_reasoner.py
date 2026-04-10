# -*- coding: utf-8 -*-
"""Contract compiler for Buddy onboarding."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Callable, Protocol

from pydantic import BaseModel, Field

from ..providers.runtime_provider_facade import (
    ProviderRuntimeSurface,
    build_compat_runtime_provider_facade,
)
from ..state import HumanProfile

logger = logging.getLogger(__name__)
_DEFAULT_REASONING_TIMEOUT_SECONDS = 45.0

_BUDDY_ONBOARDING_REASONER_PROMPT = """
你负责 CoPaw Buddy onboarding 的协作合同编译。
你的职责不是继续追问，而是读取用户的人物资料和已经确认的协作合同，
直接编译出：
1. 候选主方向
2. 推荐主方向
3. 最终目标
4. 为什么重要
5. 首批可执行 backlog

你必须只返回一个 JSON 对象，字段名必须严格使用下面这些名字：
{
  "candidate_directions": string[],
  "recommended_direction": string,
  "final_goal": string,
  "why_it_matters": string,
  "backlog_items": [
    {
      "lane_hint": string,
      "title": string,
      "summary": string,
      "priority": 1|2|3,
      "source_key": string
    }
  ]
}

硬规则：
- 不要返回 next_question、finished、question_count、transcript 等采访语义字段。
- 必须把 collaboration contract 当作正式输入，不要忽略 service_intent / collaboration_role /
  autonomy_level / confirm_boundaries / report_style / collaboration_notes。
- candidate_directions 至少给 1 个。
- recommended_direction 必须非空，并且应包含在 candidate_directions 里。
- final_goal 必须具体，不要空泛人生鸡汤。
- backlog_items 至少给 1 个，且每个 item 都必须给非空 lane_hint。
- lane_hint 要用简洁、稳定的 lane id，例如 market-research、platform-publishing、
  customer-acquisition、execution-evidence、growth-focus、proof-of-work。
- priority 只能是 1 到 3，3 最高。
- 不能因为用户提到“赚钱 / 收入 / 财富自由”就强行改写成内容创作。
- 如果用户明确说的是股票、交易、投资、仓位、回撤、策略、复盘，就保留在交易 / 投资方向。
""".strip()


class BuddyOnboardingBacklogSeed(BaseModel):
    lane_hint: str = ""
    title: str = ""
    summary: str = ""
    priority: int = Field(default=1, ge=1, le=3)
    source_key: str = ""


class BuddyCollaborationContract(BaseModel):
    service_intent: str = ""
    collaboration_role: str = "orchestrator"
    autonomy_level: str = "proactive"
    confirm_boundaries: list[str] = Field(default_factory=list)
    report_style: str = "result-first"
    collaboration_notes: str = ""


class BuddyOnboardingContractCompileResult(BaseModel):
    candidate_directions: list[str] = Field(default_factory=list)
    recommended_direction: str = ""
    final_goal: str = ""
    why_it_matters: str = ""
    backlog_items: list[BuddyOnboardingBacklogSeed] = Field(default_factory=list)


class BuddyOnboardingReasoner(Protocol):
    def compile_contract(
        self,
        *,
        profile: HumanProfile,
        collaboration_contract: BuddyCollaborationContract,
    ) -> BuddyOnboardingContractCompileResult | None: ...


class _ReasonerResponse(BaseModel):
    candidate_directions: list[str] = Field(default_factory=list)
    recommended_direction: str = ""
    final_goal: str = ""
    why_it_matters: str = ""
    backlog_items: list[BuddyOnboardingBacklogSeed] = Field(default_factory=list)


class BuddyOnboardingReasonerTimeoutError(TimeoutError):
    """Raised when Buddy onboarding waits too long for the active chat model."""


class BuddyOnboardingReasonerUnavailableError(RuntimeError):
    """Raised when Buddy onboarding cannot get a valid AI result."""


def _response_to_text(response: object) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
            else:
                text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _response_to_payload(response: object) -> dict[str, Any]:
    metadata = getattr(response, "metadata", None)
    if isinstance(metadata, BaseModel):
        return metadata.model_dump(mode="json")
    if isinstance(metadata, dict):
        return dict(metadata)
    text = _response_to_text(response)
    if not text:
        raise ValueError("Buddy onboarding reasoner returned an empty response.")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Buddy onboarding reasoner returned a non-object payload.")
    return payload


def _normalize_reasoner_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    recommended_direction = str(
        normalized.get("recommended_direction")
        or normalized.get("real_main_direction")
        or normalized.get("primary_direction")
        or normalized.get("direction")
        or ""
    ).strip()
    if recommended_direction:
        normalized["recommended_direction"] = recommended_direction
    candidate_directions = normalized.get("candidate_directions")
    if not isinstance(candidate_directions, list):
        candidate_directions = normalized.get("direction_candidates")
    if not isinstance(candidate_directions, list):
        candidate_directions = []
    if not candidate_directions and recommended_direction:
        candidate_directions = [recommended_direction]
    normalized["candidate_directions"] = candidate_directions
    why_it_matters = str(
        normalized.get("why_it_matters")
        or normalized.get("why")
        or normalized.get("reason")
        or ""
    ).strip()
    if why_it_matters:
        normalized["why_it_matters"] = why_it_matters
    backlog_items = normalized.get("backlog_items")
    if not isinstance(backlog_items, list):
        backlog_items = normalized.get("backlog")
    if not isinstance(backlog_items, list):
        backlog_items = []
    normalized["backlog_items"] = backlog_items
    return normalized


async def _materialize_response(response: object) -> object:
    if not hasattr(response, "__aiter__"):
        return response
    last_item: object | None = None
    async for item in response:  # type: ignore[misc]
        last_item = item
    return last_item if last_item is not None else response


def _run_async_blocking(
    awaitable: object,
    *,
    timeout_seconds: float | None = None,
) -> object:
    async def _coerce() -> object:
        return await awaitable  # type: ignore[misc]

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_coerce())

    result: dict[str, object] = {}
    error: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(_coerce())
        except BaseException as exc:  # pragma: no cover - passthrough
            error["value"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        raise BuddyOnboardingReasonerTimeoutError(
            f"Buddy onboarding model timed out after {timeout_seconds:g} seconds.",
        )
    if "value" in error:
        raise error["value"]
    return result.get("value")


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        lowered = text.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


class ModelDrivenBuddyOnboardingReasoner:
    """Use the active runtime model to compile a Buddy collaboration contract."""

    def __init__(
        self,
        *,
        model_factory: Callable[[], object] | None = None,
        provider_runtime: ProviderRuntimeSurface | None = None,
        reasoning_timeout_seconds: float = _DEFAULT_REASONING_TIMEOUT_SECONDS,
    ) -> None:
        resolved_runtime = (
            provider_runtime
            if provider_runtime is not None and hasattr(provider_runtime, "get_active_chat_model")
            else None
        )
        self._provider_runtime = resolved_runtime or build_compat_runtime_provider_facade()
        self._model_factory = model_factory or self._provider_runtime.get_active_chat_model
        self._reasoning_timeout_seconds = max(1.0, float(reasoning_timeout_seconds))

    def compile_contract(
        self,
        *,
        profile: HumanProfile,
        collaboration_contract: BuddyCollaborationContract,
    ) -> BuddyOnboardingContractCompileResult | None:
        try:
            model = self._model_factory()
        except Exception:
            logger.debug("Buddy onboarding compiler could not resolve an active chat model.", exc_info=True)
            raise BuddyOnboardingReasonerUnavailableError(
                "Buddy onboarding model is not available.",
            ) from None
        request_payload = {
            "profile": profile.model_dump(mode="json"),
            "collaboration_contract": collaboration_contract.model_dump(mode="json"),
        }
        messages = [
            {"role": "system", "content": _BUDDY_ONBOARDING_REASONER_PROMPT},
            {
                "role": "user",
                "content": (
                    "请根据下面的 Buddy onboarding 协作合同上下文，返回结构化 JSON。\n\n"
                    f"{json.dumps(request_payload, ensure_ascii=False, indent=2)}"
                ),
            },
        ]
        try:
            response = _run_async_blocking(
                model(messages=messages, structured_model=_ReasonerResponse),
                timeout_seconds=self._reasoning_timeout_seconds,
            )
            response = _run_async_blocking(
                _materialize_response(response),
                timeout_seconds=self._reasoning_timeout_seconds,
            )
            payload = _ReasonerResponse.model_validate(
                _normalize_reasoner_payload(_response_to_payload(response)),
            )
        except BuddyOnboardingReasonerTimeoutError:
            logger.warning("Buddy onboarding contract compiler timed out.", exc_info=True)
            raise
        except Exception:
            logger.warning("Buddy onboarding contract compiler failed.", exc_info=True)
            raise BuddyOnboardingReasonerUnavailableError(
                "Buddy onboarding model failed to return a valid result.",
            ) from None
        directions = _unique(payload.candidate_directions)
        recommended = str(payload.recommended_direction or "").strip()
        if recommended and recommended not in directions:
            directions = [recommended, *directions]
        final_goal = str(payload.final_goal or "").strip()
        why_it_matters = str(payload.why_it_matters or "").strip()
        backlog_items = [
            item
            for item in payload.backlog_items
            if item.lane_hint.strip() and item.title.strip() and item.summary.strip()
        ][:3]
        if not recommended or not final_goal or not why_it_matters or not backlog_items:
            raise BuddyOnboardingReasonerUnavailableError(
                "Buddy onboarding model failed to return a valid result.",
            )
        return BuddyOnboardingContractCompileResult(
            candidate_directions=directions[:3],
            recommended_direction=recommended,
            final_goal=final_goal,
            why_it_matters=why_it_matters,
            backlog_items=backlog_items,
        )


__all__ = [
    "BuddyCollaborationContract",
    "BuddyOnboardingBacklogSeed",
    "BuddyOnboardingContractCompileResult",
    "BuddyOnboardingReasoner",
    "BuddyOnboardingReasonerTimeoutError",
    "BuddyOnboardingReasonerUnavailableError",
    "ModelDrivenBuddyOnboardingReasoner",
]
