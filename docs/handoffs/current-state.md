# Current state

更新：2026-09-22。需求唯一来源：`docs/product/requirements.md` **V0.6**。不依赖历史聊天。

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
**V0.1 的 18 项验收已通过；V0.2 LangGraph Bootstrap 已完成。**
- 下一执行入口为独立 LangGraph 控制循环：使用公共 Provider、Validator、Executor 和预算实现真实节点，再进行 Fake 契约与小样本对照。Bootstrap 委托模式不得作为对照结论。
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
