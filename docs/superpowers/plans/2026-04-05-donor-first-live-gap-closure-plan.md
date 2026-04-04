# Donor-First Live Gap Closure Plan

**Goal:** Close only the donor-first items that are still missing in real runtime behavior, and stop treating object/read-model/test coverage as equivalent to live external capability closure.

**Scope boundary:** This plan does not reopen donor-first architecture, lifecycle truth, or Runtime Center read-model design. It only covers the remaining live gaps that block a truthful `discover -> install -> use` completion claim.

## Completion Note (`2026-04-05`)

This plan has now been executed on `main`.

Closed items:

- runtime bootstrap discovery executor is no longer a no-op
- source-chain now distinguishes `success / empty / failed / snapshot`
- GitHub/open-source donor discovery is now a real runtime path via scout/provider search
- SkillHub/curated search now suppresses dead bundles before install

Fresh verification recorded in `TASK_STATUS.md`:

- focused regression: `73 passed`
- donor read-model adjacent regression: `107 passed`
- live network validation:
  - hub search/install
  - curated search/install
  - MCP registry search/install/connect
  - gap scout + opportunity scout importing real candidates

## Verified Remaining Gaps

1. runtime bootstrap still wires an empty discovery executor, so autonomous scout defaults to `0 imported candidates`
2. source-chain records `success` on `0 hit`, which inflates source health and misleads Runtime Center
3. generic GitHub / open-source donor discovery is not yet a real runtime search path
4. SkillHub / curated search returns dead bundles, so result sets are not install-trustworthy by default

## Closure Rule

This plan is complete only when all 4 are true:

- scout can import real candidates from live providers
- source health distinguishes `success / empty / failed / snapshot`
- users can run directional search for `skill / mcp / open-source project`
- SkillHub / curated default result sets suppress dead bundles before they reach install

## Execution Order

### Task 1: Truthful source-chain semantics

- treat `0 hit` as `empty`, not `success`
- continue to next source on empty results
- only mark last-known-good on non-empty hit success
- expose `empty` in source attempts and source health

### Task 2: Real runtime discovery executor

- replace the runtime bootstrap no-op executor
- wire real provider handlers for:
  - SkillHub
  - curated catalog
  - official MCP registry
  - GitHub/open-source repo search
- keep one active source per action, but allow empty/failure fallback to the next source

### Task 3: GitHub/open-source donor path

- add a bounded GitHub repository discovery adapter
- return normalized donor hits with package/source lineage
- support directional queries such as:
  - `browser automation github`
  - `filesystem mcp`
  - `research skill`

### Task 4: SkillHub/curated installability governance

- add cached bundle validation for SkillHub results
- suppress dead bundle URLs from hub/curated search surfaces
- preserve successful bundles and annotate warnings when validation is partial

## Verification

The implementation is not complete until all of the following are executed fresh:

- focused pytest for source-chain, scout, market search/installability, and runtime-center discovery views
- real live search:
  - skill
  - curated
  - MCP registry
  - GitHub/open-source donor
- real live install:
  - one SkillHub package
  - one MCP registry package
- real live use proof:
  - MCP connection established
  - scout imports at least one real candidate through runtime bootstrap
