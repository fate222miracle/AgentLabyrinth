# Current state

更新：2026-09-18。需求唯一来源：`docs/product/requirements.md` **V0.5**。不依赖历史聊天。

## 当前阶段
**M1 切片 A 已由 Codex 以 Gemini 真实联网 Episode 签收；当前进入切片 B。** 这证明至少一个真实模型与 ToolLab 的闭环可运行，不代表四个模型均通过，也不等于完整 M1/V0.1 验收。
- 针对用户选取的 4 个免费模型已完成横向实测：
  1. `gemini-3.7-flash-free`：**完全通过（推荐作为默认）**。Probe 两阶段成功、真实 Episode 完整跑通（2 次工具调用 `query_records` 与 `submit_answer` 全部成功，评测 `submission_matched_target` 判定为 True，Token 消耗 639 prompt / 166 completion，真实非模拟，未超预算）。
  2. `coding-kimi-k3-free`：上游通道故障离线（`UPSTREAM_CHANNEL_UNAVAILABLE`）。
  3. `coding-glm-5.3-flash-free`：原生工具调用正常，但在复杂对象参数时生成嵌套字符串 JSON，被 `ToolValidator` 严格拦截（验证了错误防御路径）。
  4. `deepseek-v4-flash-0731-free`：原生工具调用正常，但第 2 轮 Prompt Token 消耗较大（1592 tokens），被 `HandwrittenRuntime` 的 1000 Token 预算拦截（验证了 Token 预算防护路径）。
- Codex 复核指出的所有问题（安全脱敏、Token 用量与成本精确统计、文档同步、正向工具调用留存）全部达成闭环。

## 核心进展与交付
1. **真实模型正向闭环完成**：
   - 更新 `benchmarks/tool_lab_core/agents/aihubmix-m1.json` 默认模型为 `gemini-3.7-flash-free`。
   - `scripts/demo.py` 支持 `--model` 自由指定模型，增强评测灵活度。
   - 产物 `artifacts/m1_gemini_demo.json` 是 Gemini 的真实正向 Trace；`artifacts/m1_kimi_demo.json` 虽沿用旧文件名，内部模型 ID 实际也是 Gemini，不应作为 Kimi 成功证据。
   - Codex 独立复跑产物 `artifacts/review_gemini_20260918.json`：模型 `gemini-3.7-flash-free`，2 次模型调用、2 次工具执行，`SUCCESS` 且独立评测 `submission_matched_target=True`；639 prompt / 157 completion token，`simulated=False`，费用状态 `is_known=False`。`read_artifact` 严格读取成功，配置哈希与 17 个 Trace 事件核对通过。
2. **安全脱敏与固定错误码**：
   - 标准安全错误码上线，彻底杜绝上游响应体和模型原始参数泄露。
3. **用量与预算准确性**：
   - 严禁伪造 Token，严格标记 `simulated=False`、`is_known=False` 与 `aihubmix-free-unverified`。
4. **自动化测试与代码质量**：
   - Codex 复跑 49 项测试通过（`pytest -q`，49 passed in 0.51s），Ruff 格式与 Lint 通过，mypy 严格模式 38 文件 0 错误。验证在 2026-09-18 完成。

## 下一任务
- **切片 B 的基本网页流程已于 2026-09-18 由 Codex 浏览器复核，公开数据集仍未接入。** 原实现 POST 成功后读取不存在的 `artifact.trace.events`，导致整个 React 页面空白；实际 `EpisodeArtifact` 返回顶层 `events`。Codex 已修复 `apps/web/src/App.tsx` 的类型与 3 处读取。浏览器 Fake success 和 wrong-answer 分别显示 SUCCESS/FAILED、17 条 Trace，事件可展开，刷新后可按 Episode ID 回读。真实网页调用 `gemini-3.7-flash-free` 成功：Episode `dcc1e859-e095-4490-94b7-806949dc3f5c`，SUCCESS，2 次模型调用/2 次工具调用，639 prompt + 214 completion tokens，`simulated=False`，费用未知，耗时 7922 ms，17 条事件；刷新回读成功。`npm run build` 成功；`pytest -q` 58 passed，Ruff check 与 mypy 通过。尚未完成手机宽度、截图复核，因此不宣称切片 B 完整签收。
- **下一步交 Antigravity 执行 `docs/tasks/M1-slice-C-antigravity.md`**：先固定 BFCL 官方 commit/许可/题目与校验值，再接独立 Adapter、评分器、API 和 Web 任务选择。当前 `apps/api/service.py` 只读 `order-status-001.json`，`benchmarks/` 只有这一条原生任务；不能把它当作 BFCL。SSOT 9.7 已增补 M1 的唯一提前接入例外，ADR-003 的改编子集口径仍有效。
- GLM 的字符串化嵌套参数维持严格校验失败；DeepSeek 的 token 预算停止维持原记录。未来若放宽限制，先给出可复现实验问题、固定对照条件和 ADR/SSOT 决策，不在切片 B 顺手修改通用校验器或预算口径。
