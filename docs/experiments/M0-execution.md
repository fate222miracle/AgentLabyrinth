# M0 实验与验证记录

本文档记录 2026-09-17 Codex 在 V0.5 契约下复核 M0 的实际结果；所有实验均使用 FakeModelProvider 和本地模拟数据。

## 1. 自动化质量检查命令输出

运行一键检查脚本 `./scripts/check.ps1`：

- **Ruff Format & Lint**：34 个 Python 源码文件格式与 Lint 全部通过。
- **Mypy Strict Type Check**：34 个 Python 源码文件通过。
- **Pytest Unit/Integration/E2E**：最终代码 39 passed in 0.53s。
- **依赖审计**：`uv audit --locked` 退出码 0；16 个包未发现已知漏洞或 adverse status。审计反映执行时的已知记录。
- 本机起初找不到 `uv`；复核时临时安装 `uv 0.12.15` 并使用锁文件同步依赖。最终一处参数校验修正后，使用同一锁定虚拟环境分别复跑 Ruff、mypy 和 pytest；临时 uv 已删除。

## 2. CLI 四场景实验实际运行输出

### 场景 1：成功场景 (`success`)
```powershell
uv run python -m scripts.demo --scenario success --output artifacts/review_success.json
```
- **Exit Code**：`0`
- **Termination Reason**：`SUCCESS`
- **Detail**：`submitted`
- **Evaluation Success**：`True` (`submission_matched_target`)
- **Step / Model / Tool Count**：2 / 2 / 2
- **Token Usage / Cost**：80 prompt / 40 completion ($0.002 USD)
- **Metrics**：`tool_selection_accuracy=1.0`, `tool_argument_validity_rate=1.0`, `forbidden_tool_call_count=0`, `expected_tool_coverage=1.0`

### 场景 2：错误答案场景 (`wrong-answer`)
```powershell
uv run python -m scripts.demo --scenario wrong-answer --output artifacts/review_wrong-answer.json
```
- **Exit Code**：`1`
- **Termination Reason**：`FAILED`
- **Detail**：`submitted`
- **Evaluation Success**：`False`
- **Evaluation Reason**：`answer_mismatch: got 'processing', expected 'shipped'`
- **Step / Model / Tool Count**：2 / 2 / 2

### 场景 3：参数错误场景 (`invalid-arguments`)
```powershell
uv run python -m scripts.demo --scenario invalid-arguments --output artifacts/review_invalid-arguments.json
```
- **Exit Code**：`1`
- **Termination Reason**：`FAILED`
- **Detail**：`invalid_arguments: INVALID_ARGUMENTS`
- **Evaluation Success**：`False` (`runtime_failed: FAILED`)
- **Step / Model / Tool Count**：1 / 1 / 0
- **TOOL_STARTED Event**：`None`（参数错误时未执行工具）

### 场景 4：超出最大步骤场景 (`max-steps`)
```powershell
uv run python -m scripts.demo --scenario max-steps --output artifacts/review_max-steps.json
```
- **Exit Code**：`1`
- **Termination Reason**：`MAX_STEPS`
- **Detail**：`max_tool_calls_reached`
- **Evaluation Success**：`False` (`runtime_failed: MAX_STEPS`)
- **Step / Model / Tool Count**：6 / 6 / 5
- **Token Usage / Cost**：240 prompt / 120 completion ($0.006 USD)
