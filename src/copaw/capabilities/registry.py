# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from .models import CapabilityMount
from .sources.cooperative import list_cooperative_capabilities
from .sources.mcp import list_mcp_capabilities
from .sources.skills import list_skill_capabilities
from .sources.system import list_system_capabilities
from .sources.tools import list_tool_capabilities

logger = logging.getLogger(__name__)


class CapabilityRegistry:
    """Phase 2 read-only registry that normalizes capability sources."""

    def list_capabilities(self) -> list[CapabilityMount]:
        payload: dict[str, CapabilityMount] = {}
        for loader in (
            list_tool_capabilities,
            list_skill_capabilities,
            list_mcp_capabilities,
            list_cooperative_capabilities,
            list_system_capabilities,
        ):
            try:
                mounts = loader()
            except Exception:
                logger.exception("capability loader failed: %s", loader.__name__)
                continue
            for mount in mounts:
                payload[mount.id] = mount
        return sorted(payload.values(), key=lambda item: (item.kind, item.id))
