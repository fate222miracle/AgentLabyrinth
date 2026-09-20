# AgentLabyrinth 协作入口

唯一权威需求是 `docs/product/requirements.md`，已核对版本 **V0.5**。本文件和任务卡只指导执行，不替代需求。

开始工作依次阅读：需求全文 → AGENTS.md → 相关 ADR → `docs/handoffs/current-state.md` → 当前任务卡 → 测试与源码。不得依赖旧聊天；需求版本不符时停止并同步。

当前推进 M1。切片 A、B、C 已签收；切片 D 的核心实现和代码门禁已由 Codex 复核，最终真实网页成功证据待补。Antigravity 暂不可用期间，Codex 已按 ADR-007 接管切片 E 的 Trace Replay、JSON 导出和移动端演示完整度，任务卡见 `docs/tasks/M1-slice-E-codex.md`。仓库记录了两个真实模型的 BFCL 成功样本；当前检出环境在 Process、User、Machine 和 `.env` 四处均没有 Key，因此本轮真实免费模型复测仍是明确阻塞。其他模型的已有可用性与失败结果见 current-state；Key 仅在本机环境/`.env` 配置，不入库、不入前端、不在聊天中传递。核心接口/Schema/评测口径变化先走 ADR，不得静默修改。

- Domain 不依赖具体环境、Provider SDK、存储或外部 Agent 框架。
- Application 通过 Domain Port 编排；Runtime 不包含订单业务；Evaluator 只读、不改状态。
- 所有工具通过 Registry/Executor 严格校验、权限与预算检查。模拟工具不需逐步人工审批。
- Python 3.12、uv、Pydantic v2、pytest、Ruff、mypy。公共函数有类型和简洁 docstring；费用 Decimal，时间 UTC，持久化边界有 schema_version。
- 不为未来功能建空模块；按当前切片实施，不实现多 Agent、GridWorld、登录鉴权或未授权的数据库。
- 串行开发，禁止同时修改同一文件。不得覆盖未知改动，不自动初始化 Git、提交、推送、打 Tag 或发布。
- 核心实现同时交付源码阅读顺序、调用链、状态变化、失败路径与实际实验结果，更新 current-state。
- 框架可用不等于 M1 完成；测试通过不等于真实闭环通过。没有运行或未跑通真实调用的不得宣称通过。

质量命令与当前交付边界见 README。
