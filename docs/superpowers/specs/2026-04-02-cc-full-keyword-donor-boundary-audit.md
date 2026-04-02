# 2026-04-02 CC 全量关键词实现与 CoPaw Donor Boundary 审计

## 1. 目标

这份审计只回答三个问题：

1. `cc` 真实实现了哪些“关键词 / shell / 显式状态”。
2. 这些能力里，哪些值得放进 CoPaw。
3. 哪些不该继续扩，避免在 CoPaw 里画蛇添足。

证据优先级：

1. 真实源码与真实调用路径
2. 测试与内联注释
3. 文档只作旁证

---

## 2. 先给结论

`cc` 的强点不是“大词库”。

`cc` 真正成熟的是四件事：

1. 窄而严格的关键词触发纪律
2. 显式 mode shell
3. attachment / prompt section 驱动的工作流提醒
4. plan / review 相关的明确状态推进

对 CoPaw 的结论也很直接：

- 应该补的是“前门表达壳”和“模式纪律”
- 不该补的是“第二套 planning truth”
- 不该把 `cc` 的远端产品壳、session-first plan file、remote task shell 搬进主链

CoPaw 的正式真相仍然必须收敛到：

`StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport`

对应依据：

- `DATA_MODEL_DRAFT.md`
- `TASK_STATUS.md`
- `AGENTS.md`
- `API_TRANSITION_MAP.md`

---

## 3. CC 真实实现了哪些关键词

### 3.1 自动关键词并不多

当前能在源码里直接确认的自动关键词实现，核心只有两类：

- `ultraplan`
- `ultrareview`

关键证据：

- `cc/src/utils/ultraplan/keyword.ts`
- `cc/src/utils/processUserInput/processUserInput.ts`
- `cc/src/components/PromptInput/PromptInput.tsx`

其中真正会改写请求并自动路由的，当前已确认只有 `ultraplan`。

`processUserInput.ts` 的真实路径是：

- 只在 interactive prompt mode 生效
- 只在非 slash 输入时生效
- 命中后把自然语言里的 `ultraplan` 改写成 `plan`
- 然后内部转成 `/ultraplan ...`

这说明：

- `cc` 不是“看到很多关键词就自动切模式”
- 它是对极少数关键词做强纪律自动路由

### 3.2 `ultrareview` 不是同级别自动路由

当前核查范围内可以确认：

- `PromptInput.tsx` 会高亮 `ultrareview`
- UI 会提示用户之后可以运行 `/ultrareview`
- `review.ts` 明确把 `/review` 和 `/ultrareview` 分开

但没有看到与 `ultraplan` 对等的“自然语言命中后自动路由 `/ultrareview`”路径。

这点很重要，因为很多人会误以为 `cc` 有一整套庞大的自然语言关键词编排系统。当前源码证据不支持这个说法。

---

## 4. CC 的关键词纪律到底强在哪

核心文件：

- `cc/src/utils/ultraplan/keyword.ts`

它做的不是简单 `contains(keyword)`，而是明确规避误触发：

- 引号、反引号、尖括号、花括号、方括号、括号里的内容不触发
- 路径、文件名、标识符上下文不触发
- `?` 问句场景不触发
- slash command 场景不触发

换句话说，`cc` 的价值在于：

- 关键词数量少
- 但误触发控制做得细

对 CoPaw 的启发是：

- 应该继续提升触发纪律
- 不应该先扩词库

如果纪律不够，词越多，误判越多，最后用户只会觉得主脑变笨。

---

## 5. CC 的 shell discipline 真实长什么样

核心文件：

- `cc/src/tools/EnterPlanModeTool/prompt.ts`
- `cc/src/tools/EnterPlanModeTool/EnterPlanModeTool.ts`
- `cc/src/utils/messages.ts`
- `cc/src/utils/planModeV2.ts`
- `cc/src/commands/plan/plan.tsx`

`cc` 的 planning shell 不是“模型自己悟出来”的。

它是被明确约束出来的：

- 显式进入 `plan mode`
- plan mode 下只允许读代码、写 plan file、问用户、最后 exit
- 有 full / sparse reminder
- 有 interview workflow 与 5-phase workflow
- 有 `AskUserQuestion` / `ExitPlanMode` 这类明确状态推进工具
- plan file 是这个 shell 的外部落点

这说明 `cc` 的 planning 能力，本质上是“workflow shell + attachment + tool contract”的产物，不是关键词本身。

---

## 6. CC 的显式状态是什么，不是什么

真实可以确认的显式状态主要集中在：

- `plan mode`
- `plan_mode` attachment 及其 reentry / exit 节律
- `ultraplan` 本地到远端 CCR 的 launch / polling / approved / failed / pending-choice 状态
- `/review` 与 `/ultrareview` 的本地 / 远端分流

关键证据：

- `cc/src/utils/messages.ts`
- `cc/src/commands/ultraplan.tsx`
- `cc/src/utils/ultraplan/ccrSession.ts`
- `cc/src/commands/review.ts`
- `cc/src/commands/review/reviewRemote.ts`
- `cc/src/state/AppStateStore.ts`

但要分清：

- `plan mode` 是本地 planning shell
- `ultraplan` / `ultrareview` 很大一部分是远端产品壳

这两者不能混成“统一关键词体系”。

---

## 7. CC 的 prompt 结构为什么稳定

核心文件：

- `cc/src/constants/prompts.ts`
- `cc/src/constants/systemPromptSections.ts`

可以直接确认三件事：

1. system prompt 是分 section 组装的
2. section 有缓存
3. 只有少量 section 被标记为 cache-break

所以 `cc` 的 prompt 不是每轮粗暴重建，而是：

- 静态段稳定缓存
- 动态段局部刷新
- attachment 再补充模式信息

这部分适合 CoPaw 借，而且我们当前单环主脑已经开始这么做：

- 稳定前缀
- 动态尾部
- scope snapshot cache
- sidecar shell

---

## 8. CoPaw 现在哪些地方确实要优化

### 8.1 要继续优化：触发纪律

当前 CoPaw 的 `main_brain_intent_shell.py` 已经有第一版：

- `plan`
- `review`
- `resume`
- `verify`

但相比 `cc/src/utils/ultraplan/keyword.ts`，纪律还不够细。

当前最值得补的不是新词，而是这些规则：

- 引号 / 代码块 / 路径 / 文件名 / 赋值语句规避再细化
- 中文触发短语分层，避免普通叙述误中
- slash hint、显式 `mode_hint`、自然语言命中三者优先级固定

### 8.2 要继续优化：shell discipline

当前 CoPaw 已有：

- `plan / review / resume / verify` advisory shell
- dynamic prompt tail
- same-window sidecar display

还值得增强的，是 shell 输出的纪律，不是状态数量：

- `plan` 必须稳定包含目标、约束、影响范围、checklist、验收、验证
- `review` 必须稳定包含结论、发现、严重级、风险、缺口、下一步
- `resume` 必须稳定包含当前状态、连续性锚点、阻塞、下一动作
- `verify` 必须稳定包含验证对象、证据、pass/fail、残余风险、下一步

### 8.3 值得优化，但要严格控边界：显式状态

CoPaw 现在还是当前轮 advisory shell，不是完整状态机。

后续可以考虑补一层轻量显式状态，但只能是 sidecar shell state，例如：

- `shell_state = active / awaiting_confirmation / awaiting_continuity / done`
- 前端刷新可恢复
- 只服务聊天表达与人机协作

不能让它变成新的正式 planning center。

---

## 9. CoPaw 现在不需要扩什么

### 9.1 不要扩大词库

现在最不该做的是：

- 继续加几十个关键词
- 让主脑看到一些常见词就切模式
- 把“帮我看看 / 帮我弄下 / 帮我继续”都当强触发

原因：

- `cc` 的真实价值不是词多
- CoPaw 当前风险是误触发，不是词不够
- 主脑正式对象链比关键词层更重要

### 9.2 不要把 shell artifact 正式落库为第二套 truth

不该新增：

- session-first plan file 作为正式计划真相
- 本地 todo / checklist 替代 backlog / cycle / assignment
- review shell 摘要替代 `AgentReport`

这会直接违反 CoPaw 当前蓝图：

- 单一真相源
- 单一运行主链
- 前门正式写链进入 `MainBrainOrchestrator -> Backlog / Assignment / Report`

### 9.3 不要搬 CC 的远端产品壳

不建议照搬：

- `ultraplan` 远端 CCR 会话
- `ultrareview` 远端 bughunter product shell
- remote polling / remote task / session URL 那整套产品行为

这些属于 donor 的产品壳，不是 CoPaw 主链资产。

---

## 10. 对 CoPaw 的准确建议

### 10.1 现在应该做

1. 强化 `main_brain_intent_shell.py` 的误触发规避
2. 把 4 个 shell 的回复结构再收紧
3. 如果要加显式状态，只加 sidecar 级、同窗口可见、可恢复的轻量状态

### 10.2 可以做，但不是现在第一优先级

1. 给 shell 增加更细的 alias，但必须一条条加测试
2. 给 `resume / verify` 增加更稳定的 continuity gating
3. 给前端补更清晰的 shell stage 可见化

### 10.3 现在明确不要做

1. 复制 `cc` 的大 command surface
2. 引入 session-first planning center
3. 把 plan shell artifact 写成正式对象
4. 搬运 `ultraplan` / `ultrareview` 远端产品流

---

## 11. 最终判断

从源码证据看，CoPaw 下一步不该朝“更大的关键词系统”走。

更正确的方向是：

- 继续保持正式对象链比 donor 更高级
- 只借 `cc` 的前门壳纪律
- 用更严格的触发规则、更稳定的 shell 输出、以及轻量显式 sidecar state，降低前门表达成本

一句话收口：

**CoPaw 应该借 `cc` 的窄关键词纪律、显式 shell、prompt section 缓存思路；不应该借它的远端产品壳、session-first plan truth、也不应该盲目扩关键词。**
