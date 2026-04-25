# Architecture Docs

This directory holds internal architecture records, active working plans, and secondary design notes that do not need to stay in the repository root or in the public website docs surface.

## Root vs docs/architecture

The repository root now keeps only:

- public entry docs such as `README.md`, `LICENSE`, and contribution/security files
- a small set of core runtime/state ledgers that are still treated as top-level operating documents

Secondary architecture material belongs here instead of cluttering the root.

Public-facing product docs should stay in `website/`.
Internal engineering docs should stay under `docs/architecture/`.
Retired or historically important but non-active material should move under `docs/archive/`.

## Working plans moved out of root

The following files were moved into [`working-plans/`](./working-plans/) to keep the root cleaner:

- `CHAT_RUNTIME_ALIGNMENT_PLAN.md`
- `MAIN_BRAIN_CHAT_ORCHESTRATION_SPLIT_PLAN.md`
- `MEDIA_ANALYSIS_INGEST_PLAN.md`
- `MEMORY_VNEXT_PLAN.md`
- `MINIMAL_CONTROL_THREAD_TASK_THREAD_UPGRADE_PLAN.md`
- `PHASE1_EXECUTION_PLAN.md`
- `V4_WORKFLOW_CAPABILITY_PLAN.md`
- `V5_EXECUTION_SURFACE_UPGRADE_PLAN.md`
- `V6_ROUTINE_MUSCLE_MEMORY_PLAN.md`
- `WORK_CONTEXT_IMPLEMENTATION_PLAN.md`
- `WORK_CONTEXT_PURPOSE_AND_IMPLEMENTATION_TARGET.md`

## Core top-level architecture documents still kept at root

These remain at the repository root because they are heavily used as canonical operating documents across the codebase, tests, or workflow instructions:

- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `TASK_STATUS.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`
- `UNIFIED_ACCEPTANCE_STANDARD.md`
- `implementation_plan.md`
- `PHASEB_EXECUTION_PLAN.md`
- `PHASEA_PHASEB_PARALLEL_PLAN.md`
- `FRONTEND_UPGRADE_PLAN.md`
- `RUNTIME_CENTER_UI_SPEC.md`
- `AGENT_VISIBLE_MODEL.md`
- `DEPRECATION_LEDGER.md`

If a document is no longer a core operating document, it should be moved under `docs/architecture/` or `docs/archive/` instead of returning to the root.

Retired architecture topics should go one step further and live under `docs/archive/retired-architecture/` instead of active working plans.

Legacy website markdown that is no longer the canonical public docs surface should also be archived instead of remaining under `website/public/`.
