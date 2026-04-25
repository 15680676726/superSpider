<div align="center">
  <img src="console/public/baize-symbol.svg" alt="superSpider logo" width="120" />

  # superSpider

  <p><b>Goal・Environment・Evidence・長期タスクのためのローカル実行システム。</b></p>
</div>

superSpider は、長期的な自律実行のためのローカル実行システムです。Goal、Agent、Task、Environment、Evidence、Patch を 1 つの Runtime Center に集約し、実行・観測・進化を同じ可視面で扱います。

現在の中核は 4 つです。assignment/backlog truth に基づく main-brain execution、持続的な environment mount、evidence-first な実行、そして分散した設定画面ではなく 1 つの local operating surface です。

## 命名

- プロジェクト名: `superSpider`
- リポジトリ: `https://github.com/15680676726/superSpider`
- 現在の Python パッケージ / CLI 名: `copaw`

公開名は `superSpider` に統一していますが、インストールと実行コマンドは現時点では `copaw` のままです。

## 現在の入口

- `console/` はメインフロントエンドであり Runtime Center です。
- `website/` はリポジトリ内ドキュメントと公開ページのソースです。
- 設計と進行状況は [System Architecture](COPAW_CARRIER_UPGRADE_MASTERPLAN.md) と [Task Status](TASK_STATUS.md) を参照してください。

## クイックスタート

```bash
pip install -e .
copaw init --defaults
copaw app
```

起動後に `http://127.0.0.1:8088/` を開きます。

## フロントエンド開発

メインフロントエンド:

```bash
cd console
npm install
npm run dev
```

ドキュメント / サイト:

```bash
cd website
npm install
npm run dev
```

## 主要ドキュメント

- [Master plan](COPAW_CARRIER_UPGRADE_MASTERPLAN.md)
- [Task status](TASK_STATUS.md)
- [Frontend upgrade plan](FRONTEND_UPGRADE_PLAN.md)
- [Runtime Center UI spec](RUNTIME_CENTER_UI_SPEC.md)
- [Agent visible model](AGENT_VISIBLE_MODEL.md)
- [Docs directory](website/public/docs/)

## コントリビュート

- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Issues](https://github.com/15680676726/superSpider/issues)
- [Discussions](https://github.com/15680676726/superSpider/discussions)
