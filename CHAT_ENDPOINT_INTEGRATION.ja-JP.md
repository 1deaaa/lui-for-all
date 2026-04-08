# Chat エンドポイント統合プロトコル（カスタム GUI 対応）

このドキュメントは LUI-for-All の統一 chat プロトコルを定義します。開発者は組み込みフロントエンドに依存せず、`chat` エンドポイントへ直接接続して独自 GUI を実装できます。

## 1. 目的

- チャット主経路を `chat` 名前空間に集約する。
- フロントエンドは「イベント描画 + ブロック描画」の実装だけで統合可能。
- 進捗、HTTP 呼び出し、承認要求/承認履歴、思考ストリーム、UI ブロックを既存 UI と同等に扱える。

## 2. 伝送タイプ一覧

| データ | エンドポイント | 伝送 | Content-Type | 説明 |
|---|---|---|---|---|
| 新規チャット開始 + 実行 | `POST /api/chat/stream` | SSE | `text/event-stream` | task_run を作成してストリーム開始 |
| 承認後の再開 | `POST /api/chat/resume` | SSE | `text/event-stream` | 同一 task_run を断点再開 |
| セッションメッセージスナップショット | `GET /api/chat/sessions/{session_id}/messages` | 通常 HTTP JSON | `application/json` | 本文/思考/承認ブロック/HTTP 要約を含む |
| タスクスナップショット | `GET /api/chat/task-runs/{task_run_id}` | 通常 HTTP JSON | `application/json` | `ui_blocks` と `execution_artifacts` を含む |
| タスクイベント再生 | `GET /api/chat/task-runs/{task_run_id}/events` | 通常 HTTP JSON | `application/json` | Event Sourcing 再生 |
| 承認記録 | `GET /api/chat/task-runs/{task_run_id}/approvals` | 通常 HTTP JSON | `application/json` | 承認要求と承認結果 |
| HTTP 実行記録 | `GET /api/chat/task-runs/{task_run_id}/http-executions` | 通常 HTTP JSON | `application/json` | ツール実行に対応する HTTP 履歴 |

## 3. SSE プロトコル

### 3.1 フレーム形式

```text
event: <event_name>
data: { ...json payload... }
```

### 3.2 主要イベント

| event | 伝送 | 主なフィールド | UI 用途 |
|---|---|---|---|
| `session_started` | SSE | `session_id`, `project_id`, `trace_id` | 会話コンテキスト初期化 |
| `task_started` | SSE | `task_run_id`, `user_message` | タスク開始表示 |
| `task_progress` | SSE | `node_name`, `progress`, `message` | 進捗バー/ステータス |
| `node_completed` | SSE | `node_name`, `progress` | ノード進行タイムライン |
| `tool_started` | SSE | `tool_name`, `title`, `detail`, `route_id` | 実行イベントログ |
| `tool_completed` | SSE | `tool_name`, `status_code`, `route_id` | HTTP 呼び出し結果表示 |
| `token_emitted` | SSE | `token` | AI 本文ストリーミング |
| `thought_emitted` | SSE | `token` | 思考ストリーミング |
| `agentic_iteration` | SSE | `iteration`, `think` | 反復推論の進捗 |
| `write_approval_required` | SSE | `batch_id`, `items[]`, `write_id`, `reasoning`, `safety_level` | 承認パネル描画 |
| `approval_pending` | SSE | `session_id`, `task_run_id` | 承認待ちでグラフ一時停止 |
| `ui_block_emitted` | SSE | `block_index`, `block_type`, `block_data` | ブロック描画 |
| `task_completed` | SSE | `summary` | 完了表示 |
| `error` | SSE | `error_code`, `error_message`, `details` | エラー表示と復旧 |

## 4. UI ブロック白名单

カスタム GUI 側で `block_type` ごとのレンダラを実装します。

- `text_block`
- `metric_card`
- `data_table`
- `echart_card`
- `confirm_panel`
- `filter_form`
- `timeline_card`
- `diff_card`

## 5. 最小統合フロー

1. `POST /api/chat/stream` に `project_id + content (+ session_id)` を送信。
2. SSE を継続受信し描画:
   - `token_emitted` 本文
   - `thought_emitted` 思考
   - `task_progress` / `tool_*` 実行トレース
   - `ui_block_emitted` 構造化 UI
3. `write_approval_required` を受信したら承認 UI を表示。
4. ユーザー決定後に `POST /api/chat/resume` を呼ぶ:
   - `action`: `approve` / `reject`
   - `approved_ids`: 実行許可 write_id 一覧
   - `decided_ids`: 当該承認パネルの write_id 全件（監査整合のため推奨）
5. 履歴再生が必要ならスナップショット API を取得。

## 6. リクエスト例

### 6.1 開始

```http
POST /api/chat/stream
Content-Type: application/json

{
  "project_id": "project-123",
  "content": "今日の承認待ち注文を金額順に並べて",
  "session_id": "optional-session-id",
  "locale": "ja-JP"
}
```

### 6.2 再開

```http
POST /api/chat/resume
Content-Type: application/json

{
  "session_id": "session-123",
  "task_run_id": "task-123",
  "action": "approve",
  "batch_id": "batch-001",
  "approved_ids": ["write-1", "write-2"],
  "decided_ids": ["write-1", "write-2", "write-3"],
  "write_id": "write-1",
  "locale": "ja-JP"
}
```

## 7. 実装ガイド

次の 4 点を実装すれば、バックエンド能力コアを変えずに GUI だけ差し替え可能です。

- SSE イベントディスパッチャ
- 8 種ブロックレンダラ
- 履歴/監査リプレイ API
- 承認 + resume 操作
