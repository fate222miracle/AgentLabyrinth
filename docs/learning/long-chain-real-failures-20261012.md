# 真实长链失败复核与修复

需求V0.6、Accepted ADR-029；负责人授权三个场景真实复测和修复。本轮不提交GitHub，已有ADR-028代码和产物保留。

## 用户失败的实际来源

- `c3beae39-afd5-4fe4-b5cd-587842f864be`：MiniMax M2.7/MCP退货，approved、三文档均成功阅读，仅证据列表按阅读顺序而不是字典序，旧评分evidence_mismatch。这是原长链评分定义过严，不是MCP不通。
- `f9000615-cb73-44d4-991e-d28aeb86645a`：MiniMax M2.7本地退货，首轮选择query_records，0工具；Schema中出现了任务不允许的工具，可能诱导错误选择。不能通过开放权限来修复。
- `21d8c8bf-bee5-4da2-b4c5-dfbdf2dfc961`、`5512a578-e5b8-467e-9b2b-5bfe9385a0a5`、`2f3141ae-e835-4484-bb79-8d06a44584c0`：GLM5.3/M3配送，首轮MULTIPLE_TOOL_CALLS，0工具；最后一条选MCP也尚未进入远程工具，与MCP网络失败不同。现有请求已parallel_tool_calls=false，不能宣称所有型号遵守。

## 最小源码修改与兼容

1. 三Task先升1.2.0，公开constraints明确每轮单行动和文档ID来源，evaluator_config.evidence_order=unordered-v1；原12题不改。最终Task1.3.0新增document_reference_protocol=direct-reference-v1，不改答案、文档或预算。
2. `ToolLabEnvironment`新工具集v1.2.0按初始化任务的允许列表过滤Provider可见Schema，Registry/Validator/Executor仍硬检查。最终ToolSetv1.3.0进一步把read_document说明升工具版本1.1.0：搜索结果或已读正文引用均可直接读取，不需再次搜索同一ID。旧v1.0/v1.1原Schema可见范围及v1.2阅读说明保留，submit版本仍1.1.0。MCP沿用本地工具Schema并远程只读。
3. `EpisodeService._task_tool_version`把新创建单次和两侧冻结Agent绑定该工具集；旧安全点/失败重跑按保存版本，不套用新条件。Budget/Runtime/Provider行为不放宽。
4. `OrderStatusEvaluator`只在显式新协议把证据列表作为排序后的多重集比较；顺序无关但重复仍拒绝，缺项/额外和未取得证据失败。实际提交与Trace不改，原顺序敏感评分v1保留，新协议记v2。
5. `experiment.py`及`run_regression.py`把新任务的评测版本写入配置/预检，Task版本和规则进指纹；两侧仍同工具/评分，旧基线不改。

阅读调用链：新建API → 固定任务 → 新ToolSet/冻结预算 → Session公共约束与允许Schema → Provider → 原硬校验 → 本地/MCP阅读 → 提交 → Task指定评测协议 → 保存/GET。无多工具丢弃、无自动重试/换模型、无历史重算。

## 验证和真实复测

专项首轮34通过（5.82s）、引用说明补充后16通过（2.15s）；新增测试覆盖证据反序通过、重复/遗漏/额外失败、旧评分继续失败、原Artifact不变、新旧工具可见范围/版本说明、禁止提议仍0执行及新协议实验回归预检。最终完整门禁：Ruff格式/lint、mypy101、pytest353（44.80s，1条既有依赖警告）、四套Fake22格零退化、CLI上下文24、Web类型/构建、Node35/35、audit0、Edge31/31（1.2m）、diff通过。最终门禁 `artifacts/quality/84585fbc-2737-4b65-9ab2-d1279abcf3fb/`，浏览器 `artifacts/playwright/b6f337ea-f095-404d-89e5-a50b452a815f/`，日志 `artifacts/long-chain-recheck-20261012/quality.log`。先前v1.2完整门禁保存在08c30d71目录和quality-v12.log，均为离线工程验证，不代替真实模型结果。

真实四题已完成：LangGraph/full/无纠错、实际MCP、10步/20000Token/300秒/1024单响应；Episode之间也13秒间隔。四次SSE完整事件与保存GET一致，无自动重试或隐式换模型。以下均为Task1.2.0/ToolSetv1.2.0/order_status_v2。

| 模型 / 任务 | Episode ID | 独立评测 / 终止 | 模型 / 工具 | 报告Token | 耗时ms |
| --- | --- | --- | --- | --- | --- |
| MiniMax M2.7 / 退货 | 6f680ca7-5813-4585-b5a9-0905afcb8708 | true / SUCCESS | 5 / 5 | 10679 | 56797 |
| MiniMax M2.7 / 配送 | 26285484-6f5c-4b4b-a432-7b9e462ef974 | false / TOKEN_BUDGET_EXCEEDED | 9 / 8 | 20766 | 108034 |
| MiniMax M2.7 / 退款 | 07b2c231-42ab-4a6f-8b83-f404edcf6a68 | true / SUCCESS | 7 / 7 | 17310 | 83545 |
| GLM5.3 / 配送 | 9002411f-cfc9-4021-909b-a3e30f170305 | true / SUCCESS | 6 / 6 | 12747 | 80302 |

共27模型请求、61502已报告Token。退货提交阅读顺序的三条证据并通过，退款五条证据通过。GLM同题成功是修复后的一次观察，不能保证型号今后始终单调用，也未复测M3/Flash长链。

MiniMax配送虽读齐四份依据，却在已知SHIP-LOG、SHIP-REVIEW、SHIP-DECISION各再次搜索，末轮提交前耗尽累计预算。read_document原参数描述仅写“Exact ID returned by search_documents”，与公开正文引用冲突，Provider系统要求遵循参数说明。这是可修的提示契约矛盾，不能把所有冗余行动必然归因于它。GLM直接读引用六步成功，也证明预算不必统一抬高。已按ADR补Task1.3.0/ToolSetv1.3.0并通过完整门禁；只复测该MiniMax配送一次，保持20000预算，结果另存results-reference.json，不覆盖上面四例。

### 引用说明修复后的单题复测

MiniMax M2.7配送 `3533440c-f72b-4d16-8780-8229f8748300`，Task1.3.0/ToolSetv1.3.0/order_status_v2，原预算/Runtime/MCP/上下文/策略保持，SUCCESS且独立评测true。6模型/6工具、69302ms、12896报告Token（12353输入＋543输出），实际路径为搜索 → 连读SHIP-ENTRY/LOG/REVIEW/DECISION → 提交replacement_approved和四条已读证据。SSE与最终产物完整GET一致，未重试。相对前例，工具8→6、模型9→6、Token20766→12896，说明这一矛盾修复后的单次运行能在预算内完成，不是统计收益结论。

本轮五Episode共33模型请求、74398报告Token。三个场景均已有MiniMax真实通过记录，但退货/退款成功是Task1.2.0，最终Task1.3.0只复测配送，不宣称最新条件下三题重复全通过。未再请求M3/Flash、未新增真实恢复验证。完整忽略产物位于artifacts/long-chain-recheck-20261012/，results.json保存前四例，results-reference.json保存最终一例；对应live.log/live-reference.log和各Episode完整JSON保留。

正常服务已恢复：API启动器17612、Web33616、MCP启动器32488，localhost8000/5173/8765。刷新http://127.0.0.1:5173/?mode=single后选择ToolLab/三场景；MCP须保持独立服务启动，直接本地工具也支持新工具说明。模型结果是2026-10-12当前账号小样本，不保证持续可用。现场建议MiniMax M2.7、LangGraph/full/无纠错、10步/20000Token，新建Episode；保存结果可用上述ID只读查看。

接手：刷新页面并新建才用当前Task1.3.0/ToolSetv1.3.0；历史链接和旧失败重跑按保存版本，不套新协议。不能让旧实验v1与新v2或不同工具说明混比，不因模型不支持单行动而偷取其第一条工具调用；批量行动支持须另立Domain/恢复/预算/Trace契约ADR。本轮只验证新建实时MCP小样本，非新真实恢复、手写Runtime长链或统计能力结论，不提交GitHub。
