# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from .models import CapabilityMount, CapabilitySummary, SourceKind
from .registry import CapabilityRegistry

if TYPE_CHECKING:
    from .service import CapabilityService


def __getattr__(name: str):
    if name == "CapabilityService":
        from .service import CapabilityService

        return CapabilityService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CapabilityMount",
    "CapabilityRegistry",
    "CapabilityService",
    "CapabilitySummary",
    "SourceKind",
]

