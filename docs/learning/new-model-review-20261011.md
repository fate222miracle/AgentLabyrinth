# 新免费模型真实可用性与能力检查：2026-10-11

依据：需求 V0.6、ADR-004/010/019；负责人明确授权测试截图新增型号，并确认已在原 Key 保存权限。密钥只从本机 `.env` 读取，未输出或复制。本轮没有修改生产 API、Provider、模型目录、工具权限、评分或历史产物，没有提交推送。

## 实际结果

北京时间 2026-10-11 下午，五个新模型各运行一道真实 BFCL Python 0。统一 LangGraph、关闭参数纠错、完整上下文、Seed 1、Token 预算 8000、总时限 180 秒、默认单响应上限 1024；正式 Provider 仍按 13 秒间隔执行。全部在模型请求处失败，未到参数校验/工具执行。

| 模型 | HTTP | 保存错误码 | 工具调用 | 能力结论 |
| --- | --- | --- | --- | --- |
| qwen3.8-27b-free | 400 | UPSTREAM_CHANNEL_UNAVAILABLE | 0 | 当前无法评测 |
| atlas-dots-3-note-preview-free | 400 | UPSTREAM_CHANNEL_UNAVAILABLE | 0 | 当前无法评测 |
| ling-3.0-flash-vl-free | 400 | UPSTREAM_CHANNEL_UNAVAILABLE | 0 | 当前无法评测 |
| nex-n2.5-pro-free | 400 | UPSTREAM_CHANNEL_UNAVAILABLE | 0 | 当前无法评测 |
| nex-n2.5-mini-free | 400 | UPSTREAM_CHANNEL_UNAVAILABLE | 0 | 当前无法评测 |

真实对照：已有 `coding-minimax-m2.7-free` 在同一 BFCL 0 / LangGraph / 预算下运行 SUCCESS，独立评分通过 `exact_call_match`，6980ms，报告输入 303、输出 86，共 389 Token。这只证明当前这一题可用，不等于多步任务或长期稳定性。

另对 Qwen 发一次无工具、最大输出 128 Token 的普通文本请求，也返回 UPSTREAM_CHANNEL_UNAVAILABLE。因此 Qwen 本轮失败不依赖工具 Schema；其余四个没有额外普通文本测试，不能扩大该项结论。

新进程三次成功读取官方 `/v1/models`：本机 Key 仅返回 `coding-minimax-m2.7-free`、`coding-glm-5.3-free`。本机环境没有覆盖 Key，`.env` 只有一处 AIHUBMIX_API_KEY 赋值，未发现重复配置。不能据此证明网页截图选中型号已保存至相同凭据或断言永久下架。

## 归因与边界

- Provider 把上游 JSON 的 `no_available_channel` 映射为 UPSTREAM_CHANNEL_UNAVAILABLE；本轮捕获的 HTTP 状态为 400，不是 429/每日额度证据，也不是网络未连接或本地工具校验失败。
- 本地生产目录尚未列出这些新候选。为避免把本地白名单拒绝误判为上游失败，诊断过程给 EpisodeService 传入只含五个授权 ID 的临时 models_path，并不启用目录 GET 的前置拒绝，直接用真实推理判断通道。所有 Runtime、预算、Registry/Validator/Executor/Evaluator 与持久化均走原路径。正式目录、运行中的服务和白名单未改。
- HTTP 状态观察只用于本次进程，不改变请求/响应或原错误处理；不读取/输出原错误消息或 Authorization。每个产物保存后重新读取并检查与内存一致、模型 ID 一致及唯一末尾 EPISODE_FINISHED。
- 六个 Episode：五失败、一成功；外加一次 Qwen 普通文本请求，总计七次真实推理尝试，没有自动重试。失败响应没有 usage，保存的零不是已确认消耗为零。五个失败都无法提供任务能力成绩，不报“模型能力 0 分”。
- 未继续订单/文档多轮任务，因为无可用候选进入下一层。不改参数权限、预算或失败评分来制造通过，也不声称其他四个没有工具调用能力。
- 首次沙箱目录访问 NETWORK_CONNECTION_FAILED；在允许的本机网络环境重查成功后才执行真实测试，不把沙箱阻断当模型失败。

## 证据与阅读入口

| 案例 | 本机 Episode ID |
| --- | --- |
| Qwen BFCL | 5ae92e32-4400-4d96-a689-4a2dcc9408b2 |
| Atlas BFCL | d253a17f-954a-493e-88a3-b8ba166805c6 |
| Ling BFCL | f016d544-c0c4-4869-b89b-ca7126333127 |
| Nex Pro BFCL | b0541aeb-5140-424e-96f1-d7b5f3b24c53 |
| Nex Mini BFCL | cec833c9-a8d9-4b88-a091-fb64daa7fb4c |
| MiniMax 对照 BFCL | 936b7960-b888-4741-9808-6d0ec6d267a7 |

本机忽略产物：`artifacts/new-model-review-20261011/results.json`、`control.json`、诊断脚本 `probe.py` / `control.py` 与临时候选配置。完整 Episode、安全点保存在原 `artifacts/`，正常 API 可只读回看；不随 Git 同步，新电脑没有这些 ID。再次执行诊断会消耗真实配额，原结果需保留。

阅读顺序：`apps/api/schemas.py` 请求 → `apps/api/service.py` 组合与候选检查 → `packages/providers/aihubmix.py` HTTP 与脱敏错误 → Runtime 的 MODEL_REQUESTED/失败终止 → `packages/evaluation/bfcl.py` no_tool_call → Checkpoint/Artifact 保存。对照调用沿同一链路产生真实工具提议及匹配评分。

## 下一步交接

1. 在供应商后台核对截图对应 Key 与本机 `.env` 的 Key 是否为同一把，确认保存后的权限持久化；不要把密钥传到聊天或文档。
2. 若确认同 Key，检查这七次请求的供应商记录和新型号通道状态。共同无通道、目录仅两个旧型号可由凭据范围、同步/路由或上游供给造成，当前证据不足以唯一归因；可将模型 ID、时间及 `no_available_channel` 提供给供应商支持。
3. 权限/通道恢复后，先重查目录并仅重测一个新型号一题；通过后再做订单、文档任务以及其余型号。测试成功才记录带日期可用说明并加入正式列表，保留旧历史原模型值。

本轮完成的是带证据的失败诊断，不是新模型准入、能力排名或版本签收。
