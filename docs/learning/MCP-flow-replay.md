# 工具调用动画源码阅读与实验

依据需求 V0.6、ADR-012/013；2026-09-27。此次只增加 Web 回放，不改变 Core、API、Schema、评测。

## 看效果

输入提示采用对话图标、标题“这次要做什么”，document_query/target_order_id 分别以“搜索关键词/目标订单”标签展示，保留原始值；CSS 入口为 .flow-bookend.input / .flow-input-context。视觉修改经过桌面浏览器截图和生产构建验证。

2026-09-27 追加首尾卡片：图上方“最初输入”读取首个 OBSERVATION_CREATED.observation.description，附实际 document_query/target_order_id；图下方“最终输出 · 已保存”读取 episode.final_state.submission.answer/evidence，开始/结束帧分别高亮。答案为空或旧产物未保存时明确提示，并显示实际 termination/detail；不读取 evaluator_config/goal_conditions 的标准答案。不重新生成自然语言结论，提交答案不代表评测通过。长答案限制卡片高度并允许滚动，保持画布为主。此为展示现有字段，未改变持久化契约。

追加验证：浏览器回读上述成功产物显示原始文档任务、return、approved、document:DOC-007；失败产物显示未保存已提交答案及 FAILED / TOOL_EXECUTION_ERROR。前端生产构建、Flow3/3与Replay4/4通过。本轮仅历史 Fake 产物回读，未再次调用模型或工具。

按 README 启动 API、Web；仅回读历史产物时不必启动 MCP。单次运行结果的 Trace Replay 默认进入“流程动画”，点“播放全过程”；可暂停、前后帧、拖动进度、变速及缩放。手机只显示当前工具，纵向排列。点击工具跳到该工具的首次提议。详细参数在“查看当前记录”，旧过程概览和技术 Trace 保留。

## 阅读顺序与调用链

1. `apps/web/src/flowFrames.ts`：纯函数按保存顺序映射阶段，以 call_id 关联工具结果；校验拒绝不会产生执行帧。明确 transport=mcp 才标 MCP；已知 ToolLab 本地环境及 MCP 的本地 submit_answer 标本地，其余不猜。
2. `apps/web/tests/flowFrames.test.mjs`：三个测试覆盖传输、拒绝、未知传输、多 call_id 与失败。
3. `apps/web/src/McpFlowReplay.tsx`：图标节点、曲线边、移动光点；播放器 index/playing/duration 状态；React Flow 禁止连接、拖动、删除。节点来自实际提议过的工具。
4. `apps/web/src/flowReplay.css`：暖色画布、活动/失败视觉、手机和减少动效样式。
5. `apps/web/src/App.tsx`：已加载 artifact → events/environment_version/model → 流程组件。原有两种回放保留。

保存 Artifact → flowFrames → 当前 index → 高亮节点/路径 → SVG 光点。观察与最终状态高亮模型；提议显示选择路径；执行显示调度到工具路径；返回显示工具到模型路径；校验拒绝高亮调度并标失败。播放每 1400ms 移动游标，速度只影响阅读节奏，**不是实际执行耗时**。切换 Episode 重建游标；切到其他视图卸载动画并清理 timer。播放控件不发请求，不改变环境。选择帧的模型/工具调用不会重新执行。

## 实际验证

- 浏览器亲自运行 Fake success / order-status-007 / Reference / MCP：Episode `0e14e216-ffbf-4165-a4e0-2af8cfdcf97b`，SUCCESS、Evaluator true、3 次模型/3 次工具、24 事件、11 动画帧。搜索/读取标 MCP；提交帧显示本地。播放到结束停止，前后帧、进度键盘操作可用。
- 停止本轮启动的 MCP 服务，再由浏览器运行相同配置：Episode `48a252cb-87f3-4a8c-9fb3-41fb89bdcf69`，FAILED、TOOL_EXECUTION_ERROR、1 次工具、9 事件、5 帧。第 4 帧显示“收到结果 · 搜索文档 / 失败”，工具和返回边为红色，无读取/提交节点。服务随后恢复。
- 390×844：三个纵向节点，document scrollWidth=375 < viewport390，没有整体横向溢出；恢复桌面视口。截图在忽略目录 `artifacts/ui-check/mcp-flow-desktop.png`、`mcp-flow-mobile.png`，手机截图仅截当前视口。
- Flow Node 测试 3/3、既有 Replay 4/4；tsc/Vite 生产构建通过（192 modules）；git diff --check 通过。官方 npm registry 的 production audit：0 vulnerabilities。
- 构建 gzip JS 127.15 KB（引入前63.92 KB），CSS8.53 KB。本轮 Python 核心未改，未重新跑 Python 全量门禁；未重新调用真实模型。

## 边界与接续

这是真实工具执行记录的动画，当前新实验模型为 Fake，不代表真实模型能力；不抓包、不展示未保存的 JSON-RPC 请求、不提供实时执行进度、不同播放帧不等于环境快照。localhost MCP 网络服务支持现有课程实验，不能据此声明公网性能。系统减少动效时隐藏移动光点，仍能逐帧查看，偏好设置尚未浏览器实测。手机布局只展示当前工具而非全部工具的缩略全图。下一步由负责人观看实际播放手感决定是否继续调整；V0.2 整版未验收。本轮未提交或推送。
