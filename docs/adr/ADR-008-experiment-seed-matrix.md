# ADR-008：Experiment Seed 矩阵与重复执行契约

## 状态

Accepted（2026-09-22，V0.1 Release Candidate）

## 背景

V0.1 要求批量执行 `Agent × Task × Seed`。现有 Experiment 已支持两个 Agent 与多个 Task，但一次请求只能运行一个 Seed，也无法区分同一 Seed 的重复运行。

## 决策

- `CreateExperimentRequest` 保留旧字段 `seed`，新增可选 `seeds` 与 `repeat_count`。未提供 `seeds` 时使用 `[seed]`；提供时以 `seeds` 为准。
- Seed 集合不能为空且不得重复；`repeat_count` 默认为 1。执行顺序固定为 Seed → Repeat → Task → Baseline → Recovery，全程串行。
- 每个 `PairComparison` 保存 `seed` 和从 1 开始的 `repeat_index`。Baseline 与 Recovery 必须共享同一 Task、Seed、Repeat、模型、工具和预算。
- 新 Experiment Artifact 使用 `schema_version=1.1`。读取 1.0 历史产物时，缺失的 `repeat_index` 默认为 1；旧单 Seed API 与 JSON 保持可读。
- 新实验配置同时保存 `seeds`、`repeat_count`，并保留 `seed` 作为首个 Seed 的兼容字段。配置哈希覆盖完整矩阵。
- 聚合指标以全部成对样本为分母，不新增小样本置信区间。
- 成对结果和聚合指标保存已知的 Decimal 费用；任一 Episode 费用未知时，实验费用保持 null，不把未知值累计为零。1.0 历史产物缺失费用字段时同样读取为 null。

## 原因

该方案以最小变更满足 V0.1 的 Seed 矩阵要求，并为重复实验提供明确身份；不引入队列、数据库或并发语义。

## 代价与风险

- Episode 数量按 `2 × tasks × seeds × repeat_count` 增长，真实模型运行时间和额度消耗会同步增加，Web 必须在运行前显示总数。
- 同一 Seed 的重复执行对 Fake Provider 会得到相同结果；Repeat 主要用于真实模型非确定性实验。

## 回滚方式

前端恢复只发送 `seed`，Application 继续以默认单 Seed、单次重复运行。1.1 产物仍可由当前兼容模型读取，不回写历史文件。
