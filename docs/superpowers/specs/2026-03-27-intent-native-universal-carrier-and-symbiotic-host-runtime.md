# Intent-Native Universal Carrier and Symbiotic Host Runtime

## 1. Positioning

This document upgrades CoPaw's formal target framing from "computer-control hardening" to a
larger carrier architecture:

- upper formal target: `Intent-Native Universal Carrier`
- execution-side formal framework: `Symbiotic Host Runtime`
- host-side mature end state: `Execution-Grade Host Twin -> Full Host Digital Twin`

It does not replace the formal write chain or formal object vocabulary.
It also does not replace the existing 7-layer target architecture in
`COPAW_CARRIER_UPGRADE_MASTERPLAN.md`.

It should be read only as:

- an upper target framing
- an execution-side formal framework

The only formal operator write truth remains:

`StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan`

This document answers a different question:

> how CoPaw should become a general execution carrier for AI ideas, while keeping Windows host,
> browser, document, and app execution tightly bound to one formal runtime chain.

## 2. Core Decision

CoPaw should not be framed primarily as:

- a browser agent
- a desktop click bot
- a workflow marketplace
- a Windows automation product

CoPaw should be framed as:

> a universal local execution carrier that compiles intent into capabilities, environments,
> governance, evidence, and recovery.

In that framing:

- browser, document, and Windows app execution are required carrier skills
- Windows is the strongest current local execution host, not the only future environment
- `Symbiotic Host Runtime` is the execution-side system that lets CoPaw live inside a real Windows
  user workspace instead of merely borrowing UI tools

## 3. Execution-Side Design Stance

`Symbiotic Host Runtime` should follow five fixed rules:

1. `native-first`
   Prefer API, extension, add-in, plugin, object-model, or file-semantic paths before raw UI
   automation.
2. `host-companion-backed`
   A Windows user session should expose durable host/session/workspace facts instead of forcing
   every turn to rediscover the machine from scratch.
3. `workspace-centered`
   Tasks should hold a living workspace, not a bag of unrelated browser/app/file tools.
4. `event-driven`
   Window drift, downloads, lock/unlock, modal rescue, process exit, and network/power changes
   must enter the formal runtime loop.
5. `ui-fallback`
   Browser/desktop/document operators remain required, but they are the fallback execution layer,
   not the only architectural language.

## 4. Formal Mapping Back to Existing Objects

No second truth source is introduced.

The new execution-side terms must map back as follows:

| New framing | Formal mapping |
| --- | --- |
| `Intent-Native Universal Carrier` | upper architecture framing only; not a new primary state object |
| `Symbiotic Host Runtime` | execution-side composition over `EnvironmentMount + SessionMount + CapabilityMount + EvidenceRecord` |
| `Seat Runtime` | `EnvironmentMount` subtype for a durable execution seat |
| `Host Companion Session` | `SessionMount` subtype for live Windows user/session/desktop continuity |
| `Workspace Graph` | derived projection over `TaskRuntime + EnvironmentMount + SessionMount + Artifact/Evidence`; not a new primary object store |
| `Host Event` | runtime mechanism backed by `EvidenceRecord + ObservationCache + environment/runtime detail projections`; not a separate event truth store |
| `Cooperative Adapter` | `CapabilityMount` family, not a fourth capability language |
| `Execution-Grade Host Twin` | derived runtime projection, not a second database or state tree |
| `Full Host Digital Twin` | mature host-side state of the same execution chain, not a one-shot phase deliverable |

Additional hard boundaries:

- `Workspace Graph` must remain a projection, not a new level-one object library
- `Host Event Bus` must remain a runtime mechanism, not a separate event truth store

## 5. Required Capability Families

For CoPaw to act as a real execution carrier, the following families are mandatory:

- browser work
  form fill, authenticated continuation, upload/download, backend operation
- document and local writing work
  file create/edit/save/reopen, long-form writing, revision, structured export
- Windows application work
  messaging apps, admin tools, office tools, finance terminals, creative tools

But these families should not all be implemented the same way.

Target priority:

- cooperative/native path first
- semantic operator second
- visual fallback last

## 6. Maturity Path

`Full Host Digital Twin` is the formal mature target, but it must not be treated as a single
phase.

Recommended maturity path:

### Phase 1: `Windows Seat Runtime Baseline`

- durable execution seat
- host companion session
- shared host contract
- browser site contract
- Windows desktop app contract
- minimal seat/workspace/handoff/recovery visibility
- explicit lease and writer-lock model for real machine contention:
  `seat lease / account scope / browser tab scope / app window scope / file writer lock`
- one formal continuity contract for:
  handoff, resume, rebind, attach-existing-session, MFA/CAPTCHA pause, and human return
- browser baseline acceptance must cover:
  authenticated continuation, form fill, upload/download, cross-tab continuation, save-and-reopen verification
- desktop/document baseline acceptance must cover:
  create/edit/save/reopen, focused-window verification, modal interruption handling, and post-write reread
- no action may be treated as successful only because a low-level tool returned success; success must be
  verified against page/app/document state change
- governance stays minimal at runtime:
  irreversible or external-boundary actions still escalate, but routine continuation must not be blocked by
  redundant approval layers
- this phase is not complete unless the system can finish a small real-world acceptance set on a live Windows
  seat and leave replayable evidence for each step

### Phase 2: `Cooperative Adapters`

- browser extension or browser companion
- office/document-chain object-model bridges
- file/download/notification watchers
- high-value Windows app adapters
- adapter families must be first-class capability mounts, not private shortcuts outside governance/evidence
- known high-value sites/apps should prefer contract-backed semantic channels before generic UI fallback
- runtime selection should become mode-aware:
  native/cooperative path first, semantic operator second, visual fallback last
- adapter rollout should be driven by real acceptance bottlenecks:
  login continuity, downloads, messaging apps, office writing chains, admin consoles

### Phase 3: `Workspace Graph`

- browser + app + file/doc + clipboard + downloads + artifacts + locks + handoffs as one
  formal task workspace projection
- the workspace graph must stay a derived projection, but it now becomes the task's operational seat map:
  what is open, what is locked, what changed, what is pending human return, and what evidence anchors exist
- multi-agent coordination must stop relying on implicit politeness; the projection should expose collision
  facts such as shared account use, writer conflicts, and active surface ownership
- role workflows should read workspace availability from this projection before dispatching UI-mutating work

### Phase 4: `Host Event Bus`

- runtime mechanism for host observation, recovery triggers, and execution-side re-observe/retry flow
- active window changes
- modal/UAC/login rescue
- download completion
- process exit/restart
- lock/unlock
- network/power change
- host events must become formal scheduler and recovery inputs instead of best-effort logs
- recovery should be event-led rather than prompt-led:
  the system re-observes from concrete host changes, checkpoints, and lease continuity instead of guessing from
  chat history
- human takeover and return should emit the same class of runtime events as crashes, focus loss, and modal drift

### Phase 5: `Execution-Grade Host Twin`

- high-confidence runtime projection of seat/workspace/events/locks/recovery state for the current
  task and execution agent
- this is the first stage where the host projection should be strong enough to support scheduling decisions,
  contention forecasts, and preflight checks before an execution agent starts mutating work
- the twin should answer:
  who owns the seat now, which surfaces are writable, what continuity is still valid, what evidence anchors are
  trusted, and what recovery path is currently legal
- reaching this phase requires that acceptance, recovery, and concurrency semantics are already stable in the
  earlier phases; it is not a substitute for them

### Phase 6: `Full Host Digital Twin`

- broader host graph coverage
- deeper app-family twins
- stronger multi-agent host coordination
- richer planning/simulation against live host state
- this mature state should support many agents working against one host without silent corruption:
  concurrent research, customer messaging, browser back-office work, and document production must coordinate
  through explicit seat/workspace/lock semantics
- workflow planning, fixed SOP dispatch, and execution scheduling should all consume the same host truth rather
  than rebuilding their own environment guesses
- even at this stage, the twin remains derived from unified state/evidence; it must never become a parallel
  database or a replacement main chain

## 7. Non-Goals

This document does not authorize:

- promising that CoPaw can instantly realize every imaginable AI idea
- making Windows UI automation the universal answer to every execution problem
- building a second host-state database outside the unified state/evidence chain
- letting the main brain directly become the browser/desktop driver again
- treating all apps/pages as generic surfaces without site/app contracts

## 8. Success Condition

This target framing is considered real only when:

- ideas can be compiled into capabilities, environments, governance, evidence, and recovery
- browser, document, and Windows app execution all become first-class required capability families
- CoPaw can hold a durable Windows seat instead of reconstructing the machine every turn
- native/cooperative paths are preferred before UI fallback
- workspaces, host events, handoff, and recovery become visible formal runtime facts
- `Full Host Digital Twin` remains the mature direction without forcing a one-shot implementation
