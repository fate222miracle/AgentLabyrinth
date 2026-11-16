# Blender + MCP 演示与交接

V0.4 已本地收工。本轮按 [ADR-048](../adr/ADR-048-blender-mcp-asset-demo.md) 验证 MCP 如何把一个结构化建模请求送入 Blender，并将真实的调用过程与生成资产一起展示。现有 GridWorld 负责游戏规则、公开观察、实时动作和回放。

## 启动与体验

准备项目锁定的 Python 环境和 Blender 可执行文件。本机使用从官方发行目录下载并通过 SHA256 校验的 Blender 4.5.15 LTS Windows 便携版。Windows 可在项目根目录的两个 PowerShell 窗口中分别运行以下命令。替换第一个命令中的 Blender 路径即可使用其他电脑上已安装的 Blender。

```powershell
uv run --locked python -m scripts.blender_mcp_demo mcp --blender 'C:\path\to\blender.exe'
```

```powershell
uv run --locked python -m scripts.blender_mcp_demo web
```

打开 [Blender 建模演示](http://127.0.0.1:19841/)，点击「生成场景」。右侧在生成期间显示实际 MCP 方法、请求参数、结果和耗时。完成后左侧出现渲染图及 `.blend`、`.glb`、`.png` 链接。`.blend` 可在 Blender 编辑，`.glb` 用于后续前端渲染。

## 源码与调用顺序

1. `scripts/blender_mcp_demo.html` 发起一次构建并逐行读取状态。
2. `scripts/blender_mcp_demo.py` 建立 MCP Streamable HTTP 连接，通过 `tools/list` 发现工具，再以固定场景 `key-door-assets` 调用 `build_key_door_scene`。
3. MCP 工具启动 Blender 后台进程执行 `scripts/blender_key_door_scene.py`。Blender 生成有独立对象的角色、门、钥匙、墙、地板及终点，保存工程并导出 GLB 与预览图。每次运行单独保存，导出通过校验后才开放下载。

## 实测与失败定位

- HTTP 调用 `857457a0-3c2b-4c4e-ad52-9947920f42e4` 成功，建模和渲染用时 13.46 秒。MCP 实际协商 `2026-07-28`，工具发现和调用成功。用 Blender 后台重开此 `.blend` 并核实 38 个场景对象。
- 浏览器点击调用 `636cf2a1-2b47-4ed3-8bfd-c06846ee7eb2` 成功，分别看到生成中状态、7.10 秒工具响应及三个文件入口。三个下载内容与原文件逐字节一致，GLB 已在 Blender 重新导入。此用时为本机样本。
- 无构建请求标识得到 HTTP 403，未知运行 ID 得到 HTTP 404，MCP 非法场景被拒绝且无新产物。两份 Python 文件的 Ruff 格式、Ruff 检查和严格 Mypy 通过。
- 原始 HTTP 调用记录在忽略目录 `artifacts/blender-mcp-demo/smoke.ndjson`。每次执行的 Blender 日志位于 `artifacts/blender-mcp-demo/runs/<run_id>/blender.log`。连接异常先查 MCP 端口和 `mcp.err.log`。工具失败再查运行日志与 Blender 安装路径。

可通过下面的命令复验浏览器背后的实时状态流。该命令会生成一份新资产。

```powershell
curl.exe --fail-with-body --no-buffer --max-time 145 --request POST --header 'X-Blender-Demo: build' http://127.0.0.1:19841/build
```

## GridWorld 集成

三维舞台位于同级工作区 `AgentLabyrinth-v03-integration-20261104`。在 [本机 Fake 预览](http://127.0.0.1:19912/gridworld) 保持默认固定路线，点击「开始运行 Episode」。也可选「先撞墙再通关」，核对被拒绝的动作不会使角色移动。结束后点击「查看保存详情与回放」，播放或拖动进度条。左上角可切换二维地图，WebGL 或资产加载失败时会自动使用二维地图。

重启预览时，后端进程启动前设置 `AGENTLABYRINTH_E2E_WEB_PORT=19912`，前端进程设置 `AGENTLABYRINTH_E2E_PROXY_API_PORT=19911`。旧预览缺少前一项，页面能打开，但浏览器的运行请求返回 `403 ORIGIN_NOT_ALLOWED`。配置后用 Edge 从同一页面运行，返回 200 并在 8 步到达目标；未登记来源仍返回 403。

前端从当前 Trace 前缀提取公开环境状态，按动作计数合并重复投影。相邻、已接受且位置变化匹配的动作播放行走；新增库存和门状态变化分别触发拾取和开门。浏览历史时自动播放使用相同投影，手动跳转直接定位。减少动效模式直接定位到已保存状态。浏览器运行时从本机站点加载 GLB，Blender 和 MCP 用于资产制作。

- 角色 `apps/web/public/gridworld/iuno-chibi.glb` 与最后一轮精修导出逐字节一致，SHA256 `68D8C52E93B7146F4C88159C157E71AF09C6A93E407902910155781C079321EA`。
- 场景 `apps/web/public/gridworld/key-door-kit.glb` 从 MCP 产物 `857457a0-3c2b-4c4e-ad52-9947920f42e4/key-door.blend` 选中两块地砖、一块墙、门的四个零件、钥匙的三个零件和目标的两件模型后，仅导出选中对象。SHA256 `A07B6DC7BF50CA8DDDC3F06827CEA0EEFD388162DB4BE96B9B6C71BD096ACE5B`。浏览器按已知格重建场景。
- 渲染依赖固定为 Three.js 0.180.0，随三维视图按需加载。[GLTFLoader 文档](https://threejs.org/docs/pages/GLTFLoader.html)。

### 回廊档案室美术

第二关使用暖色砂岩地砖、青灰矮墙、铜边拱门和青釉门扇，目标为独立灯环。构图参考 [任天堂《前进！奇诺比奥队长》微缩关卡](https://www.nintendo.com/en-gb/News/2015/January/In-shops-and-on-Nintendo-eShop-now-Captain-Toad-Treasure-Tracker-947257.html)。角色及门、钥匙、目标仍随公开事件更新，完整布局保留在服务端。

`scripts/blender_gallery_kit.py` 使用本机 Blender 4.5.15 LTS 后台生成。可编辑工程和网页截图分别在 `artifacts/blender-mcp-demo/gallery-kit/gallery-kit.blend` 与 `web-preview.png`。第二关加载 `gallery-kit.glb`，导出 13 个根对象、24 个网格、2,164 三角面，实际重导入通过。Edge 四项专项通过，包含第一关与二维回退，以及第二关的新模型加载、14 步通关和逐步回读。

### 真实模型运行

[真实 GridWorld 预览](http://127.0.0.1:19922/gridworld) 连接 19921 的正常 API 路由和 AIHubMix Provider，使用独立 SQLite。展开「修改任务与配置」，选择 Coding MiniMax M2.7 Free，再点击「开始运行 Episode」。本机目录可选 M2.7、M3、GLM 5.3、GLM 5.3 Flash，此次实跑 M2.7。

新建真实 Episode 使用 `temporary-real-160k-v2`，累计输入与总量各 160,000、单次输出 2,048、累计输出 32,768，最多 16 轮和 300 秒。旧 100,000 真实记录仍可读取，Fake 保持原预算。实际样本 `e05472ff-140d-433f-8075-35249ba9d1fa` 通关，8 次模型请求和 8 个动作，输入 27,144、输出 245，耗时 94.371 秒，网关费用未知。浏览器从保存记录直接回读至终点 `(5, 2)`，回读期间只发 GET。验收覆盖 55 项 Python、54 项 Node、5 项 Edge，另有 Ruff、类型检查和生产构建。

### 最后一轮精修

`scripts/blender_finish_iuno.py` 直接编辑 V4.0 的现有工程。V4.0 原件与 `artifacts/blender-mcp-demo/backups/iuno-before-final/iuno-chibi.blend` 的 SHA256 一致。工程对象、Transform、网格拓扑、材质槽及相机灯光配置经重新打开工程核对。

- 下巴局部最多上收 0.008 Blender 单位，前脸和下颊局部修形。眼绣缩窄约 3.4%，双眼轻微内收，蓝金共边随新脸面贴合。笑线缩窄约 4.3%，笔画减细约 12%。
- 刘海底边轻微错落并减薄，侧发缩短、贴脸且截面厚度约减 6%。马尾沿原中心线微收发根、充实中段及钝化末端，白色发圈加深对根部的包裹。
- 弱化肩颈过渡，整理袖口、前襟、衣领、裙边及鞋身。裙摆蓝线降低凸起，分别调整绒布、织物和刺绣材质。发材质粗糙度调至 0.97，镜面 IOR Level 降至 0.082。

输出目录 `artifacts/blender-mcp-demo/runs/iuno-final-fae56f6b-29d3-4831-95b1-5f3a75f2daa5/`，内含 `.blend`、`.glb` 和四张 800 × 836 检查图，依次为 `preview.png` 正面、`left-preview.png` 左前 45°、`grid-preview.png` 右前 45°、`side-preview.png` 右侧 90°。52 件蒙皮网格权重归一，GLB 重导入后确认 15 骨骼和六段动作。实拍布料有更明显的受压褶皱，侧后深度按实拍能辨认的轮廓和布偶结构推定。

### V4.0 · 罗森联动尤诺最终精修

2026-11-12，直接打开 V3.0 几何检查版工程的备份，由 `scripts/blender_refine_iuno.py` 在原有对象、骨架和材质节点上做局部调整并另存。V3.0 原文件和 `artifacts/blender-mcp-demo/backups/iuno-before-v4/iuno-chibi.blend` 的 SHA256 一致。`v3-before-refinement.json` 记录修改前各对象的 Transform、网格、材质节点和渲染配置。

| 部位 | 实际修改 |
| --- | --- |
| 脸和表情 | 下巴局部最多上收 0.017 Blender 单位，轻微饱满下颊。每只眼改为一块贴脸双色网格，蓝金交界共用 11 个顶点，绣面比面部网格前置 0.0021。眼宽缩放系数 0.96，笑线横向缩放系数 0.95。 |
| 发型 | 柔化刘海端部并减薄发片，侧发末端收短，月牙按应用厚度后的可见刘海表面贴合，压低头顶布环。马尾原中心线保持，中段截面局部增加约 3%，发根截面局部收约 2.6%。 |
| 制服和鞋 | 局部收紧肩袖根部和掌袖连接。外套前襟厚度由 0.008 减至 0.005，领片减薄并柔化边缘，领带向内贴合。裙摆蓝线和鞋绣减细，鞋身局部压低约 6%。 |
| 材质 | 分别调整现有短绒、制服织物和刺绣的粗糙度、镜面和凹凸参数。毛绒粗糙度调至 0.96，短绒密度增加 10%。 |

最终输出目录 `artifacts/blender-mcp-demo/runs/iuno-v4-06152783-13e9-47d8-b9bc-a5fd4fb4b8e1/`，包含可编辑工程、GLB、四张 800 × 836 视图和设置快照。四个正交相机、三盏灯及渲染设置均与 V3.0 对照一致。52 件蒙皮网格权重核对通过，15 骨骼与六动作已重导入 GLB，另外复核了左右转身、行走循环、拾取和开门关键帧。实拍中发圈和马尾受到的局部挤压更加不规则，模型的侧后裁片深度依据两张实拍及布偶结构推定。Blender 工程保留完整的程序绒毛和织纹，实时 GLB 保留动作、颜色和网格。

### V3.0 第一轮 · 几何修正检查版

按负责人 V3.0 修改单完成第一轮，保留 V2 的工程及生成脚本于 `artifacts/blender-mcp-demo/backups/iuno-before-v3/`。V2 工程与备份 SHA256 一致。沿现有骨架和分件重塑头部。脸与后脑网格的前后深度从 0.743 降为 0.63146 Blender 单位，约减少 15.0%。两侧马尾分别设定中心线、截面、扭转和末端形状，缩窄发根，重塑包裹发根的白色布环并移除旧根部球形凸起。刘海调整厚度过渡，侧发分成短的前后两层，肩袖改成连续蒙皮网格。侧后体积根据玩偶结构推定。

最终运行 `86e7df37-9b60-4e6c-adc5-8e29d79eb7da` 由本机 MCP 生成并在 53.26 秒后返回。输出目录 `artifacts/blender-mcp-demo/runs/86e7df37-9b60-4e6c-adc5-8e29d79eb7da/` 含工程、GLB、正面、左 45°、右 45° 及严格右 90° 正交图。四相机同高度、距离、正交比例、灯光和采样配置。54 件绑定网格权重归一、关键布偶壳体闭合，15 骨骼与六动作 GLB 重导入通过。下一轮按参考处理眼绣双色交界、耳朵、前襟、裙摆和鞋，再单独优化绒布材质。

### V2.0 · 罗森联动毛绒版精修

按负责人提供的两张实拍修改现有角色的分件网格、材质和骨架。修改前将上一版工程及生成脚本复制到 `artifacts/blender-mcp-demo/backups/iuno-before-v2/`，工程文件 SHA256 与原版一致。阶段一正面比例核对见运行 `1ec65ae3-12bc-4e7a-abfd-b9b0276da935`，阶段二与三的表情和服装核对见 `5f4ca2e1-c06f-4055-9402-0015391d94c2`。背面与侧面深度依据正面实拍及布偶结构推定。

当前候选由 `build_iuno_avatar` 生成于 `artifacts/blender-mcp-demo/runs/55971633-21eb-428f-9efb-9df3c295e073/`。该目录包含可编辑工程、带六段动作的 GLB、正面正交 `preview.png`、45° `grid-preview.png` 和侧面 `side-preview.png`。工程中有独立三台正交相机与细短绒纤维节点。实时 GLB 在添加纤维前导出，保留几何、底色、腮红与动画，织纹和绒毛可在 Blender 工程中查看。

轮廓改为软方脸、连续弧面刘海、发根收窄且末端饱满的非对称钴蓝马尾、环形发圈与短身展开姿态。眼绣的两色边界贴合脸面。制服增加前襟包边、袖口和鞋面缝线，裙摆权重随两侧大腿变形。现有骨架以脚底为原点，新的拾取和开门关键帧按展开后的手臂重新对齐。最终工程检查 56 件绑定网格、17 个材质、15 个骨骼，每个顶点最多 3 个权重。脸、发圈及马尾壳体闭合，权重归一化。使用本机 Blender 4.5 的数据接口完成检查。

### 罗森联动毛绒版初版记录

负责人指定罗森联动尤诺实拍为主参考。用[《鸣潮》官方联动公告](https://www.bilibili.com/opus/1150630650682802225)和[周边图册](https://news.17173.com/content/04092026/160305836.shtml)核对「共鸣邂逅」系列。实拍决定深蓝垂坠双马尾、浅蓝月牙贴布、白色发圈、双色刺绣眼、蓝白制服及棕色鞋。保留原有六段动画，衣袖、裤腿和裙摆改为随相邻骨骼共同变形。

最终通过本机 MCP 生成，运行 ID `98f26a8f-5ff3-4cb1-af7c-082f538fab95`，耗时 25.18 秒。目录 `artifacts/blender-mcp-demo/runs/98f26a8f-5ff3-4cb1-af7c-082f538fab95/` 含 Blender 工程、约 1.43 MB GLB、正面及斜俯视预览。实际检查六段动作、15 骨骼、原地根骨及 GLB 重导入通过。毛绒微表面由 Blender 程序材质绘制，GLB 保留便于实时渲染的底色与粗糙度。

### 首版记录

Q 版尤诺角色已通过 `build_iuno_avatar` 生成。其可编辑工程、GLB 和两张预览在 `artifacts/blender-mcp-demo/runs/09120a71-55be-4b52-b752-04c439554e0d/`。单次 MCP 请求到产物返回为 21.43 秒。本机 Blender 4.5 LTS 的内嵌 Python 为 3.11，首轮因 Python 3.12 `type` 语法失败，换用兼容类型别名后复验通过。原钥匙门工具也在更新后的服务实跑通过，ID `f988c630-fded-4122-a56a-af784bd7916b`。

### 角色建模与验收

- [库洛 Q 版手办公告](https://www.bilibili.com/opus/1252598008297553929)用于头身比例参考，[官方角色 PV](https://www.bilibili.com/video/BV1tJpwzoE2E/)用于蓝色双马尾、金色头饰与白金服装的外观参考。本轮做成可编辑的 15 骨骼模型，风格偏 Q 版玩偶。
- GLB 约 1.26 MB，34,544 个三角面，内置 `Idle`、`Walk`、`TurnLeft`、`TurnRight`、`PickUp`、`OpenDoor` 六个片段。Blender 已重新导入并核实六段动作，源文件逐帧检查了拾取和开门的向前伸手及行走步态。顶点颜色渐变和根骨无平移由检查命令验证。
- 在 Blender 打开 `.blend`，选中 `Iuno` 骨架，在动画工作区的动作编辑器切换片段。使用重新启动后的 MCP 服务，可用工具 `build_iuno_avatar` 和参数 `{"scene":"iuno-chibi"}` 重新生成资产。原演示网页的「生成场景」按钮仍触发钥匙门工具。

```powershell
uv run --locked python -m scripts.check_blender_iuno 'artifacts/blender-mcp-demo/runs/09120a71-55be-4b52-b752-04c439554e0d/iuno-chibi.glb'
```

### 三维地图接入顺序

1. 复用集成工作区 `GridWorldMap` 已验证的 `position`、`inventory`、`knownCells`、`lastAction`。前端只消费当前 Trace 前缀，未知格不放置实际地图物体。
2. 用当前格坐标决定角色落点，用相邻已接受的位置差确定朝向。浏览器在两个格子间插值并播放原地走路，完成时落在目标格。转身片段完成后把角度交给角色外层节点。
3. 拾取或开门仅在已接受动作及公开状态确有相应变化时播放。将钥匙消失和门开启与接触帧同步。对同一 `actionCount` 去重，避免工具返回和环境更新重复触发。回放拖动或减少动效时直接落到对应状态。
4. 用同一个 Fake Episode 对照二维与三维的逐步格坐标、钥匙、门和可见范围，覆盖拒绝动作、历史跳转和运行结束。通过后让三维视图成为默认，保留二维视图作为兼容显示。
