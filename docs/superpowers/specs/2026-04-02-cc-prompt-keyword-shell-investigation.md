# CC Prompt / Keyword / Planning Shell Investigation For CoPaw

## Goal

基于真实源码与真实调用路径，核查本地 `cc` 项目到底如何组织 prompt、关键词、planning shell，再给出一份适合 CoPaw 的更准确借鉴方案。

本调查只回答三件事：

1. `cc` 真正强在哪里
2. 哪些部分可以借到 CoPaw
3. 哪些部分不能借，或者即使能借也不能原样照搬

---

## Evidence Standard

本调查采用以下证据优先级：

1. 真实源码与真实调用路径
2. 测试、注释、状态管理代码中的行为说明
3. 文档与 README 仅作旁证

本次直接核查的关键文件包括：

- `cc/src/constants/prompts.ts`
- `cc/src/constants/systemPromptSections.ts`
- `cc/src/utils/systemPrompt.ts`
- `cc/src/utils/queryContext.ts`
- `cc/src/bootstrap/state.ts`
- `cc/src/utils/messages.ts`
- `cc/src/utils/attachments.ts`
- `cc/src/utils/ultraplan/keyword.ts`
- `cc/src/utils/processUserInput/processUserInput.ts`
- `cc/src/tools/EnterPlanModeTool/prompt.ts`
- `cc/src/tools/ExitPlanModeTool/prompt.ts`
- `cc/src/tools/AskUserQuestionTool/prompt.ts`
- `cc/src/tools/TodoWriteTool/prompt.ts`
- `cc/src/tools/TaskCreateTool/prompt.ts`
- `cc/src/tools/TaskUpdateTool/prompt.ts`
- `cc/src/tools/TaskListTool/prompt.ts`
- `cc/src/tools/TaskGetTool/prompt.ts`
- `cc/src/commands/plan/plan.tsx`
- `cc/src/commands/ultraplan.tsx`
- `cc/src/commands/review.ts`
- `cc/src/commands/review/reviewRemote.ts`
- `cc/src/commands/review/ultrareviewCommand.tsx`
- `cc/src/components/PromptInput/PromptInput.tsx`
- `cc/src/utils/plans.ts`
- `cc/src/utils/planModeV2.ts`

同时核对了 CoPaw 当前正式边界与现状：

- `AGENTS.md`
- `docs/superpowers/specs/2026-04-01-main-brain-single-loop-chat-design.md`
- `docs/superpowers/specs/2026-04-01-knowledge-activation-layer-design.md`
- `docs/superpowers/specs/2026-04-01-claude-runtime-contract-hardening-design.md`
- `src/copaw/kernel/main_brain_chat_service.py`
- `src/copaw/kernel/main_brain_scope_snapshot_service.py`
- `src/copaw/kernel/main_brain_orchestrator.py`
- `src/copaw/kernel/main_brain_intake.py`
- `src/copaw/state/models_reporting.py`
- `src/copaw/state/models_goals_tasks.py`

### Source limitation

`cc/src/commands/ultraplan.tsx` 明确引用了 `../utils/ultraplan/prompt.txt`，但当前本地 `cc` 工作树中该文件不存在。

这意味着：

- 我可以确认 `ultraplan` 的装配方式、调用链、状态机与远端回流机制
- 但不能对 `ultraplan` 远端专用说明文本做“逐字完整确认”
- 这不是推断，而是当前本地源码树的客观缺口

---

## Executive Conclusion

结论先说清楚：

`cc` 的强项不是“大而全的关键词词库”，而是四层壳一起工作：

1. 分段的系统 prompt
2. 会话级 prompt section 缓存
3. 基于 attachment 的状态提醒与 delta 注入
4. 显式的 plan / review / task shell

进一步说：

- `cc` 的“关键词厉害”更多是触发纪律厉害，不是关键词资产本身厉害
- `cc` 的 planning shell 确实成熟，但它不是靠主 prompt 自己悟出来，而是靠显式 plan mode、plan file、exit tool、ask-question 纪律共同驱动
- `cc` 的远端 `ultraplan` / `ultrareview` 是产品壳，不是 CoPaw 应该照搬的正式真相链

对 CoPaw 的正确结论是：

- 可以借 `cc` 的前门壳、触发纪律、planning shell discipline
- 不能把 `cc` 的 session-first / remote-first 产品模型搬成 CoPaw 的正式对象链
- CoPaw 的正式真相仍应继续收敛到 `StrategyMemory -> Lane -> Backlog -> Cycle -> Assignment -> Report`

---

## Confirmed CC Behavior

## 1. CC 不是“一个大 system prompt”，而是多层 prompt surface

直接证据：

- `cc/src/constants/prompts.ts`
- `cc/src/utils/systemPrompt.ts`
- `cc/src/utils/queryContext.ts`
- `cc/src/bootstrap/state.ts`

确认到的事实：

1. 基础系统 prompt 由 `getSystemPrompt(...)` 生成，不是硬编码单块文本。
2. `buildEffectiveSystemPrompt(...)` 还会在默认 prompt 之上叠加：
   - override system prompt
   - coordinator prompt
   - agent prompt
   - custom system prompt
   - append system prompt
3. `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 明确把 prompt 拆成“静态前缀”和“动态后缀”。
4. `systemPromptSection(...)` 与 `resolveSystemPromptSections(...)` 提供了 section 级缓存。
5. section 缓存保存在 `bootstrap/state.ts` 的 `systemPromptSectionCache` 中。

这意味着：

- `cc` 的 prompt 不是“每轮重建整段大词”
- 它明确在做 prefix 稳定化和动态段最小重算

### 当前可直接确认的动态 section

来自 `cc/src/constants/prompts.ts` 的真实 section 包括：

- `session_guidance`
- `memory`
- `ant_model_override`
- `env_info_simple`
- `language`
- `output_style`
- `mcp_instructions`，且这是明确标注为 `DANGEROUS_uncachedSystemPromptSection(...)`
- `scratchpad`
- `frc`
- `summarize_tool_results`
- `numeric_length_anchors`
- `token_budget`
- `brief`

核心含义：

- 风格、语言、memory、MCP、brief、长度约束都不是糊在一大段里
- 哪些会破缓存、哪些不该破缓存，在源码里是显式设计的

## 2. CC 的很多“提示词”实际上在 attachments，不在 base system prompt

直接证据：

- `cc/src/utils/attachments.ts`
- `cc/src/utils/messages.ts`

确认到的 attachment prompt surface 至少包括：

- `plan_mode`
- `plan_mode_reentry`
- `plan_mode_exit`
- `auto_mode`
- `auto_mode_exit`
- `relevant_memories`
- `skill_listing`
- `skill_discovery`
- `agent_listing_delta`
- `deferred_tools_delta`
- `mcp_instructions_delta`
- `output_style`
- `selected_lines_in_ide`
- `opened_file_in_ide`
- `mcp_resource`
- `critical_system_reminder`

这件事非常重要，因为它解释了为什么 `cc` 看起来“很会切换模式”：

- 不是把所有模式都揉进主 system prompt
- 而是把 mode 状态、增量能力、记忆、技能、计划提醒，拆成 side attachments

这套做法对 CoPaw 很有借鉴价值。

## 3. CC 的 planning shell 是显式状态机，不是主模型自由发挥

直接证据：

- `cc/src/tools/EnterPlanModeTool/prompt.ts`
- `cc/src/tools/ExitPlanModeTool/prompt.ts`
- `cc/src/tools/AskUserQuestionTool/prompt.ts`
- `cc/src/utils/messages.ts`
- `cc/src/utils/attachments.ts`
- `cc/src/utils/plans.ts`
- `cc/src/commands/plan/plan.tsx`
- `cc/src/utils/planModeV2.ts`

确认到的事实：

1. 进入 plan mode 是显式工具，不是自然语言猜出来的隐式状态。
2. 进入之后，模型被明确限制为：
   - 除 plan file 外不能编辑其他文件
   - 不能跑非只读工具
   - 只能读代码、写 plan file、问用户问题、最后调用 `ExitPlanMode`
3. plan mode 不是一个固定单流程，至少有两种真实 workflow：
   - 五阶段 workflow
   - interview-based iterative workflow
4. `plan_mode` attachment 有 full / sparse reminder 节律。
5. `plan_mode_exit` 是一次性 attachment，不靠模型自己记住“现在已经退出规划模式”。
6. plan 的落地介质是显式 `plan file`，由 `utils/plans.ts` 管理。

### 这意味着什么

`cc` 的 planning 能力不是“主脑变聪明了”，而是：

- 计划模式显式进入
- 计划模式显式退出
- 计划中只能用特定动作
- 计划内容写进外部 plan file
- 是否批准计划由专门工具承接

这正是 CoPaw 当前前门表达壳偏弱、但可以直接借鉴的部分。

## 4. CC 的关键词层并不大，强的是触发纪律

直接证据：

- `cc/src/utils/ultraplan/keyword.ts`
- `cc/src/utils/processUserInput/processUserInput.ts`
- `cc/src/components/PromptInput/PromptInput.tsx`

这次调查最重要的一个纠偏结论：

在当前本地 `cc` 源码里，明确实现的 planning/review 关键词并不多。

可以直接确认的关键词实现只有：

- `ultraplan`
- `ultrareview`

而且它们不是随便匹配，而是有非常明确的排除规则：

- 跳过引号、反引号、括号、尖括号、方括号、花括号中的出现
- 跳过路径/标识符上下文，如 `/`、`\`、`-`、扩展名场景
- 问句 `?` 后缀不触发
- slash command 输入不触发

### 更关键的事实

1. `ultraplan` 关键词会在 `processUserInput.ts` 中被真正改写并路由到 `/ultraplan`
2. `ultrareview` 在当前核查范围内只看到 UI 高亮与提示，没有看到同级别自动路由到 `/ultrareview`
3. 也就是说，`cc` 当前并不存在一个“巨大关键词总线，任何意图都自动切模式”的证据

这直接推翻一种常见误解：

> `cc` 强在一套特别庞大、特别专业的关键词库。

当前源码更支持的真实说法是：

> `cc` 强在少量关键词的触发纪律、前门壳、显式状态机和配套 prompt shell。

## 5. CC 的 task shell 也不是“模型自觉”，而是工具纪律

直接证据：

- `cc/src/tools/TodoWriteTool/prompt.ts`
- `cc/src/tools/TaskCreateTool/prompt.ts`
- `cc/src/tools/TaskUpdateTool/prompt.ts`
- `cc/src/tools/TaskListTool/prompt.ts`
- `cc/src/tools/TaskGetTool/prompt.ts`

确认到的事实：

- 复杂任务需要显式 task list / todo
- 状态流转明确要求 `pending -> in_progress -> completed`
- 不能在失败、未验证、部分完成时标记完成
- plan mode 下也鼓励 task 管理

所以 `cc` 的“执行很稳”同样不是只来自主 prompt，而是：

- task shell
- status discipline
- verification discipline

## 6. CC 的 memory 也不是纯 base prompt，而是“缓存段 + 异步 surfacing”

直接证据：

- `cc/src/constants/prompts.ts`
- `cc/src/utils/attachments.ts`
- `cc/src/services/compact/compact.ts`
- `cc/src/services/AgentSummary/agentSummary.ts`

确认到的事实：

1. `memory` 本身是 system prompt 的一个 section。
2. `relevant_memories` 会以 attachment 形式注入。
3. relevant memory 搜索是 prefetch 异步启动的，不一定阻塞主 turn。
4. compaction、agent summary 这类机制都在努力复用 cache-safe params，而不是每次重造整段上下文。

因此：

- `cc` 的“记忆感”不是全靠主 prompt 每轮重建
- 它把一部分记忆 surfacing 后移成 attachment / side path

## 7. CC 的远端产品壳和本地 planning shell必须拆开理解

直接证据：

- `cc/src/commands/ultraplan.tsx`
- `cc/src/utils/ultraplan/ccrSession.ts`
- `cc/src/commands/review.ts`
- `cc/src/commands/review/reviewRemote.ts`
- `cc/src/commands/review/ultrareviewCommand.tsx`

确认到的事实：

1. `ultraplan` 明确接远端 CCR 会话。
2. `ccrSession.ts` 明确在轮询远端 `ExitPlanMode` 的批准结果。
3. `review.ts` 里 `/review` 是本地 review，`/ultrareview` 是唯一远端 bughunter 路径。
4. `ultrareview` 并不是普通本地 planning shell 的一部分，而是远端产品能力。

所以：

- 不能把 `cc` 的 remote review / remote planning 当作“关键词体系”的核心资产
- 它们更像 Anthropic 产品级服务壳

---

## Prompt Surface Inventory

## 1. Main prompt surfaces

当前确认的核心 prompt 面包括：

- `constants/prompts.ts`
  - 默认 system prompt 主装配器
- `utils/systemPrompt.ts`
  - effective system prompt 叠加器
- `utils/queryContext.ts`
  - cache-safe prefix 组装辅助
- `utils/messages.ts`
  - attachments 转系统提醒
- `utils/attachments.ts`
  - attachment 生成器

## 2. Tool prompt surfaces

当前本地 `cc/src/tools/` 下实际存在 `36` 个 `prompt.ts` 类文件。

其中与本次主题直接相关的核心文件是：

- `AgentTool/prompt.ts`
- `AskUserQuestionTool/prompt.ts`
- `BriefTool/prompt.ts`
- `EnterPlanModeTool/prompt.ts`
- `ExitPlanModeTool/prompt.ts`
- `TaskCreateTool/prompt.ts`
- `TaskUpdateTool/prompt.ts`
- `TaskListTool/prompt.ts`
- `TaskGetTool/prompt.ts`
- `TodoWriteTool/prompt.ts`
- `SkillTool/prompt.ts`

## 3. Command prompt surfaces

与本次主题直接相关的 command 层包括：

- `/plan`
- `/ultraplan`
- `/review`
- `/ultrareview`

其中：

- `/plan` 偏本地 planning shell
- `/ultraplan` 偏远端 CCR planning
- `/review` 偏本地 review prompt
- `/ultrareview` 偏远端 review product shell

---

## What The Earlier Hypothesis Got Right

以下判断，当前源码证据支持：

1. 值得借 mode switch shell
2. 值得借关键词解析纪律
3. 值得借 planning shell discipline
4. 不应把 Claude 的 session-first 模型当成 CoPaw 正式真相链
5. CoPaw 的正式对象链比 Claude 的前门壳更适合做长期正式真相

---

## What The Earlier Hypothesis Missed Or Overstated

以下地方，之前那种“Claude 关键词很强、很专业”的说法是不够准确的：

## 1. 没有证据表明 CC 依赖一个庞大的关键词语义库

当前能直接确认的关键词实现非常少，至少在 planning/review 入口上就是如此。

真正强的是：

- 触发纪律
- 模式壳
- plan file
- attachment 状态提醒
- tool-level prompt discipline

不是“大词库”本身。

## 2. `ultrareview` 并不是和 `ultraplan` 同级别的自动关键词路由

当前可确认：

- `ultraplan` 会自动 route
- `ultrareview` 主要是 UI 提示与显式命令入口

所以不能把这两者都当成“关键词自动分流”的例子。

## 3. `cc` 的 planning shell 有一大块是远端产品壳，不适合搬到 CoPaw

像这些都不应原样搬：

- CCR 远端 session
- overage / quota / billing dialog
- bughunter / remote review
- 远端 teleport / archive / poll session 机制

这些不是 CoPaw 的正式对象边界。

## 4. `ultraplan` 的远端专用 prompt 文本无法在当前本地工作树里完整确认

因为被引用的 `prompt.txt` 缺失，所以不能对那一块做“完整原文确认”。

严谨结论应该是：

- `ultraplan` 调用链、状态机、审批回流可以确认
- 远端初始提示文本当前无法在本地工作树完整核实

---

## CoPaw Current Baseline

## 1. CoPaw 的正式真相链已经更高级

直接证据：

- `AGENTS.md`
- `src/copaw/state/models_reporting.py`
- `src/copaw/state/models_goals_tasks.py`

当前正式对象已经存在：

- `StrategyMemoryRecord`
- `OperatingLaneRecord`
- `BacklogItemRecord`
- `OperatingCycleRecord`
- `AssignmentRecord`
- `AgentReportRecord`

这说明：

- CoPaw 不缺正式对象
- CoPaw 缺的是前门表达壳和模式纪律

## 2. CoPaw 当前单环主脑链已经有 prompt 分段基础

直接证据：

- `src/copaw/kernel/main_brain_chat_service.py`
- `src/copaw/kernel/main_brain_scope_snapshot_service.py`

当前已经存在：

- `_PURE_CHAT_SYSTEM_PROMPT`
- `_build_stable_prompt_prefix(...)`
- `_build_scope_snapshot_body(...)`
- `_build_lexical_recall_context(...)`
- scope snapshot cache
- stable prefix cache
- prompt context body cache

这意味着：

- CoPaw 不是从零开始
- 它已经做到了“稳定前缀 + scope snapshot + recall”三段式

但和 `cc` 相比，目前还缺三样：

1. 风格壳还过于集中在大 system prompt 内
2. plan / review / resume / verify 没有显式前门模式层
3. 关键词纪律还没有正式化

## 3. CoPaw 的前门约束和 CC 不同

直接证据：

- `docs/superpowers/specs/2026-04-01-main-brain-single-loop-chat-design.md`
- `AGENTS.md`

CoPaw 当前明确要求：

- 只有一个聊天窗口
- 只有一个正式聊天前门：`POST /api/runtime-center/chat/run`
- 正式真相不能退回 session-first
- 主脑正式 side effects 仍由 kernel 提交

这决定了 CoPaw 不能复制：

- `cc` 的多产品壳
- `cc` 的远端 session-first planning product
- `cc` 的 local task list 直接上升为正式真相

---

## Design Options For CoPaw

## Option A: Only Tune Main-Brain Reply Style

做法：

- 只重写 `main_brain_chat_service.py` 的主脑聊天 system prompt
- 强化“短答、先结论、少解释、不反复问是否开始”
- 不新增关键词层，不新增 planning shell

优点：

- 改动最小
- 风险最低
- 能较快改善“像 cc 一样直接”

缺点：

- 只能改善回复味道，不能改善入口摩擦
- 用户说“帮我做个方案 / 帮我 review / 帮我继续上次”时，仍然缺少显式壳
- 很多纪律仍旧塞在一个大 prompt 里，可维护性一般

结论：

不够。

## Option B: 只做关键词层

做法：

- 增加 `plan / review / resume / verify` 等关键词解析
- 命中后直接给主脑一些 mode hint
- 不正式引入 planning shell artifact

优点：

- 入口体感会明显变轻
- 用户一句话切模式更方便

缺点：

- 如果没有对应 shell，关键词只会变成脆弱的 prompt patch
- 关键词会逐渐膨胀为第二套隐式真相
- 很容易退化成“命中词就换 prompt”的黑箱

结论：

风险偏高，不推荐单独做。

## Option C: Intent Shell + Planning Shell Sidecar + Reply Style Hardening

做法：

1. 强化主脑回复风格约束
2. 增加轻量 intent shell，只做 mode hint，不做第二判断模型
3. 把 planning / review / resume / verify 做成 sidecar shell，而不是第二套真相
4. 最终仍回落到 CoPaw 正式对象链

优点：

- 最接近 `cc` 的真实强项
- 能改善前门摩擦
- 不破坏 CoPaw 正式边界
- 后续可持续演进

缺点：

- 设计成本比只改 prompt 高
- 需要明确“shell artifact”和“formal truth”之间的边界

结论：

推荐。

---

## Recommended Direction

## 1. 回复风格：让主脑更像 cc，但不变成陪聊壳

建议不是把 CoPaw 改成“陪聊人格”，而是改成更低摩擦的正式主脑表达：

- 先结论，再理由，再下一步
- 默认短答
- 默认不反复问“是否开始”
- 当信息不足时，只追问最小缺口
- 遇到明确的执行/规划/复盘/验证意图时，直接切入对应 shell

这部分应直接落在：

- `src/copaw/kernel/main_brain_chat_service.py`

但要注意：

- 风格壳应该拆成“稳定前缀 + 动态 mode 尾部”
- 不要继续把所有表达纪律塞进单块大 prompt

## 2. 关键词层：要学 CC 的纪律，不要学成“关键词数据库”

建议增加一个轻量 `Intent Shell`，但规则必须严格：

### 强触发

仅对明确进入模式的表达触发，例如：

- `做个方案`
- `先规划一下`
- `帮我 review`
- `帮我审查`
- `继续上次`
- `恢复执行`
- `帮我验证`

### 弱触发

只在命令式、祈使式、句首场景触发，不在一般讨论句内乱触发。

### 明确排除

借 `cc` 思想，至少排除：

- 引号、反引号、代码块
- 路径、文件名、标识符
- 纯提问讨论该词本身的场景
- 前端只做提示，不做最终权威判断

### 核心原则

关键词层只产出：

- `mode_hint`
- `trigger_source`
- `candidate_scope`

绝不能直接写正式状态。

## 3. 规划壳：借 CC 的 shell discipline，不借它的 session-first truth

建议给 CoPaw 增加一个正式 sidecar planning shell，包含：

- planning draft
- affected files
- reuse anchors
- checklist
- acceptance criteria
- open questions
- verification plan

但它的定位必须明确：

- 这是前门交互壳
- 不是正式真相源
- 正式落地仍回到 `StrategyMemory / Lane / Backlog / Cycle / Assignment / Report`

换句话说：

- planning shell 是“表达与收敛壳”
- formal objects 才是“执行与治理真相”

## 4. review / verify / resume 也应走同一类 shell

推荐做成统一的前门模式层：

- `plan`
- `review`
- `resume`
- `verify`

共同特征：

- 只影响主脑 prompt 动态尾部和 sidecar artifact
- 不新增第二路模型判定
- 不新增第二路前端聊天窗口
- 不新增第二套任务真相

## 5. 不要复制的东西

明确不建议复制：

- `ultraplan` / `ultrareview` 的远端 CCR 产品壳
- billing / quota / overage / teleport 这类产品流程
- `cc` 的 session-first plan file 当最终真相
- `cc` 的任务列表直接替代 CoPaw 正式对象链
- 任何会让 CoPaw 重新长出“第二计划中心”的设计

---

## Proposed CoPaw Mapping

建议在 CoPaw 中形成如下边界：

## 1. Front-door shell objects

可以新增轻量 sidecar 对象，但必须明确定义为非正式真相，例如：

```python
class MainBrainIntentShellHint(BaseModel):
    mode_hint: Literal["none", "plan", "review", "resume", "verify"]
    trigger_source: Literal["none", "keyword", "explicit_phrase", "ui_action"]
    candidate_scope_ref: str | None = None
    confidence: float = 0.0
```

```python
class MainBrainPlanningShellDraft(BaseModel):
    summary: str = ""
    affected_files: list[str] = []
    reuse_anchors: list[str] = []
    checklist: list[str] = []
    acceptance_criteria: list[str] = []
    open_questions: list[str] = []
    verification_steps: list[str] = []
```

这些对象的作用：

- 帮主脑表达与收敛
- 帮前端可见化
- 帮 kernel 在正式提交前有结构化过渡层

这些对象的非作用：

- 不直接替代 `BacklogItem`
- 不直接替代 `Assignment`
- 不直接替代 `Report`

## 2. Formal truth landing

正式链条保持不变：

- `StrategyMemory`
- `OperatingLane`
- `BacklogItem`
- `OperatingCycle`
- `Assignment`
- `AgentReport`

sidecar shell 只能：

- 帮主脑收敛
- 帮 operator 看懂
- 帮 kernel 决定后续 formal commit

不能绕过正式对象写状态。

---

## Practical Implementation Order

如果进入实现阶段，建议按下面顺序落地：

## Phase 1: Reply Style Hardening

目标：

- 让主脑回复体感更像 `cc`
- 不改前门语义结构

落点：

- `src/copaw/kernel/main_brain_chat_service.py`

## Phase 2: Intent Shell Parser

目标：

- 为 `plan/review/resume/verify` 增加严谨触发层
- 不新增额外模型前判

建议新文件：

- `src/copaw/kernel/main_brain_intent_shell.py`

## Phase 3: Planning / Review Sidecar Shell

目标：

- 将 planning / review / verify 的结构化壳做成 sidecar artifact
- 前端同窗口可见

可能落点：

- `src/copaw/kernel/main_brain_chat_service.py`
- `src/copaw/app/runtime_chat_stream_events.py`
- `console/src/pages/Chat/*`

## Phase 4: Formal Mapping

目标：

- 把 shell 输出稳定映射到 CoPaw 正式对象链
- 不新增第二真相源

落点：

- kernel formal commit path
- state formal object services

---

## Final Position

这次调查后的最终判断是：

1. `cc` 的关键词体系没有想象中那么“大”，但它的关键词触发纪律是成熟的。
2. `cc` 真正值得借的是：
   - prompt 分段与缓存思路
   - attachment-based 模式提醒
   - planning shell discipline
   - task / verification discipline
3. `cc` 不值得直接搬的是：
   - remote CCR 产品壳
   - session-first truth
   - 本地 task list 顶替正式对象链
4. CoPaw 当前已经有比 `cc` 更高级的正式对象边界，下一步不该后退到“关键词即真相”，而应把 `cc` 的前门壳嫁接到 CoPaw 的正式对象链之上。

一句话收口：

**CoPaw 应该借 `cc` 的前门表达壳、触发纪律和 planning shell discipline，但正式真相必须继续收敛在 `StrategyMemory -> Lane -> Backlog -> Cycle -> Assignment -> Report`，不能退回 Claude 式 session-first planning center。**

## 11. 2026-04-02 实现落点

本轮在 `feature/main-brain-single-loop-chat` 上已经按上面的边界落了一版最小实现，具体形态如下：

- 新增 `src/copaw/kernel/main_brain_intent_shell.py`
  - 只做轻量 `mode_hint` 检测，当前覆盖 `plan / review / resume / verify`
  - 结果是 request-scoped advisory shell，不是正式对象
- `src/copaw/kernel/turn_executor.py`
  - 在单环主链里直接解析 shell hint
  - `plan / review` 默认留在 chat
  - `resume / verify` 只有在已有 continuity / confirmation 上下文时才会偏向 orchestrate
  - 不再因为这类前门 shell 触发额外 intake 判定
- `src/copaw/kernel/main_brain_chat_service.py`
  - 保留稳定主脑前缀
  - 增加动态 shell prompt tail
  - 让主脑在当前轮直接切入对应的 compact shell，而不是再做一轮人格化追问
- `src/copaw/app/runtime_chat_stream_events.py`
  - 不新增第二 transport
  - 通过 `turn_reply_done.payload.intent_shell` 输出同轮 advisory shell surface
- 前端同窗口接线
  - `runtimeSidecarEvents.ts` 解析 `intent_shell`
  - `ChatRuntimeSidebar.tsx` 增加 shell chip
  - `ChatIntentShellCard.tsx` 在当前聊天窗口中展示 shell card

当前实现仍然遵守本调查报告的主结论：

- shell 是前门表达壳，不是正式 truth
- shell 不写入 `main_brain_runtime_context`
- shell 不持久化为 `StrategyMemory / Lane / Backlog / Cycle / Assignment / Report`
- shell 只能帮助主脑更快进入更合适的前门表达结构
