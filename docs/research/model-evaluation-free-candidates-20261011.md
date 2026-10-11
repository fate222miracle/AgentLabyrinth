# 跨模型比较与免费候选调研

日期：2026-10-11。依据需求 V0.6；本文件是调研与建议，不是新增已验收能力或契约决策。

## 已核对的实现

- `packages/application/experiment.py` 只支持 recovery_policy、runtime_backend、context_policy 三个轴，成对 Agent 必须使用同一个模型。现有 Web 对照不能直接充当跨模型排行榜。
- ToolLab 有 12 道原生任务；BFCL Python/Java 固定改编子集分别有 8/5 道，合计目录 25 道。开发题与评测题要分开，故障注入题与正常任务要分开。这些小样本不支持通用模型能力排名。
- `packages/evaluation/order_status.py` 检查答案、证据及实际成功工具事件；参数合法不代表任务正确。
- `packages/evaluation/bfcl.py` 检查单次提议的工具名称与参数，不执行数学函数，不评数值答案，且不是官方 BFCL 分数。
- `scripts/verify_selected_models.py` 已支持显式 --model，串行跑一题 BFCL 和一题订单，保存 Episode、独立评分与调用用量。它是连通性/工具闭环冒烟，不是完整能力评测。

## 最小可行比较方案（待实施）

先复用各模型独立运行与保存产物，做只读汇总；不要挪用现有纠错轴、修改既有评分或编造挽救率。若增加公开 model 比较轴，先提交 ADR。

1. 冻结任务/来源版本、环境 Seed、提示词、工具 Schema、Runtime、上下文策略、纠错策略及每任务预算；只变模型。首次比较建议完整上下文、关闭纠错。环境 Seed 不等于供应商采样 Seed；temperature=0 仍不保证复现。
2. 新候选先各跑一题 BFCL、一题 ToolLab。成功后选择同一小组正常任务，逐模型串行运行；可按交错顺序执行模型以减小时段影响。每题重复 2–3 次用于观察稳定性，并保留原始次数。
3. 首指标：端到端成功数/全部发起次数，同时要求运行成功与独立评分通过。另列各套件的评分通过数、工具选择/参数匹配、合法参数率。不能用 Runtime SUCCESS 替代评分。
4. 单列网络、429、鉴权、上游无通道、预算及任务失败。若报告排除明确基础设施失败后的通过率，预先固定分类规则、同时展示分母与端到端率；超时原因不明时不能随意剔除。
5. 效率展示输入/输出 Token、模型/工具调用次数、耗时；成功任务的效率单独统计，避免提前失败看起来更省。耗时包括网络/等待，不能直接解释成模型推理速度；中位数需另做只读汇总，当前不是新增已实现指标。
6. 实际免费通道费用与模型厂商参考价折算分开；未知费用不填零。保留任务级结果与 Trace 入口，不先造加权综合分。

建议课堂表格：模型、ToolLab 成功数/次数、BFCL Python/Java 匹配数/次数、基础设施失败数、成功任务 Token/耗时、Trace。若模型都满分，说明当前任务分辨率不足，再安排长链/证据组合任务的独立切片，不降低现有模型分数制造差异。

## 官网免费候选（未用当前 Key 实测）

以下仅核对官方免费目录与详情页。未新增到模型配置，未发真实推理请求，不宣称当前账户可调用。

| 优先级 | API ID | 加入理由 |
| --- | --- | --- |
| 1 | coding-minimax-m3-free | 与已有 M2.7 作同系列升级比较，观察真实任务通过率与调用开销 |
| 2 | coding-glm-5.3-flash-free | 与已有 GLM 5.3 比较，检验 Flash 的任务效果及端到端延迟，不能预设更快 |
| 3 | coding-kimi-k3-free | 增加 Moonshot 系列样本；早期通道失败不代表现在仍失败，需重新冒烟 |

NVIDIA 的 `nemotron-3-super-120b-a12b-free` 也有官方免费详情页，可作后续不同系列备选，仍需核对本项目的工具调用兼容性。

新模型准入：官网有效详情页 → 本机 Key 权限范围/目录可见 → 真实函数调用 → ToolLab 查询并提交答案/证据。通过后记录最后成功时间与失败码；一次成功不承诺持续可用，失效保留历史产物原模型值。Key 只在本机配置。

官网目录可能滞后：`qwen3.6-plus-preview-free` 仍出现在免费索引，但详情页明确已移除，因此本轮不推荐。免费索引与部分模型详情的请求额度不一致；运行前以账户实际限制及官方动态配额为准，不将每个模型的免费配额相加，Episode 可能消耗多次模型请求。

## 来源

- [AIHubMix 免费目录](https://aihubmix.com/models/free)
- [MiniMax M3 免费详情](https://aihubmix.com/model/coding-minimax-m3-free)
- [GLM 5.3 Flash 免费详情](https://aihubmix.com/model/coding-glm-5.3-flash-free)
- [Kimi K3 免费详情](https://aihubmix.com/model/coding-kimi-k3-free)
- [Nemotron 3 Super 免费详情](https://aihubmix.com/model/nemotron-3-super-120b-a12b-free)
- [Qwen 3.6 Preview 移除状态](https://aihubmix.com/model/qwen3.6-plus-preview-free)
- [开发者指南与动态配额入口](https://aihubmix.com/developers)

## 交接边界

本轮仅源码核对与官方网页调研，没有运行新模型、生成排名或改变 API/Schema/评分。用户说明现有免费模型已跑通；旧日期的失败记录不能当作当前失败结论。下一步先固定比较配置与样本，再实现最小只读跨模型汇总；新增候选需在本机账户放行并验证。
