# ADR-012：课程演示提前接入受控远程 MCP 工具

## 状态

Accepted（2026-09-24）。依据需求 V0.6 §0.4、§8 与 §19，仅批准下述 V0.2 小范围例外。

## 背景

项目已有确定性 ToolLab、统一 Registry/Validator/Executor、Trace 和 Agent 对照。课程需要展示仿真平台，也希望呈现计算机网络与传统 Agent 工具生态的联系。单独启动一个 MCP Server 没有进入 Agent 调用链，不能算完成集成；本地 stdio 也不能证明网络行为。MCP 当前规范提供 Streamable HTTP 传输与 Tools 能力，Python SDK 2.x 已发布稳定版；实现锁定 SDK 版本与固定工具集。

## 决策

1. 首批仅将 ToolLab 文档任务的 `search_documents`、`read_document` 作为只读 MCP Tools，由独立进程经 localhost Streamable HTTP 提供。服务只读取仓库内固定 TaskSpec 的公开 `initial_state`，不输出 `goal_conditions` 或任意文件；不接受任意 URL、路径或外部 Server 配置。
2. 平台作为真正的 MCP Client 调用远程工具。Agent 的模型调用、Tool Schema、权限与参数校验、预算、Executor、Trace 和 Evaluator 保留既有边界；MCP 只作为 Environment 的受控执行 Adapter。远程 `read_document` 的证据仍由 Environment 在成功返回后记录，不能由最终答案伪造。
3. 原生本地执行为基线。固定同一 TaskSpec、Fake Provider、Seed、预算与 Runtime，对比本地和远程成功判定、工具调用、Token 与耗时。真实模型只做小样本探索，不将网络波动混入正式模型能力排名。
4. 首批仅绑定 `127.0.0.1`，无第三方数据或凭据传输。超时、连接失败必须形成可解释的工具失败 Trace；不得自动重试远程写操作。网络故障注入和 UI 展示在基本真实协议闭环后追加。
5. MCP 版本与 Python SDK 固定在依赖锁文件。SDK 类型只留在 Adapter 和独立 Server；Domain、Evaluator、Runtime Port 不依赖 MCP。MCP 服务不可用时本地 ToolLab 仍可运行。

## 验收

- 两个进程经真实 Streamable HTTP 完成 `tools/list`、文档搜索和读取；协议调用由官方 SDK 发起，不以普通 HTTP 接口冒充。
- 同一文档任务经本地与远程路径均成功；Evaluator 的证据、终态、工具数、Token 一致，Trace 可区分传输方式和失败。
- 服务关闭时远程路径清晰失败，本地路径仍通过；服务不得泄露私有目标或允许任意路径读取。
- 更新 `docs/learning/` 和 `docs/handoffs/current-state.md`，保存实际实验结果与未完成边界。

## 代价与限制

每次远程调用增加协议和网络开销。首批 localhost 不证明公网稳定性，也没有真实外部写入工具的幂等保证；后者仍由 V0.5 单独决策。
