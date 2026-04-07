# backend_for_test

这里放置两个标准示例后端，用于给 LUI-for-All 做能力发现与执行链路测试。

## 项目列表

- `fastapi_sample`：FastAPI 版本，自动提供 Swagger / OpenAPI。
- `node_sample`：Node.js (Express) 版本，手工暴露 `openapi.json`。

## 覆盖目标

- 常见方法：`GET` `POST` `PUT` `PATCH` `DELETE` `HEAD` `OPTIONS`
- 常见入参：Path / Query / Header / Cookie / JSON / Form / Multipart(或Raw)
- 常见返回：JSON / CSV 下载 / SSE 流式
- 常见操作：登录鉴权、CRUD、批量、嵌套资源、任务状态、幂等、Webhook

## 与 LUI-for-All 对接建议

### FastAPI 示例

- Base URL: `http://localhost:8010`
- OpenAPI URL: `http://localhost:8010/openapi.json`
- 登录接口 route_id: `POST:/api/auth/login`
- 用户名字段: `username`
- 密码字段: `password`
- 登录测试账号: `111`
- 登录测试密码: `111111`

### Node 示例

- Base URL: `http://localhost:8020`
- OpenAPI URL: `http://localhost:8020/openapi.json`
- 登录接口 route_id: `POST:/api/auth/login`
- 用户名字段: `username`
- 密码字段: `password`
- 登录测试账号: `111`
- 登录测试密码: `111111`

> 这两个示例服务都使用内存数据，仅用于测试，不需要持久化卷。
