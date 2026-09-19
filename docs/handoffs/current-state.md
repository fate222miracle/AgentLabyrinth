# Current state

更新：2026-09-19。需求唯一来源：`docs/product/requirements.md` **V0.5**。不依赖历史聊天。

## 当前阶段
**M1 切片 A、B 已完成复核；切片 C（Baseline vs Recovery Agent 对照实验闭环）已完成开发，但 Codex 首轮复核未通过，切片 D 继续锁定。**
- 严格落实 ADR-004 决策边界：BFCL 顺延为切片 D，切片 C 聚焦在相同模型、任务、工具、种子与预算下，对比 Baseline 与一次受控参数容错重试的 Recovery Agent 表现。
- 完成 4 个原生 ToolLab 任务（ORD-001 shipped, ORD-002 delivered 多订单库, ORD-003 cancelled, ORD-004 pending 紧凑预算）。
- 完成 Application 串行对照实验 Runner 与指标聚合（成功率、挽救率、Token 增量、平均步数与耗时）。
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

## Antigravity 质量门禁（切片 C 整改后实测通过）
- **pytest**：`71 passed in 1.27s`（涵盖 recovery runtime, experiment runner, API, fake provider, evaluator，包含本次整改新增的误判负例、重复 call ID、预算不足不重试测试）。
- **ruff format --check .**：69 个文件格式完全合规。
- **ruff check .**：All checks passed（0 告警，0 错误）。
- **mypy**：`Success: no issues found in 43 source files`（无类型告警）。
- **git diff --check**：退出码 0，零空白字符错误（`README.md` 与 `apps/web/src/index.css` 尾部空行已清理）。
- **web build**：`npm.cmd --prefix apps/web run build` 耗时 631ms，零错误打包。

---

## 下一步移交说明 (To Codex)
- 切片 C 整改已全部完成，交付物已由 Antigravity 自测并通过全部门禁，现提交 Codex 最终复核。

### 切片 C 整改落实清单 (2026-09-19)

1. **修正 `retry_eligible`、`recovered` 与挽救率分母**：
   - 在 `packages/application/experiment.py` 中，`retry_eligible` 严格从 Baseline Trace 确认失败原因为 `INVALID_ARGUMENTS`（`detail == "invalid_arguments"` 且终止于 `FAILED`）。
   - `recovered` 判定严格绑定 `retry_eligible and rec_success`。
   - `retry_recovery_rate` 严格以 `retry_eligible_count`（可恢复样本数）为分母。
   - 在 `tests/unit/test_experiment_runner.py` 中新增 `test_misattribution_non_invalid_arguments_not_recovered` 负例测试。
2. **完整保存实验固定变量并计算配置哈希**：
   - `exp_config` 保存全部固定变量：`baseline_agent`、`recovery_agent`、`model`、`prompt_version`、`tool_set_version`、`budget`、`tasks`（包含 id, name, version, max_steps, token_budget, evaluator_config）、`evaluator`、`seed`、`environment_version`。
   - 据此计算 SHA-256 `config_hash`，证明 ADR-004 固定变量公平性。
3. **补齐调用次数、工具选择和参数合法率指标**：
   - `PairComparison` 与 `ExperimentAggregateMetrics` 均补齐 `model_calls`、`tool_calls`、`tool_selection_accuracy`、`tool_argument_validity_rate` 及其聚合平均值。
4. **删除同步阻塞网络 I/O，恢复严格版本化模型白名单**：
   - `apps/api/service.py` 彻底移除 `_fetch_upstream_models` 与 `urllib.request.urlopen`，元数据请求毫秒级返回，消除 1.5s 阻塞。
   - `apps/api/schemas.py` 彻底移除 `"free" in model_id.lower()` 字符串推断，严格依据 `ALLOWED_AIHUBMIX_MODELS` 及显式白名单校验。
5. **任务文档与历史展示修复**：
   - `benchmarks/tool_lab_core/README.md` 详尽补全全部 4 条原生任务的设计意图、初始状态、预期工具轨迹、成功与失败条件、步数与预算限制。
   - `apps/web/src/App.tsx` 在历史实验回读时恢复控件状态，并在指标区顶部提供专用的“已保存实验配置”固定变量面板。
   - 文件尾空白清理完成（`git diff --check` 通过）。
6. **边界回归测试与完整交付**：
   - 补齐重复 call ID 立即以 `FAILED` 终止不重试测试（`test_recovery_does_not_retry_duplicate_call_id`）。
   - 补齐预算不足不重试测试（`test_recovery_does_not_retry_when_budget_exceeded`）。
   - 交付 `docs/handoffs/walkthrough.md` 与 Brain artifact walkthrough。
