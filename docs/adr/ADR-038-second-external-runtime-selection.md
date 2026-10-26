# ADR-038：第二外部 Runtime 选型（PydanticAI 优先候选）

- **状态**：Accepted（2026-10-21 负责人确认三项：A1限定可接受并记为调度缺口、`pydantic-ai-slim==2.57.0` 装入项目锁、按候选契约一次性定案）。已按 §12 完成安装、adapter、契约与参数化测试；**PydanticAI 只作为第三个运行实现，步间推进仍归 adapter**，不宣称框架驱动整轮循环，也不代表需求 §8.5 第三调度实现已完成。
- **需求**：requirements V0.6 §8.5（框架接入规则）、§19（V0.3 范围）、§29（协作规范）；[周计划](../tasks/V0.3-week-plan-20261019.md)第 4 项。
- **相关**：ADR-001（Runtime 策略）、ADR-009/010（LangGraph Bootstrap 与独立调度对照）、ADR-011（安全点恢复）、ADR-016（固定回归）、ADR-035/036（当前 AgentSpec 1.3 / 请求 1.9 / 产物 1.6 基线）。
- **编号说明**：目录当前最大 037，本文件占用 038。

## 1. 要回答的实验问题

第二个外部框架不是“多接一个模型”，而是验证：**在同一组 TaskSpec、Environment、模型、预算、Seed 与恢复策略下，换用第三个调度实现时，工具校验、Trace、终止原因、Token/费用与安全点恢复是否仍等价可解释。** 它度量的是调度与框架抽象的差异，不是模型能力；Fake 对照只能证明契约一致，不能当真实收益。

现只有 `handwritten` 与 `langgraph`，`runtime_backend` 轴右侧固定 LangGraph。缺少第三个独立实现时，“框架无关”只有两个样本，无法区分“共享 Session 设计”与“LangGraph 特有行为”。

## 2. 候选核对（2026-10-21官方来源复核，未安装）

| 候选 | 待选的固定版本（不等于当日最新） | 许可 | Python | 适配关键点 | 主要风险 |
| --- | --- | --- | --- | --- | --- |
| **A. PydanticAI** | `pydantic-ai` **2.57.0**（2026-10-16 发布） | MIT | ≥3.11 | 官方支持子类化 `Model`/`WrapperModel` 接入自定义模型；内置 `test` 模型可无 Key 做契约测试；工具/结构化输出走 Pydantic v2；OTel 可选、默认不启用外部服务 | 框架自有 agent loop 与工具分发可能绕过本项目 Validator/Executor；2.x 迭代快，需锁精确版本并记录不可比差异 |
| B. OpenAI Agents SDK | `openai-agents` **0.24.0** | MIT | ≥3.10 | agent/runner，支持可替换模型与function tools等 | 同样需验证Provider/消息/工具/预算/恢复映射；不能在未做适配比较前断言其映射面必然更大 |
| C. Google ADK | `google-adk` **2.12.0** | Apache-2.0 | ≥3.11 | 图/工作流与多Agent等能力 | 当前不需其多Agent能力；依赖规模与Adapter成本未实际测量，不能断言最大 |

可追溯固定发布页：[PydanticAI 2.57.0](https://pypi.org/project/pydantic-ai/2.57.0/)、[OpenAI Agents SDK 0.24.0](https://pypi.org/project/openai-agents/0.24.0/)、[Google ADK 2.12.0](https://pypi.org/project/google-adk/2.12.0/)。2.57.0发布于10月16日，但官方发布历史已有10月20日的2.58.0，故不能称2.57.0为10月21日最新；是否保留旧固定候选或换版本须在提案中说明，不自动追新。上述许可/Python结论仅针对这些包，**未安装、未核对全部传递依赖或证明兼容**。

依赖方案须比较完整`pydantic-ai`与`pydantic-ai-slim`：完整包默认附带多个Provider及集成，官方支持slim按需安装；本项目走自定义ModelProvider桥接时应优先论证slim且不加无用extras。[官方安装说明](https://pydantic.dev/docs/ai/overview/install/#slim-install)。选定前不修改pyproject/uv.lock；获批准后锁定实际distribution/精确版本、审查锁文件差异，并按实际安装的distribution查询版本，不能slim安装后去查询不存在的元包。

### 2.1 最少依赖方案（设计，**未安装**，代价均待实测）

| 方案 | distribution | 内容 | 结论 |
| --- | --- | --- | --- |
| 完整包 | `pydantic-ai==2.57.0` | 默认附带多个Provider及其SDK集成 | **不选**：本项目只用自定义`Model`桥接现有`ModelProvider`，额外Provider/传输栈是无用依赖 |
| slim基础 | `pydantic-ai-slim==2.57.0` | 官方slim安装，不含Provider extras | **拟选**；实际传递依赖、许可、体积在安装日以`uv lock`差异逐项列出，不以本表断言 |
| 自建Fake Model | 包内测试模型（若slim含）或自写`Model`子类 | 复用现有`FakeModelProvider`语义 | 若slim未包含内置测试模型则自写，**不为此改装完整包** |

拒绝/停止标准（任一成立即停下回报负责人，不得为“用上框架”弱化边界）：

- **R1**：需要额外Provider SDK/extras才能使用自定义`Model`或工具调用边界。
- **R2**：新增传递依赖与现有`pydantic`/`httpx`等出现不兼容的大版本，或必须更换既有锁定核心依赖。
- **R3**：框架强制初始化外部追踪/日志上报服务才能运行（本项目要求默认关闭）。
- **R4**：slim版缺少§4.1.1所需的S1/S2/S3接缝。

未安装前不得写“依赖兼容已验证”；版本必须按实际安装的distribution查询元数据（slim时查`pydantic-ai-slim`），不得查询不存在的元包。

## 3. 选项与推荐

- **方案 A（推荐）**：新增 `PydanticAIRuntimeAdapter`，用自定义 `Model` 子类把现有 `ModelProvider.generate()` 桥接进框架循环（Fake 与真实模型同路径），工具函数只委托现有校验/执行边界。理由：与项目 Pydantic v2 契约同源；官方文档称提供无 Key 测试模型（是否包含在slim内待安装日核对，缺则自写Fake Model）；许可宽松；不强制外部追踪服务。与需求 §8.5 的“PydanticAI 优先候选”一致。
- 方案 B：OpenAI Agents SDK。若 A 的 spike 证明无法保持 fail-closed 校验/批次语义，可作为第二顺位重评。
- 方案 C：Google ADK。当前单 Agent、无多 Agent 需求，图能力与 LangGraph 重叠，暂不作为第二框架。

推荐 A 的前提是 §4 的硬约束在 spike 中全部成立；**只要有一条无法成立且需要放宽原边界，就停止 A 并回到负责人重选**，不允许“为了用框架”弱化校验、预算或 Trace。

接入判据是**完整Episode的实际节点转移归属**，不是符号存在、一次Agent调用或外层是否出现while。若仅由Adapter按Session返回值复刻原model/validate/execute循环、框架每次只包装一次模型请求，则只是模型桥接，不能发布为第三Runtime或据此算需求完成。普通驱动循环消费框架实际返回的节点是允许的，LangGraph的图节点也复用Session，不能把“共享Session”本身当缺陷。完整框架调度若经准入验证可满足§8.5的适配要求，但仍不代表V0.3整版签收。未通过时报告不适配，不将限定模型桥接顺势升级为本轮产品。

## 4. 适配硬约束（不满足即放弃，不得静默降级）

1. **依赖隔离**：框架 import 只出现在 `packages/runtime/pydantic_ai/`；Domain/Application/API 不出现框架类型，不把框架消息对象写入 `SessionState` 或产物。
2. **唯一工具入口**：框架中的工具函数只做“参数 → 现有 Validator/Executor”的委托；禁止框架层自带重试、并行或跳过 `ToolCall` 校验。`UNKNOWN_TOOL`/`FORBIDDEN_TOOL`/重复 `call_id`/第二次参数错/超时/预算终止必须仍由现有规则决定。
3. **批次语义**：`tool_call_mode=single`与serial均应保持现有语义，包括整批参数/权限预检、唯一Call ID、只读/大小限制、逐项预算和剩余队列。验证阶段不支持serial时应在创建前明确拒绝，不能降级；这只是未通过准入的限制，不能据此宣布已完成需求中的批次Adapter。若要发布单工具限定范围，必须另行明确批准并同步UI/契约，不可自动缩水。
4. **Trace 单一来源**：`MODEL_REQUESTED`、`TOOL_CALL_VALIDATED`、`TOOL_SUCCEEDED`、`EPISODE_FINISHED` 等仍由共享 Session 产生；框架自有 span/事件只做内部诊断，不替代统一 `TraceEvent`。无法映射的差异写入 adapter 说明，不伪造事件。
5. **预算与终止**：沿用 `AgentBudget`/Session 的步数、工具次数、Token、时限检查；框架 recursion/step 限制只能更宽，不能先于业务终止触发。
6. **恢复**：安全点仍是 `SessionState`；框架若不支持任意节点恢复，adapter 必须在进入框架循环前恢复到同一可移植安全点，且中断后不重做已完成操作（与 LangGraph 适配同法）。
7. **模型与用量**：自定义Model须保持现有ModelConfig（temperature/max_tokens/tool_call_mode）及真实Provider响应/错误；超时来自Session剩余时限，并非ModelConfig现有字段。必须保持原始已报告/未知用量与参考费用语义，若框架计数默认0不能表示未知，统一产物仍以原Provider响应为准，不能将框架0冒充真实用量。默认关闭外部追踪、自动重试/回退和额外终结调用。
8. **供应商隔离**：不得为框架引入新的 Provider SDK 依赖到 Domain；Key 仍只在本机 `.env`，不入库、不入前端、不入聊天。

## 4.1 调用归属表（设计依据为当前工作区固定源码，**未安装任何框架**）

行号对应工作区 `packages/runtime/session.py` 当前内容（HEAD 40b57c1 + 既有未提交改动）。框架只被允许决定“下一个节点/何时终止”；下列动作在任何adapter中都必须回到同一Session方法，避免双loop/双计费。

| # | 步骤 | 负责方 | 固定依据 | 明令禁止 |
| --- | --- | --- | --- | --- |
| 1 | 时限与模型预算准入 | Session | `session.py` L399-403：`time_exceeded()`、`budget.can_call_model()` | 框架先请求再检查 |
| 2 | 上下文投影与计划覆盖 | Session | L405-449：`project_context`、`_agentlabyrinth_plan`注入 | 框架二次注入系统提示、自行裁剪/修复历史 |
| 3 | 计数并写`MODEL_REQUESTED` | Session | L450-454 | 框架另产一份“统一事件” |
| 4 | **唯一一次**Provider调用 | Session（adapter只能触达此处） | L455-460：`asyncio.timeout(remaining)`包裹单次`provider.generate(...)` | 框架重试/模型回退/结构化输出修复/第二次请求 |
| 5 | 原始响应、错误、未知用量入账 | Session | L461-496：异常携带用量仍入账；超时未返回→用量未知 | 用框架usage=0覆盖真实未知 |
| 6 | 动作分类 | Session | L503-513：`FinalAnswer`→`missing_submission`；非serial的batch→`RUNTIME_ERROR: MULTIPLE_TOOL_CALLS` | 框架把一次多调用拆成两次单调用 |
| 7 | 单次校验 | Session | L543-603：重复ID/未知/禁止工具/仅一次参数纠错 | 框架改写参数或吞掉错误 |
| 8 | 整批预检（任何工具开始前） | Session | L605-677：先全量提议/校验，再决定执行 | 先执行首项再补验其余 |
| 9 | 单项工具执行 | Session | L679-720：`can_start_tool`、`TOOL_STARTED`、`environment.step` | 框架自带executor/并行/自动重试 |
| 10 | 反馈、事件、安全点 | Session | L721-759消息与事件；`checkpoint` L181-205、`restore` L207-232 | 框架消息对象写入`SessionState`或产物 |
| 11 | 下一节点（`execute`/`model`/`end`） | 框架消费Session返回值并驱动 | 现有唯一样例`langgraph/adapter.py` L49-88 | adapter自写一套路由规则 |
| 12 | 未预期异常→`RUNTIME_ERROR` | Adapter（保持既有语义） | `langgraph/adapter.py` L99-102 | 吞异常/伪造成功 |

### 4.1.1 PydanticAI拟用接缝（固定tag只读核对，**未安装、未运行**）

核对日期2026-10-21，固定tag [`v2.57.0`](https://github.com/pydantic/pydantic-ai/tree/v2.57.0)。以下仅为**符号存在**，不是本项目适配成功或行为等价的证据。

- **S1 自定义Model**：Codex已完整取得固定tag文件并静态AST定位：本地快照`models/__init__.py`的Model为L491、request为L730–740（方法签名返回框架ModelResponse）。[固定链接](https://github.com/pydantic/pydantic-ai/blob/v2.57.0/pydantic_ai_slim/pydantic_ai/models/__init__.py)。Session.call_model返回NextNode字符串并改变Session状态，不能直接把其返回值作为框架ModelResponse。准入必须给出原始响应/错误/用量→框架消息及节点的转换，避免递归进入同一桥接Provider、重复投影或双调用；每个批准模型步只能实际请求原Provider一次。符号存在不证明这些转换已成立。
- **S2 工具执行前的延迟边界**：已核对 [`_deferred.py`](https://github.com/pydantic/pydantic-ai/blob/v2.57.0/pydantic_ai_slim/pydantic_ai/_deferred.py)：`DeferredToolRequests`可作`output_type`，模型调用后**不执行工具**而返回完整`ToolCallPart`列表；`DeferredToolResults`按**同一`tool_call_id`**回填结果；`remaining()`可只解决一项并把剩余项交回下一次运行。这与“整批预检后才执行、serial逐项执行、ID不改写”方向一致，但并发/顺序/回填次数必须在准入中实测。`DeferredToolRequests`经 [`tools.py`](https://github.com/pydantic/pydantic-ai/blob/v2.57.0/pydantic_ai_slim/pydantic_ai/tools.py) 再导出（该文件从`._deferred`导入并列入`__all__`）。
- **S3 节点迭代**：Codex完整固定源码AST定位`Agent.iter`实际实现L1314–1469，接受message_history/deferred_tool_results并返回AgentRun；[固定链接](https://github.com/pydantic/pydantic-ai/blob/v2.57.0/pydantic_ai_slim/pydantic_ai/agent/__init__.py)。用于验证#11的后继节点由框架实际产生。外层有驱动while不等于伪调度，关键是不能在驱动循环中重新实现整套业务路由。框架图文件本次下载不完整，未将其作为完整源码或已验证运行依据。
- 若S1/S2/S3不能同时成立：停止A、保留失败证据，回落`pydantic-graph`节点图时**必须如实标为图引擎**（不得称“PydanticAI Agent已接入”），或回到负责人改选B。

**S2边界不能过度推断**：静态源码`DeferredToolRequests`L28–100、remaining L89–100仅表明按结果ID计算剩余请求；DeferredToolResults L159–206保存待回填结果。它们不自动证明原始未知工具/畸形参数能在框架处理前完整交给Session、不提供本项目安全点持久化，也不决定外层循环归属。准入要验证完整调用/顺序、已执行集合、剩余队列及后继模型节点；不能预先断言“天然每步一次run/必然有调度缺口”，也不能由符号推定成功。

固定快照/逐文件SHA256/AST行号：`artifacts/runtime-source-review-20261021/source-manifest.json`；共4份完整文件（以上3份及slim pyproject），只读下载/解析，没有安装、import或执行外部代码。GitHub页面/网页工具可能折叠空行，以上行号以带SHA的本地完整字节为准；不完整的_agent_graph下载明确排除。

## 5. 契约与兼容（仅批准后实施，版本号在实施时按当时最大值复核）

下表“现状”列均为工作区固定源码事实；“候选”列未实施、未批准。版本号1.4/1.5/1.7/1.10仅为候选，实施日按当时目录最大值复核，**不得占用其他Proposed ADR已暂写的版本**。

| 契约/位置（固定依据） | 现状 | 拟变更（候选） | 旧值/旧文件行为 | 拒绝与缺失行为 |
| --- | --- | --- | --- | --- |
| `RuntimeBackend`（`models.py` L22） | 仅`handwritten`/`langgraph` | 增加`pydantic_ai` | 旧值与旧哈希不变 | 未知backend显式拒绝，**不回落**到handwritten |
| `AgentSpec`（`models.py` L186、L203-206） | 1.0–1.3，1.3为规划 | 候选1.4启用新backend | 1.0–1.3继续只接受旧backend，逐字可读、哈希不重写 | 旧版本带新backend→校验错误 |
| `ModelConfig` | temperature/max_tokens/tool_call_mode | **不变**；模型超时来自Session剩余时限（`session.py` L455-460） | 旧配置哈希不变 | 不为框架新增超时字段 |
| `CreateEpisodeRequest`（`schemas.py` L95） | 1.0–1.6 | 候选1.7，单次/实时流/恢复共用同一入口 | 1.0–1.6请求逐字重放；全局枚举扩展**不**使旧请求接受新backend | 旧请求+新backend→422；缺依赖→创建前配置错误 |
| `CreateExperimentRequest`（`schemas.py` L151-153） | 1.0–1.9；runtime轴右侧由`service.py` L1006-1020硬编码handwritten→langgraph | 候选1.10，新增**显式右侧目标**字段，仅≥1.10生效 | ≤1.9保持原硬编码语义与默认；原LangGraph趋势线不改 | 新backend仅在显式目标中允许；缺字段不得猜默认 |
| `create_experiment_plan`轴校验（`experiment.py` L443-449） | runtime轴强制handwritten/langgraph | 增加显式目标组合校验，不自动接受新组合 | 旧组合与原错误信息保持 | 其他轴两侧backend仍须相同 |
| `ExperimentCheckpoint`（`experiment.py` L287、L299-304） | 1.0–1.4，`plan_hash`覆盖全部冻结字段 | 候选1.5，记录框架精确版本与adapter版本 | 旧checkpoint按自身版本`verify()`重算逐字一致 | 版本不足却含新backend→拒绝；已完成Episode不重跑 |
| `ExperimentArtifact`（`experiment.py` L163-167） | 1.6（仅planning轴） | 候选1.7，记录框架/adapter版本来源 | 1.0–1.6按自身版本读取，1.6仍限planning轴 | 新backend写入旧版本→拒绝 |
| `RunConfig.runtime_version`（`models.py` L251；`factory.py` L21-23） | LangGraph取`version("langgraph")`，否则`reference-v2` | 新backend取实际distribution元数据（slim查`pydantic-ai-slim`） | 旧两backend取值字符串不变 | 缺依赖时**不得**伪造`reference-v2`或空串 |
| `comparison_key`（`service.py` L1177；`regression.py` fixed_config） | 现有fixed_config包含backend但**不包含runtime_version/Adapter版本**，用于跨代码版本固定回归；因此不会自动按框架版本分曲线 | 若新产物要求按SDK/Adapter版本隔离趋势，必须为新Schema明确增加带双方版本来源的key规则；不能声称无需新逻辑，也不能修改旧key或破坏跨版本回归比较 | 旧曲线/22格固定回归保持；新key与恢复来源校验分别定义 | 新要求的版本缺失保持未知/不可比，不能补当前安装值 |
| 固定回归preflight（`run_regression.py` L32-79，其中L63-68） | 四套manifest硬编码baseline=handwritten、recovery=langgraph | 新对照另建manifest；旧manifest一字不改 | 22格旧报告只读重算，禁止重录基线 | preflight不一致→在任何模型调用前拒绝 |
| Web/CSV（`schemas.py` L184-185、`apps/web/src/apiContracts.ts`） | 已有两backend枚举与历史GET | 仅增枚举/版本展示与CSV字段 | 旧历史只GET、URL只读回读不变 | 前端不得给未知backend补默认值 |
| 恢复/失败重跑 | backend+adapter写入安全点来源 | 精确版本不匹配→拒绝恢复 | 旧安全点按原来源恢复 | 允许只读旧产物，不允许自动换手写Runtime |

若实施中发现需要改动工具说明或评分才能让框架通过，视为**方案不成立**，停下重议，不能修改任务或评分来迁就框架。

## 6. 状态、失败与恢复

- 依赖缺失/import 失败/初始化失败：**配置错误**，在创建 Episode 前拒绝，不产生半成品产物。
- 框架内部异常：映射为RUNTIME_ERROR且不重试；已完成Provider响应的真实用量须保留，未返回则未知，不伪造“一次调用用量”，不漏记异常前已发生的调用。
- 框架试图调用未注册工具或伪造 `call_id`：由现有 Validator 拒绝并沿用原终止规则。
- 安全点：backend 与 adapter 版本不匹配时拒绝恢复；跨 backend 不共享安全点；中断恢复不复活终态、不撤回已提交结果。
- 取消/暂停：沿用现有 Episode 边界语义，框架层不得吞掉取消。

## 7. 公平对照

两侧固定：同一任务版本、Seed、Repeat、模型与来源、Prompt、ToolSet、预算、恢复策略、上下文策略、批次模式；**仅 `runtime_backend` 变化**。记录不可比差异（框架版本、内部系统消息、重试策略、额外 span）。Fake 结果只证明契约一致；真实小样本需单独授权，并保留失败与全部用量。旧四套 22 格回归不重录基线，新增 pydantic_ai 契约测试单独列出。

## 8. 接入步骤与验收矩阵（批准后）

1. 锁定 `pydantic-ai-slim==<精确版本>`（见§2.1，不加Provider extras），审查 `uv.lock` 与传递依赖许可；记录安装前后体积。
2. 自定义 `Model` 桥接 `ModelProvider`，先用 Fake（slim未含内置测试模型时自写Fake Model）跑通单步。
3. Contract Test：正常调用、非法参数一次纠错、未知/禁止工具、重复 `call_id`、第二次参数错、超时、预算、single/serial、安全点恢复、未知用量。
4. 与 `handwritten`/`langgraph` 跑同任务 Fake 对照（成功、终止原因、事件序列、Token/费用、耗时）。
5. 单次 API/Web 入口显示实际 backend 与框架版本；历史只 GET；CSV 记录版本。
6. 完整门禁 `uv --cache-dir .uv-cache run --locked python -m scripts.check`；本机 Edge 设 `AGENTLABYRINTH_E2E_CHANNEL=msedge`。
7. 真实单对探索仅在另行明确授权后执行，不能沿用已耗尽的一次性授权。

### 8.1 准入断言（全部Fake可判，**已在隔离环境执行，见§11.2**）

| 编号 | 断言 | 通过标准 | 复用/新增 |
| --- | --- | --- | --- |
| A-01 | 框架真实调度 | 至少一次多轮Episode中，模型→完整提议/统一校验→工具反馈→下一模型节点及终止的转移由框架驱动；禁止将Adapter复刻循环包装为Runtime。驱动循环可消费框架节点，不以有无while或一次入口节点转移判定 | 单独Fake观察节点来源/后继与实际Provider、工具调用；不将诊断当统一Trace |
| A-02 | Provider调用一次 | 正常返回轮次请求/响应各一次，无隐式重试；Provider超时/抛错且未返回时允许只有MODEL_REQUESTED，保留未知用量/终止，**不能为一一对应补MODEL_RESPONDED** | `tests/contract/test_execution_time.py`已明确超时无响应事件，复用并增加调用计数 |
| A-03 | 整批末项非法→零执行 | serial批次任一项非法时，`TOOL_STARTED`/`ENVIRONMENT_UPDATED`计数为0，终局为`batch_rejected`或仅一次纠错 | `tests/integration/test_tool_batches.py` L66/L104/L180 |
| A-04 | Call ID不被改写 | 保存Trace的call_id与提议完全一致；重复ID/未知/禁止工具仍由`session.py` L557-574/L624-652终止 | `tests/integration/test_tool_batches.py` L381 + 新增ID集合比对 |
| A-05 | 提交后不多调模型 | `submit_answer`成功即`SUCCESS/submitted`，`model_call_count`不再增长；无“总结”请求 | `test_execution_time.py` L140/L166 + 新增计数断言 |
| A-06 | 未知用量保持未知 | Provider未报告时`token_usage`不补零；框架内部usage=0不得覆盖原始未知 | `test_execution_time.py` L118/L102 + 新增Fake未报告用例 |
| A-07 | 单调用/serial新进程恢复 | 中途退出→新进程`restore`→剩余队列与已执行ID来自`SessionState`，零重复；`next_node`映射与L207-232一致 | `tests/integration/test_checkpoint_resume.py` L86 |
| A-08 | 旧产物只读兼容 | 四套旧manifest及22格报告只读重算逐值一致；旧Agent/请求/产物拒绝新backend；旧哈希不变 | `scripts/run_regression.py` preflight + §5门控测试 |
| A-09 | Trace等价三方对照 | 同一任务Fake下handwritten/langgraph/pydantic_ai事件类型与顺序可逐条解释，无伪造事件；仅backend一个变量 | 新增对照脚本，复用现有`ExperimentArtifact`/CSV |
| A-10 | 缺依赖fail-closed | 未安装/import失败时，创建Episode在**任何模型调用前**报配置错误；历史只读解析仍可用 | 新增1项import模拟测试 |

执行顺序以§10分阶段：先经批准在隔离环境固定依赖，复用可移植Session/Fake验证上述运行断言；不在此阶段向生产枚举/请求增加backend或改主锁。验证报告单独标“技术准入”，不冒充正式runtime_backend实验、生产Episode或已支持的API。通过并确认具体成品契约后，才扩主项目新backend参数化/API/恢复测试与完整门禁。不复制模拟Runtime，不把SDK TestModel代替项目Fake的业务契约证明。

## 9. 成本与回滚

- 成本：新增一个运行时依赖及其传递依赖；单 Episode 不增加模型调用；adapter 维护成本与框架版本漂移需记录。
- 回退启用：关闭新建入口；保留新旧保存Schema解析与来源校验，不能删除枚举后又承诺含该backend的新产物可读。恢复新backend必须有对应精确依赖/Adapter，缺失时明确拒绝恢复但允许只读产物；不能自动换成手写Runtime。移除依赖前需单独处理活动任务/安全点，不自动迁移或删除数据。

## 10. 决策结果（2026-10-21 负责人已确认，已执行）

负责人确认三项，本节由“待确认”转为决策记录：

1. **A1限定＝接受**：框架负责单步内节点转移（`ModelRequestNode→CallToolsNode→End`），步间推进由 adapter 消费 Session 返回值完成。该缺口必须写入成品说明与对照差异，不作为需求 §8.5 第三调度实现的完成证据。
2. **安装范围＝装入项目锁**：`pydantic-ai-slim==2.57.0`、不加Provider extras；锁差异/许可/体积在安装时审查；不改现有核心依赖版本。
3. **成品契约＝按候选一次性定案**：`RuntimeBackend+pydantic_ai`、AgentSpec 1.4、Episode请求 1.7、Experiment请求 1.10（含显式`runtime_target`）、ExperimentCheckpoint 1.5、ExperimentArtifact 1.7；随后完成单次API/Web入口、正式`runtime_backend`对照、保存恢复、CSV与完整`scripts.check`。

真实模型调用仍需**另行**明确授权；本轮全部证据为 Fake。

## 11. Codex复核：先补齐的设计准入（尚未验证）

官方[Agent节点迭代](https://pydantic.dev/docs/ai/core-concepts/agent/#iterating-over-an-agents-graph)和[Model.request接口](https://pydantic.dev/docs/ai/api/models/base/)提供可能的接缝；它们是API存在的依据，不是本项目适配成功的证据。当前在线文档可能对应较新版本，实施前必须对照选定tag/发布源码，记录文件/符号/固定链接。

Trae下一次提交需给一张明确的调用表，逐步说明谁调度、谁真实调用Provider、谁预检整批、谁执行一个工具、谁写统一事件/预算/安全点，避免框架loop与Session.call_model各调用一次。候选为Agent.iter/next按节点控制+自定义Model桥接；必须证明框架实际决定循环转移，不能只是外包一层或只用pydantic-graph却声称PydanticAI Agent已接入。不得调用HandwrittenRuntime.run来完成真实执行。

准入须明确：

1. 在CallToolsNode或同等边界**任何工具开始前**取得完整原始调用并调用Session同一预检；框架自行参数修复/输出修复/重试不能先改写或吞掉未知工具/无效参数/重复Call ID。仅工具函数内部再次校验不等价于完整整批预检。
2. `submit_answer`实际完成即结束，不让框架再补一次模型“总结”；计划/记忆投影和消息映射不重复注入系统提示、遗漏工具返回或自动修复历史；实际Provider消息/模型请求次数可核对。
3. 对single/serial与批次一项完成后的新进程恢复给具体状态映射；所有已执行ID/剩余项来自保存Session，不依赖未保存的框架内存，异常/保存失败不吞没。说明框架自有历史如何无重做地重建，不能仅写“同LangGraph”。
4. 明确只存在一个统一Trace/预算来源和一份原始用量；框架内部Usage为0时原Provider未知仍保持未知。所有额外实际调用计入，不以关闭日志来隐藏它们。
5. 在§5补全新建/读取/恢复/重跑/旧请求拒绝新值的版本矩阵、右侧backend选择与默认、依赖/Adapter版本记录、未知backend/缺依赖拒绝，以及UI/CSV/固定配置历史隔离。1.4/1.10/1.7仅候选，不占用仍在Proposed的Reflection版本，审批时按实际目录复核。

本次二次复核将审批收敛到§10的隔离Fake准入；尚未定案的成品字段/来源规则不跟随试验被自动批准。未批准前不安装/编码/调用模型。关键接缝不成立时给出最小失败和备选，不削弱边界强行接入；准入通过后仍须定案并完成普通API/Web/正式对照/恢复与完整门禁，不能止于框架demo。已批准范围内普通实现/检查无需反复询问。

### 11.1 本轮补齐对照（仍为设计，**未安装/未验证**）

| Codex要求 | 本轮落点 |
| --- | --- |
| 调用表：谁调度/谁调Provider/谁预检/谁执行/谁写事件预算安全点 | §4.1（12行，含`session.py`与`langgraph/adapter.py`固定行号）+ §4.1.1接缝S1/S2/S3与失败判定 |
| 框架必须实际决定转移，不得只外包一层 | §4.1 #11 + §4.1.1 S3 + §8.1 A-01；做不到时记“调度缺口”，见§3与§10结尾 |
| 任何工具开始前完成整批预检 | §4.1 #8（`session.py` L605-677）+ §8.1 A-03/A-04 |
| `submit_answer`后不得再补总结调用 | §4.1 #6/#11（L757-759）+ §8.1 A-05 |
| 计划/记忆投影与消息映射不重复注入 | §4.1 #2/#10 + §5（`ModelConfig`不变、框架消息不入`SessionState`） |
| single/serial与新进程恢复的状态映射 | §4.1 #9/#10/§6 + §8.1 A-07（`test_checkpoint_resume.py` L86） |
| 单一Trace/预算/用量来源，未知不补零 | §4.1 #3/#4/#5 + §8.1 A-02/A-06 |
| 版本矩阵、右侧backend、依赖/Adapter版本、缺依赖拒绝、UI/CSV历史隔离 | §2.1 + §5全表（13行，均带固定源码位置）+ §8.1 A-08/A-10 |

已完成（只读）：固定tag `v2.57.0` 的[`_deferred.py`](https://github.com/pydantic/pydantic-ai/blob/v2.57.0/pydantic_ai_slim/pydantic_ai/_deferred.py)/[`tools.py`](https://github.com/pydantic/pydantic-ai/blob/v2.57.0/pydantic_ai_slim/pydantic_ai/tools.py)符号核对，链接与日期见§4.1.1。

Codex二次复核已补完Model.request/Agent.iter与DeferredToolRequests的完整固定源码定位及SHA256，见§4.1.1；无需再把方法位置留待安装日。原11.1对照表是设计意图映射，验收以上文修正的A-01/A-02/指纹规则为准。**实际运行准入已完成并在§11.2如实报告（含调度缺口）**；仍未完成：安装到项目锁文件、许可全量审查、成品契约定案与API/Web/对照/恢复交付。

## 11.2 隔离Fake准入运行结果（2026-10-21，已执行）

**环境**：`uv run --cache-dir .uv-cache --frozen --with pydantic-ai-slim==2.57.0`（临时overlay，Python 3.12.14，distribution `pydantic-ai-slim` 2.57.0）；项目`pyproject.toml`/`uv.lock`未改，未安装进项目环境，未调用真实模型。

**直接依赖（安装后由元数据实读，非推测）**：`anyio>=4.7.0`、`genai-prices>=0.1.13`、`griffelib>=2.0`、`httpx2>=2.7`、`opentelemetry-api>=1.28.0`、`pydantic-graph==2.57.0`、`pydantic>=2.12`、`typing-inspection>=0.4.0`。与项目现有`pydantic 2.13.5`、`anyio 4.15.1`无冲突；新增面为`httpx2`/`griffelib`/`genai-prices`/`opentelemetry-api`/`pydantic-graph`。注意：OTel是**基础依赖**（API层），未安装exporter、未发现强制外联；因此“零追踪依赖”的原表述不成立，应写“默认无外联上报”。

**脚本与报告**（spike为验证脚本，**不是产品代码**）：`artifacts/runtime-admission-20261021/spike.py`、`report.json`。所有断言Fake可判，Session仍是唯一Provider调用/校验/预算/Trace/安全点来源。

| 场景 | 实际结果 |
| --- | --- |
| success | `SUCCESS/submitted`，2模型调用/2工具，事件序列完整 |
| 一次参数纠错 | `runtime_strategy=handwritten_recovery`下3模型调用后成功 |
| 第二次参数错 | `FAILED/invalid_arguments: INVALID_ARGUMENTS`，0工具执行 |
| 未注册/禁止工具 | `FAILED/unknown_tool`，1次模型调用，无框架补请求 |
| 仅FinalAnswer | `FAILED/missing_submission` |
| 未报告用量 | 两次`MODEL_RESPONDED`用量均为`null`，未被框架0覆盖 |
| 超时 | `TIME_BUDGET_EXCEEDED`，1次调用、0次`MODEL_RESPONDED`、0工具 |
| 步数预算 | `MAX_STEPS`，2模型调用、2工具 |
| serial批次末项非法 | `FAILED/batch_rejected: UNKNOWN_TOOL`，`TOOL_STARTED=0`，提议名称原样保留 |
| 批次内重复ID | 框架先抛`UnexpectedModelBehavior`，adapter捕获后仍由Session `validate()`裁决为`batch_rejected: DUPLICATE_CALL_ID`，`TOOL_STARTED=0` |
| serial正常批次 | `SUCCESS`，`call_batch_1`/`call_batch_2`/`call_submit_2`各执行一次 |
| 新进程恢复 | 首项完成后`os._exit`；新进程从`next_node=execute`+`pending=[call_batch_2]`继续，`SUCCESS`，无重复ID，`EPISODE_RESUMED`/`EPISODE_FINISHED`各1 |

断言24/24通过（A-01…A-10的运行项；A-08旧22格只读基线沿用Codex复核，A-09三方对照与A-10缺依赖拒绝属成品阶段）。

**必须报告的缺口与框架行为**：

1. **调度缺口（关键）**：每次模型步是一次独立`Agent.iter`运行，节点为`UserPromptNode → ModelRequestNode → CallToolsNode → End`；**步与步之间由adapter按Session返回值推进**，外层仍有adapter循环。按§3与§4.1.1定义属于“A1限定”，不能称“框架驱动整个循环”，也不能当作需求§8.5第三调度实现的证据。
2. **未注册工具名的处理权在桥接层**：deferred下框架对未注册名会自行再请求模型；准入脚本先按`Session._available_tools()`过滤才使模型调用保持1次。属adapter映射职责，不宣称Session原生拦截框架再请求。
3. **重复ID由框架先预占**：框架在校验前抛错，adapter必须捕获后交回Session裁决，否则终止原因会由框架决定。该路径已验证，但是**额外映射要求**。
4. **超时链路**：Session在`asyncio.timeout`内取消Provider调用，框架侧收到Session返回`end`而非异常；已验证不补发响应事件。
5. **依赖结论有限**：只证明该overlay组合可运行，不等于项目锁文件可无冲突升级；锁差异与许可全量清单仍需批准后安装时审查。

**结论**：机制层（单次调用、整批预检、ID不改写、提交后不再调用、未知用量不补零、serial逐项与新进程恢复、超时不造响应）在Fake下成立；独立调度**未完整成立**。本ADR仍为Proposed，产品化前须由负责人先决定“A1限定是否可接受”。

## 12. 成品化实施记录（2026-10-21，负责人三项确认后执行）

### 12.1 依赖与锁

- `pyproject.toml` 新增 `"pydantic-ai-slim==2.57.0"`（无Provider extras），`uv lock --cache-dir .uv-cache --offline` 重算；`uv sync --frozen --offline` 通过，运行时实读 `pydantic-ai-slim` 2.57.0 且 `pydantic_graph` 可导入。
- 锁差异：`pyproject.toml +1`、`uv.lock +67/-0`，新增5个分发 `pydantic-ai-slim`、`pydantic-graph`、`genai-prices`、`griffelib`、`logfire-api`；**无任何既有条目版本改动**。许可均为MIT/BSD/Apache族，无新增运行时exporter依赖。

### 12.2 适配器（`packages/runtime/pydantic_ai/`）

- `adapter.py`：框架类型只在本包出现；`_SessionBridgeModel(Model)` 使**一次框架模型请求 = 一次 `EpisodeSession.call_model()`**；`request()` 在Session返回非`validate`时直接以文本结束本次框架运行，只有`validate`分支才把Session已裁决的调用映射为`ToolCallPart`。
- 未注册工具名在桥接层先按 `session.available_tools()` 判断：命中不上则不产出工具调用，交回Session裁决，避免框架自行补请求（§11.2缺口2）；`UnexpectedModelBehavior` 等框架异常由adapter捕获，最终终止原因仍由Session `validate()` 决定（缺口3）。
- 步间推进仍由adapter循环完成（A1限定），未包装 `HandwrittenRuntime.run`，未用 `pydantic-graph` 冒充 `Agent` 接入。
- `session.py` 仅新增只读 `available_tools()`，未改调用/校验/预算/安全点逻辑。
- `factory.py` 新增 `RuntimeUnavailable`：缺分发或元数据缺失时 **fail-closed**，不回落 `handwritten`，也不伪造 `reference-v2`（A-10）。

### 12.3 契约版本（旧版本继续拒绝新值）

| 契约 | 新版本 | 门禁规则 |
| --- | --- | --- |
| `RuntimeBackend` | `+pydantic_ai` | 仅显式声明时生效 |
| AgentSpec | 1.4 | `runtime_backend=pydantic_ai` 必须是1.4 |
| CreateEpisodeRequest | 1.7 | `pydantic_ai` 单次必须是1.7；1.6仍拒绝 |
| CreateExperimentRequest | 1.10 | 仅runtime轴可用；`runtime_target` 必填；`target=handwritten` 拒绝；`runtime_backend=pydantic_ai` 一律拒绝（只能走 `runtime_target`） |
| ExperimentPlan | 1.5 | 含pydantic臂才1.5，且左臂必须`handwritten` |
| ExperimentCheckpoint | 1.5 | 同上；1.5只允许runtime轴 |
| ExperimentArtifact | 1.7 | 同上；1.7只允许runtime轴 |

旧轴/full语义/评分/恢复未改；`reference-v2` 仍为 `handwritten` 的版本指纹，`langgraph` 仍读自身分发版本。

### 12.4 测试扩展与结果

- `tests/contract/test_execution_time.py`、`tests/integration/test_tool_batches.py`、`tests/integration/test_checkpoint_resume.py` 参数化加入 `pydantic_ai`；`tests/contract/test_langgraph_runtime_adapter.py` 新增 `test_pydantic_ai_matches_reference`（原生任务三方等价）与 `test_missing_third_runtime_dependency_fails_closed`（A-10，断言 `provider._call_count == 0`）。
- `tests/unit/test_api.py` 新增 `test_third_runtime_requires_its_additive_revisions`（1.8遗留请求右侧仍LangGraph且experiment 1.2；1.10+`runtime_target=pydantic_ai` → experiment 1.7、右侧`pydantic_ai`、Episode agent 1.4、`runtime_version=pydantic-ai-slim-2.57.0`；非法组合422）。
- 实际结果：Python `624 passed`（忽略e2e，159.75s）、`ruff format --check`/`ruff check`/`mypy`（113 files）通过、4套回归退出0、Web `typecheck`/`build` 通过、网页单测44/44、Edge e2e 61/61。
- 真实模型**未运行**；A-08旧22格基线未重录（沿用只读复核）。

### 12.5 遗留与边界

1. A1调度缺口照旧：不得把本实现写成“框架驱动整轮循环”或需求§8.5第三调度已完成的证据。
2. Judge/人工复核与Reflection仍分别需要具体ADR/授权。

### 12.6 真实模型限定一对（2026-10-22负责人授权）

负责人批准一道真实样本后执行：`coding-minimax-m2.7-free` × `order-status-001`，左 `handwritten`/1.1、右 `pydantic_ai`/1.4，请求 1.10、`runtime_target=pydantic_ai`，实验 `db7ee2c4-98e5-4c31-b350-24e628638b46`（产物 1.7）。

- 两臂均 `SUCCESS`，Step 2/2、模型调用 2、工具调用 2、报告 Token 2790（2692+98）完全一致；右臂 `runtime_version=pydantic-ai-slim-2.57.0`，左臂 `reference-v2`。
- 两侧 Trace 均为 17 个事件且序列逐项相同，**无框架额外模型请求**，真实 Provider 下“一次框架模型请求＝一次 `Session.call_model()`”成立。
- 耗时左 18895 ms、右 23964 ms（单次，不作性能结论）。共 4 次模型请求，无重试、无补跑、无模型替换。
- 明细见 `docs/learning/V0.3-real-runtime-pair-20261022.md`；脚本 `artifacts/real-runtime-pair-20261022/run_pair.py`。该证据只说明单对该模型该题可用，不改变 A1 缺口，也不构成需求 §8.5 完成。
