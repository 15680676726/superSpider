# Four Critical Tracks Acceptance Script

> **For agentic workers:** This document is the execution script for the four tracks that are easiest to over-claim as "basically done" while still lacking real scenario-level sign-off. Use it together with the system real acceptance checklist and do not mark a track accepted unless the evidence bundle is complete.

**Goal:** Provide a strict, human-runnable acceptance script for the four remaining high-risk tracks: capability install to real use, frontend truth consistency, temporal grounding, and failure injection / fail-closed behavior.

**Architecture:** This script does not invent a second acceptance standard. It translates the existing system real acceptance checklist into explicit scenario steps, pass conditions, failure categories, and evidence requirements so each track can be honestly signed off.

**Tech Stack:** FastAPI backend, pytest regression suites, console frontend, Runtime Center, Industry, Buddy flow, capability market, donor/runtime subsystem.

---

## 1. How To Use This Script

This document is not a code-status summary.

It is only for final scenario-level acceptance.

A track may have:

- strong code coverage
- focused regression proof
- real partial smoke proof

and still remain **not accepted** if the exact live scenario below has not been run and recorded.

Every run must produce one explicit evidence bundle with:

- acceptance date
- commit hash
- environment note
- scenario name
- formal truth ids
- API/read-model proof
- frontend-visible proof after refresh/re-entry
- evidence/report ids where applicable
- final result: `passed` or `failed`

If any required proof is missing, the track is still open.

Read this script together with:

- [2026-04-12-critical-tracks-supported-scope-matrix.md](/D:/word/copaw/docs/superpowers/plans/2026-04-12-critical-tracks-supported-scope-matrix.md)
- [2026-04-12-acceptance-run-ledger-template.md](/D:/word/copaw/docs/superpowers/plans/2026-04-12-acceptance-run-ledger-template.md)
- [2026-04-12-failure-injection-methods-table.md](/D:/word/copaw/docs/superpowers/plans/2026-04-12-failure-injection-methods-table.md)
- [2026-04-12-frontend-truth-reconciliation-scenario-table.md](/D:/word/copaw/docs/superpowers/plans/2026-04-12-frontend-truth-reconciliation-scenario-table.md)

---

## 2. Shared Failure Categories

When a scenario fails, do not write "generic functional error".

Use one of these root causes:

- formal truth not created
- state not durable
- read model and write model mismatch
- frontend read old field or old route
- execution happened but no evidence was written
- evidence exists but did not write back into the formal chain
- capability/environment existed but was not truly attached
- refresh/re-entry resolved the wrong instance or wrong thread
- async timing race
- stale cache / stale local binding
- failure was not surfaced and the chain did not fail closed

---

## 3. Track D: Capability Install -> Real Use

### 3.1 What This Track Actually Means

This track is **not** "the capability appears in inventory".

This track only passes when:

- the capability is installed through a formal front door
- the install truth is durable
- the intended seat/runtime path can actually use it
- the next execution turn can really select it
- the result is visible as real execution truth, not only install truth

### 3.2 Current Supported Scope

This acceptance script only signs off the currently supported contract scope:

- skill-style capability path already supported by the formal market/read-model chain
- project donor under the current `Python + GitHub + isolated-venv` contract
- runtime/service donor under the current formal runtime contract

Current examples already proven in code history include:

- `project:black`
- `runtime:openspace`

### 3.3 Out Of Scope For This Track

Do **not** treat any of the following as implied acceptance:

- arbitrary donor from any language
- arbitrary build systems
- arbitrary repository layouts
- arbitrary external protocol
- automatic typed action discovery from any random donor

If those need sign-off, they require a new supported-scope document first.

### 3.4 Acceptance Preconditions

- backend and console are running from the target commit
- capability market front door is available
- Runtime Center capability/read surfaces are available
- a clean evidence bundle template is prepared

### 3.5 Acceptance Scenarios

Run at least these three:

1. Install and use one supported project donor
   - example: `project:black`
   - path: discover -> install -> attach/adopt if required -> execute

2. Install and use one supported runtime/service donor
   - example: `runtime:openspace`
   - path: discover -> install -> start -> ready -> stop

3. Negative case
   - choose one unsupported or intentionally malformed donor/input
   - confirm the system does not pretend install/use succeeded

### 3.6 Pass Conditions

This track passes only if all are true:

- install truth is durable after refresh/re-entry
- intended seat/runtime path shows the capability as truly usable
- the next execution turn actually uses it
- evidence reflects real execution, not just install metadata
- Runtime Center / capability surfaces show the same story
- unsupported or broken case fails explicitly instead of fake success

### 3.7 Required Evidence Bundle

- install request payload
- install job id / task id
- resulting capability id / runtime id
- effective capability read-model proof
- execution proof
- at least one evidence id or runtime action result
- frontend screenshots or equivalent read-surface proof after refresh

---

## 4. Track H: Frontend Truth Consistency

### 4.1 What This Track Actually Means

This track is not "several pages each have tests".

It passes only when the same live scenario shows the same runtime truth across:

- Chat
- Runtime Center
- Industry
- Agent Workbench where relevant

### 4.2 Acceptance Preconditions

- one real live scenario is chosen first
- that scenario has formal truth in the backend
- the operator can open all relevant surfaces without creating a second thread or second instance

### 4.3 Required Scenario Set

At minimum, compare these truth states:

1. empty
2. pending
3. running
4. blocked / handoff / need_more_evidence
5. completed

Do not use five different scenarios.
Use the same formal chain wherever possible so the comparison is honest.

### 4.4 Required Cross-Surface Checks

For the same scenario, confirm:

- status words match in meaning
- empty state appears only when formal truth is really empty
- blocked does not show as active
- pending does not show as nothing there
- refresh does not reopen a stale binding
- re-entry does not switch to a different thread or instance

### 4.5 Pass Conditions

This track passes only if all are true:

- all compared surfaces tell the same story
- refresh/re-entry preserves that story
- no surface silently falls back to stale local truth
- no page invents a synthetic empty state while the formal chain still exists

### 4.6 Required Evidence Bundle

- one shared scenario name
- formal ids used across the comparison
- API/read-model snapshots for each surface
- frontend proof from Chat / Runtime Center / Industry / Agent Workbench
- refresh/re-entry proof
- final reconciliation note explaining why the four surfaces are the same truth

---

## 5. Track K: Temporal Grounding

### 5.1 What This Track Actually Means

This track is not "the system has a time tool somewhere".

It passes only when time-sensitive reasoning is grounded to real runtime time in the real front door and remains consistent after refresh/re-entry.

### 5.2 Acceptance Preconditions

- the current date and timezone for the run are recorded before testing
- the operator records the expected current Beijing time
- chat front door, runtime summaries, and schedule/workflow-facing summaries are all reachable

### 5.3 Required Question Set

Ask all of the following through the real front door:

1. current date
2. current weekday
3. current Beijing time
4. a relative reference using `today`
5. a relative reference using `tomorrow`
6. a relative reference using `next Monday`

Then:

- refresh and ask again
- re-enter and ask again if the flow supports it
- compare with schedule/workflow-facing summaries that expose time-based interpretation

### 5.4 Pass Conditions

This track passes only if all are true:

- answers match the real runtime time basis
- relative-day reasoning uses the same basis
- refresh/re-entry does not shift to a different implicit date
- schedule/workflow-facing surfaces use the same grounded basis
- the result is not free-form model guesswork

### 5.5 Required Evidence Bundle

- wall-clock reference used for the run
- frontend question/answer proof
- any relevant API/read-model proof showing grounded time basis
- refresh/re-entry proof
- schedule/workflow-facing proof

---

## 6. Track L: Failure Injection / Fail-Closed Behavior

### 6.1 What This Track Actually Means

This track is not "there are some failure tests".

It passes only when injected failure is:

- visible
- durable
- closed cleanly
- not disguised as success
- recoverable/replayable through the formal chain when appropriate

### 6.2 Acceptance Preconditions

- one acceptance environment where failure injection is safe
- operator can inspect Runtime Center / chat / related read surfaces after failure
- evidence bundle template prepared before the first injected failure

### 6.3 Required Failure Set

Inject at least one real scenario for each:

1. model timeout
2. tool/runtime failure
3. missing capability attachment
4. handoff/resume interruption
5. environment continuity break

### 6.4 Required Checks For Each Failure

For every injected failure, confirm:

- the failure is explicitly surfaced
- the affected chain stops cleanly
- no success-like state is fabricated
- durable failure truth exists
- replay/recovery path is visible where the design expects it

### 6.5 Pass Conditions

This track passes only if all are true:

- all five failure families were exercised
- none of them silently progressed as success
- frontend surfaces do not hide the failure
- durable failure truth exists for replay/recovery
- fail-closed behavior is consistent after refresh/re-entry

### 6.6 Required Evidence Bundle

- failure injection method
- scenario name
- formal ids affected by the failure
- frontend-visible failure proof
- API/read-model proof
- evidence/report/recovery truth
- final result: did the chain fail closed or not

---

## 7. Sign-Off Template

Use this exact structure for every completed run:

```text
Track:
Scenario:
Date:
Commit:
Environment:

Formal truth ids:
- 

Frontend proof:
- 

API/read-model proof:
- 

Evidence/report proof:
- 

Refresh/re-entry proof:
- 

Result:
- passed / failed

Failure category if failed:
- 

Notes:
- 
```

---

## 8. Final Rule

These four tracks only count as accepted when both are true:

- this script is fully executed
- the matching item in [2026-04-10-system-real-acceptance-checklist.md](/D:/word/copaw/docs/superpowers/plans/2026-04-10-system-real-acceptance-checklist.md) is explicitly updated with the sign-off result

Without both, the honest status remains:

- code-strong
- partially verified
- not yet fully accepted
