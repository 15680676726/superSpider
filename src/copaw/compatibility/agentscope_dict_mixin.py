# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
from typing import Any


def _dict_mixin_deepcopy(self: dict[str, Any], memo: dict[int, object]) -> object:
    clone = type(self)(**deepcopy(dict(self), memo))
    memo[id(self)] = clone
    return clone


def ensure_agentscope_dict_mixin_deepcopy() -> None:
    """Patch AgentScope DictMixin so deepcopy no longer raises KeyError.

    AgentScope models such as ChatResponse / ChatUsage inherit DictMixin,
    whose attribute-style lookup delegates to ``dict.__getitem__``.
    Python's ``copy.deepcopy`` probes ``__deepcopy__`` via ``getattr``;
    without this patch the probe hits DictMixin.__getattr__ and raises
    ``KeyError('__deepcopy__')``.
    """

    try:
        from agentscope._utils._mixin import DictMixin
    except Exception:
        return

    current = getattr(DictMixin, "__dict__", {}).get("__deepcopy__")
    if callable(current):
        return

    DictMixin.__deepcopy__ = _dict_mixin_deepcopy  # type: ignore[attr-defined]
