# Claude Code Runtime Donor Adoption Design

## Goal

在不替换 CoPaw 正式上层对象模型、主脑自治主链、Runtime Center 与 truth-first formal memory 的前提下，把 `claude-code-source-code-main` 作为下层 runtime donor，优先吸收其执行契约、单轮闭环、MCP runtime、skill metadata 与 subagent execution shell，先把当前系统收敛到一条能稳定跑通的 canonical run path。

一句话目标：

`先跑通，再硬化，再扩展；Claude Code 只做下层 donor，不做新的系统中心。`

## Why This Design

当前 CoPaw 的主要问题不是“能力不够多”，而是：

1. 上层对象很多，但下层运行骨架不够硬。
2. 执行、治理、证据、恢复虽然都有，但还没有被同一个 runtime contract 绑死。
3. canonical run path 不够单一，导致系统整体“存在很多模块，但没有一条足够可信的执行闭环”。

Claude Code 的强项正好是：

- tool execution contract
- single-turn query loop
- background task / subagent runtime shell
- mature MCP client lifecycle
- skill metadata + loader contract
- plugin/package enablement model

因此最合理的路线不是整包并入，而是采用：

- `A`: 先把 Claude Code 当成 execution runtime donor
- `B`: 再把有价值的下层 contract 内化进 CoPaw 正式 runtime
- 不做 `C`: 不把 Claude Code 的 session/app-state/commands/task UI shell 直接并成 CoPaw 新中心

## Hard Boundaries

以下内容继续保留为 CoPaw 正式真相层与主产品层：

- `src/copaw/state/`
- `src/copaw/kernel/` 的主脑自治主链
- `src/copaw/evidence/`
- `src/copaw/environments/`
- `src/copaw/app/runtime_center/`
- `src/copaw/industry/`
- `src/copaw/memory/` 的 truth-first formal memory

以下内容允许吸收 Claude Code 的下层机制：

- 工具执行上下文与编排 contract
- 单轮 query loop
- subagent / background worker shell
- MCP runtime lifecycle
- skill metadata / loader
- plugin/package enablement
- execution-side private sidecar memory

## What Must Not Be Replaced

以下内容不应被 Claude Code 模型替换：

1. CoPaw 的上层对象模型。
2. `MainBrainOrchestrator` 所在的主脑自治主链。
3. Runtime Center / Industry / StrategyMemory 的正式产品面。
4. truth-first / no-vector formal memory 的正式口径。

这些部分是 CoPaw 比 Claude Code 更接近目标终态的地方。

## Target State

本次 donor adoption 完成后的目标运行链：

`POST /api/runtime-center/chat/run`
-> `MainBrainOrchestrator`
-> `KernelTurnExecutor`
-> `kernel.turn_loop`
-> `CapabilityExecutionFrontDoor`
-> `tool / mcp / system / worker execution`
-> `EvidenceLedger`
-> Runtime Center read surfaces

关键终态要求：

1. 所有外部动作都经过统一 execution front-door。
2. 所有状态推进都经过单一状态机入口。
3. 所有重要执行结果都有正式 `EvidenceRecord`。
4. Runtime Center 能看到目标、owner、风险、结果、证据。

## Architecture Decisions

### 1. Canonical Turn Loop

从 Claude Code 的 `QueryEngine` 借“单轮闭环”思想，但不搬它的 session-first model。

建议新增：

- `src/copaw/kernel/turn_loop.py`

职责固定为：

1. intake
2. intent resolve
3. runtime context bind
4. governance precheck
5. capability execution
6. state transition / writeback
7. evidence commit
8. outcome emit

分工边界：

- `MainBrainOrchestrator`: 主脑执行意图、环境绑定、恢复策略
- `KernelTurnExecutor`: 选执行模式和 turn path
- `turn_loop.py`: 跑完一轮 canonical execution

### 2. Capability Execution Context V2

从 Claude Code 的 `ToolUseContext`、`toolOrchestration`、`toolExecution` 借统一执行契约。

建议新增：

- `src/copaw/capabilities/execution_context.py`
- `src/copaw/capabilities/execution_orchestrator.py`

`CapabilityExecutionContext V2` 最少必须承载：

- task / goal / work_context
- owner_agent_id
- capability mount
- governance snapshot
- environment / session binding
- evidence writer
- timeout / cancellation
- concurrency policy
- result normalization

`execution_orchestrator.py` 负责：

- read-only 并发
- write/action 串行
- capability call lifecycle
- failure classification
- evidence commit hooks

### 3. Formal Execution State Machine

当前 CoPaw 最大风险之一是多个模块都可能“顺手推进状态”。

建议新增：

- `src/copaw/kernel/task_state_machine.py`

要求：

- 所有执行态变更只允许经状态机入口完成
- 恢复、治理、执行、delegation 都调用同一套迁移逻辑
- 读面不可顺手改状态

### 4. Subagent / Worker Runtime Shell

从 Claude Code 借执行壳，不照搬其 task model。

CoPaw 继续保留正式对象：

- `Assignment`
- `Task`
- `AgentReport`

仅吸收这些机制：

- worker lifecycle
- cancel / stop semantics
- background execution shell
- child runtime envelope
- transcript/result handoff

建议新增：

- `src/copaw/kernel/worker_runtime.py`

### 5. MCP Runtime Hardened

当前 CoPaw 的 `MCPClientManager` 足以做基本 init / replace / close，但不足以承载成熟 execution runtime。

建议新增：

- `src/copaw/app/mcp/runtime_client.py`
- `src/copaw/app/mcp/session_cache.py`
- `src/copaw/app/mcp/error_mapping.py`

补强方向：

- auth refresh
- session invalidation
- resource / tool cache
- timeout / retry policy
- richer error classes
- capability probing

### 6. Skill Metadata Formalization

当前 skill 仍偏 filesystem-backed contract，后续要提升为 formal capability source。

建议新增：

- `src/copaw/capabilities/skill_manifest.py`
- `src/copaw/capabilities/skill_loader.py`

skill formal metadata 至少包含：

- description
- when_to_use
- allowed_tools
- required_envs
- risk_level
- evidence_contract
- execution_context
- owner / delete_condition

### 7. Plugin / Package Binding

不照搬 Claude Code 的产品壳，只吸收 package enable/disable/bind 的思路。

建议新增：

- `src/copaw/capabilities/package_registry.py`
- `src/copaw/capabilities/package_binding_service.py`

目标是支持：

- capability package
- install binding
- enable / disable
- environment compatibility check
- role / agent binding

### 8. Sidecar File Memory

Claude Code 的 `memdir` 只可作为 execution-side private sidecar。

建议新增：

- `src/copaw/memory/sidecar_file_memory.py`

硬边界：

- 不能进入 `src/copaw/state/`
- 不能替代 truth-first recall
- 不能替代 `StrategyMemory`
- 只能存 execution-side 偏好、局部协作记忆、短到中期操作经验

## Module Mapping

### Claude Code -> CoPaw Mapping

#### Tool execution contract

- Claude Code:
  - `src/Tool.ts`
  - `src/services/tools/toolOrchestration.ts`
  - `src/services/tools/toolExecution.ts`
- CoPaw landing:
  - `src/copaw/capabilities/execution.py`
  - `src/copaw/capabilities/service.py`
  - `src/copaw/kernel/tool_bridge.py`
  - `src/copaw/kernel/query_execution_tools.py`
  - new `src/copaw/capabilities/execution_context.py`
  - new `src/copaw/capabilities/execution_orchestrator.py`

#### Query main loop

- Claude Code:
  - `src/QueryEngine.ts`
  - `src/query.ts`
- CoPaw landing:
  - `src/copaw/kernel/turn_executor.py`
  - `src/copaw/kernel/main_brain_orchestrator.py`
  - `src/copaw/kernel/query_execution.py`
  - `src/copaw/kernel/query_execution_runtime.py`
  - new `src/copaw/kernel/turn_loop.py`

#### Task / subagent runtime shell

- Claude Code:
  - `src/Task.ts`
  - `src/tools/AgentTool/`
- CoPaw landing:
  - `src/copaw/kernel/delegation_service.py`
  - `src/copaw/kernel/actor_supervisor.py`
  - `src/copaw/kernel/actor_worker.py`
  - `src/copaw/kernel/actor_mailbox.py`
  - new `src/copaw/kernel/worker_runtime.py`
  - new `src/copaw/kernel/task_state_machine.py`

#### MCP runtime

- Claude Code:
  - `src/services/mcp/client.ts`
- CoPaw landing:
  - `src/copaw/app/mcp/manager.py`
  - `src/copaw/capabilities/sources/mcp.py`
  - `src/copaw/capabilities/execution.py`
  - new `src/copaw/app/mcp/runtime_client.py`
  - new `src/copaw/app/mcp/session_cache.py`
  - new `src/copaw/app/mcp/error_mapping.py`

#### Skill metadata

- Claude Code:
  - `src/skills/loadSkillsDir.ts`
- CoPaw landing:
  - `src/copaw/capabilities/skill_service.py`
  - `src/copaw/skill_service.py`
  - `src/copaw/capabilities/models.py`
  - new `src/copaw/capabilities/skill_manifest.py`
  - new `src/copaw/capabilities/skill_loader.py`

#### Plugin / package binding

- Claude Code:
  - `src/plugins/builtinPlugins.ts`
- CoPaw landing:
  - `src/copaw/learning/acquisition_service.py`
  - `src/copaw/capabilities/install_templates.py`
  - `src/copaw/learning/service.py`
  - new `src/copaw/capabilities/package_registry.py`
  - new `src/copaw/capabilities/package_binding_service.py`

#### Sidecar memory

- Claude Code:
  - `src/memdir/memdir.ts`
- CoPaw landing:
  - `src/copaw/memory/sidecar_file_memory.py`

## Delivery Phases

### P0: Minimal Run Path Closure

目标：

先跑通最小 canonical run path，而不是先做全面 donor migration。

P0 只做：

1. 新增 `turn_loop.py`
2. 新增 `execution_context.py`
3. 新增 `task_state_machine.py`
4. 把 file / shell 能力收口到统一 execution contract
5. 让 `EvidenceLedger` 成为正式执行结果落账点

P0 最小链：

`chat/run -> orchestrator -> turn_executor -> turn_loop -> capability front-door -> file/shell -> evidence -> runtime center`

P0 验收标准：

- 聊天前门可触发正式执行
- file 和 shell 两类能力跑通
- 每次执行都有 `EvidenceRecord`
- 执行失败能明确知道失败阶段
- Runtime Center 能看到结果与证据

### P1: Runtime Hardening

目标：

在 P0 跑通基础上，把旧零散 runtime 逐步并入统一 contract。

P1 只做：

1. 统一外部动作 front-door
2. 治理与权限 precheck 收口
3. MCP runtime hardened
4. delegation / worker runtime 接入正式状态机
5. 恢复与阻塞状态推进收口

P1 验收标准：

- 所有外部动作经过统一 execution contract
- governance 不再散落
- MCP 至少跑通一条正式调用
- child task 使用同一 runtime contract
- blocked / waiting-confirm / resumed 状态只通过状态机入口推进

### P2: Skill / Package / Sidecar Closure

目标：

在系统已“能跑、够硬”的基础上补齐 formal extensibility。

P2 只做：

1. skill metadata formalize
2. skill loader formalize
3. package binding
4. sidecar file memory

P2 验收标准：

- skill 成为正式 capability source
- package 可以 enable / disable / bind
- sidecar memory 只服务 execution-side
- formal truth 不受 sidecar 污染

## Cutover Strategy

采用双层渐进切换，不做大爆炸替换。

### Layer 1: Add Before Delete

先新增：

- `turn_loop`
- `execution_context`
- `task_state_machine`

旧路径在 P0 只保留兜底，不再承接新设计。

### Layer 2: Controlled Flow Migration

切流顺序固定为：

1. file / shell
2. MCP
3. delegation / worker runtime
4. skill / package / sidecar

任何阶段都不允许长期双写、双状态推进、双 execution contract 并存。

## Deletion Targets

本次改造不是只加新代码，必须明确退役对象。

P0 后准备退役：

- 各处零散 file / shell 调用上下文拼装
- 各处重复执行结果包装
- 不走统一 front-door 的外部动作入口

P1 后准备退役：

- 偏薄 MCP lifecycle 壳
- 隐式状态推进逻辑
- 恢复靠猜、局部 patch 的旧逻辑

兼容逻辑如必须存在，应放入：

- `src/copaw/compatibility/`
- 或明确的 adapter 文件

不能继续散落到核心 `kernel/state/industry` 路径里。

## Risks

最大的 5 个风险：

1. 新旧 turn path 并存太久，形成双 canonical path。
2. 状态机没有真正收口，多个模块继续各自推进状态。
3. evidence 没跟 execution contract 绑定，Runtime Center 继续失真。
4. 把 Claude Code session/task/app-state 心智抬成新中心，污染 CoPaw 真相层。
5. P0 范围失控，提前把 plugin/memory/skill 全部混做。

## Verification

### P0

- 单元测试：
  - `turn_loop`
  - `task_state_machine`
  - `execution_context`
- 集成测试：
  - `chat/run -> orchestrator -> turn_loop -> file/shell -> evidence`
- 端到端：
  - Runtime Center 可见目标、owner、风险、结果、证据

### P1

- MCP call
- MCP error mapping
- child task runtime
- governance block / confirm
- resume path

### P2

- skill metadata parse
- package enable / disable / bind
- sidecar memory non-canonical boundary

## Success Standard

这次 donor adoption 的成功，不是“吸收了多少 Claude Code 文件”，而是：

1. CoPaw 至少有一条正式执行链稳定跑通。
2. 外部动作统一经过 execution front-door。
3. 状态推进统一经过单一状态机入口。
4. 结果、失败、阻断、证据都能在 Runtime Center 看到。
5. Claude Code 被吸收为下层 runtime donor，而不是新的系统中心。

## Immediate Next Step

设计批准后的下一步不是直接散改，而是写 implementation plan，严格按以下顺序推进：

1. `turn_loop.py`
2. `execution_context.py`
3. `task_state_machine.py`
4. `MainBrainOrchestrator` 接线
5. `KernelTurnExecutor` 接线
6. `CapabilityExecutionFacade` 接线
7. 跑通 file / shell
8. evidence 落账
9. Runtime Center 可见化
10. MCP hardened
