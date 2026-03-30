# Truth-First No-Vector Memory Design

## Summary
CoPaw now treats vector-style retrieval as retired from the formal memory architecture. Canonical `state / evidence / runtime` objects such as `StrategyMemory`, `Assignment`, `AgentReport`, `WorkContext`, `EnvironmentMount`, `SessionMount`, `EvidenceRecord`, and `Patch` remain the only truth source, and formal memory is a derived read layer over that truth. QMD/vector references are now physically removed residuals, not pending runtime cleanup.

## Current Facts
1. The formal runtime recall chain is `truth-first` and `no-vector formal memory`.
2. Shared formal memory is derived from canonical `state / evidence / runtime`, then consumed as `profile + latest facts + episodes + history`.
3. QMD, embedding readiness, vector health, and hashed-vector scoring are no longer part of the formal runtime or operator contract.
4. Private conversation compaction remains separate from shared formal memory and does not become a second truth source.
5. Any remaining mentions of `QMD / local-vector / LanceDB / embedding health` are historical references only and must be treated as physically removed residuals.

## Design Goal
Build a formal memory architecture where:
- canonical runtime/state/evidence objects remain the only truth source,
- memory is a derived and rebuildable read model,
- the main-brain consumes `profile + latest facts + episodes + history`,
- no embedding model, vector backend, or sidecar is required for normal operation,
- vector health and QMD readiness disappear from operator-facing surfaces.

## Non-Goals
1. This design does not add a second memory database as a new truth source.
2. This design does not try to preserve generic semantic document search as a first-class runtime contract.
3. This design does not keep QMD or embedding support as a formal maturity target.
4. This design does not re-expand legacy `agent-chat / task-chat` memory semantics.

## Recommended Approach
Use a truth-first derived memory model with no vector dependency in the formal runtime chain.

Why this is better than keeping the current hybrid path:
- CoPaw's most important memory problem is "what is currently true", not "what text looks similar".
- Long-running autonomy needs `latest vs history`, `temporary vs durable`, and `supersedes/expiry` more than semantic distance.
- The current vector-related surfaces mostly add operational noise without being the canonical execution truth path.
- Removing vector assumptions simplifies local setup, startup health, and operator understanding.

## Supermemory Inspiration Boundary
This design does borrow from `supermemory`, but only at the memory-organization level.

Borrow:
- `profile` as a compact first read
- explicit memory evolution (`updates / supersedes / derives`)
- `latest` versus `history`
- forgetting / expiry for temporary memory

Do not borrow:
- `supermemory` as an external product dependency
- `supermemory` as a runtime truth source
- cloud-first or API-first memory ownership
- generic container/tag memory scope in place of CoPaw's canonical runtime scopes

The intended result is: learn from `supermemory`'s memory-shaping ideas, but keep CoPaw's truth inside canonical `state / evidence / runtime` objects.

## Target Architecture

### 1. Truth Layer
Formal truth remains in canonical objects only:
- `StrategyMemory`
- `OperatingLane`
- `BacklogItem`
- `OperatingCycle`
- `Assignment`
- `AgentReport`
- `WorkContext`
- `EnvironmentMount`
- `SessionMount`
- `EvidenceRecord`
- `DecisionRequest`
- `Patch`

No memory service may become a second writer of runtime truth.

### 2. Derived Memory Layer
Formal memory becomes a derived read layer with four product-level views:
- `MemoryProfile`
- `LatestMemoryFacts`
- `MemoryEpisodes`
- `MemoryHistory`

These views are rebuilt from canonical truth and are safe to re-materialize.

### 3. Evolution Layer
Each memory fact needs explicit evolution semantics:
- `memory_type`
- `relation_kind`
- `supersedes_entry_id`
- `derived_from_refs`
- `is_latest`
- `valid_from`
- `expires_at`
- `confidence_tier`

This replaces vague "semantic similarity" with explicit lifecycle and precedence.

### 4. Retrieval Layer
The formal retrieval order becomes:
1. `MemoryProfile`
2. latest facts in the current scope
3. recent related episodes
4. lexical/scope/relation recall

There is no vector path in the formal runtime contract.

## Formal Objects

### `MemoryProfileViewRecord`
Purpose: compact, directly consumable memory surface for the main-brain and runtime prompts.

Suggested fields:
- `scope_type`
- `scope_id`
- `static_profile`
- `dynamic_profile`
- `active_preferences`
- `active_constraints`
- `current_focus_summary`
- `current_operating_context`
- `updated_at`

Interpretation:
- `static_profile`: durable identity, role, mission, long-lived preferences
- `dynamic_profile`: recent current-state context that should evolve frequently

### `MemoryFactIndexRecord` Extensions
The existing fact index stays, but becomes explicitly truth-first:
- `memory_type`: `fact | preference | episode | temporary | inference`
- `relation_kind`: `updates | supersedes | derives | references`
- `supersedes_entry_id`
- `derived_from_refs`
- `is_latest`
- `valid_from`
- `expires_at`
- `confidence_tier`

### `MemoryEpisodeViewRecord`
Purpose: summarize continuous execution stretches instead of isolated text chunks.

Suggested fields:
- `episode_id`
- `scope_type`
- `scope_id`
- `headline`
- `summary`
- `entry_refs`
- `work_context_id`
- `control_thread_id`
- `started_at`
- `ended_at`

Example episodes:
- `report -> synthesis -> replan`
- `handoff -> human-assist -> resume`
- multi-cycle operating run with one shared `work_context_id`

### `MemoryRetentionPolicy`
Retention must be explicit:
- `fact`: long-lived unless superseded
- `preference`: supersedable, profile-eligible
- `episode`: keep summary and anchors; raw detail can be aged down
- `temporary`: must expire automatically
- `inference`: never treated as runtime truth by default

## Precedence Rules
Truth-first memory needs explicit conflict rules so implementers do not invent local heuristics.

Precedence order:
1. canonical state objects with explicit current ownership or active status
2. evidence-backed facts derived from canonical objects
3. applied decision/patch outcomes that explicitly mutate the state interpretation
4. durable summaries or profiles derived from the above
5. temporary memory
6. inference

Specific rules:
- `fact` beats `inference`
- evidence-backed `fact` beats non-evidence-backed `fact`
- `temporary` never supersedes a durable `fact`; it can only narrow current handling while it is active
- `preference` can supersede an older `preference`, but cannot override a hard runtime constraint
- `patch` and `decision` outcomes may invalidate or supersede older facts when their state/application status says so
- `is_latest=true` may only exist on one active record per `(scope_type, scope_id, memory_type, subject-key)` family
- `expires_at` removes a record from default recall/profile injection, but does not delete history
- if `StrategyMemory` and `AgentReport` disagree, the default interpretation is:
  - `StrategyMemory` remains the durable operating intent
  - `AgentReport` may supersede current runtime facts only when backed by fresher evidence or explicit processed synthesis
- if `EvidenceRecord` and derived `inference` disagree, `EvidenceRecord` wins

These rules must be enforced in one shared resolver, not copied into multiple consumers.

## Shared vs Private Memory Topology
Main-brain memory and working-agent memory should be partly shared and partly separated.

Shared memory:
- canonical truth-derived memory (`MemoryProfile`, latest facts, episodes, history)
- scope-bound runtime memory keyed by `industry / work_context / task / agent / global`
- any memory used for planning, governance, runtime continuity, report synthesis, and operator-visible audit

Private memory:
- per-agent conversation compaction state
- per-session scratch summaries
- non-canonical prompt-compression artifacts

Rule:
- shared memory is product memory and must be visible, rebuildable, and auditable
- private memory is prompt/runtime plumbing and must never become a second truth source

Implication:
- the main-brain and execution agents should read from the same shared truth-derived memory surface,
- but they should not share the same private scratchpad/compaction state.

This means the current direction is only partially reasonable:
- it is correct to keep the main-brain and working agents from sharing one opaque private memory blob,
- it is not correct to keep overlapping memory semantics split across unrelated systems.

The target architecture is:
- one shared formal memory system for truth-derived recall,
- separate lightweight private compaction state per runtime actor/session.

## Main-Brain Consumption Model
The main-brain should no longer start from "search memory hits".

It should consume memory in this order:
1. `MemoryProfile`
2. current-scope latest facts
3. current-scope episodes
4. lexical recall only when more detail is needed

This makes the first prompt context "current truth" instead of "similar text".

## API Direction

### Keep
- `GET /api/runtime-center/memory/recall`
- `GET /api/runtime-center/memory/index`
- `POST /api/runtime-center/memory/rebuild`
- `GET /api/runtime-center/memory/reflections`
- `POST /api/runtime-center/memory/reflect`

### Add
- `GET /api/runtime-center/memory/profiles`
- `GET /api/runtime-center/memory/profiles/{scope_type}/{scope_id}`
- `GET /api/runtime-center/memory/episodes`
- `GET /api/runtime-center/memory/history`

### Remove or Re-scope
- `GET /api/runtime-center/memory/backends`
  - no longer expose `qmd / local-vector / lancedb` as formal product choices
- any operator/system health item that implies vector readiness is a formal runtime dependency

## Implementation Closeout

The hard-cut is landed.

Completed outcomes:
1. Formal memory now exposes a `truth-first` and `no-vector formal memory` contract.
2. QMD bootstrap, vector backend semantics, embedding/vector runtime health, and hashed-vector scoring are removed from the formal runtime path.
3. Shared formal memory remains rebuildable from canonical truth and is consumed as `profile + latest facts + episodes + history`.
4. Private conversation compaction stays isolated from shared formal memory and is no longer allowed to masquerade as shared runtime truth.

Acceptance now reads as current fact:
- starting CoPaw without embedding configuration does not produce formal memory-vector warnings,
- no formal runtime surface reports `memory_qmd_sidecar`, vector readiness, or embedding readiness as required health,
- main-brain and runtime recall stay on the truth-derived path without QMD/vector dependencies.

## Deletion Ledger
Completed physical cleanup includes:
- `src/copaw/memory/qmd_backend.py`
- `src/copaw/memory/qmd_bridge_server.mjs`
- QMD bootstrap wiring in `src/copaw/app/runtime_bootstrap_query.py`
- vector and embedding health checks in `src/copaw/app/runtime_health_service.py`
- `memory_qmd_sidecar` system check in `src/copaw/app/routers/system.py`
- `local-vector` and hashed-vector scoring paths in `src/copaw/memory/recall_service.py`
- `hashed_vector()` in `src/copaw/memory/derived_index_service.py`
- embedding/vector runtime warning logic in `src/copaw/agents/memory/memory_manager.py`
- `MemoryManager` as a runtime host dependency once compaction had been split into a dedicated service

These are physically removed residuals, not open cleanup items.

## Testing
Required verification groups:
1. `profile derivation`
   - strategy/report/evidence/work-context facts produce stable profiles
2. `latest/history separation`
   - new facts correctly supersede old facts
3. `temporary expiry`
   - handoff/recovery/human-assist temporary memory ages out correctly
4. `main-brain memory consumption`
   - prompts consume profile/latest/episodes before lexical recall
5. `hard-cut regression`
   - industry/runtime/work-context/report/evidence recall remains intact without vector/QMD paths

## Documentation Sync
The synced docs must state:
- `TASK_STATUS.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`
- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`

The updated wording explicitly states that formal memory no longer depends on vector backends or embedding configuration and that QMD/vector references are physically removed residuals.

## Recommendation
Treat this design as the current canonical architecture: one shared truth-derived formal memory system plus separate private compaction state, with no vector path in the formal runtime contract.
