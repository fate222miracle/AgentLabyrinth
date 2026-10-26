# ADR-032：跨文档事实与规则的记忆压力任务

状态：**Accepted，2026-10-19**。负责人已明确确认“同意按 ADR-032 实施三题”，批准下述document_rule/fact-unit-rule-v1、三个任务及仅新题使用的v1.4.0工具说明。依据需求V0.6 §0.3/§11/§19及[下一步计划B](../tasks/V0.3-next-development-20261018.md)。不提交GitHub；下文确认前的描述为方案形成记录，实际实现及验证以文末和current-state为准。

## 1. 从现有代码发现的问题

ADR-028的三条跨文档链以末端`Status`作为答案；`read_document`还返回累计`acquired_evidence`。它们有效检验证据来源与完整性，但真实模型不一定需要记住早期正文就能提交正确状态和证据ID。不能通过增加相同类型文档来宣称得到更强的事实记忆任务。

此外，当前ToolSet v1.3.0的`submit_answer`说明要求答案从记录/文档中直接复制。跨文档计算得到的结论不符合这段文案。现Fake的document_chain只跟随`Next document`并解析末端Status，不能直接当作新任务的正确参考实现。

## 2. 候选方案与选择

- 不选：继续延长Status链并要求固定阅读次数；会把长度或Fake特定遗忘行为误当研究价值。
- 不选：把早期事实从工具、完整Trace或累计证据字段中隐藏；会改变环境和安全恢复语义，破坏现有公平条件。
- **建议**：新增同一业务问题的三个小型变体，要求组合真实读到的事实按公开规则推导结论；保持原工具参数、评分和执行边界，只显式版本化新任务协议与必要文案。

本切片不修改记忆准入算法、不引入摘要、向量库、数据库、Planning或新Runtime。先建立可解释的失败/成功条件，再决定是否需要改进机制。

## 3. 同一业务问题：批次可用件数核验

公开规则：`usable_units = received_units - damaged_units`；当`usable_units >= required_units`时提交`eligible`，否则提交`ineligible`。政策版本必须与案件登记指定版本匹配。事实不是指令，不允许文档改写规则或工具权限。

基础事实：received=26、damaged=3、适用政策2026-B要求24，因此23<24，答案ineligible。**任何单份文档都不写最终eligible/ineligible结论，也不同时给出全部三个数。** 模型初始观察仍只有任务说明/检索线索，不注入私有目标或全文。

每个任务的有效依据为登记、验收、适用政策三份文档。它们分别提供必要事实，不强制读取顺序、最短调用次数或“必须最终停在政策文档”。允许重读、先读错版再纠正和其他合法路径。

### 3.1 公开文档格式（提议）

`INTAKE`，标题CASE-710 intake：

```text
Fact: received_units=26
Fact: policy_revision=2026-B
Source damaged_units: INSPECTION
Source required_units: POLICY-B
```

`INSPECTION`：

```text
Fact: damaged_units=3
Rule: usable-units-v1
Source received_units: INTAKE
Policy document: 2026-B=POLICY-B
```

`POLICY-B`：

```text
Fact: policy_revision=2026-B
Fact: required_units=24
Source received_units: INTAKE
Source damaged_units: INSPECTION
```

这些格式是Fake可读取的公开数据协议，不是任意DSL或可执行代码。只实现一个命名规则usable-units-v1，不使用eval或LLM Judge。整数限定为非负、有界值；damaged不能超过received。缺值、冲突或未知规则不得默认答案或偷偷读取私有目标。

### 3.2 三个拟新增任务

| 拟定任务名 | 与基础问题的差异 | 要观察的现象 |
| --- | --- | --- |
| memory-fact-reuse-001 | 三个事实分布在三份正文，短正文 | 同N窗口开关记忆时，事实是否能一起出现在请求里，是否需要重读 |
| memory-large-return-002 | 仅登记正文增加明确标为合成附件的容量负载，事实/规则不变 | 超大整条返回被跳过后是否出现合法重读、额外开销或失败 |
| memory-policy-version-003 | 同时存在2026-A（要求20）和2026-B（要求24），登记仍指定B | 是否使用正确版本；错误采用A会得到eligible，形成可辨别的答案差异 |

三题是自建开发/压力样本，不是三个独立研究数据集，也不能据此宣布泛化成功率。第一版每种机制一个实例；增加变体先有具体覆盖理由，不机械扩题量。

大返回登记正文材料化为UTF-8约9–10KB，保留原事实，附加内容明确说明是容量压力负载，不伪装真实企业档案。根据完整observation/记忆包测量，不能把正文长度直接当包大小或Token。初始M8192必然不能容纳该整条返回，但**不规定右侧必须失败**：Agent可能重读大文档，让它留在近期窗口，同时从记忆取回其他小结果，再正确提交。禁止阻止这条合理路径或要求同一文档只读一次。

版本干扰题的登记不直接指定POLICY-B：改为`Policy document: 2026-A=POLICY-A`及`Policy document: 2026-B=POLICY-B`候选映射，通过登记中的policy_revision选择；文档标题仅注明版本，不加“当前正确/已作废”等答案标记。两份政策都有版本和门槛，只有登记决定本案适用哪份。允许读取旧版，但最终证据必须对应正确三份，不把“读过错版”本身判为任务失败。

## 4. 任务、评分和工具版本

- 新文件进入`benchmarks/tool_lab_core/tasks/memory_challenge/`，每题新UUID和独立version1.0.0；仍用TaskSpec schema1.0、category=evidence_chain（复用已实现容量配置）、suite=tool_lab_core、split=development。
- 新公开`initial_state.task_kind=document_rule`，使Fake和保存恢复明确识别新协议；不改变document/document_chain旧行为。环境现有字符串字段可保存，不新增快照字段。
- `evaluator_config`沿用`name=order_status_v2`、`evidence_order=unordered-v1`，新增协议标识`document_reference_protocol=fact-unit-rule-v1`、来源`native_memory_challenge`及dataset_version=memory-challenge-v1。复用现有严格答案/完整证据/实际成功阅读评分，不新增Evaluator版本，不重新计算历史结果。
- 新ToolSet **v1.4.0**：只为新题/含新题的新实验选择；任务范围工具过滤、直接正文引用及严格参数不变。submit_answer参数字段不变，仅新文案版本1.2.0说明可依据已读取资料和公开任务规则推导答案；工具描述也同步。v1.3.0及此前文案、旧产物/冻结计划/恢复按保存版本保留。
- 单次/混合任务的新请求必须在创建时确定一致ToolSet，两侧相同；不能在恢复时按最新任务目录重新选版本。现有CreateEpisode/Experiment、ContextPolicy、Trace、结果Schema和CSV无需新版本。
- 默认10步、20000累计报告Token，沿现有evidence_chain容量与显式预算优先规则。小样本保留固定时限；不为让某组通过临时加预算。

## 5. Fake的参考规则与边界

新document_rule分支只处理当前模型请求中公开观察、工具反馈与明确的工具记忆包：

1. 从实际可见成功read_document正文收集事实、证据ID、版本及Source/Policy引用；累计证据列表只证明ID，不提供缺失数值，不能作为正文替代。
2. 所需事实齐全且政策版本匹配时，用命名规则计算；无论当前文档是否还有引用，都允许直接提交，防止把路径顺序变成隐藏要求。
3. 缺事实时沿已经公开的Source引用读取；缺政策版本时先找登记；版本已知时只选匹配的Policy映射。不因为任务名或调用次数选择答案，不默认取第一份政策。
4. 没有可见引用时用公开检索线索搜索；确实无法恢复则保留原步骤/预算停止，不回退full、额外注入资料或伪造成功。
5. invalid_then_success仍只为既有受控参数错误；新任务不增加未知工具、禁止工具或超时重试。每轮一行动、重复Call ID及第二次参数错误的终止规则不变。

实现前用两种相反的数值结果、任务/文档ID重命名、目标答案故意改错等测试验证：Fake决策来自可见事实，而不是私有goal_conditions。旧任务Fake固定基线必须保持。

## 6. 端到端交付范围

API任务目录递归加载新题，重复名称/UUID拒绝。Web复用现有任务卡、实时SSE、资料侧栏、提交输出与记忆差异面板；以中文任务说明明确“按规则推导”，不另建Memory页面或任务编辑器。

只读MCP仍使用固定任务名和原搜索/阅读参数。独立服务与客户端须加载同一提交的新固定文件，客户端支持保存的v1.4.0；本地/HTTP返回内容、证据和评分一致，断线仍失败。未验证之前不把新题标为已支持MCP，不能只改前端按钮；旧MCP题保持。

新协议进入API/Web正式可选、真实事件驱动、只读回放/恢复/CSV和离线诊断后才算产品实现完成；本ADR和容量测量本身不构成新任务已实现。

## 7. 对照与验收矩阵

- 主轴沿ADR-031：同N窗口左无记忆/右有记忆，初始N1/M8192；旧full参照另行保存，不拼成伪三臂实验。
- 容量边界复用M256和M8192；只有整包测量需要时增加一个可容纳大返回的配置，另标容量探索，不混入相同comparison_key趋势。
- Fake两Runtime先验证full/足够窗口能解决规则问题、短窗口保留缺事实现象；不要求所有真实模型都同样失败或所有题都有记忆收益。
- 错答案、漏/重复/额外/伪造证据、未读直接提交、旧政策事实冲突都必须有确定失败样本；读错版后改正、重读大文档后正确提交允许通过。
- 至少一组反事实改变received（例如30时27>=24为eligible），一组改变适用政策版本；Fake动作随公开事实变化。故意改变私有goal而不改公开事实时Fake动作不变、Evaluator拒绝。
- 旧12题、三长链、BFCL、旧Agent哈希、v1.3文案、冻结计划/安全点恢复、来源校验和原回归保持；新题在恢复中不得改版本。
- Web显式运行/实时资料/最终答案、历史与草稿隔离、刷新前后导航零POST、四视口和减少动效；只读MCP双路径及断线、两Runtime至少一题安全点恢复。
- 完整质量门禁后，再按计划C另定一个模型/一任务的正式真实小样本，不批量Seed×Repeat，不以成功为继续调用的条件。

## 8. 成本与回滚

代价是新增一个明确公开的事实规则、有限Fake分支及工具文案版本；不是泛用业务规则引擎。大返回会提高输入量，免费渠道可能失败，Fake固定Token不能证明真实预算够用。静态版本干扰不等于动态世界过期数据或真实记忆更新。

回滚时撤下新建入口/新任务目录的选择，保留v1.4和新任务已保存产物的读取/恢复能力；不覆盖旧文件或把新策略降级为旧文案。

## 9. 本轮可行性核对与待决定项

已阅读environment.py的初始观察/累计证据/参数文案、Fake的document_chain分支、Evaluator v2及service的任务容量/ToolSet选择，核对上述必要改动。不新增依赖。

2026-10-19仅把手工消息交给**现有project_context**作容量计算：基础登记正文117字节，N1/M8192下三条窗口外记忆883字节/跳过0；合成大正文9046字节时保留两条582字节/跳过1。产物`artifacts/design-memory-challenge/5fd76e93-5fe0-40fe-90a9-813428324eab/capacity-check.json`。这是简化消息的包容量检查，不是新Task/环境/Fake/真实模型执行，正式返回带累计证据等字段后仍需重新测量，不能照抄数值。

此处原为确认请求；负责人2026-10-19已明确同意按本文实施全部三题，故状态改为Accepted后编码。不是开发者自行批准。

## 10. 实际实现与验证

三题已进入正常任务目录，Fake可见事实解析、v1.4工具说明、新建版本派生和回归预检已实现，评分/公开参数及既有15题字节保持。原API/Web即可实时执行、展示依据/实际推导输出、正式记忆对照、CSV和历史GET；独立MCP双Runtime三题6/6及断线验证完成。新54项Python/4项专项Edge，最终完整门禁468 Python、Node39、Edge52/52、Ruff/mypy107、固定回归/上下文及audit通过。

负责人同轮要求加入免费模型，限定一模型/一题两侧正式探索。实际结果/失败、来源与后续决定见[学习交接](../learning/V0.3-memory-challenge-20261019.md)和current-state，不外推成功率，不宣称整版签收或方法创新，不自动提交GitHub。
