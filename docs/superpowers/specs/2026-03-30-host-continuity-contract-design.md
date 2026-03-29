HOST CONTINUITY CONTRACT ALIGNMENT

**Context.** Workflow preview, fixed-SOP, and cron each currently interpret host continuity by peeling layered data from the legacy `host_twin.continuity.status` enumeration and related metadata (continuity_status, handoff_state, etc.). That reproduces the same logic in three places and keeps the consumers tightly coupled to the old enum semantics even though we already maintain a canonical `host_twin_summary` projection.

**Goal.** Switch all three consumers to the canonical summary, enrich that summary with a `continuity_state` that is one of `ready`, `guarded`, or `blocked`, and align launch decisions so that workflow/fixed-sop/cron refer to the same single source of truth instead of the previous continuity enum.

## Approaches

1. **Central helper + summary enrichment (recommended).** Extend `build_host_twin_summary` to compute `continuity_state` via an exported helper, then have every consumer read that field. This keeps the summary canonical and lets downstream code avoid repeating the blocking logic.
2. **Per-service summary interpretation.** Let each consumer classify the summary locally. Easier for a small change but risks drift because the same classification logic would live in multiple files.
3. **Host-truth service/provider.** Materialize a `HostContinuityState` object through the environment service. Involves deeper changes to the environment stack and is out of scope for this focused handoff since the canonical summary already exists.

## Recommended Design

We follow **Approach 1**:

1. In `task_review_projection.py`, add a helper that classifies a summary as `ready`, `guarded`, or `blocked` based on `recommended_scheduler_action`, blocked surface count, `legal_recovery_mode`, and contention state. That helper is used inside `build_host_twin_summary` to attach `continuity_state`.
2. Update `src/copaw/workflows/service_preview.py` to cope with the enriched summary: stop reading the old `continuity.status` and `continuity_status`, instead consume `host_twin_summary` (including `continuity_state`, `recommended_scheduler_action`, etc.) for launch blockers.
3. Update `FixedSopService` so that both the host snapshot metadata and `_evaluate_host_preflight` rely on the aggregated `host_twin_summary`, reading `continuity_state` rather than the legacy continuity dict fields.
4. Ensure `CronExecutor` carries forward the canonical host snapshot (with `host_twin_summary`) when building dispatch meta, so future gating logic can directly leverage `continuity_state`.
5. Update the targeted tests (`tests/app/test_workflow_templates_api.py`, `tests/fixed_sops/test_service.py`, `tests/app/test_fixed_sop_kernel_api.py`, `tests/app/test_cron_executor.py`) to reflect the new field and assert we no longer rely on `continuity_status`.

## Testing Plan

- `python -m pytest tests/app/test_workflow_templates_api.py -q`
- `python -m pytest tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py tests/app/test_cron_executor.py -q`

Failures will point to either missing summary enrichment or host snapshot assembly issues.

## Next Steps

1. Internal spec review / self-check.
2. Invite user approval before continuing implementation.
3. Once approved run the testing plan above.
