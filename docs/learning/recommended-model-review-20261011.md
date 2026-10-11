# 推荐三模型真实小样本：2026-10-11

依据需求 V0.6、ADR-004/006/010/019。负责人将同一 Key 的模型范围更换为截图中的 MiniMax M3、GLM 5.3 Flash、Kimi K3，授权继续前一轮真实测试。原 Key、旧模型及所有历史产物保留，无密钥输出、自动重试、提交或推送。

## 结果

统一 LangGraph、参数纠错关闭、完整上下文、Seed 1、Token 预算 8000、总时限 180 秒、每次响应上限 1024；Provider 按原 13 秒间隔串行发送。每型号先测 BFCL Python 0，能响应者再测订单 001、文档 007；均为开发小样本，不是官方 BFCL 分数或模型排行榜。

| 模型 | BFCL 函数匹配 | 订单答案/证据 | 文档搜索/阅读/提交 | 本轮结论 |
| --- | --- | --- | --- | --- |
| coding-minimax-m3-free | 通过 | 通过 | 失败：forbidden_tool: query_records | 能调用，3 题中通过 2 题 |
| coding-glm-5.3-flash-free | 通过 | 通过 | 通过 | 能调用，3 题中通过 3 题；目录存在异常 |
| coding-kimi-k3-free | HTTP400/no_available_channel | 未测 | 未测 | 当前通道不可用，无法评价能力 |

七 Episode，五评分成功/两失败，13 次模型尝试，成功响应累计报告 13154 Token；M3 7445、Flash 5709，Kimi 失败无 usage，零记录不代表已确认消耗为零。实际费用仍按未知处理，没有新计价表。

每题仅一次，不推断统计稳定性。M3 包含失败任务，不能把它与 Flash 的累计 Token 直接当成功效率排名。耗时包含 13 秒请求调度等待、网络及模型响应，不能从一次 BFCL 的耗时排名模型推理速度。

## 成功输出与失败位置

- M3 BFCL：calculate_triangle_area(base=10,height=5)，独立匹配评分通过；3321ms、647 Token。
- Flash BFCL：calculate_triangle_area(base=10,height=5,unit=units)，可选参数符合允许答案；16056ms、383 Token。仅评函数提议，不执行计算生成数值结果。
- 两模型订单：query_records 查询 ORD-001 → submit_answer 提交 shipped 与 order:ORD-001；答案与真实获取的证据均通过。M3 26978ms/2793 Token，Flash 29529ms/2189 Token。
- Flash 文档：search_documents(return,top_k=5) → read_document(DOC-007) → submit_answer(approved,[document:DOC-007])，三次模型/三次工具，评分通过；42056ms/3137 Token。
- M3 文档：成功搜索并读取 DOC-007，已得到 approved 与 document:DOC-007；第三步提议 query_records(table=orders,filters.order_id=return)，该任务不允许该工具，立即 FAILED，没有执行这次查询或提交答案；35664ms/4005 Token。这是实际行动选择失败，不是限流/网络故障，不放宽权限或改评分使它通过。
- Kimi：首次请求 HTTP400，Provider 映射上游 no_available_channel 为 UPSTREAM_CHANNEL_UNAVAILABLE。没有工具调用，未继续消耗多轮配额；没有 429/每日额度耗尽证据。

## 两个共性问题，后续先处理

### 1. 目录与真实推理不一致

两次新进程读取 `/v1/models` 返回四个 ID：M2.7、GLM5.3、M3、KimiK3。Flash 未在目录，但全部六次模型响应 HTTP200；Kimi 目录可见但推理失败。

本轮沿用忽略目录里的临时候选 models_path，对这三个明确授权 ID 直接调用生产 EpisodeService，不开启目录 GET 前置拒绝；工具权限、Runtime、预算、Provider、Evaluator 和持久化完全沿用。此路径可证明真实任务结果，不能称为已通过网页创建入口。正式服务 `_require_live_model` 仍会拒绝目录缺失的 Flash；目前共享模型配置也未追加这三个 ID，因此没有宣称网页已可选。

后续模型准入需讨论显式可信候选和目录的关系。若改变前置拒绝规则，先记录 ADR，不能静默跳过正式校验或将目录当可用性证明。本轮不修改正式 API/Schema/Provider 或模型列表。

### 2. 文档任务的提交工具说明仍偏向订单

检查 `packages/environments/tool_lab/environment.py` 的 SubmitAnswerArgs：answer 描述要求复制 queried record，evidence 描述要求 query_records 返回的 evidence_id；但文档任务合法证据来自 read_document。Runtime system instruction 又要求严格遵循工具参数说明。M3 已阅读后仍去查询订单，与此说明冲突相符；仅是可解释的潜在影响，未通过消融证明因果。Flash 能完成，不能据此忽略说明问题或断言 M3 通用能力差。

后续应按通用答案/证据来源修订工具描述，并记录工具版本/配置指纹与兼容边界，不改变评分或允许工具集合；核心 Tool Schema 变化按 AGENTS 先走 ADR。然后复用文档题验证实际改进，旧结果不得覆盖。本次仅记录问题，没有借测试中途改 Prompt/Schema 混合条件。

## 证据与交接

| 案例 | 本机 Episode ID |
| --- | --- |
| M3 BFCL | 67da5e61-3e8f-4b0f-bebf-183f6adb2506 |
| Flash BFCL | 19845c3a-534a-475a-9e00-f1734742393d |
| Kimi BFCL | d791f7ee-5341-4697-b079-899105162d32 |
| M3 订单 | 99a8d556-f668-426f-ba92-a912007a634b |
| Flash 订单 | cc43a6d6-3070-4cc5-a4d6-bd47e82be81a |
| M3 文档失败 | 4c22299f-c666-4cba-9e37-10e41db71f4d |
| Flash 文档成功 | 15571ebc-e776-4802-bd7f-9bbf4aa26a9d |

本机忽略证据 `artifacts/recommended-model-review-20261011/results.json`、`catalog.json`、`probe.py` 与临候选配置；完整 Episode 在原 artifacts 目录，可用正常只读 GET 回看，不调用模型。诊断脚本复用前一轮，仅换三个显式 ID；没有覆写前轮记录。所有产物重读一致、型号一致与末尾 EPISODE_FINISHED 检查通过。

源码阅读：EpisodeService.execute_episode → create_runtime/LangGraph → EpisodeSession.observe/call_model → AIHubMixModelProvider.generate → Validator/Environment → OrderStatusEvaluator/BFCLEvaluator → Checkpoint/Artifact。M3 失败在校验而非 Executor；Kimi 失败在 Provider；Flash 成功在最终提交后由独立评分确认。

下一步先完善上述目录准入与通用工具描述的 ADR/兼容计划，再让已验证型号进入正式网页候选；Kimi 保留带日期失败记录并按上游通道变化复测。当前结论是小样本观察，不是连续可用保证、完成 V0.2 签收或跨模型排名。
