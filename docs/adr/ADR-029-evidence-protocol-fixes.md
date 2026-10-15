# ADR-029：真实长链失败的工具边界与证据集合修复

状态：Accepted，2026-10-12。负责人授权真实复测三个长链场景并修复失败；不提交GitHub。

## 实测问题

用户MiniMax MCP退货产物c3beae39最终approved且三证据均成功阅读，只因列表是阅读顺序而evidence_mismatch。另一MiniMax本地产物f9000615误选query_records；服务把禁止工具的Schema也发送给了模型。GLM/M3首轮多调用在实际工具执行前拒绝，与MCP无关。不能统一归为模型额度或网络。

## 决策

1. 仅三新场景升Task版本1.2.0，明确本任务每轮一个工具提议、遵循正文引用、最终提交有效状态和完整证据；不强制证据排列顺序，不强制轨迹。新增evaluator_config.evidence_order=unordered-v1。原12题和旧新题版本不改写。
2. 新协议采用ToolLab工具集v1.2.0：Provider只看该任务expected_tools扣除forbidden_tools后的Schema；Executor/Validator继续检查权限。保留v1.0/v1.1所有工具可见行为用于旧Agent/Resume/重跑。参数和submit_answer版本1.1.0不变；可直接读取正文引用的文档ID。
3. OrderStatusEvaluator只对显式新证据协议用排序后的列表比较，仍拒绝缺失、额外、重复、未实际读取或伪造证据；不改答案匹配、不改Trace/状态。版本记order_status_v2，旧协议order_status_v1。仅比较使用副本；历史结果不重算。包含新协议的实验配置与回归预检记录v2，任务版本/配置哈希区分条件，两侧保持相同工具和协议。
4. parallel_tool_calls=false与原MULTIPLE_TOOL_CALLS终止保持；不吞掉其余调用、不自动换模型、重试或开放并行工具。此次先以MiniMax三题同配置串行小样本检查，再按实际需要用另一免费模型做一题兼容验证，不扩Seed×Repeat批量。

## 验证

真实四例后的补充决策：MiniMax配送9模型/8工具因重复搜索正文已给出的ID耗尽20000预算，而GLM同题6步通过。read_document原参数描述仅允许搜索结果，与任务正文引用冲突。新Task1.3.0记录direct-reference-v1、新ToolSetv1.3.0仅将read_document说明升1.1.0，明确可直接读已知正文引用；严格参数/权限不变，旧v1.2.0保留原Schema。只再复测该失败配送一次，不额外重跑已通过案例或提高预算。

证据重排通过、重复/遗漏/伪造失败、旧评分不变；新工具可见范围与禁止调用硬校验、旧ToolSet/Agent/hash/恢复；Fake两Runtime、上下文与固定基线；API/Web/真实SSE及MCP数据通路保持，跑完整门禁。真实保存用量、阶段、终止、每次工具与独立评测，未跑通不宣称通过。入口/评分变化同时交付源码与失败交接。
