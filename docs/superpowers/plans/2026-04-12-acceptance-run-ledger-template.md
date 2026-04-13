# Acceptance Run Ledger Template

> **For agentic workers:** Use this ledger template to record every real acceptance run. A track is not signed off until at least one completed ledger entry exists and the system real acceptance checklist is updated to reference it.

**Goal:** Standardize how real acceptance runs are recorded so sign-off stops depending on memory, chat history, or vague "we tested that once" claims.

**Architecture:** The ledger sits between the acceptance script and final checklist sign-off. It records one run at a time, links formal truth to frontend-visible truth, and preserves the exact evidence bundle used to accept or reject a track.

**Tech Stack:** Markdown records, backend truth ids, API/read models, console frontend, Runtime Center, Industry, Chat, evidence/report objects.

---

## 1. Usage Rules

Use one ledger entry per real run.

Do not merge multiple runs into one fuzzy summary.

If the same scenario is re-run on a different commit, create a new entry.

If a run fails, keep it.
Failed runs are part of the acceptance history.

---

## 2. Summary Index Template

Copy this table into the top of the live ledger file when actual runs begin:

| Run ID | Track | Scenario | Date | Commit | Result | Evidence Bundle Ready | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `accept-001` |  |  |  |  | `passed/failed` | `yes/no` |  |

---

## 3. Detailed Entry Template

Copy this block once per run:

```markdown
## Run ID: accept-001

**Track:**  
**Scenario:**  
**Date:**  
**Commit:**  
**Operator:**  
**Environment:**  

### A. Preconditions

- 

### B. Trigger Path

- Real front door:
- User/operator action:
- Expected formal chain:

### C. Formal Truth IDs

- `industry_instance_id`:
- `control_thread_id`:
- `assignment_id`:
- `task_id`:
- `decision_request_id`:
- `evidence_id`:
- `agent_report_id`:

Use `N/A` only when the object truly should not exist for this scenario.

### D. API / Read-Model Proof

- Chat payload:
- Runtime Center payload:
- Industry payload:
- Agent Workbench payload:
- Other relevant payload:

### E. Frontend-Visible Proof

- Chat:
- Runtime Center:
- Industry:
- Agent Workbench:
- RightPanel / Buddy summary:

### F. Refresh / Re-entry Proof

- What was refreshed or reopened:
- What stayed consistent:
- What changed:

### G. Result

- Final result: `passed` / `failed`
- If failed, root cause category:

### H. Notes

- 
```

---

## 4. Minimum Evidence Rule

A ledger entry is incomplete unless it contains all of:

- one real front-door trigger
- formal truth ids
- API/read-model proof
- frontend-visible proof
- refresh/re-entry proof
- final pass/fail result

If one of those is missing, mark:

- `Evidence Bundle Ready = no`

and do not sign off the track.

---

## 5. Sign-Off Rule

Final checklist sign-off should reference:

- the run id
- the commit
- the ledger location

Example:

- `Accepted via accept-001 on commit abc1234; evidence bundle recorded in acceptance ledger.`
