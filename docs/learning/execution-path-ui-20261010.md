# 逐次执行路径 UI：源码与工作交接

需求 V0.6、UI 规范 1.3；沿用 ADR-013/014/022/024。负责人 2026-10-10 授权调研后按“节点随实际调用出现＋工具结果与证据卡”开发。任务卡：`docs/tasks/execution-path-ui-20261010.md`。

## 变更与阅读顺序

1. `apps/web/src/App.tsx`：既有 SSE / 历史 GET 入口，三视图共享事件游标；本轮未修改此文件。
2. `apps/web/src/flowFrames.ts`：保留既有事件帧映射；新增 `flowPath` 按当前事件前缀生成任务、每次模型请求、每次工具调用和终止节点。
3. `apps/web/src/McpFlowReplay.tsx`：替换固定模型/调度/工具拓扑，渲染稳定节点 ID、曲线箭头、每次调用入口及当前事件摘要。继续保留原 JSON、MCP 链路、专注查看、历史最终输出。
4. `apps/web/src/flowReplay.css`：暖调节点、中文行动、步骤/工具 ID/文字状态、短时进入与颜色反馈、响应式路径和清晰证据区域。
5. `apps/web/src/useContentMotion.ts` / `ReadableFields.tsx`：复用现有详情切换动效及关键数据呈现，本轮未修改。
6. `apps/web/tests/flowFrames.test.mjs` 与 `apps/web/e2e/executionPath.spec.ts`：前缀/重复调用/旧记录/失败/只读/布局验证。

`acceptance.spec.ts` 的旧“所有固定节点必须同时完整显示”检查改为“当前节点必须完整且可读”。长执行路径不缩成小字全图；旧节点可通过调用入口回看，也可用画布缩放概览。

## 调用链与状态

`历史 Artifact / SSE Trace → flowFrames → 当前 eventIndex → flowPath → React Flow / 当前事件卡`。

- EPISODE_STARTED 创建任务节点，OBSERVATION 更新同一节点；MODEL_REQUESTED 创建模型节点，MODEL_RESPONDED 更新该次模型节点。起始帧不借用下一观察，缺起始事件的旧记录也严格按原事件游标裁剪。
- TOOL_CALL_PROPOSED 创建每次调用的节点，ID 以来源事件位置确定。同名工具重复出现时不合并；结果按 Call ID 对应。
- 拒绝、开始、返回更新该次调用。ENVIRONMENT_UPDATED 更新可点击详情位置，不伪造新的工具调用。
- EPISODE_FINISHED 单独呈现终止原因；节点“结果已返回”不等于独立评测通过。
- 所有节点与状态只取当前前缀。回退时删除未来路径；实时模式只跟随已到达事件，不使用播放定时器推进执行。
- 画布按容器宽度用一至三列蛇形布局；默认对焦当前及上一行，最低自动缩放 0.85，节点正文 14px。旧路径可能在视口外；调用入口可以回到对应保存事件。
- 状态/游标即时更新，详情复用可打断动效，视口使用短时过渡；动态减少动效取消位移与数据包动画。回放速度仍只是阅读速度。

## 失败与真实性边界

参数拒绝保留失败调用及下一次尝试；TOOL_TIMEOUT 标为已记录失败，不显示成功反馈。未知传输不从模型名称推断；提议阶段标“待校验”，拒绝标“未执行”。旧缺 Call ID 的记录保留逐次节点，未记录的工具名称显示未记录。连接中断保留已收到的节点、Episode ID 与未知状态，不当作后端已停止或任务已失败。

BFCL 沿用“记录提议 / 提议已接收”文案；上游函数并未执行。专项中通用 Fake Provider 跑 BFCL 返回原有 `RUNTIME_ERROR/provider_error`，没有工具提议。保留该实际失败并验证不生成假工具节点/结果；不能把本轮测试写成 BFCL Fake 成功验证。正向 BFCL 演示仍使用既有真实保存产物或专用受控 Provider。

最终输出区域明确标为独立的已保存产物；当前阶段卡不借用其内容。工具参数、反馈、证据与原始事件继续通过现有校验边界消费。无 API、Schema、评分、Runtime、模型目录变更，无新增依赖或真实模型调用。

## 实际验证

- `npm run typecheck`：通过，含新 E2E 类型。
- `npm test`：最终 35/35，通过；新增三项路径边界检查。
- `npm run build`：通过，294 modules；最终 JS gzip 156.43 KB，CSS gzip 12.07 KB。既有 Zod 注释提示保留。
- 本机 Edge 完整网页回归：25/25，通过，57.8 秒；产物 `artifacts/playwright/7538e08f-b630-449d-b648-bc640b88d6cd/`。
- 截图复核后补传曲线箭头属性；最终构建与类型检查通过，三项路径专项再次 3/3（11.9 秒），产物 `artifacts/playwright/05419c52-dec3-4188-a926-ba2d6cddbd02/`。
- 随后自查起始游标：补 EPISODE_STARTED 任务节点与观察原位更新，并让路径严格使用原事件游标；新增起始前缀单元测试。最终类型/构建/35 项 Node 与整套 25 项 Edge（1.0 分钟）全部通过，最终截图和报告 `artifacts/playwright/b55b632d-d0dc-453b-b334-745940ae78a0/`，桌面/窄屏再次实际查看。
- 覆盖参数拒绝、重复调用、当前证据、工具超时、BFCL Provider 失败、实际 Fake 事件前缀的受控 SSE 截断、无未来反馈、历史 GET/零 POST、原产物不变、键盘、390/768/1280/1440、动态减少动效。桌面/窄屏实际截图已查看。
- `git diff --check`：通过。没有修改依赖或后端，所以未重复无关的 Python 全套、价格/API 真实推理或远端 CI。

首次本机沙箱构建/Node 子进程 EPERM，改本机受控执行后通过；首轮 23/24 因“尚未收到工具返回”被测试宽泛匹配误判，改为检测实际反馈标题。次轮 24/25 因错误假定通用 Fake 可生成 BFCL 提议，改为检查它的实际 Provider 失败，不改产品使测试假通过。最终全套与箭头补验如上。

截图的固定导航可能覆盖元素截图上方区域；页面溢出和当前节点可见性有独立断言，截图不代表系统级辅助功能认证。真实浏览器 200%/Windows 系统偏好、课堂投影和实际手感仍需负责人签收，V0.2 整版不自签。

## 演示与下一位接手

本机独立 Fake 演示目录：`artifacts/execution-ui-20261010/demo/`，索引 `demo-index.json`。通过既有 `scripts.course_demo --skip-mcp` 生成，明确 `mcp_http_verified=false`，未验证新的 MCP 远程运行。

```powershell
uv --cache-dir .uv-cache run --locked python -m scripts.course_demo --preview --artifacts-dir artifacts/execution-ui-20261010/demo
```

该路径仅当本机生成了演示目录且 8000/5173 未占用时可用；另一台电脑先运行同脚本生成自己的目录。演示 ID 仅本机有效，不作为跨电脑固定数据依赖。

打开参数纠错示例：`http://127.0.0.1:5173/?episode_id=e275778d-3d3f-530f-b531-eadf0412a606`。点击“播放全过程”观看节点逐次展开；滑块到结尾可查看全路径，再点“查询记录 · 失败”核查拒绝。关闭专注查看或 Esc 返回普通布局。该预览只提供 Fake，不改仓库正式模型目录。

接手先查看负责人对形式与投影效果的反馈；不要恢复按工具名合并节点、引入虚构思考/多 Agent/工作流编辑功能，或让历史播放重新 POST。工作区原有 API/预算/上下文/模型/UI 改动全部保留，未自动提交推送。

最终预览启动器 PID29632；8000/5173 localhost。为最后的起始游标回归停止了先前本轮预览启动器/API/Vite，按进程树核对后仅清理自有进程；未停其他服务。预览失败/外部停止后按上述命令恢复，不承诺后台进程在用户重启电脑后继续存在。

随后负责人需要免费模型入口，已停止上述隔离预览启动器/API，保留Vite PID18712，切回README的正常 `apps.api.main:app`（启动器PID33632）。5173代理GET目录实际返回live，四个免费候选与Fake可见、页面200，无真实推理POST。当前访问 `http://127.0.0.1:5173/?mode=single`；正常后端读取 `artifacts/`，本节demo专属ID须在明确需要隔离演示时才切换服务查看。新版UI无需Fake后端，可直接用于正式入口。日志 `artifacts/execution-ui-20261010/normal-api-*.log`。

## 通用任务输出：为什么阶乘题没有120

负责人运行GLM的BFCL阶乘题，实际保存的TOOL_CALL_PROPOSED为 `math.factorial` 和 `number=5`，TOOL_SUCCEEDED仅 `accepted=true`；环境快照保存proposed_call，没有120或自然语言最终回答。阅读 `packages/environments/bfcl/environment.py` 的注册handler与step：只校验、保存参数，返回接收状态；这类评测检查函数选择和参数，不执行上游数学/API代码。不能在前端计算120然后称为本次模型/工具结果；受控计算执行需单独定义环境与ADR。

负责人明确其他任务同样需要交付。调用链：`App`把保存evaluation交给`McpFlowReplay`；输入/输出显示当前环境的公开交付要求，保存卡读取Episode.final_state.submission或proposed_call，并独立显示evaluation.success/reason。流程结束节点和详情读取flowFrames中游标之前最后一份ENVIRONMENT_UPDATED.state，订单/文档呈现答案/引用，BFCL呈现调用签名与参数。尚未结束的当前详情不借用完整最终产物；缺快照/答案明确未保存。运行SUCCESS与评测success=false分开展示，保存卡仍显示失败。元信息改为逐行、较大字号；不改API/Schema/Provider/Runtime/评分或添加依赖。

新增浏览器检查在 `apps/web/e2e/executionPath.spec.ts` 前两项：BFCL显示夹具仅模拟GET显示，不改文件/评分，不代表通用Fake会答BFCL；验证早期不泄露后续调用、结束输出、1440/390视口、评测失败/缺快照、导航零POST及源产物不变。另用真实Fake服务运行订单、文档和参数拒绝，核对实际答案/证据/失败。可运行Web typecheck/build/test与Edge test:e2e（须先停止自己运行的8000/5173服务）。首次类型检查发现findLast超出当前ES目标，改用现有filter/at；沙箱构建/Node子进程EPERM改为受控本机验证，不更改安全策略。

实际验证：Web类型/构建、Node35/35、Edge完整27/27（1.1m）、diff通过；产物 `artifacts/playwright/1094deb0-5627-4f5b-ae28-ba9f6d62992d/`。桌面/390截图复核发现结束详情先放终止字段会压低输出位置，随后仅调整顺序使答案/调用优先，说明覆盖数学及其他函数；最终构建再次通过（JS gzip157.02KB/CSS12.08KB），未重复无关后端全套。正常API启动器PID21408/Web PID30072已恢复，Web代理GET目录live、四个免费候选、页面200，未发真实推理POST。当前服务不读取隔离demo目录；原用户产物和未提交改动保留，不自动提交推送。

## 实时优先：完成后不重新回放

负责人再次明确需实时展示。问题在 `App.handleRunEpisode`：本来用readEpisodeStream实时接收，完成后却setLiveRun(null)，又由Artifact身份变化的effect重置replayIndex=0，因此流程退回起点。现在调用链为点击启动→SSE trace逐条追加liveRun→flowFrames/flowPath最新前缀→complete经过原Schema/事件身份校验→保存Artifact，同时把同一liveRun置completed，替换为确认后的保存事件/实际Model与Environment版本。McpFlowReplay displayMode为live/completed/replay；completed保持终点、展示实际输出/评测，没有播放器，不自动重播。主动点击保存详情按钮才清除liveRun并从起点开启既有只读回放；刷新历史仍只GET，不补发运行。

启动的requestAnimationFrame只聚焦执行区一次，并检查pageRequests当前代次；后续事件不滚动整页。连线短动画表示已收到事件，绝不延迟SSE消费或模拟模型推理；断线、完成与动态reduce停动画。当前SSE仍只覆盖新建单次，Resume/失败重跑/Experiment原入口保持既有契约；BFCL未执行函数仍无数值结果。不要加延时队列让短任务假装复杂流程。

新增executionPath首项测试使用实际已保存Fake文档轨迹，通过受控ReadableStream按段交付给浏览器，验证模型等待/只到提议/尚无反馈/动态reduce/完整终点/complete后节点身份不变/没有播放器/主动回放/刷新零POST/源文件不变。该网络夹具只证明前端处理，不是新真实模型或真实网络时延结论。acceptance既有真实Fake新建闭环也检查completed再主动回放。类型检查修复仅是测试Window的可选字段断言，不放宽公开Schema。

最终Web类型/构建、Node35/35、Edge完整28/28（1.2m）与diff通过；浏览器 `artifacts/playwright/d3c2632c-500d-4db6-bb9c-1d0ac573cb5f/`。增量和完成截图实际查看，随后仅调整ToolLab结束详情输出先于元信息，最终构建再次通过（JS gzip157.36KB/CSS12.08KB）。正常API启动器PID8004/Web PID22188恢复，Web代理目录live、四免费候选、页面200，没有新真实推理POST/后端全套/远端CI或版本签收。打开mode=single新建运行观看实时过程；历史Episode链接仍是保存回放。交接继续保留本轮及原改动，未提交推送。
