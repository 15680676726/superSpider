# -*- coding: utf-8 -*-
"""Shared surface execution foundations."""

from .owner import (
    GuidedBrowserSurfaceIntent,
    GuidedDesktopSurfaceIntent,
    GuidedDocumentSurfaceIntent,
    ProfessionSurfaceOperationCheckpoint,
    ProfessionSurfaceOperationOwner,
    ProfessionSurfaceOperationPlan,
    build_guided_browser_surface_owner,
    build_guided_desktop_surface_owner,
    build_guided_document_surface_owner,
)
from .desktop import (
    DesktopExecutionLoopResult,
    DesktopExecutionResult,
    DesktopExecutionStatus,
    DesktopExecutionStep,
    DesktopObservation,
    DesktopSurfaceExecutionService,
    DesktopTargetCandidate,
    DesktopTargetKind,
)
from .document import (
    DocumentExecutionLoopResult,
    DocumentExecutionResult,
    DocumentExecutionStatus,
    DocumentExecutionStep,
    DocumentObservation,
    DocumentSurfaceExecutionService,
)

__all__ = [
    "GuidedBrowserSurfaceIntent",
    "GuidedDesktopSurfaceIntent",
    "GuidedDocumentSurfaceIntent",
    "ProfessionSurfaceOperationCheckpoint",
    "ProfessionSurfaceOperationOwner",
    "ProfessionSurfaceOperationPlan",
    "build_guided_browser_surface_owner",
    "build_guided_desktop_surface_owner",
    "build_guided_document_surface_owner",
    "DesktopExecutionLoopResult",
    "DesktopExecutionResult",
    "DesktopExecutionStatus",
    "DesktopExecutionStep",
    "DesktopObservation",
    "DesktopSurfaceExecutionService",
    "DesktopTargetCandidate",
    "DesktopTargetKind",
    "DocumentExecutionLoopResult",
    "DocumentExecutionResult",
    "DocumentExecutionStatus",
    "DocumentExecutionStep",
    "DocumentObservation",
    "DocumentSurfaceExecutionService",
]
