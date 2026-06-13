# Chat エンドポイント統合プロトコル（カスタム GUI 対応）

> 本ドキュメントは LUI-for-All の統一チャットプロトコルを定義する。サードパーティ開発者は `/api/chat/*` 名前空間のエンドポイントに直接接続してカスタム GUI を構築でき、リポジトリ内蔵のフロントエンドに依存する必要がない。

> ⚠️ **名前空間について**：本ドキュメントは `/api/chat/*` エンドポイントのみを対象とする。これはカスタム GUI の**唯一推奨される接続インターフェース**である。内部フロントエンドが使用する `/api/sessions/*` はレガシー内部インターフェースであり、その固有機能（旧式の承認処理など）は将来のバージョンで `/api/chat/*` に移行される予定である。管理系エンドポイント（プロジェクト管理、認証、設定、LLM 設定、監査クエリなど）は本プロトコルの範囲外である。

---

## 1. 設計目標

| 目標 | 説明 |
|---|---|
| **統一エントリ** | チャットの主要フローは `/api/chat/*` 名前空間に統一し、フロントエンドは内部のグラフオーケストレーション詳細を意識する必要がない |
| **ミニマルフロントエンド** | フロントエンドは「SSE イベントディスパッチ + UI Block レンダリング」を実装するだけで、完全な AI 機能を再利用できる |
| **データ整合性** | 組み込みフロントエンドと一貫したデータ表現を維持：AI 進捗、HTTP 呼び出し、承認フロー、思考フロー、UI Block |
| **デュアルチャネル認証** | Admin JWT（管理者）と User JWT（エンドユーザー）の両方をサポートし、マルチテナントシナリオに対応 |

---

## 2. エンドポイント一覧

| メソッド | パス | 認証 | 伝送方式 | 説明 |
|---|---|---|---|---|
| `POST` | `/api/chat/stream` | Admin / User JWT | SSE | 新規会話を開始しストリーミング実行 |
| `POST` | `/api/chat/resume` | Admin / User JWT | SSE | 承認後に実行を再開 |
| `POST` | `/api/chat/task-runs/{task_run_id}/stop` | Admin JWT | JSON | 実行中のタスクを停止 |
| `GET` | `/api/chat/projects/{project_id}/sessions` | Admin / User JWT | JSON | 指定プロジェクトの履歴セッション一覧を取得 |
| `GET` | `/api/chat/sessions/{session_id}` | Admin / User JWT | JSON | セッション詳細を取得 |
| `GET` | `/api/chat/sessions/{session_id}/messages` | Admin / User JWT | JSON | セッションメッセージのスナップショットを取得 |
| `GET` | `/api/chat/sessions/{session_id}/messages/{message_id}` | Admin / User JWT | JSON | 単一メッセージの詳細を取得 |
| `GET` | `/api/chat/task-runs/{task_run_id}` | Admin JWT | JSON | タスクスナップショットを取得 |
| `GET` | `/api/chat/task-runs/{task_run_id}/events` | Admin JWT | JSON | タスクイベントリプレイ（Event Sourcing）を取得 |
| `GET` | `/api/chat/task-runs/{task_run_id}/approvals` | Admin JWT | JSON | 承認レコードを取得 |
| `GET` | `/api/chat/task-runs/{task_run_id}/http-executions` | Admin JWT | JSON | HTTP 呼び出しレコードを取得 |

---

## 3. エンドポイント詳細

### 3.1 新規会話開始（SSE ストリーム）

- **メソッド + パス**：`POST /api/chat/stream`
- **認証**：Admin JWT または User JWT
- **伝送方式**：SSE（`text/event-stream`）

**リクエストボディ**

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `project_id` | `string` | ✅ | 対象プロジェクト ID |
| `content` | `string` | ✅ | ユーザーメッセージテキスト |
| `session_id` | `string` | ❌ | オプション。既存のセッション ID を指定してセッションを再利用。未指定の場合は新しいセッションを自動作成 |
| `locale` | `string` | ❌ | レスポンス言語コード。例：`zh-CN`、`en-US`、`ja-JP`。デフォルト `zh-CN` |

**レスポンス**

SSE ストリーム。イベントプロトコルは[第 4 節 SSE イベントプロトコル](#4-sse-イベントプロトコル)を参照。

**リクエスト例**

```http
POST /api/chat/stream
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "project_id": "project-123",
  "content": "把今天待审批订单按金额排序",
  "session_id": null,
  "locale": "zh-CN"
}
```

---

### 3.2 承認後実行再開（SSE ストリーム）

- **メソッド + パス**：`POST /api/chat/resume`
- **認証**：Admin JWT または User JWT
- **伝送方式**：SSE（`text/event-stream`）

**リクエストボディ**

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `session_id` | `string` | ✅ | セッション ID |
| `task_run_id` | `string` | ✅ | タスク実行 ID |
| `action` | `string` | ✅ | 承認アクション：`approve` または `reject` |
| `write_id` | `string` | ❌ | 単一承認の write_id（後方互換） |
| `approved_ids` | `string[]` | ❌ | 本次承認して実行する write_id のリスト |
| `decided_ids` | `string[]` | ❌ | 現在の承認パネルに関連するすべての write_id。完全な監査結果を記録するために使用 |
| `batch_id` | `string` | ❌ | 承認バッチ ID |
| `locale` | `string` | ❌ | レスポンス言語コード |

**レスポンス**

SSE ストリーム。`stream` エンドポイントと同じイベントプロトコルを共有。

**リクエスト例**

```http
POST /api/chat/resume
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "session_id": "session-123",
  "task_run_id": "task-123",
  "action": "approve",
  "batch_id": "batch-001",
  "approved_ids": ["write-1", "write-2"],
  "decided_ids": ["write-1", "write-2", "write-3"],
  "write_id": "write-1",
  "locale": "zh-CN"
}
```

---

### 3.3 実行中タスクの停止

- **メソッド + パス**：`POST /api/chat/task-runs/{task_run_id}/stop`
- **認証**：Admin JWT
- **伝送方式**：JSON

**パスパラメータ**

| パラメータ | 型 | 説明 |
|---|---|---|
| `task_run_id` | `string` | タスク実行 ID |

**リクエストボディ**

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `session_id` | `string` | ❌ | セッション ID（オプション。整合性チェック用） |
| `reason` | `string` | ❌ | 停止理由 |

**レスポンス**

| フィールド | 型 | 説明 |
|---|---|---|
| `status` | `string` | タスクの最終ステータス。例：`cancelled`、`completed` |
| `task_run_id` | `string` | タスク実行 ID |
| `stream_cancelled` | `boolean` | 実行中の SSE ストリームが正常にキャンセルされたか |
| `message` | `string` | 操作結果の説明 |

**リクエスト例**

```http
POST /api/chat/task-runs/task-123/stop
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "session_id": "session-123",
  "reason": "用户手动停止"
}
```

---

### 3.4 プロジェクト履歴セッション一覧の取得

- **メソッド + パス**：`GET /api/chat/projects/{project_id}/sessions`
- **認証**：Admin JWT または User JWT
- **伝送方式**：JSON

**パスパラメータ**

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |

**クエリパラメータ**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | ページあたり件数（1-200） |
| `offset` | `int` | ❌ | `0` | オフセット |

**レスポンス**

| フィールド | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |
| `sessions` | `Session[]` | セッション一覧 |
| `total` | `int` | 合計件数 |
| `limit` | `int` | ページあたり件数 |
| `offset` | `int` | オフセット |

**Session オブジェクト**

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | `string` | セッション ID |
| `project_id` | `string` | 所属プロジェクト ID |
| `title` | `string` | セッションタイトル |
| `status` | `string` | セッションステータス |
| `thread_id` | `string` | LangGraph スレッド ID |
| `context` | `object` | セッションコンテキスト |
| `created_at` | `string` | 作成日時（ISO 8601） |
| `updated_at` | `string` | 更新日時（ISO 8601） |
| `ended_at` | `string \| null` | 終了日時（ISO 8601） |

**リクエスト例**

```http
GET /api/chat/projects/project-123/sessions?limit=50&offset=0
Authorization: Bearer <jwt>
```

---

### 3.5 セッション詳細の取得

- **メソッド + パス**：`GET /api/chat/sessions/{session_id}`
- **認証**：Admin JWT または User JWT
- **伝送方式**：JSON

**パスパラメータ**

| パラメータ | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |

**レスポンス**

単一の [Session オブジェクト](#session-オブジェクト) を返す。

**リクエスト例**

```http
GET /api/chat/sessions/session-123
Authorization: Bearer <jwt>
```

---

### 3.6 セッションメッセージスナップショットの取得

- **メソッド + パス**：`GET /api/chat/sessions/{session_id}/messages`
- **認証**：Admin JWT または User JWT
- **伝送方式**：JSON

**パスパラメータ**

| パラメータ | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |

**クエリパラメータ**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | 最大メッセージ数（1-200） |

**レスポンス**

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `messages` | `Message[]` | メッセージ一覧 |
| `total` | `int` | メッセージ合計数 |

**Message オブジェクト**

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | `string` | メッセージ ID |
| `role` | `string` | ロール：`user`、`assistant`、`system` |
| `content` | `string` | メッセージ内容 |
| `task_run_id` | `string` | 関連タスク実行 ID |
| `created_at` | `string` | 作成日時（ISO 8601） |
| `metadata` | `object` | メタデータ。`http_calls`、`thought`、`approval_block` 等を含む |

**リクエスト例**

```http
GET /api/chat/sessions/session-123/messages?limit=50
Authorization: Bearer <jwt>
```

---

### 3.7 単一メッセージ詳細の取得

- **メソッド + パス**：`GET /api/chat/sessions/{session_id}/messages/{message_id}`
- **認証**：Admin JWT または User JWT
- **伝送方式**：JSON

**パスパラメータ**

| パラメータ | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `message_id` | `string` | メッセージ ID |

**レスポンス**

単一の [Message オブジェクト](#message-オブジェクト) を返す。

**リクエスト例**

```http
GET /api/chat/sessions/session-123/messages/msg-123
Authorization: Bearer <jwt>
```

---

### 3.8 タスクスナップショットの取得

- **メソッド + パス**：`GET /api/chat/task-runs/{task_run_id}`
- **認証**：Admin JWT
- **伝送方式**：JSON

**パスパラメータ**

| パラメータ | 型 | 説明 |
|---|---|---|
| `task_run_id` | `string` | タスク実行 ID |

**レスポンス**

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | `string` | タスク実行 ID |
| `session_id` | `string` | 所属セッション ID |
| `project_id` | `string` | 所属プロジェクト ID |
| `user_message` | `string` | ユーザーの元メッセージ |
| `normalized_intent` | `string` | 正規化されたインテント |
| `status` | `string` | ステータス：`pending`、`running`、`waiting_approval`、`completed`、`failed`、`cancelled` |
| `plan` | `object` | タスク計画 |
| `execution_artifacts` | `object[]` | 実行成果物（HTTP 呼び出しレコードなど） |
| `summary_text` | `string` | タスクサマリー |
| `ui_blocks` | `object[]` | UI Block リスト |
| `error` | `string` | エラー情報（存在する場合） |
| `trace_id` | `string` | OpenTelemetry トレース ID |
| `thread_id` | `string` | LangGraph スレッド ID |
| `checkpoint_id` | `string` | LangGraph チェックポイント ID |
| `created_at` | `string` | 作成日時（ISO 8601） |
| `updated_at` | `string` | 更新日時（ISO 8601） |
| `completed_at` | `string \| null` | 完了日時（ISO 8601） |

**リクエスト例**

```http
GET /api/chat/task-runs/task-123
Authorization: Bearer <jwt>
```

---

### 3.9 タスクイベントリプレイの取得

- **メソッド + パス**：`GET /api/chat/task-runs/{task_run_id}/events`
- **認証**：Admin JWT
- **伝送方式**：JSON

**パスパラメータ**

| パラメータ | 型 | 説明 |
|---|---|---|
| `task_run_id` | `string` | タスク実行 ID |

**レスポンス**

| フィールド | 型 | 説明 |
|---|---|---|
| `task_run_id` | `string` | タスク実行 ID |
| `events` | `Event[]` | イベントリスト（時系列順） |
| `total` | `int` | イベント合計数 |

**Event オブジェクト**

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | `string` | イベント ID |
| `task_run_id` | `string` | 所属タスク実行 ID |
| `event_type` | `string` | イベントタイプ |
| `payload` | `object` | イベントペイロード |
| `actor_type` | `string` | アクタータイプ |
| `actor_id` | `string` | アクター ID |
| `trace_id` | `string` | トレース ID |
| `evidence_refs` | `object` | エビデンス参照 |
| `ts` | `string` | タイムスタンプ（ISO 8601） |

**リクエスト例**

```http
GET /api/chat/task-runs/task-123/events
Authorization: Bearer <jwt>
```

---

### 3.10 承認レコードの取得

- **メソッド + パス**：`GET /api/chat/task-runs/{task_run_id}/approvals`
- **認証**：Admin JWT
- **伝送方式**：JSON

**パスパラメータ**

| パラメータ | 型 | 説明 |
|---|---|---|
| `task_run_id` | `string` | タスク実行 ID |

**クエリパラメータ**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | ページあたり件数（1-200） |
| `offset` | `int` | ❌ | `0` | オフセット |

**レスポンス**

| フィールド | 型 | 説明 |
|---|---|---|
| `task_run_id` | `string` | タスク実行 ID |
| `approvals` | `Approval[]` | 承認レコードリスト |
| `total` | `int` | 合計件数 |

**Approval オブジェクト**

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | `string` | 承認 ID（write_id と同一） |
| `session_id` | `string` | 所属セッション ID |
| `title` | `string` | 承認タイトル |
| `description` | `string` | 承認説明 |
| `action_summary` | `string` | アクションサマリー |
| `risk_level` | `string` | リスクレベル |
| `details` | `object` | 詳細情報 |
| `status` | `string` | ステータス：`pending`、`approved`、`rejected` |
| `timeout_seconds` | `int` | タイムアウト時間（秒） |
| `expires_at` | `string` | 有効期限（ISO 8601） |
| `decided_at` | `string \| null` | 判定日時（ISO 8601） |
| `decided_by` | `string` | 判定者 |
| `decision_reason` | `string` | 判定理由 |
| `created_at` | `string` | 作成日時（ISO 8601） |

**リクエスト例**

```http
GET /api/chat/task-runs/task-123/approvals?limit=50&offset=0
Authorization: Bearer <jwt>
```

---

### 3.11 HTTP 呼び出しレコードの取得

- **メソッド + パス**：`GET /api/chat/task-runs/{task_run_id}/http-executions`
- **認証**：Admin JWT
- **伝送方式**：JSON

**パスパラメータ**

| パラメータ | 型 | 説明 |
|---|---|---|
| `task_run_id` | `string` | タスク実行 ID |

**クエリパラメータ**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `limit` | `int` | ❌ | `50` | ページあたり件数（1-200） |
| `offset` | `int` | ❌ | `0` | オフセット |

**レスポンス**

| フィールド | 型 | 説明 |
|---|---|---|
| `task_run_id` | `string` | タスク実行 ID |
| `executions` | `Execution[]` | HTTP 呼び出しレコードリスト |
| `total` | `int` | 合計件数 |

**Execution オブジェクト**

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | `string` | レコード ID |
| `request_id` | `string` | リクエスト ID |
| `session_id` | `string` | 所属セッション ID |
| `capability_id` | `string` | ケーパビリティ ID |
| `method` | `string` | HTTP メソッド |
| `url_redacted` | `string` | マスキング処理済み URL |
| `status_code` | `int` | HTTP ステータスコード |
| `duration_ms` | `int` | 処理時間（ミリ秒） |
| `retry_count` | `int` | リトライ回数 |
| `headers_redacted` | `object` | マスキング処理済みリクエストヘッダー |
| `request_body_redacted` | `object` | マスキング処理済みリクエストボディ |
| `response_body_redacted` | `object` | マスキング処理済みレスポンスボディ |
| `trace_id` | `string` | トレース ID |
| `policy_snapshot` | `object` | ポリシースナップショット |
| `error` | `string` | エラー情報（存在する場合） |
| `created_at` | `string` | 作成日時（ISO 8601） |

**リクエスト例**

```http
GET /api/chat/task-runs/task-123/http-executions?limit=50&offset=0
Authorization: Bearer <jwt>
```

---

## 4. SSE イベントプロトコル

### 4.1 フレームフォーマット

各 SSE イベントは `event:` 行と `data:` 行で構成され、空行で終了する。`data` 内の JSON には `event` フィールドは**含まれない**（該当フィールドは `event:` 行に抽出済み）。

```text
event: <event_type>
data: <json_payload>

```

### 4.2 イベントタイプ一覧

| event | data 主要フィールド | フロントエンドでの用途 |
|---|---|---|
| `session_started` | `session_id`, `project_id`, `trace_id` | セッションコンテキストの初期化 |
| `task_started` | `session_id`, `task_run_id`, `user_message` | タスク開始のマーキング |
| `task_progress` | `session_id`, `task_run_id`, `node_name`, `progress`, `message` | プログレスバー、ステージ説明 |
| `node_completed` | `session_id`, `task_run_id`, `node_name`, `progress` | ノード完了軌跡 |
| `tool_started` | `session_id`, `task_run_id`, `tool_name`, `title`, `detail`, `step_id`, `route_id` | ランタイムイベントパネル（ツール開始） |
| `tool_completed` | `session_id`, `task_run_id`, `tool_name`, `title`, `detail`, `step_id`, `route_id`, `status_code` | ランタイムイベントパネル（ツール完了） |
| `token_emitted` | `session_id`, `task_run_id`, `token` | AI 本文のストリーミング出力 |
| `thought_emitted` | `session_id`, `task_run_id`, `token` | AI 思考プロセスのストリーミング出力 |
| `agentic_iteration` | `session_id`, `task_run_id`, `iteration`, `think` | マルチターン推論進捗 |
| `write_approval_required` | `session_id`, `task_run_id`, `batch_id`, `items[]`, `write_id`, `route_id`, `method`, `path`, `parameters`, `reasoning`, `safety_level` | 承認パネルのレンダリング |
| `approval_pending` | `session_id`, `task_run_id` | グラフ実行一時停止、ユーザー判定待ち |
| `ui_block_emitted` | `session_id`, `task_run_id`, `block_index`, `block_type`, `block_data` | ホワイトリスト UI Block のレンダリング |
| `task_completed` | `session_id`, `task_run_id`, `summary` | 終了状態とサマリー |
| `error` | `session_id`, `task_run_id`, `error_code`, `error_message`, `details` | エラー表示とリカバリ |

### 4.3 イベント詳細 Schema

#### `session_started`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `project_id` | `string` | プロジェクト ID |
| `trace_id` | `string` | トレース ID |

#### `task_started`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |
| `user_message` | `string` | ユーザーの元メッセージ |

#### `task_progress`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |
| `node_name` | `string` | 現在のノード名 |
| `progress` | `float` | 進捗値（0.0-1.0） |
| `message` | `string \| null` | 進捗メッセージ |

#### `node_completed`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |
| `node_name` | `string` | ノード名 |
| `progress` | `float` | 進捗値 |

#### `tool_started`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |
| `tool_name` | `string` | ツール名 |
| `title` | `string` | イベントタイトル |
| `detail` | `string \| null` | 詳細情報 |
| `step_id` | `string \| null` | ステップ ID |
| `route_id` | `string \| null` | ルート ID |

#### `tool_completed`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |
| `tool_name` | `string` | ツール名 |
| `title` | `string` | イベントタイトル |
| `detail` | `string \| null` | 詳細情報 |
| `step_id` | `string \| null` | ステップ ID |
| `route_id` | `string \| null` | ルート ID |
| `status_code` | `int \| null` | HTTP ステータスコード |

#### `token_emitted`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |
| `token` | `string` | Token 内容（フロントエンドで連結が必要） |

#### `thought_emitted`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |
| `token` | `string` | 思考 Token 内容（フロントエンドで連結が必要） |

#### `agentic_iteration`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |
| `iteration` | `int` | 現在のターン（1 から開始） |
| `think` | `string \| null` | 今ターンの AI 推論サマリー |

#### `write_approval_required`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |
| `batch_id` | `string \| null` | バッチ承認タスク ID |
| `items` | `object[]` | 操作項目リスト（各項目に `write_id`、`method`、`path`、`parameters`、`reasoning`、`safety_level` を含む） |
| `write_id` | `string \| null` | 単一操作 ID（後方互換） |
| `route_id` | `string \| null` | インターフェースルート（後方互換） |
| `method` | `string \| null` | HTTP メソッド（後方互換） |
| `path` | `string \| null` | インターフェースパス（後方互換） |
| `parameters` | `object` | リクエストパラメータ（後方互換） |
| `reasoning` | `string` | AI がこのライトを実行する理由（後方互換） |
| `safety_level` | `string` | セキュリティレベル（後方互換）：`soft_write`、`hard_write`、`critical` |

#### `approval_pending`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |

#### `ui_block_emitted`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |
| `block_index` | `int` | Block シリアル番号（0 から開始） |
| `block_type` | `string` | Block タイプ。[第 5 節 UI Block ホワイトリスト](#5-ui-block-ホワイトリスト)を参照 |
| `block_data` | `object` | Block データ（構造は block_type により異なる） |

#### `task_completed`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string` | セッション ID |
| `task_run_id` | `string` | タスク実行 ID |
| `summary` | `string \| null` | タスクサマリー |

#### `error`

| フィールド | 型 | 説明 |
|---|---|---|
| `session_id` | `string \| null` | セッション ID |
| `task_run_id` | `string \| null` | タスク実行 ID |
| `error_code` | `string` | エラーコード。例：`TASK_FAILED`、`TASK_CANCELLED`、`STREAM_ERROR` |
| `error_message` | `string` | エラーメッセージ |
| `details` | `object \| null` | 詳細情報 |

---

## 5. UI Block ホワイトリスト

カスタム GUI は以下の 8 種類の `block_type` のレンダラーを実装するだけでよい：

| block_type | 説明 | 主要フィールド |
|---|---|---|
| `text_block` | テキスト回答 | `content`（テキスト内容）、`format`（`plain` / `markdown`） |
| `metric_card` | メトリクスカード | `title`、`metrics[]`（各項目に `label`、`value`、`unit`、`trend`、`trend_value`） |
| `data_table` | ページング対応データテーブル | `title`、`columns[]`（`key`、`label`、`type` を含む）、`rows[]`、`total`、`page`、`page_size` |
| `echart_card` | ECharts チャート | `title`、`chart_type`（`bar`/`line`/`pie`/`scatter`/`radar`/`gauge`）、`option`（ECharts 設定）、`height` |
| `confirm_panel` | 承認パネル | `approval_id`、`title`、`description`、`action_summary`、`risk_level`、`details[]`、`timeout_seconds` |
| `filter_form` | パラメータフォーム | `title`、`description`、`fields[]`（`key`、`label`、`type`、`required`、`options` を含む）、`session_id`、`request_id` |
| `timeline_card` | タイムライン | `title`、`events[]`（`timestamp`、`title`、`description`、`status` を含む） |
| `diff_card` | 差分比較 | `title`、`description`、`items[]`（`key`、`old_value`、`new_value`、`change_type` を含む） |

---

## 6. SSE 生フレーム例

### 6.1 `token_emitted` イベント

```text
event: token_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","token":"根据"}

event: token_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","token":"您提供的条件"}

event: token_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","token":"，已为您筛选出 5 条记录。"}
```

### 6.2 `task_progress` イベント

```text
event: task_progress
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","node_name":"agentic_loop","progress":0.35,"message":"正在调用订单查询接口"}
```

### 6.3 `write_approval_required` イベント

```text
event: write_approval_required
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","batch_id":"batch-001","items":[{"write_id":"w-001","method":"POST","path":"/api/orders/approve","parameters":{"order_id":"ORD-2024"},"reasoning":"批量审批待处理订单","safety_level":"hard_write"},{"write_id":"w-002","method":"POST","path":"/api/orders/approve","parameters":{"order_id":"ORD-2025"},"reasoning":"批量审批待处理订单","safety_level":"hard_write"}],"write_id":null,"route_id":null,"method":null,"path":null,"parameters":{},"reasoning":"","safety_level":"soft_write"}
```

### 6.4 `ui_block_emitted` イベント（data_table タイプ）

```text
event: ui_block_emitted
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","block_index":0,"block_type":"data_table","block_data":{"block_type":"data_table","title":"待审批订单","columns":[{"key":"order_id","label":"订单号","type":"text"},{"key":"amount","label":"金额","type":"number","sortable":true},{"key":"status","label":"状态","type":"tag"}],"rows":[{"order_id":"ORD-2024","amount":1500.00,"status":"pending"},{"order_id":"ORD-2025","amount":2300.50,"status":"pending"}],"total":2,"page":1,"page_size":10}}
```

### 6.5 `task_completed` イベント

```text
event: task_completed
data: {"session_id":"a1b2c3","task_run_id":"d4e5f6","summary":"已完成订单查询和排序，共筛选出 5 条待审批订单，按金额从高到低排列。2 条订单已提交审批请求，等待确认。"}
```

---

## 7. 最小統合フロー

```
┌────────────┐    POST /stream     ┌────────────┐
│  カスタムGUI │ ──────────────────→ │  LUI Server │
│            │ ←── SSE イベントストリーム ── │            │
│            │    (token/progress/  │            │
│            │     block/approval)  │            │
└─────┬──────┘                     └────────────┘
      │
      │ write_approval_required
      │ + approval_pending を受信
      ▼
┌────────────┐    POST /resume     ┌────────────┐
│  承認 UI    │ ──────────────────→ │  LUI Server │
│            │ ←── SSE イベントストリーム ── │            │
└────────────┘                     └────────────┘
```

**手順**

1. **会話開始** — `POST /api/chat/stream` に `project_id + content`（オプション：`session_id`、`locale`）を送信。
2. **SSE ストリームの消費** — `event` タイプに応じてディスパッチ：
   - `token_emitted` / `thought_emitted` → 本文／思考エリアに連結してレンダリング
   - `task_progress` / `tool_*` / `node_completed` → 実行進捗と呼び出し軌跡をレンダリング
   - `ui_block_emitted` → `block_type` に応じた対応コンポーネントをレンダリング
   - `error` → エラー表示
3. **承認処理** — `write_approval_required` + `approval_pending` 受信時：
   - 承認 UI をレンダリングし、操作項目を表示
   - ユーザー判定後に `POST /api/chat/resume`（`action` + `approved_ids` + `decided_ids`）を呼び出し
   - 新しい SSE ストリームを受信し、レンダリングを継続
4. **タスク完了** — `task_completed` を受信すると、SSE ストリームは自動的にクローズ。
5. **履歴リプレイ** — メッセージ／タスク／承認／HTTP スナップショット API を呼び出して完全な履歴を読み取り可能。

---

## 8. 認証仕様

### 8.1 デュアルチャネル JWT 認証

LUI-for-All は 2 種類の JWT アイデンティティをサポートし、同一サーバー上のマルチプロジェクトエンドユーザー隔離シナリオに対応。

| JWT Subject | アイデンティティ | アクセス可能範囲 | 発行インターフェース |
|---|---|---|---|
| `lui-admin` | 管理者 | すべての `/api/*` エンドポイント | `POST /api/auth/setup` または `POST /api/auth/login` |
| `lui-user` | エンドユーザー | `/api/chat/*`、`/api/sessions/*`、`/api/projects/resolve-slug/*`、`/api/auth/me` | `POST /api/auth/user-login` |

### 8.2 JWT 伝送方式

| 方式 | フォーマット | 適用シナリオ |
|---|---|---|
| **Authorization Header** | `Authorization: Bearer <jwt>` | すべてのエンドポイント（推奨） |
| **Query Parameter** | `?token=<jwt>` | SSE エンドポイント（一部の SSE クライアントライブラリはカスタムヘッダー非対応） |

### 8.3 エンドユーザーログインフロー

1. フロントエンドは `GET /api/projects/resolve-slug/{slug}` でプロジェクト情報を取得（認証不要）。
2. ユーザーが `POST /api/auth/user-login` にクレデンシャルを送信。
3. バックエンドがクレデンシャルを検証し User JWT を発行。

**ログインリクエスト例**

```http
POST /api/auth/user-login
Content-Type: application/json

{
  "project_slug": "my-project",
  "username": "zhangsan",
  "password": "secret123"
}
```

**ログインレスポンス**

| フィールド | 型 | 説明 |
|---|---|---|
| `token` | `string` | User JWT |
| `project_id` | `string` | プロジェクト ID |
| `project_name` | `string` | プロジェクト名 |
| `project_slug` | `string` | プロジェクト slug |
| `role_profile_id` | `string` | ロールプロファイル ID |

### 8.4 User JWT Payload 構造

```json
{
  "sub": "lui-user",
  "project_id": "uuid",
  "project_slug": "my-project",
  "role_profile_id": "uuid",
  "username": "zhangsan",
  "iat": 1234567890,
  "exp": 1234567890
}
```

### 8.5 User JWT 権限境界

- User JWT は**自身のプロジェクト**のデータのみアクセス可能（バックエンドは `project_id` で検証）
- `POST /api/chat/stream` 呼び出し時、`project_id` は JWT 内の `project_id` と一致する必要がある
- バックエンドが `user_context` を自動注入し、Agentic Loop はユーザーのターゲットシステム token を優先使用して操作を実行
- 監査系エンドポイント（`task-runs/*` の GET インターフェース）は Admin JWT のみアクセス可能

### 8.6 認証不要エンドポイント

以下のエンドポイントは JWT ホワイトリストに登録されており、Token の提供は不要：

- `GET /health`
- `GET /docs`、`GET /redoc`、`GET /openapi.json`
- `GET /api/auth/status`
- `POST /api/auth/setup`
- `POST /api/auth/login`
- `POST /api/auth/user-login`
- `POST /api/auth/forgot-password-hint`

---

## 9. カスタム GUI 適用ガイドライン

| レイヤー | 実装ポイント |
|---|---|
| **イベントレイヤー** | 統一 SSE ディスパッチャーを実装し、`event` フィールドで各レンダリングモジュールにルーティング。Query Parameter 方式での Token 伝送（`?token=<jwt>`）をサポートし、すべての SSE クライアントライブラリに対応。 |
| **コンポーネントレイヤー** | 8 種類の `block_type` レンダラーを実装（第 5 節参照）。`text_block` と `data_table` が最もよく使われる 2 種類であり、優先的に実装。 |
| **承認レイヤー** | `write_approval_required` + `approval_pending` イベントペアを監視し、承認 UI をレンダリング。ユーザー判定後に `POST /api/chat/resume` を呼び出し。完全な監査記録のために `decided_ids` の伝送に注意。 |
| **リプレイレイヤー** | 4 種類のスナップショット API（`messages`、`task-runs`、`approvals`、`http-executions`）を接続し、セッション履歴リプレイと監査トレースを実装。 |
| **エラー処理** | `error` イベントを監視し、`error_code` に応じてリカバリ戦略を決定：`TASK_CANCELLED` は無視可能、`TASK_FAILED` / `STREAM_ERROR` はユーザーへの再試行促しが必要。 |
| **多言語対応** | `locale` パラメータで AI レスポンスの言語を制御。`zh-CN`、`en-US`、`ja-JP` をサポート。 |
