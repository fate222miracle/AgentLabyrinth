# ADR-001：Runtime 策略

## 状态
Accepted

## 背景
需求 V0.5 第 8、30 节已确定 Runtime 策略；学习者需要理解真实控制循环。

## 候选方案
手写循环与框架无关 Port；直接使用外部 Agent 框架。

## 决策
V0.1 采用框架无关 AgentRuntime Port 与 HandwrittenRuntime。外部 Agent 框架只能通过 Adapter 接入。LangGraph 是 V0.2 首个 Adapter，M0 不创建实现包。使用 Antigravity IDE 不等于选择 Google ADK。

## 原因
保持工具、Trace、Environment、Evaluator 与 Runner 独立且可测试，让核心机制可阅读。

## 代价与风险
需要自行维护循环与错误映射，以公共契约及关键失败测试约束。

## 回滚方式
新 ADR 替代；Adapter 必须通过相同契约与对照实验。
