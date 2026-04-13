# Frontend Truth Reconciliation Scenario Table

> **For agentic workers:** Use this table for Track H. It defines which shared scenarios to compare across surfaces and what would count as semantic mismatch.

**Goal:** Give Track H a fixed scenario table so frontend truth consistency is measured by shared live chains, not by page-by-page impressions.

**Architecture:** This table maps one formal chain to multiple operator-facing surfaces. It does not require identical wording everywhere, but it does require identical meaning everywhere.

**Tech Stack:** Chat, Runtime Center, Industry, Agent Workbench, RightPanel/Buddy summary, shared runtime/buddy read surfaces.

---

## 1. How To Use This Table

Pick one real formal chain and compare it across surfaces.

Do not compare different runs and call that "consistency".

Wording does not need to be identical.
Meaning does.

Examples:

- `blocked`
- `recovery-needed`
- `human-return-needed`

may all be acceptable **if** they point to the same blocked/handoff truth.

But these are **not** acceptable together for one chain:

- one page says `running`
- one page says `nothing here`
- one page says `completed`

---

## 2. Scenario Table

| Scenario | Formal truth to anchor on | Surfaces that must be checked | What all surfaces must agree on | What would count as mismatch |
| --- | --- | --- | --- | --- |
| Empty / no live work | No active formal work for the chosen chain | Chat, Runtime Center, Industry, Agent Workbench if applicable | There is no active work on this chain right now | One page shows empty while another still shows active/blocking work for the same formal chain |
| Pending / queued | Real pending formal object exists but execution has not started yet | Chat, Runtime Center, Industry | Work exists and is waiting/pending, not completed and not absent | One page says "nothing here" or "completed" while another shows pending |
| Running | Real execution is in progress on the chosen chain | Chat, Runtime Center, Industry, Agent Workbench if an owner seat is visible | The chain is actively running or in-progress | One page says running while another says empty, completed, or detached |
| Blocked / handoff / need_more_evidence | Formal blocked or interrupted truth exists on the chosen chain | Chat, Runtime Center, Industry, RightPanel if it summarizes the same chain | The chain is blocked/interrupted and needs action or recovery | One page turns blocked into active or hides the interruption entirely |
| Completed with evidence/report | Formal completion, evidence, and report truth exist | Chat, Runtime Center, Industry, Agent Workbench if report/owner is relevant | Work finished and left durable result truth | One page still shows active/pending while another shows completed |

---

## 3. Recommended Comparison Order

Use this order for every Track H run:

1. Chat
2. Runtime Center
3. Industry
4. Agent Workbench if the scenario has a visible owner seat
5. RightPanel/Buddy summary if the same chain is summarized there
6. Refresh
7. Re-entry / reopen

---

## 4. Per-Surface Notes

### 4.1 Chat

Check:

- current thread truth
- current progress banner or visible runtime state
- whether the page silently falls back to an empty thread or wrong thread

### 4.2 Runtime Center

Check:

- canonical runtime summary
- operator-facing status
- whether pending/running/blocked truth is preserved instead of flattened

### 4.3 Industry

Check:

- current execution focus
- whether the same instance/chain is shown
- whether the page rebinds to the wrong instance after refresh/re-entry

### 4.4 Agent Workbench

Check:

- seat/owner-specific current work
- capability/gap/drift state when relevant
- whether seat truth contradicts the main runtime truth

### 4.5 RightPanel / Buddy Summary

Check only when it summarizes the same chain.

It does not need to show every execution detail.
It must not imply a contradictory truth.

---

## 5. Refresh / Re-entry Rule

A Track H run fails if:

- refresh changes the active chain without operator intent
- re-entry reopens a stale thread or stale instance
- one surface returns to empty while formal truth still exists

---

## 6. Evidence Bundle Minimum

For one Track H run, keep:

- one scenario name
- formal ids
- screenshot or visible proof from each checked surface
- API/read-model proof for each checked surface
- refresh/re-entry proof
- one reconciliation note saying why the surfaces are semantically aligned
