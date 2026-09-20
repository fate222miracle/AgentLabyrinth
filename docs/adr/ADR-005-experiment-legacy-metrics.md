# ADR-005：实验历史指标兼容

## 状态

Accepted（2026-09-20，切片 C 验收整改；落实已要求的历史兼容，不扩大范围）

## 决策

- 旧 Experiment 1.0 文件中缺失的可恢复基数、调用次数和新增准确率读取为 null，表示未统计；不能默认为 0。保持旧文件及其配置哈希不变。
- 新实验显式写入上述指标。无可恢复样本时保存基数 0、恢复数 0、比例 0；界面应结合基数解释。
- 旧实验保留原比例，UI 明示其历史基数未统计，不能将其视作新口径的可比较结果。缺失比例显示未统计，不补成测得的 0%。
- 此次为 Application DTO 对旧缺失字段的兼容读取修正，保留 schema_version 1.0；不变更 Domain、Episode、Trace 或新实验计算规则。未来改变评分含义必须单独升级版本。
- 实验执行配置不可被展示用 metadata 覆盖。Fake scenario 单独保存在 config.scenario，不混入 ModelConfig。

## 验证与回滚

版本控制中的 `tests/fixtures/legacy_experiment.json` 用于离线兼容回归；新实验通过 Service/API 回读验证。回滚只涉及读取和显示规则，不改写任何历史产物。
