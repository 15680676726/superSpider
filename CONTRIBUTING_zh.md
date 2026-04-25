# 为 superSpider 贡献代码

## 欢迎

感谢你参与 `superSpider`。

仓库入口：

- GitHub：`https://github.com/15680676726/superSpider`
- Issues：`https://github.com/15680676726/superSpider/issues`
- Discussions：`https://github.com/15680676726/superSpider/discussions`

当前运行时包名 / CLI 名称仍然是 `copaw`，所以代码、安装命令和测试里暂时还会继续使用这个名字。

## Mainline-first 工作流

- 默认开发分支是 `main`
- 未经维护者明确批准，不要创建 feature branch、worktree 或备份分支
- 一个任务只有在 `main` 上提交、推送到 `origin/main`、并且工作树干净时，才算完成

## 本地门禁

推送前至少运行与改动相关的检查：

```bash
pip install -e ".[dev]"
pre-commit install
pre-commit run --all-files
pytest
```

如果改动涉及 `console/` 或 `website/`，还需要执行：

```bash
cd console && npm run format
cd website && npm run format
```

## 提交格式

提交信息遵循 Conventional Commits：

```text
<type>(<scope>): <subject>
```

例如：

```bash
feat(runtime): add executor recovery projection
fix(console): correct runtime center route handling
docs(readme): update open-source setup guidance
```

## 适合贡献的内容

欢迎以下类型的贡献：

- bug 修复
- 文档改进
- 测试加固
- Runtime Center / 前端体验改进
- capability、runtime、evidence 主链收口

如果是较大的改动，先开 issue 或认领 issue，再开始实现。

## 文档要求

- 只要用户可见行为变了，就同步更新文档
- 仓库内公开文档在 `website/public/docs/`
- 涉及架构、迁移、状态模型的改动，需要按仓库规范同步更新根目录文档

## PR 与评审

- 改动保持聚焦，不要把无关内容混在同一批提交里
- 如果 `pre-commit` 改写了文件，先提交改写结果，再重新跑检查

## 交流与反馈

- 讨论：`https://github.com/15680676726/superSpider/discussions`
- Bug / 功能请求：`https://github.com/15680676726/superSpider/issues`
