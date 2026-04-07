# Main-Brain Internal Exception Absorption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-only internal-exception absorption loop that keeps multi-agent runtime failures inside the main-brain boundary by adding derived stuck detection, a bounded recovery ladder, and one shared main-brain summary surface.

**Architecture:** Reuse canonical runtime truth (`AgentRuntimeRecord`, mailbox/checkpoints, kernel task phases, `HumanAssistTaskRecord`, report replan signals) and add a thin derived service layer instead of a second incident subsystem. A watchdog service scans current runtime truth and emits bounded absorption cases; an absorber executes a deterministic cleanup/retry/replan/escalate ladder; a shared summary builder projects one main-brain-readable result for Runtime Center and chat/runtime context.

**Tech Stack:** Python 3.12, FastAPI runtime services, SQLite-backed state repositories, pytest.

---

## File Map

- Create: `src/copaw/kernel/main_brain_exception_absorption.py`
  - Derived watchdog scan over runtime/mailbox/human-assist/replan truth.
  - Recovery ladder executor.
  - Shared main-brain summary payload builder.
- Modify: `src/copaw/kernel/__init__.py`
  - Export the new absorption service if the package already exports peer kernel services.
- Modify: `src/copaw/app/runtime_service_graph.py`
  - Wire the new service once and inject it into consumers.
- Modify: `src/copaw/kernel/actor_supervisor.py`
  - Run watchdog/absorber during poll lifecycle and expose absorption counters in `snapshot()`.
- Modify: `src/copaw/kernel/actor_mailbox.py`
  - Expose enough retry/age/progress metadata for watchdog classification without adding new truth tables.
- Modify: `src/copaw/app/startup_recovery.py`
  - Reuse the same absorber during restart recovery so startup and steady-state do not diverge.
- Modify: `src/copaw/app/runtime_center/overview_main_brain.py`
  - Read the shared main-brain exception summary into the main-brain card.
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
  - Stop inventing ad hoc wording for this slice and delegate to the shared summary.
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
  - Attach the same summary into the main-brain prompt/scope snapshot context.
- Modify: `src/copaw/kernel/main_brain_scope_snapshot_service.py`
  - Mark scope snapshots dirty when absorption state changes if needed.
- Test: `tests/kernel/test_main_brain_exception_absorption.py`
  - New focused watchdog/absorber unit coverage.
- Modify: `tests/kernel/test_actor_supervisor.py`
  - Assert absorption pass integration and snapshot fields.
- Modify: `tests/kernel/test_actor_mailbox.py`
  - Assert retry-loop / waiting-confirm / stale progress classification inputs.
- Modify: `tests/app/test_startup_recovery.py`
  - Assert startup recovery and steady-state absorber share the same rules.
- Modify: `tests/app/runtime_center_api_parts/overview_governance.py`
  - Assert main-brain Runtime Center output carries shared absorption summary.
- Modify: `tests/kernel/test_main_brain_chat_service.py`
  - Assert prompt context/snapshot includes main-brain-readable absorption summary, not raw scheduler details.
- Modify: `TASK_STATUS.md`
  - Register the new spec/plan and implementation status once code lands.

---

### Task 1: Add The Derived Absorption Service

**Files:**
- Create: `src/copaw/kernel/main_brain_exception_absorption.py`
- Modify: `src/copaw/kernel/__init__.py`
- Test: `tests/kernel/test_main_brain_exception_absorption.py`

- [ ] **Step 1: Write the failing watchdog classification tests**

```python
def test_absorption_service_classifies_writer_contention_from_repeated_conflicts() -> None:
    service = MainBrainExceptionAbsorptionService(...)
    summary = service.scan(...)
    assert summary.active_cases[0].case_kind == "writer-contention"


def test_absorption_service_classifies_waiting_confirm_orphan_without_creating_new_truth() -> None:
    service = MainBrainExceptionAbsorptionService(...)
    summary = service.scan(...)
    assert summary.active_cases[0].case_kind == "waiting-confirm-orphan"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
python -m pytest tests/kernel/test_main_brain_exception_absorption.py -q
```

Expected: FAIL because `MainBrainExceptionAbsorptionService` does not exist yet.

- [ ] **Step 3: Implement the minimal derived service**

```python
@dataclass(slots=True)
class AbsorptionCase:
    case_kind: str
    owner_agent_id: str | None
    scope_ref: str | None
    recovery_rung: str
    human_required: bool = False


class MainBrainExceptionAbsorptionService:
    def scan(self, *, runtimes, mailbox_items, human_assist_tasks, now) -> AbsorptionSummary:
        ...
```

Implementation notes:

- Keep this file derived-only.
- Read from current repositories/services; do not create a new repository.
- Start with a bounded vocabulary:
  - `stale-lease`
  - `retry-loop`
  - `waiting-confirm-orphan`
  - `writer-contention`
  - `progressless-runtime`
  - `repeated-blocker-same-scope`
- Build one summary object that contains:
  - active case list
  - counts by case kind
  - counts by recovery rung
  - one main-brain-readable summary sentence

- [ ] **Step 4: Run the focused service tests**

Run:

```bash
python -m pytest tests/kernel/test_main_brain_exception_absorption.py -q
```

Expected: PASS

- [ ] **Step 5: Commit the service skeleton**

```bash
git add src/copaw/kernel/main_brain_exception_absorption.py src/copaw/kernel/__init__.py tests/kernel/test_main_brain_exception_absorption.py
git commit -m "feat: add main-brain exception absorption service"
```

---

### Task 2: Wire The Recovery Ladder Into Runtime Supervision

**Files:**
- Modify: `src/copaw/kernel/actor_supervisor.py`
- Modify: `src/copaw/kernel/actor_mailbox.py`
- Modify: `src/copaw/app/startup_recovery.py`
- Test: `tests/kernel/test_actor_supervisor.py`
- Test: `tests/kernel/test_actor_mailbox.py`
- Test: `tests/app/test_startup_recovery.py`

- [ ] **Step 1: Add failing integration tests for the ladder**

```python
def test_actor_supervisor_snapshot_includes_absorption_counts(tmp_path) -> None:
    supervisor = ActorSupervisor(..., exception_absorption_service=service)
    snapshot = supervisor.snapshot()
    assert snapshot["absorption_case_count"] == 1
    assert snapshot["human_required_case_count"] == 0


def test_startup_recovery_uses_absorber_to_requeue_safe_orphans(tmp_path) -> None:
    summary = run_startup_recovery(...)
    assert summary.absorption_requeued == 1
```

- [ ] **Step 2: Run the failing supervisor/mailbox/startup slices**

Run:

```bash
python -m pytest tests/kernel/test_actor_supervisor.py tests/kernel/test_actor_mailbox.py tests/app/test_startup_recovery.py -q
```

Expected: FAIL on missing absorption fields and missing ladder integration.

- [ ] **Step 3: Implement runtime integration**

```python
snapshot.update(
    {
        "absorption_case_count": absorption.case_count,
        "human_required_case_count": absorption.human_required_case_count,
        "recovery_actions": absorption.recovery_actions,
    }
)
```

Implementation notes:

- `actor_supervisor.py`
  - Run the watchdog after a poll cycle and after local agent failure recording.
  - Keep it bounded: scan, maybe absorb, publish one runtime event, update snapshot meta.
- `actor_mailbox.py`
  - Expose enough metadata for:
    - retry count
    - last progress time
    - waiting-confirm age
    - same-scope repeated blocker detection
  - Do not create another mailbox state machine.
- `startup_recovery.py`
  - Reuse the same absorber for restart-time stale items.
  - Record startup recovery outcome in the existing summary/result structure.

- [ ] **Step 4: Run the focused recovery suite**

Run:

```bash
python -m pytest tests/kernel/test_actor_supervisor.py tests/kernel/test_actor_mailbox.py tests/app/test_startup_recovery.py -q
```

Expected: PASS

- [ ] **Step 5: Commit the runtime integration**

```bash
git add src/copaw/kernel/actor_supervisor.py src/copaw/kernel/actor_mailbox.py src/copaw/app/startup_recovery.py tests/kernel/test_actor_supervisor.py tests/kernel/test_actor_mailbox.py tests/app/test_startup_recovery.py
git commit -m "feat: wire exception absorption into runtime supervision"
```

---

### Task 3: Project One Shared Main-Brain Summary

**Files:**
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_center/overview_main_brain.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/main_brain_scope_snapshot_service.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Write failing read-model and chat-summary tests**

```python
def test_runtime_center_main_brain_card_uses_shared_absorption_summary(client) -> None:
    payload = client.get("/runtime-center/main-brain").json()
    assert payload["summary"].startswith("Main brain is absorbing")


def test_main_brain_chat_prompt_uses_absorption_summary_not_raw_scheduler_words() -> None:
    prompt = captured_prompt(...)
    assert "writer-contention" not in prompt
    assert "系统正在内部恢复" in prompt
```

- [ ] **Step 2: Run the failing projection/chat tests**

Run:

```bash
python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/test_main_brain_chat_service.py -q
```

Expected: FAIL because the shared summary is not yet wired.

- [ ] **Step 3: Implement shared summary projection**

```python
summary = exception_absorption_service.build_main_brain_summary(...)
entry_meta["exception_absorption"] = summary.model_dump(mode="json")
```

Implementation notes:

- `runtime_service_graph.py`
  - Build the service once and inject it where needed.
- `overview_main_brain.py` and `overview_cards.py`
  - Read the shared summary and surface:
    - whether the system is currently absorbing internal issues
    - whether human help is currently required
    - one translated next step
  - Do not surface raw internal scheduler terms as the primary summary.
- `main_brain_chat_service.py`
  - Add one short section to the prompt/scope snapshot context:
    - current absorption status
    - what the system already tried
    - whether human action is required
- `main_brain_scope_snapshot_service.py`
  - Mark scope cache dirty when absorption state changes so chat does not keep stale blocker language.

- [ ] **Step 4: Run the projection/chat tests**

Run:

```bash
python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/test_main_brain_chat_service.py -q
```

Expected: PASS

- [ ] **Step 5: Commit the shared summary projection**

```bash
git add src/copaw/app/runtime_service_graph.py src/copaw/app/runtime_center/overview_main_brain.py src/copaw/app/runtime_center/overview_cards.py src/copaw/kernel/main_brain_chat_service.py src/copaw/kernel/main_brain_scope_snapshot_service.py tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/test_main_brain_chat_service.py
git commit -m "feat: surface shared main-brain exception summary"
```

---

### Task 4: Escalate Structural Failures Into Formal Replan Or Human Assist

**Files:**
- Modify: `src/copaw/kernel/main_brain_exception_absorption.py`
- Modify: `src/copaw/state/human_assist_task_service.py`
- Modify: `src/copaw/compiler/planning/report_replan_engine.py`
- Test: `tests/state/test_human_assist_task_service.py`
- Test: `tests/compiler/test_report_replan_engine.py`
- Test: `tests/kernel/test_main_brain_exception_absorption.py`

- [ ] **Step 1: Add failing tests for structural escalation**

```python
def test_absorber_escalates_repeated_same_scope_blockers_to_cycle_rebalance() -> None:
    result = service.absorb(...)
    assert result.replan_decision_kind == "cycle_rebalance"


def test_absorber_emits_one_human_action_only_after_safe_recovery_budget_exhausted(tmp_path) -> None:
    result = service.absorb(...)
    assert result.human_required is True
    assert result.human_action_summary
```

- [ ] **Step 2: Run the failing escalation tests**

Run:

```bash
python -m pytest tests/kernel/test_main_brain_exception_absorption.py tests/state/test_human_assist_task_service.py tests/compiler/test_report_replan_engine.py -q
```

Expected: FAIL because the absorber does not yet issue formal escalation outputs.

- [ ] **Step 3: Implement structural escalation**

```python
if retry_budget_exhausted and same_scope_blocker_count >= 2:
    return AbsorptionAction(kind="replan", decision_kind="cycle_rebalance")
if recovery_budget_exhausted and requires_human_boundary:
    return AbsorptionAction(kind="human-assist", summary="...")
```

Implementation notes:

- Keep escalation outputs formal:
  - replan recommendation
  - human assist request
  - do not create a free-form ad hoc incident object
- Reuse `HumanAssistTaskService` for the final human step wording.
- Reuse existing replan language families where possible:
  - `lane_reweight`
  - `cycle_rebalance`
  - `strategy_review_required`

- [ ] **Step 4: Run the structural escalation suite**

Run:

```bash
python -m pytest tests/kernel/test_main_brain_exception_absorption.py tests/state/test_human_assist_task_service.py tests/compiler/test_report_replan_engine.py -q
```

Expected: PASS

- [ ] **Step 5: Commit the escalation closure**

```bash
git add src/copaw/kernel/main_brain_exception_absorption.py src/copaw/state/human_assist_task_service.py src/copaw/compiler/planning/report_replan_engine.py tests/kernel/test_main_brain_exception_absorption.py tests/state/test_human_assist_task_service.py tests/compiler/test_report_replan_engine.py
git commit -m "feat: close exception absorption escalation ladder"
```

---

### Task 5: Run Focused Regression, Sync Status Docs, And Finalize

**Files:**
- Modify: `TASK_STATUS.md`
- Verify: `tests/kernel/test_main_brain_exception_absorption.py`
- Verify: `tests/kernel/test_actor_supervisor.py`
- Verify: `tests/kernel/test_actor_mailbox.py`
- Verify: `tests/app/test_startup_recovery.py`
- Verify: `tests/app/runtime_center_api_parts/overview_governance.py`
- Verify: `tests/kernel/test_main_brain_chat_service.py`
- Verify: `tests/state/test_human_assist_task_service.py`
- Verify: `tests/compiler/test_report_replan_engine.py`

- [ ] **Step 1: Add the status-board entry after implementation lands**

```markdown
- `2026-04-07` main-brain internal exception absorption
  - watchdog / absorber / shared summary wired
  - default front-stage remains single main-brain
```

- [ ] **Step 2: Run the focused regression matrix**

Run:

```bash
python -m pytest tests/kernel/test_main_brain_exception_absorption.py tests/kernel/test_actor_supervisor.py tests/kernel/test_actor_mailbox.py tests/app/test_startup_recovery.py tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/test_main_brain_chat_service.py tests/state/test_human_assist_task_service.py tests/compiler/test_report_replan_engine.py -q
```

Expected: PASS

- [ ] **Step 3: Run one adjacent runtime sanity slice**

Run:

```bash
python -m pytest tests/app/test_runtime_center_api.py tests/kernel/test_query_execution_runtime.py -q
```

Expected: PASS

- [ ] **Step 4: Check formatting and dirty-tree safety**

Run:

```bash
git diff --check
git status --short
```

Expected:

- no whitespace/conflict errors from `git diff --check`
- only intended implementation files remain dirty before the final commit

- [ ] **Step 5: Commit the final status/doc sync**

```bash
git add TASK_STATUS.md
git commit -m "docs: record exception absorption closure status"
```

---

## Notes For Execution

- Do not create a new repository or state table for incidents.
- Do not expose raw actor/mailbox terminology as the ordinary user-facing summary.
- Keep the vocabulary tight and reusable.
- Prefer one shared summary builder over separate wording in Runtime Center and chat.
- If a planned integration starts requiring broad front-end changes, stop and cut that into a separate follow-up plan.
