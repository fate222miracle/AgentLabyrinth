# MCP 计算机网络课设可视化建议

## 当前收口：工具行为动画

用户随后明确仅需展示模型经 MCP 做了什么、调用哪些工具，优先画面。已按 ADR-013 使用 React Flow 开源核心实现保存 Trace 的动画回放，详见 `docs/learning/MCP-flow-replay.md`。以下协议遥测仅是早期备选，**本轮不实施**；不绘制未记录的 tools/list、握手、报文或真实网络耗时。

| 候选 | 适配情况 | 决定 |
| --- | --- | --- |
| [React Flow](https://reactflow.dev/) / [xyflow 开源说明](https://xyflow.com/open-source) | MIT 开源核心；已有节点、曲线、缩放与 [连线动画示例](https://reactflow.dev/examples/edges/animating-edges) | 复用 @xyflow/react 12.12.0，只读画布；不使用 Pro |
| [Rete](https://retejs.org/docs/licensing/) | 多数包 MIT，部分高级功能采用 CC-BY-NC-SA；定位可编程节点编辑器 | 本次不需要编辑执行流程，未引入 |
| [Motion](https://motion.dev/docs/react) / [源码许可](https://github.com/motiondivision/motion) | MIT 动画库；没有工具流程画布 | 不引入，移动光点用 SVG 原生 animateMotion |

以上使用官方文档调研。复用的是库 API，暖色卡片、Trace 映射和播放器为项目自己的实现。默认只显示模型、调度、工具节点、阶段短标题和播放控制，参数与原始记录折叠。

## 早期备选：协议遥测（未实施）

2026-09-27；依据需求 V0.6 与 Accepted ADR-012。以下是下一切片建议，不是新增权威需求或已实现功能。

现有链路：Web → 平台 API/Runtime → MCP Client → localhost Streamable HTTP → 独立 MCP ToolLab Server。文档搜索和读取走远程协议，submit_answer 仍在本地。已有本地/远程成功及断线失败记录见 learning/V0.2-mcp-network-pilot.md；本轮未重复真实模型实验。

建议先增加只读“网络通信”视图：呈现平台 Client 与工具 Server 两个端点，按实际请求展示 tools/list、tools/call 的方法、请求 ID、工具名、脱敏参数、响应/错误和真实往返耗时。步骤动画只回放已保存通信，不暗示当前实时执行。现有 Trace 仅有工具层 transport 标记，不能当作完整协议抓包或精确网络耗时。

为避免虚构报文，先通过 ADR 明确协议观测数据的存储边界、Schema、脱敏和计时范围，再在 MCP Adapter 的真实收发边界采集。工具执行时间与端到端往返时间应区分；无法拆分的延迟标为端到端，不声称纯网络 RTT。协议版本应来自实际 SDK/协商结果，不能硬编码网页上的最新版。

演示三组固定文档任务：本地与 MCP 的相同配置对照；MCP 成功调用的请求/响应回放；停止独立服务后的错误传播。先使用 Fake 隔离模型网络波动；localhost 使用网络协议但不能代表跨机器链路性能。跨机器、TLS、鉴权和公网开放均需独立范围决定。

网络层次讲解：MCP 的工具方法与 JSON-RPC 消息属于应用层语义，Streamable HTTP 是此路径的传输承载，下面由实际 HTTP 连接使用的 TCP/IP 栈提供通信。不要将 MCP 说成取代 HTTP/TCP，或将本地 stdio 展示成网络通信。

官方资料：[2026-07-28 规范说明](https://blog.modelcontextprotocol.io/posts/2026-07-28/)指出新版协议去掉旧 initialize/initialized 握手与会话。因此后续图不能照旧教程固定画初始化流程；必须先核验本项目锁定 SDK 实际发出的协议版本和消息。本建议不升级依赖，不改变现有 MCP 运行路径。
