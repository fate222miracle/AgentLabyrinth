# ToolLab 原生开发与评测任务集 (Native Tasks Suite)

本目录包含 12 条原创设计的原生任务（`order-status-001` 至 `order-status-012`），用于 V0.1 Slice F 的 Agent 评测与对照实验。任务按 `tool_selection`、`parameter_generation`、`multi_step_planning`、`error_recovery` 四类各 3 条组织，使用确定性本地环境和四个 ToolLab 工具，不依赖外部 Benchmark。

---

## 1. 任务清单与设计意图

### 1.1 `order-status-001`：标准基础订单查询
- **设计意图**：验证最简标准工具链（查询 → 获取真实证据 → 提交答案 → 独立评测）。
- **初始状态**：单订单环境，包含 `ORD-001`（状态 `shipped`，证据 `order:ORD-001`）。
- **预期工具轨迹**：
  1. `query_records(table="orders", filters={"order_id": "ORD-001"})`
  2. `submit_answer(answer="shipped", evidence=["order:ORD-001"])`
- **成功条件**：答案为 `shipped`，且提交的证据包含且仅包含 `order:ORD-001`（证据必须来自真实工具查询，不可伪造）。
- **失败条件与负例**：未查询直接提交、错误答案、伪造非环境返回的证据 ID。
- **约束与预算**：最多 6 步，Token 预算 1000。

### 1.2 `order-status-002`：多干扰项精准过滤查询
- **设计意图**：考察模型在存在多条无关/混淆记录的环境下，能否通过精确 `filters` 参数过滤目标订单，而非盲目提取第一条记录。
- **初始状态**：包含 3 条订单记录（`ORD-001: shipped`, `ORD-002: delivered`, `ORD-005: pending`）。
- **预期工具轨迹**：
  1. `query_records(table="orders", filters={"order_id": "ORD-002"})`
  2. `submit_answer(answer="delivered", evidence=["order:ORD-002"])`
- **成功条件**：答案为 `delivered`，且证据精确绑定 `order:ORD-002`。
- **失败条件与负例**：提取了 `ORD-001` 或 `ORD-005` 的状态与证据、全表无过滤扫描导致处理错误、伪造证据。
- **约束与预算**：最多 6 步，Token 预算 1000。

### 1.3 `order-status-003`：已取消订单边缘状态核验
- **设计意图**：检验模型对业务边缘状态（`cancelled` 已取消）的准确辨识与提取，避免预设惯性思维（如默认订单处于配送流）。
- **初始状态**：单订单环境，`ORD-003` 状态为 `cancelled`，证据 `order:ORD-003`。
- **预期工具轨迹**：
  1. `query_records(table="orders", filters={"order_id": "ORD-003"})`
  2. `submit_answer(answer="cancelled", evidence=["order:ORD-003"])`
- **成功条件**：确认已取消状态并提取合规证据 `order:ORD-003`。
- **失败条件与负例**：提交非取消状态（如误报 completed/pending）、伪造证据、未查询即提交。
- **约束与预算**：最多 6 步，Token 预算 1000。

### 1.4 `order-status-004`：紧凑预算下的参数生成
- **设计意图**：检验模型在严苛预算约束（4 步、800 Tokens）下，能否一次生成正确表名与嵌套过滤参数并完成提交。
- **初始状态**：单订单环境，`ORD-004` 状态为 `pending`，证据 `order:ORD-004`。
- **预期工具轨迹**：
  1. `query_records(table="orders", filters={"order_id": "ORD-004"})`
  2. `submit_answer(answer="pending", evidence=["order:ORD-004"])`
- **成功条件**：答案为 `pending`，证据为 `order:ORD-004`，且全链路在 4 步和 800 Tokens 内完成。
- **失败条件与负例**：超出 4 步上限（`MAX_STEPS`）、超出 800 Tokens（`TOKEN_BUDGET_EXCEEDED`）、虚假证据。
- **约束与预算**：最多 4 步，Token 预算 800。

### 1.5 `order-status-005` 至 `order-status-006`：参数生成
- **设计意图**：验证表名、嵌套 filters 和目标 ID 的结构化参数生成。
- **成功条件**：只执行正确的 `query_records` 参数并提交真实证据。

### 1.6 `order-status-007` 至 `order-status-009`：多步文档规划
- **设计意图**：验证 Agent 是否真正执行 `search_documents → read_document → submit_answer`，而不是只在文本中声称完成。
- **成功条件**：搜索摘要、读取完整文档、提交从文档内容解析的答案和实际 `evidence_id`。

### 1.7 `order-status-010` 至 `order-status-012`：错误恢复
- **设计意图**：验证一次 `INVALID_ARGUMENTS` 反馈后的受控恢复。
- **成功条件**：错误调用不执行，恢复调用完成目标；第二次参数错误仍必须终止。

---

## 2. 评测契约与执行规范
- 评分器：`OrderStatusEvaluator`（只读，独立于环境与 Runtime）。
- 工具注册：通过 `ToolRegistry` 强类型校验；非法调用被严格拦截并在 Trace 中产生 `TOOL_CALL_VALIDATED` 事件。
- 幂等性：Seed 保存在环境快照；各任务在相同 Seed 下具备严格确定性。环境还提供了仅用于测试的确定性 `TOOL_TIMEOUT` 路径，Trace 会记录 `TOOL_FAILED` 和终止结果。
