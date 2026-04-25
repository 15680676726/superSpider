# Unified MCP Activation Lifecycle Design

## 0. Goal

Generalize MCP-style capability activation into one truthful lifecycle that covers:

- `stateless`
- `auth-bound`
- `host-attached`
- `workspace-bound`

The target is not "connect more things."

The target is:

- install does not overclaim readiness
- the system auto-resolves real recoverable failures
- only objectively human-only blockers surface to the user
- all activation/recovery still stays on canonical `CapabilityMount / EnvironmentMount / SessionMount / MCP runtime` truth

This design explicitly extends the already-landed `browser-companion` first slice into a repo-wide lifecycle contract.

---

## 1. Why This Work Exists

The repo already has most of the needed pieces:

- canonical `CapabilityMount`
- canonical `EnvironmentMount / SessionMount`
- canonical install-template `doctor / example-run / install`
- typed `MCPClientRuntimeRecord` / `reload_state`
- `EnvironmentService` cooperative host/session facade
- bounded `browser-companion` self-heal on the install-template surface

But it still does **not** have one shared activation plane.

Current gaps:

- each install-template still decides activation/readiness differently
- `installed` is too easy to confuse with `usable`
- MCP runtime connect/reload truth is typed, but not yet mapped into one shared user-facing activation contract
- host-attached recovery has landed only for `browser-companion`
- auth/token/session/scope failures still do not share one retry/heal vocabulary

If this is not unified now, the repo will drift into a fourth lifecycle system:

- install-template local heuristics
- MCP manager runtime state
- environment host/session state
- product-facing "ready/degraded/blocked" strings

That is exactly the kind of parallel truth expansion this repo is trying to avoid.

---

## 2. Scope

This design covers the activation/readiness/self-heal lifecycle for MCP-style and install-template-driven capabilities.

It includes:

- shared activation state model
- shared failure taxonomy
- shared self-heal orchestration contract
- shared user-visible status language
- shared mapping from concrete capability class -> remediation strategy
- rollout path from the current `browser-companion` slice to the full four-class model

It does **not** introduce:

- a second durable activation store
- a second MCP manager
- template-specific product wording as the source of truth
- fake recovery claims without a real remediation action
- silent fallback that hides a real blocker

---

## 3. Architectural Position

This is not a new truth source.

The lifecycle must be implemented as a **derived execution plane** over existing truth:

- `CapabilityMount` answers: what is installed/adopted/governed
- `EnvironmentMount / SessionMount` answer: what host/session/scope is currently mounted
- `MCPClientRuntimeRecord` answers: what MCP runtime client is currently doing
- activation/self-heal answers: what extra bounded actions are required to move from current truth to usable truth

So the rule is:

- activation is an orchestrator
- canonical truth still lives where it already lives

No new long-lived activation database should be added.

---

## 4. Shared Lifecycle States

All four classes must map to one shared activation status set:

- `installed`
- `activating`
- `ready`
- `healing`
- `waiting_human`
- `blocked`

### State meanings

- `installed`
  - capability exists
  - no successful readiness proof yet

- `activating`
  - the system is currently running an initial readiness path

- `ready`
  - the latest canonical re-read proves the capability is usable for its declared class

- `healing`
  - the system detected a recoverable failure and is running bounded remediation

- `waiting_human`
  - further progress requires one objectively human-only action

- `blocked`
  - the capability cannot continue because the current blocker is not recoverable by the system under current policy/runtime constraints

---

## 5. Shared Failure Taxonomy

Only one failure vocabulary should be exposed to product/read surfaces.

### System-recoverable families

- `dependency_missing`
- `adapter_offline`
- `session_unbound`
- `host_unavailable`
- `token_expired`
- `scope_unbound`
- `runtime_unavailable`
- `policy_retryable_block`

These should drive self-heal first, not immediate user interruption.

### Human-only families

- `human_auth_required`
- `captcha_required`
- `two_factor_required`
- `explicit_human_confirm_required`
- `host_open_required`

These are the only families that should end in `waiting_human`.

### Hard blocked families

- `policy_blocked`
- `unsupported_host`
- `invalid_capability_contract`
- `broken_installation`

These end in `blocked` unless a later mutation changes the underlying truth.

---

## 6. Shared User-Facing Language

The user should not see internal runtime terms such as:

- `attach transport`
- `provider_session_ref`
- `overlay_scope`
- `reload_state`

The front-end/product-facing language must collapse to:

- `可直接使用`
- `系统正在自动恢复`
- `需要登录授权一次`
- `请先打开目标应用`
- `当前受策略限制`

This is a presentation rule, but it depends on the shared activation taxonomy above.

---

## 7. Shared Activation Result Contract

Activation should use one structured result shape across install-template surfaces and later runtime-center/product read surfaces.

Recommended fields:

- `capability_id`
- `activation_class`
- `status`
- `reason_code`
- `summary`
- `required_action`
- `auto_heal_attempted`
- `auto_heal_operations[]`
- `retryable`
- `environment_id`
- `session_mount_id`
- `scope_ref`
- `runtime_snapshot`
- `evidence_refs[]`

Important constraint:

- this contract is a **derived result**
- it is not a new durable store

It may be embedded in:

- install-template example-run results
- doctor detail/support payloads
- Runtime Center projections
- bounded runtime metadata

---

## 8. Shared Activation Flow

Every capability class should follow the same top-level lifecycle:

1. resolve canonical context
2. read current readiness truth
3. if ready, return success without mutation
4. if not ready, classify blocker into shared taxonomy
5. if blocker is system-recoverable, run bounded remediation
6. re-read canonical truth
7. only return `ready` if the retried canonical read proves it
8. otherwise map to `waiting_human` or `blocked`

Hard rule:

- success must always come from a fresh canonical re-read
- never from assuming the remediation worked

---

## 9. Class-Specific Strategy Mapping

The shared flow above stays the same.

What changes by class is the remediation strategy.

### 9.1 `stateless`

Examples:

- pure API-backed MCPs
- registry/search/describe style capabilities
- execution surfaces that do not require long-lived host/session continuity

Readiness requirements:

- capability enabled
- runtime client available if needed
- dependency contract valid

Typical remediation:

- rebuild/reconnect runtime client
- refresh provider selection
- retry on mirror/fallback source if applicable

Canonical truth dependencies:

- `CapabilityMount`
- `MCPClientRuntimeRecord`

No `EnvironmentMount / SessionMount` requirement by default.

### 9.2 `auth-bound`

Examples:

- OAuth-backed external APIs
- token/header/env-bound providers

Readiness requirements:

- capability enabled
- runtime client available if needed
- auth material valid

Typical remediation:

- token refresh
- runtime rebuild using current auth policy
- rebind refreshed secret source
- retry readiness probe

Escalate to `waiting_human` only when:

- first consent is required
- token refresh cannot proceed without user login
- captcha/2FA/explicit approval is required

Canonical truth dependencies:

- `CapabilityMount`
- `MCPClientRuntimeRecord`
- existing secure config/auth source

### 9.3 `host-attached`

Examples:

- `browser-companion`
- `document-office-bridge`
- `host-watchers`
- `windows-app-adapters`

Readiness requirements:

- capability enabled
- canonical host/session mount exists
- host runtime or adapter is available
- host-specific truth is present on canonical `EnvironmentMount / SessionMount`

Typical remediation:

- resolve or create canonical `SessionMount`
- ensure host runtime exists
- register canonical host truth through `EnvironmentService`
- retry canonical projection

This class must never create a side store for host readiness.

### 9.4 `workspace-bound`

Examples:

- session-scoped MCP overlays
- project/cwd/profile/tenant-bound MCPs
- scope-local additive/replace runtime mounts

Readiness requirements:

- capability enabled
- required scope is identified
- required scoped runtime/overlay is mounted

Typical remediation:

- resolve work context / scope owner
- mount or rebuild scoped overlay
- rebind runtime in the target scope
- retry scoped readiness probe

Canonical truth dependencies:

- `CapabilityMount`
- `MCPClientRuntimeRecord.reload_state`
- `overlay_scope / overlay_mode`
- `EnvironmentMount / SessionMount` where applicable

---

## 10. Where The Logic Lives

The unified lifecycle should land in shared capability code, not inside every template.

Recommended landing zones:

- `src/copaw/capabilities/activation_models.py`
  - shared activation status/reason/result models

- `src/copaw/capabilities/activation_runtime.py`
  - shared orchestrator
  - shared retry/heal budget
  - shared mapping from failure -> remediation path

- `src/copaw/capabilities/activation_strategies.py`
  - class-specific strategy implementations:
    - stateless
    - auth-bound
    - host-attached
    - workspace-bound

- `src/copaw/capabilities/install_templates.py`
  - call the shared activation runtime instead of embedding per-template lifecycle logic

- `src/copaw/app/routers/capability_market.py`
  - keep `doctor` read-only
  - expose an explicit `activate` write surface over the shared activation plane
  - return one shared activation contract from `doctor / activate / example-run`

- `src/copaw/capabilities/service.py`
  - route the unified capability execution front-door through activation when the capability class requires it
  - do not require humans to manually run `doctor` or `example-run` before real execution

- `src/copaw/app/mcp/runtime_contract.py`
  - map manager runtime signals into the shared activation taxonomy

- `src/copaw/app/mcp/manager.py`
  - remain the MCP runtime truth producer
  - do not absorb product activation logic

- `src/copaw/environments/service.py`
  - remain the canonical host/session mutation surface
  - do not absorb lifecycle orchestration policy

---

## 11. Product Surface Rules

### Doctor

`doctor` remains diagnostic-first and read-only.

It may expose:

- current activation class
- current derived activation status
- reason taxonomy
- whether auto-heal is possible
- recommended activation entry surface

But doctor should not silently mutate the system in this rollout.

It must not:

- create or bind canonical mounts
- refresh or persist auth state
- reconnect or rebuild runtimes
- perform host/application launch side effects

### Activate

`activate` is the explicit bounded activation/self-heal write surface.

It may:

- call the shared activation orchestrator
- run bounded remediation
- retry
- return structured activation proof
- stop in `waiting_human` or `blocked` with the same shared taxonomy as `doctor`

It must:

- mutate only through canonical `CapabilityMount / EnvironmentMount / SessionMount / MCP runtime` truth
- re-read canonical truth before claiming `ready`
- remain the one formal mutation surface for product-triggered activation

### Example Run

`example-run` remains a product exercise surface, but it should no longer own lifecycle policy.

It may:

- call `activate` first when the example needs a usable runtime
- run a bounded proof action on the same canonical context
- return execution proof plus the shared activation contract

It should not become:

- the only activation write surface
- a hidden substitute for real execution front-doors

### Real Execution Front-Doors

Real execution entry points must consume the same activation plane instead of asking the
user to pre-run health tools manually.

This includes the unified capability execution front-door and any higher-level runtime
entry that delegates through it.

Execution should follow this order:

1. resolve canonical capability/environment/session context
2. derive current activation status
3. if required, call the shared activation plane
4. proceed only when the post-activation canonical re-read is `ready`
5. otherwise return truthful `waiting_human` / `blocked` semantics

This prevents the system from saying "please run doctor/attach/activate first" when it
can objectively repair and retry on its own.

### Install

`install` still means:

- capability/package/client/template is installed or provisioned

It must **not** claim:

- automatically ready forever
- formally adopted by every seat/scope

### Runtime Center / Capability Market Read Surfaces

These should later consume the same activation contract instead of inventing local summaries.

---

## 12. Bounded Self-Heal Rules

Self-heal must be real and bounded.

### Allowed

- reconnect
- rebuild runtime client
- refresh token
- resolve/create canonical mount
- register canonical host truth
- mount/rebuild scoped overlay
- retry once or within a small explicit budget

### Not allowed

- infinite retry
- hidden fallback that changes the meaning of the capability
- mutating canonical truth without going through the canonical service
- claiming success before canonical re-read

Recommended default budget:

- one remediation path per attempt
- one canonical retry after remediation

---

## 13. Evidence Expectations

Important activation/heal actions should be evidence-visible.

Minimum expectations:

- activation operations returned in result payload
- canonical runtime/env/session ids returned
- blocker class/reason returned on failure

Later extension:

- structured `EvidenceRecord` for important remediation runs
- Runtime Center activation/heal history

This design does not require that evidence extension to land in the first implementation wave.

---

## 14. Rollout Sequence

This should not ship as one giant all-at-once rewrite.

### Phase 1: shared contract

- land `activation_models + activation_runtime`
- keep existing first-slice `browser-companion` behavior
- move that behavior behind the shared orchestrator

### Phase 2: complete `host-attached`

- migrate:
  - `browser-companion`
  - `document-office-bridge`
  - `host-watchers`
  - `windows-app-adapters`

### Phase 3: add `workspace-bound`

- map scope-local MCP overlays and scoped runtime rebuilds to the shared contract

### Phase 4: add `auth-bound`

- map token refresh / human auth boundary to the shared contract

### Phase 5: add `stateless`

- map pure runtime-client rebuild/retry into the same contract

### Phase 6: read-surface convergence

- Runtime Center / Capability Market read surfaces consume shared activation truth

---

## 15. Non-Goals

This design does not try to:

- replace `MCPClientManager`
- replace `EnvironmentService`
- rebuild the external-source lifecycle model
- add a new activation database
- make every external dependency magically self-solvable

It only ensures there is one honest lifecycle contract for readiness and self-heal.

---

## 16. Acceptance Standard

The lifecycle is only considered landed when:

1. all four classes map to one shared activation status and reason taxonomy
2. install-template example-run surfaces call the shared activation plane instead of open-coding lifecycle logic
3. `doctor` stays diagnostic-first and read-only while `activate` becomes the explicit bounded write surface
4. recoverable failures auto-heal through canonical services
5. real execution front-doors auto-consume the same activation plane instead of requiring manual preflight rituals
6. human-only blockers are the only path that ends in `waiting_human`
7. success is always based on a fresh canonical re-read
8. Runtime Center / product read surfaces can consume the same derived activation truth without inventing template-local wording
