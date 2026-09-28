# ADR-015：V0.2 已接入环境的恢复与实验收口

## 状态

Accepted（2026-09-28）。依据需求 V0.6 §9.7、§12、§19；扩展 ADR-011 的本地单 Episode 范围，不改变其安全点与模型请求可能重发的语义。

## 决策

1. 单 Episode Checkpoint 扩至当前已接入的 BFCL 改编单调用环境和固定文档 MCP 环境。BFCL 只记录函数调用提议，不执行外部函数；MCP 仅远程执行只读搜索与读取，本地 `submit_answer` 随环境快照恢复。恢复必须按保存的环境版本重建对应 Environment、Validator、Evaluator，并验证 Task/Agent/RunConfig 哈希。
2. 只有执行结果与环境快照一同落盘后的工具安全点才承诺不重放。模型请求中途退出可能重发；MCP 只读请求也可能重发，但不得被描述成写操作恰好一次。真实外部写工具当前不存在；引入时必须另有持久化幂等键和服务端去重或事务协议，不能套用这条承诺。
3. Experiment 的批量恢复必须保存矩阵位置、两侧已完成 Episode ID、原始 Agent/Task/配置和部分 Pair；恢复先复用最终 Artifact，再恢复未完成 Episode，最后继续未开始的单元。不得重算已完成侧、改变 Pair 顺序或静默开启新 Experiment ID。此项在独立验收前不得宣称完成。
4. 故障注入只用于受控测试/演示配置；每类故障记录注入点、预期 Trace 和判定，不把 Fake 成绩说成真实模型能力。外部 Benchmark 扩展继续采用版本化 Manifest 与逐 Suite Adapter/Evaluator；新增数据集须锁定来源、许可、协议差异后才加入。指标看板只聚合兼容 Suite/版本/协议的已保存产物，未知费用保持未知。

## 验收

- BFCL 与 MCP 各有跨进程恢复及失败路径；无最终 Artifact 时列出可恢复 ID，完成后清除存档。
- Experiment 中断后复用已完成 Episode，同 ID、同顺序、同评分产物收尾。
- 故障实验有可重跑的注入配置与 Trace 断言；Benchmark Adapter 有第二种固定来源的契约验证；看板用真实持久化产物且能处理缺字段与未知费用。
