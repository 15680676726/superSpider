# superSpider Public Launch Pack

This file is the first outbound launch pack for `superSpider`.

It is not an architecture document. It is a distribution document for helping people quickly understand, notice, and share the project.

---

## 1. Core positioning

### One-line positioning

`superSpider is the main brain for local autonomous execution.`

### Expanded positioning

`superSpider is a local-first autonomous execution system that keeps planning, memory, knowledge, evidence, and operator control in one main-brain runtime while managed external executors do the actual work.`

### What it is not

- not a generic chat UI
- not a prompt wrapper around tools
- not a random workflow marketplace
- not a black-box agent runner with hidden worker state

### What makes it worth looking at

- one main brain instead of multiple competing control loops
- formal memory and strategy, not just longer prompts
- structured knowledge and task subgraphs, not only text stuffing
- evidence, artifacts, and replay in the same writeback chain
- a visible `Runtime Center` instead of hidden runtime state
- managed external executors, with `Codex` as the current formal path

### Category boundary

Use this distinction consistently in public messaging:

- primary category: `main-brain multi-agent runtime` / `local autonomous execution system`
- secondary application story: `one-person company`, `solo operator`, `small-team leverage`

Do not lead with `one-person company` as the project type. That is a use case. The project itself is an execution system.

---

## 2. GitHub metadata

### Recommended About description

`Main brain for local autonomous execution with formal memory, structured knowledge, visible runtime state, and managed external executors.`

### Recommended website field

If no external website exists, leave it empty instead of pointing to an outdated domain.

### Recommended topics

- `ai-agent`
- `agent-runtime`
- `autonomous-agents`
- `automation`
- `codex`
- `fastapi`
- `knowledge-graph`
- `local-first`
- `long-running-agents`
- `python`
- `react`
- `runtime-center`

---

## 3. Short descriptions

### 50-character style tagline

`A main brain for local autonomous execution`

### 100-140 character social blurb

`superSpider is a local-first main-brain runtime for long-running AI execution, with memory, knowledge, evidence, recovery, and managed external executors.`

### Short paragraph

`Most AI projects stop at chat and tool calls. superSpider is trying to solve the harder layer: one main brain that plans and supervises, formal memory and knowledge that survive over time, managed external executors that do real work, and a Runtime Center that keeps runtime state, evidence, and recovery visible.`

### Scenario-style blurb

`If you want AI to act less like a chat tab and more like the operating layer of a one-person company, superSpider is the kind of system to look at: one main brain, durable memory, structured knowledge, managed executors, and visible runtime truth.`

---

## 4. Capability proof points to emphasize

These are the concrete strengths that should be repeated across README, launch posts, demos, and talks.

### Main Brain

- one control plane instead of multiple competing loops
- planning, delegation, supervision, and recovery stay in one formal runtime
- external executors do work, but they do not become a second brain

### Memory System

- strategy and long-running context survive beyond one chat turn
- the system is designed to keep operating context instead of rebuilding everything from prompt history

### Knowledge System

- structured knowledge and task subgraphs, not only raw text stuffing
- runtime decisions can be grounded in formal knowledge objects

### Evidence and replay

- execution does not end as invisible text output
- evidence, artifacts, and writeback stay in the same chain
- operators can inspect what happened instead of trusting a black box

### Runtime Center

- runtime state is visible instead of buried in logs
- recovery and execution progress can be surfaced in one place

### External executors

- execution is separated from the main brain
- `Codex` is the current formal executor path
- future executors can be attached without duplicating truth or control planes

---

## 5. Who should care

- developers building long-running agent systems
- people tired of chat-first AI demos that cannot sustain execution state
- local-first automation builders
- engineers who care about runtime truth, evidence, recovery, and replay
- contributors interested in main-brain architecture rather than one-off prompt tricks
- solo founders and one-person-company builders who want a real execution layer instead of a chat assistant

---

## 6. English launch post

### Long version

`I just open-sourced superSpider.`

`It is not another chat wrapper. It is a local autonomous execution system built around one main brain, one truth chain, structured memory and knowledge, evidence-first writeback, and a visible Runtime Center.`

`Today the formal external executor path is Codex. The goal is to let the same main brain govern more executors over time without turning them into a second brain or a second truth source.`

`If you care about long-running agent systems, local-first execution, visible runtime state, recovery, and evidence instead of black-box prompting, this is the direction I am building toward.`

`Repo: https://github.com/15680676726/superSpider`

### Short version

`Open-sourced superSpider today.`

`It is a local autonomous execution system with one main brain, formal memory and knowledge, a visible Runtime Center, evidence-first writeback, and managed external executors. Codex is the current formal executor path.`

`https://github.com/15680676726/superSpider`

---

## 7. Chinese launch post

### 长版

`今天把 superSpider 开源了。`

`它不是另一个聊天壳子，而是一套面向本地长期自治执行的主脑系统。`

`这套系统想解决的不是“模型怎么多回两句”，而是更难的那一层：`

- `主脑如何长期判断下一步做什么`
- `记忆和知识如何不只停留在 prompt 里`
- `外部执行体如何真正干活但不取代主脑`
- `证据、回放、恢复和操作员控制如何保持可见`

`当前正式外部执行体路径是 Codex。`

`如果你关心本地自治执行、长期 agent runtime、可见运行态、证据链和恢复能力，这个项目可能值得看。`

`仓库地址： https://github.com/15680676726/superSpider`

### 短版

`superSpider 开源了。`

`它不是聊天壳子，而是面向本地长期自治执行的主脑系统：主脑 + 记忆 + 知识 + 证据 + Runtime Center + 外部执行体。当前正式执行体路径是 Codex。`

`https://github.com/15680676726/superSpider`

---

## 8. Community-specific versions

### Hacker News style

Title:

`Show HN: superSpider – a local autonomous execution runtime with a main brain, memory, knowledge, and managed executors`

Body:

`I have been working on a local-first execution system instead of a chat-first assistant.`

`The core idea is simple: planning and supervision stay in one main brain, memory and knowledge stay in a formal truth chain, execution goes through managed external executors, and runtime state plus evidence stay visible in one Runtime Center.`

`Codex is the current formal executor path.`

`I would especially value feedback from people working on long-running agent systems, runtime observability, recovery, and local execution.`

### Reddit style

`I open-sourced a local autonomous execution system called superSpider.`

`It is aimed at a different problem than most chat-based agent demos: long-running work that needs a main brain, durable memory, structured knowledge, evidence, recovery, and a visible runtime surface.`

`Codex is the current external executor path.`

`Would love feedback from people building agent runtimes and local automation tools.`

### V2EX / 中文社区风格

`把一个自己长期在做的本地自治执行系统开源了，叫 superSpider。`

`它不是聊天壳子，核心是主脑、正式记忆、结构化知识、证据回写、Runtime Center 和外部执行体。`

`当前正式外部执行体路径是 Codex，后面会继续扩展。`

`如果你关注 AI agent runtime、本地自动化、可见运行态和长期执行链，可以看看。`

---

## 9. 60-second demo script

This is the minimum demo story to make the project understandable.

### Demo sequence

1. Open the repository README
   - show the one-line positioning and the system overview diagram
2. Open Runtime Center
   - show that this is not just a chat page
3. Trigger one execution loop
   - main brain decides
   - external executor starts
   - runtime events appear
4. Show evidence/writeback
   - operator can see what happened
5. End on the architecture sentence
   - `one main brain, one truth chain, one visible runtime surface`

### Demo narration

`superSpider is not trying to be another chat wrapper.`

`The main brain decides what should happen next. Memory and knowledge make the system durable over time. An external executor does the execution turn. Then runtime events, evidence, and replay come back into the same visible Runtime Center.`

`That is the core idea: long-running execution with one control plane instead of a pile of hidden loops.`

---

## 10. Launch checklist

Before sharing publicly, make sure these are done:

- README top section is current
- About description matches the project
- topics are set
- at least one release exists
- one short demo clip or GIF is ready
- one issue labeled `good first issue` exists
- one discussion or issue explicitly welcomes feedback

---

## 11. Recommended first distribution order

1. GitHub repository page
2. One English launch post
3. One Chinese launch post
4. One short demo clip
5. One follow-up post focused on architecture instead of announcement

Do not try to explain every subsystem in the first announcement. The first announcement should make people curious enough to click. The README and demo then do the heavier explanatory work.
