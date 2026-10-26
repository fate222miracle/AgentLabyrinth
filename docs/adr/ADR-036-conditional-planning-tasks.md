# ADR-036：条件路由与遗漏核验规划任务

状态：**Accepted，2026-10-20**。负责人已明确回复“按 ADR-036 实施两题（推荐）”，确认下述两题及公开协议。需求V0.6 §0.3/§19，沿ADR-035组件与[复核结论](../tasks/V0.3-planning-review-20261020.md)。无真实模型调用或GitHub提交授权。

## 1. 要验证什么

旧planning-branch-001本质仍为登记指定三事实的收集，Fake两项声明后沿原规则求解；目前没有证据证明规划带来收益。本方案增加条件依赖与遗漏核验机会，观察模型是否选择适用分支、完成全部适用条件。**任务更复杂不代表规划必然有用**；允许两侧都通过、两侧都失败或规划侧更慢，保留所有结果。

本次仅新增两道独立自建开发任务。原19题及BFCL、规划组件、工具/请求/Session/Experiment版本和评分均保持，不接数据库、摘要、外部框架、多Agent或新渲染器。

## 2. 两题与可审查的具体事实

| 新任务 | 依赖/遗漏机制 | 公开事实示例 | 确定性目标（仅任务私有目标/测试可见） |
| --- | --- | --- | --- |
| planning-route-002 | 先读验收lane，再从登记的路由选择政策；所选政策要求的审批需独立读取 | 收到41、损耗7、lane=restricted；限制通道门槛30、审批true；标准通道门槛40且无审批 | eligible；登记+验收+限制政策+审批四份实际证据 |
| planning-omit-003 | 数量门槛通过仍不能早交；所选政策在有损耗时另需复核 | 收到41、损耗7、lane=standard；标准政策门槛30、损耗复核false；非适用限制政策更宽松且审批true | ineligible；登记+验收+标准政策+损耗复核四份实际证据 |

两题的另一分支均可读取，也不向观察者标“正确/错误”。允许先读多份资料、纠正选错政策或重复阅读；只在提交时要求适用证据闭包，不禁止非适用工具阅读。不规定固定调用次数，不给规划侧独有的评分条件。完整核验是业务交付：即使数量已不达标，仍需收齐适用审核依据，不以逻辑短路跳过审批；双方同样要求。

任务描述公开业务规则与交付要求，但不列实际分支选择、正确答案或私有目标证据。初始模型观察只给description、task_kind和document_query；文档正文仍需经工具实际取得。页面沿现有资料区展示，不把观察者预览注入模型。

## 3. 有限的公开文档语法

新增task_kind=`document_route`，document_reference_protocol=`conditional-eligibility-v1`；planning_protocol仍为plan-update-v1，使现有ToolSetv1.6.0/规划入口可复用。TaskSpec schema1.0、源版本1.0.0，category=evidence_chain、max_steps=10、token_budget=20000；origin=native_planning_challenge、dataset_version=planning-routing-v1、split=development。这是自建任务，不是外部真实数据集。

正文使用与现有Fact/Source风格一致的有限标记，中文业务说明可同存；**不是通用DSL，不eval/执行文档内容**：

登记：

```text
Workflow: conditional-eligibility-v1
Inspection document: INSPECT-X
Route standard: POLICY-S
Route restricted: POLICY-R
```

验收：

```text
Fact: lane=restricted
Fact: received_units=41
Fact: damaged_units=7
```

所选政策：

```text
Fact: required_units=30
Approval document: APPROVAL-X
Damage review document: REVIEW-X
```

Approval document行可缺省，出现则必须核验；Damage review document行可缺省，出现且damaged_units>0时才适用。审批/复核正文为`Fact: approved=true`或false，不因缺字段默认false或默认通过。数量为0至1000000的整数，损耗不得大于收到；lane只接受登记已声明的standard/restricted，两条路由均明确存在。引用ID来自真实读取正文，不按任务ID拼接。相同事实/字段的冲突值、重复定义、未知流程、缺失必要字段或非法值均拒绝，不猜答案。

统一判定：usable=received-damaged；usable>=所选政策required且全部适用审批/复核为true时eligible，否则ineligible。证据闭包：登记、验收、所选政策以及实际适用检查文档的evidence_id。每份证据必须来自成功read_document，不能从search摘要、累计ID或最终提交伪造。无适用检查时不强加一份审批证据。

## 4. 实现边界与兼容

- Application/Runtime不增加业务判断；Environment只沿原Registry/Validator/Executor返回固定文档。Evaluator继续原order_status_v2的精确结论、无序完整证据与真实读取核验，不新增评分或改旧目标。
- Fake新增独立document_route分支，只解析当前可见工具返回/既有记忆封装，依公开路由采取行动。复用成功文档解析入口，旧document_rule/document_plan语义逐值保持。非法/缺失数据不默认提交ineligible。
- Fake的声明只验证规划组件控制路径，不拿手工策略收益当LLM规划收益；不读取TaskSpec、goal_conditions、源JSON文件、任务名或调用次数来决定业务答案。与旧Fake一样，唯一call_id允许用调用计数。
- 已读政策的两个独立检查可在serial中同批；需要验收lane才能知道的政策不提前猜入同批。single仍兼容，update_plan仍可选且计入预算。两侧相同full上下文/工具版本/Runtime/策略/任务/Seed/预算，仅规划组件不同。
- 新任务不会改旧19题文件/哈希；恢复与失败重跑沿保存Task，不拿最新文件重解释。MCP固定目录自动发现新任务，沿同一正文返回，无远程模型Key或新协议参数。
- Web正常任务目录、单次规划开关、实时调用/资料/声明/实际输出、正式planning轴、CSV、URL回读复用现成实现，不新增配置选项或专用演示页。若需渲染改动，只展示实际事实，不提前判出正确分支。

## 5. 验收与防止制造收益

1. 两Runtime×本地/MCP×single/serial、有/无规划均按相同业务规则可跑通Fake。Fake两侧都成功是控制验证，不是规划提升。真实验证不在本次自动授权中，另定一模型/一任务/固定预算，无自动换模型/重试/批量。
2. 反事实：翻转lane、改变门槛、审批/复核布尔值与损耗=0，答案/证据闭包随公开事实改变；重命名任务/文档ID、打乱文档顺序仍可解；私有目标故意改错时Fake仍按公开规则答，评测应失败。
3. 非适用/漏项/重复/额外证据、错结论、伪造证据、计划自称done均不通过；读过非适用资料但未引用可通过。数量通过却漏适用复核须失败，无损耗时不要求损耗复核。
4. 保留单次参数纠错、只读批次/安全点、全局预算和未知用量边界；本地/MCP恢复不重复已完成工具，旧全部固定回归通过。
5. 实际网页运行、规划对照、证据显示、输出、CSV下载与历史只GET、四视口/键盘/reduce；完整scripts.check与源码学习/状态/失败/交接文档。

不承诺这两个实例足以支撑研究结论，不调整N窗口削弱基线，不多送规划侧Token，不强制最少工具数。后续若要证明提升，需要固定留出实例/重复与失败分析，另行定义实验规模。

## 6. 决策与实施记录

负责人明确选择“按 ADR-036 实施两题（推荐）”，已按上述规则先Fake最小验证，再完成正常API/Web/对照/恢复/回归闭环。新两题已接入，旧19题字节保持。最终完整596 Python/44 Node/61 Edge及真实localhost HTTP四次Fake运行/两次新进程恢复通过；[任务验收](../tasks/V0.3-conditional-planning-20261020.md)、[源码/失败/实际结果](../learning/V0.3-conditional-planning-20261020.md)可追溯。属于工程机制交付，真实模型收益与V0.3整版未验收；保持本地，不提交GitHub。
