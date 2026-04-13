# Failure Injection Methods Table

> **For agentic workers:** This table defines the preferred safe injection methods for Track L. Use the safest method that still proves the real chain fails closed. If no safe method exists for a failure family, record the track as blocked rather than improvising in production.

**Goal:** Make Track L executable by listing how to inject each required failure family, what to inspect afterward, and what would count as fake success.

**Architecture:** These methods do not replace the failure-injection acceptance script. They operationalize it by pairing each failure family with a safe injection seam, expected formal truth, and forbidden fake-success outcomes.

**Tech Stack:** Chat front door, Runtime Center, capability execution, governance/read surfaces, host recovery, startup recovery, evidence/report chain.

---

## 1. Safety Rules

Always prefer:

1. acceptance-only environment
2. bounded timeout / bounded bad input
3. reversible interruption
4. explicit note in the ledger saying how the failure was injected

Do not use:

- uncontrolled production breakage
- destructive external actions
- random manual sabotage without a recorded method

---

## 2. Failure Injection Table

| Failure family | Preferred safe injection method | What must be checked | Durable truth expected | Fake-success signs that fail the track |
| --- | --- | --- | --- | --- |
| Model timeout | Use an acceptance-only timeout override or a staging provider/model path that deterministically exceeds the configured turn timeout. Keep it bounded so the request ends quickly and visibly. | Frontend shows timeout/failure, chain stops cleanly, no committed-success state appears | cancelled/timeout-style terminal truth, relevant task/runtime status, error summary, evidence/recovery truth where the chain normally writes it | reply looks successful, task shows completed, frontend hides timeout and continues as if normal |
| Tool/runtime failure | Use a bounded failing tool action or a runtime action guaranteed to fail in the acceptance environment. Examples: bad command with bounded timeout, runtime health/start action against a known broken acceptance target. | Error is surfaced, affected path halts, no silent fallback to fake success | terminal error/failure truth, relevant runtime/task state, evidence or error summary | UI says started/ready/completed even though the failing action never succeeded |
| Missing capability attachment | Trigger work on a seat/runtime path that intentionally lacks the required capability attachment in the acceptance setup. Verify the system surfaces the gap instead of pretending to execute. | Capability gap is visible, intended seat is shown as lacking coverage, no fake execution result appears, any supplement/temp-seat behavior matches product rules | capability governance / degraded-components style truth, staffing or capability-gap truth, no fake evidence for work never done | execution appears completed, frontend claims active work succeeded, no visible gap despite missing attachment |
| Handoff/resume interruption | Use a governed human-assist / handoff path and stop before successful return. Examples: leave the task at `need_more_evidence`, or pause before successful resume is accepted. | Chat and runtime surfaces show interruption honestly, status does not jump to closed/completed, resume path remains visible | `need_more_evidence`, `resume_queued`, `handoff_blocked`, or equivalent formal truth on the real chain | task disappears, UI returns to active success, recovery path is swallowed |
| Environment continuity break | Break the live continuity in the acceptance environment using a reversible method: expired/detached live handle, blocked host recovery path, or startup recovery scenario with missing continuity anchor. | Runtime surfaces show detached/blocked/recovery-required state, not active success; refresh/re-entry keeps that truth | recovery summary, host/environment continuity truth, blocked/recovery-needed state, recovery evidence/report where expected | UI still claims the environment is attached/ready, task continues as if continuity never broke |

---

## 3. Per-Family Notes

### 3.1 Model Timeout

Use this family to prove:

- the chain does not silently swallow slow model failure
- timeout is not turned into fake completion

### 3.2 Tool / Runtime Failure

Use this family to prove:

- execution failure is visible at the operator layer
- system does not hide behind inventory/install truth

### 3.3 Missing Capability Attachment

Use this family to prove:

- "installed somewhere" is not confused with "available on the intended seat"
- the system surfaces capability insufficiency honestly

### 3.4 Handoff / Resume Interruption

Use this family to prove:

- governed interruption stays on the same runtime chain
- the task does not vanish when the human step is incomplete

### 3.5 Environment Continuity Break

Use this family to prove:

- environment continuity is real runtime truth
- the system fails closed when continuity is broken

---

## 4. If No Safe Injection Path Exists

Do not invent a dangerous workaround.

Record:

- failure family
- why no safe path exists
- what seam is missing
- which team/code owner must add the acceptance seam

That outcome means:

- `Track L blocked by missing safe injection seam`

not:

- `Track L passed anyway`
