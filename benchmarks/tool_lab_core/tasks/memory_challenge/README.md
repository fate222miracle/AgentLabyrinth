# 事实记忆压力场景 v1

[ADR-032](../../../../docs/adr/ADR-032-fact-memory-challenge.md)经负责人确认后实施。三题为自建开发/压力样本，非外部数据集或泛化能力排名。TaskSpec 1.0、任务1.0.0、ToolSet v1.4.0；旧15题不变。

| 任务 | 差异 | 有效依据 |
| --- | --- | --- |
| memory-fact-reuse-001 | 三个数分散在三份正文 | INTAKE、INSPECTION、POLICY-B |
| memory-large-return-002 | 登记正文含明确合成附件，UTF-8共9046字节 | 同上 |
| memory-policy-version-003 | 同时提供A/B政策，登记指定B；A门槛20，B门槛24 | 同上；A可读但不属于本案提交证据 |

## 公开规则与参考解析

`usable_units = received_units - damaged_units`；大于或等于适用政策的`required_units`时答案为`eligible`，否则为`ineligible`。原始事实26、3、24得到23<24，目标为ineligible。任何一份正文均不包含全部三个数或最终结论。

公开模式`document_rule`，协议`fact-unit-rule-v1`。正文使用逐行`Fact: key=value`、`Source key: DOCUMENT-ID`、`Policy document: REVISION=DOCUMENT-ID`和`Rule: usable-units-v1`。Fake只从本次可见成功返回/显式工具记忆读取事实；数值限定非负整数且不超过1000000，损坏数不得超过登记数。缺失时沿公开引用查找；冲突或未知规则拒绝，不能默认答案、读取goal或按任务ID给答案。此解析不是通用自然语言抽取器。

登记指定适用版本，不能从文档顺序/标题猜测。允许任意合法顺序、重读、先读错版再纠正；没有固定调用数要求。旧累计证据字段保持，不替代所需数值。评分复用OrderStatusEvaluator v2：精确答案、完整无多余/重复且真正成功取得的证据；不改历史。

## 使用

网页单次运行选择ToolLab，搜索`memory-`后选题；默认完整上下文。若观察记忆，在更多设置选择近期窗口加记忆，N1/M8192。显式运行后看实时调用、右侧关联资料、最终输出。对照实验选择“工具记忆”，同一个任务、N1/M8192，保存后可读两侧Trace和下载CSV。历史刷新仅GET。

大返回超过M8192时整条被跳过，Agent仍可重读并成功，不能人为禁止或要求失败。正文字节不等于记忆包大小、Token或网络包。Fake预算和Token为模拟值，不能据此证明真实模型收益。

MCP须另启动本项目固定localhost服务，客户端/服务端须使用同一版任务文件；本地和HTTP路径均经Registry/Validator/Executor。真实调用、恢复、失败与完整门禁结果见[学习交接](../../../../docs/learning/V0.3-memory-challenge-20261019.md)。
