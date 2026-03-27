# -*- coding: utf-8 -*-
from __future__ import annotations

from .service import FixedSopService


class FixedSopRuntime:
    """Thin placeholder wrapper for future fixed SOP runtime orchestration."""

    def __init__(self, service: FixedSopService) -> None:
        self._service = service

    @property
    def service(self) -> FixedSopService:
        return self._service
