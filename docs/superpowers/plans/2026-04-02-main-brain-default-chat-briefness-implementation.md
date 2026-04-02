# Main-Brain Default Chat Briefness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten CoPaw main-brain ordinary chat replies so the default `CHAT` shell is shorter and more direct without adding new routing layers.

**Architecture:** Keep the change inside the existing default shell tail text in `main_brain_chat_service.py`. Do not introduce new classifiers, new shell modes, token-limit tweaks, post-processing layers, or any second truth source; strengthen only the prompt contract for ordinary chat turns.

**Tech Stack:** Python 3.12, pytest, existing main-brain chat prompt builder

---

### Task 1: Tighten Default CHAT Reply Discipline

**Files:**
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Write the failing tests**

Add or tighten assertions so the default `CHAT` shell tail explicitly requires:

- direct answer first for clear/simple asks
- `1-2` sentence default for simple asks
- no request restatement unless needed
- no bullets/sections for simple asks
- one decisive clarification question at most
- no donor-specific `cc` wording, labels, or shell names being introduced as part of this change

- [ ] **Step 2: Run the focused test to verify failure**

Run:

```powershell
PYTHONPATH=src python -m pytest tests/kernel/test_main_brain_chat_service.py -k "default_shell_tail" -q
```

Expected: FAIL because the current default `CHAT` shell tail does not yet encode the stricter briefness rules.

- [ ] **Step 3: Implement the minimal prompt-tail hardening**

Update only the default `Mode: CHAT` branch in `src/copaw/kernel/main_brain_chat_service.py`.

Do not:

- change the shell-mode set
- add a local reply-classification layer
- import donor-specific `cc` wording or labels into CoPaw replies
- modify `plan / review / resume / verify`
- change token limits or add response post-processing
- change formal truth or orchestration behavior

- [ ] **Step 4: Re-run the focused test**

Run:

```powershell
PYTHONPATH=src python -m pytest tests/kernel/test_main_brain_chat_service.py -k "default_shell_tail" -q
```

Expected: PASS.

- [ ] **Step 5: Run a small shell regression sweep**

Run:

```powershell
PYTHONPATH=src python -m pytest tests/kernel/test_main_brain_chat_service.py -k "default_shell_tail or tightens_front_door_shell_structure or prompt_adds_plan_shell_tail" -q
```

Expected: PASS, including the existing `review / resume / verify` shell-tail assertions covered by `tightens_front_door_shell_structure`.

- [ ] **Step 6: Commit**

```bash
git add src/copaw/kernel/main_brain_chat_service.py tests/kernel/test_main_brain_chat_service.py docs/superpowers/specs/2026-04-02-main-brain-default-chat-briefness-design.md docs/superpowers/plans/2026-04-02-main-brain-default-chat-briefness-implementation.md
git commit -m "feat: tighten main-brain default chat briefness"
```
