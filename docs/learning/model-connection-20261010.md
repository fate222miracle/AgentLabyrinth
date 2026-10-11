# 2026-10-10 模型连接失败与每日额度判别

SSOT：V0.6；本次仅现场诊断与恢复自有服务，未改变API/Schema/Provider/评分。

## 现象与调用链

最近保存的MiniMax/GLM文档任务约5秒失败，Episode.detail为 `provider_error: NETWORK_CONNECTION_FAILED`。阅读 `packages/providers/aihubmix.py` 的 `_send_http_request`：HTTPError先分类（429→RATE_LIMIT_EXCEEDED），URLError→NETWORK_CONNECTION_FAILED；错误由Runtime终止后保存，Web读取既有Artifact。此类记录没有HTTP429或每日额度耗尽的响应，不能从截图推断日额度。

## 本次实际验证

1. 不携Key请求公开 `/v1/models`：当前Windows系统代理路径HTTP200，直连HTTPS为URLError/TimeoutError。说明该电脑当前需要可用代理通路，不能因浏览器本地页面可打开就假定模型网络可用。
2. MiniMax免费模型单次最小Chat Completions：max_tokens=64、HTTP200、有choices、usage总Token108；仅验证当前还能请求，截断短响应不当作任务通过，也不证明其他模型有额度。
3. 核对并重启本轮自有API，保留Web/旧产物。不修改Windows代理、DNS、TLS校验或模型配置。
4. 平台经5173代理真实BFCL单题 `bfcl-simple_python_1`：MiniMax、Reference、max_steps=1；新Episode `4aad38d6-2efb-4bbc-8551-f952240b7dd9`，SUCCESS、独立评测true、3561ms，保存 `math.factorial(number=5)`。本环境不执行数学函数，仍不产生120。CLI小请求与平台单题共两次真实请求，无批量Seed/Repeat或文档多轮重跑。

原失败脱敏记录没有底层reason，不能确证旧代理缓存或某次网络波动。证据支持“当前MiniMax没有完全失去请求能力，项目重启后真实请求恢复”，不支持断言所有模型未限额或永久网络修复。

## 当前服务与接手

API启动器PID30104、Web PID22188，正常 `apps.api.main:app`，loopback8000/5173；日志 `artifacts/execution-ui-20261010/normal-api-*.log`，正常产物在 `artifacts/`。用户可刷新后新建单次实时运行。Key始终仅在后端本机配置，未打印、传给前端或入库。没有代码逻辑修改，无需重复无关全套门禁；未提交推送或签收版本。

再遇连接失败时先检查代理/HTTPS通路；429须结合上游错误与账户限额才能区分分钟限流和日额度，不能盲目自动重试已可能扣量的推理请求。[AIHubMix官方错误与重试说明](https://aihubmix.com/developers)。
