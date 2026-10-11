# ADR-026：上下文策略 API / Web 单变量对照

状态：Accepted，2026-10-09。负责人明确授权继续下一任务；依据需求 V0.6 §19、ADR-023/024/025 与上下文对照任务卡。

## 决策

- 复用 ContextPolicy 和完整历史安全点，仅增加 `context_policy` 对照轴。左侧显式 full，右侧显式 recent_tool_rounds（1–100）；模型、Prompt、工具、Runtime、恢复策略、任务、Seed、所有预算相同。两侧策略不同以外的变化拒绝。旧恢复/Runtime 对照仍要求上下文相同。
- 两个新建 API 增加可选 context_policy。单 Episode 请求 1.3；Experiment 请求 1.5。显式上下文必须使用新请求版本；上下文轴必须给出 recent_tool_rounds，其他轴的显式策略用于两侧。未配置时继续省略，不改旧 Agent 哈希或默认策略。
- 上下文轴冻结计划 1.2、完整结果 1.4；旧计划/结果保留版本和读取。新版本也容纳 ADR-025 全局预算。配置保存两侧 ContextPolicy，进入计划、结果与回归指纹；恢复和显式失败重跑复用原策略。
- 旧 baseline/recovery 字段仍代表左/右侧，标签分别为 Full Context / Recent Tool Rounds。上下文轴 retry_eligible 与全部挽救聚合指标为 null，recovered=false；CSV 同样为空，不将上下文差异称为参数纠错挽救。
- 网页在现有对照配置显示窗口，保存结果展示原窗口。刷新/导航只 GET，改草稿不改历史。当前模型请求帧展示保存的策略、历史/可见/剔除消息数与输入消息 UTF-8 字节；不推测缺失诊断，不把字节称为 Token 或 HTTP 大小。

## 验证与范围

Fake 001/007 验证两种 Runtime、窗口 1 遗忘失败和窗口 2 成功；完整 Trace 保留。补非法窗口/版本/混合变量、冻结计划恢复、全局预算停止、回归配置、API 和浏览器只读历史/CSV/诊断验证，运行完整门禁。

本任务不增加依赖或编排框架，不扩长链任务、Memory/Planning/Judge，不自动真实批量调用或发布。Fake 结论不是实际模型能力，自动门禁不替代 V0.2 现场签收。回滚可关闭新建入口，保留新版本读取，不改写产物。
