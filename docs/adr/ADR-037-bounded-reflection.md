# ADR-037：受限 Reflection（行动修正）提案与证据门槛

- **状态**：Proposed（2026-10-21），**未批准、未实施核心代码**。负责人同日选择 §9 方案 **C（证据门槛暂缓）**：不实施 Reflection 组件、不新增任务/协议/轴；A/B 的条件契约保留待补到可追溯证据后再定。
- **需求**：requirements V0.6 §6（实验准入）、§19（Planning/Memory/Reflection）、§20（源码学习交付）、§29（协作规范）
- **相关**：ADR-006（预算）、ADR-016（对照回归）、ADR-023/026/030/031（上下文与记忆）、ADR-033（serial 批次）、ADR-035（规划组件）、ADR-036（条件任务）
- **编号说明**：交接时目录最大为 036；本文件占用 037 作为候选，未通过确认前不得提前标 Accepted。

## 1. 要观察的问题（只写有来源的事实）

| 案例 | 来源（可追溯） | 现象 | 现有机制能否解释 |
| --- | --- | --- | --- |
| A 无恢复，参数错终止（Fake） | `artifacts/01ec4c2a-34aa-4a13-bec9-5d883a6a60ec.json`（provider=fake/model=fake-model，order-status-003，handwritten，recovery_policy=none） | step1 提议 `query_records{table:"invalid_table"}` → `TOOL_CALL_VALIDATED.arguments_valid=false, error_code=INVALID_ARGUMENTS` → 直接 `EPISODE_FINISHED/FAILED` | 能。这是 Recovery 关闭的预期边界，不是反思缺失，也不是真实模型失败 |
| B 一次纠错成功（Fake） | `artifacts/00125a9f-957b-4a50-841f-2a40943f9d41.json`（provider=fake/model=fake-model，order-status-002，handwritten_recovery）；同型 `artifacts/04d3c372-c571-5aeb-912a-a7beaf782108.json`（order-status-005，亦为Fake） | 同样的非法表名 → 下一步改为 `orders/ORD-002` → 提交成功 | 能。已有 `invalid_arguments_once` 控制验证覆盖参数纠正，不是真实模型纠错收益 |
| C 全部工具成功但不提交 | `artifacts/conditional-planning-start/pytest-fixed/test_bad_public_route_never_de10/dc16df90-297f-485f-8ba7-f8e28303deee.json` | 10 步全部 `TOOL_SUCCEEDED`、`acquired_evidence` 已在观察中，仍无 `submit_answer`，`MAX_STEPS` | **不能**当作反思必要性证据：这是反事实测试构造的 Fake 行为（"非法公开路由不得默认答案"），不是真实模型 Trace |
| D Provider/网络失败（AIHubMix） | `artifacts/003a283a-189b-4887-8267-6a495b034eb2.json`（NETWORK_CONNECTION_FAILED）、`artifacts/00841c37-cfa5-42d2-a3f1-8bfecf0eb02a.json`（RATE_LIMIT_EXCEEDED） | `RUNTIME_ERROR`，1 次调用即终止 | 能。属网络/配额，明确排除在 Reflection 之外 |
| E 重复阅读 | `docs/learning/V0.3-offline-memory-review-20261018.md` §实际验证：MiniMax 单对工具 8→5、成功阅读 6→3、重复 3→0，两侧均通过 | 同 Episode 重复读同一文档 | 能。由上下文/记忆差异解释；该一次性真实授权已耗尽，且不能挪作 Reflection 证据 |

**结论**：在上表审查的具名样本中，尚未发现足以支持独立Reflection增量假设的案例；不能由抽样或缺少TOOL_FAILED推断全部运行均无适用问题。成功工具也可能返回空文档/错误来源，必须同时查提议、实际反馈、下一次请求与行动。2026-10-21 Codex复核顶层597份Episode发现1份Fake TOOL_FAILED（a6950cc3-95cc-4ea0-8d70-8e6afa168ad8），并不能据此证明Reflection必要；具体扫描清单与范围见学习交接。建议继续暂缓组件、先形成可测假设，不要求在实验前就证明“反思一定可修”。A/B只是候选，尚未完成实施准入。

## 2. 机制选项

### 方案 A：运行时重复动作检测 + 一次约束注入（无额外模型调用）

- 触发：同一 Episode 内，**非致命**工具失败后，下一次提议与失败提议的 `(name, 规范化参数)` 完全相同，且该 Episode 未使用过修正。
- 输出：不调用模型；仅在下一次模型请求前追加一条保留封装 `_agentlabyrinth_reflection`：`{"reason":"repeated_failed_action","failed_call_id":...,"notice":"同一失败动作已重复，请改变做法"}`。
- 优点：不单独增加修正模型调用；与普通下一轮有可观察输入差异。额外约束仍增加输入Token，可能增加时延，均须按实记录，不能宣称零成本。
- 缺点：只覆盖"完全重复"，不覆盖"换了参数但方向仍错"；容易被看作运行时护栏而非反思。

### 方案 B：独立一次结构化修正（一次额外模型调用）

- 触发：同 A 的**非致命公开失败**，且 Episode 仍活动、未到次数上限。
- 输出：一次独立模型调用，必须返回结构化 `ActionRevision`：
  - `cause`：枚举 `missing_input | wrong_source | wrong_rule | incomplete_evidence | other`；
  - `next_action`：可选，形状与普通 `ToolCall` 相同（`name` + `arguments`），仍走原 Registry/Validator；
  - `goal`：≤200 字符的公开下一步目标。
- 注入：校验通过后，作为一条保留封装消息进入下一次普通模型请求；进一步工具调用仍由原循环产生。
- 上限：每 Episode **最多 1 次**；不产生第二次反思；不新增工具。
- 成本：额外 1 次模型调用与 Token，**全部计入该臂自己的预算**，不另送调用/Token。
- 缺点：输入信息与普通下一轮相同，若无"结构化约束"或"禁止直接调工具"的差异，本质上只是多一次采样；必须靠对照实验证明可区分价值，否则不应发布。

### 方案 C（推荐）：证据门槛先行

1. 先确认一个**能产生非致命公开失败**的受控场景：工具返回公开可见的失败（例如目标文档不可用、来源过期），而正确路径要求换来源/换规则，且 Episode 不因此终止。
2. 在**不新增组件**的前提下，先测"普通下一轮"与"一次参数纠错"能否解决；若已解决，则报告"Reflection 无可测增量"，不实现。
3. 只有当第 2 步仍留下可复现缺口时，才选择 A 或 B 进入实现；届时另立 Accepted ADR 明确契约版本。

**主要取舍**：C 会让本轮交付停在"方案 + 证据任务提案"，但避免把一个等同"多一次模型调用"的功能包装成新能力（违反需求 §6 实验准入与"不换名凑功能"）。

## 3. 触发与不触发（三种方案共同边界）

| 触发 | 不触发（立即按原语义终止/拒绝，反思不得放宽） |
| --- | --- |
| Episode 仍活动；工具已实际执行并返回**非致命**公开失败（业务/环境可纠正） | `INVALID_ARGUMENTS`（已有一次纠错，第二次仍终止） |
| 该失败反馈已在当前上下文中可见（来源事件 ID 可追） | `UNKNOWN_TOOL`、`FORBIDDEN_TOOL`、重复 `call_id` |
| 未使用过反思次数 | `TOOL_TIMEOUT`、`TOKEN_BUDGET_EXCEEDED`、`COST_BUDGET_EXCEEDED`、`TIME_BUDGET_EXCEEDED`、`MAX_STEPS` |
| 任务/模型/Provider 来源合法 | Provider 错误、未知用量、已终止 Episode、已提交答案 |

反思输入只能是模型本来可见的：任务公开描述、当前上下文、真实工具反馈。**不得**注入 `goal_conditions`、正确证据、Evaluator 私有结论或最终评分。

## 4. 状态与失败路径（若批准 A/B）

- `REFLECTION_PRODUCED`：记录来源失败事件 ID、`cause`、`next_action`（若有）、条数/字节、模型用量与费用（未知则保持未知）。
- `REFLECTION_REJECTED`：结构非法、越界、引用不存在事件、尝试提交答案或撤销提交 → 不执行该候选，仍记录实际用量且不重试。继续还是终止须在重新提请A/B前定案，不能实现时任意选；普通动作仍适用原校验和终止规则。
- Provider 错/超时/预算：与普通请求同语义终止，不因反思重试；用量按实际返回记录，未返回保持未知。
- 安全点：反思记录与计划一样随 Session 保存；恢复前核对来源事件、条数与最新内容，篡改/遗漏在**新模型调用之前**拒绝；恢复不重做已消费的反思。
- 终态不可复活：反思不能把已 `FAILED/MAX_STEPS/预算终止` 的 Episode 拉回活动状态，也不能撤回 `submit_answer`。

## 5. 公平对照

- 两侧固定：同一模型、Prompt（除反思模板块）、完整 `full` 上下文、相同规划开关、相同工具集、相同 Runtime、相同 Seed/Repeat、相同恢复策略、相同总预算与时限。
- 唯一变量：反思组件开/关；**两侧均不得**同时开启 planning/memory 轴制造混杂。
- 额外调用/Token/时延全部计入开启侧自身预算；不增加其全局免费额度。
- 原 Evaluator 独立评定；不接受"反思自称完成"或反思输出作为证据。

## 6. 契约与兼容（仅在被批准后实施，版本号分属不同契约）

| 契约 | 现状 | 若批准 A/B 的新增 |
| --- | --- | --- |
| `AgentSpec` | 1.3 + `PlanningConfig` | 1.4 + `ReflectionConfig` 1.0（`action-revision-v1`；方案 A 为 `repeat-guard-v1`） |
| `EventType` | 含 `PLAN_UPDATED` | + `REFLECTION_PRODUCED` / `REFLECTION_REJECTED` |
| `SessionState` | 1.2（plan） | 1.3 + 反思记录；空时序列化 pop，保持旧字节 |
| Episode 请求 | 1.6 | 1.7 + `reflection` |
| Experiment 请求 | 1.9 + `planning` | 1.10 + 轴 `reflection`（单变量校验） |
| Experiment 计划/结果/安全点 | 1.4 / 1.6 / 1.4 | 1.5 / 1.7 / 1.5，仅当含反思时 |
| ToolSet | v1.6.0 | 不变（反思不是工具） |
| Prompt | 现有版本 | 新增模板块 `reflect-v1`，仅开启侧使用，版本入配置 |
| CSV | 含 `planning_algorithm_version` | + `reflection_algorithm_version`（左空右填） |

旧请求、旧任务、旧哈希、冻结计划、安全点与重跑仍沿保存版本；新行为不塞进旧请求。

## 7. 任务与验收

**任务**：优先复用现有 21 题。但现有任务没有"非致命公开失败"结构，因此方案 A/B 需要**先批准**一个最小新任务（建议 `reflection-recover-001`，协议 `reflective-retry-v1`）：

- 公开事实：主来源文档不可用（工具返回明确失败），另有可替代来源；两条路径都可达正确答案。
- 私有目标：答案 + 有序/无序证据闭包（沿用 `order_status_v2`）。
- 不要求固定调用次数；基线允许直接换来源成功；不得给反思侧独有工具、额外预算或答案提示。
- 若负责人选择方案 C，则该任务先作为"证据场景"，不实现反思组件。

**验收矩阵（批准后）**：

1. Fake 最小：仅在符合触发条件时产生一次反思；非致命失败前无反思；反思不能提交；证据仍须真实阅读。
2. 两 Runtime（handwritten/langgraph）、single/serial（反思不进入批次）、本地/MCP。
3. 预算：额外调用计入同预算；全局 Token 准入；未知用量不补零。
4. 保存/恢复：安全点前后各侧只消费一次；篡改/遗漏在新模型调用前拒绝。
5. 正式单变量对照：同 full/同规划/同工具/同预算，仅反思开/关；无恢复指标混入。
6. API/Web：正常请求 1.7、显式运行、实时阶段只显示实际到达事件、历史只 GET、CSV。
7. 失败测试：未知/禁止/重复/超时/二次参数错/预算终止不因反思放宽；旧协议逐字兼容。

## 8. 成本与回滚

- 方案 A：不独立增加模型调用；附加输入仍有Token/时延成本，若抑制了已产生的重复提议，也要保留该轮实际调用用量与事件。
- 方案 B：每 Episode 至多 +1 次调用；延迟与 Token 全额计入该臂。未知用量保持未知。
- 回滚：关闭 `reflection` 即回到 1.3 及旧请求；保存产物按自身版本可读，不升级旧产物。

## 9. 待负责人决定

1. 选 **C（推荐：先补证据场景，不实现组件）**、A（重复动作护栏）还是 B（一次结构化修正）。
2. 若选 A/B：是否批准新增最小任务 `reflection-recover-001` 与 `reflective-retry-v1` 评分协议。
3. 若选 A/B：契约版本按 §6 执行；是否同意 Experiment 请求升到 1.10 与轴 `reflection`。

**负责人决定（2026-10-21）**：选 **C**，Reflection 暂缓实施；同时表示“新增 `reflection-recover-001` 与 `reflective-retry-v1`”的批准仅在选 A/B 时生效，因此本轮**不激活**该任务与协议。ADR-037 保持 Proposed/暂缓，不新增 `reflection` 轴、`ReflectionConfig`、`REFLECTION_*` 事件或任何契约版本。要重启 A/B，需先满足 §1 的证据门槛（可追溯、公开可见、现有机制解释不了、反思可修），或负责人另行明确授权真实单对探索并产出该 Trace。A/B 的契约与验收矩阵仅作预备，不构成已批准方案。

2026-10-21复核澄清：保留仓库所记C暂缓决定，不重新要求选择。重启依据应是“可追溯失败+普通下一轮/已有机制的对照+明确的增量假设”，收益本身留给实验检验，不能将实验前已证明可修作为循环门槛。C不激活新任务/工具错误语义。现有真正ToolError在Session中会终止，A/B设想的活动期非致命失败尚无定案；重复提议出现于哪一节点、整批未执行项如何处理、来源事件/短路规则及Reject分支都需重新具体ADR确认，不可据本表直接编码。
