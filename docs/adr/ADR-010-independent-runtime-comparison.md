# ADR-010：独立 Runtime 调度与单变量对照

## 状态

Accepted（2026-09-22）。承接需求 V0.6 与 ADR-009，替代 Bootstrap 委托模式。

## 决策

- `AgentSpec` 增加 `runtime_backend: handwritten | langgraph`，缺省为 handwritten。保留 `runtime_strategy` 的两个历史值，它现在仅选择恢复策略：handwritten 表示不纠错，handwritten_recovery 表示 INVALID_ARGUMENTS 最多纠错一次。用只读 `recovery_policy` 属性提供清晰名称，不产生第三个可冲突的配置字段。
- 新 AgentSpec、RunConfig 写为 schema 1.1；允许读取 1.0。RunConfig 保存实际 Runtime 版本，旧数据缺失版本时保留 null；历史 config_hash 不重写。
- 从旧 Runtime 提取框架无关的 EpisodeSession，集中消息、预算、验证、工具执行和 Trace 规则。手写 while 循环与 LangGraph 条件边分别调度同一组原子操作；LangGraph 不调用 HandwrittenRuntime.run。
- LangGraph 图为 observe → model → validate → execute，并具有 model 重试/继续边与 END 终止边。每个 Episode 独立 Session/图；图中不配置自动重试，递归上限随步骤预算设置，不能覆盖业务停止原因。当前 Session 在内存中，不宣称 Checkpoint/Resume 已实现。
- 公共 Runtime Port 不变；工厂仅在组合边界选择实现，外部框架的 import 限制在 Adapter 目录。统一 Trace 与只读 Evaluator 保持原事件和评分语义。
- Experiment 增加 comparison_axis（recovery_policy / runtime_backend），默认原恢复策略对照。恢复对照固定 Runtime；框架对照固定恢复策略，左侧 Reference、右侧 LangGraph。调用前验证模型、Prompt、工具和预算相同，拒绝混合变量。
- Experiment schema 升至 1.2，仍读取 1.0/1.1。为兼容现有产物，保留 baseline_* / recovery_* 作为左/右列存储名，config 明确 comparison_axis 和两侧配置/版本。框架对照的 retry_eligible 与恢复率为 null，recovered 为 false，不把框架收益解释为参数恢复率。
- API 增加上述可选字段，缺省行为兼容；Web 与交接文档必须按产物 comparison_axis 展示列名和指标含义。

## 验证与限制

固定同一 Suite、Seed、Provider、Prompt 和预算，用两种调度执行正常与失败路径，比较成功、终止原因、Token、成本及脱去 ID/时间后的 Trace。Fake 套件证明契约一致性；一个免费真实模型只跑少量成对任务。共享原子规则使实验主要度量调度一致性与开销，不代表框架改变了模型能力。

新图沿用已锁定 LangGraph 1.2.12，无新增依赖；[官方 Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) 为节点、条件边和递归限制的依据。LangGraph 依赖包含 langchain-core/langsmith，但平台不启用外部追踪服务。

## 回滚

默认 backend 恢复 handwritten 即可继续原流程；保留新旧 schema 读取，不改写既有产物。
