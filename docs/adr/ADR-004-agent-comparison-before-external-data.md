# ADR-004：先完成 Agent 对照实验，再接外部数据

## 状态

Accepted（2026-09-19；项目负责人要求先建立与 Agent 开发的直接关系）

## 背景

M1 已能从网页调用真实模型、运行单个 ToolLab Episode 并查看 Trace，但当前主要变量是模型，且只有一条任务。继续直接接 BFCL 会加强函数调用模型评测，却仍不能证明平台能验证 Agent 架构改动。SSOT V0.5 的核心目标本来就是在相同条件下比较 Baseline 与 Recovery Agent。

## 决策

1. M1 切片 C 改为 Agent 对照实验闭环；BFCL 顺延至切片 D。切片 C 完成前不开始外部数据接入。
2. `AgentSpec.runtime_strategy` 保留现有 `handwritten` 作为 Baseline，并新增唯一值 `handwritten_recovery`。旧 JSON 无需迁移；新 Recovery 产物必须显式保存该值。
3. 两种策略复用同一个 `HandwrittenRuntime` 控制循环。Recovery 只在 `INVALID_ARGUMENTS` 后向同一模型提供一次安全、结构化的校验反馈并重试；Runtime 不猜测、不解析字符串化 JSON、不替模型修改参数。
4. 未知或禁止工具、重复 call ID、预算停止、Provider/Environment 错误及第二次参数失败不可恢复。无效调用不执行，重试的模型调用、步骤、Token 和费用正常计入预算。
5. 恢复过程复用现有 TraceEvent；不新增事件类型。`TOOL_CALL_VALIDATED` 记录失败，后续 `MODEL_REQUESTED` 表示重试。
6. 最小 Experiment 由 Application/API 串行编排现有 `run_episode`。汇总产物引用独立 Episode ID 和配置哈希；本切片不把 Experiment DTO 加入 Domain，不引入数据库、队列或并发框架。
7. 对照实验必须成对固定模型、任务、工具、Seed、预算、Prompt 主体和评分器。Agent ID、版本和 `runtime_strategy` 是允许变化的字段。Fake 提供可重复的因果验收；真实模型结果标为探索性观察。

## 原因

这一顺序让页面直接服务于 Agent 开发循环：修改策略、在固定任务上运行、比较指标、打开失败 Trace、判断收益与代价。一次受控参数重试是当前代码能够清楚解释和验证的最小架构差异。

## 代价与限制

- 4 条订单类原生任务只能验证最小实验闭环，不能代表完整 Agent 能力或 V0.1 的 12 条 ToolLab-Core。
- Fake 能证明实现因果关系，不能代替真实模型统计结论。
- `handwritten_recovery` 目前只有一次参数纠错；Planning、Memory、Reflection 和通用恢复策略需要各自的实验问题与后续 ADR。

## 验收依据

执行 `docs/tasks/M1-slice-C-antigravity.md`。切片 C 经 Codex 复核后，再执行 `docs/tasks/M1-slice-D-antigravity.md`。
