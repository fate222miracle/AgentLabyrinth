# M1 切片 C：Agent 对照实验闭环

SSOT：`docs/product/requirements.md` V0.5；ADR-004 Accepted。项目负责人于 2026-09-19 明确要求先证明平台与 Agent 开发的关系，再接外部数据集。本卡授权 Antigravity 实现 **Baseline 与 Recovery Agent 的最小成对实验**。BFCL 顺延至 `docs/tasks/M1-slice-D-antigravity.md`，本切片不得提前实现。

## 要回答的实验问题

> 在模型、工具、任务、Seed 和预算完全相同时，允许一次受控参数纠错重试，能否提高可恢复错误任务的成功率？代价是多少？

- 自变量：`handwritten` Baseline 与 `handwritten_recovery`。
- 固定变量：模型及配置、System Prompt 主体、工具 schema、TaskSpec 版本、Seed、预算和评分器。
- 指标：成功次数/总数、成对任务结果、Retry Recovery Rate、工具选择与参数合法率、步骤、模型/工具调用、Token、费用是否可知、时延。
- 停止条件：每个 Agent × Task × Seed 串行运行一次；Fake 作为确定性验收，真实 Gemini 只保留一次探索性结果，不用单次随机结果宣称普遍提升。

## 行为契约

1. Baseline 保持现状：参数校验失败后结束 Episode，非法工具不得执行。
2. Recovery 只对 `INVALID_ARGUMENTS` 提供**最多一次**受控重试。它把安全错误码、允许的工具名和对应参数 schema 作为公开反馈追加到消息，再请求同一模型重新生成；不得在 Runtime 内猜测或静默改写参数。
3. `UNKNOWN_TOOL`、`FORBIDDEN_TOOL`、重复 call ID、预算耗尽和第二次参数失败均立即结束，不重试。首次非法调用不计 Tool Call，但重试消耗 Step、Model Call、Token 和费用预算。
4. 继续使用现有 `TOOL_CALL_PROPOSED`、`TOOL_CALL_VALIDATED` 与下一次 `MODEL_REQUESTED` 表达恢复链路，不新增 TraceEvent 类型。任何核心 Schema 变化不得超出 ADR-004。
5. 每个产物必须明确保存 AgentSpec、`runtime_strategy`、配置哈希及全部 Trace，旧 `runtime_strategy="handwritten"` 产物继续可读。

## 最小实现

### 1. Agent 与 Runtime

- 保留现有 Baseline Agent；新增版本化 Recovery AgentSpec。两者除 ID、名称、版本、策略和恢复说明外，实验配置必须一致。
- 在现有 HandwrittenRuntime 中复用同一控制循环，只增加由 `runtime_strategy` 控制的一次恢复分支；不要复制整个 Runtime、创建通用策略框架或加入新依赖。
- FakeProvider 增加一个确定性 `invalid-then-success` 场景：第一次返回无效参数，收到校验反馈后生成正确调用并继续完成任务。相同 Fake 行为同时供两种 Agent 使用，不允许为 Recovery 写“必胜答案”。

### 2. 原生任务数据

- 把 ToolLab 原生任务从 1 条扩为 **4 条可解释的 JSON TaskSpec**，均使用现有订单工具与确定性本地状态，但目标订单、状态或约束不同。每条写清设计意图、预期工具轨迹、成功和失败条件；不得复制 BFCL 题目。
- 任务加载必须根据后端白名单中的 task ID 选择实际文件，删除 API 对 `order-status-001` 的硬编码。未知 ID 返回安全的 4xx。
- 这 4 条是 M1 的最小开发/演示集，不得声称已经完成 V0.1 的 12 条 ToolLab-Core。

### 3. Experiment 与 API

- 新增应用层串行编排：对选定 AgentSpec × TaskSpec × Seed 逐一调用现有 `run_episode`，每个 Episode 继续使用现有 JSON 写入和读取。
- 最小接口：`POST /api/v1/experiments` 创建并同步运行一次对照实验，`GET /api/v1/experiments/{id}` 只读已有汇总。保留现有 Episode API。
- Experiment JSON 使用 UUID、`schema_version`、完整输入配置、Episode ID 列表、配置哈希和聚合指标。比较逻辑放在 Application/API 层，不放 Domain、Environment、Provider 或 Evaluator；本切片不建数据库、队列和并发执行器。
- Fake 标准实验至少包含 clean control 与 `invalid-then-success` 两种固定条件，并在产物中记录场景；成对比较只能使用完全相同的条件。

### 4. Web

- 实验配置增加 Agent 选择（默认同时选择 Baseline、Recovery）、4 条原生任务和模型；主按钮启动对照实验。
- 结果首先显示两种 Agent 的成功次数/总数、Recovery 成功恢复数、Token、步骤和时延，然后显示逐任务成对表格；每个结果可打开已有 Episode Trace，刷新只读 JSON，不重调模型。
- 页面必须明确写出唯一变量是恢复策略，并区分真实模型和 Fake。保留单次 Episode 页面；本切片只修功能和信息层级，不做视觉重构。

## 验收

1. 确定性证据：在 `invalid-then-success` 下，Baseline 因首次参数错误失败；Recovery 不执行非法调用、恰好重试一次并成功。clean control 下两者均成功。
2. 公平性证据：每组成对 Episode 的模型、任务版本、Seed、工具、预算一致；只有 Agent ID/版本与 `runtime_strategy` 不同。汇总能回溯全部 Episode 和配置哈希。
3. 负例：第二次仍无效、未知/禁止工具、重复 call ID、预算不足均不被恢复；Experiment 未知 ID/非法任务 ID 被拒绝；GET 回读不调用模型。
4. 浏览器完成一次 Fake 对照实验，显示汇总、成对任务结果和 Trace；再用同一 Gemini 配置运行两种 Agent，忠实保存实际结果，不要求人为制造差异。
5. `pytest`、Ruff、mypy、前端构建和关键浏览器流程实际通过；旧 Episode JSON 和现有单次运行继续可用。
6. 更新 README、`docs/handoffs/current-state.md`，交付源码阅读顺序、调用链、状态变化、失败路径及实验结论。Codex 复核后才可宣称切片 C 完成。

## 当前禁止

BFCL、第二个外部数据集、12 条完整任务、自动参数改写、无限重试、Planning/Memory/Reflection、多 Agent、数据库、队列、并发实验和 UI 美化。
