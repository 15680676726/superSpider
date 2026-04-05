# Python Donor Runtime Contract Design

## Goal

Turn supported GitHub/Python open-source donors into formally installable and operable `project-package / adapter / runtime-component` capabilities that can be started, probed, stopped, observed, and governed inside CoPaw without creating a second truth chain.

## Why This Exists

The current donor-first external project path solved only the first half of the problem:

- discover
- install
- resolve entrypoint
- execute a shell command

That is enough to prove materialization, but it is not enough to prove that an open-source project has become a real runtime capability inside CoPaw.

Right now a Python donor such as `OpenSpace` can land as an installed capability and pass `--help`, but it still behaves like a governed shell wrapper rather than a formal runtime component with:

- runtime state
- readiness truth
- process lifecycle
- stop/restart semantics
- Runtime Center visibility

This design closes that gap for supported Python donors.

## Scope

This design covers only:

- GitHub-hosted Python donors
- repositories installable through the current governed `pip`-based isolated-venv contract
- two runtime shapes:
  - short-lived CLI/tool donors
  - long-running service donors

This design does not cover:

- arbitrary non-Python donors
- arbitrary build systems
- arbitrary repositories with undocumented startup flows
- project-specific deep business adapters as a prerequisite for first-class runtime support

## Architecture Boundary

This design must stay inside CoPaw's existing formal architecture.

It is not allowed to create:

- a second capability manager
- a parallel runtime state store
- a donor-only environment system

The formal mapping is:

- capability/package identity remains on the existing donor/package/source/candidate/trial/lifecycle spine
- runtime lifecycle truth is added as a formal runtime record attached to existing `CapabilityMount / EnvironmentMount / SessionMount / EvidenceRecord` semantics
- Runtime Center consumes projections of that same truth

In terms of the repository's architecture questions:

1. This belongs primarily to `capabilities / state / environment / evidence`.
2. The single truth source remains the formal capability + runtime/evidence state chain.
3. It must not bypass the unified capability execution/governance path.
4. It must not introduce a fourth capability vocabulary.
5. It must emit start/ready/run/stop/restart evidence.
6. It is intended to replace the current "external Python project = shell command only" limitation.

## Supported Donor Contract

### Supported Python CLI/Tool Donors

A donor is supported as a CLI/tool donor when all of the following are true:

- it can be installed through the current isolated-venv `pip` contract
- it exposes a stable `console_script` or `python -m package` entrypoint
- it is intended to run as a short-lived command rather than a resident service
- its execution output can be captured through the existing evidence sink

### Supported Python Service Donors

A donor is supported as a service donor when all of the following are true:

- it can be installed through the current isolated-venv `pip` contract
- it exposes a stable `console_script` or `python -m package` entrypoint
- it has at least one machine-verifiable readiness signal:
  - HTTP health/readiness endpoint
  - port binding probe
  - stdout ready marker
- it accepts a standard stop path:
  - governed process terminate/kill
  - or an explicit project stop command

### Explicit Non-Supported Cases

The following are outside the first supported contract:

- projects that require manual document reading just to discover their startup path
- projects with no stable entrypoint
- projects with no usable readiness signal
- projects whose startup requires a bespoke handwritten adapter before first execution
- projects that require multi-service orchestration not expressible inside the current bounded runtime contract

## Formal Runtime Shapes

Supported Python donors are classified into exactly two runtime shapes:

- `cli`
- `service`

Classification is not a new user-facing capability type. It is runtime contract metadata attached to the existing capability landing:

- `project-package`
- `adapter`
- `runtime-component`

Examples:

- `project:black` -> `project-package + cli`
- `adapter:pywinauto` -> `adapter + cli`
- `runtime:openspace` -> `runtime-component + service`

## Formal Runtime Truth

### New Formal Record

Add a formal runtime record for installed external Python donors:

- `ExternalCapabilityRuntimeRecord`

This record represents the current runtime truth of an installed donor capability. It is not a replacement for package truth. It is the missing runtime half of the donor model.

### Required Fields

The runtime record should minimally carry:

- `runtime_id`
- `capability_id`
- `capability_kind`
- `runtime_kind`
- `status`
- `enabled`
- `install_scope`
- `session_scope`
- `environment_ref`
- `session_mount_id`
- `environment_root`
- `python_path`
- `scripts_dir`
- `command`
- `cwd`
- `process_id`
- `port`
- `health_url`
- `ready_probe_kind`
- `ready_probe_config`
- `stop_strategy`
- `start_timeout_sec`
- `last_started_at`
- `last_ready_at`
- `last_stopped_at`
- `last_exit_code`
- `last_error`
- `last_evidence_id`
- `metadata`

### Status Values

The first formal status family should be:

- `installed`
- `starting`
- `ready`
- `degraded`
- `stopped`
- `failed`

This state must be persisted, queryable, and projected into Runtime Center. It must not be inferred ad hoc from a one-shot shell result.

## Runtime Lifecycle Contract

### Install-Time Outcome

`/capability-market/projects/install` remains the install/materialization front-door.

After install, the system must:

1. resolve package entrypoint metadata
2. classify the donor as `cli` or `service`
3. materialize the installed capability config
4. create or refresh the donor runtime record
5. return the runtime contract summary in the install response

### CLI Lifecycle

CLI donors support:

- `describe`
- `run`
- `healthcheck`

CLI donors do not create a long-lived resident process. Their runtime truth still exists, but their active process lifecycle is per execution.

### Service Lifecycle

Service donors support:

- `describe`
- `start`
- `healthcheck`
- `stop`
- `restart`

State transitions:

- `installed -> starting`
- `starting -> ready`
- `starting -> failed`
- `ready -> degraded`
- `ready -> stopped`
- `failed -> starting`
- `degraded -> restarting/starting -> ready|failed`

The first version does not need a complex supervisor. It does need truthful lifecycle state and governed actions.

## Detection and Contract Resolution

### Install-Time Detection Order

The runtime contract resolver should work in this order:

1. inspect package metadata:
   - distribution name
   - package version
   - console scripts
   - entry module
2. inspect lightweight help output:
   - service-shaped flags such as `--host`, `--port`, `serve`, `server`, `api`, `daemon`, `worker`
3. inspect configured donor hints when present
4. attempt bounded runtime validation:
   - CLI smoke command
   - service start + ready probe

### Ready Probe Kinds

The first supported ready probe kinds are:

- `http`
- `port`
- `stdout`
- `none` for CLI

### Thin Hint Layer

The system may keep a thin optional hint layer for hard-to-detect but still supported donors.

Hints may specify only bounded runtime contract details such as:

- preferred runtime kind
- default startup args
- default port
- health path
- stdout ready marker
- stop strategy

Hints must not become a per-project handwritten execution adapter framework. The default path remains generic contract resolution first.

## Execution Model

### Install Is Not Runtime

The current model collapses installation and execution into the same shell abstraction. That is the core defect being corrected.

After this design lands:

- install truth lives in external package config + donor/package/source truth
- runtime truth lives in `ExternalCapabilityRuntimeRecord`
- execution actions mutate runtime truth and emit evidence

### Capability Execution

The capability execution layer must stop treating every external donor as "pick one shell command and run it".

Instead:

- `cli` actions call the bounded run path
- `service` actions call lifecycle verbs
- raw arbitrary `command` execution must no longer be the primary runtime contract for supported donors

The capability execution layer may retain an escape hatch for unsupported/manual cases, but supported Python donors must prefer the formal action contract.

## API Surface

### Install/Search Front-Door

Keep:

- `POST /capability-market/projects/search`
- `POST /capability-market/projects/install`

Extend install/search payloads to expose runtime contract summaries:

- `runtime_kind`
- `supported_actions`
- `ready_probe_kind`
- `health_url`
- `port`

### Runtime Action Front-Door

Add formal runtime actions for installed external donors.

Recommended operator-facing endpoints:

- `GET /runtime-center/capabilities/external-runtimes`
- `GET /runtime-center/capabilities/{capability_id}/runtime`
- `POST /runtime-center/capabilities/{capability_id}/runtime/run`
- `POST /runtime-center/capabilities/{capability_id}/runtime/start`
- `POST /runtime-center/capabilities/{capability_id}/runtime/healthcheck`
- `POST /runtime-center/capabilities/{capability_id}/runtime/stop`
- `POST /runtime-center/capabilities/{capability_id}/runtime/restart`

This split keeps:

- discovery/install under capability market
- runtime operations under Runtime Center/operator surfaces

## Runtime Center Visibility

Runtime Center must show external donor runtime truth as first-class operator data.

Minimum read-model fields:

- capability identity
- landing kind: `project-package / adapter / runtime-component`
- runtime kind: `cli / service`
- runtime status
- enabled state
- process id
- port
- health URL
- ready probe kind
- command/cwd summary
- last started
- last ready
- last stopped
- last error
- latest evidence link
- supported actions

This is required so installed donors stop being invisible shells and become explicit runtime assets.

## Evidence Contract

Every formal runtime action must emit evidence:

- install
- classify
- start
- ready
- healthcheck
- run
- stop
- restart
- failure/timeout

Evidence metadata must preserve:

- `capability_id`
- `runtime_id`
- `runtime_kind`
- `action`
- `process_id`
- `port`
- `health_url`
- `ready_probe_kind`
- `source_url`
- `package_ref`

## Verification Standard

This work is complete only when all three layers are true.

### 1. Unit/Integration

Must cover:

- CLI contract resolution
- service contract resolution
- lifecycle status transitions
- ready probe success/failure
- stop/restart behavior
- Runtime Center read-model projection

### 2. Repository Regression

Must preserve:

- capability market
- capability catalog
- capability execution
- donor/source/package truth
- evidence sinks
- Runtime Center capability read surfaces

### 3. Live Smoke

At least two real Python donors must be validated:

- one CLI/tool donor
- one service donor

The live smoke bar is:

- discover
- install
- classify
- run or start
- ready or successful one-shot execution
- stop for service donors

`--help` alone is not sufficient evidence for service closure.

## Rollout Recommendation

Implement in this order:

1. formal runtime record + persistence
2. runtime contract resolver for `cli / service`
3. lifecycle executor for `start / healthcheck / stop / restart / run`
4. Runtime Center read-model and endpoints
5. live smoke against one CLI and one service donor

## Non-Goals

This design does not claim:

- all languages are automatically supported
- all Python repos are automatically supported
- all supported donors need zero hints
- OpenSpace-specific business integration is required for phase 1

The goal is narrower and stricter:

Supported Python donors must stop being decorative shell wrappers and become formally operable runtime capabilities.
