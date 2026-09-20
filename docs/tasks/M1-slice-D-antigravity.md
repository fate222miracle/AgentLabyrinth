# M1 切片 D：真实 BFCL 子集接入（代码验收通过，网页成功实证待补）

SSOT：`docs/product/requirements.md` V0.5（M1 例外增补）；ADR-003/004 Accepted。切片 C 已验收，切片 D 已完成一个真实、固定、非 Live 的 BFCL 改编子集，并从同一 Web 入口运行和查看结果。2026-09-20 Codex 已通过代码、来源、评分和自动化门禁复核；仓库已有两个真实模型通过 BFCL 示例的记录，但当前检出环境没有 Key 和对应忽略产物，尚需补存一次真实模型网页成功证据后再作完整实证签收。

## 先固定来源，再编码

1. 从 [BFCL 官方仓库](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard)选定**一个上游 commit**，核对该 commit 的代码许可和题目数据许可。记录官方原始文件路径、SHA256、题目 ID、下载方式、转换脚本版本；许可不明确时只交下载说明和 Adapter，不提交上游原始数据。
2. 先选 3–5 道开发题和 3–5 道演示评测题，限定非 Live、单轮、恰好一个工具调用、参数结构能用当前 Pydantic/Registry 契约严格表达的题。固定名单，不在运行时随机抽题。记录每道题为何纳入或跳过；开发题与评测题不重叠。
3. 提交机器可读 `dataset_manifest`，字段至少覆盖 SSOT 9.7：`source_name`、`source_url`、`source_version_or_commit`、`code_license`、`data_license`、`upstream_dependencies`、`import_mode`、`transformation_script`、`checksum`、`attribution`、`redistribution_allowed`、`official_protocol_compatible`；另外列出选题 ID、split、原始文件校验值、转换快照校验值与适配器版本。脚本必须能从固定来源重新生成同一子集并校验哈希；校验失败时停止运行。

## 实现边界

- BFCL 通过独立 Adapter 映射成现有 `TaskSpec`、`Environment`、`Evaluator`，仍由现有 `run_episode`、`HandwrittenRuntime`、Trace、预算、Provider 和 JSON 读写运行。不要把 BFCL 特例塞进 Domain、通用 Runtime、ToolLab 或 `OrderStatusEvaluator`。先提出无法用现有 Port 表达的具体阻塞，再改公共契约。
- 题目给模型的工具 schema 与用户问题必须来自锁定的 BFCL 原始数据；期望调用/答案仅给评分器，不能泄露到模型消息。工具不执行任意 Python、Shell 或外部 API；本切片只评工具选择与参数。处理 BFCL 原始答案时只做安全解析，不用 `eval`/`exec`。
- 单次任务在首个工具提议后终止。独立评分器分别给出工具名匹配、参数匹配、整体成功及错误原因；公开本地匹配规则和与官方协议的差异。不能把“JSON 结构有效”直接算成“参数正确”。无工具调用、多工具调用、错工具、漏参、错值、无效 JSON 都要有明确失败结果。
- `EpisodeArtifact` 的任务元数据中保留来源 commit、题目 ID、split、manifest SHA256、适配器/评分器版本；保存原始题目或答案时遵守许可与脱敏边界。结果标为 **AgentLabyrinth-adapted subset**，不得称作官方 BFCL 分数。ToolLab 与 BFCL 不合并成单一总分。
- API 元数据列出数据集、split 和真实任务数；创建 Episode 由用户选择 suite/task，后端白名单校验选题 ID，返回可回读的现有产物。前端显示“原生 ToolLab / BFCL 改编子集”、来源、题数、评分协议、成功/失败和 Trace；单次运行即可，暂不做批量 Experiment 或视觉重做。模型密钥只在后端，Fake 结果明确标为模拟，真实模型失败不可伪装成功。

## 验收

1. 用固定原始文件重建子集，manifest/文件 SHA256 一致；断网时已缓存的数据可运行；未下载或校验失败有明确提示，不退回虚构题。
2. 自动化测试至少覆盖一条正确调用、错工具、错参数、无调用、非法题目 ID、来源哈希不一致、读回不重调模型；所有 Fake 测试无需真实 API。保留真实模型的一次网页运行证据，注明上游题目 ID、模型 ID、Trace、usage、匹配规则和结果。
3. 浏览器能选 BFCL 真题并运行、查看分开的指标和事件、刷新回读同一 ID；ToolLab 旧入口及旧 JSON 继续可用。
4. 交付变更文件清单、源码阅读顺序、调用链、状态变化、失败路径、实际运行记录与 README 复现命令；更新 `docs/handoffs/current-state.md`。Codex 复核来源/许可、评分口径、实际请求与测试后签收。

## 当前禁止

BFCL 全集、Live、并行/多工具、官方榜单评分、第二个公开数据集、任意上游代码执行、数据库、批量任务及 UI 美化。以后扩大范围先更新 SSOT/ADR。

## 2026-09-20 Codex 复核记录

- 固定来源提交、两个原始文件 SHA256、8 个题目 ID、转换快照 SHA256、许可判断和非官方协议标签均已落入 manifest。
- 导入器显式固定 CRLF 字节格式，先校验原始文件和转换结果，再写出子集；已覆盖缓存离线重建、来源损坏和无缓存下载失败。
- 独立 Adapter、无副作用 Environment、Evaluator、API 白名单、Web 选择与 Trace 回读均复用现有主调用链，未修改公共 Domain 契约。
- 全量门禁：`89 passed`，Ruff format、Ruff lint、mypy、前端生产构建和 `git diff --check` 通过。第三方依赖产生 2 条弃用警告，不影响本切片行为。
- 真实服务成功记录：小米 `43895e64-447e-487c-93aa-2f5fa2c418e8`、MiniMax `b3b9f69b-b68e-4372-ad95-b6cce0e7ee66`，均为 `simple_python_0` 的 `exact_call_match`；这些由脚本经 EpisodeService 产生，不冒充网页成功截图。
- 最终待办只有实证留档：在配置本机 Key 的环境中从网页运行上述任一可用真实模型，刷新回读同一 Episode ID，并记录题目 ID、模型 ID、Trace、usage、独立匹配指标和页面证据。不得用 Fake 或已有脚本记录替代。
