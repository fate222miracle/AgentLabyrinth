# AgentLabyrinth

面向 AI Agent 的可复现实验平台。唯一权威需求：`docs/product/requirements.md` **V0.5**。

**M0 模拟订单闭环与 M1 真实模型 CLI 已复核；M1 切片 B 的网页基本运行已复核。公开数据集 BFCL 尚未接入，完整 M1 与 V0.1 尚未验收。**

课程演示 M1 已进入开发：切片 A 使用 AIHubMix `gemini-3.7-flash-free` 完成真实 ToolLab 闭环；切片 B 已实现 Web 演示入口。下一步真实数据集接入见 `docs/tasks/M1-slice-C-antigravity.md`。最新状态见 `docs/handoffs/current-state.md`。

Codex 已提供 Domain 契约、Runner、JSON Trace 边界与基础框架测试。Antigravity 已填充 `FakeModelProvider`、`HandwrittenRuntime`、`BudgetTracker`、`ToolRegistry`/`ToolExecutor`、`ToolLabEnvironment`、`OrderStatusEvaluator` 和 CLI Demo 脚本。

## 启动与检查

需要 Python 3.12 和 uv。在项目根目录运行一键检查脚本：

```powershell
./scripts/check.ps1
```

脚本锁定同步依赖，依次运行 Ruff 格式、Lint、mypy、pytest（2026-09-18 复核 58 passed），失败立即停止。需要先安装 `uv` 并让终端能找到它。

本地网页需要分别启动 API 与前端（两个终端，项目根目录执行）：

```powershell
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd apps/web
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:5173/`。真实模型只从后端环境变量 `AIHUBMIX_API_KEY` 读取密钥；未配置时可选 Fake 离线验证。网页目前仅支持本地订单任务 `order-status-001`，不是 BFCL 数据集。若 5173 端口已被占用，以 Vite 终端实际显示的地址为准。

运行 CLI Demo 演示各种场景：

```powershell
# 1. 成功场景 (Exit code 0)
uv run python -m scripts.demo --scenario success --output artifacts/demo_success.json

# 2. 错误答案场景 (Exit code 1)
uv run python -m scripts.demo --scenario wrong-answer --output artifacts/demo_wrong_answer.json

# 3. 参数错误场景 (Exit code 1)
uv run python -m scripts.demo --scenario invalid-arguments --output artifacts/demo_invalid_args.json

# 4. 超出最大步骤场景 (Exit code 1)
uv run python -m scripts.demo --scenario max-steps --output artifacts/demo_max_steps.json

# 5. 本机后端已配置 AIHUBMIX_API_KEY 时，运行真实免费模型（Exit code 依评测结果）
uv run python -m scripts.demo --provider aihubmix --model gemini-3.7-flash-free --output artifacts/real_gemini.json
```

## 架构与阅读入口

```text
scripts.demo
  → application.run_episode
      → HandwrittenRuntime (BudgetTracker, DefaultToolValidator)
          → FakeModelProvider (Normal/WrongAnswer/InvalidArgs/MaxSteps)
          → ToolLabEnvironment (orders db state, query_records, submit_answer)
              → ToolExecutor & ToolRegistry
      → OrderStatusEvaluator (Read-only, deterministic scoring & metrics)
      → JsonTraceRecorder (Append-only event trace)
  → write_artifact (JSON Trace boundary outside asyncio)
```

详见 `docs/learning/M0-implementation.md`、`docs/experiments/M0-execution.md` 与 `docs/handoffs/current-state.md`。

## 局限

当前只有一个开发集订单任务，支持 Fake 与一个已验证的 AIHubMix 免费模型；Web UI 已有单次运行和 JSON 回读，但尚无 BFCL、数据库、批量 Experiment、多 Agent 或 GridWorld。真实模型的费用仍标为未知；异常兜底会明确标记 usage/state 不完整。Trace 按敏感键过滤，自由文本仍须由调用方保证没有秘密。

后端依赖含 Pydantic、FastAPI、uvicorn 和 httpx；前端依赖 React/Vite。精确版本见锁文件。复核实验与依赖审计见 `docs/experiments/M0-execution.md`。
