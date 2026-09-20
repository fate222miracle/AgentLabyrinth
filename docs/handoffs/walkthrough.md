# M1 切片 C 整改与复核交付 (2026-09-20 Remediation Walkthrough)

根据 Codex 2026-09-20 审查意见（`docs/handoffs/M1-slice-C-review-20260920.md`），4 项问题已整改，切片 C 已签收；随后完成切片 D 的 BFCL 改编子集核心闭环。当前全量 85 项测试通过。

## 切片 D 交付摘要

- 上游固定为 BFCL commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`；原始问题、答案与转换快照均校验 SHA256。
- 选择 `simple_python_0` 至 `simple_python_7`，development/evaluation 各 4 道且不重叠；不包含 Live、并行、多工具或任意代码执行。
- 新增独立 BFCL Adapter、单调用 Environment 与本地精确 Evaluator，复用已有 `run_episode`、Runtime、Registry、Trace、预算和 JSON 持久化。
- API 与网页可选择 suite/task，明确显示来源和 `AgentLabyrinth-adapted subset`；ToolLab 对照实验仍只列原生任务。
- 浏览器真实运行 `simple_python_0`：GLM 5.3 的 Episode `6e1ea4db-568b-4db2-9646-75dd44c37d11` 保存 `RATE_LIMIT_EXCEEDED`，GLM 5.2 的 Episode `b5659967-5c72-4149-9c77-ab8b45b9433e` 保存 `MODEL_NOT_FOUND`；刷新后只读回放一致。
- 复现与源码学习入口见 `README.md` 和 `docs/learning/M1-bfcl-adapter.md`。

---

## 一、整改落实对比表

| 审查项 | 严重度 | 原有问题 | 整改落实与代码位置 |
| :--- | :--- | :--- | :--- |
| **1. 禁止工具与参数错误并存重试** | **P1** | 校验器先返回 `INVALID_ARGUMENTS`，Runtime 在判断 `permitted` 前进入重试，导致禁止工具发生两次模型调用 | [registry.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/packages/tools/registry.py) & [runtime.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/packages/runtime/handwritten/runtime.py)：在校验器和执行循环中，未知工具（`UNKNOWN_TOOL`）与禁止工具（`FORBIDDEN_TOOL` / `not permitted`）优先于参数校验和恢复分支立即终止，单次模型调用，零工具执行，`retry_eligible=false`。 |
| **2. API 路径覆盖完整模型配置** | **P1** | Runner 已保存包含 provider/model/temp/max_tokens 的模型对象，但 `exp_config.update(config_metadata)` 将其覆盖为请求中的模型名字符串；缺省请求 scenario 存为 null | [service.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/apps/api/service.py) & [experiment.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/packages/application/experiment.py)：解析实际运行的 `resolved_scenario`（非 null）；`exp_config["model"]` 保持权威字典快照不被字符串覆盖；参数和场景变化真实反映到 `config_hash`。 |
| **3. 旧实验被默认值重新解释 (4/0)** | **P2** | 读历史 JSON 时 `retry_eligible_count` 缺失被赋默认 0，保留 `retry_recovery_count=4`，UI 显示“4 / 0 可恢复样本”；新增调用量默认 0 被当成已测量值 | [experiment.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/packages/application/experiment.py) & [App.tsx](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/apps/web/src/App.tsx)：Schema 字段调整为 `int | None = None`，旧文件保留 `None`；前端对 `retry_eligible_count == null` 显示为“4 例，历史版本未统计可恢复基数”，调用量显示为 `- / -`，表格显示“基数未统计”。 |
| **4. 历史 Fake 实验模型选项失配** | **P2** | 创建 Fake 实验保存 `fake-model`，历史读取直接赋给 `expModel`，因模型目录只有 `fake` 导致失配，再次运行时被误提交为 AIHubMix；页面加载时 meta 默认值覆盖 URL 已恢复状态 | [App.tsx](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/apps/web/src/App.tsx)：新增 `resolveModelOptionId` 映射函数；`useEffect` 中仅在无 URL 参数时应用 meta 默认模型/任务，防止覆盖 URL 恢复状态；再次运行确保保持 Fake provider。 |

---

## 二、新增与针对性回归测试

1. **`tests/unit/test_recovery_runtime.py`**:
   - `test_forbidden_tool_with_invalid_arguments_terminates_immediately`：验证禁止工具调用且带有非法参数时，单次模型调用，0 次工具执行，终止原因为 `TerminationReason.FAILED`（`forbidden_tool: query_records`），记录 `FORBIDDEN_TOOL` 事件。
2. **`tests/unit/test_experiment_runner.py`**:
   - `test_forbidden_tool_with_invalid_arguments_not_retry_eligible`：成对实验下禁止工具且参数非法时，`retry_eligible == False`，`retry_eligible_count == 0`，`baseline_model_calls == 1`。
   - `test_read_legacy_experiment_artifact_preserves_none`：直接读取 `artifacts/experiments/c1c9fe30-d820-4589-81ee-b4a86bcbe964.json`，验证 `retry_eligible_count`、`baseline_avg_model_calls` 保持为 `None`，不赋默认 `0`。
3. **`tests/unit/test_api.py`**:
   - `test_execute_experiment_preserves_full_model_config_and_scenario`：通过 API 执行实验，读取落盘文件，断言 `config.model` 保持为字典（含 provider, model, temp, scenario），断言 `scenario` 解析为 `"invalid-then-success"`（非 null），并断言场景变更会产生不同的 `config_hash`。

---

## 三、质量门禁执行汇总

- **`pytest`**：`75 passed in 1.50s`（全量通过）
- **`ruff check .`**：`All checks passed!`（0 告警，0 错误）
- **`ruff format --check .`**：`72 files already formatted`
- **`mypy packages apps/api`**：`Success: no issues found in 27 source files`
- **`git diff --check`**：退出码 0，零空白字符错误
- **`npm.cmd --prefix apps/web run build`**：`built in 704ms`，零打包与类型错误
