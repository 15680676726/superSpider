# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403
from .service_core import _GoalServiceCoreMixin
from .service_dispatch import _GoalServiceDispatchMixin
from .service_compiler import _GoalServiceCompilerMixin


class GoalService(
    _GoalServiceCoreMixin,
    _GoalServiceDispatchMixin,
    _GoalServiceCompilerMixin,
):
    pass
