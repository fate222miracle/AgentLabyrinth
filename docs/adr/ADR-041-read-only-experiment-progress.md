# ADR-041：只读查看未完成实验的保存进度

状态：Accepted，2026-10-26。负责人明确选择“按 ADR-041 实施”。依据需求V0.6§0.3/§12/§19；具体实现及实际验证见current-state。

## 问题与选择

真实serial探索计划61bd5e1e…保存了左侧失败Episode，未知用量保护阻止右侧，完整Experiment不存在。现有GET resumable仅返回UUID，页面只有恢复按钮，用户难以找到已经发生的执行。选择新增只读进度GET，保留所有执行/恢复协议，不把部分执行伪装成完整实验。不选择自动恢复、生成虚假最终Experiment或在前端猜测UUID。

## 具体契约

`GET /api/v1/experiments/{experiment_id}/progress`，只读取已冻结计划与各臂文件，不调用模型、工具、目录或写入文件，不恢复任务。

响应`ExperimentProgressResponse`版本1.0：`schema_version`、`experiment_id`、`comparison_axis`、`arms`。每臂包含：

- `episode_id`、`task_name`、`seed`、`repeat_index`、`arm`（baseline/recovery）。ID沿现有uuid5计划规则推导，不由请求传入路径。
- `state`：`completed`（保存了结束Episode，成功与否另看success）、`checkpoint`（只有可读安全点）、`no_saved_record`（没有已保存记录，可能尚未开始或尚未落盘）、`invalid`（保存文件损坏或来源不匹配）。
- `success`：boolean或null；`termination_reason`和`detail`：字符串或null，仅completed返回保存值，invalid只返回固定无效来源说明，不回显损坏输入。未知不补零，不生成未执行侧失败。

复用现有冻结计划/安全点读取与来源校验，核对计划ID、plan_hash、派生任务、Agent/RunConfig及Episode身份/配置哈希。若结束文件存在但坏了，显示invalid，不借安全点冒充完成；不得按当前草稿或新任务文件重解释。缺计划404，非法计划409，错误信息固定且无敏感内容。此接口不提供成功率、Token合计或新的评分。

冻结计划不含独立Runtime版本时，不用当前SDK版本补造历史版本或宣称版本已核对；已保存Episode/安全点的RunConfig仍相互核对。正常完成后计划被清理的实验继续走原结果接口，进度接口不伪造不存在的计划。

## 页面与失败处理

在现有未完成/可恢复实验和Job区提供“查看保存进度”，显式GET才加载。显示每侧保存状态、终止说明，已校验的结束Episode可跳转原只读详情；checkpoint/no_saved_record/invalid不给伪造结果链接。说明“可查看不等于允许继续执行”，不新增自动POST或扩大恢复授权。

读取失败可重读；切换/关闭时取消旧请求，不让旧响应覆盖新选择。保留原历史/草稿、原恢复与Job控制按钮，不改变已保存Experiment GET。新增Zod Mini响应校验、请求ID绑定和状态字段一致性校验。

现有网络失败/未知用量等原因采用共享中文解释；网络错误不直接断言每日额度耗尽，不自动重试。该文案修正可在现有范围先行。

## 验收与边界

离线Fake构造左侧已结束/右侧未保存、只有安全点、损坏文件/外来身份、缺失/损坏计划；检查GET零模型/零工具/输入字节不变。Web覆盖状态、Episode跳转、HTTP失败/错误ID/快速切换、刷新不POST、键盘/窄屏。运行相关Python、Node、类型/构建与Edge专项，记录实际结果；原完整门禁不冒充新测试。

无新增依赖、任务、评分、自动恢复、数据库或真实请求。现有所有dirty/untracked保留，不提交GitHub。回滚只撤入口与只读接口，不修改已保存文件。
