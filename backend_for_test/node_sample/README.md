# Node.js 标准测试项目

这是用于 LUI-for-All 的 Node.js（Express）示例后端，目标是覆盖常见后端请求类型与操作，方便做能力发现和自动化回归测试。

## 运行

```bash
npm install
npm run start
```

默认端口 `8020`，可通过环境变量 `PORT` 覆盖。

## OpenAPI

- OpenAPI: `http://localhost:8020/openapi.json`
- 模拟 AI SSE: `POST http://localhost:8020/v1/chat/completions`，兼容 `stream=true` 和非流式 JSON；流式输出约 50 字符/秒，末帧带 `usage`，最后发送 `[DONE]`。

## 覆盖范围

- 请求方法: `GET` `POST` `PUT` `PATCH` `DELETE` `HEAD` `OPTIONS`
- 参数类型: Path / Query / Header / Cookie / JSON Body / Form URL Encoded / Raw 上传
- 返回类型: JSON / CSV 文件下载 / SSE 流式事件
- 业务操作: 登录鉴权、用户 CRUD、批量更新、嵌套资源、任务状态、幂等支付、Webhook
