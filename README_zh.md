<div align="center">
  <img src="console/public/baize-symbol.svg" alt="Spider Mesh logo" width="120" />

  # Spider Mesh

  <p><b>面向目标、环境、证据与长期任务的本地执行系统。</b></p>
</div>

Spider Mesh是一个面向长期任务的本地执行系统。它把 Goal、Agent、Task、Environment、Evidence 和 Patch 收敛到同一个 Runtime Center，让执行、观察与演进发生在同一块可见运行面上。

它的设计重心有四个：以目标驱动执行、让环境持续挂载、让重要动作先留下证据、以及用一个本地运行中心替代分散控制面。

## 当前入口

- `console/` 是主前端，也是当前的 Runtime Center。
- `website/` 是Spider Mesh的对外产品站与介绍入口。
- 架构与实时进度以 [系统架构](COPAW_CARRIER_UPGRADE_MASTERPLAN.md) 和 [任务状态](TASK_STATUS.md) 为准。

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

占位外站：

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
