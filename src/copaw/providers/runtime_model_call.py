# -*- coding: utf-8 -*-
"""Unified runtime model call policy, validation, and health tracking."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable, Literal

from pydantic import BaseModel, ValidationError

from ..utils.model_response import materialize_model_response
from .model_diagnostics import classify_model_exception

_ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
_SYSTEM_FAILURE_THRESHOLD = 3
_SYSTEM_FAILURE_WINDOW = timedelta(minutes=15)


@dataclass(slots=True)
class RuntimeModelCallPolicy:
    timeout_seconds: float = 120
    max_retries: int = 3
    require_chinese: bool = False
    structured_schema: type[BaseModel] | None = None


@dataclass(slots=True)
class RuntimeModelHealthStatus:
    level: Literal["ok", "error"] = "ok"
    code: str | None = None
    message: str | None = None
    consecutive_failures: int = 0
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None


@dataclass(slots=True)
class RuntimeModelCallRecord:
    feature: str
    success: bool
    attempt_count: int
    error_code: str | None = None
    require_chinese: bool = False
    structured: bool = False
    system_level: bool = False
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RuntimeModelCallError(RuntimeError):
    """Structured runtime-model call failure."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        system_level: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.system_level = system_level
        self.details = details or {}


class RuntimeModelHealthTracker:
    """Tracks whether runtime model failures have escalated to system-level."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        failure_threshold: int = _SYSTEM_FAILURE_THRESHOLD,
        failure_window: timedelta = _SYSTEM_FAILURE_WINDOW,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._failure_threshold = max(1, int(failure_threshold))
        self._failure_window = max(timedelta(seconds=1), failure_window)
        self._consecutive_failures = 0
        self._last_success_at: datetime | None = None
        self._last_failure_at: datetime | None = None
        self._last_error_code: str | None = None

    def record_success(self, *, at: datetime | None = None) -> RuntimeModelHealthStatus:
        now = at or self._clock()
        self._consecutive_failures = 0
        self._last_success_at = now
        self._last_error_code = None
        return self.snapshot(at=now)

    def record_failure(
        self,
        *,
        error_code: str,
        at: datetime | None = None,
    ) -> RuntimeModelHealthStatus:
        now = at or self._clock()
        self._consecutive_failures += 1
        self._last_failure_at = now
        self._last_error_code = error_code
        return self.snapshot(at=now)

    def snapshot(self, *, at: datetime | None = None) -> RuntimeModelHealthStatus:
        now = at or self._clock()
        if self._is_system_unavailable(now):
            return RuntimeModelHealthStatus(
                level="error",
                code="MODEL_SYSTEM_UNAVAILABLE",
                message="全局模型调用持续失败，请先恢复模型服务。",
                consecutive_failures=self._consecutive_failures,
                last_success_at=self._last_success_at,
                last_failure_at=self._last_failure_at,
            )
        return RuntimeModelHealthStatus(
            level="ok",
            code=None,
            message=None,
            consecutive_failures=self._consecutive_failures,
            last_success_at=self._last_success_at,
            last_failure_at=self._last_failure_at,
        )

    def _is_system_unavailable(self, now: datetime) -> bool:
        if self._consecutive_failures < self._failure_threshold:
            return False
        if self._last_success_at is None:
            return True
        return now - self._last_success_at >= self._failure_window


class RuntimeModelCallService:
    """Shared runtime model caller with retries, validation, and health tracking."""

    def __init__(
        self,
        *,
        model_factory: Callable[[], object] | None = None,
        health_tracker: RuntimeModelHealthTracker | None = None,
        event_sink: Callable[[RuntimeModelCallRecord], None] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._model_factory = model_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._health_tracker = health_tracker or RuntimeModelHealthTracker(
            clock=self._clock
        )
        self._event_sink = event_sink

    @property
    def health_tracker(self) -> RuntimeModelHealthTracker:
        return self._health_tracker

    async def invoke_structured(
        self,
        *,
        messages: list[dict[str, Any]],
        policy: RuntimeModelCallPolicy,
        feature: str,
        model: object | None = None,
        model_kwargs: dict[str, Any] | None = None,
    ) -> BaseModel:
        schema = policy.structured_schema
        if schema is None:
            raise ValueError("Structured runtime model call requires a schema.")
        kwargs = dict(model_kwargs or {})
        return await self._invoke_with_policy(
            messages=messages,
            policy=policy,
            feature=feature,
            model=model,
            structured_model=schema,
            model_kwargs=kwargs,
        )

    async def invoke_text(
        self,
        *,
        messages: list[dict[str, Any]],
        policy: RuntimeModelCallPolicy,
        feature: str,
        model: object | None = None,
        model_kwargs: dict[str, Any] | None = None,
    ) -> object:
        kwargs = dict(model_kwargs or {})
        return await self._invoke_with_policy(
            messages=messages,
            policy=policy,
            feature=feature,
            model=model,
            structured_model=None,
            model_kwargs=kwargs,
        )

    async def _invoke_with_policy(
        self,
        *,
        messages: list[dict[str, Any]],
        policy: RuntimeModelCallPolicy,
        feature: str,
        model: object | None,
        structured_model: type[BaseModel] | None,
        model_kwargs: dict[str, Any],
    ) -> object:
        resolved_model = model if model is not None else self._resolve_model()
        attempts = max(1, int(policy.max_retries))
        timeout_seconds = max(0.001, float(policy.timeout_seconds))
        last_error: RuntimeModelCallError | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await asyncio.wait_for(
                    resolved_model(
                        messages=messages,
                        structured_model=structured_model,
                        **model_kwargs,
                    ),
                    timeout=timeout_seconds,
                )
                response = await asyncio.wait_for(
                    materialize_model_response(response),
                    timeout=timeout_seconds,
                )
                if structured_model is None:
                    if policy.require_chinese:
                        _ensure_chinese_output(_response_to_text(response))
                    self._record_success(
                        feature=feature,
                        attempt_count=attempt,
                        require_chinese=policy.require_chinese,
                        structured=False,
                    )
                    return response
                payload = _response_to_payload(response)
                validated = structured_model.model_validate(payload)
                if policy.require_chinese:
                    _ensure_chinese_output(validated.model_dump(mode="python"))
                self._record_success(
                    feature=feature,
                    attempt_count=attempt,
                    require_chinese=policy.require_chinese,
                    structured=True,
                )
                return validated
            except Exception as exc:  # pragma: no cover
                last_error = _coerce_runtime_model_call_error(exc)
                if attempt < attempts:
                    continue
        assert last_error is not None
        health = self._health_tracker.record_failure(error_code=last_error.code)
        system_level = health.level == "error"
        final_error = (
            RuntimeModelCallError(
                code="MODEL_SYSTEM_UNAVAILABLE",
                message=health.message or "全局模型调用持续失败，请先恢复模型服务。",
                system_level=True,
                details={
                    "feature": feature,
                    "attempt_count": attempts,
                    "last_error_code": last_error.code,
                },
            )
            if system_level
            else RuntimeModelCallError(
                code=last_error.code,
                message=str(last_error),
                system_level=False,
                details={
                    "feature": feature,
                    "attempt_count": attempts,
                },
            )
        )
        self._record_event(
            RuntimeModelCallRecord(
                feature=feature,
                success=False,
                attempt_count=attempts,
                error_code=final_error.code,
                require_chinese=policy.require_chinese,
                structured=structured_model is not None,
                system_level=final_error.system_level,
                created_at=self._clock(),
            )
        )
        raise final_error

    def _resolve_model(self) -> object:
        if self._model_factory is None:
            raise RuntimeModelCallError(
                code="MODEL_UPSTREAM_ERROR",
                message="运行时模型调用缺少可用的模型工厂。",
            )
        try:
            model = self._model_factory()
        except RuntimeModelCallError:
            raise
        except Exception as exc:
            detail = str(exc).strip() or "运行时模型工厂未返回可用模型。"
            raise RuntimeModelCallError(
                code="MODEL_UPSTREAM_ERROR",
                message=detail,
            ) from exc
        if model is None:
            raise RuntimeModelCallError(
                code="MODEL_UPSTREAM_ERROR",
                message="运行时模型工厂未返回可用模型。",
            )
        return model

    def _record_success(
        self,
        *,
        feature: str,
        attempt_count: int,
        require_chinese: bool,
        structured: bool,
    ) -> None:
        self._health_tracker.record_success()
        self._record_event(
            RuntimeModelCallRecord(
                feature=feature,
                success=True,
                attempt_count=attempt_count,
                require_chinese=require_chinese,
                structured=structured,
                created_at=self._clock(),
            )
        )

    def _record_event(self, record: RuntimeModelCallRecord) -> None:
        if self._event_sink is not None:
            self._event_sink(record)


class InstrumentedRuntimeChatModel:
    """Callable wrapper that routes runtime model calls through the shared policy."""

    def __init__(
        self,
        *,
        wrapped_model: object,
        call_service: RuntimeModelCallService,
        feature: str = "runtime_chat",
    ) -> None:
        self._wrapped_model = wrapped_model
        self._call_service = call_service
        self._feature = feature
        self.stream = getattr(wrapped_model, "stream", None)

    async def __call__(
        self,
        *,
        messages,
        structured_model=None,
        **kwargs,
    ):
        if isinstance(structured_model, type) and issubclass(structured_model, BaseModel):
            payload = await self._call_service.invoke_structured(
                messages=messages,
                policy=RuntimeModelCallPolicy(structured_schema=structured_model),
                feature=self._feature,
                model=self._wrapped_model,
                model_kwargs=kwargs,
            )
            return SimpleNamespace(metadata=payload.model_dump(mode="json"), content="")
        return await self._call_service.invoke_text(
            messages=messages,
            policy=RuntimeModelCallPolicy(),
            feature=self._feature,
            model=self._wrapped_model,
            model_kwargs=kwargs,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped_model, name)


def build_instrumented_chat_model(
    wrapped_model: object,
    *,
    call_service: RuntimeModelCallService,
    feature: str = "runtime_chat",
) -> InstrumentedRuntimeChatModel:
    return InstrumentedRuntimeChatModel(
        wrapped_model=wrapped_model,
        call_service=call_service,
        feature=feature,
    )


def _coerce_runtime_model_call_error(exc: Exception) -> RuntimeModelCallError:
    if isinstance(exc, RuntimeModelCallError):
        return exc
    if isinstance(exc, asyncio.TimeoutError) or isinstance(exc, TimeoutError):
        return RuntimeModelCallError(
            code="MODEL_TIMEOUT",
            message="模型在规定时间内未返回有效结果。",
        )
    if isinstance(exc, ValidationError):
        return RuntimeModelCallError(
            code="MODEL_STRUCTURED_VALIDATION_FAILED",
            message="模型返回的结构化结果不合法。",
            details={"raw_error": str(exc)},
        )
    if isinstance(exc, ValueError):
        return RuntimeModelCallError(
            code="MODEL_STRUCTURED_VALIDATION_FAILED",
            message=str(exc) or "模型返回的结构化结果不合法。",
        )
    classification = classify_model_exception(exc, stage="request")
    if classification is not None:
        code = (
            "MODEL_TIMEOUT"
            if classification.machine_code
            in {"MODEL_REQUEST_TIMEOUT", "MODEL_FIRST_TOKEN_TIMEOUT"}
            else classification.machine_code
        )
        return RuntimeModelCallError(
            code=code,
            message=classification.ui_summary,
            details={"ui_title": classification.ui_title},
        )
    return RuntimeModelCallError(
        code="MODEL_UPSTREAM_ERROR",
        message=str(exc).strip() or "模型调用失败。",
    )


def _response_to_payload(response: object) -> dict[str, Any]:
    metadata = getattr(response, "metadata", None)
    if isinstance(metadata, BaseModel):
        return metadata.model_dump(mode="json")
    if isinstance(metadata, dict):
        return dict(metadata)
    if isinstance(response, dict):
        nested_metadata = response.get("metadata")
        if isinstance(nested_metadata, BaseModel):
            return nested_metadata.model_dump(mode="json")
        if isinstance(nested_metadata, dict):
            return dict(nested_metadata)
    if isinstance(response, BaseModel):
        return response.model_dump(mode="json")
    if isinstance(response, dict):
        return dict(response)
    text = _response_to_text(response)
    if not text:
        raise ValueError("模型返回了空响应。")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("模型未返回合法 JSON 对象。") from exc
    if not isinstance(payload, dict):
        raise ValueError("模型返回了非对象结构。")
    return payload


def _response_to_text(response: object) -> str:
    if isinstance(response, str):
        return response.strip()
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            text = block.get("text") if isinstance(block, dict) else getattr(
                block,
                "text",
                None,
            )
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _ensure_chinese_output(value: Any) -> None:
    if isinstance(value, BaseModel):
        _ensure_chinese_output(value.model_dump(mode="python"))
        return
    if isinstance(value, dict):
        for child in value.values():
            _ensure_chinese_output(child)
        return
    if isinstance(value, list):
        for child in value:
            _ensure_chinese_output(child)
        return
    if not isinstance(value, str):
        return
    text = value.strip()
    if not text:
        raise RuntimeModelCallError(
            code="MODEL_CHINESE_VALIDATION_FAILED",
            message="模型返回了空的中文输出。",
        )
    if _ASCII_LETTER_RE.search(text) or not _CHINESE_CHAR_RE.search(text):
        raise RuntimeModelCallError(
            code="MODEL_CHINESE_VALIDATION_FAILED",
            message="模型未返回全中文结果。",
        )


__all__ = [
    "InstrumentedRuntimeChatModel",
    "RuntimeModelCallError",
    "RuntimeModelCallPolicy",
    "RuntimeModelCallRecord",
    "RuntimeModelCallService",
    "RuntimeModelHealthStatus",
    "RuntimeModelHealthTracker",
    "build_instrumented_chat_model",
]
