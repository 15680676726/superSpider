<div align="center">
  <img src="console/public/baize-symbol.svg" alt="superSpider logo" width="120" />

  # superSpider

  <p><b>面向目标、环境、证据与长期任务的本地执行系统。</b></p>
</div>

superSpider 是一个面向长期自治执行的本地运行系统。它把 Goal、Agent、Task、Environment、Evidence 和 Patch 收敛到同一个 Runtime Center，让执行、观察与演进发生在同一块可见运行面上。

它当前聚焦四件事：以 assignment/backlog 真相驱动主脑执行、让环境持续挂载、让重要动作优先留下证据、以及用一个本地运行中心替代分散控制面。

## 名称说明

- 项目主名：`superSpider`
- 仓库地址：`https://github.com/15680676726/superSpider`
- 当前 Python 包 / CLI 名称：`copaw`

也就是说，对外项目名已经统一为 `superSpider`，但安装命令和运行命令目前仍然使用 `copaw`。

## 当前入口

- `console/` 是主前端，也是当前的 Runtime Center。
- `website/` 保存仓库内文档与对外页面源码。
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
- [安全策略](SECURITY.md)
- [Issues](https://github.com/15680676726/superSpider/issues)
- [Discussions](https://github.com/15680676726/superSpider/discussions)
