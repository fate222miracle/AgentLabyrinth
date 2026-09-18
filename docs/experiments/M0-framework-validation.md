# M0 框架验证记录

日期：2026-09-13。SSOT：V0.5。范围：Codex 框架交付，**不是完整 M0 验收**。

## 最终实际检查

环境：Windows、Python 3.12.4；uv.lock 锁定 Pydantic 2.13.5、pytest 9.1.1、Ruff 0.16.7、mypy 1.20.2。

| 命令 | 实际结果 |
|---|---|
| `./scripts/check.ps1` | 退出码 0；锁定依赖同步成功 |
| 脚本中的 Ruff format --check | 9 个 Python 文件已格式化 |
| 脚本中的 Ruff check | All checks passed |
| 脚本中的 mypy | 9 个源文件无问题 |
| 脚本中的 pytest | 12 passed in 0.42s |
| `uv --cache-dir .uv-cache tool run pip-audit --path .venv/Lib/site-packages` | 退出码 0；No known vulnerabilities found |

依赖审计查询的是运行当时的漏洞数据，不能保证未来无新漏洞。

## 框架对照实验

实际运行：

```powershell
uv --cache-dir .uv-cache run --locked pytest -v tests/contract/test_framework.py -k runner_evaluation --basetemp artifacts/pytest-experiment
```

结果：2 passed，10 deselected，0.33s。

固定 Runtime 测试桩（返回运行 SUCCESS）、任务、预算和运行 seed；唯一自变量是 Evaluator 测试桩的布尔判定。两个测试各自拥有不同 Episode/Agent UUID 和真实执行时间，因此不比较这些字段或性能。

| 输入运行结果 | 评分 | Runner 最终结果 | 断言 |
|---|---|---|---|
| SUCCESS | true | SUCCESS | 通过 |
| SUCCESS | false | FAILED | 通过 |

同时验证 JSON 写入/重新加载相等、唯一结束事件、嵌套输入/事件修改不会污染保存的结果。其他测试验证预算字段拒绝类型转换、Decimal 精度、非法响应结构、事件因果顺序、UTC、配置 hash 与异常脱敏。

这是 **Stub 框架实验**，尚未使用产品 FakeModelProvider，更没有真实模型调用。不能据此声称订单任务成功、Agent 能力提升或 Runtime 预算执行正确。

## 检查过程中修复的问题
- 初始目录写权限阻碍已恢复。
- 首次 Ruff 未排除本地 .uv-cache，误格式化了缓存中的依赖；补充显式排除、按锁文件干净重装并删除旧缓存后重跑。
- pytest 临时目录权限/父目录缺失：检查脚本先创建 artifacts，再指定项目内 basetemp；本机最终检查经授权在沙箱外执行。
- 首次依赖审计发现 pytest 8.4.2 的 PYSEC-2026-1845（重复报告同一公告）；提高下限到修复版 9.0.3，实际锁定 9.1.1，再跑全部检查及审计通过。

## 尚未验证
具体 Fake/Runtime/Executor/ToolLab/Evaluator 行为及其契约、订单 CLI、Token/费用硬预算、工具严格参数、证据评分与真实订单状态转移均等待 Antigravity 实现。后续四种 CLI 场景须追加实际结果，不能用本记录替代。
