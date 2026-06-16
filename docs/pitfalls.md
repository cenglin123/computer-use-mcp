# 已知环境陷阱

> 记录开发和部署中遇到的坑。每条包括：现象、原因、解决方案。

## UTF-8 编码

**现象**：中文文档、注释或脚本输出在某些终端下显示乱码，或读取文件时抛出 `UnicodeDecodeError`。

**原因**：Windows 默认使用 GBK/CP936 编码，而非 UTF-8。

**解决**：
- 所有源码文件和文档统一使用 UTF-8（无 BOM）编码。
- Python 读写文件时显式指定 `encoding='utf-8'`。
- 设置环境变量 `PYTHONUTF8=1` 强制 Python UTF-8 模式。
- Git 配置 `core.quotepath false` 以原样显示中文文件名。

## 坐标偏移

**现象**：Agent 截图中看到的坐标与 `click` 实际落点不一致，点到了错误位置。

**原因**：Windows 缩放与 DPI 感知设置导致逻辑坐标和物理坐标不一致。

**解决**：
- 确保调用 `SetProcessDPIAware()`（已在 `core.py` 中设置）。
- 所有工具接口统一使用 mss 物理像素坐标。
- 多显示器混合 DPI 会被 `CoordinateSystem` 拒绝，统一缩放比例。

## 副屏可见但不能输入

**现象**：`screenshot(monitor=0/2)`、`get_monitors` 或 UI 快照能看到副屏，但点击、拖拽、滚动或键盘输入返回坐标安全错误。

**原因**：感知和输入使用不同安全边界。只读能力覆盖虚拟桌面；真实输入按产品约束只允许主屏内非负物理坐标。

**解决**：
- 将待操作窗口移到主屏后重新定位坐标。
- 不要把副屏截图坐标直接传给输入工具。
- 主屏切换或显示器热插拔后重启 MCP 服务，刷新进程内缓存的显示器拓扑。

## 鼠标/键盘与用户冲突

**现象**：Agent 操作鼠标时，用户同时移动鼠标，导致点击位置被用户光标覆盖或菜单意外关闭。

**原因**：`pyautogui` 使用全局输入设备，与用户共享光标。

**解决**：
- 在 Agent 执行任务时，提醒用户不要操作鼠标/键盘。
- 对可 UIA 识别的控件，优先使用控件级 Invoke 而非坐标点击。
- 需要完全隔离时，在独立 VM / Sandbox / RDP 会话中运行本服务。
- PyAutoGUI fail-safe 仍然生效；光标处于 `(0, 0)` 等角落时输入可能被主动中止。远控软件若把光标停在角落，先移回主屏安全区域再执行。

## 自定义绘制标题栏与不可见控件

**现象**：Agent 根据截图中的文字（如 HiBit 的“工具”菜单）点击后没有任何反应，菜单不打开；`find_control` 也找不到同名控件。

**原因**：部分应用（如 Delphi/VCL 程序）使用自定义绘制标题栏，文字只是画上去的，真正的可点击控件是另一个 UIA 元素（如 `TrkGlassButton`），两者位置可能不一致。纯坐标点击落在文字标签上不会触发菜单。

**解决**：
- 优先用 `uiautomation` / `inspect` 枚举实际控件，找到可点击元素的真实边界框。
- 对自定义菜单，由上层多模态模型直接分析截图，定位文字中心坐标后通过 `click(x, y)` 点击；MCP server 不提供 OCR 工具或视觉回退。
- 在 `docs/plans/` 或调试脚本中记录目标应用的“文字标签 → 实际控件”映射。

## UIA 覆盖不足时的回退策略

**现象**：`get_ui_snapshot`、`click_by_text`、`open_menu` 等工具返回 `ui_not_found`，因为目标应用使用自定义绘制或 UIA 树不完整。

**原因**：Windows UI Automation 对自定义绘制控件、游戏、某些 legacy 程序的覆盖有限。

**解决**：
- 复合工具只依赖 UIA；若找不到目标，返回结构化 `ui_not_found`，不替模型做视觉判断。
- 上层多模态模型可直接读取 `screenshot` 返回的截图，自行估算坐标并调用 `click(x, y)` 等原子工具。
- 对高频自定义绘制应用，可在 `docs/plans/` 中记录“视觉坐标 → 实际动作”映射表。

## 安装 MCP 不等于模型具备看图能力

**现象**：用户注册 MCP 后，让纯文本模型根据截图点击按钮，Agent 却无法判断界面布局或坐标。

**原因**：MCP 只返回本地 PNG 路径，不内置视觉模型，也不把截图 base64 放入上下文。客户端和模型必须能读取本地图片，才能完成视觉 GUI 任务。

**解决**：
- 安装后先运行 `python -m computer_use doctor`，确认能力边界提醒。
- 支持 MCP prompts 的客户端加载 `computer_use_guidance`。
- 不支持 prompts/Skill 时，复制 `docs/agent-usage.md` 或 `examples/clients/agent-prompt.md` 到客户端提示词。
- 纯文本模型只使用 `get_ui_snapshot`、`find_control`、task/trace 审计等结构化工具；需要看图定位时切换到多模态模型。

## Nested 工具名不是 MCP 外部名称

**现象**：在 `batch.actions[].tool` 或 `run_task_plan.steps[].tool` 中传入 `computer-use_press_key`、`mcp__computer-use__press_key` 或拼写错误时，步骤失败。

**原因**：嵌套调用的权威名称是 server 内部 canonical tool name。已知 MCP 前缀只做兼容规范化；未知名称会返回 `invalid_tool`，不会模糊执行。

**解决**：
- 优先使用 Schema enum 中的 canonical 名称，如 `press_key`。
- 响应里的 `requested_tool` 表示原始输入，`tool` 表示实际执行的 canonical 名称。
- 看到 `invalid_tool` 时先修正工具名，不要把它当作 GUI 操作失败。

## 空目录不是产物证据

**现象**：执行侧把 `~/.computer-use/traces/.../snapshots/` 或全局 `snapshots/` 目录描述为“本次任务含快照”，但实际 trace 没有对应文件。

**原因**：目录存在不代表本次调用产生了截图或 UI-tree JSON；历史回退目录还可能包含其他无 trace 上下文的 snapshot 截图。

**解决**：
- 汇报时以响应中的 `trace_path`、`artifact_root` 和 `artifacts` 为准。
- `artifacts.screenshots` 只表示本次 trace 下真实存在的截图 PNG。
- `artifacts.snapshots` 只表示本次 trace 下真实存在的 UI-tree JSON。
- 不要通过扫描 `<trace_dir>/snapshots/` 推断某次任务的证据。

## trace 根目录不是业务任务日志

**现象**：执行侧向用户汇报“本次任务日志在 `~/.computer-use/traces/`”，或把时间相邻的多个 trace 当作同一任务证据。

**原因**：trace 根目录是全局存储区，一天内可能包含多个业务任务、standalone 调用和历史兼容 trace。时间相邻不能证明同属一个任务。

**解决**：
- 汇报任务证据时必须给出 `task_id` 和关联 trace 数量。
- 需要跨调用审计时，先 `start_task(goal)`，后续工具调用显式传 `task_id`，最后用 `review_task_session(task_id)` 汇总。
- 不要用目录扫描或时间邻近推断 task 归属；以 task 下的 trace 归属文件和复盘结果为准。

## task 或 locator 状态异常

**现象**：`list_tasks(status=active)` 长期看到旧任务，或按 ID 查询 trace/task 失败但分区目录仍存在。

**原因**：显式 task 需要调用方结束；locator 是可重建派生索引，可能被手工删除或损坏。旧扁平 trace 也可能没有 task 归属。

**解决**：
- 审计时检查长期 active task，必要时补 `finish_task(..., cancel=true)` 或记录人工裁决。
- locator 失效时使用 `computer-use audit rebuild-index --dry-run` 先查看影响，再执行重建。
- 对无主旧 trace，不要自动归入当前任务；只有明确证据时才手工关联或在报告中标记为 legacy/unowned。
