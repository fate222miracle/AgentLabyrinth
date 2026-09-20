# M1 切片 E：Replay 与演示完整度

SSOT：`docs/product/requirements.md` V0.5，重点落实 FR-04、FR-05 和 M1 课程演示任务卡第 5 项。ADR-007 Accepted。本切片由 Codex 临时接管 Antigravity 的执行职责。

## 范围

- 单 Episode 页面增加事件类型筛选、上一步、下一步、按 Step 跳转和当前事件定位。
- Replay 左侧展示截至当前游标最近的已保存 Environment Snapshot，右侧展示当前事件及过滤后的时间线。
- Episode 与 Experiment 增加客户端 JSON 导出；导出当前已加载产物，不发起模型请求。
- 补足手机宽度下的配置、持久化栏、Replay 控件、事件头和状态面板布局。
- Runtime 在现有 `ENVIRONMENT_UPDATED` payload 中保存经过 TraceRecorder 脱敏的环境快照，旧 JSON 继续可读。

## 非目标

不实现自动播放、速度控制、Checkpoint/Resume、重新执行 Replay、数据库、Experiment 并发、CSV、登录、第二个 Benchmark 或视觉重做。不修改 Domain 模型字段、EventType、API Schema 或评分口径。

## 验收

1. Fake Episode 的初始状态和每次成功工具调用后的状态都能从 Trace 按顺序查看；移动游标不调用 Provider、Executor 或 Environment。
2. 可按事件类型筛选，可前后移动并跳转 Step；空筛选有明确提示，旧产物没有中间状态时安全回退。
3. Episode 和 Experiment 均能下载格式化 JSON，文件名含对应 UUID，内容为当前已加载产物。
4. 390px 与桌面宽度均可操作，不出现关键控件不可达或固定宽度溢出。
5. Runtime 回归测试、API 读取隔离、Ruff、mypy、pytest、前端生产构建和浏览器 Fake 演示通过。
6. 更新 README、源码阅读指南与 current-state，记录调用链、状态变化、失败路径和实际验证结果。

## 2026-09-20 执行状态

- Runtime 快照、Replay 控件、事件筛选、Step 跳转、客户端 JSON 导出与移动端布局已实现。
- Edge DevTools 以真实 390px viewport 验证 `clientWidth=390`、`scrollWidth=390`；上一事件从 `17 / 17` 到 `16 / 17`，筛选 `ENVIRONMENT_UPDATED` 后显示 `1 / 2` 和 Step 1 快照；Episode JSON 下载成功。
- Fake Episode `9b81c7f9-4fce-48fb-8a52-80d730d39e12` 成功，17 个事件包含 2 个环境更新快照，状态从 `done=false` 变为 `done=true`。
- 当前环境未配置 AIHubMix Key，真实免费模型无法在本轮重测；这不由 Fake 结果替代。使用 README 中的验证命令在本机配置 Key 后补跑。
- 最终门禁：Ruff format 52 文件、Ruff lint、mypy 56 个源文件通过；pytest `91 passed, 2 warnings in 2.07s`；前端生产构建 27 modules、954ms。
