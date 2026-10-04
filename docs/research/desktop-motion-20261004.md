# 桌面端连续动效调研与实现决策

2026-10-04；需求V0.6、UI规范1.3 §10；负责人授权调研后直接开发。只改Web交互呈现，不改API、Schema、评分或运行状态；无新增依赖，不需新增核心ADR。

## 一手来源与提炼

- [Apple：Understanding user interface responsiveness](https://developer.apple.com/documentation/xcode/understanding-user-interface-responsiveness)：连续操作更敏感于延迟，忽快忽慢的跳动破坏跟随感。采用稳定、及时、可打断的反馈。Apple HIG Motion页需要JavaScript，本轮没有把该页未获取的正文作为事实依据。
- [Fluent 2 Motion](https://fluent2.microsoft.design/motion)：动效表达关系和状态，距离/面积决定时长，约束在用户关注区域，支持无动效偏好。
- [Windows timing and easing](https://learn.microsoft.com/en-us/windows/apps/design/motion/timing-and-easing)：83/167/250ms是系统命名时长示例，进入采用减速。作为桌面参考，不直接照搬全部数值。
- [Material旧版桌面时长指南](https://m1.material.io/motion/duration-easing.html)：桌面偏短、简单，150–200ms参考；这是旧版资料，不称最新Material 3标准。
- [MDN Element.animate](https://developer.mozilla.org/en-US/docs/Web/API/Element/animate)、[Animation.cancel](https://developer.mozilla.org/en-US/docs/Web/API/Animation/cancel)：原生动画可控制和取消，局部增强可在无支持时退化到即时状态。

## 本项目决策

保留暖色界面，以120/180/240ms三级Token、平滑减速曲线、4–8px内容过渡和轻微按压为主。顶部两项导航与三项Replay共用连续滑动标记；实际内容立刻切换，动画只呈现已提交的UI状态，快速切换取消旧动画。原生details扩展到配置/历史/工具详情，支持intrinsic-size时平滑伸缩，不支持时原生展开。

不拦截wheel/touch、不模拟页面惯性；保留浏览器原生滚动和sticky导航。不加入大面积玻璃、无关弹跳或循环装饰。减少动效偏好变化时取消JS动画并禁用位移，保持选中、焦点和错误文字。动画失败也不影响导航/读取/回放，不引入Motion或新框架。

验收以实际Fake产物的多视图快速切换、键盘/焦点、展开值保留、动态减少动效、四视口与只读零POST为准。录制本机视频用于感受过渡；视频/自动测试不等于负责人手感或系统级签收。
