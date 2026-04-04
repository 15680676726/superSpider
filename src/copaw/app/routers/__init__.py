# -*- coding: utf-8 -*-
from fastapi import APIRouter

from .agent import router as agent_router
from .buddy_routes import router as buddy_router
from .capability_market import router as capability_market_router
from .capabilities import router as capabilities_router
from .config import router as config_router
from .fixed_sops import router as fixed_sops_router
from .local_models import admin_router as local_models_admin_router
from .local_models import router as local_models_router
from .learning import router as learning_router
from .media import router as media_router
from .providers import admin_router as providers_admin_router
from .providers import router as providers_router
from .goals import public_router as goals_public_router
from .routines import router as routines_router
from .runtime_center import router as runtime_center_router
from .system import router as system_router
from .workspace import router as workspace_router
from .envs import router as envs_router
from .industry import router as industry_router
from .ollama_models import admin_router as ollama_models_admin_router
from .ollama_models import router as ollama_models_router
from .predictions import router as predictions_router
from ..crons.api import router as cron_router
from .console import router as console_router


router = APIRouter()

router.include_router(agent_router)
router.include_router(buddy_router)
router.include_router(capability_market_router)
router.include_router(capabilities_router)
router.include_router(config_router)
router.include_router(console_router)
router.include_router(cron_router)
router.include_router(fixed_sops_router)
router.include_router(local_models_router)
router.include_router(local_models_admin_router)
router.include_router(learning_router)
router.include_router(media_router)
router.include_router(ollama_models_router)
router.include_router(ollama_models_admin_router)
router.include_router(predictions_router)
router.include_router(providers_router)
router.include_router(providers_admin_router)
router.include_router(routines_router)
router.include_router(runtime_center_router)
router.include_router(system_router)
router.include_router(workspace_router)
router.include_router(envs_router)
router.include_router(goals_public_router)
router.include_router(industry_router)

__all__ = ["router"]
