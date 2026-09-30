# ADR-017：原厂标价参考成本与免费网关费用分离

## 状态

Accepted（2026-09-30；用户明确指定查询对应模型原厂官网）。依据需求 V0.6 §10 FR-08、§25.5。

## 来源与价格

2026-09-30 核对原厂公开的实时 API 标价，单位 USD / 百万 Token：

| AIHubMix 免费 ID | 原厂对应型号 | 输入（未命中缓存） | 输出 | 原厂来源 |
| --- | --- | ---: | ---: | --- |
| `coding-minimax-m2.7-free` | MiniMax-M2.7 | 0.30 | 1.20 | [MiniMax API Pricing](https://platform.minimax.io/subscribe/token-plan?tab=api-enterprise) |
| `xiaomi-mimo-v2.6-pro-free` | mimo-v2.6-pro | 0.435 | 0.87 | [小米 MiMo Pricing](https://mimo.mi.com/docs/pricing) |
| `xiaomi-mimo-v2.5-pro-free` | mimo-v2.5-pro | 0.435 | 0.87 | [小米 MiMo Pricing](https://mimo.mi.com/docs/pricing) |
| `coding-glm-5.3-free` | GLM-5.3 | 1.40 | 4.40 | [Z.AI Pricing](https://docs.z.ai/guides/overview/pricing) |

原厂标价不等于 AIHubMix 对当前 Key 的实际收费，且 `coding-*` 免费 ID 到原厂型号的映射只用于比较量级，不表示两家服务条款相同。小米、MiniMax、Z.AI 均有缓存输入单价；网关响应当前只用汇总 prompt tokens，不能确定缓存命中数量，因此**全部输入按未命中缓存价**估算。此口径可能高估原厂成本；未统计附加工具费、折扣或网关补贴。

## 决策

1. 在版本化数据文件中保存上述原厂来源、型号和价格。只对这四个精确免费 ID 计算 `原厂标价参考成本 = prompt_tokens × 输入未命中价 / 1,000,000 + completion_tokens × 输出价 / 1,000,000`，用 Decimal，保留价格版本。表外型号、未返回可信 usage 的调用保持未知。
2. 参考成本与现有 `estimated_cost` 独立存入 Episode 和 Experiment 产物，并在 UI 明确标名；现有 `estimated_cost` 仍代表网关费用，当前未验证账单时继续显示未知。旧产物缺字段时不补造或按新价格重算。
3. 可在 Experiment 设置正数 `max_reference_cost_usd`，按已完成 Episode 的参考成本累计，并在后续 Episode 启动前检查。达到阈值后停止下一 Episode，保留已完成产物和计划。单个在途 Episode 的用量事后才可知，故此**不是硬性实付费用上限**，也不能保证单 Episode 不超过参考预算。
4. 原厂调价需新价格版本；持有旧版本的恢复计划不能在新旧价格下混算。真实账单上限仍须取得网关可核验的价格/扣费信息后另行启用。

## 验收

- 四个精确 ID 的 Decimal 估算正确；表外 ID 未知；历史 Artifact 保持兼容。
- 单次与成对实验明确区分参考成本和网关实付未知，故障无 usage 时不显示伪造的零。
- 实验参考预算跨 Episode 累计；中断恢复复用已结算 Episode，价格版本漂移和未知费用拒绝继续。

## 回滚

关闭请求中的参考预算；保留已保存产物。未来价格版本替换只影响新运行，不回写旧结果。
