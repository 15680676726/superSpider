# CoPaw 全面升级完整方案 v3.0

> **产品定位**：本地化部署，通用行业，客户输入行业信息后，系统自动生成多 Agent 运营团队并长期自主运营，越用越智能。
>
> **核心体验**：用户只做三件事——①首日录入行业信息 ②偶尔和管理Agent对话 ③看报告做决策。其他一切，系统自己干。
>
> ⚠️ **设计原则**：本方案全部用通用占位符描述（如"[行业X]""[岗位A]"），系统不预设任何行业，所有行业特定内容均由 AI 在运行时动态生成。文档中出现的具体行业仅作"示意说明"，不代表产品限定行业。

---

## 架构总览：前端 + 后端完整规划

```
前端（console/）                     后端（src/copaw/）
──────────────────────────────────────────────────────────
[行业初始化引导]          ←→    industry/ 新增模块
[指挥中心（主页）]        ←→    runtime_center/ 扩展
[管理Agent对话]           ←→    kernel/turn_executor
[Agent工作台]             ←→    agent_profile/ + capabilities/
[报告中心（日/周/月）]    ←→    reporting/ 新增模块
[绩效看板]                ←→    metrics/ 新增模块
[知识库管理]              ←→    knowledge/ 新增模块
[能力市场]                ←→    capability_market/ 新增模块
[运营日历]                ←→    scheduler/ 扩展
[运营治理中心]            ←→    runtime_center/decisions + patches
[系统设置]                ←→    config/ + industry/
```

---

## 系统内置双 Agent 设计（行业无关，所有客户默认拥有）

> 无论客户选择什么行业，系统默认内置且自动激活以下两个系统级 Agent。
> 其余业务岗位 Agent（[岗位A/B/C...]）由行业初始化时 AI 动态生成。

### Agent 一：管理 Agent（Manager）

| 项目 | 描述 |
|---|---|
| **角色定位** | 系统自治核心、人机交互唯一入口 |
| **默认状态** | 行业激活后**自动启动**，不需要人工确认 |
| **核心职责** | 接收用户指令 → 理解意图 → 拆解 → 委派给子 Agent → 汇总结果回传用户 |
| **附加职责** | 每日早间唤醒团队、分配当日任务；接收各 Agent 日报并汇总；检测 Agent 异常并调整分配 |
| **系统权限** | 可对任意子 Agent 发起委派；可读取全团队的 evidence 和 KPI |
| **停用限制** | **不可停用**（停用视同整个系统停止运营） |

### Agent 二：研究 Agent（Researcher）

| 项目 | 描述 |
|---|---|
| **角色定位** | 系统对外的"眼睛"，负责外部情报收集和内部知识传播 |
| **默认状态** | 默认安装，**首次启动需人工确认**（在 RuntimeCenter 审批） |
| **核心职责** | 定期搜索行业动态/竞品信息 → 提炼有效策略 → 写入共享知识库 → 主动推送给相关 Agent |
| **启动确认机制** | 首次启动生成 `DecisionRequest`（风险类型：`guarded`），用户审批通过后激活 |
| **关闭机制** | 用户可随时在 AgentWorkbench 手动暂停（`suspended` 状态），已积累知识不删除，重新开启后继续 |
| **知识写入权限** | 唯一拥有向共享知识库 `push` 内容的权限，其他 Agent 只读 |
| **需要的能力** | 网页搜索（必须）、网页抓取（可选）、文件写入（必须）|

### 双 Agent 协作架构

```
用户
  ↕（对话）
管理Agent（Manager）← 唯一和用户交互的入口
  ├── 委派 → [岗位A] Agent
  ├── 委派 → [岗位B] Agent
  ├── 委派 → [岗位C] Agent
  └── 读取 ← 研究Agent（Researcher）推送的知识

研究Agent（Researcher）← 独立运行，不接受用户直接指令
  ├── 搜索外部信息（行业动态/竞品策略）
  ├── 写入 → 共享知识库
  └── 推送 → 学习层（触发 Proposal，更新各 Agent 的 role_patch）
```

### 对应的数据模型补充

```python
class AgentRoleSpec(BaseModel):
    ...
    agent_class: str   # "system" | "business"
    # system = 内置，不可删除（manager / researcher）
    # business = 行业初始化时由 AI 动态生成
    
    activation_mode: str  # "auto" | "confirm"
    # auto   = 行业激活后立即启动（Manager）
    # confirm = 首次启动需人工通过 DecisionRequest（Researcher）
    
    suspendable: bool  # False=不可暂停（Manager）, True=可暂停（Researcher及所有业务Agent）
```

---

## 阶段一：学习飞轮打通（Week 1-2）🔴 最高优先级

**目标**：让"越用越智能"真正兑现，patch 对 Agent 行为有实际影响。

### 后端改动

#### 1.1 role_patch → system prompt 真实打通
**文件**：[src/copaw/kernel/query_execution.py](file:///d:/word/copaw/src/copaw/kernel/query_execution.py)

```python
# 组装 messages 时读取 AgentProfileOverrideRecord
profile_override = agent_profile_override_repo.get_by_agent_id(owner_agent_id)
if profile_override and profile_override.system_prompt_patch:
    system_prompt += "\n\n## 行业积累经验：\n" + profile_override.system_prompt_patch
```

#### 1.2 capability_patch → 工具选择真实影响
**文件**：[src/copaw/kernel/query_execution.py](file:///d:/word/copaw/src/copaw/kernel/query_execution.py)

构建工具列表时通过 `CapabilityService.list_capabilities(enabled_only=True)` 过滤，disabled 的工具不再注入 prompt。

#### 1.3 学习守护进程
**文件**：[src/copaw/app/_app.py](file:///d:/word/copaw/src/copaw/app/_app.py)

```python
async def _autonomous_daemon():
    while True:
        await asyncio.sleep(6 * 3600)
        await learning_service.run_strategy_cycle(auto_apply=True)
        await goal_service.dispatch_active_goals()
        await reporting_service.generate_pending_reports()
```

#### 1.4 重启后任务恢复
**文件**：[src/copaw/kernel/dispatcher.py](file:///d:/word/copaw/src/copaw/kernel/dispatcher.py)

启动时从 SQLite 恢复所有 `open/reviewing` 状态的 decision 到内存，避免进程重启导致待审批任务消失。

#### 1.5 RuntimeCenter 实时 SSE 推送
**文件**：[src/copaw/kernel/lifecycle.py](file:///d:/word/copaw/src/copaw/kernel/lifecycle.py) + 前端

任务状态转换时发布 push event，前端订阅后自动增量刷新，无需手动点刷新。

---

## 阶段二：行业化 + 自主运营启动（Week 3-6）🔴 高优先级

**目标**：任意行业的客户输入基础信息后，系统自动生成匹配的多 Agent 团队，立即开始自主运营。

### 后端新增模块：`src/copaw/industry/`

```
industry/
  models.py      # IndustryProfile, AgentRoleSpec
  generator.py   # 调用 LLM，根据行业信息动态生成团队结构和例行计划
  service.py     # 初始化、锁定、重置
  repository.py  # SQLite 存储
```

#### 核心数据模型（完全通用，无行业假设）

```python
class IndustryProfile(BaseModel):
    id: str
    name: str              # 由用户填写，如"[行业X]"
    company_name: str      # 由用户填写
    description: str       # 由用户填写，AI 根据此生成一切
    key_scenarios: list[str]  # AI 根据描述生成
    locked: bool = True

class AgentRoleSpec(BaseModel):
    id: str
    name: str              # AI 生成，如"[岗位A] Agent"
    role_type: str         # manager / operator / specialist
    responsibility: str    # AI 生成
    daily_tasks: list[str] # AI 生成
    weekly_tasks: list[str]
    kpis: list[str]        # AI 生成
    reports_to: str | None
    can_delegate_to: list[str]
    system_prompt_base: str      # AI 生成
    recommended_capabilities: list[str]  # AI 推荐该岗位需要的 skill/MCP
```

#### 行业生成器（`industry/generator.py`）

**LLM prompt 模板（完全通用）**：
```
你是一个企业运营顾问，擅长为任意行业设计 AI 团队架构。
用户公司信息：
  行业：{industry_name}
  公司名：{company_name}
  业务描述：{description}

请生成：
1. 该公司 5-8 个核心运营场景
2. 3-6 个 AI 岗位角色（含1个管理层），每个角色需要：
   - 名称、职责描述
   - 每日例行任务（3-5条）
   - KPI 指标（2-3条）
   - 汇报关系（谁管谁）
   - 该岗位执行任务所需的能力类型（如：搜索、文件处理、消息发送、数据分析）
3. 初始月度运营目标（1条根目标）

返回 JSON 格式，不要假设任何具体行业，完全基于用户描述推导。
```

#### 自主运营启动流程

用户确认 `IndustryProfile` 后，系统自动执行：
1. 为每个 `AgentRoleSpec` 创建 `AgentProfile` 记录（带 AI 生成的 system_prompt）
2. 为每个 Agent 的 `daily_tasks` 创建 `ScheduleRecord`（CronManager 注册）
3. 创建月度根 `Goal`，下挂各 Agent 子 Goal
4. 自主守护进程立即接管，无需人工干预

### 后端新增模块：`src/copaw/reporting/`

```
reporting/
  models.py      # Report（通用）：daily / weekly / monthly
  generator.py   # 从 evidence + metrics 聚合，调用 LLM 生成自然语言摘要
  service.py     # 按 agent / 按团队 / 按周期 生成和查询
  repository.py  # SQLite 存储
```

#### 报告 API

```
GET /api/reports/daily              # 今日团队报告
GET /api/reports/weekly             # 本周团队报告
GET /api/reports/monthly            # 本月团队报告
GET /api/reports/agent/{id}/daily   # 某 Agent 日报
GET /api/reports/agent/{id}/weekly  # 某 Agent 周报
GET /api/reports/kpi/{id}           # 某 Agent KPI 指标
```

### 前端新增页面

---

#### 【前端页面一】行业初始化引导 `Onboarding/`

**触发时机**：未锁定行业时全屏展示

```
Step 1/3  录入信息
  行业名称：[_______________]
  公司名称：[_______________]
  业务简介：[_______________（多行）]
  [下一步 →]

Step 2/3  AI 生成中（动画进度）
  · 分析业务场景...
  · 生成团队岗位结构...
  · 创建例行运营计划...
  · 推荐所需能力清单...

Step 3/3  确认团队方案
  系统生成的 Agent 团队：
  ├── [管理型] [岗位名] Agent —— [职责描述]
  ├── [专业型] [岗位名] Agent —— [职责描述]
  ├── [专业型] [岗位名] Agent —— [职责描述]
  └── ... （由 AI 动态生成，条数视行业而定）

  已创建的例行任务：
  · [时间] [任务描述] （[岗位名] Agent）
  · ...

  所需能力推荐（见"能力市场"，可稍后安装）：
  · [能力名] — [用途说明]

  [修改配置] [确认启动 →]
```

---

#### 【前端页面二】指挥中心 `CommandCenter/`（主页重设计）

```
┌──────────────────────────────────────────────────────────┐
│  🏢 [公司名]  运营第 N 天   整体健康度 ██░ XX%          │
├────────────┬─────────────────────────────────────────────┤
│  Agent状态  │  [岗位A] 🟢  [岗位B] 🟢  [岗位C] 🟡  ... │
│  今日总览   │  完成 N/M 任务  异常 K 项                  │
│             │                                            │
│  摘要       │  · [异常/进展 摘要条目，AI 自然语言生成]   │
│             │  · ...                                     │
├────────────┴─────────────────────────────────────────────┤
│  💬 和管理Agent说话：[________________]  [发送]          │
└──────────────────────────────────────────────────────────┘
```

> 注：所有 Agent 名称、任务描述均来自数据库动态渲染，不硬编码任何行业内容。

---

#### 【前端页面三】Agent 工作台 `AgentWorkbench/`

左侧：Agent 列表（由 DB 动态加载，条数不固定）
右侧：选中 Agent 的今日任务 + 执行日志 + KPI 进度 + 历史趋势

---

#### 【前端页面四】报告中心 `Reports/`

Tab：日报 / 周报 / 月报 / 年报

每份报告包含：
- AI 自然语言总结（基于 evidence + metrics）
- 各 Agent 完成情况数据表（动态列，由 Agent 数量决定）
- 异常事项列表
- 明日/下周计划（系统自动生成）
- 导出 PDF 按钮

---

#### 【前端页面五】绩效看板 `Performance/`

| Agent名称 | 任务完成 | 成功率 | SLA达标 | 异常率 | KPI达成 | 综合评分 |
|---|---|---|---|---|---|---|
| （来自DB，动态） | N | X% | X% | X% | ●●●○○ | A/B/C |

下方：成长轨迹折线图（第1周→第N周成功率变化）

---

#### 【前端页面六】管理 Agent 对话 `Chat/`（升级）

- 固定与"管理 Agent"对话（系统中 `role_type=manager` 的那个）
- 对话气泡内嵌套展示"委派给[岗位X] Agent"的动作和回传结果
- 支持自然语言指令："分析本周运营"、"告诉我[岗位A]状态"等

---

## 阶段三：知识库 + SOP（Week 7-9）

### 后端新增模块：`src/copaw/knowledge/`

```python
class KnowledgeChunk(BaseModel):
    id: str
    kind: str              # sop / reference / history / case
    title: str
    content: str
    industry_id: str
    role_affinity: list[str]   # 适用哪些 agent_role_id
    trigger_keywords: list[str]
    version: int = 1
```

**检索注入**：任务执行前，`KernelQueryExecutionService` 调用 `KnowledgeRetriever.search(task_title, role_id)` 取 Top-K 相关片段，附加到 system prompt。

任何行业的 SOP 文档均可导入（PDF/MD/TXT），无行业预设。

### 前端页面七：知识库管理 `Knowledge/`

```
分类导航：SOP 文件 / 参考资料 / 历史案例
文件列表：文件名、适用岗位（动态 Agent 列表）、状态、操作
[上传文档] → 选择文件 → 选择适用岗位 → 填写触发关键词 → 保存
```

---

## 阶段四：经营指标系统（Week 9-11）

### 后端新增模块：`src/copaw/metrics/`

通用指标（不依赖行业）：

| 指标 | 描述 |
|---|---|
| 任务完成率 | completed / total |
| SLA 达标率 | within_sla / total |
| 人工介入率 | human_reviewed / total |
| 异常率 | failed / total |
| Agent 负载均衡 | 各 Agent 任务分布 |
| 学习进化速度 | patches_applied / period |
| 综合评分 | 加权 A/B/C 级 |

指标计算逻辑全部从 `EvidenceLedger` + `TaskRepository` 聚合，不依赖行业特定字段。

---

## 阶段五：动态能力市场（Week 8-12）🔴 关键设计

**这是"真实业务集成"的正确解法：不预设固定 skill/MCP，而是建立动态能力发现和按需安装机制。**

### 设计原则

- 系统不假设任何行业需要哪些能力
- 行业初始化时，AI 根据业务描述**推荐**可能需要的能力（不强制）
- 用户可以在"能力市场"页面浏览、安装、卸载任何 skill/MCP
- 学习层在发现"Agent 因缺少某类能力而失败"时，主动推荐安装

### 后端新增模块：`src/copaw/capability_market/`

```
capability_market/
  models.py       # CapabilityPackage（能力包元数据）
  registry.py     # 本地能力包注册表（文件扫描 + 社区源）
  installer.py    # 安装/卸载逻辑（写入 config.json + 热重载）
  recommender.py  # 基于行业描述 + 失败记录推荐能力
  service.py      # 统一 API
```

#### 能力包元数据模型

```python
class CapabilityPackage(BaseModel):
    id: str               # 唯一标识，如 "smtp_email"
    name: str             # 显示名，如 "邮件发送"
    type: str             # skill / mcp
    description: str      # 用途描述
    applicable_roles: list[str]  # 适合哪类岗位（通用描述，非行业）
    config_schema: dict   # 安装时需要填写的配置项（如 SMTP 地址）
    install_source: str   # 本地路径 / MCP 服务地址 / 社区URL
    risk_level: str       # low / medium / high
    tags: list[str]       # ["通知", "文件", "搜索", "数据", "外部系统"]
```

#### AI 推荐机制

```python
async def recommend_for_industry(
    industry_description: str,
    agent_roles: list[AgentRoleSpec],
) -> list[CapabilityPackage]:
    """
    根据行业描述和 Agent 角色的能力需求，
    从能力注册表中匹配推荐最相关的能力包。
    不预设行业，纯基于描述语义匹配。
    """
```

#### 学习层发现缺口并主动推荐

```python
# 在 LearningService.run_strategy_cycle() 内
capability_gaps = await capability_market.detect_gaps(recent_failures)
if capability_gaps:
    await channel_manager.send_notification(
        f"💡 系统发现以下能力可能有助于减少失败：{capability_gaps}"
    )
```

#### 能力包 API

```
GET  /api/capability-market/list              # 所有可用能力包
GET  /api/capability-market/recommended       # AI 推荐列表
POST /api/capability-market/install           # 安装能力包
POST /api/capability-market/uninstall         # 卸载能力包
GET  /api/capability-market/installed         # 已安装列表
POST /api/capability-market/configure/{id}   # 更新配置
```

### 前端页面八：能力市场 `CapabilityMarket/`

```
┌──────────────────────────────────────────────────────────┐
│  🛒 能力市场                      [已安装(N)] [全部]      │
├─────────────┬────────────────────────────────────────────┤
│  标签筛选   │  ┌─────────┐ ┌─────────┐ ┌─────────┐      │
│  □ 通知     │  │📧 邮件发送│ │🔍 网页搜索│ │📊 数据分析│     │
│  □ 搜索     │  │ 发送/接收 │ │ 实时搜索  │ │ 聚合统计  │     │
│  □ 文件     │  │ 邮件通知  │ │          │ │          │     │
│  □ 数据     │  │ [已安装✅] │ │  [安装]  │ │  [安装]  │     │
│  □ 外部系统 │  └─────────┘ └─────────┘ └─────────┘      │
│  □ 消息推送 │                                            │
│             │  💡 AI推荐（基于您的业务描述）：            │
│             │  · [能力名] — [推荐原因]   [安装]           │
│             │  · ...                                     │
└─────────────┴────────────────────────────────────────────┘

点击"安装"后弹出配置对话框：
  [能力名] 安装配置
  服务地址：[____________]
  认证信息：[____________]（按需，由 config_schema 决定）
  [取消] [确认安装]
```

---

## 阶段六：多智能体自主协作（Week 12-16）

### 管理 Agent 统筹机制

`role_type=manager` 的 Agent 是系统自治核心，由守护进程每天触发：
1. 查看各子 Agent 待办，按优先级分配任务
2. 接收子 Agent 日报汇总为团队日报
3. 检测某 Agent 失败率异常，自动调整分配
4. 响应用户自然语言指令，分解并委派

### 后端改动

- `KernelDispatcher`：新增 `execute_task_batch` 支持并发执行
- 新增 `src/copaw/delegation/`：委派协议（管理Agent→子Agent→结果回传）
- `GoalRecord`：增加 `parent_goal_id` 字段，支持 Goal 树层级

---

## 阶段七：长期运营节奏（Week 14-18）

### 自动化运营时间表（由 CronManager 驱动，完全通用）

**每日**：
- 早间：管理 Agent 唤醒，生成当日任务分配方案
- 午间：各 Agent 上报进展
- 晚间：全团队日报自动生成
- 深夜：学习守护进程运行，分析当日 evidence

**每周**：
- 周始：上周周报 + 本周计划
- 周末：复盘，生成改进建议

**每月**：
- 月报 + 绩效评分 + 未达标 Agent 深度学习优化触发

### 前端页面九：运营日历 `Calendar/`

展示所有例行任务的时间分布（按 Agent 分色），支持手动添加/调整例行任务。

---

## 阶段八：运营治理面升级（Week 16-20）

现有 `RuntimeCenter` 扩展为专业治理面：

**新增功能**：
- 批量审批 Decision 队列
- 异常任务队列（重试 / 人工处理 / 忽略）
- 全操作审计日志（谁、何时、做了什么）
- Patch 管理（查看 / 应用 / 回滚）
- 灰度发布配置（高风险 patch 先小范围试行）

---

## 前端目录最终规划

```
console/src/pages/
  Onboarding/         ← 【新建】行业初始化引导
  CommandCenter/      ← 【新建】指挥中心主页
  Chat/               ← 【升级】管理Agent对话（含委派可视化）
  AgentWorkbench/     ← 【升级】含今日任务/执行日志/KPI
  Reports/            ← 【新建】日报/周报/月报/年报
  Performance/        ← 【新建】绩效看板+成长轨迹
  Knowledge/          ← 【新建】知识库和SOP管理
  CapabilityMarket/   ← 【新建】动态能力市场（安装/推荐）
  Calendar/           ← 【新建】运营日历
  RuntimeCenter/      ← 【升级】治理中心（批量审批/审计）
  Settings/           ← 【升级】行业设置/Agent管理/集成配置
```

---

## 总体时间规划

| 阶段 | 核心交付 | 周期 | 优先级 |
|---|---|---|---|
| 一 | 学习飞轮打通 | Week 1-2 | 🔴 |
| 二 | 行业初始化 + 多Agent自主运营 + 报告中心 | Week 3-6 | 🔴 |
| 三 | 知识库 + SOP | Week 7-9 | 🟡 |
| 四 | 经营指标系统 | Week 9-11 | 🟡 |
| 五 | 动态能力市场（核心业务集成入口） | Week 8-12 | 🟡 |
| 六 | 多Agent自主协作 | Week 12-16 | 🟡 |
| 七 | 长期运营节奏（日历/复盘） | Week 14-18 | 🟢 |
| 八 | 运营治理面升级 | Week 16-20 | 🟢 |

---

## 可测量交付标准

| 阶段 | 验收标准（行为可观测）|
|---|---|
| 一 | 同一 Agent 运行一周后，其 system prompt 包含学习积累的补丁内容 |
| 二 | 任意行业客户完成初始化后，5分钟内 N 个 Agent 开始自主执行例行任务 |
| 三 | 上传任意文档后，相关任务执行时 evidence 中出现文档引用片段 |
| 四 | 绩效看板展示各 Agent 任意时间段的完成率和综合评分 |
| 五 | 能力市场安装任意 skill/MCP 后，该能力立即可被 Agent 使用 |
| 六 | 管理 Agent 收到用户指令后，自动委派子任务并汇总回传结果 |
| 七 | 每日/周/月报告按时自动生成，无需人工触发 |
| 八 | 批量审批10条Decision，操作全部进入审计日志 |

---

## 补充设计规范（遗漏项）

---

### 补充一：管理 Agent 全权控制设计（核心交互原则）

> **核心原则：管理 Agent 是系统的唯一人机操控界面。**
> 用户可以通过对话让管理 Agent 执行系统中的任何操作。
> 需要确认的操作，管理 Agent 在对话中列出变更摘要，用户说"确认"即可执行，**不需要亲自去页面填写任何表单**。

#### 所有操作通过管理 Agent 执行的标准流程

```
用户（任意语言描述意图）
  ↓
管理Agent 解析意图 → 拟定操作方案 → 列出变更摘要给用户看
  ↓
用户："确认" / "修改第2条" / "取消"
  ↓（确认后）
管理Agent 调用对应系统 capability → 执行 → 回报结果
  ↓
EvidenceLedger 写入审计记录（谁说的、做了什么、何时）
```

**示例：**
```
用户："把库管改成售后"
管理Agent："好的，将做以下变更：
  · 名称：库管Agent → 售后Agent
  · 职责：建议更新为 [AI生成的售后职责描述]
  · KPI：建议更新为 [AI生成的售后KPI]
  · 库存相关例行任务将暂时移交管理Agent
  确认执行吗？"
用户："确认"
管理Agent 执行，完成后："已完成，售后Agent已激活。"
```

#### 管理 Agent 拥有的系统级 Capability 清单

| Capability ID | 描述 | 风险级别 | 确认方式 |
|---|---|---|---|
| `system:modify_agent` | 修改 Agent 属性（名称/职责/KPI） | guarded | 对话确认一次 |
| `system:create_agent` | 新增业务 Agent | guarded | 对话确认一次 |
| `system:delete_agent` | 删除业务 Agent | confirm | 对话强制确认 + 说出Agent名称 |
| `system:toggle_agent` | 暂停 / 启动任意 Agent | guarded | 对话确认一次 |
| `system:apply_patch` | 应用 / 回滚 learning patch | guarded | 对话确认一次 |
| `system:install_capability` | 安装能力包 | guarded | 对话确认（含配置项填写） |
| `system:uninstall_capability` | 卸载能力包 | guarded | 对话确认一次 |
| `system:generate_report` | 立即生成任意报告 | auto | 无需确认，直接执行 |
| `system:backup_data` | 触发数据备份 | auto | 无需确认 |
| `system:emergency_stop` | 紧急停止所有 Agent | auto | **无需确认，立即执行** |
| `system:resume_all` | 恢复紧急停止后的运营 | confirm | 对话确认一次 |
| `system:modify_schedule` | 修改例行任务时间/内容 | guarded | 对话确认一次 |
| `system:knowledge_write` | 向知识库写入内容 | auto | 无需确认 |
| `system:set_notification` | 配置通知渠道 | guarded | 对话确认一次 |
| `system:reset_industry` | 切换行业（重置） | confirm | 对话强制确认 + 说出"我确认重置" |

#### 风险级别说明

- **auto**：直接执行，事后写审计记录
- **guarded**：管理Agent列出变更摘要，用户说"确认"即执行
- **confirm**：高风险/不可逆操作，用户需要说特定确认词（如 Agent 名称、"我确认重置"）

#### 前端页面的角色重定义

**页面只负责"看"，不负责"做"。**

| 页面 | 功能 |
|---|---|
| 指挥中心 | 看团队状态、今日摘要（只读） |
| Agent工作台 | 看任务日志、KPI、成长轨迹（只读） |
| 报告中心 | 看日/周/月报、导出（只读） |
| 绩效看板 | 看指标数据（只读） |
| 知识库 | **上传文件**（唯一例外，文件上传仍走页面）|
| 能力市场 | 浏览能力包（安装指令通过管理Agent执行）|
| RuntimeCenter | 看审计日志、Decision 记录（只读） |
| Settings | 查看系统配置（只读，修改通过管理Agent）|

> **唯一例外**：文件上传（知识库文档、SOP 等）因为需要本地文件选择器，仍在页面操作。其余一切管理操作，均通过管理 Agent 对话执行。

#### 删除 Agent 的数据保留规则

- Agent Profile 标记 `deleted`，不物理删除
- 历史 Task / Evidence / 报告全部保留（审计和复盘用）
- 该 Agent 曾写入共享知识库的内容保留，转归管理Agent持有
- 关联 ScheduleRecord 自动停用

---

### 补充二：紧急停止机制（Emergency Stop）

**设计背景**：Agent 出现异常（如循环调用、意外操作外部系统），用户需要一键停止所有 Agent。

#### 触发方式

- **页面**：指挥中心顶部固定显示"⏹ 紧急停止"按钮（红色，始终可见）
- **管理Agent对话**：输入"停止所有Agent"/"紧急停止" → 立即执行（无需 DecisionRequest，例外情况）

#### 停止后状态

```
紧急停止触发
  → 所有 ScheduleRecord 状态变 paused
  → 所有运行中 Task 状态变 suspended（不是 failed）
  → 学习守护进程暂停
  → 系统保持当前状态，可随时恢复
  → EvidenceLedger 写入一条 system:emergency_stop 记录（含触发时间和原因）
```

#### 恢复

- 用户点击"▶ 恢复运营"，所有暂停的 Task/Schedule 恢复执行
- 管理Agent说"恢复运营" → 同样触发恢复流程（此次需要 DecisionRequest 确认）

---

### 补充三：Agent 健康检查

**设计背景**：某个 Agent 长期无响应、频繁失败、卡死，系统需要自动检测并处理。

#### 健康检查守护进程（集成在学习守护进程内）

每次运行时检查：
- Agent 最近 24 小时的任务成功率是否低于阈值（可配置，默认 50%）
- Agent 最近一次活动时间是否超过预期（失联检测）
- 是否有 Task 卡在 `executing` 状态超过 SLA

#### 处理策略

| 情况 | 自动处理 | 上报方式 |
|---|---|---|
| 成功率低于 50% | 触发深度学习周期 | 日报中标注 ⚠️ |
| 成功率低于 20% | 自动暂停该 Agent | DecisionRequest 通知用户 |
| 失联超 2 小时 | 发送告警 | 通知渠道推送 |
| Task 卡死超 SLA | 强制终止并标记失败 | 写入 EvidenceLedger |

---

### 补充四：数据备份与恢复

**设计背景**：本地化部署，客户数据只在本地，必须有可靠的备份机制。

#### 自动备份

```
每日 03:00 自动备份：
  state/phase1.sqlite3     → backups/state/YYYYMMDD.sqlite3
  evidence/phase1.sqlite3  → backups/evidence/YYYYMMDD.sqlite3
  config.json              → backups/config/YYYYMMDD.json
  knowledge/               → backups/knowledge/YYYYMMDD/

保留策略：每日备份保留 7 天，每周备份保留 4 周，每月备份保留 12 个月
```

#### 前端恢复入口

Settings 页面 → "数据管理" Tab：
- 查看备份列表（时间、大小、状态）
- 选择备份点 → 恢复（需输入确认码）
- 一键导出全量数据（ZIP 包）

#### 换行业（重置）时的数据归档

```
用户触发"切换行业/重置"：
  1. 当前所有数据打包归档到 archives/YYYYMMDD_[行业名]/
  2. 归档前生成一份"历史运营总结报告"（AI 生成）
  3. 清空 state，保留 archives 和 backups
  4. 进入初始化引导，开始新行业
```

---

### 补充五：用户通知渠道配置

**设计背景**：日报/周报/异常告警如何推送给用户，不能只有前端页面查看。

#### 支持的推送渠道（通过能力市场安装）

| 渠道 | 推送内容 |
|---|---|
| 系统内通知（默认）| 所有报告和告警，进入通知中心 |
| 邮件 | 日报/周报/月报 PDF 附件 |
| 企微 / 钉钉 / 飞书 Webhook | 异常告警、紧急通知 |
| 自定义 Webhook | 接入任意第三方系统 |

#### 配置入口

Settings → 通知格式配置：
- 每种事件类型可单独配置推送渠道（日报/周报/告警/Decision待审批）
- 可设置推送时间（如日报只在下班后发，告警实时发）

---

### 补充六：Agent 能力成长可视化

**设计背景**：用户应该看到"系统学了什么"，而不只是抽象的成功率提升。

#### 成长日志（每个 Agent 独立展示）

```
AgentWorkbench → [岗位A Agent] → "成长轨迹" Tab

2026-03-01  首次激活
2026-03-03  ✨ 经验积累：发现回复过长影响效率，已优化为简洁风格（role_patch #1）
2026-03-07  ✨ 能力禁用：[工具X]失败率 85%，已禁用，改用[工具Y]（capability_patch #1）
2026-03-10  📚 知识更新：研究Agent推送"[行业]最新方法"，已整合到知识库
2026-03-11  📈 成功率：本周 71% → 83%（+12%）
```

#### 系统级成长总览（绩效看板 → 成长Tab）

- 累计学习次数、生效 patch 数量
- 全团队成功率变化曲线
- 研究Agent累计推送知识条目数

---

### 补充七：Agent 冲突处理

**设计背景**：多 Agent 并发执行可能操作同一资源（如同时修改同一文档/配置）。

#### 冲突检测机制

- 每个 Task 执行前声明"资源占用锁"（resource_lock：文件路径/API端点/数据库表）
- 若另一 Task 请求相同资源，放入等待队列，当前 Task 完成后再执行
- 等待超过 SLA → 进入告警队列，由管理Agent决定处理方式

#### 冲突上报

管理Agent收到冲突报告后，可以：
- 取消低优先级 Task
- 调整执行顺序
- 通知用户决策

---

### 补充八：工作量自动均衡

**设计背景**：某个 Agent 任务过多可能质量下降，管理Agent需要动态调整。

#### 均衡规则（管理Agent执行）

- 每次分配任务时，查看各 Agent 当前待执行任务队列长度
- 若某 Agent 队列长度 > 阈值（可配置），将可转移的任务转给相同能力的其他 Agent
- 若无合适 Agent 接手，创建 DecisionRequest 询问用户是否新增 Agent

---

### 补充九：首次使用引导完善

行业初始化完成后，系统不能"静静等待"，需要主动引导用户完成第一步。

#### 引导流程

```
初始化完成后（Step 3/3 确认启动后）：

管理Agent主动发第一条消息：
  "您好！我是您的管理Agent，已经和团队准备好了。
   我已安排好今天的任务：[自动生成的今日计划摘要]
   
   以下是几件您可以现在做的事：
   ① 告诉我您最优先想解决的业务问题
   ② 上传您的业务文档/SOP到知识库
   ③ 在能力市场安装您需要的工具
   
   有什么需要我帮您安排的？"
```

#### 新手引导提示（前 3 天）

前 3 天，指挥中心顶部显示渐进式新手提示：
- 第一天："试试告诉管理Agent一个您关心的业务问题"
- 第二天："查看[报告中心]，看看昨天的运营日报"
- 第三天："去[能力市场]安装您需要的业务工具"

---

### 补充十：对话记忆（持续上下文）

**设计背景**：用户和管理Agent的对话不能"每次都从零开始"，需要记住历史。

#### 记忆层级

| 类型 | 存储位置 | 内容 |
|---|---|---|
| 会话记忆 | `MemoryManager`（已有） | 当次对话的上下文 |
| 跨会话摘要 | `AgentProfile.memory_summary` | 最近N次对话的要点摘要（AI压缩） |
| 长期事实 | 知识库（`kind=memory`）| 用户明确告知的偏好/决定/背景 |

#### 管理Agent每次对话开始时

1. 读取 `memory_summary` → 已知用户的当前关注点
2. 读取今日运营摘要 → 有什么值得主动报告的
3. 检查未处理的 DecisionRequest → 是否需要提醒用户

#### 用户可主动写入长期记忆

对话中说"记住：我们的回款周期是45天" → 管理Agent写入知识库（`kind=memory`），以后所有 Agent 执行任务时都能查到这个背景信息。

---

## 专业审查意见（Review v1.0）

> 以下是对当前方案的专业审查，包含发现的问题、修正建议和遗漏补充项。

---

### 问题一：阶段三、四、五时间线存在冲突

**现状**：
- 阶段三（知识库）：Week 7-9
- 阶段四（经营指标）：Week 9-11
- 阶段五（动态能力市场）：Week 8-12 ← **与阶段三/四重叠**

**问题**：阶段五的开始时间（Week 8）比阶段三还早开始，但阶段五依赖"行业初始化（阶段二）完成"，逻辑上正确；然而和阶段三四并行意味着团队需要同时推进三个模块，对小团队压力极大。

**修正建议**：
```
阶段三  知识库+SOP           Week 7-9
阶段四  动态能力市场          Week 8-11  （与阶段三小重叠，可以并行，知识库先行）
阶段五  经营指标系统          Week 10-12 （放在能力市场完成后，数据更完整）
阶段六  多Agent自主协作       Week 12-16
阶段七  长期运营节奏          Week 14-18
阶段八  运营治理面升级        Week 16-20
阶段九  打包部署+代码加固     Week 18-22 ← 补充
```

---

### 问题二：阶段二体量过大，存在交付风险

**现状**：阶段二（Week 3-6）包含了：
- 行业初始化引导（前端Onboarding）
- AI 动态生成 Agent 团队（后端 industry/）
- 自主运营启动机制
- 报告中心（reporting/ 模块）
- 5个新前端页面（Onboarding/CommandCenter/AgentWorkbench/Reports/Performance/Chat升级）

**问题**：6周内完成上述所有内容对于一个开发团队来说极为困难，且任何一项延误都会阻塞后续阶段。

**修正建议**：将阶段二拆分：
```
阶段二A（Week 3-4）：行业初始化 + Agent团队自动生成 + 指挥中心主页
阶段二B（Week 5-8）：自主运营启动机制 + 报告中心 + 绩效看板
```
这样至少有一个"可展示给客户的里程碑"在Week 4结束时出现。

---

### 问题三：阶段一缺少可见的用户体验验收

**现状**：阶段一的验收标准是"同一 Agent 运行一周后，其 system prompt 包含学习积累的补丁内容"——这是一个技术指标，用户看不见。

**问题**：学习飞轮打通是内部机制，如果第一阶段交付时用户没有可感知的变化，会感觉"做了两周什么都没变"。

**补充验收标准**：
- 用户运行体验：提问 Agent 时，回应内容比第一天更聚焦于自己的行业（而非通用回答）
- 前端成长轨迹 Tab 可见至少一条 patch 记录
- 守护进程日志可见"学习周期运行成功，已生成 N 个 proposal"

---

### 问题四：LLM 调用稳定性未覆盖

**现状**：所有核心流程（行业生成、报告生成、学习优化）都依赖 LLM 调用，但方案中没有任务调用失败的处理逻辑。

**问题**：
- LLM API 超时/限流/网络错误时，Agent 任务怎么办？
- 行业初始化时 AI 生成失败，用户看到什么？
- 日报生成超时，该任务是否重试？

**需要补充的设计**：
```python
class LLMCallGuard:
    max_retries: int = 3
    retry_delay_seconds: int = 5
    timeout_seconds: int = 60
    fallback_strategy: str  # "retry" | "degrade" | "human_fallback"
    # degrade = 使用简化版本（不调LLM，用模板生成）
    # human_fallback = 生成 DecisionRequest，让用户手动处理
```

---

### 问题五：缺少 API Key 配置引导（客户首次进入的前置步骤）

**现状**：方案的第一个前端页面是"行业初始化引导"，但要运行行业初始化，**必须先有可用的 LLM API Key**。

**问题**：新客户安装后，如果没有先配置 API Key，点"下一步"就会失败，体验极差。

**修正：Onboarding 应该是四步，而非三步**：

```
Step 0/4  API 配置（首次进入才显示）
  选择大模型服务商：[OpenAI ▼]
  API Key：[sk-xxx...]
  [验证连接]  → 成功后自动推断 embedding 模型
  [下一步 →]

Step 1/4  录入行业信息
Step 2/4  AI 生成运营方案
Step 3/4  确认并激活
```

---

### 问题六：记忆系统升级缺少具体实施方案

**现状**：补充十描述了记忆的三个层级，但没有说明如何实现"跨会话摘要"——这是当前代码没有的能力，需要在 `AgentProfile` 里新增 `memory_summary` 字段并在对话结束时触发压缩写入。

**需要补充的实施细节**：

```python
# 在 KernelTurnExecutor 对话轮结束时
async def _post_turn_memory_update(self, agent_id: str, recent_messages: list):
    if len(recent_messages) >= MEMORY_SUMMARY_TRIGGER_COUNT:
        summary = await memory_manager.compact_memory(recent_messages)
        await agent_profile_repo.update_memory_summary(agent_id, summary)
```

对应数据库变更：`AgentProfile` 表新增 `memory_summary TEXT` 字段。

---

### 问题七：验收标准缺少"端到端用户故事"视角

**现状**：验收标准全部是单点功能验证，缺少从用户角度的完整路径验证。

**建议补充关键用户故事验收标准**：

| 用户故事 | 验收标准 |
|---|---|
| 新客户安装当天可以开始用 | 安装→配置Key→初始化→5分钟内Agent开始工作，零代码操作 |
| 一个月后明显感觉"更懂我" | 第30天Agent回复与第1天相比，使用了至少3条学习积累的行业经验 |
| 出差时通过手机也能管 | 前端页面在移动端浏览器可正常查阅报告和与管理Agent对话 |
| 某Agent频繁失败时系统自处理 | 失败率超20%→自动暂停→通知用户→用户审批恢复，全程无需手动干预 |

---

## 遗漏补充项

---

### 补充十一：打包部署与代码加固（Week 18-22）

**当前状态**：项目使用 `pyproject.toml` + 命令行启动，普通客户无法安装使用。

**目标方案**：

```
技术选型：
  前端 → 在 pywebview 中内嵌（已有依赖）
  后端 → Nuitka 编译核心模块为 .pyd（代码加固）
  打包 → Python Embeddable + Inno Setup → .exe 安装包
  
加固范围（Nuitka 编译）：
  src/copaw/kernel/         ← 核心执行引擎
  src/copaw/learning/       ← 学习系统
  src/copaw/industry/       ← 行业生成器（商业核心）
  其余模块可保留 .py 便于客户自定义扩展
```

**客户安装体验目标**：
```
双击 CoPaw_Setup_v1.0.exe → 下一步/下一步/完成
桌面出现图标 → 双击 → 自动启动内嵌服务 → App 窗口弹出
首次进入 → API Key 配置引导 → 行业初始化引导 → 开始使用
```

**License 保护（可选后期）**：
- 激活码绑定机器码（CPU ID + 磁盘序列号）
- 首次启动联网验证，之后离线可用
- License 过期后降级为只读模式（可查报告，不能新建任务）

---

### 补充十二：移动端体验 → 利用已有渠道（飞书/钉钉/QQ）

**修正背景**：系统已集成飞书、钉钉、QQ、Discord、Telegram 等渠道，移动端需求已由这些渠道天然覆盖，不需要单独开发响应式网页或 PWA。

**各场景的移动端解决方案**：

| 场景 | 解决方案 | 现状 |
|---|---|---|
| 和管理Agent说话 | 直接在飞书/钉钉/QQ 发消息 | ✅ 已有渠道集成 |
| 收日报/告警通知 | 飞书/钉钉 Webhook 推送 | ✅ 补充五已覆盖 |
| 查详细报告数据 | 飞书消息卡片内嵌关键数据 | 🟡 需要优化消息格式 |

**真正需要做的工作**：

1. **飞书/钉钉消息卡片格式化**：日报不只推送纯文字，而是推送结构化卡片
   ```
   [今日运营日报 - 2026-03-11]
   ━━━━━━━━━━━━━━━━━━━
   ✅ 完成任务 24/27（88.9%）
   ⚠️ 异常 3 项（已处理 2 项）
   📈 本周成功率 ↑12%
   ━━━━━━━━━━━━━━━━━━━
   [查看完整报告] [处理异常]（卡片按钮）
   ```

2. **渠道指令识别增强**：用户在飞书里发"今天情况怎样"，管理Agent识别为"查询今日日报"并回复摘要（而不是让用户打开系统网页）

3. **网页端基础响应式**（低优先级）：报告中心和指挥中心做基础响应式布局，保证手机浏览器下可读，无需做 PWA。



---

### 补充十三：系统初始化前的最低能力验证

**背景**：系统启动时应检查是否具备最基础的运行条件。

```python
# _app.py 启动时执行
async def _startup_check():
    checks = [
        ("LLM API 连接", _check_llm_connection),
        ("数据库可写", _check_db_writable),
        ("必要目录存在", _check_required_dirs),
        ("网络基础连通", _check_network),
    ]
    failed = []
    for name, check_fn in checks:
        if not await check_fn():
            failed.append(name)
    
    if failed:
        # 前端展示启动检查失败的提示，引导用户修复
        await console_push_store.push_event("startup_check_failed", {"items": failed})
```

前端在 `App.tsx` 入口拦截：若存在启动失败项，展示"系统自检失败"引导页而非直接进入。

---

### 补充十四：多 LLM 服务商支持与自动降级

**背景**：客户可能使用不同服务商（OpenAI / DashScope / 本地 Ollama），或主力服务商出现故障时需要自动降级。

```python
class LLMFallbackChain:
    providers: list[str]  # 按优先级排列，如 ["openai", "dashscope", "ollama"]
    
    async def call(self, prompt, **kwargs):
        for provider in self.providers:
            try:
                return await self._call_provider(provider, prompt, **kwargs)
            except (APIError, TimeoutError):
                continue
        raise AllProvidersFailedError("所有 LLM 服务商均不可用")
```

前端 Settings → "模型配置" 支持配置多个服务商作为备用。

---

## 阶段九：分布式智能预测系统（Week 20-24）

> **设计原则**：系统不预设任何行业，所有预测维度完全从用户当前的 Agent 团队动态读取，适用于任意行业。

### 背景与定位

**为什么不直接用 MiroFish**：
- MiroFish 用千个虚拟角色仿真宏观社会事件（AGPL-3.0 License，商用需开源）
- 我们的场景是**企业内部运营决策**，有真实历史数据，比仿真准确得多
- MiroFish 没有执行闭环，我们预测完可以直接转执行

**核心差异**：MiroFish 是"没有数据靠仿真"，我们是"有真实数据靠分析"，越用越准。

---

### 预测数据来源架构（三层）

```
                         预测议题
                    （用户的"如果..."问题）
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                  ▼
   【内部历史层】     【岗位专家层】      【外部情报层】
   EvidenceLedger    各业务 Agent        研究 Agent
   ─────────────    ──────────────      ─────────────
   历史任务数据      各领域专业判断      实时外部搜索：
   过往决策结果      基于自身承载能力    · 行业基准数据
   KPI 趋势积累      给出本岗位预判      · 外部风险信号
                                        · 同类事件案例
                                        · 政策/市场变化
         └─────────────────┼─────────────────┘
                           ▼
                  管理 Agent 综合汇总
               → 多场景预测报告 + 行动建议
```

---

### 预测执行流程（通用，不限行业）

```python
# 伪代码展示核心流程
async def run_prediction(query: str, user_hypothesis: str):
    """
    query: 预测议题（如"如果[事件X]发生，会怎样？"）
    不预设任何行业，从当前 Agent 团队动态构建预测维度
    """
    # 1. 管理 Agent 发起预测任务
    agents = await agent_repo.list_active_business_agents()
    
    # 2. 各岗位 Agent 从自身角度提供预判
    domain_predictions = await asyncio.gather(*[
        agent.predict_impact(query) for agent in agents
    ])
    
    # 3. 研究 Agent 提供外部情报
    external_intelligence = await researcher_agent.search_relevant_data(query)
    
    # 4. 从 EvidenceLedger 提取历史参照
    historical_cases = await evidence_ledger.find_similar_scenarios(query)
    
    # 5. 管理 Agent 综合推演
    report = await manager_agent.synthesize_prediction(
        hypothesis=user_hypothesis,
        domain_predictions=domain_predictions,
        external_data=external_intelligence,
        historical_cases=historical_cases,
    )
    
    # 6. 生成行动建议，可直接转为委派任务
    return PredictionReport(
        scenarios=report.scenarios,        # 乐观/中性/悲观三个场景
        risk_points=report.risk_points,    # 识别到的风险点
        action_checklist=report.actions,   # 各 Agent 需要提前做的事
        confidence_score=report.confidence # 预测置信度（基于历史数据量）
    )
```

---

### 主动触发与节流防抖机制（解决"主动寻优与成本控制"痛点）

为了让系统具备"主动探寻最优解"的能力，同时避免大模型 API Token 被频繁无意义消耗，系统采用**事件驱动 + 冷却预算**的双层治理机制。

#### 1. 触发源（何时启动主动预演/寻优）

| 触发源 | 判定条件 | 核心作用 |
|---|---|---|
| **指标异动（内源）** | 某关键 KPI 连续 3 天未达标，或单日出现 >30% 断崖跌幅 | 业务指标（如转化/留存）恶化时，主动归因并寻优 |
| **任务重度失败（内源）** | 某业务 Agent 处理同类任务连续失败 3 次以上 | 常规执行遇阻，需整体审视并重写 SOP 或寻找新工具 |
| **重大情报（外源）** | 研究 Agent 巡检发现高权重外部信号（政策变动/竞品大促） | 预防性推演，预估外部变化对当前业务团队的冲击并防守 |
| **周期盘点（定时）** | 每月第 1 天或每季度末的例行时刻 | 全局复盘，在无异常时主动寻找下一个效能提升空间 |

#### 2. 冷却与预算控制（防抖节流系统）

如果不加控制，一旦 KPI 下降或异常浮现，系统可能每天连续触发高成本的全量推演。为保障商业可行性，必须引入节流闸门：

- **议题冷却期（Cooldown）**：
  针对同一问题（如"电商转化率降低"或"研究院课题卡壳"），一旦完成预演并下发了修正策略，该议题自动进入冷却期（如 7-14 天）。冷却期内即便指标尚未恢复，也**绝不重复触发高消耗推演**，必须等待策略起效。
- **置信度水位闸门（Data Cap）**：
  在启动消耗算力的深研前，管理 Agent 需先查验 `EvidenceLedger` 的历史数据量与外部情报质量。若数据严重匮乏，系统将拒绝强行"凭空猜测"，转而生成一个廉价的「强化数据收集」基础任务下发给相关 Agent。
- **算力预算账本（Token Budget）**：
  在 Settings 中可配置"自主推演额度"（如每周最多 2 次深研，或限制最高 Token 消耗额）。
  - **额度内**：自主察觉异常 → 触发推演 → 输出报告 → 自动下发应对策略。
  - **超额度**：系统拦截底层调用，改为向用户推送 `DecisionRequest` 询单："检测到转化率异常预警，但本周自动深研额度已耗尽，是否人工授权额外发起 1 次全局推演？"

---

### 预测准确率回馈闭环

**预测发出后，记录实际结果，形成学习数据**：

```
预测发出 → 记录 PredictionRecord（议题 + 预测场景 + 置信度）
     ↓
实际执行（各 Agent 按建议执行任务）
     ↓（一段时间后）
管理 Agent 自动对比：预测 vs 实际结果
     ↓
生成准确率评分（每个岗位 Agent 的预测偏差）
     ↓
送回学习层（LearningService）：
  · 预测偏差大的维度 → 触发该 Agent 的学习优化
  · 外部数据命中率 → 优化研究 Agent 的搜索策略
  · 历史案例匹配质量 → 优化 EvidenceLedger 检索算法
```

**效果**：系统运行时间越长，积累的预测-实际对比数据越多，预测置信度越高。

---

### 核心数据模型

```python
class PredictionRecord(BaseModel):
    id: str
    created_at: datetime
    industry_id: str
    hypothesis: str              # 用户的假设场景
    
    domain_inputs: list[dict]    # 各岗位 Agent 的预判输入
    external_inputs: list[dict]  # 研究 Agent 的外部情报
    historical_refs: list[str]   # 引用的历史案例 ID
    
    scenarios: list[PredictionScenario]  # 乐观/中性/悲观
    action_checklist: list[str]  # 建议行动
    confidence_score: float      # 0-1，基于数据量计算
    
    # 回馈字段（事后填写）
    actual_outcome: str | None   # 实际发生了什么
    accuracy_score: float | None # 预测准确率评分
    feedback_processed: bool = False  # 是否已送回学习层


class PredictionScenario(BaseModel):
    label: str               # "乐观" / "中性" / "悲观"
    probability: float       # 发生概率（基于历史数据）
    key_drivers: list[str]   # 主要驱动因素
    agent_impacts: dict      # 各岗位 Agent 预期承压情况
    risk_triggers: list[str] # 可能触发此场景的关键信号
```

---

### 前端页面 1：预测中心 `Predictions/`（结果消费端）

**定位**：用于查看历史预警、查阅大盘推演报告。
*(注意：不在此页设计输入框，所有的手动预测发起，统一通过总聊天页向管理Agent发送配置好的“触发关键词”进行。)*

```
┌──────────────────────────────────────────────────────────┐
│  🔮 预测中心                             [查看触发说明] │
├──────────────────────────────────────────────────────────┤
│  💡 主动预警（研究Agent发现）                             │
│  ⚠️ [今日 09:23] [外部信号描述] → 影响评估：高          │
│     受影响环节：[岗位A] [岗位B]    [查看详情] [立即应对]  │
├──────────────────────────────────────────────────────────┤
│  📊 预测历史                          准确率：██████ 78% │
│  2026-03-10  [议题描述]  已验证 ✅  预测准确率 85%       │
└──────────────────────────────────────────────────────────┘
```

**触发说明**：用户在总管理聊天框输入预设的关键词（默认如：“分析预测：” 或 “推演：”），管理 Agent 自动拉起推演引擎。当前相关入口统一收敛到 `Predictions/`。

---

### 前端页面 2：主动寻优控制台 `Predictions/`（触发与结果可见化端）

**定位**：将主动预测的触发、预算和冷却层彻底独立出来，作为系统的“大脑皮层设置页”，防止算力被黑盒消耗。

```
┌──────────────────────────────────────────────────────────┐
│  🧠 主动寻优控制台 (Predictions)                         │
├──────────────────────────────────────────────────────────┤
│  🟢 寻优引擎状态：[运行中]     本周可用 Token：150k / 500k │
├──────────────────────────────────────────────────────────┤
│  触发源配置                                               │
│  [☑️] 内源异动：当 KPI 连续 [3] 天下降 > [15]% 时触发   │
│  [☑️] 任务阻断：当同一类型任务连续失败 [3] 次时触发       │
│  [☑️] 外部情报：当研究Agent发现 [高] 风险外部情报时触发   │
│  [☑️] 周期盘点：每月第 [1] 天自动发起一次全局扫描         │
├──────────────────────────────────────────────────────────┤
│  防抖与节流控制（Cost Control）                           │
│  · 全局预算限制：每周推演最多消耗 [ 500k ] Token          │
│  · 议题冷却期：同一问题推演后冷却 [ 14 ] 天，期间不再触发 │
│  · 数据安全区：历史参考数据量低于 [ 50 ] 条时拒绝深研     │
├──────────────────────────────────────────────────────────┤
│  拦截日志 (Blocked Runs)                                  │
│  🚫 03-11 [内源异动] 转化率下跌拦截 → 原因：处于冷却期中  │
│  🚫 03-09 [周期盘点] 例行扫描拦截   → 原因：Token预算不足 │
└──────────────────────────────────────────────────────────┘
```

---

### 前端目录（补充更新）

```
console/src/pages/
  Predictions/        ← 【新建】预测中心（看报告、看预警、手动发起推演）
  Predictions/        ← 【新建】预测与主动寻优结果页（查看周期预测、建议队列与治理状态）
  ...（其余同前文规划）
```

---

### 总结：为什么这套预测系统比 MiroFish 更适合

| 维度 | MiroFish | 本系统 SimAgent |
|---|---|---|
| 数据来源 | 外部种子（无历史积累）| 真实 Evidence（越用越准）|
| 推演方式 | 千个虚拟角色仿真 | 真实岗位 Agent + 历史分析 |
| 行业适配 | 通用宏观事件 | 自适应任意行业（动态 Agent）|
| 外部情报 | 需要额外配置 | 研究 Agent 实时提供 |
| 执行闭环 | ❌ 只出报告 | ✅ 预测→决策→委派→执行→验证 |
| 部署依赖 | 需独立部署 + Zep Cloud | 内置，零额外依赖 |
| License | AGPL-3.0（商用受限）| 自研，无限制 |
| 准确率提升 | 静态 | 回馈学习，持续改进 |
