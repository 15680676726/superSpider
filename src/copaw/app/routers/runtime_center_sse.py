# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from pydantic_core import PydanticSerializationError


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
                dumped = event.model_dump(mode="json")
            payload = json.dumps(dumped, ensure_ascii=False, default=str)
        elif hasattr(event, "__dict__"):
            payload = json.dumps(vars(event), ensure_ascii=False, default=str)
        else:
            payload = json.dumps(str(event), ensure_ascii=False)
    return f"data: {payload}\n\n"


__all__ = ["_encode_sse_event"]
