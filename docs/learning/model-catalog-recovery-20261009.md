# 模型目录临时失败：排查与修复

2026-10-09，负责人反馈网页无法读取模型目录。

## 实际证据

本轮直连8000的GET `/api/v1/meta` 返回live，网页5173代理同路径返回200。目录可见 MiniMax M2.7、GLM5.3、MiMo V2.5/V2.6 与Fake；只证明ID可见，不证明真实调用权限/额度/通道。本轮没有新模型推理请求。

旧后端目录失败只设置unavailable并清空真实模型，可缓存30秒；异常详情未记录。旧前端只在挂载时GET一次，初次失败后不会自动重读。后端恢复时，已打开页面仍可停留旧状态。这是明确的恢复体验缺口；当时具体上游失败原因没有记录，不能断言为超时、Key失效或供应商下线。

## 修改与源码顺序

1. `packages/providers/aihubmix.py::list_available_model_ids`：目录TimeoutError沿用已有REQUEST_TIMEOUT错误码，和模型请求一致，不输出原异常信息。
2. `apps/api/service.py::_get_live_model_ids`：记录脱敏错误码/异常类型，不记录Key、URL认证头或原异常正文。原成功300秒/失败30秒缓存、目录过滤与真实调用预检保持不变。
3. `apps/web/src/App.tsx::loadMetadata`：复用同一GET路径，首次初始化默认值；后续重读保留仍有效的模型和任务/预算草稿，不触发POST。复用RequestGeneration保护最新读取，开发StrictMode首次双请求或旧失败晚到不能覆盖已恢复状态。首次HTTP整体失败后重读仍初始化任务。目录错误独立于Episode/历史错误，重读失败不会清除其他运行错误。
4. 页面增加“重新读取模型目录”按钮和30秒缓存说明；读取中/运行中禁用按钮。未将失败缓存绕开，也未改成无限轮询或允许未知模型运行。

## 检查与接手

16项Provider/目录专项Mock通过，包含30秒内不重复上游查询、到期后恢复live、错误日志不含私有详情、目录超时码。本机Fake浏览器覆盖unavailable与HTTP503后的主动重读、初次恢复初始化、有效草稿不重置、只GET不运行；最终完整门禁与预览进程见current-state。首轮门禁335 Python通过、浏览器20通过2失败：测试未考虑StrictMode双读且误以为独立Fake目录含真实模型；修正为显式页面Mock目录，并补旧请求延迟返回验证，2/2专项通过。发现的晚到覆盖风险在共享读取函数修复，不移除StrictMode或改为读取真实Key的测试服务。

以后出现同样提示：先点重新读取；30秒缓存内仍失败可稍后再读。若仍失败，查看后端的 `AIHubMix model catalog unavailable (...)`，按REQUEST_TIMEOUT、NETWORK_CONNECTION_FAILED、AUTHENTICATION_FAILED、RATE_LIMIT_EXCEEDED等原因进一步处理。历史旧失败无法从新日志倒推。目录live不等于模型实测通过，仍按带日期的真实任务结果选演示模型。

API/Schema/评测/恢复契约没有改变，之前未提交改动保留；本轮未提交推送。无自动后台监控、新依赖或真实模型批量测试。
