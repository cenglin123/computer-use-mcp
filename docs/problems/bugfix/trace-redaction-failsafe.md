---
id: bugfix-trace-redaction-failsafe
type: bugfix
title: 输入正文落盘与 fail-safe 中断报告
status: fixed
severity: critical
scope: [backend, security]
modules: [trace, runner, mcp-server]
tags: [redaction, logging, fail-safe, retry]
symptoms:
  - 输入正文写入日志和 trace
  - PyAutoGUI fail-safe 抛出并中断任务报告
related_files:
  - computer_use/trace.py
  - computer_use/runner.py
  - computer_use/mcp_server.py
  - tests/test_trace.py
verification:
  level: automated
  kind: regression-test
  path: tests/test_trace.py
  command: .\.venv\Scripts\python.exe -m pytest tests/test_trace.py tests/test_runner.py tests/test_mcp_server.py -v
created_at: 2026-06-15
updated_at: 2026-06-15
---

# 输入正文落盘与 fail-safe 中断报告

## 现在的行为

修复前 `type`、`fill_form` 及嵌套任务参数会原样写入日志和 trace；fail-safe 作为未处理异常中断 runner。

## 预期的行为

输入正文不落盘；脱敏步骤不可错误重放；fail-safe 形成结构化失败并保留报告。

## 复现方式

执行含文本输入的 batch/plan 后检查日志和 JSONL，或将鼠标置于 PyAutoGUI fail-safe 角落后执行任务。

## 原因是什么

日志和 trace 直接序列化原始参数，异常层也没有单独处理 `FailSafeException`。

## 怎么修复的

在 trace 写入边界递归清洗敏感键并替换关联结果文本，日志复用同一清洗规则；记录 `replayable=false` 并拒绝重试；fail-safe 映射为 `error_kind=fail_safe`。

## 验证结果

嵌套脱敏、日志脱敏、不可重放、fail-safe trace/report 测试已通过。

## 风险和后续

脱敏按字段名和本次输入值关联替换；未来新增输入型工具时应沿用这些字段约定。
