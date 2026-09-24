# Current state

更新：2026-09-24。需求唯一来源：`docs/product/requirements.md` **V0.6**。不依赖历史聊天。

## 2026-09-24 Replay 与配置 UI 调研

用户指出逐事件卡片难读、单次配置表单单调。调研与可执行设计建议见 `docs/research/replay-config-ui-20260924.md`：默认以 Agent Step 呈现「模型决定→工具反馈→状态变化」，原始事件留在技术 Trace；配置改为任务/执行选择加运行前核对、高级设置渐进展开。实际 Artifact 核查：BFCL `4716ca38-5f67-4f6d-8239-a5488541826b` 为 1 步 10 事件，MCP `c302b854-5a35-4ec7-b1b5-749b417e59e0` 为 3 步 24 事件；事件级 duration 多为 0，目前不能画准确阶段耗时瀑布。本轮仅调研和文档，UI 尚未改动；实施应保持需求 V0.6 和现有 Replay 只读契约。

## 2026-09-24 MCP 网络工具小切片

按 Accepted ADR-012，在需求 §0.4 明确课程实验例外。锁定官方 `mcp==2.2.0`，新增独立 localhost Streamable HTTP 服务和真正 SDK Client。首批只远程执行固定 ToolLab 文档任务的 `search_documents`、`read_document`；其余 Runtime/Registry/Executor/Evaluator 继续走原有契约。API 单次运行新增 `tool_transport`，Web 按任务能力展示 MCP 选项，RunConfig 记录传输版本。MCP Episode 有最终 Artifact，暂不提供 Checkpoint/Resume；原本地路径照常恢复。

实测：两个进程的 `tools/list` 返回两种工具，HTTP POST 200。Fake `order-status-007` 同配置本地/MCP 均 SUCCESS、Evaluator true、3 次工具，均为 120 prompt / 60 completion tokens；单次实测本地 32 ms、MCP 200 ms，仅是样例。关闭 MCP 服务后远程 FAILED `tool_failed: TOOL_EXECUTION_ERROR`，Trace 包含 `TOOL_STARTED → TOOL_FAILED → EPISODE_FINISHED`；本地仍 SUCCESS。结果记录在 `docs/learning/V0.2-mcp-network-pilot.md`。Fake 成绩不作为模型能力成绩。

追加一条真实模型探索样本：2026-09-24 Key 级目录仍可见 `coding-minimax-m2.7-free`；该模型在 `order-status-007` 经 MCP 获得 SUCCESS、Evaluator true，Episode `c302b854-5a35-4ec7-b1b5-749b417e59e0`，3 次模型调用、3 次工具调用、3108 prompt / 280 completion tokens。Trace 中搜索与读取标记 `transport=mcp`，本地提交无该标记。仅一题，不能作为稳定可用性或能力排名。该样本使用独立服务进程和 Service 入口；浏览器 MCP 交互仍待人工验收。

启动验收：重启 API 时清除了本机继承的失效 `127.0.0.1:9` 代理；`/api/v1/meta` 经前端代理返回 `catalog=live` 和四款真实模型。MCP 服务列出两种文档工具。经网页同源 `POST /api/v1/episodes` 运行 Fake MCP 得到 Episode `54881a8d-3013-4712-8544-2cdab7c286db`，HTTP 201、SUCCESS、3 工具；同源 GET 回读 200、24 事件。真实 MiniMax Artifact 已放入 API 默认产物目录，浏览器 `?episode_id=c302b854-5a35-4ec7-b1b5-749b417e59e0` 实际显示 SUCCESS、`工具传输：MCP HTTP`、3388 tokens 与 24 个 Trace 事件；页面草稿已选文档任务 007 与 MCP。浏览器尚未亲自点击「开始运行 Episode」发起新一轮模型调用，这项操作由演示者自行执行即可。

质量门禁：Ruff 与 mypy 针对改动文件通过；前端生产构建通过。沙箱内全量 pytest 因系统临时目录权限失败，获准常规进程重跑为 **169 passed、1 条既有依赖 warning**（MCP 回归测试已计入）。启动见 README。现有工作区包含多轮未提交改动，勿整体回滚或覆盖。

## 2026-09-23 V0.2 Checkpoint/Resume 核心实现

ADR-011 已 Accepted。`packages/runtime/session.py` 与 `packages/runtime/handwritten/budget.py` 保存可迁移 Session/预算；Reference 和 LangGraph 共用同一安全点，`packages/application/checkpoint.py` 将 ToolLab 单 Episode 的 Agent/Task/RunConfig 哈希、Trace、消息、Call ID、环境快照与预算原子写入本地 JSON。恢复时重建环境与 Trace，追加 `EPISODE_RESUMED`，Runner 仍独占唯一 `EPISODE_FINISHED`。完成的 Artifact 优先只读回放；损坏或不匹配的 Checkpoint 拒绝恢复。外部工具与 BFCL 不在此实现边界内。

可复现实验：`tests/integration/test_checkpoint_resume.py` 分别让 Reference 与 LangGraph 子进程在第一次工具成功后的安全点退出，主进程重新构造 Runtime、Provider、Environment 并恢复；两组均成功，累积 2 次模型调用、2 次工具调用、80 prompt tokens，已完成工具没有重放，Trace 因果链连续且只有一次终止事件。篡改 Task 后恢复拒绝，正常完成后 Checkpoint 清理也通过；Fake 参数纠错场景恢复通过。新增 5 项测试通过；项目全量测试为 **168 passed、1 条既有 Starlette/AnyIO warning**。Ruff、mypy 全项目及 Web 构建通过。

本轮继续将 ToolLab 单次运行接入 Checkpoint 入口，BFCL 保留原入口。API `GET /api/v1/episodes/resumable` 仅列出本次服务启动前留下、尚无最终 Artifact 的 ID，`POST /api/v1/episodes/{id}/resume` 使用原 Agent/Task/RunConfig、Fake 场景或真实模型重建执行；同进程正在恢复的 ID 暂时隐藏并拒绝重复恢复。Web 单次运行区显示待恢复 ID 和重发模型请求可能增加用量的提示，成功后进入同一 Episode Trace/URL。前端生产构建通过；跨进程测试已通过 FastAPI TestClient 验证两个 Runtime 的列表/恢复/回读。另补测 Fake `invalid-then-success` 在参数纠错安全点中断后恢复成功（3 模型调用、2 工具调用）。

浏览器故障演练已完成：子进程在第一次成功工具后退出，重启本机 API，页面识别待恢复 ID `2315b4b2-4001-4e74-8807-7073ba77cafb`；点击恢复后显示 SUCCESS、2 模型调用、2 工具调用、18 条 Trace（含恢复事件）、原 Episode URL。刷新后 SUCCESS 与恢复事件仍在。**真实模型请求中断恢复尚未实测**。ToolLab 内存工具的恢复保证不能推广到外部写入工具。源码阅读和调用链见 `docs/learning/V0.2-checkpoint-resume.md`。

## 2026-09-23 V0.2 课程交付推进：实验 CSV

已在 Web 已保存 Experiment 的导出栏增加 CSV，按每个 Episode 一行展开成对任务，带 Experiment ID、配置哈希、对照轴、Task/Seed/Repeat、运行侧、判定、工具与模型调用、Token、耗时、费用及工具指标。Reference/LangGraph 侧别与恢复策略侧别分清；未知费用及 Runtime 对照不适用的恢复指标留空；中文 UTF-8 BOM、字段转义与表格公式防护已加入。原 JSON 导出仍使用同一下载入口，不修改 API/Artifact 或评分口径。

`npm.cmd --prefix apps/web run build` 已在可启动 esbuild 的进程中通过（27 modules），`git diff --check` 返回 0。受限沙箱首次构建因子进程 EPERM 失败，常规进程重跑通过。用历史实验 JSON 提取前端 CSV 函数做一次执行自检，并生成被 Git 忽略的样例 `artifacts/exports/agentlabyrinth-experiment-ad386c5d-6458-4a59-b88b-7ed534b18ae6.csv`；Python 标准库 CSV 解析得到 2 Episode 行、20 列，Reference/LangGraph 标签与不适用恢复字段留空正确，公式/引号转义自检通过。Codex IAB 已回读该历史 Fake Experiment，看到 1 Pair、2 Episode、对照表与新增 CSV 按钮，并检查 730px 下 JSON/CSV 同行布局；IAB 下载事件两次等待超时，因此**浏览器点击后下载文件内容尚未验收**，不能宣称下载交互实测通过。当前改动与后续 Checkpoint/Resume 准入见 `docs/tasks/V0.2-m2-course-reliability.md`，决策见 Accepted ADR-011。本段 CSV 工作未运行新真实模型；Checkpoint 核心进度见上方。

## 2026-09-23 新增免费模型验收

用户将 MiMo V2.6 Pro Free 与 Coding GLM 5.3 Free 加入 AIHubMix Key 范围。官方主域 Key 级 `/v1/models` 现可见四款：新增两款及 MiniMax M2.7、MiMo V2.5 Pro。新增两款分别通过真实 BFCL `simple_python_0` 和 ToolLab `order-status-001`，共 4/4 个探索性 Episode 成功，均有真实模型、工具调用与 Trace。ID、Token、复现命令及边界见 [新增免费模型实测](../experiments/new-free-models-20260923.md)。目录已加入两款实验性候选，MiniMax 保持默认；本机 `/api/v1/meta` 当前为 live，返回这四款及 Fake。单题成功不代表全量能力或长期可用。

## 2026-09-23 AIHubMix 网络与模型目录复核

- 真实模型失败根因：Codex 沙箱启动的 API 进程继承失效代理 `127.0.0.1:9`，两次请求耗时约 200 ms、Token 为 0，错误为 `NETWORK_CONNECTION_FAILED`。已用无该沙箱代理的进程重启本机 API；不是 MiMo 模型请求格式或 Tool Schema 问题。
- 本日较早时，官方主域 Key 级 `/v1/models` 返回 200，当时只可见 MiniMax M2.7 Free、MiMo V2.5 Pro Free；用户随后扩充 Key 范围，新状态见上方。后端在 `/api/v1/meta` 做 5 分钟缓存交集过滤；目录服务失败时暂时隐藏真实模型。真实执行也会检查模型是否仍在该 Key 目录。
- 默认模型改为 `coding-minimax-m2.7-free`。MiniMax Episode `032ac2bb-0ae7-4b30-b9d0-4db9ef3becdb` 与原截图 MiMo 重跑 Episode `24b010eb-22f9-4f04-b2b6-c954d256239f` 均完成 BFCL `exact_call_match`，各 1 模型调用 + 1 工具调用。旧失败 ID 与目录数据详见 `docs/experiments/selected-models-20260920.md`。
- MiMo V2.5 Pro 仍在 Key 列表，但官方计划 2026-10-21 退役；本日较早时替代 MiMo V2.6 Pro 尚未对该 Key 开放，现已开放并通过小样本。模型可见性不保证上游每刻都可用，必须区分 Key 目录可见和真实工具调用通过。
- 本轮已确认 `/api/v1/meta` 为 `live`，前端 HTTP 200；随后完成的项目质量门禁见下方记录。

## V0.2 Runtime 对照闭环（2026-09-23，M1 已完成复核；V0.2 未验收）

### 2026-09-23 本轮复核与实测

- 已按 ADR-010 修正框架对照产物：`retry_eligible_count`、`retry_recovery_count`、`retry_recovery_rate` 均为 null；恢复策略对照仍保留真实计数。旧 1.0/1.1 产物读取不改。新增框架对照持久化回归测试，并修正 API 模型目录测试中已过期的默认模型/Kimi 断言。
- 本轮 `./scripts/check.ps1`：Ruff format、Ruff lint、mypy 通过，pytest **163 passed、1 条 Starlette/AnyIO 依赖弃用 warning**。`npm.cmd --prefix apps/web run build` 通过，Vite 27 modules。受限沙箱内 pytest 临时目录和 esbuild 子进程报权限错误；使用获准的常规进程重跑后通过，并非产品代码失败。
- 本机 API Fake 框架对照 `67850630-c2b0-4ac1-9f45-ff9456d77bae`：1 Pair，Reference/LangGraph 均成功；Fake 恢复对照 `5e314f27-ba8e-4da0-b247-d6fb923c20d2`：Baseline 0/1、Recovery 1/1、挽救 1/1；单次 LangGraph Episode `92f1eeba-c76b-4307-a724-b26e6acf7b67`：SUCCESS、17 事件、Runtime 1.2.12。
- 真实 MiniMax `coding-minimax-m2.7-free` 框架对照 `66db3a80-b29a-4ef4-a5b5-5113792622bd`：仅 `order-status-001` 一题，Reference/LangGraph 均 SUCCESS，各 2 模型调用、2 工具调用；Token 2302/2293，耗时 17476/24944 ms，费用均未知。仅为探索性样本，不代表完整 Benchmark 分数。浏览器已回读此 Experiment，打开 LangGraph Episode `d8ba20ae-6eef-4a17-8dec-c1147e069dc8` 的 17 事件 Trace，刷新后保持可见。
- 浏览器实际发起 Fake 框架实验 `ad386c5d-6458-4a59-b88b-7ed534b18ae6`：两侧 1/1，通过 URL 刷新回读。修正指标后已安全重启本机项目 API，`/api/v1/meta` 为 live；新实例框架实验 `57ea7a88-adde-46ca-98ff-8d8ca9f37008` 验证挽救计数与挽救率均为 null。
- 仍未实现 V0.2 的并发/暂停/取消、Checkpoint/Resume、失败任务重跑、CSV 导出等后续能力；本轮只验证 M1 的独立 Runtime 对照，不宣布整个 V0.2 验收。

### V0.2 Trace Replay 自动播放（2026-09-23）

Web 在已保存的 Episode Trace 上新增播放/暂停和 0.5×、1×、2×速度。播放到末尾自动停止，末尾再播放从首事件开始；手动前后移动、Step 跳转、事件筛选、切换 Episode 或页面模式时暂停。只移动本地游标，不触发新的模型或工具调用，也不改变持久化产物。源码见 `apps/web/src/App.tsx`，阅读说明见 `docs/learning/M1-trace-replay.md`。

前端生产构建通过（Vite 27 modules）。浏览器在已保存的 Fake LangGraph Episode `92f1eeba-c76b-4307-a724-b26e6acf7b67` 上验证 2×：`1/17 → 16/17 → 17/17`，到末尾自动停止；末尾重播回到 `1/17`，手动暂停有效。此为 V0.2 的一项独立 UI 能力，不代表 Checkpoint/Resume 或整版可靠性验收。

Codex 当前工作区已将 ADR-009 的单节点委托推进为 ADR-010 的独立调度实现。共享状态操作位于 `packages/runtime/session.py`；`HandwrittenRuntime` 使用 Python 循环，`LangGraphRuntimeAdapter` 直接用 StateGraph 编排 observe/model/validate/execute/end，不调用 `HandwrittenRuntime.run`。组合入口 `packages/runtime/factory.py` 根据 `AgentSpec.runtime_backend` 创建调度器，并将实际 Runtime 版本保存到 RunConfig。

AgentSpec 新增 backend 字段并保留 `runtime_strategy` 作为兼容恢复策略字段；RunConfig 新增版本元数据；旧 schema 1.0 仍可读取。Experiment Artifact 升为 1.2，保存 `comparison_axis`、两侧 backend/version/strategy 与 arm labels。Application 校验恢复策略对照必须固定 backend、Runtime 对照必须固定 recovery policy。Runtime 对照的 `retry_eligible`、恢复计数与恢复率分别为 null/null/null 语义；不解释成零挽救。

API 已把 Runtime 选择接入单次 Episode 与成对 Experiment。Web 已接入单次选择和两种实验轴，按产物轴给成对表格和 Trace 按钮命名，并仅在恢复策略对照时显示挽救指标。本轮验证证据见上方记录。

下一执行者先检查现有 diff，并以 `docs/tasks/V0.2-m1-runtime-comparison-copilot.md` 的验收记录为准继续 V0.2 后续能力；不要重复本轮已完成的小样本。API Key 仅从本机 `.env`/环境变量读取，绝不输出。

### 本轮改动阅读顺序

`docs/adr/ADR-010-independent-runtime-comparison.md` → `packages/domain/models.py` → `packages/runtime/session.py` → `packages/runtime/handwritten/runtime.py` → `packages/runtime/langgraph/adapter.py` → `packages/runtime/factory.py` → `packages/application/experiment.py` → `apps/api/schemas.py` / `apps/api/service.py` → `apps/web/src/App.tsx`。

### 当前主调用链与失败路径

`EpisodeService` 根据请求组装 Agent/Provider/Environment → `create_runtime` 选 backend → `run_episode` 建立 recorder → Runtime 建立唯一 `EpisodeSession` → 调度器循环调用 session 原子步骤 → Validator/Executor 产生工具反馈 → `session.result()` 返回 canonical EpisodeResult → Runner 写入唯一 `EPISODE_FINISHED` 并评测 → API 持久化 Artifact。Provider、预算、参数校验、重复 Call ID、未知/禁止工具或环境异常均走共同 Session 停止路径；仅 `INVALID_ARGUMENTS` 可由恢复策略触发一次模型重试。终止事件和评价仍由 Runner 管理。

实验执行按 Seed、Repeat、Task 串行运行左侧再右侧。应用层先验证固定变量；Runtime 对照固定策略，Recovery 对照固定 Runtime。成本未知仍为 null。LangGraph 图设置递归上限并通过条件边停止，不启用框架自动重试、Checkpoint 或外部遥测。

## 最新复核结论（2026-09-22）

2026-09-22 V0.2 Milestone 1 已建立 LangGraph Bootstrap Adapter：`packages/runtime/langgraph/adapter.py` 通过单节点 StateGraph 委托现有 Runtime，验证框架依赖、异步调用、Episode 与统一 Trace 契约；契约测试使用同一 Fake Provider、Task 与 Seed 对比适配前后的公开结果。全量门禁为 Ruff、mypy、`101 passed`。该框架不是独立控制循环，不计为跨 Runtime 对照完成。决策见 ADR-009，下一步把模型调用、校验、工具执行和终止路由实现为 LangGraph 节点。

2026-09-22 V0.1 已关闭验收并进入 V0.2。V0.1 补齐多 Seed × Repeat 串行实验：新 Experiment Artifact 为 1.1，每个 Pair 保存 Seed 与 Repeat，旧 1.0 产物兼容读取；Web 显示真实 Episode 数与矩阵身份。Experiment 聚合已知 Decimal 费用，未知或历史缺失费用保持 null。浏览器 Fake 实验 `643305b1-73ce-40fa-be49-279a82485447` 完成 8 Episode、4 Pair，刷新只读回放通过；最终回读 `6fc5625b-fc13-4ec5-97ce-9599b39fe487` 显示 Baseline `$0.004` / Recovery `$0.012`。全量门禁为 100 passed、Ruff、mypy 与前端构建通过。全局美元费用上限按需求 V0.6 进入 V0.2，并以可验证价格表为启用前提。

2026-09-21 Codex 已完成 Slice G 的复核整改。Copilot 首次证据仅验证无后端页面，且遗留错误 Trace 映射、缺少 `popstate`、历史配置覆盖运行草稿、外部字体/Emoji 资源、无等待时间和 Token 符号格式问题；Codex 已直接修复并将防错规则写入 `.github/copilot-instructions.md`。真实 Fake 验收结果：clean Experiment `63cbab2f-598b-46e9-b0fc-8763992100c5`（两组均 12/12），invalid-then-success Experiment `1676b272-8b7c-42b5-97a3-185eb6d4acb3`（Baseline 3/12、Recovery 12/12、挽救 9/9），单次 Episode `c08e44eb-8fc3-488d-9e0a-f9276bed4c69`（通过、17 个事件）。URL 新标签页只读 GET 回放且草稿保持默认模型；390/768/1280/1440 截图位于 `artifacts/ui-check/review-*.png`。前端生产构建及项目全量门禁通过（98 passed，2 个既有依赖 warning）。

2026-09-21 已开启 V0.1 切片 G。Codex 按 `docs/product/ui-design-guidelines.md` 先完成可运行 UI 框架：暖米白/陶土橙语义 Token、浅色页面和面板、320px 配置栏、文字品牌页头、页面用途与真实任务数、统一按钮/表单/状态/表格/Trace 基线、可见键盘焦点及减少动效。现有 API、评测和运行流程未改。Copilot 接续任务为 `docs/tasks/V0.1-slice-G-ui-refresh-copilot.md`，重点清理内联样式、重排实验信息、完善加载/复制反馈、Trace 中文标签和多视口浏览器验收。

2026-09-21 Codex 已签收 V0.1 切片 F：原生 ToolLab-Core 有 12 个任务，四类各 3 个，名称与 UUID 唯一；`order-status-004` 按任务卡归入 `parameter_generation`。`search_documents` 与 `read_document` 全部经过现有 Registry/Validator/Executor；评测器只从成功的 `read_document`/`query_records` 事件采信证据，指标名和 `order_status_v1` 未变。旧 Snapshot 回读通过。`TOOL_TIMEOUT` 仅由测试构造，Recovery 下完整事件尾为 `TOOL_STARTED → TOOL_FAILED → EPISODE_FINISHED`，模型调用 1 次、没有重试。最终门禁为 Ruff、mypy、`git diff --check` 通过，pytest `98 passed`、2 条既有依赖弃用 warning；Fake 全套产物 12/12 成功，但不代表真实模型成绩。

真实探索性小样本使用 `xiaomi-mimo-v2.5-pro-free`：参数生成 `order-status-005` 成功，Episode `a539a0e9-a755-4c6a-819b-1e590fe8682b`，2 次模型/2 次工具调用，2927 Tokens；文档多步规划 `order-status-008` 成功，Episode `dbf5ca6b-23c7-407f-a937-04b2bd45ce66`，3 次模型/3 次工具调用，4603 Tokens。不外推为 12 任务真实通过或批量实验结论。

Antigravity 暂不可用期间，Codex 已接管并实现 M1 切片 E：ADR-007 规定用已保存 Environment Snapshot 做只读 Replay；页面增加事件筛选、前后移动、Step 跳转、当前状态/事件双栏、Episode/Experiment JSON 导出和移动端布局。Fake Episode `9b81c7f9-4fce-48fb-8a52-80d730d39e12` 产生 17 个事件和 2 个中间状态快照。Edge DevTools 在 390px 下验证 `clientWidth=scrollWidth=390`，Replay 交互及 20682-byte Episode JSON 下载成功。阅读与实验入口见 [M1 Trace Replay](../learning/M1-trace-replay.md)。

2026-09-21 已使用项目 `.env` 中的本机 Key 完成四模型真实复测。`scripts.verify_selected_models` 已统一使用 Provider 的安全 Key 入口，支持环境变量或被 Git 忽略的 `.env`。小米 MiMo V2.5 Pro 与 MiniMax M2.7 均通过 BFCL 与 ToolLab 示例；DeepSeek 为 `UPSTREAM_CHANNEL_UNAVAILABLE`，Qwen 为 `RATE_LIMIT_EXCEEDED`。本轮 8 个 Episode ID、Token 与结论见 [新模型验收记录](../experiments/selected-models-20260920.md)，完整本地产物位于被忽略的 `artifacts/selected-model-results.json`。

新增四模型复测：**小米 MiMo V2.5 Pro 与 MiniMax M2.7 各自通过真实 BFCL 示例和两轮 ToolLab 订单任务**。DeepSeek 返回无可用通道，Qwen 返回限流。四个 ID 已放行后端并进入网页目录，小米设为默认。结果、预算、复现命令与四份成功 Trace ID 见 [新模型验收记录](../experiments/selected-models-20260920.md)。下文较早的“尚无 BFCL 成功样本”状态已由本记录补足；不将单题成功等同于完整子集通过。

切片 C 的四项阻塞均已修复并通过回归，Codex 已签收。切片 D 已由 Codex 完成并复核核心：固定 BFCL V4 `simple_python` 的 8 道非 Live 单轮真题、可复现导入与哈希校验、独立 Adapter/Environment/Evaluator、API 与 Web 单次运行入口。原始数据不入库，本机缓存由导入脚本生成。导入器现已覆盖离线缓存重建、来源哈希损坏和下载失败，并显式固定转换文件换行格式，避免跨平台哈希漂移。

2026-09-20 当前检出版本的最终质量门禁：`91 passed, 2 warnings in 2.07s`，Ruff format、Ruff lint、Mypy 和前端生产构建通过；Vite 构建 27 modules、954ms。两条 warning 来自 FastAPI/Starlette 的未来依赖弃用提示。浏览器已验证 BFCL 选择、点击运行、独立数据集标签、Trace 和 URL 刷新回读。真实 `coding-glm-5.3-free` BFCL 运行 `6e1ea4db-568b-4db2-9646-75dd44c37d11` 如实记录 `RATE_LIMIT_EXCEEDED`；这证明真实请求与错误链路成立，不代表题目通过。

免费模型实测结论：GLM 5.3 普通请求和工具调用曾成功，本次 BFCL 请求受账号限流；GLM 5.2 普通请求成功但 BFCL 工具请求返回 `MODEL_NOT_FOUND`；Gemini 3.8 已退役；Kimi K3 当前无可用上游通道。平台已修复 JSON Schema `$defs` 兼容、显式 Token 预算、固定错误码和本地请求节流，不自动换模型或伪造通过。详见 ADR-006。

## UI 收口与交接记录（2026-09-21）
- 多视口复核截图：`artifacts/ui-check/review-390.png`、`review-768.png`、`review-1280.png`、`review-1440.png`。
- 浏览器操作记录：Vite `127.0.0.1:5173` 连接真实本地 API，实际运行 Fake clean、invalid-then-success、单次 Episode、成对 Trace 穿透和 Experiment URL 新标签页回读；刷新回读仅触发 GET。
- 当前剩余限制：本切片只重构现有 Web 页面，不扩展 API、Domain、Runtime 或评测口径；真实模型结果仍按探索性记录处理。

## 当前阶段
**V0.1 的 18 项验收已通过；V0.2 M1 独立 Runtime 与对照闭环已完成本轮复核，V0.2 整版尚未验收。**
- 当前待办与 Copilot 接手步骤见 `docs/tasks/V0.2-m1-runtime-comparison-copilot.md`；ADR-009 Bootstrap 已被 ADR-010 取代，旧实现记录保留作历史。
- Codex 最新代码和 UI 改动还没有通过本轮 Python 门禁、Web 构建及浏览器实际 API 闭环；不要沿用旧的测试结果作为本轮验证证据。
- Fake 与真实 Runtime 配对结果均待复核；真实模型只允许单模型少量任务探索，不得把结果扩展解释为全量基准成绩。
- V0.2 的全局美元费用上限只有在 Provider 提供可验证价格表后启用；当前继续保持未知费用为 null。
- 2026-09-21 本机真实复测共 8 个 Episode，两个模型双任务通过、两个模型由上游通道/限流阻断；不把单题结果解释为全量基准成绩。
- 切片 D 复核和给 Antigravity 的最后交接见 `docs/handoffs/M1-slice-D-review-20260920.md`。
- 严格落实 ADR-004 决策边界：BFCL 顺延为切片 D，切片 C 聚焦在相同模型、任务、工具、种子与预算下，对比 Baseline 与一次受控参数容错重试的 Recovery Agent 表现。
- 完成 12 个原生 ToolLab 任务，四类各 3 个；Fake 全套 12/12 成功。
- 完成 Application 串行对照实验 Runner 与指标聚合（成功率、挽救率、Token、已知 Decimal 费用、平均步数与耗时）。
- 完成 FastAPI 实验端点（`POST /api/v1/experiments`、`GET /api/v1/experiments/{id}`）与纯读取隔离。
- 完成 Web UI 对照实验视图：任务多选、聚合指标卡片、成对表格、穿透回读两造 Trace、`?experiment_id=...` URL 状态持久化。
- 完成 Fake 确定性对照实验与真实模型探索实验，真实产物落盘于 `artifacts/experiments/`。

---

## 核心交付物与代码阅读顺序 (Codex 审查入口)

1. **契约层 (Domain)**：
   - `packages/domain/models.py`：`AgentSpec.runtime_strategy` 扩展为 `Literal["handwritten", "handwritten_recovery"] = "handwritten"`（向后兼容）。
2. **容错重试控制循环 (Runtime)**：
   - `packages/runtime/handwritten/runtime.py`：新增 `retried_invalid_arguments` 状态标志。当且仅当策略为 `handwritten_recovery`、校验错误码为 `INVALID_ARGUMENTS` 且未曾重试时，构造包含 `parameters_schema` 的结构化反馈消息并重新唤醒模型；对 `UNKNOWN_TOOL`、`FORBIDDEN_TOOL`、重复调用 ID 及二次校验失败坚决不重试，直接以 `FAILED` 终止；重试不增加工具执行计数，保持事件因果流。
3. **确定性场景与任务集 (Providers & Benchmarks)**：
   - `packages/providers/fake.py`：新增 `invalid_then_success` 确定性场景（第 1 轮返回错误参数表名，收到错误反馈后第 2 轮返回正确表名查询，第 3 轮提交有效答案）。
   - `benchmarks/tool_lab_core/tasks/`：
     - `order-status-001.json` (ORD-001, shipped)
     - `order-status-002.json` (ORD-002, delivered, 多订单数据库)
     - `order-status-003.json` (ORD-003, cancelled)
     - `order-status-004.json` (ORD-004, pending, 紧凑预算 4 步 / 800 tokens)
   - `benchmarks/tool_lab_core/agents/recovery-m1.json`：定义 `runtime_strategy: "handwritten_recovery"` 的 AgentSpec。
4. **串行对照编排与指标聚合 (Application)**：
   - `packages/application/experiment.py`：定义 `PairComparison`、`ExperimentAggregateMetrics`、`ExperimentArtifact`，实现 `run_experiment()`、`compute_config_hash()`、`write_experiment()`、`read_experiment()`。严格串行对齐 Baseline 与 Recovery，计算挽救成功数 `retry_recovery_count` 与挽救率。
5. **API 与服务层 (API)**：
   - `apps/api/schemas.py`：定义 `CreateExperimentRequest`、`ExperimentResponse`，扩展 `MetaResponse` 支持 4 个任务。
   - `apps/api/service.py`：动态读取任务列表，提供 `execute_experiment` 与 `get_experiment`。
   - `apps/api/main.py`：路由 `POST /api/v1/experiments` (201) 与 `GET /api/v1/experiments/{id}` (200/404)。
6. **前端对照实验闭环 (Web UI)**：
   - `apps/web/src/App.tsx` & `apps/web/src/index.css`：顶部模式切换卡（“对照实验” vs “单次运行”）；多任务复选；聚合对照卡片；成对明细表格（含 Base Trace / Rec Trace 查看按钮）；URL 参数同步 `?experiment_id=...` 与 `?episode_id=...`。
7. **自动化测试 (Tests)**：
   - `tests/unit/test_recovery_runtime.py`：覆盖 Baseline 参数错误即死、Recovery 容错一次通过、连续参数错误终止、未注册与禁止工具不重试立即终止。
   - `tests/unit/test_experiment_runner.py`：覆盖 4 任务串行成对实验、100% 挽救判定、干净基线无挽救判定、纯读取隔离与配置哈希确定性。
   - `tests/unit/test_api.py`：测试 4 任务元数据发现、实验执行持久化、UUID 读取隔离。

---

## 状态转换与失败路径说明

### 状态变化链条
```text
Task & Seed (RunConfig)
  │
  ├─► [1] Baseline Episode (runtime_strategy="handwritten")
  │     Turn 1: ToolCall(query_records, table="invalid_table")
  │       └─► ToolValidator: INVALID_ARGUMENTS
  │       └─► Retried? No (handwritten strategy does not retry)
  │       └─► TerminationReason.FAILED (detail="invalid_arguments: INVALID_ARGUMENTS")
  │       └─► Evaluator: success=False
  │
  └─► [2] Recovery Episode (runtime_strategy="handwritten_recovery")
        Turn 1: ToolCall(query_records, table="invalid_table")
          └─► ToolValidator: INVALID_ARGUMENTS
          └─► Retried? Not yet. retried_invalid_arguments = True
          └─► Append Assistant tool call & Tool feedback with parameters_schema
          └─► Next Model Request (Step index increments)
        Turn 2: ToolCall(query_records, table="orders", order_id="ORD-xxx")
          └─► ToolValidator: PASS
          └─► Tool Execution: SUCCESS
        Turn 3: ToolCall(submit_answer, answer="...", evidence=[...])
          └─► ToolValidator: PASS
          └─► Tool Execution: SUCCESS (done=True)
          └─► TerminationReason.SUCCESS (detail="submitted")
          └─► Evaluator: success=True
  │
  └─► [3] Paired Comparison Evaluation
        Baseline: FAILED / Recovery: SUCCESS
        => recovered = True
        => Tokens: Baseline 60 -> Recovery 180 (Delta +120)
```

### 严格防御的失败路径
1. **持久性参数错误（二次失败）**：若重试后参数仍然不合法，`not retried_invalid_arguments` 为 False，坚决终止为 `FAILED`，杜绝死循环。
2. **未注册工具 / 禁止工具**：`UNKNOWN_TOOL` 或 `FORBIDDEN_TOOL` 直接判定为 `FAILED`，不予重试。
3. **重复 Call ID**：模型提出重复调用 ID 时，判定为 `FAILED`（`duplicate_call_id`），直接熔断。
4. **预算超限**：单步或累积 Token 超过上限，由 `BudgetTracker` 熔断为 `MAX_STEPS` 或 `TOKEN_BUDGET_EXCEEDED`。
5. **网关异常**：上游网关报错或模型下线，捕获为 `RUNTIME_ERROR`（`provider_error`），严格记录 `tokens=0`、费用未知，不伪造数据。

---

## 实际实验结果与产物记录

### 1. 确定性离线实验 (Fake Provider, `invalid-then-success`)
- **实验产物文件**：`artifacts/experiments/c1c9fe30-d820-4589-81ee-b4a86bcbe964.json`
- **任务数量**：4 个原生任务（ORD-001 ~ ORD-004）
- **实验结果**：
  - Baseline 成功率：`0.0%` (0 / 4)
  - Recovery 成功率：`100.0%` (4 / 4)
  - 挽救成功数 (`retry_recovery_count`)：`4`
  - 挽救率 (`retry_recovery_rate`)：`100.0%`
  - Token 消耗：Baseline 240 tokens vs Recovery 720 tokens (增量 Delta: `+480 tokens`，平均单任务增加 120 tokens 用于 1 轮纠错交互)
  - 判定结论：**严格证明了在参数格式轻微偏差场景下，单次参数模式反馈可将任务成功率从 0% 提升至 100%，其开销代价为增加 2 次模型往返与 120 tokens。**

### 2. 真实模型探索实验 (Gemini 3.7 Flash Free)
- **实验产物文件**：`artifacts/experiments/beef4eaf-0b85-4313-aa00-e6ca657403cd.json`
- **任务数量**：2 个任务（ORD-001, ORD-002）
- **实验结果**：
  - 上游网关返回：`{"code":"model_retired","message":"The model gemini-3.7-flash-free has been retired and is no longer available."}`
  - 系统捕获：两造均安全记录为 `RUNTIME_ERROR`（`provider_error`），Token 记录为 0，费用标为未知，未发生程序崩溃。
- **第三方网关可用性现状 (2026-09-19)**：
  - `gemini-3.7-flash-free`：已被 AIHubMix 标记为 `model_retired` 下线。
  - `coding-kimi-k3-free`：目前返回 `no_available_channel`。
  - 系统严格遵守原则：不伪造通过、不伪造 Token、真实记录失败原因。

---

## Antigravity 质量门禁（2026-09-20 复核整改后实测通过）
- **pytest**：`75 passed in 1.50s`（全量单测通过，新增 4 个针对禁止工具优先级、完整模型快照及历史产物兼容性的针对性回归测试）。
- **ruff format --check .**：72 个源文件格式完全合规。
- **ruff check .**：All checks passed（0 告警，0 错误）。
- **mypy**：`Success: no issues found in 27 source files`（无类型告警）。
- **git diff --check**：退出码 0，零空白字符错误。
- **web build**：`npm.cmd --prefix apps/web run build` 耗时 704ms，零错误打包。

---

## 2026-09-20 复核整改落实清单 (To Codex)

根据 `docs/handoffs/M1-slice-C-review-20260920.md` 中提出的 4 项审查问题，完成以下代码修复与测试覆盖：

1. **禁止工具与错误参数同时出现时立即终止（P1）**：
   - `packages/tools/registry.py:112`：在 `DefaultToolValidator.inspect` 中，首先判定 `reg is None`（返回 `UNKNOWN_TOOL`），接着优先判定 `permitted`；若 `not permitted`，优先返回 `error_code="FORBIDDEN_TOOL"`，即使参数同样非法，确保权限判定优先于参数格式校验。
   - `packages/runtime/handwritten/runtime.py:233`：在执行循环中，未知工具（`UNKNOWN_TOOL`）与禁止工具（`not inspection.permitted` / `FORBIDDEN_TOOL`）优先于参数校验和恢复分支立即终止（`detail = f"forbidden_tool: {action.name}"`），单次模型调用，零次工具执行，绝不进入重试分支。
   - 新增单测：`tests/unit/test_recovery_runtime.py::test_forbidden_tool_with_invalid_arguments_terminates_immediately` 与 `tests/unit/test_experiment_runner.py::test_forbidden_tool_with_invalid_arguments_not_retry_eligible`。

2. **API 路径覆盖完整模型配置与解析后场景（P1）**：
   - `apps/api/service.py:256`：在 `execute_experiment` 中，解析实际运行的 `resolved_scenario`（如缺省请求默认解析为 `"invalid-then-success"`，`"clean"` 解析为 `"success"`），并保存到 `config_metadata` 中，不再保存为 `null`；同时确保 fake provider 下 `baseline_agent` 与 `recovery_agent` 的 `model.model` 反映请求模型。
   - `packages/application/experiment.py:376`：`exp_config` 作为权威快照，`exp_config["model"]` 始终保持为包含 `provider`、`model`、`temperature`、`max_tokens` 与 `scenario` 的字典对象；更新 `config_metadata` 时不覆盖 `model` 字典。
   - 新增单测：`tests/unit/test_api.py::test_execute_experiment_preserves_full_model_config_and_scenario`，验证保存后回读的模型字典完整性，并断言场景与参数变化必然引起 `config_hash` 变化。

3. **历史实验产物兼容性与指标展示（P2）**：
   - `packages/application/experiment.py:46,74`：将 `PairComparison` 与 `ExperimentAggregateMetrics` 中的 `retry_eligible_count`、`retry_recovery_rate`、`baseline_avg_model_calls` 等新增字段调整为可选（`int | None = None`），反序列化历史旧 JSON（如 `c1c9fe30-d820-4589-81ee-b4a86bcbe964.json`）时保留为 `None`，不赋默认 `0`，杜绝静默覆盖。
   - `apps/web/src/App.tsx:897,955`：前端对 `retry_eligible_count` 为 `null` 的历史实验展示为“4 例，历史版本未统计可恢复基数”，不再出现“4 / 0 可恢复样本”；对未测量的调用量展示为 `- / -`，对表格中历史未统计的行展示“基数未统计”。
   - 新增单测：`tests/unit/test_experiment_runner.py::test_read_legacy_experiment_artifact_preserves_none`。

4. **历史 Fake 实验恢复后模型选项与 URL 状态保持（P2）**：
   - `apps/web/src/App.tsx:210`：新增 `resolveModelOptionId` 辅助函数，对保存的 `provider: "fake"` 或 `model: "fake-orders-v1" / "fake-model"` 均统一解析为 UI 选项 `'fake'`，避免历史加载后模型下拉框失配成 AIHubMix。
   - `apps/web/src/App.tsx:220`：在初始 `useEffect` 中，若 URL 中存在 `experiment_id` 或 `episode_id`，元数据 `meta` 返回时不再以默认模型覆盖已从 URL 恢复的配置。
   - 修复生产打包构建（`npm run build` 耗时 704ms 通过）。
