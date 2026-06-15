---
id: bugfix-controlled-path-boundaries
type: bugfix
title: 截图与 trace 路径可逃逸受控目录
status: fixed
severity: high
scope: [backend, security]
modules: [mcp-server, trace]
tags: [path-traversal, screenshot, trace]
symptoms:
  - save_path 可写入任意位置
  - trace_id 可包含路径语义
related_files:
  - computer_use/mcp_server.py
  - computer_use/trace.py
  - tests/test_mcp_server.py
  - tests/test_trace.py
verification:
  level: automated
  kind: regression-test
  path: tests/test_trace.py
  command: .\.venv\Scripts\python.exe -m pytest tests/test_trace.py tests/test_mcp_server.py -v
created_at: 2026-06-15
updated_at: 2026-06-15
---

# 截图与 trace 路径可逃逸受控目录

## 现在的行为

修复前调用方可传入任意截图路径，trace ID 也可包含分隔符、绝对路径或 Windows 设备名。

## 预期的行为

截图只能写入配置目录，trace ID 只能作为安全的单一目录名。

## 复现方式

传入 `../escape.png`、UNC、盘符相对截图路径，或使用 `../escape`、`CON` 作为 trace ID。

## 原因是什么

两个写入入口都直接拼接或使用外部字符串，缺少统一边界校验。

## 怎么修复的

截图路径解析后必须位于 `screenshot_dir` 内；trace 所有读写入口统一调用 ASCII ID 校验。

## 验证结果

覆盖绝对路径、父目录逃逸、UNC、盘符相对路径、设备名和超长 ID 的测试已通过。

## 风险和后续

显式截图路径的父目录必须预先存在，这是有意约束。
