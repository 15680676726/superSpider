# Spider Mesh 系统能力概览

本页只描述当前Spider Mesh系统已经对外提供的正式能力，不再使用历史项目对比口径。

| 能力面 | 当前能力 | 主要入口 |
| :-- | :-- | :-- |
| 前台主入口 | 前台默认唯一主入口为 **Spider Mesh 执行中枢**，对话侧采用“控制线程 + 任务线程”结构。 | `/chat` |
| 团队执行 | 一个总控脑，多个专业执行位；共享事实底座，按团队角色拆任务和回收结果。 | `/industry`、`/runtime-center/agents` |
| 能力接入 | 支持安装模板、SkillHub 商店、MCP、本地技能、浏览器与桌面运行时。 | `/capability-market` |
| 治理与审批 | 统一使用 `auto / guarded / confirm` 三档治理；审批和确认单都回到运行中心处理。 | `/runtime-center/governance` |
| 证据与复盘 | 任务、证据、决策、预测、复盘都可追溯，可回看执行链路。 | `/runtime-center`、`/predictions`、`/reports` |
| 行业初始化 | 支持行业草案生成、团队编排、推荐安装包、启动后的持续自治运行。 | `/industry` |
| 交付形态 | 支持本地服务、Web 控制台、桌面安装包与 Docker 交付。 | `/docs/quickstart`、`/docs/desktop` |
