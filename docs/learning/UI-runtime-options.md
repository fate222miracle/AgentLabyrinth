# 单次运行选择与预算摘要

依据 requirements.md V0.6、UI 规范 1.1；仅前端呈现改动。

阅读顺序：App.tsx 的 execution-choice → advanced-settings → run-review → handleRunEpisode；index.css 的 execution-option 与 details-content。

调用链：原生 radio 的 onChange → singleRuntimeBackend → 选中卡片与运行前摘要 → 用户点击运行 → 原有 POST payload → 保存 Artifact → 结果与只读 Replay。选择卡片本身不发送请求。运行期间 fieldset disabled 防止误改执行方式；同一组 radio 可用方向键选择。

预算变化：steps-input 更新 maxSteps，折叠标题和摘要同步读取该状态；关闭 details 不重置值。真实模型使用显式 singleTokenBudget，留空与 Fake 使用任务元数据中的预算。结果只读展示保存配置，“下次运行配置”表示下一请求草稿，不冒充历史配置。

失败路径保持原有 API 错误提示；目录 unavailable 时 Fake 可运行。过渡不支持时原生 details 仍可操作，系统减少动效时全局 CSS 缩短过渡。Replay 参数拒绝、工具失败和旧快照路径继续由 traceSteps 检查覆盖。

实验：打开单次运行，选 Fake 与 LangGraph，展开高级设置改为 5 步，关闭后核对摘要，再运行 order-status-001；结果应按真实 Artifact 显示，刷新 Episode URL 只读回放。2026-09-27 本轮样本 f10abdbe-d599-416f-9740-a69a7b1ac890 成功，2 次模型/工具调用、17 个事件；这是模拟场景，不是模型能力成绩。

验证命令：npm.cmd --prefix apps/web run build；node apps/web/tests/traceSteps.test.mjs；git diff --check。减少动效、200% 缩放和真实模型复测仍待补。
