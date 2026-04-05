"""FastAPI 标准测试后端：覆盖常见请求类型与请求操作。"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import (
    Body,
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="LUI FastAPI Standard Test Backend",
    version="1.0.0",
    description="用于 LUI-for-All 的标准 FastAPI 测试服务，内存数据、零复杂依赖。",
)


USERS: dict[str, dict[str, Any]] = {}
ORDERS: dict[str, list[dict[str, Any]]] = {}
JOBS: dict[str, dict[str, Any]] = {}
IDEMPOTENCY_PAYMENTS: dict[str, dict[str, Any]] = {}
TOKENS: dict[str, str] = {}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserCreate(BaseModel):
    name: str
    email: str
    role: Literal["admin", "operator", "user"] = "user"
    active: bool = True
    tags: list[str] = Field(default_factory=list)


class UserReplace(BaseModel):
    name: str
    email: str
    role: Literal["admin", "operator", "user"]
    active: bool
    tags: list[str] = Field(default_factory=list)


class UserPatch(BaseModel):
    name: str | None = None
    email: str | None = None
    role: Literal["admin", "operator", "user"] | None = None
    active: bool | None = None
    tags: list[str] | None = None


class BatchCreateUsersRequest(BaseModel):
    users: list[UserCreate]


class BatchStatusRequest(BaseModel):
    user_ids: list[str]
    active: bool


class OrderCreate(BaseModel):
    product: str
    quantity: int = Field(default=1, ge=1)
    unit_price: float = Field(default=1.0, gt=0)


class BatchCancelOrderRequest(BaseModel):
    order_ids: list[str]


class JobCreate(BaseModel):
    kind: Literal["export", "sync", "report", "cleanup"]
    payload: dict[str, Any] = Field(default_factory=dict)


class JobPatch(BaseModel):
    status: Literal["pending", "running", "done", "failed"]


class PaymentRequest(BaseModel):
    amount: float = Field(gt=0)
    currency: Literal["CNY", "USD", "EUR"] = "CNY"
    remark: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _get_token(
    authorization: str | None,
    session_token: str | None,
) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    if session_token:
        return session_token
    raise HTTPException(status_code=401, detail="缺少认证信息")


def _require_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session_token: str | None = Cookie(default=None),
) -> str:
    token = _get_token(authorization=authorization, session_token=session_token)
    username = TOKENS.get(token)
    if not username:
        raise HTTPException(status_code=401, detail="认证无效或已过期")
    return username


def _must_get_user(user_id: str) -> dict[str, Any]:
    user = USERS.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")
    return user


@app.on_event("startup")
def seed_data() -> None:
    if USERS:
        return

    u1 = {
        "id": "u-1001",
        "name": "Alice",
        "email": "alice@example.local",
        "role": "admin",
        "active": True,
        "tags": ["finance", "ops"],
        "created_at": _now(),
        "updated_at": _now(),
    }
    u2 = {
        "id": "u-1002",
        "name": "Bob",
        "email": "bob@example.local",
        "role": "user",
        "active": True,
        "tags": ["support"],
        "created_at": _now(),
        "updated_at": _now(),
    }
    USERS[u1["id"]] = u1
    USERS[u2["id"]] = u2
    ORDERS[u1["id"]] = [
        {
            "id": "o-5001",
            "user_id": u1["id"],
            "product": "Keyboard",
            "quantity": 2,
            "unit_price": 199.0,
            "status": "created",
            "created_at": _now(),
        }
    ]
    ORDERS[u2["id"]] = []


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "fastapi-sample"}


@app.post("/api/auth/login")
def login(request: LoginRequest, response: Response) -> dict[str, Any]:
    token = f"token-{uuid.uuid4().hex}"
    TOKENS[token] = request.username
    response.set_cookie(key="session_token", value=token, httponly=True)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 3600,
        "username": request.username,
    }


@app.post("/api/auth/logout")
def logout(
    response: Response,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session_token: str | None = Cookie(default=None),
) -> dict[str, bool]:
    token = _get_token(authorization=authorization, session_token=session_token)
    TOKENS.pop(token, None)
    response.delete_cookie("session_token")
    return {"success": True}


@app.get("/api/auth/me")
def me(username: str = Header(default="", alias="X-Debug-User")) -> dict[str, Any]:
    # 为了测试 Header 入参，这里支持调试用户名透传；正式鉴权请走 Bearer/Cookie。
    if username:
        return {"username": username, "source": "header"}
    return {"username": "anonymous", "source": "default"}


@app.options("/api/users")
def users_options() -> Response:
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"Allow": "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS"},
    )


@app.head("/api/users")
def users_head() -> Response:
    return Response(status_code=status.HTTP_200_OK)


@app.get("/api/users")
def list_users(
    _: str = Header(default="", alias="Authorization"),
    q: str | None = Query(default=None, description="按姓名/邮箱模糊搜索"),
    active: bool | None = Query(default=None),
    role: Literal["admin", "operator", "user"] | None = Query(default=None),
    sort: Literal["created_at", "name"] = Query(default="created_at"),
    order: Literal["asc", "desc"] = Query(default="asc"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    items = list(USERS.values())

    if q:
        q_lower = q.lower()
        items = [
            item
            for item in items
            if q_lower in item["name"].lower() or q_lower in item["email"].lower()
        ]
    if active is not None:
        items = [item for item in items if item["active"] is active]
    if role:
        items = [item for item in items if item["role"] == role]

    reverse = order == "desc"
    items.sort(key=lambda item: item[sort], reverse=reverse)

    return {
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "items": items[offset : offset + limit],
    }


@app.post("/api/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, actor: str = Depends(_require_auth)) -> dict[str, Any]:
    user_id = f"u-{uuid.uuid4().hex[:8]}"
    now = _now()
    user = {
        "id": user_id,
        "name": payload.name,
        "email": payload.email,
        "role": payload.role,
        "active": payload.active,
        "tags": payload.tags,
        "created_at": now,
        "updated_at": now,
        "created_by": actor,
    }
    USERS[user_id] = user
    ORDERS.setdefault(user_id, [])
    return user


@app.post("/api/users/batch", status_code=status.HTTP_201_CREATED)
def batch_create_users(
    payload: BatchCreateUsersRequest,
    actor: str = Depends(_require_auth),
) -> dict[str, Any]:
    created = []
    for user_data in payload.users:
        user_id = f"u-{uuid.uuid4().hex[:8]}"
        now = _now()
        user = {
            "id": user_id,
            "name": user_data.name,
            "email": user_data.email,
            "role": user_data.role,
            "active": user_data.active,
            "tags": user_data.tags,
            "created_at": now,
            "updated_at": now,
            "created_by": actor,
        }
        USERS[user_id] = user
        ORDERS.setdefault(user_id, [])
        created.append(user)
    return {"count": len(created), "items": created}


@app.patch("/api/users/batch/status")
def batch_update_status(
    payload: BatchStatusRequest,
    _: str = Depends(_require_auth),
) -> dict[str, Any]:
    updated = 0
    for user_id in payload.user_ids:
        if user_id in USERS:
            USERS[user_id]["active"] = payload.active
            USERS[user_id]["updated_at"] = _now()
            updated += 1
    return {"requested": len(payload.user_ids), "updated": updated, "active": payload.active}


@app.get("/api/users/{user_id}")
def get_user(user_id: str, _: str = Depends(_require_auth)) -> dict[str, Any]:
    return _must_get_user(user_id)


@app.put("/api/users/{user_id}")
def replace_user(
    user_id: str,
    payload: UserReplace,
    _: str = Depends(_require_auth),
) -> dict[str, Any]:
    user = _must_get_user(user_id)
    user.update(
        {
            "name": payload.name,
            "email": payload.email,
            "role": payload.role,
            "active": payload.active,
            "tags": payload.tags,
            "updated_at": _now(),
        }
    )
    return user


@app.patch("/api/users/{user_id}")
def patch_user(
    user_id: str,
    payload: UserPatch,
    _: str = Depends(_require_auth),
) -> dict[str, Any]:
    user = _must_get_user(user_id)
    patch_data = payload.model_dump(exclude_none=True)
    if patch_data:
        patch_data["updated_at"] = _now()
        user.update(patch_data)
    return user


@app.delete("/api/users/{user_id}")
def delete_user(
    user_id: str,
    hard: bool = Query(default=False, description="true 表示硬删除"),
    _: str = Depends(_require_auth),
) -> dict[str, Any]:
    _must_get_user(user_id)
    if hard:
        USERS.pop(user_id, None)
        ORDERS.pop(user_id, None)
        return {"deleted": True, "hard": True, "user_id": user_id}

    USERS[user_id]["active"] = False
    USERS[user_id]["deleted_at"] = _now()
    USERS[user_id]["updated_at"] = _now()
    return {"deleted": True, "hard": False, "user_id": user_id}


@app.get("/api/users/{user_id}/orders")
def list_orders(
    user_id: str,
    status_filter: Literal["created", "paid", "cancelled"] | None = Query(default=None, alias="status"),
    _: str = Depends(_require_auth),
) -> dict[str, Any]:
    _must_get_user(user_id)
    items = ORDERS.get(user_id, [])
    if status_filter:
        items = [item for item in items if item["status"] == status_filter]
    return {"total": len(items), "items": items}


@app.post("/api/users/{user_id}/orders", status_code=status.HTTP_201_CREATED)
def create_order(
    user_id: str,
    payload: OrderCreate,
    _: str = Depends(_require_auth),
) -> dict[str, Any]:
    _must_get_user(user_id)
    order = {
        "id": f"o-{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "product": payload.product,
        "quantity": payload.quantity,
        "unit_price": payload.unit_price,
        "status": "created",
        "created_at": _now(),
    }
    ORDERS.setdefault(user_id, []).append(order)
    return order


@app.post("/api/orders/batch/cancel")
def batch_cancel_orders(
    payload: BatchCancelOrderRequest,
    _: str = Depends(_require_auth),
) -> dict[str, Any]:
    cancelled = 0
    for order_list in ORDERS.values():
        for item in order_list:
            if item["id"] in payload.order_ids and item["status"] != "cancelled":
                item["status"] = "cancelled"
                cancelled += 1
    return {"requested": len(payload.order_ids), "cancelled": cancelled}


@app.post("/api/feedback/form")
def submit_feedback(
    contact: str = Form(...),
    message: str = Form(...),
    rating: int = Form(default=5),
) -> dict[str, Any]:
    return {
        "contact": contact,
        "message": message,
        "rating": rating,
        "received_at": _now(),
    }


@app.post("/api/upload/avatar")
async def upload_avatar(
    user_id: str = Form(...),
    note: str = Form(default=""),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    _must_get_user(user_id)
    content = await file.read()
    return {
        "user_id": user_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "note": note,
        "uploaded_at": _now(),
    }


@app.get("/api/echo/headers")
def echo_headers(
    x_request_id: str = Header(..., alias="X-Request-ID"),
    x_trace_id: str | None = Header(default=None, alias="X-Trace-ID"),
) -> dict[str, Any]:
    return {
        "x_request_id": x_request_id,
        "x_trace_id": x_trace_id,
        "received_at": _now(),
    }


@app.get("/api/echo/cookies")
def echo_cookies(
    session_token: str | None = Cookie(default=None),
    locale: str | None = Cookie(default=None),
) -> dict[str, Any]:
    return {
        "session_token": session_token,
        "locale": locale,
    }


@app.get("/api/export/users.csv")
def export_users_csv(_: str = Depends(_require_auth)) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["id", "name", "email", "role", "active"])
    writer.writeheader()
    for user in USERS.values():
        writer.writerow(
            {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "active": user["active"],
            }
        )

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


@app.get("/api/stream/notifications")
async def stream_notifications() -> StreamingResponse:
    async def event_generator():
        for idx in range(1, 6):
            payload = {
                "id": idx,
                "topic": "demo.notification",
                "message": f"第 {idx} 条实时事件",
                "created_at": _now(),
            }
            yield f"id: {idx}\nevent: notification\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.4)
        yield "event: done\ndata: stream completed\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/jobs", status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreate, _: str = Depends(_require_auth)) -> dict[str, Any]:
    job_id = f"j-{uuid.uuid4().hex[:8]}"
    job = {
        "id": job_id,
        "kind": payload.kind,
        "payload": payload.payload,
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
    }
    JOBS[job_id] = job
    return job


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, _: str = Depends(_require_auth)) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@app.patch("/api/jobs/{job_id}")
def patch_job(
    job_id: str,
    payload: JobPatch,
    _: str = Depends(_require_auth),
) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    job["status"] = payload.status
    job["updated_at"] = _now()
    return job


@app.delete("/api/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, _: str = Depends(_require_auth)) -> Response:
    JOBS.pop(job_id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/payments", status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _: str = Depends(_require_auth),
) -> dict[str, Any]:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="缺少 Idempotency-Key")

    if idempotency_key in IDEMPOTENCY_PAYMENTS:
        return {
            "idempotency_hit": True,
            **IDEMPOTENCY_PAYMENTS[idempotency_key],
        }

    payment = {
        "payment_id": f"pay-{uuid.uuid4().hex[:8]}",
        "amount": payload.amount,
        "currency": payload.currency,
        "remark": payload.remark,
        "status": "accepted",
        "created_at": _now(),
    }
    IDEMPOTENCY_PAYMENTS[idempotency_key] = payment
    return {"idempotency_hit": False, **payment}


@app.post("/api/webhooks/order-updated", status_code=status.HTTP_202_ACCEPTED)
def webhook_order_updated(
    payload: dict[str, Any] = Body(...),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
) -> dict[str, Any]:
    return {
        "accepted": True,
        "signature_valid": x_signature == "test-signature",
        "received_payload": payload,
        "received_at": _now(),
    }
