# 开发与 Git 协作规范

需求以 [requirements.md V0.6](docs/product/requirements.md) 为准。本文落实其第28节，不替代需求和ADR。开始前阅读根`AGENTS.md`及`docs/handoffs/current-state.md`。

## 1. 日常流程

任务/Issue → 工作分支 → 开发与相关测试 → 自查差异 → Pull Request → CI与审查 → 合并main。

- 一个任务有明确问题、范围和验收条件。已有`docs/tasks/`任务卡可先作为引用，不为补历史伪造Issue或审批。
- 从最新main创建短期分支；main保持可运行，不作为日常开发分支。项目当前规模不增加长期develop/release分支。
- 人工分支沿用`feat/<issue-or-task>-<name>`、`fix/...`、`docs/...`；Codex使用`codex/<issue-or-task>-<name>`。没有Issue编号时用真实任务名，不编造编号。
- 先检查工作区。已有修改须先确认归属；不得为了切分支丢弃、覆盖或自动混入他人改动。既有未提交工作迁移分支前核对差异。
- 核心协议、评分或架构变化先关联批准的ADR；普通修复不额外增加审批步骤。
- AI的提交、推送、建PR和合并遵守负责人当次授权；允许开发不等于允许发布。

## 2. 提交粒度与标题

格式：`type(scope): 描述具体变化`，如：

```text
feat(web): show saved submissions in planning comparison
fix(regression): validate the configured runtime target
docs(contributing): define the pull request workflow
```

type使用`feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`ci`；scope按实际模块填写，简单文档提交可省略。中英文描述均可，保持具体。

- 每次提交表达一个可解释、可审查、可回滚的逻辑变更。配套源码、测试和必要说明通常一起提交，避免只合入源码却缺测试。
- 无关UI、Runtime、依赖升级和研究笔记分开提交/PR。按变更目的拆分，不机械按文件数或前后端划分。
- 避免`update`、`优化一下`、`最终版`等无法说明变化的标题。复杂变更的正文解释原因、兼容与风险。
- 提交前检查暂存区：文件范围、实际diff、密钥/本机路径/产物、`git diff --cached --check`。不要只看工作区diff，尤其新增文件也要检查。
- 不重写已发布main的历史，不向main强制推送。现有`254eac0`保留；它是阶段性大提交，不作为后续提交粒度范例。
- 不为了简历制造提交数量、补造时间或把一次工作拆成无意义碎片。

## 3. PR与验证

使用仓库PR模板，关联Issue或任务卡，说明问题、实现、验证、兼容与回滚。

- 一个PR解决一个问题。界面变更附真实截图；协议/执行变化附可追溯测试或Trace说明。私有产物不直接上传。
- 每项验证写实际命令、日期和结果；未运行、失败、受环境阻塞分别标明。旧门禁不能替代本次结果，Fake不能写成真实模型收益。
- 按改动风险运行相关检查，合并前完成需求规定的质量门禁。完整入口为`uv --cache-dir .uv-cache run --locked python -m scripts.check`；本机Edge与CI Chromium分开记录。
- 现有`.github/workflows/quality.yml`在push/PR触发`quality`作业；工作流文件存在不等于某次CI已通过。真实模型授权与离线CI分开，CI不使用模型Key。
- 审查先看范围、契约、失败处理和来源，再看可维护性与格式。AI自查如实标注，不冒充独立人工审批。
- 由负责人确认合并。个人项目可记录负责人自查，不虚构第二位审查者；多人协作时再要求独立审批。
- 单一变更PR可Squash merge为一个有意义的提交；确需保留多个独立变更时先拆PR。合并后删除已无用工作分支，按需要保留可追溯记录。
- 回滚共享分支使用新revert提交，并核对数据/协议兼容；不得用reset和强制推送覆盖公开历史。并非所有数据变更都能靠代码revert撤销。

## 4. 仓库与GitHub设置边界

`.env`、密钥、原始实验产物和缓存不提交；文档提供实验配置、结果摘要、失败及局限。版本Tag只在真实验收并明确授权后创建，不把每次push当版本发布。

建议负责人在GitHub为main配置分支保护或ruleset：要求PR、要求实际CI产生的quality检查通过、禁止强推和删除。检查名称以GitHub真实运行结果为准。多人加入后再配置独立审批数量。

**规范与模板不代表远端保护已经生效。** 是否读取、配置或生效以实际记录为准；无需为此引入提交钩子、commitlint或新的依赖。

## 5. 积累改动的交付

已积累多个任务时，仍按变更目的拆分提交与PR；共享文件按段暂存并核对。确有依赖时可使用关联PR，明确base及合并顺序；不能把最终集成分支的门禁冒称每个中间提交均已独立验证。远端CI结果与本地门禁分别记录。
