# M1 切片 B：Web 演示闭环交给 Antigravity

SSOT：`docs/product/requirements.md` V0.5。ADR-003 Accepted。切片 A 已由 Codex 用 `gemini-3.7-flash-free` 独立联网复跑并签收；证据见 `docs/handoffs/current-state.md`。本卡授权切片 B 的 API、前端、最小 JSON 读写和相应测试，不授权更改 Domain、Runtime Port、Trace Schema、工具校验或评测口径。

## 目标与边界

浏览器完成一次真实 ToolLab Episode：选模型与预算 → 启动 → 看结果 → 按步骤看 Trace → 刷新后重读同一产物。默认模型为已实测的 `gemini-3.7-flash-free`；Fake 可供自动测试与离线演示。Kimi 上游不可用、GLM 参数校验失败、DeepSeek 在当前任务预算下停止，这些是分别记录的实验结果，不能在页面上标成已通过。

只做本地单用户演示。可以新增实际使用的 `apps/api`、`apps/web`、相关测试、启动说明和必要依赖；不建数据库、登录、队列、任务编辑器、第二套评分器、BFCL Adapter 或额外 Provider。若必须改变核心契约，先写明问题和最小方案，交 Codex 审查并更新 ADR，不在页面层绕过。

## 实施顺序

1. **API**：使用现有 `run_episode`、`write_artifact`、`read_artifact` 和已注册的 ToolLab 组件。最小接口为 `POST /api/v1/episodes`（创建单次运行，成功返回 201）与 `GET /api/v1/episodes/{id}`（按 UUID 重读产物），再提供只含当前可选模型和任务的配置数据。API DTO 严格校验、带 schema_version 与 request_id；返回脱敏的统一错误结构，不返回供应商原始响应、Key 或本机路径。真实运行失败也保存并返回可查看的 Episode，而非伪造成功。
2. **前端**：React/Vite 做实验配置、结果、Trace 三个清晰视图。默认选 Gemini；提供 Fake。其他已试模型如开放选择，必须标明“实验性”与已观察到的限制，禁止任意模型 ID 输入触发付费请求。运行中有加载状态；结果显示模型 ID、真实/Fake、成功/失败、终止原因、步数、Token、时延；`is_known=False` 时费用写“未知”，不显示 `$0`。Trace 按事件顺序呈现工具提议、校验、执行反馈和环境变化；回放只读 JSON，不重调模型。
3. **最小持久化与体验**：每个 Episode 使用自身 UUID 保存独立 JSON；读取时严格校验，避免用户可控路径。刷新结果页仍可打开该 Episode。桌面和手机宽度可操作；空状态、网络错误、模型服务失败有可理解的安全文案。不得把失败 Trace 当作成功范例。

## 验收证据

- 自动化：API Fake 成功与失败、非法配置、未知 Episode、保存后读取、读取不发模型请求、Key 不出现在响应；前端构建与关键交互检查。继续运行 Ruff、mypy、pytest；报告实际命令和结果。
- 手动：浏览器用 Gemini 完成一次真实 ToolLab Episode，并刷新查看同一 Trace；用 Fake 演示离线流程。保存桌面和手机截图，核对浏览器网络响应没有 Key 或绝对路径。免费通道临时故障时保留失败结果和真实成功 Trace，不伪造现场成功。
- 交付：修改文件清单、入口与调用链、状态变化、失败路径、实际运行记录、截图、README 启动命令和 `docs/handoffs/current-state.md` 更新。Codex 复核后签收切片 B。

## 后续口径

本切片不放宽工具参数严格校验。GLM 的嵌套 JSON 字符串若要兼容，应先证明是稳定的网关格式问题，再由 Codex 评审仅在 Provider 边界做有界转换及负例测试；不能让 Executor 接受任意字符串。DeepSeek 的预算停止属于按现有 TaskSpec 执行；将来比较模型时必须固定并公开同一预算，改变任务预算或评分口径先走 ADR/SSOT。BFCL 切片 C 开始前，须先处理其与 SSOT“外部数据 V0.2 起接入”的版本边界。
