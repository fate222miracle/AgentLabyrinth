# 免费模型真实运行复核：2026-10-08

依据：需求 V0.6、ADR-010/017；负责人明确授权使用当前列表的免费模型运行并检查问题。本轮使用本机已配置 Key，无密钥输出、无自动换模型或 HTTP 自动重试。

## 范围与结果

复用 `scripts.verify_selected_models` → `EpisodeService.execute_episode` → Runtime / Validator / Environment / Evaluator → Checkpoint / Artifact。四个配置型号各跑 BFCL Python 0、ToolLab 订单 001，默认手写调度，Seed 1，Token 上限 20000；服务对请求使用 13 秒间隔。之后用默认 MiniMax 再跑一次 LangGraph 文档 007，Token 上限 8000，并启用正式服务的实时目录检查。

| 模型 | BFCL 0 | 订单 001 | 额外任务 | 本轮建议 |
| --- | --- | --- | --- | --- |
| coding-minimax-m2.7-free | 通过，1 模型/1 工具，392 Token | 通过，2/2，2414 Token | LangGraph 文档 007 通过，4/4，4655 Token | 默认课程候选 |
| coding-glm-5.3-free | 通过，1/1，354 Token | 通过，2/2，2205 Token | 未测 | 真实备用候选 |
| xiaomi-mimo-v2.6-pro-free | HTTP 429，0 工具 | HTTP 429，0 工具 | 未测 | 本轮不推荐现场使用 |
| xiaomi-mimo-v2.5-pro-free | HTTP 429，0 工具 | HTTP 429，0 工具 | 未测 | 本轮不推荐现场使用 |

总计 9 Episode，5 成功/4 失败，14 次模型尝试、10 次工具执行。成功响应累计报告 10020 Token（prompt + completion，simulated=false）；429 无 usage，产物记录的零不能解释为已确认上游消耗为零。网关实付费用仍未知，未因型号名称带 free 而补零或验证计价。

这些结果只证明当前账号、当前通道、这些小样本的执行情况；没有检验连续可用性、配额续期、真实并发、中断恢复或上下文窗口的真实消融效果。

## 遇到的问题与归因

1. **两种 MiMo 均上游 429。** 由 Provider 的 HTTPError 429 映射为 RATE_LIMIT_EXCEEDED，在工具校验/执行之前结束；不是本地白名单拦截、工具权限、步数或 Token 预算阻止调用。13 秒间隔下两题各自仍失败，本轮没有继续自动重试。429 可能涉及账号/每日额度/模型通道限额，仅凭状态码不能进一步确定，应查看供应商账号配额与请求记录。放宽 Validator 或工具权限不能修复此错误。
2. **目录可见不等于可调用。** 正式服务 get_meta 返回 live，四个型号均可见；两种 MiMo 仍 429。不能把列表可见性当作健康探测，或将 429 永久标为退役。
3. **旧模型说明已过期。** 旧说明称 MiniMax 当前 Key 不允许，本轮同一配置凭据实际通过。更新 `benchmarks/tool_lab_core/models.json` 的日期与证据：MiniMax 默认候选、GLM 备用、MiMo 当前 429；保留所有 ID 和 experimental 标志，不改历史产物或价格表。现有 API GET 已回读新说明。
4. **文档任务展示了可解释的搜索调整。** MiniMax 首先搜索 `return order policy status`，再搜索 `return policy`，读取 DOC-007，调用 submit_answer 提交 approved 与 document:DOC-007；四次工具全部成功，独立评分通过，耗时 44929ms。第一轮宽泛搜索后的再次搜索不等同于 INVALID_ARGUMENTS Recovery 重试，也不证明新增 Planning/Reflection。
5. **之前的本地预览服务已退出。** 初次 GET 8000 被拒绝，与供应商 429 分开归因；恢复原本仅 loopback 的 API/Web 后，meta、保存 Episode GET 与 Web HTTP200 通过。历史 GET 不重新调用模型。

BFCL 失败评分中的 no_tool_call 是调用未发生的评分结果；根因应读取 Episode.detail 的 provider_error: RATE_LIMIT_EXCEEDED。现有 Web 已优先用 detail 展示供应商限流说明，没有发现需要放宽执行契约的故障。

## 证据与复现

本机忽略目录：`artifacts/live-model-review-20261008/results.json`、`document.json`；完整 Artifact 仍在原 `artifacts/`，可直接使用正常历史读取。以下不是公开仓库自带的产物，新电脑没有同步本机 Artifact 时 ID 不能回读。

| 案例 | Episode ID |
| --- | --- |
| MiniMax BFCL | 180123d2-7543-4c95-bd5c-4b6526103ded |
| MiniMax 订单 | 0ec17f45-936a-4b66-9d26-7c9fa5c20b4e |
| MiMo V2.6 BFCL | 55beae74-7492-48e6-9a97-7c768bb2550d |
| MiMo V2.6 订单 | fd153f53-a409-43d8-af30-86db2732e056 |
| GLM BFCL | 80ac2822-f94c-463f-8b94-3cb5750f7530 |
| GLM 订单 | eff4f0a8-56d0-4c91-b397-d563fb4199e4 |
| MiMo V2.5 BFCL | 04b34787-75a5-43e0-97d6-c80ed3e400a8 |
| MiMo V2.5 订单 | 1a5a76ca-bc2c-4251-a814-426dfb220a97 |
| MiniMax LangGraph 文档 | ae543224-be7b-4326-aacd-360ea33f6955 |

仅在明确需要重新消耗模型配额时运行：

```powershell
uv --cache-dir .uv-cache run --locked python -m scripts.verify_selected_models --all-catalog --output artifacts/live-model-review-new/results.json
```

补测文档复用 CreateEpisodeRequest（provider=aihubmix，model=coding-minimax-m2.7-free，task_id=order-status-007，runtime_backend=langgraph，token_budget=8000）和 EpisodeService(live_model_catalog=True)，没有新增生产脚本或模块。

Provider 错误分类、目录响应与验证脚本边界 **16 passed，1.10s**，均为 Mock 自动测试，不消耗真实额度：

```powershell
uv --cache-dir .uv-cache run --locked python -m pytest tests/unit/test_aihubmix_provider.py tests/unit/test_verify_selected_models.py tests/unit/test_model_catalog_responsiveness.py -q
```

没有新业务逻辑，未重跑完整门禁或浏览器自动套件；API GET/HTTP200 不代表网页视觉验收。未提交推送、未自动签收版本、未新增价格或模型通道保证。下一次课堂前可只探测默认 MiniMax 一道题，不需要再反复跑全部限流型号。
