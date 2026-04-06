# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LearningRuntimeBindings:
    """Shared runtime collaborators wired into the learning facade."""

    industry_service: object | None = None
    capability_service: object | None = None
    kernel_dispatcher: object | None = None
    fixed_sop_service: object | None = None
    agent_profile_service: object | None = None
    experience_memory_service: object | None = None


__all__ = ["LearningRuntimeBindings"]
