# -*- coding: utf-8 -*-
"""Legacy compatibility shim for private conversation compaction."""
from __future__ import annotations

import logging

from ...memory import conversation_compaction_service as compaction_module
from ...memory.conversation_compaction_service import (
    ConversationCompactionService,
    ReMeLight,
)

logger = logging.getLogger(__name__)
_REME_AVAILABLE = compaction_module._REME_AVAILABLE


class MemoryManager(ConversationCompactionService):
    """Backward-compatible alias for private conversation compaction."""

    def __init__(self, working_dir: str):
        compaction_module._REME_AVAILABLE = _REME_AVAILABLE
        super().__init__(working_dir=working_dir)
