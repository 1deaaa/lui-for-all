# Route Extraction Result: fastapi_sample

- Adapter: python_decorator
- Source Path: C:\Users\SERVER\Desktop\lui-for-all\backend_for_test\fastapi_sample
- Route Count: 29

## Route List

1. GET:/health | GET /health | app.py:183-185
2. POST:/api/auth/login | POST /api/auth/login | app.py:188-201
3. POST:/api/auth/logout | POST /api/auth/logout | app.py:204-213
4. GET:/api/auth/me | GET /api/auth/me | app.py:216-221
5. OPTIONS:/api/users | OPTIONS /api/users | app.py:224-229
6. HEAD:/api/users | HEAD /api/users | app.py:232-234
7. GET:/api/users | GET /api/users | app.py:237-270
8. POST:/api/users | POST /api/users | app.py:273-290
9. POST:/api/users/batch | POST /api/users/batch | app.py:293-316
10. PATCH:/api/users/batch/status | PATCH /api/users/batch/status | app.py:319-330
11. GET:/api/users/{user_id} | GET /api/users/{user_id} | app.py:333-335
12. PUT:/api/users/{user_id} | PUT /api/users/{user_id} | app.py:338-355
13. PATCH:/api/users/{user_id} | PATCH /api/users/{user_id} | app.py:358-369
14. DELETE:/api/users/{user_id} | DELETE /api/users/{user_id} | app.py:372-387
15. GET:/api/users/{user_id}/orders | GET /api/users/{user_id}/orders | app.py:390-400
16. POST:/api/users/{user_id}/orders | POST /api/users/{user_id}/orders | app.py:403-420
17. POST:/api/orders/batch/cancel | POST /api/orders/batch/cancel | app.py:423-434
18. POST:/api/feedback/form | POST /api/feedback/form | app.py:437-448
19. POST:/api/upload/avatar | POST /api/upload/avatar | app.py:451-466
20. GET:/api/echo/headers | GET /api/echo/headers | app.py:469-478
21. GET:/api/echo/cookies | GET /api/echo/cookies | app.py:481-489
22. GET:/api/export/users.csv | GET /api/export/users.csv | app.py:492-512
23. GET:/api/stream/notifications | GET /api/stream/notifications | app.py:515-529
24. POST:/api/jobs | POST /api/jobs | app.py:532-544
25. GET:/api/jobs/{job_id} | GET /api/jobs/{job_id} | app.py:547-552
26. PATCH:/api/jobs/{job_id} | PATCH /api/jobs/{job_id} | app.py:555-566
27. DELETE:/api/jobs/{job_id} | DELETE /api/jobs/{job_id} | app.py:569-572
28. POST:/api/payments | POST /api/payments | app.py:575-599
29. POST:/api/webhooks/order-updated | POST /api/webhooks/order-updated | app.py:602-612

## Function Implementation Blocks

### GET:/health

```text
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "fastapi-sample"}
```

### POST:/api/auth/login

```text
@app.post("/api/auth/login")
def login(request: LoginRequest, response: Response) -> dict[str, Any]:
    if request.username != LOGIN_USERNAME or request.password != LOGIN_PASSWORD:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = f"token-{uuid.uuid4().hex}"
    TOKENS[token] = request.username
    response.set_cookie(key="session_token", value=token, httponly=True)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 3600,
        "username": request.username,
    }
```

### POST:/api/auth/logout

```text
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
```

### GET:/api/auth/me

```text
@app.get("/api/auth/me")
def me(username: str = Header(default="", alias="X-Debug-User")) -> dict[str, Any]:
    # 为了测试 Header 入参，这里支持调试用户名透传；正式鉴权请走 Bearer/Cookie。
    if username:
        return {"username": username, "source": "header"}
    return {"username": "anonymous", "source": "default"}
```

### OPTIONS:/api/users

```text
@app.options("/api/users")
def users_options() -> Response:
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"Allow": "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS"},
    )
```

### HEAD:/api/users

```text
@app.head("/api/users")
def users_head() -> Response:
    return Response(status_code=status.HTTP_200_OK)
```

### GET:/api/users

```text
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
```

### POST:/api/users

```text
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
```

### POST:/api/users/batch

```text
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
```

### PATCH:/api/users/batch/status

```text
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
```

### GET:/api/users/{user_id}

```text
@app.get("/api/users/{user_id}")
def get_user(user_id: str, _: str = Depends(_require_auth)) -> dict[str, Any]:
    return _must_get_user(user_id)
```

### PUT:/api/users/{user_id}

```text
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
```

### PATCH:/api/users/{user_id}

```text
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
```

### DELETE:/api/users/{user_id}

```text
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
```

### GET:/api/users/{user_id}/orders

```text
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
```

### POST:/api/users/{user_id}/orders

```text
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
```

### POST:/api/orders/batch/cancel

```text
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
```

### POST:/api/feedback/form

```text
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
```

### POST:/api/upload/avatar

```text
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
```

### GET:/api/echo/headers

```text
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
```

### GET:/api/echo/cookies

```text
@app.get("/api/echo/cookies")
def echo_cookies(
    session_token: str | None = Cookie(default=None),
    locale: str | None = Cookie(default=None),
) -> dict[str, Any]:
    return {
        "session_token": session_token,
        "locale": locale,
    }
```

### GET:/api/export/users.csv

```text
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
```

### GET:/api/stream/notifications

```text
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
```

### POST:/api/jobs

```text
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
```

### GET:/api/jobs/{job_id}

```text
@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, _: str = Depends(_require_auth)) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job
```

### PATCH:/api/jobs/{job_id}

```text
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
```

### DELETE:/api/jobs/{job_id}

```text
@app.delete("/api/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, _: str = Depends(_require_auth)) -> Response:
    JOBS.pop(job_id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

### POST:/api/payments

```text
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
```

### POST:/api/webhooks/order-updated

```text
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
```
