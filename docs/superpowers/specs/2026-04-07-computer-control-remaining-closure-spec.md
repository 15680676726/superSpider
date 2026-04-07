# CoPaw Computer-Control Remaining Closure Spec

## 0. Purpose

Implementation note as of `2026-04-08`:

- the remaining closure packages described here have been implemented on the
  current mainline code path
- browser routing is now explicit and truthful instead of implicit:
  built-in browser remains the default channel, healthy attached browser
  continuity resolves to the browser MCP channel, and attach-required requests
  fail closed instead of silently degrading
- Runtime Center environment detail now projects browser channel selection and
  health
- guarded live smoke now includes attached-browser channel continuation proof in
  addition to the managed built-in browser continuation chain

This spec defines the remaining closure work for CoPaw's computer-control chain after:

- the current Windows-first browser/desktop/document runtime baseline
- the existing cooperative runtime landing
- the focused `2026-04-07-desktop-control-hardening-plan.md`

This is not a new architecture.

It is a truthful closure spec for the remaining gaps that still separate:

- "the chain is real and usable"
from
- "the chain is fully closed and can be described without caveats"

This spec must remain aligned with:

- `AGENTS.md`
- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `TASK_STATUS.md`
- `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md`
- `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md`

It must not invent a second execution architecture or a second host truth source.

It must also not be read as a mandate to keep expanding CoPaw-owned raw
browser/desktop action logic.

For computer control, the intended steady-state boundary is:

- execution agent decides when to observe / act / verify / recover
- adapter / host layer executes concrete computer actions
- MCP is the preferred external exposure / transport boundary for those actions
- runtime / kernel / environment layer owns session / lease / lock / evidence /
  risk / recovery / anti-contention

This means:

- `MCP-first` must not be read as `MCP-only`
- MCP is not the computer-control engine
- host / adapter primitives such as Windows host, UIA semantic control, browser
  companion/session control, and their cleanup/recovery semantics remain the
  real execution core

This spec therefore describes remaining runtime-governance closure work under an
`MCP-exposed, adapter/host-backed` action boundary, not a new platform-side
action brain.

---

## 1. Truthful Baseline

The current repo is not starting from zero.

The following facts are already true:

- browser/document/windows-app surfaces already flow through one formal environment facade
- shared host/session facts are already projected through the same environment/runtime truth
- writer lease semantics already exist as formal repository-backed leases
- recovery/handoff/resume semantics already exist as formal runtime concepts
- Runtime Center already has formal read-model visibility over these surfaces
- Windows desktop control is already backed by real host primitives rather than prompt-only simulation

The current codebase has also already been live-smoked for real actions, including:

- managed browser open + real click
- desktop file write/edit round trip
- real Notepad launch/edit/save/close
- real dialog semantic fill/confirm

This means the correct judgment is:

- the computer-control chain is already real
- the remaining problem is closure depth, not existence
- browser execution already has a strong enough built-in path to remain the
  default near-term execution channel
- browser MCP should be treated as an optional upgraded exposure path, not a
  prerequisite for truthful near-term closure

Current repo reality is also hybrid rather than perfectly uniform:

- desktop control already trends toward MCP-adapter-backed execution
- browser control still retains a stronger built-in execution path

That hybrid reality is acceptable as a transitional state, but it should not be
used as justification to keep growing first-party raw action surfaces inside
CoPaw core.

---

## 2. What The Existing Desktop Hardening Plan Actually Closes

`docs/superpowers/plans/2026-04-07-desktop-control-hardening-plan.md` is valid, but it only closes one narrow slice of the remaining work.

It correctly targets three residual hardening gaps:

1. formal desktop replay should fail closed when the owning runtime capability is absent
2. desktop doctor/example-run should stop overclaiming readiness from shallow host checks
3. desktop document writes should derive a more stable writer scope than `session_mount_id`

This plan is therefore best understood as:

- a residual desktop hardening plan
- not the complete remaining computer-control closure plan

It does not close:

- real-user browser attach continuity maturity
- watcher runtime deepening into a true host-companion-backed runtime path
- deeper semantic-readiness judgment for desktop control
- broader app-family semantic coverage
- the full live verification matrix needed to claim closure without caveats

---

## 3. Remaining Closure Packages

The rest of the work should be understood as six closure packages.

### 3.1 Package A: Browser Channel Policy And Deferred Attach Continuity

This is now a policy/deferred-maturity package rather than a current closure
blocker.

Current truthful state:

- `attach-existing-session` already exists as a first-class browser mode
- transport/session/scope/reconnect truth is already persisted and projected
- lifecycle cleanup and recovery semantics already exist
- repository tests already cover the contract well
- the built-in browser path is already mature enough to remain the current
  default execution channel

Current gap:

- browser channel selection policy should be stated more explicitly
- browser MCP should only be preferred when it is both installed and healthy
- requests that explicitly require attaching to a real user browser/session
  must not silently fall back to the built-in browser path
- `attach-existing-session` continuity maturity is still behind the current
  managed built-in browser baseline

Closure target:

- the built-in browser path remains the truthful default when browser MCP is
  absent or unhealthy
- browser MCP becomes the selected path only when it is installed and healthy
- attach-required requests either bind to the declared real browser scope or
  fail closed with explicit diagnostics
- deeper `attach-existing-session` continuity proof remains a later maturity
  track instead of a current closure gate

Recommended browser maturity order:

1. keep built-in browser as the default execution channel
2. add a single browser-channel resolver so route selection is explicit rather
   than implicit
3. project the selected browser channel and its health into Runtime Center
4. harden `attach-existing-session` continuity/reconnect diagnostics
5. add opt-in live proof for real attached-session continuation
6. only after the above, consider making healthy browser MCP the preferred
   channel for the matching task classes

Primary landing zones:

- `src/copaw/environments/cooperative/browser_attach_runtime.py`
- `src/copaw/environments/service.py`
- `src/copaw/capabilities/browser_runtime.py`
- `tests/environments/test_cooperative_browser_attach_runtime.py`
- live smoke coverage adjacent to `tests/routines/test_live_routine_smoke.py`

### 3.2 Package B: `HostWatcherRuntime` Deepening

This is the most obvious host-event/runtime gap.

Current truthful state:

- watcher status is already registered into formal environment/session truth
- download and notification events already enter the runtime event bus
- Runtime Center can already project watcher availability

Current gap:

- the current implementation is still closer to "watcher runtime contract + event ingress"
  than to "repo-owned real host watcher runtime"
- it should not be over-described as if the repo already ships a complete always-on OS watcher daemon

Closure target:

- host watcher runtime should have a clear companion-backed or host-backed runtime path
- filesystem/download/notification families should have explicit lifecycle and readiness truth
- watcher-originated events should become reliable triggers for re-observe/recover/retry flows, not just passive event records

Primary landing zones:

- `src/copaw/environments/cooperative/watchers.py`
- `src/copaw/environments/service.py`
- `src/copaw/environments/health_service.py`
- `tests/environments/test_cooperative_watchers.py`

### 3.3 Package C: Desktop Semantic Readiness Contract

This is the most obvious desktop-readiness honesty gap.

Current truthful state:

- desktop doctor already checks host/platform/install basics
- desktop example-run already proves that the host can respond

Current gap:

- current doctor is still too close to "Windows + pywin32 + adapter installed"
- current example-run is still too shallow to prove semantic-control readiness
- "desktop host reachable" is not the same thing as "desktop semantic control ready"

Closure target:

- doctor must separately expose:
  - host-ready
  - MCP/adapter-ready
  - semantic-control-ready
  - writer-capable-ready when relevant
- example-run should use a bounded low-risk semantic/control path when available instead of only a generic host liveness check

Primary landing zones:

- `src/copaw/capabilities/install_templates.py`
- `tests/app/test_capability_market_api.py`
- `tests/environments/test_cooperative_windows_apps.py`

### 3.4 Package D: App-Family Semantic Coverage

This is a maturity package, not a proof-of-existence package.

Current truthful state:

- generic Win32/UIA desktop control is real
- desktop app contracts and adapter projections already exist

Current gap:

- semantic coverage is still generic-first
- not enough app-family-specific semantic adapters exist to call the chain "mature across common desktop work"

Closure target:

- keep the generic Windows host path as the base runtime
- add stronger semantic adapters only for the highest-value app families
- do not turn this into an endless per-app customization project

Recommended first families:

- office-document
- dialog/form workflows
- bounded productivity apps with stable accessibility trees

This package is important, but it should not block honest closure language if
Packages A/B/C/E/F are done.

The key constraint is:

- if Package D deepens adapter/operator semantics that agents can call, it is
  aligned
- if Package D turns workflow/bootstrap/service layers into app-specific action
  planners, it is misaligned

### 3.5 Package E: Writer Contract Completion

The existing desktop hardening plan addresses the first half of this problem.

Current truthful state:

- shared writer leases already exist
- document actions already acquire/release formal writer leases
- current fallback can still collapse to `session_mount_id`

Current gap:

- stable identity derivation is not yet strong enough across all equivalent document scopes
- writer scope should cover more than "this session"
- the final contract must reflect real document/account/window ownership semantics

Closure target:

- stable document identity should outrank ephemeral session identity
- equivalent writes against the same underlying document should converge on the same writer scope
- the runtime should express both live-window and underlying document/account scope when relevant

Primary landing zones:

- `src/copaw/environments/surface_control_service.py`
- `src/copaw/environments/health_service.py`
- `tests/environments/test_cooperative_document_bridge.py`

### 3.6 Package F: Expanded Live Verification Matrix

This package is required for honest closure, even though it is not "new functionality."

Current truthful state:

- the chain has real live evidence already
- but that evidence is still concentrated in a narrower subset of modes and scenarios

Closure target:

- live verification must cover the remaining high-value truth claims:
  - watcher-driven runtime observation/event flow
  - semantic desktop readiness path
  - stable writer locking across equivalent document scopes
  - recovery/handoff/resume behavior for at least one real interrupted path

Without this package, the repo may be functionally stronger while still lacking proof strong enough to claim "fully closed."

---

## 4. Closure Blockers vs Maturity Enhancers

The remaining work should be judged in two buckets.

### 4.1 Closure Blockers

These must be closed before the computer-control chain should be described as fully closed:

- Package B: `HostWatcherRuntime` deepening
- Package C: desktop semantic readiness contract
- Package E: writer contract completion
- Package F: expanded live verification matrix

### 4.2 Maturity Enhancers

These improve product quality materially, but should not be confused with the minimum truthful closure bar:

- Package A: browser channel policy tightening and later attach continuity maturity
- Package D: app-family semantic coverage

---

## 5. Recommended Construction Order

The correct order is:

1. finish `2026-04-07-desktop-control-hardening-plan.md`
2. deepen `HostWatcherRuntime`
3. strengthen desktop semantic-readiness judgment
4. complete writer identity/scope convergence
5. run the expanded live verification matrix
6. continue app-family semantic coverage as a maturity track
7. revisit browser MCP/attach continuity as a later maturity track

Reason:

- the hardening plan removes the most local honesty bugs
- watcher/semantic readiness/writer stability are the biggest remaining closure blockers
- live verification should come after the target runtime paths exist
- app-family depth should build on a stable truthful base instead of replacing it
- browser donor maturity can safely lag as long as the browser channel policy
  stays honest
- browser planning still needs to be explicit, but it should advance as a
  maturity track after the current blocker-closure work is honest and green

---

## 6. Non-Goals

This spec does not require:

- inventing a second browser/desktop runtime
- reassigning surface ownership from execution agents back to the main brain
- growing a first-party raw computer-action catalog when an adapter/host +
  MCP-exposed boundary can own the actuation boundary
- turning workflow / bootstrap / install-template surfaces into platform action
  brains
- claiming `Full Host Digital Twin` maturity beyond the current repo definition
- universal support for every desktop application
- cross-platform parity beyond the current Windows-first execution baseline

---

## 7. Exit Criteria

The computer-control chain should be called "fully closed" only when:

- desktop hardening plan items are complete
- watcher runtime has a truthful host-backed runtime path and observable lifecycle
- desktop doctor/example-run distinguish host readiness from semantic readiness
- equivalent document writes converge on stable writer scope beyond session identity
- live verification covers the remaining truth claims that are currently only partially evidenced
- browser routing remains truthful: built-in by default, MCP only when
  installed and healthy, and attach-required requests fail closed rather than
  silently degrading
- the closure language remains consistent with the intended steady-state
  boundary:
  agent decides, adapter/host executes, MCP exposes, runtime governs
  continuity and safety

Until then, the honest repo judgment remains:

- the chain is real
- the baseline is already strong
- but a few closure blockers still remain
