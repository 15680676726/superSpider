# -*- coding: utf-8 -*-
"""Shared scalar and mapping helpers for Runtime Center projections."""
from __future__ import annotations


def first_non_empty(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
            continue
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None


def string_list_from_values(*values: object) -> list[str]:
    items: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                items.append(normalized)
            continue
        if isinstance(value, (list, tuple, set)):
            items.extend(string_list_from_values(*list(value)))
            continue
        normalized = str(value).strip()
        if normalized:
            items.append(normalized)
    return items


def dict_from_value(value: object) -> dict[str, object] | None:
    if isinstance(value, dict):
        return dict(value)
    return None


def dict_list_from_value(value: object) -> list[dict[str, object]]:
    if isinstance(value, dict):
        return [dict(value)]
    if isinstance(value, (list, tuple, set)):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


__all__ = [
    "dict_from_value",
    "dict_list_from_value",
    "first_non_empty",
    "string_list_from_values",
]
