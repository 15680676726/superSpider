# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from ..media import MediaAnalysisRequest, MediaService, MediaSourceSpec


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _merge_string_list(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            text = _string(item)
            if text is None or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, (list, tuple, set)) else [value]
    return _merge_string_list([str(item or "") for item in raw_items])


def _request_extra_payload(request_payload: AgentRequest) -> dict[str, Any]:
    extra = getattr(request_payload, "model_extra", None)
    return extra if isinstance(extra, dict) else {}


def _request_payload_data(request_payload: AgentRequest) -> dict[str, Any]:
    payload_data = request_payload.model_dump(mode="python")
    return payload_data if isinstance(payload_data, dict) else {}


def _resolve_runtime_thread_id(
    request_payload: AgentRequest,
    *,
    extra_payload: dict[str, Any],
    thread_id: str | None = None,
) -> str | None:
    return (
        _string(thread_id)
        or _string(extra_payload.get("thread_id"))
        or _string(extra_payload.get("control_thread_id"))
        or _string(request_payload.session_id)
    )


def _resolve_work_context_id(
    request_payload: AgentRequest,
    *,
    extra_payload: dict[str, Any],
) -> str | None:
    work_context = extra_payload.get("work_context")
    return (
        _string(extra_payload.get("work_context_id"))
        or (
            _string(work_context.get("id"))
            if isinstance(work_context, dict)
            else None
        )
        or _string(getattr(request_payload, "work_context_id", None))
    )


def _should_writeback_runtime_media(
    request_payload: AgentRequest,
    *,
    extra_payload: dict[str, Any],
    industry_instance_id: str | None,
) -> bool:
    if industry_instance_id is None:
        return False

    purpose = _string(extra_payload.get("purpose"))
    if purpose in {"draft-enrichment", "learn-and-writeback"}:
        return True

    requested_actions = {
        item.lower()
        for item in _string_list(extra_payload.get("requested_actions"))
    }
    if any(
        action.startswith("writeback_") or action == "apply_writeback"
        for action in requested_actions
    ):
        return True

    session_kind = _string(extra_payload.get("session_kind"))
    if session_kind == "industry-control-thread":
        return True

    for ref in (
        _string(extra_payload.get("control_thread_id")),
        _string(extra_payload.get("thread_id")),
        _string(request_payload.session_id),
    ):
        if ref and ref.startswith("industry-chat:"):
            return True
    return False


def get_runtime_media_service(app_state: Any) -> MediaService | None:
    service = getattr(app_state, "media_service", None)
    return service if isinstance(service, MediaService) else None


def normalize_media_analysis_ids(value: object) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    return _merge_string_list([str(item or "") for item in raw_items])


def normalize_media_inputs(value: object) -> list[MediaSourceSpec]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    normalized: list[MediaSourceSpec] = []
    seen: set[str] = set()
    for item in raw_items:
        candidate: MediaSourceSpec | None = None
        if isinstance(item, MediaSourceSpec):
            candidate = item
        elif isinstance(item, str):
            url = _string(item)
            if url:
                try:
                    candidate = MediaSourceSpec(source_kind="link", url=url)
                except Exception:
                    candidate = None
        elif isinstance(item, dict):
            try:
                candidate = MediaSourceSpec.model_validate(item)
            except Exception:
                candidate = None
        if candidate is None:
            continue
        dedupe_key = (
            candidate.source_id
            or candidate.artifact_id
            or candidate.storage_uri
            or candidate.url
            or candidate.filename
            or ""
        ).strip()
        if dedupe_key and dedupe_key in seen:
            continue
        if dedupe_key:
            seen.add(dedupe_key)
        normalized.append(candidate)
    return normalized


def _request_content_blocks(request_payload: AgentRequest) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    payload_data = _request_payload_data(request_payload)
    for message in payload_data.get("input") or []:
        if not isinstance(message, dict):
            continue
        for block in message.get("content") or []:
            if isinstance(block, dict):
                blocks.append(block)
    return blocks


def _filename_from_url(url: str | None) -> str | None:
    parsed = urllib.parse.urlparse(url or "")
    filename = Path(parsed.path or "").name
    return _string(filename)


def _source_from_url(
    *,
    url: str,
    filename: str | None = None,
    analysis_mode: str | None = None,
) -> MediaSourceSpec | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "file":
        try:
            local_path = urllib.request.url2pathname(parsed.path)
        except Exception:
            return None
        resolved_filename = _string(filename) or _string(Path(local_path).name)
        return MediaSourceSpec(
            source_kind="upload",
            filename=resolved_filename,
            storage_uri=_string(local_path),
            analysis_mode=analysis_mode,
        )
    return MediaSourceSpec(
        source_kind="link",
        url=url,
        filename=_string(filename) or _filename_from_url(url),
        analysis_mode=analysis_mode,
    )


def _media_source_from_content_block(block: dict[str, Any]) -> MediaSourceSpec | None:
    block_type = _string(block.get("type"))
    if block_type == "file":
        file_data = _string(block.get("file_data"))
        filename = _string(block.get("filename"))
        if file_data is not None:
            return MediaSourceSpec(
                source_kind="upload",
                filename=filename,
                upload_base64=file_data,
            )
        file_url = _string(block.get("file_url"))
        if file_url is not None:
            return _source_from_url(url=file_url, filename=filename)
        file_id = _string(block.get("file_id"))
        if file_id is not None:
            return MediaSourceSpec(
                source_kind="existing-artifact",
                artifact_id=file_id,
                filename=filename,
            )
        return None
    if block_type == "video":
        video_url = _string(block.get("video_url"))
        if video_url is None:
            return None
        return _source_from_url(
            url=video_url,
            filename=_filename_from_url(video_url),
            analysis_mode="video-lite",
        )
    if block_type == "audio":
        audio_data = _string(block.get("data"))
        if audio_data is None:
            return None
        audio_format = _string(block.get("format"))
        filename = f"audio.{audio_format}" if audio_format else "audio.bin"
        mime_type = f"audio/{audio_format}" if audio_format else None
        return MediaSourceSpec(
            source_kind="upload",
            filename=filename,
            mime_type=mime_type,
            upload_base64=audio_data,
        )
    return None


def extract_media_inputs_from_request_content(
    request_payload: AgentRequest,
) -> list[MediaSourceSpec]:
    extracted: list[MediaSourceSpec] = []
    for block in _request_content_blocks(request_payload):
        candidate = _media_source_from_content_block(block)
        if candidate is not None:
            extracted.append(candidate)
    return normalize_media_inputs(extracted)


def _append_media_prompt_context(
    request_payload: AgentRequest,
    *,
    media_service: MediaService,
    analysis_ids: list[str],
) -> AgentRequest:
    if not analysis_ids:
        return request_payload

    context = str(media_service.build_prompt_context(analysis_ids, limit_chars=6000) or "").strip()
    if not context:
        return request_payload

    payload_data = request_payload.model_dump(mode="python")
    messages = list(payload_data.get("input") or [])
    if not messages:
        return request_payload
    last_message = dict(messages[-1] or {})
    message_text = str(last_message.get("message") or "")
    if context in message_text:
        return request_payload
    content = list(last_message.get("content") or [])
    appended = False
    for block in reversed(content):
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        block_text = str(block.get("text") or "")
        if context in block_text:
            return request_payload
        block["text"] = f"{block_text.rstrip()}\n\n{context}".strip()
        appended = True
        break
    if not appended:
        if message_text.strip():
            last_message["message"] = f"{message_text.rstrip()}\n\n{context}"
        else:
            content.append({"type": "text", "text": context})
            last_message["content"] = content
    else:
        last_message["content"] = content
    messages[-1] = last_message
    payload_data["input"] = messages
    return AgentRequest.model_validate(payload_data)


async def enrich_agent_request_with_media(
    request_payload: AgentRequest,
    *,
    app_state: Any,
    thread_id: str | None = None,
) -> tuple[AgentRequest, list[str], bool]:
    media_service = get_runtime_media_service(app_state)
    if media_service is None:
        return request_payload, [], False

    extra_payload = _request_extra_payload(request_payload)
    analysis_ids = normalize_media_analysis_ids(extra_payload.get("media_analysis_ids"))
    media_inputs = normalize_media_inputs(
        [
            *normalize_media_inputs(extra_payload.get("media_inputs")),
            *extract_media_inputs_from_request_content(request_payload),
        ]
    )
    consumed_media_inputs = bool(media_inputs)
    industry_instance_id = _string(extra_payload.get("industry_instance_id")) or _string(
        getattr(request_payload, "industry_instance_id", None),
    )
    resolved_thread_id = _resolve_runtime_thread_id(
        request_payload,
        extra_payload=extra_payload,
        thread_id=thread_id,
    )
    work_context_id = _resolve_work_context_id(
        request_payload,
        extra_payload=extra_payload,
    )
    should_writeback = _should_writeback_runtime_media(
        request_payload,
        extra_payload=extra_payload,
        industry_instance_id=industry_instance_id,
    )

    if media_inputs:
        entry_point = _string(extra_payload.get("entry_point")) or "chat"
        purpose = _string(extra_payload.get("purpose")) or "chat-answer"
        result = await media_service.analyze(
            MediaAnalysisRequest(
                sources=media_inputs,
                industry_instance_id=industry_instance_id,
                thread_id=resolved_thread_id,
                work_context_id=work_context_id,
                entry_point=entry_point,
                purpose=purpose,
                writeback=should_writeback,
            )
        )
        completed_ids = [
            item.analysis_id
            for item in result.analyses
            if str(item.status or "").strip().lower() == "completed"
        ]
        analysis_ids = _merge_string_list(analysis_ids, completed_ids)

    if should_writeback and industry_instance_id and analysis_ids:
        adopt_ids = analysis_ids if not media_inputs else []
        if adopt_ids:
            adopter = getattr(media_service, "adopt_analyses_for_industry", None)
            if callable(adopter):
                adopted = await adopter(
                    industry_instance_id=industry_instance_id,
                    analysis_ids=adopt_ids,
                    thread_id=resolved_thread_id,
                    work_context_id=work_context_id,
                )
                analysis_ids = _merge_string_list(
                    analysis_ids,
                    [item.analysis_id for item in adopted],
                )

    updated_request = request_payload
    if analysis_ids:
        payload_data = updated_request.model_dump(mode="python")
        payload_data["media_analysis_ids"] = analysis_ids
        if consumed_media_inputs:
            payload_data["media_inputs"] = []
        updated_request = AgentRequest.model_validate(payload_data)
        updated_request = _append_media_prompt_context(
            updated_request,
            media_service=media_service,
            analysis_ids=analysis_ids,
        )
        return updated_request, analysis_ids, consumed_media_inputs

    if consumed_media_inputs:
        payload_data = updated_request.model_dump(mode="python")
        payload_data["media_inputs"] = []
        updated_request = AgentRequest.model_validate(payload_data)

    return updated_request, analysis_ids, consumed_media_inputs


__all__ = [
    "enrich_agent_request_with_media",
    "extract_media_inputs_from_request_content",
    "get_runtime_media_service",
    "normalize_media_analysis_ids",
    "normalize_media_inputs",
]
