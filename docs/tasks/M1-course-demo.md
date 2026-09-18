# M1 课程演示任务卡
 
SSOT：`docs/product/requirements.md` V0.5。ADR-003 已于 2026-09-18 Accepted；项目负责人已明确授权启动 M1 实现。切片 A 已用 `gemini-3.7-flash-free` 实验签收，当前执行切片 B，详见 `docs/tasks/M1-slice-B-antigravity.md`。

Antigravity 的具体开发顺序、契约阻塞点和证据格式见 `docs/handoffs/M1-antigravity-development-guide.md` 与 `docs/handoffs/current-state.md`。

## 目标
候选 M1 交付一个可联网运行、可在浏览器操作的 Agent 能力评测演示：选 ToolLab 或 BFCL 改编子集、选 AIHubMix 免费模型、运行受预算约束的实验、查看指标与完整 Trace、导出并重读结果。四个月是课程最晚窗口，开发启动后尽快交付第一版可演示闭环；后续组员可在稳定接口上扩充任务和展示。

## 实施顺序
1. **真实模型闭环（已完成）**：AIHubMix 后端 Provider、多轮工具调用消息、真实 usage/未知费用契约已落地；`gemini-3.7-flash-free` 已通过真实 ToolLab Episode。`coding-kimi-k3-free` 的通道故障单独记录，不影响已验证模型的切片 A 结论。
2. **Web 第一屏**：最小 FastAPI 端点接收固定实验配置并调用现有 Runner；React/Vite 提供实验配置、运行状态和单次结果。API Key 从不传给浏览器；页面展示真实/Fake 标识。
3. **外部数据**：锁定 BFCL 上游 commit 和 Apache-2.0 许可文件；建立机器可读 manifest、选题 ID 和校验值。仅接支持一轮单工具调用的非 Live 题目，提供独立评分、适配偏差说明与复现测试。
4. **演示完整度**：最小批量运行、结果对比、Trace 单步回看、JSON 导出；统一视觉设计、空状态、加载状态、错误与断网反馈。录制现场演示脚本并完成一次真实 API 运行记录。

## M1 验收
- 一次真实 AIHubMix 工具调用成功，模型 ID、响应 usage、实际限制和错误路径有记录；不提交 Key。
- 至少一个 ToolLab 多轮任务和一个固定 BFCL 改编子集可由同一 Web 入口启动，运行结果能分清数据来源与评分协议。
- 实验可设置模型、数据集/子集和预算；运行时展示进度与安全错误；结果页展示成功次数/总数、工具选择与参数指标、步骤、Token、费用是否可用、时延。
- Episode 页可按步骤查看公开消息、工具提议、校验、执行反馈和环境状态；回看不重新请求模型。
- JSON 保存完整配置、来源 manifest/hash、Trace 与评测，并能再次严格读取；无真实 API 的自动化测试可重复通过。
- 手机宽度和桌面宽度均可操作；无明显遮挡、截断或不可辨认的错误信息。
- README 提供从配置 Key 到启动网页、运行真实模型及 Fake 备用演示的命令；实验报告说明改编子集不可与官方 BFCL 榜单直接比较。

## 当前不做
第二个外部 Benchmark、多个 Provider、官方 BFCL 全集/榜单评分、真实 Shell/浏览器工具、数据库、分布式调度、登录权限、多 Agent、GridWorld、自动部署。功能只在实际验收链路需要时增加。

## 分工接口
- Codex：公共契约与 ADR、Provider/Adapter 设计、核心评分和预算审查、验收测试。
- Antigravity 或组员：按任务卡实现 Web 页面、普通 API、数据清单与视觉细节；不得静默改 Domain、Trace Schema 或评测口径。
- 项目负责人：已取得 AIHubMix Key；在本机后端环境配置 `AIHUBMIX_API_KEY` 并执行一次真实联网演示；组织最终课程验收。不得分享或提交 Key。

## 快速交付目标
开发启动且本机 Key 可用后，建议前 2–3 个工作日接通真实模型与 ToolLab CLI；第 1 周让网页完成一次真实 Episode；第 2 周接固定 BFCL 子集；第 3 周完善对比、Replay 与视觉。各阶段一通过就保留可演示版本，不等待后续功能。具体时间以实际验证为准，四个月留作课程交付缓冲、组员扩展与报告视频；不提前建立未使用模块。
