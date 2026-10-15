# 对照实验布局与图形看板优化

2026-10-13负责人明确授权优化对照UI；优先级取代此前暂缓对照界面。需求仍V0.6，沿用ADR-018/022/026，纯已实现能力呈现，不改API/Schema/评分/存储，不提交GitHub。

## 交付与阅读

1. 先读[参考与数据边界](../research/experiment-dashboard-20261013.md)、AGENTS和current-state。
2. App的experimentConfigPanel：全宽执行设置/任务选择网格，模型说明折叠，高级设置按需展开，主操作集中显示规模；保存结果在前，下次草稿收起在后。输入状态、handleRunExperiment、Job、历史URL不改。
3. ExperimentCharts：原生SVG双环与双侧条形，结果用保存metrics；每侧环是自身通过/未通过，不合并两侧成功率成饼。成功次数仅使用实际提供值，未知不反推。
4. ExperimentDashboard复用comparableHistory选组，展示单场概览和最多30次同组趋势；HistoryTrendChart成功率/Token/耗时切换，原始数值表和键盘点跳转。时间只排序，X等间距运行序号，明确标注。
5. index.css的experiment-workspace/experiment-setup-grid/chart-*：宽屏两列、小屏堆叠；沿用颜色/焦点，图形无等待动画，不影响读取/运行。
6. e2e/experimentDashboard.spec.ts：真实Fake保存实验→精确0/100%和Token→改草稿不改结果→同组折线/异组不混→键盘只GET→旧产物不变；目录失败、无样本/单次/未知费用与四视口。

状态变化：未运行为配置草稿；显式运行原Job后才生成指标。历史GET校验后绘图，读取失败保留原失败提示；无比较键不画趋势，少于2次不造连接线，total_pairs=0不显示比例颜色。上下文历史纠正成上下文标签，未知轴使用中性名称，不套恢复策略。

## 验证与失败路径

相关测试在apps/web运行`npm run typecheck`、`npm test`、`npm run build`；空闲8000/5173时设置`$env:AGENTLABYRINTH_E2E_CHANNEL='msedge'`并运行`npm run test:e2e`。Fake验收不读取Key，不是实际模型能力证据。

首轮类型/构建/36单元与10项相关Edge通过，布局与趋势截图实际查看后移除重复的两个文字成功率盒子，将保存的成功次数放到环图下，避免图形+重复数字堆叠。最终结果与本机服务恢复见current-state；课堂实际观感/200%真实浏览器缩放与整版签收不由自动测试替代。

完整Edge42/42（1.6m）通过；随后空样本旧进度条/差值补降级，相关3/3通过。正常52条历史只读复核发现同值线完全重合，补实线/虚线、不同点径和明确提示；最终类型/构建、3/3专项（11.3s，含实际Fake Runtime两次同值）通过，产物44b0867e-3f11-4df3-9369-a40aac1e564e，完整产物fd5b48ad-c3be-4099-9d7b-ea6b34a293e0。没有重算或修改历史；最终正常页面/截图/服务信息见current-state。

防错：不混同配置key；不把两侧率相加成饼；不把平均耗时/Token放同一数值轴；不借草稿标签重命名历史；不把日期排序误称真实时间轴；不从四舍五入历史成功率推整数次数；图表/点/筛选不得触发运行POST。既有所有本地改动与历史保留。
