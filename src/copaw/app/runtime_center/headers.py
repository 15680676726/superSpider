# -*- coding: utf-8 -*-
"""Discovery headers for the Runtime Center operator surface."""

from fastapi import Response

RUNTIME_CENTER_OVERVIEW_PATH = "/api/runtime-center/overview"
RUNTIME_CENTER_SURFACE_VERSION = "runtime-center-v1"


def apply_runtime_center_surface_headers(
    response: Response,
    *,
    surface: str,
) -> None:
    """Expose discovery headers for the Runtime Center operator surface."""
    response.headers["X-CoPaw-Runtime-Surface-Version"] = (
        RUNTIME_CENTER_SURFACE_VERSION
    )
    response.headers["X-CoPaw-Runtime-Surface"] = surface
    response.headers["X-CoPaw-Runtime-Overview"] = RUNTIME_CENTER_OVERVIEW_PATH
