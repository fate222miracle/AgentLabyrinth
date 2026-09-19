# AgentLabyrinth

面向 AI Agent 的可复现实验平台。唯一权威需求：`docs/product/requirements.md` **V0.5**。

**M0 模拟订单闭环与 M1 真实模型 CLI 已复核；M1 切片 B 网页单次运行与切片 C 对照实验闭环已交付。公开数据集 BFCL 顺延至切片 D，完整 M1 与 V0.1 尚未验收。**

课程演示 M1 推进：
- 切片 A：完成 AIHubMix 真实 ToolLab 闭环。
- 切片 B：完成 Web 演示单次执行与 Trace 回读。
- 切片 C：已完成 Baseline 与 Recovery Agent 对照实验闭环（见 `docs/tasks/M1-slice-C-antigravity.md` 与 ADR-004）。扩充至 4 个 ToolLab 原生任务，提供串行 Experiment API、聚合对照卡片、成对比较表格（可穿透查看两造 Trace）与 URL 状态持久化。
- BFCL 顺延至切片 D。最新状态见 `docs/handoffs/current-state.md`。

Codex 负责 Domain 契约、预算与评测审查；Antigravity 负责内部实现（`HandwrittenRuntime` 容错重试分支、`run_experiment` 串行编排、4 条原生 TaskSpec、FastAPI 实验端点与 Web 对照视图）。

## 启动与检查

需要 Python 3.12 和 uv。在项目根目录运行一键检查脚本：

```powershell
./scripts/check.ps1
```

脚本锁定同步依赖，依次运行 Ruff 格式、Lint、mypy、pytest（49 项测试全数通过），失败立即停止。需要先安装 `uv` 并让终端能找到它。

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

详见 `docs/learning/M0-implementation.md`、`docs/experiments/M0-execution.md` 与 `docs/handoffs/current-state.md`。

## 局限

当前已接入 4 个原生 ToolLab 订单任务（ORD-001 shipped, ORD-002 delivered, ORD-003 cancelled, ORD-004 pending 紧凑预算）。
对照实验严格以串行方式执行，不引入后台队列或数据库；容错仅限于 `INVALID_ARGUMENTS` 且最多 1 次重试，不猜测业务字段，不放宽通用校验规则；BFCL 数据集尚未接入（顺延至切片 D）。
真实第三方网关模型存在上游退役或通道波动（如 `gemini-3.7-flash-free` 上游下线、`coding-kimi-k3-free` 偶发无可用通道），系统以 `RUNTIME_ERROR` 安全兜底，严禁伪造 Token 与费用。
