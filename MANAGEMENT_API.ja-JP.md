# 管理 API リファレンス

> 本文書では LUI-for-All の全管理 API エンドポイントについて説明します。チャット関連のエンドポイント（カスタム GUI 接続）については [Chat エンドポイント統合プロトコル](CHAT_ENDPOINT_INTEGRATION.md) を参照してください。

> ⚠️ すべての管理エンドポイントは Admin JWT 認証（`sub=lui-admin`）が必要です（特に明記されていない場合）。認証方法：`Authorization: Bearer <token>`。

---

## 目次

- [1. 認証](#1-認証)
- [2. プロジェクト管理](#2-プロジェクト管理)
- [3. ロールプロファイル](#3-ロールプロファイル)
- [4. 監査クエリ](#4-監査クエリ)
- [5. 承認管理](#5-承認管理)
- [6. システム設定](#6-システム設定)
- [7. LLM モデル管理](#7-llm-モデル管理)
- [8. 汎用エンドポイント](#8-汎用エンドポイント)
- [9. MCP プロトコルエンドポイント](#9-mcp-プロトコルエンドポイント)

---

## 1. 認証

ソースコード：`backend/app/api/auth.py`

### 1.1 エンドポイント一覧

| メソッド | パス | 認証 | 説明 |
|---|---|---|---|
| `GET` | `/api/auth/status` | なし | パスワードが設定済みか確認 |
| `POST` | `/api/auth/setup` | なし | 初回管理者パスワード設定、JWT 発行 |
| `POST` | `/api/auth/login` | なし | 管理者ログイン、JWT 発行 |
| `GET` | `/api/auth/forgot-password-hint` | なし | パスワード忘れのヒント |
| `POST` | `/api/auth/user-login` | なし | エンドユーザーログイン（対象システムで認証）、User JWT 発行 |

### 1.2 リクエスト/レスポンスモデル

| モデル | フィールド | 型 | 制約 | 説明 |
|---|---|---|---|---|
| `PasswordSetupRequest` | `password` | `string` | `min_length=8`、大文字・小文字・数字を含むこと | 管理者パスワード |
| `LoginRequest` | `password` | `string` | — | 管理者パスワード |
| `UserLoginRequest` | `project_slug` | `string` | 必須 | プロジェクト URL スラッグ |
| | `username` | `string` | 必須 | 対象システムのユーザー名 |
| | `password` | `string` | 必須 | 対象システムのパスワード |

**レスポンスモデル：**

| モデル | フィールド | 型 | 説明 |
|---|---|---|---|
| `AuthStatusResponse` | `password_set` | `bool` | パスワードが設定済みかどうか |
| `PasswordSetupResponse` | `token` | `string` | Admin JWT Token |
| `LoginResponse` | `token` | `string` | Admin JWT Token |
| `ForgotPasswordHintResponse` | `hint` | `string` | ヒントメッセージ |
| | `file_path` | `string` | パスワードファイルの相対パス |
| `UserLoginResponse` | `token` | `string` | User JWT Token |
| | `project_id` | `string` | プロジェクト ID |
| | `project_name` | `string` | プロジェクト名 |
| | `project_slug` | `string \| null` | プロジェクトスラッグ |
| | `role_profile_id` | `string \| null` | マッチしたロールプロファイル ID |

### 1.3 エンドポイント詳細説明

#### 1.3.1 認証状態の確認

`GET /api/auth/status`

- **認証**：なし
- **説明**：管理者パスワードが設定済みか確認する。フロントエンドはこれに基づいて「パスワード設定」または「ログイン」画面を表示する。
- **リクエストボディ**：なし
- **レスポンス**：

```json
{ "password_set": true }
```

#### 1.3.2 初回パスワード設定

`POST /api/auth/setup`

- **認証**：なし（パスワード未設定時のみ使用可能）
- **説明**：初回の管理者パスワードを設定し JWT を発行する。パスワードは8文字以上で、大文字・小文字・数字を含む必要がある。
- **リクエストボディ**：

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `password` | `string` | はい | パスワード（8文字以上、大文字小文字+数字） |

- **レスポンス**：

```json
{ "token": "eyJhbGciOiJIUzI1NiIs..." }
```

- **エラーコード**：
  - `409` — パスワードが既に設定済みで、重複設定不可
  - `422` — パスワード強度不足

#### 1.3.3 管理者ログイン

`POST /api/auth/login`

- **認証**：なし
- **説明**：管理者パスワードを検証し JWT を発行する。
- **リクエストボディ**：

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `password` | `string` | はい | 管理者パスワード |

- **レスポンス**：

```json
{ "token": "eyJhbGciOiJIUzI1NiIs..." }
```

- **エラーコード**：
  - `400` — パスワードがまだ設定されていない
  - `401` — パスワードが間違っている

#### 1.3.4 パスワード忘れのヒント

`GET /api/auth/forgot-password-hint`

- **認証**：なし
- **説明**：パスワードファイルのパスヒントを返す。ユーザーはサーバーにアクセスしてパスワードファイルを削除し、サービスを再起動するとパスワードを再設定できる。
- **リクエストボディ**：なし
- **レスポンス**：

```json
{
  "hint": "サーバーにアクセスしてパスワードファイルを削除し、サービスを再起動するとパスワードを再設定できます",
  "file_path": "workspace/password.txt"
}
```

#### 1.3.5 エンドユーザーログイン

`POST /api/auth/user-login`

- **認証**：なし
- **説明**：エンドユーザーが対象システムのログインインターフェースで資格情報を検証する。システムはプロジェクトに設定されたログインルートを呼び出し、成功後に User JWT を発行しロールプロファイルをマッチングする。
- **リクエストボディ**：

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `project_slug` | `string` | はい | プロジェクト URL スラッグ |
| `username` | `string` | はい | 対象システムのユーザー名 |
| `password` | `string` | はい | 対象システムのパスワード |

- **レスポンス**：

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "project_name": "サンプルプロジェクト",
  "project_slug": "my-app",
  "role_profile_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

- **エラーコード**：
  - `400` — プロジェクトにログインインターフェースが未設定
  - `403` — プロジェクトがユーザーログインを許可していない、またはロールプロファイルが未設定
  - `404` — プロジェクトが存在しない
  - `401` — ユーザー名またはパスワードが間違っている
  - `502` — 対象システムへの接続に失敗
  - `500` — ログイン成功だが対象システムのトークンを取得できなかった

---

## 2. プロジェクト管理

ソースコード：`backend/app/api/projects.py`

### 2.1 エンドポイント一覧

| メソッド | パス | 認証 | 説明 |
|---|---|---|---|
| `GET` | `/api/projects/` | Admin | 全プロジェクトの一覧取得 |
| `POST` | `/api/projects/import` | Admin | 新規プロジェクトのインポート |
| `PATCH` | `/api/projects/{project_id}` | Admin | プロジェクト情報の変更 |
| `DELETE` | `/api/projects/{project_id}` | Admin | プロジェクトの削除 |
| `GET` | `/api/projects/resolve-slug/{slug}` | なし | URL スラッグをプロジェクト情報に解決（公開エンドポイント） |
| `POST` | `/api/projects/verify-source-path` | Admin | ソースコードパスの到達可能性検証 |
| `POST` | `/api/projects/test-connection` | Admin | 接続テスト |
| `POST` | `/api/projects/fetch-routes` | Admin | ルート一覧の取得 |
| `POST` | `/api/projects/verify-login` | Admin | ログインインターフェースの検証 |
| `GET` | `/api/projects/import-presets` | Admin | インポートプリセットの取得 |
| `POST` | `/api/projects/{project_id}/discover` | Admin | プロジェクト発見のトリガー |
| `GET` | `/api/projects/{project_id}/status` | Admin | 発見状態の取得 |
| `GET` | `/api/projects/{project_id}/route-map` | Admin / User | ルートマップの取得 |
| `GET` | `/api/projects/{project_id}/capabilities` | Admin / User | ケーパビリティマップの取得 |
| `PATCH` | `/api/projects/{project_id}/capabilities/{capability_id}` | Admin | ケーパビリティ情報の変更 |

### 2.2 リクエスト/レスポンスモデル

**リクエストモデル：**

| モデル | フィールド | 型 | 制約 | 説明 |
|---|---|---|---|---|
| `ProjectImportRequest` | `name` | `string` | 必須 | プロジェクト名 |
| | `base_url` | `string` | 必須 | 対象システムのベースアドレス |
| | `openapi_url` | `string \| null` | 任意 | OpenAPI ドキュメントのアドレス |
| | `description` | `string \| null` | 任意 | プロジェクトの説明 |
| | `slug` | `string \| null` | 任意 | URL スラッグ。未指定時は自動生成 |
| | `username` | `string \| null` | 任意 | 対象システムのログインアカウント |
| | `password` | `string \| null` | 任意 | 対象システムのログインパスワード |
| | `login_route_id` | `string \| null` | 任意 | ログインインターフェースの route_id（例：`POST:/api/auth/login`） |
| | `login_field_username` | `string \| null` | デフォルト `"username"` | ログインインターフェースのユーザー名フィールド名 |
| | `login_field_password` | `string \| null` | デフォルト `"password"` | ログインインターフェースのパスワードフィールド名 |
| | `source_path` | `string` | 必須 | 対象プロジェクトのローカルソースコードディレクトリの絶対パス |
| `ProjectUpdateRequest` | `name` | `string \| null` | 任意 | プロジェクト名 |
| | `description` | `string \| null` | 任意 | プロジェクトの説明 |
| | `slug` | `string \| null` | 任意 | URL スラッグ |
| | `base_url` | `string \| null` | 任意 | ベースアドレス |
| | `user_login_enabled` | `bool \| null` | 任意 | エンドユーザーログインを許可するか |
| | `default_role_profile_id` | `string \| null` | 任意 | デフォルトのロールプロファイル ID |
| `FetchRoutesRequest` | `base_url` | `string` | 必須 | ベースアドレス |
| | `openapi_url` | `string \| null` | 任意 | OpenAPI ドキュメントのアドレス |
| | `source_path` | `string \| null` | 任意 | ソースコードパス |
| `VerifySourcePathRequest` | `source_path` | `string` | 必須 | ソースコードディレクトリの絶対パス |
| `TestConnectionRequest` | `base_url` | `string` | 必須 | ベースアドレス |
| | `openapi_url` | `string \| null` | 任意 | OpenAPI ドキュメントのアドレス |
| | `source_path` | `string \| null` | 任意 | ソースコードパス |
| `VerifyLoginRequest` | `base_url` | `string` | 必須 | ベースアドレス |
| | `login_route_id` | `string` | 必須 | ログインインターフェースの route_id |
| | `username` | `string` | 必須 | テスト用ユーザー名 |
| | `password` | `string` | 必須 | テスト用パスワード |
| | `body_field_username` | `string` | デフォルト `"username"` | ユーザー名フィールド名 |
| | `body_field_password` | `string` | デフォルト `"password"` | パスワードフィールド名 |
| `CapabilityUpdateRequest` | `permission_level` | `string \| null` | 任意 | 権限レベル |

### 2.3 エンドポイント詳細説明

#### 2.3.1 全プロジェクトの一覧取得

`GET /api/projects/`

- **認証**：Admin JWT
- **説明**：インポート済みの全プロジェクトを一覧表示する。
- **リクエストボディ**：なし
- **レスポンス**：

```json
{
  "projects": [
    {
      "id": "550e8400-...",
      "name": "サンプルプロジェクト",
      "slug": "my-app",
      "description": "...",
      "base_url": "http://localhost:8010",
      "discovery_status": "completed",
      "discovery_progress": 100,
      "discovery_message": "マッピング完了",
      "discovery_error": null,
      "model_version": null,
      "user_login_enabled": true,
      "default_role_profile_id": "...",
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 1
}
```

#### 2.3.2 新規プロジェクトのインポート

`POST /api/projects/import`

- **認証**：Admin JWT
- **説明**：新規プロジェクトをインポートする。ソースコードパスの到達可能性を自動検証し、スラッグ（未指定時）を生成し、プロジェクトレコードを作成する。
- **リクエストボディ**：`ProjectImportRequest`（2.2 参照）
- **レスポンス**：

```json
{
  "project_id": "550e8400-...",
  "name": "サンプルプロジェクト",
  "status": "pending"
}
```

- **エラーコード**：
  - `400` — ソースコードパスに到達不可能またはディレクトリではない

#### 2.3.3 プロジェクト情報の変更

`PATCH /api/projects/{project_id}`

- **認証**：Admin JWT
- **説明**：プロジェクト名、説明、スラッグ、ベースアドレス、ユーザーログインのオン/オフ、またはデフォルトロールプロファイルを変更する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |

- **リクエストボディ**：`ProjectUpdateRequest`（2.2 参照、全フィールド任意）
- **レスポンス**：

```json
{ "project_id": "550e8400-...", "status": "updated" }
```

- **エラーコード**：
  - `400` — スラッグが予約語を使用している
  - `404` — プロジェクトが存在しない
  - `409` — スラッグが他のプロジェクトに使用されている

#### 2.3.4 プロジェクトの削除

`DELETE /api/projects/{project_id}`

- **認証**：Admin JWT
- **説明**：プロジェクトとその全関連レコード（セッション、タスク、監査、ルートマップ、ケーパビリティマップなど）を削除する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |

- **レスポンス**：

```json
{ "project_id": "550e8400-...", "status": "deleted" }
```

#### 2.3.5 スラッグの解決

`GET /api/projects/resolve-slug/{slug}`

- **認証**：なし（公開エンドポイント）
- **説明**：URL スラッグをプロジェクト情報に解決する。フロントエンドのユーザーログインページ初期化に使用する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `slug` | `string` | プロジェクト URL スラッグ |

- **レスポンス**：

```json
{
  "project_id": "550e8400-...",
  "name": "サンプルプロジェクト",
  "slug": "my-app"
}
```

- **エラーコード**：
  - `403` — プロジェクトがユーザーログインを許可していない
  - `404` — プロジェクトが存在しない

#### 2.3.6 ソースコードパスの検証

`POST /api/projects/verify-source-path`

- **認証**：Admin JWT
- **説明**：ソースコードパスの到達可能性を検証し、構造化された診断情報を返す（Docker 環境の検知、フレームワーク検出を含む）。
- **リクエストボディ**：

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `source_path` | `string` | はい | ソースコードディレクトリの絶対パス |

- **レスポンス**：

```json
{
  "source_path": "/app/projects/my-app",
  "accessible": true,
  "is_directory": true,
  "readable": true,
  "framework_detected": "FastAPI",
  "adapter_name": "FastAPI",
  "available_adapters": ["FastAPI", "Express", "Flask"],
  "file_count": 42,
  "sample_files": ["main.py", "requirements.txt", ...],
  "running_in_container": true,
  "hint": null
}
```

#### 2.3.7 接続テスト

`POST /api/projects/test-connection`

- **認証**：Admin JWT
- **説明**：対象システムの接続性と OpenAPI ドキュメントの可用性をテストし、同時にソースコードパスの到達可能性を検出する。
- **リクエストボディ**：`TestConnectionRequest`（2.2 参照）
- **レスポンス**：

```json
{
  "status": "success",
  "message": "接続および OpenAPI 探索が利用可能です (http://localhost:8010/openapi.json)",
  "routes": [...],
  "source": "openapi",
  "source_path_info": { ... }
}
```

#### 2.3.8 ルート一覧の取得

`POST /api/projects/fetch-routes`

- **認証**：Admin JWT
- **説明**：OpenAPI アドレスまたはソースコードの AST からルート一覧を取得する。フロントエンドでのログインインターフェース選択に使用する。
- **リクエストボディ**：`FetchRoutesRequest`（2.2 参照）
- **レスポンス**：

```json
{
  "routes": [
    {
      "route_id": "POST:/api/auth/login",
      "method": "POST",
      "path": "/api/auth/login",
      "summary": "Login"
    }
  ],
  "source": "openapi",
  "warning": null
}
```

#### 2.3.9 ログインインターフェースの検証

`POST /api/projects/verify-login`

- **認証**：Admin JWT
- **説明**：提供された資格情報で対象システムのログインインターフェースを呼び出し、トークンを取得できるか検証する。
- **リクエストボディ**：`VerifyLoginRequest`（2.2 参照）
- **レスポンス**：

```json
{
  "success": true,
  "status_code": 200,
  "message": "ログイン成功、トークンをキャプチャしました"
}
```

#### 2.3.10 インポートプリセットの取得

`GET /api/projects/import-presets`

- **認証**：Admin JWT
- **説明**：フロントエンドでサンプルプロジェクトをクイックインポートするためのプリセット（FastAPI サンプル、Node サンプルなど）を返す。
- **リクエストボディ**：なし
- **レスポンス**：

```json
{
  "presets": [
    {
      "id": "sample-fastapi",
      "name": "FastAPI サンプル",
      "description": "ローカルの FastAPI サンプルアドレスとソースコードディレクトリを自動入力します。",
      "base_url": "http://localhost:8010",
      "openapi_url": "http://localhost:8010/openapi.json",
      "source_path": "...",
      "login_route_id": "POST:/api/auth/login",
      "username": "111",
      "password": "111111",
      "body_field_username": "username",
      "body_field_password": "password",
      "available": true
    }
  ]
}
```

#### 2.3.11 プロジェクト発見のトリガー

`POST /api/projects/{project_id}/discover`

- **認証**：Admin JWT
- **説明**：プロジェクトのケーパビリティマッピングプロセスをトリガーする（非同期実行）。既に実行中の場合は、現在の進捗を返す。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |

- **レスポンス**：

```json
{
  "project_id": "550e8400-...",
  "status": "in_progress",
  "progress": 0,
  "message": "プロジェクト発見タスクを開始しました"
}
```

#### 2.3.12 発見状態の取得

`GET /api/projects/{project_id}/status`

- **認証**：Admin JWT
- **説明**：プロジェクトの発見状態、進捗、ルート数、ケーパビリティ数を取得する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |

- **レスポンス**：

```json
{
  "project_id": "550e8400-...",
  "name": "サンプルプロジェクト",
  "slug": "my-app",
  "base_url": "http://localhost:8010",
  "status": "completed",
  "progress": 100,
  "progress_message": "マッピング完了",
  "route_count": 15,
  "capability_count": 8,
  "error": null
}
```

#### 2.3.13 ルートマップの取得

`GET /api/projects/{project_id}/route-map`

- **認証**：Admin JWT または User JWT
- **説明**：プロジェクトのルートマップを取得する。エンドユーザーにはそのロールプロファイルで到達可能なルートのみを返す。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |

- **レスポンス**：

```json
{
  "project_id": "550e8400-...",
  "version": 1,
  "routes": [...],
  "schemas": {...},
  "route_count": 15,
  "source": "openapi",
  "created_at": "2024-01-01T00:00:00"
}
```

#### 2.3.14 ケーパビリティマップの取得

`GET /api/projects/{project_id}/capabilities`

- **認証**：Admin JWT または User JWT
- **説明**：プロジェクトのケーパビリティマップを取得する。エンドユーザーには到達可能なケーパビリティのみを返す。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |

- **レスポンス**：

```json
{
  "project_id": "550e8400-...",
  "capabilities": [
    {
      "capability_id": "cap_001",
      "name": "ユーザー管理",
      "description": "...",
      "domain": "auth",
      "backed_by_routes": [...],
      "user_intent_examples": [...],
      "permission_level": "read",
      "safety_level": "readonly_safe",
      "data_sensitivity": "low",
      "requires_confirmation": false,
      "best_modalities": ["text"],
      "parameter_hints": {...},
      "ai_usage_guidelines": "...",
      "source_code_analysis": "..."
    }
  ],
  "total": 8
}
```

#### 2.3.15 ケーパビリティ情報の変更

`PATCH /api/projects/{project_id}/capabilities/{capability_id}`

- **認証**：Admin JWT
- **説明**：ケーパビリティの権限レベルなどの情報を変更する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |
| `capability_id` | `string` | ケーパビリティ ID |

- **リクエストボディ**：

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `permission_level` | `string \| null` | いいえ | 権限レベル |

- **レスポンス**：

```json
{ "capability_id": "cap_001", "status": "updated" }
```

---

## 3. ロールプロファイル

ソースコード：`backend/app/api/role_profiles.py`

### 3.1 エンドポイント一覧

| メソッド | パス | 認証 | 説明 |
|---|---|---|---|
| `GET` | `/api/projects/{project_id}/role-profiles` | Admin | プロジェクトの全ロールプロファイルを一覧表示 |
| `POST` | `/api/projects/{project_id}/role-profiles` | Admin | ロールプロファイルの作成と権限プローブのトリガー |
| `GET` | `/api/projects/{project_id}/role-profiles/{profile_id}` | Admin | ロールプロファイルの詳細表示 |
| `POST` | `/api/projects/{project_id}/role-profiles/{profile_id}/reprobe` | Admin | 権限プローブの再トリガー |
| `PATCH` | `/api/projects/{project_id}/role-profiles/{profile_id}/accessibility/{route_id:path}` | Admin | ルート到達可能性の手動修正 |
| `DELETE` | `/api/projects/{project_id}/role-profiles/{profile_id}` | Admin | ロールプロファイルの削除 |
| `PUT` | `/api/projects/{project_id}/default-role` | Admin | デフォルトロールプロファイルの設定 |

### 3.2 リクエスト/レスポンスモデル

| モデル | フィールド | 型 | 制約 | 説明 |
|---|---|---|---|---|
| `CreateRoleProfileRequest` | `name` | `string` | 必須 | ロール名（例：「一般ユーザー」「管理者」） |
| | `description` | `string \| null` | 任意 | ロールの説明 |
| | `probe_username` | `string` | 必須 | プローブ用の対象システムユーザー名 |
| | `probe_password` | `string` | 必須 | プローブ用の対象システムパスワード |
| `UpdateAccessibilityRequest` | `accessible` | `bool` | 必須 | 到達可能かどうか |
| `SetDefaultRoleRequest` | `role_profile_id` | `string \| null` | 必須 | ロールプロファイル ID。`null` でデフォルトを解除 |

### 3.3 エンドポイント詳細説明

#### 3.3.1 ロールプロファイルの一覧表示

`GET /api/projects/{project_id}/role-profiles`

- **認証**：Admin JWT
- **説明**：指定プロジェクトの全ロールプロファイルを一覧表示する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |

- **レスポンス**：

```json
{
  "profiles": [
    {
      "id": "...",
      "name": "一般ユーザー",
      "description": null,
      "probe_username": "user1",
      "probe_status": "completed",
      "probe_error": null,
      "route_count": 10,
      "accessible_count": 7,
      "is_default": true,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 1
}
```

#### 3.3.2 ロールプロファイルの作成

`POST /api/projects/{project_id}/role-profiles`

- **認証**：Admin JWT
- **説明**：ロールプロファイルを作成し、権限プローブを非同期でトリガーする。プロジェクトにはログインインターフェースが設定済みでなければならない。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |

- **リクエストボディ**：`CreateRoleProfileRequest`（3.2 参照）
- **レスポンス**：

```json
{
  "id": "...",
  "name": "一般ユーザー",
  "probe_status": "pending",
  "message": "ロールプロファイルが作成され、権限プローブが非同期で開始されました"
}
```

- **エラーコード**：
  - `400` — プロジェクトにログインインターフェースが未設定
  - `404` — プロジェクトが存在しない

#### 3.3.3 ロールプロファイルの詳細表示

`GET /api/projects/{project_id}/role-profiles/{profile_id}`

- **認証**：Admin JWT
- **説明**：ロールプロファイルの詳細を表示する。各ルートの到達可能性プローブ結果を含む。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |
| `profile_id` | `string` | ロールプロファイル ID |

- **レスポンス**：

```json
{
  "id": "...",
  "name": "一般ユーザー",
  "description": null,
  "probe_username": "user1",
  "probe_status": "completed",
  "probe_error": null,
  "route_count": 10,
  "accessible_count": 7,
  "accessibility": [
    {
      "id": "...",
      "route_id": "GET:/api/users",
      "accessible": true,
      "probe_status_code": 200,
      "probe_method": "auto",
      "manually_overridden": false,
      "updated_at": "2024-01-01T00:00:00"
    }
  ],
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

#### 3.3.4 権限プローブの再トリガー

`POST /api/projects/{project_id}/role-profiles/{profile_id}/reprobe`

- **認証**：Admin JWT
- **説明**：ロールプロファイルの権限プローブを再トリガーする。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |
| `profile_id` | `string` | ロールプロファイル ID |

- **レスポンス**：

```json
{
  "id": "...",
  "probe_status": "pending",
  "message": "権限プローブが再開されました"
}
```

- **エラーコード**：
  - `404` — ロールプロファイルが存在しない
  - `409` — プローブが実行中

#### 3.3.5 ルート到達可能性の手動修正

`PATCH /api/projects/{project_id}/role-profiles/{profile_id}/accessibility/{route_id:path}`

- **認証**：Admin JWT
- **説明**：単一ルートの到達可能性を手動で修正する。レコードが存在しない場合は作成する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |
| `profile_id` | `string` | ロールプロファイル ID |
| `route_id` | `string` | ルート ID（例：`GET:/api/users`） |

- **リクエストボディ**：

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `accessible` | `bool` | はい | 到達可能かどうか |

- **レスポンス**：

```json
{
  "route_id": "GET:/api/users",
  "accessible": true,
  "manually_overridden": true
}
```

#### 3.3.6 ロールプロファイルの削除

`DELETE /api/projects/{project_id}/role-profiles/{profile_id}`

- **認証**：Admin JWT
- **説明**：ロールプロファイルとその関連する到達可能性データを削除する。デフォルトプロファイルの場合はデフォルト参照を自動的に解除する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |
| `profile_id` | `string` | ロールプロファイル ID |

- **レスポンス**：

```json
{ "id": "...", "message": "ロールプロファイルが削除されました" }
```

#### 3.3.7 デフォルトロールプロファイルの設定

`PUT /api/projects/{project_id}/default-role`

- **認証**：Admin JWT
- **説明**：プロジェクトのデフォルトユーザーロールプロファイルを設定する。プローブ完了済みのプロファイルのみデフォルトに設定できる。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `project_id` | `string` | プロジェクト ID |

- **リクエストボディ**：

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `role_profile_id` | `string \| null` | はい | ロールプロファイル ID。`null` でデフォルトを解除 |

- **レスポンス**：

```json
{
  "project_id": "550e8400-...",
  "default_role_profile_id": "660e8400-..."
}
```

- **エラーコード**：
  - `400` — プロファイルのプローブが未完了
  - `404` — プロジェクトまたはロールプロファイルが存在しない

---

## 4. 監査クエリ

ソースコード：`backend/app/api/audit.py`

### 4.1 エンドポイント一覧

| メソッド | パス | 認証 | 説明 |
|---|---|---|---|
| `GET` | `/api/audit/task-runs` | Admin | タスク実行レコードの一覧取得 |
| `GET` | `/api/audit/task-runs/{task_run_id}` | Admin | タスク実行の詳細取得 |
| `GET` | `/api/audit/task-runs/{task_run_id}/events` | Admin | タスクイベント一覧の取得 |
| `GET` | `/api/audit/http-executions` | Admin | HTTP 実行レコードの一覧取得 |
| `GET` | `/api/audit/http-executions/{request_id}` | Admin | 単一 HTTP 実行レコードの取得 |
| `GET` | `/api/audit/approvals` | Admin | 承認操作レコードの一覧取得 |
| `GET` | `/api/audit/policy-verdicts` | Admin | ポリシー判定レコードの一覧取得 |
| `GET` | `/api/audit/model-calls` | Admin | モデル呼び出しレコードの一覧取得 |

### 4.2 エンドポイント詳細説明

#### 4.2.1 タスク実行レコードの一覧取得

`GET /api/audit/task-runs`

- **認証**：Admin JWT
- **説明**：タスク実行レコードを一覧表示する。プロジェクト、セッション、ステータスによるフィルタリングとページネーションをサポートする。
- **クエリパラメータ**：

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `project_id` | `string` | いいえ | プロジェクトでフィルタリング |
| `session_id` | `string` | いいえ | セッションでフィルタリング |
| `status` | `string` | いいえ | ステータスでフィルタリング |
| `limit` | `int` | いいえ | 1ページあたりの件数（デフォルト 50、最大 100） |
| `offset` | `int` | いいえ | オフセット（デフォルト 0） |

- **レスポンス**：

```json
{
  "task_runs": [
    {
      "id": "...",
      "session_id": "...",
      "project_id": "...",
      "user_message": "全ユーザーを表示",
      "normalized_intent": "list_users",
      "status": "completed",
      "summary_text": "ユーザー一覧の取得に成功しました...",
      "error": null,
      "trace_id": "...",
      "created_at": "2024-01-01T00:00:00",
      "completed_at": "2024-01-01T00:00:05"
    }
  ],
  "total": 50
}
```

#### 4.2.2 タスク実行の詳細取得

`GET /api/audit/task-runs/{task_run_id}`

- **認証**：Admin JWT
- **説明**：単一タスク実行の完全な詳細を取得する。計画、実行成果物、UI Block などを含む。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `task_run_id` | `string` | タスク実行 ID |

- **レスポンス**：

```json
{
  "id": "...",
  "session_id": "...",
  "project_id": "...",
  "user_message": "全ユーザーを表示",
  "normalized_intent": "list_users",
  "status": "completed",
  "plan": {...},
  "execution_artifacts": [...],
  "summary_text": "...",
  "ui_blocks": [...],
  "error": null,
  "trace_id": "...",
  "thread_id": "...",
  "checkpoint_id": "...",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:05",
  "completed_at": "2024-01-01T00:00:05"
}
```

#### 4.2.3 タスクイベント一覧の取得

`GET /api/audit/task-runs/{task_run_id}/events`

- **認証**：Admin JWT
- **説明**：タスクのイベントソーシング（Event Sourcing）リストを取得する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `task_run_id` | `string` | タスク実行 ID |

- **レスポンス**：

```json
{
  "events": [
    {
      "id": "...",
      "task_run_id": "...",
      "event_type": "tool_call",
      "payload": {...},
      "actor_type": "agent",
      "actor_id": "...",
      "trace_id": "...",
      "evidence_refs": [...],
      "ts": "2024-01-01T00:00:01"
    }
  ],
  "total": 5
}
```

#### 4.2.4 HTTP 実行レコードの一覧取得

`GET /api/audit/http-executions`

- **認証**：Admin JWT
- **説明**：HTTP 実行レコードを一覧表示する。プロジェクト、タスク、キーワードによるフィルタリングとページネーションをサポートする。
- **クエリパラメータ**：

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `project_id` | `string` | いいえ | プロジェクトでフィルタリング |
| `task_run_id` | `string` | いいえ | タスクでフィルタリング |
| `keyword` | `string` | いいえ | URL であいまい検索 |
| `limit` | `int` | いいえ | 1ページあたりの件数（デフォルト 50、最大 100） |
| `offset` | `int` | いいえ | オフセット |

- **レスポンス**：

```json
{
  "executions": [
    {
      "id": "...",
      "request_id": "...",
      "session_id": "...",
      "task_run_id": "...",
      "capability_id": "cap_001",
      "method": "GET",
      "url_redacted": "/api/users",
      "status_code": 200,
      "duration_ms": 120,
      "error": null,
      "created_at": "2024-01-01T00:00:01",
      "headers_redacted": "...",
      "request_body_redacted": null,
      "response_body_redacted": "...",
      "trace_id": "..."
    }
  ],
  "total": 100
}
```

#### 4.2.5 HTTP 実行レコードの詳細取得

`GET /api/audit/http-executions/{request_id}`

- **認証**：Admin JWT
- **説明**：単一 HTTP 実行レコードの完全な情報を取得する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `request_id` | `string` | リクエスト ID |

- **レスポンス**：一覧項目と同じ構造（4.2.4 参照）。

#### 4.2.6 承認操作レコードの一覧取得

`GET /api/audit/approvals`

- **認証**：Admin JWT
- **説明**：承認操作レコード（監査ログ）を一覧表示する。フィルタリングとページネーションをサポートする。
- **クエリパラメータ**：

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `project_id` | `string` | いいえ | プロジェクトでフィルタリング |
| `status` | `string` | いいえ | ステータスでフィルタリング |
| `keyword` | `string` | いいえ | キーワード検索 |
| `limit` | `int` | いいえ | 1ページあたりの件数（デフォルト 50、最大 100） |
| `offset` | `int` | いいえ | オフセット |

- **レスポンス**：

```json
{
  "approvals": [
    {
      "id": "...",
      "task_run_id": "...",
      "title": "DELETE /api/users/123",
      "action_summary": "DELETE /api/users/123  パラメータ: {...}",
      "risk_level": "hard_write",
      "status": "approved",
      "decided_at": "2024-01-01T00:05:00",
      "decided_by": "user",
      "decision_reason": "削除を確認しました",
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 10
}
```

#### 4.2.7 ポリシー判定レコードの一覧取得

`GET /api/audit/policy-verdicts`

- **認証**：Admin JWT
- **説明**：ポリシー判定レコードを一覧表示する。
- **クエリパラメータ**：

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `project_id` | `string` | いいえ | プロジェクトでフィルタリング |
| `task_run_id` | `string` | いいえ | タスクでフィルタリング |
| `action` | `string` | いいえ | アクションでフィルタリング |
| `limit` | `int` | いいえ | 1ページあたりの件数（デフォルト 50） |

- **レスポンス**：

```json
{
  "verdicts": [
    {
      "id": "...",
      "task_run_id": "...",
      "route_id": "POST:/api/orders",
      "capability_id": "cap_003",
      "action": "confirm",
      "safety_level": "soft_write",
      "permission_level": "write",
      "reasons": ["書き込み操作には確認が必要です"],
      "created_at": "2024-01-01T00:00:02"
    }
  ],
  "total": 5
}
```

#### 4.2.8 モデル呼び出しレコードの一覧取得

`GET /api/audit/model-calls`

- **認証**：Admin JWT
- **説明**：モデル呼び出しレコードを一覧表示する。
- **クエリパラメータ**：

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `project_id` | `string` | いいえ | プロジェクトでフィルタリング |
| `task_run_id` | `string` | いいえ | タスクでフィルタリング |
| `limit` | `int` | いいえ | 1ページあたりの件数（デフォルト 50） |

- **レスポンス**：

```json
{
  "model_calls": [
    {
      "id": "...",
      "task_run_id": "...",
      "trace_id": "...",
      "provider": "openai",
      "model_name": "gpt-4o",
      "latency_ms": 2500,
      "token_usage": {"prompt": 1200, "completion": 300},
      "parse_success": true,
      "created_at": "2024-01-01T00:00:01"
    }
  ],
  "total": 3
}
```

---

## 5. 承認管理

ソースコード：`backend/app/api/approvals.py`

### 5.1 エンドポイント一覧

| メソッド | パス | 認証 | 説明 |
|---|---|---|---|
| `GET` | `/api/approvals/` | Admin | 承認レコードの一覧取得 |
| `GET` | `/api/approvals/{approval_id}` | Admin | 承認の詳細取得 |
| `POST` | `/api/approvals/{approval_id}/approve` | Admin | 承認リクエストの承認 |
| `POST` | `/api/approvals/{approval_id}/reject` | Admin | 承認リクエストの拒否 |

### 5.2 リクエスト/レスポンスモデル

| モデル | フィールド | 型 | 説明 |
|---|---|---|---|
| `ApprovalDecisionRequest` | `reason` | `string \| null` | 決定理由 |
| `ApprovalResponse` | `approval_id` | `string` | 承認 ID |
| | `status` | `string` | 処理後のステータス |
| | `message` | `string` | 結果メッセージ |

### 5.3 エンドポイント詳細説明

#### 5.3.1 承認レコードの一覧取得

`GET /api/approvals/`

- **認証**：Admin JWT
- **説明**：承認レコードを一覧表示する。
- **クエリパラメータ**：

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `status` | `string` | いいえ | ステータスでフィルタリング（`pending`/`approved`/`rejected`/`timeout`） |
| `limit` | `int` | いいえ | 1ページあたりの件数（デフォルト 50） |

- **レスポンス**：

```json
{
  "approvals": [
    {
      "id": "...",
      "title": "DELETE /api/users/123",
      "risk_level": "hard_write",
      "status": "pending",
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 5
}
```

#### 5.3.2 承認の詳細取得

`GET /api/approvals/{approval_id}`

- **認証**：Admin JWT
- **説明**：承認レコードの完全な詳細を取得する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `approval_id` | `string` | 承認 ID |

- **レスポンス**：

```json
{
  "id": "...",
  "task_run_id": "...",
  "session_id": "...",
  "title": "DELETE /api/users/123",
  "description": "手動承認が必要な書き込み操作",
  "action_summary": "DELETE /api/users/123  パラメータ: {...}",
  "risk_level": "hard_write",
  "details": {...},
  "status": "pending",
  "timeout_seconds": 300,
  "expires_at": "2024-01-01T00:05:00",
  "decided_at": null,
  "decided_by": null,
  "decision_reason": null,
  "created_at": "2024-01-01T00:00:00"
}
```

#### 5.3.3 承認リクエストの承認

`POST /api/approvals/{approval_id}/approve`

- **認証**：Admin JWT
- **説明**：保留中の承認リクエストを承認する。処理済みまたはタイムアウトした承認は操作できない。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `approval_id` | `string` | 承認 ID |

- **リクエストボディ**：

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `reason` | `string \| null` | いいえ | 承認理由 |

- **レスポンス**：

```json
{
  "approval_id": "...",
  "status": "approved",
  "message": "承認が承認され、タスクは続行されます"
}
```

- **エラーコード**：
  - `400` — 承認は処理済みまたはタイムアウト済み
  - `404` — 承認レコードが存在しない

#### 5.3.4 承認リクエストの拒否

`POST /api/approvals/{approval_id}/reject`

- **認証**：Admin JWT
- **説明**：保留中の承認リクエストを拒否する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `approval_id` | `string` | 承認 ID |

- **リクエストボディ**：

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `reason` | `string \| null` | いいえ | 拒否理由 |

- **レスポンス**：

```json
{
  "approval_id": "...",
  "status": "rejected",
  "message": "承認が拒否され、タスクはキャンセルされます"
}
```

- **エラーコード**：5.3.3 と同様

---

## 6. システム設定

ソースコード：`backend/app/api/settings.py`

### 6.1 エンドポイント一覧

| メソッド | パス | 認証 | 説明 |
|---|---|---|---|
| `GET` | `/api/settings` | Admin | 現在のシステム設定を読み取り |
| `PUT` | `/api/settings` | Admin | システム設定の保存 |

### 6.2 リクエスト/レスポンスモデル

| モデル | フィールド | 型 | 制約 | 説明 |
|---|---|---|---|---|
| `SettingsPayload` | `mcp_api_token` | `string \| null` | 任意 | MCP API Token |
| | `safety_default_action` | `string \| null` | デフォルト `"confirm"` | グローバルデフォルトの承認アクション |
| `SettingsResponse` | `SettingsPayload` の全フィールドを継承 | | | |

### 6.3 エンドポイント詳細説明

#### 6.3.1 システム設定の読み取り

`GET /api/settings`

- **認証**：Admin JWT
- **説明**：現在のシステム設定を読み取る。
- **リクエストボディ**：なし
- **レスポンス**：

```json
{
  "mcp_api_token": "your-token-here",
  "safety_default_action": "confirm"
}
```

#### 6.3.2 システム設定の保存

`PUT /api/settings`

- **認証**：Admin JWT
- **説明**：システム設定を `workspace/.env` に保存し、即座に有効化する。
- **リクエストボディ**：

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `mcp_api_token` | `string \| null` | いいえ | MCP API Token（空の場合は更新しない） |
| `safety_default_action` | `string \| null` | いいえ | デフォルトの承認アクション（`"confirm"` または `"allow"`） |

- **レスポンス**：6.3.1 と同様

---

## 7. LLM モデル管理

ソースコード：`backend/app/api/llm_status.py`

### 7.1 エンドポイント一覧

| メソッド | パス | 認証 | 説明 |
|---|---|---|---|
| `GET` | `/api/llm-status/main` | Admin | メインモデル設定の読み取り |
| `PUT` | `/api/llm-status/main` | Admin | メインモデル設定の更新 |
| `GET` | `/api/llm-status/manager` | Admin | LLM マネージャースナップショットの取得 |
| `POST` | `/api/llm-status/manager/main-selection` | Admin | メインモデル選択の設定 |
| `POST` | `/api/llm-status/manager/platforms` | Admin | LLM プラットフォームの作成 |
| `PUT` | `/api/llm-status/manager/platforms/{platform_id}` | Admin | LLM プラットフォームの更新 |
| `DELETE` | `/api/llm-status/manager/platforms/{platform_id}` | Admin | LLM プラットフォームの削除 |
| `POST` | `/api/llm-status/manager/platforms/{platform_id}/models` | Admin | モデルの追加 |
| `PUT` | `/api/llm-status/manager/models/{model_id}` | Admin | モデルの更新 |
| `DELETE` | `/api/llm-status/manager/models/{model_id}` | Admin | モデルの削除 |
| `POST` | `/api/llm-status/manager/platforms/{platform_id}/probe-and-sync` | Admin | プラットフォームモデルのプローブと同期 |
| `POST` | `/api/llm-status/probe` | Admin | 利用可能なモデルのプローブ |
| `POST` | `/api/llm-status/test` | Admin | モデル接続テスト |
| `POST` | `/api/llm-status/speed-test` | Admin | ストリーミング速度テスト（SSE） |
| `GET` | `/api/llm-status/llm-key-status` | Admin | LLM_KEY 設定状態の確認 |
| `POST` | `/api/llm-status/set-llm-key` | Admin | マスターキーの設定 |

### 7.2 リクエスト/レスポンスモデル

| モデル | フィールド | 型 | 説明 |
|---|---|---|---|
| `MainModelConfig` | `llm_api_base` | `string` | API Base URL |
| | `llm_api_key` | `string` | API Key |
| | `llm_model_id` | `string` | モデル ID |
| | `llm_extra_body` | `string` | Extra Body JSON 文字列 |
| `MainSelectionPayload` | `platform_id` | `int` | プラットフォーム ID |
| | `model_id` | `int` | モデル ID |
| `PlatformCreatePayload` | `name` | `string` | プラットフォーム名 |
| | `base_url` | `string` | Base URL |
| | `api_key` | `string \| null` | API Key |
| `PlatformUpdatePayload` | `name` | `string \| null` | プラットフォーム名 |
| | `base_url` | `string \| null` | Base URL |
| | `api_key` | `string \| null` | API Key |
| | `update_api_key` | `bool` | API Key を更新するか（デフォルト `false`） |
| `ModelCreatePayload` | `model_name` | `string` | モデル名/ID |
| | `display_name` | `string \| null` | 表示名 |
| | `extra_body` | `string \| null` | Extra Body JSON 文字列 |
| `ModelUpdatePayload` | `model_name` | `string \| null` | モデル名/ID |
| | `display_name` | `string \| null` | 表示名 |
| | `extra_body` | `string \| null` | Extra Body JSON 文字列 |
| `LLMManagerSnapshot` | `selected_platform_id` | `int \| null` | 現在選択中のプラットフォーム ID |
| | `selected_model_id` | `int \| null` | 現在選択中のモデル ID |
| | `platforms` | `ManagedPlatform[]` | プラットフォーム一覧 |
| `ManagedPlatform` | `platform_id` | `int` | プラットフォーム ID |
| | `name` | `string` | プラットフォーム名 |
| | `base_url` | `string` | Base URL |
| | `api_key_set` | `bool` | API Key が設定済みかどうか |
| | `models` | `ManagedModel[]` | モデル一覧 |
| `ManagedModel` | `model_id` | `int` | モデル ID |
| | `model_name` | `string` | モデル名 |
| | `display_name` | `string` | 表示名 |
| | `extra_body` | `string` | Extra Body JSON 文字列 |
| `TestPayload` | `llm_api_base` | `string` | API Base URL |
| | `llm_api_key` | `string \| null` | API Key |
| | `llm_model_id` | `string` | モデル ID |
| | `llm_extra_body` | `string \| null` | Extra Body JSON 文字列 |
| `PlatformProbeSyncResult` | `snapshot` | `LLMManagerSnapshot` | スナップショット |
| | `probed` | `int` | プローブされたモデル数 |
| | `created` | `int` | 新規追加されたモデル数 |
| `LLMKeyPayload` | `key` | `string` | マスターキー（8文字以上） |

### 7.3 エンドポイント詳細説明

#### 7.3.1 メインモデル設定の読み取り

`GET /api/llm-status/main`

- **認証**：Admin JWT
- **説明**：現在のメインモデル（`main` 用途）の設定情報を読み取る。
- **リクエストボディ**：なし
- **レスポンス**：`MainModelConfig`

```json
{
  "llm_api_base": "https://api.openai.com/v1",
  "llm_api_key": "sk-...",
  "llm_model_id": "gpt-4o",
  "llm_extra_body": ""
}
```

#### 7.3.2 メインモデル設定の更新

`PUT /api/llm-status/main`

- **認証**：Admin JWT
- **説明**：メインモデル設定を更新する。プラットフォーム/モデルが存在しない場合はシステムプラットフォームとモデルを自動作成する。
- **リクエストボディ**：`MainModelConfig`
- **レスポンス**：更新後の `MainModelConfig`

#### 7.3.3 LLM マネージャースナップショットの取得

`GET /api/llm-status/manager`

- **認証**：Admin JWT
- **説明**：すべての LLM プラットフォームとモデルの完全なスナップショットを取得する。
- **リクエストボディ**：なし
- **レスポンス**：`LLMManagerSnapshot`

#### 7.3.4 メインモデル選択の設定

`POST /api/llm-status/manager/main-selection`

- **認証**：Admin JWT
- **説明**：既存のプラットフォームとモデルからメインモデルを選択する。
- **リクエストボディ**：`MainSelectionPayload`
- **レスポンス**：更新後の `LLMManagerSnapshot`

#### 7.3.5 LLM プラットフォームの作成

`POST /api/llm-status/manager/platforms`

- **認証**：Admin JWT
- **説明**：新しい LLM プラットフォームを作成する。
- **リクエストボディ**：`PlatformCreatePayload`
- **レスポンス**：更新後の `LLMManagerSnapshot`

#### 7.3.6 LLM プラットフォームの更新

`PUT /api/llm-status/manager/platforms/{platform_id}`

- **認証**：Admin JWT
- **説明**：LLM プラットフォームの名前、Base URL、または API Key を更新する。少なくとも1つの更新フィールドを提供する必要がある。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `platform_id` | `int` | プラットフォーム ID |

- **リクエストボディ**：`PlatformUpdatePayload`
- **レスポンス**：更新後の `LLMManagerSnapshot`

#### 7.3.7 LLM プラットフォームの削除

`DELETE /api/llm-status/manager/platforms/{platform_id}`

- **認証**：Admin JWT
- **説明**：指定されたシステムプラットフォームを無効化（ソフト削除）する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `platform_id` | `int` | プラットフォーム ID |

- **レスポンス**：更新後の `LLMManagerSnapshot`

#### 7.3.8 モデルの追加

`POST /api/llm-status/manager/platforms/{platform_id}/models`

- **認証**：Admin JWT
- **説明**：指定プラットフォームに新しいモデルを追加する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `platform_id` | `int` | プラットフォーム ID |

- **リクエストボディ**：`ModelCreatePayload`
- **レスポンス**：更新後の `LLMManagerSnapshot`

#### 7.3.9 モデルの更新

`PUT /api/llm-status/manager/models/{model_id}`

- **認証**：Admin JWT
- **説明**：モデルの名前、表示名、または Extra Body を更新する。少なくとも1つの更新フィールドを提供する必要がある。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `model_id` | `int` | モデル ID |

- **リクエストボディ**：`ModelUpdatePayload`
- **レスポンス**：更新後の `LLMManagerSnapshot`

#### 7.3.10 モデルの削除

`DELETE /api/llm-status/manager/models/{model_id}`

- **認証**：Admin JWT
- **説明**：指定されたモデルを無効化（ソフト削除）する。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `model_id` | `int` | モデル ID |

- **レスポンス**：更新後の `LLMManagerSnapshot`

#### 7.3.11 プラットフォームモデルのプローブと同期

`POST /api/llm-status/manager/platforms/{platform_id}/probe-and-sync`

- **認証**：Admin JWT
- **説明**：指定プラットフォームの利用可能なモデル一覧をプローブし、データベースに自動同期する（未存在のモデルのみ新規追加）。
- **パスパラメータ**：

| パラメータ | 型 | 説明 |
|---|---|---|
| `platform_id` | `int` | プラットフォーム ID |

- **レスポンス**：`PlatformProbeSyncResult`

```json
{
  "snapshot": { ... },
  "probed": 15,
  "created": 3
}
```

#### 7.3.12 利用可能なモデルのプローブ

`POST /api/llm-status/probe`

- **認証**：Admin JWT
- **説明**：提供された API Key を使用して、プラットフォームの利用可能なモデル一覧をプローブする。
- **リクエストボディ**：`TestPayload`
- **レスポンス**：

```json
{ "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"] }
```

#### 7.3.13 モデル接続テスト

`POST /api/llm-status/test`

- **認証**：Admin JWT
- **説明**：テストメッセージを送信してモデルの接続性を検証する。
- **リクエストボディ**：`TestPayload`
- **レスポンス**：

```json
{ "reply": "Hello! How can I help you?" }
```

#### 7.3.14 ストリーミング速度テスト

`POST /api/llm-status/speed-test`

- **認証**：Admin JWT
- **説明**：ストリーミング速度テストエンドポイント。SSE でリアルタイム速度データを返す。
- **リクエストボディ**：`TestPayload`
- **レスポンス**：`text/event-stream`（SSE）

```
data: {"chunk": "Hello", "tokens_per_second": 42.5, ...}
data: {"chunk": " world", "tokens_per_second": 45.0, ...}
data: [DONE]
```

#### 7.3.15 LLM_KEY 状態の確認

`GET /api/llm-status/llm-key-status`

- **認証**：Admin JWT
- **説明**：LLM_KEY マスターキーが設定済みか確認する。
- **リクエストボディ**：なし
- **レスポンス**：

```json
{ "configured": true }
```

#### 7.3.16 マスターキーの設定

`POST /api/llm-status/set-llm-key`

- **認証**：Admin JWT
- **説明**：LLM_KEY マスターキー（API Key 暗号化保存用）を設定または更新する。
- **リクエストボディ**：

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `key` | `string` | はい | マスターキー（8文字以上） |

- **レスポンス**：

```json
{ "ok": true }
```

- **エラーコード**：
  - `400` — マスターキーが空または長さ不足

---

## 8. 汎用エンドポイント

### 8.1 エンドポイント一覧

| メソッド | パス | 認証 | 説明 |
|---|---|---|---|
| `GET` | `/health` | なし | ヘルスチェック |

### 8.2 エンドポイント詳細説明

#### 8.2.1 ヘルスチェック

`GET /health`

- **認証**：なし
- **説明**：サービスの稼働状態を返す。Docker ヘルスチェックやロードバランサーの生存確認に使用する。
- **リクエストボディ**：なし
- **レスポンス**：

```json
{ "status": "ok" }
```

---

## 9. MCP プロトコルエンドポイント

ソースコード：`backend/app/mcp/server.py`、`backend/app/main.py`

### 9.1 接続方法

MCP エンドポイントは `/mcp` パスにマウントされ、[FastMCP](https://github.com/jlowin/fastmcp) の **Streamable HTTP** トランスポートプロトコルを使用する。

- **エンドポイントアドレス**：`POST /mcp/`
- **プロトコル**：MCP Streamable HTTP（JSON-RPC 2.0 ベース）
- **対応 MCP クライアント**：OpenClaw、Claude Desktop、Cursor など MCP プロトコルに対応した AI Agent

### 9.2 認証

環境変数 `LUI_MCP_API_TOKEN` で静的 Bearer Token を設定する。

- リクエストヘッダー：`Authorization: Bearer <token>`
- Token 未設定時、MCP エンドポイントは完全にブロックされる（401 を返す）
- Token は管理画面の「システム設定」ページで設定可能、または `workspace/.env` の `LUI_MCP_API_TOKEN` を直接設定

> ⚠️ **セキュリティの前提条件**：MCP モードは手動承認プロセスをスキップする。使用前に「システム設定」で「デフォルトアクション」を「すべて許可」（`safety_default_action=allow`）に切り替える必要がある。

### 9.3 利用可能な Tools

| Tool 名 | 説明 | 読み取り専用 |
|---|---|---|
| `list_projects` | インポート済みの全プロジェクトを一覧表示。ID、名前、説明、ケーパビリティ数を返す | ✅ |
| `get_project_capabilities` | プロジェクトのケーパビリティ一覧を取得。domain/safety_level/keyword でのフィルタリングとバッチ詳細クエリをサポート | ✅ |
| `chat` | 自然言語メッセージを送信し、内部 AI が実行して結果を返す | ❌ |
| `get_task_run_result` | task_run_id でタスク実行結果と成果物をクエリ | ✅ |
| `get_session_history` | 指定セッションの会話履歴を取得 | ✅ |

### 9.4 推奨ワークフロー

1. `list_projects` を呼び出して利用可能な `project_id` を取得
2. `get_project_capabilities` を呼び出してプロジェクトのケーパビリティ一覧を確認
3. `chat` を呼び出して自然言語指令を送信（マルチターン会話対応：`session_id` を渡してコンテキストを維持）
4. `get_task_run_result` を呼び出して過去のタスク詳細をクエリ
5. `get_session_history` を呼び出して会話ログを確認

### 9.5 MCP 設定例

**環境変数設定**（`workspace/.env`）：

```env
LUI_MCP_API_TOKEN=your-secret-token-here
LUI_SAFETY_DEFAULT_ACTION=allow
```

**Claude Desktop 設定例**（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "lui-for-all": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer your-secret-token-here"
      }
    }
  }
}
```
