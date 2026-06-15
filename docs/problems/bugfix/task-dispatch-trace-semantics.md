---
id: bugfix-task-dispatch-trace-semantics
type: bugfix
title: 任务递归、超时误判与重复 trace
status: fixed
severity: high
scope: [backend]
modules: [runner, mcp-server, trace, review]
tags: [recursion, timeout, trace, resource-limit]
symptoms:
  - timeout 被计为成功
  - 任务工具可递归展开
  - 一次任务产生两个 trace
related_files:
  - computer_use/runner.py
  - computer_use/mcp_server.py
  - tests/test_runner.py
  - tests/test_mcp_server.py
verification:
  level: automated
  kind: regression-test
  path: tests/test_runner.py
  command: .\.venv\Scripts\python.exe -m pytest tests/test_runner.py tests/test_review.py tests/test_mcp_server.py -v
created_at: 2026-06-15
updated_at: 2026-06-15
---

# 任务递归、超时误判与重复 trace

## 现在的行为

修复前只识别 `error` 字段，任务工具可相互递归，MCP 包装层与 runner 各生成一个 trace。

## 预期的行为

超时与错误一致失败，任务展开有界，一次任务只使用一个 trace。

## 复现方式

让等待工具返回 `timeout=true`，或在 plan/batch 中嵌套任务工具，再统计 trace 目录。

## 原因是什么

失败判定、递归约束和 trace 上下文分别散落在不同执行层。

## 怎么修复的

统一结构化失败判定；禁止任务工具递归；限制最多 100 个展开步骤；将外层 trace ID 传入 runner。

## 验证结果

timeout、三类递归矩阵、预算和单 trace 测试已通过。

## 风险和后续

当前只支持一层 batch，这是明确的资源安全边界。
