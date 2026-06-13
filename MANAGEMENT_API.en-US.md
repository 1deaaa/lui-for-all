# Management API Reference

> This document covers all management API endpoints of LUI-for-All. For chat-related endpoints (custom GUI integration), see [Chat Endpoint Integration Protocol](CHAT_ENDPOINT_INTEGRATION.md).

> ⚠️ All management endpoints require Admin JWT authentication (`sub=lui-admin`), except where explicitly noted. Authentication method: `Authorization: Bearer <token>`.

---

## Table of Contents

- [1. Authentication](#1-authentication)
- [2. Project Management](#2-project-management)
- [3. Role Profiles](#3-role-profiles)
- [4. Audit Queries](#4-audit-queries)
- [5. Approval Management](#5-approval-management)
- [6. System Settings](#6-system-settings)
- [7. LLM Model Management](#7-llm-model-management)
- [8. General Endpoints](#8-general-endpoints)
- [9. MCP Protocol Endpoints](#9-mcp-protocol-endpoints)

---

## 1. Authentication

Source: `backend/app/api/auth.py`

### 1.1 Endpoint Overview

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/auth/status` | None | Check if password has been set |
| `POST` | `/api/auth/setup` | None | Set admin password for the first time, returns JWT |
| `POST` | `/api/auth/login` | None | Admin login, returns JWT |
| `GET` | `/api/auth/forgot-password-hint` | None | Forgot password hint |
| `POST` | `/api/auth/user-login` | None | End-user login (verified via target system), returns User JWT |

### 1.2 Request/Response Models

| Model | Field | Type | Constraint | Description |
|---|---|---|---|---|
| `PasswordSetupRequest` | `password` | `string` | `min_length=8`, must contain uppercase, lowercase letters and digits | Admin password |
| `LoginRequest` | `password` | `string` | — | Admin password |
| `UserLoginRequest` | `project_slug` | `string` | Required | Project URL slug |
| | `username` | `string` | Required | Target system username |
| | `password` | `string` | Required | Target system password |

**Response Models:**

| Model | Field | Type | Description |
|---|---|---|---|
| `AuthStatusResponse` | `password_set` | `bool` | Whether password has been set |
| `PasswordSetupResponse` | `token` | `string` | Admin JWT Token |
| `LoginResponse` | `token` | `string` | Admin JWT Token |
| `ForgotPasswordHintResponse` | `hint` | `string` | Hint message |
| | `file_path` | `string` | Relative path to the password file |
| `UserLoginResponse` | `token` | `string` | User JWT Token |
| | `project_id` | `string` | Project ID |
| | `project_name` | `string` | Project name |
| | `project_slug` | `string \| null` | Project slug |
| | `role_profile_id` | `string \| null` | Matched role profile ID |

### 1.3 Detailed Endpoint Description

#### 1.3.1 Check Authentication Status

`GET /api/auth/status`

- **Auth**: None
- **Description**: Check if admin password has been set. The frontend uses this to decide whether to show the "Set Password" or "Login" screen.
- **Request Body**: None
- **Response**:

```json
{ "password_set": true }
```

#### 1.3.2 First-Time Password Setup

`POST /api/auth/setup`

- **Auth**: None (only available when password has not been set)
- **Description**: Set admin password for the first time and issue JWT. Password must be at least 8 characters and include uppercase, lowercase letters and digits.
- **Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `password` | `string` | Yes | Password (at least 8 characters, must include uppercase + lowercase + digits) |

- **Response**:

```json
{ "token": "eyJhbGciOiJIUzI1NiIs..." }
```

- **Error Codes**:
  - `409` — Password already set, cannot set again
  - `422` — Password strength insufficient

#### 1.3.3 Admin Login

`POST /api/auth/login`

- **Auth**: None
- **Description**: Verify admin password and issue JWT.
- **Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `password` | `string` | Yes | Admin password |

- **Response**:

```json
{ "token": "eyJhbGciOiJIUzI1NiIs..." }
```

- **Error Codes**:
  - `400` — Password has not been set yet
  - `401` — Incorrect password

#### 1.3.4 Forgot Password Hint

`GET /api/auth/forgot-password-hint`

- **Auth**: None
- **Description**: Returns a hint with the password file path. Users should go to the server, delete the password file, and restart the service to set a new password.
- **Request Body**: None
- **Response**:

```json
{
  "hint": "Go to the server, delete the password file, and restart the service to set a new password",
  "file_path": "workspace/password.txt"
}
```

#### 1.3.5 End-User Login

`POST /api/auth/user-login`

- **Auth**: None
- **Description**: End-user authenticates via the target system's login endpoint. The system will call the project's configured login route, issue a User JWT on success, and match role profiles.
- **Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `project_slug` | `string` | Yes | Project URL slug |
| `username` | `string` | Yes | Target system username |
| `password` | `string` | Yes | Target system password |

- **Response**:

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "project_name": "Sample Project",
  "project_slug": "my-app",
  "role_profile_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

- **Error Codes**:
  - `400` — Project has not configured a login endpoint
  - `403` — Project has not enabled user login, or no role profile configured
  - `404` — Project does not exist
  - `401` — Incorrect username or password
  - `502` — Failed to connect to target system
  - `500` — Login succeeded but failed to obtain target system token

---

## 2. Project Management

Source: `backend/app/api/projects.py`

### 2.1 Endpoint Overview

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/projects/` | Admin | List all projects |
| `POST` | `/api/projects/import` | Admin | Import a new project |
| `PATCH` | `/api/projects/{project_id}` | Admin | Update project info |
| `DELETE` | `/api/projects/{project_id}` | Admin | Delete project |
| `GET` | `/api/projects/resolve-slug/{slug}` | None | Resolve URL slug to project info (public endpoint) |
| `POST` | `/api/projects/verify-source-path` | Admin | Verify source path accessibility |
| `POST` | `/api/projects/test-connection` | Admin | Test connectivity |
| `POST` | `/api/projects/fetch-routes` | Admin | Fetch route list |
| `POST` | `/api/projects/verify-login` | Admin | Verify login endpoint |
| `GET` | `/api/projects/import-presets` | Admin | Get import presets |
| `POST` | `/api/projects/{project_id}/discover` | Admin | Trigger project discovery |
| `GET` | `/api/projects/{project_id}/status` | Admin | Get discovery status |
| `GET` | `/api/projects/{project_id}/route-map` | Admin / User | Get route map |
| `GET` | `/api/projects/{project_id}/capabilities` | Admin / User | Get capability map |
| `PATCH` | `/api/projects/{project_id}/capabilities/{capability_id}` | Admin | Update capability info |

### 2.2 Request/Response Models

**Request Models:**

| Model | Field | Type | Constraint | Description |
|---|---|---|---|---|
| `ProjectImportRequest` | `name` | `string` | Required | Project name |
| | `base_url` | `string` | Required | Target system base URL |
| | `openapi_url` | `string \| null` | Optional | OpenAPI document URL |
| | `description` | `string \| null` | Optional | Project description |
| | `slug` | `string \| null` | Optional | URL slug, auto-generated if not provided |
| | `username` | `string \| null` | Optional | Target system login username |
| | `password` | `string \| null` | Optional | Target system login password |
| | `login_route_id` | `string \| null` | Optional | Login endpoint route_id (e.g. `POST:/api/auth/login`) |
| | `login_field_username` | `string \| null` | Default `"username"` | Username field name for login endpoint |
| | `login_field_password` | `string \| null` | Default `"password"` | Password field name for login endpoint |
| | `source_path` | `string` | Required | Absolute path to the target project's local source directory |
| `ProjectUpdateRequest` | `name` | `string \| null` | Optional | Project name |
| | `description` | `string \| null` | Optional | Project description |
| | `slug` | `string \| null` | Optional | URL slug |
| | `base_url` | `string \| null` | Optional | Base URL |
| | `user_login_enabled` | `bool \| null` | Optional | Whether to enable end-user login |
| | `default_role_profile_id` | `string \| null` | Optional | Default role profile ID |
| `FetchRoutesRequest` | `base_url` | `string` | Required | Base URL |
| | `openapi_url` | `string \| null` | Optional | OpenAPI document URL |
| | `source_path` | `string \| null` | Optional | Source path |
| `VerifySourcePathRequest` | `source_path` | `string` | Required | Absolute path to the source directory |
| `TestConnectionRequest` | `base_url` | `string` | Required | Base URL |
| | `openapi_url` | `string \| null` | Optional | OpenAPI document URL |
| | `source_path` | `string \| null` | Optional | Source path |
| `VerifyLoginRequest` | `base_url` | `string` | Required | Base URL |
| | `login_route_id` | `string` | Required | Login endpoint route_id |
| | `username` | `string` | Required | Test username |
| | `password` | `string` | Required | Test password |
| | `body_field_username` | `string` | Default `"username"` | Username field name |
| | `body_field_password` | `string` | Default `"password"` | Password field name |
| `CapabilityUpdateRequest` | `permission_level` | `string \| null` | Optional | Permission level |

### 2.3 Detailed Endpoint Description

#### 2.3.1 List All Projects

`GET /api/projects/`

- **Auth**: Admin JWT
- **Description**: List all imported projects.
- **Request Body**: None
- **Response**:

```json
{
  "projects": [
    {
      "id": "550e8400-...",
      "name": "Sample Project",
      "slug": "my-app",
      "description": "...",
      "base_url": "http://localhost:8010",
      "discovery_status": "completed",
      "discovery_progress": 100,
      "discovery_message": "Mapping completed",
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

#### 2.3.2 Import New Project

`POST /api/projects/import`

- **Auth**: Admin JWT
- **Description**: Import a new project. Automatically verifies source path accessibility, generates slug (if not specified), and creates the project record.
- **Request Body**: `ProjectImportRequest` (see 2.2)
- **Response**:

```json
{
  "project_id": "550e8400-...",
  "name": "Sample Project",
  "status": "pending"
}
```

- **Error Codes**:
  - `400` — Source path is unreachable or not a directory

#### 2.3.3 Update Project Info

`PATCH /api/projects/{project_id}`

- **Auth**: Admin JWT
- **Description**: Update project name, description, slug, base URL, user login toggle, or default role profile.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |

- **Request Body**: `ProjectUpdateRequest` (see 2.2, all fields optional)
- **Response**:

```json
{ "project_id": "550e8400-...", "status": "updated" }
```

- **Error Codes**:
  - `400` — Slug uses a reserved name
  - `404` — Project does not exist
  - `409` — Slug already in use by another project

#### 2.3.4 Delete Project

`DELETE /api/projects/{project_id}`

- **Auth**: Admin JWT
- **Description**: Delete a project and all its associated records (sessions, tasks, audit logs, route map, capability map, etc.).
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |

- **Response**:

```json
{ "project_id": "550e8400-...", "status": "deleted" }
```

#### 2.3.5 Resolve Slug

`GET /api/projects/resolve-slug/{slug}`

- **Auth**: None (public endpoint)
- **Description**: Resolve a URL slug to project info, used by the frontend user login page initialization.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `slug` | `string` | Project URL slug |

- **Response**:

```json
{
  "project_id": "550e8400-...",
  "name": "Sample Project",
  "slug": "my-app"
}
```

- **Error Codes**:
  - `403` — Project has not enabled user login
  - `404` — Project does not exist

#### 2.3.6 Verify Source Path

`POST /api/projects/verify-source-path`

- **Auth**: Admin JWT
- **Description**: Verify source path accessibility, returning structured diagnostic info (including Docker environment awareness, framework detection).
- **Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `source_path` | `string` | Yes | Absolute path to the source directory |

- **Response**:

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

#### 2.3.7 Test Connection

`POST /api/projects/test-connection`

- **Auth**: Admin JWT
- **Description**: Test connectivity to the target system and OpenAPI document availability, while also detecting source path accessibility.
- **Request Body**: `TestConnectionRequest` (see 2.2)
- **Response**:

```json
{
  "status": "success",
  "message": "Connection and OpenAPI exploration available (http://localhost:8010/openapi.json)",
  "routes": [...],
  "source": "openapi",
  "source_path_info": { ... }
}
```

#### 2.3.8 Fetch Route List

`POST /api/projects/fetch-routes`

- **Auth**: Admin JWT
- **Description**: Fetch route list from OpenAPI URL or source code AST, for the frontend to select a login endpoint.
- **Request Body**: `FetchRoutesRequest` (see 2.2)
- **Response**:

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

#### 2.3.9 Verify Login Endpoint

`POST /api/projects/verify-login`

- **Auth**: Admin JWT
- **Description**: Call the target system's login endpoint with provided credentials to verify if a token can be obtained.
- **Request Body**: `VerifyLoginRequest` (see 2.2)
- **Response**:

```json
{
  "success": true,
  "status_code": 200,
  "message": "Login successful, token captured"
}
```

#### 2.3.10 Get Import Presets

`GET /api/projects/import-presets`

- **Auth**: Admin JWT
- **Description**: Returns presets for quickly importing sample projects from the frontend (e.g. FastAPI sample, Node sample).
- **Request Body**: None
- **Response**:

```json
{
  "presets": [
    {
      "id": "sample-fastapi",
      "name": "FastAPI Sample",
      "description": "Auto-fill the local FastAPI sample address and source directory.",
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

#### 2.3.11 Trigger Project Discovery

`POST /api/projects/{project_id}/discover`

- **Auth**: Admin JWT
- **Description**: Trigger the project's capability mapping process (executes asynchronously). If already in progress, returns the current progress.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |

- **Response**:

```json
{
  "project_id": "550e8400-...",
  "status": "in_progress",
  "progress": 0,
  "message": "Project discovery task started"
}
```

#### 2.3.12 Get Discovery Status

`GET /api/projects/{project_id}/status`

- **Auth**: Admin JWT
- **Description**: Get the project's discovery status, progress, route and capability counts.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |

- **Response**:

```json
{
  "project_id": "550e8400-...",
  "name": "Sample Project",
  "slug": "my-app",
  "base_url": "http://localhost:8010",
  "status": "completed",
  "progress": 100,
  "progress_message": "Mapping completed",
  "route_count": 15,
  "capability_count": 8,
  "error": null
}
```

#### 2.3.13 Get Route Map

`GET /api/projects/{project_id}/route-map`

- **Auth**: Admin JWT or User JWT
- **Description**: Get the project's route map. For end-users, only routes accessible by their role profile are returned.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |

- **Response**:

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

#### 2.3.14 Get Capability Map

`GET /api/projects/{project_id}/capabilities`

- **Auth**: Admin JWT or User JWT
- **Description**: Get the project's capability map. For end-users, only capabilities accessible to them are returned.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |

- **Response**:

```json
{
  "project_id": "550e8400-...",
  "capabilities": [
    {
      "capability_id": "cap_001",
      "name": "User Management",
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

#### 2.3.15 Update Capability Info

`PATCH /api/projects/{project_id}/capabilities/{capability_id}`

- **Auth**: Admin JWT
- **Description**: Update capability permission level and other info.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |
| `capability_id` | `string` | Capability ID |

- **Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `permission_level` | `string \| null` | No | Permission level |

- **Response**:

```json
{ "capability_id": "cap_001", "status": "updated" }
```

---

## 3. Role Profiles

Source: `backend/app/api/role_profiles.py`

### 3.1 Endpoint Overview

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/projects/{project_id}/role-profiles` | Admin | List all role profiles for a project |
| `POST` | `/api/projects/{project_id}/role-profiles` | Admin | Create a role profile and trigger permission probing |
| `GET` | `/api/projects/{project_id}/role-profiles/{profile_id}` | Admin | View role profile details |
| `POST` | `/api/projects/{project_id}/role-profiles/{profile_id}/reprobe` | Admin | Re-trigger permission probing |
| `PATCH` | `/api/projects/{project_id}/role-profiles/{profile_id}/accessibility/{route_id:path}` | Admin | Manually override route accessibility |
| `DELETE` | `/api/projects/{project_id}/role-profiles/{profile_id}` | Admin | Delete role profile |
| `PUT` | `/api/projects/{project_id}/default-role` | Admin | Set default role profile |

### 3.2 Request/Response Models

| Model | Field | Type | Constraint | Description |
|---|---|---|---|---|
| `CreateRoleProfileRequest` | `name` | `string` | Required | Role name (e.g. "Regular User", "Admin") |
| | `description` | `string \| null` | Optional | Role description |
| | `probe_username` | `string` | Required | Target system username for probing |
| | `probe_password` | `string` | Required | Target system password for probing |
| `UpdateAccessibilityRequest` | `accessible` | `bool` | Required | Whether accessible |
| `SetDefaultRoleRequest` | `role_profile_id` | `string \| null` | Required | Role profile ID, `null` to unset default |

### 3.3 Detailed Endpoint Description

#### 3.3.1 List Role Profiles

`GET /api/projects/{project_id}/role-profiles`

- **Auth**: Admin JWT
- **Description**: List all role profiles for the specified project.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |

- **Response**:

```json
{
  "profiles": [
    {
      "id": "...",
      "name": "Regular User",
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

#### 3.3.2 Create Role Profile

`POST /api/projects/{project_id}/role-profiles`

- **Auth**: Admin JWT
- **Description**: Create a role profile and asynchronously trigger permission probing. The project must have a login endpoint configured.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |

- **Request Body**: `CreateRoleProfileRequest` (see 3.2)
- **Response**:

```json
{
  "id": "...",
  "name": "Regular User",
  "probe_status": "pending",
  "message": "Role profile created, permission probing started asynchronously"
}
```

- **Error Codes**:
  - `400` — Project has not configured a login endpoint
  - `404` — Project does not exist

#### 3.3.3 View Role Profile Details

`GET /api/projects/{project_id}/role-profiles/{profile_id}`

- **Auth**: Admin JWT
- **Description**: View role profile details, including accessibility probe results for each route.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |
| `profile_id` | `string` | Role profile ID |

- **Response**:

```json
{
  "id": "...",
  "name": "Regular User",
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

#### 3.3.4 Re-trigger Permission Probing

`POST /api/projects/{project_id}/role-profiles/{profile_id}/reprobe`

- **Auth**: Admin JWT
- **Description**: Re-trigger permission probing for the role profile.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |
| `profile_id` | `string` | Role profile ID |

- **Response**:

```json
{
  "id": "...",
  "probe_status": "pending",
  "message": "Permission probing restarted"
}
```

- **Error Codes**:
  - `404` — Role profile does not exist
  - `409` — Probing is already in progress

#### 3.3.5 Manually Override Route Accessibility

`PATCH /api/projects/{project_id}/role-profiles/{profile_id}/accessibility/{route_id:path}`

- **Auth**: Admin JWT
- **Description**: Manually override the accessibility of a single route. Creates a new record if one does not exist.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |
| `profile_id` | `string` | Role profile ID |
| `route_id` | `string` | Route ID (e.g. `GET:/api/users`) |

- **Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `accessible` | `bool` | Yes | Whether accessible |

- **Response**:

```json
{
  "route_id": "GET:/api/users",
  "accessible": true,
  "manually_overridden": true
}
```

#### 3.3.6 Delete Role Profile

`DELETE /api/projects/{project_id}/role-profiles/{profile_id}`

- **Auth**: Admin JWT
- **Description**: Delete a role profile and its associated accessibility data. If it is the default profile, the default reference is automatically cleared.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |
| `profile_id` | `string` | Role profile ID |

- **Response**:

```json
{ "id": "...", "message": "Role profile deleted" }
```

#### 3.3.7 Set Default Role Profile

`PUT /api/projects/{project_id}/default-role`

- **Auth**: Admin JWT
- **Description**: Set the project's default user role profile. Only profiles with completed probing can be set as default.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `project_id` | `string` | Project ID |

- **Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `role_profile_id` | `string \| null` | Yes | Role profile ID, `null` to unset default |

- **Response**:

```json
{
  "project_id": "550e8400-...",
  "default_role_profile_id": "660e8400-..."
}
```

- **Error Codes**:
  - `400` — Profile has not completed probing
  - `404` — Project or role profile does not exist

---

## 4. Audit Queries

Source: `backend/app/api/audit.py`

### 4.1 Endpoint Overview

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/audit/task-runs` | Admin | List task run records |
| `GET` | `/api/audit/task-runs/{task_run_id}` | Admin | Get task run details |
| `GET` | `/api/audit/task-runs/{task_run_id}/events` | Admin | Get task event list |
| `GET` | `/api/audit/http-executions` | Admin | List HTTP execution records |
| `GET` | `/api/audit/http-executions/{request_id}` | Admin | Get single HTTP execution record |
| `GET` | `/api/audit/approvals` | Admin | List approval operation records |
| `GET` | `/api/audit/policy-verdicts` | Admin | List policy verdict records |
| `GET` | `/api/audit/model-calls` | Admin | List model call records |

### 4.2 Detailed Endpoint Description

#### 4.2.1 List Task Run Records

`GET /api/audit/task-runs`

- **Auth**: Admin JWT
- **Description**: List task run records with filtering by project, session, status, and pagination.
- **Query Parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project_id` | `string` | No | Filter by project |
| `session_id` | `string` | No | Filter by session |
| `status` | `string` | No | Filter by status |
| `limit` | `int` | No | Items per page (default 50, max 100) |
| `offset` | `int` | No | Offset (default 0) |

- **Response**:

```json
{
  "task_runs": [
    {
      "id": "...",
      "session_id": "...",
      "project_id": "...",
      "user_message": "List all users",
      "normalized_intent": "list_users",
      "status": "completed",
      "summary_text": "Successfully retrieved user list...",
      "error": null,
      "trace_id": "...",
      "created_at": "2024-01-01T00:00:00",
      "completed_at": "2024-01-01T00:00:05"
    }
  ],
  "total": 50
}
```

#### 4.2.2 Get Task Run Details

`GET /api/audit/task-runs/{task_run_id}`

- **Auth**: Admin JWT
- **Description**: Get complete details for a single task run, including plan, execution artifacts, UI Blocks, etc.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `task_run_id` | `string` | Task run ID |

- **Response**:

```json
{
  "id": "...",
  "session_id": "...",
  "project_id": "...",
  "user_message": "List all users",
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

#### 4.2.3 Get Task Event List

`GET /api/audit/task-runs/{task_run_id}/events`

- **Auth**: Admin JWT
- **Description**: Get the task's Event Sourcing list.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `task_run_id` | `string` | Task run ID |

- **Response**:

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

#### 4.2.4 List HTTP Execution Records

`GET /api/audit/http-executions`

- **Auth**: Admin JWT
- **Description**: List HTTP execution records with filtering by project, task, keyword, and pagination.
- **Query Parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project_id` | `string` | No | Filter by project |
| `task_run_id` | `string` | No | Filter by task |
| `keyword` | `string` | No | Fuzzy match by URL |
| `limit` | `int` | No | Items per page (default 50, max 100) |
| `offset` | `int` | No | Offset |

- **Response**:

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

#### 4.2.5 Get HTTP Execution Record Details

`GET /api/audit/http-executions/{request_id}`

- **Auth**: Admin JWT
- **Description**: Get complete info for a single HTTP execution record.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `request_id` | `string` | Request ID |

- **Response**: Same structure as list items (see 4.2.4).

#### 4.2.6 List Approval Operation Records

`GET /api/audit/approvals`

- **Auth**: Admin JWT
- **Description**: List approval operation records (audit logs) with filtering and pagination.
- **Query Parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project_id` | `string` | No | Filter by project |
| `status` | `string` | No | Filter by status |
| `keyword` | `string` | No | Keyword search |
| `limit` | `int` | No | Items per page (default 50, max 100) |
| `offset` | `int` | No | Offset |

- **Response**:

```json
{
  "approvals": [
    {
      "id": "...",
      "task_run_id": "...",
      "title": "DELETE /api/users/123",
      "action_summary": "DELETE /api/users/123  Params: {...}",
      "risk_level": "hard_write",
      "status": "approved",
      "decided_at": "2024-01-01T00:05:00",
      "decided_by": "user",
      "decision_reason": "Confirmed deletion",
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 10
}
```

#### 4.2.7 List Policy Verdict Records

`GET /api/audit/policy-verdicts`

- **Auth**: Admin JWT
- **Description**: List policy verdict records.
- **Query Parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project_id` | `string` | No | Filter by project |
| `task_run_id` | `string` | No | Filter by task |
| `action` | `string` | No | Filter by action |
| `limit` | `int` | No | Items per page (default 50) |

- **Response**:

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
      "reasons": ["Write operation requires confirmation"],
      "created_at": "2024-01-01T00:00:02"
    }
  ],
  "total": 5
}
```

#### 4.2.8 List Model Call Records

`GET /api/audit/model-calls`

- **Auth**: Admin JWT
- **Description**: List model call records.
- **Query Parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `project_id` | `string` | No | Filter by project |
| `task_run_id` | `string` | No | Filter by task |
| `limit` | `int` | No | Items per page (default 50) |

- **Response**:

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

## 5. Approval Management

Source: `backend/app/api/approvals.py`

### 5.1 Endpoint Overview

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/approvals/` | Admin | List approval records |
| `GET` | `/api/approvals/{approval_id}` | Admin | Get approval details |
| `POST` | `/api/approvals/{approval_id}/approve` | Admin | Approve approval request |
| `POST` | `/api/approvals/{approval_id}/reject` | Admin | Reject approval request |

### 5.2 Request/Response Models

| Model | Field | Type | Description |
|---|---|---|---|
| `ApprovalDecisionRequest` | `reason` | `string \| null` | Decision reason |
| `ApprovalResponse` | `approval_id` | `string` | Approval ID |
| | `status` | `string` | Status after processing |
| | `message` | `string` | Result message |

### 5.3 Detailed Endpoint Description

#### 5.3.1 List Approval Records

`GET /api/approvals/`

- **Auth**: Admin JWT
- **Description**: List approval records.
- **Query Parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `status` | `string` | No | Filter by status (`pending`/`approved`/`rejected`/`timeout`) |
| `limit` | `int` | No | Items per page (default 50) |

- **Response**:

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

#### 5.3.2 Get Approval Details

`GET /api/approvals/{approval_id}`

- **Auth**: Admin JWT
- **Description**: Get complete details for an approval record.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `approval_id` | `string` | Approval ID |

- **Response**:

```json
{
  "id": "...",
  "task_run_id": "...",
  "session_id": "...",
  "title": "DELETE /api/users/123",
  "description": "Write operation requiring manual approval",
  "action_summary": "DELETE /api/users/123  Params: {...}",
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

#### 5.3.3 Approve Approval Request

`POST /api/approvals/{approval_id}/approve`

- **Auth**: Admin JWT
- **Description**: Approve a pending approval request. Already processed or timed-out approvals cannot be acted upon.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `approval_id` | `string` | Approval ID |

- **Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `reason` | `string \| null` | No | Approval reason |

- **Response**:

```json
{
  "approval_id": "...",
  "status": "approved",
  "message": "Approval granted, task will continue execution"
}
```

- **Error Codes**:
  - `400` — Approval already processed or timed out
  - `404` — Approval record does not exist

#### 5.3.4 Reject Approval Request

`POST /api/approvals/{approval_id}/reject`

- **Auth**: Admin JWT
- **Description**: Reject a pending approval request.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `approval_id` | `string` | Approval ID |

- **Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `reason` | `string \| null` | No | Rejection reason |

- **Response**:

```json
{
  "approval_id": "...",
  "status": "rejected",
  "message": "Approval rejected, task will be cancelled"
}
```

- **Error Codes**: Same as 5.3.3

---

## 6. System Settings

Source: `backend/app/api/settings.py`

### 6.1 Endpoint Overview

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/settings` | Admin | Read current system settings |
| `PUT` | `/api/settings` | Admin | Save system settings |

### 6.2 Request/Response Models

| Model | Field | Type | Constraint | Description |
|---|---|---|---|---|
| `SettingsPayload` | `mcp_api_token` | `string \| null` | Optional | MCP API Token |
| | `safety_default_action` | `string \| null` | Default `"confirm"` | Global default approval action |
| `SettingsResponse` | Inherits all fields from `SettingsPayload` | | | |

### 6.3 Detailed Endpoint Description

#### 6.3.1 Read System Settings

`GET /api/settings`

- **Auth**: Admin JWT
- **Description**: Read current system settings.
- **Request Body**: None
- **Response**:

```json
{
  "mcp_api_token": "your-token-here",
  "safety_default_action": "confirm"
}
```

#### 6.3.2 Save System Settings

`PUT /api/settings`

- **Auth**: Admin JWT
- **Description**: Save system settings to `workspace/.env`, effective immediately.
- **Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `mcp_api_token` | `string \| null` | No | MCP API Token (leave empty to skip update) |
| `safety_default_action` | `string \| null` | No | Default approval action (`"confirm"` or `"allow"`) |

- **Response**: Same as 6.3.1

---

## 7. LLM Model Management

Source: `backend/app/api/llm_status.py`

### 7.1 Endpoint Overview

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/llm-status/main` | Admin | Read main model config |
| `PUT` | `/api/llm-status/main` | Admin | Update main model config |
| `GET` | `/api/llm-status/manager` | Admin | Get LLM manager snapshot |
| `POST` | `/api/llm-status/manager/main-selection` | Admin | Set main model selection |
| `POST` | `/api/llm-status/manager/platforms` | Admin | Create LLM platform |
| `PUT` | `/api/llm-status/manager/platforms/{platform_id}` | Admin | Update LLM platform |
| `DELETE` | `/api/llm-status/manager/platforms/{platform_id}` | Admin | Delete LLM platform |
| `POST` | `/api/llm-status/manager/platforms/{platform_id}/models` | Admin | Add model |
| `PUT` | `/api/llm-status/manager/models/{model_id}` | Admin | Update model |
| `DELETE` | `/api/llm-status/manager/models/{model_id}` | Admin | Delete model |
| `POST` | `/api/llm-status/manager/platforms/{platform_id}/probe-and-sync` | Admin | Probe and sync platform models |
| `POST` | `/api/llm-status/probe` | Admin | Probe available models |
| `POST` | `/api/llm-status/test` | Admin | Test model connection |
| `POST` | `/api/llm-status/speed-test` | Admin | Streaming speed test (SSE) |
| `GET` | `/api/llm-status/llm-key-status` | Admin | Check LLM_KEY config status |
| `POST` | `/api/llm-status/set-llm-key` | Admin | Set master key |

### 7.2 Request/Response Models

| Model | Field | Type | Description |
|---|---|---|---|
| `MainModelConfig` | `llm_api_base` | `string` | API Base URL |
| | `llm_api_key` | `string` | API Key |
| | `llm_model_id` | `string` | Model ID |
| | `llm_extra_body` | `string` | Extra Body JSON string |
| `MainSelectionPayload` | `platform_id` | `int` | Platform ID |
| | `model_id` | `int` | Model ID |
| `PlatformCreatePayload` | `name` | `string` | Platform name |
| | `base_url` | `string` | Base URL |
| | `api_key` | `string \| null` | API Key |
| `PlatformUpdatePayload` | `name` | `string \| null` | Platform name |
| | `base_url` | `string \| null` | Base URL |
| | `api_key` | `string \| null` | API Key |
| | `update_api_key` | `bool` | Whether to update API Key (default `false`) |
| `ModelCreatePayload` | `model_name` | `string` | Model name/ID |
| | `display_name` | `string \| null` | Display name |
| | `extra_body` | `string \| null` | Extra Body JSON string |
| `ModelUpdatePayload` | `model_name` | `string \| null` | Model name/ID |
| | `display_name` | `string \| null` | Display name |
| | `extra_body` | `string \| null` | Extra Body JSON string |
| `LLMManagerSnapshot` | `selected_platform_id` | `int \| null` | Currently selected platform ID |
| | `selected_model_id` | `int \| null` | Currently selected model ID |
| | `platforms` | `ManagedPlatform[]` | Platform list |
| `ManagedPlatform` | `platform_id` | `int` | Platform ID |
| | `name` | `string` | Platform name |
| | `base_url` | `string` | Base URL |
| | `api_key_set` | `bool` | Whether API Key is configured |
| | `models` | `ManagedModel[]` | Model list |
| `ManagedModel` | `model_id` | `int` | Model ID |
| | `model_name` | `string` | Model name |
| | `display_name` | `string` | Display name |
| | `extra_body` | `string` | Extra Body JSON string |
| `TestPayload` | `llm_api_base` | `string` | API Base URL |
| | `llm_api_key` | `string \| null` | API Key |
| | `llm_model_id` | `string` | Model ID |
| | `llm_extra_body` | `string \| null` | Extra Body JSON string |
| `PlatformProbeSyncResult` | `snapshot` | `LLMManagerSnapshot` | Snapshot |
| | `probed` | `int` | Number of models probed |
| | `created` | `int` | Number of new models created |
| `LLMKeyPayload` | `key` | `string` | Master key (at least 8 characters) |

### 7.3 Detailed Endpoint Description

#### 7.3.1 Read Main Model Config

`GET /api/llm-status/main`

- **Auth**: Admin JWT
- **Description**: Read the current main model (`main` purpose) configuration.
- **Request Body**: None
- **Response**: `MainModelConfig`

```json
{
  "llm_api_base": "https://api.openai.com/v1",
  "llm_api_key": "sk-...",
  "llm_model_id": "gpt-4o",
  "llm_extra_body": ""
}
```

#### 7.3.2 Update Main Model Config

`PUT /api/llm-status/main`

- **Auth**: Admin JWT
- **Description**: Update main model config. If the platform/model does not exist, a system platform and model are automatically created.
- **Request Body**: `MainModelConfig`
- **Response**: Updated `MainModelConfig`

#### 7.3.3 Get LLM Manager Snapshot

`GET /api/llm-status/manager`

- **Auth**: Admin JWT
- **Description**: Get a complete snapshot of all LLM platforms and models.
- **Request Body**: None
- **Response**: `LLMManagerSnapshot`

#### 7.3.4 Set Main Model Selection

`POST /api/llm-status/manager/main-selection`

- **Auth**: Admin JWT
- **Description**: Select the main model from existing platforms and models.
- **Request Body**: `MainSelectionPayload`
- **Response**: Updated `LLMManagerSnapshot`

#### 7.3.5 Create LLM Platform

`POST /api/llm-status/manager/platforms`

- **Auth**: Admin JWT
- **Description**: Create a new LLM platform.
- **Request Body**: `PlatformCreatePayload`
- **Response**: Updated `LLMManagerSnapshot`

#### 7.3.6 Update LLM Platform

`PUT /api/llm-status/manager/platforms/{platform_id}`

- **Auth**: Admin JWT
- **Description**: Update an LLM platform's name, Base URL, or API Key. At least one update field must be provided.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `platform_id` | `int` | Platform ID |

- **Request Body**: `PlatformUpdatePayload`
- **Response**: Updated `LLMManagerSnapshot`

#### 7.3.7 Delete LLM Platform

`DELETE /api/llm-status/manager/platforms/{platform_id}`

- **Auth**: Admin JWT
- **Description**: Disable (soft delete) the specified system platform.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `platform_id` | `int` | Platform ID |

- **Response**: Updated `LLMManagerSnapshot`

#### 7.3.8 Add Model

`POST /api/llm-status/manager/platforms/{platform_id}/models`

- **Auth**: Admin JWT
- **Description**: Add a new model to the specified platform.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `platform_id` | `int` | Platform ID |

- **Request Body**: `ModelCreatePayload`
- **Response**: Updated `LLMManagerSnapshot`

#### 7.3.9 Update Model

`PUT /api/llm-status/manager/models/{model_id}`

- **Auth**: Admin JWT
- **Description**: Update a model's name, display name, or Extra Body. At least one update field must be provided.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `model_id` | `int` | Model ID |

- **Request Body**: `ModelUpdatePayload`
- **Response**: Updated `LLMManagerSnapshot`

#### 7.3.10 Delete Model

`DELETE /api/llm-status/manager/models/{model_id}`

- **Auth**: Admin JWT
- **Description**: Disable (soft delete) the specified model.
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `model_id` | `int` | Model ID |

- **Response**: Updated `LLMManagerSnapshot`

#### 7.3.11 Probe and Sync Platform Models

`POST /api/llm-status/manager/platforms/{platform_id}/probe-and-sync`

- **Auth**: Admin JWT
- **Description**: Probe the specified platform for available models and automatically sync them to the database (only adds models that do not already exist).
- **Path Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `platform_id` | `int` | Platform ID |

- **Response**: `PlatformProbeSyncResult`

```json
{
  "snapshot": { ... },
  "probed": 15,
  "created": 3
}
```

#### 7.3.12 Probe Available Models

`POST /api/llm-status/probe`

- **Auth**: Admin JWT
- **Description**: Use the provided API Key to probe the platform's available model list.
- **Request Body**: `TestPayload`
- **Response**:

```json
{ "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"] }
```

#### 7.3.13 Test Model Connection

`POST /api/llm-status/test`

- **Auth**: Admin JWT
- **Description**: Send a test message to verify model connectivity.
- **Request Body**: `TestPayload`
- **Response**:

```json
{ "reply": "Hello! How can I help you?" }
```

#### 7.3.14 Streaming Speed Test

`POST /api/llm-status/speed-test`

- **Auth**: Admin JWT
- **Description**: Streaming speed test endpoint, returns real-time speed data via SSE.
- **Request Body**: `TestPayload`
- **Response**: `text/event-stream` (SSE)

```
data: {"chunk": "Hello", "tokens_per_second": 42.5, ...}
data: {"chunk": " world", "tokens_per_second": 45.0, ...}
data: [DONE]
```

#### 7.3.15 Check LLM_KEY Status

`GET /api/llm-status/llm-key-status`

- **Auth**: Admin JWT
- **Description**: Check whether the LLM_KEY master key has been configured.
- **Request Body**: None
- **Response**:

```json
{ "configured": true }
```

#### 7.3.16 Set Master Key

`POST /api/llm-status/set-llm-key`

- **Auth**: Admin JWT
- **Description**: Set or update the LLM_KEY master key (used to encrypt stored API Keys).
- **Request Body**:

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | `string` | Yes | Master key (at least 8 characters) |

- **Response**:

```json
{ "ok": true }
```

- **Error Codes**:
  - `400` — Master key is empty or too short

---

## 8. General Endpoints

### 8.1 Endpoint Overview

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Health check |

### 8.2 Detailed Endpoint Description

#### 8.2.1 Health Check

`GET /health`

- **Auth**: None
- **Description**: Returns the service running status, used for Docker health checks and load balancer liveness probes.
- **Request Body**: None
- **Response**:

```json
{ "status": "ok" }
```

---

## 9. MCP Protocol Endpoints

Source: `backend/app/mcp/server.py`, `backend/app/main.py`

### 9.1 Access Method

MCP endpoints are mounted at the `/mcp` path, using [FastMCP](https://github.com/jlowin/fastmcp)'s **Streamable HTTP** transport protocol.

- **Endpoint URL**: `POST /mcp/`
- **Protocol**: MCP Streamable HTTP (based on JSON-RPC 2.0)
- **Supported MCP Clients**: OpenClaw, Claude Desktop, Cursor, and other AI Agents that support the MCP protocol

### 9.2 Authentication

Configured via the `LUI_MCP_API_TOKEN` environment variable as a static Bearer Token.

- Request header: `Authorization: Bearer <token>`
- When no Token is configured, the MCP endpoint is completely blocked (returns 401)
- Token can be configured in the admin dashboard's "System Settings" page, or by directly setting `LUI_MCP_API_TOKEN` in `workspace/.env`

> ⚠️ **Security Prerequisite**: MCP mode bypasses the manual approval process. Before use, you must switch the "Default Action" to "Allow All" (`safety_default_action=allow`) in "System Settings".

### 9.3 Available Tools

| Tool Name | Description | Read-Only |
|---|---|---|
| `list_projects` | List all imported projects, returning ID, name, description, and capability count | ✅ |
| `get_project_capabilities` | Get project capability list, supports filtering by domain/safety_level/keyword, supports batch detail queries | ✅ |
| `chat` | Send a natural language message, executed by internal AI and returns results | ❌ |
| `get_task_run_result` | Query task execution results and artifacts by task_run_id | ✅ |
| `get_session_history` | Get conversation history for a specified session | ✅ |

### 9.4 Recommended Workflow

1. Call `list_projects` to get available `project_id`
2. Call `get_project_capabilities` to view the project capability list
3. Call `chat` to send natural language instructions (supports multi-turn conversation: pass `session_id` to maintain context)
4. Call `get_task_run_result` to query historical task details
5. Call `get_session_history` to review conversation records

### 9.5 MCP Configuration Examples

**Environment Variable Configuration** (`workspace/.env`):

```env
LUI_MCP_API_TOKEN=your-secret-token-here
LUI_SAFETY_DEFAULT_ACTION=allow
```

**Claude Desktop Configuration Example** (`claude_desktop_config.json`):

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
