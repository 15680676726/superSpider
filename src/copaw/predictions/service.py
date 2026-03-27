# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403
from .service_core import _PredictionServiceCoreMixin
from .service_context import _PredictionServiceContextMixin
from .service_recommendations import _PredictionServiceRecommendationMixin
from .service_refresh import _PredictionServiceRefreshMixin


class PredictionService(
    _PredictionServiceCoreMixin,
    _PredictionServiceContextMixin,
    _PredictionServiceRecommendationMixin,
    _PredictionServiceRefreshMixin,
):
    pass
