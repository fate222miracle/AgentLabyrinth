# ADR-023：V0.3 上下文管理首切片

- 状态：Accepted
- 日期：2026-10-04
- 依据：需求 V0.6 §0.3、§6.8、§19、§20；负责人明确授权开始 V0.3。

## 问题、假设与范围

EpisodeSession 每次把完整历史发给 Provider，重复携带早期工具结果。固定原生订单/文档任务可检查：缩短请求是否减少输入量，是否因丢失证据破坏完成任务的路径。完整历史为基线，仅更改上下文策略；任务、Seed、Prompt、工具、模型、恢复策略、Runtime 和预算固定。

首批交付运行时投影和离线 CLI 消融模板，不扩展 Experiment 的既有对照轴、Job API 或页面配置入口。CLI 通过正式 Runner、Environment、Evaluator 和 Artifact 产生结果；独立版本化诊断报告引用 Episode 与配置哈希，明确不是新的 Experiment 契约。历史 Episode 可用原网页只读回放；同步 Web 消费字段校验与配置说明，避免上下文结果冒充完整历史运行。

假设：最近完整工具轮次可减少模型可见消息，但未必提高成功率，也未必减少累计 Token（重复搜索可使消耗增加）。Fake 的 Token 沿用固定模拟值，新增序列化消息 UTF-8 字节数用于测量输入体积，不能换算或冒充模型 Token。原生文档 Fake 决策先检查搜索结果再检查读取结果；窗口 1 可导致搜索/读取循环。它证明工程行为和遗忘风险，不是对真实模型能力的结论。窗口 2 为控制组，订单短链为无伤害对照。

## 契约与兼容

1. 新增 Domain `ContextPolicy` schema 1.0：`full` 或 `recent_tool_rounds`；后者须指定 1–100 个完整轮次，full 禁止携带窗口。算法版本固定 `tool-round-window-v1`，不提供截断单条消息、摘要、持久记忆或自动选策略。
2. AgentSpec 增加可选 `context_policy`，显式配置要求 AgentSpec 1.2；旧 1.0/1.1 读取与默认写入保持原状，缺省字段从序列化剔除，既有哈希/四套基线不重写。新配置进入现有 Agent 哈希与 Checkpoint 身份验证。既有恢复/框架对照必须固定相同上下文策略，拒绝混合变量。
3. 请求前的纯投影保留初始 system/user 前缀，以及最后 N 组完整 assistant Tool Call 和对应 tool 反馈；不读取 Task 私有目标或环境快照。工具匹配、不重复 Call ID、无孤儿反馈、无未完成调用是前置校验，异常在 Provider 调用前明确终止，不静默退回 full。
4. Session 的完整历史与 Checkpoint 不截断；两种 Runtime 共享投影，恢复后按原配置重建相同请求。传给 Provider 的消息深拷贝，避免 Adapter 修改存档。
5. 显式配置的 MODEL_REQUESTED 在现有 JSON payload 添加 `context` 诊断（算法/策略/轮次、历史及可见消息数、剔除数、请求消息字节数）；消息正文和私有目标不复制入诊断。默认历史 payload 保持原状；Trace/Episode/Checkpoint 外层 schema 不变。统计仅为消息部分，不含工具 Schema、Provider 包装或真实 tokenizer。
6. CLI 固定原生 001/007、Seed 1/17、两 Runtime、full/窗口1/窗口2，24 Episode；每组三侧从同一 Agent 构造，记录实际评分、终止、步骤、模拟 Token、输入字节及哈希。已有输出目录拒绝覆盖，失败的预期结果保留，验证不符合预期或运行时错误导致非零退出。离线预览验证完成的ContextReport后复用既有课程Fake服务，不读取Key、拒绝真实请求与端口占用。

## 验收与后续

严格参数/孤儿与多调用匹配/深拷贝/原哈希、两 Runtime 正常与遗忘失败、完整历史的跨进程恢复及配置篡改拒绝、CLI 单变量及报告落盘均须测试；跑完整门禁和四套 Fake 回归。无新增依赖；真实模型和 UI 创建入口属于下一切片，未执行不宣称通过。V0.2 待验项不清除，不自动提交/推送/发布。

回滚时去掉显式 context_policy 即恢复 full；保留新 schema 读取能力才能继续访问已生成产物，不能把窗口产物的配置重写为 full。
