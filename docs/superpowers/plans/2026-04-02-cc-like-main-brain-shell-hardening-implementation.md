# CC-Like Main-Brain Shell Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CoPaw's single-window main-brain chat feel more like `cc` at the front door by hardening reply style, adding a lightweight intent shell for `plan/review/resume/verify`, and rendering the resulting shell state in the same chat window without creating a second truth source.

**Architecture:** Keep `/api/runtime-center/chat/run` as the only front door and keep formal truth in CoPaw's existing object chain. Add a lightweight shell layer that produces mode hints and shell artifacts for the current turn, while the formal kernel/orchestrator path remains the only place allowed to materialize durable objects or governance transitions.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, TypeScript, React, Vitest, existing runtime-center SSE sidecar transport

**Companion Docs:**
- Spec: `docs/superpowers/specs/2026-04-02-cc-prompt-keyword-shell-investigation.md`
- Baseline: `docs/superpowers/specs/2026-04-01-main-brain-single-loop-chat-design.md`
- Guardrails: `AGENTS.md`

---

## File Map

### Backend

- Modify: `src/copaw/kernel/main_brain_chat_service.py`
  - Reply style hardening, dynamic shell prompt tail, shell output shaping.
- Create: `src/copaw/kernel/main_brain_intent_shell.py`
  - Lightweight keyword/phrase discipline for `plan/review/resume/verify`.
- Modify: `src/copaw/kernel/main_brain_intake.py`
  - Carry optional mode hints without introducing a second model pass.
- Modify: `src/copaw/kernel/turn_executor.py`
  - Preserve ordinary single-loop chat while allowing explicit shell hints to flow through.
- Modify: `src/copaw/app/runtime_chat_stream_events.py`
  - Canonical sidecar event shape for shell state.
- Modify: `src/copaw/kernel/main_brain_turn_result.py`
  - Extend turn result contract with non-durable shell metadata if needed.

### Frontend

- Modify: `console/src/pages/Chat/runtimeSidecarEvents.ts`
  - Parse shell sidecar events.
- Modify: `console/src/pages/Chat/useChatRuntimeState.ts`
  - Store and hydrate shell state in the single chat window.
- Modify: `console/src/pages/Chat/index.tsx`
  - Mount shell card/badge in current thread UI.
- Create: `console/src/pages/Chat/ChatIntentShellCard.tsx`
  - Same-window shell artifact card for plan/review/resume/verify.
- Create: `console/src/pages/Chat/ChatIntentShellCard.test.tsx`

### Tests

- Modify: `tests/kernel/test_main_brain_chat_service.py`
- Modify: `tests/kernel/test_turn_executor.py`
- Modify: `tests/app/runtime_center_api_parts/overview_governance.py`
- Modify: `tests/app/test_runtime_canonical_flow_e2e.py`
- Modify: `console/src/pages/Chat/runtimeSidecarEvents.test.ts`
- Modify: `console/src/pages/Chat/useChatRuntimeState` (indirect via existing chat tests if available)

---

### Task 1: Harden Main-Brain Reply Style

**Files:**
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Write the failing backend tests for reply-style guardrails**

```python
def test_main_brain_pure_chat_prompt_contains_short_direct_reply_contract() -> None:
    prompt = module._PURE_CHAT_SYSTEM_PROMPT
    assert "先给结论" in prompt
    assert "默认短答" in prompt
    assert "不要反复追问" in prompt

def test_main_brain_dynamic_shell_tail_uses_mode_hint_when_present() -> None:
    service = build_service()
    tail = service._build_intent_shell_prompt_tail(mode_hint="plan", shell_payload=None)
    assert "plan" in tail.lower()
```

- [ ] **Step 2: Run the targeted backend tests**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_main_brain_chat_service.py -q`
Expected: FAIL because there is no dedicated shell-tail builder and current reply-style contract remains monolithic.

- [ ] **Step 3: Implement the minimal reply-style hardening**

Rules:
- keep CoPaw as formal main brain, not a casual companion persona
- split reply discipline into stable prefix + dynamic shell tail
- encode explicit rules for short/direct answers, minimal follow-up questions, and no repeated "should I start" behavior
- do not introduce a second model pass or a second truth source

- [ ] **Step 4: Run the targeted backend tests again**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_main_brain_chat_service.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/main_brain_chat_service.py tests/kernel/test_main_brain_chat_service.py
git commit -m "feat: harden main-brain reply style shell"
```

### Task 2: Add Lightweight Intent Shell For Plan/Review/Resume/Verify

**Files:**
- Create: `src/copaw/kernel/main_brain_intent_shell.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/main_brain_intake.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `tests/kernel/test_turn_executor.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Write the failing tests for intent-shell parsing and flow**

```python
def test_intent_shell_detects_plan_phrase_without_path_false_positive() -> None:
    result = detect_main_brain_intent_shell("先规划一下这个功能")
    assert result.mode_hint == "plan"

def test_intent_shell_ignores_codeish_or_path_context() -> None:
    result = detect_main_brain_intent_shell("请看 src/plan/review.ts")
    assert result.mode_hint == "none"

@pytest.mark.asyncio
async def test_turn_executor_keeps_plain_chat_single_loop_when_no_hint() -> None:
    ...
    assert resolved_mode == "chat"
```

- [ ] **Step 2: Run the targeted backend tests**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_chat_service.py -q`
Expected: FAIL because there is no dedicated intent-shell parser and no mode-hint flow.

- [ ] **Step 3: Implement the parser and wire it into the existing single-loop path**

Rules:
- parser may only emit shell metadata such as `mode_hint`, `trigger_source`, `matched_text`
- parser must not create or mutate formal truth objects
- ordinary chat stays on the same single-loop path
- explicit shell hints only affect prompt tail and sidecar metadata unless the existing formal kernel path later chooses to commit something durable

- [ ] **Step 4: Run the targeted backend tests again**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_chat_service.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/main_brain_intent_shell.py src/copaw/kernel/main_brain_chat_service.py src/copaw/kernel/main_brain_intake.py src/copaw/kernel/turn_executor.py tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_chat_service.py
git commit -m "feat: add main-brain intent shell hints"
```

### Task 3: Stream Shell State In Same Chat Window

**Files:**
- Modify: `src/copaw/app/runtime_chat_stream_events.py`
- Modify: `tests/app/runtime_center_api_parts/overview_governance.py`
- Modify: `tests/app/test_runtime_canonical_flow_e2e.py`
- Modify: `console/src/pages/Chat/runtimeSidecarEvents.ts`
- Modify: `console/src/pages/Chat/useChatRuntimeState.ts`
- Modify: `console/src/pages/Chat/index.tsx`
- Create: `console/src/pages/Chat/ChatIntentShellCard.tsx`
- Create: `console/src/pages/Chat/ChatIntentShellCard.test.tsx`
- Modify: `console/src/pages/Chat/runtimeSidecarEvents.test.ts`

- [ ] **Step 1: Write the failing sidecar and frontend tests**

```ts
it("parses shell sidecar event into runtime state", () => {
  const event = parseRuntimeSidecarEvent(raw)
  expect(event?.type).toBe("intent_shell")
  expect(event?.mode_hint).toBe("plan")
})

it("renders the shell card in the current chat window", () => {
  render(<ChatIntentShellCard shell={shellState} />)
  expect(screen.getByText("PLAN")).toBeInTheDocument()
})
```

```python
def test_chat_run_stream_includes_intent_shell_sidecar(client, app) -> None:
    body = _collect_sse(client, payload=_payload(query="先规划一下"))
    assert "intent_shell" in body
```

- [ ] **Step 2: Run the targeted frontend and backend stream tests**

Run: `cmd /c npm --prefix console test -- runtimeSidecarEvents.test.ts ChatIntentShellCard.test.tsx`
Run: `PYTHONPATH=src python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_canonical_flow_e2e.py -q`
Expected: FAIL because shell sidecar event and same-window UI do not exist yet.

- [ ] **Step 3: Implement same-window shell rendering**

Rules:
- no second chat window
- no second transport
- shell card is sidecar only, not formal truth
- shell card must survive normal same-thread refresh/hydration patterns where practical

- [ ] **Step 4: Re-run the targeted frontend and backend tests**

Run: `cmd /c npm --prefix console test -- runtimeSidecarEvents.test.ts ChatIntentShellCard.test.tsx`
Run: `PYTHONPATH=src python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_canonical_flow_e2e.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/runtime_chat_stream_events.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_canonical_flow_e2e.py console/src/pages/Chat/runtimeSidecarEvents.ts console/src/pages/Chat/useChatRuntimeState.ts console/src/pages/Chat/index.tsx console/src/pages/Chat/ChatIntentShellCard.tsx console/src/pages/Chat/ChatIntentShellCard.test.tsx console/src/pages/Chat/runtimeSidecarEvents.test.ts
git commit -m "feat: surface intent shell in chat window"
```

### Task 4: Full Regression Sweep And Docs Sync

**Files:**
- Modify: `docs/superpowers/specs/2026-04-02-cc-prompt-keyword-shell-investigation.md`
- Modify: `TASK_STATUS.md` if architecture/status moved materially

- [ ] **Step 1: Update docs/status if implementation shape changed from the investigation**

Rules:
- only update docs that changed materially
- do not invent a second truth source in docs language

- [ ] **Step 2: Run backend regressions**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_chat_service.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_canonical_flow_e2e.py -q`
Expected: PASS.

- [ ] **Step 3: Run frontend regressions**

Run: `cmd /c npm --prefix console test -- runtimeTransport.test.ts runtimeSidecarEvents.test.ts ChatCommitConfirmationCard.test.tsx ChatIntentShellCard.test.tsx`
Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run: `cmd /c npm --prefix console run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-04-02-cc-prompt-keyword-shell-investigation.md TASK_STATUS.md
git commit -m "docs: sync intent shell implementation status"
```
