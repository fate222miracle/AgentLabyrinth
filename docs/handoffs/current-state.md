# Current state

更新：2026-10-28。需求唯一来源：`docs/product/requirements.md` **V0.6**。不依赖历史聊天。

## 2026-10-28 GitHub分组交付回执

负责人本轮明确要求提交GitHub，覆盖下文开发阶段当时的本地保留约束，仅限本次提交/推送及关联PR。已通过本机既有代理完成远端fetch并核对原main为254eac0，没有改全局代理、强推或重写main。GitHub创建与推送均实际成功：

| PR | 内容 | 当前base → head |
| --- | --- | --- |
| [#1](https://github.com/fate222miracle/AgentLabyrinth/pull/1) | Git规范/模板/过期指引与跨平台门禁修复 | main → codex/git-collaboration-rules |
| [#2](https://github.com/fate222miracle/AgentLabyrinth/pull/2) | 已报告用量、安全默认值、只读保存进度与执行证据 | codex/git-collaboration-rules → codex/experiment-reliability-closeout |
| [#3](https://github.com/fate222miracle/AgentLabyrinth/pull/3) | 网络诊断、截止时间测试与最终交接 | codex/experiment-reliability-closeout → codex/fix-provider-network-diagnostics |

实际源码提交：c880507（Git规范）、d611ec1（报告用量）、34b4a51（安全默认）、f3617c8（只读保存与执行证据）、891677f（连接诊断/测试与集成交接），交付回执28113f4。App共享文件已按段暂存，40份交付文件检查无实际Key/产物；密钥、本机环境、实验文件与临时发布脚本保持忽略。原集成代码有10月28日本地705Python/48Node/73Edge、22格零退化与audit0的完整实跑，不冒称每个中间提交都有单独完整门禁。

首次实际远端CI失败：PR#1/#2的Linux Mypy均在scripts/course_demo.py的55/301行报CREATE_NO_WINDOW不存在，未到Python/浏览器；可追溯失败Job 122603865284/122604000347。已补两行标准库getattr兼容回退到0，Windows保持隐藏窗口；保留os导入供受控中断演练使用。共享修复80e79f5还将已验证的截止时间测试修复放入共同基分支，以正常merge提交8eb1dd5/0c4b2f8传到依赖分支，没有强推。兼容补丁后实际30项课程/时限专项通过，Linux目标Mypy在基分支115文件/最终集成116文件均通过，Ruff通过；本机705完整门禁是该两行补丁之前，不能冒称补丁后已重跑全套。修正过程中一次误删仍需的os导入引发子进程失败，已恢复并复跑通过，未发布该错误版本。三个PR已推送修复并重新触发CI，最终远端结果查看各PR实时Checks；不把旧失败藏掉或假称已全绿。没有虚构独立审批、配置分支保护、发布Tag或自动合并。

三个PR存在依赖，保持未合并：先审查/合并#1到main，再将#2的base改为main后审查合并，最后对#3重复；链式交付宜保留祖先关系。不要直接把#2/#3合入其当前功能base而误称已交付main。负责人尚未授权合并。本机当前主工作分支为codex/fix-provider-network-diagnostics；下一步仍处理已有可靠性/效果证据问题，真实调用须新具体授权。

远端后续还出现课程超时演示的时序假设：Job122607293015中40ms在请求前耗尽，系统正确零调用/已知零用量，但演示校验强制未知而报错。同SHA另一份CI已成功，说明该假设受机器调度影响。已按实际Trace区分未请求已知零与已请求无返回的未知，仍禁止工具执行/响应/伪造消耗，新增强制启动前超时回归；不抬时限、不重试挑成功。实际31项课程/时限及Linux Mypy115文件、Ruff通过，沿共同基分支正常merge传递，完整门禁另行实跑。

同步期间发现账号下另有同head、base为main的[PR#4](https://github.com/fate222miracle/AgentLabyrinth/pull/4)，创建时间2026-10-28T03:08:44Z；不是本轮上述三次创建的回执，保留不修改/关闭，不假定已授权合并。该PR与#3共用分支，因此后续分支修复会同时反映。

## 2026-10-28 Provider连接诊断与截止时间回归修复

负责人要求修存量问题，本轮先修AIHubMix目录/推理的连接可观测性：共用安全本地日志分类，包装超时沿已有REQUEST_TIMEOUT，读取重置/HTTP截断转原安全失败码；已收到HTTP状态的错误正文截断保留原状态映射。公开Schema/Trace/评分/CSV及无重试/未知用量规则不改，旧原因不回填。实际仅一次目录GET成功（1047ms、4可见型号、HTTPS代理已配置），不是推理稳定性证明；没有真实推理/Judge/恢复。源码、日志读法和全部失败证据见[本轮交接](../learning/V0.3-network-diagnostics-20261028.md)。

首次完整门禁Python阶段701通过/1失败，定位为既有80ms取消测试假定框架已进入请求；生产系统其实在初始化期间正确零调用超时。仅修测试隔离计时并新增三Runtime初始化耗尽边界，保留真实asyncio取消与所有原断言，64项专项通过；首次失败日志quality.log保留。

最终完整`scripts.check`退出0、**Quality gate passed**：Python **705/119.66秒**、Ruff/Mypy **116文件**、旧四套 **22格零退化**、上下文消融、Web类型/构建、Node **48**、audit **0漏洞**、Edge **73/3.4分钟**。最终证据`artifacts/quality/9097a93e-85ca-4f79-84a7-547ed8e93faa/`、`artifacts/playwright/9c802ca1-9b2e-40e7-96b3-3720d40ac88c/`，日志`artifacts/network-diagnostics-20261028/quality-final.log`。21题及原失败Episode共22份SHA保持；API8000/Web5173恢复，页面GET200、代理回读原368937f4…仍NETWORK_CONNECTION_FAILED/报告3364，没有倒填分类。MCP本轮未启动/未使用；Starlette弃用与大chunk提示保留，无依赖升级。

分支codex/fix-provider-network-diagnostics保留全部dirty/untracked，无Git提交/推送或新真实推理/Judge/恢复。新增分类只进本地日志，目前仍没有Episode/API request_id级关联，若需公开/持久化须先具体方案；这是剩余诊断边界。下一步先根据实际失败日志定位链路，研究收益仍需明确范围与授权的真实对照，不自动重试旧失败。暂停新增机制，A1与真实收益缺口保持。

## 2026-10-26 暂停新增功能，先修明显硬伤

负责人要求先处理存量问题。当前执行交接为[硬伤修复](../learning/V0.3-hardening-20261026.md)：保存Episode按请求/返回/计数及输入输出对账，不完整显示已报告Token与总用量未知，无报告不补零；实验汇总/折线只标已报告值，不能冒称完整节省。Web首次默认Fake、一个普通ToolLab任务/两侧2次、整场16000Token边界预算；无Fake显示空选项，显式选择真实模型后目录刷新保留草稿。工具选择标签澄清为允许工具命中比例，评分/字段/CSV不改。Copilot入口删除旧V0.2任务与有Key就自动真实试跑要求，改读当前SSOT/交接和当次授权。窄屏长错误码实际截图发现越卡后补原生换行，增加卡片自身溢出断言。UI规范1.13。

最终代码完整`scripts.check`退出0、**Quality gate passed**：Python **679/102.15秒**、Ruff/Mypy **116文件**、旧四套 **22格零退化**、上下文消融、Web类型/构建、Node **48**、audit **0漏洞**、Edge **73/2.9分钟**。证据`artifacts/quality/0afe957a-935d-40aa-b971-3d90ecf8148e/`、`artifacts/playwright/acf2e50e-c50b-4cf0-be5b-5b4c7ba02ce9/`，日志`artifacts/hardening-20261026/quality-final.log`；已查看最终1440/390并自动检查1280/720、减少动效、页面及卡片不溢出。早期专项末尾误比较动态request_id而失败已纠正，不隐藏记录；首次完整门禁后截图发现的换行修复已由最终完整门禁覆盖。现存Starlette弃用与构建大chunk提示仍有，不是本轮新增。

21份任务及原真实网络失败Episode共22份SHA前后保持；共享检查对368937f4…实际返回不完整/报告3364，未追加推理或重跑。API8000/Web5173已恢复，页面及代理只读回读该原Episode成功；MCP本轮未启动/未使用。分支 **codex/fix-reporting-and-run-defaults**，全部先前dirty/untracked保留，无Git提交/推送。下一步继续排查网络失败与已有功能的证据/维护问题，不自动进入Reflection/新机制、数据库或多Agent；真实调用仍需具体新授权。完整回归不是规划收益、网络稳定性或整版研究效果证明。

## 2026-10-26 ADR-041只读保存进度与中文诊断交付

负责人确认具体方案后实现GET `/api/v1/experiments/{id}/progress`：以冻结计划和uuid5定位两臂，复用保存结果/安全点与来源hash核查，区分completed/checkpoint/no_saved_record/invalid。缺计划404、坏计划409且不回显内容；坏结果不借安全点冒充完成。Web在Job/待恢复区显式查看，可进入校验通过的Episode；切换/关闭取消旧请求，全部只GET，不自动恢复或推理。原执行/恢复/评分不改，部分执行不生成总体成绩；共享中文诊断明确网络错误不等于配额耗尽。UI规范1.12和源码/失败交接同步。

原真实计划61bd5e1e…只读核对：左368937f4…为completed/false/网络失败，右no_saved_record/null，源字节保持。没有新增真实模型/恢复/Judge。实际新完整`scripts.check`退出0、**Quality gate passed**：Python **679/103.98秒**、Ruff/Mypy **116文件**、旧22格零退化/消融、Web类型/构建、Node **47**、audit **0漏洞**、Edge **70/2.9分钟**。产物`artifacts/quality/c925b5e2-d0ec-46ad-9691-0c47d9ce7aae/`、最终浏览器`artifacts/playwright/1b58ce46-8f5a-411b-a830-c9ad6de6843a/`；专项11Edge及1440/390截图另已核查。API8000/Web5173恢复，MCP未用于本轮。源码顺序/调用链/边界见[学习交接](../learning/V0.3-experiment-progress-20261026.md)。分支仍codex/planning-serial-validation，原规划/规范dirty全部保留，无Git提交/推送；下一真实请求仍需单独授权。

## 2026-10-26 serial规划对照未完成与组件采用提示

负责人另批一对serial，其他条件保持；已创建codex/planning-serial-validation分支，原规划UI与Git规范改动全部保留、未提交。离线正式Fake预检两侧通过。真实POST的左侧首轮执行2个检索，第二模型请求NETWORK_CONNECTION_FAILED，报告Token3280/84仅部分用量；未知用量保护阻止右侧。计划 **61bd5e1e-2d57-4fbb-b955-9a5bb7ebd025**、左Episode **368937f4-84bc-523c-a5f3-9c685578cd72**保存，右侧未启动、完整Experiment未生成；不得将其写成双方失败或完整对照。HTTP400不意味着零模型执行，授权已消费，没有重试/恢复/换模型/Judge。只读核查计划/安全点/Trace与21题SHA通过。

沿ADR-035在PlanningPairReview区分组件启用与实际未声明；缺Trace仍未知。实际typecheck/build、Edge规划专项 **6/6、28.4秒**通过，未重跑全套/Node45，不沿用旧数字。API8000/Web5173恢复，MCP本轮未使用/未启动。下一步先定位网络与未完成实验可观测性，不扩机制；源码/调用链/产物和边界见[学习交接](../learning/V0.3-planning-serial-validation-20261026.md)。本轮不Git同步，Reflection暂缓、A1保留。

## 2026-10-26 Git协作规范落地

负责人要求GitHub协作对齐企业开发。复用需求§28和现有quality工作流，补根CONTRIBUTING.md、Issue/PR模板及README入口；明确任务分支、原子提交、PR实际证据、负责人合并和revert原则。Codex使用codex/前缀，不引入长期develop或新工具依赖。既有254eac0保留，不重写公开历史；后续规划UI与规范应分组提交，共同文件按段核对。远端分支保护未核实/配置、CI本轮未执行；只做文档差异与模板入口检查，不用此前测试数字背书。本轮不提交/推送/创建PR，原规划代码与交接全部保留。

## 2026-10-26 规划执行证据展示与唯一真实对照

负责人接续开发并另行批准MiniMax M2.7×planning-route-002唯一一对（handwritten/single/full/无纠错，各10步/20000Token/300秒、全局40000）。已运行并保存实验 **39164f38-2e4f-4845-beb5-776bdb829315**：左MULTIPLE_TOOL_CALLS/21489报告Token，右累计输入预算终止/23793Token；均6模型/5工具、4成功读/0重复、无计划声明、无实际提交。核查固定变量/安全点/Trace与21题哈希通过；不重试、不换模型、不追加Judge，授权已消费。这不是规划收益证据，也不能把右侧失败归因于未发生的额外规划调用。

沿ADR-035/036完善PlanningPairReview：并列展示实际提交/证据、成功阅读与引用、模型/工具次数、已报告输入输出Token/耗时/终止说明；复用已有派生工具与中文字段组件，不改Schema/评分或任务。缺Trace保留未知，缺提交明确提示；刷新/快速切换只GET。实际typecheck/build、Node **45**及Edge规划专项 **6/6、28.7秒**通过，已查看1440/390截图，服务恢复。没有Python业务改动，未重跑全套668/68，不把旧数字冒充新门禁。源码/失败/全部真实结果及下一候选见[学习交接](../learning/V0.3-planning-evidence-20261026.md)。本轮不自动Git同步，Reflection暂缓、A1保留，下一真实实验仍须单独授权。

## 2026-10-26 阶段回顾与本次GitHub同步授权

负责人明确要求提交GitHub并回顾工作，授权本次同步已验证源码、测试、21题及协作文档；覆盖旧“不提交”阶段约束，不授权未来自动推送或新增真实推理。阶段成果、证据与下一步见[回顾](V0.3-stage-review-20261026.md)。本轮不改业务代码，沿用10月25日最终完整门禁668Python/45Node/68Edge，提交前另核对差异和敏感文件；本机密钥、实验产物与测试缓存保留本地。Git提交/远端同步结果以实际操作回执为准。

## 2026-10-25 ADR-040真实Judge：撤下演示操作，接入真正模型评审

负责人确认ADR-040并随后明确允许试一次免费模型，覆盖旧“真实v2只准备”的阶段限制。已撤下正常页面人工表单/Fake生成和大块空白；新增Review请求1.1显式aihubmix/model，经原白名单/目录校验与Provider一次无工具评审，65536字节输入闸门/800输出Token/30秒，无重试/修复/剥离。旧1.0、人工作品、Fake与v1/v2历史、完整CSV及原评分保持。Web展示判断/理由/引用和与规则一致或分歧，旧人工/Fake仅归档；对照复核只统计真实模型记录。无新依赖、不提交Git，21题和所有既有成果保护。

首次后端31项、Web专项5/5通过；修复前完整门禁665Python/110.51s、Node45、Edge68/2.9m、Ruff/Mypy115、旧22格零退化、消融/构建/审计通过（`artifacts/quality/dc6aade3-fc88-4e2e-bbb3-7e6c4541a03d/`）。

按初次授权通过正常POST1.1实测MiniMax M2.7，Review24d1c9ec…因INVALID_JUDGE_OUTPUT失败，Token2827/355。负责人另批一次格式诊断，确证think前缀238字符，内部JSON合法且5条引用归属有效，Token2827/245、不保存推理、不新增Review。按MiniMax官方原生reasoning_split参数修复，仅MiniMax Judge设True，普通Runtime默认None不加键；严格JSON/Prompt v2不变、不剥离。负责人再批准修复后仅一次，正常API成功保存 **b6303391-9092-4150-9aae-b04c42f04013**，completed/pass、三维度pass、中文理由与5条实际引用，Token **2827/264**、费用未知。源Episode `3af370c8-b2a7-54ae-b76f-92ad9b6a804f`与输入哈希吻合、Episode606/Experiment55保持，旧Review字节不变；失败/诊断/成功均保留。实测产物`artifacts/real-judge-product-20261025/`和`artifacts/real-judge-native-20261025/`，三个授权均消费，不再自动真实请求。

最终修复后完整`scripts.check`退出0、**Quality gate passed**：Python **668/107.82s**、Ruff/Mypy115文件、旧22格零退化、消融、Web类型/构建、Node **45**、审计通过、Edge **68/3.0m**。产物`artifacts/quality/b1b24f87-5deb-4064-8902-fe490272d444/`，浏览器`artifacts/playwright/a7821354-be6a-415e-8bef-fd4274f02389/`。API8000/Web5173已恢复，代理GET确认保存Judge为completed/pass/5引用、模型目录live，21题SHA字节保持。查看源Episode的最新评审可看到中文理由，历史排序最新在前，不重新调用模型。源码/状态/失败与有无组件证据边界见[学习交接](../learning/V0.3-real-judge-entry-20261025.md)。Judge只证明该次链路可用，不认证准确率或提高Agent成绩；Planning还没有真实效果证据，后续先固定真实对照，再决定新增机制。无Git提交，Memory/Planning真实批量未授权。

## 2026-10-25 结果复核用途与界面层级优化

负责人认为原面板看不懂、用途不明，要求立即优化。已在ADR-039现有展示范围改为“结果复核”：说明运行后可选检查，人工入口采用“记录我的检查”和完整中文问题；主区保留人工/真实模型的结论、理由与维度，版本/Token/未知费用等默认折叠。Fake按钮及历史移入“模拟测试（开发用）”，完成只标模拟记录生成，不再把固定未知当质量判断；Episode与Experiment复核面板将模拟数量单列，原Experiment评分/图表分母不改。完整CSV、源产物/API/Schema/严格校验均保持，没有真实模型调用/Git提交。

首轮专项Web构建/类型/Node45、Edge4/4通过，已看1440/390截图；后补对照摘要分组与主区文案，最终完整`scripts.check`退出0、**Quality gate passed**：Ruff/Mypy115文件、Python **647/110.48s**、旧22格零退化、上下文消融、Web类型/构建、Node **45**、审计及Edge **67/3.0m**全部通过。产物`artifacts/quality/eec633b4-e1a2-412a-b042-656855032c6a/`，最终截图`artifacts/playwright/edc87e06-d349-4941-ad35-cbe9887df8d8/`，已看最终1440图。源码/状态/失败见[学习交接](../learning/V0.3-review-usability-20261025.md)。测试后自己启动的API/Web已恢复8000/5173，实际GET200且目录live，MCP与历史保持。此前现场验收确认不撤回，也不虚构本次新UI的负责人体验；无Git提交/真实模型推理。

## 2026-10-25 负责人现场确认通过，接续固定实验准备

负责人明确回复“继续进行开发吧，我验收了”，当前交付范围现场体验通过，不再把这项列为等待，也不代填每项操作结果；Reflection暂缓、PydanticAI A1边界、v2真实Judge未验证和研究效果待证保留，V0.2独立整版签收不由本次追溯补写。

Codex沿已批准组件继续检查实验链路，发现`run_regression.preflight`将右侧写死LangGraph，导致合法PydanticAI误拒绝、相反方向目标变化却可能漏过前检。已在共享校验按`runtime_target or langgraph`修复，与正常冻结计划一致；旧默认/显式两目标/更换目标拒绝三组回归修复前3失败，修复后含记忆/规划/上下文**59 passed / 10.99s**，Ruff及单文件Mypy通过。

复用现有六题生成固定Fake记忆/规划各三对基线，并经正式回归再跑；记忆三题左MAX_STEPS/右SUCCESS，规划三题双方SUCCESS，PydanticAI一对另验证回归入口，**6+6+2=14格零退化/零改进**，不是全部Episode成功或真实收益。记忆离线报告reviewed；21份任务SHA前后一致。旧四套回归另复跑**22格零退化**。产物`artifacts/fixed-experiment-preparation-20261025/`及`artifacts/fixed-regression-20261025/`；[固定清单、源码/失败与下一步](../learning/V0.3-fixed-experiment-preparation-20261025.md)。只改脚本目标校验和测试，Web/公开协议/评分未改；未重跑全套，上一条644/45/67仍为此前门禁，不冒充本次。现场三项服务保持，无新增真实模型/Git提交。

下一步候选为planning-route-002的一模型/一任务/同full限定一对，具体条件已准备但未授权执行；Judge v2同样需要新的明确一次授权。两者不捆绑执行，不按旧授权自动补跑。

## 2026-10-25 现场MCP工具服务补启动

用户真实运行e66b6a9a…（MiniMax M2.7/PydanticAI/配送任务）模型返回一次调用后，MCP search_documents报TOOL_EXECUTION_ERROR。只读检查8765未监听：本次启动只开API/Web而未开独立MCP服务，非模型目录/额度问题。Codex已补启动固定localhost MCP服务，经与API同权限的客户端实际search_documents验证HTTP200、返回documents/search_mode。未新发模型请求、未改失败产物。已补演示文档第三终端命令；用户可保持MCP并显式新运行，或选择本地ToolLab。连接恢复只证明工具链路，不自动宣称真实任务通过。

## 2026-10-25 现场启动：模型目录网络权限问题已恢复

负责人现场发现免费模型目录不可读。Codex启动的API此前位于受限沙箱，日志`NETWORK_CONNECTION_FAILED`；同Key沙箱外只读GET目录成功（4个可见模型），密钥配置存在，未输出Key。仅停止自己启动的API并以获准网络权限重启（仍127.0.0.1:8000），经前端5173代理实际GET `/api/v1/meta`返回`model_catalog_status=live`，可选MiniMax M2.7、GLM5.3、MiniMax M3、GLM5.3 Flash及Fake。无源码/配置/权限白名单变更，无推理请求；目录恢复不证明模型推理配额或实际任务成功。后续由Codex启动需确保后端允许外网；普通本机终端无需因此改Key或关闭校验。

## 2026-10-25 Codex接续：评审来源/用量/CSV与演示收尾

负责人要求继续，Codex确认10月23日P0仍未实现后接手完成：EpisodeReviewPanel按provider显示真实/Fake来源，失败保留失败码；补提示/量表版本、模型、评审Token/模拟标识、估算费用及价格表。Review CSV保留旧列并追加9列，费用未知导出空金额及false已知标识，旧Experiment CSV/核心Schema/评分不变。新增离线GET夹具验证v1失败/v2完成、空用量/模拟用量、实际CSV下载的BOM/转义/公式防护与刷新零POST，五视口含720等效200%及减少动效通过，专项Edge4/4。源码/状态/失败见[学习交接](../learning/V0.3-review-presentation-20261025.md)，[三分钟Fake演示及失败预置](V0.3-demo-20261025.md)待负责人体验。

首次完整门禁在新Zod审计处停止，升级前独立Edge67通过。负责人随后明确批准只升Zod4.6.6，已完成package.json一行及锁根声明/Zod包项更新，逐条比较其他锁包项不变、既有Vite6.4.5保留。升级后Ruff/Mypy115文件、Python644/109.26s、固定回归22格0退化、上下文消融、Web类型/构建/Node45、Edge67/2.9m全部通过，审计0漏洞，整条`scripts.check`退出0、**Quality gate passed**。产物`artifacts/quality/069bff9b-5a52-45fa-a854-057b1aa5fb11/`。未调用真实模型/提交Git；v2真实验证仍需新的一次授权、Reflection继续暂缓、A1调度边界与整版待现场签收保持。

## 2026-10-23 Codex复核Trae与最新交接

当前执行入口：[Trae交接](trae-20261023.md)；[复核明细](../tasks/V0.3-trae-review-20261023.md)。v2严格协议、Vite补丁、Runtime选择器及下载修复已核对。Codex增强v1兼容测试以实际GET单份/列表和字节不变为准，增加四组真实失败形状的Fake回归（一次调用、无工具、不修复）及Node两版本断言。实际**111 Python定向/7.89s、45 Node、5 Edge/14.6s、typecheck、相关Ruff/Mypy通过**；首轮Windows沙箱临时目录权限失败后获准重跑，不是产品失败；未重跑完整640/66套件，不改原日期证据。

只读复核真实实验db7ee2c4…与评审9091d602…：版本/Token/17事件一致，Review源/输入哈希均吻合；两臂费用实际`is_known=false`，已修正报告误写已知，规划对照请求应1.9而非1.6也已修正。待收尾：原Review列表把真实llm_judge误标Fake，版本/用量/未知费用未展示和导出，交Trae按ADR-039现有字段修复、离线夹具验收，再做现场材料。真实Judge v2仍未经验证，需另行明确一次授权；不自动批量，不提交Git，全部既有成果保护。

## 2026-10-23 Judge Prompt 升级 episode-review-v2（仅协议层，未发真实模型）

按ADR-039 §11确证的根因（`episode-review-v1`未声明枚举取值、未禁止推理文本），本轮把Judge System Prompt升级为`episode-review-v2`并**未发任何真实模型请求**。`packages/application/review.py`新增`JUDGE_SYSTEM_PROMPT`常量，逐条写明六个字段枚举（`verdict: pass|fail|uncertain`，三维度`pass|fail|unknown`，`rationale`非空≤2000字符，`event_ids`只能取输入事件UUID）、只输出一个JSON对象、禁止`<think>`推理文本/围栏/前后说明；`prompt_version`常量升为`episode-review-v2`。**未放宽任何校验**：`JudgeOutput`类型、`model_validate_json`严格解析、`_validate_event_ids`、无重试、无自动剥离全保持；`EpisodeReviewArtifact.prompt_version`放宽为`episode-review-v1 | episode-review-v2`仅为让历史评审（含`9091d602…`）继续可读，`artifacts/reviews`未重写；Web`apiContracts.ts`同步接受两版本字面量。自动化：Python**640 passed**（新增v1兼容只读用例）、Ruff format/check与Mypy 115文件、Web typecheck/build、Node**45/45**、Edge**66/66**（msedge）。**v2未经真实模型验证**，Fake只覆盖协议闭环；真实调用需负责人另行授权一次，且单次仍不构成Judge质量/一致性证据。详见[真实Judge限定一次](learning/V0.3-real-judge-20261022.md)§6与ADR-039 §12。

## 2026-10-22 真实Judge限定一次：链路打通，严格JSON闸门拒绝（失败留档，不重试）

负责人按ADR-039 §9.4单独授权“一个模型、一道已保存Episode、一次请求”后执行：`coding-minimax-m2.7-free`对Episode`3af370c8-b2a7-54ae-b76f-92ad9b6a804f`（`order-status-001`，SUCCESS，17事件）的唯一一次请求返回非严格JSON，产品按既有规则保存`failed / INVALID_JUDGE_OUTPUT`（评审`9091d602-582d-4009-8584-2a4a0b98799f`），**无verdict、无重试、无二次请求**；真实用量prompt 2711/completion 252（`simulated=false`），费用仍未知（`aihubmix-free-unverified`）。源Episode哈希`ee74a953…`评审前后一致，Episode 603/Experiment 55数量不变，只新增1份评审。`POST /api/v1/episode-reviews`仍只暴露Fake Judge，未改契约、未在网页开放真实Judge；原始响应文本不落盘。负责人随后批准**A方案**追加唯一一次诊断请求（不写评审、不改产品代码）：原文为`<think>…</think>`加JSON，严格解析在第1行即失败；切出花括号后仍有4个契约错误——`verdict="PASS"`大写、三个维度是布尔`true`而非`pass|fail|unknown`，`rationale`与5个`event_ids`本身合法且都属于该Episode。故根因是`episode-review-v1`未声明枚举取值、未禁止推理文本，属**协议描述不足**，不是解析器过严或模型完全不会评；正确改进是升`prompt_version`（须另行确认），不得放宽解析/自动剥离/自动重试。详见[真实Judge限定一次](learning/V0.3-real-judge-20261022.md)§5与ADR-039 §11。

## 2026-10-22 真实模型限定一对：Reference vs PydanticAI 两臂均通过（单对，不外推）

负责人授权一道真实样本后执行：`coding-minimax-m2.7-free` × `order-status-001`，左`handwritten`/`reference-v2`、右`pydantic_ai`/`pydantic-ai-slim-2.57.0`，请求1.10、`runtime_target=pydantic_ai`，实验`db7ee2c4-98e5-4c31-b350-24e628638b46`（产物1.7）。两臂均SUCCESS、Step2/2、模型调用2、工具调用2、报告Token 2790（2692+98）完全一致；两侧Trace均17个事件且逐项相同，**无框架额外模型请求**，真实Provider下“一次框架模型请求＝一次`Session.call_model()`”成立。耗时左18895ms、右23964ms（单次，不作性能结论）；共4次模型请求，无重试、无补跑、无模型替换。明细见[真实限定一对](learning/V0.3-real-runtime-pair-20261022.md)与ADR-038 §12.6；**单对样本不外推收益/稳定性，A1调度缺口不变，真实Judge/Reflection仍另行授权**。

## 2026-10-22 V0.3整版验收矩阵已出具（技术门禁全绿，未签收）

Trae接续Codex，按需求V0.6 §19逐项复核并实跑：Python**639 passed**（177.00s）、Ruff format 115文件、Ruff check通过、Mypy 115文件、四套固定回归**2/8/8/4共22格0退化**、`context_ablation`退出0、Web typecheck/build通过、Node**45/45**、Edge**66/66**（3.8m）。负责人批准后`npm audit fix`只把`vite 6.4.3=>6.4.5`（锁3行，`package.json`未改），审计**0漏洞**；完整`scripts.check`已**Quality gate passed**（证据`artifacts/quality/ecc86849-de72-4ce8-9843-ae9a4c362e76`）。

同日补两处真实缺口：新增`apps/web/e2e/runtimeTarget.spec.ts`覆盖PydanticAI对照选择器、界面披露与CSV `runtime_version`；修复`EpisodeReviewPanel`在`click()`同tick回收blob导致Edge偶发`download.path: canceled`（改为与`App.downloadFile`一致的延迟回收），复跑全套66项无失败。

逐项结论：Context/Memory/Recovery/Planning/第二Runtime/消融模板/独立复核7项有实现与自动化证据，Reflection按负责人决定C**未实施**。矩阵同时标注真实模型效果（Memory/Planning区分度、Judge一致性）仍未证、A1调度缺口、真实Judge未授权。**V0.3整版未签收**，现场体验清单（Fake、不读Key）交负责人执行；V0.2现场签收同样独立未完成。明细见[验收矩阵](V0.3-acceptance-review-20261022.md)，门禁产物在`artifacts/quality/`。本轮无Git提交/推送，dirty/untracked与21题保护，Reflection继续C暂缓。

## 2026-10-22 ADR-039：独立 Judge 与人工复核已实施

负责人明确同意ADR-039后，新增独立`EpisodeReviewArtifact1.0`和`reviews/<review_id>.json`原子产物；人工复核与Fake Judge共用总判断/答案/证据/过程量表及Trace事件引用。评审冻结输入刻意不含原`evaluation`，保存源Episode和输入SHA-256；源缺失/改变、无最终提交或外来事件默认拒绝。Judge仅一次无工具Provider调用，无自动修复/重试；成功、非法JSON、非法事件引用、Provider失败均有独立状态，Fake固定`uncertain/unknown`只验证机制。

API新增显式创建、按Review ID回读、按Episode列表三个端点。Episode Web并列原规则评分与独立复核，支持人工表单、显式Fake Judge、刷新只读和独立Review CSV；Experiment折叠区仅在展开后GET已有覆盖/同向数，不自动创建评审，不改原图表分母。原Episode/Experiment/Evaluator/Trace/Agent预算/成功率/旧CSV保持。

实际定向后端**105 passed**；完整Python**638 passed**、Ruff/Mypy115文件通过，四套固定Fake回归**2/8/8/4、0退化**，Web typecheck/build及Node**45 passed**。首次Edge全套暴露新折叠区误复用旧`.episode-details`类的选择器兼容问题，改为独立类后最终完整Edge **63 passed**。共享质量命令仍在既有`vite<=6.4.3`高危开发依赖审计处停止，未改锁/自动升级。完整源码顺序、调用链和失败见[学习交接](../learning/V0.3-independent-review-20261022.md)。本轮无真实模型、Git提交/推送；Reflection继续C暂缓，下一项是V0.3整版验收矩阵与负责人体验签收。

## 2026-10-22 Codex接续开发：第三Runtime边界修复与ADR-039

Trae已完成ADR-038第三Runtime成品，Codex以仓库内固定依赖复核契约/超时/批次/跨进程恢复/API，首次因Windows临时目录权限仅89项进入执行、84项夹具前报错；改用获准的项目临时目录后**173 passed / 23.93s**，不是代码失败。静态审查发现PydanticAI在调用Session桥接前若框架初始化异常，adapter吞掉异常并返回默认`FAILED/loop_terminated_without_submission`；现改为`RUNTIME_ERROR/unhandled_runtime_error`，保留已由Session裁决的validate/end路径，新增零Provider调用回归后**174 passed / 24.63s**。本次未跑真实模型或提交Git。

该阶段随后由负责人确认ADR-039并已实施，最新事实以上节为准；真实Judge仍另行授权。Reflection继续C暂缓。

## 2026-10-21 第二Runtime成品化：ADR-038已定案，第三调度接入项目（A1缺口保留）

负责人确认ADR-038 §10三项后执行：**A1限定接受并记为调度缺口**、**`pydantic-ai-slim==2.57.0`装入项目锁**、**按候选一次性定案契约**。ADR-038已由Proposed改为Accepted，实施记录见其§12。

- **依赖/锁**：`pyproject.toml` +1行（无Provider extras）；`uv.lock` 仅新增，**无既有版本改动**，新增5个分发`pydantic-ai-slim`/`pydantic-graph`/`genai-prices`/`griffelib`/`logfire-api`，许可为MIT/BSD/Apache族，无新增exporter。`uv sync --frozen --offline`通过，运行时实读2.57.0。
- **适配器**：`packages/runtime/pydantic_ai/adapter.py`用自定义`Model`桥接，**一次框架模型请求＝一次`call_model()`**；框架只负责单步内`ModelRequestNode→CallToolsNode→End`，**步间推进仍由adapter按Session返回值完成**（A1缺口，不得宣称需求§8.5第三调度完成）。未包装`HandwrittenRuntime.run`，未用`pydantic-graph`冒充`Agent`。`session.py`只增只读`available_tools()`；`factory.py`缺依赖/缺元数据时抛`RuntimeUnavailable`，不回落`handwritten`、不伪造`reference-v2`（A-10）。
- **契约**：`RuntimeBackend+pydantic_ai`，AgentSpec 1.4、单次请求1.7、实验请求1.10（`runtime_target`显式、`handwritten`目标拒绝、`runtime_backend=pydantic_ai`一律拒绝）、ExperimentPlan/Checkpoint 1.5、ExperimentArtifact 1.7；1.5/1.7只允许runtime轴且左臂必须`handwritten`。旧轴、`full`语义、评分与恢复未改。
- **产品链路**：单次API/Web三态入口、正式`runtime_backend`对照右侧目标（LangGraph/PydanticAI）、保存恢复、CSV新增`runtime_version`列与图表右侧标签均按`recovery_agent.runtime_backend`读取。
- **实际门禁**：Python **624 passed**（忽略e2e，137.87s）、`ruff format --check`/`ruff check`/`mypy`（113 files）通过、4套回归退出0、Web `typecheck`/`build`通过、网页单测**44/44**、Edge e2e **61/61**（`AGENTLABYRINTH_E2E_CHANNEL=msedge`）。
- **未通过项与边界**：`npm audit --audit-level=high`报`vite <=6.4.3`的3条`launch-editor`告警（开发依赖，锁定未改，属外部通告），升级需另行批准。**真实模型未运行**（全部Fake），A-08旧22格基线未重录、沿用只读复核；Reflection保持C暂缓，Judge/人工复核仍另行ADR。无Git提交/推送，全部dirty/untracked、21题保护。

## 2026-10-21 第二Runtime：隔离Fake准入已执行（机制通过，调度有缺口）

按负责人授权“隔离环境/固定版本/仅Fake”，以`uv run --cache-dir .uv-cache --frozen --with pydantic-ai-slim==2.57.0`在临时overlay执行（Python 3.12.14，distribution实读2.57.0）。**未改`pyproject.toml`/`uv.lock`，未装进项目环境，未新增backend枚举/API，未跑真实模型，未提交Git。**

脚本与报告：`artifacts/runtime-admission-20261021/spike.py`、`report.json`，断言**24/24通过**。覆盖：单次Provider调用与`MODEL_REQUESTED/RESPONDED`对应（超时允许只有请求、无响应）、未知/禁止工具终止且无补请求、参数纠错一次、第二次参数错零执行、整批末项非法`TOOL_STARTED=0`、`batch_rejected`原样保留Call ID、提交后不再调模型、未报告用量保持`null`、步数预算、serial逐项、新进程从`pending=[call_batch_2]`恢复到`SUCCESS`无重复。

**调度缺口（不自行通过）**：每条模型步为一次独立`Agent.iter`，节点`UserPromptNode→ModelRequestNode→CallToolsNode→End`；步间推进仍由adapter按Session返回值执行，属ADR-038 §3的“A1限定”，不是“框架驱动整个循环”，不构成需求§8.5第三调度实现的已完成证据。另记录两项框架行为：deferred下未注册工具名会触发框架再请求（桥接须先按Session暴露集过滤才能保持1次调用）；批次内重复ID由框架先抛`UnexpectedModelBehavior`，adapter捕获后交回Session裁决。

依赖实读：slim直接依赖`anyio`/`genai-prices`/`griffelib`/`httpx2`/`opentelemetry-api`/`pydantic-graph`/`pydantic>=2.12`/`typing-inspection`，与项目现有`pydantic 2.13.5`、`anyio 4.15.1`无冲突；OTel为基础依赖且无exporter，docs中“零追踪依赖”表述已改为“默认无外联上报”。锁文件差异/许可全量清单仍需批准安装时审查。

待负责人三项决策见ADR-038 §10（A1限定取舍、安装范围、成品契约候选）。ADR-038仍Proposed；旧153/22与596/44/61均为各自日期基线，非本轮新增；21题与全部未提交成果保持。

## 2026-10-21 Codex第二次复核：设计补充完成，运行准入未做

负责人再次要求核查Trae并安排。Trae新增ADR-038依赖/调用表/兼容矩阵/断言等设计，没有新增代码、依赖或测试。Codex修正三项实质问题：仅一次框架节点转移/禁止while不是独立Runtime判据，单步模型桥接不能当第三Runtime；现有fixed_config不含runtime_version，不能宣称框架版本自动分曲线；Provider未返回时不应为请求/响应一一对应补事件。补了固定v2.57.0完整源码的Model.request/Agent.iter/Deferred符号定位及逐文件SHA；方法签名存在不是适配成功，Session.call_model返回NextNode与框架ModelResponse仍需运行桥接验证。

最新[二次复核记录](../tasks/V0.3-trae-review-20261021.md)与[执行卡顶部](../tasks/V0.3-runtime-admission-trae-20261021.md)：下一步提交ADR-038§10的**隔离环境、固定slim2.57.0、仅Fake准入**具体审批；获准后直接验证完整多轮调度、单一Provider/Trace/预算、整批预检、未知用量与新进程恢复。不改主锁/公开Schema、不真模型/Git。通过再基于证据定案正常成品协议与API/Web/对照/恢复，失败不包装限定桥接算完成。当前未批准安装，Reflection C暂缓，Judge/人工复核仍未实施。

静态快照/AST/SHA在`artifacts/runtime-source-review-20261021/source-manifest.json`（4份完整文件；图文件下载不完整排除），只读指纹检查`fingerprint-check.json`。本次无新框架或功能测试/模型运行，未复跑153/596套件，旧结果仍按原日期引用；源码/21题/依赖锁与全部dirty/untracked保护，不提交GitHub。

## 2026-10-21 Trae第二外部Runtime设计补充（未安装/未实施，已由顶部复核更正）

按[执行卡](../tasks/V0.3-runtime-admission-trae-20261021.md)第一批完成ADR-038设计补齐：§2.1最少依赖方案（拟`pydantic-ai-slim`，R1–R4拒绝标准）、§4.1调用归属表12行（每步标明由Session还是框架负责，并给出`session.py` L399-460/L543-677/L679-759、`langgraph/adapter.py` L49-102固定行号）、§4.1.1接缝S1/S2/S3与失败判定、§5入口/兼容矩阵13行（Agent/Model/单次请求/实验请求/轴校验/checkpoint/产物/`runtime_version`/`comparison_key`/回归preflight/Web/CSV/恢复，旧Schema仍拒绝新值）、§8.1准入断言A-01…A-10（全部Fake可判、复用现有参数化清单，A-08旧22格只读重算不变）、§10五项一次确认。

Trae原固定tag核对定位了Deferred符号，Model.request/Agent.iter原未定位；Codex二次复核已补完整文件与AST位置。Deferred符号只表明延迟调用/按ID回填接口，不能推断SDK天然每步一次run/必然有调度缺口，也不证明完整预检或恢复成立。以顶部复核判据为准，不接受模型桥接作为本轮第三Runtime交付。

本轮**未安装依赖、未改pyproject/uv.lock/业务源码/测试/任务**，未调用模型或提交Git；ADR-038仍Proposed。153项/22格报告与596/44/61均为先前证据，不是本轮新验证。§10已经二次复核收窄为隔离Fake准入的具体审批，不直接批准未定的整版Schema或限定桥接发布。

## 2026-10-21 Codex复核Trae：设计记录整改与下一项准入

负责人要求审查Trae成果并明确安排。Trae本阶段主要交付接手核查、失败清单、ADR-037/038提案和旧Recovery回归报告，没有实现Reflection/第三Runtime。Codex核对并修正：00125a9f/01ec4c2a/04d3c372三份纠错产物实际Provider=fake，不是真实模型；原205份扫描缺抽样清单，不能断言全库无工具失败，本次明确扫描顶层597份发现1份Fake TOOL_FAILED；成功工具空结果也需审查。Reflection A附加输入非零Token/时延，A/B状态/非致命错误仍未定，不由候选表授权实施。保留仓库记录的C暂缓，不激活新任务/协议。

ADR-038已补来源与准入缺口：2.57.0为固定候选而非当日最新；应比较slim/完整依赖；明确框架loop与Session的单次调用/整批预检/Trace/用量/恢复接缝，补单次API、新旧对照目标默认、计划/安全点/版本/历史及回退设计要求。仍Proposed，未安装/实现。当前最新[复核记录](../tasks/V0.3-trae-review-20261021.md)与[Trae下一执行卡](../tasks/V0.3-runtime-admission-trae-20261021.md)：先只读核对固定tag/完成ADR具体矩阵，确认后最小Fake准入，成功后完成正常API/Web/正式对照/恢复成品，随后Judge/人工复核具体ADR和整版验收。

本次实际复跑四文件**153 passed /20.49s**，日志`.uv-cache/codex-trae-review-20261021.log`；严格只读解析/preflight/重算四份旧回归报告逐值一致，22格0退化/0改进，审计`artifacts/trae-review-20261021/saved-regression-audit.json`。扫描清单亦在该目录，不冒充原205筛选复现或全量来源审计。仅修文档/设计，未改业务源码/任务/评分/依赖，不因文档变化重跑完整Web门禁；596/44/61仍为10月20日完整基线。没有真实模型调用、Git提交/推送，所有dirty/untracked保持。

## 2026-10-21 设计交付：接手核查、有来源失败清单、ADR-037（Proposed）与Recovery模板

按[交接入口](trae-20261021.md)顺序先做P0短核查与P1设计交付，未重做Planning。HEAD仍40b57c1，工作区全部既有dirty/untracked保护（本轮前39改/38未跟踪，仅新增本阶段文档），原生任务21题，旧质量/浏览器/日志产物在位。定向Python **153 passed（28.09s）**，未改业务源码/测试/任务/基线，未跑真实模型，无Git提交/推送。

失败清单6项含Fake纠错/构造循环与AIHubMix网络/限流/预算样本；纠错三份Provider实际为Fake，不能称真实模型纠错。原205无TOOL_FAILED的筛选未保存，结论已限制为所列具名样本不足以支持独立Reflection增量假设，不外推全部产物。ADR-037保持Proposed/暂缓；A/B仍只是未定候选，附加提醒有输入成本，并未形成可直接实现的新协议。更正与具体路径见顶部Codex复核和学习交接。

Recovery模板复用现有`recovery_policy`轴与四套`RegressionManifest`/`preflight`/`fixed_config`，实际重跑 **2/8/4/8＝22格，0退化、0改进、各退出0**；报告`artifacts/regression-20261021/regression-reports/`下`0a72fb43-…`、`a48682ad-…`、`a66e57e4-…`、`6bc0e186-…`。旧基线未重录，报告明确这是Fake控制逻辑而非真实模型恢复率。

仓库决策记录：**负责人同日答复选C（证据门槛暂缓）**；新任务/协议未激活，ADR-037保持Proposed/暂缓，不新增reflection轴、ReflectionConfig、REFLECTION_*或契约版本。后续继续第二Runtime设计准入，无需再次选择C/A/B。详见[学习交接](../learning/V0.3-reflection-evidence-20261021.md)。

第二外部Runtime只读调研[ADR-038](../adr/ADR-038-second-external-runtime-selection.md)为Proposed，未批准/安装/实施；固定候选PydanticAI2.57.0、OpenAI Agents SDK0.24.0、Google ADK2.12.0的包元数据已补官方链接。Codex核对PydanticAI已有2.58.0，原固定版本不等于最新；候选支持自定义Model不是本项目契约/恢复已可行的证据。原契约表遗漏单次API等问题已补为设计准入要求，具体版本仍待完整矩阵确认，不视为已定案。

## 2026-10-21 移交Trae：下一主项Reflection设计与Recovery专项

负责人本轮要求做好Trae任务交接。最新[交接入口](trae-20261021.md)、[执行卡](../tasks/V0.3-reflection-recovery-trae-20261021.md)已写明具体顺序，取代10月19日“从零做Planning”的旧指引。HEAD核对仍40b57c1，工作区大量已修改/未跟踪源码、任务和文档保持；当前原生21题。Planning组件及ADR-036两题已完成工程闭环，真实规划效果尚未测，不重复开发或把Fake双方通过当研究收益。

Trae先短核查/保护已有成果；第一主项为有保存Trace/测试来源的失败问题清单、受限Reflection具体Proposed ADR，以及现有Recovery固定实验模板/报告。具体机制尚未决定，不能把一次INVALID_ARGUMENTS纠错改名为Reflection，不能借反思放开禁止/未知工具、重复ID、二次参数错、超时/预算终止，不能注入私有目标。新协议确认后再做两Runtime/工具路径、预算/来源/恢复、正式公平对照和正常API/Web实时/历史/CSV成品；等待决定时继续独立复现/模板/文档。其后沿周计划逐项推进第二外部Runtime选型ADR、独立Judge/人工复核与整版验收，未实施状态如实保留。

本轮仅核对文件/源码入口、已有日志与HTTP摘要存在并编制交接，**没有修改业务代码、运行功能测试/模型或Git提交/推送**。下面596 Python/44 Node/61 Edge及HTTP4次运行/2次新进程恢复为10月20日实际基线，不是本轮重新运行或Trae修改后结果。真实模型一对仅可先提具体待批准方案；新ADR/框架/新任务协议不能由本交接自动Accepted。完整门禁、操作/学习交付、旧版本保护及跨机器缺失产物处理已写入交接。

## 2026-10-20 ADR-036：条件路由与遗漏核验任务闭环

负责人要求接续开发并明确确认“按 ADR-036 实施两题”。新增planning-route-002/omit-003，分别需按验收lane选择政策、避免数量通过后漏掉损耗复核；均为自建开发实例，沿原精确结论/完整无序实际证据评分。新document_route/conditional-eligibility-v1由Fake仅从成功可见文档解析；Runtime/Evaluator/工具及API版本不增加业务或改语义，正常v1.6规划工具、目录/实时资料/输出/正式同full对照/CSV/只GET历史共用。两侧相同条件，计划可选、不要求固定路径/调用次数；当前Fake双方通过、计划侧额外一次声明，不能当真实收益。

原19份任务逐字节哈希保持，总原生任务21。工作前状态/哈希记录在artifacts/conditional-planning-start，全部既有dirty/untracked保护，HEAD仍40b57c1。62项定向Python通过，覆盖32格矩阵、路由/阈值/审批/零损耗/双检查/重命名/私有目标反事实、非法/缺失事实、证据闭包及恢复/正式对照。Edge专项3/3覆盖正常Web显式键盘启动、实时输出与资料、四视口/reduce、游标前缀/刷新只GET和实际四行CSV；已看390计划截图。初次沙箱临时目录权限及测试严格JSON构造/mypy类型问题修复后通过，没有放宽生产校验。

**最终完整门禁退出0：596 Python/93.70s、Ruff/mypy111、四套22格固定回归零退化、旧24格上下文、Web类型/构建、44 Node、audit0、Edge61/61（2.5m）**。日志`.uv-cache/codex-conditional-planning-20261020.log`，质量`artifacts/quality/f31b935b-112f-4241-b26f-33b490e6abc2/`，浏览器`artifacts/playwright/56a6625a-ffe2-4e17-9d67-c2b98a69606d/`。仅随后同步文档；未声称远端CI/Chromium通过，旧警告保留。

实际独立MCP HTTP（仅Fake）：双题×双Runtime4/4；在计划和政策已读处中断，由新Python子进程经正常resume_episode恢复2/2，均7工具/一次声明，无重做；服务已关闭。`artifacts/conditional-planning-http/47f1feae-3818-4aae-86c1-cc98a313d3bb/summary.json`及子进程完整产物可查，不外推真实模型/外部写幂等。

源码顺序、调用链、状态变化、失败、实际结果、网页入口和复现命令见[学习交接](../learning/V0.3-conditional-planning-20261020.md)，[任务卡](../tasks/V0.3-conditional-planning-20261020.md)。真实模型新题/规划效果尚未测，下一步需明确一模型/一题/同预算的探索方案与授权；后续Reflection/第二外部Runtime/Judge和整版验收仍沿周计划具体ADR，不把这两题当研究充分性或整版完成。无Git提交/推送、真实模型调用、数据库/多Agent开发。

## 2026-10-20 Codex验收Trae：修补后组件技术通过

负责人要求验收Trae工程交付。先核对V0.6、交接/执行卡及负责人已确认四项取舍的Accepted ADR-035，HEAD仍40b57c1、大量既有dirty/untracked保持。Trae已实现规划工具/Session、正式planning轴、API/报告与CSV，并非未实施；但原526/57门禁不足以覆盖本次发现的问题。按原ADR最小修复后，当前规划组件主链路**通过技术验收**；真实效果/任务区分度/整版签收未通过或未进行的部分继续保留。

已复现：修改安全点session.plan但保持原Trace/配置，仍可恢复；删掉结果右侧planning并重算hash，后端仍接受。探针`artifacts/planning-review-probe/5b96e42f-327a-4dc5-a3e1-a0910f707d63/`。已补Domain共享计划图校验、恢复对照提议/权限/成功返回/消息/PLAN_UPDATED/最新声明，删除或篡改在新模型调用之前拒绝；结果要求左侧无规划、右侧合法PlanningConfig与合法一致的Runtime来源。整批校验/单次纠错/预算和只读性质不变。

产品闭环补缺：元数据supports_planning由实际任务协议派生、单次更多设置显式开关走已有请求1.6、历史显示保存组件；PLAN_UPDATED进入实际事件前缀，实时和回放只显示已到达声明，回退初始游标不借未来计划。计划状态明确为模型声明，汇总工具开始次数不冒充成功或子目标完成。计划附加消息的实际数量/输入字节与声明来源有记录，MCP里的update_plan标本地组件；project_context本体不改。禁止工具指标不再漏掉被排除的组件尝试；1.8混合规划/记忆任务的回归预检依真实工具档位。

基线公平修正：原planning-branch-001要求无工具的基线也“先用update_plan”，现源版本1.1.0改为工具提供时可自主声明，并承认公开复合条件。事实/答案/评分不变，旧保存Task/产物不改。当前样本仍沿三事实规则、公开登记直接给出引用，只能验证机制，不足以证明有意义的复杂分支规划优化；Fake的facts→decide声明模板不是被测真实模型的规划能力证据。

**最终完整门禁退出0：534 Python/86.17s、Ruff/mypy110、四套22格固定回归零退化、旧24格上下文、Web类型/构建、44 Node、audit0、Edge58/58（2.4m）**。日志`.uv-cache/codex-planning-review-20261020.log`，质量`artifacts/quality/4d8d0097-0058-4322-a302-7d152563fb64/`，浏览器`artifacts/playwright/1f85bc90-67e9-4f9c-9917-04a5f4f5a43a/`。定向21项包含两Runtime/本地MCP/single-serial组合的计划来源/批次恢复与篡改零调用、非法计划批次/最多一次纠错、done不代替提交等。新增单次Edge最初把历史刷新当末帧导致定位超时，按真实游标语义修正测试后专项1/1；实际查看截图再修声明区嵌套排版，最终完整门禁包含该修正，之后仅同步文档。旧大包/Starlette提醒保留；未声称远端CI/Chromium通过。

独立隐藏localhost MCP HTTP：两Runtime正常规划执行2/2；每种在计划已成功、批次搜索待执行时退出，由新的Python子进程经正常resume_episode恢复2/2，均6工具/1次声明，无重做。产物`artifacts/planning-review-http/c3046b2a-532f-410d-a2b3-f12255330ea7/summary.json`；服务已关闭。仅Fake，不能外推真实模型恢复或外部写幂等。本次没有新的真实模型调用，没有Git提交/推送。

详见[问题与验收记录](../tasks/V0.3-planning-review-20261020.md)、[源码交接](../learning/V0.3-planning-challenge-20261019.md)及ADR-035§12。下一建议先定义有区分度的规划任务/对照与明确预算的真实探索方案，不能弱化基线制造收益；后续Reflection/第二框架/Judge等沿周计划逐项推进，未实现项不因本次技术验收而勾销。保持所有已有改动，忽略产物跨机器缺失时说明缺失，不补造同次结果。

## 2026-10-19 ADR-035：Planning Challenge 成品（Accepted，已实施）

负责人确认§10四项取舍后，按 [ADR-035](../adr/ADR-035-planning-challenge.md) 实施规划对照成品。经核对：代码原无任何 planning 概念；现有任务为线性链/三事实规则，无“复合目标须自行拆子目标并跟踪”的结构；真实实验9626ea36左侧失败（重复读6）可由记忆差异解释，**不能归因缺 Planning**——因此首个规划对照固定两侧 `full` 上下文等全部变量，**仅**切换规划组件。

机制=只读声明工具 `update_plan`（经既有 Registry/Validator/Executor、可入 serial 只读批次）：`PlanItem{id,goal,status,depends_on}` 结构严格校验（1–8项、id≤32、goal≤200、同计划内依赖且无环，fail closed）；计划由 Session 保存为 Agent 声明，在 `project_context` 投影**之后**以保留封装 `_agentlabyrinth_plan` 注入，并随 `SessionState` 恢复；计划声明**不**替代环境提交与独立 Evaluator，只有真实 `submit_answer` 成功才算完成。`update_plan` 是**组件工具**，不入任务 `expected_tools`（避免无规划臂被结构性扣分），Evaluator 对 `plan-update-v1` 任务从 proposed/validated 事件中排除该声明以免污染工具指标。

契约新增（旧版本逐字保持、门控新增）：`AgentSpec`1.3+`PlanningConfig`1.0/`plan-update-v1`、`EventType.PLAN_UPDATED`、`SessionState`1.2+`plan`、ToolSet`v1.6.0`（注册 `update_plan`）、Episode`1.6`、Experiment`1.9`+轴 `planning`、`ExperimentCheckpoint`1.4、`ExperimentArtifact`1.6；保留“先派生任务、再选工具版本”，旧 context/请求/任务/产物/冻结计划/安全点/回归不变。新任务 `benchmarks/tool_lab_core/tasks/planning_challenge/planning-branch-001.json`（`task_kind=document_plan`、`planning_protocol=plan-update-v1`），Fake 只按公开可见观察推进一次声明，无私有答案/任务ID硬编码。

**完整门禁退出0：526 Python/91.92s、Ruff/mypy110、Web 类型/构建/Node、Edge57/57（2.5m）**。质量产物 `artifacts/quality/19b0b511-6342-468f-9fe1-c992c207e8f7/`。新增13项规划集成测试（两 Runtime、声明注入不执行、恢复不重做已完成臂、全局Token准入、API接受/拒绝）与2项规划Edge（四视口/键盘/reduce、失败与空Trace隔离、只读历史、CSV含 `planning_algorithm_version`）。期间修复真实缺陷：工具指标分母排除声明、分子未排除导致 `*_validity_rate>1`——已在 Evaluator 同步排除。旧 `test_api`/`test_linked_evidence_tasks` 任务计数守卫与 `linkedEvidence` 单视图计数随第19题更新。源码/调用链/状态/失败/命令见 [学习交接](../learning/V0.3-planning-challenge-20261019.md)。未跑真实模型（另按 ADR-035 §9 单列）；保留全部未提交交付，无Git提交/推送。

## 2026-10-19 移交Trae接续V0.3

负责人明确由Trae承担接下来的任务。当前入口[trae-20261019](trae-20261019.md)，执行卡[V0.3-planning-trae-20261019](../tasks/V0.3-planning-trae-20261019.md)，优先Planning具体ADR与成品，再按[周计划](../tasks/V0.3-week-plan-20261019.md)继续。交接写明本地HEAD40b57c1且大量成果尚未提交、读取顺序、当前契约与源码链路、旧失败/最新真实单对、验收和防退化规则。10月14日旧交接已加新入口，不按旧“多调用全拒绝/记忆轴未实现”执行。Planning协议尚未定案，不把本文视为新核心方案已批准；常规修复/已授权实现不反复确认。保留全部既有dirty/untracked，不能仅从GitHub旧HEAD开始。本次只整理文档/入口并检查链接/格式，未改业务代码、未重复运行功能测试或模型、未提交/推送GitHub；下面513/41/55等为接手前实际基线，Trae修改后须重新记录验证。

## 2026-10-19 ADR-034：检索收口与V0.3周计划

负责人要求继续下一步开发，本周基本完成V0.3。按Accepted ADR-034先修实际搜索问题：新Episode1.5/Experiment1.8为文档任务冻结+id-search-v1执行变体，serial组合为+id-search-v1.serial-v1，选择ToolSetv1.5.0；文档ID精确优先、字面回退，空返回解释规则/直接引用，不做语义搜索。原JSON/目标/评分/预算不改，搜索仍零阅读证据；旧1.4/1.7与保存工具/安全点/计划/回归保持旧行为。本地/MCP共用检索函数，新MCP内部附协议、旧客户端三参数保持，未知协议拒绝。Web复用实际返回节点和字段，没有新增冗余配置项。

定向测试发现Experiment先选工具版本、后派生新任务而误用v1.4，已修复为先派生再选择；9项检索/证据/严格参数/正式预检/离线审查/两Runtime×本地MCP批次恢复测试通过。**完整门禁退出0：513 Python/83.50s、Ruff/mypy109、四套22格固定回归零退化、旧24格上下文、Web类型/构建、41 Node、audit0和Edge55/55（2.3m）**。日志`.uv-cache/codex-document-search-20261019.log`，质量`artifacts/quality/14d4ffb4-7310-4984-9676-11fda3674a02/`，浏览器`artifacts/playwright/7f763fe0-a80a-4d79-8d45-e68316b5a58f/`。门禁后只加强测试截图可见性：初次定位同时匹配可读摘要与折叠JSON而失败，缩至摘要后专项1/1通过（6.6s）；最终日志`.uv-cache/document-search-visual-20261019-final.log`与147b6275-4014-465b-b9ab-196e1f1dbb44浏览器目录，390提示截图已实际查看。业务源码未再改，未声称远端CI或Chromium运行。

独立隐藏localhost MCP HTTP：四查询×新旧两协议8次逐值一致，未知协议明确拒绝；三题×两Runtime Fake共6/6成功，完成后关闭自有服务。产物`artifacts/document-search-http/ecaeb633-5a4d-476a-a12c-16d3ba366615/`。本轮新安全点恢复检查采用服务器函数替身，不扩大声称实际HTTP跨进程恢复。原15份源任务SHA256、三个新事实任务与9份最初smoke保存Task的契约哈希均保持。

**限定免费模型实测完成**：正式实验`9626ea36-60c1-431a-b742-8e0c368982a1`，MiniMax M2.7、基础事实题、LangGraph/local、serial、Seed1/Repeat1、同N1、右M8192；每侧10步/20000累计报告Token阈值/300秒，全局40000。左Episode`97041973-29d1-5712-87f4-9a09332bc579`：TOKEN_BUDGET_EXCEEDED、未提交，8模型/10工具/成功读9/重复6、21146+751=21897报告Token、94243ms。右`8646f053-0ce2-562d-be5c-3379812cec2c`：SUCCESS/ineligible与三份真实证据，5模型/7工具/成功读3/重复0、14202+638=14840Token、65893ms。两侧用量完整，总36737；累计阈值在响应返回后判断，单次响应可能越阈值，未加预算。右第三轮POLICY-B exact_id正确命中、另一次组合搜索仍为空，第四轮直接读两份引用后提交。单对不是稳定收益或检索因果证明；前两次真实失败均保留，无重试/换模型/批量。正式产物在artifacts原目录；摘要和一致性reviewed报告在`artifacts/document-search-real/9626ea36-60c1-431a-b742-8e0c368982a1/`，reviewed不等于所有任务通过。

源码顺序、调用链/状态/失败/实际命令/网页入口见[学习交接](../learning/V0.3-document-search-20261019.md)，实施卡[V0.3-document-search-20261019](../tasks/V0.3-document-search-20261019.md)。本周原始需求全量缺口/时间安排见[周计划](../tasks/V0.3-week-plan-20261019.md)：下一主项为Planning Challenge具体ADR与成品，其后受限Reflection/Recovery及消融模板、第二外部Runtime、独立Judge/人工复核和整版验收。现有确定性Evaluator/离线一致性审查不是Judge，未实现项不能用Memory收尾代替。V0.2/V0.3整版签收独立；不启数据库/GridWorld/多Agent。本轮保留全部既有未提交成果，无Git提交/推送；忽略的artifacts不随Git，其他机器缺失时不能伪造同次结果。

## 2026-10-19 ADR-033：多工具顺序执行成品

负责人明确要求实施多工具、兼容单工具、同步UI，再进行后续优化。按Accepted ADR-033交付ModelConfig1.1/tool_call_mode、ModelResponse1.1/2–8只读调用批次、新请求Episode1.4/Experiment1.7、Session1.1剩余队列。旧None/single/历史/失败重跑保留，BFCL固定单函数协议；原18题源文件未改，新serial运行冻结+serial-v1执行约束变体及来源。整批预检、逐项执行/预算/Trace/安全点；写工具必须单独调用，参数纠错仍最多一次，未知/禁止/重复/第二次参数错不重试，中途失败/超时不执行剩余项。窗口N保持一个assistant及所有匹配返回，复用原投影与记忆。

UI ToolLab默认多工具，可在更多设置切single；对照两侧共用保存模式，历史不跟草稿升级。实时每Call ID独立节点/同轮序号，概览列出本轮全部调用、参数和结果，整行区域两列卡片/窄屏单列，CSV追加tool_call_mode。UI规范1.9同步。新增配置下Provider拒绝响应如有可信用量则记录MODEL_RESPONDED/rejected及用量；缺用量保持未知，不补造上一旧失败的消耗。

最终完整门禁退出0：**504 Python/79.29s、Ruff/mypy108、四套22格回归零退化、旧24格上下文、Web类型/构建、Node40、audit0、Edge54/54（2.2m）**。日志`.uv-cache/codex-tool-batches-20261019-final.log`，质量`artifacts/quality/03d32d15-c7e4-4a38-aa69-c47e7b55e366/`，浏览器`artifacts/playwright/58acbf6f-b2e0-46be-89c7-891746f5def2/`。最后批次卡片布局在完整Edge运行前落盘，之后额外构建`.uv-cache/tool-batches-final-build.log`成功，已查看1440/390最终截图。初次门禁测试缩进未格式化即止，保留旧失败日志，不隐藏。旧大包提醒/Starlette弃用警告仍在，不是检查失败，未运行远端CI。

专项Python36项与Edge6项通过；实际独立HTTP六任务（3题×2Runtime）均4模型/5工具成功，手写Runtime在批次一项已完成/一项待执行处退出后HTTP恢复成功，总计5工具；证据`artifacts/multi-tools-http/fa2e8396-5787-4237-b1d7-4bec58491268/`。本地两Runtime有跨进程恢复，MCP适配两Runtime函数替身恢复，真实HTTP本轮恢复仅手写Runtime，不扩大为所有真实模型恢复或外部写幂等。服务均由本次创建并关闭。

授权免费模型复测已完成新独立正式实验e00a1a74-76d6-407a-a163-27de4b50b2ab，MiniMax M2.7/基础事实题、两侧serial/LangGraph/local、N1/M8192、每侧10步20000报告Token300秒/全局40000。两侧多工具实际执行、完整用量及成对产物保存，均因max_tool_calls_reached失败，无提交：左8模型/10工具/9成功读/重复6/19969报告Token/94208ms；右5模型/10工具/1成功读/重复0/13530Token/64803ms。右多次空关键词搜索，最终直接读引用时预算不足；最后提出的两项未执行。没有重试或换模型，旧single实验1c204cee保持。摘要与reviewed离线报告在`artifacts/multi-tools-real/e00a1a74-76d6-407a-a163-27de4b50b2ab/`，reviewed不等于任务通过。详细逐轮来源及后续检索交互候选见[源码/实验交接](../learning/V0.3-serial-tool-batches-20261019.md)§6—7，不外推记忆收益；未自动扩大真实调用。

工作区全部前期未提交交付保留，未提交/推送GitHub。学习材料包含源码顺序/调用链/状态/失败/命令，不引入新依赖、Planning、摘要模型、数据库或多Agent，不签收整版V0.2/V0.3。

## 2026-10-19 ADR-032三题成品与免费模型失败诊断

负责人明确确认三题后实施：自建基础事实复用、大返回、政策版本干扰Task1.0.0，公开document_rule/fact-unit-rule-v1、仅新题ToolSetv1.4.0/submit说明1.2.0；旧15题SHA-256不变，旧文案/评分/保存版本保持。服务新建时派生版本，两侧同容量；Fake仅解析可见事实/版本/引用和既有记忆包，按公开规则计算，不读私有目标/任务ID，不默认缺失答案。沿用Evaluator v2、Registry/Validator/Executor、完整Trace/Checkpoint。正常Web可检索`memory-`三题，实时资料、派生输出、正式记忆轴、懒读Trace、CSV及历史GET已贯通，无新依赖/业务页。

完整门禁退出0：**468 Python/70.90s、Ruff/mypy107、四套22格固定回归零退化、旧24格上下文、Web类型/构建、Node39、audit0、Edge52/52（2.2m）**。日志`.uv-cache/codex-fact-memory-challenge-20261019.log`；质量`artifacts/quality/a400bb18-d0eb-4ab8-b888-365771d1307a/`，浏览器`artifacts/playwright/c394e2c4-e88c-4aa7-82dd-388234552699/`。新增54项Python覆盖反事实/私有目标隔离、异常事实/证据与运行边界、两Runtime本地/MCP安全点恢复和正式回归/离线审查；Edge4新增用例覆盖三题、四视口/reduce、实际CSV下载和只读历史。独立localhost HTTP六次任务6/6通过、断线按失败保存；实际HTTP恢复未在本轮扩大实测，安全点HTTP适配使用固定服务函数替身。

Fake：两Runtime full/window3三题通过，window1/M256三题均MAX_STEPS无提交；M8192基础/版本各5工具，大返回允许重读后7工具通过。不是实际模型提升。学习交接包含调用链/状态/失败/源码顺序：[V0.3-memory-challenge-20261019](../learning/V0.3-memory-challenge-20261019.md)。

负责人随后允许加入免费模型；目录live且默认MiniMax M2.7在列。固定一题memory-fact-reuse-001、LangGraph、本地、N1/M8192、每侧10步/20000报告Token/300秒、全局40000。冻结实验1c204cee-fe2b-4ee8-81ae-e2f18cd3ec62；左587cba77-fad2-5d4e-85c5-fdf8cc560dde第三轮因**provider_error: MULTIPLE_TOOL_CALLS**终止，已执行2工具/成功读1文档，耗时30671ms；已返回两轮合计4497报告Token，失败轮用量未知，不能称完整总量。右侧未启动，无正式完整Experiment结果。源码已发送parallel_tool_calls=false；该返回不符合当前每轮一个工具的约束，不是429/额度耗尽证据，也不是记忆失效证据。全局预算完整记账检查阻止继续；没有重试/换模型/丢弃多余调用/放宽权限。

正常Episode和冻结计划在artifacts根；摘要`artifacts/memory-challenge-real/1c204cee-fe2b-4ee8-81ae-e2f18cd3ec62/summary.json`。完整对照离线审查因结果缺失明确rejected；内联辅助摘要曾误传helper参数，已纯离线改用保存events生成，未重跑模型。错误与未运行侧均保留，不补造成功率/记忆收益。后续先按该兼容性失败提具体方案，若改变单行动/错误恢复语义先走ADR；暂不启动Planning、摘要/数据库/多Agent或更多真实调用。

本轮业务代码在完整门禁后未改，仅文档/授权实测/只读产物核验。全部前期未提交交付保留，未提交/推送GitHub，V0.2/V0.3整版仍待负责人验收。忽略产物不随Git，其他机器缺文件不得伪造同次结果。

## 2026-10-18 执行下一步A：离线记忆诊断已交付

负责人同意按规划执行，Codex先完成A。新增`scripts/review_memory.py`：明确指定保存Experiment UUID或两个Episode UUID，离线复用Artifact严格JSON解析、content_hash、CheckpointStore/冻结计划verify、fixed_config及现有成对固定变量校验；逐侧核对保存配置/任务/Seed矩阵/结果，并关联每次请求此前成功返回的记忆来源。输出独立Markdown表格和JSON，不覆盖旧目录/输入。无完整Trace、缺诊断或未报告用量保持未知；跳过只报告原Trace已有条数，不补造逐条清单或因果解释。失败退出2且尽可能保留中性拒绝报告，不回显Pydantic原始输入。诊断JSON不是新公开Episode/Experiment协议。

原`scripts/episodic_memory_ablation.py`复用新的按时间扫描成功阅读函数，减少重复逻辑并避免先收集全体提议可能关联未来事件的隐患；原报告列/单对运行预算、恢复/评分/API/Web/算法均不变。完整调用链、命令、状态/失败处理、实际示例和源码阅读见[学习交接](../learning/V0.3-offline-memory-review-20261018.md)。README、AGENTS、下一步计划同步。

验证：初次静态检查长行/类型错误修复；首轮21相关测试19通过/2因测试本身JSON严格读取和WindowsGBK失败，修复并补旧上下文/小容量/非法Schema后23项通过（6.29s）。新19项验证离线零网络/零模型/工具调用、输入哈希不变、拒绝覆盖、错误ID/hash、重算哈希后的预算混变量、未来来源、坏计数/事件、正式矩阵/结果/配置错配、缺Trace/诊断及未知用量。**最终完整门禁退出0**：414 Python/62.36s、Ruff/mypy106、四套22格回归零退化、旧24格上下文、Web类型/构建、Node39、audit0和Edge48/48（1.9m）。日志`.uv-cache/codex-offline-memory-review-20261018.log`，质量`artifacts/quality/19802c55-7258-44c5-8638-9e052555381a/`，浏览器`artifacts/playwright/b5e9747b-df19-48a1-bd2a-5239e1b96875/`。门禁后只同步说明，源码未再修改；不冒称远端CI/Chromium运行。

实际只读运行：原2026-10-14真实CLI对审查报告`artifacts/memory-reviews/cd07d3ed-ef40-46cd-bde0-e687489c3271/`，核对两侧通过/工具8与5/重复3与0；旧正式Fake实验报告`artifacts/memory-reviews/ea45329f-650f-49d9-8684-6a903921440a/`，左未通过/5工具/重复1，右通过/3工具/重复0。Markdown/JSON已阅读，来源与独立/正式身份正确；不属于新真实模型实验，不外推收益。忽略产物不随Git同步，其他机器缺失时不可伪造。

下一步按[开发计划B](../tasks/V0.3-next-development-20261018.md)先设计少量跨阶段复用、超大返回/静态版本干扰压力任务并形成具体ADR，确认后实现正式产品入口；不先改算法或引入数据库/多Agent/真实批量。V0.2/V0.3整版签收仍独立。全部先前未提交内容保留，本轮无Git提交/推送。

## 2026-10-18 下一步开发规划（仅计划）

负责人要求规划下一步。[执行计划](../tasks/V0.3-next-development-20261018.md)提出：A先复用保存产物/来源校验做离线记忆诊断报告（零模型/工具调用）；B按具体ADR设计跨阶段复用、超大返回与静态版本干扰的少量Memory Challenge场景；C另行确定一模型/一任务，经正式同窗口入口补一次真实小样本；D依据实际失败决定继续记忆、Planning或可靠性修复。已有真实单对两侧均通过，未证明需要新算法；不把Fake容量失败当真实模型结论，不保证提升比例。规划未批准新协议/任务评分版本、批量真实实验、数据库或多Agent；本轮仅新增计划/更新交接，没有代码、模型调用、测试重跑或Git提交。上一节开发交付与395/39/48门禁仍属上一任务证据，全部未提交修改保留。

## 2026-10-18 V0.3 记忆实验结果的执行差异审查

负责人要求接续项目开发。本轮沿ADR-030/031收尾现有记忆产品的可解释性：保存的 `memory_ablation` 实验增加“记忆有没有减少重复工作？”面板，按任务/Seed/重复选择后，显式GET两侧Episode，直接对比评测结论、工具调用、成功阅读/重复阅读及实际文档明细。不自动批量读全部Trace，不重新运行模型，不改变保存配置、URL或草稿；旧轴、默认full、公开Schema、评分、CSV和记忆算法均不变。

调用链：`App`已保存实验 → 新 `MemoryPairReview` → `apiClient.readEpisode`校验Schema与所请求ID → `flowFrames.savedDocumentReads`复用`documentEvidence`。缺起止Trace阅读统计为未知，不补零；404/错误ID单侧拒绝，另一侧保留；显式重试清旧数据。换任务、实验或离页卸载并abort，旧响应不回填。阅读统计不借最终快照、未返回的工具提议或观察者预览；重复阅读不自动判为无效工作或稳定收益。

实际检查：首次Node在沙箱报spawn EPERM，提升本机测试权限后39/39；首轮专项Edge1/2因测试把仅提议的最后读取误计，核对实际Trace后只修预期，保留失败记录。修正后专项2/2（12.6s）；四视口/Enter/reduce、单侧404/重试、ID错配、空Trace及延迟切换通过，实际查看1440和390截图。**最终完整门禁退出0**：Python395/67.59s，Ruff/mypy104，四套22格回归零退化，旧24格上下文，Web类型/构建、Node39、audit0及Edge48/48（2.0m）。日志 `.uv-cache/codex-memory-result-review-20261018.log`，质量 `artifacts/quality/38ace1f8-14d8-48aa-b66a-cf753a8f90a6/`，浏览器 `artifacts/playwright/ce6d5326-9626-49bb-860c-0b4ffa4d28af/`。完整构建包含最后的错误状态样式，未对源码再作门禁后的修改。

范围/逐项结果/使用入口见[任务卡](../tasks/V0.3-memory-result-review-20261018.md)，调用链及状态/失败处理见[学习交接](../learning/V0.3-memory-ablation-20261015.md)新增章节。仅Fake，未进行新真实模型探索、原系统复现或远端CI，不签收整版。接手HEAD40b57c1且工作区干净；本轮代码/文档保留本地，没有Git提交/推送，不延用上次一次性授权。下一核心能力仍先明确实际失败与具体ADR，未来多Agent研究保持独立。

## 2026-10-16 本次研究文档GitHub同步授权

负责人明确要求提交最新成果。本轮范围是VirT-Lab完整精读、任务覆盖与组合研究贡献讨论，以及AGENTS/需求/长期研究参考/交接共5份文档；业务代码保持上一提交34fe06e，无新增功能、模型调用或原系统复现。此前本地保留限制对本次由明确授权取代，后续仍不自动提交。检查本地文档链接、diff格式、敏感信息及远端分歧后提交并推送；不包含.env、缓存、原始PDF及artifacts中提取/渲染/实验数据。完成状态以Git历史与远端HEAD核对为准，不提前声称成功；纯文档不重跑无关代码门禁。

## 2026-10-15 VirT-Lab精读结论同步未来开发文档

最终轮收尾：精读笔记§15—16完成§4—6四类评估、消融/规模结果、SD/SE与独立实验单位、任务完成比例/成功率/时长区分、用户研究与讨论及全篇开发参考总结。重读第12—20页，视觉核对第15页消融与第18页图11（图10/表3先前已核对）；不把3次重复、小均值差或误差条重叠直接当显著性判断，保留超过2000步的截止口径与源码/原始数据待核实项。笔记顶部、旧下一轮安排和研究入口同步为“本轮v1主体精读完成”，不等于原系统复现/创新确认。未来按具体研究问题回查或另行复现，当前无实现、真实模型调用或GitHub提交。文档链接/格式检查通过，未重跑无关代码门禁。

第二轮精读已完成：笔记§14新增§3.2/3.3.1/4.1/4.2角色、FAISS记忆、二维矩阵/区域分割/连接关系、可见信息和任务评分，交叉核对第14/18/25页，并实际查看第7/8页图4/5。区分人设/知识/权限；不补造top-k或全队共享记忆；不把分割树当通路图；LLM生成成功函数再执行不等于每步LLM打分。原文未充分给出的技能强制约束、过滤/失效/生成函数隔离继续标待核实。新增6类未来检查建议，未实现；研究入口已同步，下一轮精读实验公平性与消融证据。纯文档，链接/格式验证，无代码门禁、系统复现、模型调用或GitHub提交。

同日补研究方法论：负责人倾向组合现有优化方法，并对创新程度保留判断。精读笔记§13及研究入口已记录问题/方法/基线区别、工程集成与组合贡献边界、组件/直接组合/新增机制及最接近已有工作的公平比较。查核MAST v3和Evolving Orchestration v2作为失败分类/已有动态编排参考，不声称完成新颖性检索；不因改名或优于弱基线宣称创新，不承诺毕业/发表。纯文档，无具体方法定案或实现授权。

同日负责人进一步讨论毕业论文/答辩的任务覆盖。已在精读笔记§12和长期研究入口记录：一个代表案例可细讲，证据需与方法主张匹配的多样实例/重复/消融，区分环境、任务族、实例和随机重复；候选“一个世界+2—3类相关机制”不是院校标准或已批准样本矩阵。核对VirT-Lab的20次模拟、3地图尺寸×2—5Agent/每配置3次，及Collab-Overcooked正式来源30任务/13模型；保留开发/测试隔离、失败与泛化范围边界。仅研究文档，无实现、实验或GitHub提交。

负责人要求协助精读，并将结论持续写入未来多Agent开发参考。[固定v1精读笔记](../research/virt-lab-close-reading-2510.08242v1.md)已新增：29页PDF版本/SHA-256、事实/解读/建议/待核实分层、本轮§3.3.2/Algorithm 1/A.2/A.5及A.3/A.4交叉阅读、原实验数字和局限、未来检查场景。第9/10/16/25/26页关键图表/算法做过页面视觉核对；中间文本与渲染仅在被忽略artifacts/paper-reading/，原PDF不入库。

核心结论：借鉴角色/环境/事件/通信分层与地图/时间线/动作/对话的联动；事件复制是否导致共享效果重复属于待核实而非已确认源码bug。未来需明确一次提交与多方通知、同刻排序/过期状态/资源冲突、世界时间/墙钟/动画分离。A.2提示抑制交流、A.5允许近似对象匹配，会影响通信与能力归因；需冻结提示词并保留原始决策/解析/执行、全部辅助调用成本。简单地图关闭通信仍完成、无记忆主要降低效率，不能外推协作或记忆普遍收益。

同步AGENTS、需求§0.5及V0.6阅读入口、多Agent研究方向顶部。未来路径是具体规则/观察/预算/评分→固定基线→实际失败→相关方法检索和消融→产品闭环，不提前定引擎/数据库/新Schema或创新点。下一轮精读角色/FAISS记忆、世界矩阵/区域图、任务与观察范围；原作者系统未安装/复现，未声称运行结果。纯研究文档，检查链接、来源页码和diff格式，不重复代码门禁；无新模型调用/多Agent代码。

上一轮已授权GitHub提交34fe06e确实推送并与origin/main核对一致（连接直连失败后临时沿用系统本机代理成功，未修改全局Git配置）。本轮仅新增/同步研究文档，保留本地，不延用为自动提交授权；不改变V0.3范围或整版验收状态。

## 2026-10-15 本次GitHub提交授权

负责人明确要求先提交GitHub，再开展其所读论文的精读。本次授权提交/推送已验收的本地源码、任务、测试、研究/交接文档及狐狸品牌资源；此前禁止自动提交仍作为后续默认，不把本次授权延长为自动发布。最终完整门禁证据沿下节395 Python/38 Node/47 Edge，提交前检查远端差异、diff格式与敏感数据；本机.env、缓存及实验产物不纳入Git。提交与推送完成状态以Git提交历史和远端校验为准，本文不提前声称成功。论文范围待负责人提供标题/链接/PDF，不从旧讨论猜测。

## 2026-10-15 Codex验收Trae并接管主要技术开发

负责人要求复核Trae已完成内容并由Codex承担后续主要技术开发。本轮沿ADR-031验收已经落地的同窗口记忆正式Experiment，不转而实施多Agent或其他新核心协议。Trae主流程可用，但Codex复现并修复三类校验缺口：①冻结计划verify未重复检查模型/Prompt/工具/预算等固定变量，改后重算plan_hash也曾通过；现共享记忆校验比较除id/name/context_policy外的完整Agent配置。②请求已有双向版本门，但计划1.3/结果1.5尚可挂旧轴；补后端与Web的反向拒绝，仅新轴使用新版本。③新轴结果漏查recovery_policy，Web漏查runtime_version，两侧同时缺字段也曾被视为一致；现必需且匹配Runtime来源、校验策略与恢复标签一致，并让null/数组臂配置产生正常ValidationError，而不是拖垮历史看板。

两项新增失败测试在原实现实测均DID NOT RAISE，修复后相关Python33项通过；后续追加损坏配置/无效Runtime来源拒绝。首次普通权限运行因测试父目录缺失/沙箱缓存权限未能执行，建隔离目录并使用本机测试权限后才复现；保留失败记录。完整门禁首轮退出0：395 Python/58.73s、mypy104、四套22格回归零退化、旧24格上下文、Node38、Edge47/47（1.9m）、audit0，日志.uv-cache/codex-memory-review-20261015.log，产物artifacts/quality/8cc7224a-fb6a-4419-ae37-ee8cd7edd79a/。补完最后的损坏配置/Runtime来源检查后，**最终代码再次完整门禁退出0**：395 Python/60.48s（含18项新轴用例）、Node38/38、完整Edge47/47（1.9m），格式/lint/mypy104、四套22格回归/旧24格上下文、构建及audit0均通过。最终日志.uv-cache/codex-memory-review-final-20261015.log，产物artifacts/quality/9c8f141b-0ec7-4930-a42e-0b4dd63b45b6/。本机Edge通道，不冒称未运行的Chromium/远端CI通过。

浏览器覆盖新轴显式运行、非法N/M、CSV既有列、刷新/前后导航仅GET、草稿隔离和Trace记忆来源。四视口自动检查通过；Codex实际查看首轮1440/1280/768/390结果截图（playwright/81946a66-7fc2-4a73-a0d6-5768a450a927/），无整体溢出。只是自动化及截图技术复核，不替代现场投影/操作手感签收。本轮没有新真实模型推理；既有MiniMax单对CLI证据不伪装为新正式Experiment或稳定收益。

[源码阅读/调用链/失败路径/防错交接](../learning/V0.3-memory-ablation-20261015.md)已新增，README、AGENTS、需求§0.5同步。ADR-031与任务卡顶部改为Implemented/待负责人验收，明确已实现事实，不自行标Accepted或签收整版V0.2/V0.3。下一步先负责人查看当前入口；新的V0.3能力由实际失败驱动并另提具体ADR，不自动引入摘要模型/数据库/多Agent。接手时8000/5173/8765没有监听服务；本轮测试仅启动独立Fake服务，不主动改正常服务配置。HEAD998ff6e与全部先前未提交/未跟踪交付保留，没有GitHub提交/推送。

## 2026-10-15 按修订ADR-031实施同窗口记忆对照（本地完成，成品入口）

负责人确认“按修订 ADR-031 开始开发”，按指定顺序完成后端→网页→验收。本轮新增**独立轴**`memory_ablation`，不改旧三轴与旧产物：请求`CreateExperimentRequest`1.6、冻结计划`ExperimentCheckpoint`1.3、结果`ExperimentArtifact`1.5，均为**仅新轴**使用的版本；旧默认请求仍1.5、单次运行仍默认full。

后端：`ComparisonAxis`加`memory_ablation`；`_validate_memory_agents`+`_require_memory_arm_pair`严格校验两侧均recent、同N、左无记忆(1.0/`tool-round-window-v1`)、右有记忆(1.1/`tool-round-window-memory-v1`)、同backend/strategy/recovery_policy，创建/冻结`verify()`/恢复都执行；`ExperimentArtifact.token_budget_revision`加1.5分支(同backend/strategy、同N、左无右有、挽救指标全空、`recovered is False`)。`prepare_experiment`新分支服务端确定性派生左=同N无记忆、右=请求记忆策略，两侧除`context_policy`记忆子版本外完全一致(单变量哈希对比通过)。`run_experiment`臂标签左`Recent Window`/右`Recent Window + Memory`。请求1.6仅允许新轴，显式记忆与全局预算共享版本门同步加入(1.6)；旧轴接受规则不变。回归`preflight`按新轴派生两侧策略(左无记忆/右记忆、Runtime strategy按轴推导)，`fixed_config`/`comparison_key`无需改动；`ExperimentDashboard`/`ExperimentCharts`新轴标签就位，读保存轴不从草稿推断。

Web：对照轴下拉加“工具记忆：相同近期窗口 vs 相同窗口+记忆”，选中后显示**相同窗口轮次N(1–100，两侧共用)**与**右侧记忆上限M(256–32768字节)**，复用`.context-settings`/数字/折叠帮助，不缩字体/不重置草稿；默认演示N1/M8192。结果区显示保存的两臂策略、成对结论标签(有/无记忆均通过等)、育人解读块(“左右窗口相同，仅记忆配置变化”“字节不是Token”)，刷新/前进/后退只GET。CSV列序/列集不变，仅填充既有`context_*`列(左`memory_max_bytes`空、右=M)。Trace穿透沿用`McpFlowReplay`请求诊断(记忆条数/字节/跳过/源call_id)与`DocumentEvidence`阅读计数。`apiContracts.ts`加轴值与1.5 refine。

实际Fake结果(机制事实，非成功率)：原生`order-status-007`+N1/M8192，handwritten与langgraph两Runtime均左`MAX_STEPS`失败、右`SUCCESS`通过；N5/M32768两侧均通过；N1/M256两侧均失败(容量不足右侧也失败)。同一受控结果只对该任务/N/M成立，其他组合不套用。

验收：新增`tests/integration/test_memory_ablation_experiment.py`(16项，计划/校验/双Runtime执行/保存回读/恢复不重跑左/失败重跑沿用原策略/全局Token拒绝/API接受与错配拒绝)、`apps/web/tests/apiContracts.test.mjs`新轴结果校验、`apps/web/e2e/memoryAblation.spec.ts`(配置/非法拒绝/只读/草稿隔离/CSV/URL GET/Trace穿透/四视口)。完整门禁`uv --cache-dir .uv-cache run --locked python -m scripts.check`设`AGENTLABYRINTH_E2E_CHANNEL=msedge`**退出0**：Python393项(61.72s)、Node38/38、Edge47/47(1.9m)，产物`artifacts/quality/409becda-bca8-452a-a47f-2c0ac041ec4e`。首轮因新增测试文件`ruff format`/`mypy`未过而失败，修正后重跑通过，失败历史不隐匿。默认chromium未装仍属环境限制。

本轮仅Fake端到端；无新真实模型调用、不批量Seed×Repeat。ADR-031仍标**Proposed**(未自标Accepted，实施记录见其§12)，不签收V0.2/V0.3整版；不新增数据库/摘要/多Agent；HEAD998ff6e及全部未提交/未跟踪改动保留，不提交/推送GitHub。

## 2026-10-14 Codex复核Trae交付与下一步（方案仍待批准）

负责人询问Trae完成后下一步。已核对交付任务、ADR-031、实施方案和实际源码调用点，并读取最终完整门禁日志：376 Python（62.20s）、mypy103、四套22格回归零退化、Node37、Edge46/46（1.9m）、Quality gate passed；首轮日志为376/92.27s及Chromium缺二进制导致46项launch失败，保留首轮失败。此为复核Trae记录，本轮没有重新运行这些测试或新真实模型调用。

现有记忆收尾交付有完整门禁证据；新memory_ablation尚未实现，ComparisonAxis仍原三轴。独立新轴/请求1.6/计划1.3/结果1.5方向可以进入负责人审核，Codex先修订Proposed ADR-031和对应实施卡：补全局预算/显式context共享版本门、严格创建/恢复固定变量、scripts.run_regression.preflight的左右策略/Runtime推导以及Dashboard/Charts标签；修正recovered必须False（不是None）、旧轴允许相同已有记忆、固定Fake结果只适用于特定任务/N/M，说明单对随机性，不声明已证明因果收益。

下一步建议批准**修订后的ADR-031**，然后实施完整API/Application/Web同窗口记忆对照：冻结/恢复/重跑/版本拒绝/回归/历史只读/CSV一起交付，默认演示N1/M8192，单次仍默认full；先Fake端到端与完整门禁，已有真实探索只读核验，不扩大真实批量。当前状态仍Proposed；按AGENTS与需求§0.3/§29，负责人确认具体新公开协议方案后才实施，本轮不自行Accepted。仅文档修订，链接/路径与diff检查，无业务代码/GitHub提交，多Agent仍未来研究。

## 2026-10-14 Trae 接手复核与同窗口记忆对照方案（最新，本地完成）

Trae按[交接入口](trae-20261014.md)复核现有V0.3单任务工具记忆/阅读统计/历史隔离与恢复，逐项核对投影(全历史先校验再投影、仅窗口外成功result整条准入、含实际call来源、UTF-8整包预算、超大整条跳过、256字节不足仍失败、保留字段拒绝)、两Runtime恢复一致性、原生007与三跨文档任务证据评分、资料readCount仅实际匹配正文才计读(空文档/失败/未返回/预览不计、重复成功读同ID才计重复)、草稿/历史/只GET隔离、full与旧恢复/Runtime轴、CLI逐侧保存回读与禁止覆盖。未复现需改动已批准算法的缺陷，故本轮不改算法、不动旧1.0序列化/哈希与旧产物。

直接相关全通过：Python77项(39.80s)、CLI六格Fake(window失败/memory通过)、Web类型、Node37/37、构建298模块(JS gzip164.71KB/CSS14.05KB)、Edge相关7/7(22.9s)。完整门禁`uv --cache-dir .uv-cache run --locked python -m scripts.check`首轮Python376(92.27s)、ruff/mypy103文件、四套回归零退化、旧24格上下文、Type/Build/Node/audit通过；**首轮E2E因本机缺默认chromium-1243二进制出现46项launch失败**(环境限制，非代码回归)。设`AGENTLABYRINTH_E2E_CHANNEL=msedge`后重跑同一完整命令**退出0**，最终Python376(62.20s)，完整Edge46/46(1.9m)，Python/回归产物artifacts/quality/373d8d62-98d3-43d5-b596-7262ad32cbbf/。失败日志.uv-cache/full-gate-trae.log保留，最终.uv-cache/full-gate-trae-msedge.log；不跳过后宣称通过，默认chromium未装如实记录。

随后交付[Proposed ADR-031](../adr/ADR-031-same-window-memory-ablation.md)与[实施/界面信息设计](../tasks/V0.3-memory-ablation-20261014.md)：新增**独立轴**`memory_ablation`(左=同N轮近期窗口无记忆，右=同N轮+记忆M字节)，请求1.6/冻结计划1.3/结果1.5，复用`context_policy`承载右侧记忆策略、服务端确定性派生左侧以结构性保证“仅记忆不同”。旧三轴语义/版本规则与哈希保持，共享验证器须增加新分支；`fixed_config`/`comparison_key`可不改，但回归preflight需适配（Codex复核后修订）。不改单次默认full，不实施新公开协议，待负责人确认。多Agent仍仅研究背景，不启动；不提交/推送GitHub；不签收V0.2/V0.3整版。

## 2026-10-14 Codex → Trae 交接（当前下一任务）

负责人明确选择继续V0.3：记忆功能收尾与同窗口对照方案。[交接入口](trae-20261014.md)、[具体任务卡](../tasks/V0.3-memory-closeout-trae-20261014.md)已创建，AGENTS与需求§0.5同步。Trae先复核/最小兼容修复已实现单任务记忆/阅读统计/历史与恢复，重新记录完整门禁；再交固定同N轮窗口无/有记忆的Proposed ADR、Web/API信息设计、版本/恢复/指纹/CSV兼容与测试计划。现有Web轴仍左full，不能只改标签或放宽旧校验冒充纯记忆消融；新公开协议实现待具体ADR确认，不自行Accepted。

本轮仅整理交接，没有新功能修改、质量门禁、真实模型调用或向外部Trae发送消息；文档链接/路径与diff已检查。此前测试和真实数字作为带日期证据保留，不标作Trae复核已通过。HEAD998ff6e及全部既有未提交/未跟踪内容保留，不提交GitHub。正常服务沿下方最近记录，接手需重新核对，不按旧PID直接终止进程。未来自己的多Agent世界参考AgentWorld，仍是研究背景而非此次执行任务。

**负责人最新澄清：在AgentLabyrinth自己的平台中设计多Agent协作世界，参考AgentWorld的世界/角色/任务设计方法。** Codex此前将其理解成优先接入原环境开展研究，现已纠正；外部Adapter/复现仅候选，不是主路线决定，原自建场景也未被负责人否定。参考能力/资源/观察差异、真实任务依赖、高层动作、明确通信和可验证评分；本平台自定世界与任务，按实际事件实时可视化。引擎、任务题材、调度协议和方法创新尚待选定，不默认复制完整MMORPG或强制round-robin。研究记录顶部已注明最新优先级；未安装/复现、不启动多Agent/新服务/Schema/真实批量，当前V0.3与不提交GitHub约束保持。

## 2026-10-14 多Agent近期进展补充（仅调研，非开发授权）

负责人读Collab-Overcooked后询问当前进展与开题参考。已核对该作2025首发/EMNLP2025，补2025–2026原始论文：Evolving Orchestration（NeurIPS2025动态RL协调）、Scaling Agent Systems v3（260配置/6基准，架构收益依任务）、MASBench（2026-10-03局部观察Protocol/Memory/Routing）、RCR-Router v4（角色/预算记忆路由）、SyncPlan（2026-08同步/过期重规划）、AgentWorld（2026-09长链角色/过程）、CooperBench与When Messages Go Wrong（2026-10-11通信故障/已有执行和证据保护）。部分为预印本，未跑外部实现，不把跨基准数字当能力提升或行业均值。

[研究记录文末补充](../research/multi-agent-sandbox-direction-20261013.md)明确：原“事件触发/定向消息+记忆”是已有相关工作的宽泛基线，不能直接称开题创新。候选缩窄到局部观察/通信预算下，任务依赖影响的消息选择与自适应恢复；须对照已有路由/同步/证据保护做新颖性检索和失败验证。三角色二维配送仍为未来载体；当前V0.3、Git与实现范围不变，无新代码/模型调用/外部复现，不启动多Agent。

## 2026-10-14 同窗口记忆真实验证与阅读统计（最新，本地完成）

负责人授权接续开发。沿用ADR-030，新增显式CLI --model（默认仍为6格Fake），经正式EpisodeService/Checkpoint Runner仅执行一模型一任务两侧；每侧保存后回读/校验哈希，除context_policy外固定Agent、Task和RunConfig，报告原子写入，旧目录拒绝覆盖，Provider报错保存部分报告并停止，不换模型或扩大重复。

MiniMax M2.7、LangGraph、本地工具、退货Task1.3.0/ToolSetv1.3.0、Seed1、window1、10步/20000Token/300秒；memory侧8192字节。真实两侧均通过approved+3条完整证据：window eb1fe5b8-a120-4e48-ba55-f411385e2e73为8模型/8工具、成功读6次/重复3、14992输入+774输出=15766报告Token、95849ms；memory 297d40c4-24d5-4ebb-bb35-c4b86efb14f6为5/5、成功读3/重复0、9962+355=10317Token、65122ms。窗口侧确实将ENTRY/POLICY/DECISION各读两遍；记忆侧一次读完。最后memory请求3条实际来源/1141字节/无跳过，早期搜索、ENTRY与POLICY随投影送入，DECISION在近期轮次内。报告artifacts/episodic-memory/real-pair-20261014/memory-pair.json与根目录完整Episode已只读交叉核对，不改旧产物。

本对调用少37.5%、报告Token少34.56%、耗时少32.06%，仅单对探索；不是稳定优化率、成功率提升或实付费用，固定顺序/模型随机性/网络影响保留。现有full仍默认，当前没有实测必要引入摘要/数据库；下一步同窗口开关的Web产品对照需先ADR再开协议，不自行加轴或批量Seed×Repeat。

资料侧栏复用documentEvidence增加只读readCount，总成功阅读/重复次数随当前Trace前缀变化；实际匹配正文返回才计读，空文档、失败、开始未返回、最终快照/观察者预览不增加。重复并不自动代表无用或遗忘，不据次数推导评分。源码、复现、失败及全部实际结果见[任务交接](../tasks/V0.3-memory-real-pair-20261014.md)和[学习说明](../learning/V0.3-episodic-memory-20261014.md)。

最终格式/lint/mypy通过；相关Python63项（20.07s，含新增4探针用例），原6格Fake再跑通过（14b1f3e2-bd38-4ec8-8a37-1feebe462fd5/）；Web类型、Node37/37、298模块构建通过（JS gzip164.71KB/CSS14.05KB，原Zod/分包提示保留）。相关Edge7/7（25.3s，7acfe6f3-8673-44e0-bd6b-3f198d5668e3/）通过；真实两记录1440/390只读浏览器核对零POST、无整体溢出，桌面/390截图已查看（报告下screenshots/）。首次pytest临时目录/Node子进程受沙箱限制未运行，初次证据顺序测试假设修正，浏览器端口占用未跑后核对并暂停自有服务再验证；不清除这些失败历史。本轮不声称新全套Python/46项Edge或远端CI通过，原门禁记录仍保留。

正常服务恢复：API启动器10852/监听30452、Web8892，MCP7048保持，日志artifacts/memory-real-product-20261014/；5173 GET200、目录live、28题/5模型含Fake。可只读打开两份Episode并把动画进度移至结尾查看差异，已保存运行不是新的实时请求。所有已有改动保留，无GitHub提交/推送，不签收整版V0.2/V0.3。以下“记忆真实未测”为前一交付时历史状态，由本节实测替代。

## 2026-10-14 单次运行配置布局收口（本地完成）

负责人指出截图中任务列表下方空白与右侧参数过长，授权参考成熟配置界面并修改。根因：左侧任务目录max-height，右侧高级配置展开拉长同一Grid行。已把高级参数移为两栏下方独立整行，按工具/容错、上下文/记忆、运行预算分组；右侧保持模型、Runtime、草稿摘要和启动按钮。数字并排、长说明原生details；summary样式改为直接子选择器，防止嵌套帮助继承顶层加减号。仅UI，无API/策略/预算/评分变化，现有控件ID/处理保持。

[参考与决定](../research/compact-run-settings-20261014.md)、[源码/实际验证/防错交接](../tasks/compact-run-settings-20261014.md)及UI规范1.8已更新。类型、生产构建与Node37通过；完整Edge46/46（1.8m）通过，目录814cd12a-7340-43c7-bf21-d77fa0cde39b/。截图复查后补卡片内容高度和数字底部对齐，最终构建与相关5/5（20.6s）通过，目录94950385-246d-4865-9187-deacf781fc3e/。1440/1280/768/640/390无整体溢出，桌面/390截图实际查看；640等效窄视口不是实际200%缩放签收。失败工具不执行、显式参数落盘、历史只GET与草稿隔离仍通过。298模块、JS gzip164.59KB/CSS14.05KB，原有构建提示保留，无新依赖；纯UI不重复无关Python全套。

正常API启动器19036/监听28348、Web9624已恢复，MCP7048保持（8000/5173/8765）。5173 GET200、目录live、28题/5模型含Fake，日志artifacts/compact-settings-product-20261014/。刷新单次工作区即可查看右侧紧凑操作台与下方三组更多设置；没有新真实模型推理或GitHub提交，保留既有全部改动。Fake候选模型仅用于布局展示，不能当作新模型实测通过。先前服务PID由本节替代，上一记忆切片真实验证待办仍保留。

## 2026-10-14 V0.3受限单任务工具记忆（本地完成，真实未测）

负责人明确选择继续单Agent上下文/记忆，不提前二维多Agent。Accepted ADR-030和任务卡V0.3-episodic-memory-20261014已落盘；ContextPolicy子版本1.1采用固定window-memory算法、256–32768字节完整返回记忆。仅窗口外成功result反馈入记忆，附call_id/工具名；error/未返回/私有目标/最终快照不读取，超大整条跳过。只修改Provider投影，完整Session/Trace/Checkpoint、原预算/工具校验/评分不变；旧1.0字段形状和哈希保留。

已接单次及上下文对照Web配置、当前模型节点记忆诊断、保存来源和CSV算法/限额列；窗口+memory与full比较不能单独归因记忆，另有正式Runner的六格同窗口Fake消融。[学习交接](../learning/V0.3-episodic-memory-20261014.md)和[实际结果/待办](../tasks/V0.3-episodic-memory-20261014.md)已完成。

最终六格Fake目录artifacts/episodic-memory/d37e3ebf-b79f-4867-98fb-29ccae3abe3a/：两Runtime均full与memory成功3模型/3工具，window1失败6模型/5工具；累计消息字节2984/2883/5562，memory最后279字节、来源call_search_1。不是实际Token或模型成功率结论。三跨文档场景×两Runtime在窗口1+8192字节记忆下均保全实际读取证据；连同API和指纹22项通过，256字节容量不足仍失败、不退回full。

共享检查的Python372/56.47s、mypy102、格式/lint、四套22格回归零退化、旧24格上下文、Web类型/构建/Node37及audit0漏洞通过，Python产物artifacts/quality/48fc6e1f-6b5f-4bb8-9b6c-f3b566645f4b/。首轮Edge42/44：旧Trace标签改变和新测试误点未来节点；恢复旧入口名，测试按已保存frame推进且Step0无未来诊断。最终类型/构建/Node37及完整Edge44/44（1.8m）通过，浏览器327e00ae-1b5e-4409-8d3e-74d6b14a5f9f/；298模块、JS gzip164.36KB/CSS13.76KB。首轮共享脚本日志memory-quality-20261014.log保留退出1，最终浏览器日志memory-browser-final-20261014.log；不改写失败历史。桌面/390截图已查看，真正手感/现场签收仍由负责人完成。

正常API启动器6996/监听37204、Web19528已恢复，MCP7048保持（8000/5173/8765），日志artifacts/memory-product-20261014/。5173 GET200、目录live、28题/5模型含Fake。查看单次运行→ToolLab文档任务→更多设置→近期轮次+工具记忆（建议窗口1/8192字节）；模型节点显示保存来源和大小，旧历史只GET。无新真实模型推理、远端CI或GitHub提交，所有先前改动/产物保留。下一任务为一模型一任务的同窗口开关真实小样本，再根据失败决定记忆压缩/选择或专项挑战；不先启动数据库、多Agent或框架。

## 2026-10-13 多Agent小人沙箱与合作竞争方向（最新研究偏好，未开发）

最新澄清：负责人认为现有课程展示已经够用；二维多Agent场景是约一年后开题时的演示设想，随未来需求持续讨论，不是当前课程必做项或整版签收。研究必须有近三年文献。本轮补查北邮Collab-Overcooked（EMNLP2025）、美国VirT-Lab（2025研究稿）、Melting Pot的2024LLM合作研究/竞赛、浙大AgentCoord（2024预印本/2025出版）及GovSim，已在研究文档列论文/作者源码和实际二维或图结构界面区别。VirT-Lab匿名代码链接/正式录用未核实，不宣称复现；二维实时可行性有先例，“小人+角色+对照”本身不构成新颖性，候选研究还需失败驱动和公平实验。仅更新研究/交接，无功能开发、模型调用、图形依赖或GitHub提交。

负责人随后明确场景建模/实时小人博弈展示在学有余力时后期推进。按研究建议记录为可视化扩展，不提前启动图形引擎或新多Agent实现；世界规则、角色隔离与算法验证和展示层分开。

负责人认为通用技术栈简历描述不足，明确长期希望多个独立角色的小人Agent合作/竞争/博弈，并用同条件基线与改进双世界可视化；具体优化尚未选定。已核对需求V0.6/V0.7路线并查MAST、NegotiationArena、GovSim和Evolving Orchestration，形成[场景/建模/调度通信/实验与交付建议](../research/multi-agent-sandbox-direction-20261013.md)。建议首场景3角色局部信息协同配送，合作中资源争用和真正私有利益博弈分开；第一候选研究事件触发/定向通信，并用A/B/C/D消融拆因素，同Agent/世界/团队总预算。小人反映实际世界动作，LLM仅高层决策，模拟tick与真实时延分开，不硬编码优化胜利。独立角色是状态/观察/工具/目标/会话隔离，不等于分别训练模型；来源记忆建议仍可作子机制。仅研究建议，无新实现/阶段变更/ADR接受/真实实验/提交GitHub，尚不能写多Agent已支持或提升率；正常产品服务沿用下节。

## 2026-10-13 简历成果与开题主线调研（建议，未启动实现）

负责人要求暂离UI优化，分析技术栈、可量化改进与论文关联。已核对源码/需求和既有真实结果，并查AgentFold、ACE、GEPA、τ-bench及Mem0原文；[调研与实验建议](../research/resume-and-research-roadmap-20261013.md)记录真实栈、工程贡献、候选证据约束上下文管理与可靠性方向、任务不足、对照/消融及简历口径。现有窗口一对Token少3.02%但时间多14.40%，配送单次契约修复前失败/后6工具通过，不包装成稳定成功率或37.9%总体节省。建议从有依赖的新任务与来源可追溯的证据记忆验证，不把平台版本迭代称Agent已经自我进化；开发/测试隔离、提取开销、全部失败与重复可靠性须计入。此为研究建议，不是新Accepted ADR、算法实现、整版签收或已证实论文创新。仅新增文档，无真实推理/代码变更/提交GitHub，产品服务沿用下节。

## 2026-10-13 对照实验布局与图形指标看板（最新，本地未提交）

负责人重新授权优化对照UI，取代此前暂缓对照界面的优先级。现改全宽执行设置/任务选择网格，模型说明折叠、高级预算多列按需展开、主操作集中显示真实执行规模；保存结果在前，下一次草稿收起在后，消除320px窄长侧栏及其旁边空白。结果采用两侧独立通过/未通过环，实际成功次数放环下，删除重复成功率盒；Token总量与平均耗时分图条形展示，费用/质量明细与原成对Trace保留。看板概览只读单场，选择comparison_key后用最多30次非空历史画成功率/Token/耗时折线，X为等间距运行序号而非真实时间间隔，原始表保留，点/筛选/刷新只GET；单次/无样本/未知费用中性，0/100%不补造，缺次数不反推。上下文历史标签纠正，未知轴中性。正常同值曲线曾被第二侧遮盖，补实线/虚线、不同点径和重合提示，不挪数据坐标。

仅复用React/SVG/CSS与原保存指标，无新依赖、API/Schema/评分/预算或数据库变更。需求V0.6、UI规范1.7、AGENTS/README同步；[官方参考与设计决定](../research/experiment-dashboard-20261013.md)、[源码阅读/状态/失败与防错交接](../tasks/experiment-dashboard-20261013.md)完整。所有既有本地工作和产物保留，不提交GitHub。

Web类型与36单元通过，首轮10项专项Edge通过；删除重复卡后完整Edge42/42（1.6m）通过，目录artifacts/playwright/fd5b48ad-c3be-4099-9d7b-ea6b34a293e0。随后空样本旧进度条和差值补降级、正常截图补同值区别，最终类型/生产构建与3/3专项（11.3s）通过，目录44b0867e-3f11-4df3-9369-a40aac1e564e。最终297模块，JS gzip163.00KB/CSS13.76KB，既有Zod注释/500KB分包提示保留；无新增依赖或调阈值，不重复无关Python全套。截图实际检查全宽、环/条/折线及1440/1280/768/390；动态reduce通过，真实200%缩放/课堂观感/整版签收仍不由自动检查代替。

正常后端已有52条历史只读核验：旧真实MiniMax上下文实验16116cfd-cc05-4c57-9689-eacce4af070f两侧100%/各1次，Token10408/10094、毫秒57909/66248与图形一致；某同配置Runtime组3次的重合趋势实际查看。正常四宽度、刷新零POST、控制台无错误、原Artifact未变，报告/截图/脚本在artifacts/dashboard-ui-20261013/；本轮没有新真实模型推理，Fake图形测试不是新的模型能力结论。

最终正常API启动器24612/监听2580、Web33136（8000/5173），MCP仍启动器17212/监听7048（8765）。经5173代理目录live、28任务/5模型（含Fake）；日志在dashboard-ui目录，浏览器打开请求queued。刷新http://127.0.0.1:5173/?mode=experiment查看配置；运行或GET旧结果查看图形，展开历史并选同配置组看趋势。HEAD998ff6e，无暂存/提交/推送，此节替代旧服务PID；V0.2现场和整版V0.3仍待签收。

## 2026-10-13 本地项目启动（最新服务状态）

负责人要求启动项目。核对8000/5173/8765均空闲后启动正常后端、Vite与固定只读MCP；API启动器33384/监听11900、Web27068、MCP启动器17212/监听7048。工作台http://127.0.0.1:5173/?mode=single实测HTTP200，经前端代理GET元信息目录live、28题/5模型（含Fake）；未发模型推理请求，目录可读不等于额度或调用通过。后台隐藏启动，日志artifacts/startup-20261013/；浏览器打开请求queued。未修改功能代码或提交GitHub；此前服务PID由本节替代，产品与验收状态沿用下文。

## 2026-10-12 实时关联资料工作台（最新，本地未提交）

负责人要求暂缓推进对照实验，优先把关联依据放在实时演示旁。已复用ADR-013/014/028/029和原Trace，新增环境文档卡片/正文预览/实际已读与提交引用状态；ToolLab本地/MCP共用，BFCL无文档不显示。来源严格当前前缀的初始快照、成功搜索与实际阅读返回，包含干扰项，不读私有goal、不借最终快照补造。read_document开始自动选择资料并在节点显示实际文档ID；成功且匹配返回才计已读，提交成功才标实际引用，是否有效仍由Evaluator判断。拒绝/超时/null不取得证据，断线未返回显示未知；早先读取成功不被后续失败抹去。网页选择只预览、零工具调用/零模型注入，独立目录滚动不抢焦点。宽屏资料与当前阶段在画布旁，900px以下堆叠；正文可键盘滚动。[任务/源码/状态/防错交接](../tasks/realtime-evidence-20261012.md)，UI规范1.6和需求/AGENTS/README同步。

最终Web类型/生产构建通过，296模块，JS gzip160.81KB/CSS12.65KB，既有Zod注释及500KB分包提示保留，未新增依赖；Node36/36（新增资料投影失败检查）通过。首轮沙箱spawn EPERM，允许现有本机测试子进程后通过；16项专项Edge通过后补文档节点ID/断线未知文案，最终完整Edge39/39（1.5m）通过，产物artifacts/playwright/43239e69-74ce-4aa7-bf46-66f746cf1183/，覆盖增量状态、预览零执行、提交不提前、超时/空文档/拒绝、断线/缺快照、原历史不变、1440/1280/768/390与reduce。桌面、768/390和真实MCP截图实际查看；没有新真实模型推理POST，不重复无关Python全套，不代表现场或整版签收。

恢复正常服务后，仅GET回看既有真实产物：本地退货cd65f7b9-fe5b-5cf4-8b4b-75eb84cad8cf显示3/5已读与3份实际引用；MCP配送3533440c-f72b-4d16-8780-8229f8748300显示4/6与4份引用，原评测true/完整产物保持。两个产物刷新及页面零POST、无控制台错误；报告/截图与服务日志在artifacts/realtime-evidence-20261012/。这些是旧真实记录的呈现核查，不能写作新真实实跑。

正常API启动器41428/监听37736，Web9680，MCP仍启动器9712/监听11524，8000/5173/8765。正常网页已恢复28题、5个模型（含Fake），目录状态另以实际GET为准；刷新http://127.0.0.1:5173/?mode=single，选场景实时演示→核对模型→运行，资料随首个环境快照出现，实际读取自动联动。HEAD998ff6e，无暂存/提交/推送，所有既有改动与历史保留；V0.2现场与整版V0.3签收仍待。

## 2026-10-12 课堂演示工作台成品收口（最新，本地未提交）

负责人授权从最小验证推进成品。三场景中文入口已接现有Web，明确配置实时单次或上下文对照：只填草稿、保留当前工作区模型、单任务Seed1/Repeat1、相同预算，只比较full vs窗口1；原历史/Job/评分与版本保持。缺任务、元信息读取中、运行中禁用；配置后折叠场景并聚焦原配置，确认后才运行。保存上下文结果新增用户解读，复用原CSV/JSON及Trace穿透。任务卡V0.3-classroom-product-20261012和[源码/状态/失败/真实交接](../learning/V0.3-classroom-product-20261012.md)同步，无数据库/框架/新核心接口或GitHub提交。

真实仅MiniMax退货Task1.3.0一对，本地/LangGraph/无纠错/20000Token/300秒/总边界40000；实验16116cfd-cc05-4c57-9689-eacce4af070f，两侧均SUCCESS且独立评分true、5模型/5工具，full10408Token/57909ms、窗口1为10094Token/66248ms，共10请求/20502报告Token。最新诊断full可见10消息/3823字节，窗口1可见4/1990字节，完整历史10；单样本不能证明优胜，Fake遗忘失败不代表真实模型必失败。探针CSV错误404来自不存在的导出接口；Job已完成，只GET补采产物，无新增真实请求。实际Web下载发现旧CSV缺模型来源，共享导出末尾追加保存的model_id/provider/task_name，原23列与未知空值不变，不借当前草稿补来源。真实CSV、页面、刷新零POST与完整结果不变已在Edge复核，证据artifacts/classroom-product-20261012/。

首轮专项2通过/1失败，误给单次Fake传Experiment的clean场景被422拒绝；改用原success契约后，完整Edge36/36（1.4m）通过，目录artifacts/playwright/1771af31-1b5d-4599-b067-526cf2ee1ff4/。随后CSV来源补充，最终4项相关Edge4/4（17.9s）通过，目录91fc18cb-8a7a-439e-9472-39217b1cc58e；原上下文/挽救空列兼容保持。最终类型/构建与35单元通过，295模块、JS gzip159.24KB/CSS12.29KB；既有Zod提示及500KB主包分包提示保留，未新增依赖/调阈值。1440/1280/768/390场景截图和真实结果实际查看，API/Runtime/评分未改，不重复无关Python全套，不替代现场/整版签收。

为隔离浏览器测试仅核对并停止本项目API/Web，MCP保持。最终恢复正常API启动器34344/Web22236（8000/5173），MCP仍启动器9712/监听进程11524（8765），日志final-*.log在classroom-product目录。打开 `http://127.0.0.1:5173/?mode=single`：顶部选场景→实时演示或上下文对照→核对当前模型→点击运行；查看上述真实实验链接仅GET。最新服务PID与“成品进行中”由本节替代；HEAD998ff6e，无暂存/提交/推送，V0.2现场签收和完整V0.3仍待。

## 2026-10-12 寻径之狐正式接入与加载动画（最新）

负责人明确授权更换图标和制作Logo加载动画。以已选狐狸柔化稿统一手写SVG，导航改fox-motion.svg、静态favicon改fox-icon.svg；狐狸侧脸/尖耳/卷尾保留，圆润留白路径与透明遮罩统一，应用/单色/动画路径均从唯一主SVG生成。原Wayfinder/原preview.html和候选PNG保留为历史；UI规范1.4记录新品牌边界，需求仍V0.6。任务卡与[源码/设计/动画/验证交接](../design/fox-v1/README.md)同步。

导航初次加载：0–560ms狐狸显形、180–480ms五官、380–1330ms尾部通道展开，之后恢复基础样式停住；不阻塞页面、不循环、不表达Trace/模型/网络状态。点击/Enter品牌在新页打开fox-preview.html，可重播、阅读理念和尺寸示例。动态reduce立即静态、无动画CSS仍完整，动画资源失败在导航/展示页仅回退静态，不影响实验。首轮检查器CSS返回格式/二进制深断言内存异常，以及保留合成层时PNG不一致均修正；有限动画采用backwards、结束释放裁剪/变换，完成PNG与静态逐字节比较通过，未放宽断言。

专项Edge通过路径一致/中间动画/结束静态一致/动态reduce/无CSS兜底/键盘/四宽度/PNG尺寸导出，报告/截图/录像 `artifacts/brand/fox-v1/`。Web类型/构建/Node35/35通过（294模块，JS gzip157.69KB/CSS12.08KB，两条既有Zod提示），完整Edge33/33（1.3m）通过；`artifacts/playwright/42a7e3fc-bddd-4e7e-a933-f1db89a12f76/`含新增品牌打开页面零POST、草稿/历史不变、快速重播与资源失败测试。实际查看桌面/390预览、深浅底/尺寸与工作台1440/390导航；不代替实机/整版签收，没有真实模型请求、后端契约变更或重复无关Python全套。

浏览器测试开始前核对8000/5173/8765已无服务占用，未结束未知进程；结束后启动正常API启动器22108/Web41728/MCP启动器9712，端口8000/5173/8765，日志normal-*.log在brand/fox-v1目录。刷新 `http://127.0.0.1:5173/?mode=single` 看新导航，或访问 `http://127.0.0.1:5173/brand/fox-preview.html` 看/重播完整动画。此前旧PIDs与“尚未替换”由本节替代；旧实验与所有已有长链修复保留，HEAD仍998ff6e，无暂存/提交/推送。

## 2026-10-12 动物品牌方向探索（最新设计进展）

后续按负责人x20.1%/y75%标注将狐狸尾部留白直角柔化，主图/单色/导航转折已实际查看；最新fox-soft-path-concept.png及提示词保留原稿。补[寻径之狐设计理念](../design/animal-concepts-20261012/fox-design-rationale.md)：狐狸提供探索形象，尾部路径呼应Labyrinth和可观测执行轨迹，暖色沿用工作台；含汇报可用说明。应用图标几何仍须统一SVG，未接入/发布，无模型请求或功能代码变化。

负责人希望图标增加动物联想和辨识度，随后明确更喜欢B/狐狸，已作为后续主方向取代浣熊推荐。基于原B完成狐狸侧脸/尖耳/路径尾巴精修PNG，实际查看；提示词、精修与原三方向候选保存在[设计交接](../design/animal-concepts-20261012/README.md)。仍是概念稿，应用示例与主图局部几何不同，不算统一SVG或小尺寸验收；后续统一轮廓并实测，现用Wayfinder/导航/favicon尚未替换。仅新增设计资料和偏好记录，无模型请求/功能代码变化，未重复功能门禁，无提交推送。最新产品修复/运行状态仍以下节为准。

## 2026-10-12 三场景真实失败修复与复测（最新，本地未提交）

负责人授权复测免费模型的三个长序列任务并修复，Accepted ADR-029；当前Task1.3.0/ToolSetv1.3.0/order_status_v2。用户失败实际分为：已读证据仅排列不同被旧评分误判；文档任务可见禁止query_records误导选工具；GLM/M3首轮多调用被严格拒绝。后续实测另发现read_document描述只准搜索结果，与正文引用冲突，MiniMax重复搜索耗尽预算。新协议仅三题启用无序多重集证据比较、允许工具Schema过滤和直接正文引用说明；重复/遗漏/额外/未读证据、参数/权限/单行动硬校验仍拒绝。原12题、旧评分/Schema/Agent/hash/恢复/失败重跑保留，未改写历史。新建请求选最新工具集，两侧对照同规则；不截多调用、不自动换模型或重试。

真实经正常5173代理SSE、独立MCP/LangGraph/full/无纠错，10步/20000Token/300秒/1024单响应：MiniMax退货 `6f680ca7-5813-4585-b5a9-0905afcb8708` 5/5工具与模型、10679Token通过；退款 `07b2c231-42ab-4a6f-8b83-f404edcf6a68` 7/7、17310Token通过（两题Task1.2.0）。配送首例 `26285484-6f5c-4b4b-a432-7b9e462ef974` 9模型/8工具、20766Token预算失败保留；GLM5.3同题Task1.2.0 `9002411f-cfc9-4021-909b-a3e30f170305` 6/6、12747Token通过。引用说明修复后仅复测MiniMax配送Task1.3.0 `3533440c-f72b-4d16-8780-8229f8748300` 6/6、12896Token/69302ms通过，四份依据均直接阅读，预算未增加。五题共33模型请求/74398已报告Token，全部SSE与保存GET一致。三个场景有真实通过记录，不称最新Task1.3.0三题重复全过、统计收益、全部免费型号可用或新真实恢复验收。

完整门禁：Ruff/mypy101、pytest353（44.80s，1条既有依赖警告）、四套22格Fake零退化、CLI上下文24、Web类型/构建、Node35/35、audit0、Edge31/31（1.2m）、diff通过。最终门禁 `artifacts/quality/84585fbc-2737-4b65-9ab2-d1279abcf3fb/`，浏览器 `artifacts/playwright/b6f337ea-f095-404d-89e5-a50b452a815f/`，真实/日志 `artifacts/long-chain-recheck-20261012/`；不替代实机/整版签收。模型notes同步实际结果；M3/Flash新协议未复测，不自动提升推荐。

正常API启动器17612/Web33616/MCP启动器32488，8000/5173/8765。刷新 `http://127.0.0.1:5173/?mode=single`，选ToolLab“退货/配送/退款”、MiniMax、LangGraph/full/无纠错、10步/20000Token；须新建Episode，旧产物重跑沿用旧协议。源码阅读、状态/失败、全部ID与版本差异见[最新交接](../learning/long-chain-real-failures-20261012.md)。HEAD998ff6e，未暂存/提交/推送，全部既有工作与产物保留。本节优先于下文旧版本、旧模型说明与旧服务PID。

## 2026-10-12 跨文档场景产品闭环（最新，本地未提交）

负责人授权少量有价值的复杂场景，并要求最小验证后完成实际产品；同时撤回自动提交GitHub授权。Accepted ADR-028、任务卡/需求/AGENTS同步，基线998ff6e，未暂存/提交/推送。新增退货/配送/退款三题，3/4/5份关联有效文档、旧版/错案干扰，独立自建development仿真，不称外部真实数据。固定long_chain子目录递归进入现有ToolLab/API/MCP，原12题字节及旧四套基线不改。类别evidence_chain、公开模式document_chain，不改Schema/工具参数/评分；Fake仅从公开可见工具消息跟引用、复制状态、收集证据，不读goal或按ID答题。完整证据须来自成功阅读，允许任意正确路径，不凑调用次数。

网页可选题/SSE实时过程/最终答案证据/失败/保存回读和上下文对照。修复默认任务不按meta.default_task及选长任务沿用6步的问题，未手改步数/Token随任务推荐值，手改值保留；新题不自动加入默认12题对照。MiniMax实际累计9493Token暴露旧8000不足，新Task版本1.1.0推荐10步/20000Token，原产物和显式低预算不改；两侧预算相同进哈希。Provider带工具显式parallel_tool_calls=false匹配原单行动边界，供应商仍返回多调用则原样失败，不取第一条或自动重试。

最终完整门禁：Ruff/mypy100、pytest351（45.11s，1条既有依赖警告）、四套22格Fake零退化、CLI上下文24、Web类型/构建、Node35/35、audit0、Edge31/31（1.2m）、diff通过。路径 `artifacts/quality/3292de5d-364f-4066-963f-6b92e40664cc/`、浏览器 `artifacts/playwright/bbd6d3d2-fcb6-4821-8d69-3d58197c04e2/`，日志 `artifacts/linked-evidence-20261012/quality.log`；截图实际查看，自动验收不替代实机/课程签收。类型声明、浏览器默认值、探针响应字段/实例保护与启动就绪竞态的失败均保留，未弱化保护。

真实：GLM Flash关闭参数前后各一题仍MULTIPLE_TOOL_CALLS、0工具、usage未知；MiniMax初版8000末轮预算失败（9493报告Token），新版本20000 `e9065b98-a8c5-475d-a1e1-1582d464c0fe` 真正通过：5模型/5工具/56158ms/10066报告Token，approved＋三条真实读取证据，38SSE Trace/complete与GET一致。共4真实Episode/12推理尝试，19559已报告Token，两次未知不当零；不称三题真实全过或统计收益。网页候选说明同步，建议新退货演示用默认MiniMax，配送/退款尚未真实复测。

Fake：三任务两Runtime/full与窗口足够通过，窗口1证据缺失失败；正常MCP退款 `8c701b37-b7fb-49bc-a3ea-dfad4852c28b` 7工具/5证据通过，正式上下文实验 `b6b95a7c-70cc-42d0-a998-6b30307392ec` full3/3、窗口1为0/3。两Runtime中断后新实例恢复五份文档各读一次；这是Fake工程验证，不宣称新真实跨进程恢复或真实遗忘效果。

正常API启动器37420/Web34008/MCP启动器32488，8000/5173/8765。刷新 `http://127.0.0.1:5173/?mode=single`，ToolLab搜索“退货/配送/退款”；实时新建与历史回放入口沿用。源码/调用链/状态/失败/结果/接续见[学习交接](../learning/V0.3-linked-evidence-20261012.md)、[任务卡](../tasks/V0.3-linked-evidence-20261012.md)与[场景说明](../../benchmarks/tool_lab_core/tasks/long_chain/README.md)。没有数据库、新框架、独立Planning/Memory、Judge或业务写操作；V0.2现场签收和其余V0.3保持待办。本节优先于前文自动同步授权、旧服务PID和旧预算建议。

## 2026-10-11 GitHub 同步授权

负责人要求本次及后续任务完成后及时提交/推送，授权已写入AGENTS；按已完成门禁汇总提交当前全局Token预算、上下文API/Web对照、实时执行/通用输出呈现和模型准入/工具说明修复，关联ADR-025–027及各学习交接。此前各轮“未提交”是当时状态；本轮核对GitHub远端与暂存来源并扫描凭据后同步main，最终提交SHA和远端核对结果留在本机 `artifacts/publish/20261011/`，不将实验产物/.env入库。质量证据沿用紧邻完成的全套343 Python/35 Node/29 Edge及Fake回归；仅补授权/同步记录不重复推理或干扰正在运行的网页。整版现场签收和远端CI仍另行确认。

发布前远端fetch确认HEAD与origin/main一致（4581ffb）；直连GitHub遇连接重置/443超时，临时沿用本机既有HTTPS代理后成功，不修改Git全局代理/证书。暂存58个文件，索引扫描297文本/11二进制，未发现本机凭据值或常见密钥模式；.env/artifacts不在索引内。补清理此前未跟踪ReadableFields文件末尾空行，暂存diff检查通过，不改变运行行为。扫描报告 `artifacts/publish/20261011/secret-scan.json`。

## 2026-10-11 两个共性问题修复（最新）

负责人授权处理推荐模型实测发现的目录误拦截和提交说明问题，Accepted ADR-027 已落地。仅正式配置的 Flash 允许精确布尔目录例外，元信息及共享执行检查一致，客户端不得注入，未配置型号/Provider 失败仍拒绝或失败；M3/Flash 新增为实验候选，默认仍 M2.7，Kimi 不加入。新 API ToolLab 工具说明固定 v1.1.0，答案/证据支持记录与成功文档阅读，严格参数/权限/评分不改；旧安全点、失败重跑、冻结计划按保存版本，固定 CLI 回归按基线版本执行，原基线/hash 不改。BFCL 不变。

最终完整门禁通过：mypy99、pytest343（46.97s，1 条既有依赖警告）、四套 Fake22格零退化、CLI上下文24、Web类型/构建、Node35/35、audit0、Edge29/29（1.1m）、Ruff/diff。修正首轮脚本版本兼容与浏览器测试漏展开问题，未放宽断言/评分。目录 `artifacts/quality/cc2b1c0e-71f6-4c35-b782-78a7dc815cc1/`、浏览器 `artifacts/playwright/90dd056c-b6e7-439d-8899-a53c3b672173/`，日志 `artifacts/admission-20261011/quality.log`。

正常5173代理SSE真实文档007各一题：Flash `935c9445-dc06-4f41-946f-7fc03ade9759` 正式例外通过，approved/document:DOC-007，3模型/3工具/32196ms/3180报告Token；M3 `c22c8823-f06a-4eef-bbc2-bfecfdf0003d` 完成搜索/阅读/提交但答案多带原文，精确评分 false/FAILED，3模型/3工具/34990ms/4031Token。每题24Trace+1complete，GET重读一致；未重试或继续调参，不能把可调用记为能力全通过。正式meta live含M2.7/GLM5.3/M3/Flash/Fake，Flash缺目录提示保持，notes同步新失败原因。源码/版本/失败路径/复测/接续见 [学习交接](../learning/model-admission-tool-descriptions-20261011.md) 与 [任务卡](../tasks/model-admission-tool-descriptions-20261011.md)。

已恢复正常API启动器PID19328/Web PID40112，8000/5173，日志 `artifacts/admission-20261011/`；刷新 `http://127.0.0.1:5173/?mode=single` 可选择新候选，文档现场演示先用 M2.7 或本次通过的 Flash。全部旧改动/历史保留，无提交推送、远端CI或整版签收；本轮未新增真实MCP/恢复实验。前文旧PIDs/“网页候选尚未追加”由本节替代。

## 2026-10-11 推荐三模型小样本（最新）

负责人更换Key模型范围后授权接续：M3 BFCL/订单通过、文档读完后误提query_records被权限校验终止（2/3）；GLM5.3 Flash BFCL/订单/文档均通过（3/3）；KimiK3目录可见但HTTP400/no_available_channel，未测多轮。统一LangGraph/无纠错/full/Seed1/8000Token/180秒/1024单响应，七Episode、13模型尝试、13154已报告Token，无自动重试或隐式换模型。两次目录仍无Flash但六次真实响应200，正式GET目录前置检查会拦截；临models_path诊断不代表网页新建验收。另发现SubmitAnswerArgs描述只说queried record/query_records证据，与文档read_document冲突，可能误导M3但未证实因果。后续先为可信候选准入及通用工具描述/版本兼容形成ADR，不能静默改评分/权限或中途混Prompt。正式目录、API/Schema/Provider与旧历史未改；保存产物核验通过，完整结果与ID/阅读路径见 [三模型实测与共性问题交接](../learning/recommended-model-review-20261011.md)。无提交推送/整版签收，网页候选尚未追加。

## 2026-10-11 截图中新模型真实检查

负责人授权测试并确认原Key已保存权限。截图新增Qwen3.8 27B、Atlas Dots3 Note Preview、Ling3.0 Flash VL、Nex N2.5 Pro/Mini，五个均经真实BFCL0/LangGraph小样本返回HTTP400、UPSTREAM_CHANNEL_UNAVAILABLE（上游no_available_channel），0工具；当前无法评能力，不记能力零分。已有MiniMax同配置对照通过，6980ms/389报告Token；Qwen一次无工具小请求也无通道。新进程目录三次仍仅MiniMax/GLM两ID，无环境Key覆盖或.env重复项；权限/凭据一致性、同步与上游路由尚不能唯一归因，不宣称每日额度耗尽或永久下架。共六Episode＋一次文本请求，七推理尝试，无自动重试，未延伸多轮/批量。诊断临时候选models_path只用于当前进程，生产目录、API/Provider/权限/评分与原历史不改；产物重读/身份/末尾事件核验通过。证据和接续步骤见 [真实测试交接](../learning/new-model-review-20261011.md)，本机忽略结果在artifacts/new-model-review-20261011/。无提交推送或整版签收。

## 2026-10-11 跨模型比较与免费候选调研

负责人说明现有免费模型已跑通，询问如何衡量结果及寻找新候选。本轮核对现有 Experiment 三轴都要求同模型；ToolLab 答案/证据与 BFCL 函数提议匹配分别评分，运行 SUCCESS 不等于独立评分通过。建议固定任务/预算/Runtime/上下文/纠错，只变模型，先复用独立产物做只读汇总，另列上游失败与成功任务效率；新增公开 model 轴先走 ADR。官网核对 MiniMax M3、GLM5.3 Flash、Kimi K3 免费详情，均仅候选、未用本机 Key 实测或入目录；Qwen3.6 Preview 索引与下架详情冲突，排除。原工作区改动保留，无推理请求、契约/评分变化或提交推送。口径、调用链入口、候选来源及下一步见 [调研与交接](../research/model-evaluation-free-candidates-20261011.md)。

## 2026-10-10 模型连接失败现场排查（最新运行状态）

负责人询问每日额度。核对最近MiniMax/GLM文档任务均约5秒终止，保存码NETWORK_CONNECTION_FAILED，没有保存HTTP429/每日额度证据。无Key公开目录探测：当前系统代理可HTTP200，直连HTTPS超时；MiniMax一次最多64输出Token真实小请求HTTP200（108总Token），证明当前该模型仍可请求，不能扩为其他模型额度结论。仅重启已核对自有API，保留Web与全部产物；随后平台经5173代理真实单题BFCL MiniMax成功，Episode `4aad38d6-2efb-4bbc-8551-f952240b7dd9`，SUCCESS且独立评测true，3561ms，输出math.factorial/number=5（未执行计算）。没有重跑文档多轮或其他模型批量；本轮共两次真实小请求，不把目录200当推理成功。

当前API启动器PID30104/Web PID22188，loopback8000/5173。旧进程网络路径/代理状态或瞬时连接异常与重启后恢复一致，但原脱敏错误未保留底层reason，无法确证某一种原因；不宣称上游额度重置，也不修改全局代理、证书、DNS或Provider/Schema/评分。后续若再次出现，优先记录脱敏连接类型与当前代理通路，不盲目更换模型或自动重试歧义推理请求。日志沿用 `artifacts/execution-ui-20261010/normal-api-*.log`，[排查记录](../learning/model-connection-20261010.md)含证据与边界。未提交推送。

## 2026-10-10 实时优先与结束保持（最新）

负责人明确要运行中看到Agent过程，不要完成后再播。确认原新建单次已使用SSE，但完成后setLiveRun(null)切历史，Artifact身份effect重置到起点。沿用ADR-014，App保留completed状态与确认后的保存事件/实际Model及Environment；McpFlowReplay displayMode区分live/completed/replay，前两种始终跟随最新已收到事件，complete后保留终点和最终输出、不出现播放器。启动时一次聚焦执行区并检查请求代次，后续不反复滚动；短时连线随事件到达，断线/完成/reduce不动画。主动点击“查看保存详情与回放”才进入旧只读回放，历史GET/导航继续保留。BFCL仍不执行函数，无数值结果；不改API/Trace/Schema/评分，不扩Resume/重跑/Experiment实时订阅。

Web类型/构建、Node35/35、Edge完整28/28（1.2m）、diff通过。浏览器 `artifacts/playwright/d3c2632c-500d-4db6-bb9c-1d0ac573cb5f/`，实际查看增量/完成截图；新增分段ReadableStream夹具使用实际Fake文档事件，仅证明前端消费/不提前显示/完整结果后保持同一终点/主动回放/动态reduce/刷新零POST/源产物不变，不是新真实模型或网络时延证据。既有Fake实际新建闭环同步验收completed。截图复核后只把ToolLab输出详情移到终止元信息之前，最终构建再次通过（JS gzip157.36KB/CSS12.08KB）。不重复无关后端全套/远端CI或自动签收。

正常API启动器PID8004/Web PID22188已恢复，loopback8000/5173；Web代理GET目录live、四个免费候选、页面200，无真实推理POST。日志 `artifacts/execution-ui-20261010/normal-*.log`，进入 `http://127.0.0.1:5173/?mode=single` 新发起任务才展示实时过程，已有Episode链接是保存历史；真实多轮演示可用ToolLab文档007，不以一次BFCL调用代表长链。任务卡/UI规范与 [源码阅读/状态/失败交接](../learning/execution-path-ui-20261010.md)已更新，原所有改动与历史保留，无提交推送；现场视觉/实机签收继续待办。

## 2026-10-10 通用任务交付展示（最新）

负责人指出BFCL阶乘题没有输出，随后明确所有任务应展示对应交付要求。核对本机GLM实际轨迹只有 `math.factorial(number=5)` 与accepted=true，无120；BFCL环境仅接收提议。沿用ADR-013/014/022，前端输入/输出补公开交付要求，结束节点/详情从当前前缀快照呈现答案/证据或函数调用/参数；独立保存产物补评测success/reason，SUCCESS不推导评测通过，失败/缺字段/缺快照不补造。数字结果与其他函数执行结果仍不生成，新增执行环境须单独ADR；未改Schema/评分/Provider或历史文件。源码/交接补充见 [执行路径说明](../learning/execution-path-ui-20261010.md)、任务卡与UI规范7.4。

Web类型、构建、Node35/35、Edge完整27/27（1.1m）、diff通过；浏览器产物 `artifacts/playwright/1094deb0-5627-4f5b-ae28-ba9f6d62992d/`，BFCL桌面/390截图实际查看。新增显示夹具仅Mock GET，不能作为BFCL Fake成功证据；订单/文档/参数拒绝为隔离Fake真实运行。覆盖早期不借后续输出、评分失败、缺快照、历史零POST、文件不变和视口。截图复核后仅将结束输出移到终止元信息之前、说明改为通用函数，最终构建再次通过（JS gzip157.02KB/CSS12.08KB）；不重复无关Python全套、新真实推理或远端CI，不签收整版。

测试停止并核对自有服务后已恢复正常API启动器PID21408/Web PID30072，loopback8000/5173，经Web代理GET目录live，四个免费候选可见、页面200；本次不再切Fake演示后端。运行日志 `artifacts/execution-ui-20261010/normal-*.log`。刷新历史并将动画滑块移到结尾查看新输出；本机阶乘历史ID `e609046d-7706-4e08-9342-237c8538dbae`，另一台电脑用自身产物，不依赖该ID。所有原未提交改动保留，无提交推送；课程实机/投影反馈与整版签收待办仍保留。

## 2026-10-10 正常模型入口恢复（当前运行服务）

负责人发现免费模型消失；原因是上轮启动的 `scripts.course_demo --preview` 使用 DemoService，只开放 Fake，并非候选配置被删除。已按进程树核对停止该演示启动器/API，保留 Vite PID18712，改为 README 正常 `apps.api.main:app` 后端（启动器 PID33632），读取默认 `artifacts/`。经5173代理实际 GET `/api/v1/meta` 返回 `live`，MiniMax M2.7、GLM5.3、MiMo V2.5/V2.6四个免费候选与Fake均可见，网页200；无真实推理POST，不代表额度或通道重新通过。当前入口 `http://127.0.0.1:5173/?mode=single`；上一节隔离演示ID仍保存在demo目录，正常后端不读取该目录。UI与正式模型配置未改，日志 `artifacts/execution-ui-20261010/normal-api-*.log`。后续展示新版UI优先保留正常后端，仅明确需要离线隔离演示时切换DemoService，避免正常模型入口被演示服务替代。

## 2026-10-10 逐次执行路径与证据阅读 UI（最新）

负责人批准调研后按“节点随实际调用出现＋工具结果与证据卡”开发，要求优化视觉。沿用 ADR-013/014/022/024，只改前端呈现；[任务卡](../tasks/execution-path-ui-20261010.md)、[源码/状态/失败/接手说明](../learning/execution-path-ui-20261010.md)完整，UI 规范新增 7.4。复用既有 React Flow/CSS/ReadableFields/useContentMotion，固定模型/调度/工具图改为每次模型请求与每次调用独立节点，同名重复不合并，失败尝试保留；稳定来源 ID 与当前事件前缀，不提前显示后续工具/传输/结果。暖调行动卡、清晰文字状态、曲线箭头、逐次入口、短时可打断详情/视口过渡，长链默认对焦当前区域而非缩成小字。原三视图游标、MCP 链路、技术 Trace、保存最终结果和专注查看保留。

Web 类型/构建、Node34/34、Edge完整25/25（57.8s）与diff通过，浏览器产物`artifacts/playwright/7538e08f-b630-449d-b648-bc640b88d6cd/`。桌面/窄屏截图实际查看后补箭头显示，最终构建（JS gzip156.27KB/CSS12.03KB）与类型通过，三项路径专项再次3/3（11.9s），最终产物`artifacts/playwright/05419c52-dec3-4188-a926-ba2d6cddbd02/`。覆盖重复/拒绝/证据/超时、BFCL Provider失败、受控SSE截断、历史零POST/原产物不变、键盘/四视口/动态reduce。首次EPERM、首轮测试误匹配“尚未收到工具返回”、次轮错误假定通用Fake可答BFCL均如实记录，未篡改评分/Provider使测试假通过。通用Fake的BFCL仍是provider_error；正向BFCL展示用既有真实历史/专用受控Provider，不能宣称本轮通过。无依赖/API/Schema/模型目录/后端修改或新真实模型调用，未重复无关Python全套/远端CI，不自签V0.2。

随后自查并补起始游标：EPISODE_STARTED创建任务节点，观察原位更新，路径严格按原eventIndex裁剪；旧首帧晚于游标时不提前显示其反馈。最终Web类型/构建（JS gzip156.43KB/CSS12.07KB）、Node35/35、Edge完整25/25（1.0m）再次通过，最终产物`artifacts/playwright/b55b632d-d0dc-453b-b334-745940ae78a0/`，桌面/窄屏截图实际查看。

已恢复独立Fake预览，最终启动器PID29632，loopback8000/5173，Web/目录GET可达。示例`http://127.0.0.1:5173/?episode_id=e275778d-3d3f-530f-b531-eadf0412a606`（参数纠错）；点击播放全过程查看逐次出现，再回看失败调用。目录/日志`artifacts/execution-ui-20261010/`；本次`--skip-mcp`生成，不声称新的MCP实测。预览只提供Fake，正式模型目录未改；另一台电脑先生成自己的演示索引。原工作区未提交改动全部保留，无自动提交推送。下一步先收负责人视觉/投影/实机反馈，既有真实小样本/系统辅助功能/整版签收待办不清除。

## 2026-10-09 模型目录恢复体验修复（最新）

负责人反馈目录不可读。本轮排查8000直连meta为live，5173代理200，四个配置真实ID均可见；旧目录异常未记录，不能断言当时超时/Key失效/下线。确认旧Web只首次读取，临时失败后停留旧提示，原后端失败缓存30秒。修复共享loadMetadata首次/重读初始化区别、有效模型与任务/预算草稿保持、独立目录错误/手动重读、读取中与运行中禁用、复用RequestGeneration拒绝旧响应覆盖恢复；TimeoutError沿用REQUEST_TIMEOUT，后端只记录错误码/异常类型，不输出原异常/Key。缓存/模型预检/API/Schema/评分不改。[源码与接手说明](../learning/model-catalog-recovery-20261009.md)完整。

16项目录/Provider Mock专项通过；首门禁335 Python通过、20 Edge通过2新测试失败（StrictMode双读与独立Fake服务仅Fake的测试预期），修测试并发现/补晚到响应保护后专项2/2通过。最终完整门禁Ruff格式/lint、mypy98、pytest335 passed（46.04s，1条既有依赖警告）、四套22格Fake零退化、CLI上下文24预期一致、Web类型/294模块构建（JS gzip155.33KB）、Node32/32、audit零漏洞、Edge22/22（57.2s）、diff通过。门禁`artifacts/quality/b8b9ec2e-45a3-4453-b141-78b6e175af0d/`，浏览器`artifacts/playwright/377b7e97-df25-4ae3-9bef-4d7e2eda0b3c/`，日志`artifacts/catalog-recovery-20261009/quality-final.log`；无真实推理POST或远端CI/整版签收。

最终恢复API启动器PID37076/Web PID21256，loopback8000/5173。新后端经5173代理再次GET目录live，MiniMax M2.7/GLM5.3/MiMo V2.5/V2.6可见，Web200；不等于重新验证调用额度/权限。日志与脱敏索引`artifacts/catalog-recovery-20261009/`。原改动与实验保留，没有提交推送；刷新页面可使用新重读入口，30秒缓存内失败仍可稍后再读。

## 2026-10-09 V0.3 上下文 API/Web 对照（质量门禁完成，最新）

负责人授权接续下一任务，Accepted ADR-026、需求V0.6受控例外与AGENTS已同步。[任务卡](../tasks/V0.3-context-comparison-next.md)、[源码/演示/失败/接手说明](../learning/V0.3-context-comparison-web-20261009.md)完整。复用ContextPolicy与正式Runtime/Runner/Job，仅增加context_policy轴：左full、右最近1–100完整轮次，同模型/Prompt/工具/Runtime/纠错策略/任务/Seed/预算。旧轴仍固定上下文，缺省Agent/hash不改。单Episode请求1.3、Experiment请求1.5，显式策略要求新版；新轴计划1.2/结果1.4，兼容全局Token。策略进冻结来源、结果和回归指纹，恢复和显式失败重跑沿用原策略；上下文轴全部挽救指标null、recovered=false。网页配置/原窗口只读、成对表格、CSV策略字段与当前请求帧诊断完成；字节非Token/HTTP包，旧无诊断不补造。

最终完整门禁：Ruff格式/lint、mypy98、pytest333 passed（42.77s，1条既有依赖警告）、四套Fake22格零退化、CLI上下文24案例预期一致、Web类型/294模块构建（JS gzip155.14KB）、Node32/32、audit零漏洞、Edge20/20（53.0s）与diff检查通过。门禁`artifacts/quality/8cd84ed7-acb1-4f82-9f50-200acbbe2b6a/`，浏览器`artifacts/playwright/a73d4052-9aa5-4779-b4f0-17e06d2b92b9/`，日志`artifacts/context-web-20261009/quality-final.log`。新专项最初12/12，后补单Episode API至13项并进入全套；覆盖窗口1遗忘/窗口2成功、两Runtime、版本/窗口/混变量拒绝、原策略重跑、完成侧不改写恢复、全局预算停止/恢复、回归策略预检。Edge覆盖从页面创建、失败明确、草稿与保存值隔离、刷新/前后只GET、实际CSV下载、四视口/减少动效/当前帧。专项与最终截图实际查看，不代替实机手感、系统辅助功能或整版签收。

最终截图复核后，仅把页头说明补入已实现的上下文对照，Web类型/构建再次通过（JS gzip155.15KB）；未改运行逻辑，未重复整套门禁。

首轮专项沙箱WinError5（5通过/7目录错误）、Node子进程EPERM，改受控本机执行；首两轮浏览器测试预期误用success选项（UI为clean）/CSV空值引号，首完整门禁332通过1失败（新测试误期200，原接口201），只修测试后全套通过。未修改原创建状态码或模拟成功掩盖失败。

原预览已退出，质量门禁后恢复API PID23288/Web PID9940，loopback8000/5173与HTTP已保存演示通过。Fake上下文实验`98b5dcd2-6bb3-4b23-b402-f51b36ad320e`，001/007各一对，完整历史2/2、窗口1为1/2；文档右侧预期MAX_STEPS。链接`http://127.0.0.1:5173/?experiment_id=98b5dcd2-6bb3-4b23-b402-f51b36ad320e`，日志/脱敏索引`artifacts/context-web-20261009/`，演示仅Fake，不是新增真实验证。

保留此前未提交UI/模型/预算等改动；无新依赖、数据库、额外框架、真实批量、提交推送或整版签收。下一步建议单独安排一个当前可用模型的小样本上下文对照与课程实机演练，再决定长链任务；不将本轮Fake工程结果当真实策略有效性或完整V0.3完成。

## 2026-10-08 V0.2 全局 Token 预算（质量门禁完成，最新）

负责人授权接续开发。Accepted ADR-025、SSOT FR-08与[任务卡](../tasks/V0.2-global-token-budget-20261008.md)同步，API/Web/Experiment已接可选max_total_tokens：跨矩阵已报告输入+输出的Episode边界准入，完整结果/安全点只计一次，失败报告用量照计，未知响应/不一致停止，旧单次预算/配置哈希不改。请求1.4、新预算计划1.1/结果1.3，旧版本可读；终态安全点零额外调用落盘，半对不伪造完整评分。最后在途Episode可超额，非供应商硬上限。Job失败原因和实际累计/保存预算在Web明确呈现，窄屏失败结果先于草稿。[源码、调用链、失败与交接](../learning/V0.2-global-token-budget-20261008.md)齐全。

完整共享门禁：Ruff格式/lint、mypy97、pytest320 passed（46.80s、1条既有依赖警告）、四套Fake22格零退化、上下文24案例预期一致、Web类型/294模块构建、Node31/31、audit零漏洞、Edge19/19（51.3s）、diff检查通过。产物`artifacts/quality/e28f0367-8fd1-498c-9e17-8632631ee79b/`；浏览器`artifacts/playwright/5cf6b5c2-f0e9-4050-9116-22c6dbf75be6/`。首次专项1失败40通过（测试误用真实预算值）修正；首次完整312通过7失败，短目录七例通过、等长目录复现，定位Windows临时文件名过长。共享原子写缩短临时名、计划/安全点复用helper后长路径原用例通过，保留fsync/replace/失败清理，不承诺任意长最终路径。

首轮停止截图实际查看后补失败Job结果区与窄屏前置（不再“尚无结果”），后端不变；最终Web类型/构建（JS gzip154.02KB）、Node31/31、Edge19/19（51.2s）再次通过。最终截图/报告`artifacts/playwright/f1edd75f-3536-41d3-8438-1b079edbbda2/`，预算停止1440/390实图已查看；键盘/四视口/减少动效自动覆盖不替代实机签收。未进行新的真实预算调用或远端CI。

预览恢复API PID8288、Web PID21596，日志`artifacts/global-token-20261008/`；本机HTTP Fake补演示完整实验`f82fec0f-2e8a-4c43-a1bf-f4bb8945b44f`（121阈值/240模拟Token）和停止Job`168f623c-d43d-458b-bb24-241ec5d2b8e9`（预算1、明确failed），GET/网页200通过。现有UI/模型/文档修改保留，无新增依赖/提交推送/整版签收。V0.2全局Token代码缺口已补，实机/第二机器/现场、真实预算与整版签收仍待；下一开发按[上下文对照任务卡](../tasks/V0.3-context-comparison-next.md)先新ADR，复用现有首切片，不启动完整V0.3。

## 2026-10-08 当前免费模型真实复测（最新）

负责人授权使用列表免费模型实际运行。[结果与失败归因](../learning/free-model-review-20261008.md)：四个型号各两题，MiniMax M2.7和GLM5.3的BFCL/订单均通过；MiMo V2.5/V2.6各两次上游HTTP429，尚未执行工具，13秒间隔下仍失败，具体限额原因未确定，不是放宽平台权限能修复。MiniMax另经正式实时目录检查，用LangGraph完成文档007（两次搜索→读取→提交，4模型/4工具、4655实际报告Token、44.929s）。共9 Episode、5成功/4失败，成功响应报告10020Token；失败零usage不证明上游零消耗，网关实付仍未知。

实时目录live且四ID均可见，未把可见性当可用性。已更新models.json旧日期说明，保留默认MiniMax和实验标记，GLM作为备用候选、MiMo标明本轮429；历史产物/评分/预算不改。16项Provider/目录/脚本Mock测试通过（1.10s），未重跑完整门禁/浏览器或真实上下文消融，未承诺持续可用或自动签收/提交推送。原本预览服务已退出，恢复API PID29720、Web PID13228；meta/历史EpisodeGET与Web200通过。日志/脱敏结果在`artifacts/live-model-review-20261008/`，完整产物在原artifacts，可用文档Episode `ae543224-be7b-4326-aacd-360ea33f6955` 只读演示。

## 2026-10-08 V0.2 收尾与 V0.3 推进复核（最新）

负责人要求检查版本完成情况与可继续内容。[复核与下一步顺序](V0.2-V0.3-progress-review-20261008.md)已核对需求、ADR与实际代码：V0.2主要受控能力已实现，FR-08跨Episode全局Token仍缺；最终真实模型、第二机器/实机/现场及整版签收未收口。已实现总时限、MCP/BFCL可视化与10月8日UI/audit修复不再列为当前缺口。V0.3上下文首切片已存在，API/Web尚无新建策略及上下文对照轴；建议先补V0.2预算，再按新ADR接上下文网页对照、少量长链任务和单模型小样本，其余机制按实验需要依次推进。

本轮专项68 passed（26.11s、1条既有依赖警告）；独立CLI Fake24案例为20成功/4个文档窗口1预期MAX_STEPS，报告与产物校验通过。产物`artifacts/version-review-20261008/`。首次缺basetemp父目录30 passed/38 setup errors，第二次沙箱WinError5，第三次本机隔离目录通过，过程如实记录。本轮仅分析/专项验证/交接，没有业务代码或契约变化、真实调用、完整门禁、浏览器重测、提交推送或整版签收；现有UI改动与预览服务保留。

## 2026-10-08 课堂演示 UI 与可视化优化（最新）

负责人授权优先优化现有 UI/可视化。按 V0.6、UI1.3 与 ADR-013/014/022/024，完成对照结论前置、历史草稿折叠、流程当前帧参数/反馈/证据、MODEL_REQUESTED/RESPONDED 阶段及三视图共享原事件锚点。已保存实验结果在 DOM 与视觉上均先于草稿，窄屏不再被最近历史列表压下；Job 控制/恢复入口保持可见。技术 JSON 按需查看，不改 API/Schema/评分/运行条件。源码阅读、失败路径、演示顺序及接手规则见 [阅读交接](../learning/ui-classroom-20261008.md)、[任务卡](../tasks/ui-classroom-20261008.md)。

最终 Web 类型/294模块构建（JS gzip153.01KB）、Node30/30、Edge18/18（47.6s）、npm audit零漏洞及diff检查通过；浏览器证据 `artifacts/playwright/8f0a0c71-db46-4271-99c9-76461269684a/`，含四视口、减少动效、失败/损坏历史与SSE、导航竞态、同一事件位置、只读历史和草稿隔离。`source-map-js` 仅1.2.1→1.2.2安全补丁，无新项目依赖。首次沙箱EPERM、TS导入扩展名错误、旧进程占用安装及首次Edge14通过/4失败（折叠步骤、缺FFmpeg）均已修复后复核，过程见交接。未重跑无改动后端全套门禁或远端CI，不替代现场签收。

IAB实际检查历史真实对照和MCP专注回放，参数/返回/已保存终点分层，截图 `artifacts/ui-classroom-20261008/`；没有重新调用真实模型。目录初次读取暂不可用，后续GET恢复模型ID可见，未将目录可见性当作真实可用性通过。前后端恢复本机8000/5173（API PID3140、Web PID23756，日志 `artifacts/local-review-20261008/`）；历史MCP无需重新启动MCP服务。保留10月7日复核报告，未提交/推送；全局Token、模型最终收口、第二机器/真实现场与V0.2整版签收仍单独保留。

## 2026-10-07 V0.1 / V0.2 需求与可视化复核（最新）

代码基线 `4581ffb`；负责人要求分析需求符合度、可视化与优化可行性。完整矩阵、源码依据和建议见 [复核报告](V0.1-V0.2-review-20261007.md)。V0.1 保留既有18项签收；V0.2主要受控能力具备，但全局Token、最终模型入口、实机/第二机器/现场与远端CI仍未收尾。Episode总时限已实现，不再沿用10月1日实现前的缺失结论；ADR-023上下文首切片保持既有授权边界。

本次确认12原生任务四类各3、ID/名称唯一；任务契约/总时限/看板/回归专项25 passed（2.61s、1条既有警告）。首次沙箱临时目录权限失败22 passed/3 setup errors，改项目内隔离目录和本机执行后通过；未重跑完整门禁。`npm audit --json` 当前返回1 high（间接source-map-js，GHSA-68fv-2mgg-jv7q，修复版本1.2.2），10月4日零漏洞仅为历史快照，本轮未升级依赖。

IAB只读查看当前真实历史对照及ToolLab/MCP/BFCL回放，1440桌面与390窄屏抽查；图与关键参数分离、对照结论层级、三种视图切换重置位置、模型请求等待阶段和播放器非真实耗时说明仍有优化空间。推荐先做结论优先、当前帧摘要与共享回放位置；全局Token需另ADR，不把建议视为新需求或自动启动实现。截图在本机忽略目录`artifacts/ui-review-20261007/`，媒体模拟/窄屏不替代系统辅助功能签收。

开始时前轮服务已退出，首次Trace GET出现Failed to fetch；恢复loopback API/Web后同ID读取正常，未归因为产品bug。前后端保持运行，视口已重置、浏览器返回原Experiment；未新调用真实模型、未重启MCP，历史MCP无需服务器。只交付分析文档，没有业务代码/Schema/模型目录/评分变更或提交推送，不自签整版。

## 2026-10-04 发布与质量快照（历史）

上一轮复核发布基线 `64dc5ae`。负责人2026-10-04再次明确授权接入Logo/动态效果并提交/推送最新代码；本次发布前已fetch确认基线与origin/main一致，完整门禁与暂存内容密钥扫描通过。本提交包含ADR-021–024的可靠性/Web边界/上下文首切片、连续动效、页面层级和D图标/动画。`.env`、测试截图和临时实验产物继续Git忽略，未知`.unsnooze/`保留本地不提交。发布结果在本机`artifacts/publish/20261004/`记录，整版人工签收与远端CI状态分开确认。

发布前最终检查：质量产物`artifacts/quality/2e4f7a71-8ff7-4128-8530-6f4999fa17c6/`；Ruff格式/lint、mypy96文件、pytest298（64.06s、1条既有依赖警告）、四套Fake22格零退化、24上下文案例预期一致、Web严格类型/293模块构建、Node29/29、npm audit零漏洞、Edge16/16（47.0s）与diff检查全部通过。浏览器产物`artifacts/playwright/1f20516f-a3ae-4839-805b-98915dcda1ee/`。未进行新真实模型调用；Github/Chromium CI与整版签收不据此补签。

密钥扫描检查Git索引内268个文本文件、11个二进制文件中的本机凭据值，未发现匹配；仅报告数量/路径、不输出凭据，报告`artifacts/publish/20261004/secret-scan.json`。`.env`、`.unsnooze/`和`artifacts/`不在索引内。GitHub官方Action标签的额外网络核对遇443连接失败，未称远端CI已通过；现有SHA固定工作流保留，推送后的运行结果另行核查。

## 2026-10-04 D / Wayfinder 图标初版与动态展示（最新）

负责人在四候选后明确选择D作为图标初版，并授权优化和动态展示。已保留原方案、用内置image_gen补优化参考稿，手写SVG统一开环/两阶路径/出口与精确色值；导航品牌加载一次短动画后保持静态，点击/Enter在新页打开完整展示，反白静态图标接favicon，导出透明标志/16、32、48、180、512px应用图标及单色版。实际生产符号以SVG为准。

独立动态SVG1620ms有限播放：圆环→路径→出口，完成后静态，不表示实际模型执行；展示页支持按钮/Enter重播，动态reduce与CSS兜底静态。主导航不循环。源文件/呈现链、失败记录、资产与验证见[Wayfinder 01](../design/wayfinder-v1/README.md)，[任务卡](../tasks/logo-wayfinder-20261004.md)。

Web严格类型/293模块构建、Node29/29、Edge16/16（51.0s）通过；JS gzip151.00KB，无新增依赖，既有Zod提示保留。独立Edge图标/动画核验通过，报告/实际录制/桌面窄屏截图`artifacts/brand/wayfinder-v1/`；平台导航实图已查看，浏览器产物`artifacts/playwright/85c0fff9-fc9c-43b4-a0e5-0ab9c2e9c911/`。仅改品牌呈现，本轮未重跑无关后端；上轮完整门禁快照保留。先前构建/单元spawn EPERM与校验器属性匹配失败均记录后重跑通过，不隐瞒首次失败。

本机Fake course_demo预览（执行会话97349）已为发布检查停止；此前展示页/SVG HTTP200且IAB打开重播通过，恢复预览可使用下方已有course_demo命令。未调用真实模型，品牌接入无API/Schema/评分变更，不自签整版；负责人明确授权提交推送，发布检查见本文顶部。初版可继续根据负责人反馈迭代。

## 2026-10-04 前端页面可用性复核

负责人要求继续从前端页面优化角度重新审视。需求V0.6、UI规范1.3不变，按[任务卡](../tasks/frontend-usability-20261004.md)只调整已实现呈现，保护原工作区修改。实际IAB查看配置/结果/对照页面，发现历史输入缺label/Enter、导航缺可访问选中态、单次主操作早于配置、八张结果卡压低流程与对照次要设置常驻。

已修正：HistoryReader复用原GET入口，持续label/Enter且不自动运行；nav当前模式、skip link与main/Trace焦点；启动摘要移至模型/Runtime/更多设置之后；EpisodeSummary仅展示保存Artifact，Fake/真实来源与Token模拟标记准确、四核心指标、失败原因常驻、费用/版本按需展开并直达调用过程；对照details保留Seed/重复/预算摘要，非法Seed说明禁用原因，多选任务group与完整描述。复核补修页内hash引发popstate重读/丢焦点，改用实际ref焦点/滚动、URL不变；运行与断线使用streaming布局，避免无最终Artifact时隐藏已收到Trace，保存ID/未知状态不伪造成功。无API/Schema/评分/运行条件变化，无新增依赖。

新增前三条与原浏览器用例14/14（50.6s）通过；首轮完整门禁浏览器14通过/1条页内跳转焦点失败，已定位修正，未称通过。断线隐藏用例先复现失败，再修布局；专项5/5（18.4s）通过。最终完整共享门禁全部通过：Ruff格式/lint、mypy96文件、pytest298（66.42s、1条既有警告）、四套Fake22格零退化、24上下文案例预期一致、Web严格类型/293模块构建、Node29/29、audit零漏洞、Edge16/16（44.1s）、diff检查。JS gzip150.95KB，无新增依赖；既有Zod构建提示保留。

质量产物`artifacts/quality/d3fd261d-f5c6-46dd-8f02-46b4dada019a/`，门禁浏览器`artifacts/playwright/4706c259-4326-47f0-9ffc-a09b9940c4a3/`。门禁后仅修截图测试的回页首定位（断言scrollY=0），生产代码不变；类型与全16条Edge补验通过，HTML报告45.78s、0失败/跳过/不稳定。最终桌面/窄屏/流程/断线截图与录像在`artifacts/playwright/8182346e-75be-4db6-b4f1-55d45d05a0cf/`，桌面/窄屏实际查看正确，报告`artifacts/playwright-report/index.html`。自有服务退出，8000/5173/8765无监听；`.env`和截图Git忽略已核对。

源码顺序、调用链、状态/失败和后续可用性潜力见[页面优化交接](../learning/frontend-usability-20261004.md)。未读取Key或调用真实模型，未提交/推送/发布，不自签版本。真实200%/Windows系统动效、第二台机器/现场与远端CI待验保留。

## 2026-10-04 桌面连续动效（上一轮快照）

负责人授权先调研桌面动效再直接开发。已核对需求V0.6/UI规范1.3；一手来源为Apple响应性、Fluent/Windows时长及MDN原生动画，取短时、平滑减速、可打断的局部反馈。调研和决策见[研究记录](../research/desktop-motion-20261004.md)，范围见[任务卡](../tasks/ui-motion-20261004.md)，无核心接口/Schema/评分变化或新增依赖，不改变当前产品阶段。

实现CSS时长/曲线Token、两项导航与三项Replay连续滑块、main/Replay/故事步骤共享useContentMotion；新操作从未完成动画的当前呈现值接续，旧动画/媒体监听清理，状态与URL立即按原规则变化。原生details配置/历史/工具详情支持intrinsic-size时平滑伸缩，否则即时展开；按钮按压/桌面任务悬停有小幅反馈。不拦截滚轮/触控，动态reduce取消JS/SVG与非必要位移；animate缺失/抛错静态降级。

新增三条Edge用例，独立11/11（38.8s）通过；视频配置首轮放describe被拒绝，已修正并如实记录。快速切换/中间滑块采样、键盘/焦点、展开草稿保留、动态reduce、动画API故障及原有四视口/只读/错误路径通过。最终共享门禁全部通过：Ruff格式/lint、mypy96文件、pytest298 passed（59.86s、1条既有依赖警告），四套Fake22格零退化、24上下文实验预期一致，Web严格类型/291模块构建、Node29/29、npm audit零漏洞、Edge11/11（33.2s）、diff检查通过。JS gzip149.73KB，既有两条Zod构建提示未屏蔽。

最终质量目录`artifacts/quality/52244c2f-7ee4-453d-bb53-52db7e073d60/`，浏览器`artifacts/playwright/4f370c51-a6b3-46fe-9b4c-05d1b3cdd2d2/`，录像在`results/motion-continuous-desktop--d1abe-motion-preserve-saved-state/video.webm`，HTML报告`artifacts/playwright-report/index.html`。测试服务已退出，8000/5173/8765监听数0；录像与实验产物保持Git忽略。离线预览复现命令见下方动效交接。

源码阅读/调用链/生命周期/失败与本机录像见[动效交接](../learning/ui-motion-20261004.md)。本轮Fake验证，无Key读取或新真实模型调用，未提交/推送/发布；原未提交修改保留。实机手感、真实200%/Windows系统动效、第二台机器/课程现场和GitHub/Chromium CI仍待验，不自签V0.2/V0.3。

## 2026-10-04 已实现能力优化（上一轮快照）

负责人要求在暂时没有人工验收时间的情况下优化现有能力；本轮按Accepted [ADR-024](../adr/ADR-024-existing-capabilities-integrity.md)与[任务卡](../tasks/optimization-20261004.md)实施，不扩大V0.3功能。需求仍是V0.6，UI规范1.3。

已修复：显式上下文策略参与每侧比较指纹，旧缺省/null指纹兼容；完整结果复用核对ID/事件归属、有安全点时核对Agent/Task/RunConfig/双方哈希；坏JSON可从有效安全点重建，错身份/来源保留记录并明确拒绝、不遮住有效安全点；Context CLI保存既有Fake场景来源，失败重跑新ID保持原配置；ContextReport交叉核对24矩阵、文件身份/哈希/单变量/Trace链/用量与诊断，不只信完成标记；消息构造后复查时限，不再发过期调用。减少动效时不生成SVG数据包动画，媒体偏好变化即时生效，保留手动回放。

新增12项测试先全部复现失败，修复后12 passed（6.24s），另补两项Trace/报告同时错计数的检查。首轮完整门禁后端296项及22格回归/24上下文实验通过，前端未使用导入失败，已修正并完整复跑。最终共享门禁全部通过：Ruff格式/lint、mypy96文件，pytest298 passed（61.68s、1条既有依赖警告）；旧四套22格零退化；24上下文实验预期一致；Web严格类型/290模块构建、Node29项、npm audit零漏洞、Edge八条24.1s、diff检查通过。浏览器真实CLI→真实隔离API GET→只读网页→按原策略失败重跑，新ID/原文件不变；390/768/1280/1440px画布、无横向溢出、导航、键盘切帧和动态减少动效通过。

最终质量目录`artifacts/quality/c35f95ef-fe9f-48c3-b045-d4d764504613/`，浏览器`artifacts/playwright/65b1d25e-eabc-4421-9cfc-8ce248a4009d/`，HTML报告`artifacts/playwright-report/index.html`。成功/窗口1失败/窗口2成功的本机ID、预览命令和截图边界见下方学习交接。测试服务已退出，8000/5173/8765监听数0，`.env`与实验产物仍被Git忽略。

源码阅读顺序、调用链、状态变化、失败路径、最短人工核对见[优化交接](../learning/existing-capabilities-optimization-20261004.md)。仅历史无安全点结果维持旧Schema只读兼容，不重算旧配置哈希；完整性核对不是密码学认证。没有读取Key、真实模型调用、Git提交推送或发布，既有未提交改动保留。V0.2/V0.3未整版签收；真实200%/Windows系统开关、第二台机器/现场与远端CI仍待验。

## 2026-10-04 V0.3 上下文管理首切片（上一轮快照）

负责人明确要求开始V0.3，已完整核对需求V0.6，先修订当前阶段/受控例外、建立Accepted [ADR-023](../adr/ADR-023-context-management-first-slice.md) 和 [任务卡](../tasks/V0.3-context-management-first-slice.md)，再编码。V0.2仍未整版签收；下方“先收尾、不提前V0.3”是此前快照，本次例外仅覆盖上下文管理首切片，不自签旧版本。

新增严格ContextPolicy1.0与显式AgentSpec1.2；默认旧配置不产生字段、哈希/基线不改写。Session请求投影保留初始system/user及完整工具轮次，两调度器共享规则；协议错误在请求Provider前停止；消息深拷贝，完整历史继续保存/Checkpoint恢复。MODEL_REQUESTED仅显式配置扩展context诊断，外层Schema/评分不改。既有恢复/Runtime对照固定相同context_policy，拒绝混合变量。Web校验和只读历史标注已同步，API/Web新建入口暂未开放。

CLI `uv --cache-dir .uv-cache run --locked python -m scripts.context_ablation` 固定001/007、Seed1/17、两个Runtime、full/窗口1/窗口2，共24Episode，使用正式Runner/Environment/Evaluator/Artifact；诊断报告单独版本化，不冒充Experiment/真实模型。20成功、4个窗口1文档失败符合预期；订单各策略1608字节/2模型/2工具，文档full与窗口2为2984字节/3模型/3工具，窗口1因Fake遗忘循环5562字节/6模型/5工具，max_tool_calls_reached（沿用MAX_STEPS）停止。字节仅序列化消息，模拟Token仍40/20每调用，不是tokenizer或HTTP包大小。

最终完整共享门禁已通过：Ruff/mypy95文件、pytest284 passed（55.95s、1条既有依赖警告）；旧四套Fake2/8/8/4零退化；新24实验预期匹配；Web严格类型/290模块构建/Node29项、npm audit0漏洞、Edge七条21.2s、diff检查通过。新增专项由真实CLI生成的产物在HTTP读取边界供页面回放，策略/评分失败/终止/技术Trace及零POST通过；不宣称新建上下文API可用。首轮后端两条工具次数断言与专项评分文案断言失败已修正并完整复跑。离线预览现在验证ContextReport后复用原Fake服务；不读取Key或接管占用端口。

最终质量/上下文产物 `artifacts/quality/4b8e0fdd-4732-46ac-87c7-267d425bcec8/`；浏览器与截图 `artifacts/playwright/72e37303-6bbc-45be-8995-ea0f1e9d35a0/results/acceptance-actual-context--f53f6-and-failed-read-only-replay/context-history.png`，HTML报告 `artifacts/playwright-report/index.html`。首次完整门禁目录 `612751c6-c603-4978-8dc7-26c0bf0a46ae` 保留并供学习文档示例回放；独立产物 `artifacts/context-ablation/verified-20261004-a/`。自己的服务已退出，8000/5173/8765监听数0。

源码阅读/调用链/状态/失败/命令及本机可回放ID见[学习交接](../learning/V0.3-context-management.md)。本轮没有真实模型调用、Key读取、提交推送或Tag发布，原V0.2未提交修改保留。下一切片：显式上下文单变量Experiment/API/Web（先ADR，含Job/历史/看板身份兼容），再选定免费模型小样本与更长任务；Planning/Memory/Reflection/LLM Judge/第二框架尚未开始。V0.2最终模型/预算、实机辅助功能/第二台机器/现场签收与远端CI待验不清除。

## 2026-10-03–04 V0.2 收尾：Web 数据边界与自动门禁

按负责人继续依照需求收尾的授权，已完成 Accepted [ADR-022](../adr/ADR-022-web-response-validation.md) 范围。Web 元数据、Episode/Experiment、Job、指标看板、恢复 ID 列表及 SSE 都先校验再更新状态；静态类型从 Zod Mini 消费投影推导。历史/恢复/Job 核对请求 ID，Trace 拒绝重复或错属事件，complete 与已收到的轨迹保持顺序一致。保留历史未知指标、Decimal 字符串、未知费用和未消费来源字段；后端 Pydantic 仍是公开契约来源，没有改变 Domain/评分或公开 Schema。

新增 6 条 Playwright，实际启动隔离 Fake API 和 Web，拒绝复用占用端口，不读取 Key。覆盖新建 Episode→独立评分→Trace→只读回放、坏历史清空旧成功、同 SPA 迟到 Job 受理竞争、错 ID、坏 SSE 和坏恢复列表。统一入口 `uv --cache-dir .uv-cache run --locked python -m scripts.check`；PowerShell 包装及 GitHub Actions 使用同一门禁，官方 Actions 固定 SHA、只读权限、无模型 Secret。

完整本地实跑通过：Ruff format/lint、mypy **91 文件**；pytest **251 passed**（45.00s、1 条既有 Starlette/AnyIO 警告）；Web strict 类型含 E2E、**290 modules** 构建；Node **28/28**；Edge Playwright **6/6**（17.7s）；四套 Fake **2/8/8/4 cells、零退化**；npm audit **0 vulnerabilities** 和 diff 检查通过。JS gzip **149.11 KB**，相比上一轮增加约11.46 KB。构建仍有两条 Zod 源码注释的 Rollup 提示，未屏蔽。

完整门禁证据：`artifacts/quality/b5aa5fad-9cf2-4bcf-85b8-c52bfb931f47/`；浏览器 API 产物 `artifacts/playwright/75d8e52f-4c63-4569-9965-ca35a0770f2f/api/`，报告 `artifacts/playwright-report/index.html`。锁定 Chromium 首次启动在本机报 WinError 14001、未进入页面；实际用已安装 Edge 验证，不修改系统库。**GitHub/Chromium CI 尚未运行**，不能据本地通过宣称远端已绿。测试结束自己的服务已退出，8000/5173/8765 无监听。

10-04 交接前最终配置增加内部 run ID 的 UUID 检查，strict 类型与六条 Edge 用例再次通过（26.4s），产物 `artifacts/playwright/7cd69255-405e-448c-8248-f9188a0b7a57/api/`；YAML 解析与工作流静态检查通过。最新 HTML 报告已更新，最后核对项目端口监听数为0。仅文档更新没有重复真实模型或重跑全部后端。

源码阅读、调用链、状态/失败路径、依赖选择和最小实验见[学习交接](../learning/V0.2-web-boundaries-automation-20261003.md)，执行与验收见[任务卡](../tasks/V0.2-web-boundaries-automation-20261003.md)。本轮没有新的真实模型调用，没有提交/推送、Tag/发布；上一轮未提交的修复仍保留。**V0.2 未整版签收**：最终免费模型和全局 Token 继续延期；当前机器真实200%/Windows系统减少动效、第二台机器与课程现场签收仍待补验。下一步先运行发布后的远端门禁并完成实机/现场核对，再由负责人决定模型/预算收口；不提前增加 Docker、数据库或 V0.3。

## 2026-10-03 再次复核：状态正确性与 Job 持久受理

按负责人再次检查并继续推进的授权，已修复 Token 超限漏记本次费用/未知标记、Job 创建/控制迟到响应夺回导航、暂停 Job 恢复时遗留加载、旧 Job 状态短暂错配新 ID、failed Job 被误列为可恢复。提取前端 RequestGeneration，所有历史/运行入口统一判断页面请求归属；后端执行不会因页面离开而被宣称取消。

新增 Accepted [ADR-021](../adr/ADR-021-durable-experiment-acceptance.md)：202 前先保存既有 Checkpoint 1.0 固定计划，再保存 queued Job，队列仅携 ID，首次执行和恢复统一读取计划。第三个 Job 等待执行槽位时退出进程，现在可重启恢复原矩阵；旧无计划孤儿可直接取消。两文件不是事务，计划写成但 Job 写失败时不返回 202，有效计划可经非 Job 入口恢复。没有数据库或新公开 Schema。

历史详情增加 Episode 内部 ID，以及 Experiment ID/config_hash/Pair 数量校验；两个 GET 移至线程读取。Experiment 的坏 Episode 最终 JSON 仅在有效安全点存在时恢复，完整但来源不同拒绝复用；预算耗尽时坏文件不能假冒可免费复用结果。未新增完整 Episode 配置哈希校验，旧 Experiment 1.0 继续可读。

最终实跑：Ruff format/lint、mypy **89 文件**、pytest **251 passed**（1 条既有依赖弃用警告）；Web **196 modules** 构建、Node **13/13**、`git diff --check` 通过。四套 Fake 固定回归 **2/8/8/4 单元、零退化**，最终报告在 `artifacts/recheck-state-final-regression-20261003/regression-reports/`。子进程实际退出覆盖第三个 queued Job，故障注入覆盖两次持久写入各自失败、错误来源和坏 JSON 恢复。首轮新增测试场景名称错误已修正并全量重跑，不把失败隐去。

浏览器 Fake 新实验 `be9750ea-2503-42cd-9640-e668f8ba7b0d` 为 Baseline 0/1、Recovery 1/1；单次 SSE `05764436-f421-404c-b2c5-b7a0482603d8` SUCCESS、17 事件、2 工具，输入/输出/专注视图正常。8 秒延迟的受理响应没有覆盖期间打开的看板历史；暂停 Job `6a514a12-63aa-4b82-b18c-213d7aa9e3a8` 恢复期间后退没有卡住页面，前进可 GET 回读同 ID 已完成结果。截图 `artifacts/recheck-ui-20261003/fake-flow.png`。实际细节、阅读顺序、调用链、状态与失败路径见[学习交接](../learning/V0.2-state-integrity-recheck-20261003.md)，范围见[任务卡](../tasks/V0.2-recheck-state-integrity-20261003.md)。

可继续 V0.2 的前端 API 边界运行时校验、交互自动化和统一自动门禁收尾。**整版仍未签收**：全局 Token 与最终免费模型清单按负责人决定延期；本轮没有新的真实模型调用，真实 200%/Windows 减少动效、第二台机器与课程现场签收仍待完成。数据库需要单独 ADR 和授权；不推进未签收版本之外的功能。临时延迟仅在忽略的诊断脚本里；本轮 API/Web 已停止，8000/5173/8765 无监听，临时浏览器页已关闭。

## 2026-10-03 严格架构与 UI 复核（上一轮已发布）

本轮按负责人“发现问题自行修改”的授权，对既有 API、模型入口、历史状态、流程动画与离线回归做跨模块复核；修复结果见 [任务卡](../tasks/V0.2-architecture-audit-20261002.md)、[ADR-020](../adr/ADR-020-local-browser-origin-boundary.md) 和[源码阅读/实验交接](../learning/V0.2-architecture-audit-20261003.md)。本地 API 原通配 CORS 可被外部网页利用，现仅接受固定 localhost 浏览器 Origin，并在路由前拒绝不可信 GET/POST；CLI 无 Origin 仍可用，API 必须保持 loopback。`/v1/models` 公共目录并不证明 Key 可调用，真实模型 UI 不再展示无法通过后端白名单的自定义入口，文案与带日期的模型说明改为如实表达。目录查询从事件循环移出并加锁复用，避免一次慢查询卡住其他 API 请求。

Web 的单次/对照切换现在保留 URL 所指结果与空态，浏览器前进后退可还原；恢复和重跑迟到响应不再覆盖新导航。实时流程图新增工具节点时重新适配画布；超时等非 SUCCESS 终态的输出卡显示失败。没有修改 Domain/Runtime/Evaluator、核心 Schema 或评分口径，没有读取或提交 Key。

最终质量门禁：Ruff format/lint、mypy **88 文件**，pytest **233 passed**（1 条既有 Starlette/AnyIO 弃用警告）；Web **195 modules** 构建、Node **11/11**、`git diff --check` 通过。受限沙箱中 pytest 临时目录权限拒绝导致复跑失败；换新隔离目录及可访问进程后全量通过，不把环境失败隐藏成通过。四套 Fake 固定回归分别 **2/8/8/4 单元、零退化**；报告在本机忽略目录 `artifacts/audit-regression-20261003/regression-reports`。浏览器隔离 Fake 新 Episode `1f55646f-e069-468b-bce0-f5789419c706` 为 SUCCESS/评测通过/17 事件/2 次工具；延时 Fake 检查实时画布 3→4 节点、两阶段均在视野内。MCP 成功/超时失败/对照历史回放、URL 导航与 390/768/1280/1440 CSS px 抽查通过。MCP 输入/输出与流程截图在本机忽略目录 `artifacts/audit-ui-20261003/`。本轮没有新的真实模型请求；临时预览已停止，8000/5173/8765 无监听。

V0.2 **尚未整版签收**：全局 Token 与最终免费模型仍按负责人决定延期，真实 200%/系统级减少动效、第二台机器及课程现场签收待办；本轮没有自动提交或推送。原 `2026-10-01` 段落保留为当日快照，涉及旧模型目录/验收状态时以本段与带日期的新记录为准。

## 2026-10-01 UI 复验与课程案例固化（当日快照）

按负责人接续授权完成固定 Fake 演示生成器 `scripts/course_demo.py`：正式 EpisodeService 跑成功、一次参数纠错对照、40ms 总时限/250ms 人为等待、真实子进程安全点退出后同 ID 恢复，以及独立 localhost MCP HTTP 本地/远程一致性与固定断线。八个 Episode、一个 Experiment；校验终态与独立评分，失败非零退出、旧目录拒绝覆盖，输出仅诊断索引不新增核心契约。`--preview` 一条命令启动隔离 API/Web，拒绝已有占用端口、只停止自己启动的进程；演示 API 只展示 Fake 并在创建 Provider 前拒绝真实请求，不读取 Key。生成时 MCP 服务 finally 停止，回放只 GET。

完整实跑产物目录 `artifacts/course-demo/verified-20261001`、索引 `demo-index.json` 标记 `mcp_http_verified=true`。实验 `fb6d1263-3f4f-4d84-a87d-a8aacad55cfe` 基线0/1、恢复1/1；时间终止 `267b3e72-0b21-4322-b158-557fae931fe3` 0工具、未知费用；同ID恢复 `c49d6348-bc4a-437e-a063-594a6a37ac72` 查询一次/提交一次/18事件；MCP成功 `9ac57a59-9572-4014-b6d9-59c8f61a54a4`、断线失败 `0caaf54e-4881-455d-b92e-5534b8a3b7a1`。首轮误认为本地 submit 保存 transport=local 的验收断言已按实际字段省略修正，部分产物保留，没有改变 Trace Schema。

浏览器复现并修复历史读取404后残留旧成功：两类历史请求发起时清空对应产物并先更新请求URL；迟到响应序号防护保留。Episode/Experiment失败均无旧动画/表格/通过率；5轮模式切换、连续后退/前进后URL与产物一致。统一辅助色到#625f59，修正选中浅色背景的文字对比度；任务类别/说明/限制14px、流程工具ID/署名12px。单次/对照/失败/技术视图计算色组合扫描最低抽样4.69:1，无低于普通文字4.5:1发现，不是完整WCAG认证。390/768/1440px页面无横向溢出，任务Tab可见焦点、专注查看/Esc、恢复事件筛选实测可用。截图 `artifacts/ui-freeze-20261001/mcp-focus.jpg`、`mcp-mobile.jpg`。真实200%与Windows系统减少动画工具未能控制，仍未验；跨电脑说明已写但没有第二台新机器实装，三分钟视频未录制。

最终 Ruff format/lint、mypy **86文件**、pytest **225 passed**（1条既有Starlette/AnyIO警告）、Web **195 modules**、Node **11/11**通过。四套Fake固定回归沿用本日上一收尾的2/8/8/4 cells零退化证据；本轮没有修改Runtime评分或新增真实模型调用，没有提交/推送。新MCP轨迹全程播放到11/11，预览日志只有GET；验收后关闭本轮临时浏览器页、重置视口并停止自己启动的预览，8000/5173/8765均无监听。换电脑/启动/三分钟讲解与案例结果见 [课程交接](V0.2-course-demo-20261001.md)，源码顺序/调用链/状态/失败边界见 [阅读指南](../learning/V0.2-course-demo-freeze.md)，执行范围见 [任务卡](../tasks/V0.2-demo-freeze-20261001.md)。全局Token、最终免费模型、剩余实机检查和负责人现场签收继续待办；数据库仍待新ADR，V0.2没有整版签收。

## 2026-10-01 产品收尾实现（上一轮）

负责人明确延期全局 Token 预算与最终免费模型选择，授权推进其余收尾。按 Accepted [ADR-019](../adr/ADR-019-episode-time-budget.md) 已新增可选 Episode 总时限（Budget 1.1、Episode 请求 1.2、Experiment 请求 1.3）；共同 Session 用单调时钟检查并限制模型等待，两种 Runtime 同规则。恢复继承安全点已用时间、排除暂停/进程停机；已开始的同步工具先完成并保存结果，再停止后续动作，不能宣称毫秒级强制取消。未收到模型响应时详情标明上游用量未知，费用总额保持未知，不自动重试。旧未配置时限的 Budget 序列化/哈希不变，旧客户端、CLI、固定回归和历史产物兼容。

Web 新运行默认 300 秒，保存配置与下次草稿分离；历史读取按钮准确显示读取状态；历史看板默认折叠，配置组附 Seed/重复/短键；Token 标签如实改为每次运行，未补全局拦截。动画增加浏览器全屏专注查看，桌面输入/输出并排，实际容器尺寸驱动画布缩放，窄屏可滚动；保留播放/逐帧/速度/可选记录，不虚构协议报文。

实际验证：Ruff format/lint、mypy **84 文件**，pytest **221 passed**（1 条既有 Starlette/AnyIO 弃用警告）；Web **195 modules**，Node **11/11**。四套 Fake 回归 2/8/8/4 cells、0 regressions，报告 ID：`a1353459-3e1e-46f9-abe9-dd2a1d9e471f`、`ec27e907-0f21-4e83-bad1-821812c548a0`、`baf4ee0b-6d25-4e93-b8f6-2b39873c957d`、`7ba2f1d4-720d-4c6b-8058-e7e0c95b81ae`，位于本机忽略目录 `artifacts/closeout-20261001`。Node 在受限环境因 spawn EPERM 未启动，允许子进程的环境复跑通过。

浏览器 Fake 一题对照 `7560ad79-cd43-4341-b139-5bd8fa03de17`：人为每请求延迟 0.5 秒、总时限 1 秒，Baseline 参数错误失败，Recovery `TIME_BUDGET_EXCEEDED`、0 次工具，两侧均未通过，配置回读为 1 秒；历史看板默认折叠且可展开。已有 MCP Episode `0e14e216-ffbf-4165-a4e0-2af8cfdcf97b` 回读通过，11 帧、输入/输出/证据、专注查看/按钮退出/Esc 返回、390×844 无横向溢出和逐帧操作已抽查；最终桌面截图 `artifacts/ui-closeout-20261001/mcp-focus-desktop.jpg`。回放不需要启动 MCP Server 或模型请求。验收结束已关闭临时页并停止本轮启动的 API/Web，人工延迟没有留在运行服务中。

源码阅读顺序、调用链、状态/失败路径、时限边界与后续数据库候选见 [本轮学习交接](../learning/V0.2-product-closeout-20261001.md)，执行范围见 [任务卡](../tasks/V0.2-product-closeout-20261001.md)。数据库只记录为后续 ADR 候选，未建空模块或做数据迁移。本轮没有新增真实模型调用、没有改模型目录/价格表、没有提交/推送。整版仍待全局 Token 实现、最终模型与近期验证入口收口、UI 全矩阵及负责人现场签收；不将本轮通过扩大成整版签收。

## 2026-10-01 产品验收复核快照（收尾实现前）

按负责人要求以产品验收者身份从需求反查源码和实机，完整结论见 [V0.2 产品验收复核](V0.2-product-audit-20261001.md)。V0.2 主要受控工程能力具备，但**尚不能整版签收，并非只差现场签字**：FR-08 的全局 Token 预算没有跨 Episode 累计拦截，§13.3 的 Episode 总执行时限仍缺失。离线 Fake 实验 `1c06b074-86c7-4aaa-af40-3251e1280ef8` 用 `token_budget=200` 完成 2 对/4 Episode，全部成功、累计 480 tokens；现有字段实际是每个 Episode 的预算。Budget Schema 仍无时间字段，单请求网络超时不能替代总时限。补实现前先走 ADR，保留旧字段/产物语义，明确部分 Pair、预算终态、恢复累计和未知用量边界。

本机启动页面后默认为 MiMo V2.6、12 任务/24 Episode；此前新 Key 此型号两次 429，已通过完整双任务的是 GLM 5.3。公共模型目录不能证明 Key 权限；最终免费模型确定后统一配置/页面默认与带日期的真实验证状态。实机历史读取时运行按钮暂显示“正在串行执行”，需与历史 GET 状态分开；MCP Fake 历史动画 11 帧、输入/最终输出、对照历史和明确 404 抽查可用。首屏历史看板占据主视区，推荐后续收拢；系统减少动画、全量对比度/快速切换与本机实际 200% 缩放仍待补验。

本轮新复跑 Ruff format/lint、mypy 83 文件、pytest **203 passed**（1 条既有警告）、Web 195 modules、Node **11/11**，四套 Fake 回归 2/8/8/4 单元均 0 退化。报告 ID 与权限复跑记录见产品审查；现有测试通过不能证明上述缺失要求已实现。没有新增真实模型调用，没有修改业务代码/Schema/模型目录/价格表，没有提交或推送。接续顺序：预算 ADR/实验 → 全局 Token 与总时限实现 → 最终模型入口 → UI/证据收尾 → 负责人现场签收。

## 2026-10-01 新 Key 的四模型最小真实调用（最新）

用户在 AIHubMix 控制台新建 Key，截图所示允许模型为 `xiaomi-mimo-v2.6-pro-free`、`coding-glm-5.3-flash-free`、`coding-glm-5.3-free`、`minimax-m3-free`。本机 `.env` 仅有一条 Key 配置，进程环境变量没有覆盖；本轮未输出、保存或提交 Key。对上述**精确 ID** 串行发送真实 `POST /v1/chat/completions`，不以公共 `GET /v1/models` 判定权限：

| 模型 | 最小文本请求 | 单工具请求 | 项目内固定任务 |
| --- | --- | --- | --- |
| `xiaomi-mimo-v2.6-pro-free` | 两次 HTTP 429，错误类别 `rate_limit` | 未跑 | 未跑；本轮不能判定可用 |
| `coding-glm-5.3-flash-free` | HTTP 200，有内容，87 tokens | 两次 HTTP 200，返回 `report_status` 工具调用；复查参数严格匹配 `{"status":"ready"}`，213 tokens | 未跑；当前不在项目模型目录 |
| `coding-glm-5.3-free` | HTTP 200，有内容，130 tokens | HTTP 200，返回 `report_status` 工具调用，216 tokens | BFCL `bfcl-simple_python_0` 成功，Episode `71f95f63-a92f-492a-9178-bf0b410e97b8`，1 次模型/1 次工具，295/88 输入/输出 tokens；ToolLab `order-status-001` 成功，Episode `35a14662-2a84-43fa-b1a1-bff34a9f9334`，2 次模型/2 次工具，2081/109 tokens |
| `minimax-m3-free` | 三次 HTTP 400，错误码 `no_available_channel`；其中一次省略 `max_tokens` 后仍相同 | 未跑 | 未跑；当前上游无可用通道 |

最小探针位于被 Git 忽略的 `artifacts/diagnostics/model_range_probe_20261001.py`，只打印状态与结构化元数据；GLM 项目内双任务结果位于忽略的 `artifacts/selected-model-results-20261001-newkey-glm.json`，真实 Episode 已持久化。上述结果仅证明此刻的新 Key 可调用两个 GLM，其中只有现有目录内的 GLM 5.3 完成项目闭环；不代表长期配额、所有任务或 V0.2 整版通过。`benchmarks/tool_lab_core/models.json` 仍以不在此 Key 允许范围的 `coding-minimax-m2.7-free` 为默认，且缺少 Flash/M3；在调整目录与默认模型前，网页默认真实模式不能据此判为可用。后续先按需求和 ADR 流程确定模型目录迁移，再对新增模型跑固定 BFCL/ToolLab，复核原厂参考价映射与 UI 展示；本轮没有改核心 Schema、Provider、模型目录或费用口径。

## 2026-10-01 API Key 401 进一步诊断（最新）

用户确认 `.env` 内为 AIHubMix 平台 Key。本机只输出布尔检查：仅有一条 `AIHUBMIX_API_KEY` 赋值，进程环境变量未覆盖；文件值无引号、`Bearer` 前缀或空白。使用同一值向正式 `POST https://aihubmix.com/v1/chat/completions` 发送**无工具、8 token 上限**的最小请求，仍为 HTTP 401；只读取脱敏后的错误类别 `key_invalid`，不保存或输出原始响应、Key。此前两个不同模型、两个固定任务的四次 401 因此不是 Tool Schema 触发。按官方 HTTP 错误表，401 指缺少凭据或 token 无效/过期；模型/IP 限制通常返回 403，余额不足也为 403。项目请求头为 `Authorization: Bearer`，与官方开发者说明一致。结论：当前 Key 在 Chat Completions 鉴权没有通过；应在 AIHubMix 控制台核查当前 Key 状态并重新复制或新建 Key，仍只更新本机 `.env`，然后重跑一条最小真实调用。此次没有成功模型输出，也没有修改 Provider/Schema/评测代码。

## 2026-09-30 新填 API Key 的真实调用检查（最新）

项目根目录的本机 `.env` 已有 `AIHUBMIX_API_KEY`，代码实际读取的是该文件值（进程环境变量未覆盖）；Key 未输出、未入库。当前 Key 外形无引号、Bearer 前缀或空白误填。对 `coding-minimax-m2.7-free` 和 `coding-glm-5.3-free` 分别执行固定 BFCL `bfcl-simple_python_0` 与 ToolLab `order-status-001`，四次上游 Chat Completions 请求均返回 `401`，落地 Episode `31d160dd-1f6b-4aac-9243-615877121a8b`、`1c9195ab-a9be-420e-a4e4-42ef5e32cf98`、`581b5d45-4237-402a-a452-801db1513ac0`、`9b403490-887c-4d56-b3ea-133e7c00762f`，均为 `provider_error: AUTHENTICATION_FAILED`、无模型输出/Token。结果保存在被忽略的 `artifacts/selected-model-results-20260930-keycheck*.json`。脚本退出码为 0 只表示探针运行完成，不能当作模型成功。

`GET https://aihubmix.com/v1/models` 对当前 Key 和故意无效的 Key 都返回 200，因此公共目录中看到四个免费模型**不能证明当前 Key 有调用权限**；旧页面的目录状态会产生误导。官方开发者文档仍要求 `POST /v1/chat/completions` 使用 `Authorization: Bearer`，与当前 Provider 一致。优先由负责人在 AIHubMix 控制台确认 Key 来源、启用状态、到期日、IP/CIDR、允许模型及消费上限，然后只在本机 `.env` 替换/修正并重跑一题；不要在聊天里发送 Key。此前其他电脑/Key 的真实成功证据不能证明新 Key 可用。

## 2026-09-30 本机课程演示与 UI 复验（最新）

当前 HEAD `038a3fa`；本轮改动尚未提交或推送。可直接操作的本机 URL、暂停/恢复/取消 Job ID、截图、复现方法与剩余签收项见 [课程演示交接](V0.2-course-demo-20260930.md)。本机新建 Fake 恢复对照 `23e7dd24-26e5-45ac-bcbd-b97453f60b1e`（Baseline 0/1、Recovery 1/1）和 Fake + 独立 localhost MCP HTTP Episode `ee367faf-5353-41a6-a6ba-a89f09cfb27a`（SUCCESS、24 事件、3 工具）。MCP 传输实跑，模型为 Fake；本轮没有新的真实模型请求。

为实机操作 Job 控制，临时延时 Fake API 创建 `0849fc41-4e10-4e6e-9efa-545d92a6f6c9`（暂停，可恢复）、`bc9e594e-1bee-4100-af93-a0991117f143`（暂停后恢复完成）、`d8cb8f69-d0ce-46c7-8e7b-c682bc343412`（取消）。延时服务已停止、普通 API 已恢复；重启后 GET 状态分别为 paused/completed/cancelled，完成实验 GET 200。延时仅为演示手动控制，不作为性能样本。

本机浏览器检查 390/768/1280/1440 CSS px 均无页面级横向溢出；键盘打开历史、复制 ID 与反馈可用；不存在的 UUID 有明确 404。采样发现任务说明 11.2px、对比度 3.95:1，已在 `apps/web/src/index.css` 调整至 13px 和约 4.98:1。Replay 快速切帧时节点曾短暂隐藏；`McpFlowReplay.tsx` 固定图卡尺寸后，11 帧连续键盘切换均保持五节点可见。UI 规范 §7.1 已修正为 ADR-014 真实 Episode SSE 与 Job 状态的准确边界；`scripts/check.ps1` 已纳入 `apps/api` Ruff 范围。全量对比度、跨模式快速连续切换、真实浏览器 200% 与 Windows 系统级减少动画在本机这轮未完成，历史 Edge/媒体模拟证据见下文，不写成当前 OS 验收。V0.2 整版仍待课程现场观看与负责人签收。

本机质量：BFCL Java 固定缓存初缺导致首轮 pytest 2 失败，执行 `uv run python scripts/import_bfcl_subset.py --suite java` 后哈希匹配 manifest，复跑 **203 passed**、1 条既有依赖弃用警告。四套 Fake 回归 2/8/8/4 单元 0 regressions，报告 ID 为 `8047e69d-cc60-4782-ae11-149be346cf25`、`ea800927-bc88-4b5e-8094-070279e1ba25`、`523db946-9970-4f75-8436-7802fcb5438e`、`93cdf8a9-9f58-4520-b08b-2a8cb22a948e`。本轮 CSS/演示脚本改动后，Ruff format/lint（含 `apps/api`）、mypy **83 文件**、Web 构建 195 modules、Node **11/11** 与 `git diff --check` 再次通过；受限进程内构建和 Node worker 遇 `spawn EPERM`，改用普通进程运行通过。Node 22.21.1 不接受旧 `--test-isolation` 参数，已在验收记录中改为显式四文件命令。此前本机缺少另一台机器的真实产物/截图，不宣称本轮再次查看它们。

## 2026-09-30 Codex 复核 Copilot 补验与提交授权

用户已明确授权检查通过后提交并推送最新代码。独立复核下载CSV：894字节、UTF-8 BOM、3行各21列，侧别/原Episode ID正确，网关费用为空，原厂参考金额正确。已查看768/1440、200%缩放、减少动效与404截图；当前API只读回读真实Experiment和MCP Episode均200，隔离测试Job的旧ID为404，与文档说明一致。减少动效的证据仍仅为浏览器媒体偏好模拟，没有系统级开关实测。课程现场签收不因本次代码提交自动完成。

本次重新运行锁定依赖同步、Ruff format/lint（补含apps/api）、mypy82文件、pytest **203 passed**（1条既有依赖弃用警告），Web构建195 modules、前端**11/11**；四套Fake回归22单元均无退化。新报告分别为 `81b4e411-9b1f-4f13-817a-930fa71630d7`、`20ac0ca4-17e8-4222-865f-49cde6aef018`、`c9fe22ee-ea2f-4058-8d1c-c96b22eda6bf`、`87eb6dd1-bc0f-4af0-9fb1-0767e9b239a2`，保存在忽略目录的regression-reports。未新增真实模型调用。

`powershell.exe -NoProfile -File scripts/check.ps1`仍被系统ExecutionPolicy拒绝；按脚本内容逐项命令复核通过，不修改执行策略。前端初次沙箱构建因子进程权限失败，普通进程复跑通过。已修正文档中的CSV待验旧结论；后续继续准备课程演示，必要时新建暂停/恢复演示Job。本文将随本次提交同步；推送状态以Git远端为准，下面保留此前未提交阶段的历史记录。

交接入口：[V0.2 验收记录的 Copilot 接手任务卡](V0.2-acceptance-review-20260930.md#copilot-接手任务卡)。本次已用普通 Edge 下载并验证21列 CSV，补测 768/1440px、真实浏览器200%缩放、减少动效媒体偏好与历史读取失败；课程演示操作顺序及可回读产物已补入验收记录。当前 HEAD `956437f`；仓库原有实现与文档改动仍未提交，本次不提交/推送，也未调用真实模型。`./scripts/check.ps1` 被 PowerShell ExecutionPolicy 阻止；未绕过策略，改为直接运行脚本内锁定的质量检查命令，结果全部通过。暂停/取消的旧临时 Job ID 当前不可回读，现场演示与用户签收仍待完成。

## 2026-09-30 Copilot 接续实机补验

- 普通浏览器打开 `http://127.0.0.1:5173/?experiment_id=ce712291-37da-45b1-af4c-abb86f5b3116`，下载到 `C:\Users\Netlab\Downloads\agentlabyrinth-experiment-ce712291-37da-45b1-af4c-abb86f5b3116.csv`（894 bytes）。UTF-8 BOM 存在；表头加两条 Episode 数据共 3 行，每行 21 列。`cost_usd` 两侧为空，`official_reference_cost_usd` 为 `0.0008154` / `0.0010038`，侧别为 `baseline` / `recovery`；下载名、CSV 转义及真实浏览器落盘均已核对。
- 普通 Edge 视口复核：768×1000 时页面宽 753px、数据表在局部滚动容器内；1440×1000 时页面宽 1425px、成对表完整显示。Edge 通过实际 Ctrl+Plus 缩放到 200%（DPR 2、CSS 视口 460×464），页面宽 453px，无页面级横向溢出，成对表保留局部横向滚动；Tab 焦点轮廓为 3px 实线。`prefers-reduced-motion: reduce` 使用浏览器媒体偏好模拟验证，匹配为 true，按钮 transition/animation 为 `1e-05s`。此项不是 Windows 系统辅助功能开关的 OS 级验收。
- 保存截图：`artifacts/ui-check/v02-final-edge-768.png`、`v02-final-edge-1440.png`、`v02-final-edge-200pct.png`、`v02-final-edge-reduced-motion.png`、`v02-final-edge-error-200pct.png`。200% 下不存在的 Experiment 返回 404，并显示明确的“未能找到 Experiment …”错误；页面无整体横向溢出。
- 真实 MCP Episode `603b2362-2006-42e7-997c-7bd2804d84dc` 通过 URL `?episode_id=...` GET 回读，刷新后仍显示同一 ID、order-status-007、MCP HTTP 与 25 个事件；观察到的请求均为 GET（200），没有 POST。用于离线单次演示的 Fake Episode `92f1eeba-c76b-4307-a724-b26e6acf7b67` 可回读（SUCCESS、17 事件）；Fake 参数恢复对照 `64de7e32-e985-4e09-82e5-6b3f9e40fff2` 为 Baseline 0/1、Recovery 1/1；Fake Runtime 对照 `57ea7a88-adde-46ca-98ff-8d8ca9f37008` 两侧均成功。
- 暂停/恢复与取消的既有网页验证 ID `aa991b59-b427-4913-b40e-79b790d28086`、`07368374-1ffd-43ee-9e4a-eaecc10913c2`，本次对当前 API 查询均返回 404；保留它们仅作历史测试记录，不作为当前可回读演示产物。可先展示对应 Fake 集成测试与原验收证据；需要现场操作演示时须重建延时 Fake Job 并重新记录 ID。
- 验证命令：`uv --cache-dir .uv-cache sync --locked` 通过；`ruff format --check packages tests scripts`、`ruff check packages tests scripts`、`mypy`、`pytest -q --basetemp artifacts/pytest-temp` 均通过（203 passed，1 条既有 Starlette/AnyIO 弃用警告）；`course-smoke`、`course-four-categories`、`course-runtime`、`course-timeout` 回归分别 2/8/8/4 cells、均 0 regressions；`npm.cmd --prefix apps/web run build`（195 modules）及 `node --test --test-isolation=none apps/web/tests/*.test.mjs`（11/11）通过。直接执行 `./scripts/check.ps1` 因当前 PowerShell 执行策略拒绝而未能启动；没有更改执行策略或使用绕过参数。以上没有产生新的真实模型请求。

下一步：由负责人检查浏览器下载文件与截图并完成课程现场演示/签收；若课程必须现场操作暂停与恢复，先创建新的延时 Fake Job 并保存当前有效 ID。之后再决定是否授权提交或推送。

## 2026-09-30 可靠性实测、四套基线与同配置看板收口

最新结论以本段为准，下方按日期保留历史证据。整版技术复核见 [验收矩阵](V0.2-acceptance-review-20260930.md)，源码阅读顺序、调用链、状态与失败路径见 [学习记录](../learning/V0.2-reliability-closeout.md)。当前受控范围代码与关键验证通过；**课程现场演示与用户签收尚未完成，不自签整版验收，不自动提交/推送。**

可靠性真实小样本已补齐：同一个 MiniMax 免费模型，BFCL Handwritten Episode `0b04b45f-1e23-4bfb-a8d2-e52f09c89545` 成功（298 tokens，恢复无追加模型/提议）；独立 HTTP MCP + LangGraph Episode `603b2362-2006-42e7-997c-7bd2804d84dc` 成功（3433 tokens，已完成搜索/读取不重复）；Handwritten Experiment `ce712291-37da-45b1-af4c-abb86f5b3116` 子进程退出后同 ID 恢复，两侧成功（4723 tokens，Baseline 字节不变）。探针增量结果在 `artifacts/live-resume-probe/`，完整产物也已放至正式 artifacts 供网页 GET 回读。这些补齐旧文中的真实 BFCL/MCP/Experiment 恢复缺口，不推广到所有模型、真实并发或外部写工具。

本轮修复 Job Resume 的共同入口：失败状态在改 queued 前返回 409，避免绕过 Service 终态校验。新增真正子进程退出后的 Fake Experiment Job 恢复测试。网页用隔离延时 Fake 服务实际验证暂停→刷新→同 ID 恢复成功，以及取消→刷新→不可恢复；临时服务已停止，正式 API/Vite/MCP 已还原运行。

固定回归扩至 `course-smoke`、`course-four-categories`、`course-runtime`、`course-timeout`，22 单元，0 退化。四类 Runtime 回归两侧各 4/4；超时两侧各 0/2 是固定预期失败。基线来自实际 Fake 运行，不代表真实模型得分。

按 Accepted [ADR-018](../adr/ADR-018-comparable-experiment-dashboard.md) 收口看板：GET DTO 1.1 新增可选模型/矩阵/故障/参考费用与比较键；复用固定回归协议哈希，只在兼容组比较最近两次成功率百分点、Token、耗时。旧缺来源记录不纳入趋势，损坏、配置哈希错误和 Pair 数量错误跳过并提示；费用未知不补 0。Web 处理刷新取消与迟到响应，并补 390/640/1280px、键盘焦点、筛选/读取失败实机验证；截图在 `artifacts/ui-check/v02-dashboard-{1280,390}.jpg`。本輪未再实测全页面 200% 缩放与减少动效。

最终门禁：Ruff format/lint、mypy 82 文件、pytest **203 passed**（1 条既有依赖警告）、四套回归 22 单元；Web 构建195 modules、前端 **11/11**。CSV 生产函数 21 列生成/解析、BOM/转义/防公式及独立参考金额检查通过；本轮 IAB 点击导出但未返回下载事件，指定 Downloads 未发现新文件，因此新增列的实际下载仍需普通浏览器取证。2026-09-28 旧20列落盘证据不冒充本次21列验收。

下一步：按验收矩阵进行课程现场演示，普通浏览器验证 CSV 下载并补 UI 缩放/减少动效复验，再由用户签收。当前范围无需新增 Runtime/Queue/数据库抽象；实际账单硬上限仍受 ADR-017 条件限制。

## 2026-09-30 原厂参考成本与四类任务回归

用户明确要求到各模型**原厂官网**取价，而非以 AIHubMix 免费价作模型价值。按 [ADR-017](../adr/ADR-017-official-reference-pricing.md) 固定 MiniMax M2.7（输入/输出 $0.30/$1.20）、小米 MiMo V2.6 Pro 与 V2.5 Pro（$0.435/$0.87）、Z.AI GLM-5.3（$1.40/$4.40），单位 USD/百万 Token，输入均按未命中缓存价。来源链接、四个 AIHubMix 精确 ID 映射及限制见 ADR。原厂参考成本写入独立字段，**AIHubMix 实际费用仍未知**，不得称为实付账单或硬美元费用上限；旧产物不追溯重算。Experiment 的可选参考预算只在已完成 Episode 后结算并拦截下一题，在途题可能超额；价格版本漂移和 usage 未知会拒绝恢复。前端与 CSV 区分两种费用。调用链、状态、失败路径及复现实验见 [阅读记录](../learning/V0.2-official-reference-pricing.md)。

MiniMax 免费模型真实小样本：改编 BFCL `bfcl-simple_python_1` Episode `b4602664-9f62-4133-8b58-cf68c3e8c60f` 成功，234 输入/63 输出 Token，原厂参考成本 $0.0001458，网关费用未知。仅是本次真实连通与参考计算验证，非官方 BFCL 分数或长期可用保证。固定 Fake 回归新增四类各一题的 `course-four-categories`，与旧 `course-smoke` 一起由 `scripts/check.ps1` 执行；基线为 Baseline 1/4、Recovery 4/4。完整门禁已复核：Ruff、mypy、pytest **200 passed**（1 条依赖弃用警告），旧回归 2 单元与新回归 8 单元均 0 退化；Web 生产构建 194 modules。V0.2 整版仍未验收，所有本地改动未提交/推送。

## 2026-09-29 截图状态复核与两项未开始工作推进

截图中的五项“部分完成”按 [ADR-015](../adr/ADR-015-v02-partial-closure.md) 与下表复核：Checkpoint 已覆盖 ToolLab、BFCL Python/Java、只读 MCP 和 Experiment 计划恢复，Fake 跨进程测试通过；真实模型只验证过 ToolLab 单题安全点，BFCL/MCP 的真实中断恢复未测。幂等性只覆盖已提交的本地状态与只读 MCP；没有外部写工具的恰好一次保证。受控 Fake 故障注入有超时、空结果、MCP 断线与 Trace 断言，尚无任意故障矩阵。外部 Benchmark 有两类固定 BFCL 改编子集，仍无任意 Benchmark 通用适配器，也不是官方 BFCL 分数。指标看板已读持久化 Experiment、处理损坏与未知费用，尚未提供跨实验趋势/排名。这五项的**当前受控交付范围可用**，原截图若按通用能力解释仍不能标“全部完成”。CSV 已实际浏览器下载验收；美元费用上限仍等待经验证价格表，未知费用继续保持未知。

两项“未做”现在按 [ADR-016](../adr/ADR-016-experiment-control-regression.md) 落地：`POST /api/v1/experiments/jobs` 提交有稳定 ID 的后台任务，最多两个不同 Experiment 并行，同一 Experiment 串行配对；`GET /jobs/{id}` 与 `POST /jobs/{id}/pause|cancel|resume` 使用版本化原子状态文件，在 Episode 边界停止，已完成侧通过原 Checkpoint/Artifact 复用。进程异常结束的运行态读作 `interrupted`；取消保留审计产物但不会进入可恢复列表。失败 Episode 的 `POST /api/v1/episodes/{id}/rerun` 保留原产物，以新 ID 和版本化来源记录运行保存的 Agent/Task/RunConfig；旧 Fake 单次产物若没有场景来源会拒绝，Experiment Fake 产物从已保存 Experiment 读取场景。Web 增加任务状态、暂停/取消/恢复和失败 Episode 重跑入口，运行时 URL 用 `experiment_job_id`，完成后换成只读 `experiment_id`。

固定套件回归：`benchmarks/regression/course-smoke.json` 锁定 Fake 单题模型与配置，保存真实生成的基线 Experiment；`scripts/run_regression.py` 在调用模型前校验 Task 版本、Agent/Prompt/工具/预算、种子/重复、对照轴、场景与故障，然后运行当前版本、逐单元比较成功退化，写版本化 JSON 报告。`scripts/check.ps1` 现自动执行此回归；Fake 结果仅验证工程行为，不代表真实模型能力。未知费用不参与退化判定。跨实验趋势/排名仍待独立设计，不能把这个同协议回归报告称作全局 Leaderboard。

验证：完整 `scripts/check.ps1` **194 passed**、Ruff、mypy、固定回归 2 单元 0 退化；Web 生产构建 194 modules、`git diff --check` 通过。集成测试覆盖两个 Job 并行/第三个排队、暂停恢复复用原文件、取消不隐式恢复、失败 Episode 来源与成功 Episode 拒绝、配置不兼容回归拒绝。浏览器 Fake 单题异步 Job `64de7e32-e985-4e09-82e5-6b3f9e40fff2` 和 12 对批量 Job `349f484c-42e5-49c8-b02d-f1ad7f930f5b` 均完成，URL 从 job ID 切到结果 ID；从批量实验的失败侧 `cf1e098c-2a3a-5aae-b3fc-43fc4bde7b81` 在 Web 点击单独重跑，生成新 Episode `e5093c3f-a827-4b8c-a2d5-4bfb9651c5c7`。Fake 跑得太快，浏览器未抢在终态前点到暂停；暂停/取消的实际生效由带闸门的 API 集成测试证明。本轮未调用真实模型，V0.2 整版仍未验收；调度仅限本地单 API 进程，部署多 worker 前需要共享队列与锁。所有改动未提交/推送。

## 2026-09-29 Codex 复核 Copilot 交付：最终产物原子落盘与跨进程恢复

复核提交 `956437f` 时发现断点恢复的共同失败窗口：最终 Episode/Experiment JSON 直接写到目标路径；进程写到一半退出会留下损坏文件。旧恢复列表只按文件是否存在排除存档，导致有效 Checkpoint 被隐藏。现 `packages/application/trace.py` 的最终写入先写临时文件、同步并原子替换，Experiment 复用同一写入函数；恢复列表只把**可解析的完整终态**视作已完成，旧版半截终态可从有效 Checkpoint 重建。替换失败保留旧完整文件并清理临时文件。

跨进程验收补齐：`tests/integration/_checkpoint_worker.py` 在独立子进程写入 BFCL Python、BFCL Java、MCP 的安全点后直接退出；新 Service 恢复同一 Episode ID，三项均成功并清理 Checkpoint。MCP 测试在子进程用受控远程函数替身完成两次只读调用，恢复侧若重复该读取即失败；这验证持久状态和去重边界，实际 HTTP 网络链路的验证仍以 ADR-012 的独立实验为准。损坏终态文件测试覆盖 ToolLab 跨进程与 Experiment 计划恢复。

验证：`scripts/check.ps1` 的 Ruff、mypy、pytest **187 passed**（1 条既有 Starlette/AnyIO 警告）；Web 生产构建 194 modules、前端聚焦测试 10/10、`git diff --check` 通过。本轮只改 Python 持久化边界、相关测试和文档；未重新调用真实模型或做本轮浏览器视觉验收，因此不把此次结果写成新的真实模型结论。V0.2 整版未验收，外部写工具仍无恰好一次语义。本地改动未提交/推送。

## 2026-09-28 V0.2 五项部分能力接续

以下为 2026-09-28 的历史状态；当时写为“仍待实现”的实验控制与回归已在本文顶部更新。

依据 [ADR-015](../adr/ADR-015-v02-partial-closure.md) 收口截图中的五项，当前证据与边界如下：

| 项目 | 本轮可用能力 | 验证与边界 |
| --- | --- | --- |
| Checkpoint/Resume | 单 Episode 扩至 BFCL Python/Java 单调用与固定文档 MCP；Experiment 持久化运行矩阵，恢复时复用已完成侧，同 ID 继续未完成侧。 | ToolLab 已有 Fake 跨进程和 MiniMax 真实安全点验证；BFCL Python/Java、MCP 的 Fake 跨进程验证见 2026-09-29 记录；Experiment 有中断、重启 Service、API 恢复与篡改拒绝测试。BFCL/MCP 真实模型中断及 Experiment 操作系统进程退出仍未实测。 |
| 幂等性 | 当前 ToolLab 本地状态与 BFCL 非执行提议在安全点不重放；MCP 工具仅只读，完成后恢复不重复已提交读取。 | 不存在可验证的外部写工具，不能宣称对任意外部写的恰好一次保证；未来引入写工具须服务端幂等键或事务协议。模型请求中断仍可能重发、增加上游用量。 |
| 故障注入 | Fake 单次/成对实验可选择工具超时、查询空结果；固定文档 MCP 单次可选择本机断线。故障名随 Task 和 Experiment 保存。 | 集成测试核对 Trace 失败码、终态、两侧相同故障配置及真实模型禁用注入；这不是外部网络故障的全面模拟。 |
| 外部 Benchmark | 在原 BFCL `simple_python` 8 题外，接入同一固定上游提交的 `simple_java` 5 题；两套 Manifest、原始及转换 SHA256、独立 suite 标签。 | `python scripts/import_bfcl_subset.py --suite java` 可重复导入；Java 恢复测试通过。真实 MiniMax 在 `bfcl-simple_java_18` Episode `104c043a-6f7a-4887-ad6e-02305b142f71` 得到 SUCCESS、`exact_call_match`、1 模型/1 工具。仍是本地改编评分，非 BFCL 官方分数，也不是任意 Benchmark 的通用运行器。 |
| Trace/指标看板 | Web 读取持久化 Experiment 列表，逐实验展示两侧成功率、Token、平均耗时、费用并可回读；损坏产物跳过且提示，不跨协议排名。 | Dashboard GET 集成测试保证只读、损坏文件不遮蔽有效实验；前端生产构建通过。未知费用保留“未知”，不按 0 计。 |

复核时独立运行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\check.ps1`：Ruff、mypy、pytest **183 passed**（1 条已有 Starlette/AnyIO 弃用警告）；`npm.cmd --prefix apps/web run build` 通过（194 modules）；BFCL Java 导入校验产出 5 题且转换 SHA256 与 Manifest 一致；新增前端聚焦测试 10/10 通过，`git diff --check` 通过。真实浏览器从当前 API 读取 25 个任务（ToolLab 12、BFCL Python 8、BFCL Java 5），Java 套件呈现 5 个任务，卡片明确标为“本地函数调用提议评测”，不暗示执行上游函数；Fake SSE 单次 Episode `7a1ac771-54c3-454c-a8b7-c8ac4917a6e3` 为 SUCCESS、2 模型/2 工具、17 事件。刷新和前进/后退回到同一 Episode，相关请求均为 GET、没有重新 POST；实验看板实际显示 8 条记录且无损坏提示。1280px 与 390px 浏览器视口均无整体横向溢出，截图在被忽略的 `artifacts/ui-check/codex-dashboard-{1280,390}.png`。这些是 Fake/UI 与固定数据验证，不是新的真实模型实验；V0.2 整版的暂停/取消、并发、失败任务重跑、自动回归和经验证价格表的全局费用上限仍待实现。

## 2026-09-28 V0.2 已实现能力收口：真实恢复与 CSV 下载

以下为 2026-09-28 的历史状态；后续进展以本文顶部为准。

按 Accepted ADR-011 的现有范围，用 `scripts/probe_live_checkpoint_resume.py` 对当前 Key 目录可见的 `coding-minimax-m2.7-free` 做一题真实 ToolLab 中断恢复。子进程首次提交查询工具后退出，新进程从同一 Checkpoint 继续；Episode `f4bba2a4-68c7-418f-8b15-096989bfd7e0` 最终 SUCCESS、Evaluator true，累计 2 次模型、2 次工具、2373 tokens、18 事件。原查询未重跑：2 个 `TOOL_STARTED` 的 Call ID 唯一，Trace 父链完整，`EPISODE_RESUMED` 和 `EPISODE_FINISHED` 各一次，最终 Artifact 存在且 Checkpoint 已清理。首次尝试使用任务默认 1000 Token 预算，在首个模型响应后 `TOKEN_BUDGET_EXCEEDED`、0 工具；验收脚本现显式设 8000，失败产物仍留在被忽略的 `artifacts/live-resume-probe/`。此为单题小样本，未验证模型请求中途退出的重复计费，也不把 ToolLab 保证推广到外部写工具、BFCL 或 MCP。

历史 Fake Experiment `ad386c5d-6458-4a59-b88b-7ed534b18ae6` 的网页“导出 CSV”已实际点击；IAB 下载事件接口未返回，但本机 Downloads 中出现对应文件。用 Python `csv` 读取为表头 + 2 行，每行 20 列，UTF-8 BOM 正确，`reference`/`langgraph` 侧别正确，Runtime 对照不适用的挽救字段为空。前端 CSV 交互与内容据此收口；没有改 API、Artifact Schema 或评分。

新增探针已通过 Ruff、mypy；全项目 `scripts/check.ps1` 在普通进程通过：Ruff format/lint、mypy、pytest **171 passed、1 条既有依赖 warning**。受限沙箱初跑因 `artifacts/pytest-temp` 的 WinError 5 失败，普通进程重跑通过；`git diff --check` 通过。

V0.2 整版仍未验收。并发、暂停/取消、失败任务重跑、自动回归评测、扩展故障注入、跨实验看板和经验证价格表的全局费用上限仍需独立设计与实施；固定 BFCL 改编子集已是当前外部 Benchmark 接入，不宣称通用 Adapter。下一开发项优先定义暂停/取消的持久化语义，再扩展批量编排；未知费用不可写成 0。现有工作区改动均未提交/推送。

## 2026-09-28 手写 Runtime 调研与 MCP 演示可见性

手写 Runtime 的公开样例、现有实现对照及可行补强顺序见 [调研](../research/handwritten-runtime-examples-20260928.md)。结论是控制循环短属正常，先补 V0.2 取消/恢复/失败路径与对照证据，不为显得复杂而新增抽象。

用户未看到 MCP 协议可视化：现有 React Flow 仅在工具节点写 `MCP`，没有突出两进程网络边界。`apps/web/src/McpFlowReplay.tsx` 对已标记 `tool-lab-mcp-v1` 的 Episode 增加 Client → localhost Streamable HTTP → Server 链路，按实际 Trace 中的远程工具开始/结果/失败高亮；本地 `submit_answer` 不伪装为远程调用。页面明示 Trace 没有记录握手或 `tools/list` 报文，因此这是网络调用链演示，不是协议抓包。历史真实模型 Episode `c302b854-5a35-4ec7-b1b5-749b417e59e0` 可直接回读：浏览器第 3 帧显示 `search_documents · 远程调用开始`，第 4 帧显示结果返回；390px 视口无横向溢出。旧 Fake MCP ID `0e14e216-ffbf-4165-a4e0-2af8cfdcf97b` 在当前默认产物目录不存在，不能再作为直达演示链接；旧失败产物 `a6950cc3-95cc-4ea0-8d70-8e6afa168ad8` 缺少逐工具传输标记，因此不会把失败帧伪称为已记录的 MCP 往返。前端构建 194 modules、流程帧测试 3/3、`git diff --check` 通过；未重跑 Python 全套或调用新模型。

## 2026-09-28 暖色小字可读性

根据用户的过程概览截图，`apps/web/src/index.css` 把步骤编号、分段标签、工具名及“查看本步原始事件”等关键暖色文字提升到至少 14px，并使用现有深陶土色；链接常态显示下划线。同步覆盖页眉提示、任务类别、选中页签和错误标签，规则已写入 UI 规范。390px 浏览器回读已保存的 ToolLab Episode `7eb9bad7-7696-4263-a3e1-2c42988e6b86`，核对 Step 1 标签计算字号为 14px、深陶土色，入口为 14px 且有下划线；页面无横向溢出。深陶土文字在三种实际浅色背景上的对比度为 5.93–7.10:1；前端生产构建 194 modules、`git diff --check` 通过。仅展示层变更，未调用模型、未修改 Trace/评分或提交推送。

## 2026-09-28 单次 Episode 实时 Trace

用户明确要求运行时节点实时出现。Accepted [ADR-014](../adr/ADR-014-live-episode-trace.md) 后保留原 `POST /episodes`，新增 `POST /episodes/stream`，复用同一 Recorder/Runner/Checkpoint 路径顺序发送脱敏 Trace；落盘成功再发完整 Artifact。Web 运行中用现有 React Flow 图根据实到事件增加节点，结束后切到原只读 Replay；断线显示状态未知和 Episode ID。无领域事件、Artifact Schema、Evaluator、模型提供商或依赖变更。源码阅读顺序、状态、失败路径与实验见 [学习记录](../learning/V0.2-live-trace.md)。

项目完整质量门禁 Ruff、mypy、pytest **171 passed**（1 条既有 Starlette/AnyIO 警告）；API 流单元测试 19/19（包括流与 Artifact 完全一致、非法模型无完成事件），Web 流解析 2/2，前端生产构建 194 modules、`git diff --check` 通过。浏览器离线 Fake 成功 Episode `9bd6b972-596c-4572-8f28-381a31c64ba0`；真实 MiniMax/BFCL `99b2bc6f-5452-4e13-a17a-78d36fec4a50` 在请求未完成时可见实时模型/校验节点，最终 SUCCESS；真实 MiniMax/ToolLab `7eb9bad7-7696-4263-a3e1-2c42988e6b86` 最终 SUCCESS。后两者只是小样本，未证明模型长期可用。当前本机 API 已重启加载最终新路由，Web 服务仍在 5173；非法模型的实时错误已通过本机 HTTP 复核为版本化响应。未提交推送，既有未提交改动保留。

## 2026-09-28 BFCL 流程回放与长序列方向

用户指出 BFCL 回放画布空白。浏览器回读真实模型历史 Episode `6af0d696-d26c-4849-a25a-1637d19f3b77`：Trace 有 10 个事件、1 次 `solve_quadratic_equation(a=2,b=6,c=5)` 提议，`flowFrames` 已生成 5 帧及 3 个节点；空白不能归因于无事件。React Flow 原允许拖动画布，可能将全部节点移出可视区；现关闭拖动平移，保留缩放和适应画布控件。另发现 BFCL Observation 保存的是 `question`、终态保存的是 `proposed_call`，旧 UI 只读取 ToolLab 的 `description`/`submission`，误称两端未保存。`apps/web/src/McpFlowReplay.tsx` 现按 BFCL 保存字段显示原题、函数名和参数，并把执行阶段标为“记录函数调用/调用已接收”，避免将非执行型 BFCL 改编任务说成实际运行了上游函数。ToolLab 文案和数据路径保留。

阅读顺序：`packages/environments/bfcl/environment.py`（只校验和记录一次提议）→ `apps/web/src/flowFrames.ts`（按已保存事件生成帧）→ `apps/web/src/McpFlowReplay.tsx`（首尾卡、节点、播放状态）→ `apps/web/src/App.tsx`（按 Episode ID 重建回放组件）。调用链为历史 GET/运行产物 → Observation/Trace/final_state → 流程帧和 BFCL 首尾字段 → 只读 React Flow；失败时无 `proposed_call` 就显示“未保存函数调用提议”与真实终止原因，不补造函数执行结果。验证：Flow Node 测试 3/3、前端生产构建 193 modules、`git diff --check` 通过；浏览器回读上述成功 BFCL 显示原题、调用节点与 `a=2 · b=6 · c=5`，限流失败 BFCL `23b3bc8d-f0cc-45aa-9f54-324a16be2733` 显示原题、无提议和 `RATE_LIMIT_EXCEEDED`，ToolLab `1f3148a2-3ded-4e78-a02f-c4d39a840859` 仍显示原答案/证据。只读历史产物；本轮未调用模型、未改 API/Schema/评测、未提交推送。

长序列调研与需求 §9.8 一致：当前固定 BFCL `simple_python` 为单调用、最多 1 步。可优先评估官方 BFCL 多轮子集，但需新环境状态、工具反馈与独立评分协议，不能仅扩充 JSON；τ 系列适合多轮用户/业务工具，当前需求建议 V0.3 后接入。其旧 `tau-bench` 仓库已标记任务过时，后续实际选型应核对维护中的 [τ³-bench](https://github.com/sierra-research/tau2-bench) 固定 release。WebArena/BrowserGym 环境和部署更重，不作为近期课程演示主线。选型前锁定上游版本、许可、任务数、改编标签与失败样本；当前没有接入或测出长序列成绩。目前 API `POST /episodes` 等运行完成才返回 Artifact，流程图只读回放已保存 Trace；若“执行时”是指运行过程中实时出帧，则需要另行设计流式事件传输和持久化边界，不能把回放动画冒充实时运行。

## 2026-09-28 BFCL 任务卡中文展示

按用户反馈，单次运行的固定 8 道 BFCL 任务卡改用中文说明，并将类别、开发集/评测集标签统一中文化；搜索同时匹配中英文。仅修改 `apps/web/src/App.tsx` 展示层，API 任务目录、上游英文原题、模型输入、Adapter、Evaluator 与历史 Artifact 均保持原值。页面明确提示“任务卡为中文说明，模型仍接收英文原题”。浏览器已逐卡核对 8 道题的中文内容与原始数值；本轮未发起模型运行。

## 2026-09-28 Codex 复核单次运行工作区

复核 Copilot 未提交 UI 改动时发现并修复：快速 URL 前进/后退可能由较早 GET 覆盖当前产物或过早结束加载；搜索过滤掉已选任务后仍能运行不可见任务；历史摘要缺少部分字段时被误判为请求失败或评测失败；损坏的本地历史列表可能让页面渲染报错；旧版对照实验缺少 `comparison_axis` 时会借用当前草稿变量显示；折叠配置在 768px 时模型名与“修改”过近。修复在 `apps/web/src/App.tsx`、`apps/web/src/historySummary.ts`、`apps/web/src/index.css`，新增 `apps/web/tests/historySummary.test.mjs`。无 API/Schema/评分修改。

浏览器用本机 API/Web 实测：历史 Episode `1f3148a2-3ded-4e78-a02f-c4d39a840859` 保留产物模型 `fake-orders-v1`，下次运行草稿仍为当前 MiniMax；刷新和连续前进/后退回到 URL 对应 Episode/Experiment `ad386c5d-6458-4a59-b88b-7ed534b18ae6`；无效 Episode/Experiment ID 显示错误，深链不展示旧产物。历史回读调用路径只有 GET，本轮未新建运行。搜索隐藏已选任务后按钮禁用；ToolLab 文档任务可选 MCP，过滤/切换到不支持任务后隐藏控件并使用本地，BFCL 选中首个目录任务。键盘 Tab 可聚焦任务卡且焦点描边可见。

390/768/1280/1440 CSS px 的 DOM `scrollWidth=clientWidth`，全页截图复核单列/双列、主按钮、历史行及任务说明；768px 折叠标题间距已修。减少动效 CSS 的全局动画/过渡短路规则已核对。当前浏览器的视口覆盖最小约 240 CSS px，无法独立复现 Copilot 所述的 195px 或真实 200% 缩放；该项仍需在可设置 200% 缩放的浏览器人工看一遍。`node apps/web/tests/historySummary.test.mjs` 1/1、Replay 4/4、流程帧 3/3、前端生产构建 193 modules、`git diff --check` 均通过。未重跑 Python 全套、未调用真实模型、未提交/推送；V0.2 整版仍未验收。

## 2026-09-28 单次运行工作区优化

按 [UI 调研](../research/replay-config-ui-20260924.md#2026-09-28-补充调研停止把配置堆进窄侧栏) 完成单次运行工作区重排。`apps/web/src/App.tsx` 以 API 返回的 ToolLab/BFCL 任务目录提供套件筛选、搜索和任务卡，右侧执行区集中模型/Runtime 与运行按钮；纠错、MCP、步数和 Token 预算收进更多设置，MCP 仅在任务支持时出现。套件切换清空搜索并选中首个可见任务。历史存在时配置折叠标为“下次运行配置”，历史条目读取任务、模型、时间和结果，恢复条目与历史分开；不以历史产物覆盖草稿、不改变 API/Schema/评分口径。`apps/web/src/index.css` 复用现有暖色 Token，加入宽屏双栏、窄屏单列和响应式任务/执行卡布局；`docs/product/ui-design-guidelines.md` 与本研究报告同步记录实施边界。

真实本机 API + Web 的 Fake 浏览器闭环：Fake `order-status-007` Episode `fa71b63d-83ce-42cc-8183-07be14285771` 成功，刷新 GET 回读同一 Episode 和 24 个事件；Fake `order-status-001`、`invalid-then-success` + `handwritten_recovery` Episode `659eecb4-b712-4aa1-a42a-9b627990e667` 回读成功，3 次模型调用、2 次工具调用、21 个事件。浏览器检查任务支持时 MCP 选项出现并反映于摘要，切到不支持 MCP 的任务后控件消失且传输回本地；切换 BFCL 清空搜索，选择 `bfcl-simple_python_0`（development、最多 1 步、本地工具）。后退/前进和刷新回到同一 URL/产物；本轮 URL 回读未观察到重新 POST。真实模型本轮未调用。

验收：390/768/1280/1440 CSS px 的 `scrollWidth` 均等于 `clientWidth`（375/753/1265/1425）；以 200% 等效宽度 195px 检查时两者均为 180px。键盘 Space 可切换到 BFCL 并选中首个任务；`prefers-reduced-motion: reduce` 生效。截图保存在被忽略的 `artifacts/ui-check/single-workspace-{390,768,1280,1440}.png`。`npm.cmd --prefix apps/web run build` 通过（192 modules）；Replay 4/4、流程帧 3/3；`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\check.ps1` 通过（Ruff、mypy、pytest 169 passed，1 条既有 Starlette/AnyIO 弃用警告）；`git diff --check` 通过。无依赖、密钥、真实模型或公共契约变更；未提交或推送。截图交互与视觉仍请 Codex 复核，本轮不代表 V0.2 整版验收。

## 2026-09-27 开源流程动画原型

输入卡片视觉接续：用户反馈首尾输入提示生硬，改为对话图标、“这次要做什么”标题和带名称的搜索关键词/目标订单标签；保留原始描述和值，未改任务语义。浏览器截图核对暖色卡片与关键词标签，生产构建通过，git diff --check通过。

追加用户要求的最初输入/最终输出：图上方首个已保存 Observation 描述与查询/订单条件，图下方 final_state.submission 的答案及证据，开始/结束帧分别高亮；无提交时显示缺失及实际终止原因。不使用评分标准答案，不生成猜测结论。成功/断线两个历史 Fake Episode 浏览器回读验证字段正确，构建及7项回放检查通过。阅读见 MCP-flow-replay.md；本轮无新模型/工具调用，未提交推送。

按用户“画面优先、展示 MCP 工具行为”要求，调研 React Flow/Rete/Motion 后复用 MIT @xyflow/react 12.12.0 开源核心，选择记录在 Accepted ADR-013。新增 flowFrames.ts、McpFlowReplay.tsx、flowReplay.css，默认流程动画；旧概览和技术 Trace 保留。模型→调度→实际工具节点用活动线和移动光点播放，失败为红色，参数折叠。手机纵向显示当前工具。只读已保存事件，播放器不发模型/工具请求，不展示未记录协议报文或阶段耗时；Core/API/Schema/评分无变化。

浏览器新运行 Fake MCP SUCCESS Episode `0e14e216-ffbf-4165-a4e0-2af8cfdcf97b`：Evaluator true、3 模型/3 工具、24 事件、11 帧；搜索与读取显示 MCP，提交本地。关闭本轮 MCP 服务后浏览器新运行 `48a252cb-87f3-4a8c-9fb3-41fb89bdcf69`：FAILED TOOL_EXECUTION_ERROR、9 事件、5 帧，失败返回红色，无后续工具；服务已恢复。播放、暂停、逐帧与进度操作已验证。390px scrollWidth375，无整体溢出。图和字段没有消失：浏览器可访问树会省略视口外节点，DOM 实查节点保持存在；最终截图确认活动路径。

Flow 测试3/3、原 Replay4/4，生产构建192 modules通过，git diff --check通过；官方 registry production npm audit=0 vulnerabilities。gzip JS127.15 KB（此前63.92），CSS8.53 KB。阅读链、失败与截图路径见 `docs/learning/MCP-flow-replay.md`，库对比见 `docs/research/mcp-network-visualization.md`。未重新调用真实模型、未重跑 Python 门禁，减少动效尚未浏览器实测；不宣称 V0.2 整版验收。未提交/推送，需负责人观看动画手感。

## 2026-09-27 单次配置交互接续

追加导航：按用户明确要求，顶部采用暖白 78% 背景、16px backdrop blur，不支持时保持原 96% 背景。将 html/body/root 的 overflow-x 从 hidden 改为 clip，避免 sticky 被祖先滚动容器约束；保留 sticky/top=0，加入 scroll-padding-top。浏览器桌面与 390px 下滚动约 995px，导航 boundingClientRect.top 均为 0；390px scrollWidth=375，无整体溢出。前端构建 28 modules、1.01s 通过，截图 artifacts/ui-check/sticky-glass-390.png。UI 规范记录了用户授权的局部毛玻璃例外。MCP 课设可视化建议见 docs/research/mcp-network-visualization.md，尚未实施协议遥测或新 Schema。

先将 main 从 4d01e41 快进到 GitHub 的 4a57da0，工作区干净后接续已有 UI。Runtime 选择改为原生 radio 卡片，显示 Reference/LangGraph 及调度方式，支持键盘选择、焦点和运行期间禁用。高级设置沿用原生 details，支持 intrinsic-size 的浏览器使用 240ms 高度过渡，不支持时正常展开；减少动效沿用现有全局规则。折叠标题保留当前步数，运行前摘要显示 Task/请求预算、纠错策略及模拟/真实调用性质。历史结果存在时配置标题明确为“下次运行配置”。无新增依赖、API 或 Schema 变化。

本轮实测：前端生产构建 28 modules 通过（1.30s）；Replay Node 检查 4/4 通过；git diff --check 通过。浏览器点击 LangGraph、展开预算、改为 5 步再关闭，摘要保持一致；发起 Fake clean order-status-001 得到 Episode f10abdbe-d599-416f-9740-a69a7b1ac890，Evaluator true、SUCCESS、2 模型/2 工具调用、17 事件。点击查询步骤显示参数、记录与新增证据；URL 刷新回读同一 Episode。390/768/1280/1440px 下 document scrollWidth 分别 375/753/1265/1425，没有整体横向溢出。截图：被忽略的 artifacts/ui-check/runtime-options-390.png。

阅读入口见 docs/learning/UI-runtime-options.md。此轮仅 Fake UI 验证；模型目录显示 unavailable，未重新调用真实模型。减少动效和 200% 缩放尚未浏览器实测，动效手感仍需项目负责人观看；不宣称 V0.2 整版验收。Python 核心未改，本轮未重跑 Python 全量门禁。未提交或推送。

## 2026-09-25 Replay 复核与失败测试

对照需求 FR-05、UI 规范 1.1、ADR-007/012 复核本轮 UI。发现共同根因：旧过程概览只用 `arguments_valid` 判断工具校验，导致 `UNKNOWN_TOOL`/`FORBIDDEN_TOOL` 可能被误标为“通过”；现统一按已保存的 `error_code`、`arguments_valid`、`permitted` 判断，并让失败终态优先于同一步工具成功。缺失上一步快照时明确说无法计算变化；自动播放的播报范围缩至步骤标题，避免重复朗读整个详情。原始技术 Trace 仍保留完整事件与 JSON。

验证：全项目质量门禁 Ruff、mypy、pytest **169 passed、1 条既有依赖 warning**；前端生产构建通过（28 modules）。Replay 单元检查 **4/4 连续 3 轮**，LangGraph 失败边界 **14/14 连续 3 轮**。浏览器回读三条历史产物：Fake `INVALID_ARGUMENTS` 步骤显示工具未执行，MCP `TOOL_EXECUTION_ERROR` 显示真实错误字段和失败终态，BFCL 工具成功但最终 `FAILED` 显示失败；URL 刷新保持同一 Episode，技术 Trace 可查看原始事件。这些是历史回放与离线失败测试，没有在本次复核重新调用真实模型，也不构成 V0.2 整版验收。首次受限进程的 pytest 临时目录权限和 Vite 子进程权限导致启动/测试失败，获准正常进程重跑后上述门禁通过。

## 2026-09-25 Replay 关键字段与失败路径接续

按用户确认，过程概览只呈现理解行动所需的 JSON 字段：初始观察优先任务说明/问题，工具反馈按工具类型选择记录、文档或提交确认，状态区优先证据、提交、结束标志和 BFCL 调用；其他未知工具保留最多四个已保存字段作为兜底。技术 Trace 仍保留完整原始 JSON。MCP 失败时从真实 `TOOL_FAILED.payload.error` 展示错误码、说明、可重试标志，并在步骤顶部标明 `MCP HTTP`；不把通用 `TOOL_EXECUTION_ERROR` 擅自解释成某个具体网络原因。步骤轨道支持焦点在卡片时用左右方向键、Home、End 跳转，焦点与播放游标同步。若同一步工具成功但 Episode 最终失败，步骤结果优先显示已保存的失败终态，避免误导。

阅读顺序：`apps/web/src/traceSteps.ts` 的 `keyFields` → `apps/web/src/App.tsx` 的 `preferredFeedbackKeys`/`visibleStateChanges`/`observationFields` 与步骤轨道 `onKeyDown` → `apps/web/src/index.css` 的 MCP 标签。调用链仍是历史 GET 或单次 POST → 保存 Artifact → 步骤分组 → 从本步实际提议、工具结果及环境快照抽取关键字段；原始 Trace 不裁剪。错误路径以保存的 `TOOL_FAILED` 和 `EPISODE_FINISHED` 为依据；无 `ENVIRONMENT_UPDATED.state` 时明确提示无法确认字段变化。

验证：前端生产构建通过（28 modules）；`node apps/web/tests/traceSteps.test.mjs` **3/3 通过**；网页用已保存 MCP 失败 Episode `a6950cc3-95cc-4ea0-8d70-8e6afa168ad8` 回读：Step 1 显示 `search_documents`、`MCP HTTP`、`TOOL_EXECUTION_ERROR`、`retryable=false` 与 `FAILED`，没有虚构状态变化。该验收副本从 `artifacts/mcp-smoke/` 放到被 Git 忽略的默认 Artifact 目录，仅供网页回读，原始文件保留。Fake Recovery Episode 上聚焦 Step 1 后按右箭头到 Step 2，焦点、下拉框与详情同步；文档任务 `bc4079e8-d881-4f10-b460-6a49c6e29d7a` 的 `read_document` 步骤只呈现 DOC-007 标题、内容、证据 ID 与新增证据。另用历史真实 BFCL 失败 Episode `1090793d-7036-4186-b0aa-ebd75310240c` 检查工具已接受但最终评测 `FAILED` 的步骤，轨道与详情均显示失败；此处只是回读历史产物，并未新调用模型。代码仍未提交或推送。

## 2026-09-25 Replay 可读详情与切换整改

用户复核首版后指出双栏原始 JSON 单调、切步生硬。过程概览已改为同一视图区的“任务观察/模型行动 → 校验与工具反馈 → 环境变化”三段阅读卡：字段名可读、嵌套记录按键值呈现，参数错误明确显示错误码及工具未执行；环境变化只比较前后**已保存**快照，旧产物或失败步骤没有新快照时明确说明不能确认变化。初始状态只显示环境条目数量；每一步可直达对应的技术 Trace 原始事件。技术 Trace 的 JSON、筛选和时间线仍保留。步骤卡选中使用短距离位移与阴影，详情容器通过可打断的原生 Web Animations API 过渡；系统开启减少动效时不播放该过渡。未引入前端依赖，也未改变 API、Artifact 或评分契约。

阅读顺序：`apps/web/src/traceSteps.ts` 的 `groupTraceByStep`/`changedStateFields` → `apps/web/src/App.tsx` 的 `snapshotAt`、`ReadableFields`、Replay 派生状态与 story JSX → `apps/web/src/index.css` 的 `.story-*`。调用链：GET 历史 Episode 或单次 POST → `setArtifact` → 按保存事件分组 → 游标切换 → 提取提议工具、校验、反馈与不晚于该步的快照 → 渲染可读卡；点击“查看本步原始事件”定位技术 Trace 的该步首事件。失败路径：`INVALID_ARGUMENTS` 可见但无工具返回/新快照；无快照的旧产物只显示未知，不补造中间状态。播放仍只移动本地游标。

验证：`node apps/web/tests/traceSteps.test.mjs` **2/2 通过**（增加快照差异断言），前端生产构建通过（28 modules），`git diff --check` 通过。浏览器回读 Fake Recovery Episode `1f3148a2-3ded-4e78-a02f-c4d39a840859`：Step 1 显示 `INVALID_ARGUMENTS`、工具未执行且无新状态快照；Step 2 显示查询记录和新增证据；Step 3 显示提交与 `done` 变化。过程视图点击原始事件入口可定位技术 Trace Step 2 的首事件。390px 视口 document scrollWidth 375px，无整体横向溢出。动画手感属主观验收，仍需项目负责人在本机观看。此次只验收 Fake Replay UI，不代表真实模型稳定性或 V0.2 整版验收。工作区未提交/推送；原有未提交改动保持原样。

## 2026-09-25 单次运行与 Replay UI 首轮实现

按 UI 规范 1.1，在 `apps/web/src/App.tsx` 将单次运行配置排为“任务 → 执行方式 → 运行前核对”，加任务目标预览与原生高级设置折叠；运行按钮始终在折叠区外。选择任务时不覆盖已加载的历史结果；切换任务/数据集会把 MCP 传输恢复为本地，只有任务声明支持时展示 MCP 选项。`apps/web/src/index.css` 增加选中标记滑动、短距离内容进入、任务/步骤选中反馈，并在中等视口把 Replay 详情与状态面板改为纵向，减少窄栏 JSON 换行。没有新增动画依赖。

Replay 默认“过程概览”：`apps/web/src/traceSteps.ts` 仅按已保存事件的相邻 `step_index` 分组，从 `TOOL_CALL_PROPOSED`、校验、工具结果提取标题与结果；步骤轨道选中后更新详情和 `snapshotAt` 状态。步骤播放仍只移动前端游标。切到“技术 Trace”会恢复逐事件筛选、展开、JSON 和事件级播放；URL 刷新继续 GET 原 Episode，不重新调用模型/工具。失败事件只根据真实 payload 展示，缺少快照仍沿用 ADR-007 的回退规则。调用链：历史 GET 或单次 POST → `setArtifact` → `groupTraceByStep` → `visibleEvents`（过程步骤末事件或技术筛选事件）→ `replayIndex` → Inspector 与 Snapshot。

验证：`node apps/web/tests/traceSteps.test.mjs` 1/1 通过，覆盖步骤顺序、参数错误和工具成功；`npm.cmd --prefix apps/web run build` 通过（28 modules）。浏览器回读 BFCL Episode `4716ca38-5f67-4f6d-8239-a5488541826b`：10 事件显示为 2 个步骤，切换到技术 Trace 可见完整 10 事件。网页发起 Fake `order-status-007` Episode `bc4079e8-d881-4f10-b460-6a49c6e29d7a`：SUCCESS、Evaluator true、3 步/3 工具、24 事件，过程概览呈现初始观察、search_documents、read_document、submit_answer；刷新原 URL 后仍显示同一产物。另在 Fake `invalid-then-success` + Recovery 下运行 `order-status-001`，Episode `1f3148a2-3ded-4e78-a02f-c4d39a840859` 为 SUCCESS、21 事件；Step 1 显示“参数错误”和真实 `INVALID_ARGUMENTS`，Step 2 显示工具成功。390px 视口 DOM 主面板宽 351px、document scrollWidth 375px，无整体横向溢出。受限进程曾阻止 esbuild/Node 测试子进程，正常构建和直接 Node 测试均通过。此为 Fake UI 验证，不代表真实模型能力或 V0.2 整版验收。

接续：用一条 MCP 失败产物检查过程概览的网络错误表达，再考虑键盘快速跳步与对照实验的同类过渡。状态变化可读摘要已在上方整改中完成。真实模型目录本次浏览器会话为 unavailable，不据此判断模型失效；原因需另行诊断。本轮代码尚未提交或推送。

## 2026-09-24 UI 风格与动效规范更新

用户确认希望界面具有灵动、流畅的切换感。`docs/product/ui-design-guidelines.md` 升至 1.1：在现有暖色研究工作台基础上，明确模式切换、配置选择、面板展开、运行结果出现及 Replay/Inspector 联动的连续过渡；加入 120/180/240ms 起点、快速连续操作、减少动效及真实状态约束。参考 Linear、Apple、W3C 与 Motion 官方资料，链接见规范。当前仅更新文档，尚未修改页面或新增动画依赖；下一步以单次运行与 Replay 做真实页面原型并浏览器验收，再扩展到对照实验。需求与 ADR 的数据/评分契约不变。

## 2026-09-24 Replay 与配置 UI 调研

用户指出逐事件卡片难读、单次配置表单单调。调研与可执行设计建议见 `docs/research/replay-config-ui-20260924.md`：默认以 Agent Step 呈现「模型决定→工具反馈→状态变化」，原始事件留在技术 Trace；配置改为任务/执行选择加运行前核对、高级设置渐进展开。实际 Artifact 核查：BFCL `4716ca38-5f67-4f6d-8239-a5488541826b` 为 1 步 10 事件，MCP `c302b854-5a35-4ec7-b1b5-749b417e59e0` 为 3 步 24 事件；事件级 duration 多为 0，目前不能画准确阶段耗时瀑布。本轮仅调研和文档，UI 尚未改动；实施应保持需求 V0.6 和现有 Replay 只读契约。

## 2026-09-24 MCP 网络工具小切片

按 Accepted ADR-012，在需求 §0.4 明确课程实验例外。锁定官方 `mcp==2.2.0`，新增独立 localhost Streamable HTTP 服务和真正 SDK Client。首批只远程执行固定 ToolLab 文档任务的 `search_documents`、`read_document`；其余 Runtime/Registry/Executor/Evaluator 继续走原有契约。API 单次运行新增 `tool_transport`，Web 按任务能力展示 MCP 选项，RunConfig 记录传输版本。MCP Episode 有最终 Artifact，暂不提供 Checkpoint/Resume；原本地路径照常恢复。

实测：两个进程的 `tools/list` 返回两种工具，HTTP POST 200。Fake `order-status-007` 同配置本地/MCP 均 SUCCESS、Evaluator true、3 次工具，均为 120 prompt / 60 completion tokens；单次实测本地 32 ms、MCP 200 ms，仅是样例。关闭 MCP 服务后远程 FAILED `tool_failed: TOOL_EXECUTION_ERROR`，Trace 包含 `TOOL_STARTED → TOOL_FAILED → EPISODE_FINISHED`；本地仍 SUCCESS。结果记录在 `docs/learning/V0.2-mcp-network-pilot.md`。Fake 成绩不作为模型能力成绩。

追加一条真实模型探索样本：2026-09-24 Key 级目录仍可见 `coding-minimax-m2.7-free`；该模型在 `order-status-007` 经 MCP 获得 SUCCESS、Evaluator true，Episode `c302b854-5a35-4ec7-b1b5-749b417e59e0`，3 次模型调用、3 次工具调用、3108 prompt / 280 completion tokens。Trace 中搜索与读取标记 `transport=mcp`，本地提交无该标记。仅一题，不能作为稳定可用性或能力排名。该样本使用独立服务进程和 Service 入口；浏览器 MCP 交互仍待人工验收。

启动验收：重启 API 时清除了本机继承的失效 `127.0.0.1:9` 代理；`/api/v1/meta` 经前端代理返回 `catalog=live` 和四款真实模型。MCP 服务列出两种文档工具。经网页同源 `POST /api/v1/episodes` 运行 Fake MCP 得到 Episode `54881a8d-3013-4712-8544-2cdab7c286db`，HTTP 201、SUCCESS、3 工具；同源 GET 回读 200、24 事件。真实 MiniMax Artifact 已放入 API 默认产物目录，浏览器 `?episode_id=c302b854-5a35-4ec7-b1b5-749b417e59e0` 实际显示 SUCCESS、`工具传输：MCP HTTP`、3388 tokens 与 24 个 Trace 事件；页面草稿已选文档任务 007 与 MCP。浏览器尚未亲自点击「开始运行 Episode」发起新一轮模型调用，这项操作由演示者自行执行即可。

质量门禁：Ruff 与 mypy 针对改动文件通过；前端生产构建通过。沙箱内全量 pytest 因系统临时目录权限失败，获准常规进程重跑为 **169 passed、1 条既有依赖 warning**（MCP 回归测试已计入）。启动见 README。现有工作区包含多轮未提交改动，勿整体回滚或覆盖。

## 2026-09-23 V0.2 Checkpoint/Resume 核心实现

ADR-011 已 Accepted。`packages/runtime/session.py` 与 `packages/runtime/handwritten/budget.py` 保存可迁移 Session/预算；Reference 和 LangGraph 共用同一安全点，`packages/application/checkpoint.py` 将 ToolLab 单 Episode 的 Agent/Task/RunConfig 哈希、Trace、消息、Call ID、环境快照与预算原子写入本地 JSON。恢复时重建环境与 Trace，追加 `EPISODE_RESUMED`，Runner 仍独占唯一 `EPISODE_FINISHED`。完成的 Artifact 优先只读回放；损坏或不匹配的 Checkpoint 拒绝恢复。外部工具与 BFCL 不在此实现边界内。

可复现实验：`tests/integration/test_checkpoint_resume.py` 分别让 Reference 与 LangGraph 子进程在第一次工具成功后的安全点退出，主进程重新构造 Runtime、Provider、Environment 并恢复；两组均成功，累积 2 次模型调用、2 次工具调用、80 prompt tokens，已完成工具没有重放，Trace 因果链连续且只有一次终止事件。篡改 Task 后恢复拒绝，正常完成后 Checkpoint 清理也通过；Fake 参数纠错场景恢复通过。新增 5 项测试通过；项目全量测试为 **168 passed、1 条既有 Starlette/AnyIO warning**。Ruff、mypy 全项目及 Web 构建通过。

本轮继续将 ToolLab 单次运行接入 Checkpoint 入口，BFCL 保留原入口。API `GET /api/v1/episodes/resumable` 仅列出本次服务启动前留下、尚无最终 Artifact 的 ID，`POST /api/v1/episodes/{id}/resume` 使用原 Agent/Task/RunConfig、Fake 场景或真实模型重建执行；同进程正在恢复的 ID 暂时隐藏并拒绝重复恢复。Web 单次运行区显示待恢复 ID 和重发模型请求可能增加用量的提示，成功后进入同一 Episode Trace/URL。前端生产构建通过；跨进程测试已通过 FastAPI TestClient 验证两个 Runtime 的列表/恢复/回读。另补测 Fake `invalid-then-success` 在参数纠错安全点中断后恢复成功（3 模型调用、2 工具调用）。

浏览器故障演练已完成：子进程在第一次成功工具后退出，重启本机 API，页面识别待恢复 ID `2315b4b2-4001-4e74-8807-7073ba77cafb`；点击恢复后显示 SUCCESS、2 模型调用、2 工具调用、18 条 Trace（含恢复事件）、原 Episode URL。刷新后 SUCCESS 与恢复事件仍在。**真实模型请求中断恢复尚未实测**。ToolLab 内存工具的恢复保证不能推广到外部写入工具。源码阅读和调用链见 `docs/learning/V0.2-checkpoint-resume.md`。

## 2026-09-23 V0.2 课程交付推进：实验 CSV

已在 Web 已保存 Experiment 的导出栏增加 CSV，按每个 Episode 一行展开成对任务，带 Experiment ID、配置哈希、对照轴、Task/Seed/Repeat、运行侧、判定、工具与模型调用、Token、耗时、费用及工具指标。Reference/LangGraph 侧别与恢复策略侧别分清；未知费用及 Runtime 对照不适用的恢复指标留空；中文 UTF-8 BOM、字段转义与表格公式防护已加入。原 JSON 导出仍使用同一下载入口，不修改 API/Artifact 或评分口径。

`npm.cmd --prefix apps/web run build` 已在可启动 esbuild 的进程中通过（27 modules），`git diff --check` 返回 0。受限沙箱首次构建因子进程 EPERM 失败，常规进程重跑通过。用历史实验 JSON 提取前端 CSV 函数做一次执行自检，并生成被 Git 忽略的样例 `artifacts/exports/agentlabyrinth-experiment-ad386c5d-6458-4a59-b88b-7ed534b18ae6.csv`；Python 标准库 CSV 解析得到 2 Episode 行、20 列，Reference/LangGraph 标签与不适用恢复字段留空正确，公式/引号转义自检通过。Codex IAB 已回读该历史 Fake Experiment，看到 1 Pair、2 Episode、对照表与新增 CSV 按钮，并检查 730px 下 JSON/CSV 同行布局；IAB 下载事件两次等待超时，因此**浏览器点击后下载文件内容尚未验收**，不能宣称下载交互实测通过。当前改动与后续 Checkpoint/Resume 准入见 `docs/tasks/V0.2-m2-course-reliability.md`，决策见 Accepted ADR-011。本段 CSV 工作未运行新真实模型；Checkpoint 核心进度见上方。

## 2026-09-23 新增免费模型验收

用户将 MiMo V2.6 Pro Free 与 Coding GLM 5.3 Free 加入 AIHubMix Key 范围。官方主域 Key 级 `/v1/models` 现可见四款：新增两款及 MiniMax M2.7、MiMo V2.5 Pro。新增两款分别通过真实 BFCL `simple_python_0` 和 ToolLab `order-status-001`，共 4/4 个探索性 Episode 成功，均有真实模型、工具调用与 Trace。ID、Token、复现命令及边界见 [新增免费模型实测](../experiments/new-free-models-20260923.md)。目录已加入两款实验性候选，MiniMax 保持默认；本机 `/api/v1/meta` 当前为 live，返回这四款及 Fake。单题成功不代表全量能力或长期可用。

## 2026-09-23 AIHubMix 网络与模型目录复核

- 真实模型失败根因：Codex 沙箱启动的 API 进程继承失效代理 `127.0.0.1:9`，两次请求耗时约 200 ms、Token 为 0，错误为 `NETWORK_CONNECTION_FAILED`。已用无该沙箱代理的进程重启本机 API；不是 MiMo 模型请求格式或 Tool Schema 问题。
- 本日较早时，官方主域 Key 级 `/v1/models` 返回 200，当时只可见 MiniMax M2.7 Free、MiMo V2.5 Pro Free；用户随后扩充 Key 范围，新状态见上方。后端在 `/api/v1/meta` 做 5 分钟缓存交集过滤；目录服务失败时暂时隐藏真实模型。真实执行也会检查模型是否仍在该 Key 目录。
- 默认模型改为 `coding-minimax-m2.7-free`。MiniMax Episode `032ac2bb-0ae7-4b30-b9d0-4db9ef3becdb` 与原截图 MiMo 重跑 Episode `24b010eb-22f9-4f04-b2b6-c954d256239f` 均完成 BFCL `exact_call_match`，各 1 模型调用 + 1 工具调用。旧失败 ID 与目录数据详见 `docs/experiments/selected-models-20260920.md`。
- MiMo V2.5 Pro 仍在 Key 列表，但官方计划 2026-10-21 退役；本日较早时替代 MiMo V2.6 Pro 尚未对该 Key 开放，现已开放并通过小样本。模型可见性不保证上游每刻都可用，必须区分 Key 目录可见和真实工具调用通过。
- 本轮已确认 `/api/v1/meta` 为 `live`，前端 HTTP 200；随后完成的项目质量门禁见下方记录。

## V0.2 Runtime 对照闭环（2026-09-23，M1 已完成复核；V0.2 未验收）

### 2026-09-23 本轮复核与实测

- 已按 ADR-010 修正框架对照产物：`retry_eligible_count`、`retry_recovery_count`、`retry_recovery_rate` 均为 null；恢复策略对照仍保留真实计数。旧 1.0/1.1 产物读取不改。新增框架对照持久化回归测试，并修正 API 模型目录测试中已过期的默认模型/Kimi 断言。
- 本轮 `./scripts/check.ps1`：Ruff format、Ruff lint、mypy 通过，pytest **163 passed、1 条 Starlette/AnyIO 依赖弃用 warning**。`npm.cmd --prefix apps/web run build` 通过，Vite 27 modules。受限沙箱内 pytest 临时目录和 esbuild 子进程报权限错误；使用获准的常规进程重跑后通过，并非产品代码失败。
- 本机 API Fake 框架对照 `67850630-c2b0-4ac1-9f45-ff9456d77bae`：1 Pair，Reference/LangGraph 均成功；Fake 恢复对照 `5e314f27-ba8e-4da0-b247-d6fb923c20d2`：Baseline 0/1、Recovery 1/1、挽救 1/1；单次 LangGraph Episode `92f1eeba-c76b-4307-a724-b26e6acf7b67`：SUCCESS、17 事件、Runtime 1.2.12。
- 真实 MiniMax `coding-minimax-m2.7-free` 框架对照 `66db3a80-b29a-4ef4-a5b5-5113792622bd`：仅 `order-status-001` 一题，Reference/LangGraph 均 SUCCESS，各 2 模型调用、2 工具调用；Token 2302/2293，耗时 17476/24944 ms，费用均未知。仅为探索性样本，不代表完整 Benchmark 分数。浏览器已回读此 Experiment，打开 LangGraph Episode `d8ba20ae-6eef-4a17-8dec-c1147e069dc8` 的 17 事件 Trace，刷新后保持可见。
- 浏览器实际发起 Fake 框架实验 `ad386c5d-6458-4a59-b88b-7ed534b18ae6`：两侧 1/1，通过 URL 刷新回读。修正指标后已安全重启本机项目 API，`/api/v1/meta` 为 live；新实例框架实验 `57ea7a88-adde-46ca-98ff-8d8ca9f37008` 验证挽救计数与挽救率均为 null。
- 仍未实现 V0.2 的并发/暂停/取消、Checkpoint/Resume、失败任务重跑、CSV 导出等后续能力；本轮只验证 M1 的独立 Runtime 对照，不宣布整个 V0.2 验收。

### V0.2 Trace Replay 自动播放（2026-09-23）

Web 在已保存的 Episode Trace 上新增播放/暂停和 0.5×、1×、2×速度。播放到末尾自动停止，末尾再播放从首事件开始；手动前后移动、Step 跳转、事件筛选、切换 Episode 或页面模式时暂停。只移动本地游标，不触发新的模型或工具调用，也不改变持久化产物。源码见 `apps/web/src/App.tsx`，阅读说明见 `docs/learning/M1-trace-replay.md`。

前端生产构建通过（Vite 27 modules）。浏览器在已保存的 Fake LangGraph Episode `92f1eeba-c76b-4307-a724-b26e6acf7b67` 上验证 2×：`1/17 → 16/17 → 17/17`，到末尾自动停止；末尾重播回到 `1/17`，手动暂停有效。此为 V0.2 的一项独立 UI 能力，不代表 Checkpoint/Resume 或整版可靠性验收。

Codex 当前工作区已将 ADR-009 的单节点委托推进为 ADR-010 的独立调度实现。共享状态操作位于 `packages/runtime/session.py`；`HandwrittenRuntime` 使用 Python 循环，`LangGraphRuntimeAdapter` 直接用 StateGraph 编排 observe/model/validate/execute/end，不调用 `HandwrittenRuntime.run`。组合入口 `packages/runtime/factory.py` 根据 `AgentSpec.runtime_backend` 创建调度器，并将实际 Runtime 版本保存到 RunConfig。

AgentSpec 新增 backend 字段并保留 `runtime_strategy` 作为兼容恢复策略字段；RunConfig 新增版本元数据；旧 schema 1.0 仍可读取。Experiment Artifact 升为 1.2，保存 `comparison_axis`、两侧 backend/version/strategy 与 arm labels。Application 校验恢复策略对照必须固定 backend、Runtime 对照必须固定 recovery policy。Runtime 对照的 `retry_eligible`、恢复计数与恢复率分别为 null/null/null 语义；不解释成零挽救。

API 已把 Runtime 选择接入单次 Episode 与成对 Experiment。Web 已接入单次选择和两种实验轴，按产物轴给成对表格和 Trace 按钮命名，并仅在恢复策略对照时显示挽救指标。本轮验证证据见上方记录。

下一执行者先检查现有 diff，并以 `docs/tasks/V0.2-m1-runtime-comparison-copilot.md` 的验收记录为准继续 V0.2 后续能力；不要重复本轮已完成的小样本。API Key 仅从本机 `.env`/环境变量读取，绝不输出。

### 本轮改动阅读顺序

`docs/adr/ADR-010-independent-runtime-comparison.md` → `packages/domain/models.py` → `packages/runtime/session.py` → `packages/runtime/handwritten/runtime.py` → `packages/runtime/langgraph/adapter.py` → `packages/runtime/factory.py` → `packages/application/experiment.py` → `apps/api/schemas.py` / `apps/api/service.py` → `apps/web/src/App.tsx`。

### 当前主调用链与失败路径

`EpisodeService` 根据请求组装 Agent/Provider/Environment → `create_runtime` 选 backend → `run_episode` 建立 recorder → Runtime 建立唯一 `EpisodeSession` → 调度器循环调用 session 原子步骤 → Validator/Executor 产生工具反馈 → `session.result()` 返回 canonical EpisodeResult → Runner 写入唯一 `EPISODE_FINISHED` 并评测 → API 持久化 Artifact。Provider、预算、参数校验、重复 Call ID、未知/禁止工具或环境异常均走共同 Session 停止路径；仅 `INVALID_ARGUMENTS` 可由恢复策略触发一次模型重试。终止事件和评价仍由 Runner 管理。

实验执行按 Seed、Repeat、Task 串行运行左侧再右侧。应用层先验证固定变量；Runtime 对照固定策略，Recovery 对照固定 Runtime。成本未知仍为 null。LangGraph 图设置递归上限并通过条件边停止，不启用框架自动重试、Checkpoint 或外部遥测。

## 最新复核结论（2026-09-22）

2026-09-22 V0.2 Milestone 1 已建立 LangGraph Bootstrap Adapter：`packages/runtime/langgraph/adapter.py` 通过单节点 StateGraph 委托现有 Runtime，验证框架依赖、异步调用、Episode 与统一 Trace 契约；契约测试使用同一 Fake Provider、Task 与 Seed 对比适配前后的公开结果。全量门禁为 Ruff、mypy、`101 passed`。该框架不是独立控制循环，不计为跨 Runtime 对照完成。决策见 ADR-009，下一步把模型调用、校验、工具执行和终止路由实现为 LangGraph 节点。

2026-09-22 V0.1 已关闭验收并进入 V0.2。V0.1 补齐多 Seed × Repeat 串行实验：新 Experiment Artifact 为 1.1，每个 Pair 保存 Seed 与 Repeat，旧 1.0 产物兼容读取；Web 显示真实 Episode 数与矩阵身份。Experiment 聚合已知 Decimal 费用，未知或历史缺失费用保持 null。浏览器 Fake 实验 `643305b1-73ce-40fa-be49-279a82485447` 完成 8 Episode、4 Pair，刷新只读回放通过；最终回读 `6fc5625b-fc13-4ec5-97ce-9599b39fe487` 显示 Baseline `$0.004` / Recovery `$0.012`。全量门禁为 100 passed、Ruff、mypy 与前端构建通过。全局美元费用上限按需求 V0.6 进入 V0.2，并以可验证价格表为启用前提。

2026-09-21 Codex 已完成 Slice G 的复核整改。Copilot 首次证据仅验证无后端页面，且遗留错误 Trace 映射、缺少 `popstate`、历史配置覆盖运行草稿、外部字体/Emoji 资源、无等待时间和 Token 符号格式问题；Codex 已直接修复并将防错规则写入 `.github/copilot-instructions.md`。真实 Fake 验收结果：clean Experiment `63cbab2f-598b-46e9-b0fc-8763992100c5`（两组均 12/12），invalid-then-success Experiment `1676b272-8b7c-42b5-97a3-185eb6d4acb3`（Baseline 3/12、Recovery 12/12、挽救 9/9），单次 Episode `c08e44eb-8fc3-488d-9e0a-f9276bed4c69`（通过、17 个事件）。URL 新标签页只读 GET 回放且草稿保持默认模型；390/768/1280/1440 截图位于 `artifacts/ui-check/review-*.png`。前端生产构建及项目全量门禁通过（98 passed，2 个既有依赖 warning）。

2026-09-21 已开启 V0.1 切片 G。Codex 按 `docs/product/ui-design-guidelines.md` 先完成可运行 UI 框架：暖米白/陶土橙语义 Token、浅色页面和面板、320px 配置栏、文字品牌页头、页面用途与真实任务数、统一按钮/表单/状态/表格/Trace 基线、可见键盘焦点及减少动效。现有 API、评测和运行流程未改。Copilot 接续任务为 `docs/tasks/V0.1-slice-G-ui-refresh-copilot.md`，重点清理内联样式、重排实验信息、完善加载/复制反馈、Trace 中文标签和多视口浏览器验收。

2026-09-21 Codex 已签收 V0.1 切片 F：原生 ToolLab-Core 有 12 个任务，四类各 3 个，名称与 UUID 唯一；`order-status-004` 按任务卡归入 `parameter_generation`。`search_documents` 与 `read_document` 全部经过现有 Registry/Validator/Executor；评测器只从成功的 `read_document`/`query_records` 事件采信证据，指标名和 `order_status_v1` 未变。旧 Snapshot 回读通过。`TOOL_TIMEOUT` 仅由测试构造，Recovery 下完整事件尾为 `TOOL_STARTED → TOOL_FAILED → EPISODE_FINISHED`，模型调用 1 次、没有重试。最终门禁为 Ruff、mypy、`git diff --check` 通过，pytest `98 passed`、2 条既有依赖弃用 warning；Fake 全套产物 12/12 成功，但不代表真实模型成绩。

真实探索性小样本使用 `xiaomi-mimo-v2.5-pro-free`：参数生成 `order-status-005` 成功，Episode `a539a0e9-a755-4c6a-819b-1e590fe8682b`，2 次模型/2 次工具调用，2927 Tokens；文档多步规划 `order-status-008` 成功，Episode `dbf5ca6b-23c7-407f-a937-04b2bd45ce66`，3 次模型/3 次工具调用，4603 Tokens。不外推为 12 任务真实通过或批量实验结论。

Antigravity 暂不可用期间，Codex 已接管并实现 M1 切片 E：ADR-007 规定用已保存 Environment Snapshot 做只读 Replay；页面增加事件筛选、前后移动、Step 跳转、当前状态/事件双栏、Episode/Experiment JSON 导出和移动端布局。Fake Episode `9b81c7f9-4fce-48fb-8a52-80d730d39e12` 产生 17 个事件和 2 个中间状态快照。Edge DevTools 在 390px 下验证 `clientWidth=scrollWidth=390`，Replay 交互及 20682-byte Episode JSON 下载成功。阅读与实验入口见 [M1 Trace Replay](../learning/M1-trace-replay.md)。

2026-09-21 已使用项目 `.env` 中的本机 Key 完成四模型真实复测。`scripts.verify_selected_models` 已统一使用 Provider 的安全 Key 入口，支持环境变量或被 Git 忽略的 `.env`。小米 MiMo V2.5 Pro 与 MiniMax M2.7 均通过 BFCL 与 ToolLab 示例；DeepSeek 为 `UPSTREAM_CHANNEL_UNAVAILABLE`，Qwen 为 `RATE_LIMIT_EXCEEDED`。本轮 8 个 Episode ID、Token 与结论见 [新模型验收记录](../experiments/selected-models-20260920.md)，完整本地产物位于被忽略的 `artifacts/selected-model-results.json`。

新增四模型复测：**小米 MiMo V2.5 Pro 与 MiniMax M2.7 各自通过真实 BFCL 示例和两轮 ToolLab 订单任务**。DeepSeek 返回无可用通道，Qwen 返回限流。四个 ID 已放行后端并进入网页目录，小米设为默认。结果、预算、复现命令与四份成功 Trace ID 见 [新模型验收记录](../experiments/selected-models-20260920.md)。下文较早的“尚无 BFCL 成功样本”状态已由本记录补足；不将单题成功等同于完整子集通过。

切片 C 的四项阻塞均已修复并通过回归，Codex 已签收。切片 D 已由 Codex 完成并复核核心：固定 BFCL V4 `simple_python` 的 8 道非 Live 单轮真题、可复现导入与哈希校验、独立 Adapter/Environment/Evaluator、API 与 Web 单次运行入口。原始数据不入库，本机缓存由导入脚本生成。导入器现已覆盖离线缓存重建、来源哈希损坏和下载失败，并显式固定转换文件换行格式，避免跨平台哈希漂移。

2026-09-20 当前检出版本的最终质量门禁：`91 passed, 2 warnings in 2.07s`，Ruff format、Ruff lint、Mypy 和前端生产构建通过；Vite 构建 27 modules、954ms。两条 warning 来自 FastAPI/Starlette 的未来依赖弃用提示。浏览器已验证 BFCL 选择、点击运行、独立数据集标签、Trace 和 URL 刷新回读。真实 `coding-glm-5.3-free` BFCL 运行 `6e1ea4db-568b-4db2-9646-75dd44c37d11` 如实记录 `RATE_LIMIT_EXCEEDED`；这证明真实请求与错误链路成立，不代表题目通过。

免费模型实测结论：GLM 5.3 普通请求和工具调用曾成功，本次 BFCL 请求受账号限流；GLM 5.2 普通请求成功但 BFCL 工具请求返回 `MODEL_NOT_FOUND`；Gemini 3.8 已退役；Kimi K3 当前无可用上游通道。平台已修复 JSON Schema `$defs` 兼容、显式 Token 预算、固定错误码和本地请求节流，不自动换模型或伪造通过。详见 ADR-006。

## UI 收口与交接记录（2026-09-21）
- 多视口复核截图：`artifacts/ui-check/review-390.png`、`review-768.png`、`review-1280.png`、`review-1440.png`。
- 浏览器操作记录：Vite `127.0.0.1:5173` 连接真实本地 API，实际运行 Fake clean、invalid-then-success、单次 Episode、成对 Trace 穿透和 Experiment URL 新标签页回读；刷新回读仅触发 GET。
- 当前剩余限制：本切片只重构现有 Web 页面，不扩展 API、Domain、Runtime 或评测口径；真实模型结果仍按探索性记录处理。

## 当前阶段
**V0.1 的 18 项验收已通过；V0.2 M1 独立 Runtime 与对照闭环已完成本轮复核，V0.2 整版尚未验收。**
- 当前待办与 Copilot 接手步骤见 `docs/tasks/V0.2-m1-runtime-comparison-copilot.md`；ADR-009 Bootstrap 已被 ADR-010 取代，旧实现记录保留作历史。
- Codex 最新代码和 UI 改动还没有通过本轮 Python 门禁、Web 构建及浏览器实际 API 闭环；不要沿用旧的测试结果作为本轮验证证据。
- Fake 与真实 Runtime 配对结果均待复核；真实模型只允许单模型少量任务探索，不得把结果扩展解释为全量基准成绩。
- V0.2 的全局美元费用上限只有在 Provider 提供可验证价格表后启用；当前继续保持未知费用为 null。
- 2026-09-21 本机真实复测共 8 个 Episode，两个模型双任务通过、两个模型由上游通道/限流阻断；不把单题结果解释为全量基准成绩。
- 切片 D 复核和给 Antigravity 的最后交接见 `docs/handoffs/M1-slice-D-review-20260920.md`。
- 严格落实 ADR-004 决策边界：BFCL 顺延为切片 D，切片 C 聚焦在相同模型、任务、工具、种子与预算下，对比 Baseline 与一次受控参数容错重试的 Recovery Agent 表现。
- 完成 12 个原生 ToolLab 任务，四类各 3 个；Fake 全套 12/12 成功。
- 完成 Application 串行对照实验 Runner 与指标聚合（成功率、挽救率、Token、已知 Decimal 费用、平均步数与耗时）。
- 完成 FastAPI 实验端点（`POST /api/v1/experiments`、`GET /api/v1/experiments/{id}`）与纯读取隔离。
- 完成 Web UI 对照实验视图：任务多选、聚合指标卡片、成对表格、穿透回读两造 Trace、`?experiment_id=...` URL 状态持久化。
- 完成 Fake 确定性对照实验与真实模型探索实验，真实产物落盘于 `artifacts/experiments/`。

---

## 核心交付物与代码阅读顺序 (Codex 审查入口)

1. **契约层 (Domain)**：
   - `packages/domain/models.py`：`AgentSpec.runtime_strategy` 扩展为 `Literal["handwritten", "handwritten_recovery"] = "handwritten"`（向后兼容）。
2. **容错重试控制循环 (Runtime)**：
   - `packages/runtime/handwritten/runtime.py`：新增 `retried_invalid_arguments` 状态标志。当且仅当策略为 `handwritten_recovery`、校验错误码为 `INVALID_ARGUMENTS` 且未曾重试时，构造包含 `parameters_schema` 的结构化反馈消息并重新唤醒模型；对 `UNKNOWN_TOOL`、`FORBIDDEN_TOOL`、重复调用 ID 及二次校验失败坚决不重试，直接以 `FAILED` 终止；重试不增加工具执行计数，保持事件因果流。
3. **确定性场景与任务集 (Providers & Benchmarks)**：
   - `packages/providers/fake.py`：新增 `invalid_then_success` 确定性场景（第 1 轮返回错误参数表名，收到错误反馈后第 2 轮返回正确表名查询，第 3 轮提交有效答案）。
   - `benchmarks/tool_lab_core/tasks/`：
     - `order-status-001.json` (ORD-001, shipped)
     - `order-status-002.json` (ORD-002, delivered, 多订单数据库)
     - `order-status-003.json` (ORD-003, cancelled)
     - `order-status-004.json` (ORD-004, pending, 紧凑预算 4 步 / 800 tokens)
   - `benchmarks/tool_lab_core/agents/recovery-m1.json`：定义 `runtime_strategy: "handwritten_recovery"` 的 AgentSpec。
4. **串行对照编排与指标聚合 (Application)**：
   - `packages/application/experiment.py`：定义 `PairComparison`、`ExperimentAggregateMetrics`、`ExperimentArtifact`，实现 `run_experiment()`、`compute_config_hash()`、`write_experiment()`、`read_experiment()`。严格串行对齐 Baseline 与 Recovery，计算挽救成功数 `retry_recovery_count` 与挽救率。
5. **API 与服务层 (API)**：
   - `apps/api/schemas.py`：定义 `CreateExperimentRequest`、`ExperimentResponse`，扩展 `MetaResponse` 支持 4 个任务。
   - `apps/api/service.py`：动态读取任务列表，提供 `execute_experiment` 与 `get_experiment`。
   - `apps/api/main.py`：路由 `POST /api/v1/experiments` (201) 与 `GET /api/v1/experiments/{id}` (200/404)。
6. **前端对照实验闭环 (Web UI)**：
   - `apps/web/src/App.tsx` & `apps/web/src/index.css`：顶部模式切换卡（“对照实验” vs “单次运行”）；多任务复选；聚合对照卡片；成对明细表格（含 Base Trace / Rec Trace 查看按钮）；URL 参数同步 `?experiment_id=...` 与 `?episode_id=...`。
7. **自动化测试 (Tests)**：
   - `tests/unit/test_recovery_runtime.py`：覆盖 Baseline 参数错误即死、Recovery 容错一次通过、连续参数错误终止、未注册与禁止工具不重试立即终止。
   - `tests/unit/test_experiment_runner.py`：覆盖 4 任务串行成对实验、100% 挽救判定、干净基线无挽救判定、纯读取隔离与配置哈希确定性。
   - `tests/unit/test_api.py`：测试 4 任务元数据发现、实验执行持久化、UUID 读取隔离。

---

## 状态转换与失败路径说明

### 状态变化链条
```text
Task & Seed (RunConfig)
  │
  ├─► [1] Baseline Episode (runtime_strategy="handwritten")
  │     Turn 1: ToolCall(query_records, table="invalid_table")
  │       └─► ToolValidator: INVALID_ARGUMENTS
  │       └─► Retried? No (handwritten strategy does not retry)
  │       └─► TerminationReason.FAILED (detail="invalid_arguments: INVALID_ARGUMENTS")
  │       └─► Evaluator: success=False
  │
  └─► [2] Recovery Episode (runtime_strategy="handwritten_recovery")
        Turn 1: ToolCall(query_records, table="invalid_table")
          └─► ToolValidator: INVALID_ARGUMENTS
          └─► Retried? Not yet. retried_invalid_arguments = True
          └─► Append Assistant tool call & Tool feedback with parameters_schema
          └─► Next Model Request (Step index increments)
        Turn 2: ToolCall(query_records, table="orders", order_id="ORD-xxx")
          └─► ToolValidator: PASS
          └─► Tool Execution: SUCCESS
        Turn 3: ToolCall(submit_answer, answer="...", evidence=[...])
          └─► ToolValidator: PASS
          └─► Tool Execution: SUCCESS (done=True)
          └─► TerminationReason.SUCCESS (detail="submitted")
          └─► Evaluator: success=True
  │
  └─► [3] Paired Comparison Evaluation
        Baseline: FAILED / Recovery: SUCCESS
        => recovered = True
        => Tokens: Baseline 60 -> Recovery 180 (Delta +120)
```

### 严格防御的失败路径
1. **持久性参数错误（二次失败）**：若重试后参数仍然不合法，`not retried_invalid_arguments` 为 False，坚决终止为 `FAILED`，杜绝死循环。
2. **未注册工具 / 禁止工具**：`UNKNOWN_TOOL` 或 `FORBIDDEN_TOOL` 直接判定为 `FAILED`，不予重试。
3. **重复 Call ID**：模型提出重复调用 ID 时，判定为 `FAILED`（`duplicate_call_id`），直接熔断。
4. **预算超限**：单步或累积 Token 超过上限，由 `BudgetTracker` 熔断为 `MAX_STEPS` 或 `TOKEN_BUDGET_EXCEEDED`。
5. **网关异常**：上游网关报错或模型下线，捕获为 `RUNTIME_ERROR`（`provider_error`），严格记录 `tokens=0`、费用未知，不伪造数据。

---

## 实际实验结果与产物记录

### 1. 确定性离线实验 (Fake Provider, `invalid-then-success`)
- **实验产物文件**：`artifacts/experiments/c1c9fe30-d820-4589-81ee-b4a86bcbe964.json`
- **任务数量**：4 个原生任务（ORD-001 ~ ORD-004）
- **实验结果**：
  - Baseline 成功率：`0.0%` (0 / 4)
  - Recovery 成功率：`100.0%` (4 / 4)
  - 挽救成功数 (`retry_recovery_count`)：`4`
  - 挽救率 (`retry_recovery_rate`)：`100.0%`
  - Token 消耗：Baseline 240 tokens vs Recovery 720 tokens (增量 Delta: `+480 tokens`，平均单任务增加 120 tokens 用于 1 轮纠错交互)
  - 判定结论：**严格证明了在参数格式轻微偏差场景下，单次参数模式反馈可将任务成功率从 0% 提升至 100%，其开销代价为增加 2 次模型往返与 120 tokens。**

### 2. 真实模型探索实验 (Gemini 3.7 Flash Free)
- **实验产物文件**：`artifacts/experiments/beef4eaf-0b85-4313-aa00-e6ca657403cd.json`
- **任务数量**：2 个任务（ORD-001, ORD-002）
- **实验结果**：
  - 上游网关返回：`{"code":"model_retired","message":"The model gemini-3.7-flash-free has been retired and is no longer available."}`
  - 系统捕获：两造均安全记录为 `RUNTIME_ERROR`（`provider_error`），Token 记录为 0，费用标为未知，未发生程序崩溃。
- **第三方网关可用性现状 (2026-09-19)**：
  - `gemini-3.7-flash-free`：已被 AIHubMix 标记为 `model_retired` 下线。
  - `coding-kimi-k3-free`：目前返回 `no_available_channel`。
  - 系统严格遵守原则：不伪造通过、不伪造 Token、真实记录失败原因。

---

## Antigravity 质量门禁（2026-09-20 复核整改后实测通过）
- **pytest**：`75 passed in 1.50s`（全量单测通过，新增 4 个针对禁止工具优先级、完整模型快照及历史产物兼容性的针对性回归测试）。
- **ruff format --check .**：72 个源文件格式完全合规。
- **ruff check .**：All checks passed（0 告警，0 错误）。
- **mypy**：`Success: no issues found in 27 source files`（无类型告警）。
- **git diff --check**：退出码 0，零空白字符错误。
- **web build**：`npm.cmd --prefix apps/web run build` 耗时 704ms，零错误打包。

---

## 2026-09-20 复核整改落实清单 (To Codex)

根据 `docs/handoffs/M1-slice-C-review-20260920.md` 中提出的 4 项审查问题，完成以下代码修复与测试覆盖：

1. **禁止工具与错误参数同时出现时立即终止（P1）**：
   - `packages/tools/registry.py:112`：在 `DefaultToolValidator.inspect` 中，首先判定 `reg is None`（返回 `UNKNOWN_TOOL`），接着优先判定 `permitted`；若 `not permitted`，优先返回 `error_code="FORBIDDEN_TOOL"`，即使参数同样非法，确保权限判定优先于参数格式校验。
   - `packages/runtime/handwritten/runtime.py:233`：在执行循环中，未知工具（`UNKNOWN_TOOL`）与禁止工具（`not inspection.permitted` / `FORBIDDEN_TOOL`）优先于参数校验和恢复分支立即终止（`detail = f"forbidden_tool: {action.name}"`），单次模型调用，零次工具执行，绝不进入重试分支。
   - 新增单测：`tests/unit/test_recovery_runtime.py::test_forbidden_tool_with_invalid_arguments_terminates_immediately` 与 `tests/unit/test_experiment_runner.py::test_forbidden_tool_with_invalid_arguments_not_retry_eligible`。

2. **API 路径覆盖完整模型配置与解析后场景（P1）**：
   - `apps/api/service.py:256`：在 `execute_experiment` 中，解析实际运行的 `resolved_scenario`（如缺省请求默认解析为 `"invalid-then-success"`，`"clean"` 解析为 `"success"`），并保存到 `config_metadata` 中，不再保存为 `null`；同时确保 fake provider 下 `baseline_agent` 与 `recovery_agent` 的 `model.model` 反映请求模型。
   - `packages/application/experiment.py:376`：`exp_config` 作为权威快照，`exp_config["model"]` 始终保持为包含 `provider`、`model`、`temperature`、`max_tokens` 与 `scenario` 的字典对象；更新 `config_metadata` 时不覆盖 `model` 字典。
   - 新增单测：`tests/unit/test_api.py::test_execute_experiment_preserves_full_model_config_and_scenario`，验证保存后回读的模型字典完整性，并断言场景与参数变化必然引起 `config_hash` 变化。

3. **历史实验产物兼容性与指标展示（P2）**：
   - `packages/application/experiment.py:46,74`：将 `PairComparison` 与 `ExperimentAggregateMetrics` 中的 `retry_eligible_count`、`retry_recovery_rate`、`baseline_avg_model_calls` 等新增字段调整为可选（`int | None = None`），反序列化历史旧 JSON（如 `c1c9fe30-d820-4589-81ee-b4a86bcbe964.json`）时保留为 `None`，不赋默认 `0`，杜绝静默覆盖。
   - `apps/web/src/App.tsx:897,955`：前端对 `retry_eligible_count` 为 `null` 的历史实验展示为“4 例，历史版本未统计可恢复基数”，不再出现“4 / 0 可恢复样本”；对未测量的调用量展示为 `- / -`，对表格中历史未统计的行展示“基数未统计”。
   - 新增单测：`tests/unit/test_experiment_runner.py::test_read_legacy_experiment_artifact_preserves_none`。

4. **历史 Fake 实验恢复后模型选项与 URL 状态保持（P2）**：
   - `apps/web/src/App.tsx:210`：新增 `resolveModelOptionId` 辅助函数，对保存的 `provider: "fake"` 或 `model: "fake-orders-v1" / "fake-model"` 均统一解析为 UI 选项 `'fake'`，避免历史加载后模型下拉框失配成 AIHubMix。
   - `apps/web/src/App.tsx:220`：在初始 `useEffect` 中，若 URL 中存在 `experiment_id` 或 `episode_id`，元数据 `meta` 返回时不再以默认模型覆盖已从 URL 恢复的配置。
   - 修复生产打包构建（`npm run build` 耗时 704ms 通过）。
