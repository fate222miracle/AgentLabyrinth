# 已实现能力优化：读取证据、恢复与演示闭环

依据：需求V0.6、UI规范1.3、[ADR-024](../adr/ADR-024-existing-capabilities-integrity.md)、[任务卡](../tasks/optimization-20261004.md)。负责人暂无时间人工验收；本轮优化已实现能力，不扩展V0.3的功能清单，也不替负责人签收V0.2/V0.3。

## 修复的问题

1. 相同任务/模型但不同上下文窗口原来能共享历史比较键，造成不可比结果混入趋势。每侧显式ContextPolicy现在进入固定配置指纹；缺省/null继续省略，四套旧基线不迁移。非法策略拒绝比较。
2. 结构完整的错Episode结果会遮住有效安全点，直接恢复还可能返回错ID。恢复前检查请求ID、事件归属；有安全点时核对Agent/Task/RunConfig及双方配置哈希。错身份/来源拒绝，不调用Provider、不覆盖文件；有效安全点仍可发现。损坏JSON只有在安全点有效时才能重建。
3. CLI产物缺少Fake场景来源，页面虽然有失败重跑按钮，后端仍拒绝。生成时保存既有`episode-inputs`1.0来源；重跑遵守原配置、新ID。窗口1仍因遗忘失败，重跑不是自动改策略。
4. 预览原来只相信报告中的完成标记。现在交叉核对24格矩阵、每条Episode身份/内容哈希、完整Trace链、实际调用/模拟用量、上下文诊断与报告指标及单变量约束。缺失/错属/篡改产物拒绝预览，不重新调用模型或重评历史。报告原子替换。
5. 构造模型消息也消耗时间。构造完成后再次检查时限；超时直接停止，模型计数为0，不记录MODEL_REQUESTED。两个Runtime共用同一保护。
6. 既有CSS隐藏减少动效模式下的数据包，本轮进一步不生成SVG animateMotion；偏好变化即时生效，静态工具状态、输入/输出和手动切帧保留。没有改执行轨迹或评分。

## 源码阅读顺序

1. `tests/integration/test_optimization_integrity.py`：先读可复现失败的输入和断言。理解“文件能解析”不足以证明归属、来源或报告真实性。
2. `packages/application/regression.py`：固定变量如何参与比较；为什么省略旧字段能保留历史指纹。
3. `packages/application/checkpoint.py`的`read_completed_episode`、`resume_checkpointed_episode`；再读`apps/api/service.py`的恢复列表。列表发现安全点与允许覆盖冲突文件是两件事。
4. `scripts/context_ablation.py`的`case_from_artifact`、`ContextReport.validate_artifacts`、`run_ablation`；随后`packages/application/trace.py`的原子写入。报告是对实际产物的诊断投影，不是新的Experiment契约。
5. `packages/runtime/session.py`的`call_model`：预算检查→消息投影→时限复查→计数/Trace→Provider。和既有投影算法一起读。
6. `apps/api/service.py`的`rerun_failed_episode`：读取原Agent/Task/RunConfig、Fake来源与新ID；原结果不改写。
7. `apps/web/src/McpFlowReplay.tsx`的媒体偏好监听与边数据；`apps/web/e2e/acceptance.spec.ts`的实际产物→真实隔离API→网页回读/重跑，以及响应式/键盘/动态减少动效实验。

## 调用链与状态

```text
CLI固定矩阵 → 保存Fake输入来源 → Runner/Runtime/Environment/Evaluator
 → 保存Episode → 从Trace/用量提取ContextCase
 → 逐一核对24个文件与矩阵 → 原子保存ContextReport
 → course_demo预览再核对 → Fake API GET → Web严格校验 → 只读动画

网页明确点击失败重跑 → POST /episodes/<原ID>/rerun
 → 读取原配置与来源 → 新ID执行 → 独立评分 → 新结果
 → 原结果和原报告不改写

恢复列表 → 有效Checkpoint → 检查完成文件
 → 匹配结果：不再列为待恢复
 → 坏JSON：可从安全点继续
 → 错身份/来源：保留安全点可发现，执行恢复明确拒绝，不覆盖

消息构造 → 时限已到 → TIME_BUDGET_EXCEEDED
 → model_call_count=0，无MODEL_REQUESTED，无Provider调用
```

## 失败边界与兼容性

- 有效结果与安全点冲突时保留两者，交给后续诊断；本轮不提供自动删除或替换冲突记录的操作。列表出现不代表恢复一定能执行。
- 没有安全点的历史完整结果继续只读兼容，仅核对ID/事件归属，不因新Schema默认值重算旧配置哈希或迁移文件。这里不是历史产物的密码学认证。
- 报告与Artifact/Trace内部交叉核对，不证明恶意操作者没有同时伪造全部文件。输入字节数仍是记录的消息序列化测量，不是Token或HTTP包大小。
- 原子替换单文件不构成数据库事务；没有多worker/外部写工具的幂等保证。
- Fake场景固定为已有success；缺少来源的旧文件继续拒绝重跑，不猜测。真实模型、最终免费模型和全局Token预算均未在本轮重新验证。
- 浏览器媒体偏好模拟不等于Windows系统开关验收；四种CSS视口不等于真实200%缩放或第二台机器。

## 实际验证

首轮新增12项测试全部失败，确认五类真实缺口；修复后12项通过（6.24s）。随后增加报告与Trace同时篡改的Token/工具计数检查，以及浏览器动态减少动效/四视口验证。首次完整门禁：296项Python通过、四套22格回归零退化、24个上下文实验预期一致；前端严格类型检查发现未使用导入，已移除，不能把这一轮标为完整通过。

最终命令与结果：

```powershell
$env:AGENTLABYRINTH_E2E_CHANNEL='msedge'
uv --cache-dir .uv-cache run --locked python -m scripts.check
```

- Ruff格式/lint及mypy96文件通过，pytest **298 passed**（61.68s）；新增完整性测试共14项。
- 四套历史Fake **2/8/8/4 cells，零退化**；旧配置的比较指纹不迁移。
- 上下文矩阵24条，20成功、4个窗口1失败符合预期；字节/模拟Token/步骤与上轮一致。
- Web严格类型/290模块生产构建、Node **29/29**、npm audit **0 vulnerabilities**；JS gzip149.43KB，上一轮149.35KB。
- Edge **8/8**（24.1s）。实际CLI存档由实际隔离API读取，网页失败重跑保留Agent/哈希、新ID且原文件字节不变。四视口全部节点在画布内、无页面横向溢出、sticky导航、键盘切帧与动态减少动效通过，回放期间零POST。
- diff检查通过。保留1条既有Starlette/AnyIO弃用警告、2条Zod注释构建提示；没有将其隐藏为没有警告。测试服务已退出，8000/5173/8765监听数0。

质量证据：`artifacts/quality/c35f95ef-fe9f-48c3-b045-d4d764504613/`。四套回归报告ID依次为`92f7e68c-5e06-474d-980a-1e5751de9a70`、`5536ea6e-4730-4662-8c17-aaf171c3e54f`、`dc39fadd-48dc-495e-8963-71553f13f94a`、`9846ad82-57df-42c5-bbd7-cab09e173fcf`。

最终浏览器证据：`artifacts/playwright/65b1d25e-eabc-4421-9cfc-8ce248a4009d/`，HTML报告`artifacts/playwright-report/index.html`。实际查看了独立复跑`71eb1fb5-d6dd-408a-a212-2dd454a8abdd`的390/1440画布截图：窄屏三节点纵向、桌面五节点并排。元素整区截图会带入当前滚动位置的sticky导航覆盖，不能当作全部文字同时可见的实机证明；输入/输出与布局自动断言另有记录。没有新的真实模型或远端CI运行。

可回放的手写Runtime/Seed1文档案例：

| 策略 | Episode ID | 保存结果 |
| --- | --- | --- |
| full | `2712ef0d-77f8-4e07-82b1-92ddac13d829` | SUCCESS/approved |
| 最近1轮 | `157532ed-9c91-43ed-9c75-1194f4bb6c91` | MAX_STEPS/max_tool_calls_reached |
| 最近2轮 | `90a3f965-cacd-41f9-a0aa-6e55d09016df` | SUCCESS/approved |

本机隔离预览：

```powershell
uv --cache-dir .uv-cache run --locked python -m scripts.course_demo --preview --artifacts-dir artifacts/quality/c35f95ef-fe9f-48c3-b045-d4d764504613/context
```

看到服务启动后打开`http://127.0.0.1:5173/?episode_id=2712ef0d-77f8-4e07-82b1-92ddac13d829`。替换为表中失败ID可重跑；随后Ctrl+C结束自己启动的服务。目录仅在本机忽略产物中，不随源码Git推送；其他电脑重新运行context_ablation生成自己的ID。已有8000/5173服务时先关闭自己的服务，预览不会接管或终止未知进程。

## 留给负责人的最短人工核对

暂时无需立即验收。方便时用隔离预览看下面三件事；自动检查通过不能替代你的判断：

1. 成功文档任务：最初输入、三个工具、最终答案/证据是否容易理解，画面是否符合课程展示预期。
2. 窗口1失败：看到MAX_STEPS及原策略；明确点重跑后新ID仍保留窗口1，原历史不变。
3. 你的实机200%缩放与Windows减少动效设置：导航、关键文字、播放/切帧和技术Trace仍可用。第二台机器与现场演示随后单独核对。

下一步开发仍是ADR-023交接约定的显式上下文单变量Experiment/API/Web切片，需先单独ADR；本轮不据“额度多”擅自添加数据库或新框架。未提交、未推送、未发布。
