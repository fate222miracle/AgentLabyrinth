# AgentLabyrinth

面向 AI Agent 的可复现实验平台。唯一权威需求：`docs/product/requirements.md` **V0.6**。

2026-10-01 收尾：Episode/对照 API 支持可选 `max_execution_time_ms`，Web 新运行默认 300 秒；恢复累计安全点活动耗时，已开始的工具先完成再停止。历史看板默认折叠，动画支持“专注查看”。源码/实验与限制见 [学习交接](docs/learning/V0.2-product-closeout-20261001.md)。全局 Token 预算、最终免费模型选择与整版现场签收仍待完成，数据库为后续 ADR 方向。

**V0.1 已完成 18 项验收。V0.2 当前受控范围已补齐实验控制、恢复、固定回归与同配置历史看板；ToolLab/BFCL/只读 MCP/Experiment 均有单模型真实安全点恢复证据。全局 Token、最终模型收口、剩余 UI 实机检查与负责人签收待完成；准确边界见 [验收矩阵](docs/handoffs/V0.2-acceptance-review-20260930.md) 与 `docs/handoffs/current-state.md`。**

课程演示 M1 推进：
- 切片 A：完成 AIHubMix 真实 ToolLab 闭环。
- 切片 B：完成 Web 演示单次执行与 Trace 回读。
- 切片 C：已完成 Baseline 与 Recovery Agent 对照实验闭环（见 `docs/tasks/M1-slice-C-antigravity.md` 与 ADR-004）。扩充至 4 个 ToolLab 原生任务，提供串行 Experiment API、聚合对照卡片、成对比较表格（可穿透查看两造 Trace）与 URL 状态持久化。
- 切片 D：固定 BFCL V4 `simple_python` 上游提交，接入 8 道非 Live 单轮真题；结果独立标记为 `AgentLabyrinth-adapted subset`，不作为官方 BFCL 分数。
- 切片 E：Episode Trace 支持事件筛选、前后移动、Step 跳转和环境快照；Episode 与 Experiment 可直接导出当前已加载的 JSON，回放和导出均不重新调用模型。
- 切片 F：已补齐四类各 3 个、共 12 个原生任务；`search_documents/read_document` 通过现有 Registry/Executor，Fake 可离线跑通全套，评测器计入文档证据。
- Slice G：实验工作台 UI 已按 `docs/product/ui-design-guidelines.md` 完成收口与真实 Fake 闭环验收，复核记录见 Copilot 任务卡。

Codex 负责 Domain 契约、预算与评测审查；Antigravity 负责内部实现（`HandwrittenRuntime` 容错重试分支、`run_experiment` 串行编排、4 条原生 TaskSpec、FastAPI 实验端点与 Web 对照视图）。

## 固定课程演示（2026-10-01）

依赖准备：`uv sync --locked`、`npm.cmd --prefix apps/web ci`。从项目根目录生成新案例，再一条命令启动隔离 API/Web：

```powershell
$demoPath = Join-Path (Get-Location) ('artifacts/course-demo/' + [guid]::NewGuid().ToString())
uv --cache-dir .uv-cache run --locked python -m scripts.course_demo --artifacts-dir $demoPath
uv --cache-dir .uv-cache run --locked python -m scripts.course_demo --preview --artifacts-dir $demoPath
```

完成索引 `demo-index.json` 提供当前机器的链接；Ctrl+C 停止预览。固定成功、参数纠错、时间终止、子进程中断恢复和真实 localhost MCP HTTP/断线案例自动核验，模型全部 Fake、不读取 Key。拒绝覆盖旧目录或接管占用端口。只有生成退出码 0 才通过；`--skip-mcp` 不算网络验收。换电脑与三分钟讲解见 [演示交接](docs/handoffs/V0.2-course-demo-20261001.md)，调用链/失败路径见 [阅读指南](docs/learning/V0.2-course-demo-freeze.md)。另一电脑需取得包含该脚本的新提交后才能使用；未实测第二台全新机器安装。

## 启动与检查

需要 Python 3.12 和 uv。在项目根目录运行一键检查脚本：

```powershell
./scripts/check.ps1
```

脚本锁定同步依赖，依次运行 Ruff 格式、Lint、mypy、pytest 和四套固定 Fake 跨版本回归（单题、四类任务、Runtime 对照、超时预期失败），失败立即停止。回归 JSON 报告写入 `artifacts/regression/regression-reports/`。2026-10-01 最终后端225测试、mypy/Ruff86文件、Web11项检查与生产构建通过；四套回归22单元无退化来自同日上一收尾验证。需要先安装 `uv` 并让终端能找到它。

也可单独执行固定回归；Manifest 锁定模型、任务、Seed 和基线产物，成功变失败会返回非零退出码。真实模型回归需另备真实基线并显式使用 `--allow-live`：

```powershell
uv run python -m scripts.run_regression benchmarks/regression/course-smoke.json --candidate-revision working-tree
```

首次使用 BFCL 前，从固定官方来源构建本地缓存并校验原始文件及转换结果哈希：

```powershell
uv run python scripts/import_bfcl_subset.py
uv run python scripts/import_bfcl_subset.py --suite java
```

上游题目许可未单独明确，因此原始数据和转换缓存不入库；已缓存后可断网运行。两套 manifest 分别位于 `benchmarks/bfcl_adapted/` 与 `benchmarks/bfcl_java_adapted/`；本地改编评分不等于官方 BFCL 分数。

本地网页需要分别启动 API 与前端（两个终端，项目根目录执行）：

```powershell
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd apps/web
npm install
npm run dev
```

文档任务（007–009）还可选择 MCP HTTP 工具传输。先在第三个终端启动固定的只读 MCP 服务，再在单次运行中选择文档任务和「MCP HTTP」：

```powershell
uv run python -m packages.environments.tool_lab.mcp
```

服务仅监听 `127.0.0.1:8765/mcp`，使用官方 MCP Streamable HTTP；不接收任意任务路径。服务停止后远程工具会失败并留下 Trace，本地 ToolLab 仍可运行。MCP Episode 可在已保存安全点恢复；未完成的远程只读请求可能重发。

观看 MCP 网络演示：网页切到「单次运行」→ ToolLab 文档任务 `order-status-007` →「更多设置」选「MCP HTTP」→ 选择 Fake 模型并运行。结果区默认的「流程动画」先展示 Client、localhost HTTP、独立 Server；播放到搜索/读取文档步骤时显示远程调用和返回。本地提交答案不会标成 MCP。此视图依据 Trace 展示工具边界，未记录协议握手或 `tools/list` 报文。

浏览器打开 `http://127.0.0.1:5173/`。支持切换“对照实验 (Paired Experiment)”与“单次运行 (Single Episode)”：
- 实验历史看板：读取最近100条已保存实验，可选择同配置组；至少两次兼容运行才显示最近两次的差值。旧产物缺完整协议来源仍可打开，不参与趋势；不跨协议排名。读取、筛选和刷新只 GET，不发模型请求。实际网关费用与原厂参考成本分开展示。
- 对照实验模式：可选择恢复策略对照（Baseline vs Recovery）或 Runtime 对照（Reference vs LangGraph），多选原生评测任务并配置 1–10 个不重复 Seed 与每 Seed 重复次数。运行前显示真实 Episode 数。结果按对照类型展示成功率、适用的恢复指标、Token 与费用，成对表格可穿透审查两侧 Trace。支持 `?experiment_id=...` 与 `?episode_id=...` 刷新回读。
- 已加载的实验可导出 JSON 和 CSV。CSV 每个 Episode 一行，含实验哈希、任务、Seed、重复次数、对照侧、成功判定、用量及指标；未知费用和不适用的恢复指标留空。导出只读取当前产物，不重新调用模型。
- 新实验由异步 Job 运行，Web 可查看状态并在当前 Episode 完成后暂停/取消；暂停后可按原 ID 恢复。不同 Experiment 最多两个并行，单个 Experiment 的成对顺序不变。运行中的 URL 用 `?experiment_job_id=...`，完成后自动切到只读结果 URL。API 提供 `POST /api/v1/experiments/jobs`、`GET /api/v1/experiments/jobs/{id}`、`GET /api/v1/experiments/jobs/resumable` 和 `POST /api/v1/experiments/jobs/{id}/pause|cancel|resume`；旧同步 Experiment API 保留，Job 须走 Job 恢复入口。
- 单次运行模式：可切换原生 ToolLab、8 道 BFCL Python 与 5 道 BFCL Java 固定改编真题，展示数据来源、本地评分协议、结果与完整 Trace。
- 单次运行可选择 Reference/LangGraph Runtime 和关闭/单次参数纠错策略；实际版本保存在 Episode RunConfig。
- 单次运行在安全点本地存档。后端进程意外退出并重启后，可在单次运行表单恢复上次进程留下的 ToolLab、BFCL 或固定文档 MCP Episode；也可调用 `GET /api/v1/episodes/resumable` 与 `POST /api/v1/episodes/{id}/resume`。对照实验保存运行矩阵，可通过 `GET /api/v1/experiments/resumable` 与 `POST /api/v1/experiments/{id}/resume` 继续，同一侧已完成 Episode 不重算。中断中的上游模型请求可能重新发送并产生额外用量；这不保证任意外部写操作恰好一次。
- 失败 Episode 可从结果页显式“单独重跑”，或调用 `POST /api/v1/episodes/{id}/rerun`；新运行有新 ID 与来源记录，原产物不被覆盖。旧 Fake 单次产物若缺保存的模拟场景，会拒绝重跑。
- Trace Replay：按事件类型筛选，使用前后按钮或 Step 下拉定位，左侧查看截至当前事件最近的 Environment Snapshot；历史旧产物缺少中间快照时仍可浏览事件。

真实免费模型必须在本机后端环境配置 `AIHUBMIX_API_KEY` 后用真实 POST 验证，Key 不写入仓库、前端或聊天。页面从 `benchmarks/tool_lab_core/models.json` 候选中筛选 `/v1/models` 可见项，目录缓存 5 分钟；该目录即使使用无效 Key 也可能返回 200，**不能证明当前 Key 的权限、额度或通道**。当前目录默认 MiniMax M2.7 属于历史配置；2026-10-01 新 Key 的已知小样本仅 GLM 5.3 项目内闭环成功，最终免费模型名单仍待确定。默认复测 MiniMax M2.7 与 MiMo V2.5 Pro；`--all-catalog` 会串行复测候选表中的 AIHubMix 模型，每个模型各跑一条 BFCL 和一条 ToolLab，并把真实结果增量保存到 `artifacts/selected-model-results.json`：

```powershell
uv run python -m scripts.verify_selected_models
uv run python -m scripts.verify_selected_models --all-catalog
```

真实进程退出恢复探针支持 ToolLab、BFCL、MCP 与 Experiment，每次一题；先配置本机 Key，MCP 需独立服务，重测时使用新输出目录保留证据。例如：

```powershell
uv run python scripts/probe_live_checkpoint_resume.py --suite mcp --runtime langgraph --artifacts-dir artifacts/recheck-mcp
```

其他路径命令、真实结果与源码阅读见 [可靠性收口记录](docs/learning/V0.2-reliability-closeout.md)。安全点前模型请求可能重发，不能从这些小样本推导外部写工具恰好一次。

运行 CLI Demo 与对照实验脚本：

```powershell
# 1. 运行切片 C 对照实验（4 个原生任务，含 Fake 确定性挽救场景与探索实验）
uv run python scripts/run_slice_c_experiments.py

# 2. 单次运行场景演示 (Exit code 0 或 1)
uv run python -m scripts.demo --scenario success --output artifacts/demo_success.json
uv run python -m scripts.demo --scenario invalid-arguments --output artifacts/demo_invalid_args.json
```

## 架构与阅读入口

```text
scripts.run_slice_c_experiments / apps.api
  → application.run_experiment (Serial pair orchestration)
      → application.run_episode (Baseline: handwritten)
          → HandwrittenRuntime (Terminates on first invalid_arguments)
      → application.run_episode (Recovery: handwritten_recovery)
          → HandwrittenRuntime (Retries once with parameter schema feedback)
      → ToolLabEnvironment (orders db state, query_records, submit_answer)
      → OrderStatusEvaluator (Read-only, deterministic scoring)
      → ExperimentAggregateMetrics & write_experiment

V0.2 paired Runtime comparison
  → application.run_experiment (serial paired orchestration)
      → create_runtime (composition boundary)
          ├─ HandwrittenRuntime (Python scheduler)
          └─ LangGraphRuntimeAdapter (independent StateGraph scheduler)
      → shared EpisodeSession (provider, budget, validation, execution, Trace)
      → canonical Episode / Trace / Evaluation contracts
```

Bootstrap 阶段已由独立节点图取代，不作为当前架构描述。详见 `docs/adr/ADR-010-independent-runtime-comparison.md`、`docs/tasks/V0.2-m1-runtime-comparison-copilot.md` 与 `docs/handoffs/current-state.md`。

## 局限

当前已接入 12 个原生 ToolLab 任务，覆盖 Tool Selection、Parameter Generation、Multi-step Planning、Error Recovery 四类各 3 个。Error Recovery 的确定性结论来自显式 `invalid_then_success` Fake 场景；真实模型小样本只作探索性证据。
当前原生 ToolLab-Core 共 12 条任务（四类各 3 条），包含订单查询、参数生成、文档多步规划和错误恢复；对照实验严格串行执行，不引入队列或数据库；容错仅限 `INVALID_ARGUMENTS` 且最多 1 次重试。BFCL 仅覆盖单轮单工具选择与参数生成，工具不会执行任意上游 Python、Shell 或 API。
真实第三方网关存在限流、退役与通道波动。2026-09-20 实测 GLM 5.3 可完成工具调用但当前账号受限流；GLM 5.2 普通调用可用但 BFCL 工具请求返回 `MODEL_NOT_FOUND`；Gemini 3.8 已退役，Kimi K3 暂无通道。系统保存固定错误码、未知费用和真实 Trace，不自动切换模型。
