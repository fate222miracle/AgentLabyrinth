# Wayfinder 01：选定D后的初版

2026-10-12后续负责人选择狐狸并授权更换图标；当前导航/favicon与动画见[寻径之狐01](../fox-v1/README.md)。本目录资源及原preview.html保留为历史，以下接入/验证记录对应当时Wayfinder版本。

2026-10-04；负责人选择D作为平台图标初版，授权继续优化并制作动态展示。原始四方案保留为历史，最新实用资产以本目录说明为准。

## 几何与使用

保留开环、两阶路径与右出口；手写SVG统一圆弧、6.5单位线宽和箭头间距，去除生成纹理，采用现有#C96442。应用图标使用#A6492D底与#FFFDF9反白，符号四边留安全区。导航保持既有文字/尺寸，旁边的装饰图标有空alt与aria-hidden，不重复朗读产品名；favicon无需字体或外部服务。所有静态、动态和应用标志使用相同四条路径；不将参考PNG直接缩成favicon。

改进概念图由内置image_gen基于原D编辑，[提示词](refinement-prompt.json)与[参考图](../logo-concepts-20261004/D-wayfinder-refined.png)保留；该PNG仍是概念稿。正式几何由SVG确定，导航继续使用现有文本字体，不直接采用生成图的文字。

## 源码与调用链

1. `apps/web/public/brand/wayfinder-mark.svg`：透明标志；`wayfinder-icon.svg`为反白应用图标，`wayfinder-monochrome.svg`为单色。
2. `apps/web/src/App.tsx`的brand-mark → 装饰img加载有限动态标志，初次加载后保持完整图标；`index.css`保留原导航占位，`apps/web/index.html` → 静态SVG favicon。导航品牌为原生链接，点击/Enter在新页打开完整动态展示，不改当前任务状态。
3. `apps/web/public/brand/wayfinder-motion.svg`：圆环900ms、路径560ms后绘制760ms、箭头1100ms后呈现520ms，总计1620ms，均只播放一次后停留完整标志。没有模型/执行状态含义。
4. `apps/web/public/brand/preview.html`：独立动态展示，原生按钮/Enter重播，通过替换同一img资源重新起播；新播放替代旧播放，没有定时器累积或后台循环。监听reduce后替换静态标志；SVG本身也有CSS媒体偏好兜底，不支持CSS动画仍呈现完整静态路径。
5. 本目录`verify-preview.mjs`：用项目现有Playwright/Edge打开本地展示文件，校验路径一致、有限动画、键盘重播与动态reduce、390px无溢出，直接由SVG导出PNG。可以在仓库根目录执行`node docs/design/wayfinder-v1/verify-preview.mjs`复现。

SVG/PNG无需新增运行依赖。PNG包括16/32/48/180/512px应用图标和透明512px标志，存放`apps/web/public/brand/`。SVG圆角应用图标与透明标志可独立使用；彩色以正式SVG的精确色值为准。

## 验证与边界

先核对静态图标与导航，再核对动态展示；不因纯品牌变化重复运行无关后端实验。本轮不读取Key、不调用真实模型、不修改API/Schema/评分、不提交/推送。Logo首次生成优化稿已实际查看。

初次Web构建/单元在Windows沙箱被spawn EPERM限制拦截，类型已通过，构建/测试失败不计通过；正常本机测试权限重跑后构建293模块/JS gzip151.00KB、Node29/29通过。两条既有Zod构建提示保留，无新增依赖。动态核验脚本初次将aria-labelledby末尾误当作d属性，检查器修正后完整通过；此为校验器问题，不是符号几何差异。

动态核验已通过，报告`artifacts/brand/wayfinder-v1/verification.json`；桌面/窄屏截图、实际录制`brand-motion.webm`同目录。实际查看桌面/窄屏成图与透明512px导出：符号和16/32/48样例保留入口/出口轮廓；16px是简化轮廓用途，不承诺所有细节可读。

最终Web严格类型、构建、Node29/29与Edge16/16（51.0s）通过。浏览器目录`artifacts/playwright/85c0fff9-fc9c-43b4-a0e5-0ab9c2e9c911/`，其中`results/usability-saved-results-fo-7658a-led-facts-at-four-viewports/results-desktop.png`已实际查看，导航显示选定D标志；四视口与原流程/历史/故障路径保留。HTML报告`artifacts/playwright-report/index.html`。

打开`apps/web/public/brand/preview.html`即可本地播放；前端运行时可访问`/brand/preview.html`。2026-10-04负责人授权将图标/动画接入项目并提交GitHub；主导航初次加载有限短动画，随后保持静态，可点击标志打开完整展示；减少动效由SVG媒体规则直接降级。不加入持续循环或延迟业务加载。本次发布前需退出自有预览、通过完整共享门禁并扫描待提交源码，结果见current-state；此前展示会话97349已停止，不结束无关进程。

正式接入后的发布前完整门禁已通过，Python298、Web29、Edge16（47.0s），结果与密钥排除记录见current-state顶部；不是整版人工验收。公开资产可随生产构建使用，不依赖本机生成目录、录屏或报告。
