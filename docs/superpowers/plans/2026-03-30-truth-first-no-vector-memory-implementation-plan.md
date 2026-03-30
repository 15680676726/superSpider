# Truth-First No-Vector Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace CoPaw's split memory stack with a single truth-first, no-vector formal memory system, remove QMD/vector/embedding runtime dependencies, and retire the old runtime `MemoryManager` path after extracting private conversation compaction into a dedicated service.

**Architecture:** Keep canonical `state / evidence / runtime` objects as the only truth source, then derive formal memory views (`profile`, latest facts, episodes, history). First hard-cut operator/runtime noise and the old runtime memory dependency, then land the additive state/schema changes, then switch all runtime consumers to profile-first recall. This preserves runtime stability while still ending at a fully no-vector formal memory architecture.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite state repositories, pytest

---

## Migration Strategy

- Existing SQLite databases must remain bootable throughout the rollout.
- Schema changes in `src/copaw/state/store.py` must be additive and idempotent first: add nullable/new columns and new tables before any code relies on them.
- Existing `memory_fact_index` rows are treated as legacy facts:
  - default `memory_type='fact'`
  - default `relation_kind='references'`
  - default `is_latest=1`
  - `valid_from` falls back to `created_at`
  - `expires_at` stays null
- New profile/episode views are rebuildable projections, so no irreversible row-by-row backfill is required; `rebuild_all()` becomes the canonical materialization path after schema upgrade.
- Rollback safety:
  - Phase 1 removes QMD/vector/operator noise and the old runtime dependency without requiring the new schema
  - Phase 2 starts using new columns only after additive schema tests and rebuild coverage pass
- Acceptance for migration:
  - opening an older on-disk DB under the new code does not crash
  - rebuild/materialization on old rows succeeds
  - repeated store initialization is idempotent

## File Map

- Modify: `src/copaw/app/runtime_bootstrap_query.py`
  - Stop default QMD bootstrap and expose a no-vector formal recall contract.
- Modify: `src/copaw/app/runtime_service_graph.py`
  - Remove QMD prewarm/backends logic and thread the new memory services through the runtime graph.
- Modify: `src/copaw/app/runtime_health_service.py`
  - Delete vector/embedding runtime health checks.
- Modify: `src/copaw/app/routers/system.py`
  - Delete QMD sidecar operator health surface.
- Modify: `src/copaw/memory/models.py`
  - Remove vector backend contract from the formal memory API.
- Create: `src/copaw/memory/conversation_compaction_service.py`
  - Isolate private compaction/scratch handling from legacy runtime memory.
- Modify: `src/copaw/app/runtime_host.py`
  - Stop default startup of the legacy `MemoryManager`; host the new compaction service instead.
- Modify: `src/copaw/kernel/turn_executor.py`
  - Pass conversation compaction service rather than a legacy runtime memory manager.
- Modify: `src/copaw/kernel/query_execution_runtime.py`
  - Stop depending on the old runtime `MemoryManager` path.
- Modify: `src/copaw/agents/react_agent.py`
  - Use private compaction service without reintroducing a second formal memory runtime.
- Modify: `src/copaw/agents/memory/memory_manager.py`
  - Strip embedding/vector warning logic from the formal runtime path as part of retirement.
- Modify: `src/copaw/agents/tools/memory_search.py`
  - Keep behavior aligned with the private compaction runtime rather than a formal shared memory system.
- Modify: `src/copaw/state/models_memory.py`
  - Extend fact records with truth-first evolution fields and add profile/episode view records.
- Modify: `src/copaw/state/store.py`
  - Add/adjust SQLite schema for new memory fields and new view tables.
- Modify: `src/copaw/state/repositories/sqlite_memory.py`
  - Persist new truth-first memory records and views.
- Create: `src/copaw/memory/precedence.py`
  - Shared precedence resolver and latest/history selection rules.
- Create: `src/copaw/memory/profile_service.py`
  - Build `MemoryProfile` and episode/history projections from canonical truth.
- Modify: `src/copaw/memory/derived_index_service.py`
  - Materialize truth-first records and remove local hashed-vector helpers.
- Modify: `src/copaw/memory/recall_service.py`
  - Convert runtime recall to profile/latest/lexical-scope-relation recall only.
- Modify: `src/copaw/memory/retain_service.py`
  - Ensure retained runtime facts produce truth-first entries/profile inputs.
- Modify: `src/copaw/memory/__init__.py`
  - Export new services and remove retired vector-specific exports.
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
  - Register the new memory services in bootstrap dataclasses.
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
  - Pass truth-first memory services into main-brain/query services.
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
  - Remove backend surface, add profile/episodes/history endpoints, keep rebuild/reflect/index/recall.
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
  - Switch pure chat recall injection to profile-first memory consumption.
- Modify: `src/copaw/kernel/query_execution_prompt.py`
  - Switch prompt recall to profile/latest facts first, lexical fallback second.
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- Test: `tests/app/test_runtime_bootstrap_helpers.py`
- Test: `tests/app/test_system_api.py`
- Test: `tests/test_memory_compaction_hook.py`
- Test: `tests/kernel/test_turn_executor.py`
- Test: `tests/agents/test_memory_manager_config.py`
- Test: `tests/agents/test_memory_manager_model_refresh.py`
- Test: `tests/state/test_truth_first_memory_state.py`
- Test: `tests/state/test_truth_first_memory_recall.py`
- Test: `tests/app/test_runtime_center_memory_api.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/kernel/test_memory_recall_integration.py`

### Task 1: Hard-Cut Vector/QMD Runtime Noise

**Files:**
- Modify: `src/copaw/app/runtime_bootstrap_query.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_health_service.py`
- Modify: `src/copaw/app/routers/system.py`
- Modify: `src/copaw/memory/models.py`
- Test: `tests/app/test_runtime_bootstrap_helpers.py`
- Test: `tests/app/test_system_api.py`

- [ ] **Step 1: Write the failing hard-cut tests**

Add tests for:
- no default QMD bootstrap
- no `memory_qmd_sidecar`
- no `memory_vector_ready`
- no `memory_embedding_config`
- default memory recall contract no longer advertises vector/QMD as formal runtime choices

- [ ] **Step 2: Run the hard-cut tests to verify they fail**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/app/test_runtime_bootstrap_helpers.py tests/app/test_system_api.py -q`
Expected: FAIL because QMD/vector/embedding runtime surfaces are still present.

- [ ] **Step 3: Implement the minimal runtime noise hard-cut**

Required outcome:
- runtime bootstrap stops default QMD creation
- runtime health and system surfaces stop exposing vector/QMD readiness
- formal memory backend contract no longer treats vector/QMD as product runtime choices
- Deletion checklist:
  - remove `memory_qmd_sidecar`
  - remove memory vector/embedding health checks
  - remove default QMD bootstrap/prewarm path

- [ ] **Step 4: Run the hard-cut tests again**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/app/test_runtime_bootstrap_helpers.py tests/app/test_system_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/runtime_bootstrap_query.py src/copaw/app/runtime_service_graph.py src/copaw/app/runtime_health_service.py src/copaw/app/routers/system.py src/copaw/memory/models.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_system_api.py
git commit -m "refactor: hard-cut vector memory runtime noise"
```

### Task 2: Retire Legacy Runtime Memory And Extract Private Compaction

**Files:**
- Create: `src/copaw/memory/conversation_compaction_service.py`
- Modify: `src/copaw/app/runtime_host.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/agents/react_agent.py`
- Modify: `src/copaw/agents/memory/memory_manager.py`
- Modify: `src/copaw/agents/tools/memory_search.py`
- Test: `tests/test_memory_compaction_hook.py`
- Test: `tests/kernel/test_turn_executor.py`
- Test: `tests/agents/test_memory_manager_config.py`
- Test: `tests/agents/test_memory_manager_model_refresh.py`

- [ ] **Step 1: Write the failing legacy-retirement tests**

Add tests for:
- runtime host starting without legacy `MemoryManager`
- private compaction state staying available via the new compaction service
- turn executor/query runtime no longer requiring the old runtime memory path
- old memory manager embedding/vector warnings no longer participating in normal runtime startup
- Deletion checklist:
  - `MemoryManager` stops being a runtime host dependency
  - no second formal runtime memory blob remains

- [ ] **Step 2: Run the legacy-retirement tests to verify they fail**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/test_memory_compaction_hook.py tests/kernel/test_turn_executor.py tests/agents/test_memory_manager_config.py tests/agents/test_memory_manager_model_refresh.py -q`
Expected: FAIL because compaction is still coupled to the legacy runtime memory path.

- [ ] **Step 3: Implement the minimal compaction extraction and retirement**

Required outcome:
- private compaction is handled by `ConversationCompactionService`
- runtime host no longer bootstraps `MemoryManager` as a formal runtime dependency
- agent/runtime plumbing uses the private compaction service rather than a second formal memory runtime

- [ ] **Step 4: Run the legacy-retirement tests again**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/test_memory_compaction_hook.py tests/kernel/test_turn_executor.py tests/agents/test_memory_manager_config.py tests/agents/test_memory_manager_model_refresh.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/memory/conversation_compaction_service.py src/copaw/app/runtime_host.py src/copaw/kernel/turn_executor.py src/copaw/kernel/query_execution_runtime.py src/copaw/agents/react_agent.py src/copaw/agents/memory/memory_manager.py src/copaw/agents/tools/memory_search.py tests/test_memory_compaction_hook.py tests/kernel/test_turn_executor.py tests/agents/test_memory_manager_config.py tests/agents/test_memory_manager_model_refresh.py
git commit -m "refactor: retire legacy runtime memory manager"
```

### Task 3: Truth-First State Schema And Storage

**Files:**
- Modify: `src/copaw/state/models_memory.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/sqlite_memory.py`
- Test: `tests/state/test_truth_first_memory_state.py`

- [ ] **Step 1: Write the failing state/storage tests**

Add tests for:
- fact record evolution fields (`memory_type`, `relation_kind`, `supersedes_entry_id`, `is_latest`, `valid_from`, `expires_at`, `confidence_tier`)
- profile and episode view persistence
- latest/history uniqueness expectations at repository level
- opening an older on-disk DB after schema change
- rebuild/materialization on legacy rows
- repeated schema initialization idempotency

- [ ] **Step 2: Run the state/storage tests to verify they fail**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/state/test_truth_first_memory_state.py -q`
Expected: FAIL because the schema/repositories do not yet support truth-first memory records and views.

- [ ] **Step 3: Implement the minimal state/schema/repository changes**

Required outcome:
- `MemoryFactIndexRecord` supports the new evolution fields
- new profile/episode records exist in state
- SQLite schema and repositories round-trip the new fields cleanly
- legacy DB rows remain readable and rebuildable

- [ ] **Step 4: Run the state/storage tests again**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/state/test_truth_first_memory_state.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/models_memory.py src/copaw/state/store.py src/copaw/state/repositories/sqlite_memory.py tests/state/test_truth_first_memory_state.py
git commit -m "feat: add truth-first memory state models"
```

### Task 4: No-Vector Recall Core And Shared Memory Views

**Files:**
- Modify: `src/copaw/memory/derived_index_service.py`
- Modify: `src/copaw/memory/recall_service.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `src/copaw/memory/__init__.py`
- Create: `src/copaw/memory/precedence.py`
- Create: `src/copaw/memory/profile_service.py`
- Test: `tests/state/test_truth_first_memory_recall.py`

- [ ] **Step 1: Write the failing memory-core tests**

Add tests for:
- profile derivation from strategy/report/evidence/work-context inputs
- precedence rules (`fact > inference`, evidence-backed facts win, temporary facts do not supersede durable facts)
- latest/history separation
- recall without `hashed_vector()` or sidecar backends
- profile/history views rebuilding from legacy rows after schema upgrade
- Deletion checklist:
  - no `hashed_vector()` in formal recall chain
  - no `local-vector`
  - no sidecar backend preparation for formal runtime recall

- [ ] **Step 2: Run the memory-core tests to verify they fail**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/state/test_truth_first_memory_recall.py -q`
Expected: FAIL because the memory core still exposes vector semantics and lacks profile/precedence services.

- [ ] **Step 3: Implement the minimal memory-core changes**

Required outcome:
- hashed-vector scoring is removed
- truth-first recall uses profile/latest/lexical-scope-relation
- shared precedence/profile services exist and are exported
- legacy rows still participate cleanly after rebuild

- [ ] **Step 4: Run the memory-core tests again**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/state/test_truth_first_memory_recall.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/memory/derived_index_service.py src/copaw/memory/recall_service.py src/copaw/memory/retain_service.py src/copaw/memory/__init__.py src/copaw/memory/precedence.py src/copaw/memory/profile_service.py tests/state/test_truth_first_memory_recall.py
git commit -m "feat: add truth-first memory recall core"
```

### Task 5: Runtime Consumers, Docs, And Final Regression

**Files:**
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- Test: `tests/app/test_runtime_center_memory_api.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/kernel/test_memory_recall_integration.py`

- [ ] **Step 1: Write the failing runtime/doc tests**

Add tests for:
- no `/runtime-center/memory/backends` formal surface
- profile and episode/history endpoints
- main-brain pure chat consuming profile/latest facts before lexical recall
- query execution prompts preferring work-context/profile/latest truth-first recall
- system/runtime docs reflecting truth-first no-vector memory wording
- Deletion checklist:
  - no product-facing backend chooser
  - no profile injection bypassing latest/history resolver

- [ ] **Step 2: Run the runtime/doc tests to verify they fail**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/app/test_runtime_center_memory_api.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_memory_recall_integration.py -q`
Expected: FAIL because runtime routes/consumers still expose old memory contracts.

- [ ] **Step 3: Implement the minimal runtime/doc changes**

Required outcome:
- runtime-center memory API exposes profile/history/episodes and no backend chooser
- main-brain and prompt consumers switch to truth-first recall order
- status/model/transition/masterplan docs reflect the no-vector formal memory architecture
- acceptance criteria match the spec wording for no-vector formal memory

- [ ] **Step 4: Run the runtime/doc tests and the final regression suite**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/app/test_runtime_bootstrap_helpers.py tests/app/test_system_api.py tests/test_memory_compaction_hook.py tests/kernel/test_turn_executor.py tests/agents/test_memory_manager_config.py tests/agents/test_memory_manager_model_refresh.py tests/state/test_truth_first_memory_state.py tests/state/test_truth_first_memory_recall.py tests/app/test_runtime_center_memory_api.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_memory_recall_integration.py -q`
Expected: PASS

- [ ] **Step 5: Run the focused runtime regressions**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_chat_media.py tests/app/test_phase_next_autonomy_smoke.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/app/runtime_bootstrap_models.py src/copaw/app/runtime_bootstrap_domains.py src/copaw/app/routers/runtime_center_routes_memory.py src/copaw/kernel/main_brain_chat_service.py src/copaw/kernel/query_execution_prompt.py TASK_STATUS.md DATA_MODEL_DRAFT.md API_TRANSITION_MAP.md COPAW_CARRIER_UPGRADE_MASTERPLAN.md tests/app/test_runtime_center_memory_api.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_memory_recall_integration.py
git commit -m "feat: finish truth-first no-vector memory rollout"
```
