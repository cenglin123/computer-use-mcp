# Agent 使用指南

> 分发层指导优先级：MCP prompt `computer_use_guidance` > `skills/computer-use/SKILL.md` > 复制本页或 `.agents/examples/clients/agent-prompt.md` 到客户端提示词。

## 能力边界

- 视觉 GUI 自动化需要读取本地 PNG 截图文件的能力。`screenshot` 工具保存 PNG 并返回路径，读取该文件即可观察界面。
- 如果读取截图后无法获得视觉内容（如确实不具备图像理解能力），才回退到 UIA 结构化查询、任务会话、trace 复盘和审计工具。
- MCP 工具会操作真实 Windows 鼠标和键盘，执行前必须确认目标窗口、坐标和安全边界。
- 安装后先运行 `python -m computer_use doctor`，再做只读 smoke。

## 推荐提示词

```text
You have access to the local Computer Use MCP server for Windows GUI automation.

Use it only when the task requires observing or controlling the Windows desktop.
For visual GUI tasks, read the saved screenshot PNG to see the screen. If you cannot interpret image content after reading, use structured UIA tools as fallback.

Operate with this loop:
1. Start a task session with start_task when the task needs auditability.
2. Observe: call screenshot(monitor=1), then read the saved file to see what is on screen. Use get_ui_snapshot or find_control for supplementary info.
3. Prefer UIA/semantic targeting over raw coordinates.
4. Use coordinates only after confirming the screenshot and monitor bounds.
5. Use batch for short mechanical action sequences.
6. Verify after every meaningful state change. When you use coordinate-based clicking, take a fresh screenshot and check the red cursor marker to confirm the click landed on the intended target.
7. Review with review_task_session and finish the task session with trace evidence when done.

Safety rules:
- Treat mouse and keyboard tools as real user input.
- Do not bypass MCP safety with ad-hoc pyautogui scripts.
- Stop and re-observe after safety_block, fail_safe, timeout, ui_not_found, or invalid_tool.
- Use returned trace_path, artifact_root, artifacts, task_id, and review tools as the source of truth. Do not infer status by scanning global trace directories.
```

## 执行纪律

- 优先用 `launch_app`、`wait_for_window`、`wait_for_control` 和 UIA 定位。
- 对自绘界面或 UIA 不可见控件，再回退到截图视觉定位。
- 长上下文或多步点击时优先用 `batch`，默认不请求最终截图，除非需要证据。
- 使用坐标点击后必须立即截图，通过红色光标标记验证落点是否命中目标。
- 连续多个顶层调用属于同一业务任务时，显式使用 `start_task` 返回的 `task_id`。
- 汇报时引用 MCP 返回的 trace/task 路径，不扫描 `~/.computer-use/traces/` 猜测当前任务。
