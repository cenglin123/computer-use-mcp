---
id: bugfix-input-screenshot-safety
type: bugfix
title: 输入目标检查与截图敏感检测缺陷
status: fixed
severity: high
scope: [backend, security]
modules: [core, safety, mcp-server, cli, composite, snapshot, ui-automation]
tags: [password, coordinates, scroll, screenshot, uia, safety]
symptoms:
  - 安全密码控件被错误拒绝输入
  - 副屏坐标可触发鼠标或键盘输入
  - 无坐标滚动未检查当前目标
  - 敏感窗口不在屏幕中心时可能被截图
related_files:
  - computer_use/safety.py
  - computer_use/core.py
  - computer_use/mcp_server.py
  - computer_use/cli.py
  - computer_use/composite.py
  - computer_use/snapshot.py
  - computer_use/ui_automation.py
  - tests/test_safety.py
  - tests/test_core.py
  - tests/test_mcp_server.py
  - tests/test_snapshot.py
  - tests/test_ui_automation.py
verification:
  level: automated
  kind: regression-test
  path: tests/test_safety.py
  command: .\.venv\Scripts\python.exe -m pytest tests/ -q
created_at: 2026-06-15
updated_at: 2026-06-16
---

# 输入目标检查与截图敏感检测缺陷

## 现在的行为

所有 `core.py` 公共输入原语在调用 PyAutoGUI 前强制校验主屏内非负坐标。带坐标的鼠标、拖拽和滚动校验显式坐标；键盘输入、无坐标滚动和无坐标鼠标释放校验当前光标。MCP 拖拽在开始前检查实际起点和终点，snapshot UID 点击按最终坐标实时检查目标。安全密码控件允许输入，敏感进程、窗口类名和危险文本仍被阻断。截图和只读感知继续支持虚拟桌面与副屏。

## 预期的行为

密码状态本身不阻断输入，但敏感进程、敏感窗口类名和危险文本仍须拒绝。所有真实输入只允许主屏内非负物理坐标，且最低执行层不可绕过。拖拽的起点和终点都必须安全，snapshot 中的安全元数据不能替代实时检查。截图、显示器枚举和只读检查继续支持虚拟桌面与副屏。

## 复现方式

使用 mock PyAutoGUI 直接调用 `core.click(2000, 500)` 等公共输入原语，或把 mock 当前光标放到副屏后调用键盘和无坐标输入原语。另可构造敏感起点、安全终点的拖拽，或在 snapshot 中伪造安全进程元数据但让最终坐标实时命中敏感目标。正确行为是在任何真实输入调用前返回安全错误。

## 原因是什么

安全校验曾只位于 MCP、CLI 等入口，最终 PyAutoGUI 原语没有强制边界，直接调用可以绕过。拖拽目标检查只覆盖终点；snapshot 点击使用了客户端携带的进程和窗口元数据，没有按最终坐标获取实时目标。密码状态、滚动目标和截图范围还存在各自独立的安全语义缺口。

## 怎么修复的

`core.py` 在每个公共输入原语进入 PyAutoGUI 前调用统一主屏坐标校验；无显式坐标的输入读取并校验当前光标。该层只负责不可绕过的坐标边界，依赖 UIA 的目标窗口检查仍由 MCP/CLI 安全执行层承担。拖拽依次检查起点和终点的实时目标后才调用 core；snapshot UID 点击只使用 snapshot 定位坐标，并通过 `inspect_point` 获取实时安全元数据。密码、滚动和截图逻辑继续执行各自的目标与内容检查。

## 验证结果

执行 `.\.venv\Scripts\python.exe -m pytest tests/ -q` 覆盖 core 最终输入边界、MCP/CLI、composite、snapshot、密码输入、滚动目标和截图安全。真实桌面截图测试需显式环境变量启用。

## 风险和后续

`core.py` 不引入 UIA 依赖，因此只保证最终坐标边界；进程、窗口类名和控件类型检查必须由公开安全执行入口完成。允许密码控件输入不等于放宽目标或内容安全。真实桌面截图受宿主 BitBlt 状态影响，保留环境变量控制的人工集成测试。
