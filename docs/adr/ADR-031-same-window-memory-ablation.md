# ADR-031：相同近期窗口下的工具记忆消融对照

状态：**Implemented，待负责人验收**，2026-10-15。原 Proposed 方案已由 Trae 实施（记录见 §12），负责人本日要求 Codex 复核并接管主要技术开发；不能再把已实现功能写成“未实施”。本状态不代替负责人签收或自行宣称 Accepted。依据需求 V0.6 §19、Accepted ADR-023/026/030 与本次任务卡 [V0.3-memory-closeout-trae-20261014](../tasks/V0.3-memory-closeout-trae-20261014.md)。只实现“相同窗口、仅切换记忆”对照轴，不启动多 Agent、数据库、摘要模型、跨任务记忆或新框架，不修改默认 `full`，不提交 GitHub。下文待批准措辞是原方案选择过程，最新实现与复核以文末和 current-state 为准。

## 1. 问题与自变量

现有 Web 上下文轴是 **full vs recent_tool_rounds（右侧可加 memory）**（ADR-026）。它把窗口长度与记忆两个变量一起改变，无法把差异单独归因于记忆。已有一对真实 CLI 探索（window1 无记忆 vs window1+memory8192，见 [V0.3-memory-real-pair-20261014](../tasks/V0.3-memory-real-pair-20261014.md)），但尚无正式 Web/API 的同窗口开关协议。

研究问题：在**完全相同的 N 轮近期窗口**里，加入受限单 Episode 工具记忆（M 字节）是否改变工具/模型调用次数、重复文档阅读、报告 Token 与任务成功，而其余条件全部一致？

- 自变量：工具记忆开关（左侧关、右侧开），窗口轮次 N 两侧相同。
- 固定：provider、model、temperature、Prompt、tool_set_version、Runtime backend、Runtime strategy、recovery_policy、environment_version、任务集合、seed(s)、repeat、预算（max_steps / 报告 Token / 时间 / 全局 Token / 参考费用）。
- 唯一变化：右侧 `memory_max_bytes=M`（256–32768），左侧无记忆。

## 2. 方案选择：独立轴，而非改写旧轴（任务卡 B.2）

- **选项 A（否）**：把现有 `context_policy` 轴的左条件从 `full` 改成“同 N 无记忆”。这会改写 ADR-026 已冻结的“左 full”语义，迫使放宽旧验证器（`ExperimentArtifact.token_budget_revision` 与 `_validate_context_agents` 均硬性要求 left=full），并让历史 full 对照在重读时含义漂移。违反“旧协议无静默变化、不得仅松开旧验证器”。
- **选项 B（建议，待批准）**：新增**独立轴值** `comparison_axis="memory_ablation"`。旧 `recovery_policy` / `runtime_backend` / `context_policy` 三轴的语义、默认值、旧版本接受/拒绝规则及历史哈希保持；新轴走新的请求/计划/结果版本号。共享校验器需要增加新轴/版本分支，不要求源码逐字不变，不能据此放宽旧协议。

被否决的另一写法：给请求新增独立 `memory_max_bytes` 字段并让 `context_policy` 只承载左窗口。可读但引入更多请求面且需要重复校验窗口一致性；改为**用 `context_policy` 承载右侧策略、左侧由服务端确定性派生**（见 §3），结构上保证“仅记忆不同”。

## 3. 请求 / 计划 / 结果 / 版本（任务卡 B.3）

| 层 | 旧版本 | 新版本 |
| --- | --- | --- |
| `CreateExperimentRequest.schema_version` | ≤1.5 | **1.6** |
| `ExperimentCheckpoint.schema_version` | ≤1.2 | **1.3** |
| `ExperimentArtifact.schema_version` | ≤1.4 | **1.5** |

请求（`apps/api/schemas.py` 的 `CreateExperimentRequest`）：

- 新 `comparison_axis` 取值 `"memory_ablation"`（`ComparisonAxis` 增加该字面量）。
- `context_policy` 承载**右侧**策略：必须是记忆策略（`schema_version="1.1"`、`algorithm_version="tool-round-window-memory-v1"`、`mode="recent_tool_rounds"`、`memory_max_bytes` 为 256–32768 整数）。`ContextPolicy` 现有校验（`models.py`）已强制这些组合，直接复用。
- 新轴必须用请求版本 1.6；旧版本带新轴拒绝。
- 拒绝规则：
  - `memory_ablation` 且 `context_policy is None` 或不是记忆策略 → 拒绝；
  - `memory_ablation` 且 `context_policy.mode != "recent_tool_rounds"` → 拒绝（记忆已隐含此约束，仍显式校验）；
  - 非 `memory_ablation` 轴沿用旧规则：`context_policy`轴左full/右可记忆，Recovery/Runtime轴可使用两侧相同的已有记忆策略，不新增左右不一致的条件；
  - 非法 `memory_max_bytes`、非整数、越界由 `ContextPolicy` 拒绝。

新请求1.6仅允许memory_ablation，旧轴继续沿用原版本，默认请求版本保持原1.5。需要显式更新共享版本门：`CreateExperimentRequest.global_token_revision`现仅允许1.4/1.5全局预算、显式context仅1.5；新轴1.6应允许其显式记忆和全局预算，但旧轴的接受规则不能改变。计划/结果的全局Token版本门及Web对应refine同理加入仅新轴使用的1.3/1.5；必须测试轴/版本双向错配和“新轴+全局Token”创建、停止、恢复、回读，而非只在Literal加入新版本。

派生（服务端，`apps/api/service.py` 的 `prepare_experiment` 新分支）：

- **左（baseline）**：`ContextPolicy(schema_version="1.0", algorithm_version="tool-round-window-v1", mode="recent_tool_rounds", max_tool_rounds=N)`（同 N、无记忆）。
- **右（recovery）**：请求的 `context_policy`（同 N、`memory_max_bytes=M`）。
- 两侧 backend / strategy / runtime_version / recovery_policy / model / prompt / tool_set / budget / tasks 完全一致；只有 `context_policy` 的记忆子版本不同。

计划（`ExperimentCheckpoint`，`packages/application/experiment.py`）：

- `schema_version="1.3"` 仅当 `comparison_axis=="memory_ablation"`；`verify()` 增加该版本门与 `_validate_memory_agents(left, right)`。
- `_validate_memory_agents`：两侧均严格按ContextPolicy校验，recent且同N；左为原1.0窗口/无记忆，右为1.1记忆算法/合法M；同backend/strategy以及相同model/prompt/tool_set/budget。创建、冻结计划verify和恢复都执行对应固定变量检查，身份/name区别不作实验变量；结果读取校验其保存的两侧策略、Runtime来源、共享配置与配置哈希。非法或篡改不能通过重算plan_hash绕过单变量检查。

结果（`ExperimentArtifact`）：

- `schema_version="1.5"` 仅当 `comparison_axis=="memory_ablation"`；`token_budget_revision` 校验增加该分支：同 backend/strategy/version；左右均 recent；同 N；左无记忆、右有记忆；`retry_eligible is None` 且 `recovered is False` 且聚合挽救指标全为 `None`（该轴不使用 Recovery 挽救率，沿用 context 轴约定）。

## 4. Application / 服务编排（任务卡 B.4）

- `ComparisonAxis` 增加 `"memory_ablation"`。
- `create_experiment_plan` 增加分支：仅当 `comparison_axis=="memory_ablation"` 调用 `_validate_memory_agents`；`model/prompt_version/tool_set_version/budget`仍两侧相同，只有context_policy按新轴允许不同，Runtime backend/strategy仍必须相同。计划 `schema_version="1.3"`。
- `run_experiment` 臂标签（`arm_labels`）新增：`{"baseline": "Recent Window", "recovery": "Recent Window + Memory"}`。
- 冻结计划、暂停/恢复、失败重跑：完全复用现有 `CheckpointStore` / `ExperimentCheckpoint` / `rerun_failed_episode` 路径；恢复时按冻结的原策略重建 provider 与 Runtime，不重新执行既有安全点；失败重跑沿用原策略，不换变量、不选最好一次。
- 全局 Token / 参考费用预算沿用现有限制；恢复沿用 `comparison_axis` 无关的既有逻辑。
- `comparison_key`（`packages/application/regression.py` 的 `fixed_config`）：**无需改动**。`context_policy` 已在每臂 `arm_config` 内，故每个 (N, M) 组合仍生成稳定、可区分的键；记忆开关与窗口不进同一趋势，符合“窗口无记忆与有记忆不混入同配置趋势”。旧轴键语义不变。

## 5. 兼容与拒绝（任务卡 B.5、B.6）

- 旧 `ContextPolicy` 1.0 序列化/哈希、旧 `AgentSpec` 哈希、旧 `ExperimentArtifact`（≤1.4）/`ExperimentCheckpoint`（≤1.2）/旧 CSV 列顺序与未知空值**逐字保留**。新轴只新增版本号与一个 LooseObject 轴值。
- Recovery/Runtime旧轴仍要求两侧上下文相同；context_policy旧轴仍左full/右recent（可memory），不能概括成全部旧轴上下文相同。
- 上下文与记忆轴**均不使用 Recovery 挽救率**；`retry_eligible`与`retry_recovery_*`为None，持久Pair的`recovered`保持bool且必须False，不改成None。CSV中非恢复轴的挽救相关列继续为空。派生阅读指标沿用“只有实际成功返回且正文 ID 匹配才计已读；空 `document:null`、失败、未返回、预览不计；同一 ID 再次成功返回计重复”，来源为当前 Trace 前缀，不借最终快照补数据。
- 非法 N/M、混合变量（记忆策略与窗口不匹配、两侧 backend 不同）、旧版本误用新轴一律拒绝；**不静默降级**成旧窗口。

## 6. Web 配置与结果信息设计（任务卡 B.7）

只增加必要选项，历史草稿隔离，URL 只 GET：

- 对照轴下拉新增一项 **“工具记忆：相同近期窗口 vs 相同窗口+记忆”**。
- 选择后显示两个字段：**相同窗口轮次 N（1–100，两侧共用）** 与 **右侧记忆上限 M（256–32768 字节）**；左侧固定为同 N 无记忆，界面明确标注“仅记忆开关不同”。
- `ContextSettings` 复用现有数字与帮助样式；不缩小字体、不重置草稿。默认演示候选 N=1、M=8192，但**不改单次默认 full**。
- 结果区：既有只读上下文对照块扩展为显示两臂策略（左“最近 N 轮工具交互”、右“最近 N 轮工具交互 + 记忆 M 字节”），并保留“保存结果不随草稿改变”“字节不是 Token”“记忆可能增加输入量，不保证效果”的提示。
- CSV：旧列顺序与列集不变；新增轴仅需在既有 `context_mode`/`context_max_tool_rounds`/`context_algorithm_version`/`context_memory_max_bytes` 列上正确导出左右臂（左 `memory_max_bytes` 为空，右为 M）。
- 刷新/前进/后退只 GET；改草稿不影响任何历史；右侧穿透来源展示沿用 `McpFlowReplay` 当前请求诊断（记忆条数/字节/跳过/源 call_id），资料阅读沿用 `DocumentEvidence`。
- 结果说明表述为“左右窗口相同，仅记忆配置变化”；仍标记真实模型随机性和单对探索，不能称已证实因果收益。审核各处轴标签，包含ExperimentDashboard、ExperimentCharts和成对结论，避免新轴被默认显示为Recovery或未知类型。

## 7. 拟改文件与实现顺序（任务卡 B.8）

1. `packages/application/experiment.py`：`ComparisonAxis`、`_validate_memory_agents`、`ExperimentCheckpoint.verify`、`ExperimentArtifact.token_budget_revision`、`create_experiment_plan`、`run_experiment` 臂标签。
2. `apps/api/schemas.py`：`CreateExperimentRequest.schema_version="1.6"` 与 `memory_ablation` 校验分支。
3. `apps/api/service.py`：`prepare_experiment` 新轴建双侧 Agent（左派生、右=请求策略）。
4. `apps/web/src/apiContracts.ts`：`experimentConfig.comparison_axis` 增加 `"memory_ablation"`；`experimentArtifactSchema.schema_version` 增加 `"1.5"` 及对应 refine。
5. `apps/web/src/App.tsx`：对照轴选项、配置字段（N/M）、CSV 轴标签、只读结果块。
6. `apps/web/src/ContextSettings.tsx`：新轴的 N/M 输入与帮助文案。
   `apps/web/src/ExperimentDashboard.tsx`和`ExperimentCharts.tsx`：新轴与两侧曲线/环图标签；读取保存轴不从草稿推断。
   `scripts/run_regression.py`的`preflight`：新轴必须按request.runtime_strategy推导两侧策略，并按同N无记忆/有记忆推导策略。现代码仅对runtime/context轴如此处理，新memory轴会误入默认Recovery策略，且错误要求左侧等于右memory；`fixed_config`无需改不等于整个回归入口无需改。新增支出前预检用例；混变量须在Provider调用之前拒绝。
7. 测试：
   - `tests/unit/test_context_projection.py`（如需补充策略组合边界，复用现有断言风格）。
   - 新增 `tests/integration/test_memory_ablation_experiment.py`：Fake 两 Runtime 的计划/校验/执行/保存回读/恢复/失败重跑/拒绝用例。
   - `tests/integration/test_context_comparison_web.py`：新轴请求校验与旧轴回归不变。
   - `apps/web/tests/apiContracts.test.mjs`、`apps/web/tests/flowFrames.test.mjs`：schema/CSV 断言。
   - `apps/web/e2e/memoryAblation.spec.ts`：配置、只读、CSV、URL GET。
8. 回滚/关闭：若不采纳，隐藏对照轴新选项即可，**保留新版本读取**，不改写任何产物；无数据迁移。

## 8. 测试矩阵（草案）

| 类别 | 用例 |
| --- | --- |
| 请求校验 | 1.6 接受新轴；旧版本带新轴拒绝；缺 `context_policy`/非记忆策略拒绝；`mode=full` 拒绝；越界/非整数 M 拒绝 |
| 版本/全局预算 | 新版本搭旧轴拒绝；新轴全局Token请求/计划/结果/Web校验通过，达到/未知预算不开始下一臂，恢复保留累计；旧版本矩阵不变 |
| 计划校验 | 两侧 recent 且同 N 通过；左有记忆或右无记忆拒绝；N 不同拒绝；backend 不同拒绝；计划版本 1.3 门 |
| 结果校验 | schema 1.5 门；recovery 挽救指标为空；同 N/左右记忆约束；config_hash 自洽 |
| 执行 | Fake 两 Runtime 各跑一次；左 window 失败/右 memory 通过（沿用既有机制事实）；两侧仅 `context_policy` 哈希不同，其余哈希相同 |
| 保存/恢复 | 保存回读一致；计划冻结；恢复不重跑既有安全点；篡改策略拒绝 |
| 失败重跑 | 仅失败 Episode 可重跑，沿用原策略与冻结变量 |
| 回归/看板 | `fixed_config`键稳定且旧轴不变，改N/M或轴不能混趋势；run_regression.preflight新轴/原策略匹配、篡改预算/窗口/记忆/版本在支出前拒绝；Dashboard/Charts标签正确 |
| Web | 新轴选项、N/M 输入、只读结果、CSV 列正确、刷新只 GET、草稿隔离 |

## 9. 真实验证范围

- 默认Fake只验证机制：指定原生007、N=1/M=8192时窗口失败/记忆成功是既有受控预期；其他任务/N/M不套用该固定结果。须覆盖较大窗口两侧成功、容量不足右侧也失败，不能为满足预期改评分/伪造事实。
- 真实模型为**可选**：复用 `scripts/episodic_memory_ablation.py --model` 的既有逐侧报告（当前顺序固定 window→memory，仅一对探索，不外推成功率或稳定收益）。本 ADR 不要求新的真实 POST，也不批量 Seed×Repeat。
- 采纳后目标是“完整可用入口”（可冻结/可恢复的正式 Experiment），不能把静态图或两次孤立 POST 当作冻结结果。

## 10. 验收与边界

采纳后须验证旧序列化/哈希、旧三轴与旧结果读取不变、新轴严格校验与拒绝、两 Runtime 计划/执行/保存/恢复/失败重跑、`fixed_config`/看板兼容、Web 只读与 CSV、README 记录的完整门禁（含 Edge 通道）。

本轴可能增加右侧输入量、丢失超大返回或保留无关内容，**不保证成功率或 Token 收益**；单对探索不是因果证明或行业排名。它不是持久知识库、语义检索、LLM 摘要或新算法。发现需要新 Schema/评分/Provider 权限/恢复语义变化时，记录复现并另提 Proposed ADR。不提交 GitHub。

## 11. Codex复核修订（2026-10-14）

独立轴及版本化方向可作为待批准方案。本轮补齐全局预算共享版本门、创建/恢复单变量检查、回归preflight与看板标签调用点；修正recovered=False、旧轴记忆兼容和固定Fake预期范围。仅修订方案，未实施API/Application/Web协议，状态仍Proposed；负责人确认这份具体修订方案后再编码。

## 12. 实施记录（2026-10-15，本地完成）

负责人2026-10-15确认“按修订 ADR-031 开始开发”，本轮按本 ADR 修订方案完成 API/Application/Web 协议实现与 Fake 端到端验收，状态仍由负责人决定（本条不自标 Accepted，不签收 V0.2/V0.3 整版）。

- 版本与轴：`memory_ablation` 加入 `ComparisonAxis`；请求 1.6 / 计划 1.3 / 结果 1.5 均仅该轴使用，旧默认请求 1.5、单次运行默认 `full` 不变；旧三轴语义/版本接受规则/旧哈希逐字保留。
- 校验：`_validate_memory_agents`/`_require_memory_arm_pair` 覆盖两侧 recent 同 N、左无记忆、右有记忆、同 backend/strategy/recovery_policy，创建与冻结 `verify()` 及恢复都执行；`ExperimentArtifact` 1.5 分支校验同 backend/strategy、同 N、左右记忆约束与挽救指标全空(`recovered is False`)，篡改不能靠重算 `plan_hash` 绕过。
- 派生：`prepare_experiment` 服务端确定性派生左=同 N 无记忆(1.0/`tool-round-window-v1`)、右=请求记忆策略(1.1/`tool-round-window-memory-v1`)；两臂除 `context_policy` 记忆子版本外完全一致(实测单变量哈希对比通过)。臂标签左 `Recent Window` / 右 `Recent Window + Memory`。回归 `preflight` 按新轴派生左右策略与 Runtime strategy；`fixed_config`/`comparison_key` 保持无需改动。
- 验收：Fake 两 Runtime(handwritten/langgraph) 计划/执行/保存回读/恢复/失败重跑、全局 Token 拒绝、请求与结果非法组合拒绝；Web 配置/只读/草稿隔离/CSV/URL GET/Trace 穿透/四视口。完整门禁设 `AGENTLABYRINTH_E2E_CHANNEL=msedge` 退出 0(Python393/Node38/Edge47，产物 `artifacts/quality/409becda-bca8-452a-a47f-2c0ac041ec4e`)；首轮 ruff format/mypy 未过已修正重跑，失败未隐匿。
- 受控 Fake 期望只对指定任务(原生 `order-status-007`)与 N1/M8192 成立；另覆盖 N5/M32768 两侧均通过与 N1/M256 两侧均失败，不改评分或伪造事实。真实模型仍为可选，本轮无新真实调用、不批量 Seed×Repeat。

## 13. Codex技术验收与修复（2026-10-15）

原实现仍有三类缺口，已在既定协议内修复：共享记忆校验增加全部固定Agent字段，覆盖创建与冻结verify/恢复，重算哈希不能放行混变量；计划1.3/结果1.5与新轴的版本门补反向拒绝；结果后端/Web都要求两侧完整且匹配的Runtime来源、恢复标签与策略一致，非对象臂配置明确校验失败。旧轴与旧版本接受规则保持。

两项新增测试先在原实现复现失败，修复后最终完整门禁退出0：395 Python（60.48s）、mypy104、四套22格回归零退化、旧24格上下文、Node38、Edge47/47（1.9m）、构建/audit通过。最终日志 `.uv-cache/codex-memory-review-final-20261015.log`，产物 `artifacts/quality/9c8f141b-0ec7-4930-a42e-0b4dd63b45b6/`。首轮门禁与失败记录保留；本机Edge验证，不宣称远端CI。源码、调用链、复现与协作者防错规则见[学习交接](../learning/V0.3-memory-ablation-20261015.md)。技术复核通过，负责人体验/整版签收仍独立；无新真实模型调用或GitHub提交。
