# -*- coding: utf-8 -*-
"""Runtime model diagnostics and fallback-aware error normalization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, TYPE_CHECKING

from agentscope_runtime.engine.schemas.exception import AppBaseException
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

if TYPE_CHECKING:  # pragma: no cover
    from .provider_manager import ModelSlotConfig


@dataclass(slots=True)
class ModelErrorClassification:
    machine_code: str
    ui_title: str
    ui_summary: str
    status: int
    fallback_eligible: bool


@dataclass(slots=True)
class ModelAttemptRecord:
    provider_id: str
    model: str
    source: str
    stage: str
    error_type: str
    error_message: str
    fallback_eligible: bool

    def slot_label(self) -> str:
        return f"{self.provider_id}/{self.model}"


class ModelRuntimeException(AppBaseException):
    """Structured model runtime exception for UI-friendly diagnostics."""

    def __init__(
        self,
        *,
        code: str,
        ui_title: str,
        message: str,
        status: int,
        details: dict[str, Any],
    ) -> None:
        super().__init__(status=status, code=code, message=message, details=details)
        self.ui_title = ui_title


def normalize_runtime_exception(exc: Exception) -> Exception:
    """Convert raw upstream/model errors into structured runtime exceptions."""
    if isinstance(exc, AppBaseException):
        return exc
    classification = classify_model_exception(exc, stage="request")
    if classification is None:
        return exc
    raw_message = _trim_error_message(exc)
    ui_title = classification.ui_title
    message = "\n".join(
        [
            classification.ui_summary,
            f"最后错误：{raw_message}",
        ],
    )
    return ModelRuntimeException(
        code=classification.machine_code,
        ui_title=ui_title,
        message=message,
        status=classification.status,
        details={
            "ui_title": ui_title,
            "raw_error": raw_message,
            "normalized": True,
        },
    )


def format_slot_label(slot: "ModelSlotConfig") -> str:
    return f"{slot.provider_id}/{slot.model}"


def unavailable_attempt(
    *,
    slot: "ModelSlotConfig",
    source: str,
    reason: str,
    stage: str = "availability",
) -> ModelAttemptRecord:
    return ModelAttemptRecord(
        provider_id=slot.provider_id,
        model=slot.model,
        source=source,
        stage=stage,
        error_type="slot_unavailable",
        error_message=reason,
        fallback_eligible=True,
    )


def failed_attempt(
    *,
    slot: "ModelSlotConfig",
    source: str,
    exc: Exception,
    stage: str,
) -> tuple[ModelAttemptRecord, ModelErrorClassification]:
    classification = classify_model_exception(exc, stage=stage)
    if classification is None:
        default_title = "模型初始化失败" if stage == "model_init" else "模型执行失败"
        default_summary = (
            "模型实例初始化失败，系统将优先尝试其他候选。"
            if stage == "model_init"
            else "模型执行过程中发生未归类异常。"
        )
        classification = ModelErrorClassification(
            machine_code="MODEL_RUNTIME_FAILED",
            ui_title=default_title,
            ui_summary=default_summary,
            status=502,
            fallback_eligible=stage == "model_init",
        )
    record = ModelAttemptRecord(
        provider_id=slot.provider_id,
        model=slot.model,
        source=source,
        stage=stage,
        error_type=exc.__class__.__name__,
        error_message=_trim_error_message(exc),
        fallback_eligible=classification.fallback_eligible,
    )
    return record, classification


def _coerce_attempt_record(value: Any) -> ModelAttemptRecord | None:
    if isinstance(value, ModelAttemptRecord):
        return value
    if not isinstance(value, dict):
        return None
    provider_id = str(value.get("provider_id") or "").strip()
    model = str(value.get("model") or "").strip()
    if not provider_id or not model:
        return None
    return ModelAttemptRecord(
        provider_id=provider_id,
        model=model,
        source=str(value.get("source") or "unknown"),
        stage=str(value.get("stage") or "unknown"),
        error_type=str(value.get("error_type") or "unknown"),
        error_message=str(value.get("error_message") or "Unknown error."),
        fallback_eligible=bool(value.get("fallback_eligible")),
    )


def _attempt_error_message(value: Any) -> str:
    record = _coerce_attempt_record(value)
    if record is not None:
        return record.error_message
    if isinstance(value, dict):
        for key in ("error_message", "message", "error"):
            text = str(value.get(key) or "").strip()
            if text:
                return text
    text = str(value).strip()
    return text or "未记录到具体错误。"


def build_exhausted_model_exception(
    *,
    attempts: list[ModelAttemptRecord],
    last_classification: ModelErrorClassification | None = None,
) -> ModelRuntimeException:
    if last_classification is None:
        last_classification = ModelErrorClassification(
            machine_code="MODEL_SLOT_UNAVAILABLE",
            ui_title="没有可用模型",
            ui_summary="当前没有可用的聊天模型，请检查激活模型、API Key 和回退链配置。",
            status=503,
            fallback_eligible=False,
        )
    normalized_attempts = [
        record
        for attempt in attempts
        if (record := _coerce_attempt_record(attempt)) is not None
    ]
    attempted_slots = []
    for attempt in normalized_attempts:
        label = attempt.slot_label()
        if label not in attempted_slots:
            attempted_slots.append(label)
    last_error = attempts[-1].error_message if attempts else "未记录到具体错误。"
    message_lines = [last_classification.ui_summary]
    if attempted_slots:
        message_lines.append(f"已尝试：{' -> '.join(attempted_slots)}")
    if len(attempted_slots) > 1:
        message_lines.append("系统已经自动尝试回退链，但没有找到可成功执行的模型。")
    message_lines.append(f"最后错误：{last_error}")
    details = {
        "ui_title": last_classification.ui_title,
        "attempt_count": len(attempts),
        "attempts": [asdict(attempt) for attempt in attempts],
        "attempted_slots": attempted_slots,
        "fallback_attempted": len(attempted_slots) > 1,
        "raw_error": last_error,
    }
    return ModelRuntimeException(
        code=last_classification.machine_code,
        ui_title=last_classification.ui_title,
        message="\n".join(message_lines),
        status=last_classification.status,
        details=details,
    )


def classify_model_exception(
    exc: Exception,
    *,
    stage: str,
) -> ModelErrorClassification | None:
    raw = _trim_error_message(exc).lower()
    status_code = _extract_status_code(exc, raw)
    is_first_token_stage = stage == "first_token"

    if isinstance(exc, AuthenticationError) or any(
        token in raw
        for token in (
            "account_deactivated",
            "invalid_api_key",
            "authentication",
            "unauthorized",
            "401",
        )
    ):
        return ModelErrorClassification(
            machine_code="MODEL_AUTH_FAILED",
            ui_title="模型鉴权失败",
            ui_summary="当前模型通道鉴权失败，请检查 API Key、账号状态或上游渠道授权。",
            status=401,
            fallback_eligible=True,
        )

    if isinstance(exc, RateLimitError) or "429" in raw or "rate limit" in raw:
        return ModelErrorClassification(
            machine_code="MODEL_RATE_LIMITED",
            ui_title="模型请求受限",
            ui_summary="上游模型当前限流或额度不足，系统会优先尝试其他可用候选。",
            status=429,
            fallback_eligible=True,
        )

    if isinstance(exc, APITimeoutError) or isinstance(exc, TimeoutError) or any(
        token in raw for token in ("timed out", "timeout", "time out")
    ):
        return ModelErrorClassification(
            machine_code=(
                "MODEL_FIRST_TOKEN_TIMEOUT"
                if is_first_token_stage
                else "MODEL_REQUEST_TIMEOUT"
            ),
            ui_title="模型响应超时",
            ui_summary=(
                "模型首个响应等待超时。"
                if is_first_token_stage
                else "模型请求超时。"
            ),
            status=504,
            fallback_eligible=True,
        )

    if isinstance(exc, APIConnectionError) or any(
        token in raw
        for token in (
            "connection error",
            "failed to connect",
            "connection refused",
            "network error",
            "connection aborted",
        )
    ):
        return ModelErrorClassification(
            machine_code="MODEL_CONNECTION_FAILED",
            ui_title="模型连接失败",
            ui_summary="模型上游连接异常，当前请求未能建立稳定通道。",
            status=503,
            fallback_eligible=True,
        )

    if isinstance(exc, InternalServerError) or status_code in {502, 503, 504}:
        if status_code == 502 or "bad gateway" in raw:
            return ModelErrorClassification(
                machine_code="MODEL_UPSTREAM_BAD_GATEWAY",
                ui_title="模型上游网关异常",
                ui_summary="模型上游返回了网关错误，通常是渠道或中转服务暂时不可用。",
                status=502,
                fallback_eligible=True,
            )
        if any(
            token in raw
            for token in (
                "no available channel",
                "model_not_found",
                "service unavailable",
                "channel unavailable",
            )
        ):
            return ModelErrorClassification(
                machine_code="MODEL_CHANNEL_UNAVAILABLE",
                ui_title="模型通道不可用",
                ui_summary="当前模型通道不可用，系统会尝试切换到回退候选。",
                status=503,
                fallback_eligible=True,
            )
        return ModelErrorClassification(
            machine_code="MODEL_UPSTREAM_UNAVAILABLE",
            ui_title="模型上游不可用",
            ui_summary="模型上游当前不可用，系统会尝试其他候选模型。",
            status=max(status_code or 503, 500),
            fallback_eligible=True,
        )

    if isinstance(exc, BadRequestError) or status_code == 400:
        return ModelErrorClassification(
            machine_code="MODEL_REQUEST_INVALID",
            ui_title="模型请求无效",
            ui_summary="当前请求被模型上游拒绝，通常是参数、上下文或工具载荷不合法。",
            status=400,
            fallback_eligible=False,
        )

    if isinstance(exc, APIStatusError) and status_code:
        return ModelErrorClassification(
            machine_code="MODEL_UPSTREAM_ERROR",
            ui_title="模型上游异常",
            ui_summary="模型上游返回了异常状态，当前请求无法继续执行。",
            status=status_code,
            fallback_eligible=status_code >= 500 or status_code in {401, 403, 429},
        )

    if any(
        token in raw
        for token in (
            "no available channel",
            "bad gateway",
            "service unavailable",
            "connection error",
            "account_deactivated",
        )
    ):
        return ModelErrorClassification(
            machine_code="MODEL_UPSTREAM_ERROR",
            ui_title="模型上游异常",
            ui_summary="模型上游返回了异常，当前请求无法稳定执行。",
            status=503,
            fallback_eligible=True,
        )

    return None


def _extract_status_code(exc: Exception, raw: str) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
    for candidate in (504, 503, 502, 429, 401, 400):
        if f"{candidate}" in raw:
            return candidate
    return None


def _trim_error_message(exc: Exception) -> str:
    raw = str(exc).strip()
    if not raw:
        raw = exc.__class__.__name__
    raw = " ".join(raw.split())
    return raw[:320]


__all__ = [
    "ModelAttemptRecord",
    "ModelRuntimeException",
    "build_exhausted_model_exception",
    "classify_model_exception",
    "failed_attempt",
    "format_slot_label",
    "normalize_runtime_exception",
    "unavailable_attempt",
]
