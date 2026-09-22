# ADR-009：LangGraph Runtime Adapter 启动边界

## 状态

Accepted（2026-09-22，V0.2 Milestone 1）

## 背景

V0.2 首先需要验证外部 Agent 框架能否通过既有 `AgentRuntime` Port 接入，同时保持 Environment、Tool Executor、Evaluator 和统一 Trace 不依赖框架。直接重写完整控制循环会同时改变执行器和恢复策略，无法先验证边界。

## 决策

- 增加 `langgraph>=1.2,<2`，只在 `packages/runtime/langgraph/` 使用；Domain 与其他核心层不得导入 LangGraph 类型。
- 第一阶段实现单节点 Bootstrap Graph：节点委托现有 `AgentRuntime` 完成 Episode，LangGraph 负责编译和调度，Runner 仍负责最终事件与评测。
- Bootstrap 只证明依赖、异步调用、结果和 Trace 契约可接入，不计为独立 Runtime，也不产生跨 Runtime 性能结论。
- 当前不扩展 `AgentSpec.runtime_strategy`。等独立 LangGraph 控制循环落地时，再用新 ADR 将 Runtime 实现与 Recovery Policy 拆成两个实验变量，并迁移旧字段。
- 不启用 LangSmith、远程遥测、Checkpoint 或持久化。

## 原因

这是最小可运行接入：先锁定框架边界和回归契约，再替换内部节点，避免一次修改 Runtime、Schema、Trace 和 Experiment 四个边界。

## 代价与风险

当前 LangGraph 节点仍调用 HandwrittenRuntime，因此不能与 HandwrittenRuntime 做有效能力或性能比较。每个 Episode 会编译一次小图；只有性能数据证明其成为瓶颈后才缓存图。

## 下一准入条件

独立控制循环必须复用相同 Provider、Registry、Validator、Executor、预算与任务；统一 Trace 仍是评分事实来源。通过 Fake Contract Test 后，才运行单模型小样本对照。

## 回滚方式

删除 `packages/runtime/langgraph/`、对应契约测试和依赖即可；公共 Domain 契约无需回滚。
