# CoPaw P0 Runtime Gap Audit Ledger

## 0. Purpose

This document records the first batch of real runtime-chain issues identified
during the `2026-04-09` P0 closure audit.

The goal is not to propose fixes yet.

The goal is:

- count real gaps
- separate confirmed issues from probable seams
- attach each issue to concrete files and chains
- prevent the current repo state from being misdescribed as "feature-complete"
  when important closure gaps still exist

This ledger should be read together with:

- [2026-04-09-execution-chat-front-door-dispatch-gap-spec.md](/D:/word/copaw/docs/superpowers/specs/2026-04-09-execution-chat-front-door-dispatch-gap-spec.md)

---

## 1. Confirmed Issues

### P0-001 Execution-chat front door can record backlog without same-turn execution start

- **Status:** confirmed
- **Severity:** critical
- **Primary files:**
  - [service_lifecycle.py](/D:/word/copaw/src/copaw/industry/service_lifecycle.py)
  - [runtime_lifecycle.py](/D:/word/copaw/src/copaw/app/runtime_lifecycle.py)
  - [system_team_handlers.py](/D:/word/copaw/src/copaw/capabilities/system_team_handlers.py)
- **Key functions:**
  - `apply_execution_chat_writeback(...)`
  - `kickoff_execution_from_chat(...)`
  - `_materialize_backlog_into_cycle(...)`
  - `run_operating_cycle(...)`
  - `handle_run_operating_cycle(...)`
- **What is happening:**
  - execution-core chat intake can persist formal backlog truth
  - the same turn may not materialize fresh assignment truth
  - actual materialization/dispatch can be delayed into the later
    operating-cycle chain
- **Why it matters:**
  - this is the main reason the system can feel like chat plus recording instead
    of main-brain-led execution
- **Notes:**
  - the later chain does dispatch
  - the confirmed problem is same-turn dispatch closure, not total absence of
    later execution

### P0-002 Operating-cycle automation delay can widen the same-turn execution gap

- **Status:** confirmed
- **Severity:** high
- **Primary files:**
  - [runtime_lifecycle.py](/D:/word/copaw/src/copaw/app/runtime_lifecycle.py)
- **Key functions:**
  - `start_automation_tasks(...)`
  - `automation_interval_seconds(...)`
- **What is happening:**
  - the default `operating-cycle` automation loop interval is `180` seconds
- **Why it matters:**
  - when P0-001 occurs, the product can remain in a "recorded but not started"
    state until the next automation sweep
- **Notes:**
  - this is not a separate architecture flaw
  - it amplifies P0-001

### P0-003 Chat writeback formal object creation lacks dedicated first-class evidence

- **Status:** confirmed
- **Severity:** high
- **Primary files:**
  - [main_brain_service.py](/D:/word/copaw/src/copaw/state/main_brain_service.py)
  - [ledger.py](/D:/word/copaw/src/copaw/evidence/ledger.py)
- **Key functions:**
  - `record_chat_writeback(...)`
  - `record_generated_item(...)`
- **What is happening:**
  - formal writeback/backlog object creation can be durable
  - but that acceptance step does not itself produce a dedicated
    `EvidenceRecord`
- **Why it matters:**
  - the system can create formal truth without a dedicated audit evidence record
    for the acceptance step itself
  - outer kernel-task completion evidence may still exist, but it is not the
    same thing as a purpose-built writeback-acceptance evidence record
  - this weakens replay, explainability, and operator-visible proof

### P0-004 Runtime Center read model can hide wiring loss as empty data

- **Status:** confirmed
- **Severity:** high
- **Primary files:**
  - [state_query.py](/D:/word/copaw/src/copaw/app/runtime_center/state_query.py)
- **Key functions:**
  - `list_human_assist_tasks(...)`
  - `get_current_human_assist_task(...)`
  - `get_human_assist_task_detail(...)`
  - plus many similar `if not callable(...): return []/None` read paths
- **What is happening:**
  - the Runtime Center query service frequently degrades missing/unwired services
    into `[]` or `None`
- **Why it matters:**
  - a missing service wire can look identical to "there is simply no data"
  - this makes read-model breaks appear as empty pages instead of explicit
    failures
- **Product effect:**
  - operators can misread a broken chain as a quiet idle state

### P0-005 Human-assist can appear to disappear immediately after acceptance

- **Status:** confirmed
- **Severity:** medium-high
- **Primary files:**
  - [runtime_center_routes_core.py](/D:/word/copaw/src/copaw/app/routers/runtime_center_routes_core.py)
  - [human_assist_task_service.py](/D:/word/copaw/src/copaw/state/human_assist_task_service.py)
  - [ChatHumanAssistPanel.tsx](/D:/word/copaw/console/src/pages/Chat/ChatHumanAssistPanel.tsx)
- **Key functions:**
  - `_resume_human_assist_task(...)`
  - `mark_resume_queued(...)`
  - `get_current_human_assist_task(...)`
  - `refreshCurrentTask()`
- **What is happening:**
  - once a human-assist task is accepted and queued for resume, its status moves
    to `resume_queued`
  - current-task lookup then stops exposing it as the "current" task
  - the chat panel interprets the resulting `404` as "no current task"
- **Why it matters:**
  - the underlying resume path may still be working
  - but the user sees the task disappear at the exact moment they expect
    continuity confirmation

### P0-009 Persisted main-brain commit state can leak into later pure-chat turns

- **Status:** confirmed
- **Severity:** high
- **Primary files:**
  - [main_brain_chat_service.py](/D:/word/copaw/src/copaw/kernel/main_brain_chat_service.py)
  - [runtime_chat_stream_events.py](/D:/word/copaw/src/copaw/app/runtime_chat_stream_events.py)
  - [conversations.py](/D:/word/copaw/src/copaw/app/runtime_center/conversations.py)
  - [useChatRuntimeState.ts](/D:/word/copaw/console/src/pages/Chat/useChatRuntimeState.ts)
  - [ChatCommitConfirmationCard.tsx](/D:/word/copaw/console/src/pages/Chat/ChatCommitConfirmationCard.tsx)
- **Key functions:**
  - `MainBrainChatService.execute_stream(...)`
  - `_build_sidecar_events(...)`
  - `RuntimeConversationFacade._get_persisted_main_brain_commit(...)`
  - `hydrateRuntimeSidecarState(...)`
- **What is happening:**
  - if the thread snapshot already contains a prior `phase2_commit`
  - and the new turn is only pure chat (`commit_deferred/no_commit_action`)
  - `MainBrainChatService.execute_stream(...)` restores the old persisted commit
    into `effective_commit_state`
  - that old state is then reattached to the request runtime and can be
    re-hydrated by chat surfaces
- **Why it matters:**
  - a new non-executing turn can still look like it carries an active committed
    or confirm-required writeback state from an earlier turn
  - this makes chat threads feel "sticky" in the wrong way: old durable commit
    truth bleeds into new conversational turns
- **Concrete audit evidence:**
  - local replay of "prior committed snapshot + new pure chat turn" produced:
    - final assistant text: `just chat this turn`
    - final request commit status: `committed`
    - final request record id: `truth-1`

### P0-010 Industry cockpit subchain cards can inherit overall carrier status and overstate work

- **Status:** confirmed
- **Severity:** medium-high
- **Primary files:**
  - [IndustryRuntimeCockpitPanel.tsx](/D:/word/copaw/console/src/pages/Industry/IndustryRuntimeCockpitPanel.tsx)
  - [pageHelpers.tsx](/D:/word/copaw/console/src/pages/Industry/pageHelpers.tsx)
- **Key functions:**
  - `IndustryRuntimeCockpitPanel(...)`
  - `deriveIndustryTeamStatus(...)`
- **What is happening:**
  - several cockpit subchain nodes fall back to `detail.status` when the
    specific sub-surface has no focused item and no first item
  - examples include backlog, assignment, report, lane, environment, and
    evidence cards
  - `deriveIndustryTeamStatus(...)` also falls back to `detail.status`
- **Why it matters:**
  - the page can show an "active" or otherwise healthy status badge for a
    subchain even when the subchain currently has `0` items
  - this masks whether there is actually:
    - no assignment yet
    - no backlog yet
    - no report yet
    - or only a healthy top-level carrier with empty internals
- **Product effect:**
  - operators can misread an active carrier as active execution when a
    particular subchain is still empty

### P0-011 Chat top-bar lifecycle ignores `commit_deferred`

- **Status:** confirmed
- **Severity:** medium
- **Primary files:**
  - [runtimeTransport.ts](/D:/word/copaw/console/src/pages/Chat/runtimeTransport.ts)
  - [runtimeSidecarEvents.ts](/D:/word/copaw/console/src/pages/Chat/runtimeSidecarEvents.ts)
  - [ChatRuntimeSidebar.tsx](/D:/word/copaw/console/src/pages/Chat/ChatRuntimeSidebar.tsx)
- **Key functions:**
  - `resolveRuntimeLifecycleState(...)`
  - `consumeRuntimeSidecarEvent(...)`
  - `reduceRuntimeSidecarEvent(...)`
- **What is happening:**
  - the backend can emit `runtime.sidecar` events with terminal event
    `commit_deferred`
  - the chat sidecar reducer supports `deferred`
  - but the top-bar lifecycle mapping in `runtimeTransport.ts` does not handle
    `commit_deferred`
- **Why it matters:**
  - the main chat state can know the turn ended in a deferred durable state
  - while the top bar remains on an earlier optimistic phase such as accepted,
    reply-done, or commit-started
- **Product effect:**
  - the UI splits into two truths:
    - the confirmation card can show deferred
    - the top lifecycle strip does not
  - this weakens operator understanding of whether work truly started or only
    got delayed/deferred

### P0-012 `dispatch_deferred` is not exposed as a unified first-class runtime state across surfaces

- **Status:** confirmed
- **Severity:** medium-high
- **Primary files:**
  - [service_lifecycle.py](/D:/word/copaw/src/copaw/industry/service_lifecycle.py)
  - [query_execution_prompt.py](/D:/word/copaw/src/copaw/kernel/query_execution_prompt.py)
  - [actorPulse.ts](/D:/word/copaw/console/src/pages/RuntimeCenter/actorPulse.ts)
  - [IndustryRuntimeCockpitPanel.tsx](/D:/word/copaw/console/src/pages/Industry/IndustryRuntimeCockpitPanel.tsx)
- **Key functions:**
  - `apply_execution_chat_writeback(...)`
  - `_build_chat_writeback_lines(...)`
  - `resolveRuntimeAssignment(...)`
- **What is happening:**
  - the writeback path computes explicit deferred-routing truth via
    `dispatch_deferred`
  - that specific flag is consumed most directly by prompt text generation in
    `_build_chat_writeback_lines(...)`
  - other durable signals such as staffing/seat-gap truth do exist, but they are
    not exposed as one unified runtime state that all surfaces render the same
    way
- **Why it matters:**
  - the operator can get one textual reply explaining:
    - work was recorded
    - staffing/routing is still pending
  - but that same truth is not durably projected as one dedicated visible
    runtime state after refresh or page switch
- **Product effect:**
  - "recorded but not yet staffed/dispatched" is not treated as a first-class
    product status
  - this makes deferred execution easier to misread as either:
    - successful start
    - or empty/idle state
  - depending on which surface the operator opens next

### P0-013 Runtime Center automation summary can overstate active progress from paused schedules

- **Status:** confirmed
- **Severity:** medium-high
- **Primary files:**
  - [overview_cards.py](/D:/word/copaw/src/copaw/app/runtime_center/overview_cards.py)
- **Key functions:**
  - `_build_main_brain_automation_payload(...)`
- **What is happening:**
  - the top-level automation status becomes `active` whenever `schedule_count > 0`
  - that condition uses total visible schedules, not `active_schedule_count`
  - so a repo state with:
    - only paused schedules
    - zero running loops
    - idle/non-degraded supervisor
    can still be summarized as active automation
- **Why it matters:**
  - the Runtime Center can make automation look alive simply because schedules
    exist in storage
  - this overstates whether the system is currently progressing autonomous work
- **Product effect:**
  - operators can misread "configured automation exists" as
    "automation is currently advancing work"

### P0-014 Runtime Center capability-candidate pack projection resolves runtime layers by role id instead of agent id

- **Status:** confirmed
- **Severity:** medium-high
- **Primary files:**
  - [state_query.py](/D:/word/copaw/src/copaw/app/runtime_center/state_query.py)
  - [agent_profile_service.py](/D:/word/copaw/src/copaw/kernel/agent_profile_service.py)
  - [service_recommendations.py](/D:/word/copaw/src/copaw/predictions/service_recommendations.py)
- **Key functions:**
  - `_candidate_active_pack_composition(...)`
  - `get_agent_detail(...)`
- **What is happening:**
  - Runtime Center candidate projection reads `target_role_id`
  - then calls `get_agent_detail(target_role_id)`
  - but `get_agent_detail(...)` expects an `agent_id`
  - candidate/recommendation payloads already carry `target_agent_id`, but this
    read path ignores it
- **Why it matters:**
  - candidate/trial read-models can return empty or incorrect runtime capability
    layers even when the target execution seat actually has a live capability
    attachment
  - this weakens visibility for:
    - active trial membership
    - current pack composition
    - whether rollout really reached the intended seat
- **Product effect:**
  - Runtime Center can under-report capability rollout/trial attachment and make
    an actually attached candidate look inactive

### P0-015 Capability Market success can mean inventory-only install, not runtime attachment

- **Status:** confirmed
- **Severity:** medium-high
- **Primary files:**
  - [index.tsx](/D:/word/copaw/console/src/pages/CapabilityMarket/index.tsx)
  - [capabilityMarket.ts](/D:/word/copaw/console/src/api/modules/capabilityMarket.ts)
  - [capability_market.py](/D:/word/copaw/src/copaw/app/routers/capability_market.py)
- **Key functions / flows:**
  - `installCuratedSkill(...)`
  - `installProject(...)`
  - `handleInstallTemplate(...)`
  - `_assign_capabilities_to_agents(...)`
  - `install_market_hub_skill(...)`
  - `install_market_curated_skill(...)`
  - `install_market_project_donor(...)`
- **What is happening:**
  - the frontend install actions for:
    - curated skills
    - project donors
    - install templates
    submit install requests without `target_agent_id(s)` by default
  - backend capability assignment is optional and only happens when explicit
    target agents are provided
  - the page still surfaces the result as a generic install success
- **Why it matters:**
  - the operator can believe "this capability is now usable"
  - while the real result is only "this capability now exists in global
    inventory/config"
- **Product effect:**
  - this is a direct path to "installed but not actually usable by the
    execution seat", which then makes later execution failures feel
    inconsistent or opaque

### P0-017 Project-donor install accepted state is reported as final success and no job truth is surfaced

- **Status:** confirmed
- **Severity:** high
- **Primary files:**
  - [index.tsx](/D:/word/copaw/console/src/pages/CapabilityMarket/index.tsx)
  - [capabilityMarket.ts](/D:/word/copaw/console/src/api/modules/capabilityMarket.ts)
  - [capability_market.py](/D:/word/copaw/src/copaw/app/routers/capability_market.py)
- **Key functions / flows:**
  - `installProject(...)`
  - `installCapabilityMarketProject(...)`
  - `install_market_project_donor(...)`
  - `get_market_project_install_job(...)`
  - `get_market_project_install_job_result(...)`
- **What is happening:**
  - backend project install is explicitly asynchronous:
    - `POST /capability-market/projects/install`
    - returns `202 Accepted`
    - response model `CapabilityMarketProjectInstallAcceptedResponse`
    - includes `task_id` plus status/result routes
  - frontend still types that same call as final
    `CapabilityMarketProjectInstallResponse`
  - `installProject(...)` immediately shows `message.success("安装成功")`
    and refreshes the page
  - no frontend path polls the returned install-job routes
- **Why it matters:**
  - a project donor can still be:
    - queued
    - running
    - blocked
    - failed
  - while the UI has already claimed success
  - final truth such as:
    - verified stage
    - trial attachment
    - probe result
    - install failure
    never becomes the first-class product outcome
- **Product effect:**
  - heavy donor installs can fail later while the operator already saw
    "installed successfully"
  - project donor onboarding therefore overstates completion and weakens trust in
    external capability rollout

### P0-018 Runtime Center environment cockpit can default to "环境已就绪" without real environment truth

- **Status:** confirmed
- **Severity:** medium-high
- **Primary files:**
  - [runtimeEnvironmentSections.tsx](/D:/word/copaw/console/src/pages/RuntimeCenter/runtimeEnvironmentSections.tsx)
- **Key functions:**
  - `buildRuntimeEnvironmentCockpitSignals(...)`
- **What is happening:**
  - the environment cockpit signal resolves its value as:
    - environment source text
    - or governance summary
    - or literal fallback `"环境已就绪"`
  - this means the UI can show a positive-ready label even when there is:
    - no concrete environment source
    - no host-twin continuity proof
    - no explicit governance detail supporting readiness
- **Why it matters:**
  - environment continuity is one of the core conditions for true execution
  - defaulting missing truth into a ready-looking summary overstates actual
    execution readiness
- **Product effect:**
  - the Runtime Center can visually imply "environment ready" during exactly the
    situations where the environment chain is missing, unwired, or still not
    formally attached

### P0-019 Skill onboarding trial can pass on `describe` without real execution

- **Status:** confirmed
- **Severity:** medium-high
- **Primary files:**
  - [acquisition_runtime.py](/D:/word/copaw/src/copaw/learning/acquisition_runtime.py)
- **Key functions:**
  - `_run_capability_trial_check(...)`
- **What is happening:**
  - for `skill:` capabilities, onboarding trial does not execute a real business
    action
  - it resolves the executor and calls `executor(action="describe")`
  - if that tool-description call succeeds, the trial result can be marked as
    passed
- **Why it matters:**
  - "describe works" is not the same thing as:
    - skill is actionable
    - skill can execute a real task
    - skill can survive runtime context and produce evidence
- **Product effect:**
  - capability onboarding can report a successful trial even though no
    real-world task execution was proven
  - this weakens the truth value of "trial passed" for newly attached skills

### P0-020 Patch lifecycle evidence is emitted but not attached back to patch truth

- **Status:** confirmed
- **Severity:** medium-high
- **Primary files:**
  - [runtime_core.py](/D:/word/copaw/src/copaw/learning/runtime_core.py)
  - [patch_runtime.py](/D:/word/copaw/src/copaw/learning/patch_runtime.py)
  - [engine.py](/D:/word/copaw/src/copaw/learning/engine.py)
  - [runtime_center_routes_actor.py](/D:/word/copaw/src/copaw/app/routers/runtime_center_routes_actor.py)
- **Key functions:**
  - `_append_patch_evidence(...)`
  - `approve_patch(...)`
  - `reject_patch(...)`
  - `apply_patch(...)`
  - `rollback_patch(...)`
  - `get_patch_detail(...)`
- **What is happening:**
  - patch lifecycle actions append ledger evidence and `_append_patch_evidence(...)`
    returns the new evidence id
  - callers ignore that returned evidence id
  - patch objects stored by the engine are not updated with the new
    `source_evidence_id` / `evidence_refs`
  - patch detail read-model then loads evidence only from:
    - `patch.source_evidence_id`
    - `patch.evidence_refs`
- **Why it matters:**
  - lifecycle evidence for:
    - approval
    - rejection
    - apply
    - rollback
    can exist in the ledger but still be absent from the patch's own detail view
- **Product effect:**
  - patch read surfaces can under-report their real lifecycle proof
  - the audit trail becomes fragmented: evidence exists, but patch truth does
    not formally point to it

### P0-021 Agent Workbench performance tab is global, not scoped to the selected agent

- **Status:** confirmed
- **Severity:** medium
- **Primary files:**
  - [index.tsx](/D:/word/copaw/console/src/pages/AgentWorkbench/index.tsx)
  - [AgentReports.tsx](/D:/word/copaw/console/src/pages/AgentWorkbench/AgentReports.tsx)
  - [runtime_center_routes_actor.py](/D:/word/copaw/src/copaw/app/routers/runtime_center_routes_actor.py)
- **Key functions / flows:**
  - `AgentGrowthTrajectory()`
  - `useReportData()`
  - `list_growth(...)`
  - `list_proposals(...)`
  - `list_patches(...)`
- **What is happening:**
  - the workbench page is explicitly focused on a selected execution seat / agent
  - but the performance tab fetches:
    - `/runtime-center/learning/growth`
    - `/runtime-center/learning/proposals`
    - `/runtime-center/learning/patches`
    - `/runtime-center/evidence`
    without passing any `agent_id`
  - daily/weekly reports are agent-scoped, but the performance tab is not
- **Why it matters:**
  - the user can enter one agent's workbench and see global system learning
    items as if they belonged to that agent
- **Product effect:**
  - performance/growth attribution becomes misleading
  - a selected agent can appear to have patches, proposals, or evidence that
    actually belong to other agents or the system as a whole

### P0-006 Runtime conversation reload could drop durable query-runtime commit truth

- **Status:** confirmed
- **Severity:** high
- **Primary files:**
  - [conversations.py](/D:/word/copaw/src/copaw/app/runtime_center/conversations.py)
  - [main_brain_chat_service.py](/D:/word/copaw/src/copaw/kernel/main_brain_chat_service.py)
  - [query_execution_runtime.py](/D:/word/copaw/src/copaw/kernel/query_execution_runtime.py)
- **What was happening:**
  - query-runtime durable commit truth could persist only under
    `query_runtime_state.commit_outcome`
  - conversation reload meta previously only read `main_brain.phase2_commit`
  - after refresh, the same control thread could therefore lose the durable
    commit state that was visible during the live stream
- **Why it mattered:**
  - this created a real cross-surface split path:
    - live sidecars could show the durable execution outcome
    - conversation reload could show no durable commit at all
- **Current round outcome:**
  - reproduced with explicit reload coverage
  - fixed by teaching Runtime Conversation reload to fall back to
    `query_runtime_state.commit_outcome` when `phase2_commit` is absent

### P0-008 Symbolic `environment_ref` could count as active continuity without live proof

- **Status:** confirmed
- **Severity:** medium-high
- **Primary files:**
  - [main_brain_environment_coordinator.py](/D:/word/copaw/src/copaw/kernel/main_brain_environment_coordinator.py)
  - [turn_executor.py](/D:/word/copaw/src/copaw/kernel/turn_executor.py)
- **What was happening:**
  - `MainBrainEnvironmentCoordinator` can legally emit
    `continuity_source="environment-ref"` with `resume_ready=False`
  - `KernelTurnExecutor._request_has_active_confirmation_or_continuity(...)`
    previously treated any continuity token as active continuity proof
  - that meant a symbolic environment reference could force resume/verify shells
    into orchestration behavior before a live session was actually attached
- **Why it mattered:**
  - resume routing could over-trust symbolic environment identifiers
  - the operator-facing behavior looked more continuous than the environment
    contract actually was
- **Current round outcome:**
  - reproduced with explicit auto-mode coverage
  - fixed by requiring either:
    - explicit continuity proof
    - or live `resume_ready`
    before continuity is treated as active

### P0-016 Startup recovery could infer live capability intent from legacy allowlists

- **Status:** confirmed
- **Severity:** medium
- **Primary files:**
  - [startup_recovery.py](/D:/word/copaw/src/copaw/app/startup_recovery.py)
- **What was happening:**
  - when `capability_layers` were absent, startup recovery treated
    `allowed_capabilities` as a successful runtime capability projection
  - that projection was then used to infer `requested_surfaces` and requeue
    legacy execution-core chat writeback gaps
- **Why it mattered:**
  - legacy design-time allowlists are weaker truth than current runtime
    capability layers
  - startup recovery could therefore reopen routing/capability gaps based on
    weaker evidence than the current contract allows
- **Current round outcome:**
  - reproduced at both surface-detection and startup-recovery levels
  - fixed by making recovery fail closed when formal `capability_layers` are
    absent or invalid

---

## 2. Final Seam Closure

### P0-007 Buddy carrier helper may over-canonicalize control thread continuity

- **Status:** confirmed
- **Severity:** medium
- **Primary files:**
  - [buddy_execution_carrier.py](/D:/word/copaw/src/copaw/kernel/buddy_execution_carrier.py)
  - [buddy_domain_capability_growth.py](/D:/word/copaw/src/copaw/kernel/buddy_domain_capability_growth.py)
  - [buddy_projection_service.py](/D:/word/copaw/src/copaw/kernel/buddy_projection_service.py)
- **Key function:**
  - `build_buddy_execution_carrier_handoff(...)`
- **What was happening:**
  - when `instance_id` existed, the helper always derived
    `industry-chat:{instance_id}:execution-core`
  - an explicit stored `control_thread_id` was ignored even when the active
    domain record already carried continuity truth
- **Why it matters:**
  - a legacy active domain can legitimately carry:
    - blank `industry_instance_id`
    - non-empty historical `control_thread_id`
  - `BuddyDomainCapabilityGrowthService._backfill_legacy_binding(...)` will then
    backfill the instance id while preserving the stored thread id
  - `BuddyProjectionService.build_chat_surface(...)` could therefore expose an
    `execution_carrier.control_thread_id` that differed from the persisted
    active-domain `control_thread_id`
  - this creates split-brain continuity truth between the domain record and the
    carrier handed back to chat/runtime surfaces
- **Current round outcome:**
  - reproduced with explicit legacy-backfill coverage
  - fixed by preserving an explicit `control_thread_id` in the carrier handoff
    and only deriving canonical thread ids when the field is actually missing

---

## 3. Current Count

### Confirmed

- `21` issues

### Probable

- `0` issues

### Total currently recorded

- `21` issues

This count is provisional and should grow only when new issues are tied to
concrete files and chains.

---

## 4. Next Audit Focus

The next most valuable audit passes should target:

1. which execution-ready instructions should bypass backlog-first handling
2. whether frontend sidecar phases overstate true execution start
3. whether Chat / Runtime Center / Industry surfaces expose the same
   materialized assignment truth
4. whether environment/capability readiness is sometimes reported earlier than
   executable readiness
5. whether top-level chat/runtime status surfaces replay stale durable commit
   truth across later pure-chat turns
6. whether capability-market inventory/install surfaces clearly distinguish:
   - globally installed
   - seat attached
   - actually execution-ready

Until those are checked, the repo should not be described as fully closed on the
runtime front door.
