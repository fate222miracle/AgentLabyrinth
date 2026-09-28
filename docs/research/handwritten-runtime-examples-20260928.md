# 手写 Agent Runtime 样例调研（2026-09-28）

依据需求 V0.6 §8、§19。这里只比较公开实现的设计方法，不复制上游代码，也不改变当前 Runtime 契约。

| 样例 | 值得读的代码/说明 | 可借鉴的重点 | 与本项目的距离 |
| --- | --- | --- | --- |
| [mini-SWE-agent 控制循环](https://github.com/SWE-agent/mini-swe-agent/blob/main/docs/advanced/control_flow.md) | `run → step → query → execute_actions → observation`，循环非常短 | 核心循环短是正常现象；价值在模型、环境、状态和终止边界 | 最接近当前手写 Runtime，适合作为源码教学对照 |
| [Hugging Face smolagents](https://github.com/huggingface/smolagents/blob/main/src/smolagents/agents.py) | `MultiStepAgent`、流式步骤、Step 回调与 Memory | 行动与观察的逐步记录、可插入的步骤钩子 | 可借鉴观测方式；不应为了复杂度加入 CodeAgent 执行沙箱 |
| [OpenAI Agents SDK Runner](https://github.com/openai/openai-agents-python/blob/main/docs/running_agents.md) | 模型输出分流到终答、工具与交接；turn 限制、暂停态、工具错误策略 | 明确每个逻辑 turn 的计数、取消与恢复语义 | 功能面远大于课程需求，适合检查失败边界而非整体仿制 |
| [SWE-agent 主循环](https://github.com/SWE-agent/SWE-agent/blob/main/sweagent/agent/agents.py) | 每步保存 trajectory，任务完成后可由 review/retry loop 选择再试 | 轨迹作为可审查产物；策略循环与单步执行分离 | 面向软件工程任务，不能直接当 ToolLab 的任务逻辑 |

当前实现：`packages/runtime/handwritten/runtime.py` 只负责 `model → validate → execute` 的调度；`packages/runtime/session.py` 统一消息、预算、权限、Trace、失败终止和安全点状态；`packages/application/checkpoint.py` 落盘并校验恢复。短的 `while` 不代表整个 Runtime 只有短循环。它的可验证特色是同一 Session 原子操作可由手写循环和 LangGraph 分别调度，在相同任务与预算下做对照（ADR-010）。

值得补强的真实缺口：

1. **V0.2 优先：** 暂停/取消、失败 Episode 重跑和并发实验的状态转换；逐项验证模型请求中、工具执行中、落盘前后的取消/恢复语义。参考 [OpenAI Runner 的生命周期规则](https://github.com/openai/openai-agents-python/blob/main/.agents/references/runner-lifecycle.md)，但仍使用本项目 Port。
2. **V0.2 验证：** 现有 ToolLab 单 Episode 恢复已通过 Fake 跨进程测试，需真实模型中断小样本，核对重复上游用量与 Trace 因果链。不可把本地只读工具的幂等保证推广到外部写工具。
3. **后续研究：** 当前 `ModelResponse` 每次只允许一个动作，长序列上下文也尚无压缩策略。若选择多工具调用或上下文管理作为研究变量，应先提 ADR、建立相同 Suite 的消融实验，再修改领域契约；否则只增加代码量，无法证明性能收益。可参考 [smolagents 的多步结构](https://github.com/huggingface/smolagents/blob/main/docs/source/en/conceptual_guides/intro_agents.md)。

结论：可把当前实现诚实表述为“框架无关、可恢复且可观测的受控 Agent Runtime”，不要仅以代码行数宣称先进。下一步通过失败边界和对照实验提高可信度。
