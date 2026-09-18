# Antigravity 执行任务：填充 M0 内部实现

SSOT：`docs/product/requirements.md` V0.5。负责 Agent：Antigravity。先完整阅读需求、AGENTS、ADR-001/002、current-state、M0 任务卡、现有代码与测试。低于该需求版本先同步。

## 授权与目标
用户指定 Codex 搭框架、Antigravity 填充实现、Codex 最后审查。本任务卡授权跨以下 M0 实现目录；没有授权修改 Domain 语义、公共 Port、Trace Schema 或评测口径。若发现契约确有缺口，先记录具体调用例、影响和 Proposed ADR，交回 Codex/负责人决定，不静默改接口。

在现有 run_episode 上接通一个订单任务、Fake、手写 Runtime、工具、环境与独立评测，交付真实运行的 JSON Trace 和 CLI 实验。

## 允许修改
- 新建 `packages/providers/fake.py`。
- 新建 `packages/tools/registry.py`、`executor.py`。
- 新建 `packages/environments/tool_lab/environment.py` 及订单参数、状态类型。
- 新建 `packages/runtime/handwritten/runtime.py`、`budget.py`。
- 新建 `packages/evaluation/order_status.py`。
- 新建 `scripts/demo.py`（用 `uv run python -m scripts.demo` 运行）及必需的包初始化文件。
- 新建 `benchmarks/tool_lab_core/agents/baseline-m0.json`，补充任务说明，不扩充为 12 任务。
- 新增 unit/contract/integration/e2e 测试；不得删除或放宽现有框架测试。
- 更新 README、learning、experiments、current-state，并把新增 scripts Python 文件纳入 Ruff/mypy。

禁止修改 `docs/product/requirements.md`、现有 ADR 的已接受结论、`packages/domain/`、`packages/application/` 与锁文件来绕过失败。确有问题写交接，不自行掩盖。

## 串行实现顺序与契约

### 1. Registry / Executor / ToolLab
Registry 将名称映射到参数模型及 handler；拒绝重复注册。参数模型 strict=True、extra=forbid，嵌套同样严格。JSON Schema 从同一参数模型生成，不能手写一份与实际验证不一致的 Schema。

`ToolValidator.validate(action, allowed_tools)` 是无副作用方法；实现注册查找 → 参数校验 → 权限。组装时同一 Registry/Executor 实例注入 Runtime 和 ToolLab。Runtime 验证后做预算检查，环境 step 通过该 Executor 防御性复验，再执行 handler。不要在工具内部记录第二套 Trace。

工具参数固定：
- query_records：table 只能是 orders；filters 只允许非空 order_id 字符串。
- submit_answer：非空 answer 字符串、非空 evidence 字符串列表；多余字段和隐式类型转换拒绝。

ToolLab.reset 从 TaskSpec.initial_state 读取模拟数据，独立拷贝，保存 seed、已返回的 evidence ID、submission。公开 Observation 只包含任务描述/目标订单 ID/反馈，不包含 goal_conditions 和尚未查询的记录；Fake 不接收完整 TaskSpec。

query 返回结构化记录并记录已取得证据；submit 只保存提交并令 StepResult.done=true，不判答案正确。只允许已注册的受控工具。snapshot/restore 严格校验并深拷贝；恢复仅用于状态契约，不做 Runtime Resume。

### 2. FakeModelProvider
实现 ModelProvider.generate。正常模式根据公开 observation 查询 ORD-001，再从 tool 消息读 status/evidence 并提交；不能读取私有 goal_conditions 或把 shipped 写死为预知答案。允许显式脚本模式注入错误响应供测试。Fake usage 必须模拟标记、Decimal 费用；不读取网络/文件/真实密钥。

### 3. HandwrittenRuntime / Budget
实现 AgentRuntime.run 原签名；构造函数注入 Provider 与 ToolValidator。seed 从 recorder.run_config 取；Runtime reset 环境，记录初始快照与 observation。

循环顺序：检查下一模型调用预算 → MODEL_REQUESTED → Provider → 校验响应并核算 Token/费用 → MODEL_RESPONDED → TOOL_CALL_PROPOSED → validate → TOOL_CALL_VALIDATED → 工具预算 → TOOL_STARTED → environment.step → TOOL_SUCCEEDED/TOOL_FAILED → ENVIRONMENT_UPDATED → 追加公开工具反馈。提交 done 后返回，不再请求模型。只由 Runner 写 EPISODE_FINISHED。

计数和停止规则：step_count=model_call_count=实际请求次数；tool_call_count=真正开始执行的次数。步骤上限取 Agent/Task 的较小值；Token 同时受 Agent 分项上限和 Task 总 Token 上限约束。调用前计数，异常仍计入已尝试请求。触及 Token/费用上限时不执行该响应的工具；触及工具次数上限后不再执行下一工具。重复 call_id 在执行前拒绝，参数错误不修复、不重试。FinalAnswer 直接结束为 FAILED/detail=missing_submission。

未知工具、参数错误、禁止工具、重复 ID → FAILED，带安全错误 code。最大步骤/模型数/工具数 → MAX_STEPS + 具体 detail；Token → TOKEN_BUDGET_EXCEEDED；费用 → COST_BUDGET_EXCEEDED；无法解析响应、Provider/Environment 未预期错误 → RUNTIME_ERROR。保留已知状态和已用预算，不能依赖 Runner 的不完整兜底。不要吞掉取消信号。

### 4. 独立 Evaluator
只读 task、EpisodeResult.final_state 和 events；不得调用 Environment 或 Provider。成功必须满足：运行正常提交、答案等于目标、提交证据与目标一致且全部出现在实际成功查询结果、expected_tools 被成功执行、无 forbidden_tools 提议。

M0 指标口径（不要自改）：
- tool_selection_accuracy = 名称属于 expected_tools 且不属于 forbidden_tools 的提议数 / TOOL_CALL_PROPOSED 数；零分母为 null。
- tool_argument_validity_rate = 仅通过参数 Schema 校验的提议数 / 提议数；未知工具计无效。TOOL_CALL_VALIDATED.payload 必须分别记录 arguments_valid、permitted、error_code，不能把权限拒绝冒充参数错误。
- forbidden_tool_call_count 按提议数；expected_tool_coverage 按成功执行的不同名称数 / expected_tools 不同名称数（空集合为 null）。
- 输出 step/model/tool 次数、Token、估算费用、时延和终止原因时使用 Episode 的实际字段，不重新猜测。

### 5. CLI 与交付
组装 Port 并调用现有 Runner；文件读写位于 asyncio.run 外。CLI 运行正常和负例，提供 --scenario success/wrong-answer/invalid-arguments/max-steps 与 --output，输出 JSON Trace 路径和明确退出码（成功 0、任务失败 1、配置错误 2）。禁止业务代码 print；CLI 输出允许。输入路径从项目位置解析或 CLI 指定，不硬编码本机目录。

## 必须新增并执行的验收测试
1. 严格参数：缺字段、多字段、字符串冒充数值/布尔、嵌套未知字段；拒绝不改变状态。
2. 未知/禁止工具、重复注册、重复 ToolCall ID；已开始执行计数准确。
3. reset 同 task/seed 相同；snapshot/restore 拷贝隔离；查询后 evidence 更新，提交后 done。
4. 独立评分：正确、错误答案、伪造证据、正确但未查询证据、只有 FinalAnswer。
5. 每类预算恰好达到/超过上限；请求前/执行前均不越过下一行动；Decimal 精确。
6. 模型无法解析、Provider/Environment 异常；安全错误和最后已知状态仍可追踪。
7. Fake/ToolLab/Runtime/Evaluator 各自 Port 契约；更换测试用 Environment 无需改 Runner。
8. 完整两轮成功 Episode，Trace 因果链及配置 hash、UUID、UTC、JSON roundtrip。
9. CLI 子进程成功与失败退出码和 artifact；参数错误发生时没有 TOOL_STARTED。

运行 `./scripts/check.ps1`；另运行四种场景并记录实际结果。禁止用 xfail、skip 或放宽断言把未实现伪装成通过。

## 完成报告
更新 current-state 和学习文档：修改文件、入口与调用链、关键状态、失败路径、实际检查输出、Fake 对照结果、已知问题。全部是 Fake，不得声称真实模型提升。不要提交/推送；交回 Codex 审查后由用户验收。
