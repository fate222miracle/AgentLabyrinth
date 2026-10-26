# ADR-035：规划组件与 Planning Challenge

状态：**Accepted，2026-10-19**。负责人已确认本方案的四项取舍（详见 §10）：机制=方案B（只读声明工具 `update_plan`）、新增 `planning_challenge` 最小实例、首个对照两侧固定 `full` 上下文、`update_plan` 作 `READ_ONLY` 允许进入 serial 批次。按根 `AGENTS.md`，新核心协议经负责人一次确认具体方案后实施。入口：[交接](../handoffs/trae-20261019.md)、[执行卡](../tasks/V0.3-planning-trae-20261019.md)。依据需求 V0.6 §0.3/§19。不提交 GitHub。§1–§9 为定案设计，实现状态与实测以 §10、current-state 和学习交接为准。

## 1. 从现有代码与真实证据发现的问题

分两层，先把“规划缺口”与“记忆/上下文缺失”分开，避免错误归因：

- **现有代码**：`packages/domain/models.py` 的 `AgentSpec`（1.0–1.2）只有 model/prompt/tool_set/runtime/budget/context_policy；不存在任何 planning 字段、plan 事件或 plan 工具（`Grep planning|update_plan|PLAN_UPDATED|subgoal` 仅命中 `tests/unit/test_tool_lab_suite.py` 的一个计数字符串）。`packages/runtime/session.py` 的循环是 observe→model→validate→execute，模型可见输入只有初始 system/user 与工具轮次（`session.py#L294-L313`）。
- **现有任务结构**：`order-status-*`（单记录查询）、`long_chain/*`（线性 `Next document` 链，末端 `Status` 即答案，见 `return-evidence-chain-001.json`）、`memory_challenge/*`（三事实规则，Fake 用“缺哪条事实就读其引用”推进，见 `fake.py#L193-L330`）。它们检验检索、证据完整与记忆，但**没有“复合目标需自行拆成子目标并跟踪完成”的结构**：线性链读到末端即得答案，agent 无需自持进度。
- **真实证据**（experiment `9626ea36-60c1-431a-b742-8e0c368982a1`）：左侧无记忆臂 `TOKEN_BUDGET_EXCEEDED`、8/10 工具、9 成功读/6 重复读/21897 Token；右侧有记忆臂 SUCCESS、5/7 工具、3/0 重复读/14840 Token。**该失败与重复读可由记忆/上下文差异解释**（右臂记忆把重复读降为 0），**不能归因为缺少规划**。
- **结论**：N1 无记忆失败**不能**证明“缺 Planning”。因此首个规划对照必须固定两侧上下文/记忆等变量，只改规划组件；并且在现有任务上先确认是否存在“信息已可得但子目标遗漏/依赖顺序错/完成误判/不必要重复”的真实迹象——经核对，现有任务不提供该结构，故需**最小**新增任务（§5），而非人为拉长工具链。

## 2. 候选方案与选择（机制）

- 方案A（**不选**）：在 `ModelResponse` 增加结构化 `plan_update` 字段。真实 OpenAI 风格 Provider 无法稳定产出该字段，需改 Provider 解析与响应契约，代价大且偏离既有工具路径。
- **方案B（选定）**：保留只读声明工具 `update_plan`，经现有 Registry/Validator/Executor 与 single/serial 路径；计划由 Session 保存为“Agent 声明”，每轮以保留封装 `_agentlabyrinth_plan` 注入 Provider 输入；结构严格校验。`update_plan` 作 `READ_ONLY`，允许进入 serial 只读批次。
- 方案C（**未选，保留记录**）：循环前单次确定性规划调用（observation 后固定一次额外模型调用）产出初始计划，额外调用全额计费。更贴近“规划阶段”的研究直觉，但改写两 Runtime 循环形状、必然增加一次固定调用，恢复与公平对照更复杂。

选择理由：方案B 不改变循环形状、不新增 Provider 能力要求、复用既有权限/预算/校验/事件路径，最贴合“先建立可解释的失败/成功条件”。

本切片**不引入**摘要、向量库、数据库、多 Agent 或新 Runtime；**不改** `project_context`、记忆准入或旧评分。

## 3. 规划组件契约

- **定位**：计划是模型可见的**高层可执行子目标/约束的结构化声明**，不是私有思维链。只保存必要的计划摘要与行动依据；不要求、也不伪造隐藏推理文本。计划项文本不得包含或暗示任务私有答案，不得按任务 ID 硬编码执行顺序。
- **计划项 `PlanItem`（新 Contract）**：`id`（短标识）、`goal`（有界短文本）、`status`（`pending`/`active`/`done`/`cancelled`）、`depends_on`（同计划内其它 id）。有界：项数 1–8；`id` ≤ 32 字符；`goal` ≤ 200 字符；`depends_on` ≤ 8 且须引用**同计划内** id；无环。
- **语义**：**创建/更新** = 一次 `update_plan` 调用提交整份计划（幂等替换）；**完成/取消** = 用新一次 `update_plan` 把对应项置为 `done`/`cancelled`。由被测模型在循环中按需产生；Runtime 不代替模型写计划。
- **保存/注入**：`update_plan` 经正常 validate/execute 路径，append `PLAN_UPDATED` 事件；Session 持有当前计划，并在每轮 `project_context` 投影**之后**以保留封装 `_agentlabyrinth_plan` 追加注入，保证 `recent_tool_rounds` 下计划仍可见；计划同时写入 `SessionState` 供恢复。**不改 `project_context` 本体**（不触碰旧哈希与旧逻辑）。
- **核验原则**：计划是 Agent 声明；**计划自称的 `done` 永不替代环境提交与独立 Evaluator 的真实完成**。产品与离线分析展示“计划声明”与“已到达事件”的对应/背离，不把计划当已执行。

## 4. 公平对照与实验轴

- 新配对轴 `planning`（沿用既有 Experiment 机制，与 `memory_ablation` 同构）。
- 两侧固定：任务、模型（provider/model）、`prompt_version`/`tool_set_version`、Runtime 后端与版本、恢复策略与纠错、Seed、预算、**上下文策略一致**（本首个对照**两侧同为 `full`**）；**唯一变化 = 规划组件**：左 = 无 `update_plan` 工具且不注入计划；右 = 可用 `update_plan` 且注入计划。Agent 差异仅 `planning` 字段与身份（`id`/`name`）。
- 额外规划调用与 Token 全部计入规划侧自身预算；**不给规划侧更高预算、不另送免费调用、不加额外记忆容量**。总预算中止、未知用量、失败结果照旧真实保存。

## 5. 任务选择

- **先复用**：`long_chain`（线性链）与 `memory_challenge`（三事实规则）用于回归与对照可行性检查，但不作为“规划必要”的证据。
- **需最小新增**：一个**复合目标需自行拆分并跟踪完成**的任务族 `benchmarks/tool_lab_core/tasks/planning_challenge/`，与既有 `document_rule` **同一业务规则与评分口径**（避免新增评分逻辑）。差异仅在：任务描述给出**复合完成条件**（须同时满足 a/b/c），而**初始观察不含子目标清单或跳转表**，路线分散在分支文档中，模型须自行枚举子目标并保持不遗漏。不人为拉长工具链，不强制固定调用次数。
  - 拟 `planning-branch-001`：复合规则任务，答案需综合两条独立分支（如分类分支 + 政策分支），且政策分支的适用性依赖分类分支读到的分类事实（形成依赖顺序）；完成需两侧证据齐全。
  - 备选 `planning-omit-002`：设置“看似可先提交、实则遗漏分支”的诱因，观察完成误判/子目标遗漏。
  - 两题只作本机制的可解释样本，第一版各一实例；不据此宣布泛化成功率。
- **任务协议**：新 `task_kind=document_plan`；`TaskSpec` schema 1.0 复用；`evaluator_config` 复用 `name=order_status_v2`/`evidence_order=unordered-v1`，新增 `planning_protocol=plan-update-v1`、来源 `origin=native_planning_challenge`、`dataset_version=planning-challenge-v1`。环境 `_Snapshot`/`restore` **不变**（计划在 Session，不在环境状态）。
- **Fake 参考实现**：新 `document_plan` 分支只依据当前请求**公开可见**的观察、工具反馈与计划包推进；按公开规则与依赖顺序收集分支，不读私有 `goal_conditions`、不按任务 ID/调用次数选择答案。实现前用两种相反数值结果、任务/文档 ID 重命名、答案故意改错等反事实验证。旧任务 Fake 固定基线保持。

## 6. 状态、校验与失败路径

- **结构严格校验（fail closed）**：未知/重复 `id`、超过项数上限、`depends_on` 引用不存在或成环、`status` 非法、超出长度 → 拒绝并记 `TOOL_FAILED`/终止码，**不静默修正**。
- **边界沿用**：TimeoutError、`MISSING_TOKEN_USAGE` 等沿用既有边界（缺用量不补零）；**不扩大**工具纠错范围（`update_plan` 参数错误仍遵循“最多纠正一次”，未知/禁止/重复 ID/第二次参数错不重试）。
- **保存/中断**：计划随 `SessionState` 保存；保存失败 raise `CheckpointFailure`；恢复时校验计划与任务执行变体一致（§7）。
- **完成语义**：计划声明**不**触发环境 `done`；只有真实 `submit_answer` 成功才 `done`。

## 7. 契约版本与兼容

| 契约 | 变更 | 旧默认/兼容 |
| --- | --- | --- |
| `AgentSpec` | 新增 `"1.3"`，新字段 `planning: PlanningConfig \| None` | 旧 1.0–1.2 无该字段；`planning=None` 时序列化 pop，旧哈希不变 |
| `PlanningConfig`（新） | `schema_version="1.0"`、`algorithm_version="plan-update-v1"` | 仅规划实验使用；未使用即等同旧行为。计划项上界由工具 schema 固定为 8，总调用/Token 由既有预算约束 |
| `EventType` | 新增 `PLAN_UPDATED` | 旧事件不变；旧产物无该事件 |
| `SessionState` | 新增 `"1.2"`，新字段 `plan` | `plan=()` 时 pop，保留 1.0/1.1 字节；含 plan 需 1.2 |
| ToolSet | 新增 `v1.6.0`（注册 `update_plan`） | v1.0–v1.5 行为/说明保持；旧请求/产物/恢复按**保存版本**，不按新目录重选 |
| `CreateEpisodeRequest` | 新增 `1.6` | `planning` 需 1.6；旧 1.0–1.5 语义与校验不变 |
| `CreateExperimentRequest` | 新增 `1.9`；`comparison_axis` 增 `planning` | 旧轴默认/校验不变；planning 需 1.9 |
| `ExperimentCheckpoint` | 新增 `"1.4"` | 旧 1.0–1.3 保持；planning 轴需 1.4 |
| `ExperimentArtifact` | 新增 `"1.6"` | 旧 1.0–1.5 保持；planning 轴需 1.6 |
| `comparison_key`/CSV/回归 | 新轴标签 | 未知指标不补零；旧键/旧回归/旧恢复不变；`scripts/run_regression.py` preflight 增 planning 派生 |

**不松开旧版本验证器**：以上均为“新增版本 + 新字段门控”，旧版本解析/序列化/哈希/冻结来源**逐字保持**。特别保留“**先派生任务，再选工具版本**”（ADR-034 教训）：含 planning 的任务/实验在创建时冻结 `v1.6.0`，恢复时按保存版本，不按最新目录重选。

## 8. 适配与 UI

- **手写与 LangGraph**：共用 Session 的 `update_plan` 校验/记录/注入机制；LangGraph 适配层仅接同一 Session 状态与事件，不各写一套规划器。
- **本地/MCP**：沿用原执行边界；`update_plan` 为本地声明工具（是否经 MCP 传输按既有范围策略决定），不新增 MCP 契约。
- **Web**：复用现有配置/运行/实时 SSE/资料侧栏/对照面板/CSV；新增“计划 vs 已执行”只读区分（计划来源 = 声明，执行来源 = 已到达事件），正常页**不展示虚构思维链**；刷新/前进/后退只 GET、仅显式运行 POST；历史草稿隔离。尽量复用现有控件/画布，不新建长侧栏或渲染框架。

## 9. 验收矩阵

- Fake 只验证控制逻辑；两 Runtime；single/serial；checkpoint/resume **不重做**已完成工具；旧 context/请求/任务/产物/冻结计划/安全点可读且哈希保持；BFCL 维持独立单函数评分。
- 有/无规划两侧固定变量：额外调用成本、未知用量、全局预算中止及失败结果真实保存，**不给规划侧更高预算**。
- 无目标/答案泄漏；不强迫固定调用次数；计划非已执行、仅展示已到达事件。
- API/Web 类型与事件边界；四视口 1440/1280/768/390、键盘、动态减少动效、中文说明与实际输出；CSV 可读、未知指标不补零。
- 真实模型验证另定**一模型/一任务/固定两侧与预算**，不自动重试/换模型/批量 Seed×Repeat，保留所有失败。

## 10. 成本、回滚与待决定项

- **成本**：规划侧多出的调用/Token 计入自身预算；total/全局阈值机制不变。
- **回滚**：`planning` 为可选字段，未使用即等同旧行为；旧产物/恢复不受影响。
- **负责人已确认的四项决定（2026-10-19）**：
  1. 机制：**方案B**（`update_plan` 工具，经既有 Registry/Validator/Executor），不采用方案C。
  2. 任务：**同意新增** `planning_challenge/` 最小实例（`planning-branch-001`，含分支依赖；`planning-omit-002` 视需要）。
  3. `update_plan` 作 **`READ_ONLY`**，**允许**进入 serial 只读批次。
  4. 首个规划对照两侧固定 **`full`** 上下文。
- **实现状态**：**已实施并通过完整门禁（2026-10-19）**；真实模型验证未跑，见 §9。

## 11. 实现与验证记录

**状态**：Accepted 并实施完成；完整门禁退出 0。

**修改/新增文件**：

- `packages/domain/models.py`：`PlanItem`、`PlanningConfig`（`1.0`/`plan-update-v1`），`AgentSpec`→`1.3` + `planning`，`EventType.PLAN_UPDATED`；`planning=None` 时序列化 pop。
- `packages/runtime/session.py`：`PLANNING_TOOL="update_plan"`；`SessionState`→`1.2` + `plan`（空时 pop）；`checkpoint/restore` 版本阶梯与规划一致性；每轮投影后注入 `_agentlabyrinth_plan`；`_available_tools/_allowed_tools` 对组件工具的暴露门控；执行成功回写计划并记 `PLAN_UPDATED`。
- `packages/environments/tool_lab/environment.py`：ToolSet`v1.6.0`（`_planning_tool`），`UpdatePlanArgs`（严格校验，无环 DFS），注册 `update_plan`（`READ_ONLY`、`1.0.0`），`reset()` 追加为组件允许工具。
- `packages/providers/fake.py`：`document_plan` 分支；`_plan_visible` 只看保留封装；`_plan_response` 只产生一次两项声明（`facts`→`decide` 依赖）；旧任务基线不动。
- `packages/application/experiment.py`：轴 `planning`、`_validate_planning_agents`、`arm_labels`、plan 1.4/artifact 1.6/checkpoint 1.4 与 Exclusivity 校验。
- `apps/api/schemas.py`/`service.py`：Episode`1.6`、Experiment`1.9` 与轴门控；`_task_tool_version`→`v1.6.0`（先派生任务再选版本）；两侧 `full` 对照构建。
- `packages/evaluation/order_status.py`：对 `plan-update-v1` 任务从 proposed **与 validated** 事件排除 `update_plan`（修 `*_validity_rate>1`）。
- `scripts/run_regression.py`：`planning` 派生与工具档位前置校验。
- 新任务 `benchmarks/tool_lab_core/tasks/planning_challenge/planning-branch-001.json`。
- Web：`apiContracts.ts`（planning 契约/事件/1.6 校验）、`App.tsx`（轴入口/标签/CSV 列 `planning_algorithm_version`）、`PlanningPairReview.tsx`、`ExperimentCharts.tsx`/`ExperimentDashboard.tsx`。
- 测试：`tests/integration/test_planning_experiment.py`（13）、`apps/web/e2e/planningChallenge.spec.ts`（2）、`apps/web/tests/apiContracts.test.mjs`（+2）、计数守卫更新。

**命令与结果**：

- 门禁：`$env:AGENTLABYRINTH_E2E_CHANNEL='msedge'; uv --cache-dir .uv-cache run --locked python -m scripts.check` → 退出 0；**526 Python / 91.92s、Ruff+mypy 110、Web 类型/构建/Node、Edge 57/57（2.5m）**；质量产物 `artifacts/quality/19b0b511-6342-468f-9fe1-c992c207e8f7/`。

**闭环证据**：两 Runtime（handwritten/langgraph）规划矩阵两侧均 SUCCESS、无恢复指标；计划声明仅在右臂暴露、`PLAN_UPDATED` 仅右臂；右臂 `MODEL_REQUESTED` = 左臂 +1（额外声明计入自身预算且两侧预算相等）；保存+恢复不重做已完成臂（复用原 Episode id）；全局 Token 准入按轴生效；API 1.9 接受、1.8/非规划任务/非 full 被拒。Fake 从公开观察推进，不含私有答案/任务 ID。

**兼容**：所有旧契约（ContextPolicy/请求/任务/产物/冻结计划/安全点/回归）逐字保持，新行为全部由新版本/新键门控；`fixed_config` 不含 `planning`（轴变量非公平字段）。

**未做**：真实模型验证（按 §9 另定一模型/一任务/固定两侧与预算）；不自动重试/换模型/批量 Seed×Repeat。本轮无 Git 提交/推送。

## 12. 2026-10-20 Codex复核修正

负责人要求验收Trae交付。原交付主链路已实现，但发现计划安全点未绑定实际成功声明、保存Experiment未要求右侧组件、单次UI缺规划开关/实时声明、基线任务要求不可用工具、混合工具档位与声明请求诊断/安全指标遗漏；已在原边界修复。问题、复现、最终门禁和未验收项见[复核记录](../tasks/V0.3-planning-review-20261020.md)，不能再把原526/57视为最终验收。

补充原定案的实现细节：任务元数据新增可缺省的supports_planning（由已保存任务协议派生，旧元数据缺失视为不支持）；单次显式启用走既有请求1.6，旧默认不改。计划图校验在Domain共享，安全点须匹配提议/权限、成功工具返回/消息与PLAN_UPDATED，删除/篡改也拒绝；新请求记录计划来源/叠加计数，并按实际Provider消息统计输入字节，不修改project_context算法。真实Token/费用仍取Provider报告。

原题描述对无规划侧强制“先用update_plan”，本轮源版本升1.1.0，改成工具可用时自主声明，不改事实/答案/评分；旧产物/冻结任务不改。当前题仍是公开三事实规则的机制样本，不能由这一个题或Fake声明模板认定已证明复杂规划收益。§5对分支挑战的研究性目标尚需有区分度任务与后续实验验证；不把技术闭环与研究价值验收混同。本次无新真实模型调用、无Git提交。
