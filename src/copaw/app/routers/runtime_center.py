# -*- coding: utf-8 -*-
"""Runtime Center API for the operator surface."""
from __future__ import annotations

# Deliberate aggregator import: route modules register against the shared
# runtime-center router and schemas defined in runtime_center_shared.
from .runtime_center_shared import *  # noqa: F401,F403
from . import runtime_center_routes_core as _runtime_center_routes_core  # noqa: F401
from . import runtime_center_routes_ops as _runtime_center_routes_ops  # noqa: F401
from . import runtime_center_routes_actor as _runtime_center_routes_actor  # noqa: F401
from . import runtime_center_routes_overview as _runtime_center_routes_overview  # noqa: F401
from . import runtime_center_routes_memory as _runtime_center_routes_memory  # noqa: F401
from . import runtime_center_routes_knowledge as _runtime_center_routes_knowledge  # noqa: F401
from . import runtime_center_routes_reports as _runtime_center_routes_reports  # noqa: F401
from . import runtime_center_routes_industry as _runtime_center_routes_industry  # noqa: F401
