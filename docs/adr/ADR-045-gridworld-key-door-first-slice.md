# ADR-045：GridWorld 钥匙与门首个环境切片

- **状态**：Accepted；负责人明确批准按送审稿实施。
- **需求**：requirements V0.6 §0.3、§0.4、§7.2、V0.4。
- **前置条件**：V0.3 整版已由负责人确认签收；负责人已明确批准本 ADR 与 ADR-046。按任务卡分阶段实施，首阶段验收前不进入实时 Web 或跨进程恢复。
- **范围**：一个 Agent、一个不可变二维地图、局部观察、取钥匙、开对应门并抵达目标。

## 问题与目标

ToolLab 已覆盖受控工具任务，但不能直接检验空间移动、部分可观测和状态改变后的路线选择。本 ADR 决定使用一张可手算、可复现的小地图，以现有 `Environment`、Episode、Trace、Checkpoint 和 Evaluator 边界承载首个 GridWorld 任务。

首切片用于验证环境规则、模型可见边界、单次运行与回放/恢复闭环；不据一题宣称长程规划、记忆或模型能力收益。

## 外部设计参照与采用边界

这些项目仅为设计/研究参照，不构成依赖、代码移植、基准兼容或实现授权：

- **MiniGrid DoorKey** 是钥匙/门/局部观察与离散移动的玩法先例。本提案只借鉴这类可解释的核心循环；地图、动作、资源消耗、观察范围和 Episode 预算均按 AgentLabyrinth 自己的版本化规则实现，不安装 MiniGrid、不复制其源码，也不报告 MiniGrid 分数。来源：[Farama MiniGrid 项目](https://github.com/Farama-Foundation/Minigrid)。
- **AgentWorld** 的共享世界、非对称角色和行动因果依赖可作为长期研究方向的对照参照。此处只保留单 Agent 的“取得匹配钥匙 → 开门 → 到达目标”固定前置链，不实现 MMORPG、多角色、共享计划、通信或其任务调度，也不采用其 CCE 指标；本任务的依赖由本地确定性规则/Evaluator验证，不把生成解释当成因果真值。来源：[AgentWorld 论文](https://arxiv.org/abs/2609.31590)及[作者仓库](https://github.com/openagents-org/agentworld)。
- **VirT-Lab** 的研究组织、动作时间线/空间状态联动和观察者复盘视角，提醒产品区分 Agent 当时可见事件与事后全局解释。本切片仅采用“Agent 视角 vs 明确标记的观察者视角”和事件前缀回放要求，不引入其场景生成、多人调度、记忆检索或前端引擎。来源：[固定 v1 论文](https://arxiv.org/html/2510.08242v1)。
- **Collab-Overcooked** 展示了协作基准可覆盖多个任务与模型；论文报告的任务/模型规模属于该论文的研究设置，并非本项目门槛。本切片不做合作任务、不对齐其评分或声称可比，只把它作为“单个钥匙门谜题不能支撑协作/泛化结论”的范围提醒。来源：[EMNLP 2025 论文](https://aclanthology.org/2025.emnlp-main.249/)。

本地精读和先例核查见 `docs/research/multi-agent-sandbox-direction-20261013.md`、`docs/research/virt-lab-close-reading-2510.08242v1.md`。以上资料支持设计边界，不证明本提案的新颖性、效果或可复现外部结果。

## 决策

### 地图、坐标与状态

- 坐标从零开始，`x` 向右、`y` 向下。地图为 7 列 × 5 行，边界为墙；地图定义不可变，动态状态单独保存。
- 首个地图 ID 为 `key-door-001-v1`，环境版本为 `gridworld-key-door-v1`：

```text
      x 0 1 2 3 4 5 6
y=0     # # # # # # #
y=1     # . K # . . #
y=2     # S . D . G #
y=3     # . . # . . #
y=4     # # # # # # #
```

`S` 是起点 `(1,2)`，`K` 是钥匙 `key-amber` `(2,1)`，`D` 是对应门 `door-amber` `(3,2)`，`G` 是目标 `(5,2)`。墙、地面、钥匙、门与目标位置属于地图版本，不在运行中编辑。

- 该地图固定，不由 Seed 随机化；Seed 仍写入标准 `RunConfig` 以便回读，但对本地图不改变布局。后续不同布局必须使用新的地图版本或显式、版本化的生成算法，禁止让同一地图 ID 在同一 Seed 下改变含义。
- 服务端权威环境快照至少包括地图/环境版本、当前位置、真实钥匙/门状态、环境动作数、非法行动数与终止状态；地图静态布局（包括隐藏目标坐标）由固定地图版本重建。Agent 知识投影另存当前位置、持有资源、已探索格及每格最后已观察到的事实/时间点。恢复分别校验权威状态与知识投影版本和合法组合；不得从权威全图重新生成 Agent 已探索记忆。
- 钥匙为单个、匹配门的资源；成功使用后**消耗**，门保持开启。钥匙消耗和开门是同一次原子状态转换，不允许出现门开而钥匙未消耗或相反的中间状态。目标成功条件是 Agent 进入目标格；不要求额外提交答案。

### 行动及失败语义

注册单步、单调用工具：`move_up`、`move_down`、`move_left`、`move_right`、`inspect`、`pickup`、`use`。移动/检查/拾取工具不带参数；`use` 只接受观察中获得的精确 `target_id`，首图使用 `door-amber`。所有 Schema 严格拒绝额外字段。

- `move_*` 进入墙、越界或关闭的门：位置不变，增加行动数和非法行动数，返回本地可理解的阻挡反馈。
- `pickup` 仅在当前位置有未拾取钥匙时成功；否则为非法游戏行动，不抛出运行时异常。
- `use` 仅在与可见目标门相邻、门未开且持有匹配钥匙时成功；否则状态不变并增加非法行动数。目标不存在、不可见或不相邻时统一返回 `target_unavailable`，不用于探测隐藏地图。
- `inspect` 产生当前位置的局部观察并增加行动数，不改变钥匙、门或位置。
- 首题最多允许 **16 个到达环境的游戏动作**，单次模型响应最多一个动作；不启用 Planning、Reflection 或批量工具。首题将 `TaskSpec.max_steps=16`、Agent `Budget.max_steps=16`、`Budget.max_model_calls=16`、`Budget.max_tool_calls=16` 固定为一轮一动作。当前 `BudgetTracker` 的有效 Runtime 轮次为 `min(TaskSpec.max_steps, Budget.max_steps)`；因此第 16 个模型请求可执行第 16 个动作，而若动作未通关，Runtime 在准备第 17 个模型请求前由 `can_call_model()` 拒绝，终止为 `MAX_STEPS / max_steps_reached`。明确**不接受第 16 个未通关动作后的额外模型请求**，避免支付一次不能再执行新动作、且 `FinalAnswer` 也不会使环境通关的请求。`max_tool_calls=16` 是第二道保护，不依赖第 17 个动作被模型提出后才终止。
- `step_count` 仍是 Runtime 模型轮次，环境 `action_count` 是已送达 Environment 的动作数，两者不得混写。工具权限/schema 在环境之前拒绝的提案不是游戏动作，但会消耗模型轮次；故某些非法提案会使 Episode 在少于 16 个环境动作时按 `MAX_STEPS / max_steps_reached` 结束。环境内被规则拒绝但通过 Schema 的动作会消耗一个工具调用、环境动作和 Runtime 轮次；这类游戏规则拒绝应作为正常工具回执中的结构化结果返回，不设置 `StepResult.error`，否则现有 Runtime 会立即以 `FAILED` 停止。Token、时间及费用等独立限制若更早触发，保留其原有终止 detail；Token 的单次/累计边界及当前动作是否执行以 [ADR-046](./ADR-046-gridworld-visibility-and-budget.md) 为准：响应超出单次或累计硬边界时，完整记账但拒绝该响应的动作；累计 Token 恰好达限时，当前已通过 Schema/权限验证的单个动作（含规则内拒绝）允许完成，随后不再发送下一次 Provider 请求。
- 动作先应用确定性状态转换并记录反馈，再检查是否成功。第 16 个动作进入目标时，Episode 以 `SUCCESS` 结束优先；否则该动作完成后直接以 `MAX_STEPS / max_steps_reached` 终止，不请求模型、也不执行第 17 个动作。首切片应使用此任务配置的固定值，不得静默提高步数以“补救”。
- 首切片不支持 `communicate`、批量行动、多个 Agent、随机地图、地图编辑器、资源合成或外部写入。

### Agent 可见信息与回放

- 每次 reset 和动作后返回当前观察。观察由当前位置及四条正交射线构成，每条最多向外两格，不含对角线；射线显示阻挡格本身，并在墙或**关闭的门**处停止。关闭门挡住的门后格不会仅凭观察门而被揭示。
- 成功开门后，门格在未来观察中显示为已开启且可通过的门；每条射线的总可见距离仍不超过起点外两格：若第 1 格是已开的门，可见射线经过该门并显示紧接着的第 2 格。以 Agent 位于 `(2,2)` 为例，可看到门 `(3,2)` 和门后的 `(4,2)`，但看不到 `(5,2)`。墙或另一扇关闭门仍会阻断射线。此前被门遮挡、现进入视线范围的格子才在这次新观察中加入已探索集合。
- 已探索信息是 Agent 的**最后已知记忆**，不是对全图当前状态的查询：离开视野后复用当时观察到的地形/实体状态；动态实体仅在再次进入视野或由 Agent 自己执行且已确认成功的动作改变时更新，未知仍为未知。恢复时原样恢复此知识投影，不用当前完整地图反向补齐。钥匙是否已消耗只通过 Agent 自己的资源状态和成功动作反馈体现，不暴露地图私有数据。Agent 视角历史仍只显示相应事件到达时已揭示的信息。
- Agent 可见投影可包含当前位置、已知地形/实体、持有资源、本次动作反馈和公开行动计数；不得包含完整地图数组、未发现坐标、隐藏目标状态/坐标、`goal_conditions` 或 Evaluator 的内部状态。
- 权威全图/状态只用于服务端环境转移、独立 Evaluator 和明确标注的观察者全局视图；不得注入 Provider 消息或普通 Agent 视角 Trace/API 投影。Agent 视角 Trace 只保存真实发生的动作与当时发出的 Observation。若现有 `Environment.snapshot` / `ENVIRONMENT_UPDATED.state` 接口无法将私有可恢复状态与 Agent 可见 Trace 投影分开，应在实现前另提核心接口/事件 ADR，不得把全量 Snapshot 直接塞入 Agent 可见事件。
- 历史 Agent 视角必须由当前事件前缀重建，不能拿最终全图、最终发现集合或未来动作覆盖早期游标；历史 GET/刷新不重跑 Episode。观察者全局视图必须显式标记其来源是服务端权威状态，不得伪装成 Agent 当时观察。

### 接入、版本与持久化

- 实现应符合现有 `Environment.reset / available_tools / step / snapshot / restore`，经共享工具校验与 Executor 执行动作，并使用既有 `TaskSpec`、`RunConfig.environment_version`、Trace 和 `Evaluator`。任务与 Agent 固定步数配置及模型调用/工具调用上限如上；权威环境快照与 Agent 知识投影分别按前述边界保存。固定任务路线 8 步必须通过各 Runtime/Episode 入口。若实现中不能隔离私有快照与 Agent 视角事件，先提出独立 ADR，不得静默改核心契约。
- 单次产品接入需核对 `apps/api/service.py` 的新建与 `_saved_environment` 恢复分支、正常/实时 API、历史读取与 Replay、`packages/application/checkpoint.py` 的版本校验，以及 SQLite Episode/安全点保存。任务和环境版本进入已保存来源；不覆盖现有 ToolLab 版本和历史。
- 第一交付切片依次为：确定性环境与契约/单元测试；Fake 单次 API、真实实时事件与事件前缀回放；快照保存、进程重启恢复和历史只读；最后才考虑同条件 Experiment。Experiment 构造目前有 ToolLab 专用路径，未接通前不宣称 GridWorld 可用于对照。
- 初版优先复用现有 SQLite JSON 载荷，不新增数据库、公开通用指标或依赖。若地图/观察/快照必须改变现有公开 Schema 或事件格式，先提交协议 ADR 并明确旧产物兼容规则。

### 评价和资源边界

Evaluator 只读完整环境状态与发生过的 Trace，判定是否确实拾取匹配钥匙、打开门并进入目标；报告成功/终止原因、动作步数、非法行动数、钥匙拾取与门开启情况。第一切片不增加综合分数，也不报告路径效率/最短路径。若后续报告最短路径，必须明确其是使用完整地图的全信息参照，不能等同于 Agent 实际观察路径。

手算路径是 **8 个环境动作**：`move_up → move_right → pickup → move_down → use(door-amber) → move_right（进入原门格）→ move_right（到 x=4）→ move_right（进入 G，x=5）`。开门工具 `use` 本身不移动位置，故从相邻位置到目标还需经过门格及其后一个地格。用于机制验收的固定动作序列不代表模型结果；自动化和初次浏览器演示只用 Fake，不需要真实模型/Judge 授权。

## 必需验收

1. 固定地图和任意 Seed 下 reset、动作与快照哈希可复现；不同地图/环境版本被明确拒绝恢复。
2. 8 动作手算路线成功；钥匙与开门原子消耗、开门后视线揭示/遮挡符合规则；已探索但不在视野中的动态实体保持最后已知状态，恢复不补入隐藏变化；墙、边界、未持钥匙、错目标、关闭门、重复拾取、非法 `use` 的状态与计数符合规则。
3. 固定预算下通关动作可在第 16 轮成功；若第 16 个有效动作未到目标，结果必须是 `MAX_STEPS / max_steps_reached`，第 17 次 Provider 请求数为零、第 17 个环境动作数为零。非法参数消耗 Runtime 轮次但不增加环境动作；更低 Token/时间等预算仍按其自身终止 detail。
4. 每个工具观察均满足射线范围/遮挡；权威快照可用于恢复但不混入 Provider 输入、工具回执或 Agent 视角 Trace/API。测试隐藏目标坐标、完整地图和 Evaluator 私有字段不会提前泄露；明确标注的观察者全局视图才可呈现权威状态。
5. 快照恢复后位置、资源、已开门、已探索信息、环境动作数及终止状态一致；恢复后只发新事件，不重复模型/工具调用；旧 ToolLab 安全点、任务和历史回读不变。
6. 实时展示与历史 Replay 只反映已到达事件前缀；直接 GET、刷新和 URL 导航不触发 POST。
7. API/Web Fake 闭环覆盖目标成功、非法行动、预算边界、错误 ID、保存/恢复和无后端错误页之外的实际 Episode 回读；报告实际 Episode ID 与 Trace。

## 风险与实施边界

- 地图、可见射线、非法动作计步、模型轮次/动作数上限映射、最后已知状态与钥匙消耗为已批准规则；本阶段仍须通过自动化契约验证，后续变更须另提 ADR。
- **私有快照与 Trace 隔离为持续安全不变量**：Runtime 将私有 `snapshot()` 用于 Session checkpoint，将 `public_state()` 用于 Observation、Trace 与最终公开产物。工具、评估、投影或恢复失败时不得将私有快照回退到公开事件/产物。若需超出本 ADR/ADR-046 的 Domain Port、Trace 语义或公开 Schema 改动，另提并获批协议 ADR。
- `StepResult` 的通用 `done/error` 必须保留“游戏规则非法但工具交互成功”的区分；规则内非法动作用结构化 observation 回执继续运行，真正的工具/环境故障才使用 `error`。
- 固定 Episode 预算见已批准的 [ADR-046](./ADR-046-gridworld-visibility-and-budget.md)。
- 隐藏信息是相对 Agent 的部分可观测边界，不是访问控制或机密数据保证。UI 的观察者视图必须显式标注。
- V0.3 整版与 ADR-045/046 均已获负责人批准；本次首阶段不包含实时 Web、跨进程恢复、GridWorld Experiment、真实模型/Judge 或 GitHub 写操作。

## 参考实现入口

- `packages/domain/ports.py`：Environment/Evaluator 接口。
- `packages/environments/tool_lab/environment.py`：现有受控环境与工具执行模式。
- `apps/api/service.py`：单次环境构造与 `_saved_environment` 版本恢复。
- `packages/application/checkpoint.py`：快照及环境版本检查。
- `packages/application/experiment.py`：当前 ToolLab 专用对照构造。
- [V0.4 GridWorld 开发规范与首片任务卡](../tasks/V0.4-gridworld-development-spec-20261105.md)：批准后的阶段顺序及兼容/验收矩阵。
