# Truth-First No-Vector Memory Implementation Plan

## Final Sync
This file now records the landed implementation state rather than open execution steps. The memory rollout is complete: CoPaw runs on a `truth-first` and `no-vector formal memory` contract, and QMD/vector references are physically removed residuals, not pending cleanup work.

## Final Architecture
- Shared formal memory is derived from canonical `state / evidence / runtime` truth only.
- Formal memory is consumed in the order `profile -> latest facts -> episodes -> history -> lexical fallback`.
- Private conversation compaction remains isolated per runtime actor or session and does not become a second truth source.
- No embedding model, vector backend, or QMD sidecar is required for normal runtime operation.

## Completed Workstreams

### 1. Hard-Cut Vector Runtime Noise
Landed outcome:
- default QMD bootstrap is gone from the formal runtime path
- operator and runtime health no longer advertise `memory_qmd_sidecar`, `memory_vector_ready`, or `memory_embedding_config` as formal readiness requirements
- formal memory backend semantics no longer present `qmd`, `local-vector`, or `lancedb` as canonical runtime choices

Verification intent:
- boot without embedding configuration
- confirm no vector/QMD readiness warnings on formal surfaces
- confirm recall and prompt injection continue to work

### 2. Legacy Runtime Memory Retirement And Private Compaction Split
Landed outcome:
- legacy `MemoryManager` stopped being the formal runtime host dependency
- private conversation compaction was split into dedicated non-canonical plumbing
- runtime agents no longer rely on a second opaque shared memory blob

Verification intent:
- runtime host starts without legacy shared-memory boot requirements
- compaction remains available without reintroducing a second truth source
- no embedding/vector startup warnings remain in the formal memory path

### 3. Truth-First State Schema And Storage
Landed outcome:
- truth-first evolution fields now exist on formal memory facts
- profile and episode style views are rebuildable from canonical truth
- legacy rows remain bootable and rebuildable through additive schema handling

Verification intent:
- older SQLite state still opens under the new code
- rebuild/materialization succeeds on legacy rows
- repeated schema initialization remains idempotent

### 4. No-Vector Recall Core
Landed outcome:
- formal recall no longer uses `hashed_vector()` or sidecar preparation
- shared precedence rules and truth-first profile/latest/history views drive recall
- lexical recall remains only as fallback after truth-derived memory views

Verification intent:
- precedence rules hold under mixed fact/history/temporary cases
- history and latest views stay distinct
- recall remains correct without vector semantics

### 5. Runtime Consumers And Documentation Closeout
Landed outcome:
- runtime consumers read profile/latest/history truth-first memory before lexical fallback
- docs and specs now describe QMD/vector paths as retired and physically removed
- formal product memory stays aligned with the shared truth-derived model plus separate private compaction state

Verification intent:
- main-brain and runtime prompt consumers follow the truth-first recall order
- architecture/status/model docs keep the no-vector wording
- doc assertions lock the final wording in place

## Physical Cleanup Ledger
Completed removals and retirements include:
- formal QMD bootstrap wiring
- formal vector/embedding runtime health checks
- operator-facing QMD sidecar health surfaces
- hashed-vector scoring in the formal recall chain
- formal backend chooser language that treated vector stores as canonical runtime options
- legacy `MemoryManager` as a shared runtime truth dependency

These are physically removed residuals, not future tasks.

## Acceptance Snapshot
The final synced acceptance bar is:
- shared formal memory remains `truth-first`
- shared formal memory remains `no-vector formal memory`
- private compaction stays private and non-canonical
- no formal runtime or operator surface treats QMD/vector/embedding readiness as required
- memory docs, plans, and architecture references describe the cleanup as completed physical removal

## Verification
The doc/spec closeout should continue to be checked with:
- focused memory integration assertions
- runtime consumer regression tests that cover truth-first recall order
- architecture/documentation sync checks for the core state documents

## Documentation Scope
The final-sync wording is expected to stay aligned across:
- `docs/superpowers/specs/2026-03-30-truth-first-no-vector-memory-design.md`
- `TASK_STATUS.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`
- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`

If a future document mentions QMD/vector as an open cleanup item in the formal memory path, that document is out of sync with the current architecture.
