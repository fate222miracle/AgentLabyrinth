# ADR-014：单次 Episode 实时 Trace 传输

## 状态

Accepted（2026-09-28；项目负责人明确要求运行时节点实时出现）。

## 背景

`POST /api/v1/episodes` 等待运行与落盘完成才返回 Artifact。ADR-013 的流程图只能回放已保存结果，无法展示正在发生的模型请求和工具调用。

## 决策

- 保留现有同步结果接口，新增 `POST /api/v1/episodes/stream`，以 `text/event-stream` 顺序发送 `trace` 与最终 `complete`；失败发送不含内部堆栈的 `error`。每条 `trace` 携带现有版本化、脱敏的 `TraceEvent`，`complete` 携带原 `EpisodeResponse`，不新增领域事件或改变评分。
- `JsonTraceRecorder` 在成功追加事件后可调用一个可选观察回调。Web 使用与历史回放相同的 `flowFrames` 和 React Flow 组件，只随真实事件推进，不按定时器伪造执行进度。历史 GET 与 Replay 仍只读。
- 单次运行的服务端任务在浏览器断开后继续执行并保存最终 Artifact；断线的浏览器明确显示状态未知与 Episode ID，不能把断线当作 Agent 失败。仅当前 API 进程内的连接可实时观察；刷新后通过原 GET 读取已完成产物，不承诺跨进程补发实时事件。
- 第一阶段仅覆盖单次 Episode（ToolLab 本地/MCP 与固定 BFCL 子集）；对照实验、Resume 和多用户订阅另行设计。不传模型隐藏思维链，也不把 BFCL 调用提议显示为上游函数真正执行。

## 代价与风险

新增一条 HTTP 流和前端流解析。开发代理或浏览器可能缓冲/中断传输；最终结果以落盘 Artifact 为准。实时流在连接中只保留有限单次 Episode 事件，不作为第二套持久化存储。模型自身的一次响应仍可能耗时，期间只显示已到达的 `MODEL_REQUESTED`，不显示未保存的 token 流。

## 回滚

Web 改回原 `POST /api/v1/episodes`；删除 stream 路由和观察回调。Artifact 与既有 Replay 不受影响。
