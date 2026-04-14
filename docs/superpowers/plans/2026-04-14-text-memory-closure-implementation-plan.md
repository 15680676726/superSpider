# Text Memory Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the formal text-memory system so CoPaw keeps only high-value truth-first memory, recalls it by stable scope priority and budget, and fully retires the legacy `MemoryManager` compatibility shell.

**Architecture:** Keep the current `truth-first + no-vector formal memory` foundation. Add one explicit text-memory policy layer for selective ingestion and scope routing, one explicit retrieval-budget layer for recall/activation, one canonical compaction path for repeated stable writes, and remove the old `agents/memory/memory_manager.py` compatibility shell so private conversation compaction stays private.

**Tech Stack:** Python, SQLite-backed state repositories, existing `memory / state / kernel / agents` modules, pytest.

---

## File Structure

### New files

- `src/copaw/memory/text_memory_policy.py`
  Purpose: One place for selective-ingestion decisions and formal scope routing for text memory writes.

- `src/copaw/memory/retrieval_budget.py`
  Purpose: One place for scope-priority ordering and recall/activation budget limits.

- `src/copaw/memory/canonical_compaction.py`
  Purpose: One place for formal long-term text-memory merge/dedupe/compaction rules.

### Modified files

- `src/copaw/memory/retain_service.py`
  Purpose: Route report/chat/routine retention through the new ingestion, routing, and compaction rules.

- `src/copaw/state/knowledge_service.py`
  Purpose: Preserve formal memory document behavior while supporting stable update/reuse semantics required by compaction.

- `src/copaw/memory/recall_service.py`
  Purpose: Enforce fixed scope priority and retrieval-budget limits in truth-first recall.

- `src/copaw/memory/activation_service.py`
  Purpose: Apply the same budget discipline to activation-layer recall so planner/runtime do not over-read.

- `src/copaw/memory/surface_service.py`
  Purpose: Keep Runtime Center memory read surfaces aligned with the new recall budget and private-compaction boundary.

- `src/copaw/agents/memory/__init__.py`
  Purpose: Remove `MemoryManager` export after compatibility retirement.

- `src/copaw/agents/react_agent.py`
  Purpose: Stop importing/typing the legacy `MemoryManager` shell and use `ConversationCompactionService` directly.

- `src/copaw/agents/command_handler.py`
  Purpose: Rename internal typing/boundary from memory-manager wording to conversation-compaction wording without changing user-facing commands.

- `src/copaw/agents/hooks/memory_compaction.py`
  Purpose: Update hook typing/contracts so the hook depends on compaction service behavior, not the retired alias shell.

- `src/copaw/app/runtime_commands.py`
  Purpose: Remove any remaining runtime-side alias wording that still treats private compaction as a “memory manager”.

- `tests/state/test_memory_services.py`
  Purpose: Lock selective ingestion, scope routing, recall priority, and canonical compaction behavior.

- `tests/state/test_knowledge_service.py`
  Purpose: Lock stable formal memory document routing and update semantics.

- `tests/memory/test_activation_service.py`
  Purpose: Lock activation-layer budget limits and scope-order recall behavior.

- `tests/memory/test_surface_service.py`
  Purpose: Lock Runtime Center read-surface boundary between truth-first memory and private compaction.

- `tests/kernel/test_memory_recall_integration.py`
  Purpose: Lock runtime/compiler consumers to the new bounded recall behavior.

- `tests/memory/test_conversation_compaction_service.py`
  Purpose: Keep private compaction behavior intact while retiring the old alias shell.

- `tests/test_memory_compaction_hook.py`
  Purpose: Update hook tests to target compaction service contracts instead of `MemoryManager`.

- `tests/kernel/test_query_execution_runtime.py`
  Purpose: Ensure runtime surfaces still expose private compaction visibility without reviving legacy alias paths.

- `tests/kernel/test_turn_executor.py`
  Purpose: Ensure runtime host and executor still only recognize `conversation_compaction_service`.

- `DATA_MODEL_DRAFT.md`
  Purpose: Record the final text-memory boundary, selective-ingestion rule, and `memory_manager` retirement.

- `TASK_STATUS.md`
  Purpose: Record what was actually implemented and which verification commands passed.

### Deleted files

- `src/copaw/agents/memory/memory_manager.py`
  Purpose: Retire the legacy compatibility shim.

## Task 1: Selective Ingestion Policy

**Files:**
- Create: `src/copaw/memory/text_memory_policy.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `tests/state/test_memory_services.py`

- [ ] **Step 1: Write the failing tests**

Add tests proving:
- low-value chat noise is rejected from formal memory
- stable report outcomes are retained
- work-context continuity writes route to `work_context` memory
- industry-level shared knowledge stays in `industry` scope

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/state/test_memory_services.py -q`
Expected: FAIL on missing selective-ingestion policy behavior.

- [ ] **Step 3: Write minimal implementation**

Implement `src/copaw/memory/text_memory_policy.py` with:
- a formal write decision function
- a formal scope-routing function
- fixed allow/deny categories for text memory

Wire `MemoryRetainService` to use the new policy before writing formal memory chunks.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/state/test_memory_services.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/memory/text_memory_policy.py src/copaw/memory/retain_service.py tests/state/test_memory_services.py
git commit -m "Add selective text memory ingestion policy"
```

## Task 2: Formal Scope Routing And Knowledge Write Semantics

**Files:**
- Modify: `src/copaw/state/knowledge_service.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `tests/state/test_knowledge_service.py`
- Modify: `tests/state/test_memory_services.py`

- [ ] **Step 1: Write the failing tests**

Add tests proving:
- formal text memory writes cannot silently drift to the wrong scope
- repeated writes with the same stable source can update/reuse a formal memory anchor
- work-context memory remains preferred over broader related scopes

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/state/test_knowledge_service.py tests/state/test_memory_services.py -q`
Expected: FAIL on missing stable routing/update behavior.

- [ ] **Step 3: Write minimal implementation**

Update `StateKnowledgeService` and `MemoryRetainService` so formal memory writes:
- respect routed scope only
- reuse stable chunk anchors where appropriate
- preserve readable `memory:{scope_type}:{scope_id}` document semantics

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/state/test_knowledge_service.py tests/state/test_memory_services.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/knowledge_service.py src/copaw/memory/retain_service.py tests/state/test_knowledge_service.py tests/state/test_memory_services.py
git commit -m "Stabilize formal text memory scope routing"
```

## Task 3: Retrieval Budget And Scope Priority

**Files:**
- Create: `src/copaw/memory/retrieval_budget.py`
- Modify: `src/copaw/memory/recall_service.py`
- Modify: `src/copaw/memory/activation_service.py`
- Modify: `src/copaw/memory/surface_service.py`
- Modify: `tests/memory/test_activation_service.py`
- Modify: `tests/memory/test_surface_service.py`
- Modify: `tests/kernel/test_memory_recall_integration.py`
- Modify: `tests/app/test_runtime_center_memory_api.py`

- [ ] **Step 1: Write the failing tests**

Add tests proving:
- recall uses fixed scope order `work_context -> task -> agent -> industry -> global`
- activation obeys bounded result limits instead of unbounded derived-view reads
- Runtime Center memory reads stay aligned with the new bounded recall behavior

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/memory/test_activation_service.py tests/memory/test_surface_service.py tests/kernel/test_memory_recall_integration.py tests/app/test_runtime_center_memory_api.py -q`
Expected: FAIL on missing budgeted recall behavior.

- [ ] **Step 3: Write minimal implementation**

Implement `src/copaw/memory/retrieval_budget.py` and wire it into recall/activation/surface paths so:
- recall budgets are explicit
- scope priority is shared
- current readers do not over-fetch

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/memory/test_activation_service.py tests/memory/test_surface_service.py tests/kernel/test_memory_recall_integration.py tests/app/test_runtime_center_memory_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/memory/retrieval_budget.py src/copaw/memory/recall_service.py src/copaw/memory/activation_service.py src/copaw/memory/surface_service.py tests/memory/test_activation_service.py tests/memory/test_surface_service.py tests/kernel/test_memory_recall_integration.py tests/app/test_runtime_center_memory_api.py
git commit -m "Bound truth-first memory recall and activation"
```

## Task 4: Canonical Compaction For Formal Text Memory

**Files:**
- Create: `src/copaw/memory/canonical_compaction.py`
- Modify: `src/copaw/memory/retain_service.py`
- Modify: `src/copaw/state/knowledge_service.py`
- Modify: `tests/state/test_memory_services.py`
- Modify: `tests/state/test_truth_first_memory_state.py`

- [ ] **Step 1: Write the failing tests**

Add tests proving:
- repeated low-value duplicates do not endlessly append formal memory
- repeated stable findings merge into canonical summary/anchor content
- formal memory compaction does not delete source-backed truth, only normalizes durable text memory

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/state/test_memory_services.py tests/state/test_truth_first_memory_state.py -q`
Expected: FAIL on missing compaction/merge behavior.

- [ ] **Step 3: Write minimal implementation**

Implement canonical compaction helpers and apply them to retained report/chat/routine writes so:
- duplicate stable writes are merged
- noisy repeated writes are suppressed
- canonical text-memory anchors stay readable and deterministic

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/state/test_memory_services.py tests/state/test_truth_first_memory_state.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/memory/canonical_compaction.py src/copaw/memory/retain_service.py src/copaw/state/knowledge_service.py tests/state/test_memory_services.py tests/state/test_truth_first_memory_state.py
git commit -m "Compact repeated formal text memory writes"
```

## Task 5: Retire Legacy MemoryManager Compatibility Shell

**Files:**
- Delete: `src/copaw/agents/memory/memory_manager.py`
- Modify: `src/copaw/agents/memory/__init__.py`
- Modify: `src/copaw/agents/react_agent.py`
- Modify: `src/copaw/agents/command_handler.py`
- Modify: `src/copaw/agents/hooks/memory_compaction.py`
- Modify: `src/copaw/app/runtime_commands.py`
- Modify: `tests/memory/test_conversation_compaction_service.py`
- Modify: `tests/test_memory_compaction_hook.py`
- Modify: `tests/kernel/test_query_execution_runtime.py`
- Modify: `tests/kernel/test_turn_executor.py`

- [ ] **Step 1: Write the failing tests**

Add/update tests proving:
- runtime/agent code depends directly on `ConversationCompactionService`
- no import/export path still requires `MemoryManager`
- private compaction commands/hooks still work after the alias shell is removed

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/memory/test_conversation_compaction_service.py tests/test_memory_compaction_hook.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_turn_executor.py -q`
Expected: FAIL on remaining `MemoryManager` references.

- [ ] **Step 3: Write minimal implementation**

Delete the compatibility shell and update call sites/tests to reference `ConversationCompactionService` directly.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/memory/test_conversation_compaction_service.py tests/test_memory_compaction_hook.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_turn_executor.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/agents/memory/__init__.py src/copaw/agents/react_agent.py src/copaw/agents/command_handler.py src/copaw/agents/hooks/memory_compaction.py src/copaw/app/runtime_commands.py tests/memory/test_conversation_compaction_service.py tests/test_memory_compaction_hook.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_turn_executor.py
git rm src/copaw/agents/memory/memory_manager.py
git commit -m "Retire legacy memory manager compatibility shell"
```

## Task 6: Docs And Final Verification

**Files:**
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Update docs**

Record:
- formal text-memory selective-ingestion boundary
- retrieval-budget and scope-priority rule
- `memory_manager` retirement
- verification commands that passed

- [ ] **Step 2: Run focused final verification**

Run:

```bash
python -m pytest tests/state/test_truth_first_memory_state.py tests/state/test_memory_services.py tests/state/test_knowledge_service.py tests/memory/test_activation_service.py tests/memory/test_surface_service.py tests/memory/test_conversation_compaction_service.py tests/kernel/test_memory_recall_integration.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_turn_executor.py tests/app/test_runtime_center_memory_api.py -q
```

Expected: PASS

- [ ] **Step 3: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: no diff format errors

- [ ] **Step 4: Commit**

```bash
git add DATA_MODEL_DRAFT.md TASK_STATUS.md
git commit -m "Document formal text memory closure"
```

