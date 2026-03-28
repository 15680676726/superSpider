# Chat-First Human Assist Tasks

## 1. Positioning

This document defines the formal runtime feature for chat-first human collaboration tasks.

It is not:

- a prompt trick
- a skill
- a second chat system
- a money-reward marketplace

It is:

- a formal runtime object for human-only checkpoints
- a chat-first handoff surface inside the existing main control thread
- an evidence-backed acceptance and resume mechanism

The target product feel is "slightly novel-like", but the implementation boundary remains strict:
the system may only issue a human assist task when it truly cannot do the step itself or should not
cross the boundary automatically.

## 2. Core Product Decision

CoPaw should support `HumanAssistTask` as a first-class runtime feature for the following class of
work:

- login or identity steps that require the host
- payment or other guarded external actions that should remain human-owned
- phone calls, offline action, photography, document scan, upload, or physical confirmation
- proof-return checkpoints where the system is blocked until the host supplies a verifiable result

The main entry is the existing chat window:

- the system issues the task in the message flow
- the chat header shows the current active task
- clicking the header opens the task list/history
- the host submits in the same chat by saying they completed it or attaching proof

There is no separate public `task-chat:*` thread.

## 3. Hard Boundaries

`HumanAssistTask` may be issued only when all of the following are true:

1. the step is blocked by proof or inherently human-owned
2. the system cannot lawfully or reliably finish it itself
3. the runtime can name what proof will count as completion
4. a resume checkpoint exists for the blocked execution chain

The system must not issue a human assist task for:

- generic nudges or vague reminders
- work the machine can already perform directly
- tasks with no acceptance contract
- "trust me I finished it" style completion with no verification path

## 4. Formal Object

Add `HumanAssistTaskRecord` as a real state object adjacent to `AssignmentRecord` and `TaskRecord`.

Minimum fields:

- identity/binding
  - `id`
  - `industry_instance_id`
  - `assignment_id`
  - `chat_thread_id`
- product
  - `title`
  - `summary`
  - `task_type`
  - `reason_code`
  - `reason_summary`
  - `required_action`
- runtime/acceptance
  - `submission_mode`
  - `acceptance_mode`
  - `acceptance_spec`
  - `resume_checkpoint_ref`
  - `status`
- rewards
  - `reward_preview`
  - `reward_result`
- evidence refs
  - `block_evidence_refs`
  - `submission_evidence_refs`
  - `verification_evidence_refs`
- timestamps
  - `issued_at`
  - `submitted_at`
  - `verified_at`
  - `closed_at`
  - `expires_at`

Status set:

- normal
  - `created`
  - `issued`
  - `in_progress`
  - `submitted`
  - `verifying`
  - `accepted`
  - `resume_queued`
  - `closed`
- exceptional
  - `rejected`
  - `expired`
  - `cancelled`
  - `handoff_blocked`

## 5. Acceptance Contract

Every `HumanAssistTask` must carry an explicit acceptance contract before it can be issued.

Suggested `acceptance_spec` shape:

- `version`
- `verification_window_seconds`
- `submission_requirements`
- `hard_anchors`
- `result_anchors`
- `negative_anchors`
- `persist_check`
- `pass_rule`
- `on_unknown`
- `failure_hint`

Supported acceptance modes:

- `anchor_verified`
- `evidence_verified`
- `state_change_verified`

Rules:

- no acceptance anchors -> task cannot be published
- host saying "我完成了" only starts verification
- verification must read from formal runtime/evidence/environment facts where possible
- unknown verification result must not silently pass

## 6. Chat UX Contract

The chat product contract is:

- current task strip at the top of the active control thread
- task card in the message flow when a task is issued
- host submission from the same thread
- automatic verification response in the same thread
- task history/list reachable from the chat header

Expected assistant responses:

- `正在验收...`
- accepted result
- rejected result
- need-more-evidence result

The acceptance interaction should feel companion-like, but it must still surface concrete proof,
failure hints, and the next required action.

## 7. Reward Model

Rewards are virtual only. The goal is host companionship and visible progress, not cash payout.

Display vocabulary:

- `协作值`
- `同调经验`
- `默契等级`
- `系统熟练度`
- `共生记录`

Suggested level framing:

- `Lv.1 初始连接`
- `Lv.2 协作同调`
- `Lv.3 并肩推进`
- `Lv.4 深度共鸣`
- `Lv.5 共生契约`

Reward display must remain subordinate to truth: rewards are emitted only after acceptance passes.

## 8. Runtime Integration

The feature should plug into the existing chain instead of adding a parallel subsystem.

Required landing surfaces:

- state model + repository + service
- runtime bootstrap wiring
- runtime center read side for current-task strip and history list
- conversation facade enrichment
- `POST /api/runtime-center/chat/run` submission/verification flow
- evidence emission for issue, submit, verify, accept, reject, resume

Preferred data flow:

`blocked execution -> HumanAssistTask issued in chat -> host submission -> verification -> reward result -> resume queued -> formal execution resumes`

## 9. Non-Goals for This Slice

- no cash or wallet system
- no public worker marketplace
- no second durable chat domain
- no arbitrary crowd task dispatch
- no acceptance logic that relies only on tone or wording

## 10. Success Criteria

This feature is successful when:

- the system can explicitly hand a truly human-only step back to the host
- the host can finish and submit it entirely from chat
- the system can verify completion before acceptance
- acceptance emits evidence and queues resume
- the runtime center can show current task and historical task outcomes
