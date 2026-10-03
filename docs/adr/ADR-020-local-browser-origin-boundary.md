# ADR-020：本地 API 浏览器来源边界

## 状态

Accepted（2026-10-03）。负责人授权严格架构审查及修复；依据 V0.6 的本地单用户、密钥仅在后端和安全边界要求。

## 问题与决策

API 的通配 CORS 会向任意网页开放本地历史读取和任务提交；后端持有 Key，即使 Key 不返回浏览器，外部网页仍可能消耗模型配额。仅收紧 CORS 响应头不足以阻止不经预检的有副作用请求。

- 在路由执行前检查实际 Origin：只允许 `http://127.0.0.1`、`http://localhost`、`http://[::1]` 的 5173（开发）、4173（预览）、8000（API 文档）端口；不可信来源包括 `null`，均返回现有 ErrorResponse 结构的 403 `ORIGIN_NOT_ALLOWED`。
- CORS 使用同一精确列表，只允许 GET/POST/OPTIONS 与 Content-Type，不启用 credentials。无 Origin 的本机 CLI/API 客户端继续可用。
- 不引入登录、用户权限或数据库，不修改 Domain、持久化 Schema、评分或模型名单。这是浏览器边界加固，不能代替身份认证；API 仍必须绑定 loopback，不作为公网部署方案。

## 验证

离线测试覆盖不可信来源的读取、直接 POST 与预检在 Provider 前拒绝；受信本地网页和无 Origin 客户端完成 Fake Episode；原 API/流式/Job 测试继续通过。
