# 切片 C 整改复核 — 2026-09-20

## 结论

**复验通过，切片 C 于 2026-09-20 正式签收，切片 D 已解锁。** 下列四项均已修复并由针对性测试覆盖；Fake 四任务浏览器实验得到 Baseline 0/4、Recovery 4/4、可恢复样本 4/4，URL 刷新后可回读并再次运行。

最终门禁：85 项 pytest 全部通过，Ruff、Mypy、前端生产构建通过。原审查问题保留在下文作为整改依据。

## 必须修复的问题

### 1. 禁止工具与错误参数同时出现时仍然重试（P1）

- 位置：`packages/tools/registry.py:112`、`packages/runtime/handwritten/runtime.py:237`。
- 校验器先返回 `INVALID_ARGUMENTS`，Runtime 在判断 `permitted` 前进入恢复分支。
- 实测：任务将 `query_records` 加入 `forbidden_tools`，使用 `handwritten_recovery` 和 `FakeModelProvider(scenario="invalid_arguments")`。出现两次模型调用；两个校验事件均为 `arguments_valid=false, permitted=false, error_code=INVALID_ARGUMENTS`，最终原因却是 `invalid_arguments: INVALID_ARGUMENTS`。
- 未发生禁止工具执行，但违反 ADR-004 的禁止工具立即终止边界，同时会将此类失败误归入可恢复样本。
- 修复要求：未知工具、禁止工具必须先于参数恢复终止，保持明确错误分类；复用现有校验入口，检查 Executor 与 Runtime 两条调用路径。
- 复验：同时禁止且参数错误的调用只允许一次模型调用，零工具执行，原因为禁止工具，实验 `retry_eligible=false`。

### 2. API 路径覆盖完整模型配置（P1）

- 位置：`apps/api/service.py:256`、`packages/application/experiment.py:376`。
- Runner 已保存包含 provider/model/temperature/max_tokens 的模型对象，但随后 `exp_config.update(config_metadata)` 将其覆盖为请求中的模型名字符串。
- 实测：通过 `EpisodeService.execute_experiment` 提交 fake、模型名 `fake-model`、单任务 `order-status-001`，保存的 `config.model` 类型是字符串；实验 ID 为 `ec99c99e-af02-47a6-a9c2-fec560e57108`，产物位于 `artifacts/review-20260920/experiments/`。
- 影响：实际执行参数丢失，配置哈希无法证明模型参数一致。直接调用 Runner 的现有测试无法覆盖此问题。
- 修复要求：执行配置作为权威快照，请求附加信息不得覆盖它；保存实际解析后的 scenario，而非缺省请求的 null。
- 复验：走 API/Service 真实调用链，保存后再读取，断言模型参数和实际配置一致，并验证参数变化会影响哈希。

### 3. 旧实验被默认值重新解释，出现 4/0 挽救率（P2）

- 位置：`packages/application/experiment.py:75`、`:99`、`:408`；`apps/web/src/App.tsx:897`。
- 实测读取现有 `artifacts/experiments/c1c9fe30-d820-4589-81ee-b4a86bcbe964.json`：原始文件没有 `retry_eligible_count`，反序列化后默认变成 0，保留 `retry_recovery_count=4`、`retry_recovery_rate=1.0`。
- UI 使用这个 0，最终展示的口径是“100%，4 / 0 可恢复样本”。新增调用次数的默认 0 也不能当成旧实验的真实测量值。
- 修复要求：先记录兼容决策；旧口径明确标识为旧口径/未知，或者依据完整 Trace 迁移并留痕。不能用默认零值补成新口径，更不能静默覆盖历史产物。
- 复验：用上述旧产物和新产物分别回读，旧缺失指标不展示为已测量的零，新指标分子分母一致。

### 4. 历史 Fake 实验恢复后模型选项不匹配（P2）

- 位置：`apps/web/src/App.tsx:330`、`:407`。
- 静态调用链确认：创建 Fake 实验发送并保存 `fake-model`；历史读取直接赋给 `expModel`；模型目录唯一 Fake 选项 ID 是 `fake`。再次运行时无法在目录匹配，`isFake` 为 false，错误提交为 AIHubMix。直接 Runner 产物中的 `fake-orders-v1` 同样不能作为目录选项 ID。
- 修复要求：按保存的 provider 与模型目录恢复选项，区分 UI 选项 ID 和执行模型名；元数据默认值加载不得覆盖 URL 已恢复配置。
- 复验：浏览器创建 Fake 对照实验、回读、刷新、再次运行，仍为 Fake，任务/种子/场景不变；再验证真实模型历史读取。此项本轮未做浏览器操作，须在修复后补验。

## 本轮已运行的检查

| 检查 | 结果 |
| --- | --- |
| pytest 全量 | 71 passed，2 条依赖弃用警告 |
| Ruff check | 通过 |
| Ruff format --check | 71 个文件无需调整 |
| mypy packages apps/api | 27 个源文件通过 |
| 前端生产构建 | 通过 |
| git diff --check | 通过 |
| 禁止工具 + 错误参数复现 | 确认错误重试两次 |
| Service 配置持久化复现 | 确认模型对象被字符串覆盖 |
| 旧实验读取复现 | 确认 recovered=4、eligible=0、rate=1.0 |

pytest 首次运行因沙箱临时目录权限失败，前端首次构建因 spawn EPERM 失败；授权后分别重跑通过，不将环境错误列为产品缺陷。通过命令为 `.venv\Scripts\python.exe -m pytest -q --basetemp=artifacts/pytest-acceptance-20260920-elevated` 与 `npm.cmd --prefix apps/web run build`。

## 接下来如何推进

1. 先修上述四项，补针对性回归及浏览器验收；保留已有改动，不重写框架或 UI。
2. 切片 C 验收签署后启动切片 D，按现有任务卡固定范围引入真实 BFCL 小子集；未签署前不开展 D 编码。
3. 按用户 2026-09-20 最新分工，下一阶段由 Codex 主写数据集适配、执行环境、评测、API 集成及核心回归；Antigravity 可承担任务说明、界面辅助文案和验收材料，串行交接，避免同时修改相同文件。
4. 真实模型上游失败继续如实记录，不用 Fake 结果替代真实闭环证据；本轮未重新探测上游，昨日可用性记录不代表今天状态。
