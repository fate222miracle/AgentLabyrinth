# M1 切片 D Codex 复核与交接

日期：2026-09-20。SSOT：`docs/product/requirements.md` V0.5。范围只含固定 BFCL 改编子集，不扩展到 BFCL 全集、Live、多工具、批量实验或官方榜单评分。

## 复核结论

切片 D 的代码范围和自动化验收已通过。实现沿用既有 Domain、Runtime、预算、Trace 和 JSON 产物契约；新增内容停留在数据导入、BFCL Adapter、无副作用 Environment、独立 Evaluator、API/Web 选择和对应测试。没有为了 BFCL 修改公共核心 Schema，因此本轮无需新增 ADR。

完整实证签收仍保留一个明确待办：当前检出环境没有 AIHubMix Key，仓库又忽略 `artifacts/`，所以本轮无法重新读取仓库文档中记录的真实成功 Trace，也无法补跑网页成功样本。已有小米和 MiniMax 成功 ID 只能作为先前运行记录，不能声称是本轮或网页实测。

## 变更文件

- `uv.lock`：补齐 `pyproject.toml` 已声明的 FastAPI、Uvicorn、httpx 及传递依赖，使 `uv sync --locked` 在新检出环境可复现。
- `benchmarks/bfcl_adapted/dataset_manifest.json`：将转换脚本版本更新为 `1.1.0`，输出 checksum 和固定题集不变。
- `scripts/import_bfcl_subset.py`：抽出可测试的 `materialize_subset`，增加离线缓存、下载失败、原始来源哈希、转换哈希与写出顺序保护；显式固定 CRLF 字节格式以保持已锁定 checksum 跨平台一致。
- `tests/unit/test_bfcl_import.py`：新增缓存离线重建、来源哈希损坏、无缓存下载失败三条测试。
- `tests/unit/test_bfcl_adapter.py`：仅由 Ruff 统一既有格式，无行为变化。
- `AGENTS.md`、README、任务卡、阅读指南和 current-state：同步实际阶段、证据边界与复现方式。

## 源码阅读顺序

1. `benchmarks/bfcl_adapted/dataset_manifest.json`：来源 commit、两个原始文件 SHA256、固定题目、许可判断、转换 SHA256 和非官方标签。
2. `scripts/import_bfcl_subset.py`：来源获取、离线复用、两层哈希校验和确定性快照。
3. `packages/environments/bfcl/adapter.py`：`BFCLCase` 到 `TaskSpec` 与严格 Pydantic 参数模型。
4. `packages/environments/bfcl/environment.py`：注册一个无外部副作用的工具处理器，首个合格提议后结束。
5. `packages/evaluation/bfcl.py`：独立计算工具名、参数和整体匹配，明确 `official_bfcl_score=False`。
6. `apps/api/service.py`、`apps/api/main.py`、`apps/api/schemas.py`：suite/task 白名单、单 Episode 执行和只读回放。
7. `apps/web/src/App.tsx`：数据集与题目选择、来源说明、独立指标、Trace 和 URL 回读。
8. `tests/unit/test_bfcl_import.py`、`test_bfcl_adapter.py`、`test_api.py`：导入、评分、非法 ID 和读取隔离的验收证据。

## 调用链与状态变化

```text
首次准备
  manifest -> verified raw cache -> deterministic subset bytes -> subset checksum

网页运行
  POST /api/v1/episodes (suite=bfcl_adapted, task_id=白名单 ID)
  -> EpisodeService 选择 BFCLCase
  -> BFCLCase.task_spec + BFCLEnvironment + BFCLEvaluator
  -> run_episode -> HandwrittenRuntime -> ModelProvider
  -> Registry 对首个 ToolCall 做严格参数校验
  -> Environment 记录提议并 done=True，不执行上游函数
  -> BFCLEvaluator 只读 Trace，分别判断工具名与参数
  -> EpisodeArtifact JSON
  -> GET /api/v1/episodes/{id} 从磁盘只读回放
```

模型只能看到原始问题和工具 schema。期望调用保留在 `TaskSpec.goal_conditions`，供独立 Evaluator 使用；Environment 不执行 BFCL 对应的 Python、Shell 或外部 API。一次有效工具提议后任务结束，ToolLab 分数和 BFCL 指标不合并。

## 失败路径

- 本地无原始缓存且下载失败：`BFCL source unavailable: <file>; download failed and no verified cache exists`。
- 原始文件被修改：`BFCL source checksum mismatch: <file>`，停止且不覆盖已有转换快照。
- 转换行为漂移：`BFCL transformed subset checksum mismatch`，在写文件前停止。
- 子集缺失或加载哈希错误：Adapter 拒绝启动 BFCL 目录，不回退到虚构题。
- 非白名单题目：API 400；GET 未知 Episode：404；GET 已有 Episode 不调用模型。
- 无调用、错工具、错参数、多调用：分别给出本地评分失败原因；结构合法本身不算参数正确。
- Provider 认证、限流、模型退役或无通道：Runtime 保存固定错误码，不伪造调用、usage 或成功结果。

## 实际验证结果

- `uv run python -m scripts.import_bfcl_subset`：8 cases，SHA256 `c86068faaf6c6ac69ea3924da3b1c903cc42887cc973555e0382aebf53b4f81a`。
- `./scripts/check.ps1`：Ruff format 51 文件通过；Ruff lint 通过；mypy 55 个源文件通过；pytest `89 passed, 2 warnings in 1.97s`。
- `npm.cmd --prefix apps/web run build`：TypeScript 与 Vite 生产构建通过，27 modules，1.07s。
- `git diff --check`：通过。两条 pytest warning 来自 FastAPI/Starlette 对未来 httpx2 与 anyio 别名的弃用提示，不是本切片失败。
- 仓库记录的真实 Provider 成功：小米 BFCL `43895e64-447e-487c-93aa-2f5fa2c418e8`，502 Tokens；MiniMax BFCL `b3b9f69b-b68e-4372-ad95-b6cce0e7ee66`，391 Tokens。二者均为 `simple_python_0`、一次模型调用、一次工具调用、`exact_call_match`。本轮未因缺少 Key 重跑。

## 给 Antigravity 的最后任务

只补实证，不改契约或评分口径：

1. 在本机后端环境配置 `AIHUBMIX_API_KEY`，不得写入仓库、前端或日志。
2. 启动 API 与 Web，从“单次运行”选择 BFCL 改编子集、`simple_python_0` 和当前可用的真实模型。
3. 页面运行成功后记录 Episode ID、模型 ID、上游题目 ID、usage、`tool_name_match`、`argument_match`、`overall_success`、事件数和 Trace；刷新 URL，确认回读同一 ID 且没有第二次模型请求。
4. 保存不含 Key 的页面证据和本地产物，在 `docs/experiments/` 增补事实记录并更新 `docs/handoffs/current-state.md`。若上游失败，原样记录固定错误码，不能改用 Fake 冒充成功。
5. 不触碰 Domain、Runtime、Evaluator 口径或 manifest 固定集合；如实证暴露公共接口阻塞，先写 ADR 再改。
