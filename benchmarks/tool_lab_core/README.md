# M0 原生 development 任务

只含 order-status-001，一条原创模拟订单；不是 ToolLab-Core 完整 12 任务 Suite，也不是外部 Benchmark。

设计意图：验证查询 → 工具反馈 → 提交 → 独立评测。预期 query_records → submit_answer。只有答案正确、证据来自实际查询、顺序和提交均成立才成功。错误答案/伪造证据/未查询即提交为负例。seed 保存在环境快照；此任务不随机改变订单事实。

TaskSpec 初始结构已校验；具体任务级行为测试待 Antigravity 实现，当前不可声称任务已运行通过。
