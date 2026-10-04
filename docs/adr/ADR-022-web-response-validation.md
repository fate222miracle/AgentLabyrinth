# ADR-022：Web 响应校验与浏览器回归门禁

- 状态：Accepted
- 日期：2026-10-03
- 依据：需求 V0.6 §25.2、§25.7、§27；负责人授权继续 V0.2 收尾。

## 背景与决策

TypeScript 接口不能验证网络 JSON。页面现有类型转换允许损坏事件、未知 Job 状态和错配 ID 进入动画或统计。使用 Zod 作为轻量 Web 边界依赖，从消费字段的 Schema 推导静态类型；保留未知扩展字段，明确接受既有版本，历史可选指标不赋零。后端 Pydantic 是公开契约来源，本次 Web Schema 只验证页面消费的投影，不建立替代领域需求；后端契约变化仍先按需求走 ADR，并同步投影测试。

统一 HTTP JSON 校验和错误读取，历史详情及 Job 控制另核对请求 ID；SSE Trace 与 complete 使用相同校验。校验错误只提供字段路径，不回显原始值或堆栈。费用仍是字符串 Decimal，未知费用与历史指标仍保留未知。

增加需求已指定的 Playwright 测试工具，仅开发依赖；实际启动隔离 Fake API 与 Vite，拒绝复用现有服务，不读取 .env 或调用真实模型。运行结果置于忽略目录。测试使用独立 Artifact 目录，每次运行不依赖旧历史。GitHub Actions 与本地统一检查，发布后才可确认远端 CI。

## 候选、代价和回滚

手写逐字段 guards 容易遗漏且静态接口与规则分离；全量生成 Pydantic Schema 再引入验证器会把未消费的历史默认值兼容问题带到 UI。选用维护活跃、MIT 的 Zod 4.6.5 Mini 入口；现有 React/TypeScript 不提供运行时校验。构建压缩 JS 相比上一轮增加约 11 KB，费用保持字符串且不做隐式转换。Playwright 1.63.0 为 Apache-2.0，仅测试用；Node 22 类型依赖为 MIT。浏览器安装耗时不进入产品依赖，本机可显式选择已安装的 Edge/Chrome，CI 默认锁定 Chromium。

官方资料：[Zod 类型推导与解析](https://zod.dev/basics)、[Zod Mini](https://zod.dev/packages/mini)、[Playwright CI](https://playwright.dev/docs/ci)。精确版本写入 package-lock；不引入通用状态框架或基础设施。回滚可移除验证层和测试依赖，后端 API、历史 JSON 和评分不变；不应恢复将未知数据直接展示为有效结果的行为。
