# 模型准入与工具说明：源码及交接

日期：2026-10-11。需求 V0.6，Accepted [ADR-027](../adr/ADR-027-model-admission-and-tool-descriptions.md)，[任务卡](../tasks/model-admission-tool-descriptions-20261011.md)。本轮只处理之前真实测试发现的两个共性问题。

## 修复与阅读顺序

1. `benchmarks/tool_lab_core/models.json`：新增 M3 和 Flash 实验候选，仅 Flash 的内部 `allow_catalog_missing` 为 true。原默认 M2.7 和历史条目保留；没有加入 Kimi。
2. `apps/api/service.py`：`_configured_model_ids(catalog_optional=True)` 只认可服务端配置中 AIHubMix 型号及精确布尔 true。`_load_configured_models` 和 `_require_live_model` 共用该来源；普通模型仍按目录过滤/预检。公开元信息不暴露可提交的例外字段，缺失目录时说明实际来源，失败仍标 unavailable。
3. `packages/environments/tool_lab/environment.py`：保留原 SubmitAnswerArgs 与 v1.0.0 工具 Schema；v1.1.0 仅改提交说明，答案来自查询记录或读取文档，证据从成功返回的 evidence_id 复制。搜索摘要不等于已获得阅读证据。字段、严格类型、空答案/空证据验证与 Executor 保持。
4. `packages/environments/tool_lab/mcp.py`：传入同一工具说明版本，远程只读服务没有新增权限；提交工具仍在本地。
5. `apps/api/service.py`、`packages/application/experiment.py`：新单次/成对 Agent 显式记录 v1.1.0；Resume、失败重跑及冻结计划按保存 Agent.tool_set_version 创建环境。环境直接使用的缺省和旧别名 v1/tool-lab-v1 保留旧说明，未知版本拒绝。
6. `scripts/run_regression.py`：服务按已保存基线的受支持工具版本构造，再核对其他固定参数。旧基线原文不改；新旧版本指纹不混比。
7. `apps/web/src/App.tsx`、`apps/web/e2e/modelCatalog.spec.ts`：目录失败提示解释例外候选，不把失败标为 live；模型说明仍需展开。浏览器覆盖目录失败下选择实验候选、运行按钮可用、说明可读且没有新建 POST。

## 调用链与状态

正常 Web GET meta → 服务刷新上游目录 → 配置过滤及例外说明 → 用户选择 → POST episodes/stream → 原模型白名单 → 共享目录检查 → 按 v1.1.0 构造 Agent/环境 → 原 Runtime/Registry/Validator/Executor → 只读 Evaluator → 保存完整 Artifact → SSE complete → GET 同 ID 核验。

目录例外只跳过“该显式 ID 未出现在目录”的拒绝。HTTP 429、无通道、网络错误、参数错误、禁用工具及预算终止仍走原失败路径；没有自动重试或隐式更换模型。历史 Agent/hash、工具说明版本、读取源文件均不改写。

## 验证

- 专项 18 项通过，补回归版本兼容后相关 23 项通过；新增主测试为 `tests/integration/test_model_admission_tool_descriptions.py`。
- 最终完整命令：`uv --cache-dir .uv-cache run --locked python -m scripts.check`，本机 Edge（`AGENTLABYRINTH_E2E_CHANNEL=msedge`）。Ruff 格式/lint、mypy 99 源文件、pytest 343 passed（46.97s，1 条既有 Starlette/AnyIO 弃用警告）、四套 Fake 22 格零退化、CLI 上下文 24 案例、Web 类型/构建、Node 35/35、audit 0 漏洞、Edge 29/29（1.1m）及 diff 检查通过。
- 完整门禁目录：`artifacts/quality/cc2b1c0e-71f6-4c35-b782-78a7dc815cc1/`；日志 `artifacts/admission-20261011/quality.log`。浏览器目录 `artifacts/playwright/90dd056c-b6e7-439d-8899-a53c3b672173/` 及 `artifacts/playwright-report/`。
- 发现并修复的验证问题：最初全套 4 个上下文回归测试因脚本只支持旧工具说明而失败；改为按冻结基线版本运行，未修改基线。首轮完整门禁后端通过，新增浏览器测试因漏展开模型说明失败（28/29）；补用户实际展开动作后全门禁通过。不是放宽可见性断言。
- Fake 边界检查涵盖目录缺失/Timeout、字符串 true 拒绝、客户端额外字段拒绝、未授权型号拒绝、Provider 限流不重试、伪造证据失败，以及新旧工具版本恢复/显式重跑。浏览器测试是隔离 Fake 服务的元信息夹具，不等于真实模型推理证明。

## 真实小样本

通过正常 5173 网页代理的 `/api/v1/episodes/stream`，各跑一题 `order-status-007`；统一 LangGraph、无纠错、full、Seed 1、8000 Token、180 秒执行上限、1024 单响应上限、本地工具、v1.1.0。目录例外不通过临时 models_path 绕过；每个 complete 后 GET 核对同一保存产物、版本和终止事件。忽略的本机证据在 `artifacts/admission-20261011/live-results.json` 和 `live.log`。

| 模型 | 保存 Episode | 独立评测 | 实际提交 | 模型/工具次数 | 耗时 | 报告 Token |
| --- | --- | --- | --- | --- | --- | --- |
| GLM 5.3 Flash | `935c9445-dc06-4f41-946f-7fc03ade9759` | true / SUCCESS | approved + document:DOC-007 | 3 / 3 | 32196 ms | 3180 |
| MiniMax M3 | `c22c8823-f06a-4eef-bbc2-bfecfdf0003d` | false / FAILED | approved. Returns are accepted within 30 days. + document:DOC-007 | 3 / 3 | 34990 ms | 4031 |

两者均实际走 search_documents → read_document → submit_answer，没有再提出订单查询；各收到 24 条 Trace 与 1 次 complete，总计 6 次模型请求、7211 个已报告 Token，没有自动重试或第二轮调参复测。Flash 正式目录例外闭环通过；M3 可调用且提交有效证据，但没有遵守状态答案的精确格式，原评测正确拒绝多余原文。不能把“工具均成功”记为任务成功，也不能以一例变化证明说明修复的因果效果。模型候选 notes 已同步此次失败原因。

正常元信息实读为 live：M2.7、GLM5.3、M3、Flash 和 Fake 可见，默认仍 M2.7。Flash 的目录未确认说明仍显示；没有把真实推理成功写成目录已包含该 ID。小样本不承诺后续额度、网络或上游通道持续可用。

## 接手与演示

完整门禁后恢复正常后端 `apps.api.main:app`，API 启动器 PID19328，Web PID40112，loopback 8000/5173；不是仅 Fake 的演示服务。日志 `artifacts/admission-20261011/{api,web}-{out,err}.log`。刷新 `http://127.0.0.1:5173/?mode=single`，选择 M3 或 Flash，展开“模型目录说明”，选 ToolLab 文档 007 后运行查看实时事件；历史链接只读取已保存产物。

接手者新增目录例外须先留带日期真实证据，再在服务端显式型号配置设置精确 true，不能全局取消目录/权限检查。改变工具描述须固定新版本，Resume/重跑沿用保存版本；做模型能力比较时固定任务/版本/预算/Runtime，不以一次改善证明因果。未重测 Kimi、未扩大真实批量/MCP 实测或新模型对照轴。

本机产物、日志、Key/.env 不入库；全部旧未提交改动和实验保留。本轮没有提交推送、远端 CI 或 V0.2 整版人工签收。
