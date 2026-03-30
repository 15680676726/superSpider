# Truth-First No-Vector Memory Design

## Summary
CoPaw should stop treating vector-style retrieval as part of its formal memory architecture. The current repo already has a stronger memory truth source than generic semantic search: canonical `state / evidence` objects such as `StrategyMemory`, `Assignment`, `AgentReport`, `WorkContext`, `EnvironmentMount`, `SessionMount`, `EvidenceRecord`, and `Patch`. What remains is a split memory stack: the formal runtime recall path still mixes in local hashed-vector scoring and bootstraps an optional QMD sidecar, while the older `MemoryManager` path still emits embedding/vector health warnings for resident agents. This design hard-cuts memory to a truth-first model: memory becomes a derived read layer over canonical runtime truth, and all vector/embedding/QMD dependencies leave the formal product path.

## Current Facts
1. The formal runtime recall service defaults to `hybrid-local`, not to external embeddings or QMD.
2. `hybrid-local` is still not truly non-vector; it mixes lexical scoring with local `hashed_vector()` scoring.
3. QMD is not the default backend, but it is still bootstrapped, listed, warmed, and surfaced as a health concern.
4. A separate legacy `MemoryManager` still starts in the runtime host and produces embedding/vector warnings even when the formal runtime memory chain does not rely on embeddings.
5. The product now needs memory to serve long-running execution truth, not exploratory document similarity.

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

## Hard-Cut Plan

### Phase 1: Remove Vector Noise and False Dependencies
Goal: stop operator/runtime surfaces from pretending embeddings or QMD are expected.

Changes:
1. Stop default bootstrapping of `QmdRecallBackend`.
2. Remove QMD from formal runtime/system health checks.
3. Remove vector/embedding readiness checks from operator-facing health surfaces.
4. Stop treating `MemoryManager` embedding gaps as runtime warnings.
5. Keep runtime recall alive with lexical/scope/relation scoring only.

Acceptance:
- starting CoPaw without any embedding config produces no memory-vector warning,
- no runtime surface reports `memory_qmd_sidecar`,
- recall and prompt injection still work.

### Phase 2: Finish Truth-First Memory
Goal: remove all remaining vector assumptions and make profile/latest/history formal.

Changes:
1. Add `MemoryProfileService`.
2. Extend `MemoryFactIndexRecord` with evolution fields.
3. Add `MemoryEpisodeViewRecord`.
4. Delete local vector scoring and `hashed_vector()`.
5. Remove `local-vector`, `qmd`, and `lancedb` from formal backend semantics.
6. Remove QMD implementation files and related runtime wiring.
7. Shrink or retire legacy `MemoryManager` responsibilities until only non-vector conversation compaction remains, or split compaction out of it completely.

Acceptance:
- the formal runtime memory chain contains no vector backend or sidecar,
- main-brain memory injection is profile-first,
- latest/history/temporary semantics are visible and test-covered.

## Deletion Ledger
End-state deletions should include:
- `src/copaw/memory/qmd_backend.py`
- `src/copaw/memory/qmd_bridge_server.mjs`
- QMD bootstrap wiring in `src/copaw/app/runtime_bootstrap_query.py`
- vector and embedding health checks in `src/copaw/app/runtime_health_service.py`
- `memory_qmd_sidecar` system check in `src/copaw/app/routers/system.py`
- `local-vector` and hashed-vector scoring paths in `src/copaw/memory/recall_service.py`
- `hashed_vector()` in `src/copaw/memory/derived_index_service.py`
- embedding/vector runtime warning logic in `src/copaw/agents/memory/memory_manager.py`

These deletions are part of the delivery, not optional cleanup.

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
Once implementation starts, update:
- `TASK_STATUS.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`
- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`

The updated wording must explicitly state that formal memory no longer depends on vector backends or embedding configuration.

## Recommendation
Proceed with a two-stage hard-cut:
1. immediately remove QMD/vector/embedding runtime noise,
2. then complete the truth-first memory model and delete hashed-vector scoring.

This preserves stability while still ending at a fully no-vector formal memory architecture.
