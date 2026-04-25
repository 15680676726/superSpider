<div align="center">
  <img src="console/public/spider-mesh-symbol.svg" alt="superSpider logo" width="120" />

  # superSpider

  <p><b>面向本地自治执行的主脑系统。</b></p>
</div>

superSpider 不是另一个聊天壳子。它是一个本地主脑执行系统，用来通过受管的外部执行体、可见的运行态、持续环境和证据优先回写，驱动长期任务持续运行。

当前正式外部执行体路径是 `Codex`。这套架构后续会继续扩展到更多外部执行体，包括 `Hermes` 这一类 runtime，但不会把这些执行体变成第二个主脑，也不会让它们拥有第二套系统真相。

## 为什么会有这个项目

大多数 AI 项目停留在聊天、提示词和工具调用这一层。那一层当然有用，但一旦任务需要持续运行、恢复、追责、核对证据，或者在模型回复之后继续推进，单纯聊天就不够了。

superSpider 想解决的是更难的那一层：

- 只有一个主脑，负责判断下一步该做什么
- 外部执行体负责真正执行
- 所有运行态、证据、恢复和人工控制都回到同一个 Runtime Center
- 用一个本地运行面替代散落的脚本、控制台和隐藏 worker 状态

## superSpider 到底是什么

superSpider 是一个 local-first 的自治执行系统，它的边界很明确：

- `superSpider` 是主脑
- 外部执行体是执行层
- Runtime Center 是可见的操作面
- 证据和运行态回写到同一条本地真相链

这个边界很重要。执行体应该执行，主脑应该负责规划、派发、监督、恢复，以及让整套系统长期保持一致。

## 现在已经能做什么

当前仓库已经具备这些核心能力：

- 围绕目标、backlog、assignment、runtime state 和 evidence 的正式主脑执行链
- 基于 `Codex` 的受管本地外部执行体路径
- runtime continuity、事件摄取、证据回写和恢复链
- 一个可用于执行、观察、治理和操作员控制的 Runtime Center
- 本地优先的运行方式，让操作者能看见系统做了什么、失败在哪里、当前真相是什么

## 外部执行体模型

superSpider 不把外部执行体当成“挂在 prompt 后面的插件”。

它把外部执行体当成受管的执行面。

- `superSpider` 负责主脑逻辑、任务真相、恢复逻辑和操作员可见状态
- 外部执行体负责执行 turn
- 执行结果以 runtime event、evidence 和结构化 writeback 的形式回流

当前正式路径：

- `Codex` 是现役外部执行体路径

后续路径：

- `Hermes` 这一类 runtime，以及其他能满足同一执行合同的正式 executor provider

## 为什么值得开发者关注

superSpider 面向的不是只想聊天的人，而是想要真正执行系统的人：

- 想做 AI agent / automation，但不想接受黑盒运行时的开发者
- 想在本地跑自治执行，而不是依赖托管编排层的独立开发者
- 做长期任务、看重证据、恢复和状态连续性的工程团队

## 这个仓库不是什么

superSpider 不是：

- 通用聊天 UI
- 套着工具调用的 prompt 外壳
- 随便拼接能力的工作流市场
- 把任意导入项目都当成正式执行体的容器

这个仓库想做的是一套有纪律的执行架构，不是一堆 demo 的拼盘。

## 仓库结构

- `src/copaw/`：运行内核、状态、能力、执行、证据和兼容层
- `console/`：主前端和 Runtime Center
- `website/`：仓库内文档和对外页面
- 根目录规划与状态文档：记录架构、迁移和验收进度

## 命名说明

- 项目名：`superSpider`
- 仓库地址：`https://github.com/15680676726/superSpider`
- 当前 Python 包 / CLI 名称：`copaw`

也就是说，对外项目名已经统一成 `superSpider`，但安装和运行命令目前仍然使用 `copaw`。

## 当前项目状态

- 仓库已经公开
- Issues、Discussions 和 Pull Requests 都已开放
- 当前治理模式仍然是 maintainer-led
- 较大的改动应先从 issue 或 discussion 开始

系统架构和实时进度以这些文档为准：

- [系统架构总说明](COPAW_CARRIER_UPGRADE_MASTERPLAN.md)
- [任务状态](TASK_STATUS.md)
- [数据模型草案](DATA_MODEL_DRAFT.md)
- [API 迁移图](API_TRANSITION_MAP.md)

## 快速启动

```bash
pip install -e .
copaw init --defaults
copaw app
```

启动后打开 `http://127.0.0.1:8088/`。

## 前端开发

主前端：

```bash
cd console
npm install
npm run dev
```

文档 / 网站：

```bash
cd website
npm install
npm run dev
```

## 关键文档

- [升级总方案](COPAW_CARRIER_UPGRADE_MASTERPLAN.md)
- [任务状态](TASK_STATUS.md)
- [前端升级路线](FRONTEND_UPGRADE_PLAN.md)
- [运行中心 UI 规范](RUNTIME_CENTER_UI_SPEC.md)
- [Agent 可见模型](AGENT_VISIBLE_MODEL.md)
- [文档目录](website/public/docs/)

## 参与方式

- [贡献指南](CONTRIBUTING_zh.md)
- [社区行为规范](CODE_OF_CONDUCT.md)
- [支持与反馈](SUPPORT.md)
- [治理方式](GOVERNANCE.md)
- [安全策略](SECURITY.md)
- [Issues](https://github.com/15680676726/superSpider/issues)
- [Discussions](https://github.com/15680676726/superSpider/discussions)
