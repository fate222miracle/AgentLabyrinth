# M1 切片 C 整改与复核交付 (Remediation Walkthrough)

根据 Codex 最新的代码审查意见（`docs/handoffs/current-state.md` 第 126 行及 3 项 P1 级审查反馈），已全面完成 M1 切片 C 的整改工作。

---

## 一、整改完成项对比

| 审查项 | 原有问题 | 整改落实与代码位置 |
| :--- | :--- | :--- |
| **1. 挽救过度归因与分母** | 任意基准失败且容错成功均算作挽救，分母误用总任务数 | [experiment.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/packages/application/experiment.py)：严格定义 `retry_eligible = (not base_success) and (base_term == TerminationReason.FAILED) and ("invalid_arguments" in base_detail)`，`recovered = retry_eligible and rec_success`；分母严格使用 `retry_eligible_count`。 |
| **2. 固定变量与配置哈希** | 产物未保存完整 Agent、模型、预算、TaskSpec 版本和评分器 | [experiment.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/packages/application/experiment.py)：`exp_config` 完整保存 `baseline_agent`、`recovery_agent`、`model`、`budget`、`tasks`（含版本与预算）、`evaluator`、`seed`、`environment_version`，并据此计算 SHA-256 `config_hash`。 |
| **3. 补齐指标** | 缺少模型调用、工具调用、工具选择率与参数合法率汇总 | [experiment.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/packages/application/experiment.py)：`ExperimentAggregateMetrics` 与 `PairComparison` 完整补齐 `model_calls`、`tool_calls`、`tool_selection_accuracy`、`tool_argument_validity_rate` 及其平均值。 |
| **4. 阻塞网络 I/O** | `/api/v1/meta` 同步执行 `urllib.request.urlopen` 阻塞 1.5s | [service.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/apps/api/service.py)：彻底删除动态网络请求，纯粹读取版本化 `models.json`，元数据接口毫秒级返回。 |
| **5. 模糊字符串判断** | `is_model_permitted` 用 `"free" in model_id` 判定免费模型 | [schemas.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/apps/api/schemas.py)：彻底废除字符串推断，只接受 `ALLOWED_AIHUBMIX_MODELS` 及显式白名单模型。 |
| **6. 任务文档** | `tool_lab_core/README.md` 仅包含 1 条任务说明 | [README.md](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/benchmarks/tool_lab_core/README.md)：详尽补全全部 4 条原生任务的设计意图、初始状态、预期工具轨迹、成功条件与负例、步数与预算限制。 |
| **7. 历史实验展示** | 回读时实验配置重置为默认模型，与结果不一致 | [App.tsx](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/apps/web/src/App.tsx)：历史回读自动从 `config` 恢复控件状态，并在指标区顶部提供专用的“已保存实验配置”固定变量面板。 |
| **8. 边界与负例测试** | 缺少非 `INVALID_ARGUMENTS` 误判测试、重复 call ID 与预算不足测试 | [test_experiment_runner.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/tests/unit/test_experiment_runner.py) & [test_recovery_runtime.py](file:///c:/Users/Netlab/.gemini/antigravity-ide/scratch/AgentLabyrinth/tests/unit/test_recovery_runtime.py)：补齐误判测试与边界测试，测试集由 68 项增至 71 项。 |
| **9. 文件尾空白** | `git diff --check` 报警 `README.md` 与 `index.css` 尾部空行 | 清理两处尾部多余空白行，`git diff --check` 零告警退出。 |

---

## 二、测试与质量门禁执行结果

全套门禁实测全部通过：

1. **`pytest`**：`71 passed in 1.27s`
   - 新增 `test_misattribution_non_invalid_arguments_not_recovered`
   - 新增 `test_recovery_does_not_retry_duplicate_call_id`
   - 新增 `test_recovery_does_not_retry_when_budget_exceeded`
2. **`ruff check .`**：`All checks passed!`（0 告警，0 错误）
3. **`ruff format --check .`**：`69 files already formatted`
4. **`mypy packages apps/api tests`**：`Success: no issues found in 43 source files`
5. **`git diff --check`**：退出码 0，零空白字符错误。
6. **`npm.cmd --prefix apps/web run build`**：`built in 631ms`，零 TypeScript / 打包错误。

---

## 三、移交检查清单 (For Codex)

- [x] 挽救转化率公式：`retry_recovery_count / retry_eligible_count`（分母严格为 Baseline 发生 `INVALID_ARGUMENTS` 的样本数）。
- [x] 汇总产物包含完整固定变量（AgentSpec、Runtime 策略、模型参数、预算、TaskSpec 清单及版本、评分器）与对应 `config_hash`。
- [x] 模型调用数、工具调用数、工具选择准确率、参数合法率完整进入产物与页面表格。
- [x] `/api/v1/meta` 无任何网络阻塞 I/O，安全恢复版本化白名单。
- [x] 4 条任务设计意图与轨迹已完整写入 `benchmarks/tool_lab_core/README.md`。
- [x] 历史实验回读控件同步恢复且展示固定变量只读卡片。
