# M1 给 Antigravity 的开发交接

**状态：M1 已启动，ADR-003/004 Accepted；切片 A 已签收，切片 B 的基本网页流程已复核，当前执行切片 C。** 需求唯一来源是 `docs/product/requirements.md` V0.5；本文件指导已授权切片，不替代需求。切片 C 的具体范围见 `docs/tasks/M1-slice-C-antigravity.md`，BFCL 已顺延至切片 D。

## 1. 启动前阅读与分工

按 `AGENTS.md` 的顺序阅读需求全文、ADR-001/002/003/004、`docs/handoffs/current-state.md`、当前任务卡、相关测试与源码。不要以本交接代替需求。

- **Codex 先做**：让 M1 范围进入需求和 Accepted ADR；决定下文 3 个契约阻塞点；只建立必要的公共接口、迁移约束和契约测试。核心 Schema、Runtime、预算与评测口径由 Codex 审查。
- **Antigravity 随后做**：按已接受契约实现 Provider、数据 Adapter、API、页面和相应测试。以一个能跑通的端到端切片为单位交付，串行修改；不同时编辑同一文件，不覆盖未知改动。
- **项目负责人**：在本机后端环境设置 `AIHUBMIX_API_KEY`，不把 Key 发到聊天、截图、仓库或浏览器；确认现场联网。Gemini 的真实成功结果已留存，其他模型仍按各自实测状态标注。

## 2. 已选真实模型与最小探针

2026-09-18 核对用户截图与 [AIHubMix 模型页](https://preview.aihubmix.com/model/coding-kimi-k3-free)：页面名 **Coding Kimi K3 (free)**，请求中的准确 ID 是 **`coding-kimi-k3-free`**，不是口头简写 `kimi-k3-coding`。OpenAI 兼容的 `base_url` 是 `https://aihubmix.com/v1`，接口为 Chat Completions。页面公布 5 次/分钟、100 次/天、100 万 token/天，并宣称支持工具调用；这些是页面信息，不是本项目实测保证。不要把免费价格永久硬编码为事实。

启动开发后的第一个联网验证只跑小请求：先普通回答确认认证和连通性，再用一个无副作用工具 schema 让模型生成 **恰好一个** `tool_calls`，核对 `id`、函数名、JSON 参数、`finish_reason`、`usage`。若普通回答成功但工具调用缺失，记录原始结构的**脱敏摘要**并停止“真实工具调用已通过”的宣称；不得用解析自由文本伪装为原生工具调用。探针限制输出 token，关闭流式，设置有限超时；仅在确认限额行为后安排批量请求。密钥只在后端读取，报错不回传供应商原文、请求头或 Key。

Provider 只实现现有 `ModelProvider.generate` 的边界映射：公开消息与工具 schema → 供应商请求，响应 → `ModelResponse`。供应商 SDK 对象不得越过 Provider；工具仍由 Registry/Executor 校验并执行。无 `usage`、无 `tool_calls`、参数 JSON 无效、多条工具调用、429、认证失败、网络超时、5xx 均需有明确、脱敏的失败结果，不可静默降级为成功或丢弃额外调用。自动重试次数与节流策略先按 ADR 决定，避免免费额度被重试耗尽。

## 3. 编码前必须裁决的契约阻塞点

1. **多轮工具调用消息**：当前 `HandwrittenRuntime` 收到工具调用后只追加 `role=tool` 反馈，下一轮没有相应的 assistant `tool_calls` 消息；而现有 `Message` 也没有结构化 assistant 工具调用字段。真实 Chat Completions 的多轮消息组装必须能保留 call ID 的完整关联。Codex 先定 Domain/Provider 边界与旧 Trace 兼容方案，并通过两轮真实格式的契约测试；不能靠 Provider 猜测或重写历史消息。
2. **真实 usage 与费用**：当前 `BudgetTracker.total_token_usage()` 固定 `simulated=True`，`total_estimated_cost()` 固定 `fake-zero-v1`，`EstimatedCost.amount` 不能表示未知。Codex 先决定真实 token 缺失、价格未知、预算如何保守处理，以及 schema_version 和旧 JSON 迁移；不能把未知费用记为已验证的 `$0`，不能把真实 usage 标成模拟。
3. **BFCL 题目与 Runner**：M0 `TaskSpec`/Runner 的成功路径偏向“工具执行并提交订单”；BFCL 的 simple/multiple 单轮题目是工具选择与参数生成。Codex 先确定单轮调用的 Adapter、终止/评价结果及 Trace 口径。不要把 BFCL 伪装成订单任务，也不要把 BFCL 评分塞进通用 Runtime。当前 `ModelResponse` 一次只支持一个动作，所以首版只选适配的单调用题目。

上述问题如果无法在现有 Port 下正确表达，先提出小范围 ADR、兼容测试，再改契约。不要为了赶 UI 先硬塞临时字段。

## 4. 真实数据集接入规范

首个外部数据选 [BFCL 官方仓库](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard)的**非 Live、单轮、单工具调用**小子集：simple 验证参数生成，multiple 验证工具选择。官方[数据说明](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/bfcl_eval/data/README.md)说明这两类的一道题只要求一次函数调用；不含 parallel、Live、搜索、需执行真实外部工具的题。实际选题要检查锁定版本的每个样本和答案，不凭类别名假设全可用。

先锁定上游完整 commit SHA、原始文件 SHA256、题目 ID 清单、筛选规则、代码及数据许可。默认 **Reference Adapter**：按固定版本获取原始数据、本地转换，不整包复制进仓库。只有锁定版本的许可证明确允许时才考虑提交转换快照，并保留 attribution。机器可读 `dataset_manifest` 至少含 SSOT 9.7 的 `source_name`、`source_url`、`source_version_or_commit`、`code_license`、`data_license`、`upstream_dependencies`、`import_mode`、`transformation_script`、`checksum`、`attribution`、`redistribution_allowed`、`official_protocol_compatible`；另记选题 ID、排除理由和本地评测器版本。

开发样本与展示评测样本分开，固定后不得静默换题。转换测试检查题数、ID 唯一、工具 schema 合法、原始文件哈希一致；评分测试用明确的正例、错工具、错参数和无调用负例。结果必须显示 **`AgentLabyrinth-adapted subset`**、分母、题目版本、评分规则及转换偏差。只有完整复现官方任务、工具、提示、环境和评分器时才能称官方 BFCL 分数；本计划不满足该条件。ToolLab 与 BFCL 各自展示指标，不合成“总分”。

## 5. 最小开发切片与验收证据

| 顺序 | Antigravity 实施重点 | 可交付证据 |
|---|---|---|
| A. 模型闭环 | 已定契约后接后端 Provider，先用真实 Kimi 跑 ToolLab CLI 一次；Fake 保留 | 脱敏请求配置、真实响应 usage/工具调用摘要、完整 JSON Trace、失败路径；无 Key 的自动测试 |
| B. 网页闭环 | FastAPI `/api/v1` 接 Runner；React/Vite 做实验配置、结果、Trace 三个视图；先接 ToolLab | 浏览器启动真实 Episode、刷新后读取保存结果、手机与桌面截图；前端网络请求无 Key |
| C. Agent 对照 | Baseline/Recovery 在相同条件下串行运行；4 条原生任务；汇总与成对 Trace | Fake 的确定性恢复证据、公平性检查、真实 Gemini 探索性结果、Experiment JSON |
| D. 外部子集 | 切片 C 验收后固定 BFCL 版本与 manifest，单轮 Adapter 与独立评分 | 样本 ID/哈希/许可与转换报告、正负评分测试、真实模型子集运行结果 |
| E. 演示完善 | 按步回放、导出与重读、明确状态与错误文案 | 现场脚本，从启动到真实结果与回放；断网、限额和无 Key 情况可解释 |

一个真实 ToolLab Episode 已从 CLI 进入网页。现在先证明 **Agent 策略变化能够在固定条件下被比较**，再接 BFCL。每步完成即保存一个可演示版本；复杂图表只在真实需求和额度允许时增加。页面不能用静态假数据冒充真实结果：显示模型 ID、Agent 版本、真实/Fake 标识、Suite 来源、运行时间、样本分母、成功/失败、步骤、token、时延、费用“已知/未知”；Trace 回放只读 JSON，不再次调用模型。

接口统一校验 `schema_version`、返回 `request_id` 与安全错误码；前端不保存 Key、不显示隐藏思维链。保存配置、来源、运行结果、Trace、评分和适配版本，读取时再次严格校验。真实模型执行采用低并发与运行前请求数提示，先保守控制在页面公布配额内；遇 429 显示“额度/速率限制”，不要无限重试。API 不能返回供应商原始 SDK 对象或本机绝对路径。

## 6. 代码质量与交付格式

遵循 SSOT 的 Python 3.12、uv 锁定依赖、Pydantic v2、pytest、Ruff、mypy；公共函数类型完整，费用 Decimal，时间 UTC，持久化边界版本化。新增依赖先说明现有依赖/标准库为何不够。无实际使用的数据库、Provider 工厂、任务编辑器、第二个 Benchmark 或部署配置不建。

每个切片交付时附：修改文件、源码阅读顺序、调用链、状态变化、停止/失败路径、脱敏的真实运行命令与结果、Fake/Mock 测试结果、尚未验证项；更新 `docs/handoffs/current-state.md`。运行 `./scripts/check.ps1` 并报告**实际**结果；没跑过不能说通过。Codex 对契约、预算、数据评分和密钥边界复核后再进入下一切片。不自动初始化 Git、提交、推送、打 Tag 或发布。

## 7. 当前事实与启动条件

- 现状已有 M1 Provider 与 M0 Fake + ToolLab；`gemini-3.7-flash-free` 已完成真实多轮工具调用和独立评测，Kimi 通道仍不可用，BFCL 数据尚未下载。
- 用户已取得 API Key，但本交接不包含、不读取、不保存 Key；后续 Provider 仅从环境变量读取用于调用，不打印值。
- 切片 B 以已验证的 Gemini 和 Fake 建立网页闭环；其他免费模型维持真实实验中观察到的状态，后续放宽参数格式或预算需独立审查。
