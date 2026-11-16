# ADR-046：GridWorld 可见状态隔离与首切片预算

- **状态**：Accepted；负责人明确批准按送审稿实施。
- **需求**：requirements V0.6 §4.2、§7.2、§12、§13.3、§26.3、V0.4。
- **前置**：V0.3 整版已签收；GridWorld 环境规则见已批准 [ADR-045](./ADR-045-gridworld-key-door-first-slice.md)。
- **范围**：为 ADR-045 的单 Agent Key-Door 首切片确定私有恢复快照、Agent 可见事件/产物的隔离规则和固定 Episode 预算。
- **不包含**：GridWorld 源码实现、Observer 全图视图、Experiment 对照入口、真实模型/Judge 运行、SQLite Schema 迁移或历史产物改写。

## 问题

现有 Runtime 用 `Environment.snapshot()` 同时承担两个不同目的：写入 Session checkpoint 以恢复执行，以及写入 `OBSERVATION_CREATED.initial_state` / `ENVIRONMENT_UPDATED.state` / 最终 `EpisodeResult.final_state` 供 Trace、Replay 和 API 展示。若 GridWorld 快照含未探索地图、真实钥匙/门状态或隐藏目标，这种复用会把 Agent 当时未知的信息带进事件和历史产物。GridWorld 还必须在 16 轮以外明确累计 Token、单次输出、时限和费用的边界。

## 决策

### 1. 私有恢复状态与 Agent 可见投影

为共享 `Environment` Port 增加一个必需的 `public_state() -> dict[str, JsonValue]` 方法；其值为当前 Agent 视角下可用于时间线/Replay 的状态投影，与 `snapshot()` 的私有、可恢复状态是两个独立接口。不能以默认实现 `return snapshot()` 代替显式投影：只有已核实无隐藏状态的兼容环境可明确声明两者等价。

| 边界 | 使用的数据 | 是否包含未探索真值 |
|---|---|---|
| `Environment.snapshot()`、`restore()`、`SessionState.last_state` | 版本化权威恢复快照，服务端内部保存/恢复 | 可以；仅供 Runtime、Environment 和确定性 Evaluator 使用，不作为公开状态回退值 |
| Episode 中可回读的 TaskSpec 元数据 | 公开任务/地图版本标识和 Agent 起点事实；目标/Evaluator 字段仅公开规则 ID | 不可以；不得写真实目标坐标、完整地图或隐藏状态 |
| Provider messages、`Observation`、`TOOL_SUCCEEDED.observation` | 当时生成的 Agent Observation 与真实工具回执 | 不可以 |
| `OBSERVATION_CREATED.initial_state`、`ENVIRONMENT_UPDATED.state` | `Environment.public_state()` 的 Agent 视角投影 | 不可以 |
| Replay、实时 SSE、Episode API 的 `episode.final_state` | 已到达 Trace 前缀及最终 Agent 视角投影 | 不可以 |
| Evaluator | Runner 内存中的权威 Episode 状态与已发生 Trace | 可读；结果 DTO 不返回完整地图或隐藏位置 |

规则如下：

1. `reset()` 与每次成功/规则内拒绝的环境动作，都从同一 Agent 知识投影生成 `Observation` 和 `public_state()`。已探索信息只保留最后已知事实；不得用权威快照反向补齐观察记忆。
2. `SessionState.last_state` 继续保存私有 `snapshot()`，用于安全点恢复。快照只在服务端存储与 Runtime/Environment 恢复路径中使用，不进入 Provider 输入、Trace event、SSE、普通 Episode GET 或 Web Replay。
3. `EpisodeResult.final_state` 在 Runner 内保留权威状态供确定性 Evaluator 评估；评估完成、终态归一后，Runner 将即将持久化/返回的 Episode `final_state` 替换为 `public_state()`。因此最终 API、SQLite 完成产物和历史 Replay 不包含私有快照。
4. GridWorld 的 TaskSpec `initial_state` 仅写公开起点/地图版本；`goal_conditions` / `evaluator_config` 只写公开规则标识，不写目标坐标、完整地图或可还原隐藏布局的数据。该规则同时覆盖被保存、API 回读或打入 Trace 的任务元数据。Evaluator 根据固定 `environment_version` 的服务器端地图定义和权威最终状态评分；展示的 Evaluation 仅包含已批准的成功/终止指标。
5. 本首切片不提供 Observer 全局地图视图。若以后增加，必须是独立、显式标记且不得混入 Agent Replay 的视图。
6. 隐藏信息是相对 Agent 的产品可见性边界，不是对同机用户或本地数据库文件的访问控制保证。
7. **失败时只允许保留已验证的公开投影或 fail-closed。** Runtime 在成功 reset/step 后保留最近一次已验证的 `public_state()`，独立于私有 checkpoint。工具执行或 Evaluator 失败时，公开 Episode/Trace 只能使用这份安全投影；`public_state()` 序列化/校验失败时，不得退回 `snapshot()`，终止为现有安全运行时失败语义，并用 `{}` 或最后一份已验证公开投影结束。恢复校验/重建失败时不将不可信 checkpoint 作为 Episode/Trace 状态；拒绝恢复或以无私有数据的失败产物结束。若安全投影无法证明未泄漏，宁可不返回状态，也不得返回权威快照。

### 2. Schema 与旧产物兼容

- `TraceEvent` 字段、API 路径和 SQLite 表不变；新增的是 Domain `Environment` Port 的显式投影方法。GridWorld 使用新的 `RunConfig.environment_version` 标识其 Agent 可见投影语义。此 Port 变更影响所有实现方，合入前必须通过下列兼容矩阵。
- **`ToolLabEnvironment`**：`public_state()` 显式返回与现有 Agent 可见 Replay state 完全相同的值；不改私有 checkpoint、Trace、任务配置哈希或现有评测语义。
- **`MCPToolLabEnvironment`**：继承并验证 ToolLab 的公开投影；远程只读工具回执/失败保持当前语义。不得将 MCP 客户端内部/传输状态、远端未返回数据或私有 snapshot 附加到公开投影。
- **`BFCLEnvironment`**：显式投影仅包括 BFCL Agent 已可见的状态/已接受提案；保留单次工具提案、原 Evaluator 输入与 BFCL 与 ToolLab 分开展示/评分。不能因新增 Port 改变一函数调用约束或执行上游代码。
- **测试环境/替身**：`tests/contract/test_framework.py` 的 `StubEnvironment`、`tests/contract/test_multi_turn_messages.py` 的 `DummyMockEnvironment`、执行时限测试中的 `ToolLabEnvironment` 子类，以及所有新增 Fake/Mock 环境，必须实现显式 `public_state()`。协议测试同时验证 `snapshot()` 仍用于 checkpoint，公开 Trace 不会直接调用或暴露 snapshot。
- `public_state()` 不是可选接口，不提供会静默回退到 `snapshot()` 的默认实现。新增/第三方环境无法提供安全投影时拒绝运行 GridWorld/相应 Runtime 入口，并报告明确的协议错误。
- 既有 ToolLab 的 `public_state()` 必须返回与当前 Replay 使用的 `snapshot()` 完全一致的值。既有 Trace、Artifact、Checkpoint 的字节、哈希和回读语义不改、不重写。
- 历史产物仍按保存时的事件与最终状态原样读取；不使用新投影重算旧历史，也不对旧 JSON/SQLite 记录做迁移或回填。
- 新 GridWorld 安全点按其环境版本校验并恢复私有快照与 Agent 知识投影；恢复后只追加新事件，不重发已记录动作、不调用模型补齐历史。
- 若实现发现既有 API/Trace 消费者必须改变公共 Schema、事件类型或 TaskSpec 序列化才可隔离数据，停止实现并另提协议 ADR，不得把字段悄悄隐藏或静默改写旧产物。

### 3. 固定首 Episode 预算

以下是**每个 GridWorld Episode** 的冻结值；发生恢复时沿用原安全点已消耗量，不重置。单次 Episode 不运行 Reflection、Planning 或工具批次。

| 限制 | 固定值 | 计数/超限语义 |
|---|---:|---|
| Runtime 轮次 / `TaskSpec.max_steps` | 16 | `BudgetTracker` 有效轮次为二者最小值；第 16 轮可执行动作。未通关时不发第 17 次 Provider 请求，终止 `MAX_STEPS / max_steps_reached`。 |
| `Budget.max_steps` | 16 | 与任务轮次一致；更早的其它预算仍优先按其原 detail 终止。 |
| `Budget.max_model_calls` | 16 | 每轮最多一个动作响应；动作前的失败请求仍计入模型调用。 |
| `Budget.max_tool_calls` | 16 | 只计送达 Executor 的工具调用；Schema/权限拒绝不算环境动作，但消耗模型轮次。 |
| 每次模型响应 `ModelConfig.max_tokens` | 800 completion tokens | 每个请求均发送此上限。Provider 报告单次 completion **> 800** 时，先完整记录该响应真实用量/费用，再以 `TOKEN_BUDGET_EXCEEDED / model_completion_tokens_exceeded` 拒绝执行该响应中的动作；不截断、重试或丢弃超额用量。实现必须在 Runtime 响应边界显式检查，累计 `BudgetTracker` 上限不能代替该检查。 |
| Episode 累计 `TaskSpec.token_budget` | 16,000 tokens | 对所有模型请求累计报告的 prompt + completion；计入有可信用量的失败响应。累计 **> 16,000** 时完整记账并在本响应动作执行前停止；累计**恰好 = 16,000** 时允许当前已通过 Schema/权限验证的单个动作完成（包括规则内拒绝的游戏动作），随后不再启动下一 Provider 请求。 |
| `Budget.max_prompt_tokens` | 16,000 tokens | Episode 累计 prompt 上限；`> 16,000` 的响应完整记账后拒绝执行动作；恰好达到时允许当前合法动作结束，然后禁止后续模型请求。 |
| `Budget.max_completion_tokens` | 12,800 tokens | 16 次 × 每次 800 的 Episode 累计 completion 上限；超过时完整记账后不执行当前动作；恰好达到时允许当前合法动作结束，然后禁止后续模型请求。 |
| `Budget.max_execution_time_ms` | 300,000 ms（5 分钟） | 单 Episode 总运行时间；包括模型、工具及恢复后的剩余执行时间。过期不重试。超时导致上游用量未知时保持未知。 |
| `Budget.max_estimated_cost` | USD 1.00 / Episode | 仅作为**已知估算费用**阈值，不代表网关实付或发票硬上限。已知估算超限后停止后续请求；未知费用保持未知，不当作零。 |

设置 300,000ms 运行上限时，现有契约要求 `Budget.schema_version="1.1"`；其他新值使用现有字段，`ModelConfig.max_tokens=800`，不改公共字段或旧配置默认值。精确累计 Token 上限的语义是“完成当前合法动作后停止”，而不是允许开始下一次请求；累计超限或单次输出超限的当前动作不执行。金额/时限边界仍按现有规则：响应后如实入账，超过时停止后续动作/请求，不伪称预先控制在途成本。

Token/估算费用来自 Provider 响应，按现有 Budget 语义在响应后核账；已经发出的响应完整保留。最后一个在途响应可能使累计值跨过阈值，但 Runtime 必须在该响应记账后停止，不再发下一次请求。不得把可能的在途超额写成严格的预先封顶保证。任何以后启用真实 Provider 的硬费用上限都需要可验证的预估/预留机制和单独准入；本 ADR 不授权真实模型调用。首切片自动化与浏览器验收只使用 Fake。

### 4. 规则内非法行动

墙/关闭门阻挡、错误拾取、不可用目标等属于有效游戏行动：Environment 增加动作与非法行动计数，并通过正常 `StepResult.observation` 返回结构化拒绝结果；不设置 `StepResult.error`，不伪装成 `TOOL_FAILED`。`StepResult.error` 仅代表工具/环境执行故障，沿现有 Runtime 失败语义停止。

## 兼容与安全验收

实现必须提供自动化证据，至少覆盖：

1. **不泄露**：在初始 Observation、Provider 全部消息、每个 Trace payload、实时 SSE、最终 Episode Artifact/API GET 和 Replay JSON 中递归查找隐藏目标坐标、未探索格、权威钥匙/门状态和快照专用字段；Agent 可见范围之外的数据不得出现。对照保留服务端 checkpoint 内确需恢复的私有快照。
2. **前缀正确**：初始观察、实时事件、最终产物和历史回读分别验证；移动 Replay 游标或历史 GET 不可借最终状态补全过去的地图，也不触发 POST。
3. **Evaluator 独立性**：使用权威状态评估成功/失败；改变仅服务端隐藏目标或门状态的测试夹具时，Evaluator 结果跟随真实权威状态，而 Agent Observation/Trace 仍只含当时可见投影。
4. **动作规则**：ADR-045 固定 8 动作路径成功；墙、边界、关门、未持钥匙、错误/不可见目标、重复拾取等只返回规则内拒绝，状态与计数准确；真正执行异常仍走 Runtime 故障路径。
5. **16 轮边界**：16 轮完成动作允许成功；第 16 轮未完成时没有第 17 次 Provider 请求和环境动作；Schema/权限拒绝消耗模型轮次但不增加环境动作。
6. **预算边界**：Fake 精确覆盖 800 单次输出、16,000 累计 Tokens、12,800 completion、300 秒、已知估算 USD 1.00 边界；覆盖响应后超额记账、不再续发、用量未知不补零和恢复不重置预算。
7. **请求级/累计 Token 边界**：800 completion 正好时执行当前合法动作；801 时精确记录 801 和相关费用、动作拒绝、无 `TOOL_STARTED`/环境事件；累计 Token 正好 16,000 时执行当前合法动作但无后续 `MODEL_REQUESTED`，累计 16,001 时记录用量并拒绝当前动作；12,800 completion 与 16,000 prompt 的等值/超值分别断言同样语义。
8. **共享 Port 兼容**：ToolLab、MCP ToolLab、BFCL、`StubEnvironment`、`DummyMockEnvironment`、执行时限子类及其他测试替身均显式实现 `public_state()`；比较 ToolLab/MCP 与旧 Replay state，验证 BFCL 一次提案及评测不变，并验证 snapshot/restore round-trip 仍使用私有状态。
9. **故障 fail-closed**：分别注入模型响应超限、工具执行失败、Evaluator 抛错、`public_state()` 抛错/产生无效 JSON、checkpoint 读取/版本校验/restore 失败。所有公开 Trace/Artifact/SSE/API 只含最后有效公开投影或空状态；扫描不得发现私有 snapshot，绝不把私有快照作为兜底。失败过程中不重复模型请求、工具调用或覆盖历史记录。
10. **恢复**：在取得钥匙、开门和探索信息分别设置中断点；跨进程恢复后权威状态与 Agent 已知状态分别一致，不能从私有地图补记忆；无重复工具执行/模型请求。
11. **旧版兼容**：锁定代表性已保存 ToolLab Agent/Task/Trace/Artifact/Checkpoint 哈希；新 Port 实现前后 ToolLab Trace state 与历史 API/Replay 保持一致，旧历史不迁移、不覆盖。
12. **真实产品闭环**：Fake API/Web 实测创建、实时事件、结束产物、SQLite 保存、服务重启、Episode ID GET、URL 刷新/前进/后退；记录真实本地 ID、HTTP 与 Network 方法。

## 批准记录与实施边界

负责人已明确批准 ADR-045 与本 ADR，按上述送审稿实施。冻结预算及 Token 边界为当前首切片契约；不得静默提高限制、丢弃超额用量、或将未知用量/费用视为零。

实施严格依照[开发规范与首片任务卡](../tasks/V0.4-gridworld-development-spec-20261105.md)分阶段推进：先完成环境/预算/信息隔离契约和兼容测试，再进入 Fake 实时 Web 闭环，最后处理 SQLite 跨进程恢复。本 ADR 不授权真实模型/Judge、GitHub 写入、历史迁移或 GridWorld Experiment。
