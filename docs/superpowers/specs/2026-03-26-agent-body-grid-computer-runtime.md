# CoPaw Agent Body Grid Symbiotic Host Runtime Spec

## 1. Positioning

This document defines the next runtime-first execution baseline for CoPaw after the current hard-cut autonomy rebuild:

> execution agents, not the main brain, own computer-operation bodies; browser, desktop apps, files, and documents are all managed as surfaces inside a unified local computer runtime.

Within the `2026-03-27` target framing, this spec should now be understood as:

- the execution-side spec for `Symbiotic Host Runtime`
- the local-host execution substrate inside `Intent-Native Universal Carrier`
- a supplement that does **not** replace the existing 7-layer target architecture

This spec is a supplement to, not a replacement for:

- `AGENTS.md`
- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `TASK_STATUS.md`
- `DATA_MODEL_DRAFT.md`
- `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md`

It must not create a second main chain. The only formal operator write truth remains:

`StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan`

## 1.1 Relationship to the Other Three Documents

This document is only one quarter of the current hard-cut package:

- this spec defines the execution-side computer runtime target
- `docs/superpowers/specs/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md` defines the automation-side hard cut
- the two matching plan files define construction order

Boundary:

- this spec answers how execution agents operate computers
- the fixed SOP spec answers how low-judgment automation is kept inside CoPaw
- neither spec is allowed to absorb the other's responsibility
- the upper framing is now defined by
  `docs/superpowers/specs/2026-03-27-intent-native-universal-carrier-and-symbiotic-host-runtime.md`
  and this spec must remain execution-side only

## 2. Problem Statement

The current codebase already contains real browser and desktop control primitives, but it does not yet satisfy the only requirement that matters for this stage:

> the system must act like a real worker on a real computer, understand what it is doing, and reliably finish browser, app, and document tasks.

Current gaps:

- browser automation exists, but "tool returned success" is still too often treated as task success
- desktop automation exists, but action success is not reliably tied to document/app state change
- environment recovery exists as a domain, but browser/desktop live handles are not yet first-class recoverable execution bodies
- the main brain still coordinates runtime context primarily through request/runtime metadata instead of managing durable execution bodies as formal execution resources
- multiple execution agents would currently contend for real machine resources without a formal lock/scheduler model

## 3. Core Architecture Decision

The correct owner model is:

- `Main Brain`: planning, assignment, supervision, synthesis, governance
- `Execution Agent`: owns task execution responsibility
- `Agent Body`: the durable computer-operation body used by an execution agent

Therefore CoPaw should evolve toward:

`Main Brain -> Assignment -> Execution Agent -> Agent Body Runtime -> Browser/Desktop/Document Operators -> Evidence/Report -> Main Brain`

This replaces the old mental model of "main brain directly uses browser/desktop tools".

## 3.1 Workflow, Routine, and Scheduler Boundary

This runtime direction does not replace role workflows, routines, or the native fixed SOP kernel.

The intended layering is:

`Assignment -> Role Workflow -> Body Scheduler -> Body Lease -> Routine/Operator -> Evidence/Report`

Responsibilities:

- `Assignment`: defines who owns the execution responsibility
- `Role Workflow`: defines the coherent role-specific sequence for this class of work
- `Body Scheduler`: decides which live body/session/resource can be used now
- `Routine`: defines how a leaf action chain is stably executed inside a leased body
- `Operator`: performs the concrete browser/desktop/document step with observe-act-verify semantics

Rules:

- workflow and scheduling must not be merged into the same abstraction
- workflow decides what sequence should happen; scheduling decides when and where it can safely run
- a workflow step is not executable unless it can resolve both a responsible execution agent and a valid body/resource lease
- future workflow preview/launch must check not only capability availability, but also body/session/resource availability

## 3.2 Native Fixed SOP Kernel Boundary

`n8n`, external workflow hubs, and imported community workflow JSON are retired from the target architecture.

CoPaw should instead keep a native minimal fixed-SOP kernel for:

- webhook intake
- schedule/cron materialization through existing cron services
- API fan-out and callback waits
- fixed low-judgment condition routing

Disallowed uses:

- owning the browser/desktop/document execution loop
- acting as the truth source for workflow/routine definitions
- reintroducing a generic external marketplace / adapter product path
- deciding flexible cross-role business judgment
- bypassing CoPaw evidence, recovery, governance, or report backflow

If a fixed SOP needs real UI work, the native kernel should invoke CoPaw's leased body runtime and wait for structured completion instead of executing the UI path itself.

The retirement and replacement path is specified in `docs/superpowers/specs/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`.

## 3.3 Dependency Rule

The body runtime does not depend on an external SOP adapter to be valid.

However, the final target state does depend on the `n8n` retirement decision already being fixed:

- `Agent Body Grid` is the only target for real browser/desktop/document execution
- `Native Fixed SOP Kernel` is the only target for low-judgment automation
- no implementation should land that keeps both the old `sop_adapters` path and the new body-runtime path as long-lived peers

## 3.4 Symbiotic Host Runtime Design Stance

This spec should no longer be read as "a stronger click bot plan."

Execution-side design stance:

- `native-first`
  prefer cooperative/native semantic paths before raw UI fallback
- `host-companion-backed`
  the Windows user/desktop/session should expose durable continuity facts
- `workspace-centered`
  tasks should hold a living workspace instead of only isolated browser/app/file handles
- `event-driven`
  host changes should be able to trigger re-observe/recover/handoff/retry
- `ui-fallback`
  browser/desktop/document operators remain required, but they are the fallback execution layer

## 4. Formal Runtime Model

### 4.1 Agent Body Grid

The system should expose a pool of managed computer-operation bodies:

- some are browser-focused
- some are desktop-focused
- some are document/file focused
- some can be composite bodies that hold multiple surfaces at once

This pool is the `Agent Body Grid`.

Each body is assigned through a lease, not through implicit shared global state.

### 4.2 Computer Runtime

The local host should be modeled as a formal runtime substrate, not as scattered tool functions.

Responsibilities:

- enumerate and manage machine surfaces
- provide screenshots, window/process state, clipboard state, browser session state, filesystem state
- provide durable Windows user-session / desktop-session / foreground-desktop continuity facts
- provide downloads / notification / network-power / process-liveness observation where relevant
- provide controlled input/output primitives
- expose resource locks and leases
- support recovery and resume

### 4.3 Surface Operators

Computer operation must not collapse into a single click bot.

The target execution stack should be understood as:

- `HostCompanion`
  keeps Windows user/session/desktop/workspace continuity alive
- `CooperativeAdapter`
  exposes browser extension, object-model, plugin, watcher, or app-specific semantic paths when available
- `WorkspaceGraph`
  assembles browser/app/file/clipboard/download state into one live task workspace
- `HostEventBus`
  turns host changes into formal runtime facts
- `BrowserOperator / DesktopOperator / DocumentOperator`
  provide observe/act/verify execution when cooperative/native paths are unavailable or incomplete

The runtime should have specialized operators:

- `BrowserOperator`
- `DesktopOperator`
- `DocumentOperator`

Each operator can use multiple channels:

- semantic channel: DOM, accessibility tree, file/object model
- spatial channel: screenshot, visual grounding, region state
- primitive channel: mouse, keyboard, window/process, clipboard, filesystem

Policy:

- cooperative/native semantic paths should be preferred before raw UI operator paths
- browser work is DOM-first, vision-fallback
- desktop work is accessibility/window-first when possible, vision-fallback
- document/file work is native-object-first, UI-fallback only when necessary
- browser/document/app remain required skill families; none of them should be treated as optional sidecars

### 4.4 Surface Host Contract

Browser and desktop/document surfaces must not evolve separate runtime languages.

Every live execution surface should project the same shared host/session facts:

- `surface_kind`
- `host_mode`
- `lease_class`
- `access_mode`
- `session_scope`
- `account_scope_ref`
- `continuity_source`
- `handoff_state`
- `resume_kind`
- `verification_channel`
- `capability_summary`
- `current_gap_or_blocker`

Contract:

- `surface_kind` answers whether this body is currently acting through `browser / desktop / document`
- `host_mode` answers whether the surface is local-managed, attached-to-existing, or provider-hosted
- `lease_class` answers how the scheduler treats this live surface:
  `exclusive-writer | parallel-read | pooled | queued-side-effect`
- `access_mode` answers the current intended interaction posture:
  `read-only | writer | side-effect-queued`
- `session_scope` answers whether the lease is tied to one tab/window, a grouped scope, or a wider body/account scope
- `continuity_source` answers where the current live continuity came from
- `handoff_state` and `resume_kind` are cross-surface continuity facts, not browser-only concepts
- `verification_channel` records which channel currently has authority for success checking:
  semantic tree, accessibility tree, native object model, or visual fallback

Suggested shared host-mode values:

- `local-managed`
- `attach-existing`
- `provider-hosted`

Rules:

- `browser_mode` and future desktop-specific host details may refine `host_mode`, but may not replace it
- `lease_class` and `access_mode` should be visible in scheduling, health, and operator surfaces; they are not internal-only scheduler trivia
- a live writer surface without explicit `lease_class/access_mode` is malformed runtime state

- browser-specific and desktop-specific details may extend these fields, but may not replace them
- Runtime Center and Agent Workbench should project shared host facts first, then surface-specific facts
- no execution surface may collapse into a single binary "ready / not ready" label once live session truth exists

#### Seat Runtime / Host Companion Interpretation

The shared host contract should also be readable as the minimum contract for:

- `Seat Runtime`
  a durable execution seat owned by an execution agent
- `Host Companion Session`
  the live Windows user/session/desktop continuity source behind that seat

This does not create a second truth source.

It means that browser/desktop/document surfaces should increasingly be viewed as live workspace
members hanging off the same durable seat/runtime contract.

### 4.5 Browser Runtime Modes

Browser operation must be modeled in explicit runtime modes rather than as one generic
"browser-ready" state.

#### `managed-isolated`

CoPaw owns the browser profile/context lifecycle itself.

Use it for:

- deterministic acceptance flows
- repetitive fixed browser routines
- lower-trust websites where isolated storage and download control matter

Characteristics:

- strongest control over profile, storage, locale/timezone overrides, and download capture
- best default for repeatable observe/act/verify execution
- recovery should prefer profile/session restore before falling back to fresh recreation

#### `attach-existing-session`

CoPaw attaches to a real user-controlled Chromium session through an existing live browser
transport.

Use it for:

- continuing already-authenticated backend/admin work
- tasks where a human has already established the login/session state
- browser work that must stay inside a real user profile instead of a fresh isolated context

Characteristics:

- this is a formal runtime mode, not an ad-hoc debug trick
- the lease scope is browser-wide or tab-group scoped, not "one tool call against one tab"
- not every managed-browser feature is guaranteed in this mode
- first attachment to a real user browser remains an explicitly governed action

#### `remote-provider`

CoPaw leases a provider-hosted browser or remote browser endpoint.

Use it for:

- pooled research bodies
- remote/CDP-hosted browser capacity
- environments where the runtime cannot or should not own the local browser directly

Characteristics:

- capability and recovery depend partly on provider durability and provider features
- parallel scale is stronger than a single local foreground browser body
- provider-specific anti-bot or stealth features must never be treated as baseline CoPaw guarantees

Rules:

- `managed-isolated` is the default browser mode for deterministic execution and acceptance work
- `attach-existing-session` is first-class and must be documented everywhere the system reasons
  about browser recovery
- unsupported mode-specific capabilities must surface as explicit gaps, not be silently faked
- no mode may imply "CoPaw can freely operate any page"; site contracts, auth state, and
  governance still apply

### 4.6 Browser Capability Matrix

The browser runtime contract must distinguish baseline capabilities from mode-dependent
capabilities.

| Capability | `managed-isolated` | `attach-existing-session` | `remote-provider` | Contract |
| --- | --- | --- | --- | --- |
| navigation + DOM read/write | baseline | baseline | baseline | core browser operator surface |
| multi-tab / window continuation | baseline | baseline | baseline | lease scope must be explicit |
| authenticated continuation | supported | first-class | provider-dependent | human-established auth is valid input |
| file upload | baseline | baseline | provider-dependent | verifier must confirm file state changed |
| download capture | baseline | mode-dependent | provider-dependent | unsupported paths must surface explicit gaps |
| PDF export / print-to-file | baseline | mode-dependent | provider-dependent | no fake green on unsupported modes |
| cookies/storage inspection + controlled mutation | baseline | mode-dependent | provider-dependent | tied to session/storage scope |
| locale/timezone/device/geolocation override | baseline | mode-dependent | provider-dependent | not assumed in attached real-user browsers |
| resume / rebind / reattach | baseline | first-class | provider-dependent | recovery path must be recorded in state/evidence |

Contract notes:

- authenticated continuation is a first-class browser task, but automated login, CAPTCHA
  clearance, and MFA solving are not baseline guarantees
- `attach-existing-session` exists primarily to continue work in an already-authenticated real
  browser, not to pretend all local browser features are controllable
- download capture, PDF export, storage mutation, and locale/timezone/device overrides are
  mode-dependent and must be surfaced as such in runtime health and UI
- a coarse `browser_surface_ready` signal is insufficient without a mode-scoped capability view

### 4.7 Browser Session Contract

A browser body may own one tab, a tab group, or a browser-scoped authenticated session. The
lease scope must therefore be explicit.

Browser session state must carry at least:

- browser mode
- lease scope (`single-tab / tab-group / browser-wide`)
- login state
- profile/attach/provider references needed to recover the session truthfully
- last verified page anchors rather than only raw action payloads

Evidence and verification rules:

- success must be verified from real page state such as URL/title/DOM anchors, not only tool
  return payloads
- evidence should record observed-before, action, observed-after, verification outcome, and
  active tab/session identity
- if verification falls back from semantic readout to visual fallback, the evidence must say so

Recovery rules:

- browser recovery continues to map to existing environment vocabulary:
  `resume-environment / rebind-environment / attach-environment / fresh`
- `attach-existing-session` recovery must re-attach to the same real browser scope or fail
  explicitly; it must not be reconstructed from prompt memory alone
- if a mode cannot support a requested operation after recovery, the runtime must emit a visible
  capability gap or governed handoff instead of pretending success

### 4.8 Browser Site Contract

CoPaw should not treat every authenticated or mutating website as a generic DOM surface.

For known browser targets, execution must resolve a site contract that describes:

- what class of system/site this is
- whether the current work is read-only research, authenticated continuation, or mutating writer work
- which action classes are supported in each browser mode
- which actions require `auto / guarded / confirm`
- whether manual login, CAPTCHA completion, or MFA completion is expected to be human-mediated
- which verification anchors are authoritative after an action
- whether uploads/downloads/PDF/storage mutation are supported for this site/session combination

Boundary:

- this is not a second main chain or a second browser-truth store
- site contract is execution-side product contract metadata attached to existing capability,
  workflow, environment, and session reasoning
- if no site contract exists, generic read-only exploration may proceed, but authenticated or
  mutating writer flows should not silently proceed as if fully supported

Policy:

- site contract should be resolved before writer work starts, not only after an action fails
- a browser body without an applicable site contract should surface a launch blocker, governed
  handoff, or read-only downgrade rather than guessing through the site blindly
- "works on one page" is not enough; the contract must reflect the whole site/system interaction
  shape relevant to the workflow

### 4.9 Human Handoff and Return Contract

Human takeover is a formal execution state, not a hidden interruption.

Valid handoff cases include:

- manual login into an authenticated system
- CAPTCHA or MFA completion
- ambiguous writer confirmation where the browser body cannot safely continue autonomously
- recovery rescue after drift, broken anchors, or lost browser continuity

Rules:

- handoff must preserve the current assignment/body/session truth rather than spawning a shadow
  thread of execution
- the system must persist who the browser was handed to, why, from which checkpoint, and what
  condition allows return
- after a human returns the browser to an execution agent, the agent must re-observe and
  re-verify the live page before continuing
- the main brain may supervise or request the handoff, but it does not become the browser driver;
  the resumed owner remains an execution-side body/agent relationship

Return outcomes:

- `resume-after-human-step`
- `resume-after-human-login`
- `resume-after-human-recovery`
- `manual-only-terminal`

No browser session may silently flip between human and agent control without leaving evidence,
checkpoint, and return-state facts.

### 4.10 Windows-First Desktop Host Contract

This repository should treat Windows as the primary desktop runtime target.

The target shape is not a macOS companion pattern. The formal default is:

- Windows host runtime
- Windows foreground desktop body
- Windows app/window/control observation and actuation
- Windows-native recovery and lease semantics

The desktop host must provide at least:

- active foreground window identity
- window tree / process identity / handle references where available
- accessibility/control metadata where available
- screenshot and region-state capture
- controlled keyboard/mouse/clipboard primitives
- focused window switching and app activation
- durable host/session facts for recovery

Rules:

- current and future Windows desktop control should remain execution-agent-owned body runtime,
  even if some primitives come from adapters/providers
- Windows-first does not forbid future remote workers, but local Windows host semantics are the
  baseline contract
- desktop host truth must not live only inside adapter process memory
- loss of foreground focus, active window drift, or account/window contention must become formal
  runtime facts, not hidden operational trivia

### 4.11 Desktop App Contract

Desktop applications should not be treated as generic "click somewhere on screen" targets.

For known applications, execution should resolve an app contract that describes:

- `app_identity`
- `window_scope`
- `control_channel`
- `app_contract_status`
- `writer_lock_scope`
- `manual_handoff_policy`
- `verification_anchor_strategy`

Windows-first control policy:

- accessibility/window/control tree first when available
- process/window identity next
- vision fallback only when the app cannot expose reliable semantic/control anchors

Contract notes:

- `window_scope` should distinguish `single-window / window-group / app-wide`
- `writer_lock_scope` should cover both the live window and the underlying account/document scope
- `app_contract_status` should distinguish at least
  `missing | read-only | writer-ready | handoff-required | blocked`
- applications with real account/session state must not be treated as stateless desktop canvases
- "Win32 API returned success" is not enough; the contract must define how real app state change
  is verified

Valid desktop handoff cases include:

- Windows login or unlock requirement
- native app login/MFA
- unknown modal dialog or privileged OS prompt
- broken focus / lost window ownership / ambiguous destructive confirmation

After human return, the execution agent must re-observe:

- active window identity
- focused control or region
- app contract status
- last verified state anchor

before resuming writer work.

## 5. Formal Object Mapping

This spec intentionally does not introduce a second first-class truth vocabulary. New runtime language must map back to existing formal objects.

| New runtime language | Formal object mapping |
| --- | --- |
| `ComputerHost` | runtime-host level environment runtime + environment registry host/process identity |
| `AgentBody` | `EnvironmentMount` subtype with execution-body semantics |
| `BodySession` | `SessionMount` subtype for live browser/desktop/document session state |
| `BodyLease` | `SessionMount` lease metadata and resource-slot lease records |
| `SurfaceHostContract` | shared environment/session metadata projected into Runtime Center and workflow launch blockers |
| `BrowserSiteContract` | `CapabilityMount`/workflow/environment metadata + session-linked site contract refs + launch blockers |
| `DesktopAppContract` | capability/workflow/environment metadata + window/account lock scope + session-linked app contract refs |
| `HumanHandoff` | `DecisionRequest` + `AgentCheckpointRecord` + `EvidenceRecord` + session handoff metadata |
| `BodyCheckpoint` | `AgentCheckpointRecord` + runtime frame snapshots |
| `BodyScheduler` | environment/resource lease services + execution-plane scheduling policy |

The data model must remain rooted in:

- `EnvironmentMount`
- `SessionMount`
- `AssignmentRecord`
- `TaskRecord`
- `TaskRuntimeRecord`
- `AgentCheckpointRecord`
- `EvidenceRecord`
- `AgentReportRecord`

## 6. Execution Contract

Every execution agent body must run an explicit loop:

1. `observe`
2. `interpret`
3. `plan-next-step`
4. `act`
5. `verify`
6. `record-evidence`
7. `decide-continue-or-recover`

Rules:

- no action may be considered successful without post-action verification
- no verification may rely only on tool return payloads
- verification must read the actual surface state again
- every loop iteration must leave a structured checkpoint

## 7. Multi-Agent Concurrency Contract

Real computer resources are not all safely parallel.

CoPaw must treat resources in four classes:

### 7.1 Exclusive Resources

One writer at a time:

- a foreground desktop body
- a WeChat window/account session
- a single document being actively edited
- a single authenticated browser backend session when actions mutate state

### 7.2 Parallel Read Resources

Can run concurrently:

- independent browser read-only sessions
- independent research browser contexts
- filesystem reads
- document analysis on copies/snapshots

### 7.3 Pooled Resources

Can scale with more bodies:

- browser contexts
- sandboxed browser runtimes
- VM/RDP/isolated desktop workers

### 7.4 Queued Side-Effect Resources

Must serialize or pass policy gates:

- customer messaging
- publishing
- account registration
- money movement
- irreversible external submissions

## 8. Governance Contract

Governance should be minimized, but not deleted.

The right model is:

- keep only `auto / guarded / confirm`
- move most policy into identity/site/action contracts
- keep a minimal runtime confirmation boundary for real external side effects

Examples:

- read page content: `auto`
- internal drafting inside a leased writer body: `auto` or `guarded`
- customer-facing message send: `guarded` by default
- account creation / irreversible submission / money movement: `confirm`

Browser-specific boundaries:

- first attach into a real user browser session is at least `guarded`, and may escalate to
  `confirm` by site/action contract
- authenticated writer work without a resolved site contract should default to a blocker or
  governed handoff, not optimistic auto-execution
- CAPTCHA, anti-bot clearance, and MFA remain human-in-the-loop unless a provider/site contract
  explicitly narrows that boundary
- human login/CAPTCHA/MFA completion is a formal handoff path, not an invisible side effect
- publish/send/submit/transfer actions remain governed by the action itself, not weakened by the
  fact that the runtime has a live browser body

Windows desktop-specific boundaries:

- known Windows app writer work without a resolved `app contract` should default to blocker or
  governed handoff, not optimistic execution
- Windows unlock, UAC/privileged OS prompts, and native app login/MFA remain human-in-the-loop
  unless an explicit contract narrows that boundary
- destructive desktop actions performed under `vision-fallback` should not silently inherit the
  same trust as accessibility/window-tree verified actions
- customer-facing publishing, messaging, financial, or irreversible submission actions remain
  governed by the underlying action contract even when initiated through a foreground desktop body

The runtime must not re-expand into many approval levels.

## 9. Recovery Contract

Recovery is a first-class requirement.

If a body is interrupted, the system must be able to answer:

- which assignment owns this body
- which surface was active
- what the last successful verified step was
- what failed
- whether the body can be resumed, rebound, or must be recreated

Browser and desktop recovery must not stay as ad-hoc process memory only.

The end-state is:

- live handles are represented through environment/session mounts
- resumability is visible through formal recovery metadata
- main-brain supervision can reason over body health without directly driving the body

## 10. Real Acceptance Suite

This architecture is only valid if real tasks pass.

The baseline acceptance suite must include at least:

### 10.1 Browser

- complete a managed-isolated flow that reads a real page, fills a real form, submits it, and
  verifies the post-submit state
- attach to an already-authenticated browser session and continue backend work across navigation
  and tab changes
- require a site contract or explicit governed handoff before authenticated writer work on a known
  backend/admin surface
- execute upload/download/PDF flows where the current browser mode supports them
- emit an explicit unsupported/capability-gap result when the requested browser operation is not
  available in the current mode

### 10.2 Desktop App

- open a real desktop app
- focus the right target region/control
- perform input/click operations
- verify the app state actually changed
- require an app contract or explicit handoff before known Windows writer flows
- survive a modal/UAC/login interruption and resume only after a fresh window/control re-observe

### 10.3 Document/File

- create a file/document
- write content
- save it
- reopen and verify exact content

### 10.4 Recovery

- interrupt an executing body
- reload/rebind runtime state
- continue from the last verified checkpoint instead of restarting blindly
- hand the browser to a human for login/recovery and then resume from a fresh re-observe step

### 10.5 Multi-Agent Scheduling

- multiple research agents can run in parallel
- only one writer can hold a document write lease
- a customer-facing messaging body is exclusive and visible in scheduling state

## 11. Implementation Order

The implementation order should be:

1. formalize the architecture and object mapping
2. build the real acceptance harness first
3. refactor browser operator around observe/act/verify
4. refactor desktop/document operator around observe/act/verify
5. introduce body leases, scheduler, and exclusive resource locking
6. unify recovery into the main execution chain
7. shrink legacy tool-first paths once the new body runtime is live

## 12. Non-Goals

This spec does not authorize:

- making the main brain directly control windows/pages again
- replacing all surfaces with screenshot-only automation
- deleting all governance boundaries
- allowing multiple agents to mutate the same document/account/window simultaneously
- accepting tool payload success as proof of real-world task success
- claiming that CoPaw can arbitrarily operate any page in every browser mode
- silently treating known authenticated sites as generic browser surfaces without site contract or
  explicit handoff policy

## 13. Success Criteria

This spec is considered realized only when:

- execution agents, not the main brain, own computer-operation bodies
- the execution-side runtime is clearly understood as `Symbiotic Host Runtime`, not merely a bigger UI automation bundle
- browser/desktop/document actions all run through observe/act/verify loops
- all live browser/desktop/document surfaces project shared `Surface Host Contract` facts
  including `host_mode / lease_class / access_mode / session_scope / handoff_state / resume_kind`
- at least one durable `Seat Runtime` / `Host Companion Session` path exists for Windows-first execution
- a task can be viewed as a live workspace instead of only isolated surface handles
- host changes can enter the runtime loop as formal recovery/handoff signals rather than only raw logs
- browser runtime explicitly distinguishes `managed-isolated / attach-existing-session /
  remote-provider` and surfaces mode-scoped capability/recovery contracts
- authenticated browser writer work resolves site contract or explicit handoff policy before
  acting
- Windows desktop writer work resolves app contract or explicit handoff policy before acting
- body/resource leasing prevents destructive contention
- browser and desktop live state become formally recoverable execution resources
- the real acceptance suite passes on the target machine
