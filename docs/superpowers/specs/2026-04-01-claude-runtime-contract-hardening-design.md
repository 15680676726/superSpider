# Claude-Derived Runtime Contract Hardening Design

## Goal

在不替换 CoPaw 正式真相层、主脑自治主链、Runtime Center 与 truth-first formal memory 的前提下，吸收 Claude Code 成熟的下层 runtime contract 设计，把 CoPaw 当前“不容易完整跑通任务”的薄弱执行层收紧成一条更稳定的、可诊断的、可持续演进的执行闭环。

一句话目标：

`不是移植 Claude Code，而是用 Claude-derived contract 硬化 CoPaw 已经活着的主链。`

## Current Reality

这次工作的前提不是“系统完全坏了”，而是：

- 当前主脑主链和正式对象层已经活着。
- 代表性测试已能通过，说明现有主链不是零基线重建问题。
- 真正的问题是每次执行完整任务时，下层 contract 不够硬，导致执行容易在不同边界失配、阻断或失真。

因此这次工作的性质应是：

- runtime contract hardening
- canonical run path tightening
- execution-grade completion repair

而不是：

- Claude Code module transplant
- 第二套执行中心
- 主脑/真相层重建

## Unified Ingress Boundary

CoPaw 需要保留聊天前门，但要明确它的边界。

`/runtime-center/chat/run` 的正确定位是：

- 统一入口
- transport ingress
- payload normalization boundary
- stream relay / request relay surface

它不应被理解为：

- 聊天系统本身
- 第二条主链
- 与主脑并列的语义中心

正确形态应为：

`front door -> intake -> main brain classify -> chat or execute branch -> unified runtime contract`

这意味着：

1. `chat/run` 继续存在
2. 主脑继续判断本轮是聊天还是执行
3. `KernelTurnExecutor` 继续承担 runtime branch selection
4. 前门不再各自长出一套聊天逻辑和一套执行逻辑

后续如需继续硬化，正确方向是引入更正式的 operator ingress service，让 `chat/run` 成为该 ingress 的一个 HTTP surface，而不是继续让前门承载更多业务语义。

## What Must Not Be Replaced

以下内容继续保留为 CoPaw 正式核心：

1. `src/copaw/state/` 的 formal truth
2. `MainBrainOrchestrator` 所在的主脑自治主链
3. `Runtime Center / Industry / StrategyMemory` 的正式产品面
4. truth-first / no-vector formal memory

这些层是 CoPaw 比 Claude Code 更接近目标终态的部分。

## What Should Be Hardened

真正需要替换或收紧的是下层 runtime contract：

1. 统一执行上下文
2. 统一 file/shell front-door
3. 统一执行结果与证据落账
4. 统一 phase/status projection
5. 更薄、更清晰的 canonical turn loop
6. 后续再补 MCP runtime、subagent shell、skill/package contract

## Claude Autonomy Extraction Boundary

Claude Code 在“自治执行壳”上有很多成熟做法，这部分值得吸收，但不能整套复制。

可以借的内容：

1. request normalization
2. single-turn intake discipline
3. task envelope
4. worker lifecycle
5. background execution shell
6. child task / subagent result envelope
7. stage-aware failure model

不能整套复制的内容：

1. Claude 的 session-first 中心
2. Claude 的 task/app-state 产品心智
3. Claude 顶层的 agent/task/product model
4. Claude 作为 CoPaw 的新调度中心

CoPaw 的正式上层对象仍然是：

- `BacklogItem`
- `OperatingCycle`
- `Assignment`
- `Task`
- `AgentReport`

因此后续正确做法是：

- 借 Claude 的 execution shell
- 不替换 CoPaw 的正式任务与调度对象
- 把成熟自治能力落成 CoPaw 现有对象体系下的 execution hardening

## Core Design Decisions

### 1. `CapabilityExecutionContext` 先落在执行层内部

P0 第一刀不是重写主脑，也不是改前门，而是先把统一执行上下文落在：

- `src/copaw/capabilities/execution.py`

新增：

- `src/copaw/capabilities/execution_context.py`

P0 里它只承担内部标准上下文，不承担新的系统中心职责。

最低职责：

- task / goal / work_context identity
- capability identity
- owner / risk / environment binding
- evidence binding
- cancellation / timeout
- read-vs-write execution hints

### 2. `task_state_machine` 只能包装现有 `KernelTask.phase`

P0 最大约束：

- 不新增第二套 live vocabulary
- 不发明另一套 canonical task status 语言

CoPaw 当前正式 kernel phase 已经存在：

- `pending`
- `risk-check`
- `executing`
- `waiting-confirm`
- `completed`
- `failed`
- `cancelled`

而对外 live contract 已经收成：

- `assigned`
- `queued`
- `claimed`
- `executing`
- `blocked`

因此新增的：

- `src/copaw/kernel/task_state_machine.py`

只能做两件事：

1. 包装现有 `KernelTask.phase` 合法迁移
2. 复用现有 phase <-> task/runtime status mapping

不能做的事：

1. 发明新的 canonical vocabulary
2. 在 P0 重新定义 live status contract
3. 跳过现有 `TaskLifecycleManager` / persistence mapping

### 3. P0 先收 file/shell，再碰 turn loop

P0 首刀应先落在：

- `src/copaw/capabilities/execution.py`
- `src/copaw/kernel/tool_bridge.py`

先把：

- file
- shell
- evidence

三者收成统一 front-door。

只有在这条下层 contract 收紧并通过测试后，才增加：

- `src/copaw/kernel/turn_loop.py`

### 4. `turn_loop.py` 在 P0 只能是薄适配层

P0 中的 `turn_loop.py` 不是重写：

- `MainBrainOrchestrator`
- `/runtime-center/chat/run`
- Runtime Center read model

它只能是：

- 一个薄的 orchestration wrapper
- 编排现有组件
- 最后以最小侵入方式接到 `KernelTurnExecutor`

P0 原则：

- 不重写主脑
- 不重写聊天前门
- 不改造 Runtime Center 为了迎合 turn loop

### 5. Claude Code 文件只作为语义参考，不做 1:1 移植

最容易误导实现者的地方，是把“参考 Claude Code”理解成“认领 donor 文件”。

本设计明确禁止这种实现姿势。

正确做法是：

- 抽 contract
- 抽边界
- 抽 failure model
- 抽 lifecycle discipline

错误做法是：

- 逐文件对搬
- 在 CoPaw 里抬第二套 session/task/app-state 中心

## Reference Extraction Map

以下映射是“提炼 contract”的参考，不是 1:1 文件迁移计划。

### Tool execution contract

参考：

- `claude-code-source-code-main/src/Tool.ts`
- `claude-code-source-code-main/src/services/tools/toolOrchestration.ts`
- `claude-code-source-code-main/src/services/tools/toolExecution.ts`

落位：

- `src/copaw/capabilities/execution.py`
- `src/copaw/capabilities/execution_context.py`
- `src/copaw/kernel/tool_bridge.py`

提炼内容：

- execution context
- read/write orchestration discipline
- normalized result envelope
- tool/evidence coupling

### Query loop

参考：

- `claude-code-source-code-main/src/QueryEngine.ts`
- `claude-code-source-code-main/src/query.ts`

落位：

- `src/copaw/kernel/turn_loop.py`
- `src/copaw/kernel/turn_executor.py`

提炼内容：

- single-turn closure
- stage ordering
- stage-aware failure surface

### Task / subagent runtime shell

参考：

- `claude-code-source-code-main/src/Task.ts`
- `claude-code-source-code-main/src/tools/AgentTool/`

落位：

- `src/copaw/kernel/actor_worker.py`
- `src/copaw/kernel/actor_supervisor.py`
- `src/copaw/kernel/delegation_service.py`

提炼内容：

- worker lifecycle
- cancel/stop semantics
- background execution shell

此项不进入 P0。

### MCP runtime

参考：

- `claude-code-source-code-main/src/services/mcp/client.ts`

落位：

- `src/copaw/app/mcp/manager.py`

提炼内容：

- lifecycle hardening
- auth/session/cache/error policy

此项不进入 P0。

### Skill/package contract

参考：

- `claude-code-source-code-main/src/skills/loadSkillsDir.ts`
- `claude-code-source-code-main/src/plugins/builtinPlugins.ts`

落位：

- `src/copaw/capabilities/skill_service.py`
- `src/copaw/capabilities/models.py`
- future package binding services

此项不进入 P0。

### Sidecar memory

参考：

- `claude-code-source-code-main/src/memdir/memdir.ts`

落位：

- `src/copaw/memory/sidecar_file_memory.py`

此项只能作为 execution-side non-canonical sidecar，不进入 P0。

## P0 Scope

P0 只做这 4 步：

1. 新增 `CapabilityExecutionContext`，但只作为 `capabilities/execution.py` 的内部标准上下文。
2. 新增 `task_state_machine`，只统一现有 `KernelTask.phase` 迁移规则和 phase/status projection，不改 live vocabulary。
3. 先把 file/shell 两条执行链通过统一 front-door 跑通并补证据测试。
4. 最后再加一个薄的 `turn_loop.py`，只编排现有组件，并以最小侵入方式接到 `KernelTurnExecutor`。

P0 明确不做：

- 重写 `MainBrainOrchestrator`
- 改写 `/runtime-center/chat/run`
- 为了 turn loop 重做 Runtime Center 读面
- MCP runtime hardening
- subagent shell hardening

## P1 Scope

P0 绿灯后，P1 再做：

1. MCP runtime hardened
2. request normalization hardening
3. task envelope hardening
4. assignment execution / worker lifecycle hardening
5. 更正式的 execution diagnostics
6. 更清晰的 turn-loop stage failure surface
7. 必要时再扩到 `QueryExecutionRuntime`

## P2 Scope

P1 之后，再做：

1. subagent / worker runtime hardening
2. skill metadata formalization
3. package binding
4. sidecar memory
5. 更强的自治执行策略与降级策略

## Risks

这次工作的最大风险不是“改得不够多”，而是：

1. 重新造出第二套状态词汇
2. 过早切入主脑和前门
3. 把 donor reference 写成 donor transplant
4. 把活着的主链当成重建对象
5. 把 Claude 的自治壳误当成 CoPaw 的上层调度模型

## Success Standard

P0 的成功不是“Claude Code 进来了多少”，而是：

1. file/shell 执行都走统一 front-door
2. evidence 写入和执行 contract 绑定
3. `KernelTask.phase` 迁移更清晰，但没有新增第二套 vocabulary
4. 现有聊天前门仍然活着
5. 在不打断现有主链的前提下，更容易把完整任务跑通

## Immediate Next Step

下一步不是继续扩范围，而是按收紧后的 `P0` 写实现计划：

1. `execution_context.py`
2. `task_state_machine.py`
3. file/shell/evidence front-door hardening
4. thin `turn_loop.py`
