# 管理 API 参考

> 本文档覆盖 LUI-for-All 的全部管理类 API 端点。聊天相关的端点（自定义 GUI 接入）请参见 [Chat 端点集成协议](CHAT_ENDPOINT_INTEGRATION.md)。

> ⚠️ 所有管理端点均需 Admin JWT 认证（`sub=lui-admin`），除特别标注外。认证方式：`Authorization: Bearer <token>`。

---

## 目录

- [1. 认证](#1-认证)
- [2. 项目管理](#2-项目管理)
- [3. 角色画像](#3-角色画像)
- [4. 审计查询](#4-审计查询)
- [5. 审批管理](#5-审批管理)
- [6. 系统设置](#6-系统设置)
- [7. LLM 模型管理](#7-llm-模型管理)
- [8. 通用端点](#8-通用端点)
- [9. MCP 协议端点](#9-mcp-协议端点)

---

## 1. 认证

源码：`backend/app/api/auth.py`

### 1.1 端点总览

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `GET` | `/api/auth/status` | 无 | 检查密码是否已设置 |
| `POST` | `/api/auth/setup` | 无 | 首次设置管理员密码，返回 JWT |
| `POST` | `/api/auth/login` | 无 | 管理员登录，返回 JWT |
| `GET` | `/api/auth/forgot-password-hint` | 无 | 忘记密码提示 |
| `POST` | `/api/auth/user-login` | 无 | 终端用户登录（通过目标系统验证），返回 User JWT |

### 1.2 请求/响应模型

| 模型 | 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|---|
| `PasswordSetupRequest` | `password` | `string` | `min_length=8`，需包含大小写字母和数字 | 管理员密码 |
| `LoginRequest` | `password` | `string` | — | 管理员密码 |
| `UserLoginRequest` | `project_slug` | `string` | 必填 | 项目 URL slug |
| | `username` | `string` | 必填 | 目标系统用户名 |
| | `password` | `string` | 必填 | 目标系统密码 |

**响应模型：**

| 模型 | 字段 | 类型 | 说明 |
|---|---|---|---|
| `AuthStatusResponse` | `password_set` | `bool` | 密码是否已设置 |
| `PasswordSetupResponse` | `token` | `string` | Admin JWT Token |
| `LoginResponse` | `token` | `string` | Admin JWT Token |
| `ForgotPasswordHintResponse` | `hint` | `string` | 提示信息 |
| | `file_path` | `string` | 密码文件相对路径 |
| `UserLoginResponse` | `token` | `string` | User JWT Token |
| | `project_id` | `string` | 项目 ID |
| | `project_name` | `string` | 项目名称 |
| | `project_slug` | `string \| null` | 项目 slug |
| | `role_profile_id` | `string \| null` | 匹配到的角色画像 ID |

### 1.3 端点详细说明

#### 1.3.1 检查认证状态

`GET /api/auth/status`

- **认证**：无
- **说明**：检查管理员密码是否已设置。前端据此决定显示「设置密码」或「登录」界面。
- **请求体**：无
- **响应**：

```json
{ "password_set": true }
```

#### 1.3.2 首次设置密码

`POST /api/auth/setup`

- **认证**：无（仅当密码未设置时可用）
- **说明**：首次设置管理员密码并签发 JWT。密码要求至少 8 位，必须包含大写字母、小写字母和数字。
- **请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `password` | `string` | 是 | 密码（至少 8 位，需大小写+数字） |

- **响应**：

```json
{ "token": "eyJhbGciOiJIUzI1NiIs..." }
```

- **错误码**：
  - `409` — 密码已设置，无法重复设置
  - `422` — 密码强度不足

#### 1.3.3 管理员登录

`POST /api/auth/login`

- **认证**：无
- **说明**：验证管理员密码并签发 JWT。
- **请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `password` | `string` | 是 | 管理员密码 |

- **响应**：

```json
{ "token": "eyJhbGciOiJIUzI1NiIs..." }
```

- **错误码**：
  - `400` — 密码尚未设置
  - `401` — 密码错误

#### 1.3.4 忘记密码提示

`GET /api/auth/forgot-password-hint`

- **认证**：无
- **说明**：返回密码文件路径提示。用户需前往服务器删除密码文件后重启服务，即可重新设置密码。
- **请求体**：无
- **响应**：

```json
{
  "hint": "请前往服务器删除密码文件后重启服务，即可重新设置密码",
  "file_path": "workspace/password.txt"
}
```

#### 1.3.5 终端用户登录

`POST /api/auth/user-login`

- **认证**：无
- **说明**：终端用户通过目标系统登录接口验证凭据。系统将调用项目配置的登录路由，成功后签发 User JWT 并匹配角色画像。
- **请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_slug` | `string` | 是 | 项目 URL slug |
| `username` | `string` | 是 | 目标系统用户名 |
| `password` | `string` | 是 | 目标系统密码 |

- **响应**：

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "project_name": "示例项目",
  "project_slug": "my-app",
  "role_profile_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

- **错误码**：
  - `400` — 项目未配置登录接口
  - `403` — 项目未开放用户登录，或未配置角色画像
  - `404` — 项目不存在
  - `401` — 用户名或密码错误
  - `502` — 目标系统连接失败
  - `500` — 登录成功但未获取到目标系统 token

---

## 2. 项目管理

源码：`backend/app/api/projects.py`

### 2.1 端点总览

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `GET` | `/api/projects/` | Admin | 列出所有项目 |
| `POST` | `/api/projects/import` | Admin | 导入新项目 |
| `PATCH` | `/api/projects/{project_id}` | Admin | 修改项目信息 |
| `DELETE` | `/api/projects/{project_id}` | Admin | 删除项目 |
| `GET` | `/api/projects/resolve-slug/{slug}` | 无 | 将 URL slug 解析为项目信息（公开端点） |
| `POST` | `/api/projects/verify-source-path` | Admin | 验证源码路径可达性 |
| `POST` | `/api/projects/test-connection` | Admin | 测试连通性 |
| `POST` | `/api/projects/fetch-routes` | Admin | 拉取路由列表 |
| `POST` | `/api/projects/verify-login` | Admin | 验证登录接口 |
| `GET` | `/api/projects/import-presets` | Admin | 获取导入预置项 |
| `POST` | `/api/projects/{project_id}/discover` | Admin | 触发项目发现 |
| `GET` | `/api/projects/{project_id}/status` | Admin | 获取发现状态 |
| `GET` | `/api/projects/{project_id}/route-map` | Admin / User | 获取路由地图 |
| `GET` | `/api/projects/{project_id}/capabilities` | Admin / User | 获取能力图谱 |
| `PATCH` | `/api/projects/{project_id}/capabilities/{capability_id}` | Admin | 修改能力信息 |

### 2.2 请求/响应模型

**请求模型：**

| 模型 | 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|---|
| `ProjectImportRequest` | `name` | `string` | 必填 | 项目名称 |
| | `base_url` | `string` | 必填 | 目标系统基地址 |
| | `openapi_url` | `string \| null` | 可选 | OpenAPI 文档地址 |
| | `description` | `string \| null` | 可选 | 项目描述 |
| | `slug` | `string \| null` | 可选 | URL slug，不填则自动生成 |
| | `username` | `string \| null` | 可选 | 目标系统登录账号 |
| | `password` | `string \| null` | 可选 | 目标系统登录密码 |
| | `login_route_id` | `string \| null` | 可选 | 登录接口 route_id（如 `POST:/api/auth/login`） |
| | `login_field_username` | `string \| null` | 默认 `"username"` | 登录接口用户名字段名 |
| | `login_field_password` | `string \| null` | 默认 `"password"` | 登录接口密码字段名 |
| | `source_path` | `string` | 必填 | 目标项目本地源码目录绝对路径 |
| `ProjectUpdateRequest` | `name` | `string \| null` | 可选 | 项目名称 |
| | `description` | `string \| null` | 可选 | 项目描述 |
| | `slug` | `string \| null` | 可选 | URL slug |
| | `base_url` | `string \| null` | 可选 | 基地址 |
| | `user_login_enabled` | `bool \| null` | 可选 | 是否开放终端用户登录 |
| | `default_role_profile_id` | `string \| null` | 可选 | 默认角色画像 ID |
| `FetchRoutesRequest` | `base_url` | `string` | 必填 | 基地址 |
| | `openapi_url` | `string \| null` | 可选 | OpenAPI 文档地址 |
| | `source_path` | `string \| null` | 可选 | 源码路径 |
| `VerifySourcePathRequest` | `source_path` | `string` | 必填 | 源码目录绝对路径 |
| `TestConnectionRequest` | `base_url` | `string` | 必填 | 基地址 |
| | `openapi_url` | `string \| null` | 可选 | OpenAPI 文档地址 |
| | `source_path` | `string \| null` | 可选 | 源码路径 |
| `VerifyLoginRequest` | `base_url` | `string` | 必填 | 基地址 |
| | `login_route_id` | `string` | 必填 | 登录接口 route_id |
| | `username` | `string` | 必填 | 测试用户名 |
| | `password` | `string` | 必填 | 测试密码 |
| | `body_field_username` | `string` | 默认 `"username"` | 用户名字段名 |
| | `body_field_password` | `string` | 默认 `"password"` | 密码字段名 |
| `CapabilityUpdateRequest` | `permission_level` | `string \| null` | 可选 | 权限级别 |

### 2.3 端点详细说明

#### 2.3.1 列出所有项目

`GET /api/projects/`

- **认证**：Admin JWT
- **说明**：列出所有已导入的项目。
- **请求体**：无
- **响应**：

```json
{
  "projects": [
    {
      "id": "550e8400-...",
      "name": "示例项目",
      "slug": "my-app",
      "description": "...",
      "base_url": "http://localhost:8010",
      "discovery_status": "completed",
      "discovery_progress": 100,
      "discovery_message": "建图完成",
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

#### 2.3.2 导入新项目

`POST /api/projects/import`

- **认证**：Admin JWT
- **说明**：导入新项目。自动验证源码路径可达性，生成 slug（如未指定），创建项目记录。
- **请求体**：`ProjectImportRequest`（见 2.2）
- **响应**：

```json
{
  "project_id": "550e8400-...",
  "name": "示例项目",
  "status": "pending"
}
```

- **错误码**：
  - `400` — 源码路径不可达或不是目录

#### 2.3.3 修改项目信息

`PATCH /api/projects/{project_id}`

- **认证**：Admin JWT
- **说明**：修改项目名称、描述、slug、基地址、用户登录开关或默认角色画像。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |

- **请求体**：`ProjectUpdateRequest`（见 2.2，所有字段均可选）
- **响应**：

```json
{ "project_id": "550e8400-...", "status": "updated" }
```

- **错误码**：
  - `400` — slug 使用了保留名称
  - `404` — 项目不存在
  - `409` — slug 已被其他项目使用

#### 2.3.4 删除项目

`DELETE /api/projects/{project_id}`

- **认证**：Admin JWT
- **说明**：删除项目及其所有关联记录（会话、任务、审计、路由图、能力图谱等）。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |

- **响应**：

```json
{ "project_id": "550e8400-...", "status": "deleted" }
```

#### 2.3.5 解析 Slug

`GET /api/projects/resolve-slug/{slug}`

- **认证**：无（公开端点）
- **说明**：将 URL slug 解析为项目信息，供前端用户登录页初始化使用。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `slug` | `string` | 项目 URL slug |

- **响应**：

```json
{
  "project_id": "550e8400-...",
  "name": "示例项目",
  "slug": "my-app"
}
```

- **错误码**：
  - `403` — 项目未开放用户登录
  - `404` — 项目不存在

#### 2.3.6 验证源码路径

`POST /api/projects/verify-source-path`

- **认证**：Admin JWT
- **说明**：验证源码路径的可达性，返回结构化诊断信息（含 Docker 环境感知、框架检测）。
- **请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `source_path` | `string` | 是 | 源码目录绝对路径 |

- **响应**：

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

#### 2.3.7 测试连通性

`POST /api/projects/test-connection`

- **认证**：Admin JWT
- **说明**：测试目标系统的连通性和 OpenAPI 文档可用性，同时检测源码路径可达性。
- **请求体**：`TestConnectionRequest`（见 2.2）
- **响应**：

```json
{
  "status": "success",
  "message": "连接与 OpenAPI 探索可用 (http://localhost:8010/openapi.json)",
  "routes": [...],
  "source": "openapi",
  "source_path_info": { ... }
}
```

#### 2.3.8 拉取路由列表

`POST /api/projects/fetch-routes`

- **认证**：Admin JWT
- **说明**：从 OpenAPI 地址或源码 AST 拉取路由列表，供前端选择登录接口。
- **请求体**：`FetchRoutesRequest`（见 2.2）
- **响应**：

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

#### 2.3.9 验证登录接口

`POST /api/projects/verify-login`

- **认证**：Admin JWT
- **说明**：用提供的凭据调用目标系统登录接口，验证是否能拿到 token。
- **请求体**：`VerifyLoginRequest`（见 2.2）
- **响应**：

```json
{
  "success": true,
  "status_code": 200,
  "message": "登录成功，token 已捕获"
}
```

#### 2.3.10 获取导入预置项

`GET /api/projects/import-presets`

- **认证**：Admin JWT
- **说明**：返回用于前端快速导入示例项目的预置项（如 FastAPI 示例、Node 示例）。
- **请求体**：无
- **响应**：

```json
{
  "presets": [
    {
      "id": "sample-fastapi",
      "name": "FastAPI 示例",
      "description": "自动填充本机 FastAPI 示例地址与源码目录。",
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

#### 2.3.11 触发项目发现

`POST /api/projects/{project_id}/discover`

- **认证**：Admin JWT
- **说明**：触发项目的能力建图流程（异步执行）。若已在进行中，返回当前进度。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |

- **响应**：

```json
{
  "project_id": "550e8400-...",
  "status": "in_progress",
  "progress": 0,
  "message": "项目发现任务已启动"
}
```

#### 2.3.12 获取发现状态

`GET /api/projects/{project_id}/status`

- **认证**：Admin JWT
- **说明**：获取项目的发现状态、进度、路由和能力数量。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |

- **响应**：

```json
{
  "project_id": "550e8400-...",
  "name": "示例项目",
  "slug": "my-app",
  "base_url": "http://localhost:8010",
  "status": "completed",
  "progress": 100,
  "progress_message": "建图完成",
  "route_count": 15,
  "capability_count": 8,
  "error": null
}
```

#### 2.3.13 获取路由地图

`GET /api/projects/{project_id}/route-map`

- **认证**：Admin JWT 或 User JWT
- **说明**：获取项目的路由地图。终端用户仅返回其角色画像可达的路由。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |

- **响应**：

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

#### 2.3.14 获取能力图谱

`GET /api/projects/{project_id}/capabilities`

- **认证**：Admin JWT 或 User JWT
- **说明**：获取项目的能力图谱。终端用户仅返回其可达的能力。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |

- **响应**：

```json
{
  "project_id": "550e8400-...",
  "capabilities": [
    {
      "capability_id": "cap_001",
      "name": "用户管理",
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

#### 2.3.15 修改能力信息

`PATCH /api/projects/{project_id}/capabilities/{capability_id}`

- **认证**：Admin JWT
- **说明**：修改能力的权限级别等信息。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |
| `capability_id` | `string` | 能力 ID |

- **请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `permission_level` | `string \| null` | 否 | 权限级别 |

- **响应**：

```json
{ "capability_id": "cap_001", "status": "updated" }
```

---

## 3. 角色画像

源码：`backend/app/api/role_profiles.py`

### 3.1 端点总览

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `GET` | `/api/projects/{project_id}/role-profiles` | Admin | 列出项目的所有角色画像 |
| `POST` | `/api/projects/{project_id}/role-profiles` | Admin | 创建角色画像并触发权限探测 |
| `GET` | `/api/projects/{project_id}/role-profiles/{profile_id}` | Admin | 查看角色画像详情 |
| `POST` | `/api/projects/{project_id}/role-profiles/{profile_id}/reprobe` | Admin | 重新触发权限探测 |
| `PATCH` | `/api/projects/{project_id}/role-profiles/{profile_id}/accessibility/{route_id:path}` | Admin | 手动修正路由可达性 |
| `DELETE` | `/api/projects/{project_id}/role-profiles/{profile_id}` | Admin | 删除角色画像 |
| `PUT` | `/api/projects/{project_id}/default-role` | Admin | 设置默认角色画像 |

### 3.2 请求/响应模型

| 模型 | 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|---|
| `CreateRoleProfileRequest` | `name` | `string` | 必填 | 角色名（如「普通用户」「管理员」） |
| | `description` | `string \| null` | 可选 | 角色描述 |
| | `probe_username` | `string` | 必填 | 探测用的目标系统用户名 |
| | `probe_password` | `string` | 必填 | 探测用的目标系统密码 |
| `UpdateAccessibilityRequest` | `accessible` | `bool` | 必填 | 是否可达 |
| `SetDefaultRoleRequest` | `role_profile_id` | `string \| null` | 必填 | 角色画像 ID，`null` 表示取消默认 |

### 3.3 端点详细说明

#### 3.3.1 列出角色画像

`GET /api/projects/{project_id}/role-profiles`

- **认证**：Admin JWT
- **说明**：列出指定项目的所有角色画像。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |

- **响应**：

```json
{
  "profiles": [
    {
      "id": "...",
      "name": "普通用户",
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

#### 3.3.2 创建角色画像

`POST /api/projects/{project_id}/role-profiles`

- **认证**：Admin JWT
- **说明**：创建角色画像并异步触发权限探测。项目必须已配置登录接口。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |

- **请求体**：`CreateRoleProfileRequest`（见 3.2）
- **响应**：

```json
{
  "id": "...",
  "name": "普通用户",
  "probe_status": "pending",
  "message": "角色画像已创建，权限探测已异步启动"
}
```

- **错误码**：
  - `400` — 项目未配置登录接口
  - `404` — 项目不存在

#### 3.3.3 查看角色画像详情

`GET /api/projects/{project_id}/role-profiles/{profile_id}`

- **认证**：Admin JWT
- **说明**：查看角色画像详情，包含每条路由的可达性探测结果。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |
| `profile_id` | `string` | 角色画像 ID |

- **响应**：

```json
{
  "id": "...",
  "name": "普通用户",
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

#### 3.3.4 重新触发权限探测

`POST /api/projects/{project_id}/role-profiles/{profile_id}/reprobe`

- **认证**：Admin JWT
- **说明**：重新触发角色画像的权限探测。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |
| `profile_id` | `string` | 角色画像 ID |

- **响应**：

```json
{
  "id": "...",
  "probe_status": "pending",
  "message": "权限探测已重新启动"
}
```

- **错误码**：
  - `404` — 角色画像不存在
  - `409` — 探测正在进行中

#### 3.3.5 手动修正路由可达性

`PATCH /api/projects/{project_id}/role-profiles/{profile_id}/accessibility/{route_id:path}`

- **认证**：Admin JWT
- **说明**：手动修正单条路由的可达性。若记录不存在则创建。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |
| `profile_id` | `string` | 角色画像 ID |
| `route_id` | `string` | 路由 ID（如 `GET:/api/users`） |

- **请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `accessible` | `bool` | 是 | 是否可达 |

- **响应**：

```json
{
  "route_id": "GET:/api/users",
  "accessible": true,
  "manually_overridden": true
}
```

#### 3.3.6 删除角色画像

`DELETE /api/projects/{project_id}/role-profiles/{profile_id}`

- **认证**：Admin JWT
- **说明**：删除角色画像及其关联的可达性数据。若为默认画像则自动清除默认引用。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |
| `profile_id` | `string` | 角色画像 ID |

- **响应**：

```json
{ "id": "...", "message": "角色画像已删除" }
```

#### 3.3.7 设置默认角色画像

`PUT /api/projects/{project_id}/default-role`

- **认证**：Admin JWT
- **说明**：设置项目的默认用户角色画像。只能将已完成探测的画像设为默认。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `project_id` | `string` | 项目 ID |

- **请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `role_profile_id` | `string \| null` | 是 | 角色画像 ID，`null` 表示取消默认 |

- **响应**：

```json
{
  "project_id": "550e8400-...",
  "default_role_profile_id": "660e8400-..."
}
```

- **错误码**：
  - `400` — 画像未完成探测
  - `404` — 项目或角色画像不存在

---

## 4. 审计查询

源码：`backend/app/api/audit.py`

### 4.1 端点总览

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `GET` | `/api/audit/task-runs` | Admin | 列出任务运行记录 |
| `GET` | `/api/audit/task-runs/{task_run_id}` | Admin | 获取任务运行详情 |
| `GET` | `/api/audit/task-runs/{task_run_id}/events` | Admin | 获取任务事件列表 |
| `GET` | `/api/audit/http-executions` | Admin | 列出 HTTP 执行记录 |
| `GET` | `/api/audit/http-executions/{request_id}` | Admin | 获取单条 HTTP 执行记录 |
| `GET` | `/api/audit/approvals` | Admin | 列出审批操作记录 |
| `GET` | `/api/audit/policy-verdicts` | Admin | 列出策略判定记录 |
| `GET` | `/api/audit/model-calls` | Admin | 列出模型调用记录 |

### 4.2 端点详细说明

#### 4.2.1 列出任务运行记录

`GET /api/audit/task-runs`

- **认证**：Admin JWT
- **说明**：列出任务运行记录，支持按项目、会话、状态过滤和分页。
- **查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_id` | `string` | 否 | 按项目过滤 |
| `session_id` | `string` | 否 | 按会话过滤 |
| `status` | `string` | 否 | 按状态过滤 |
| `limit` | `int` | 否 | 每页条数（默认 50，最大 100） |
| `offset` | `int` | 否 | 偏移量（默认 0） |

- **响应**：

```json
{
  "task_runs": [
    {
      "id": "...",
      "session_id": "...",
      "project_id": "...",
      "user_message": "查看所有用户",
      "normalized_intent": "list_users",
      "status": "completed",
      "summary_text": "已成功获取用户列表...",
      "error": null,
      "trace_id": "...",
      "created_at": "2024-01-01T00:00:00",
      "completed_at": "2024-01-01T00:00:05"
    }
  ],
  "total": 50
}
```

#### 4.2.2 获取任务运行详情

`GET /api/audit/task-runs/{task_run_id}`

- **认证**：Admin JWT
- **说明**：获取单条任务运行的完整详情，包含计划、执行产物、UI Block 等。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `task_run_id` | `string` | 任务运行 ID |

- **响应**：

```json
{
  "id": "...",
  "session_id": "...",
  "project_id": "...",
  "user_message": "查看所有用户",
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

#### 4.2.3 获取任务事件列表

`GET /api/audit/task-runs/{task_run_id}/events`

- **认证**：Admin JWT
- **说明**：获取任务的事件溯源（Event Sourcing）列表。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `task_run_id` | `string` | 任务运行 ID |

- **响应**：

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

#### 4.2.4 列出 HTTP 执行记录

`GET /api/audit/http-executions`

- **认证**：Admin JWT
- **说明**：列出 HTTP 执行记录，支持按项目、任务、关键词过滤和分页。
- **查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_id` | `string` | 否 | 按项目过滤 |
| `task_run_id` | `string` | 否 | 按任务过滤 |
| `keyword` | `string` | 否 | 按 URL 模糊匹配 |
| `limit` | `int` | 否 | 每页条数（默认 50，最大 100） |
| `offset` | `int` | 否 | 偏移量 |

- **响应**：

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

#### 4.2.5 获取 HTTP 执行记录详情

`GET /api/audit/http-executions/{request_id}`

- **认证**：Admin JWT
- **说明**：获取单条 HTTP 执行记录的完整信息。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `request_id` | `string` | 请求 ID |

- **响应**：与列表项结构相同（见 4.2.4）。

#### 4.2.6 列出审批操作记录

`GET /api/audit/approvals`

- **认证**：Admin JWT
- **说明**：列出审批操作记录（审计日志），支持过滤和分页。
- **查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_id` | `string` | 否 | 按项目过滤 |
| `status` | `string` | 否 | 按状态过滤 |
| `keyword` | `string` | 否 | 关键词搜索 |
| `limit` | `int` | 否 | 每页条数（默认 50，最大 100） |
| `offset` | `int` | 否 | 偏移量 |

- **响应**：

```json
{
  "approvals": [
    {
      "id": "...",
      "task_run_id": "...",
      "title": "DELETE /api/users/123",
      "action_summary": "DELETE /api/users/123  参数: {...}",
      "risk_level": "hard_write",
      "status": "approved",
      "decided_at": "2024-01-01T00:05:00",
      "decided_by": "user",
      "decision_reason": "确认删除",
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 10
}
```

#### 4.2.7 列出策略判定记录

`GET /api/audit/policy-verdicts`

- **认证**：Admin JWT
- **说明**：列出策略判定记录。
- **查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_id` | `string` | 否 | 按项目过滤 |
| `task_run_id` | `string` | 否 | 按任务过滤 |
| `action` | `string` | 否 | 按动作过滤 |
| `limit` | `int` | 否 | 每页条数（默认 50） |

- **响应**：

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
      "reasons": ["写入操作需要确认"],
      "created_at": "2024-01-01T00:00:02"
    }
  ],
  "total": 5
}
```

#### 4.2.8 列出模型调用记录

`GET /api/audit/model-calls`

- **认证**：Admin JWT
- **说明**：列出模型调用记录。
- **查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_id` | `string` | 否 | 按项目过滤 |
| `task_run_id` | `string` | 否 | 按任务过滤 |
| `limit` | `int` | 否 | 每页条数（默认 50） |

- **响应**：

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

## 5. 审批管理

源码：`backend/app/api/approvals.py`

### 5.1 端点总览

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `GET` | `/api/approvals/` | Admin | 列出审批记录 |
| `GET` | `/api/approvals/{approval_id}` | Admin | 获取审批详情 |
| `POST` | `/api/approvals/{approval_id}/approve` | Admin | 批准审批请求 |
| `POST` | `/api/approvals/{approval_id}/reject` | Admin | 拒绝审批请求 |

### 5.2 请求/响应模型

| 模型 | 字段 | 类型 | 说明 |
|---|---|---|---|
| `ApprovalDecisionRequest` | `reason` | `string \| null` | 决策理由 |
| `ApprovalResponse` | `approval_id` | `string` | 审批 ID |
| | `status` | `string` | 处理后状态 |
| | `message` | `string` | 结果消息 |

### 5.3 端点详细说明

#### 5.3.1 列出审批记录

`GET /api/approvals/`

- **认证**：Admin JWT
- **说明**：列出审批记录。
- **查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `status` | `string` | 否 | 按状态过滤（`pending`/`approved`/`rejected`/`timeout`） |
| `limit` | `int` | 否 | 每页条数（默认 50） |

- **响应**：

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

#### 5.3.2 获取审批详情

`GET /api/approvals/{approval_id}`

- **认证**：Admin JWT
- **说明**：获取审批记录的完整详情。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `approval_id` | `string` | 审批 ID |

- **响应**：

```json
{
  "id": "...",
  "task_run_id": "...",
  "session_id": "...",
  "title": "DELETE /api/users/123",
  "description": "需要人工审批的写入操作",
  "action_summary": "DELETE /api/users/123  参数: {...}",
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

#### 5.3.3 批准审批请求

`POST /api/approvals/{approval_id}/approve`

- **认证**：Admin JWT
- **说明**：批准待处理的审批请求。已处理或已超时的审批无法操作。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `approval_id` | `string` | 审批 ID |

- **请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `reason` | `string \| null` | 否 | 批准理由 |

- **响应**：

```json
{
  "approval_id": "...",
  "status": "approved",
  "message": "审批已批准，任务将继续执行"
}
```

- **错误码**：
  - `400` — 审批已处理或已超时
  - `404` — 审批记录不存在

#### 5.3.4 拒绝审批请求

`POST /api/approvals/{approval_id}/reject`

- **认证**：Admin JWT
- **说明**：拒绝待处理的审批请求。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `approval_id` | `string` | 审批 ID |

- **请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `reason` | `string \| null` | 否 | 拒绝理由 |

- **响应**：

```json
{
  "approval_id": "...",
  "status": "rejected",
  "message": "审批已拒绝，任务将取消"
}
```

- **错误码**：同 5.3.3

---

## 6. 系统设置

源码：`backend/app/api/settings.py`

### 6.1 端点总览

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `GET` | `/api/settings` | Admin | 读取当前系统设置 |
| `PUT` | `/api/settings` | Admin | 保存系统设置 |

### 6.2 请求/响应模型

| 模型 | 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|---|
| `SettingsPayload` | `mcp_api_token` | `string \| null` | 可选 | MCP API Token |
| | `safety_default_action` | `string \| null` | 默认 `"confirm"` | 全局默认审批动作 |
| `SettingsResponse` | 继承 `SettingsPayload` 所有字段 | | | |

### 6.3 端点详细说明

#### 6.3.1 读取系统设置

`GET /api/settings`

- **认证**：Admin JWT
- **说明**：读取当前系统设置。
- **请求体**：无
- **响应**：

```json
{
  "mcp_api_token": "your-token-here",
  "safety_default_action": "confirm"
}
```

#### 6.3.2 保存系统设置

`PUT /api/settings`

- **认证**：Admin JWT
- **说明**：保存系统设置到 `workspace/.env`，立即生效。
- **请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `mcp_api_token` | `string \| null` | 否 | MCP API Token（留空则不更新） |
| `safety_default_action` | `string \| null` | 否 | 默认审批动作（`"confirm"` 或 `"allow"`） |

- **响应**：同 6.3.1

---

## 7. LLM 模型管理

源码：`backend/app/api/llm_status.py`

### 7.1 端点总览

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `GET` | `/api/llm-status/main` | Admin | 读取主模型配置 |
| `PUT` | `/api/llm-status/main` | Admin | 更新主模型配置 |
| `GET` | `/api/llm-status/manager` | Admin | 获取 LLM 管理器快照 |
| `POST` | `/api/llm-status/manager/main-selection` | Admin | 设置主模型选择 |
| `POST` | `/api/llm-status/manager/platforms` | Admin | 创建 LLM 平台 |
| `PUT` | `/api/llm-status/manager/platforms/{platform_id}` | Admin | 更新 LLM 平台 |
| `DELETE` | `/api/llm-status/manager/platforms/{platform_id}` | Admin | 删除 LLM 平台 |
| `POST` | `/api/llm-status/manager/platforms/{platform_id}/models` | Admin | 添加模型 |
| `PUT` | `/api/llm-status/manager/models/{model_id}` | Admin | 更新模型 |
| `DELETE` | `/api/llm-status/manager/models/{model_id}` | Admin | 删除模型 |
| `POST` | `/api/llm-status/manager/platforms/{platform_id}/probe-and-sync` | Admin | 探测并同步平台模型 |
| `POST` | `/api/llm-status/probe` | Admin | 探测可用模型 |
| `POST` | `/api/llm-status/test` | Admin | 测试模型连接 |
| `POST` | `/api/llm-status/speed-test` | Admin | 流式测速（SSE） |
| `GET` | `/api/llm-status/llm-key-status` | Admin | 检查 LLM_KEY 配置状态 |
| `POST` | `/api/llm-status/set-llm-key` | Admin | 设置主密钥 |

### 7.2 请求/响应模型

| 模型 | 字段 | 类型 | 说明 |
|---|---|---|---|
| `MainModelConfig` | `llm_api_base` | `string` | API Base URL |
| | `llm_api_key` | `string` | API Key |
| | `llm_model_id` | `string` | 模型 ID |
| | `llm_extra_body` | `string` | Extra Body JSON 字符串 |
| `MainSelectionPayload` | `platform_id` | `int` | 平台 ID |
| | `model_id` | `int` | 模型 ID |
| `PlatformCreatePayload` | `name` | `string` | 平台名称 |
| | `base_url` | `string` | Base URL |
| | `api_key` | `string \| null` | API Key |
| `PlatformUpdatePayload` | `name` | `string \| null` | 平台名称 |
| | `base_url` | `string \| null` | Base URL |
| | `api_key` | `string \| null` | API Key |
| | `update_api_key` | `bool` | 是否更新 API Key（默认 `false`） |
| `ModelCreatePayload` | `model_name` | `string` | 模型名称/ID |
| | `display_name` | `string \| null` | 显示名称 |
| | `extra_body` | `string \| null` | Extra Body JSON 字符串 |
| `ModelUpdatePayload` | `model_name` | `string \| null` | 模型名称/ID |
| | `display_name` | `string \| null` | 显示名称 |
| | `extra_body` | `string \| null` | Extra Body JSON 字符串 |
| `LLMManagerSnapshot` | `selected_platform_id` | `int \| null` | 当前选中的平台 ID |
| | `selected_model_id` | `int \| null` | 当前选中的模型 ID |
| | `platforms` | `ManagedPlatform[]` | 平台列表 |
| `ManagedPlatform` | `platform_id` | `int` | 平台 ID |
| | `name` | `string` | 平台名称 |
| | `base_url` | `string` | Base URL |
| | `api_key_set` | `bool` | API Key 是否已配置 |
| | `models` | `ManagedModel[]` | 模型列表 |
| `ManagedModel` | `model_id` | `int` | 模型 ID |
| | `model_name` | `string` | 模型名称 |
| | `display_name` | `string` | 显示名称 |
| | `extra_body` | `string` | Extra Body JSON 字符串 |
| `TestPayload` | `llm_api_base` | `string` | API Base URL |
| | `llm_api_key` | `string \| null` | API Key |
| | `llm_model_id` | `string` | 模型 ID |
| | `llm_extra_body` | `string \| null` | Extra Body JSON 字符串 |
| `PlatformProbeSyncResult` | `snapshot` | `LLMManagerSnapshot` | 快照 |
| | `probed` | `int` | 探测到的模型数 |
| | `created` | `int` | 新增的模型数 |
| `LLMKeyPayload` | `key` | `string` | 主密钥（至少 8 位） |

### 7.3 端点详细说明

#### 7.3.1 读取主模型配置

`GET /api/llm-status/main`

- **认证**：Admin JWT
- **说明**：读取当前主模型（`main` 用途）的配置信息。
- **请求体**：无
- **响应**：`MainModelConfig`

```json
{
  "llm_api_base": "https://api.openai.com/v1",
  "llm_api_key": "sk-...",
  "llm_model_id": "gpt-4o",
  "llm_extra_body": ""
}
```

#### 7.3.2 更新主模型配置

`PUT /api/llm-status/main`

- **认证**：Admin JWT
- **说明**：更新主模型配置。若平台/模型不存在则自动创建系统平台和模型。
- **请求体**：`MainModelConfig`
- **响应**：更新后的 `MainModelConfig`

#### 7.3.3 获取 LLM 管理器快照

`GET /api/llm-status/manager`

- **认证**：Admin JWT
- **说明**：获取所有 LLM 平台和模型的完整快照。
- **请求体**：无
- **响应**：`LLMManagerSnapshot`

#### 7.3.4 设置主模型选择

`POST /api/llm-status/manager/main-selection`

- **认证**：Admin JWT
- **说明**：从已有平台和模型中选择主模型。
- **请求体**：`MainSelectionPayload`
- **响应**：更新后的 `LLMManagerSnapshot`

#### 7.3.5 创建 LLM 平台

`POST /api/llm-status/manager/platforms`

- **认证**：Admin JWT
- **说明**：创建新的 LLM 平台。
- **请求体**：`PlatformCreatePayload`
- **响应**：更新后的 `LLMManagerSnapshot`

#### 7.3.6 更新 LLM 平台

`PUT /api/llm-status/manager/platforms/{platform_id}`

- **认证**：Admin JWT
- **说明**：更新 LLM 平台的名称、Base URL 或 API Key。需至少提供一个更新字段。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `platform_id` | `int` | 平台 ID |

- **请求体**：`PlatformUpdatePayload`
- **响应**：更新后的 `LLMManagerSnapshot`

#### 7.3.7 删除 LLM 平台

`DELETE /api/llm-status/manager/platforms/{platform_id}`

- **认证**：Admin JWT
- **说明**：禁用（软删除）指定的系统平台。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `platform_id` | `int` | 平台 ID |

- **响应**：更新后的 `LLMManagerSnapshot`

#### 7.3.8 添加模型

`POST /api/llm-status/manager/platforms/{platform_id}/models`

- **认证**：Admin JWT
- **说明**：向指定平台添加新模型。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `platform_id` | `int` | 平台 ID |

- **请求体**：`ModelCreatePayload`
- **响应**：更新后的 `LLMManagerSnapshot`

#### 7.3.9 更新模型

`PUT /api/llm-status/manager/models/{model_id}`

- **认证**：Admin JWT
- **说明**：更新模型的名称、显示名或 Extra Body。需至少提供一个更新字段。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `model_id` | `int` | 模型 ID |

- **请求体**：`ModelUpdatePayload`
- **响应**：更新后的 `LLMManagerSnapshot`

#### 7.3.10 删除模型

`DELETE /api/llm-status/manager/models/{model_id}`

- **认证**：Admin JWT
- **说明**：禁用（软删除）指定的模型。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `model_id` | `int` | 模型 ID |

- **响应**：更新后的 `LLMManagerSnapshot`

#### 7.3.11 探测并同步平台模型

`POST /api/llm-status/manager/platforms/{platform_id}/probe-and-sync`

- **认证**：Admin JWT
- **说明**：探测指定平台的可用模型列表，并自动同步到数据库（仅新增未存在的模型）。
- **路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `platform_id` | `int` | 平台 ID |

- **响应**：`PlatformProbeSyncResult`

```json
{
  "snapshot": { ... },
  "probed": 15,
  "created": 3
}
```

#### 7.3.12 探测可用模型

`POST /api/llm-status/probe`

- **认证**：Admin JWT
- **说明**：使用提供的 API Key 探测平台的可用模型列表。
- **请求体**：`TestPayload`
- **响应**：

```json
{ "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"] }
```

#### 7.3.13 测试模型连接

`POST /api/llm-status/test`

- **认证**：Admin JWT
- **说明**：发送测试消息验证模型连通性。
- **请求体**：`TestPayload`
- **响应**：

```json
{ "reply": "Hello! How can I help you?" }
```

#### 7.3.14 流式测速

`POST /api/llm-status/speed-test`

- **认证**：Admin JWT
- **说明**：流式测速端点，通过 SSE 返回实时速度数据。
- **请求体**：`TestPayload`
- **响应**：`text/event-stream`（SSE）

```
data: {"chunk": "Hello", "tokens_per_second": 42.5, ...}
data: {"chunk": " world", "tokens_per_second": 45.0, ...}
data: [DONE]
```

#### 7.3.15 检查 LLM_KEY 状态

`GET /api/llm-status/llm-key-status`

- **认证**：Admin JWT
- **说明**：检查 LLM_KEY 主密钥是否已配置。
- **请求体**：无
- **响应**：

```json
{ "configured": true }
```

#### 7.3.16 设置主密钥

`POST /api/llm-status/set-llm-key`

- **认证**：Admin JWT
- **说明**：设置或更新 LLM_KEY 主密钥（用于加密存储 API Key）。
- **请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `key` | `string` | 是 | 主密钥（至少 8 位） |

- **响应**：

```json
{ "ok": true }
```

- **错误码**：
  - `400` — 主密钥为空或长度不足

---

## 8. 通用端点

### 8.1 端点总览

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| `GET` | `/health` | 无 | 健康检查 |

### 8.2 端点详细说明

#### 8.2.1 健康检查

`GET /health`

- **认证**：无
- **说明**：返回服务运行状态，用于 Docker 健康检查和负载均衡器探活。
- **请求体**：无
- **响应**：

```json
{ "status": "ok" }
```

---

## 9. MCP 协议端点

源码：`backend/app/mcp/server.py`、`backend/app/main.py`

### 9.1 接入方式

MCP 端点挂载在 `/mcp` 路径下，使用 [FastMCP](https://github.com/jlowin/fastmcp) 的 **Streamable HTTP** 传输协议。

- **端点地址**：`POST /mcp/`
- **协议**：MCP Streamable HTTP（基于 JSON-RPC 2.0）
- **支持的 MCP 客户端**：OpenClaw、Claude Desktop、Cursor 等支持 MCP 协议的 AI Agent

### 9.2 认证

通过环境变量 `LUI_MCP_API_TOKEN` 配置静态 Bearer Token。

- 请求头：`Authorization: Bearer <token>`
- 未配置 Token 时，MCP 端点将被完全阻断（返回 401）
- Token 可在管理后台「系统设置」页面配置，或直接设置 `workspace/.env` 中的 `LUI_MCP_API_TOKEN`

> ⚠️ **安全前提**：MCP 模式跳过了人工审批环节。使用前必须在「系统设置」中将「默认动作」切换为「全部允许」（`safety_default_action=allow`）。

### 9.3 可用 Tools

| Tool 名称 | 说明 | 只读 |
|---|---|---|
| `list_projects` | 列出所有已导入项目，返回 ID、名称、描述、能力数量 | ✅ |
| `get_project_capabilities` | 获取项目能力清单，支持按 domain/safety_level/keyword 过滤，支持批量详情查询 | ✅ |
| `chat` | 发送自然语言消息，由内部 AI 执行并返回结果 | ❌ |
| `get_task_run_result` | 按 task_run_id 查询任务执行结果与产物 | ✅ |
| `get_session_history` | 获取指定会话的对话历史 | ✅ |

### 9.4 推荐工作流

1. 调用 `list_projects` 获取可用的 `project_id`
2. 调用 `get_project_capabilities` 查看项目能力清单
3. 调用 `chat` 发送自然语言指令（支持多轮对话：传入 `session_id` 保持上下文）
4. 调用 `get_task_run_result` 查询历史任务详情
5. 调用 `get_session_history` 回看对话记录

### 9.5 MCP 配置示例

**环境变量配置**（`workspace/.env`）：

```env
LUI_MCP_API_TOKEN=your-secret-token-here
LUI_SAFETY_DEFAULT_ACTION=allow
```

**Claude Desktop 配置示例**（`claude_desktop_config.json`）：

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
