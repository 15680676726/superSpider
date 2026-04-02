# Main-Brain Default Chat Briefness Design

## Goal

Make ordinary main-brain chat feel closer to `cc` at the front door by tightening the default `CHAT` reply discipline only.

## Scope

In scope:

- tighten the default `Mode: CHAT` prompt tail
- make clear/simple asks default to a shorter direct answer
- reduce repeated request restatement and background padding
- keep the existing `plan / review / resume / verify` shell behavior unchanged

Out of scope:

- new keyword families
- new state machines
- extra model passes
- new local reply classifiers or "briefness profile" layers
- changes to formal truth, writeback, or orchestration boundaries

## Constraints

- Keep CoPaw formal truth in `StrategyMemory -> Lane -> Backlog -> Cycle -> Assignment -> Report`.
- Keep `/api/runtime-center/chat/run` as the only chat front door.
- Do not add a second planning center or another intent-routing layer.
- Avoid editing the large Chinese system prompt body unless necessary; prefer tightening the existing default shell tail in `main_brain_chat_service.py`.
- Borrow `cc` front-door discipline only. Do not transplant `cc`-specific labels, slash-command semantics, donor wording, or any donor-only shell names into CoPaw `CHAT` replies.
- Keep this change to prompt-tail text only. Do not widen scope into token-limit tuning, response post-processing, or any other behavioral layer.

## Approaches Considered

### 1. Add a local reply-classification layer

Rejected.

This would push CoPaw away from "borrow CC discipline, not CC product complexity" and add one more front-door mechanism to maintain.

### 2. Lower `max_tokens` globally

Rejected.

It is too blunt. It can shorten good replies, but it does not reliably improve reply shape.

### 3. Tighten only the default `CHAT` shell tail

Selected.

This is the closest donor-boundary move:

- no extra mechanism
- no new truth
- no new mode
- direct impact on ordinary chat tone and length
- no donor-language transplant into CoPaw reply text

## Design

The default `Mode: CHAT` shell tail should add stronger front-door rules:

- answer clear/simple asks directly first
- default simple asks to `1-2` sentences
- do not restate the user's request unless it changes execution or risk understanding
- do not expand into bullets or sections for simple asks
- do not add background or implementation detail unless the user asked for depth
- if clarification is required, ask only one decisive question

The existing `plan / review / resume / verify` shell tails remain unchanged.
This change must not modify their wording, structure, or verification behavior.

## Verification

- add failing tests around the default `CHAT` tail text
- run focused `pytest` for `test_main_brain_chat_service.py`
- confirm no regression to `plan / review / resume / verify` shell-tail tests
