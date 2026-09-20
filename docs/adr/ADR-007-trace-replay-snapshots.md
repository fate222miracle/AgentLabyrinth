# ADR-007：Trace Replay 使用已保存环境快照

## 状态

Accepted（2026-09-20；M1 演示完整度切片，不改变公共模型字段）

## 问题

V0.5 FR-05 要求 Replay 不重新调用模型，并能逐步查看环境状态。现有 Trace 已在 `OBSERVATION_CREATED.payload.initial_state` 保存初始状态，但 `ENVIRONMENT_UPDATED` 只记录 `done`，历史中间状态无法由前端可靠重建。仅展示最终 `EpisodeResult.final_state` 会把最终状态错误地投射到更早步骤。

## 决策

- `HandwrittenRuntime` 在每次成功执行 Environment step 后调用既有 `Environment.snapshot()`，并把独立副本写入 `ENVIRONMENT_UPDATED.payload.state`。不新增 EventType，不修改 Pydantic Schema 或持久化 `schema_version`。
- 初始状态继续来自 `OBSERVATION_CREATED.payload.initial_state`；最终状态继续保留在 `EpisodeResult.final_state`。Replay 依事件顺序选择不晚于当前游标的最近快照，不调用 `Environment.restore()`，也不重新执行 Provider 或工具。
- TraceRecorder 继续负责深拷贝和敏感键脱敏。Environment 作者仍必须保证 `snapshot()` 只返回允许实验操作者查看的 JSON 状态；模型消息不会读取该字段。
- 历史产物保持可读。若旧 `ENVIRONMENT_UPDATED` 没有 `state`，前端使用最近的已知初始状态；到达最后事件时可显示 `final_state`，并明确标记快照来源。
- JSON 导出在浏览器端对已读取的 EpisodeArtifact 或 ExperimentArtifact 生成文件，不新增下载 API，不重新访问模型，不包含后端环境变量。

## 后果

新 Episode 的 JSON 会比旧产物更大，但当前 ToolLab 与固定 BFCL 子集的状态很小，且 M1 仅串行演示。将来若接入大状态环境，需要单独 ADR 决定增量快照、大小限制和私有字段策略；本切片不提前实现。

## 验证

- Runtime 测试断言初始快照、每次更新快照和最终状态的顺序与独立性。
- 旧 Trace 缺少中间 `state` 时仍可加载和浏览。
- 前端生产构建通过，并用 Fake Episode 验证筛选、上一步、下一步、步骤跳转、状态面板、JSON 导出和 URL 刷新回读。
