---
id: bugfix-input-screenshot-safety
type: bugfix
title: 滚动绕过目标检查与截图敏感检测采样不足
status: fixed
severity: high
scope: [backend, security]
modules: [mcp-server, composite, ui-automation]
tags: [scroll, screenshot, uia, safety]
symptoms:
  - 无坐标滚动未检查当前目标
  - 敏感窗口不在屏幕中心时可能被截图
related_files:
  - computer_use/mcp_server.py
  - computer_use/composite.py
  - computer_use/ui_automation.py
  - tests/test_ui_automation.py
verification:
  level: automated
  kind: regression-test
  path: tests/test_ui_automation.py
  command: .\.venv\Scripts\python.exe -m pytest tests/test_ui_automation.py tests/test_composite.py tests/test_mcp_server.py -v
created_at: 2026-06-15
updated_at: 2026-06-15
---

# 滚动绕过目标检查与截图敏感检测采样不足

## 现在的行为

修复前无坐标滚动直接操作当前目标；截图只检查捕获范围中心点。

## 预期的行为

每次滚动检查当前光标目标，截图检查捕获范围内全部可见顶层窗口。

## 复现方式

将光标放在敏感窗口后调用无坐标滚动，或把敏感窗口放在显示器边缘后截图。

## 原因是什么

坐标分支才执行安全检查；截图实现以单点采样代替窗口范围枚举。

## 怎么修复的

原子与复合滚动都校验当前光标目标；UIA 枚举顶层 Window 并按矩形相交过滤，枚举失败时回退中心点。

## 验证结果

滚动目标检查、窗口可见性、矩形相交和 UIA 不可用回退测试已通过。

## 风险和后续

真实桌面截图受宿主 BitBlt 状态影响，保留了环境变量控制的 manual 集成测试。
