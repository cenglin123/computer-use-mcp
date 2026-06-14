# 项目记忆

> 跨会话沉淀的关键上下文。只保留**通用**、**可复用**的经验；单次任务的具体坐标、截图路径、时间线等应留在反馈日志中，不进入长期记忆。

## 用户偏好

- 语言：中文。
- 决策风格：重要任务先规划，倾向用 converge 评审后再执行。
- 关注重点：工具执行效率、安全性、可验证性。

## 项目关键上下文

- **用途**：本地 MCP 服务器 + 调试 CLI，用于 Windows GUI 自动化。
- **核心定位**：MCP 只保留最简键鼠宏 + 屏幕观察能力（点击、移动、拖拽、按键、滚动、截图、控件查找、启动应用、固定等待）；复杂多步任务由上层 Agent 通过 ReAct 边截图边规划执行，能用 Bash 更方便完成的则不塞进 MCP。
- **上下文保护硬约束**：`screenshot` 工具永远把 PNG 保存到本地，只返回文件路径引用，**绝不返回 base64 图像**；`batch.final_screenshot` 也默认关闭。
- **核心依赖**：`pyautogui`（输入控制）、可选 `uiautomation`（UIA 控件）、`mss`（截图）。
- **运行测试**：`.venv/Scripts/pytest tests/ -v`。
- **运行 CLI**：`.venv/Scripts/python -m computer_use`。

## 已验证的重要教训

1. **GUI 启动优先用 Shell**：`Shell.Application.InvokeVerb` / `WScript.Shell` 解析 `.lnk` 比坐标/点击更稳定。
2. **视觉理解优先于结构化识别**：模型本身的多模态能力足以理解大多数截图；需要精确定位时优先用 UIA 或 Windows API，不要依赖 OCR。
3. **输入设备安全是硬约束**：`core.py` 的 `click` / `move_to` 必须走 `safety.py` 的坐标与目标窗口检查，禁止绕过。
4. **dynamic workflow 在 Kimi Code 中的边界**：Kimi Code 的 `Agent` 工具无法被外部脚本调用，因此 `scheduler.py` / `executor.py` 不适用；推荐 TodoList + 顺序 Agent + pytest 门控 + converge 验收。
5. **长上下文会严重拖慢回合制交互**：上下文膨胀后，每个截图→分析→执行的循环可能耗时数分钟；应把多个动作通过 MCP 原生的 `batch` 工具一次性调用，减少 ReadMediaFile 次数，仅在关键节点验证。
6. **优先使用 MCP 原生工具调用，不要用 Bash 写 Python 再调 `_call_tool`**：Kimi Code 已暴露 `mcp__computer-use__*` 工具，模型应直接传 JSON 参数调用；Bash 里写 `python -c "import sys..."` 会浪费上下文、增加出错面，只在需要 Windows API（如读 `SysListView32`）时才用 Bash。
7. **等待策略**：优先使用 `wait_for_window` / `wait_for_control` 等事件驱动等待；只有目标无法被 UIA/窗口标题探测时才回退到 `sleep` 固定等待。
8. **自定义绘制界面常无法 UIA 定位**：部分应用（如 HiBit Uninstaller 的标题栏按钮/下拉菜单）是自定义绘制，UIA 不暴露对应控件，必须回退到视觉定位或项目记忆中的相对位置策略。
9. **产品边界：MCP 只做最简键鼠宏 + 观察**：复杂多步 GUI 任务应让上层 Agent 用 ReAct 边截图边规划，MCP 只提供可靠原语；踩坑后及时反思并记录，能走 Bash 的复杂任务不塞进 MCP。
10. **GUI 操作标准化闭环**：接到 GUI 任务后先分解为 `n` 步；每步循环：截图确认元素位置 → 基于沉淀经验和 UIA/视觉信息确定参数 → 调用 MCP 原生工具模块（`screenshot`/`click`/`move_to`/`type`/`key_combo`/`find_control`/`sleep` 等）执行 → 截图验证效果再推导下一步。把基本操作固化为带参数的模块调用，避免每轮重新猜测参数；若多模态识别有偏差，用偏移量修正而非换策略。
11. **桌面图标坐标应读 `SysListView32`，不要目测**：Windows 桌面图标列表的精确位置可通过 `LVM_GETITEMPOSITION` 获取；目测 3840×1089 截图极易点错。一旦坐标点击后目标未出现，应立刻用 OS API 验证位置，而不是重复点击。
12. **每个工具响应都带 `timestamp`**：便于复盘时精确计算各步骤间隔，区分系统响应时间与 Agent 思考时间。

## 参考文件

- 系统设计：[docs/overview.md](/docs/overview.md)
- 工具约定：[docs/api.md](/docs/api.md)
- 环境陷阱：[docs/pitfalls.md](/docs/pitfalls.md)
