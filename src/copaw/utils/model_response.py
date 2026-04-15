# -*- coding: utf-8 -*-
from __future__ import annotations


def supports_async_iteration(response: object) -> bool:
    try:
        iterator = getattr(response, "__aiter__", None)
    except Exception:
        return False
    return callable(iterator)


async def materialize_model_response(response: object) -> object:
    if not supports_async_iteration(response):
        return response

    last_item: object | None = None
    async for item in response:  # type: ignore[misc]
        last_item = item
    return last_item if last_item is not None else response


__all__ = ["materialize_model_response", "supports_async_iteration"]
