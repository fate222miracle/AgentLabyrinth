# Current state

更新：2026-10-01。需求唯一来源：`docs/product/requirements.md` **V0.6**。不依赖历史聊天。

## 2026-10-01 UI 复验与课程案例固化（最新）

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
