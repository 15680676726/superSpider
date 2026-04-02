# CC Discipline Runtime Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the proven runtime-discipline gaps by moving Runtime Center review state, capability execution policy, child-run MCP overlay lifecycle, and skill/package provenance discipline onto explicit typed contracts instead of heuristics or branch-local hardcoding.

**Architecture:** Keep CoPaw on its formal truth chain. Borrow Claude/CC discipline, not product shell: projection must read typed truth instead of inventing state, execution policy must come from declared capability contract instead of capability-id lists, child-run lifecycle must own additive MCP setup and cleanup through one shared shell, and skill install/read/write must follow explicit provenance and identity rules instead of permissive fallback behavior. The partially-proven gaps (`2/4`) stay in audit mode unless fresh code evidence upgrades them to real defects during this work.

**Tech Stack:** Python, pytest, existing CoPaw kernel/capability/runtime-center services, MCP runtime contract, git worktree isolation.

---

### Task 1: Runtime Center Review State Uses Typed Truth

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`
- Test: `tests/app/test_runtime_projection_contracts.py`
- Test: `tests/app/test_runtime_query_services.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`

- [x] **Step 1: Write failing tests for canonical host summary and typed review-state precedence**

Add tests proving:
- top-level `host_twin_summary` is treated as canonical without merging stale nested `host_twin.host_twin_summary`
- `build_task_review_payload()` derives `awaiting-verification` from typed continuity/verification data
- `build_task_review_payload()` derives blocked/runtime states from typed blocker data instead of checkpoint text search

- [x] **Step 2: Run tests to verify they fail for the right reason**

Run:

```powershell
python -m pytest tests/app/test_runtime_projection_contracts.py -k "canonical_host_twin_summary or typed_review_state" -q
python -m pytest tests/app/test_runtime_query_services.py -k "canonical_host_twin_summary or typed_review_state" -q
```

Expected:
- failures show current merge/heuristic behavior still leaking into the payload

- [x] **Step 3: Implement minimal canonical-summary and typed-state fix**

Required changes:
- in `state_query.py`, treat top-level `host_twin_summary` as canonical; only fill missing continuity from the canonical summary itself and stop merging stale nested twin summary into the projection
- in `task_review_projection.py`, change `derive_review_execution_state()` to consume typed inputs from `continuity`, host-blocker, recovery, and evidence closeout instead of text marker matching
- keep `latest_result_summary` and `stuck_reason` for operator readability, but stop using them as primary state truth

- [x] **Step 4: Run targeted tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/runtime_center_api_parts/overview_governance.py -q
```

Expected:
- all targeted Runtime Center projection tests pass

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/runtime_center/state_query.py src/copaw/app/runtime_center/task_review_projection.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/runtime_center_api_parts/overview_governance.py
git commit -m "fix: harden runtime center typed review projection"
```

### Task 2: Capability Execution Policy Comes From Mount Contract

**Files:**
- Modify: `src/copaw/capabilities/sources/tools.py`
- Modify: `src/copaw/capabilities/execution.py`
- Test: `tests/app/test_capabilities_execution.py`

- [x] **Step 1: Write failing tests for mount-declared action/evidence policy**

Add tests proving:
- `action_mode` is resolved from mount metadata, not capability-id switch tables
- tool-bridge evidence ownership is resolved from mount metadata, not capability-id switch tables
- a mount without explicit policy remains backward-compatible

- [x] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/app/test_capabilities_execution.py -k "mount_declared_action_mode or mount_declared_evidence_owner" -q
```

Expected:
- failures show execution still depends on hard-coded capability-id lists

- [x] **Step 3: Implement minimal mount-declared execution contract**

Required changes:
- add explicit execution policy metadata for built-in tool mounts in `sources/tools.py`
- in `execution.py`, resolve `action_mode` and tool-bridge evidence ownership from the resolved `CapabilityMount`, with a compatibility fallback only for mounts that still lack policy metadata
- do not create a new capability truth source; keep the policy inside `CapabilityMount.metadata`

- [x] **Step 4: Run targeted tests to verify they pass**

Run:

```powershell
python -m pytest tests/app/test_capabilities_execution.py -k "action_mode or tool_bridge or mount_declared" -q
```

Expected:
- execution contract tests pass and old behavior stays green

- [ ] **Step 5: Commit**

```bash
git add src/copaw/capabilities/sources/tools.py src/copaw/capabilities/execution.py tests/app/test_capabilities_execution.py
git commit -m "fix: move execution policy into capability mounts"
```

### Task 3: Child-Run Shell Owns Scoped MCP Overlay Lifecycle

**Files:**
- Modify: `src/copaw/kernel/child_run_shell.py`
- Modify: `src/copaw/kernel/actor_worker.py`
- Modify: `src/copaw/kernel/delegation_service.py`
- Test: `tests/kernel/test_actor_worker.py`
- Test: `tests/app/test_mcp_runtime_contract.py`
- Test: `tests/app/test_capabilities_execution.py`

- [x] **Step 1: Write failing tests for child-run MCP overlay mount/cleanup**

Add tests proving:
- child-run execution can mount a scoped MCP overlay from task/mailbox metadata before execution
- overlay is cleared on success, failure, and cancellation
- direct delegation execution and actor-worker execution both use the same overlay shell

- [x] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/kernel/test_actor_worker.py -k "mcp_overlay" -q
python -m pytest tests/app/test_mcp_runtime_contract.py -k "child_run" -q
```

Expected:
- failures show actor/delegation lifecycle never calls `mount_scope_overlay()` / `clear_scope_overlay()`

- [x] **Step 3: Implement minimal shared MCP overlay shell**

Required changes:
- extend `child_run_shell.py` with a parsed child-run MCP overlay contract plus one shared `mount -> execute -> cleanup` shell
- make `actor_worker.py` and `delegation_service.py` call that same shell
- keep the overlay contract additive and scoped; do not create a parallel MCP lifecycle path outside `app/mcp/runtime_contract.py`

- [x] **Step 4: Run targeted tests to verify they pass**

Run:

```powershell
python -m pytest tests/kernel/test_actor_worker.py tests/app/test_mcp_runtime_contract.py -q
```

Expected:
- child-run lifecycle tests pass for success/failure/cancel cleanup

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/child_run_shell.py src/copaw/kernel/actor_worker.py src/copaw/kernel/delegation_service.py tests/kernel/test_actor_worker.py tests/app/test_mcp_runtime_contract.py tests/app/test_capabilities_execution.py
git commit -m "fix: wire scoped mcp overlays into child-run lifecycle"
```

### Task 4: Re-verify Remaining Audit Gaps and Close Issue 6 When Proven

**Files:**
- Review only unless fresh evidence upgrades scope:
  - `src/copaw/environments/service.py`
  - `src/copaw/memory/conversation_compaction_service.py`
  - `src/copaw/kernel/query_execution_runtime.py`
  - `src/copaw/capabilities/skill_service.py`
  - `src/copaw/capabilities/catalog.py`
  - `src/copaw/skill_service.py`
  - `src/copaw/agents/skills_hub.py`
  - `tests/agents/test_skills_hub.py`
  - `tests/app/test_capability_skill_service.py`
  - `tests/app/test_capability_catalog.py`
  - `tests/test_skill_service.py`

- [x] **Step 1: Re-audit issues 2/4/6 after Tasks 1-3 land**

Check whether:
- `2` is still only partial after the shared child-run shell changes
- `4` still lacks a formal query-runtime entropy contract
- `6` still lacks strong activation/dedup/frontmatter discipline

- [x] **Step 2: Only add code if a partial issue becomes a proven defect in the current branch**

Result:
- `2` stayed partial: the shared writer primitive exists, but repo-wide adoption across direct browser/desktop/document/file mutators is still incomplete
- `4` stayed partial: degradation and compaction exist, but a formal query-runtime entropy contract is still missing
- `6` was upgraded to a proven defect and fixed by hardening source allowlists, frontmatter rejection, tree-write sanitization, and canonical package-identity dedupe

- [x] **Step 3: Record the final audited status**

Recorded here as the focused runtime closure document for this branch.

### Task 5: Final Verification

**Files:**
- Verify only

- [x] **Step 1: Run focused regression**

```powershell
python -m pytest tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_capabilities_execution.py tests/app/test_mcp_runtime_contract.py tests/kernel/test_actor_worker.py -q
```

- [x] **Step 2: Run broader integration slices**

```powershell
python -m pytest tests/app/test_runtime_center_api.py tests/app/runtime_center_api_parts/detail_environment.py tests/kernel/test_turn_executor.py tests/app/test_operator_runtime_e2e.py -q
```

- [x] **Step 3: Review git diff for scope drift**

Check:
- no unrelated files changed
- no second truth source introduced
- no new branch-local policy tables added

- [x] **Step 4: Prepare closeout summary**

Report:
- what was fixed in `1/3/5/6`
- whether `2/4` stayed partial
- exact verification commands and outcomes
