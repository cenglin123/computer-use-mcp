# 计划:新增 activate_window 工具 + SKILL 指引加固

## 背景

一轮原神 MCP 测试的思考轨迹暴露了多个风险点(多模态自我认知已单独修复)。本计划处理剩余两类根因:

1. **工具缺口**:MCP 36 个工具中没有"激活/聚焦窗口"的能力。当目标 App 在后台时,模型被迫写 Win32 `SetForegroundWindow` C# 注入代码,直接越过 MCP 能力边界(违反 SKILL "Do not bypass the MCP tools")。
2. **指引强度不足**:UIA desktop 搜索误命中 Agent 自己的宿主终端窗口(自指污染);截图后跳过读取直接上 UIA;反复纠结 OCR;desktop 快照撞 too large;放弃任务不收尾。

## 问题清单与影响文件

### A. 新增 `activate_window` 工具(P0)

按窗口标题把目标窗口置前台(必要时从最小化恢复),消除模型用 Win32 越界的根本诱因。

实现要点:
- 复用 `ui_automation._find_window_by_name` 定位 window 控件。
- 自指污染防御:命中窗口后检查其 `process_name` 是否等于当前 MCP 宿主进程(通过 `os.getpid()` → `psutil.Process(pid).name()` 或 `psutil.Process(pid).parent()` 递归匹配)。若命中自身进程,返回 `{activated: false, reason: "self_activation_blocked", detail: "refusing to activate own host window"}`。此项也作为 SKILL B1 模型自检的可操作依据。
- 激活前对命中窗口跑 `safety.check_target_window(process_name, class_name, control_type)`,命中敏感进程返回 `blocked`(对齐 `find_control` 的敏感窗口检测机制而非 `launch_app` 的白名单机制)。
- 直接调用 `uiautomation.WindowControl.SetActive()`——该方法内部调用 `WindowPattern.SetWindowVisualState(WindowVisualState.Normal)`,自动处理最小化恢复和前置激活,无需单独调用不存在的 `ShowWindow`。
- `SetActive()` 调用包裹在 `try/except` 中,捕获 COM 异常(包括 UIPI 阻挡)后返回 `{activated: false, reason: "activate_failed", detail: "<异常信息>"}`。
- UIA 不可用时返回 `{"activated": false, "uia_available": false, "reason": "uia_unavailable"}`,不抛异常。
- 返回结构:`{activated, name, process_name, rect}` 或 `{activated: false, reason}`,reason ∈ `{not_found, blocked, self_activation_blocked, uia_unavailable, activate_failed}`。额外可选 `detail` 字段携带异常细节。
- 多虚拟桌面边界:目标窗口位于另一虚拟桌面时,`SetActive()` 行为依 Windows 版本和窗口完整性级别而异——可能自动切换桌面,也可能静默失败。在工具描述和 `docs/api.md` 中注明此限制。

影响文件:
- `computer_use/ui_automation.py` — 新增 `activate_window(name)` 实现。函数签名为一次性查找+激活,不轮询。调用方需先 `wait_for_window` 确认窗口存在再调用激活,或在外部做轮询。
- `computer_use/mcp_server.py` — import + `_dispatch_tool` 增加 `if name == "activate_window"` 分支。
- `computer_use/tools/schemas.py` — 新增 `Tool(name="activate_window", ...)` 声明。
- `computer_use/tool_contract.py` — 加入 `ATOMIC_AND_COMPOSITE_TOOL_NAMES`(自动进入 batch/task 白名单)。

### B. SKILL 指引加固(P0/P1)

只编辑 `skills/computer-use/SKILL.md`,改完 `Copy-Item` 同步到 `.agents/skills/computer-use/SKILL.md`。

1. **UIA 命中归属核对(安全,P0)**:`find_control`/`click_by_text` 在 `scope=desktop` 命中后,必须确认所属进程是目标 App,排除 Agent 自己的终端/聊天宿主窗口,否则不得点击。`activate_window` 的实现已内建自指污染检测并返回 `self_activation_blocked`,所以 SKILL 指引中直接说"用 `activate_window` 返回的 `process_name` 核对目标进程;调用 `find_control` 时也检查 `process_name` 字段,与已知宿主进程列表(WindowsTerminal.exe, pwsh.exe, cmd.exe, Cursor.exe, Code.exe, msedge.exe, chrome.exe 等当前 Agent 宿主进程)比对。不确定目标进程时,用 `launch_app` 启动确认后再操作"。
2. **截图后必读(P1)**:Standard Loop 第 2 步明确"截图后第一动作是 Read 该 PNG,确认看不到目标前不得转 UIA/shell"。
3. **禁用 OCR / shell 探测环境(P1)**:读取截图本身即视觉步骤,本项目无 OCR 也不需要;判断 App 是否运行/前台用 `find_control`/`wait_for_window`/`activate_window`,不要用 shell 查进程或装 OCR。
4. **foreground 默认前置(P2)**:把"定位单窗口控件默认 `scope=foreground`"提到 Standard Loop。
5. **放弃任务也收尾(P2)**:阻塞/放弃要 `finish_task(cancel=true)` 说明原因。
6. **工具表/分发引用**:Quick Reference 的 Launch 行补 `activate_window`。

### C. 文档与同步

- `docs/api.md` — 工具约定补 `activate_window`。
- `CHANGELOG.md` — 当天日期节追加变更摘要。
- `python scripts/agent_links.py check`(若动了 AGENTS 系列;本计划不动)。

## 验收标准

- [ ] `activate_window` 能把后台窗口置前台(安全环境手动验证一次,含最小化恢复)。
- [ ] 敏感进程命中时返回 `blocked`,不激活。
- [ ] 自身宿主进程命中时返回 `self_activation_blocked`,不激活自身。
- [ ] `SetActive()` 抛出 COM 异常(如 UIPI 阻挡)时返回 `activate_failed` + `detail`,不抛未捕获异常。
- [ ] `pytest tests/test_distribution_readiness.py -v` 通过(SKILL 两副本一致)。
- [ ] 新增工具的单元测试通过(mock uiautomation,覆盖 found/not_found/blocked/self_activation_blocked/uia_unavailable/activate_failed)。
- [ ] `pytest tests/ -v` 全绿(至少受影响模块:ui_automation、mcp_server、schemas、tool_contract、distribution_readiness)。
- [ ] reviewer 视角复查:工具是否真接入 batch/task 白名单;dispatch 是否被 `_call_tool` 正确路由;安全链(自指污染+敏感进程+UIPI)未被绕过。

## 不做(范围外)

- 不补按句柄(hwnd)激活的重载;先只支持标题匹配,与现有 `wait_for_window`/`find_control` 一致。
- 不改 `launch_app` 现有行为。
- 不引入任何 OCR 依赖。
