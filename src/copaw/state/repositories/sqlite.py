# -*- coding: utf-8 -*-
"""SQLite repository implementations for the state layer."""
from __future__ import annotations

from .sqlite_tasks import (
    SqliteGoalRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)
from .sqlite_human_assist_tasks import (
    SqliteHumanAssistTaskRepository,
)
from .sqlite_work_context import (
    SqliteWorkContextRepository,
)
from .sqlite_workflows import (
    SqliteExecutionRoutineRepository,
    SqliteFixedSopBindingRepository,
    SqliteFixedSopTemplateRepository,
    SqliteRoutineRunRepository,
    SqliteWorkflowPresetRepository,
    SqliteWorkflowRunRepository,
    SqliteWorkflowTemplateRepository,
)
from .sqlite_predictions import (
    SqlitePredictionCaseRepository,
    SqlitePredictionRecommendationRepository,
    SqlitePredictionReviewRepository,
    SqlitePredictionScenarioRepository,
    SqlitePredictionSignalRepository,
)
from .sqlite_governance_agents import (
    SqliteAgentCheckpointRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteCapabilityOverrideRepository,
    SqliteDecisionRequestRepository,
    SqliteGoalOverrideRepository,
    SqliteGovernanceControlRepository,
)
from .sqlite_runtime_automation import (
    SqliteAutomationLoopRuntimeRepository,
)
from .sqlite_external_runtimes import (
    SqliteExternalCapabilityRuntimeRepository,
)
from .sqlite_executor_runtime import (
    SqliteExecutorRuntimeRepository,
)
from .sqlite_industry import (
    SqliteAgentReportRepository,
    SqliteAssignmentRepository,
    SqliteBacklogItemRepository,
    SqliteIndustryInstanceRepository,
    SqliteOperatingCycleRepository,
    SqliteOperatingLaneRepository,
)
from .sqlite_media import (
    SqliteMediaAnalysisRepository,
)
from .sqlite_strategy import (
    SqliteKnowledgeChunkRepository,
    SqliteStrategyMemoryRepository,
)
from .sqlite_memory import (
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryRelationViewRepository,
    SqliteMemoryReflectionRunRepository,
)
from .sqlite_memory_sleep import SqliteMemorySleepRepository
from .sqlite_research import SqliteResearchSessionRepository
from .sqlite_surface_learning import (
    SqliteSurfaceCapabilityTwinRepository,
    SqliteSurfacePlaybookRepository,
)
