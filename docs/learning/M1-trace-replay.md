# M1 Trace Replay 阅读与实验指南

## 这部分解决什么

Replay 用已经保存的 TraceEvent 和 Environment Snapshot 复盘一次 Episode。移动游标、筛选事件、刷新 URL 或导出 JSON 都是只读操作，不重新请求模型、不重新执行工具，也不调用 `Environment.restore()`。

## 源码阅读顺序

1. `docs/adr/ADR-007-trace-replay-snapshots.md`：为什么中间环境状态必须随事件保存，以及旧产物的兼容规则。
2. `packages/runtime/handwritten/runtime.py`：初始状态写入 `OBSERVATION_CREATED.initial_state`，成功工具步骤后的状态写入 `ENVIRONMENT_UPDATED.state`。
3. `packages/application/trace.py`：事件深拷贝、敏感键脱敏、父事件链和 JSON 读写。
4. `packages/domain/models.py`：`TraceEvent`、`EpisodeResult.final_state` 和 `EpisodeArtifact` 契约。
5. `apps/web/src/App.tsx`：事件筛选、游标、Step 跳转、最近快照选择和客户端 JSON 下载。
6. `apps/web/src/index.css`：桌面双栏 Replay 与 390px 单栏布局。
7. `tests/unit/test_handwritten_runtime.py`、`tests/unit/test_api.py`：快照顺序、最终状态和 GET 读取隔离。

## 调用链

```text
Environment.reset
  -> snapshot
  -> OBSERVATION_CREATED.initial_state
  -> ModelProvider / ToolValidator / ToolExecutor
  -> Environment.step
  -> snapshot
  -> ENVIRONMENT_UPDATED.state
  -> EpisodeResult.final_state
  -> EpisodeArtifact JSON
  -> GET /api/v1/episodes/{id}
  -> Web Replay 游标与筛选（纯读取）
```

JSON 导出直接把页面已经持有的 `EpisodeArtifact` 或 `ExperimentArtifact` 格式化成 Blob。文件名包含对应 UUID，不发起新的 API 或模型请求。

## 状态变化

订单成功样本共 17 个事件。Step 0 保存初始订单库、空证据和空提交；Step 1 查询订单后，快照新增 `order:ORD-001` 证据但 `done=false`；Step 2 提交答案后，快照包含 submission 且 `done=true`；最终事件显示终止原因与评测结果。

页面定位某个事件时，从事件 0 开始扫描到当前事件，使用最近的 `initial_state` 或 `state`。到达最后事件时显示 `EpisodeResult.final_state`。因此页面不会把未来状态提前显示在过去事件上。

## 失败与兼容路径

- 旧 JSON 的 `ENVIRONMENT_UPDATED` 没有 `state`：继续显示最近的初始快照，最后事件使用 `final_state`。
- 当前事件之前没有任何快照：状态栏明确显示“尚无环境快照”，事件仍可查看。
- 筛选无匹配：显示空筛选提示，不改变原始 Trace。
- GET 未知 UUID：后端返回净化后的 404；不会调用模型。
- 下载失败：浏览器本地能力失败，不影响已持久化的服务端 JSON。
- Environment 快照含敏感键：仍由 TraceRecorder 统一脱敏；后续大状态或私有字段策略需另走 ADR。

## 实际验证

- Fake Episode：`9b81c7f9-4fce-48fb-8a52-80d730d39e12`，SUCCESS，17 个事件，2 个 `ENVIRONMENT_UPDATED.state`。
- 390px Edge DevTools：`innerWidth=clientWidth=scrollWidth=390`，Replay、导出按钮和 17 个事件均已渲染；前后控件矩形全部位于 viewport 内。
- 交互：从最后事件点击上一步得到 `16 / 17`、`ENVIRONMENT_UPDATED`、`Step 2 更新后`；筛选环境更新得到 `1 / 2`、`Step 1 更新后`。
- 导出：生成 `agentlabyrinth-episode-9b81c7f9-4fce-48fb-8a52-80d730d39e12.json`，20682 bytes。
- 真实模型不参与 Replay 自动化测试。当前环境没有 `AIHUBMIX_API_KEY`，免费模型复测必须在本机配置 Key 后单独执行并记录真实结果。
