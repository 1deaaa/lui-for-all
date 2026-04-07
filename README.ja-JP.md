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

2. OpenAPI からの自動能力モデリング
- `OpenAPI/Swagger` を自動取り込み
- ドメイン、表示モダリティ、安全レベル付き能力グラフを生成
- 再検出で上流 API 変更に追従

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

## クイックスタート

### 必要環境

- Python 3.11+（Conda 推奨）
- Node.js 18+ / pnpm 10
- 対象システムの OpenAPI 公開（`/openapi.json` など）

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

`http://localhost:5173` を開き、OpenAPI URL（例: `http://your-app/openapi.json`）を入力してプロジェクトを登録します。

## アーキテクチャ（要約）

- Frontend: Vue 3 + Vite + Pinia + Vue Router + Element Plus
- Protocol: AG-UI スタイル SSE + 宣言的 UI ブロック
- Backend: FastAPI + LangGraph + SQLAlchemy + SQLite
- Discovery: OpenAPI 取り込み + 能力グラフ生成
- Safety: ポリシーマトリクス + Human-in-the-loop

## ロードマップ

- [x] MVP 実行パイプライン
- [x] OpenAPI 自動能力発見
- [x] 8 種 UI ブロック白名单
- [x] SSE ストリーミング + 承認割り込み
- [x] マルチモデルゲートウェイ
- [ ] Git セマンティック解析
- [ ] 能力グラフ管理 UI
- [ ] マルチテナント権限管理
- [ ] プライベート導入ガイド

<div align="center">

*言葉を、インターフェースに。*

</div>
