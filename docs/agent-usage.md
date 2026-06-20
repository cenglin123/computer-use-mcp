# Agent 使用指南

> 分发层指导优先级：MCP prompt `computer_use_guidance` > `skills/computer-use/SKILL.md` > 复制本页或 `examples/clients/agent-prompt.md` 到客户端提示词。

## 能力边界

- 视觉 GUI 自动化需要多模态模型，或客户端具备读取本地 PNG 截图的能力。
- 纯文本模型不能可靠完成“看截图定位并点击”的任务，只适合使用 UIA 结构化查询、任务会话、trace 复盘和审计工具。
- MCP 工具会操作真实 Windows 鼠标和键盘，执行前必须确认目标窗口、坐标和安全边界。
- 安装后先运行 `python -m computer_use doctor`，再做只读 smoke；不要把安装成功等同于模型具备看图能力。

## 推荐提示词

```text
You have access to the local Computer Use MCP server for Windows GUI automation.

Use it only when the task requires observing or controlling the Windows desktop.
For visual GUI tasks, you must be able to read local PNG screenshots returned by the screenshot tool. If you are a text-only model, do not attempt screenshot-based clicking; use only structured UIA, task, trace, and audit tools.

Operate with this loop:
1. Start a task session with start_task when the task needs auditability.
2. Observe before acting with screenshot, get_ui_snapshot, find_control, wait_for_window, or wait_for_control.
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
