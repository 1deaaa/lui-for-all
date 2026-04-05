const express = require('express');
const crypto = require('crypto');

const app = express();
const PORT = Number(process.env.PORT || 8020);

app.use(express.json({ limit: '2mb' }));
app.use(express.urlencoded({ extended: false }));

const users = new Map();
const orders = new Map();
const jobs = new Map();
const idempotencyPayments = new Map();
const tokens = new Map();

function now() {
  return new Date().toISOString();
}

function parseCookies(cookieHeader) {
  if (!cookieHeader) return {};
  return cookieHeader
    .split(';')
    .map((item) => item.trim())
    .filter(Boolean)
    .reduce((acc, item) => {
      const [key, ...rest] = item.split('=');
      acc[key] = decodeURIComponent(rest.join('='));
      return acc;
    }, {});
}

function getToken(req) {
  const auth = req.headers.authorization;
  if (auth && auth.startsWith('Bearer ')) {
    return auth.replace('Bearer ', '').trim();
  }
  const cookies = parseCookies(req.headers.cookie);
  return cookies.session_token || null;
}

function authRequired(req, res, next) {
  const token = getToken(req);
  if (!token || !tokens.has(token)) {
    res.status(401).json({ detail: '认证无效或已过期' });
    return;
  }
  req.username = tokens.get(token);
  next();
}

function mustGetUser(userId, res) {
  const user = users.get(userId);
  if (!user) {
    res.status(404).json({ detail: `用户 ${userId} 不存在` });
    return null;
  }
  return user;
}

function seedData() {
  if (users.size > 0) return;

  const alice = {
    id: 'u-2001',
    name: 'Carol',
    email: 'carol@example.local',
    role: 'admin',
    active: true,
    tags: ['analytics', 'ops'],
    created_at: now(),
    updated_at: now(),
  };
  const bob = {
    id: 'u-2002',
    name: 'Dave',
    email: 'dave@example.local',
    role: 'user',
    active: true,
    tags: ['support'],
    created_at: now(),
    updated_at: now(),
  };

  users.set(alice.id, alice);
  users.set(bob.id, bob);
  orders.set(alice.id, [
    {
      id: 'o-7001',
      user_id: alice.id,
      product: 'Mouse',
      quantity: 1,
      unit_price: 99,
      status: 'created',
      created_at: now(),
    },
  ]);
  orders.set(bob.id, []);
}

function buildOpenApiSpec(serverUrl) {
  return {
    openapi: '3.1.0',
    info: {
      title: 'LUI Node Standard Test Backend',
      version: '1.0.0',
      description: '用于 LUI-for-All 的 Node.js 标准测试服务，内存数据、零复杂依赖。',
    },
    servers: [{ url: serverUrl }],
    paths: {
      '/health': {
        get: { summary: '健康检查', responses: { '200': { description: 'OK' } } },
      },
      '/api/auth/login': {
        post: {
          summary: '登录并获取 token',
          requestBody: {
            required: true,
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  required: ['username', 'password'],
                  properties: {
                    username: { type: 'string' },
                    password: { type: 'string' },
                  },
                },
              },
            },
          },
          responses: { '200': { description: '登录成功' } },
        },
      },
      '/api/auth/logout': {
        post: { summary: '退出登录', responses: { '200': { description: '退出成功' } } },
      },
      '/api/auth/me': {
        get: { summary: '获取当前用户', responses: { '200': { description: '用户信息' } } },
      },
      '/api/users': {
        get: { summary: '分页查询用户', responses: { '200': { description: '用户列表' } } },
        post: { summary: '创建用户', responses: { '201': { description: '创建成功' } } },
        options: { summary: '查询允许的方法', responses: { '204': { description: 'No Content' } } },
        head: { summary: '用户资源头信息', responses: { '200': { description: 'OK' } } },
      },
      '/api/users/batch': {
        post: { summary: '批量创建用户', responses: { '201': { description: '创建成功' } } },
      },
      '/api/users/batch/status': {
        patch: { summary: '批量修改用户状态', responses: { '200': { description: '更新成功' } } },
      },
      '/api/users/{userId}': {
        get: { summary: '查询单个用户', responses: { '200': { description: '查询成功' } } },
        put: { summary: '全量更新用户', responses: { '200': { description: '更新成功' } } },
        patch: { summary: '部分更新用户', responses: { '200': { description: '更新成功' } } },
        delete: { summary: '删除用户', responses: { '200': { description: '删除成功' } } },
      },
      '/api/users/{userId}/orders': {
        get: { summary: '查询用户订单', responses: { '200': { description: '查询成功' } } },
        post: { summary: '创建用户订单', responses: { '201': { description: '创建成功' } } },
      },
      '/api/orders/batch/cancel': {
        post: { summary: '批量取消订单', responses: { '200': { description: '取消结果' } } },
      },
      '/api/feedback/form': {
        post: {
          summary: 'URL Encoded 表单提交',
          requestBody: {
            content: {
              'application/x-www-form-urlencoded': {
                schema: {
                  type: 'object',
                  properties: {
                    contact: { type: 'string' },
                    message: { type: 'string' },
                    rating: { type: 'integer' },
                  },
                },
              },
            },
          },
          responses: { '200': { description: '提交成功' } },
        },
      },
      '/api/upload/avatar': {
        post: {
          summary: '原始文件上传示例',
          requestBody: {
            content: {
              'application/octet-stream': {
                schema: { type: 'string', format: 'binary' },
              },
            },
          },
          responses: { '200': { description: '上传成功' } },
        },
      },
      '/api/echo/headers': {
        get: { summary: '回显请求头', responses: { '200': { description: '回显成功' } } },
      },
      '/api/echo/cookies': {
        get: { summary: '回显 Cookie', responses: { '200': { description: '回显成功' } } },
      },
      '/api/export/users.csv': {
        get: { summary: '导出 CSV', responses: { '200': { description: 'CSV 内容' } } },
      },
      '/api/stream/notifications': {
        get: {
          summary: 'SSE 流式消息',
          responses: {
            '200': {
              description: 'SSE 事件流',
              content: {
                'text/event-stream': {
                  schema: { type: 'string' },
                },
              },
            },
          },
        },
      },
      '/api/jobs': {
        post: { summary: '创建异步任务', responses: { '202': { description: '已受理' } } },
      },
      '/api/jobs/{jobId}': {
        get: { summary: '查询任务', responses: { '200': { description: '查询成功' } } },
        patch: { summary: '更新任务状态', responses: { '200': { description: '更新成功' } } },
        delete: { summary: '删除任务', responses: { '204': { description: '删除成功' } } },
      },
      '/api/payments': {
        post: { summary: '幂等支付创建', responses: { '201': { description: '创建成功' } } },
      },
      '/api/webhooks/order-updated': {
        post: { summary: 'Webhook 接收', responses: { '202': { description: '已受理' } } },
      },
    },
  };
}

seedData();

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'node-sample' });
});

app.get('/openapi.json', (req, res) => {
  const serverUrl = `${req.protocol}://${req.get('host')}`;
  res.json(buildOpenApiSpec(serverUrl));
});

app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password) {
    res.status(400).json({ detail: 'username 和 password 必填' });
    return;
  }

  const token = `token-${crypto.randomUUID().replace(/-/g, '')}`;
  tokens.set(token, username);
  res.setHeader('Set-Cookie', `session_token=${encodeURIComponent(token)}; HttpOnly; Path=/`);
  res.json({ access_token: token, token_type: 'bearer', expires_in: 3600, username });
});

app.post('/api/auth/logout', (req, res) => {
  const token = getToken(req);
  if (token) tokens.delete(token);
  res.setHeader('Set-Cookie', 'session_token=; Max-Age=0; Path=/');
  res.json({ success: true });
});

app.get('/api/auth/me', (req, res) => {
  const debugUser = req.get('X-Debug-User');
  if (debugUser) {
    res.json({ username: debugUser, source: 'header' });
    return;
  }
  res.json({ username: 'anonymous', source: 'default' });
});

app.options('/api/users', (req, res) => {
  res.setHeader('Allow', 'GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS');
  res.status(204).send();
});

app.head('/api/users', (req, res) => {
  res.status(200).send();
});

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

app.post('/api/users', authRequired, (req, res) => {
  const { name, email, role = 'user', active = true, tags = [] } = req.body || {};
  if (!name || !email) {
    res.status(400).json({ detail: 'name 和 email 必填' });
    return;
  }

  const id = `u-${crypto.randomUUID().slice(0, 8)}`;
  const user = {
    id,
    name,
    email,
    role,
    active: Boolean(active),
    tags: Array.isArray(tags) ? tags : [],
    created_at: now(),
    updated_at: now(),
    created_by: req.username,
  };

  users.set(id, user);
  if (!orders.has(id)) orders.set(id, []);
  res.status(201).json(user);
});

app.post('/api/users/batch', authRequired, (req, res) => {
  const list = Array.isArray(req.body?.users) ? req.body.users : [];
  const created = [];

  for (const item of list) {
    if (!item?.name || !item?.email) continue;
    const id = `u-${crypto.randomUUID().slice(0, 8)}`;
    const user = {
      id,
      name: item.name,
      email: item.email,
      role: item.role || 'user',
      active: item.active !== undefined ? Boolean(item.active) : true,
      tags: Array.isArray(item.tags) ? item.tags : [],
      created_at: now(),
      updated_at: now(),
      created_by: req.username,
    };
    users.set(id, user);
    orders.set(id, []);
    created.push(user);
  }

  res.status(201).json({ count: created.length, items: created });
});

app.patch('/api/users/batch/status', authRequired, (req, res) => {
  const userIds = Array.isArray(req.body?.user_ids) ? req.body.user_ids : [];
  const active = Boolean(req.body?.active);
  let updated = 0;

  for (const userId of userIds) {
    if (!users.has(userId)) continue;
    const user = users.get(userId);
    user.active = active;
    user.updated_at = now();
    updated += 1;
  }

  res.json({ requested: userIds.length, updated, active });
});

app.get('/api/users/:userId', authRequired, (req, res) => {
  const user = mustGetUser(req.params.userId, res);
  if (!user) return;
  res.json(user);
});

app.put('/api/users/:userId', authRequired, (req, res) => {
  const user = mustGetUser(req.params.userId, res);
  if (!user) return;

  const { name, email, role, active, tags = [] } = req.body || {};
  if (!name || !email || !role || active === undefined) {
    res.status(400).json({ detail: 'name/email/role/active 必填' });
    return;
  }

  user.name = name;
  user.email = email;
  user.role = role;
  user.active = Boolean(active);
  user.tags = Array.isArray(tags) ? tags : [];
  user.updated_at = now();
  res.json(user);
});

app.patch('/api/users/:userId', authRequired, (req, res) => {
  const user = mustGetUser(req.params.userId, res);
  if (!user) return;

  const patch = req.body || {};
  if (patch.name !== undefined) user.name = patch.name;
  if (patch.email !== undefined) user.email = patch.email;
  if (patch.role !== undefined) user.role = patch.role;
  if (patch.active !== undefined) user.active = Boolean(patch.active);
  if (patch.tags !== undefined) user.tags = Array.isArray(patch.tags) ? patch.tags : user.tags;
  user.updated_at = now();
  res.json(user);
});

app.delete('/api/users/:userId', authRequired, (req, res) => {
  const user = mustGetUser(req.params.userId, res);
  if (!user) return;

  const hard = String(req.query.hard || 'false') === 'true';
  if (hard) {
    users.delete(req.params.userId);
    orders.delete(req.params.userId);
    res.json({ deleted: true, hard: true, user_id: req.params.userId });
    return;
  }

  user.active = false;
  user.deleted_at = now();
  user.updated_at = now();
  res.json({ deleted: true, hard: false, user_id: req.params.userId });
});

app.get('/api/users/:userId/orders', authRequired, (req, res) => {
  const user = mustGetUser(req.params.userId, res);
  if (!user) return;

  const statusFilter = req.query.status ? String(req.query.status) : null;
  let items = orders.get(req.params.userId) || [];
  if (statusFilter) {
    items = items.filter((item) => item.status === statusFilter);
  }
  res.json({ total: items.length, items });
});

app.post('/api/users/:userId/orders', authRequired, (req, res) => {
  const user = mustGetUser(req.params.userId, res);
  if (!user) return;

  const { product, quantity = 1, unit_price = 1 } = req.body || {};
  if (!product) {
    res.status(400).json({ detail: 'product 必填' });
    return;
  }

  const order = {
    id: `o-${crypto.randomUUID().slice(0, 8)}`,
    user_id: req.params.userId,
    product,
    quantity: Number(quantity) > 0 ? Number(quantity) : 1,
    unit_price: Number(unit_price) > 0 ? Number(unit_price) : 1,
    status: 'created',
    created_at: now(),
  };

  const list = orders.get(req.params.userId) || [];
  list.push(order);
  orders.set(req.params.userId, list);
  res.status(201).json(order);
});

app.post('/api/orders/batch/cancel', authRequired, (req, res) => {
  const orderIds = Array.isArray(req.body?.order_ids) ? req.body.order_ids : [];
  let cancelled = 0;

  for (const [, orderList] of orders.entries()) {
    for (const item of orderList) {
      if (orderIds.includes(item.id) && item.status !== 'cancelled') {
        item.status = 'cancelled';
        cancelled += 1;
      }
    }
  }

  res.json({ requested: orderIds.length, cancelled });
});

app.post('/api/feedback/form', (req, res) => {
  const { contact, message, rating = 5 } = req.body || {};
  if (!contact || !message) {
    res.status(400).json({ detail: 'contact 和 message 必填' });
    return;
  }
  res.json({ contact, message, rating: Number(rating), received_at: now() });
});

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

app.get('/api/echo/cookies', (req, res) => {
  const cookies = parseCookies(req.headers.cookie);
  res.json({
    session_token: cookies.session_token || null,
    locale: cookies.locale || null,
  });
});

app.get('/api/export/users.csv', authRequired, (req, res) => {
  const lines = ['id,name,email,role,active'];
  for (const item of users.values()) {
    lines.push(`${item.id},${item.name},${item.email},${item.role},${item.active}`);
  }
  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename=users.csv');
  res.send(lines.join('\n'));
});

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

app.post('/api/jobs', authRequired, (req, res) => {
  const kind = req.body?.kind;
  if (!kind) {
    res.status(400).json({ detail: 'kind 必填' });
    return;
  }

  const job = {
    id: `j-${crypto.randomUUID().slice(0, 8)}`,
    kind,
    payload: req.body?.payload || {},
    status: 'pending',
    created_at: now(),
    updated_at: now(),
  };
  jobs.set(job.id, job);
  res.status(202).json(job);
});

app.get('/api/jobs/:jobId', authRequired, (req, res) => {
  const job = jobs.get(req.params.jobId);
  if (!job) {
    res.status(404).json({ detail: '任务不存在' });
    return;
  }
  res.json(job);
});

app.patch('/api/jobs/:jobId', authRequired, (req, res) => {
  const job = jobs.get(req.params.jobId);
  if (!job) {
    res.status(404).json({ detail: '任务不存在' });
    return;
  }

  const status = req.body?.status;
  const allowed = new Set(['pending', 'running', 'done', 'failed']);
  if (!allowed.has(status)) {
    res.status(400).json({ detail: 'status 非法' });
    return;
  }

  job.status = status;
  job.updated_at = now();
  res.json(job);
});

app.delete('/api/jobs/:jobId', authRequired, (req, res) => {
  jobs.delete(req.params.jobId);
  res.status(204).send();
});

app.post('/api/payments', authRequired, (req, res) => {
  const idempotencyKey = req.get('Idempotency-Key');
  if (!idempotencyKey) {
    res.status(400).json({ detail: '缺少 Idempotency-Key' });
    return;
  }

  if (idempotencyPayments.has(idempotencyKey)) {
    res.json({ idempotency_hit: true, ...idempotencyPayments.get(idempotencyKey) });
    return;
  }

  const amount = Number(req.body?.amount || 0);
  if (!(amount > 0)) {
    res.status(400).json({ detail: 'amount 必须大于 0' });
    return;
  }

  const payment = {
    payment_id: `pay-${crypto.randomUUID().slice(0, 8)}`,
    amount,
    currency: req.body?.currency || 'CNY',
    remark: req.body?.remark || null,
    status: 'accepted',
    created_at: now(),
  };
  idempotencyPayments.set(idempotencyKey, payment);
  res.status(201).json({ idempotency_hit: false, ...payment });
});

app.post('/api/webhooks/order-updated', (req, res) => {
  const signature = req.get('X-Signature') || '';
  res.status(202).json({
    accepted: true,
    signature_valid: signature === 'test-signature',
    received_payload: req.body || {},
    received_at: now(),
  });
});

app.use((req, res) => {
  res.status(404).json({ detail: '路由不存在', path: req.path, method: req.method });
});

app.listen(PORT, () => {
  console.log(`[node-sample] listening on :${PORT}`);
});
