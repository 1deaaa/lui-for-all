# Route Extraction Result: node_sample

- Adapter: nodejs_typescript
- Source Path: C:\Users\SERVER\Desktop\lui-for-all\backend_for_test\node_sample
- Route Count: 30

## Route List

1. GET:/health | GET /health | server.js:245-247
2. GET:/openapi.json | GET /openapi.json | server.js:249-252
3. POST:/api/auth/login | POST /api/auth/login | server.js:254-270
4. POST:/api/auth/logout | POST /api/auth/logout | server.js:272-277
5. GET:/api/auth/me | GET /api/auth/me | server.js:279-286
6. OPTIONS:/api/users | OPTIONS /api/users | server.js:288-291
7. HEAD:/api/users | HEAD /api/users | server.js:293-295
8. GET:/api/users | GET /api/users | server.js:297-332
9. POST:/api/users | POST /api/users | server.js:44-52
10. POST:/api/users/batch | POST /api/users/batch | server.js:44-52
11. PATCH:/api/users/batch/status | PATCH /api/users/batch/status | server.js:44-52
12. GET:/api/users/{userId} | GET /api/users/{userId} | server.js:44-52
13. PUT:/api/users/{userId} | PUT /api/users/{userId} | server.js:44-52
14. PATCH:/api/users/{userId} | PATCH /api/users/{userId} | server.js:44-52
15. DELETE:/api/users/{userId} | DELETE /api/users/{userId} | server.js:44-52
16. GET:/api/users/{userId}/orders | GET /api/users/{userId}/orders | server.js:44-52
17. POST:/api/users/{userId}/orders | POST /api/users/{userId}/orders | server.js:44-52
18. POST:/api/orders/batch/cancel | POST /api/orders/batch/cancel | server.js:44-52
19. POST:/api/feedback/form | POST /api/feedback/form | server.js:512-519
20. POST:/api/upload/avatar | POST /api/upload/avatar | server.js:521-538
21. GET:/api/echo/headers | GET /api/echo/headers | server.js:540-551
22. GET:/api/echo/cookies | GET /api/echo/cookies | server.js:553-559
23. GET:/api/export/users.csv | GET /api/export/users.csv | server.js:44-52
24. GET:/api/stream/notifications | GET /api/stream/notifications | server.js:571-600
25. POST:/api/jobs | POST /api/jobs | server.js:44-52
26. GET:/api/jobs/{jobId} | GET /api/jobs/{jobId} | server.js:44-52
27. PATCH:/api/jobs/{jobId} | PATCH /api/jobs/{jobId} | server.js:44-52
28. DELETE:/api/jobs/{jobId} | DELETE /api/jobs/{jobId} | server.js:44-52
29. POST:/api/payments | POST /api/payments | server.js:44-52
30. POST:/api/webhooks/order-updated | POST /api/webhooks/order-updated | server.js:684-692

## Function Implementation Blocks

### GET:/health

```text
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'node-sample' });
});
```

### GET:/openapi.json

```text
app.get('/openapi.json', (req, res) => {
  const serverUrl = `${req.protocol}://${req.get('host')}`;
  res.json(buildOpenApiSpec(serverUrl));
});
```

### POST:/api/auth/login

```text
app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password) {
    res.status(400).json({ detail: 'username 和 password 必填' });
    return;
  }

  if (username !== LOGIN_USERNAME || password !== LOGIN_PASSWORD) {
    res.status(401).json({ detail: '用户名或密码错误' });
    return;
  }

  const token = `token-${crypto.randomUUID().replace(/-/g, '')}`;
  tokens.set(token, username);
  res.setHeader('Set-Cookie', `session_token=${encodeURIComponent(token)}; HttpOnly; Path=/`);
  res.json({ access_token: token, token_type: 'bearer', expires_in: 3600, username });
});
```

### POST:/api/auth/logout

```text
app.post('/api/auth/logout', (req, res) => {
  const token = getToken(req);
  if (token) tokens.delete(token);
  res.setHeader('Set-Cookie', 'session_token=; Max-Age=0; Path=/');
  res.json({ success: true });
});
```

### GET:/api/auth/me

```text
app.get('/api/auth/me', (req, res) => {
  const debugUser = req.get('X-Debug-User');
  if (debugUser) {
    res.json({ username: debugUser, source: 'header' });
    return;
  }
  res.json({ username: 'anonymous', source: 'default' });
});
```

### OPTIONS:/api/users

```text
app.options('/api/users', (req, res) => {
  res.setHeader('Allow', 'GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS');
  res.status(204).send();
});
```

### HEAD:/api/users

```text
app.head('/api/users', (req, res) => {
  res.status(200).send();
});
```

### GET:/api/users

```text
app.get('/api/users', (req, res) => {
  const q = String(req.query.q || '').trim().toLowerCase();
  const active = req.query.active;
  const role = req.query.role ? String(req.query.role) : null;
  const sort = req.query.sort === 'name' ? 'name' : 'created_at';
  const order = req.query.order === 'desc' ? 'desc' : 'asc';
  const offset = Math.max(0, Number(req.query.offset || 0));
  const limit = Math.min(200, Math.max(1, Number(req.query.limit || 20)));

  let items = Array.from(users.values());
  if (q) {
    items = items.filter((item) => item.name.toLowerCase().includes(q) || item.email.toLowerCase().includes(q));
  }
  if (active !== undefined) {
    const activeBool = String(active) === 'true';
    items = items.filter((item) => item.active === activeBool);
  }
  if (role) {
    items = items.filter((item) => item.role === role);
  }

  items.sort((a, b) => {
    const left = a[sort];
    const right = b[sort];
    if (left === right) return 0;
    if (order === 'asc') return left > right ? 1 : -1;
    return left < right ? 1 : -1;
  });

  res.json({
    total: items.length,
    offset,
    limit,
    items: items.slice(offset, offset + limit),
  });
});
```

### POST:/api/users

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### POST:/api/users/batch

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### PATCH:/api/users/batch/status

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### GET:/api/users/{userId}

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### PUT:/api/users/{userId}

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### PATCH:/api/users/{userId}

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### DELETE:/api/users/{userId}

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### GET:/api/users/{userId}/orders

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### POST:/api/users/{userId}/orders

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### POST:/api/orders/batch/cancel

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### POST:/api/feedback/form

```text
app.post('/api/feedback/form', (req, res) => {
  const { contact, message, rating = 5 } = req.body || {};
  if (!contact || !message) {
    res.status(400).json({ detail: 'contact 和 message 必填' });
    return;
  }
  res.json({ contact, message, rating: Number(rating), received_at: now() });
});
```

### POST:/api/upload/avatar

```text
app.post('/api/upload/avatar', express.raw({ type: '*/*', limit: '10mb' }), authRequired, (req, res) => {
  const userId = req.query.user_id ? String(req.query.user_id) : '';
  if (!userId) {
    res.status(400).json({ detail: 'query 参数 user_id 必填' });
    return;
  }
  const user = mustGetUser(userId, res);
  if (!user) return;

  const body = Buffer.isBuffer(req.body) ? req.body : Buffer.from('');
  res.json({
    user_id: userId,
    filename: req.get('X-File-Name') || 'blob.bin',
    content_type: req.get('Content-Type') || 'application/octet-stream',
    size: body.length,
    uploaded_at: now(),
  });
});
```

### GET:/api/echo/headers

```text
app.get('/api/echo/headers', (req, res) => {
  const requestId = req.get('X-Request-ID');
  if (!requestId) {
    res.status(400).json({ detail: '缺少 X-Request-ID' });
    return;
  }
  res.json({
    x_request_id: requestId,
    x_trace_id: req.get('X-Trace-ID') || null,
    received_at: now(),
  });
});
```

### GET:/api/echo/cookies

```text
app.get('/api/echo/cookies', (req, res) => {
  const cookies = parseCookies(req.headers.cookie);
  res.json({
    session_token: cookies.session_token || null,
    locale: cookies.locale || null,
  });
});
```

### GET:/api/export/users.csv

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### GET:/api/stream/notifications

```text
app.get('/api/stream/notifications', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  let count = 0;
  const timer = setInterval(() => {
    count += 1;
    const payload = {
      id: count,
      topic: 'demo.notification',
      message: `第 ${count} 条实时事件`,
      created_at: now(),
    };
    res.write(`id: ${count}\n`);
    res.write('event: notification\n');
    res.write(`data: ${JSON.stringify(payload)}\n\n`);

    if (count >= 5) {
      res.write('event: done\n');
      res.write('data: stream completed\n\n');
      clearInterval(timer);
      res.end();
    }
  }, 400);

  req.on('close', () => {
    clearInterval(timer);
  });
});
```

### POST:/api/jobs

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### GET:/api/jobs/{jobId}

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### PATCH:/api/jobs/{jobId}

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### DELETE:/api/jobs/{jobId}

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### POST:/api/payments

```text
function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}
```

### POST:/api/webhooks/order-updated

```text
app.post('/api/webhooks/order-updated', (req, res) => {
  const signature = req.get('X-Signature') || '';
  res.status(202).json({
    accepted: true,
    signature_valid: signature === 'test-signature',
    received_payload: req.body || {},
    received_at: now(),
  });
});
```
