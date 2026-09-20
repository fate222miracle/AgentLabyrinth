# M1 BFCL 改编子集阅读指南

## 这部分验证什么

切片 D 用真实 BFCL 题目验证模型能否选择正确工具并生成正确参数。它复用平台已有的 Runtime、Trace、预算和产物读写，只增加数据适配、无副作用环境与独立评分器。结果名为 `AgentLabyrinth-adapted subset`，不能与官方 BFCL 榜单直接比较。

## 源码阅读顺序

1. `benchmarks/bfcl_adapted/dataset_manifest.json`：固定来源提交、原始文件哈希、选题 ID、许可判断和转换哈希。
2. `scripts/import_bfcl_subset.py`：下载或复用缓存，验证哈希，选出 4 道 development 与 4 道 evaluation 题。
3. `packages/environments/bfcl/adapter.py`：把一条 BFCL 题映射为 `TaskSpec` 和严格工具参数模型。
4. `packages/environments/bfcl/environment.py`：通过现有 Registry/Executor 接收一次工具提议，但不执行上游函数。
5. `packages/evaluation/bfcl.py`：独立比较工具名和参数候选值。
6. `apps/api/service.py`：按 suite 白名单选择 ToolLab 或 BFCL，并继续调用同一个 `run_episode`。
7. `apps/web/src/App.tsx`：数据集和题目选择、来源标签、结果、Trace 与 URL 回读。

## 主调用链

```text
Web POST /api/v1/episodes (suite=bfcl_adapted)
  → EpisodeService.bfcl.case_for_task
  → BFCLCase.task_spec + BFCLEnvironment + BFCLEvaluator
  → HandwrittenRuntime
  → AIHubMixModelProvider 或 FakeModelProvider
  → Registry 严格校验一次工具提议
  → BFCLEvaluator 精确匹配工具名与参数
  → EpisodeArtifact JSON
  → GET /api/v1/episodes/{id} 只读回放
```

## 状态变化

1. Adapter 校验 manifest 与本地子集 SHA256，找不到缓存或哈希不一致就停止。
2. Runtime 只拿到公开问题、约束与工具 schema；`goal_conditions.expected_call` 不进入模型消息。
3. 模型提出一个 `ToolCall`。Registry 校验工具名、必填字段、类型和额外字段。
4. Environment 只保存被校验的提议，立即结束；不运行 Python、Shell 或外部 API。
5. Evaluator 读取 Trace，与私有期望调用比较并给出 `tool_name_match`、`argument_match`、`overall_success` 和失败原因。

## 失败路径

- 缓存缺失或来源/转换哈希不一致：拒绝加载，不生成虚构题。
- 非白名单题目 ID：API 返回 400。
- 无工具、错工具、错参数、多工具：独立失败原因，不把 JSON 合法等同于答案正确。
- 模型网关认证、限流、退役、无通道或网络错误：Trace 只保存固定安全错误码。
- GET 历史 Episode：只读本地 JSON，不再次请求模型。

## 可运行实验

```powershell
uv run python scripts/import_bfcl_subset.py
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
cd apps/web
npm run dev
```

浏览器进入“单次运行”，选择“BFCL 改编子集”。2026-09-20 的真实网页证据均使用 `simple_python_0`：GLM 5.3 Episode `6e1ea4db-568b-4db2-9646-75dd44c37d11` 返回 `RATE_LIMIT_EXCEEDED`；GLM 5.2 Episode `b5659967-5c72-4149-9c77-ab8b45b9433e` 返回 `MODEL_NOT_FOUND`。刷新后仍回读同一 ID、结果和 4 个事件。这些结果证明真实请求、错误分类、持久化与回放成立；它们不证明题目通过。正确调用、错工具、错参数、无调用、非法 ID、哈希不一致和只读回放由自动化测试覆盖。
