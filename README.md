# AgentLabyrinth

面向 AI Agent 的可复现实验平台。唯一权威需求：`docs/product/requirements.md` **V0.5**。

**M0 与 M1 切片 A、B、C 已复核；切片 D 已接入固定 BFCL 改编子集并通过代码门禁，最终网页成功实证待补。完整 V0.1 尚未验收。**

课程演示 M1 推进：
- 切片 A：完成 AIHubMix 真实 ToolLab 闭环。
- 切片 B：完成 Web 演示单次执行与 Trace 回读。
- 切片 C：已完成 Baseline 与 Recovery Agent 对照实验闭环（见 `docs/tasks/M1-slice-C-antigravity.md` 与 ADR-004）。扩充至 4 个 ToolLab 原生任务，提供串行 Experiment API、聚合对照卡片、成对比较表格（可穿透查看两造 Trace）与 URL 状态持久化。
- 切片 D：固定 BFCL V4 `simple_python` 上游提交，接入 8 道非 Live 单轮真题；结果独立标记为 `AgentLabyrinth-adapted subset`，不作为官方 BFCL 分数。
- 切片 E：Episode Trace 支持事件筛选、前后移动、Step 跳转和环境快照；Episode 与 Experiment 可直接导出当前已加载的 JSON，回放和导出均不重新调用模型。

Codex 负责 Domain 契约、预算与评测审查；Antigravity 负责内部实现（`HandwrittenRuntime` 容错重试分支、`run_experiment` 串行编排、4 条原生 TaskSpec、FastAPI 实验端点与 Web 对照视图）。

## 启动与检查

需要 Python 3.12 和 uv。在项目根目录运行一键检查脚本：

```powershell
./scripts/check.ps1
```

脚本锁定同步依赖，依次运行 Ruff 格式、Lint、mypy、pytest（当前 91 项），失败立即停止。需要先安装 `uv` 并让终端能找到它。

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

浏览器打开 `http://127.0.0.1:5173/`。支持切换“对照实验 (Baseline vs Recovery)”与“单次运行 (Single Episode)”：
- 对照实验模式：多选评测任务（4 个任务）、选择模型或离线场景，运行后展示两造成功率、挽救率（Retry Recovery Rate）、Token 代价增量、成对比较表格，可一键跳转审查任意一边的详细 Trace。支持 `?experiment_id=...` 与 `?episode_id=...` 刷新回读。
- 单次运行模式：可切换原生 ToolLab 与 8 道 BFCL 改编真题，展示数据来源、本地评分协议、结果与完整 Trace。
- Trace Replay：按事件类型筛选，使用前后按钮或 Step 下拉定位，左侧查看截至当前事件最近的 Environment Snapshot；历史旧产物缺少中间快照时仍可浏览事件。

真实免费模型必须在本机后端环境配置 `AIHUBMIX_API_KEY` 后验证，Key 不写入仓库、前端或聊天。默认复测用户选定的四个模型；`--all-catalog` 会串行复测页面目录中的全部 AIHubMix 免费模型，每个模型各跑一条 BFCL 和一条 ToolLab，并把真实结果增量保存到 `artifacts/selected-model-results.json`：

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
```

详见 `docs/learning/M0-implementation.md`、`docs/learning/M1-bfcl-adapter.md`、`docs/experiments/M0-execution.md` 与 `docs/handoffs/current-state.md`。

## 局限

当前已接入 4 个原生 ToolLab 订单任务（ORD-001 shipped, ORD-002 delivered, ORD-003 cancelled, ORD-004 pending 紧凑预算）。
对照实验严格串行执行，不引入队列或数据库；容错仅限 `INVALID_ARGUMENTS` 且最多 1 次重试。BFCL 仅覆盖单轮单工具选择与参数生成，工具不会执行任意上游 Python、Shell 或 API。
真实第三方网关存在限流、退役与通道波动。2026-09-20 实测 GLM 5.3 可完成工具调用但当前账号受限流；GLM 5.2 普通调用可用但 BFCL 工具请求返回 `MODEL_NOT_FOUND`；Gemini 3.8 已退役，Kimi K3 暂无通道。系统保存固定错误码、未知费用和真实 Trace，不自动切换模型。
