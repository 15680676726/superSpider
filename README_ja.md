<div align="center">
  <img src="console/public/baize-symbol.svg" alt="Spider Mesh logo" width="120" />

  # Spider Mesh

  <p><b>Goal・Environment・Evidence・長期タスクのためのローカル実行システム。</b></p>
</div>

Spider Mesh は、長期タスクのためのローカル実行システムです。Goal、Agent、Task、Environment、Evidence、Patch を 1 つの Runtime Center に集約し、実行・観測・進化を同じ可視面で扱います。

設計の軸は 4 つです。Goal 起点の実行、持続する Environment、evidence-first の実行、そして分散した管理画面ではなく 1 つのローカル Runtime Center です。

## 現在の入口

- `console/` が主フロントエンドであり、現在の Runtime Center です。
- `website/` は Spider Mesh の対外プロダクトサイトです。
- アーキテクチャと進行状況は [System Architecture](COPAW_CARRIER_UPGRADE_MASTERPLAN.md) と [Task Status](TASK_STATUS.md) を参照してください。

## クイックスタート

```bash
pip install -e .
copaw init --defaults
copaw app
```

起動後に `http://127.0.0.1:8088/` を開きます。

## フロントエンド開発

主フロントエンド:

```bash
cd console
npm install
npm run dev
```

プレースホルダー外部サイト:

```bash
cd website
npm install
npm run dev
```

## 重要ドキュメント

- [Master plan](COPAW_CARRIER_UPGRADE_MASTERPLAN.md)
- [Task status](TASK_STATUS.md)
- [Frontend upgrade plan](FRONTEND_UPGRADE_PLAN.md)
- [Runtime Center UI spec](RUNTIME_CENTER_UI_SPEC.md)
- [Agent visible model](AGENT_VISIBLE_MODEL.md)
