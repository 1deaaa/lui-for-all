# プロジェクト完全実行計画（MVP）

> 言語: [简体中文](LUI-for-all_Execution_Plan.md) | [English](LUI-for-all_Execution_Plan.en-US.md) | **日本語**
>
> README: [简体中文](README.md) | [English](README.en-US.md) | [日本語](README.ja-JP.md)

## 1. ビジョンと中核要件

目的は、既存の GUI 中心システムに対して、独立した自然言語 UI（LUI）を提供することです。

ユーザーは画面遷移と複雑な操作の代わりに、自然言語で目的を伝えます。システムが意図を理解し、既存 API を実行し、結果を整理して返答します。

### 10 の製品原則

1. 既存システムを置換せず、横付けで提供する。
2. 画面操作を言語操作へ昇格する。
3. 能力グラフを自動生成する。
4. API 単純対応ではなく Task-First で編成する。
5. 安全隔離をデフォルトにする。
6. 完全な監査証跡を残す。
7. 回答はテキスト中心、UI は必要時のみ補助。
8. 指令主導の操作導線へ再編成する。
9. RPA や低コード生成とは明確に境界を引く。
10. まずは複雑な業務システムに集中する。

## 2. MVP 固定技術スタック

### バックエンド

- Python（Conda + `requirements.txt`）
- FastAPI
- Pydantic v2
- LangGraph 1.x
- httpx
- SQLAlchemy 2
- SQLite + `langgraph-checkpoint-sqlite`

### フロントエンド

- Vue 3.5 + TypeScript
- Vite 7
- Vue Router 4 + Pinia 3
- Element Plus 2.x
- Apache ECharts
- pnpm 10

### データ/プロトコル

- Pydantic と ORM の責務分離
- リアルタイム配信は SSE（WebSocket 非依存）
- 宣言的 UI ブロックの厳格ホワイトリスト

## 3. サブシステム設計

### 3.1 Project Modeler（OpenAPI 駆動）

- OpenAPI を第一の確定情報源として取り込む。
- 軽量な使用痕跡シグナルを補助情報として追加する。
- 能力グラフに以下を付与する:
  - `domain`
  - `best_modalities`
  - `requires_confirmation`
  - `user_intent_examples`

### 3.2 宣言的 UI とイベントプロトコル

- A2UI 思想に基づく宣言的ブロック出力。
- AG-UI 風 SSE イベントストリーム。
- モデル出力は 8 種ホワイトリストのみに制限:
  - `text_block`
  - `metric_card`
  - `data_table`
  - `echart_card`
  - `confirm_panel`
  - `filter_form`
  - `timeline_card`
  - `diff_card`

### 3.3 安全ポリシー階層

- `readonly_safe`: 直接実行
- `readonly_sensitive`: 実行 + マスキング
- `soft_write`: 人間承認必須
- `hard_write` / `critical`: MVP では遮断

## 4. リポジトリ構成（目標）

```text
lui-for-all/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── graph/
│   │   ├── discovery/
│   │   ├── policy/
│   │   ├── executor/
│   │   ├── schemas/
│   │   └── models/
├── frontend/
│   └── src/
│       ├── views/
│       ├── stores/
│       ├── composables/
│       └── components/
└── workspace/
```

## 5. エージェント実行指示（段階制）

### Phase 1: 基盤とスキーマ

1. 基本構成とテレメトリ連携を構築。
2. 能力・UI ブロック・SSE・ポリシーのスキーマを実装。
3. `workspace/` 配下で SQLite を初期化。

### Phase 2: 能力発見エンジン

1. OpenAPI 取り込みパイプラインを実装。
2. 軽量な利用シグナル抽出を追加。
3. AI 補完付き能力モデリングと検証を整備。

### Phase 3: LangGraph ワークフロー

1. 共有状態モデルを定義。
2. チェックポイント永続化を有効化。
3. 意図解析から UI ブロック出力までノード連鎖を構築。
4. 分離された HTTP 実行器を統合。

### Phase 4: Vue レンダリングパイプライン

1. SSE 受信・状態同期を実装。
2. スキーマ準拠のブロック描画を実装。
3. レンダリング経路での越権解釈を禁止。

### Phase 5: Human-in-the-Loop 安全運用

1. 実行マトリクスとポリシーゲートを実装。
2. `soft_write` は `interrupt()` で停止。
3. `ConfirmPanel` による承認/拒否を反映。
4. 断点復帰後に完全監査ログを保存。

## 6. 受け入れ条件

- `workspace/` 以外への書き込み禁止。
- 書き込みリスク操作は必ず承認経路を通る。
- ユーザー入力から結果表示まで追跡可能。
- UI 描画はプロトコル準拠のみ。
- 上流 API 更新に対して再検出で追従可能。
