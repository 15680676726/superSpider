# -*- coding: utf-8 -*-
"""AI daily-report generation for the Runtime Center human cockpit."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from ...providers.runtime_model_call import (
    RuntimeModelCallError,
    RuntimeModelCallPolicy,
    RuntimeModelCallService,
)
from .models import (
    RuntimeHumanCockpitModelStatus,
    RuntimeHumanCockpitReportBlock,
    RuntimeHumanCockpitReportError,
    RuntimeHumanCockpitReportSection,
)

ReportKind = Literal["morning", "evening"]

_REPORT_TITLES: dict[ReportKind, str] = {
    "morning": "早报",
    "evening": "晚报",
}

_MORNING_SECTION_LABELS: tuple[tuple[str, str], ...] = (
    ("what_today", "今天要做什么"),
    ("priority_first", "重点先做什么"),
    ("risk_note", "风险提醒"),
)

_EVENING_SECTION_LABELS: tuple[tuple[str, str], ...] = (
    ("done_today", "今天完成了什么"),
    ("produced_result", "产出了什么结果"),
    ("next_step", "明天继续什么"),
)


class _MorningReportSchema(BaseModel):
    what_today: str
    priority_first: str
    risk_note: str


class _EveningReportSchema(BaseModel):
    done_today: str
    produced_result: str
    next_step: str


class RuntimeDailyReportGenerationService:
    """Generates structured Chinese morning/evening reports via the shared runtime model."""

    def __init__(
        self,
        *,
        model_call_service: RuntimeModelCallService | None,
    ) -> None:
        self._model_call_service = model_call_service

    def snapshot_model_status(self) -> RuntimeHumanCockpitModelStatus:
        if self._model_call_service is None:
            return RuntimeHumanCockpitModelStatus(
                level="error",
                code="MODEL_UPSTREAM_ERROR",
                message="日报生成失败：当前没有可用的模型调用服务。",
            )
        health = self._model_call_service.health_tracker.snapshot()
        return RuntimeHumanCockpitModelStatus(
            level=health.level,
            code=health.code,
            message=health.message,
            consecutive_failures=health.consecutive_failures,
            last_success_at=_isoformat(health.last_success_at),
            last_failure_at=_isoformat(health.last_failure_at),
        )

    async def generate_report(
        self,
        *,
        report_kind: ReportKind,
        facts: dict[str, Any],
        generated_at: str | None = None,
    ) -> RuntimeHumanCockpitReportBlock:
        title = _REPORT_TITLES[report_kind]
        if self._model_call_service is None:
            return self._error_block(
                report_kind=report_kind,
                title=title,
                code="MODEL_UPSTREAM_ERROR",
                message="日报生成失败：当前没有可用的模型调用服务。",
                generated_at=generated_at,
            )
        schema: type[BaseModel]
        if report_kind == "morning":
            schema = _MorningReportSchema
        else:
            schema = _EveningReportSchema
        try:
            payload = await self._model_call_service.invoke_structured(
                messages=self._build_messages(report_kind=report_kind, facts=facts),
                policy=RuntimeModelCallPolicy(
                    timeout_seconds=120,
                    max_retries=3,
                    require_chinese=True,
                    structured_schema=schema,
                ),
                feature=f"runtime_daily_report_{report_kind}",
            )
        except RuntimeModelCallError as exc:
            return self._error_block(
                report_kind=report_kind,
                title=title,
                code=exc.code,
                message=str(exc),
                generated_at=generated_at,
            )
        return RuntimeHumanCockpitReportBlock(
            kind=report_kind,
            title=title,
            status="ready",
            sections=self._build_sections(report_kind=report_kind, payload=payload),
            generated_at=generated_at,
            error=None,
        )

    def _build_messages(
        self,
        *,
        report_kind: ReportKind,
        facts: dict[str, Any],
    ) -> list[dict[str, str]]:
        slot_descriptions = (
            "今天要做什么、重点先做什么、风险提醒"
            if report_kind == "morning"
            else "今天完成了什么、产出了什么结果、明天继续什么"
        )
        return [
            {
                "role": "system",
                "content": (
                    "你是 Runtime Center 的日报生成器。"
                    "只输出全中文。"
                    "必须返回结构化结果。"
                    f"当前要生成{_REPORT_TITLES[report_kind]}，固定槽位为：{slot_descriptions}。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "report_kind": report_kind,
                        "facts": {
                            key: self._normalize_fact_text(value)
                            for key, value in facts.items()
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        ]

    def _build_sections(
        self,
        *,
        report_kind: ReportKind,
        payload: BaseModel,
    ) -> list[RuntimeHumanCockpitReportSection]:
        labels = (
            _MORNING_SECTION_LABELS
            if report_kind == "morning"
            else _EVENING_SECTION_LABELS
        )
        content = payload.model_dump(mode="python")
        return [
            RuntimeHumanCockpitReportSection(
                key=key,
                label=label,
                content=self._normalize_fact_text(content.get(key)),
            )
            for key, label in labels
        ]

    def _error_block(
        self,
        *,
        report_kind: ReportKind,
        title: str,
        code: str,
        message: str,
        generated_at: str | None,
    ) -> RuntimeHumanCockpitReportBlock:
        return RuntimeHumanCockpitReportBlock(
            kind=report_kind,
            title=title,
            status="error",
            sections=[],
            generated_at=generated_at,
            error=RuntimeHumanCockpitReportError(
                code=code,
                message=message,
            ),
        )

    @staticmethod
    def _normalize_fact_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


__all__ = ["RuntimeDailyReportGenerationService"]
