# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from pydantic_core import PydanticSerializationError


def _json_safe_event_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _json_safe_event_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe_event_value(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump(mode="json", fallback=str)
        except TypeError:
            try:
                dumped = value.model_dump(mode="json")
            except (PydanticSerializationError, TypeError, ValueError):
                dumped = None
        except (PydanticSerializationError, TypeError, ValueError):
            dumped = None
        if dumped is not None:
            return _json_safe_event_value(dumped)
    if hasattr(value, "__dict__"):
        public_payload = {
            key: item
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
        if public_payload:
            return _json_safe_event_value(public_payload)
    return str(value)


def _encode_sse_event(event: object) -> str:
    try:
        if hasattr(event, "model_dump_json"):
            payload = event.model_dump_json()
        elif hasattr(event, "json"):
            payload = event.json()
        else:
            payload = json.dumps(event, ensure_ascii=False)
    except (PydanticSerializationError, TypeError, ValueError):
        if hasattr(event, "model_dump"):
            try:
                dumped = event.model_dump(mode="json", fallback=str)
            except TypeError:
                try:
                    dumped = event.model_dump(mode="json")
                except (PydanticSerializationError, TypeError, ValueError):
                    dumped = None
            if dumped is not None:
                payload = json.dumps(
                    _json_safe_event_value(dumped),
                    ensure_ascii=False,
                    default=str,
                )
            elif hasattr(event, "__dict__"):
                payload = json.dumps(
                    _json_safe_event_value(event),
                    ensure_ascii=False,
                    default=str,
                )
            else:
                payload = json.dumps(str(event), ensure_ascii=False)
        elif hasattr(event, "__dict__"):
            payload = json.dumps(
                _json_safe_event_value(event),
                ensure_ascii=False,
                default=str,
            )
        else:
            payload = json.dumps(str(event), ensure_ascii=False)
    return f"data: {payload}\n\n"


__all__ = ["_encode_sse_event"]
