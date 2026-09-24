# 四个新模型真实示例验收

2026-09-20，用户授权放行截图中四个模型。调用本机 AIHubMix Key，通过真实 EpisodeService → Runtime → Provider → Executor → Evaluator 运行，每个模型使用相同两道题；无自动重试、无模型替换。

运行：`uv run python -m scripts.verify_selected_models`。完整 Trace 在 `artifacts/{episode_id}.json`，汇总在 `artifacts/selected-model-results.json`。这些本地产物不包含 API Key，不入库。

预算：每任务总 Token 20000，单次输出 1024，BFCL 最多 1 步，订单最多 6 步；原任务与严格评测规则保持一致，预算覆盖写入产物。四个模型已通过共享后端允许列表，网页默认改为小米。

| 模型 | BFCL simple_python_0 | ToolLab order-status-001 | 结论 |
| --- | --- | --- | --- |
| deepseek-v4-flash-0731-free | 无可用通道 | 无可用通道 | 上游通道问题 |
| qwen3.8-27b-free | 限流 | 限流 | 供应商限额，未测到模型行为 |
| xiaomi-mimo-v2.5-pro-free | 通过，502 Tokens | 通过，2261 Tokens | 两题真实闭环通过 |
| coding-minimax-m2.7-free | 通过，391 Tokens | 通过，1814 Tokens | 两题真实闭环通过 |

成功证据：

- 小米 BFCL：`43895e64-447e-487c-93aa-2f5fa2c418e8`，1 次模型调用、1 次工具调用，`exact_call_match`。
- 小米订单：`f64d6abe-a1dd-4ca8-9bb2-6152ef701198`，2 次模型调用、2 次工具调用，`submission_matched_target`。
- MiniMax BFCL：`b3b9f69b-b68e-4372-ad95-b6cce0e7ee66`，1 次模型调用、1 次工具调用，`exact_call_match`。
- MiniMax 订单：`09b8e251-43a6-4acd-89ab-f7b07b63dc0c`，2 次模型调用、2 次工具调用，`submission_matched_target`。

结论仅覆盖各模型本次两道示例，不能解释为全量 BFCL 成绩或长期可用性保证。BFCL 使用平台本地改编评分协议。

## 2026-09-21 复测

同一验证脚本再次执行四模型 × 两任务，结果与前一日一致。脚本已统一使用 Provider 的安全 Key 读取逻辑，因此支持进程环境变量或被 Git 忽略的项目 `.env`，不输出 Key。

| 模型 | BFCL | ToolLab | 本轮结论 |
| --- | --- | --- | --- |
| deepseek-v4-flash-0731-free | 失败：`UPSTREAM_CHANNEL_UNAVAILABLE` | 失败：`UPSTREAM_CHANNEL_UNAVAILABLE` | 上游无可用通道 |
| qwen3.8-27b-free | 失败：`RATE_LIMIT_EXCEEDED` | 失败：`RATE_LIMIT_EXCEEDED` | 上游限流 |
| xiaomi-mimo-v2.5-pro-free | 通过，512 Tokens，`05a121da-711d-4c07-a270-af1b9c331010` | 通过，2915 Tokens，`d95ba328-17f9-4950-9acd-99f3eb740839` | 两个真实闭环均通过 |
| coding-minimax-m2.7-free | 通过，388 Tokens，`2677fcce-7cae-451a-bb81-abcbcccb3f97` | 通过，2294 Tokens，`30a98b83-8787-4c89-b8eb-9d6887a5ee88` | 两个真实闭环均通过 |

本轮可用率按“两个示例均通过”统计为 **2/4**。这是网关当时状态与两个固定样例的结果，不是模型排行榜。

## 2026-09-23 可用目录与网络故障复核

失败 Episode `eaa48e6a-8f3a-4d48-8ebb-2f258aa2152a` 与 `f57c1847-feda-438b-90f8-f8e20fe2815e` 都在模型调用前返回 `NETWORK_CONNECTION_FAILED`，耗时约 200 ms，Token 为 0。根因为本机 API 进程继承了 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY=http://127.0.0.1:9`，该代理端口没有服务监听，请求没有到达 AIHubMix。重启 API 时使用不带该失效代理的本机环境后，模型调用恢复。

向官方主域 `https://aihubmix.com/v1/models` 发起只读目录请求，HTTP 200；当前 API Key 可访问的模型只有 `coding-minimax-m2.7-free` 与 `xiaomi-mimo-v2.5-pro-free`。MiniMax BFCL 单题 Episode `032ac2bb-0ae7-4b30-b9d0-4db9ef3becdb` 与截图对应 MiMo BFCL 重跑 Episode `24b010eb-22f9-4f04-b2b6-c954d256239f` 均 SUCCESS、`exact_call_match`、各 1 次模型调用及 1 次工具调用。

`benchmarks/tool_lab_core/models.json` 现在只保留这两个账号可见且此前通过真实工具任务的候选，默认改为 MiniMax M2.7。后台 `/api/v1/meta` 每 5 分钟刷新一次 Key 级 `/v1/models` 目录，只呈现其与这份已验证候选表的交集；目录无法访问时只提供 Fake 并报告状态。执行端也拒绝 Key 目录中已不可见的模型。新增候选需先在目录文件登记并跑真实工具任务后才能显示。

AIHubMix 官方免费模型目录在 2026-09-22 显示 60 个免费模型；这不代表当前 Key 都有访问权限。官方退役列表显示 MiMo V2.5 Pro 将于 2026-10-21 退役，建议迁移到 MiMo V2.6 Pro；当前 Key 目录尚未开放该替代模型。因此 MiMo V2.5 Pro 标为临近退役备选，不再作为默认。目录和模型生命周期链接：[免费模型目录](https://aihubmix.com/models/free)、[模型退役列表](https://aihubmix.com/models/retirements)。

## 绕过平台的故障定位复验

四个模型均已通过 `is_model_permitted`。再对 DeepSeek 与 Qwen 各发送一次直接 HTTP 普通聊天请求（无工具、无 Runtime、无平台预算与节流，输出上限 128），仍收到：

- DeepSeek：HTTP 400，`no_available_channel`；供应商表示当前无法服务该模型。请求 ID：`202609200909415469875908010521`。
- Qwen：HTTP 429，消息为供应商通用错误与支持入口，未给出 `Retry-After` 或具体额度原因。请求 ID：`2026092009094236772336216426669`。

因此两项失败均发生于 AIHubMix 服务端，不能归因于本项目模型白名单、工具 schema 或预算；也不能据此判定底层模型能力差。DeepSeek 需要供应商恢复通道或确认模型 ID；Qwen 需供应商确认账号/模型限额或网关错误，不能仅凭 429 断言日额度已耗尽。无需继续放宽本地执行校验。
