# ADR-003：课程演示的外部数据、真实模型与 Web 入口

## 状态
Accepted（2026-09-18；项目负责人批准启动 M1 切片 A，三项契约阻塞点已裁决）

## 背景
项目负责人需要在约四个月内交付可现场演示的仿真实验平台，并希望越快形成可运行版本越好；四个月不是首版排期。M0 已有 Fake + ToolLab 的多轮闭环，但没有真实模型、外部评测数据和 Web UI。第一版希望通过 AIHubMix 免费模型联网调用。

## 候选方案
1. 一次接入多个大型 Benchmark 与多个模型供应商。
2. 固定一个外部子集和一个真实模型网关，保留 ToolLab 仿真实验，再开放最小 Web 闭环。
3. 只做静态页面和 Fake 演示。

## 建议决策
- 建议方案 2。M1 包含原生 ToolLab 与一个 BFCL 非 Live 改编子集。BFCL Adapter 固定上游 commit、选题 ID、来源许可和文件 SHA256；默认不把整个上游数据复制进仓库。BFCL 改编任务与原生 ToolLab 指标分开展示，不合并成一个“总分”。
- BFCL 初期只接一轮恰好一个工具调用的题目；多工具并行、Live、Web 搜索及官方可执行评分留待明确需求。评分器明确记录所采用的本地匹配规则，并把结果标为 `AgentLabyrinth-adapted subset`，不宣称官方 BFCL 分数。
- 真实模型通过后端 `ModelProvider` Adapter 使用 AIHubMix 的 OpenAI 兼容 Chat Completions；候选准确模型 ID 为 `coding-kimi-k3-free`，实际请求 ID 从配置读取，Key 从后端环境变量 `AIHUBMIX_API_KEY` 读取，浏览器只提交模型选择和实验配置。保留 Fake 作为测试与讲解路径。模型页公布的配额与工具调用能力须在首次联网验收时实测，不能在代码中当作永恒保证。
- Web 入口按现有技术基线使用 FastAPI 与 React/Vite。M1 页面为实验配置、结果、Episode Trace/Replay；本地 JSON 产物是首个存储边界，后续数据库按实际需求和独立 ADR 再引入。
- API、页面与 BFCL Adapter 调用既有 Runner/Trace 契约；不把 BFCL 评分规则或 AIHubMix 响应类型写进 Domain 或 HandwrittenRuntime。
- 三项契约阻塞点裁决如下：
  1. **多轮工具调用消息**：在 `Message` 契约中增加可选 `tool_calls: tuple[ToolCall, ...] | None = None`，`HandwrittenRuntime` 在工具调用成功后成对追加 assistant 消息（含 tool_calls）与 tool 反馈消息，满足 OpenAI 标准格式且保持 call ID 关联。
  2. **真实 usage 与费用**：真实 Provider 返回时显式设置 `TokenUsage.simulated = False`；在 `EstimatedCost` 增加 `is_known: bool = True`，未知或未验证价格（如 aihubmix free tier）标为 `is_known = False`，价格表版本记录 `aihubmix-free-unverified`，避免误记为 `$0`。
  3. **BFCL 题目与 Runner**：按 ADR-004 顺延至切片 D接入单轮题目，作为独立 Adapter 与评分器接入，结果标记为 `AgentLabyrinth-adapted subset`。

## 原因
第一版可以同时证明“受控环境里的多轮 Agent 行为”和“国外公开基准上的真实模型工具调用”，并能从浏览器完整演示。固定子集、版本和评分口径可复现，也便于组员后续增加其他 Suite。

## 代价与风险
- BFCL 初期只覆盖工具选择与参数生成，不能代表 Agent 全部能力。
- AIHubMix 的免费模型、限额和网络状态会变化；现场需预跑真实模型并准备已明确标记的 Fake 产物用于讲解。没有 Key 时不能声称真实 API 测试通过。
- JSON 产物适合单机演示，不提供并发写保证；迁移到数据库另立 ADR。

## 回滚方式
BFCL Adapter 与 AIHubMix Provider 作为独立实现可移除；旧 M0 JSON Trace 保留并继续可读。任何 Schema 升级配套显式版本和旧产物兼容测试。

## 依据
- [BFCL 官方数据说明](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/bfcl_eval/data/README.md)
- [BFCL 官方局部评测说明](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/README.md)
- [AIHubMix 官方 Quick Start](https://docs.aihubmix.com/en/quick-start)
- [AIHubMix Coding Kimi K3 (free) 模型页](https://preview.aihubmix.com/model/coding-kimi-k3-free)
