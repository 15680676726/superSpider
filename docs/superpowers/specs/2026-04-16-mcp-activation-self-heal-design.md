# MCP Activation Self-Heal Design

## Goal

Give install-template driven MCP-style capabilities one truthful activation path:
`install -> doctor/read -> activate/self-heal -> canonical re-read -> retry`.

The first landed slice targets `browser-companion`, because it already has:

- canonical `CapabilityMount` truth
- canonical `EnvironmentMount / SessionMount` truth
- canonical install-template doctor/example-run surfaces
- a real managed browser runtime that can create a usable browser seat

## Scope

This slice does not try to finish the whole MCP lifecycle in one jump.

It only adds one formal behavior:

- when `browser-companion` example-run finds no usable mounted companion runtime, the
  system may automatically create or rebind a canonical browser session lease, start
  a managed browser runtime, write the resulting companion/attach facts back through
  `EnvironmentService`, and retry the same canonical read path

It does not add:

- a second runtime truth source
- a separate activation store
- fake recovery claims without a real action
- new user-facing internal terms such as `attach transport` or `provider_session_ref`

## Formal Semantics

### Layers

- capability truth stays in `CapabilityMount`
- host/session truth stays in `EnvironmentMount / SessionMount`
- activation/self-heal is an execution-side orchestration over that existing truth
- in the currently landed slice, install-template `example-run` remains the temporary bounded activation entry surface
- in the generalized lifecycle, `doctor` stays read-only and an explicit `activate` surface becomes the formal write entry

### Browser Companion First Slice

`browser-companion` example-run should follow this order:

1. resolve canonical runtime context
2. read current browser companion availability
3. if healthy, return success without mutation
4. if unhealthy but auto-recoverable, run bounded remediation:
   - ensure a canonical browser session lease exists
   - ensure a managed browser runtime session exists
   - register canonical browser companion facts
   - register canonical browser attach facts
5. re-read canonical runtime context
6. return success only if the retried read is now healthy

If remediation cannot be completed, the surface must still return a truthful error.

### Human Boundary

The system should auto-resolve everything it objectively can.

Only these families are allowed to remain human-blocking:

- first-time login/authorization
- captcha
- 2FA / explicit approval
- host application genuinely not present/open when no automatic launch path exists

## Current Slice Constraints

- default general browser work still prefers `browser-local`
- this slice does not change general browser routing
- this slice only makes `browser-companion` capable of self-activating into a truthful,
  canonical managed companion seat when no attached seat is already mounted
- doctor remains diagnostic-only
- until the generalized lifecycle lands, example-run is the bounded recovery surface for this slice
- after generalization, this slice should move behind the shared `activate` surface instead of keeping browser-specific mutation logic in `example-run`

## Evidence / Read Surface Expectations

- success must come from a fresh canonical re-read, not from assuming remediation worked
- returned runtime payload must expose the canonical `session_mount_id`,
  `environment_id`, `browser_companion`, `browser_attach`, and browser runtime snapshot
- operations must show whether auto-recovery actually happened

## Follow-Up Direction

Once this slice is stable, the same pattern should be generalized into a shared MCP
activation lifecycle for:

- stateless capabilities
- auth-bound capabilities
- host-attached capabilities
- workspace/session-bound capabilities
