# Main Brain Shell Discipline Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten CoPaw single-loop main-brain shell trigger discipline and reply-shell structure without expanding the keyword surface or adding a second planning truth.

**Architecture:** Keep the change inside the existing single-loop chat front door. Harden `main_brain_intent_shell.py` so matches are evaluated per occurrence instead of whole-string blanket rejection, then tighten the `plan/review/resume/verify` prompt tails in `MainBrainChatService` so the shell structure is more explicit and less likely to drift.

**Tech Stack:** Python, pytest, existing main-brain chat/orchestrator kernel services

---

### Task 1: Harden Intent-Shell Trigger Discipline

**Files:**
- Modify: `src/copaw/kernel/main_brain_intent_shell.py`
- Test: `tests/kernel/test_main_brain_intent_shell.py`

- [ ] **Step 1: Write failing trigger-discipline tests**

Add tests covering:

- quoted shell phrases should not trigger
- fenced / bracketed shell phrases should not trigger
- code/path/file-name context should not trigger
- mixed text like `先做个计划，然后看 src/app.py` should still trigger
- question/about-the-feature phrasing around ASCII shell words should not trigger
- Chinese literal-discussion phrasing like `把先做个计划这几个字放到标题里` should not trigger

- [ ] **Step 2: Run the focused test file to verify failure**

Run:

```powershell
$env:PYTHONPATH='D:/word/copaw/.worktrees/main-brain-single-loop-chat/src'; python -m pytest D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_main_brain_intent_shell.py -q
```

Expected: one or more new tests fail because current detection is substring-based and uses whole-string codeish rejection.

- [ ] **Step 3: Implement minimal per-match detection hardening**

Implement in `src/copaw/kernel/main_brain_intent_shell.py`:

- exclude quoted / fenced / bracketed ranges per occurrence
- stop using “any codeish text anywhere => no trigger”
- apply per-match context guards for ASCII hints
- apply local literal-discussion guards for Chinese trigger phrases
- keep existing `plan/review/resume/verify` surface area unchanged

- [ ] **Step 4: Re-run the focused trigger tests**

Run:

```powershell
$env:PYTHONPATH='D:/word/copaw/.worktrees/main-brain-single-loop-chat/src'; python -m pytest D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_main_brain_intent_shell.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/main_brain_intent_shell.py tests/kernel/test_main_brain_intent_shell.py
git commit -m "feat: harden main-brain shell trigger discipline"
```

### Task 2: Tighten Front-Door Reply Shell Structure

**Files:**
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Write failing prompt-shell tests**

Add tests covering:

- `review` shell explicitly requires risk plus evidence gaps
- `resume` shell explicitly requires continuity anchors and blocker framing
- `verify` shell explicitly requires pass/fail plus unresolved risk
- each shell says not to add extra sections or claim execution/evidence without context

- [ ] **Step 2: Run the focused chat-service shell tests to verify failure**

Run:

```powershell
$env:PYTHONPATH='D:/word/copaw/.worktrees/main-brain-single-loop-chat/src'; python -m pytest D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_main_brain_chat_service.py -q
```

Expected: one or more new assertions fail because the current shell tail is weaker than the new discipline.

- [ ] **Step 3: Implement minimal prompt-tail tightening**

Update `src/copaw/kernel/main_brain_chat_service.py` so the shell tail:

- uses a stricter, explicit section list per mode
- reinforces “answer-first, no invented execution/evidence”
- stays inside the current single-loop chat prompt path

- [ ] **Step 4: Re-run the focused shell tests**

Run:

```powershell
$env:PYTHONPATH='D:/word/copaw/.worktrees/main-brain-single-loop-chat/src'; python -m pytest D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_main_brain_chat_service.py -q
```

Expected: all focused shell tests pass.

- [ ] **Step 5: Run cross-file regression for the affected kernel path**

Run:

```powershell
$env:PYTHONPATH='D:/word/copaw/.worktrees/main-brain-single-loop-chat/src'; python -m pytest D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_main_brain_intent_shell.py D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_main_brain_chat_service.py D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_turn_executor.py -q
```

Expected: the main-brain shell path remains green.

- [ ] **Step 6: Commit**

```bash
git add src/copaw/kernel/main_brain_chat_service.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py
git commit -m "feat: tighten main-brain front-door shell discipline"
```
