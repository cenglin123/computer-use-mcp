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

## 截图坐标与屏幕坐标的绑定

**现象**：Agent 从聊天客户端展示的截图预览中估算坐标，传给 `click(x, y)` 后点到了错误位置；多屏环境下偏移更明显。

**原因**：聊天客户端会缩放截图预览以适应对话窗口，预览中的像素坐标与实际屏幕坐标不一致。此外，`monitor=0` 的虚拟桌面截图覆盖多个显示器，其坐标空间与主屏输入坐标空间不同。

**解决**：
- **优先使用 `click_on_screenshot(screenshot_path, image_x, image_y)`**，而非从缩放预览估算裸 `click(x, y)` 坐标。该工具读取截图的 sidecar metadata 将图像像素准确映射为屏幕坐标，再走完整安全链。
- `screenshot` 返回 `coordinate_space`（`monitor` 或 `virtual_desktop`）、`capture_left`、`capture_top`，并在 PNG 旁写入 `<saved_path>.json` sidecar。
- 小目标先用 `crop_screenshot` 裁剪放大，裁剪图继承源截图的坐标偏移，`click_on_screenshot` 对裁剪图仍能映射回原始屏幕坐标。
- 映射后的屏幕坐标仍受主屏输入安全策略限制；即使源截图来自 `monitor=0`，映射后落入副屏的点击会被 `SafetyError` 拒绝。
- 映射规则：`screen_x = metadata.capture_left + image_x`，`screen_y = metadata.capture_top + image_y`。

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
- 不支持 prompts/Skill 时，复制 `docs/agent-usage.md` 或 `.agents/examples/clients/agent-prompt.md` 到客户端提示词。
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

## 首次使用 launch_app 被拦截

**现象**：调用 `launch_app("Notepad")` 返回 `No commands are allowed` 或 `... is not in allowed_commands whitelist`，应用没有启动。

**原因**：`launch_app` 依赖 `safety.allowed_commands` 白名单；默认配置中该列表为空，未命中任何条目时所有启动请求都会被拒绝。

**解决**：
- 复制 `config.example.yaml` 到 `~/.computer-use/config.yaml`，按本机实际路径填写 `allowed_commands`。
- 白名单支持绝对路径或程序名；敏感进程（如 KeePass、certmgr）即使列入白名单仍会被拦截。
- 错误消息已区分“白名单为空”和“未命中白名单”，并指向 `config.example.yaml`。

## 混合 DPI 被 fail-fast

**现象**：服务启动或第一次调用输入工具时抛出混合 DPI 错误。

**原因**：`CoordinateSystem` 在初始化时检测各显示器缩放比例，发现不一致时直接拒绝启动，避免截图坐标与输入坐标错位。

**解决**：
- 统一所有显示器的缩放比例（Windows 设置 → 系统 → 显示 → 缩放与布局）。
- 如果必须使用不同缩放，暂时只连接主显示器，或在统一缩放的虚拟机/RDP 会话中运行服务。
- 混合 DPI 多显示器支持已明确排除在当前计划之外，将作为后续独立计划推进。

## UIA 不可用时只能回退视觉坐标

**现象**：`get_ui_snapshot`、`find_control`、`click_by_text` 等工具返回 `uiautomation_not_available` 或 `ui_not_found`。

**原因**：这些工具依赖可选的 `uiautomation` 包；未安装或目标应用未暴露 UIA 控件时无法使用语义定位。

**解决**：
- 安装 `uiautomation` 并重新运行 `python -m computer_use doctor` 确认检查通过。
- 对自定义绘制或 UIA 覆盖不足的应用，由上层多模态模型读取 `screenshot` 返回的截图，估算坐标后调用 `click(x, y)` 等原子工具。
- MCP server 不内置 OCR 或视觉回退引擎，视觉判断由模型完成。

## 集成测试会操作真实桌面

**现象**：运行 `tests/manual/` 下的测试后，桌面上出现 Notepad 窗口或残留进程。

**原因**：`tests/manual/` 中的测试在真实 Windows 桌面环境执行，会启动应用、截取屏幕、移动/点击鼠标。

**解决**：
- 默认情况下这些测试被 `manual` marker 保护，不会自动运行；CI 或非手动环境使用 `pytest tests/ -m "not manual"`。
- 手动运行前设置 `COMPUTER_USE_RUN_MANUAL=1`，并确保当前无人操作鼠标键盘、无敏感窗口可见。
- 测试 fixture 会尝试终止启动的进程，但异常退出时可能需要手动清理。

## 长上下文 GUI 任务响应退化

**现象**：随着截图、UIA 快照和工具输出在上下文中累积，对上下文规模敏感的模型出现明显的响应延迟退化（从数秒退化到数分钟）。

**原因**：上下文膨胀主要来自三类来源：
1. **桌面级 UIA JSON**：`get_ui_snapshot(scope="desktop")` 可产生数百 KB 的结构化输出。
2. **CLI base64 截图输出**：通过 CLI `python -m computer_use screenshot` 获取截图时，base64 PNG 直接写入 stdout 并进入上下文。
3. **连续读取多张 PNG**：每张截图作为多模态内容挂入上下文，累积放大规模。

**解决**：
- 使用 MCP `screenshot` 工具（只返回文件路径，不返回 base64）。
- UIA 快照默认使用 `scope="foreground"`；仅在需要跨窗口定位时才用 `scope="desktop"`。
- 不要在上下文中累积历史截图；按需读取最新一张即可。
- 当单次工具响应耗时超过 60 秒，或连续工具输出累积规模明显放大时，停止视觉迭代，汇总当前状态后新开会话或让用户确认继续。

## 桌面级快照组合被拦截

**现象**：`get_ui_snapshot(scope="desktop", include_screenshot=true)` 返回 `high_cost_snapshot_blocked` 错误。

**原因**：该组合曾产生约 9.5MB 截断输出。MCP 分发层现在直接拦截。

**解决**：使用 `scope="foreground"`，或 `scope="desktop"` 不带 `include_screenshot`。如需跨窗口定位，用 `find_control`。仅取 `scope="desktop"` 但 JSON 仍超过内联预算（200K chars）时还会返回 `snapshot_output_too_large`，此时同样应改用更窄的查询。

## 缺失 task_id 被拒绝

**现象**：在 `start_task` 之后调用可执行工具（如 `screenshot`、`click`、`get_ui_snapshot`），返回 `missing_task_id` 或 `missing_task_id_ambiguous`，工具没有执行。

**原因**：存在未结束的显式业务任务时，MCP 分发层强制要求每次顶层调用显式传 `task_id`，防止归属丢失。task 管理工具和只读的 `review_task` 不受此约束。

**解决**：把响应中的 `active_task_id` 加到重试调用的 `task_id` 参数；若有多个 active task，先用 `finish_task(..., cancel=true)` 或选定其中之一再继续。
