# AgentLabyrinth 协作入口

唯一权威需求是 `docs/product/requirements.md`，已核对版本 **V0.6**。本文件和任务卡只指导执行，不替代需求。

负责人2026-10-28明确要求提交GitHub，授权本次提交/推送全部已验证源码、测试和文档并按CONTRIBUTING创建关联PR；覆盖此前本地保留约束，仅限本次交付。密钥、本机配置、实验产物和缓存不入库，不授权真实模型请求或自动合并。按Git规范、实验可靠性、网络诊断分组，实际提交/PR/CI状态见current-state，不能把本地Edge门禁冒称远端CI通过。

负责人2026-10-28要求继续修存量问题。当前交接docs/learning/V0.3-network-diagnostics-20261028.md：AIHubMix目录/推理共用安全连接分类日志，补响应读取中断及包装超时处理，沿用原公开错误码/未知用量/无重试。一次只读目录GET已成功，不代表模型推理稳定或旧失败原因已找回；无真实推理/Judge/恢复/Git同步。分支codex/fix-provider-network-diagnostics保留全部既有dirty/untracked，最终验证以current-state为准。仍暂停新增机制，效果实证与A1等缺口保留。

负责人2026-10-26要求暂停下一步功能开发，先修明显硬伤。当前任务为docs/learning/V0.3-hardening-20261026.md：保存用量对账与未知提示、首次Fake/单题/整场16000Token边界默认、工具指标名称澄清、过期协作入口修正；不改公开契约/评分/CSV，不新增真实模型调用或Git同步。分支codex/fix-reporting-and-run-defaults保留所有既有dirty/untracked。完整门禁结果以current-state实际记录为准，不能把本轮修复外推为网络已恢复或规划收益已证。后续先处理存量问题，不自动恢复新机制开发。

负责人2026-10-26确认按ADR-041实施只读实验保存进度。已接GET /experiments/{id}/progress、来源核对与四状态、显式Web查看及原Episode跳转；缺记录不作失败或零用量，坏结束文件不借安全点冒充完成，读取/切换/刷新无POST。共享中文失败解释，不凭网络错误断定配额。实际完整679Python/47Node/70Edge、116文件Ruff/Mypy、旧22格零退化/消融/构建/审计0漏洞通过；详情docs/learning/V0.3-experiment-progress-20261026.md。原真实失败计划只读核对、源字节不变；没有新增模型推理/恢复/Judge/Git同步，保护全部已有改动。下一步先分析失败可观测性和网络，新的真实调用另行授权；Reflection暂缓、A1保持。

负责人2026-10-26另批唯一serial规划对：MiniMax M2.7×planning-route-002，原handwritten/无纠错/full/Seed1/Repeat1/每侧10步20000Token300秒/全局40000保持，两侧同serial，仅右侧规划。Fake预检通过后真实POST已执行左侧：首轮2个检索成功，第二模型请求NETWORK_CONNECTION_FAILED，用量未知阻止右侧，计划61bd5e1e…、左Episode368937f4…保留，完整Experiment未生成。授权已消费，不按400当零执行补跑；右侧未启动不计失败或零用量。分支codex/planning-serial-validation保留全部既有未提交成果。沿ADR-035补组件启用/实际未声明/Trace未知提示，实际typecheck/build和6Edge/28.4s通过；详情docs/learning/V0.3-planning-serial-validation-20261026.md。未跑新全套/真实重试/Judge/Git同步，后续先看网络与未完成实验可观测性。

负责人2026-10-26要求Git协作对齐企业开发。执行需求§28及根CONTRIBUTING.md：短期任务分支、原子提交、PR实际验证/审查后合并，Codex分支前缀codex/；不重写已发布main、不制造提交数。Issue/PR模板已补，远端保护未读取/配置，不冒称强制生效。本次仅本地规范整理，原规划改动保留；提交/推送/建PR/合并仍需当次授权。

负责人2026-10-26接续开发并明确授权唯一真实规划对：MiniMax M2.7×planning-route-002、handwritten/无纠错/single/full，Seed1/Repeat1，每侧10步/20000Token/300秒、全局40000Token，只有右侧规划。保留失败、无补跑/换模型/Judge；执行和实际结果见docs/learning/V0.3-planning-evidence-20261026.md。同时沿ADR-035/036完善规划保存对的实际提交/阅读/开销展示，不改契约或评分。本轮不自动Git同步，已完成的上轮提交为254eac0；旧668/45/68不冒充本轮门禁。

该唯一对已完成、授权已消费：实验39164f38…两侧失败（single多调用拒绝/累计输入预算终止），双方均无计划声明、无提交，4成功读/0重复。不能据此宣称规划收益或额外规划开销致失败。展示改动实际typecheck/build、45Node和6Edge规划专项通过，未改Python业务/未跑新全套；21题保持、服务已恢复。下一候选双方serial仅方案，不自动再跑，详见上述学习交接/current-state。

负责人2026-10-26明确要求提交GitHub并回顾阶段工作，授权本次提交/推送当前已验证源码、测试、任务与文档，覆盖此前本地保留限制，仅限本次同步。密钥、本机环境、实验产物与测试缓存不入库，不延伸为新真实模型调用或后续自动推送授权。阶段回顾见docs/handoffs/V0.3-stage-review-20261026.md；最新完整门禁为2026-10-25的668Python/45Node/68Edge，本轮文档整理不冒充新全套实跑。

负责人2026-10-25明确确认ADR-040，要求真实大模型Judge，撤下正常页面人工/Fake创建与无价值空面板。现按Review请求1.1显式aihubmix/model接原Provider，一次无工具/无重试，65536字节冻结输入/800输出Token/30秒；1.0旧人工/Fake与历史/评分/完整CSV保持。UI只提供真实评审，展示理由/引用与规则分歧，人工/Fake仅历史归档。随后负责人授权“试一下我的免费模型”：允许Codex对一份已保存Episode用一个免费型号发一次真实Judge请求，不重跑任务/补跑/批量；具体源码/实际结果见docs/learning/V0.3-real-judge-entry-20261025.md和current-state。该最新授权覆盖旧“真实v2仅准备”的阶段限制；不提交Git，保护全部未提交成果与21题，Memory/Planning真实批量仍未授权。后续先验证组件差异再扩功能，不把Fake、测试数量或Judge同向当收益。

同轮初次v2真实评审因think前缀失败（24d1c9ec…）；负责人另行批准一次格式诊断，确认内部JSON合法/5条引用合法；再批准修复后验证一次。按MiniMax官方原生reasoning_split参数修复仅MiniMax Judge的Provider构造，默认None不影响旧Runtime载荷，不剥离推理/不改Prompt或严格校验。正常API成功Review b6303391…，Token2827/264、费用未知，源/输入哈希和Episode606/Experiment55保持。三个授权均已消费；不是Judge准确率或Memory/Planning收益证据。最终新门禁见current-state，不沿用修复前665/68。

负责人2026-10-25要求立即优化看不懂的评审面板。按ADR-039现有范围，结果复核先说明运行后可选检查的用途，人工/真实记录显示结论与理由，版本/用量等收进技术详情；Fake按钮及历史默认折叠为“模拟测试（开发用）”，正常记录只标功能生成，不伪造质量判断，Episode与Experiment复核面板分别显示模拟数。历史/评分/Schema/完整CSV保持，无真实模型/Git调用。UI规范1.10、学习交接docs/learning/V0.3-review-usability-20261025.md；实际新门禁与服务恢复见current-state，不沿用旧数字。

负责人2026-10-25回复“继续进行开发吧，我验收了”，当前交付范围的现场体验已确认通过，不再要求重复体验；不代填逐项检查记录，不等于Reflection实现、A1缺口消除或真实效果已证。Codex接续修复run_regression.preflight右侧硬编码LangGraph：按runtime_target或旧默认校验，避免误拒绝PydanticAI及错放目标变化。实际59项定向Python、Ruff/单文件Mypy通过，旧22格与新增Fake14格0退化，21题字节保持；源码/固定六题/基线和下一步方案见docs/learning/V0.3-fixed-experiment-preparation-20261025.md与current-state。本轮未重新跑完整门禁，未新增真实调用/Git提交；真实Judge v2及规划限定一对均只准备，需另行明确授权。

负责人2026-10-25要求继续开发，Codex接手完成trae-20261023的P0/P1：历史Review来源按provider识别、版本/报告Token/模拟标识/未知费用展示，独立Review CSV原列后追加9列；未知金额空导出并保留已知标识/价格版本，旧Experiment CSV不改。离线历史夹具验证v1失败/v2完成/Fake、转义与实际下载，四视口及720等效200%/减少动效检查；新增docs/learning/V0.3-review-presentation-20261025.md与docs/handoffs/V0.3-demo-20261025.md。实际完整门禁以current-state为准。下一步负责人现场体验、Memory/Planning固定实验设计；真实Judge v2仍需单独一次授权，不恢复Reflection/扩数据库多Agent，不提交Git，保护全部未提交成果。

负责人同轮明确批准仅升级Zod4.6.5到4.6.6以修复审计GHSA-mrhx-c7xc-m3w5；package.json一行及锁对应根声明/Zod包项变化，相对升级前快照其他锁包项不变。既有Vite6.4.5保持，未批量升级；升级后须以实际新门禁为准，不延伸为其他依赖授权。

负责人2026-10-23要求先复核Trae再交接。当前执行入口改为docs/handoffs/trae-20261023.md，复核见docs/tasks/V0.3-trae-review-20261023.md。Codex补v1历史API回读/字节保持、v2原失败形状一次调用回归和Node双版本断言；实际111Python定向/45Node/5Edge通过，不冒充旧640/66全套。纠正真实Runtime费用实际未知、规划对照请求1.9及矩阵阶段描述。下一项先补EpisodeReviewPanel真实历史来源误标Fake、已有版本/Token/未知费用展示及独立CSV，属于ADR-039现有范围；然后现场验收材料与完整门禁。真实v2验证只准备，需单独授权一次；不沿用已消费的v1/诊断授权。整版未签收、Reflection暂缓、A1边界不变，不提交GitHub，全部dirty/untracked及21题保护。

负责人2026-10-23接续开发。按ADR-039 §11确证的根因（`episode-review-v1`未声明枚举取值、未禁止推理文本），本轮只做协议层修正：`packages/application/review.py`新增`JUDGE_SYSTEM_PROMPT`并升`prompt_version`为`episode-review-v2`，逐条写明六个字段枚举（`verdict: pass|fail|uncertain`，三维度`pass|fail|unknown`）、`rationale`非空≤2000字符、`event_ids`只能取输入事件UUID、只输出一个JSON对象、禁止`<think>`/围栏/前后说明；**未放宽任何校验**（`JudgeOutput`、严格JSON、事件引用校验、无重试、无自动剥离均不变），`EpisodeReviewArtifact.prompt_version`放宽为v1|v2仅为历史评审（含`9091d602…`）继续可读，`artifacts/reviews`未重写，Web `apiContracts.ts`同步接受两版本。门禁实跑：Python**640 passed**（新增v1兼容只读用例）、Ruff format/check与Mypy 115文件、Web typecheck/build、Node**45/45**、Edge**66/66**（msedge）。**本轮未发真实模型请求，v2未经真实验证**；真实Judge调用仍需负责人另行授权一次，单次结果不构成质量/一致性证据。ADR-039§12、`docs/learning/V0.3-real-judge-20261022.md`§6、current-state已同步；无Git提交/推送，全部dirty/untracked与21题保护。

负责人2026-10-22要求接续Codex继续开发。ADR-039独立复核已实施；Trae本轮出具`docs/handoffs/V0.3-acceptance-review-20261022.md`整版验收矩阵并实跑门禁：Python**639 passed**、Ruff/Mypy 115文件、四套固定回归**22格0退化**、`context_ablation`退出0、Web typecheck/build、Node**45/45**、Edge**66/66**，负责人批准后`vite 6.4.3=>6.4.5`（锁3行）使`npm audit`**0漏洞**，完整`scripts.check`**Quality gate passed**（证据`artifacts/quality/ecc86849-de72-4ce8-9843-ae9a4c362e76`）。同日补两处缺口：新增`apps/web/e2e/runtimeTarget.spec.ts`（PydanticAI选择器/披露/CSV版本列），并修复`EpisodeReviewPanel`同tick回收blob导致的Edge偶发下载取消。随后按负责人授权跑**真实限定一对**：`coding-minimax-m2.7-free` × `order-status-001`，左`handwritten`/`reference-v2`、右`pydantic_ai`/`pydantic-ai-slim-2.57.0`，两臂均SUCCESS、Step2/2、模型调用2、Token 2790一致，Trace各17事件逐项相同、无框架额外请求（实验`db7ee2c4-98e5-4c31-b350-24e628638b46`，明细`docs/learning/V0.3-real-runtime-pair-20261022.md`）；**单对不外推收益/稳定性**。V0.6 §19七项有实现与自动化证据，Reflection按C暂缓未实施；Memory/Planning区分度与Judge一致性仍须另行授权，A1调度缺口不变，**整版未签收**，现场体验清单交负责人执行。负责人同日再授权**真实Judge限定一次**：`coding-minimax-m2.7-free`对已保存Episode`3af370c8…`只发一次请求，返回非严格JSON，按既有规则留档`failed / INVALID_JUDGE_OUTPUT`（评审`9091d602-582d-4009-8584-2a4a0b98799f`，用量2711/252，源哈希与Episode/Experiment数量不变），无重试、无二次请求，API仍只暴露Fake Judge，**该失败不构成Judge质量证据**；随后批准A方案加发唯一一次诊断（不写评审、不改产品代码），确证根因为`<think>`推理文本+字段不合契约（`verdict="PASS"`、维度为布尔`true`），属`episode-review-v1`协议描述不足，正确改进是升`prompt_version`且须另行确认，不得放宽解析/自动剥离/自动重试，明细`docs/learning/V0.3-real-judge-20261022.md`§5与ADR-039§11。无Git提交/推送，全部dirty/untracked与21题保护。

负责人2026-10-21再次核查Trae。当前执行仍docs/tasks/V0.3-runtime-admission-trae-20261021.md顶部，二次结论docs/tasks/V0.3-trae-review-20261021.md：Trae补了设计表格，未安装/实现/新测试；Codex补固定源码AST/SHA并修正独立调度判据、fixed_config不含runtime_version和超时不能补响应等错误。下一项为ADR-038§10具体审批的隔离Fake准入（固定slim2.57.0、独立环境、不改主锁/公开Schema/真模型/Git），获准后用运行证据判断是否完整Runtime；不将单步模型桥接发布为第三Runtime，也不以外层while否定合法框架驱动。通过再定案成品协议并接正常API/Web/对照/恢复，失败交最小复现停止；当前安装未批准，Reflection C继续暂缓。旧153/22/596-44-61不冒充新测试，21题和全部未提交成果保护。

负责人2026-10-21要求复核Trae并明确下一步。最新复核docs/tasks/V0.3-trae-review-20261021.md，当前执行卡docs/tasks/V0.3-runtime-admission-trae-20261021.md。Trae本阶段为设计/旧回归记录，未实现Reflection/第二外部Runtime；纠错样本实际Fake、205扫描范围与方案零成本等表述已修正，保留仓库所记Reflection C暂缓、不激活新任务。ADR-038仍Proposed，先查固定tag、补单次调用/整批预检/Trace/用量/恢复接缝、最少依赖及新旧API/对照目标/来源矩阵；具体方案确认后Fake准入，通过再成品API/Web/对照/恢复，不静默single或包装手写loop。153项复跑20.49s、旧22格报告只读重算一致；596/44/61仍旧完整基线。保留全部dirty/untracked与21题；无安装/真实模型/Git提交授权，后续Judge/人工复核仍具体ADR。

负责人2026-10-21要求向Trae交接，当前执行入口改为docs/handoffs/trae-20261021.md和docs/tasks/V0.3-reflection-recovery-trae-20261021.md，取代10月19日从零做Planning的任务顺序。先保护HEAD40b57c1后的全部dirty/untracked及当前21题，短核查已实现规划/记忆/批次/检索；第一主项为有Trace/测试来源的失败清单、受限Reflection具体Proposed ADR和现有Recovery固定模板/报告，新协议确认后再做正常API/Web/双Runtime/预算/恢复/公平对照成品。随后沿周计划推进第二外部Runtime选型ADR、独立Judge/人工复核和整版签收；不能把参数纠错改名反思、Fake声明当真实收益或未定ADR写Accepted。596Python/44Node/61Edge仅为10月20日接手前基线，修改后记录实际门禁。本次仅文档交接，无新模型调用、Git提交/推送授权，保留全部既有成果；普通已批准范围修复/选择不反复问是否继续。

负责人2026-10-20要求接续开发并明确确认按ADR-036实施两题。已接入document_route/conditional-eligibility-v1的条件路由与遗漏核验，复用原评分/工具/规划/API/Web；Fake只读公开文档，原19题字节保持。最终596Python/44Node/61Edge完整门禁、实际MCP HTTP4次运行/2次新Python进程恢复通过；源码/状态/失败与产物见docs/learning/V0.3-conditional-planning-20261020.md、对应任务卡及current-state。Fake双方都通过且计划侧多声明，不等于真实规划收益或V0.3整版；后续真实一对须明确范围与授权，Reflection/第二框架/Judge仍先具体ADR。保留全部既有未提交成果，不提交/推送GitHub，无新增真实模型调用。

负责人2026-10-20要求Codex验收Trae。ADR-035已由负责人确认四项取舍并实施，不再按旧交接称Planning完全未实现。Codex复现修正计划安全点/保存结果来源、单次与实时入口、偏置基线文案、请求诊断/混合工具档位及安全指标，任务源升1.1.0且旧冻结来源保持。修补后534Python/44Node/58Edge完整门禁通过，两Runtime实际MCP HTTP运行及新进程恢复各2/2。具体根因、源码与实际产物见docs/tasks/V0.3-planning-review-20261020.md及current-state。仅组件技术验收，真实模型未跑、唯一样本的复杂规划区分度未证，不等于V0.3整版签收；后续新任务/协议仍先ADR，不自动批量真实调用或Git提交，保留全部既有成果。

负责人2026-10-19明确将接下来的开发交由Trae完成。最新入口docs/handoffs/trae-20261019.md、执行卡docs/tasks/V0.3-planning-trae-20261019.md；取代10月14日交接作为当前任务入口。先保护本地HEAD40b57c1之后全部未提交/未跟踪成果，核对已实现的记忆轴/三事实题/serial批次/ID检索；下一主项为Planning具体ADR与正常API/Web/恢复/公平对照成品，再沿周计划推进。新规划不能以N1无记忆失败直接证明必要，也不能把未定方案写Accepted；按现有ADR规则，不因常规选择反复问是否继续。接手前513Python/41Node/55Edge仅为旧基线，修改后记录实际门禁。此次仅文档交接，无新模型调用或Git提交/推送授权；未来多Agent仍为研究方向。

负责人2026-10-19要求接续开发，本周目标基本完成V0.3。先按Accepted ADR-034收口实测暴露的检索问题：新Episode1.5/Experiment1.8、文档任务+id-search-v1、ToolSetv1.5.0采用ID精确优先/字面回退及空结果建议；本地/MCP共用实现，旧请求/安全点/回归依保存版本，搜索仍零阅读证据。必须在任务派生后选择工具集，防止新计划误用旧工具。实际门禁/真实限定单对见current-state与V0.3-document-search-20261019学习交接。本周全部原定能力及缺口见docs/tasks/V0.3-week-plan-20261019.md，Planning/Reflection/第二外部Runtime/Judge等未实施项仍先具体ADR，不能将Memory收尾算整版完成；不自动提交GitHub，保留所有既有改动。

负责人2026-10-19随后明确要求完成多工具调用、保留单工具并同步UI，按Accepted ADR-033实现有界只读批次/顺序执行。此前“多调用坚决终止”对旧single保存模式继续有效，不能阻止本次授权的serial新模式。ModelConfig1.1、ModelResponse1.1批次、新请求Episode1.4/Experiment1.7及Session1.1队列明确版本化；新serial任务派生+serial-v1，原JSON/评分保持。代码/状态/失败/质量及免费模型复测以docs/learning/V0.3-serial-tool-batches-20261019.md和current-state最新记录为准，不宣称批次并发或外部写幂等。保留所有未提交交付，不自动提交GitHub。

负责人2026-10-19确认Accepted ADR-032全部三题，Codex已接入document_rule/fact-unit-rule-v1和仅新题的v1.4工具说明，复用OrderStatusEvaluator v2和原工具参数。旧15题字节保持、恢复沿保存版本；新三题在正常目录/实时资料/派生输出/记忆轴/CSV可用。负责人同轮允许免费模型验证，限定一个模型/一题两侧，结果/失败/完整门禁以docs/learning/V0.3-memory-challenge-20261019.md及current-state最新记录为准，不能沿旧计划声称尚未批准。后续按实际失败先提具体ADR；不扩摘要、数据库/Planning/多Agent或批量测试，不提交GitHub，保护之前未提交交付。

2026-10-18负责人同意执行下一步计划，Codex已完成A离线记忆诊断：`scripts.review_memory`只审查保存Experiment/一对Episode，复用配置/来源/固定变量校验，缺Trace/用量保持未知，拒绝覆盖与未来来源；共享按事件顺序的成功阅读统计给原CLI。源码、命令、实际旧真实样本只读审查及414Python/39Node/48Edge最终门禁见V0.3-offline-memory-review-20261018学习交接和current-state。B下一步先做少量压力任务的具体ADR/设计，当前未批准新任务协议/评分、摘要/数据库/多Agent或真实批量。本轮不提交GitHub，保留先前未提交交付。

2026-10-18接续开发：在ADR-030/031已实现范围内补保存记忆实验的执行差异审查，任务卡V0.3-memory-result-review-20261018。仅显式GET当前一对Episode，复用Schema/ID校验与documentEvidence成功阅读规则，缺起止Trace显示未知、单侧失败保留另一侧、切换时取消旧请求；不改评分/CSV/公开契约或默认full。实际验证与源码交接见current-state及V0.3-memory-ablation-20261015学习文档。本轮保留本地，不沿用上次一次性GitHub授权；多Agent仍为研究参考。

负责人2026-10-16明确要求将最新成果提交GitHub，本次授权提交/推送当前精读笔记及研究/需求/交接文档，覆盖此前这些文档“保留本地”的阶段约束。本次无新增业务代码，不包含本机密钥、缓存、原始PDF或实验产物，不延伸为后续自动提交授权。

负责人2026-10-15要求持续把论文精读结论同步后续开发文档，供未来多Agent设计参考。先读docs/research/virt-lab-close-reading-2510.08242v1.md及multi-agent-sandbox-direction-20261013.md顶部；原文事实/推断/建议/待核实分清，页码和固定版本可追溯。当前仅研究文档，不启动多Agent或把论文方法视为已采用/已复现/新颖贡献；未来实现仍需具体ADR。上一轮GitHub推送已完成（34fe06e），本轮新增精读文档不自动提交。

负责人2026-10-15本轮明确要求先提交GitHub，授权本次提交/推送已验收的本地源码、文档、测试和品牌资产。下文“不提交GitHub”为此前阶段约束，本次按最新明确授权执行；不包含.env、本机配置、缓存或实验产物，不延伸为后续自动提交授权。

负责人2026-10-15要求Codex验收Trae交付，并承担后续大部分技术开发。Trae已实现ADR-031同窗口记忆轴（请求1.6/计划1.3/结果1.5），不能再依旧交接声称未实现；ADR状态为Implemented、待负责人验收，不等于整版签收。Codex补恢复固定变量、版本/轴双向拒绝与保存Runtime来源校验，源码学习及防错规则见docs/learning/V0.3-memory-ablation-20261015.md，实际门禁见current-state。旧轴/full默认/完整历史保持；下一功能先针对实际失败提ADR，不自动扩数据库/摘要/多Agent，不提交GitHub。

负责人2026-10-14要求向Trae交接，并明确选择“继续V0.3：记忆功能收尾与同窗口对照方案”。先读docs/handoffs/trae-20261014.md和docs/tasks/V0.3-memory-closeout-trae-20261014.md，复核/最小修复现有记忆与完整门禁；随后提出同N轮窗口无/有记忆的Proposed ADR及具体实施/UI方案。旧context_policy轴仍左full，不能静默放宽；新公开协议在具体ADR获负责人确认后实施。未来AgentWorld借鉴只作研究背景，不转而开发多Agent；不提交GitHub，保护全部未提交/未跟踪交付。

负责人2026-10-14授权接续开发，沿用ADR-030做一模型/一任务的同窗口记忆真实探索。MiniMax M2.7退货Task1.3.0两侧均通过：window1为8工具/重复读3/15766报告Token，memory8192为5工具/重复读0/10317Token；仅单对，不外推成功率或稳定收益。新增显式CLI探针与当前Trace前缀阅读计数，空文档/失败不计读，预览零调用；任务V0.3-memory-real-pair-20261014和current-state记录证据。不新增核心协议、数据库/摘要/多Agent，不提交GitHub。

负责人2026-10-14要求单次配置消除空白与右侧堆叠；仅重排UI，右侧常用项/启动操作，高级参数移到独立整行分组，数字紧凑、帮助按需展开。不能通过缩小字体或静默重置配置解决；保留MCP可见权限、历史草稿隔离与仅显式运行POST。任务compact-run-settings-20261014，UI规范1.8，不提交GitHub。

负责人2026-10-14选择接续V0.3单Agent上下文/记忆。按Accepted ADR-030实施有成功工具来源、大小受限的单Episode工具记忆，完整Trace/Checkpoint不裁剪，旧ContextPolicy1.0序列化/哈希保持；Web配置和当前请求来源展示一起交付。任务卡V0.3-episodic-memory-20261014；不启动二维多Agent、数据库或跨任务知识库，不提交GitHub。

负责人2026-10-13重新授权优化对照界面与Dashboard，取代此前暂缓对照UI的优先级。仅全宽配置/图形展示：每侧通过比例环、Token/耗时分图、同comparison_key历史折线，原生SVG无新依赖；历史草稿隔离、未知费用/无样本/单次边界不变，不改API/评分。参考、源码与实际验收见docs/research/experiment-dashboard-20261013.md、docs/tasks/experiment-dashboard-20261013.md和current-state，不提交GitHub。

负责人2026-10-12要求暂缓对照开发，优先实时关联资料侧栏。沿用ADR-013/014/028/029，资料来自当前Trace前缀的初始快照/实际返回，包括干扰项；成功读取才计入已读，实际submit成功才标提交引用，预览按钮零工具调用/零模型注入。断线未返回明确未知，历史不借最终快照补资料；阅读与验证见docs/tasks/realtime-evidence-20261012.md和current-state。不提交GitHub。

负责人2026-10-12授权接续成品开发，现有三场景演示配置/上下文说明与源模型CSV已收口，沿用ADR-026/028/029，只填草稿、不自动运行或改历史。MiniMax退货场景一对真实上下文两侧通过；完整Edge36项、CSV追加后相关4项及真实只读下载复核通过，任务卡V0.3-classroom-product-20261012及current-state记录实际结果。不是整版V0.3签收，不扩大Seed×Repeat，不提交GitHub。

负责人2026-10-12明确更喜欢动物候选B/狐狸；后续品牌方向采用狐狸侧脸、尖耳和路径尾巴，取代此前浣熊推荐。随后要求尾部拐角柔化并说明设计理由；最新柔化PNG、提示词和“寻径之狐”理念见docs/design/animal-concepts-20261012/README.md。仍为概念，不算统一SVG或小尺寸验收，现用Wayfinder未替换。不提交/推送GitHub。

负责人随后授权更换正式图标并制作Logo动态加载动画，已接入统一狐狸SVG、导航1330ms有限播放/独立重播、静态favicon；动态reduce和资源失败静态兜底，不阻塞工作台或代表Trace。Web类型/构建/35单元、完整Edge33/33及专项图标核验通过，实施/实际结果见docs/tasks/logo-fox-20261012.md和docs/design/fox-v1/README.md，原Wayfinder保留。此前“仍为概念/未替换”为历史，最新状态以current-state为准。仍不提交/推送GitHub。

负责人2026-10-12撤回自动提交/推送授权：完成任务后保留本地改动和交接，等待负责人明确要求再决定提交GitHub。不得沿用2026-10-11的自动同步授权。

负责人2026-10-12授权补少量有实验价值的复杂任务，要求最小验证后完成实际Web产品闭环。按ADR-028增加跨文档引用与完整证据任务，不强行增加调用次数，不引入数据库或新框架；原12题/评分/历史保持。任务卡与current-state记录验证、真实小样本及演示入口。

负责人2026-10-12授权复测三个新场景并修复真实失败，按ADR-029为新任务启用无序证据评分和任务限定工具范围；当前Task1.3.0/ToolSetv1.3.0进一步明确可直接读取正文引用，旧v1.2.0说明保留。旧任务/结果/恢复沿用保存版本；多调用仍严格终止，禁止靠丢弃调用或放宽伪造证据通过。继续不提交GitHub。

负责人2026-10-04选定D / Wayfinder为图标初版，授权优化和Logo动态展示，随后授权接入项目并提交/推送最新代码。导航SVG初次有限播放，点击品牌打开完整展示；favicon静态，reduce即时降级，不代表Trace。资产/验证见 `docs/design/wayfinder-v1/README.md` 与 `docs/tasks/logo-wayfinder-20261004.md`，原四候选保留。此为品牌呈现，不改契约/产品阶段；提交前完整门禁与密钥扫描，不推送本机配置/实验产物。

负责人2026-10-04授权继续从前端页面角度复核优化。范围是历史读取/导航语义、先配置后运行、保存结果分层与对照高级配置；不改变API/Schema/评分/运行条件。见 `docs/tasks/frontend-usability-20261004.md`、`docs/learning/frontend-usability-20261004.md` 和current-state；Fake/未知费用与失败仍明确，键盘与四视口自动验证不替代实机签收。

负责人2026-10-04授权桌面动效调研后直接开发；只优化已实现Web交互，不修改API/Schema/评分或增加依赖。资料和决策见 `docs/research/desktop-motion-20261004.md`，任务与阅读交接见 `docs/tasks/ui-motion-20261004.md`、`docs/learning/ui-motion-20261004.md`。动效不阻塞状态/导航、不劫持滚动，尊重动态减少动效；录像和自动验证不能替代实机手感或版本签收。

负责人2026-10-04暂无时间人工验收，授权优化已实现能力。按Accepted ADR-024补历史上下文比较指纹、完整结果/安全点来源保护、CLI Fake重跑来源、报告与实际Trace交叉核验、投影后的时限检查及减少动效/四视口自动验证。见 `docs/tasks/optimization-20261004.md`、`docs/learning/existing-capabilities-optimization-20261004.md` 与current-state；自动验证不替代人工版本签收，不因额度充足扩大数据库/框架范围或发布代码。

负责人2026-10-04授权按Accepted ADR-023受控启动V0.3上下文管理首切片；V0.2仍待整版签收。ContextPolicy仅投影Provider输入，Checkpoint/Trace保持完整历史；旧Agent哈希不改写。CLI Fake消融与学习交接见 `docs/tasks/V0.3-context-management-first-slice.md`、`docs/learning/V0.3-context-management.md`。消息字节数不是Token或HTTP包大小，Fake遗忘失败不是实际模型能力结论；API/Web新建对照入口、真实小样本和其余V0.3能力留待后续ADR切片。

负责人2026-10-09授权接续上下文API/Web对照，按Accepted ADR-026实现full vs recent_tool_rounds，复用冻结计划和完整历史。新请求版本与新轴结果必须校验；旧轴不混变量，挽救率不适用于上下文轴。源码与验证见任务卡和current-state，不自动扩长链任务/真实批量或发布。

负责人2026-10-11授权修复模型目录误拦截与通用提交说明，按Accepted ADR-027，仅后端配置的实测型号可显式允许目录缺失。新API ToolLab使用v1.1.0工具说明，旧安全点/失败重跑/冻结计划保持保存版本，BFCL评分与权限不变；见current-state及对应学习交接，不把单次成功宣称持续可用。

开始工作依次阅读：需求全文 → AGENTS.md → 相关 ADR → `docs/handoffs/current-state.md` → 当前任务卡 → 测试与源码。不得依赖旧聊天；需求版本不符时停止并同步。

 M1 切片 A–E、V0.1 切片 F 与 Slice G UI 收口已签收，V0.1 的 18 项验收已通过。V0.2 独立 Handwritten/LangGraph Runtime、单变量对照 API/Web 已完成质量门禁、Fake 浏览器闭环与单模型真实小样本；整版尚未验收。ToolLab 单 Episode Checkpoint/Resume 已通过 Fake 跨进程、接口、浏览器及 MiniMax 单题真实中断恢复。BFCL/MCP 单 Episode 和 Experiment 计划恢复、故障注入、第二类固定 BFCL 来源及指标看板见 ADR-015 与 `docs/handoffs/current-state.md`；不能扩大为外部写工具的幂等保证。Slice G 的初次 Copilot 交付由 Codex 复核整改，问题与防错规则见 `docs/tasks/V0.1-slice-G-ui-refresh-copilot.md` 和 `.github/copilot-instructions.md`。Key 仅在本机环境/`.env` 配置，不入库、不入前端、不在聊天中传递。核心接口/Schema/评测口径变化先走 ADR，不得静默修改。

Experiment 的本地单进程并行 Job、Episode 边界暂停/取消/恢复、失败 Episode 显式重跑与固定 Fake 套件回归见 Accepted ADR-016、`docs/learning/V0.2-experiment-control-regression.md` 和 current-state；真实模型与多 worker 并发未验收。

Job 受理前保存固定计划、排队退出后恢复、孤儿取消与两次写入失败边界见 Accepted ADR-021 和 `docs/learning/V0.2-state-integrity-recheck-20261003.md`。完整结果须核对身份与来源才可复用；坏 JSON 仅从有效安全点恢复，仍遵守参考预算。此收尾不等于数据库事务、多 worker 或整版签收。

Web API/SSE 消费字段的 Zod Mini 校验与 Playwright 自动验收见 Accepted ADR-022 和 `docs/learning/V0.2-web-boundaries-automation-20261003.md`。类型从 Schema 推导，历史未知指标不补零；后端 Pydantic 仍是公开契约来源。完整门禁为 `uv --cache-dir .uv-cache run --locked python -m scripts.check`，首次需安装 Web/浏览器依赖；测试拒绝占用端口，独立 Fake 服务不读取 Key。本机实际使用 Edge，未运行的 GitHub/Chromium CI 不得标为通过。

课程 MCP 网络实验按 Accepted ADR-012 提前实施受控例外：固定文档任务的只读工具由独立 localhost Streamable HTTP 服务提供，API/Web 可选远程传输；Fake 双路径、断线 Trace 与单题真实模型探索均已实测。MCP 单 Episode 安全点恢复已按 ADR-015 接入，并通过 Fake 子进程退出后的恢复测试及2026-09-30 MiniMax/LangGraph 独立 HTTP 单题真实恢复。BFCL/Experiment 同日补真实小样本；四套 Fake 回归与 ADR-018 兼容历史看板见 `docs/learning/V0.2-reliability-closeout.md`，整版现场签收仍待完成。阅读 `docs/tasks/V0.2-mcp-network-pilot.md`、`docs/learning/V0.2-mcp-network-pilot.md` 和 current-state。

- Domain 不依赖具体环境、Provider SDK、存储或外部 Agent 框架。
- Application 通过 Domain Port 编排；Runtime 不包含订单业务；Evaluator 只读、不改状态。
- 所有工具通过 Registry/Executor 严格校验、权限与预算检查。模拟工具不需逐步人工审批。
- Python 3.12、uv、Pydantic v2、pytest、Ruff、mypy。公共函数有类型和简洁 docstring；费用 Decimal，时间 UTC，持久化边界有 schema_version。
- 不为未来功能建空模块；按当前切片实施，不实现多 Agent、GridWorld、登录鉴权或未授权的数据库。
- 串行开发，禁止同时修改同一文件。不得覆盖未知改动，不自动初始化 Git、提交、推送、打 Tag 或发布。
- 核心实现同时交付源码阅读顺序、调用链、状态变化、失败路径与实际实验结果，更新 current-state。
- 框架可用不等于 M1 完成；测试通过不等于真实闭环通过。没有运行或未跑通真实调用的不得宣称通过。

质量命令与当前交付边界见 README。
