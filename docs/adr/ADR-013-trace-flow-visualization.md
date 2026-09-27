# ADR-013：使用 React Flow 展示已保存工具轨迹

## 状态

Accepted（2026-09-27；用户授权调研复用开源流程组件并制作视觉原型）。

## 决策

Web 引入 MIT 许可的 @xyflow/react 开源核心，用只读节点/连线展示已保存 Trace 的模型选择、MCP 工具执行、返回和本地提交。禁用编辑、连接和删除；保留原有过程详情与技术 Trace。仅动画表示回放顺序，不表示正在运行或真实阶段耗时。优先实际 TOOL_STARTED.transport；历史未记录传输时显示未记录，不由模型名字推断 MCP。

## 原因与代价

React Flow 提供节点、曲线路径、键盘焦点、缩放与画布，现有 React/CSS 无对应能力；自行维护画布会增加工作量。Rete 偏流程编辑，Motion 不提供图画布。本轮不引入其他动画/布局库，不使用 Pro 内容。增加浏览器依赖及包体，构建后记录体积与 npm audit 结果；不变更 Core、API、Trace Schema 或评测。

## 回滚

删除流程组件、入口和 @xyflow/react 依赖，原有 Replay 保持可用。

## 来源

[React Flow 核心与许可证](https://xyflow.com/open-source)、[官方连线动画](https://reactflow.dev/examples/edges/animating-edges)、[Rete 许可](https://retejs.org/docs/licensing/)、[Motion 文档](https://motion.dev/docs/react)。只复用开源依赖 API，组件视觉与 Trace 映射为项目实现。
