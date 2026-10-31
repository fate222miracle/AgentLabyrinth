# ADR-044：无进展行动修正 Reflection Challenge

- **状态**：Accepted / Implemented（2026-10-31），负责人已确认原方案并完成产品闭环。
- **需求**：requirements V0.6 §6、§19；承接 ADR-037 的证据门槛。
- **不包含**：真实模型请求、跨任务长期记忆、Evaluator 私有答案注入、自动重试网络错误。

## 可测问题

现有 `empty_result` 故障样本会出现“工具成功返回空结果，Agent 在完整上下文中重复相同调用，直到 Max Steps”。这不是参数错误，现有 `invalid_arguments_once` Recovery 不适用；也不能由 Memory 或 Planning 自动解释。它提供了一个公开可见、非致命、可复现的“无进展”问题，但 Fake 只验证机制，不证明真实模型收益。

## 决策方案

新增可关闭的 `no-progress-revision-v1`：同一 Episode 内，连续两次规范化后的工具名+参数相同、工具均成功、环境未结束，且返回内容与已取得证据均无增长时，最多触发一次独立结构化自检。

自检复用同一 Provider，**不提供工具**，只看到任务公开描述和两次已发生的调用/返回；严格输出：

```json
{
  "diagnosis": "为什么当前动作没有产生新信息，最多200字",
  "revised_goal": "下一步应改变什么，最多200字"
}
```

校验通过后以 `_agentlabyrinth_reflection` 保留封装加入下一次普通模型请求。自检不能直接调用工具、提交答案、引用私有 `goal_conditions` 或撤销历史。额外请求、Token、费用和时延全部计入开启侧原预算；每 Episode 最多一次，无额外额度。

选择独立自检而不是简单重复拦截，是为了让被测变量确实是“模型基于反馈生成行动修正”；选择一次上限，是为了避免把更多采样次数包装成算法收益。Pi仅提供“显式事件、先持久化再展示、能力边界清楚”的设计启发，不引入其依赖或替换本项目Runtime。

## 失败和恢复

- 严格 JSON、字段长度或来源校验失败：记录 `REFLECTION_REJECTED` 并以 `FAILED / invalid_reflection` 结束，不自动剥离或重试。
- Provider、超时、预算或未知用量：沿现有失败语义结束；未知保持未知。
- `UNKNOWN_TOOL`、`FORBIDDEN_TOOL`、参数错误、工具异常、网络错误、已提交和终态不触发。
- 安全点保存反思是否已消费、来源事件与内容；恢复前核对 Trace，不重复消费第二次。

## 公平对照与任务

新增一题 `reflection-stale-alias-001`：公开说明先查询旧别名，空结果时改用同一说明中给出的规范订单 ID；两条信息对两侧完全相同。基线可以自行修正，Reflection 侧不获得答案或额外工具。原 Evaluator 评分保持，成功仍须真实查询并提交证据。

正式 Experiment 固定同模型、任务、Runtime、完整上下文、无 Planning/Memory/Recovery、同 Seed/Repeat、同总 Token/时间/步数；唯一变量为 Reflection 开关。报告成功率、重复无进展次数、模型/工具调用、Token、耗时和失败原因。Fake 验证协议，真实小样本另行逐次授权。

## 契约与验收

- `AgentSpec 1.5` + `ReflectionConfig 1.0`；`SessionState 1.3`。
- Episode 请求 `1.8`；Experiment 请求 `1.11`，新增 `reflection` 单变量轴。
- Experiment计划/结果/安全点使用各自下一可用子版本；旧请求和旧字节不升级。
- 新事件：`REFLECTION_PRODUCED`、`REFLECTION_REJECTED`；Replay/UI只显示实际到达事件。
- 单次、实时、历史、CSV、SQLite恢复、本地/MCP、Handwritten/LangGraph/PydanticAI均走同一Session边界。
- 最小失败测试覆盖：只触发一次、无进展前不触发、禁止答案泄漏、非法JSON、Provider失败、预算不足、恢复不重做、旧协议逐字兼容。

## 实施记录

三种 Runtime 共用 `EpisodeSession` 触发/预算/严格校验；正常 API、实时 Trace、SQLite 安全点/恢复、正式对照、Web 和 CSV 已接入。Fake 基线失败/开启侧通过只验证机制，不作真实模型收益结论。本轮未扩展为多轮 Reflection、跨任务经验库或自动评分反馈。源码阅读与实际验证见 `docs/learning/V0.3-reflection-challenge-20261031.md`。
