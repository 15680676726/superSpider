# V7 — 社区模板共享层

## 版本目标

将个人经验转化为社区资产，构建网络效应护城河。用户跑通的行业方案可脱敏后发布到社区，其他用户一键复用，形成"方案越多→成功率越高→用户越多"的飞轮。

## 产品定位差异化

| 维度 | 悟空（阿里） | QClaw（腾讯） | Spider Mesh V7 |
|------|-------------|--------------|----------------|
| 定位 | 企业办公自动化 | 通用桌面操控 | AI创业合伙人 |
| 入口 | 钉钉 | 微信/QQ | 独立产品 |
| 用户画像 | 已有明确任务的企业员工 | 已有明确指令的C端用户 | 不知道做什么的创业者/个人 |
| 核心价值 | 帮你做 | 帮你操作 | 帮你想清楚+帮你做+帮你复盘 |
| 壁垒 | 生态绑定 | 生态绑定 | 社区沉淀的行业方案 |

## Slogan

> "不知道做什么？告诉我你的想法，剩下的交给我。"

创建团队后消失，替换为运行状态概览。

## 核心功能模块

### 7.1 方案脱敏导出

用户跑通一个行业方案后，可将其导出为可分享模板：

- 自动脱敏：移除个人信息、API密钥、具体账号、业务数据
- 保留结构：团队角色蓝图、目标拆解、计划步骤、workflow模板、capability依赖清单
- 保留肌肉记忆骨架：操作流程步骤（脱敏后），不含具体业务数据
- 用户可手动编辑导出内容，选择性隐藏敏感步骤
- 导出格式：JSON + 可读摘要

### 7.2 社区模板市场（Template Hub）

基于现有 CapabilityMarket 和 WorkflowTemplates 架构扩展：

- 发布：用户上传脱敏方案，填写行业标签、适用场景、预期效果
- 发现：按行业分类浏览、搜索、热门排行、最新发布
- 评价：使用者评分（1-5星）+ 文字评价 + 成功率统计
- 版本：方案作者可迭代更新，使用者可选择版本
- 依赖检查：复用前自动检测所需capability是否已安装

### 7.3 一键复用

- 用户选择社区模板后，进入 Industry 页面的 preview 流程
- 模板预填 draft 表单（角色、目标、计划、capability）
- 用户可在此基础上调整后 bootstrap
- 复用记录关联原模板，形成使用链路追踪

### 7.4 成功案例展示

- 匿名展示已跑通方案的关键指标：运行时长、任务完成率、复盘评分
- 作者可选择公开部分复盘摘要作为案例背书
- 按行业聚合展示"这个行业已有N人成功启动"

### 7.5 贡献激励

- 方案被复用次数、评分、成功率作为作者积分
- 积分可兑换高级功能（更多agent并发、更大模型预算等）
- 排行榜展示优质贡献者

## 技术方案

### 数据模型扩展

```
CommunityTemplate {
  template_id: string
  author_id: string (脱敏显示)
  industry_tags: string[]
  title: string
  summary: string
  version: number

  // 方案内容
  team_blueprint: IndustryDraftPlan (脱敏)
  workflow_templates: WorkflowTemplate[]
  capability_dependencies: string[]
  muscle_memory_skeletons: MemorySkeleton[]

  // 统计
  use_count: number
  avg_rating: number
  success_rate: number

  created_at: timestamp
  updated_at: timestamp
}

TemplateReview {
  review_id: string
  template_id: string
  user_id: string
  rating: number (1-5)
  comment: string
  outcome: "success" | "partial" | "failed" | "in_progress"
  created_at: timestamp
}
```

### 前端页面

| 页面 | 路由 | 说明 |
|------|------|------|
| 社区市场 | /community | 浏览、搜索、筛选社区模板 |
| 模板详情 | /community/:id | 查看方案详情、评价、使用 |
| 我的发布 | /community/mine | 管理已发布的模板 |
| 发布向导 | /community/publish | 脱敏预览→编辑→发布 |

### API 端点

```
GET    /api/community/templates          — 列表/搜索
GET    /api/community/templates/:id      — 详情
POST   /api/community/templates          — 发布
PUT    /api/community/templates/:id      — 更新
DELETE /api/community/templates/:id      — 下架
POST   /api/community/templates/:id/use  — 复用（返回预填draft）
GET    /api/community/templates/:id/reviews — 评价列表
POST   /api/community/templates/:id/reviews — 提交评价
GET    /api/community/rankings           — 排行榜
POST   /api/industry/export-template     — 从现有实例导出脱敏模板
```

### 架构复用

- 社区市场页面复用 CapabilityMarket 的卡片布局和筛选组件
- 一键复用对接现有 Industry bootstrap 流程，模板作为 draft 预填数据源
- 评价系统复用 Predictions 页面的 review 交互模式
- 依赖检查复用 WorkflowTemplates 的 dependency 校验逻辑

## 开发阶段

### Phase 1：导出与发布（约1周）
- [ ] 方案脱敏导出接口
- [ ] 发布向导页面
- [ ] CommunityTemplate 数据模型

### Phase 2：社区市场（约1周）
- [ ] 社区市场列表页
- [ ] 模板详情页
- [ ] 搜索与筛选

### Phase 3：复用与评价（约1周）
- [ ] 一键复用→Industry draft 预填
- [ ] 评价系统
- [ ] 使用统计

### Phase 4：激励与运营（约0.5周）
- [ ] 贡献积分
- [ ] 排行榜
- [ ] 成功案例聚合展示

## 风险与注意事项

- 冷启动：初期没有社区内容，需要自己先跑几个行业方案作为种子模板
- 质量控制：需要审核机制防止低质量或误导性模板
- 隐私安全：脱敏算法必须可靠，不能泄露用户业务数据
- 版权归属：明确模板的使用协议（建议CC BY-SA或类似）
