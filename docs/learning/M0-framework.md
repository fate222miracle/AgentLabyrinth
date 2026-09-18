# M0 框架阅读指南

当前解决的是“如何让不同模块在同一套契约下协作”，还没有实现完整订单执行循环。本文描述当前可读代码，并标记下一阶段。

## 阅读顺序
1. `docs/adr/ADR-001-runtime-strategy.md` 与 ADR-002：理解边界及当前范围。
2. `packages/domain/models.py`：Agent/Task、Action、结果与事件。
3. `packages/domain/ports.py`：找出可替换的 Runtime/Provider/Environment/Evaluator 和 ToolValidator。
4. `packages/application/runner.py::run_episode`：编排入口，先运行再评分。
5. `packages/application/trace.py::JsonTraceRecorder`：事件如何隔离、过滤和保存。
6. `tests/contract/test_framework.py`：从 test_runner_evaluation_and_roundtrip 开始，观察评分 true/false 的差异。
7. `docs/tasks/M0-antigravity.md`：尚未实现的内部循环如何接入。

## 当前实际调用链
pytest → asyncio.run(run_episode) → JsonTraceRecorder → StubRuntime.run → StubEnvironment.reset → StubEvaluator.evaluate → EPISODE_FINISHED → write_artifact/read_artifact。

Stub 在 tests 内，只检验框架边界，不是产品 Fake。后续替换为 HandwrittenRuntime 与 ToolLab，Runner 应不需变化。

## 对象生命周期和状态
- Agent/Task/RunConfig 在 Runner 入口深拷贝，保存输入及内容 hash；适配器再拿独立副本。
- 每次调用创建新 UUID 和 Recorder；STARTED 是第一个事件。
- Runtime 返回暂定运行结果。测试里它报告 SUCCESS。
- Evaluator 收到独立结果和事件副本；即使测试故意修改嵌套字典，也不会污染最终 artifact。
- 评分 true → 最终 SUCCESS；评分 false → 最终 FAILED。唯一 FINISHED 由 Runner 写入。
- Recorder 返回的事件也是副本；FINISHED 后禁止继续追加。
- 文件写入在同步函数完成。JSON 读取只校验数据，不调用模型，不等于已有 Replay 产品。

## 已验证的失败路径
非法类型/未知字段 → Pydantic 拒绝；未知父事件/倒退步骤/完成后追加 → Recorder 拒绝；评分失败 → FAILED；未处理 Runtime 异常 → RUNTIME_ERROR，隐藏异常原文，并显式标记 usage/state 不完整。

尚待实现：工具参数校验、预算控制、真实状态转移、错误提议、模型解析失败和订单证据评测。不能把类型层的预算正数检查称作已实现 Budget Controller。

## 本地实验
先运行 `./scripts/check.ps1`。再运行：

```powershell
uv --cache-dir .uv-cache run --locked pytest -v tests/contract/test_framework.py -k runner_evaluation --basetemp artifacts/pytest-temp
```

固定 StubRuntime，只改变 StubEvaluator.success。这是框架行为对照，不是 Agent 能力实验。实际结果见 experiments 文档。

## 读完应能回答
- 为什么 Runtime SUCCESS 不直接等于任务完成？
- frozen 模型为何仍需深拷贝嵌套字典？
- Provider 能否拿到私有答案或自行执行工具？
- 一个事件的 parent 为什么必须先存在？
- 为什么 Runner 的异常兜底不能替代 Runtime 的预算和失败处理？
- Antigravity 增加 ToolLab 后，应改哪个实现而不改 Runner？

暂无真实模型、超时重试、数据库、多 Agent 等机制；Antigravity 实现后需补上真实订单调用链、每步快照及四场景结果。
