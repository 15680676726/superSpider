# Main Brain Shell Priority Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CoPaw main-brain shell selection prefer stronger explicit hints over weaker natural-language aliases, without expanding the keyword surface.

**Architecture:** Keep all changes inside the existing request-scoped `intent_shell` path. Detect all triggerable matches, rank them by strength and position, and preserve the existing `request.mode_hint` override in `turn_executor` with explicit tests so shell priority stays deterministic and boundary-safe.

**Tech Stack:** Python, pytest, existing kernel chat/orchestrator routing

---

### Task 1: Lock Down Shell Match Priority

**Files:**
- Modify: `src/copaw/kernel/main_brain_intent_shell.py`
- Test: `tests/kernel/test_main_brain_intent_shell.py`

- [ ] **Step 1: Tighten the existing priority parametrized test**

Update the existing priority matrix in `tests/kernel/test_main_brain_intent_shell.py` so it covers:

- later `/review` should beat earlier weak `plan` natural-language wording
- later `/verify` should beat earlier weak `review` natural-language wording
- leading explicit ASCII shell alias should keep winning over a later weaker Chinese natural alias of a different shell
- same-strength explicit slash matches should prefer earlier position
- assertions must verify the winning `matched_text`, not only `mode_hint`

- [ ] **Step 2: Run the focused test file to verify failure**

Run:

```powershell
$env:PYTHONPATH='D:/word/copaw/.worktrees/main-brain-single-loop-chat/src'; python -m pytest D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_main_brain_intent_shell.py -q
```

Expected: one or more new tests fail because current detection returns the first rule-ordered match rather than the strongest triggerable match.

- [ ] **Step 3: Implement minimal match ranking**

Implement in `src/copaw/kernel/main_brain_intent_shell.py`:

- collect all triggerable matches instead of returning on first rule hit
- rank by trigger strength first, then earlier position
- keep current alias surface unchanged
- keep current quoted/codeish/literal-discussion guards intact

- [ ] **Step 4: Re-run the focused tests**

Run:

```powershell
$env:PYTHONPATH='D:/word/copaw/.worktrees/main-brain-single-loop-chat/src'; python -m pytest D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_main_brain_intent_shell.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/main_brain_intent_shell.py tests/kernel/test_main_brain_intent_shell.py
git commit -m "feat: prioritize explicit main-brain shell hints"
```

### Task 2: Codify Request Hint Override In Routing

**Files:**
- Modify: `tests/kernel/test_turn_executor.py`

- [ ] **Step 1: Tighten the existing routing-priority regression test**

Use or tighten the existing request-side regression in `tests/kernel/test_turn_executor.py` so it shows:

- `request.mode_hint="verify"` overrides conflicting natural-language or slash-like text in the user message

- [ ] **Step 2: Run the focused routing test to verify behavior**

Run:

```powershell
$env:PYTHONPATH='D:/word/copaw/.worktrees/main-brain-single-loop-chat/src'; python -m pytest D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_turn_executor.py -q -k "mode_hint"
```

Expected: this regression may already pass because routing precedence is already implemented; keep it as coverage and do not add production code if so.

- [ ] **Step 3: Run cross-file regression for the shell path**

Run:

```powershell
$env:PYTHONPATH='D:/word/copaw/.worktrees/main-brain-single-loop-chat/src'; python -m pytest D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_main_brain_intent_shell.py D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_turn_executor.py D:/word/copaw/.worktrees/main-brain-single-loop-chat/tests/kernel/test_main_brain_chat_service.py -q
```

Expected: the request-scoped shell path remains green.

- [ ] **Step 4: Commit**

```bash
git add tests/kernel/test_turn_executor.py docs/superpowers/plans/2026-04-02-main-brain-shell-priority-hardening-implementation.md
git commit -m "test: lock main-brain shell priority routing"
```
