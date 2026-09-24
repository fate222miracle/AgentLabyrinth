# AgentLabyrinth

面向 AI Agent 的可复现实验平台。唯一权威需求：`docs/product/requirements.md` **V0.6**。

**V0.1 已完成 18 项验收。V0.2 已完成独立 Reference/LangGraph Runtime 对照、网页实跑与单模型真实小样本；ToolLab 单 Episode 的 Checkpoint/Resume 已接入 API/Web，并通过跨进程、接口和浏览器 Fake 故障演练，真实模型中断仍待实测。最新证据与模型可用性见 `docs/handoffs/current-state.md`。**

课程演示 M1 推进：
- 切片 A：完成 AIHubMix 真实 ToolLab 闭环。
- 切片 B：完成 Web 演示单次执行与 Trace 回读。
- 切片 C：已完成 Baseline 与 Recovery Agent 对照实验闭环（见 `docs/tasks/M1-slice-C-antigravity.md` 与 ADR-004）。扩充至 4 个 ToolLab 原生任务，提供串行 Experiment API、聚合对照卡片、成对比较表格（可穿透查看两造 Trace）与 URL 状态持久化。
- 切片 D：固定 BFCL V4 `simple_python` 上游提交，接入 8 道非 Live 单轮真题；结果独立标记为 `AgentLabyrinth-adapted subset`，不作为官方 BFCL 分数。
- 切片 E：Episode Trace 支持事件筛选、前后移动、Step 跳转和环境快照；Episode 与 Experiment 可直接导出当前已加载的 JSON，回放和导出均不重新调用模型。
- 切片 F：已补齐四类各 3 个、共 12 个原生任务；`search_documents/read_document` 通过现有 Registry/Executor，Fake 可离线跑通全套，评测器计入文档证据。
- Slice G：实验工作台 UI 已按 `docs/product/ui-design-guidelines.md` 完成收口与真实 Fake 闭环验收，复核记录见 Copilot 任务卡。

Codex 负责 Domain 契约、预算与评测审查；Antigravity 负责内部实现（`HandwrittenRuntime` 容错重试分支、`run_experiment` 串行编排、4 条原生 TaskSpec、FastAPI 实验端点与 Web 对照视图）。

## 启动与检查

需要 Python 3.12 和 uv。在项目根目录运行一键检查脚本：

```powershell
./scripts/check.ps1
```

脚本锁定同步依赖，依次运行 Ruff 格式、Lint、mypy、pytest，失败立即停止。需要先安装 `uv` 并让终端能找到它。

首次使用 BFCL 前，从固定官方来源构建本地缓存并校验原始文件及转换结果哈希：

```powershell
uv run python scripts/import_bfcl_subset.py
```

上游题目许可未单独明确，因此原始数据和转换缓存不入库；已缓存后可断网运行。manifest 位于 `benchmarks/bfcl_adapted/dataset_manifest.json`。

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

服务仅监听 `127.0.0.1:8765/mcp`，使用官方 MCP Streamable HTTP；不接收任意任务路径。服务停止后远程工具会失败并留下 Trace，本地 ToolLab 仍可运行。MCP Episode 当前保存最终 Artifact，但不提供断点恢复。

浏览器打开 `http://127.0.0.1:5173/`。支持切换“对照实验 (Paired Experiment)”与“单次运行 (Single Episode)”：
- 对照实验模式：可选择恢复策略对照（Baseline vs Recovery）或 Runtime 对照（Reference vs LangGraph），多选原生评测任务并配置 1–10 个不重复 Seed 与每 Seed 重复次数。运行前显示真实 Episode 数。结果按对照类型展示成功率、适用的恢复指标、Token 与费用，成对表格可穿透审查两侧 Trace。支持 `?experiment_id=...` 与 `?episode_id=...` 刷新回读。
- 已加载的实验可导出 JSON 和 CSV。CSV 每个 Episode 一行，含实验哈希、任务、Seed、重复次数、对照侧、成功判定、用量及指标；未知费用和不适用的恢复指标留空。导出只读取当前产物，不重新调用模型。
- 单次运行模式：可切换原生 ToolLab 与 8 道 BFCL 改编真题，展示数据来源、本地评分协议、结果与完整 Trace。
- 单次运行可选择 Reference/LangGraph Runtime 和关闭/单次参数纠错策略；实际版本保存在 Episode RunConfig。
- ToolLab 单次运行在安全点本地存档。后端进程意外退出并重启后，单次运行表单可列出并恢复上次进程留下的 Episode；也可调用 `GET /api/v1/episodes/resumable` 与 `POST /api/v1/episodes/{id}/resume`。中断中的上游模型请求可能重新发送并产生额外用量；BFCL 和 Experiment 暂不支持恢复。
- Trace Replay：按事件类型筛选，使用前后按钮或 Step 下拉定位，左侧查看截至当前事件最近的 Environment Snapshot；历史旧产物缺少中间快照时仍可浏览事件。

真实免费模型必须在本机后端环境配置 `AIHUBMIX_API_KEY` 后验证，Key 不写入仓库、前端或聊天。页面模型目录从 `benchmarks/tool_lab_core/models.json` 的已验证候选中筛选当前 Key `/v1/models` 可见项，目录缓存 5 分钟；模型上游仍可能临时限流或不可用。默认复测 MiniMax M2.7 与 MiMo V2.5 Pro；`--all-catalog` 会串行复测候选表中的 AIHubMix 模型，每个模型各跑一条 BFCL 和一条 ToolLab，并把真实结果增量保存到 `artifacts/selected-model-results.json`：

```powershell
uv run python -m scripts.verify_selected_models
uv run python -m scripts.verify_selected_models --all-catalog
```

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
