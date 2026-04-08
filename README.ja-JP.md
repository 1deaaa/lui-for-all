<div align="center">

# LUI-for-All

**自然言語で、あらゆるシステムを操作する。**

*Language User Interface · ゼロ侵襲導入/撤去 · エンタープライズ級セーフティ*
</div>

---

> 言語: [简体中文](README.md) | [English](README.en-US.md) | **日本語**

## 解決する課題

多くの業務システムは機能が強力である一方、操作が複雑です。ユーザーは多層メニューの移動、条件の組み合わせ、フォーム入力を繰り返さないと業務を完了できません。

**LUI-for-All** は既存システムの横に独立フォルダとして配置され、既存コードを変更せずに自然言語操作レイヤーを提供します。

```text
ユーザー: 「先週の承認待ち購買申請を金額降順で一覧化し、
50,000超をハイライトして。」

LUI: [意図理解 -> 既存 API 呼び出し -> テーブル + ハイライト表示]
     ✓ 既存コードは未変更
```

## 主な特徴

1. ゼロ侵襲導入・簡単撤去
- 既存プロジェクト横に独立配置
- 既存コードへのアクセスは原則 read-only
- 実行時の書き込みは `workspace/` に隔離

2. OpenAPI + Tree-sitter AST のハイブリッド発見
- まず `OpenAPI/Swagger` を優先取り込みし、構造化されたルートを高速取得
- 統一 AST 抽出層（`FrameAdapter + get_tree_sitter_query`）で実装コード（Handler）まで取得
- 主要バックエンドに標準対応: Python（FastAPI/Flask/Sanic）、Node.js（NestJS/Express/Fastify）、Java（Spring Boot）、C#（ASP.NET Core）、Go（Gin/Echo/Fiber/chi）
- OpenAPI が未公開/到達不可でも `source_path` を使って AST 発見へ自動フォールバック
- ルート引数表記（例: `:id -> {id}`）を正規化し、フレームワーク差異を吸収

3. 宣言的 UI ホワイトリスト
- モデル出力は JSON ブロックのみ
- HTML/JS/CSS の直接出力は禁止
- 対応 8 種: `text_block`, `metric_card`, `data_table`, `echart_card`, `confirm_panel`, `filter_form`, `timeline_card`, `diff_card`

4. LangGraph 実行核 + 人間承認ゲート
- チェックポイント付きの多段オーケストレーション
- 書き込みリスク操作は `interrupt()` で強制停止
- 承認後に断点再開、監査ログを保持

5. AG-UI + SSE リアルタイムイベント
- ノード進捗をリアルタイム配信
- 推論・出力をストリーミング表示
- 承認要求時に UI 側を即時割り込み

6. エンドツーエンド可観測性
- API 層、Graph 層、HTTP 実行層で Trace ID を統一
- すべての意思決定を追跡可能

7. マルチモデルゲートウェイ
- Agent Matchbox を内蔵
- モデル切替時に業務コード変更不要

8. Docker / ローカル環境の自動接続解決
- 実行環境に応じてサンプル接続先を自動解決
- Docker ではサービス DNS 名、ローカルでは `localhost` を使用
- `test-connection` と `fetch-routes` は `source_path` による AST フォールバックに対応し、OpenAPI 到達不可でも導入フローを継続可能

## クイックスタート

### 必要環境

- Python 3.11+（Conda 推奨）
- Node.js 18+ / pnpm 10
- OpenAPI 公開を推奨（`/openapi.json` など）
- OpenAPI 未公開の場合は、AST 発見のため `source_path`（アクセス可能なソースコードパス）を指定

### 1. クローン

```bash
git clone https://github.com/your-org/lui-for-all.git
cd lui-for-all
```

### 2. バックエンド準備

```bash
conda create -n lui python=3.11 -y
conda activate lui
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

### 3. フロントエンド準備

```bash
cd frontend
pnpm install
```

### 4. 起動

```bash
# ターミナル 1
cd backend
conda run -n lui uvicorn app.main:app --reload --port 6689

# ターミナル 2
cd frontend
pnpm dev
```

### 5. 最初のプロジェクト接続

`http://localhost:5173` を開き、まず OpenAPI URL（例: `http://your-app/openapi.json`）を入力してプロジェクトを登録します。

OpenAPI がない場合でも、`source_path` のみで登録可能です。発見処理は自動的に AST モードへ切り替わります。

## アーキテクチャ（要約）

- Frontend: Vue 3 + Vite + Pinia + Vue Router + Element Plus
- Protocol: AG-UI スタイル SSE + 宣言的 UI ブロック
- Backend: FastAPI + LangGraph + SQLAlchemy + SQLite
- Discovery: OpenAPI 取り込み + Tree-sitter AST フォールバック + 能力グラフ生成
- Safety: ポリシーマトリクス + Human-in-the-loop

## ロードマップ

- [x] MVP 実行パイプライン
- [x] OpenAPI 自動能力発見
- [x] 8 種 UI ブロック白名单
- [x] SSE ストリーミング + 承認割り込み
- [x] マルチモデルゲートウェイ
- [x] Tree-sitter AST ルートセマンティック解析（OpenAPI 非依存オンボーディング対応）
- [ ] 能力グラフ管理 UI
- [ ] マルチテナント権限管理
- [ ] プライベート導入ガイド

<div align="center">

*言葉を、インターフェースに。*

</div>
