# -*- coding: utf-8 -*-
from __future__ import annotations

from importlib import import_module

__all__ = [
    "CapabilityMount",
    "CapabilityRegistry",
    "CapabilityService",
    "CapabilitySummary",
    "SourceKind",
]

_EXPORTS = {
    "CapabilityMount": (".models", "CapabilityMount"),
    "CapabilityRegistry": (".registry", "CapabilityRegistry"),
    "CapabilityService": (".service", "CapabilityService"),
    "CapabilitySummary": (".models", "CapabilitySummary"),
    "SourceKind": (".models", "SourceKind"),
}


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, symbol = target
    module = import_module(module_name, __name__)
    return getattr(module, symbol)
