# AgentLabyrinth 协作入口

唯一权威需求是 `docs/product/requirements.md`，已核对版本 **V0.5**。本文件和任务卡只指导执行，不替代需求。

开始工作依次阅读：需求全文 → AGENTS.md → 相关 ADR → `docs/handoffs/current-state.md` → 当前任务卡 → 测试与源码。不得依赖旧聊天；需求版本不符时停止并同步。

当前推进 M1。用户已正式授权启动 M1 课程演示开发，ADR-003 已 Accepted；SSOT V0.5 已增补一个 BFCL 改编子集提前接入例外。切片 A 已用 AIHubMix `gemini-3.7-flash-free` 真实闭环签收；切片 B 的网页基本运行经 Codex 浏览器复核。当前交给 Antigravity 的是切片 C，见 `docs/tasks/M1-slice-C-antigravity.md`。由 Codex 负责契约、预算与评测审查，Antigravity 填充内部实现，Codex 审查。其他模型的可用性与失败结果见 current-state；Key 仅在本机环境/`.env` 配置，不入库不入前端。核心接口/Schema/评测口径变化先走 ADR，不得静默修改。

- Domain 不依赖具体环境、Provider SDK、存储或外部 Agent 框架。
- Application 通过 Domain Port 编排；Runtime 不包含订单业务；Evaluator 只读、不改状态。
- 所有工具通过 Registry/Executor 严格校验、权限与预算检查。模拟工具不需逐步人工审批。
- Python 3.12、uv、Pydantic v2、pytest、Ruff、mypy。公共函数有类型和简洁 docstring；费用 Decimal，时间 UTC，持久化边界有 schema_version。
- 不为未来功能建空模块；按当前切片实施，不实现多 Agent、GridWorld、登录鉴权或未授权的数据库。
- 串行开发，禁止同时修改同一文件。不得覆盖未知改动，不自动初始化 Git、提交、推送、打 Tag 或发布。
- 核心实现同时交付源码阅读顺序、调用链、状态变化、失败路径与实际实验结果，更新 current-state。
- 框架可用不等于 M1 完成；测试通过不等于真实闭环通过。没有运行或未跑通真实调用的不得宣称通过。

质量命令与当前交付边界见 README。
