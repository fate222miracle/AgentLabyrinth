# AgentLabyrinth Copilot instructions

Read in this order before editing: full `docs/product/requirements.md` V0.6, `AGENTS.md`, relevant approved ADRs, `docs/handoffs/current-state.md`, then the current task card identified there. Read `docs/product/ui-design-guidelines.md` when changing Web presentation. Old task cards are historical evidence, not the current assignment.

Preserve all existing user changes and untracked deliverables. Reuse the current React/Vite Web flow and CSS tokens in `apps/web/src/index.css`. Do not add infrastructure, dependencies or future-version features without authorization. Public schemas and metric definitions follow the SSOT and their approved ADRs; propose a concrete ADR before changing them.

Run the applicable checks and the full quality gate required by the current task (`uv --cache-dir .uv-cache run --locked python -m scripts.check`). Record actual results, artifact IDs and remaining gaps in `docs/handoffs/current-state.md`; do not reuse old counts as new evidence. Real model/Judge calls, retries and GitHub synchronization require authorization for the current operation. An available key, free model or consumed historical authorization is not permission. Never write API keys to source, tests, output, or frontend code. Follow `CONTRIBUTING.md` for Git collaboration.

## UI 验收防错规则

- UI 中的事件名、状态码和字段必须从 Domain 枚举、API Schema 或一份真实 JSON 产物逐项核对；不得凭常见命名猜测。
- “浏览器验证通过”必须启动真实后端并完成任务卡要求的 POST、GET、Trace 和 URL 回读。只验证无后端错误页不能作为闭环证据；记录实际 Experiment/Episode ID。
- 使用 `pushState` 的页面必须同时处理 `popstate`，验证刷新、前进和后退后 URL 与页面产物一致，且 GET 回读不会重新 POST。
- 历史产物只负责展示。不得自动覆盖“下次运行配置”；历史模型失效时仍按产物原值展示。
- 检查入口 HTML、CSS 和组件三处：禁止外部字体 CDN、正式 Emoji 图标、虚假进度和阻塞式 `alert()`。
- 宣称响应式通过前，实际检查任务卡列出的全部视口并保存截图；构建成功不等于交互验收成功。
