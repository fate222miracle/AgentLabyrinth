# AgentLabyrinth 协作入口

唯一权威需求是 `docs/product/requirements.md`，已核对版本 **V0.6**。本文件和任务卡只指导执行，不替代需求。

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
