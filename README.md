# AgentLabyrinth

2026-10-26 [V0.3阶段回顾与后续安排](docs/handoffs/V0.3-stage-review-20261026.md)：汇总记忆、多工具、规划、第三Runtime和真实Judge的交付与证据边界。负责人授权本次GitHub同步；下文“不提交”是各历史阶段的当时约束。

2026-10-25 按负责人确认的[ADR-040](docs/adr/ADR-040-real-judge-product-entry.md)接入真实大模型Judge：选择型号、显式一次评审，显示理由/引用及规则分歧；撤下人工/Fake产品操作，旧记录保留。[源码/实测/效果证据交接](docs/learning/V0.3-real-judge-entry-20261025.md)，最新门禁与一次免费模型实测见current-state。Judge不改变任务成绩，Memory/Planning收益仍须真实对照。

2026-10-25 结果复核易用性优化：先说明检查用途，人工/真实模型意见与模拟测试分开，技术字段默认折叠；保留全部历史与完整CSV。[源码与验证交接](docs/learning/V0.3-review-usability-20261025.md)，实际最新门禁见current-state。

2026-10-25 负责人已确认当前交付范围现场体验通过；接续修复PydanticAI回归目标校验，完成六题固定Fake对照与离线报告。[固定实验、实际结果与下一步](docs/learning/V0.3-fixed-experiment-preparation-20261025.md)。59项定向Python、旧22格及新14格回归通过；真实效果、Reflection暂缓与A1边界仍按记录保留，不提交GitHub。

2026-10-25 评审展示收尾：真实历史来源不再误标Fake，提示/量表版本、评审Token与未知费用可查看，独立CSV补齐来源和用量。[三分钟Fake演示与失败预置](docs/handoffs/V0.3-demo-20261025.md)、[源码交接](docs/learning/V0.3-review-presentation-20261025.md)。最新门禁见current-state；真实Judge v2未新增验证。

2026-10-23 [Codex复核与整改](docs/tasks/V0.3-trae-review-20261023.md)：Judge v2及Runtime/下载交付定向通过，补历史回读和严格失败回归，纠正费用说明。下一项交[Trae](docs/handoffs/trae-20261023.md)完成Review来源/用量/CSV展示与现场验收材料；真实v2仍需单独授权，整版未签收，不提交GitHub。

2026-10-22 负责人确认并完成[ADR-039独立Episode评审](docs/adr/ADR-039-independent-episode-review.md)：人工复核与一次Fake Judge独立保存，Episode并列展示、Experiment按需覆盖摘要及Review CSV可用；源Episode/输入/事件归属校验，刷新只GET，原确定性评分、预算和旧CSV保持。Fake只验证链路，真实Judge另行授权；[源码与失败交接](docs/learning/V0.3-independent-review-20261022.md)。第三Runtime边界修复仍保持，不提交GitHub。

2026-10-21 [ADR-038](docs/adr/ADR-038-second-external-runtime-selection.md)已接入PydanticAI第三Runtime：固定`pydantic-ai-slim==2.57.0`、单次与正式Runtime对照API/Web、保存恢复和CSV已完成，A1步间由adapter推进的调度缺口保留。实际624 Python/44 Node/61 Edge通过，真实模型未运行，见[current-state](docs/handoffs/current-state.md)。

2026-10-21 [Trae二次复核](docs/tasks/V0.3-trae-review-20261021.md)：本轮新增为设计补充，尚无新框架代码/测试。关键源码已只读定位，独立调度/版本指纹/超时事件断言已修正；[下一执行卡](docs/tasks/V0.3-runtime-admission-trae-20261021.md)先提隔离Fake准入审批，通过运行验证再推进成品。未安装依赖/调用真实模型/提交GitHub。

2026-10-21 [Trae成果复核](docs/tasks/V0.3-trae-review-20261021.md)：153项复跑通过、旧22格报告重算一致，纠正Fake/真实证据归类与设计缺口。Reflection按记录暂缓，第二框架尚未实施；[下一执行卡](docs/tasks/V0.3-runtime-admission-trae-20261021.md)先补ADR-038准入设计，具体确认后Fake验证及正常产品闭环。无新模型调用/依赖安装/Git提交。

2026-10-21 [最新Trae交接](docs/handoffs/trae-20261021.md)、[下一阶段执行卡](docs/tasks/V0.3-reflection-recovery-trae-20261021.md)：保护本地全部未提交成果，Planning已实现，下一主项为受限Reflection具体ADR与现有Recovery专项模板/报告；后续第二外部Runtime/Judge逐项推进。仅文档交接，不授权真实模型调用或Git提交，596/44/61为接手前门禁。

2026-10-20 按负责人确认的[ADR-036](docs/adr/ADR-036-conditional-planning-tasks.md)新增条件路由/遗漏核验两题。ToolLab搜索`planning-`，正常单次或规划对照可运行，复用实时资料、实际输出、声明与CSV；原19题保持。596 Python/44 Node/61 Edge及实际MCP HTTP新进程恢复通过，[源码/操作/失败与交接](docs/learning/V0.3-conditional-planning-20261020.md)。仅Fake机制验证，真实规划效果未测，不提交GitHub。

2026-10-20 [Codex验收Trae规划交付](docs/tasks/V0.3-planning-review-20261020.md)：修正计划恢复/结果来源及基线描述，补单次规划开关、实时声明与历史隔离；修补后534 Python/44 Node/58 Edge及两Runtime实际MCP HTTP跨进程恢复通过。属于组件技术验收，尚未验证真实模型规划收益或整版V0.3；本地保留、不提交GitHub。

2026-10-19 负责人指定Trae接续V0.3开发：[最新工作交接](docs/handoffs/trae-20261019.md)、[Planning任务卡](docs/tasks/V0.3-planning-trae-20261019.md)。最新成果在当前本地工作区尚未提交，接手先保护已有修改；按周计划推进并持续更新current-state，不自动提交GitHub。

2026-10-19 接续[本周V0.3开发计划](docs/tasks/V0.3-week-plan-20261019.md)，先按[ADR-034](docs/adr/ADR-034-document-id-search.md)修复实际检索障碍：新网页文档运行支持文档ID精确查找，空搜索显示字面规则及下一步建议，本地/MCP一致；旧历史/恢复不升级。搜索仍不计已读证据，无新增配置项。[源码、验证及交接](docs/learning/V0.3-document-search-20261019.md)。这不是整版签收，Planning/Reflection/第二框架/Judge等未实现项如实保留。

2026-10-19 多工具调用按[ADR-033](docs/adr/ADR-033-serial-tool-batches.md)接入：网页ToolLab默认允许同轮最多8个只读调用，按顺序逐项校验执行与保存；单工具仍兼容且可选，BFCL保持单函数协议。同轮每个Call ID在实时画布/概览独立呈现，CSV记录保存模式，历史/恢复不按新草稿升级。[源码与工作交接](docs/learning/V0.3-serial-tool-batches-20261019.md)。

2026-10-19 按Accepted ADR-032接入三题自建事实记忆压力场景：ToolLab搜索`memory-`，组合登记/验收/适用政策计算结论；支持原实时资料/最终输出、正式同窗口记忆对照、CSV及只读历史。大返回允许合法重读，版本题按登记选择政策，旧任务/评分保持。[任务说明](benchmarks/tool_lab_core/tasks/memory_challenge/README.md)、[源码/测试/实际免费模型交接](docs/learning/V0.3-memory-challenge-20261019.md)。本地保留、不自动提交；不是整版V0.3验收或泛化收益结论。

2026-10-18 新增已保存记忆记录的离线诊断：`uv --cache-dir .uv-cache run --locked python -m scripts.review_memory --help`。支持正式Experiment或一对独立Episode，输出逐次窗口/记忆来源、成功/重复阅读与任务结果的Markdown和JSON；零模型/工具执行，不覆盖原产物。[命令、源码与失败路径](docs/learning/V0.3-offline-memory-review-20261018.md)。

2026-10-15 同窗口工具记忆对照已接入正式网页/API：对照实验选择“工具记忆”，两侧共享窗口N，仅右侧增加M字节记忆。支持冻结/恢复、失败显式重跑、保存结果与CSV；旧full上下文轴和单次默认full保持。Codex复核并补固定变量及历史来源校验，[使用与源码交接](docs/learning/V0.3-memory-ablation-20261015.md)，最新验证见current-state。Fake只验证机制，未签收整版V0.3，不提交GitHub。

2026-10-14 完成一对真实同窗口工具记忆探索：MiniMax M2.7退货场景两侧均通过，工具调用8→5、重复阅读3→0、报告Token15766→10317。仅单个探索样本，不是成功率或稳定收益结论。资料侧栏新增当前前缀的实际阅读/重复次数；显式真实验证命令 `uv --cache-dir .uv-cache run --locked python -m scripts.episodic_memory_ablation --model coding-minimax-m2.7-free`，默认不带--model仍为Fake。[复现与工作交接](docs/tasks/V0.3-memory-real-pair-20261014.md)。不提交GitHub。

2026-10-14 单次运行配置改为右侧紧凑模型/Runtime/启动操作台，高级参数在下方独立三组排列，避免展开设置撑高任务目录旁空白。条件数字并排、长说明按需展开，原配置/历史保持；[参考与工作交接](docs/tasks/compact-run-settings-20261014.md)，UI规范1.8。完整Edge46项及最终5项复查通过，本地未提交。

2026-10-14 按[ADR-030](docs/adr/ADR-030-bounded-episodic-tool-memory.md)接续V0.3单任务工具记忆：网页更多设置可选择近期窗口加有来源的工具记忆，大小受限、超大结果整条跳过，完整Trace/Checkpoint保留。固定同窗口Fake消融命令为 `uv --cache-dir .uv-cache run --locked python -m scripts.episodic_memory_ablation`；Fake不是实际模型能力结论。配置、源码阅读与边界见[学习交接](docs/learning/V0.3-episodic-memory-20261014.md)，最新测试状态见current-state。本地开发，不提交GitHub。

品牌图标采用 D / Wayfinder 初版：导航短动画加载后保持完整标志，点击品牌可打开独立动态展示；浏览器favicon为静态图标，尊重减少动效。前端启动后访问 `/brand/preview.html`，SVG/透明PNG与实际验证见[设计交接](docs/design/wayfinder-v1/README.md)。

面向 AI Agent 的可复现实验平台。唯一权威需求：`docs/product/requirements.md` **V0.6**。

2026-10-12 新增三个跨文档证据场景：退货审批、配送争议、退款核验，分别关联3/4/5份文件。正常网页ToolLab内搜索场景名称即可运行，复用实时过程、最终证据、保存结果、上下文对照及只读MCP。独立自建仿真，不是外部真实数据集；原12题和BFCL保持。[场景说明](benchmarks/tool_lab_core/tasks/long_chain/README.md)、[验证与源码交接](docs/learning/V0.3-linked-evidence-20261012.md)。后续提交须负责人明确授权。

2026-10-04 前端可用性复核：历史表单支持标签/Enter，导航可识别当前模式并跳至工作区；单次先配置后运行，结果突出来源与核心指标，详情按需展开并可直达调用过程；对照种子/预算集中设置。实际检查、源码顺序与复现见 [页面优化交接](docs/learning/frontend-usability-20261004.md)，不改变API或评分。

2026-10-04 桌面动效优化：导航/Replay连续滑块、可打断内容过渡、原生面板伸缩与按压反馈；保留浏览器原生滚动，动态减少动效及动画故障降级。调研、源码/调用链与实际验证见 [动效交接](docs/learning/ui-motion-20261004.md)，无新增依赖或接口变化。

2026-10-04 已实现能力优化按 [ADR-024](docs/adr/ADR-024-existing-capabilities-integrity.md) 推进：不同上下文分组比较，恢复前核对结果来源，CLI产物可按原策略重跑，预览核验完整矩阵与Trace，超时停止新请求，动画响应减少动效偏好。阅读顺序、复现实验和稍后人工核对见 [优化交接](docs/learning/existing-capabilities-optimization-20261004.md)；自动验证与负责人签收分别记录。

2026-10-04 按 [ADR-023](docs/adr/ADR-023-context-management-first-slice.md) 受控启动 **V0.3 上下文管理首切片**，V0.2尚未整版签收。已实现完整历史/最近完整工具轮次的请求投影、两种Runtime和安全点恢复、固定Fake消融及只读历史策略显示；尚无新建上下文对照的Web入口、摘要/Memory或第二外部框架。运行 `uv --cache-dir .uv-cache run --locked python -m scripts.context_ablation` 生成24条实际轨迹与报告；20成功、4个窗口1文档失败符合工程预期，不能代表真实模型得分。源码顺序/调用链/失败和实际结果见 [阅读指南](docs/learning/V0.3-context-management.md)。

2026-10-01 收尾：Episode/对照 API 支持可选 `max_execution_time_ms`，Web 新运行默认 300 秒；恢复累计安全点活动耗时，已开始的工具先完成再停止。历史看板默认折叠，动画支持“专注查看”。源码/实验与限制见 [学习交接](docs/learning/V0.2-product-closeout-20261001.md)。全局 Token 预算、最终免费模型选择与整版现场签收仍待完成，数据库为后续 ADR 方向。

**V0.1 已完成 18 项验收。V0.2 当前受控范围已补齐实验控制、恢复、固定回归与同配置历史看板；ToolLab/BFCL/只读 MCP/Experiment 均有单模型真实安全点恢复证据。全局 Token、最终模型收口、剩余 UI 实机检查与负责人签收待完成；准确边界见 [验收矩阵](docs/handoffs/V0.2-acceptance-review-20260930.md) 与 `docs/handoffs/current-state.md`。**

课程演示 M1 推进：
- 切片 A：完成 AIHubMix 真实 ToolLab 闭环。
- 切片 B：完成 Web 演示单次执行与 Trace 回读。
- 切片 C：已完成 Baseline 与 Recovery Agent 对照实验闭环（见 `docs/tasks/M1-slice-C-antigravity.md` 与 ADR-004）。扩充至 4 个 ToolLab 原生任务，提供串行 Experiment API、聚合对照卡片、成对比较表格（可穿透查看两造 Trace）与 URL 状态持久化。
- 切片 D：固定 BFCL V4 `simple_python` 上游提交，接入 8 道非 Live 单轮真题；结果独立标记为 `AgentLabyrinth-adapted subset`，不作为官方 BFCL 分数。
- 切片 E：Episode Trace 支持事件筛选、前后移动、Step 跳转和环境快照；Episode 与 Experiment 可直接导出当前已加载的 JSON，回放和导出均不重新调用模型。
- 切片 F：已补齐四类各 3 个、共 12 个原生任务；`search_documents/read_document` 通过现有 Registry/Executor，Fake 可离线跑通全套，评测器计入文档证据。
- Slice G：实验工作台 UI 已按 `docs/product/ui-design-guidelines.md` 完成收口与真实 Fake 闭环验收，复核记录见 Copilot 任务卡。

Codex 负责 Domain 契约、预算与评测审查；Antigravity 负责内部实现（`HandwrittenRuntime` 容错重试分支、`run_experiment` 串行编排、4 条原生 TaskSpec、FastAPI 实验端点与 Web 对照视图）。

## 固定课程演示（2026-10-01）

依赖准备：`uv sync --locked`、`npm.cmd --prefix apps/web ci`。从项目根目录生成新案例，再一条命令启动隔离 API/Web：

```powershell
$demoPath = Join-Path (Get-Location) ('artifacts/course-demo/' + [guid]::NewGuid().ToString())
uv --cache-dir .uv-cache run --locked python -m scripts.course_demo --artifacts-dir $demoPath
uv --cache-dir .uv-cache run --locked python -m scripts.course_demo --preview --artifacts-dir $demoPath
```

完成索引 `demo-index.json` 提供当前机器的链接；Ctrl+C 停止预览。固定成功、参数纠错、时间终止、子进程中断恢复和真实 localhost MCP HTTP/断线案例自动核验，模型全部 Fake、不读取 Key。拒绝覆盖旧目录或接管占用端口。只有生成退出码 0 才通过；`--skip-mcp` 不算网络验收。换电脑与三分钟讲解见 [演示交接](docs/handoffs/V0.2-course-demo-20261001.md)，调用链/失败路径见 [阅读指南](docs/learning/V0.2-course-demo-freeze.md)。另一电脑需取得包含该脚本的新提交后才能使用；未实测第二台全新机器安装。

## 启动与检查

需要 Python 3.12、uv 和 Node.js 22.21+。首次安装锁定的前端依赖及浏览器：

```powershell
npm.cmd --prefix apps/web ci
cd apps/web
npx.cmd playwright install --no-shell chromium
cd ../..
```

在项目根目录运行完整门禁（先停止自己启动的 8000/5173 服务，测试不复用已运行的 API/Web）：

```powershell
./scripts/check.ps1
```

PowerShell 入口锁定同步 Python 依赖后调用跨平台 `scripts.check`。它校验两类固定 BFCL 来源，运行 Ruff 格式/Lint、mypy、pytest、四套 Fake 回归、Web strict 类型/构建/单测、依赖漏洞扫描与 Playwright，失败立即停止。产物每次写入独立 `artifacts/quality/<UUID>/`，浏览器报告为 `artifacts/playwright-report/`。首次 BFCL 下载和 npm 漏洞扫描需要网络，模型全部 Fake，不读取 Key；不自动提交或发布。GitHub Actions 调用同一入口，官方 Actions 固定提交版本、只读权限，不配置模型 Secret。

2026-10-03 本地完整门禁实跑：后端 **251 passed**，Ruff/mypy **91 文件**，前端 **28/28**，浏览器 **6/6**，四套回归 **22 单元、零退化**，npm audit **0 vulnerabilities**。本机锁定 Chromium 启动报 WinError 14001，实际浏览器验证采用已安装的 Edge；CI 默认 Chromium 尚未在 GitHub 运行。Zod Mini 校验已覆盖所有页面接口与 SSE，见 [ADR-022](docs/adr/ADR-022-web-response-validation.md) 和[学习交接](docs/learning/V0.2-web-boundaries-automation-20261003.md)。V0.2 尚未整版签收。

若本机 Chromium 无法启动且已有 Edge，可明确选择 Edge 后运行；如果系统策略阻止 `.ps1`，直接使用 Python 入口，不修改系统策略：

```powershell
$env:AGENTLABYRINTH_E2E_CHANNEL = 'msedge'
uv --cache-dir .uv-cache sync --locked
uv --cache-dir .uv-cache run --locked python -m scripts.check
```

`AGENTLABYRINTH_E2E_CHANNEL` 仅允许 chromium、chrome、msedge；只影响测试浏览器。单独验证前端可在 `apps/web` 执行 `npm.cmd run typecheck`、`npm.cmd test`、`npm.cmd run test:e2e`。

也可单独执行固定回归；Manifest 锁定模型、任务、Seed 和基线产物，成功变失败会返回非零退出码。真实模型回归需另备真实基线并显式使用 `--allow-live`：

```powershell
uv run python -m scripts.run_regression benchmarks/regression/course-smoke.json --candidate-revision working-tree
```

首次使用 BFCL 前，从固定官方来源构建本地缓存并校验原始文件及转换结果哈希：

```powershell
uv run python scripts/import_bfcl_subset.py
uv run python scripts/import_bfcl_subset.py --suite java
```

上游题目许可未单独明确，因此原始数据和转换缓存不入库；已缓存后可断网运行。两套 manifest 分别位于 `benchmarks/bfcl_adapted/` 与 `benchmarks/bfcl_java_adapted/`；本地改编评分不等于官方 BFCL 分数。

本地网页需要分别启动 API 与前端（两个终端，项目根目录执行）：

```powershell
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd apps/web
npm install
npm run dev
```

文档任务（007–009）还可选择 MCP HTTP 工具传输。先在第三个终端启动固定的只读 MCP 服务，再在单次运行中选择文档任务和「MCP HTTP」：

```powershell
uv run python -m packages.environments.tool_lab.mcp
```

服务仅监听 `127.0.0.1:8765/mcp`，使用官方 MCP Streamable HTTP；不接收任意任务路径。服务停止后远程工具会失败并留下 Trace，本地 ToolLab 仍可运行。MCP Episode 可在已保存安全点恢复；未完成的远程只读请求可能重发。

品牌展示：前端启动后点击左上狐狸Logo，或打开 `http://127.0.0.1:5173/brand/fox-preview.html`，可重播短动画和阅读设计理念。导航首次播放后保持静态，减少动效设置即时生效；图标来源及验证见[狐狸品牌规范](docs/design/fox-v1/README.md)。

课堂演示：网页顶部「课堂演示场景」选择退货、配送或退款，点「实时演示」或「上下文对照」填好草稿，再核对当前模型并点击运行。Fake用于离线机制演示，真实模型使用本机后端Key；对照仅同任务各运行一次，模型不会被预设偷偷切换。结果支持答案/证据、成对Trace和JSON/CSV；CSV来源列来自保存配置。流程、真实小样本和边界见[成品工作交接](docs/learning/V0.3-classroom-product-20261012.md)。

当前优先实时演示：关联资料在首个环境快照到达后显示在画布旁，Agent读取时自动切换，成功读取和实际提交引用分别标记。环境目录包含干扰资料；网页点击只预览，真正工具调用仍由Agent自主发起。断线保留未确认状态，历史只按游标读取。见[资料侧栏交接](docs/tasks/realtime-evidence-20261012.md)。

对照工作区采用全宽双列配置；保存结果展示两侧通过比例环、Token与耗时条形图。展开「实验历史与趋势」并选择同配置组，可以切换成功率/Token/耗时折线，点击点只回读保存实验。单次或没有样本不补造趋势，未知费用仍显示未知。[看板设计与验收交接](docs/tasks/experiment-dashboard-20261013.md)。

观看 MCP 网络演示：网页切到「单次运行」→ ToolLab 文档任务 `order-status-007` →「更多设置」选「MCP HTTP」→ 选择 Fake 模型并运行。结果区默认的「流程动画」先展示 Client、localhost HTTP、独立 Server；播放到搜索/读取文档步骤时显示远程调用和返回。本地提交答案不会标成 MCP。此视图依据 Trace 展示工具边界，未记录协议握手或 `tools/list` 报文。

浏览器打开 `http://127.0.0.1:5173/`。支持切换“对照实验 (Paired Experiment)”与“单次运行 (Single Episode)”：
- 实验历史看板：读取最近100条已保存实验，可选择同配置组；至少两次兼容运行才显示最近两次的差值。旧产物缺完整协议来源仍可打开，不参与趋势；不跨协议排名。读取、筛选和刷新只 GET，不发模型请求。实际网关费用与原厂参考成本分开展示。
- 对照实验模式：可选择恢复策略对照（Baseline vs Recovery）或 Runtime 对照（Reference vs LangGraph），多选原生评测任务并配置 1–10 个不重复 Seed 与每 Seed 重复次数。运行前显示真实 Episode 数。结果按对照类型展示成功率、适用的恢复指标、Token 与费用，成对表格可穿透审查两侧 Trace。支持 `?experiment_id=...` 与 `?episode_id=...` 刷新回读。
- 已加载的实验可导出 JSON 和 CSV。CSV 每个 Episode 一行，含实验哈希、任务、Seed、重复次数、对照侧、成功判定、用量及指标；未知费用和不适用的恢复指标留空。导出只读取当前产物，不重新调用模型。
- 新实验由异步 Job 运行，Web 可查看状态并在当前 Episode 完成后暂停/取消；暂停后可按原 ID 恢复。不同 Experiment 最多两个并行，单个 Experiment 的成对顺序不变。运行中的 URL 用 `?experiment_job_id=...`，完成后自动切到只读结果 URL。API 提供 `POST /api/v1/experiments/jobs`、`GET /api/v1/experiments/jobs/{id}`、`GET /api/v1/experiments/jobs/resumable` 和 `POST /api/v1/experiments/jobs/{id}/pause|cancel|resume`；旧同步 Experiment API 保留，Job 须走 Job 恢复入口。
- 单次运行模式：可切换原生 ToolLab、8 道 BFCL Python 与 5 道 BFCL Java 固定改编真题，展示数据来源、本地评分协议、结果与完整 Trace。
- 单次运行可选择 Reference/LangGraph Runtime 和关闭/单次参数纠错策略；实际版本保存在 Episode RunConfig。
- 单次运行在安全点本地存档。后端进程意外退出并重启后，可在单次运行表单恢复上次进程留下的 ToolLab、BFCL 或固定文档 MCP Episode；也可调用 `GET /api/v1/episodes/resumable` 与 `POST /api/v1/episodes/{id}/resume`。对照实验保存运行矩阵，可通过 `GET /api/v1/experiments/resumable` 与 `POST /api/v1/experiments/{id}/resume` 继续，同一侧已完成 Episode 不重算。中断中的上游模型请求可能重新发送并产生额外用量；这不保证任意外部写操作恰好一次。
- 失败 Episode 可从结果页显式“单独重跑”，或调用 `POST /api/v1/episodes/{id}/rerun`；新运行有新 ID 与来源记录，原产物不被覆盖。旧 Fake 单次产物若缺保存的模拟场景，会拒绝重跑。
- Trace Replay：按事件类型筛选，使用前后按钮或 Step 下拉定位，左侧查看截至当前事件最近的 Environment Snapshot；历史旧产物缺少中间快照时仍可浏览事件。

真实免费模型必须在本机后端环境配置 `AIHUBMIX_API_KEY` 后用真实 POST 验证，Key 不写入仓库、前端或聊天。页面从 `benchmarks/tool_lab_core/models.json` 候选中筛选 `/v1/models` 可见项，目录缓存 5 分钟；该目录即使使用无效 Key 也可能返回 200，**不能证明当前 Key 的权限、额度或通道**。当前目录默认 MiniMax M2.7 属于历史配置；2026-10-01 新 Key 的已知小样本仅 GLM 5.3 项目内闭环成功，最终免费模型名单仍待确定。默认复测 MiniMax M2.7 与 MiMo V2.5 Pro；`--all-catalog` 会串行复测候选表中的 AIHubMix 模型，每个模型各跑一条 BFCL 和一条 ToolLab，并把真实结果增量保存到 `artifacts/selected-model-results.json`：

```powershell
uv run python -m scripts.verify_selected_models
uv run python -m scripts.verify_selected_models --all-catalog
```

真实进程退出恢复探针支持 ToolLab、BFCL、MCP 与 Experiment，每次一题；先配置本机 Key，MCP 需独立服务，重测时使用新输出目录保留证据。例如：

```powershell
uv run python scripts/probe_live_checkpoint_resume.py --suite mcp --runtime langgraph --artifacts-dir artifacts/recheck-mcp
```

其他路径命令、真实结果与源码阅读见 [可靠性收口记录](docs/learning/V0.2-reliability-closeout.md)。安全点前模型请求可能重发，不能从这些小样本推导外部写工具恰好一次。

运行 CLI Demo 与对照实验脚本：

```powershell
# 1. 运行切片 C 对照实验（4 个原生任务，含 Fake 确定性挽救场景与探索实验）
uv run python scripts/run_slice_c_experiments.py

# 2. 单次运行场景演示 (Exit code 0 或 1)
uv run python -m scripts.demo --scenario success --output artifacts/demo_success.json
uv run python -m scripts.demo --scenario invalid-arguments --output artifacts/demo_invalid_args.json
```

## 架构与阅读入口

```text
scripts.run_slice_c_experiments / apps.api
  → application.run_experiment (Serial pair orchestration)
      → application.run_episode (Baseline: handwritten)
          → HandwrittenRuntime (Terminates on first invalid_arguments)
      → application.run_episode (Recovery: handwritten_recovery)
          → HandwrittenRuntime (Retries once with parameter schema feedback)
      → ToolLabEnvironment (orders db state, query_records, submit_answer)
      → OrderStatusEvaluator (Read-only, deterministic scoring)
      → ExperimentAggregateMetrics & write_experiment

V0.2 paired Runtime comparison
  → application.run_experiment (serial paired orchestration)
      → create_runtime (composition boundary)
          ├─ HandwrittenRuntime (Python scheduler)
          └─ LangGraphRuntimeAdapter (independent StateGraph scheduler)
      → shared EpisodeSession (provider, budget, validation, execution, Trace)
      → canonical Episode / Trace / Evaluation contracts
```

Bootstrap 阶段已由独立节点图取代，不作为当前架构描述。详见 `docs/adr/ADR-010-independent-runtime-comparison.md`、`docs/tasks/V0.2-m1-runtime-comparison-copilot.md` 与 `docs/handoffs/current-state.md`。

## 局限

当前已接入 12 个原生 ToolLab 任务，覆盖 Tool Selection、Parameter Generation、Multi-step Planning、Error Recovery 四类各 3 个。Error Recovery 的确定性结论来自显式 `invalid_then_success` Fake 场景；真实模型小样本只作探索性证据。
当前原生 ToolLab-Core 共 12 条任务（四类各 3 条），包含订单查询、参数生成、文档多步规划和错误恢复；对照实验严格串行执行，不引入队列或数据库；容错仅限 `INVALID_ARGUMENTS` 且最多 1 次重试。BFCL 仅覆盖单轮单工具选择与参数生成，工具不会执行任意上游 Python、Shell 或 API。
真实第三方网关存在限流、退役与通道波动。2026-09-20 实测 GLM 5.3 可完成工具调用但当前账号受限流；GLM 5.2 普通调用可用但 BFCL 工具请求返回 `MODEL_NOT_FOUND`；Gemini 3.8 已退役，Kimi K3 暂无通道。系统保存固定错误码、未知费用和真实 Trace，不自动切换模型。
