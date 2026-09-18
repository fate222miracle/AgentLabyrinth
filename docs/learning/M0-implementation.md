# M0 内部实现源码阅读与调用链说明

M0 解决的问题：让模拟模型通过公开观察选择工具、取得证据并提交答案，再由独立评测器根据状态与事件判定结果。这里的模型和费用都是模拟值。

## 1. 源码阅读顺序

1. `packages/domain/models.py` & `ports.py`：先看跨模块数据与接口。
2. `packages/application/runner.py` & `trace.py`：看 Episode 入口、最终判定、配置哈希和事件记录。
3. `packages/tools/registry.py` & `executor.py`：了解工具注册、严格参数 Schema、无副作用校验与防御性执行。
4. `packages/environments/tool_lab/environment.py`：了解模拟订单、查询和提交的状态变更、公开 Observation 与私有 Snapshot。
5. `packages/providers/fake.py`：了解 Fake 如何从公开观察和工具反馈提议操作。
6. `packages/runtime/handwritten/budget.py` & `runtime.py`：看预算与主循环的停止点。
7. `packages/evaluation/order_status.py`：看独立评分及指标。
8. `scripts/demo.py`：看组装入口与 JSON 输出。

## 2. 核心调用链

```text
scripts.demo (main)
  ├── 1. 读取 AgentSpec & TaskSpec (文件 IO，asyncio.run 外)
  ├── 2. 实例化组件:
  │     ├── FakeModelProvider(scenario=...)
  │     ├── ToolLabEnvironment (绑定 Registry/Executor)
  │     ├── DefaultToolValidator (共享 Registry)
  │     ├── HandwrittenRuntime (注入 Provider & Validator)
  │     └── OrderStatusEvaluator
  ├── 3. asyncio.run(run_episode(...))
  │     ├── JsonTraceRecorder (EPISODE_STARTED)
  │     ├── HandwrittenRuntime.run(...)
  │     │     ├── environment.reset(...) → OBSERVATION_CREATED
  │     │     ├── Loop:
  │     │     │    ├── BudgetTracker.can_call_model()
  │     │     │    ├── MODEL_REQUESTED (step_idx)
  │     │     │    ├── provider.generate(messages, tools, config)
  │     │     │    ├── BudgetTracker.accrue_usage(...) → MODEL_RESPONDED
  │     │     │    ├── ToolCall proposed:
  │     │     │    │    ├── TOOL_CALL_PROPOSED
  │     │     │    │    ├── ToolValidator.inspect(...) → TOOL_CALL_VALIDATED
  │     │     │    │    ├── Check duplicate call_id / arguments_valid / permitted
  │     │     │    │    ├── BudgetTracker.can_start_tool()
  │     │     │    │    ├── TOOL_STARTED (tool_call_count++)
  │     │     │    │    ├── environment.step(action)
  │     │     │    │    ├── TOOL_SUCCEEDED / TOOL_FAILED
  │     │     │    │    └── ENVIRONMENT_UPDATED (done?)
  │     │     │    └── FinalAnswer proposed → end with FAILED (missing_submission)
  │     │     └── Return EpisodeResult with snapshot & usage
  │     ├── OrderStatusEvaluator.evaluate(task, episode, events)
  │     │     ├── Validate submission answer & evidence match
  │     │     ├── Check evidence query provenance
  │     │     └── Calculate tool_selection_accuracy, validity_rate, coverage, forbidden_count
  │     ├── Finalize EpisodeResult termination_reason with Evaluator verdict
  │     └── JsonTraceRecorder (EPISODE_FINISHED)
  └── 4. write_artifact (JSON Trace 输出，asyncio.run 外)
```

## 3. 关键状态变化与失败路径

- **成功路径 (`success`)**：
  - Turn 1: Model 提议 `query_records` $\rightarrow$ Validated $\rightarrow$ Started $\rightarrow$ Environment 查询 order ORD-001，记录 evidence ID `"order:ORD-001"` $\rightarrow$ Feedback 追加到 Message 历史。
  - Turn 2: Model 提议 `submit_answer` (`answer="shipped"`, `evidence=["order:ORD-001"]`) $\rightarrow$ Validated $\rightarrow$ Started $\rightarrow$ Environment 保存 submission，`done=True` $\rightarrow$ Runtime 返回 `SUCCESS` $\rightarrow$ Evaluator 校验通过 $\rightarrow$ Exit Code 0.

- **错误答案路径 (`wrong-answer`)**：
  - Turn 2: Model 提交 `answer="processing"` $\rightarrow$ Runtime 正常结束，Evaluator 发现答案不匹配 $\rightarrow$ Runner 将 termination_reason 调整为 `FAILED` $\rightarrow$ Exit Code 1.

- **参数错误路径 (`invalid-arguments`)**：
  - Turn 1: Model 提议 invalid `query_records` (`table="invalid_table"`) $\rightarrow$ `TOOL_CALL_VALIDATED` 记录 `arguments_valid=False`, `error_code="INVALID_ARGUMENTS"` $\rightarrow$ Runtime 立即终止为 `FAILED` (`invalid_arguments: INVALID_ARGUMENTS`) $\rightarrow$ 不触发 `TOOL_STARTED` $\rightarrow$ Exit Code 1.

- **超出上限路径 (`max-steps`)**：
  - Turn 1..6: Model 不断循环提议 `query_records` $\rightarrow$ 达到 `max_tool_calls=5` 限制 $\rightarrow$ Runtime 终止为 `MAX_STEPS` (`max_tool_calls_reached`) $\rightarrow$ Exit Code 1.

## 4. 对象生命周期与停止点

每次 `run_episode` 新建 Recorder；Runtime 在本次运行中维护预算和已见 call ID。Environment `reset` 用任务与 seed 重建状态，查询增加已取得证据，提交保存答案并把 `done` 设为 true。Evaluator 只接收 Episode 和事件副本，Runner 根据评测结果写唯一的结束事件。无提交、非法工具或参数、重复 ID、预算触顶、Provider 或 Environment 异常均停止；异常详情不写原始报错文本。

## 5. 本地实验与解读

在仓库根目录执行 `uv run python -m scripts.demo --scenario success --output artifacts/demo_success.json`，再把 `success` 改为 `wrong-answer`。前者两次模型调用、两次工具调用后通过；后者同样完成提交，但独立评测因答案错误将最终 Episode 标记为 FAILED。两次模型响应均来自 Fake，不能推断真实模型成功率。四场景完整结果见 `docs/experiments/M0-execution.md`。

## 6. 刻意保留的边界

M0 仅有一个订单任务，没有真实模型、超时重试、时间预算、批量实验或 Replay 产品。JSON Trace 可严格重读，但没有数据库查询与崩溃恢复。

## 7. 阅读后检查问题

1. 为什么 `submit_answer` 的 `done=true` 还不能代表任务成功？
2. 未经查询而提交正确证据，Evaluator 在哪里拒绝？
3. 工具参数通过校验后，为什么 Environment 仍要通过 Executor 复验？
4. 第六次工具提议被拒绝时，模型调用和工具执行次数各是多少？
