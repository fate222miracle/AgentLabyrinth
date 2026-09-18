# 课程演示平台调研（2026-09-17）

**状态：仅调研。** 当前 SSOT 仍是 `docs/product/requirements.md` V0.5；本文和 Proposed ADR-003、M1 草案任务卡均未授权产品编码或改变既有验收。四个月是课程交付的最晚窗口，项目负责人希望能尽快完成；开发启动后应先尽快做出可联网、可从网页操作的演示，再逐步加外部数据和完整展示。

## 结论

建议把演示做成两条可解释的实验线：现有 ToolLab 展示 **Agent 在模拟环境中查询、取得证据、提交和被评测的多轮行为**；BFCL 的固定非 Live 子集展示 **真实模型在国外公开题目上的工具选择与参数生成**。两者从同一网页启动和查看，但分别标明数据来源与评分口径。BFCL 只覆盖工具调用能力，不能代表完整 Agent 能力。

第一次外部数据接入建议 BFCL；暂不选择 AgentBench 或 τ-bench 作为首个实现。BFCL 官方将非 Live 题目分为 simple、multiple 等类别，且其评测工具支持局部题目；一旦转换为本项目的环境或评分器，就必须标成 `AgentLabyrinth-adapted subset`，不能引用官方榜单分数。[BFCL 数据说明](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/bfcl_eval/data/README.md) · [BFCL 局部评测说明](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/README.md)

## 数据集选择

| 候选 | 能展示什么 | 首次接入判断 |
|---|---|---|
| BFCL 非 Live | 工具选择、参数生成；可选一轮单工具题目 | 最适合第一个固定子集，按上游 commit、题目 ID 和 SHA256 锁定。上游说明将数据标为 Apache-2.0，实施时仍要核对锁定版本的 LICENSE。 |
| AgentBench | 多环境中的 Agent 行为 | 当前官方仓库的功能调用版依赖容器及任务服务；首次演示的部署成本高，留给后续组员评估。 |
| τ-bench | 工具 Agent 与模拟用户的领域交互 | 原仓库提示任务版本已过时并指向 τ³；且需模拟用户模型，首版成本与变量较多。 |

依据：[BFCL 官方数据说明](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/bfcl_eval/data/README.md)、[AgentBench 官方仓库](https://github.com/THUDM/AgentBench)、[τ-bench 官方仓库](https://github.com/sierra-research/tau-bench)。

数据接入研究清单：确定上游 commit；确认代码和数据的精确许可；列出选题 ID 与筛选规则；保存原始文件校验值；区分开发集与演示评测集；记录本项目的工具映射和评分差异。默认按需获取上游数据，不把整个数据集复制到仓库。

## 真实模型 API

用户已取得 AIHubMix Key，课程网页需要联网调用。2026-09-18 根据用户截图和[模型官方页面](https://preview.aihubmix.com/model/coding-kimi-k3-free)核对，所选免费模型的请求 ID 是 **`coding-kimi-k3-free`**（不是口头简写 `kimi-k3-coding`）。AIHubMix 官方 Quick Start 给出 OpenAI 兼容的 `https://aihubmix.com/v1/chat/completions` 和 SDK `base_url=https://aihubmix.com/v1`。后端通过现有 `ModelProvider` Port 映射消息、工具与响应，Key 只从后端环境变量 `AIHUBMIX_API_KEY` 读取；网页不直接调用网关，也不保存 Key。[AIHubMix Quick Start](https://docs.aihubmix.com/en/quick-start)

模型页标示工具调用能力、5 次/分钟、100 次/天、100 万 token/天；这是页面公布的额度，尚未由本项目实测。实际开发前需用用户本机 Key 跑一次普通请求和一次小型工具调用探针，记录模型 ID、`tool_calls` 结构、usage、响应时间及错误路径。**用户已有 Key，但本项目尚无真实 API 实验结果；Key 不应提供给聊天或保存到仓库。** Fake 仍用于自动化测试和解释环境行为，现场验收必须另有真实调用。[AIHubMix 模型页](https://preview.aihubmix.com/model/coding-kimi-k3-free)

## 第一版网页的演示路径

1. **实验台**：选择 ToolLab 或 BFCL 改编子集，选择已实测的模型，设置最大任务数/步骤/Token/费用，启动实验。显示预计调用次数与数据来源。
2. **结果页**：先看成功次数/总数、工具选择和参数有效率，再看步骤、Token、费用是否可得及时延；能点开失败任务。明确标识“真实模型”或“Fake”、“原生任务”或“改编子集”。
3. **轨迹页**：左侧按步骤显示 Observation、模型提议、校验、工具反馈，右侧显示状态和证据。Replay 只读取保存的 Trace，不再次请求模型。

视觉建议：深蓝灰底色、冷青色强调色、克制的状态色；大数字用于核心指标，小图用于任务间比较；运行进度、空状态、网络错误和免费额度耗尽都要有明确文案。桌面优先，同时保证手机宽度可操作。视觉质量通过真实数据、清晰层级与一致组件实现，避免只做静态大屏。

## 现有代码与缺口

M0 已有 `run_episode → HandwrittenRuntime → ToolLab → Evaluator → JSON Trace`，39 项测试通过。现有 `ModelConfig` 只允许 Fake；一轮 `ModelResponse` 只表示一个 ToolCall 或 FinalAnswer；订单任务的工具与评分规则是固定实现；尚无 Web API、前端、批量运行与外部数据 Adapter。接 AIHubMix、BFCL 或改变费用未知值表示，先更新 SSOT 并通过 ADR 定义 Schema、兼容和评分口径；不能把外部 SDK 类型放入 Domain，也不能把 BFCL 逻辑塞进通用 Runtime。

## 最快可演示路径

四个月只作为缓冲与课程截止窗口，不把首个闭环排到第一个月末。**建议目标**（从确认开始开发且本机 Key 可用时起算，依实际验证调整）：

| 顺序 | 目标时间 | 可验收产物 |
|---|---|---|
| 1 | 前 2–3 个工作日 | Codex 定必要 ADR/契约，Antigravity 接通 AIHubMix 与现有 ToolLab；真实 CLI Episode 有 Trace。 |
| 2 | 第 1 周 | 网页可选模型并运行 ToolLab，显示一次真实 Episode 的结果和轨迹；形成第一版可讲解演示。 |
| 3 | 第 2 周 | 固定 BFCL 非 Live 小子集、来源 manifest、独立评分接入同一入口。 |
| 4 | 第 3 周 | 结果对比、Replay、视觉细节、故障提示和现场演示脚本完善。 |

每一步完成即可演示，不等后一阶段；从真实调用和可读 Trace 验证开始。剩余时间用于组员扩展任务、对照实验、报告、视频及稳定性，按实际课程要求决定是否需要。以上是调研阶段的目标，不是已承诺工期。

## 给 Codex / Antigravity 的后续交接

确认进入开发后，Codex 先更新 V0.5 SSOT、把 ADR-003 及必要的 Schema ADR 定稿，给出 Provider、数据 Adapter、API DTO 的接口和关键验收测试。Antigravity 再按 `docs/tasks/M1-course-demo.md` 填充 Provider、API、前端和数据转换的内部实现；Codex 最后审查并复跑真实/Fake 实验。继续串行开发，不同时修改同一文件，不自动初始化 Git、提交或推送。

首个真实模型验证只需项目负责人在本机后端环境配置 Key；已核对模型 ID 为 `coding-kimi-k3-free`。不要把 Key 发进聊天、仓库文件或 Trace。可执行的后续开发规范与契约阻塞点见 `docs/handoffs/M1-antigravity-development-guide.md`，目前仍是调研交接。
