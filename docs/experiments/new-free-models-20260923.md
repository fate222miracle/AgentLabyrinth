# 新增免费模型真实任务复测（2026-09-23）

用户在 AIHubMix Key 的模型范围新增 `xiaomi-mimo-v2.6-pro-free` 与 `coding-glm-5.3-free`。官方主域 `GET /v1/models` 对该 Key 返回这两款及现有 MiniMax M2.7、MiMo V2.5 Pro。官网模型页存在不等于当前 Key 可用；本次先核对 Key 级目录，再运行真实模型。

使用本机被 Git 忽略的 `.env` Key，官方 `https://aihubmix.com/v1`，执行：

```powershell
uv --cache-dir .uv-cache run --locked python -m scripts.verify_selected_models --model xiaomi-mimo-v2.6-pro-free --model coding-glm-5.3-free --output artifacts/selected-model-results-20260923-new.json
```

脚本通过 `EpisodeService → AIHubMixModelProvider → Runtime → Tool Registry/Executor → Evaluator` 串行运行；无自动重试、无模型替换。每题总 Token 上限 20000、单次输出上限 1024。原始产物在本机 `artifacts/{episode_id}.json`，结果汇总不入库且不含 Key。

| 模型 | 任务 | Episode ID | 结果 | 调用 | Tokens |
| --- | --- | --- | --- | --- | ---: |
| MiMo V2.6 Pro | BFCL `simple_python_0` | `a2ac6d51-272e-42d7-9294-26b229b3bf9c` | SUCCESS / `exact_call_match` | 模型 1、工具 1 | 275 |
| MiMo V2.6 Pro | ToolLab `order-status-001` | `0ec5bd09-fdde-400c-a4a7-3aa60a27840f` | SUCCESS / `submission_matched_target` | 模型 2、工具 2 | 2255 |
| GLM 5.3 | BFCL `simple_python_0` | `ff0c623d-e496-45b5-a7dd-520827a30149` | SUCCESS / `exact_call_match` | 模型 1、工具 1 | 356 |
| GLM 5.3 | ToolLab `order-status-001` | `f2487aa3-363a-4a91-bcb6-1987f2a33fc7` | SUCCESS / `submission_matched_target` | 模型 2、工具 2 | 2238 |

四条 Trace 分别有 10、17、10、17 个事件，最终状态和评测成功均已从本地产物复核。BFCL 是平台固定改编子集的本地精确匹配，不是 BFCL 官方排行榜成绩。以上只证明当时该 Key 对两个固定任务的真实工具调用闭环，不能保证持续可用或推断全量任务成功率。前端模型目录保留 MiniMax 默认，新增两款标为实验性；Key 级目录仍用于动态隐藏不可见模型。
