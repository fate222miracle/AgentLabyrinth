# 从操作路径重新审视前端页面

2026-10-04；需求V0.6、UI规范1.3，沿用ADR-022/024。本轮仅改善已实现的Web呈现与交互，不变更公开契约、评分或运行条件。范围见[任务卡](../tasks/frontend-usability-20261004.md)。

## 复核结论与实际修正

从首次配置、完成后复盘、历史读取三个阶段检查，而不是继续增加装饰动效。暖色主题、原生滚动、既有连续过渡和真实事件流程图保留。

| 实际问题 | 实施结果 | 对用户的意义 |
| --- | --- | --- |
| UUID输入只有占位文字，没有label，也不能用Enter读取 | 两处复用HistoryReader，持续可见label、原生form提交 | 可用键盘读取原结果；仍调用既有GET入口 |
| 导航没有可访问选中状态，键盘进入正文须经过导航 | nav有名称、aria-pressed、跳至工作区链接和可聚焦main | 不依赖颜色识别当前模式，可直接进入内容 |
| 单次启动区位于任务/模型之前 | 启动摘要和按钮移到执行配置之后 | 先看任务、模型/Runtime与更多设置，再运行 |
| 八张指标卡常驻，压低工具流程 | 来源与模型独立一行、四个核心指标，费用/版本展开；增加查看调用过程链接 | 快速看到结论，再直接进入输入/输出与流程图 |
| 对照Seed/重复/预算/时限全部常驻 | 原生details集中设置，折叠摘要保留当前值；非法Seed给出按钮旁说明 | 页面更短，修改后收起仍能核对条件 |
| 多选任务的label没有关联控件，描述被固定截断 | 明确命名group，保留完整描述并仅作视觉两行裁切 | 操作范围清楚，可访问名称保留完整目标 |
| 页内锚点触发原popstate读取，Trace被重建而丢焦点 | 页内链接按DOM ref聚焦/滚动，不修改URL/发请求 | 保持结果、回放位置与键盘焦点 |
| 无最终Artifact时configuring样式隐藏实时Trace，包括断线后已收事件 | 单独streaming呈现状态，来自原liveRun而非定时推测 | 空流只说明未知；部分流展示已收到事件并保留运行ID |

用本机1280×720 IAB实际读取同一Fake订单产物，改动前结果面板约483.5px、Trace文档位置约938.4px；首轮紧凑布局结果面板约338.4px。该测量是当时布局快照，字体/内容/窗口改变会改变高度，不作为性能、帧率或所有任务的固定承诺。后续更紧凑标题与直接跳转入口继续降低查找成本。

结果的真实/模拟来源从保存的Provider读取，Token的模拟标记从保存的token_usage.simulated读取；不会根据下次配置或模型名猜测。失败原因常驻核心指标，不藏到费用详情。未知费用仍未知，金额字符串不转float、不重新算价，参考成本不称实付。对照设置收起不会改变表单状态，也不改变运行矩阵。

## 源码阅读顺序

1. `apps/web/src/HistoryReader.tsx`：两处实际复用的原生表单，label与输入ID、Enter、防空/忙碌提交。
2. `apps/web/src/EpisodeSummary.tsx`：只接收已校验的Artifact；来源/核心指标/详情分层，保留缺失与未知事实。
3. `apps/web/src/App.tsx`：导航语义、main/Trace跳转、HistoryReader接既有读取函数；单次启动块顺序、对照details和禁用说明。
4. `apps/web/src/index.css`：复用色彩Token、历史表单、四/两列指标、focus、窄屏规则与任务视觉裁切。
5. `apps/web/e2e/usability.spec.ts`：实际Fake产物、键盘读取/失败、配置与真实运行选择、只读原文件核对、四视口及未知费用响应夹具。

两个组件是现有界面的内部呈现提取，没有创建通用表单框架。读取与执行、业务状态与UI展开状态继续分开；API/Pydantic契约不变。

## 调用链、状态与失败路径

```text
输入历史ID → Enter/读取结果 → HistoryReader阻止默认页面提交
 → 原loadEpisodeById/loadExperimentById
 → 原请求归属与ID校验 → GET和Schema校验
 → 清空旧结果/更新URL → 有效Artifact → EpisodeSummary/Replay
 → 404/坏响应：保留错误与请求ID，不残留旧成功，不自动POST

选择任务/模型/Runtime → 原React草稿状态 → 启动摘要
 → 更多设置/种子预算展开或关闭：只切换原生details
 → 原运行条件与handler → 实际SSE/Job → 保存结果

已保存Artifact → 来源/四核心指标/费用摘要
 → 用户展开：原金额、未知状态、价格/Runtime版本与评分协议
 → 查看调用过程：本页焦点/滚动到Trace；保持Episode URL与只读数据

运行开始 → 原liveRun → streaming布局，显示真实等待
 → 收到有效事件：显示已有节点 → 流结束但没有complete
 → 原interrupted状态，保留实际事件/ID并说明后端未知
 → 只有最终产物读取与校验成功才进入已保存结果
```

动画依然由上一轮useContentMotion与CSS负责，不等待动画才生效。main和Trace的tabIndex=-1用于直接聚焦，不增加普通Tab停靠点。页内链接保留href作为语义入口，正常点击防止浏览器hash导航，由实际ref聚焦/滚动，不触发原popstate结果读取；滚轮/触控不受影响。details不卸载表单，不把草稿覆盖到历史结果；费用详情按Episode ID重置展开状态。HistoryReader不自行发网络请求，不增加自动重试。streaming只改变布局类，不修改SSE消费或停止条件。

空目录/无任务/无模型/非法Seed/非法重复次数提供操作附近提示；加载说明保留真实请求含义。故障输入的演示只影响独立浏览器响应夹具：未知金额为0但is_known=false时仍显示未知；不会改写真实Artifact，也不是实际供应商实验。

## 实际验证与复现

```powershell
$env:AGENTLABYRINTH_E2E_CHANNEL='msedge'
uv --cache-dir .uv-cache run --locked python -m scripts.check
```

首次本机预览因构建子进程spawn EPERM退出，经正常本机子进程权限启动成功；IAB一次点击反馈超时，但实际Fake运行已完成，先读取页面确认结果，没有重复POST。检查前后停止自有预览，再启动拒绝复用端口的测试服务。

新增前三条检查与原11条浏览器用例首次 **14/14**通过（50.6s）。随后补充直接跳转的焦点、未知费用/失败常驻验证，以及实际Token模拟标记与折叠预算摘要。首轮共享门禁后端298项/回归/上下文/Web类型构建/29单元/audit均通过，浏览器14通过、1条跳转焦点失败，不能称整轮通过（质量目录`artifacts/quality/cb68b404-1e1f-490b-b452-96379c25012f/`）。定位到hash导航触发popstate重读，已改为保持URL的显式聚焦/滚动。

复核另发现实时Trace隐藏问题，新增断线用例先真实失败（hidden，`artifacts/playwright/4cb176d2-c33d-4ada-8653-a03dd0eb0687/`），再修布局。下一轮四通过/一失败只是测试误用历史回放名称，实际实时区域名称不同，已修正；专项最终 **5/5**（18.4s）通过，包含空流/实际Fake事件截断、未知费用响应夹具、键盘和四视口。专项目录`artifacts/playwright/8a974feb-a6e7-49df-b55b-c0e37487e3cb/`；实际查看结果/流程/断线/窄屏截图。

最终共享门禁**全部通过**：Ruff格式96文件/lint、mypy96文件、pytest **298 passed**（66.42s，1条既有依赖弃用警告）、四套Fake22格零退化、24上下文消融案例预期一致（20成功/4例预期Fake遗忘失败）、Web严格类型、293模块构建、Node **29/29**、npm audit零漏洞、本机Edge **16/16**（44.1s）与diff检查。JS gzip150.95KB，相比上一轮动效149.73KB增加1.22KB；未加入依赖，既有两条Zod构建提示保留。

质量目录：`artifacts/quality/d3fd261d-f5c6-46dd-8f02-46b4dada019a/`；共享门禁浏览器目录：`artifacts/playwright/4706c259-4326-47f0-9ffc-a09b9940c4a3/`。随后发现全页截图会把非零滚动位置的sticky合成到文档中部，键盘Home又可能被已聚焦Trace消耗；仅修测试捕获，明确回页首并断言scrollY=0，再通过Web类型检查和全部16条Edge补验（HTML报告45.78s）。生产代码没有再次变化，不重复无关后端门禁。

补验目录：`artifacts/playwright/8182346e-75be-4db6-b4f1-55d45d05a0cf/`；HTML报告：`artifacts/playwright-report/index.html`。报告16预期通过、0失败/跳过/不稳定。已实际查看最终桌面与390px全页截图，确认页首捕获正确；回放与断线截图亦保留。检查结束8000/5173/8765无监听，自有服务已退出；`.env`与截图已核对Git忽略。

实际截图（均为Fake，不是模型能力结论）：

- [桌面结果](../../artifacts/playwright/8182346e-75be-4db6-b4f1-55d45d05a0cf/results/usability-saved-results-fo-7658a-led-facts-at-four-viewports/results-desktop.png)
- [窄屏完整页面](../../artifacts/playwright/8182346e-75be-4db6-b4f1-55d45d05a0cf/results/usability-saved-results-fo-7658a-led-facts-at-four-viewports/results-mobile.png)
- [调用流程](../../artifacts/playwright/8182346e-75be-4db6-b4f1-55d45d05a0cf/results/usability-saved-results-fo-7658a-led-facts-at-four-viewports/replay-desktop.png)
- [截断事件流](../../artifacts/playwright/8182346e-75be-4db6-b4f1-55d45d05a0cf/results/usability-an-interrupted-s-149ab--without-inventing-a-result/interrupted-stream.png)

本机预览可使用已生成的上下文Fake报告：

```powershell
uv --cache-dir .uv-cache run --locked python -m scripts.course_demo --preview --artifacts-dir artifacts/quality/d3fd261d-f5c6-46dd-8f02-46b4dada019a/context
```

本轮不读取Key、不调用真实模型、无新增依赖或Git发布。浏览器使用本机Edge，不能据此声称GitHub/Chromium CI或整版验收通过。

## 剩余优化潜力与验收边界

当前最有价值的后续工作是由实际使用反馈决定信息层级：对照结果的首次阅读顺序、窄屏长表格逐列核查，以及长真实模型ID/复杂失败消息的可读性。先用现有数据和页面调整，不引入新看板、数据库或组件框架。拆分App剩余的大段渲染可作为内部维护任务，按单个真实职责渐进提取，避免同时改动网络与运行状态。

真实200%浏览器缩放、Windows系统减少动效、第二台机器与现场签收继续待验；媒体偏好模拟和视口尺寸不冒充系统验收或WCAG全量认证。自动检查不能代替负责人对“更好用”的实际判断。

学习核对：为什么Enter回读不会运行模型；为什么不能用草稿显示历史模型；未知金额为0时为何不能显示零费用；收起配置为什么不会丢值；按钮禁用时如何让用户知道下一步；为什么四张核心指标比八张等权卡更适合复盘。
