# 寻径之狐 01：正式图标与有限加载动画

2026-10-12，需求V0.6、任务卡logo-fox-20261012。负责人已选狐狸、要求尾部柔化及设计理由，随后授权正式替换图标与制作加载动画。本轮保留本地，不提交/推送。

## 形象与设计理由

以[柔化概念稿](../animal-concepts-20261012/fox-soft-path-concept.png)为参考，手写统一SVG：尖耳与朝左侧脸构成狐狸识别特征，卷尾中圆润通道呼应Labyrinth和可观察的执行路径。配色精确为陶土橙#C96442、炭灰#2D2B27；应用图标用深陶土#A6492D及暖白#FFFDF9。眼睛为负空间小孔，尾部不再使用生硬直角。完整理念及汇报说明见[寻径之狐](../animal-concepts-20261012/fox-design-rationale.md)。

正式轮廓依SVG确定，未直接裁切生成PNG，不声称逐像素还原概念图。16px用于识别耳朵/侧脸/卷尾，不承诺所有眼睛细节可见。旧Wayfinder资源和展示页保留为历史。

## 源码阅读与生成

1. `apps/web/public/brand/fox-mark.svg`：唯一主轮廓。silhouette为橙色主体，features为耳/眼/鼻/胸腹细节，fox-cutout遮罩抠除脸部与柔和尾部通道，因此透明标志可放在不同底色。
2. `docs/design/fox-v1/build-assets.mjs`：读取主SVG，生成fox-monochrome.svg、fox-icon.svg、fox-motion.svg。仅改变颜色、应用图标背景/安全区与动画样式，所有d路径一致；无运行时生成或新依赖。
3. `apps/web/src/App.tsx`：既有brand链接加载fox-motion.svg，装饰图空alt和aria-hidden避免重复读品牌名；失败时仅兜底fox-mark.svg一次，不反复请求。保持原导航占位与工作区状态，点击/Enter在新页打开fox-preview.html。
4. `apps/web/index.html`：静态fox-icon.svg favicon，无加载动效或外部字体。
5. `apps/web/public/brand/fox-preview.html`：独立品牌展示、设计理由与小尺寸/单色示例；重播替换同一img的资源，不累积计时器。减少动效监听实时切静态；动画资源失败展示静态和明确提示，不影响业务请求。

修改主SVG后先执行 `node docs/design/fox-v1/build-assets.mjs`，再执行 `node docs/design/fox-v1/verify-preview.mjs`。后者以现有Playwright/本机Edge核验并导出16/32/48/180/512px应用PNG与透明512px标志；静态生产SVG不依赖测试工具。

## 动画阶段与失败路径

- 0–560ms：狐狸整体轻微上移并显形。
- 180–480ms：五官细节显现。
- 380–1330ms：尾部留白由左至右展开，形成完整柔和通道。
- 1330ms后：结束所有动效，恢复基础SVG样式，与静态标志一致；不循环。

使用CSS及SVG遮罩，浏览器动态减少动效时animation:none，完整形象立即显示。无动画样式时主轮廓仍完整。只使用backwards填充，结束不保留动画合成层；最后释放裁剪/变换，避免边缘与静态版本的差异。首轮检查发现Edge裁剪属性返回格式不同、二进制深度断言异常输出耗内存，以及保留动画层时静态PNG不一致；修正检查器的简短断言与最终基础样式后，精确PNG比较通过，未放宽图形一致性要求。

这是一段品牌加载动画，页面无需等待它结束，既有真实加载/失败状态仍单独展示；它不表示模型正在推理、网络已连接、执行完成或评分成功。

## 验证与接续

专项Edge已通过：四SVG路径一致，动画有中间阶段/按期停止，完成PNG与静态PNG逐字节一致，动态reduce、移除动画CSS、键盘重播、390/640/800/1440px无横向溢出以及尺寸导出。报告/图片/录像：`artifacts/brand/fox-v1/verification.json`、preview-*.png、backgrounds.png、fox-motion.webm。实际查看桌面/390预览、深浅背景与尺寸样例、工作台1440/390导航截图；键盘焦点轮廓保持可见。不以自动结果替代整版实机签收。

Web严格类型/构建/35条单元已通过，构建294模块、JS gzip157.69KB、CSS12.08KB，两条既有Zod注解提示保留。新增两项品牌测试覆盖键盘打开独立页面、不改变历史/草稿、零业务POST、导航和预览动画资源失败静态兜底、快速重播/动态reduce。完整Edge33/33通过（1.3m），目录 `artifacts/playwright/42a7e3fc-bddd-4e7e-a933-f1db89a12f76/`；类型/构建/单元/浏览器日志在 `artifacts/brand/fox-v1/`。本轮没有真实模型推理、后端契约或评测变化，不重复无关后端全套或远端CI。

前端运行时打开 `/brand/fox-preview.html` 或点击左上品牌即可查看/重播；浏览器标签图标若缓存旧资源可强制刷新。原Wayfinder的 `/brand/preview.html`仍可只读查看。本轮未提交GitHub，旧实验与当前任务修复全部保留。
