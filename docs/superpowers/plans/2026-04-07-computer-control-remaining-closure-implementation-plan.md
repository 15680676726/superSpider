# Computer-Control Remaining Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining computer-control blockers so CoPaw can describe its browser/desktop/document chain as fully closed without overstating watcher depth, semantic readiness, or writer-scope stability, while keeping browser routing truthful.

**Architecture:** Keep the existing Windows-first environment/runtime chain and tighten the remaining closure seams instead of inventing a second runtime. Treat computer actuation as `adapter/host-executed + MCP-exposed`, keep CoPaw core focused on session/lease/lock/evidence/risk/recovery, and avoid growing product-layer raw action brains. Browser policy for the current phase is: built-in browser remains the default path; browser MCP is selected only when installed and healthy; attach-required requests must fail closed instead of silently falling back. Execute the current desktop hardening slice first, then close the remaining watcher/readiness/writer/live-proof gaps, and only then expand app-family semantic depth as adapter maturity rather than platform scripting.

**Tech Stack:** Python, FastAPI services, Pydantic, pytest, Windows desktop runtime, live smoke harness

**Implementation Status (2026-04-08):**
- Closure work in this plan has been implemented in code.
- Browser routing is now explicit: built-in remains the default channel, attach-required requests fail closed, and healthy attached-channel execution is projected into Runtime Center.
- Final blocker matrix passed:
  `python -m pytest tests/routines/test_routine_service.py tests/app/test_capability_market_api.py tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_watchers.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_environment_registry.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q`
  `179 passed`
- Browser/Runtime Center regression slices passed:
  `python -m pytest tests/environments/test_cooperative_browser_companion.py tests/environments/test_cooperative_browser_attach_runtime.py tests/environments/test_environment_registry.py -k "browser or browser_attach_runtime_truth" -q`
  `30 passed`
  `python -m pytest tests/app/test_capability_market_api.py tests/app/runtime_center_api_parts/detail_environment.py -k "browser or runtime_center_environment_read_endpoints" -q`
  `8 passed`
- Guarded live browser proof passed:
  `$env:COPAW_RUN_V6_LIVE_ROUTINE_SMOKE='1'; python -m pytest tests/routines/test_live_routine_smoke.py -k "attached_browser_channel_continuation_smoke or authenticated_continuation_cross_tab_save_reopen_smoke" -q`
  `2 passed`

---

### Task 1: Land The Existing Desktop Hardening Prerequisite Under The MCP-Exposed Boundary

**Files:**
- Reference: `docs/superpowers/plans/2026-04-07-desktop-control-hardening-plan.md`
- Modify: `src/copaw/routines/service.py`
- Verify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/capabilities/install_templates.py`
- Modify: `src/copaw/environments/surface_control_service.py`
- Test: `tests/routines/test_routine_service.py`
- Test: `tests/app/test_capability_market_api.py`
- Test: `tests/environments/test_cooperative_document_bridge.py`

- [ ] Execute Task 1 through Task 4 from `docs/superpowers/plans/2026-04-07-desktop-control-hardening-plan.md` in the current branch before starting the remaining-closure packages.
- [ ] Treat `RoutineService` bootstrap injection as an already-landed baseline; only patch `src/copaw/app/runtime_bootstrap_domains.py` if a fresh failing test proves the wiring is absent or regressed in the target branch.
- [ ] Run `python -m pytest tests/routines/test_routine_service.py tests/app/test_capability_market_api.py tests/environments/test_cooperative_document_bridge.py -q` and verify the prerequisite hardening slice is green.
- [ ] Run `python -m pytest tests/routines/test_routine_execution_paths.py tests/environments/test_cooperative_windows_apps.py -q` to make sure the prerequisite slice did not regress the surrounding desktop execution path.
- [ ] Do not start Task 2 until the prerequisite hardening matrix is fully green.

### Task 2: Keep Browser Routing Truthful While Deferring Attach Maturity

**Files:**
- Verify: `src/copaw/capabilities/browser_runtime.py`
- Verify: `src/copaw/environments/service.py`
- Verify: `tests/environments/test_cooperative_browser_attach_runtime.py`

- [ ] Keep browser execution on the built-in path by default when browser MCP is absent or unhealthy.
- [ ] Do not schedule attach-existing-session continuity deepening inside the current blocker-closure track.
- [ ] Make sure any attach-required path remains fail-closed rather than silently degrading to the built-in browser channel.
- [ ] Revisit deeper browser MCP / attach continuity work only after the current desktop/document closure blockers are green.

### Task 3: Deepen `HostWatcherRuntime` From Projection To Runtime Lifecycle

**Files:**
- Modify: `src/copaw/environments/cooperative/watchers.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/health_service.py`
- Test: `tests/environments/test_cooperative_watchers.py`
- Test: `tests/app/test_runtime_projection_contracts.py`
- Test: `tests/app/test_runtime_query_services.py`

- [ ] Add a failing test proving watcher state distinguishes declared metadata availability from actual runtime/companion-backed lifecycle readiness.
- [ ] Run `python -m pytest tests/environments/test_cooperative_watchers.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q` to verify the gap is real.
- [ ] Implement the minimal watcher lifecycle truth needed to expose family readiness, blocker reason, and runtime-backed event-response hints through the canonical environment projection.
- [ ] Keep watcher work on the runtime-signal plane only; do not let watcher handlers start making agent-level action decisions.
- [ ] Extend the projection/query tests so Runtime Center read models expose the strengthened watcher lifecycle contract without inventing a second truth source.
- [ ] Re-run the watcher/projection/query matrix until green.

### Task 4: Split Desktop Host Reachability From Semantic Readiness

**Files:**
- Modify: `src/copaw/capabilities/install_templates.py`
- Modify: `src/copaw/environments/cooperative/windows_apps.py`
- Modify: `src/copaw/environments/health_service.py`
- Test: `tests/app/test_capability_market_api.py`
- Test: `tests/environments/test_cooperative_windows_apps.py`

- [ ] Add a failing test proving the desktop doctor can report host-ready while semantic-control-ready is still false.
- [ ] Add a failing test proving the desktop example-run no longer claims full readiness from a bare `list_windows(...)` host smoke.
- [ ] Run `python -m pytest tests/app/test_capability_market_api.py tests/environments/test_cooperative_windows_apps.py -q` to verify both failures are real.
- [ ] Implement the minimal readiness split so doctor/example-run distinguish host reachability, MCP/adapter availability, semantic-control readiness, and writer-capable readiness when applicable.
- [ ] Re-run the capability-market and cooperative Windows-app tests until the new readiness contract is green.

### Task 5: Complete The Writer Contract Beyond Session Identity

**Files:**
- Modify: `src/copaw/environments/surface_control_service.py`
- Modify: `src/copaw/environments/health_service.py`
- Test: `tests/environments/test_cooperative_document_bridge.py`
- Test: `tests/environments/test_environment_registry.py`

- [ ] Add a failing test proving equivalent document writes from different sessions converge on the same writer scope when they target the same stable document identity.
- [ ] Run `python -m pytest tests/environments/test_cooperative_document_bridge.py tests/environments/test_environment_registry.py -q` to verify the writer-scope instability is real.
- [ ] Implement the minimal stable identity derivation so document/account scope outranks ephemeral `session_mount_id` when no explicit writer scope is provided.
- [ ] Extend the environment projection tests so the strengthened writer scope is visible through the canonical host/desktop/document projections.
- [ ] Re-run the document-bridge and environment-registry matrix until green.

### Task 6: Prove The Remaining Truth Claims With Expanded Live Verification

**Files:**
- Modify: `tests/routines/test_live_routine_smoke.py`
- Verify: `tests/environments/test_cooperative_browser_attach_runtime.py`
- Verify: `tests/environments/test_cooperative_watchers.py`
- Verify: `tests/environments/test_cooperative_windows_apps.py`
- Verify: `tests/environments/test_cooperative_document_bridge.py`

- [ ] Extend the guarded live smoke harness so it covers the remaining closure claims: watcher-driven observation flow, semantic desktop readiness path, stable writer locking, and at least one recovery/resume interruption path.
- [ ] Run the repository regression slice first with `python -m pytest tests/environments/test_cooperative_watchers.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_cooperative_document_bridge.py -q`.
- [ ] Run the guarded live smoke selection with `\$env:COPAW_RUN_V6_LIVE_ROUTINE_SMOKE='1'; python -m pytest tests/routines/test_live_routine_smoke.py -q -k "<updated computer-control live selection>"` and record the exact passing scenarios.
- [ ] If a live scenario cannot be made trustworthy yet, downgrade the closure claim in docs instead of silently skipping the gap.
- [ ] Do not describe the chain as fully closed until the repository matrix and guarded live matrix both pass.

### Task 7: App-Family Semantic Coverage Adapter Maturity Track

**Files:**
- Modify: `src/copaw/adapters/desktop/windows_host.py`
- Modify: `src/copaw/adapters/desktop/windows_uia.py`
- Modify: `src/copaw/environments/cooperative/windows_apps.py`
- Test: `tests/adapters/test_windows_host.py`
- Test: `tests/environments/test_cooperative_windows_apps.py`
- Verify: `tests/routines/test_live_routine_smoke.py`

- [ ] Start this task only after Tasks 1 through 6 are green, because it is a maturity enhancer rather than a closure blocker.
- [ ] Add a failing test for one high-value app family at a time, beginning with `office-document` or bounded dialog/form workflows, instead of creating a generic “support every app” program.
- [ ] Run the narrow adapter/cooperative test slice that covers only the selected family before changing implementation.
- [ ] Implement the minimal app-family semantic adapter depth on top of the existing generic Windows host runtime, without bypassing the formal environment/runtime/evidence chain.
- [ ] Prefer MCP/server-side adapter semantics or equivalent capability-adapter depth; do not implement Task 7 as workflow/service-layer app playbooks.
- [ ] Re-run the family-specific adapter tests and, when safe, one matching guarded live smoke scenario before moving to the next family.

### Post-Closure Browser Maturity Track

**Files:**
- Modify: `src/copaw/capabilities/browser_runtime.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/app/runtime_center/environment_feedback_projection.py`
- Test: `tests/environments/test_cooperative_browser_attach_runtime.py`
- Test: `tests/app/runtime_center_api_parts/detail_environment.py`
- Verify: `tests/routines/test_live_routine_smoke.py`

- [ ] Start this track only after the current blocker-closure matrix is green.
- [ ] Add a single browser-channel resolver so built-in vs browser MCP route selection is explicit and testable.
- [ ] Keep built-in browser as the default channel unless browser MCP is both installed and healthy.
- [ ] Make attach-required requests fail closed instead of silently falling back to the built-in browser channel.
- [ ] Project browser channel selection and health into Runtime Center so operators can see which browser path was used.
- [ ] Harden `attach-existing-session` continuity and reconnect diagnostics only after the channel resolver exists.
- [ ] Add an opt-in live smoke proving attached-session continuation against a real user-scoped browser session.
- [ ] Only after the above is stable, evaluate whether healthy browser MCP should become the preferred channel for the matching task classes.

### Task 8: Final Verification And Documentation Closure

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `docs/superpowers/specs/2026-04-07-computer-control-remaining-closure-spec.md`
- Verify: `docs/superpowers/plans/2026-04-07-desktop-control-hardening-plan.md`
- Verify: `docs/superpowers/plans/2026-04-07-computer-control-remaining-closure-implementation-plan.md`

- [ ] Run the final blocker matrix as one bundle after Tasks 1 through 6: `python -m pytest tests/routines/test_routine_service.py tests/app/test_capability_market_api.py tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_watchers.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_environment_registry.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py -q`.
- [ ] Re-run the guarded live smoke command that now represents the closure-proof matrix and capture the exact passing scenarios in task notes.
- [ ] Update `TASK_STATUS.md` and `docs/superpowers/specs/2026-04-07-computer-control-remaining-closure-spec.md` only after the final matrix proves the closure language is justified, and keep the final wording explicitly aligned with the `agent decides / adapter-host executes / MCP exposes / runtime governs` boundary.
- [ ] Commit the blocker-closure bundle before starting any further maturity-only app-family expansion.
