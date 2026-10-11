# AgentLabyrinth 协作入口

唯一权威需求是 `docs/product/requirements.md`，已核对版本 **V0.6**。本文件和任务卡只指导执行，不替代需求。

负责人2026-10-11明确授权提交并推送当前最新代码，要求后续任务完成后及时同步GitHub。执行前核对差异与远端、运行相关质量门禁、扫描暂存内容的凭据；仅提交已完成且验证的源码/测试/文档，不提交本机配置或实验产物。此授权不包含强制推送、覆盖未知改动、打Tag或部署；验证失败先修复并记录，网络失败如实交接。

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
