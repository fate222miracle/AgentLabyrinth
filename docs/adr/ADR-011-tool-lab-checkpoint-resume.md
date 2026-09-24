# ADR-011：ToolLab Episode 的持久化恢复边界

## 状态

Accepted（2026-09-23）。承接需求 V0.6 §12 与 ADR-010；按下述边界分步实现，未通过跨进程验收前不得宣称 Checkpoint/Resume 可用。

## 背景

当前 Reference 和 LangGraph 调度共享 `EpisodeSession`，但消息、预算、已见 Tool Call ID 和环境状态只在内存。LangGraph `_GraphState` 仅有 `next_node`。现有 ToolLab `snapshot/restore` 用于只读 Replay，尚无 Runtime 恢复。单独添加框架 checkpointer 无法解决跨进程恢复或工具重复写入。

## 决策

1. 首批只支持本地 ToolLab 单 Episode；BFCL、外部 MCP、Experiment 批量暂停不纳入首批验收。Checkpoint 由应用层持久化，Runtime 通过共同 `EpisodeSession` 导出/导入版本化状态，两种调度器使用同一状态契约。
2. 只在安全边界落盘：初始 Observation 完成后，以及一次工具调用的反馈、环境快照、Agent 消息和 Trace 均完成后、下一次模型请求之前。参数纠错重新进入模型前也需要安全点。模型请求进行中中断时从上一个安全点重发请求；必须明确记录可能增加的上游 Token/费用，不把它称作模型调用的恰好一次执行。
3. Checkpoint 至少含 Episode ID、Agent/Task/RunConfig 及其哈希、下一节点、当前 Step、Agent 可见消息、预算计数与费用已知状态、已见 Call ID、参数重试状态、Environment Snapshot、Trace 事件及最后父事件 ID。恢复先验证 schema、哈希、Task/Environment 版本，再由 `environment.reset(task, seed)` 后 `restore(snapshot)`；不得把 `goal_conditions` 加进 Agent 消息。
4. 同一 Episode 的 Checkpoint 使用原子文件替换写入。ToolLab 的写操作只影响内存；已提交的状态与执行 Call ID 一起保存在 Checkpoint，恢复后不重放已提交工具。未来真实外部写工具必须有持久化幂等键/事务语义，不能直接复用此 ToolLab 保证。
5. 恢复记录一个新 Trace 事件，随后沿原事件链追加；`EPISODE_FINISHED` 仍只由 Runner 写一次。已有终态 Artifact 不再重新运行。历史 Episode/Experiment JSON 读取保持兼容，不迁移旧产物。
6. Checkpoint JSON 经过既有敏感字段过滤。目录仅存本机，Key 不进入状态文件；损坏、外来 Episode、版本/配置不匹配时拒绝恢复，不能静默从头运行。

## 验收条件

- 两个独立进程：进程 A 在一次成功工具调用后的安全点退出，进程 B 用相同 Episode ID 恢复，得到正确最终状态与唯一终态事件。
- 已提交工具的 Call ID 和状态在恢复前后各出现一次；预算累计且不得归零；Reference 与 LangGraph 分别通过。
- 不匹配或损坏 Checkpoint 拒绝；完整 Artifact 的读取无模型调用；旧产物仍可读。
- Fake 用于可重复工程验证，真实模型只做小样本探索；不把 Provider 请求本身宣称为恰好一次。

## 代价与限制

本地 JSON 原子替换只保证 ToolLab 安全点的持久状态，不能为外部服务提供分布式事务或原生恰好一次语义。模型请求可能重发并产生额外费用；UI 必须如实展示这种限制。
