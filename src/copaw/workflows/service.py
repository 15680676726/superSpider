# -*- coding: utf-8 -*-
from __future__ import annotations

from ..capabilities.remote_skill_contract import (
    _BUSINESS_AGENT_EXTRA_CAPABILITY_LIMIT as _WORKFLOW_BUSINESS_AGENT_EXTRA_CAPABILITY_LIMIT,
)
from .service_shared import *  # noqa: F401,F403
from .service_runs import _WorkflowServiceRunMixin
from .service_preview import _WorkflowServicePreviewMixin
from .service_context import _WorkflowServiceContextMixin
from .service_builtin import _WorkflowServiceBuiltinMixin


class WorkflowTemplateService(
    _WorkflowServiceRunMixin,
    _WorkflowServicePreviewMixin,
    _WorkflowServiceContextMixin,
    _WorkflowServiceBuiltinMixin,
):
    _BUSINESS_AGENT_EXTRA_CAPABILITY_LIMIT = (
        _WORKFLOW_BUSINESS_AGENT_EXTRA_CAPABILITY_LIMIT
    )
