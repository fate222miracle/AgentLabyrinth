# 对照实验与Dashboard布局参考

2026-10-13，负责人要求优化左长条/右空白和纯文字看板，参考成熟Dashboard。需求V0.6，复用现有保存实验；本次只改展示，不改变对照变量、指标、API或历史文件。

## 参考与落地

| 官方参考 | 本项目采用 |
| --- | --- |
| [Grafana Dashboard最佳实践](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/)：围绕问题组织、由概览到细节、明确图表单位与文档 | 先任务通过比例、再用量/耗时、后成对Trace；不同单位分图，详细费用/协议按需展开 |
| [Metabase Dashboard](https://www.metabase.com/docs/latest/dashboards/introduction)：可调整的图表卡片与布局 | 复用暖调工作台的全宽网格，配置分执行设置/任务两区，消除窄长侧栏；不嵌入BI后台 |
| [Grafana饼图](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/pie-chart/)：比例数据与图例 | 每侧各自一个通过/未通过环，不把两侧成功率相加成为一个饼；0/100准确，无样本中性 |
| [Grafana时序图](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/time-series/)：不同系列线/点呈现 | 只连接同comparison_key历史；成功率、Token、平均耗时可切换。横轴是保存时间排序的等间距运行序号，明确不是实际时间间隔 |

本项目决策：原生SVG+CSS足以覆盖双环、双侧条形与最多30次的折线，沿用React，不引入新图表/动画依赖或重做数据查询。不是复刻平台外观；暖调、狐狸品牌、已有语义色保持。

## 数据边界

- 当前保存结果与下次草稿隔离；改草稿Runtime/上下文窗口不改图表来源。
- 看板概览为单场保存结果，不把最近100场不同模型/协议汇总；趋势必须选择兼容组，旧来源不完整的记录仅单独看。
- 环形比例来自保存的独立评测成功率；保存结果可显示真实成功次数，历史摘要缺次数不反推整数计数。无样本不着色，单次不画连接线，零值不当缺失。
- Token是已报告量；耗时来自保存毫秒，不推断推理能力/网关速度或统计显著性。没有费用图，未知实付费用维持未知，参考成本单列。
- 图例不只靠颜色；SVG名称、精确数值、趋势原始表及原成对表保留。点支持键盘只读打开历史，不重新运行。
- 正常历史实看发现两侧数值相同时完全重合；采用实线/虚线、不同点径及重合说明，不移动数值坐标伪造差异。
- 模型可用性说明折叠仍可展开；高级预算表单保持原验证和端口隔离；小屏堆叠与reduce即时显示。

实现/验收与阅读交接见docs/tasks/experiment-dashboard-20261013.md和current-state。
