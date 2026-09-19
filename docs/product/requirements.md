# AgentLabyrinth 产品需求与开发规范

**项目名称：** AgentLabyrinth  
**项目定位：** 面向 AI Agent 的可复现评测、实验、对比与多智能体竞技平台  
**文档性质：** 产品需求、架构契约与开发协作的单一事实来源（SSOT）  
**文档版本：** V0.5  
**当前产品阶段：** V0.1 MVP  
**项目形态：** 长期演进型个人开源项目  
**目标读者：** 项目成员、协作开发者、AI Coding Agent、项目评审者  

---

## 0. 文档治理

### 0.1 文档优先级

本文档是当前项目的唯一权威需求和开发约束来源。发生冲突时，优先级如下：

1. 本文档中的项目边界、接口契约和验收标准
2. 已批准的 ADR（Architecture Decision Record）
3. 已合并的接口定义与自动化测试
4. Issue、会议记录和聊天讨论
5. 个人理解或临时实现

聊天中出现的新想法，在写入本文档或 ADR 前不属于正式需求。

### 0.2 规范用语

- **必须（MUST）：** 不满足即不可合并或不可验收。
- **应该（SHOULD）：** 默认遵守；偏离时必须说明理由。
- **可以（MAY）：** 可选实现，不影响当前版本验收。
- **当前不做（OUT OF SCOPE）：** 不得以“顺便实现”为理由加入当前版本。

### 0.3 变更规则

以下变更必须先更新本文档或新增 ADR，再开始编码：

- 新增或删除核心模块
- 改变领域模型含义
- 修改 Environment、Runtime、Tool、Trace 或 Evaluator 核心接口
- 引入新的基础设施或重量级依赖
- 修改数据表、事件格式或评测口径
- 扩大当前版本范围

纯 Bug 修复、内部重构和不改变外部行为的小型优化，可以直接通过 Issue 与 Pull Request 管理。

### 0.4 版本边界

当前版本未通过验收前，不得实现后续版本功能。可以为下一版本预留最小且已被当前代码使用的接口，但不得提前建设未来模块。

课程演示 M1 经 ADR-003 单独授权：允许提前接入一个固定的 BFCL 非 Live 改编子集，用于课程网页演示。根据 ADR-004，必须先完成 Baseline 与 Recovery 的 Agent 对照实验，再开始 BFCL 接入。该例外不改变 V0.1 的 12 个原生 ToolLab 任务及其验收条件；BFCL 结果必须与原生任务分开展示和评分。

### 0.5 项目负责人真实意图与学习方式

本项目同时服务于作品交付与实践学习，二者优先级相同。所有协作开发者和 AI Coding Agent 必须理解以下事实：

- 项目负责人采用“先完成可运行实现，再阅读源码、运行实验并追问原理”的实践式学习方法，不以先看完整课程作为开发前置条件。
- 核心代码可以主要由 Codex 与 Google Antigravity 协助实现，但最终必须达到项目负责人能够沿调用链阅读、运行、修改和解释的程度。
- 代码不得为了追求短期生成速度而牺牲命名、边界、测试和可读性，也不得用大型框架隐藏本项目需要学习的 Runtime 核心机制。
- 每个核心功能交付时，必须同时提供源码阅读顺序、主调用链、关键状态变化、失败路径和可运行实验，不能只交付代码。
- 项目负责人可能在另一台电脑继续开发，因此任何关键需求、决策和上下文都必须写入仓库，不得依赖某一次聊天记录。
- 另一台电脑上的 Codex、Antigravity 或其他 AI Agent 必须以本文档、AGENTS.md、ADR、测试和当前代码为准，不得自行猜测项目负责人的偏好。

本项目的学习完成标准不是“所有代码均由项目负责人手写”，而是项目负责人能够回答：为什么这样设计、主流程如何运行、失败如何处理、如何验证改动是否有效。

---

## 1. 项目概述

AgentLabyrinth 是一个用于运行、观察、评测和比较 AI Agent 的实验平台。

平台不只评价 Agent 最终回答是否正确，还记录 Agent 在任务执行过程中的工具选择、参数生成、环境反馈、错误恢复、Token 消耗、执行时延和任务状态变化，从而回答以下问题：

- 同一模型采用不同 Agent 架构后，表现是否发生变化？
- Memory、Planning、Reflection 等机制是否真的有效？
- Agent 为什么成功或失败？
- 多 Agent 是否一定优于单 Agent？
- 能力提升是否值得额外的成本与延迟？
- 一个 Agent 在不同任务类型上的优势和短板是什么？

项目采用统一的 Agent、Environment、Task、Episode、Trace 和 Evaluation 抽象，使实验能够复现、回放和横向比较。

---

## 2. 项目背景

### 2.1 从“大模型回答问题”到“Agent 完成任务”

普通大模型应用通常接收一次输入并生成一次输出：

```text
用户输入
→ 模型生成
→ 最终回答
```

这类应用的核心评价对象是最终答案，例如答案是否正确、完整和符合格式。

Agent 的目标则不是只生成一段文本，而是在一个环境中持续采取行动并完成任务。例如，一个 Agent 可能需要先检索文档，再查询结构化数据，根据结果调用计算工具，遇到错误后调整参数，最后提交带有证据的答案。

```text
接收任务
→ 观察环境
→ 选择工具或行动
→ Runtime 校验并执行
→ 获取环境反馈
→ 更新状态与计划
→ 继续行动或结束任务
```

因此，Agent 的真正产物不仅是最终回答，还包括一条完整的执行轨迹。

### 2.2 Agent 的能力不等于底层模型能力

两个 Agent 即使使用相同模型，也可能因为工程设计不同而产生完全不同的表现。

影响 Agent 行为的因素包括：

- System Prompt
- Tool Schema 与工具集合
- Agent Runtime
- Planning 策略
- Memory 机制
- Reflection 与错误恢复
- Context Management
- 最大步数、Token 与费用预算
- Environment 的状态和反馈方式
- 多 Agent 通信与协作协议

例如，一个基础 ReAct Agent 可能在工具超时后直接失败；加入错误分类和重试策略后，它可能恢复任务；加入 Planning 后，它可能减少无效调用；加入 Memory 后，它可能完成需要跨步骤记忆的信息任务。这些差异无法通过模型本身的通用 Benchmark 直接说明。

### 2.3 当前 Agent 开发中的实际问题

Agent 项目在开发过程中通常通过少量 Demo 验证效果：

```text
修改 Prompt 或架构
→ 手动运行几个案例
→ 观察结果似乎变好
→ 继续开发
```

这种方式存在以下问题：

1. **实验条件不一致。** 不同 Agent 可能面对不同任务、数据、工具返回、随机状态和预算，结果无法公平比较。
2. **只看最终答案。** 即使任务失败，也不知道是工具选择、参数生成、环境反馈、预算耗尽还是错误恢复出了问题。
3. **无法稳定复现。** 外部 API、模型输出和环境状态随运行变化，很难重现某次成功或失败。
4. **缺少统一指标。** 成功率、步骤数、Token、费用、时延、非法行动和恢复能力往往分散记录。
5. **架构优化依赖主观感觉。** 加入 Memory、Planning 或 Reflection 后，缺少对照组和重复实验，无法证明提升来自该机制。
6. **多 Agent 容易变成概念堆叠。** Agent 数量增加了，但成功率、成本和通信损耗是否改善并不清楚。
7. **演示和研究相互割裂。** 日志可以排错，但不一定能形成可回放、可聚合和可比较的实验数据。

### 2.4 AgentLabyrinth 解决什么问题

AgentLabyrinth 不负责替用户解决某一个具体业务问题，也不试图在第一阶段成为通用评测基础设施。它首先是一个规模可控、结构透明的 Agent 实验工作台，用于学习和验证 Runtime、Tool Calling、Trace 与架构对照实验。

平台将一次 Agent 实验标准化为：

```text
AgentVersion
+ TaskVersion
+ EnvironmentVersion
+ ToolSetVersion
+ ModelConfig
+ Seed
+ Budget
= Episode
```

每个 Episode 由统一的 Runtime 执行，产生结构化 Trace，再由确定性规则、环境状态、工具轨迹和必要的 Judge 进行评价。

在此基础上，平台能够回答：

- Agent 是否完成了任务？
- 它调用了哪些工具，顺序和参数是否正确？
- 失败发生在哪一步？
- 它是否从可恢复错误中恢复？
- 完成任务消耗了多少步骤、Token、费用和时间？
- 两个 Agent 在相同条件下谁更稳定？
- 某项架构修改带来了多大收益，又增加了多少成本？

### 2.5 为什么当前先实现 ToolLab

真实浏览器、搜索引擎、数据库和第三方 API 会引入网络波动、数据变化、权限和费用问题，不利于第一阶段验证评测平台本身。

因此，V0.1 使用确定性的 ToolLab Environment：

- 工具和数据由本地环境提供
- 初始状态由 TaskVersion 与 Seed 控制
- 可以稳定注入超时、空结果和参数错误
- 能精确判断期望工具、禁止工具和正确证据
- 普通用户只需选择配置并启动实验，不需要手工控制 Agent

ToolLab 首先验证 AgentLabyrinth 的 Runtime、Trace、Evaluation、Replay 和 Experiment 是否成立，而不是模拟所有真实业务场景。

### 2.6 为什么后续加入 GridWorld

ToolLab 主要研究抽象工具调用和信息处理，但空间探索、部分可观测、资源管理与长期目标更适合在具有状态变化的模拟世界中研究。

GridWorld 将作为后续独立 Environment 接入同一个 Episode Runner，用于测试：

- 环境感知
- Long-horizon Planning
- 空间与历史记忆
- 子目标分解
- 失败后的重新规划
- 多 Agent 协作与竞争

因此，GridWorld 不是脱离主项目的小游戏，而是 AgentLabyrinth 从工具任务扩展到连续决策任务的第二类 Benchmark Environment。

### 2.7 项目定位边界

AgentLabyrinth 不是：

- 用于解决单一业务需求的 Agent 应用
- 只比较基础模型知识能力的 LLM Benchmark
- 只展示日志和调用链的可观测平台
- 替开发者编写 Agent 的通用 Agent 框架
- 单纯展示多 Agent 对话的 Demo

它将 Runtime、Environment、Task、Trace、Evaluation、Replay 和 Experiment 连接起来，定位为：

> **一个用于构建可控任务、运行 Agent、复盘行为并进行架构对照实验的 Agent 实验平台。**

### 2.8 与现有项目的关系

Agent 评测并不是无人探索的方向。Inspect AI 已提供 Task、Agent、Tool、Scorer、日志查看和沙箱等通用评测能力；Harbor 支持在隔离环境中运行不同 Agent 和 Benchmark；AgentGym 研究统一 Environment 接口；AgentBoard 强调细粒度进度和轨迹分析；BFCL 与 τ-bench 分别覆盖函数调用和真实领域工具交互。

因此，本项目不声称“行业缺少 Agent 评测平台”，也不以替代这些成熟项目为目标。

本项目选择自行实现最小核心，是因为项目的首要目标包括：

- 在开发过程中理解 Agent Runtime 的真实控制循环
- 亲自实现 Tool Schema、Function Calling 和 Tool Executor
- 将一次 Agent 行为转化为可查询的 TraceEvent
- 用最小任务集完成一次可复现的架构对照实验
- 为后续 GridWorld 提供一个自己能够完全理解和修改的 Environment 接口

后续可以为 Inspect AI、Harbor 或其他生态增加 Adapter，但 V0.1 不以兼容外部框架为验收要求。

---

## 3. 项目目标

### 3.1 当前目标

V0.1 只验证一个具体的最小闭环：

> 两个使用相同模型和工具、但 Runtime 策略不同的 Agent，在同一组 ToolLab 任务和预算下自动运行；用户能够查看每次执行轨迹，并通过成功率、工具准确率、Token、费用和时延判断策略变化是否有效。

### 3.1.1 V0.1 标准演示场景

V0.1 默认提供：

- Baseline Agent：基础 Tool Calling 循环
- Recovery Agent：增加参数修复和一次受控重试
- ToolLab-Core：12 个确定性任务
- 一次相同模型、相同任务、相同预算的对照实验

演示必须能够回答：

- Recovery Agent 是否提高了受控错误任务的成功率？
- 它是否增加了 Tool Call、Token、费用和时延？
- 提升发生在哪些任务，失败又发生在哪一步？

### 3.2 长期目标

项目长期演进为支持以下能力的统一实验平台：

- 单 Agent 能力评测
- Agent 架构消融实验
- 工具调用与错误恢复评测
- Memory、Planning、Reflection 专项评测
- 多 Agent 协作与竞争
- 可插拔 Environment
- MCP 工具接入
- 人工审批与高风险工具控制
- Agent 长期行为研究

### 3.3 非目标

本项目不以训练新的基础模型为目标，也不把“接入尽可能多的模型”作为核心价值。

当前阶段不追求：

- 大规模 Agent Society
- 数十到数百个 Agent 的长期模拟
- Agent 自动修改自身代码
- 无边界的真实浏览器或系统操作
- 大规模分布式调度
- 用单一综合分数宣称某个 Agent 绝对更强

---

## 4. 核心价值

### 4.1 可复现

同一实验应固定：

- Task 版本
- Environment 版本
- Random Seed
- Model 与模型版本
- Temperature 等生成参数
- Prompt 版本
- Tool Schema 版本
- 最大步骤、Token 与费用预算

### 4.2 可观测

平台记录 Agent 的完整可观测执行事件，包括：

- 输入 Observation
- 模型请求与响应元数据
- Tool Call 名称与参数
- 参数校验结果
- 工具执行结果与错误
- Environment 状态变化
- Token、费用和时延
- Episode 终止原因

平台不要求、也不依赖存储模型隐藏的 Chain-of-Thought。Trace 只保存可公开的消息、结构化行动、工具结果、状态变化和可选的简短决策摘要。

### 4.3 可比较

平台支持控制变量实验，例如：

```text
相同模型 + 相同任务 + 相同工具
仅改变 Memory 是否启用
```

从而观察成功率、成本、步骤数和错误率的变化。

### 4.4 可扩展

Agent、Environment、Task、Evaluator、Tool 和 Model Provider 均采用可插拔接口，后续加入 GridWorld、OpsWorld 或 Multi-Agent Arena 时不需要重写核心 Runner。

---

## 5. 核心用户

### 5.1 Agent 学习者

通过执行轨迹理解：

- Agent Runtime 如何运行
- 模型如何选择工具
- 工具调用为什么失败
- Memory 如何影响决策
- Reflection 是否改善结果

### 5.2 Agent 开发者

用于验证：

- Agent 是否能够稳定完成任务
- 架构修改是否带来真实收益
- Prompt 或工具描述修改是否造成回归
- 成本、延迟和成功率之间如何权衡

### 5.3 Agent 研究者

用于开展可控的小规模实验：

- Planning Strategy
- Memory Architecture
- Tool-use Behavior
- Error Recovery
- Single-Agent 与 Multi-Agent 对比

### 5.4 Experiment Operator（实验操作者）

平台的主要使用者，负责运行和查看实验。其日常操作只有：

1. 选择一个或多个 AgentVersion
2. 选择 Benchmark Suite
3. 设置 Seeds、重复次数和预算
4. 启动 Experiment
5. 查看结果、对比和 Replay

实验操作者不需要手动选择每一步工具、填写 Tool Call 参数、逐步控制 Agent，也不需要为每次实验重新创建任务。

### 5.5 Benchmark Author（任务作者）

负责创建和维护 TaskSpec、测试数据与 Evaluator。V0.1 不开发复杂的任务编辑后台，任务作者通过版本控制中的 YAML/JSON 和测试代码定义任务。

### 5.6 Maintainer（平台维护者）

负责 Runtime、Environment、Provider Adapter、存储、前端、测试和发布流程。

### 5.7 Human-in-the-loop 边界

ToolLab V0.1 全部是受控模拟工具，不包含高风险真实写操作，因此默认没有人工审批步骤。Human-in-the-loop 在 MCP 和真实工具接入阶段再引入，不得为了展示技术而添加无意义确认弹窗。

---

## 6. 产品设计原则

1. **先评测，后优化。** 每个 Agent 技术都需要对应可测量的问题。
2. **先单 Agent，后多 Agent。** 多 Agent 不是 MVP 前置条件。
3. **先确定性环境，后开放环境。** 第一阶段避免网络波动影响评测。
4. **不存储隐藏思维链。** 使用事件、行动和结果解释 Agent 行为。
5. **不以技术堆叠代替产品价值。** 每项技术必须解决明确问题。
6. **默认安全。** Agent 只能通过注册工具和 Environment Action 影响外部状态。
7. **版本化一切影响实验结果的配置。** 包括任务、提示词、工具和评测器。
8. **新技术必须通过实验准入。** 引入 Planning、Memory、Reflection、RAG、Multi-Agent 等能力前，必须先写清待解决的失败现象、基线方案、实验假设、测试任务、评价指标和成本代价；无法形成对照实验的功能不得进入当前版本。

---

## 7. 核心领域模型

### 7.1 AgentSpec

AgentSpec 描述一个可运行的 Agent 配置。

```text
AgentSpec
├── id
├── name
├── description
├── model_config
├── prompt_version
├── tool_set_version
├── runtime_strategy
├── memory_config
├── reflection_config
└── budget_config
```

AgentSpec 必须不可变并支持版本化。修改 Prompt、工具或 Runtime 策略后，应生成新版本，而不是覆盖历史实验配置。

### 7.2 Environment

Environment 是 Agent 执行任务的受控世界，负责：

- 初始化环境状态
- 根据当前状态生成 Observation
- 接收并校验 Action
- 执行状态变更
- 返回 Feedback
- 判断任务是否结束
- 根据 Seed 保证初始条件可复现

统一接口建议：

```python
class Environment:
    def reset(self, task, seed) -> Observation: ...
    def available_tools(self) -> list[ToolSchema]: ...
    def step(self, action: Action) -> StepResult: ...
    def snapshot(self) -> dict: ...
    def restore(self, snapshot: dict) -> None: ...
```

### 7.3 TaskSpec

TaskSpec 描述 Agent 的目标和评价标准。

```text
TaskSpec
├── id
├── version
├── category
├── description
├── initial_state
├── goal_conditions
├── constraints
├── expected_tools
├── forbidden_tools
├── max_steps
├── token_budget
└── evaluator_config
```

### 7.4 Episode

Agent 执行一次 Task 称为一个 Episode。

```text
AgentSpec Version
+ TaskSpec Version
+ Environment Version
+ Seed
+ Runtime Configuration
= Episode
```

Episode 终止状态：

- `SUCCESS`
- `FAILED`
- `MAX_STEPS`
- `TOKEN_BUDGET_EXCEEDED`
- `COST_BUDGET_EXCEEDED`
- `TIMEOUT`
- `RUNTIME_ERROR`

### 7.5 TraceEvent

Episode 由有序 TraceEvent 组成。

事件类型至少包括：

- `EPISODE_STARTED`
- `OBSERVATION_CREATED`
- `MODEL_REQUESTED`
- `MODEL_RESPONDED`
- `TOOL_CALL_PROPOSED`
- `TOOL_CALL_VALIDATED`
- `TOOL_STARTED`
- `TOOL_SUCCEEDED`
- `TOOL_FAILED`
- `ENVIRONMENT_UPDATED`
- `EPISODE_FINISHED`

每个事件包含：

```text
event_id
episode_id
step_index
event_type
timestamp
duration_ms
payload
token_usage
cost
parent_event_id
```

### 7.6 Experiment

Experiment 是一组批量、可比较的 Episode。

```text
N 个 AgentSpec
× M 个 TaskSpec
× K 个 Seeds
= N × M × K Episodes
```

Experiment 保存完整实验配置，并输出聚合指标与成对比较结果。

---

## 8. 系统架构

```text
Web UI
  │
  ▼
API Service
  │
  ├── Agent Registry
  ├── Task Registry
  ├── Environment Registry
  ├── Experiment Service
  └── Evaluation Service
          │
          ▼
      Episode Runner
          │
          ├── Agent Runtime
          ├── Model Provider Adapter
          ├── Tool Registry / Executor
          ├── Budget Controller
          └── Trace Recorder
                  │
                  ▼
                Database
```

### 8.1 Agent Runtime

Runtime 是 Episode 的主控制循环：

```text
读取当前状态
    ↓
构造模型上下文
    ↓
调用模型
    ↓
解析 Tool Call 或 Final Answer
    ↓
校验权限、参数和预算
    ↓
执行工具 / Environment Action
    ↓
记录 Trace
    ↓
判断继续或结束
```

V0.1 必须自行实现最小 Runtime，以掌握 Tool Schema、Function Calling、消息循环、错误处理和状态管理。后续再增加 LangGraph Adapter，对比手写 Runtime 与框架 Runtime。

AgentLabyrinth Core 必须保持框架无关。Domain、Episode Runner、Environment、Trace、Evaluator 和 Tool Executor 不得直接依赖 LangGraph、PydanticAI、OpenAI Agents SDK、Google ADK、CrewAI 或其他 Agent 框架。

统一 Runtime Port：

~~~python
class AgentRuntime(Protocol):
    async def run(
        self,
        agent: AgentSpec,
        task: TaskSpec,
        environment: Environment,
        recorder: TraceRecorder,
    ) -> EpisodeResult: ...
~~~

V0.1 的 `HandwrittenRuntime` 实现该 Port；后续所有外部框架必须通过 Adapter 实现同一 Port，并映射为统一的 `TraceEvent`、`TerminationReason`、Token、费用和评价结果。

### 8.2 Tool Registry 与 Tool Executor

每个 Tool 包含：

- Tool Name
- Description
- JSON Schema
- Risk Level
- Timeout
- Retry Policy
- Implementation
- Version

Tool Executor 负责：

- 工具查找
- Schema 参数校验
- 权限校验
- 超时和重试
- 错误标准化
- 结果截断与脱敏
- Trace 记录

### 8.3 Model Provider Adapter

不同模型通过统一接口接入：

```python
class ModelProvider(Protocol):
    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
        config: ModelConfig,
    ) -> ModelResponse: ...
```

V0.1 只要求稳定支持一个真实模型提供方和 `FakeModelProvider`；不以接入模型数量作为完成标准。任何 Provider SDK 类型都不得出现在 Domain、Runtime Port 或统一 Trace Schema 中。

### 8.4 分层与依赖规则

项目采用 Ports and Adapters 思路，依赖方向必须为：

~~~text
Interface / API
    ↓
Application
    ↓
Domain
    ↑
Infrastructure Adapters
~~~

必须遵守：

- Domain 不依赖 FastAPI、数据库 SDK、模型 SDK 或前端类型。
- Application 通过 Port 接口访问模型、数据库和工具。
- Infrastructure 实现 Port，不向 Domain 泄露供应商类型。
- API 层只做协议转换、鉴权和输入校验，不放置核心业务规则。
- Environment 不直接调用前端或数据库。
- Agent Runtime 不包含 ToolLab 或 GridWorld 专用业务逻辑。
- Evaluator 不得修改 Episode 或 Environment 状态。
- 禁止循环依赖。

### 8.5 Agent 框架接入规则

外部 Agent 框架属于可替换的 Infrastructure Adapter，不属于 Domain 或 Application Core。

接入顺序：

1. V0.1：`HandwrittenRuntime`
2. V0.2：`LangGraphRuntimeAdapter`
3. V0.3 之后：根据实验问题选择 `PydanticAIRuntimeAdapter`、`OpenAIAgentsRuntimeAdapter` 或 `GoogleADKRuntimeAdapter`
4. Multi-Agent 阶段再评估 CrewAI 与 Microsoft Agent Framework

每个新 Runtime Adapter 必须：

- 运行同一组 TaskSpec、Environment、Seed 和预算。
- 不绕过统一 Tool Executor、Trace Recorder 与 Evaluator，除非 ADR 明确说明并提供等价事件映射。
- 记录框架名称、精确版本、模型配置和不可比差异。
- 提供至少一个 Contract Test 和一组与 HandwrittenRuntime 的对照实验。
- 不得把框架专用状态对象泄露到 Domain。

使用 Google Antigravity IDE 不构成选用 Google ADK 的理由。IDE 是开发工具，Agent Runtime 是产品技术决策，两者必须独立评估。

---

## 9. 当前内置实验环境：ToolLab

### 9.1 定位

ToolLab 是 V0.1 的确定性工具调用实验环境，用于测试 Agent 的工具选择、多步规划、参数生成和错误恢复能力。

ToolLab 不访问真实外部网络。所有数据、工具返回和故障注入均由 Seed 控制，避免外部 API 波动破坏实验公平性。

### 9.2 用户操作原则

ToolLab 不要求普通用户手动参与任务执行。

- 用户只配置 Experiment，不遥控 Agent。
- Tool Call 选择、参数生成与重试由 Agent 和 Runtime 自动完成。
- 任务和工具由 Benchmark Suite 预先定义。
- ToolLab V0.1 不要求每次 Tool Call 人工确认。
- 失败 Episode 可以手动重跑，但重跑不是正常流程的必需操作。

典型操作表单：

~~~text
Agents: Baseline-ReAct, Planning-Agent
Suite: ToolLab-Core-v1
Seeds: 1, 2, 3
Repeat: 3
Max Cost: 20 CNY

[Run Experiment]
~~~

### 9.3 内置工具

V0.1 只实现四个最小工具：

```text
search_documents(query, top_k)
read_document(document_id)
query_records(table, filters)
submit_answer(answer, evidence)
```

工具结果采用结构化格式。V0.1 必须支持两类受控故障：

- 参数不合法
- 暂时性超时

空结果、不可重试错误、结果过长和冲突信息在 V0.2 按实验需要增加，不得为了凑故障类型提前实现。

### 9.4 任务类型

#### A. Tool Selection

要求 Agent 从相似工具中选择正确工具。

#### B. Parameter Generation

要求 Agent 正确生成必填参数、枚举值和过滤条件。

#### C. Multi-step Planning

任务必须按照依赖关系调用多个工具才能完成。

#### D. Error Recovery

工具首次调用会受控失败，测试 Agent 是否能识别错误并调整策略。

Evidence Grounding 作为所有任务均可启用的评价维度；Budget Awareness 作为 Runtime 的统一约束。二者不在 V0.1 单独扩展为任务类别。

### 9.5 任务定义方式

V0.1 TaskSpec 使用版本控制中的 YAML 或 JSON 定义，不开发任务编辑器 UI。

~~~yaml
id: tool-selection-001
version: 1.0.0
category: tool_selection
description: 查询订单状态并提交证据
expected_tools:
  - query_records
  - submit_answer
forbidden_tools:
  - calculate
max_steps: 6
max_tool_calls: 5
evaluator: order_status_v1
~~~

TaskSpec 必须通过 Schema 校验和至少一个任务级测试后才能加入 Benchmark Suite。

### 9.6 V0.1 任务集规模

- 共 12 个原生 TaskSpec
- 覆盖 Tool Selection、Parameter Generation、Multi-step Planning、Error Recovery 四类任务
- 每类 3 个案例
- 同一 Agent 配置默认重复运行 3 次；Environment Seed 和重复次数分别记录
- 必须包含正常案例和受控失败案例

12 个任务的目标不是形成权威排行榜，而是验证平台闭环、暴露 Runtime 差异并支撑第一组对照实验。扩大任务规模必须以发现覆盖缺口为依据。

### 9.7 Benchmark 数据来源与复用规范

项目采用“原生最小任务集 + 外部 Benchmark Adapter”的双层结构。

#### A. 原生任务集

- V0.1 使用 12 个团队自建的小型确定性任务。
- 原生任务用于验证 AgentLabyrinth 自身的 Tool Schema、Runtime、故障注入、Trace 和 Evaluator 契约。
- 每个任务必须说明设计意图、预期工具轨迹、成功条件和失败条件。
- 原生任务不追求数量，优先保证可理解、可测试和可复现。

#### B. 外部成熟数据集

V0.2 起允许通过 Adapter 接入成熟项目的数据集或环境；课程演示 M1 的一个固定 BFCL 非 Live 改编子集按 ADR-003 作为唯一提前接入例外。接入优先级如下：

1. 与 Tool Calling 和错误恢复直接相关、运行成本低的基准。
2. 具有明确任务定义、可自动评测和稳定版本的数据集。
3. 许可清晰且允许本项目预期使用、转换或再分发的数据集。
4. 复杂 Web、操作系统和多智能体环境在核心闭环稳定后再接入。

外部数据接入默认采用“按需下载 + 本地转换 + Adapter 映射”，不直接把第三方完整数据复制进本仓库。只有许可证明确允许再分发时，才可以提交转换后的数据快照。

#### C. 三种允许的接入方式

1. **Reference Adapter（首选）：** 保存下载说明、版本和校验值，运行时由使用者获取原始数据。
2. **Converted Snapshot：** 在许可允许时保存转换后的固定快照，同时保留原始许可、版权声明、来源版本和转换脚本。
3. **Inspired Native Tasks：** 只借鉴能力分类和任务设计思想，重新编写独立任务；不得复制受限制的题目、答案、数据或专有环境资源。

#### D. 数据清单

每个外部 Suite 必须提供机器可读的 `dataset_manifest`，至少包含：

```text
source_name
source_url
source_version_or_commit
code_license
data_license
upstream_dependencies
import_mode
transformation_script
checksum
attribution
redistribution_allowed
official_protocol_compatible
```

代码仓库的开源许可证不自动覆盖其中的数据、模型、网页内容和上游环境。接入负责人必须逐项核对精确版本；许可不明确时只提供 Adapter 和获取说明，不分发原始数据。

#### E. 结果命名与可比性

- 只有完整复现官方任务、工具、提示、环境、评测器和版本时，结果才可以标注为对应 Benchmark 的官方协议结果。
- 任务经过抽样、改写、格式转换或运行在 AgentLabyrinth 自有环境时，必须命名为“AgentLabyrinth-adapted subset”，不得宣称为官方分数。
- 报告必须公开 Suite 版本、数据来源、转换方式、模型配置、运行次数和已知偏差。
- Development Set 与 Evaluation Set 必须隔离；已发布 Evaluation 快照不可静默修改。

#### F. Adapter 边界

Benchmark Adapter 只负责把外部任务、环境反馈和评价结果映射到 `TaskSpec`、`Environment` 与 `EvaluationResult`，不得把特定 Benchmark 逻辑写进通用 Agent Runtime。一个外部数据集是否值得接入，应由它能否回答新的实验问题决定，而不是由其知名度决定。

### 9.8 外部 Benchmark 候选清单

以下仅作为当前技术选型参考。许可证结论以实际接入时锁定版本中的文件为准，不构成法律意见。

| 候选项目 | 适合验证的能力 | 当前许可线索 | 接入建议 |
|---|---|---|---|
| [BFCL / Gorilla](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard) | Function Calling、参数生成、多轮工具调用 | Gorilla 仓库声明 Apache-2.0 | 最适合作为第一个外部 Adapter；先接入低成本、非 Live 的小子集 |
| [τ-bench](https://github.com/sierra-research/tau-bench) | 工具、用户模拟、业务规则和状态一致性 | 仓库 LICENSE 为 MIT | 价值高但环境更复杂，建议 V0.3 之后接入 |
| [AgentDojo](https://github.com/ethz-spylab/agentdojo) | Prompt Injection 攻防与工具安全 | 仓库声明 MIT，API 仍可能变化 | 安全模块形成后接入，使用固定 release，不跟随 main 分支 |
| [AgentBoard](https://github.com/hkust-nlp/AgentBoard) | 多环境、多轮任务和细粒度进度评测 | 代码 Apache-2.0，数据集 GPL-2.0，且包含多个上游环境 | 当前只借鉴评测维度；若接入，必须逐个检查上游环境并隔离 GPL 数据 |

接入顺序建议为：BFCL 小子集 → τ-bench 或 AgentDojo 的单一 Suite → 更重的多环境 Benchmark。每次只增加一个 Adapter，并配套一份对照实验和一篇结果报告。

---

## 10. MVP 功能需求

### FR-01 Agent 配置管理

V0.1 使用版本控制中的 YAML 或 JSON 定义 AgentSpec，不开发完整的可视化 CRUD 和版本历史系统。

- 至少提供 Baseline Agent 与 Recovery Agent 两个示例配置。
- 可以配置模型、Prompt、工具集、Runtime 策略和预算。
- 参与实验的配置必须生成内容哈希并随结果保存，禁止覆盖后导致历史结果失去依据。
- 克隆和修改配置可通过文件完成。

### FR-02 Task 与 Environment 管理

系统能够加载、校验并展示 TaskSpec 与 Environment 版本，使用固定 Seed 启动任务，并通过代码或配置文件新增任务。

V0.1 不开发任务编辑器，也不要求单独的任务管理后台。

### FR-03 Episode 执行

用户选择 Agent、Task 和 Seed 后启动 Episode。

系统必须执行多轮 Model Call 与 Tool Call，应用停止条件并持久化结构化 Trace。V0.1 可以在 Episode 结束后统一展示结果，不把实时流式 UI 作为验收前置条件。

运行过程至少记录当前步骤、Observation、Tool Call、Tool Result、错误、Token、估算费用、时延和终止原因。

### FR-04 Trace Viewer

用户可以：

- 按时间顺序查看 TraceEvent
- 按事件类型筛选
- 展开工具参数和结果
- 查看 Token、时延和费用
- 查看错误与重试关系
- 跳转至任意 Step

### FR-05 Replay

Replay 基于已保存事件和 Environment Snapshot，不重新调用模型。

支持：

- 上一步
- 下一步
- 跳转到指定步骤
- 查看任意步骤的环境状态

Replay 的目标是复盘，不用于证明重新执行能够得到相同模型输出。

自动播放和速度控制放入 V0.2。

### FR-06 Evaluation

V0.1 至少计算：

- Task Success Rate
- Tool Selection Accuracy
- Tool Argument Validity Rate
- Termination Reason
- Step Count
- API Call Count
- Prompt / Completion Tokens
- Estimated Cost
- End-to-End Latency

Expected Tool Coverage、Forbidden Tool Call Count、Retry Recovery Rate 和 Evidence Accuracy 作为任务级可选指标，在有明确实验需要时启用。

### FR-07 Agent Comparison

用户可以选择多个 AgentSpec，在相同 Task、Seed 和预算下批量运行。

比较页面必须展示：

- 指标均值
- 成功次数 / 总次数
- 成对任务结果
- 成本与成功率关系

中位数、标准差和置信区间在样本量足够时增加。V0.1 不生成误导性的单一 Overall Score。

### FR-08 Experiment

用户可以创建 Experiment，配置：

- AgentSpec 集合
- TaskSpec 集合
- Seed 集合
- 全局费用上限

V0.1 支持创建、启动、查看状态与结果，并导出 JSON。暂停、取消、并发控制、失败 Episode 单独重跑和 CSV 导出放入 V0.2。

### FR-09 Dashboard

完整 Dashboard 与 Leaderboard 不属于 V0.1。首页直接展示 Experiment 列表和标准演示入口；统计信息在 Experiment Detail 中呈现。

后续 Leaderboard 只允许在相同 Benchmark Suite、版本和协议内生成，禁止跨不同任务集直接排名。

---

## 11. 公平性与实验规范

### 11.1 控制变量

架构消融实验必须明确：

- 自变量
- 固定变量
- 评价指标
- 样本规模
- 停止条件

例如：

```text
实验：Memory 是否提高长期信息任务成功率

自变量：Memory enabled / disabled
固定变量：模型、Prompt 主体、工具、任务、Seed、预算
指标：成功率、Token、步骤数、费用
```

### 11.2 模型非确定性

Random Seed 只能保证 Environment 一致，不能保证云端模型输出完全一致。因此平台必须：

- 对每个配置重复运行多个 Episode
- 记录模型名称与可用版本标识
- 记录 Temperature 等参数
- 使用统计聚合而非单次结果下结论

### 11.3 评测器分层

优先级如下：

1. 确定性规则评测
2. Environment 状态评测
3. 工具轨迹评测
4. LLM-as-a-Judge
5. 人工抽样复核

能用代码判断的指标不得只依赖 LLM Judge。

### 11.4 数据集隔离

任务集应划分为：

- Development Set：用于开发和调试
- Evaluation Set：用于版本比较
- Hidden Set：后期用于降低针对测试集调 Prompt 的风险

---

## 12. Checkpoint 与恢复

Checkpoint / Resume 属于 V0.2，V0.1 只在数据模型中保留可选扩展位置，不实现恢复流程。

V0.2 实现时，Checkpoint 至少保存：

- 当前 Step
- Agent 可见消息
- Environment State
- 已用预算
- 已执行 Tool Call ID
- Runtime 状态

恢复要求：

- 进程退出后可以从最近 Checkpoint 恢复
- 相同写操作不能因为恢复而重复执行
- Tool Call 使用唯一幂等键
- 恢复事件写入 Trace

---

## 13. 安全与成本控制

### 13.1 工具安全

所有行为必须经过：

```text
Model Proposal
→ Schema Validation
→ Tool Permission Check
→ Budget Check
→ Runtime Execution
→ Result Sanitization
```

模型不得直接访问文件系统、网络、数据库或 Shell。

### 13.2 工具风险分级

```text
READ_ONLY      自动执行
LOW_RISK_WRITE 记录并执行或要求审批
HIGH_RISK      必须人工审批
FORBIDDEN      永不执行
```

ToolLab 中默认只提供受控模拟工具。真实外部工具在后续版本中接入。

### 13.3 预算控制

每个 Episode 必须支持：

- Max Steps
- Max Model Calls
- Max Tool Calls
- Max Prompt Tokens
- Max Completion Tokens
- Max Estimated Cost
- Max Execution Time

达到任一硬限制时，Runtime 必须终止 Episode 并记录明确原因。

### 13.4 密钥管理

- API Key 仅保存在后端环境变量或 Secret Store
- 前端不能获得明文密钥
- 数据库不保存明文密钥
- Trace 自动脱敏 Authorization、Token 和用户敏感字段

---

## 14. 非功能需求

### NFR-01 可复现性

任何历史 Experiment 均可查看完整配置和版本信息。

### NFR-02 可扩展性

新增 Agent、Environment、Tool 和 Evaluator 不应修改 Episode Runner 核心逻辑。

### NFR-03 可观测性

所有 Model Call、Tool Call 和 Episode 都拥有 Trace ID，并记录结构化日志。

### NFR-04 稳定性

单个 Episode 失败不得导致整个 Experiment 崩溃。

### NFR-05 性能

在不包含模型响应时间时，Runtime 单步调度开销目标小于 100ms。

### NFR-06 测试

核心 Runtime、预算控制器、Tool Executor 和 Evaluator 必须具有单元测试；完整 Episode 必须具有集成测试。

---

## 15. 数据模型

```text
User
│
├── AgentSpec
│     └── AgentVersion
│
├── EnvironmentSpec
│     └── EnvironmentVersion
│
├── TaskSpec
│     └── TaskVersion
│
└── Experiment
      ├── ExperimentConfig
      └── Episode
            ├── TraceEvent
            ├── Checkpoint
            ├── EvaluationResult
            └── Artifact
```

建议核心表：

- `agent_specs`
- `agent_versions`
- `environment_versions`
- `task_versions`
- `experiments`
- `episodes`
- `trace_events`
- `checkpoints`（V0.2）
- `evaluation_results`
- `model_usage_records`

---

## 16. 推荐技术栈

以下为 V0.1 已确定的技术基线。依赖的精确版本在初始化仓库时写入锁文件；替换核心框架或新增重量级基础设施必须先更新本文档或通过 ADR。

### 后端

- Python 3.12
- uv（环境、依赖与锁文件）
- FastAPI
- Pydantic v2
- SQLAlchemy 2.0 稳定版
- Alembic
- SQLite（V0.1）

PostgreSQL 只在 SQLite 已构成可测量瓶颈时通过 Repository Adapter 替换。不得在 V0.1 引入 Redis、Celery 或独立任务队列。

### Agent

- AgentLabyrinth 自有 Runtime Port
- V0.1：`HandwrittenRuntime`
- V0.2：`LangGraphRuntimeAdapter`
- 自有 `ModelProvider` Port、一个真实 Provider Adapter 与 `FakeModelProvider`
- Pydantic 只用于 Domain、Tool Schema 和结构化数据校验；V0.1 不引入 PydanticAI
- OpenAI Agents SDK、Google ADK、CrewAI、Microsoft Agent Framework 和 LlamaIndex 均不得成为 V0.1 Core 依赖
- MCP SDK 仅在后续 MCP 版本接入

### 前端

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Tailwind CSS
- Recharts（仅用于确有必要的实验指标图）

V0.1 不使用 Next.js。项目是本地实验控制台，不需要 SEO、SSR 或 React Server Components；前后端通过明确的 HTTP API 契约通信。

### 工程化

- 本地一键启动脚本
- pytest
- Ruff
- mypy
- GitHub Actions
- 前端单元测试与至少一条 Playwright E2E
- Docker Compose、OpenTelemetry、Prometheus / Grafana 仅在后续出现明确需求时引入

### V0.1 明确不使用

```text
LangChain
LangGraph（作为 Core 或提前实现 Adapter）
PydanticAI
OpenAI Agents SDK
Google ADK
CrewAI
Next.js
Redis / Celery
PostgreSQL
Kafka
Docker Compose
Kubernetes
微服务拆分
```

### 技术选型依据

- FastAPI 与 Pydantic 提供类型化 API、JSON Schema 和 OpenAPI，适合复用 Tool Schema 与领域契约。
- React + Vite 足以实现本地实验配置、结果对比和 Trace Replay，避免引入本项目不需要的服务端渲染复杂度。
- 手写 Runtime 保留完整学习与观测价值；LangGraph 作为首个 Adapter，用于学习状态图、持久化、Checkpoint 与 Human-in-the-loop。
- Inspect AI 作为重要参考项目和潜在外部评测 Adapter，不作为 AgentLabyrinth Core 底座，避免本项目退化为现有评测框架的 UI 包装。

---

## 17. MVP 页面

V0.1 只要求三个页面。AgentSpec 与 TaskSpec 由配置文件维护，可在实验页面只读展示，不单独开发管理后台。

### 17.1 Experiment List / Builder

- 查看最近实验
- 选择 Agent
- 选择任务集
- 设置 Seeds 与预算
- 估算 Episode 数量
- 启动实验

### 17.2 Experiment Detail

- 当前进度
- 成功 / 失败统计
- Agent 对比表
- 成本与延迟
- Episode 列表

### 17.3 Episode Trace / Replay

左侧展示 Environment 状态，右侧展示 TraceEvent 时间线，支持单步回放和事件筛选。

---

## 18. MVP 验收标准

V0.1 完成必须同时满足：

1. 可以加载并以内容哈希固化至少 2 个 AgentSpec：Baseline Agent 与 Recovery Agent。
2. 可以运行 12 个 ToolLab 原生 TaskSpec，覆盖四类核心任务。
3. 同一任务可以使用固定 Seed 重建相同初始环境。
4. Agent 能够完成多轮 Tool Calling，而非单次模型问答。
5. Runtime 能处理非法工具、参数错误、暂时性超时和最大步骤限制。
6. 每个 Episode 都有完整结构化 Trace。
7. Replay 不重新调用模型即可复盘全部步骤。
8. 可以批量执行 Agent × Task × Seed 实验。
9. 可以比较成功率、工具准确率、步骤、Token、费用和时延。
10. 使用同一模型、工具、任务、Seed 和预算完成 Baseline 与 Recovery Runtime 的对照实验，并形成结论。
11. 同时提供 FakeModelProvider 和至少一个真实 Model Provider Adapter；自动化测试不得依赖付费模型。
12. 核心 Runtime、Tool Executor、Environment 与 Evaluator 具有自动化测试。
13. README 提供一键启动、架构说明、标准演示、实验方法、结果和局限性。
14. 普通实验操作者无需逐步操作 ToolLab 或手动批准模拟工具。
15. 新增 Environment 不需要修改 Episode Runner 核心逻辑。
16. V0.1 不以接入外部数据集为验收条件，但外部 Suite Adapter 接口和数据清单规范必须明确。
17. Domain、Application Core 与 HandwrittenRuntime 不依赖任何外部 Agent 框架。
18. `docs/learning/` 提供 HandwrittenRuntime、Tool Executor、Trace 与 Evaluator 的源码阅读指南和最小运行实验。

---

## 19. 版本路线图

### V0.1 — Arena Core

目标：跑通可复现的单 Agent 评测闭环。

- 框架无关的 Runtime Port 与 HandwrittenRuntime
- Tool Schema 与 Function Calling
- ToolLab Environment
- Task / Episode / Trace
- 基础 Evaluation
- Replay
- Agent Comparison
- 最小批量 Experiment
- 预算控制

### V0.2 — Experiment & Reliability

目标：从 Demo 升级为可靠实验平台。

- 并发 Experiment、暂停 / 取消与失败任务重跑
- Checkpoint / Resume
- 幂等性
- 扩展故障注入
- 外部 Benchmark Adapter
- 自动回归评测
- LangGraph Runtime Adapter
- HandwrittenRuntime 与 LangGraph 在同一 Suite 下的对照实验
- Trace 与指标看板

### V0.3 — Agent Intelligence Lab

目标：研究 Agent 架构组件的真实效果。

- Planning Challenge
- Memory Challenge
- Reflection Challenge
- Error Recovery Challenge
- Context Management
- 通过 ADR 选择第二个外部 Runtime Adapter，PydanticAI 为优先候选
- 消融实验模板
- LLM-as-a-Judge 与人工复核

### V0.4 — GridWorld Arena

目标：增加具有趣味性、可视化和确定性规则的规划环境。

GridWorld 包含：

- 二维地图
- 墙、钥匙、门、资源与目标点
- 部分可观测地图
- 隐藏信息
- 有限步数与资源
- 可视化 Replay

Agent 可执行：

```text
move_up
move_down
move_left
move_right
inspect
pickup
use
communicate
```

GridWorld 重点评测：

- 空间规划
- Long-horizon Planning
- 历史信息记忆
- 非法行动率
- 路径效率
- 失败后的重新规划

该环境不属于当前 MVP，但作为长期项目的重要更新内容保留。

### V0.5 — MCP & Human-in-the-loop

目标：接入更接近生产环境的工具生态。

- 自建 MCP Server
- MCP Tools / Resources
- Tool Risk Level
- Human Approval
- Prompt Injection 防护
- Tool Audit Log

### V0.6 — Multi-Agent Arena

目标：比较单 Agent 与多 Agent 的收益和代价。

- Coordinator / Specialist 模式
- Handoff
- 多 Agent Communication
- Cooperation Task
- Hidden Information
- 单 Agent / 多 Agent 对比

### V0.7 — Competition Arena

目标：支持受控竞争与博弈任务。

- 有限资源竞争
- 协作与背叛机制
- 多轮策略
- Agent Elo 或场景内积分
- 对局 Replay

Elo 只用于同一规则版本下的竞技任务，不替代通用能力评测。

### V1.0 — AgentLabyrinth

形成具备以下能力的稳定版本：

- 多 Environment
- 单 Agent 与多 Agent
- 可复现实验
- 架构消融
- Trace 与 Replay
- MCP 与安全审批
- 自动化评测与回归测试

Agent Society、Digital Life 和 Agent Evolution 作为 V1.0 之后的研究方向，不承诺具体交付时间。

---

## 20. 项目开发与学习策略

项目采用“问题驱动式演进”，每一项新技术必须对应一个真实问题：

```text
模型无法访问外部状态
→ Tool Calling

多轮工具调用难以管理
→ Agent Runtime

流程分支与恢复复杂
→ LangGraph / Checkpoint

历史经验无法复用
→ Memory

工具接入耦合严重
→ MCP

危险工具不可直接执行
→ Human-in-the-loop / Guardrails

不知道优化是否有效
→ Eval / Trace / Ablation Study

单 Agent 上下文或能力不足
→ Multi-Agent
```

每个功能版本必须产出：

- 一个明确 Issue
- 一个可运行实现
- 至少一个失败测试
- 一次前后对比实验
- 一份简短技术决策记录
- 一个 Git Tag 或 Release

### 20.1 实践式学习闭环

核心功能采用以下闭环，而不是要求项目负责人先完整学习框架再开始开发：

```text
明确要解决的问题
→ AI Agent 在约束内实现
→ 自动化测试与实验验证
→ 项目负责人按阅读顺序阅读源码
→ 运行或修改一个最小案例
→ 向 Codex / Antigravity 追问设计与原理
→ 用自己的语言记录理解
→ 再进入下一项技术
```

源码阅读是正式交付环节，不是开发完成后的可选活动。项目负责人阅读后发现难以理解的结构，可以提出重命名、拆分或补充文档，但不得以“更容易读”为由破坏正确的架构边界。

### 20.2 核心功能学习交付包

Runtime、Tool Executor、Trace、Evaluator、Environment、Checkpoint、Memory、MCP 和 Multi-Agent 等核心功能完成时，必须在 `docs/learning/` 提供一份学习说明，至少包含：

1. 该功能解决了什么具体问题。
2. 建议阅读的文件顺序。
3. 入口函数与主调用链。
4. 关键对象及其生命周期。
5. 正常路径、失败路径和停止条件。
6. 一条可以本地运行的最小命令或测试。
7. 一组对照实验及结果解释。
8. 当前实现刻意没有解决的问题。
9. 项目负责人读完后应能回答的检查问题。

学习文档不得逐行翻译代码，也不得伪造设计动机。代码注释优先说明“为什么存在此约束”，不重复描述语句表面含义。

---

## 21. 项目交付物

项目进入简历前至少具备：

- 可公开访问的代码仓库
- 清晰的 README
- 面向开发 Agent 的 AGENTS.md
- 面向团队成员的 CONTRIBUTING.md
- 系统架构图
- 一键启动脚本
- 12 个经过测试的原生评测任务
- 至少一份外部 Benchmark Adapter 设计说明；实际接入可在 V0.2 后完成
- 完整 Trace 与 Replay 演示
- 一份 Agent 架构消融报告
- 成本、延迟、成功率对比图
- 3 分钟以内演示视频
- 自动化测试与 CI 结果

---

## 22. 项目风险与应对

### 风险 1：范围持续扩大

应对：严格按照版本路线开发，当前版本未验收前不实现后续功能。

### 风险 2：平台很复杂，但没有有价值的实验

应对：V0.1 即提供任务集和消融实验，不把 UI 或框架数量作为核心成果。

### 风险 3：GridWorld 被认为只是小游戏

应对：将其定位为后续确定性规划 Benchmark，并与 ToolLab、Memory 和 Multi-Agent 实验结合，不作为平台唯一环境。

### 风险 4：模型随机性破坏公平比较

应对：固定环境、配置和预算，使用多个 Seed 与重复运行，通过统计指标得出结论。

### 风险 5：Token 成本失控

应对：从第一版实现硬预算、运行前 Episode 数量提示和 Experiment 总费用限制。

### 风险 6：Trace 泄露敏感数据

应对：默认脱敏，不存储密钥和隐藏思维链，支持字段级过滤。

### 风险 7：ToolLab 用户操作过多

应对：严格区分 Experiment Operator 与 Benchmark Author。普通用户只配置并启动实验，工具调用和错误恢复由 Agent 与 Runtime 自动完成。

### 风险 8：团队成员与 AI Agent 理解不一致

应对：本文档作为 SSOT；关键决策写入 ADR；每个 Issue 必须明确目标、非目标、验收标准和测试要求。

### 风险 9：直接复制外部数据造成许可、污染或错误对比

应对：外部数据默认按需下载；保存来源、版本、许可和校验值；开发集与评测集隔离；适配或抽样结果不得冒充官方 Benchmark 分数。

---

## 23. 当前实现边界

### 23.1 V0.1 必须实现

- 框架无关的 AgentRuntime Port 与 HandwrittenRuntime
- Tool Schema 与 Function Calling
- Tool Registry 与 Tool Executor
- ToolLab Environment
- Task、Episode、Trace 与 Evaluation
- 单个 Episode 和批量 Experiment
- 基础 Replay
- Agent Comparison
- Token、费用、步骤和时间预算
- FakeModelProvider 与自动化测试
- 核心功能学习交付包与跨电脑 current-state 文档

### 23.2 V0.1 只定义接口、不实现

- Checkpoint / Resume
- LangGraph Runtime Adapter 的接入契约；不创建实现包
- Agentic RAG
- Memory
- Reflection
- MCP
- Human-in-the-loop
- GridWorld
- Multi-Agent

接口预留必须最小化，并且至少被当前实现或契约测试使用。禁止创建空模块、空服务或未经验证的未来抽象。

### 23.3 V0.1 禁止实现

- GridWorld 游戏逻辑与地图编辑器
- Agent Society、Digital Life 和 Agent Evolution
- Browser / Computer Use
- 真实 Shell 和危险外部写操作
- 分布式微服务拆分
- Kubernetes
- 复杂 RBAC
- 付费、订阅和多租户
- 将 LangGraph、PydanticAI、OpenAI Agents SDK、Google ADK、CrewAI 或其他 Agent 框架引入 Core

---

## 24. 仓库与模块规范

### 24.1 推荐目录

~~~text
agent-labyrinth/
├── apps/
│   ├── api/
│   └── web/
├── packages/
│   ├── domain/
│   ├── application/
│   ├── runtime/
│   │   └── handwritten/
│   ├── environments/
│   │   └── tool_lab/
│   ├── tools/
│   ├── evaluation/
│   ├── providers/
│   └── persistence/
├── benchmarks/
│   └── tool_lab_core/
│       ├── suite.yaml
│       ├── tasks/
│       ├── fixtures/
│       └── evaluators/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── e2e/
├── docs/
│   ├── adr/
│   ├── architecture/
│   ├── experiments/
│   ├── learning/
│   └── handoffs/
├── .agents/
│   └── rules/
├── scripts/
├── alembic/
├── pyproject.toml
├── uv.lock
├── README.md
├── AGENTS.md
└── CONTRIBUTING.md
~~~

### 24.2 目录规则

- Benchmark 数据不得散落在业务代码目录。
- Provider SDK 只能出现在 providers 或 infrastructure。
- ToolLab 业务逻辑只能位于 environments/tool_lab。
- 通用领域对象不得引用 ToolLab。
- 测试夹具不得与生产数据混用。
- API Route 不得直接访问数据库实现。
- 外部 Agent 框架代码只能位于 Runtime Adapter 目录；V0.1 不创建空 Adapter 模块。
- `docs/learning/` 保存核心功能源码阅读指南，`docs/handoffs/current-state.md` 保存跨电脑继续开发所需的当前状态。
- `.agents/rules/` 保存 Antigravity 和其他兼容 Coding Agent 必须读取的工作区规则，其内容不得与本文档冲突。
- 临时脚本进入 scripts；确认无复用价值后删除。
- 新增顶级目录必须说明职责和依赖方向。

---

## 25. 编码与数据规范

### 25.1 Python

- 使用 Python 3.12+。
- 公共函数和接口必须有类型注解。
- 数据边界使用 Pydantic 校验。
- 领域模型优先使用 dataclass 或明确的领域类型。
- 异步 I/O 使用 async / await。
- 禁止在 async 函数中直接执行阻塞网络或文件操作。
- 禁止裸 except。
- 禁止在业务代码中使用 print。
- 使用结构化日志。
- 公共接口必须有简洁 docstring。
- 优先组合与 Protocol，避免不必要的继承。

### 25.2 TypeScript

- 开启 strict。
- 禁止无说明的 any。
- API 数据必须有静态类型并在边界进行 Schema 校验。
- 页面组件不得包含复杂业务规则。
- 服务端状态与本地 UI 状态必须分离。

### 25.3 命名

- 类：PascalCase
- Python 函数与变量：snake_case
- TypeScript 函数与变量：camelCase
- 常量：UPPER_SNAKE_CASE
- 事件类型：UPPER_SNAKE_CASE
- 数据库表：snake_case 复数
- API 路径：小写复数名词

### 25.4 ID 与时间

- 业务实体统一使用 UUID 或 ULID，具体方案由 ADR 确定。
- 外部可见 ID 不得直接使用数据库自增主键。
- 后端统一存储 UTC。
- 时间使用 ISO 8601。
- Duration 使用整数毫秒。

### 25.5 Token 与费用

- Token 数量使用整数。
- 金额使用 Decimal，禁止 float。
- 保存货币代码与价格表版本。
- Estimated Cost 必须明确标记为估算值。

### 25.6 配置与密钥

- 配置与代码分离。
- 不得硬编码 API Key、模型价格、URL 和机器路径。
- 提供 .env.example，但不得提交真实 .env。
- 前端、日志和 Trace 不得出现明文密钥。

### 25.7 新增依赖

新增运行时依赖必须在 PR 中说明：

- 解决的问题
- 为什么现有依赖不能解决
- 维护状态
- License
- 安全和体积影响

新增重量级框架或基础设施必须建立 ADR。

---

## 26. API、事件与错误规范

### 26.1 API

- API 使用版本前缀，例如 /api/v1。
- 路径使用小写复数名词。
- 创建资源返回 201。
- 创建异步 Experiment 返回 202。
- 请求与日志必须携带 request_id。
- 列表接口统一分页。
- API 不得返回供应商 SDK 原始对象。

### 26.2 错误响应

~~~json
{
  "error": {
    "code": "TASK_VERSION_NOT_FOUND",
    "message": "Task version does not exist",
    "retryable": false,
    "details": {},
    "request_id": "..."
  }
}
~~~

错误至少分为：

- VALIDATION_ERROR
- NOT_FOUND
- CONFLICT
- BUDGET_EXCEEDED
- MODEL_PROVIDER_ERROR
- TOOL_EXECUTION_ERROR
- ENVIRONMENT_ERROR
- STORAGE_ERROR
- INTERNAL_ERROR

用户可见错误不得暴露堆栈、密钥和内部绝对路径。

### 26.3 TraceEvent

所有 TraceEvent 必须包含：

~~~text
event_id
episode_id
step_index
event_type
timestamp
duration_ms
payload
token_usage
estimated_cost
parent_event_id
schema_version
~~~

TraceEvent 写入后原则上不可修改；纠错通过追加事件完成。

### 26.4 Schema 版本

所有持久化配置、公共 API DTO 和事件必须包含或可解析出 schema_version。

---

## 27. 测试与质量门槛

### 27.1 Unit Test

必须覆盖：

- Budget Controller
- Tool Schema Validation
- Tool Executor
- Environment State Transition
- Evaluator
- Runtime Stop Condition

### 27.2 Contract Test

所有 Environment、ModelProvider、AgentRuntime 和 Evaluator 实现必须通过对应公共契约测试。

### 27.3 Integration Test

完整 Episode 集成测试使用 FakeModelProvider，不依赖真实付费模型。

### 27.4 E2E Test

至少覆盖：

~~~text
创建 AgentVersion
→ 运行 Episode
→ 生成 Trace
→ 执行 Evaluation
→ Replay
~~~

### 27.5 必测失败场景

- 不存在的工具
- Tool Schema 参数错误
- Tool 超时
- 可重试与不可重试错误
- 模型返回无法解析
- 重复 Tool Call
- 最大步骤终止
- Token 或费用超限
- 单个 Episode 失败但 Experiment 继续

### 27.6 合并门槛

Pull Request 必须满足：

- 格式化通过
- Lint 通过
- 类型检查通过
- 单元测试通过
- 相关集成测试通过
- 无新增高危依赖漏洞
- 行为变化已更新文档或测试
- 核心接口变化已关联 ADR

覆盖率作为风险信号，不作为唯一质量目标。Runtime、Tool Executor、Budget Controller 与 Evaluator 的关键分支必须有明确测试。

---

## 28. Git 与团队协作规范

### 28.1 分支

- main 必须始终可运行。
- 功能分支：feat/issue-id-short-name
- 修复分支：fix/issue-id-short-name
- 文档分支：docs/issue-id-short-name

### 28.2 Commit

建议使用 Conventional Commits：

- feat:
- fix:
- refactor:
- test:
- docs:
- chore:

一个 Commit 应表达一个逻辑变更。禁止将无关格式化、重构和功能混在同一 Commit。

### 28.3 Issue

每个功能 Issue 必须包含：

- 背景与问题
- 目标
- 明确不做
- 验收标准
- 影响模块
- 测试要求

### 28.4 Pull Request

PR 必须说明：

- 改了什么
- 为什么改
- 如何验证
- 是否改变接口或数据
- 风险与回滚方式
- UI 或 Agent 行为变化的截图或 Trace

### 28.5 Code Review 顺序

1. 是否超出版本边界
2. 是否破坏核心接口
3. 是否遗漏错误状态
4. 是否可测试、可观测
5. 是否带来安全或成本风险
6. 代码风格

---

## 29. AI Coding Agent 协作规范

任何协助开发的 AI Agent 在修改代码前必须：

1. 阅读本文档
2. 阅读仓库根目录 AGENTS.md
3. 检查相关模块和现有测试
4. 明确任务验收标准
5. 保持改动范围最小

AI Agent 必须遵守：

- 不自行扩大需求
- 不提前实现后续版本
- 不以未来可能需要为由增加复杂抽象
- 不静默改变核心接口
- 不新增依赖而不说明理由
- 不删除未知用途代码
- 不覆盖团队成员未提交的改动
- 不把密钥、真实数据或隐藏思维链写入仓库
- 不伪造测试结果、指标或 Benchmark 数据
- 不把 Mock 结果描述成真实模型结果
- 完成后运行与改动相关的测试
- 报告修改文件、验证结果和剩余风险

出现以下情况时，AI Agent 必须停止并请求确认：

- 需求与本文档冲突
- 需要跨越多个核心模块边界
- 需要修改数据 Schema
- 需要新增外部服务
- 需要执行破坏性数据库或文件操作
- 无法判断现有数据或代码是否可删除

### 29.1 协作角色边界

| 角色 | 主要职责 | 未经确认不得执行 |
|---|---|---|
| 项目负责人 | 产品决策、学习验收、运行验证、合并与发布 | 无 |
| Codex | 架构、领域模型、核心 Runtime、Tool Executor、Trace、Evaluator、关键测试与架构审查 | 擅自扩大产品范围或替项目负责人作不可逆业务决策 |
| Google Antigravity | 按既定契约实现前端、API、Persistence、Task Fixture、普通测试、E2E 和 UI 验证 | 修改 Domain 语义、Runtime Port、Trace Schema 或评测口径 |
| 其他 AI Agent | 完成任务卡明确授权的局部工作 | 跨越任务卡文件范围或重新设计架构 |

角色表示默认分工，不代表代码所有权。任何 Agent 修改他人负责的核心区域前，必须先说明原因、影响和验证方法。

同一时间不得让两个 AI Agent 修改同一文件。前期采用同一仓库串行开发；需要并行时使用独立 Git Worktree 和独立分支，通过 Commit 或 PR 合并。

### 29.2 跨电脑与上下文同步

项目可能在不同电脑、不同 Codex 任务和 Antigravity IDE 中继续开发。所有 Agent 必须遵守：

1. 不把聊天历史视为可移植上下文。
2. 开始任务前核对本文档版本；低于当前 SSOT 版本时停止开发并先同步。
3. 依次阅读需求文档、`AGENTS.md`、相关 ADR、`docs/handoffs/current-state.md`、相关测试和代码。
4. 每次合并核心功能后更新 `current-state.md`，包括当前阶段、已完成、正在进行、下一任务、已知问题和最后验证命令。
5. 影响架构的口头决定必须写入 ADR；影响当前范围的决定必须更新本文档。
6. 任务提示必须引用 SSOT 版本和相关文件，不得只写“按照之前聊的继续”。
7. 本机特有路径、密钥、模型账号和 IDE 设置不得写死在代码或共享文档中。

### 29.3 AI Agent 任务模板

~~~text
SSOT 版本：

目标：

背景：

负责 Agent：Codex / Antigravity / 其他

允许修改：

禁止修改：

明确不做：

验收标准：

相关接口：

必须运行的测试：

学习交付要求：

交付说明：
~~~

团队给 AI Agent 分派开发任务时应该优先使用该模板。

### 29.4 AI Agent 完成交付格式

核心任务完成后，AI Agent 必须同时报告：

- 修改了哪些文件以及各自职责。
- 从哪个入口开始阅读源码。
- 主调用链和关键状态变化。
- 实现了哪些失败处理和停止条件。
- 运行了哪些测试，结果是什么。
- 哪些结论来自真实模型实验，哪些只来自 FakeModelProvider。
- 剩余风险、未实现内容和建议的下一个最小任务。

不得只回复“已完成”或提供一段无法与仓库代码对应的概念解释。

---

## 30. ADR 与技术决策

项目初始化时必须建立 `ADR-001-runtime-strategy.md`，状态为 Accepted，记录以下已确定决策：V0.1 采用框架无关 Runtime Port 与 HandwrittenRuntime；外部 Agent 框架只能通过 Adapter 接入；LangGraph 是 V0.2 的首个 Adapter；使用 Antigravity IDE 不等于选择 Google ADK。

以下决策必须建立 ADR：

- 改变 Runtime Core 策略或选择新的外部 Runtime Adapter
- 数据库与迁移方案
- ID 策略
- Trace 存储方式
- Queue 选择
- MCP 接入方式
- GridWorld 状态模型
- Multi-Agent 通信协议

ADR 模板：

~~~text
# ADR-NNN：标题

## 状态
Proposed / Accepted / Superseded

## 背景

## 候选方案

## 决策

## 原因

## 代价与风险

## 回滚方式
~~~

ADR 只记录重要、长期且难以回滚的技术决策。

---

## 31. 项目成功指标

在 V0.1 阶段，项目成功不以用户数量衡量，而以以下结果衡量：

- 能否稳定执行并复盘多轮 Agent 任务
- 能否准确定位 Agent 失败步骤
- 能否公平比较两个 Agent 配置
- 能否通过数据证明某项 Agent 技术有效或无效
- 能否控制成本、循环和危险行为
- 能否在不修改 Runner 的情况下新增任务、工具和环境

---

## 32. 项目一句话定义

> **AgentLabyrinth 是一个面向 AI Agent 的可复现实验与评测平台，通过标准化 Agent、Environment、Task、Runtime、Trace 和 Evaluation，让不同 Agent 在统一条件下完成任务、复盘行为并比较能力，并逐步扩展至 GridWorld、多智能体协作与竞技。**

---

## 33. 简历项目描述参考

> 设计并实现 AgentLabyrinth——面向 AI Agent 的可复现实验与评测平台，自研 Agent Runtime 与工具执行链路，支持结构化 Tool Calling、预算控制、错误恢复、完整 Trace 及无模型重放 Replay。

> 构建版本化的 Agent、Task 与 Environment 抽象，在相同任务、随机种子和预算下批量执行对照实验，从成功率、工具选择准确率、参数合法率、Token 成本和执行时延等维度评价 Agent 架构。

> 建立 ToolLab 确定性任务集及自动化评测流程，通过消融实验定量分析 Planning、Memory、Reflection 等机制的收益与代价；后续扩展 GridWorld、MCP 和 Multi-Agent Arena。
