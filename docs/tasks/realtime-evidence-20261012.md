# 实时关联资料工作台

2026-10-12，负责人要求暂缓推进对照实验，优先在实时演示旁展示关联依据及Agent的调用。需求V0.6，沿用ADR-013/014/028/029；本轮为已有Trace呈现，不改API/Schema/评分/模型输入或新建资料后端。不提交GitHub，既有对照和历史保留。

## 产品行为与边界

- ToolLab本地与MCP共用资料侧栏，初始资料来自已到达的initial_state.documents，包括旧政策和错案干扰；不读取goal_conditions或预标正确答案。BFCL/无文档记录保持原展示。
- 成功搜索标“搜索已定位”，不是阅读证据。read_document的TOOL_STARTED自动选中对应资料，卡片与正文显示读取状态；TOOL_SUCCEEDED且返回匹配文档才累计已读取。拒绝、TOOL_FAILED和document:null不算成功阅读；后续失败不抹去早先已取得的记录。
- 接收submit_answer的成功事件后才显示参数中的实际引用；“已提交引用”不代表评测通过，未读引用仍明示未读，独立Evaluator判有效性。
- 观察者可点击或键盘预览正文；只切本地选择，不POST、不发工具调用、不补证据、不把全文注入模型。下一次真实读取开始自动跟随新文档；资料目录仅在自身容器滚动，不抢焦点/滚动页面。
- 实时断线或历史游标停在未返回调用时显示“读取已发起 · 结果未确认”。不是仍在推理或已经失败的断言。历史只按游标前缀，缺初始快照时仅显示已记录的搜索/阅读资料，不借final_state补造。
- 当前正文为环境保存的原始资料，不翻译或改写模型所读内容。资料数量为环境目录数（含干扰项），不同于场景卡所说的3/4/5份有效关联依据；界面解释干扰项，不提前标正确资料。

## 源码阅读与调用链

1. `packages/runtime/session.py`保存初始环境/调用/返回事件，原SSE链路未改。
2. `apps/web/src/flowFrames.ts`的documentEvidence按当前cursor扫Trace，以call_id关联工具及参数，仅白名单文档字段；输出资料、状态、最近读取游标。
3. `apps/web/src/McpFlowReplay.tsx`共用live/completed/replay游标，调用上述投影，读取节点副标题显示实际document_id；挂载侧栏与原当前阶段摘要。
4. `apps/web/src/DocumentEvidence.tsx`只保存观察者选择；新读取游标优先自动跟随，独立目录滚动。`flowReplay.css`宽屏并列，900px以下堆叠，全文区可键盘滚动。
5. `apps/web/tests/flowFrames.test.mjs`验证成功/拒绝/超时/null/引用及不借未来；`e2e/documentEvidence.spec.ts`分段发送实际Fake轨迹验证中间状态和实跑产物保持。

运行检查：在apps/web运行`npm test`、`npm run typecheck`、`npm run build`；空闲8000/5173端口时，PowerShell设置`$env:AGENTLABYRINTH_E2E_CHANNEL='msedge'`后`npm run test:e2e`。浏览器服务隔离Fake，不读Key；分段流只证明UI事件消费，不代表真实模型时延或新的模型通过结果。

## 验证与交接

已通过类型检查与36个Node检查；首轮沙箱子进程EPERM，授权本机测试子进程后测试/构建通过，没有修改测试规避权限。首轮16项相关Edge通过；截图检查后补读取节点文档ID和中断未确认文案，再跑最终浏览器验收，实际结果与服务恢复见current-state。

最终完整Edge39/39（1.5m）通过、最终生产构建通过；四视口和旧真实本地/MCP产物截图已检查。旧真实记录回读显示3/5、4/6已读和相应实际引用，刷新零POST且原文件不变，报告在artifacts/realtime-evidence-20261012/saved-real-check.json。本轮完整浏览器产物43239e69-74ce-4aa7-bf46-66f746cf1183；没有新真实模型请求。正常服务恢复与PID见current-state。

本轮无真实推理POST，既有真实退货/配送/退款产物不改写。进入正常工作台→配置任一场景实时演示→核对模型并启动，资料在首个环境快照到达后出现，Agent自动走原search/read/submit。现场手感/课程签收仍待负责人确认。

Copilot防错：不要把可预览、搜索命中、提交参数、最终快照当成功阅读；不要为演示自动调用工具或注入全量文档；不要按任务私有答案过滤干扰项；不要从连接中断推断模型失败或继续运行；不要把本轮Fake验收写成真实模型复测。
