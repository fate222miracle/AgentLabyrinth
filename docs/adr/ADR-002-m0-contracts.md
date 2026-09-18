# ADR-002：M0 初始契约、ID 与 JSON Trace

## 状态
Accepted（用户已授权 M0 跨模块实现及必要初始 Schema）

## 背景
初始目录只有 V0.5 需求。先交付 Codex 框架，再由 Antigravity 填内部实现；不得把接口骨架当成已完成 M0。

## 候选方案
单文件 Demo；框架托管循环；明确 Port 的手写循环。选择第三种。

## 决策
- packages 为 Python 包根。Domain 保存严格 Pydantic 边界类型与 Protocol，Application 保存 Runner、输入加载与内存 Trace/JSON 边界。具体适配器后续仅在本次实际实现时建包，不创建空服务。
- AgentRuntime.run(agent, task, environment, recorder) 与 ModelProvider.generate(messages, tools, config) 保留需求签名。Environment 的 reset(task, seed)、available_tools、step(action)、snapshot、restore 均为同步内存操作；Runtime/Provider 为异步。seed 由 Recorder.run_config 提供，Runtime 负责 reset；Runner 不重复初始化环境。
- Runtime 返回 EpisodeResult，不判订单对错；正常提交的运行终止暂记 SUCCESS。Runner 把快照、只读事件副本交给独立 Evaluator；只有运行 SUCCESS 且 evaluation.success 才保留 SUCCESS，否则改为 FAILED。EPISODE_FINISHED 只由 Runner 写一次，避免已经落盘的成功事件被修改。异常映射 RUNTIME_ERROR，未知异常不暴露原文。
- Evaluator.evaluate(task, episode, events) 同步纯函数，只读深拷贝；返回 EvaluationResult。成功必须有真实提交及正确答案、正确且实际查询取得的证据。统计分母口径在实现前按子任务卡固定，不用模型自报成功。
- 一轮模型请求返回一个 ToolCall 或一个 FinalAnswer（判别联合）。FinalAnswer 不能替代 submit_answer 完成订单任务。step_count 指模型请求次数。同一 Episode 的重复 ToolCall ID 拒绝；不实现跨进程幂等性。
- Registry/Executor 负责注册查找、strict/extra=forbid 参数校验、权限及标准化错误。其 validate 方法实现 ToolValidator Port，并由组装入口把同一个实例注入 Runtime 和 ToolLab。Runtime 先 validate，再检查预算，然后调用 Environment.step；step 经同一个 Executor 防御性复验并执行注册 handler，不得复制另一套校验器。Runtime 统一记录校验/工具事件，Executor 不另写重复事件。Runtime 与 Environment 的边界只流通 Domain 类型。
- AgentSpec.model 是需求 model_config 的初始 Python 字段名（避开 Pydantic 保留的 model_config 类配置属性）；budget 对应 budget_config。持久化格式以当前 schema 1.0 为准。未使用的 memory/reflection 和超时字段不创建。
- query_records 参数为 table='orders', filters={order_id: str}；submit_answer 参数为 answer: str, evidence: list[str]。订单逻辑只放 environments/tool_lab，工具通用注册执行放 tools，答案判断放 evaluation。
- M0 支持步骤、模型/工具次数、Prompt/Completion Token 和 Decimal 费用限制；触及阈值停止下一行动。调用次数触顶复用 MAX_STEPS，detail 指明是哪项。Token/费用在响应后核算，执行工具前检查；真实模型预留预算和时间限制不在 M0。
- 业务实体 ID 与 Trace ID 使用 UUID；ToolCall ID 保留 Provider 字符串。初始 schema_version=1.0，Agent/Task 另有语义版本。UTC ISO 8601，整数毫秒，Decimal 费用字符串，记录货币、价格表版本及 estimated=true。Fake usage 是模拟值。
- 所有边界模型 frozen/extra=forbid；mutable JSON 在跨 Port、Recorder 读写时深拷贝，不能把 frozen 误当递归不可变。
- Trace 先内存追加，再由同步 CLI 写 JSON；保存完整 Agent/Task/RunConfig 和各自规范 JSON SHA256、环境版本、初始/结束状态、事件及 Evaluation。事件字段以需求 26.3 为准，父事件必须属于本 Episode 已有事件。写文件不在 async 函数内。
- Trace 对敏感键递归脱敏，拒绝隐藏思维链字段；不保证自由文本秘密识别。基准与配置必须只含模拟数据，不含真实秘密；配置 hash 对原始规范内容计算。
- 运行依赖仅 Pydantic v2（MIT），负责严格数据边界和 JSON Schema；标准库缺少该能力。精确版本 uv.lock；pytest/Ruff/mypy 是开发检查。暂不引入未使用的 FastAPI/SQLAlchemy。

## 代价与风险
JSON 无数据库查询、崩溃恢复或并发写保证。当前无真实模型效果结论。只有本次订单用到的初始字段，不预建未来模块。

## 回滚方式
生成 artifacts 可重跑；修改持久化格式或 Port 先新增 ADR 和迁移说明，不能静默重释旧 Trace。
