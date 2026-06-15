# MCP Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement each defect with a verified RED/GREEN cycle.

**Goal:** 修复深度审计中的全部确认缺陷，同时显式保留“安全密码控件允许输入”和“仅限制主屏”两项用户确认的产品边界。

**Architecture:** 保持现有 MCP 工具接口不变，在安全边界、任务调度和 trace 层增加集中校验。避免重构 `mcp_server.py` 的整体结构，只提取足以消除重复判断的轻量辅助函数。所有行为变更先补回归测试，再实施最小修复。

**Tech Stack:** Python 3.11、MCP Python SDK、pytest、PyAutoGUI、UI Automation。

---

## 范围

修复审计项：

1. 绝对路径 `allowed_commands` 被 basename 绕过。
2. `screenshot.save_path` 与 `trace_id` 可逃逸受控目录。
3. 无坐标 `scroll`/`scroll_until` 绕过目标窗口检查。
4. `run_task_plan`/`batch` 可递归调用导致资源耗尽。
5. 敏感截图检测仅检查显示器中心点。
6. 等待超时被任务执行和 trace 误判为成功。
7. `run_task_plan` 外层包装生成孤立 trace。
8. `COMPUTER_USE_CONFIG` 未生效，文档与实现不一致。
9. 日志与 trace 原样记录输入文本。
10. PyAutoGUI fail-safe 未结构化记录，任务报告中断。

明确保留：

- 安全目标中的密码控件必须允许输入，这是用户确认的产品特性；密码状态本身不得成为阻断条件，并须有 safety 与 MCP 回归测试，同时继续阻断敏感进程/类名和危险文本。
- 只支持主屏/非负坐标，这是用户确认的当前产品边界；本计划不新增负坐标或副屏输入支持。

### 输入坐标安全边界

- 感知与输入采用不同坐标边界：截图、`get_monitors`、窗口/控件检查等只读感知能力可覆盖虚拟桌面、`monitor=0` 和副屏；任何鼠标、拖拽、滚动、点击或由 UIA/快照派生的指针输入，只允许主屏内的非负物理坐标。
- 主屏坐标校验必须下沉到 `core.py` 的最终公共输入原语，确保直接调用也无法绕过；有显式坐标的原语校验该坐标，无显式坐标的滚轮、键盘和鼠标释放原语校验当前光标位置。`core.py` 不承担依赖 UIA 的目标窗口检查，目标检查继续由 MCP/CLI 等安全执行层负责。
- `safety.py` 提供统一主屏坐标规则，调用方不得通过传入全部显示器范围扩大输入能力；`to_physical` 只负责坐标转换，转换后的输入坐标仍必须经过主屏校验。
- 必须覆盖 MCP 显式坐标动作、当前光标位置上的滚动/键盘输入安全检查、CLI 指针输入、composite 与 `target_name`/UIA 派生坐标、snapshot `click_by_uid`，确保所有公开输入路线不可绕过主屏限制。
- 拖拽必须在任何按键或移动输入发生前检查实际起点和终点的坐标及目标窗口；任一点敏感时不得执行拖拽。
- snapshot UID 点击只能使用 snapshot 定位坐标，不得信任 snapshot 携带的进程、类名或控件类型作为安全事实；执行前必须按最终坐标实时检查目标。
- 保留并回归验证敏感进程、窗口类名、危险文本检查；不修改已确认的安全密码控件输入行为。
- TDD 验收必须先用 RED 测试证明直接 core 调用、敏感拖拽起点和伪造 snapshot 元数据可绕过，再实现修复并确认 GREEN；同时验证主屏输入正常，以及多显示器截图、`monitor=0`、副屏截图和 `get_monitors` 行为不变。

## 影响文件

- 修改：`computer_use/config.py`
- 修改：`computer_use/safety.py`
- 修改：`computer_use/mcp_server.py`
- 修改：`computer_use/runner.py`
- 修改：`computer_use/trace.py`
- 修改：`computer_use/ui_automation.py`
- 修改：`tests/test_config.py`
- 修改：`tests/test_safety.py`
- 修改：`tests/test_mcp_server.py`
- 修改：`tests/test_runner.py`
- 修改：`tests/test_trace.py`
- 修改：`tests/test_ui_automation.py`
- 新增：`docs/problems/bugfix/*.md`，每个独立缺陷一篇
- 修改：`docs/deployment.md`
- 修改：`docs/api.md`
- 修改：`CHANGELOG.md`，使用 `scripts/changelog.py add`

## Task 1：配置与启动白名单

- [ ] 在 `tests/test_config.py` 增加 `COMPUTER_USE_CONFIG` 覆盖默认路径测试，运行并确认 RED。
- [ ] 在 `computer_use/config.py` 读取环境变量指定路径，运行目标测试确认 GREEN。
- [ ] 在 `tests/test_safety.py` 增加“绝对路径白名单不允许其他目录同名程序”测试，运行并确认 RED。
- [ ] 修改 `computer_use/safety.py`：配置项是绝对路径时只允许规范化后的同一路径；仅显式 basename 配置才允许按名称匹配。
- [ ] 运行 `tests/test_config.py tests/test_safety.py tests/test_launcher.py`。

## Task 2：文件与 trace 路径边界

- [ ] 在 `tests/test_trace.py` 增加非法 `trace_id`（路径分隔符、`..`、绝对路径）拒绝测试，确认 RED。
- [ ] 补充 Windows 设备名、尾随点/空格、超长 ID 测试；覆盖 `trace_root`、`write_trace_meta`、`read_trace_meta`、`read_trace` 的所有入口。
- [ ] 在 `computer_use/trace.py` 增加单一 `validate_trace_id`，仅允许稳定的 ASCII 标识字符且禁止路径语义；所有 trace 读写入口强制调用。
- [ ] 在 `tests/test_mcp_server.py` 增加 `screenshot.save_path` 只能落在配置截图目录内的测试，覆盖绝对路径、`..`、UNC、盘符相对路径和目录本身，确认 RED。
- [ ] 修改 `computer_use/mcp_server.py`，解析并验证截图目标路径；默认和显式路径均限制在 `screenshot_dir`。
- [ ] 运行路径相关目标测试。

## Task 3：输入安全与敏感截图

- [ ] 在 `tests/test_safety.py` 增加密码状态本身不会导致 `check_target_window` 拒绝的回归测试，确认 RED。
- [ ] 在 `tests/test_mcp_server.py` 增加 MCP `type` 可向安全密码控件输入的回归测试，并确认敏感进程/类名和危险文本仍被阻断，确认 RED。
- [ ] 修改输入安全检查：移除密码状态这一阻断条件，保留进程、窗口类名、坐标和危险文本检查；直接 CLI 与 MCP 通过同一安全规则保持一致。
- [ ] 在 `tests/test_mcp_server.py` 增加无坐标 `scroll` 对当前鼠标目标执行安全检查的测试，确认 RED。
- [ ] 在 `tests/test_composite.py` 增加 `scroll_until` 继承该安全检查的测试。
- [ ] 修改 `mcp_server.py`，所有滚动都检查当前鼠标位置对应目标；保留主屏坐标限制。
- [ ] 在 `tests/test_ui_automation.py` 增加枚举可见敏感窗口/控件的测试。
- [ ] 修改截图敏感检测：仅检查目标截图范围内的顶层窗口，避免普通子控件类名造成误判；任一敏感目标命中即整图遮盖。
- [ ] 覆盖 UIA 不可用、枚举异常、monitor=0 和显示器偏移；失败时保留现有中心点检查作为保守降级。
- [ ] 运行输入与截图安全目标测试。

## Task 4：任务调度与错误语义

- [ ] 在 `tests/test_runner.py` 增加等待返回 `timeout=true` 时停止计划并标记失败的测试，确认 RED。
- [ ] 增加 timeout 的 trace/report/review 一致性断言，确认 RED。
- [ ] 实现统一结构化失败判定，覆盖 `error` 与 `timeout=true`；运行目标测试确认 GREEN。
- [ ] 在 `tests/test_mcp_server.py` 增加 batch 对 timeout 失败的测试。
- [ ] 实现 batch 使用同一失败判定，运行测试确认 GREEN。
- [ ] 在 `tests/test_mcp_server.py` 分别增加 `run_task_plan -> run_task_plan`、`run_task_plan -> batch -> run_task_plan`、`batch -> run_task_plan -> batch` 测试，每个测试先确认 RED。
- [ ] 在调度层增加统一执行上下文：禁止任务级工具递归，并设置单次最大展开步骤预算；所有 MCP 入口共享预算。
- [ ] 运行递归与预算测试确认 GREEN。
- [ ] 在 `tests/test_mcp_server.py` 增加 MCP 调用 `run_task_plan` 只生成一个共享 trace 的测试，确认 RED。
- [ ] 修改 trace_id 传递，消除外层孤立 trace；report 与返回 trace 保持一致。
- [ ] 运行 runner、mcp_server、review、trace 目标测试。

## Task 5：日志脱敏与 fail-safe

- [ ] 在 `tests/test_trace.py` 增加工具感知的递归脱敏测试，覆盖 `type`、`fill_form`、`batch.actions`、`run_task_plan.steps`、结果和 error/report 文本，确认 RED。
- [ ] 明确重试策略：包含已脱敏输入的步骤返回 `retry_not_supported_for_redacted_step`，不得使用占位符重放；增加 RED 测试。
- [ ] 在 trace 写入边界集中清洗参数和结果；保留长度、字段名等调试元数据，并写入 `replayable=false`。
- [ ] 修改 `retry_step`，拒绝重放 `replayable=false` 的步骤；运行脱敏与重试测试确认 GREEN。
- [ ] 在 `tests/test_mcp_server.py` 增加日志递归脱敏测试，确认 RED；实现日志使用同一清洗器后确认 GREEN。
- [ ] 在 `tests/test_mcp_server.py` 增加 `FailSafeException` 转为 `fail_safe` 且 trace 分类正确的测试，确认 RED。
- [ ] 捕获 `pyautogui.FailSafeException` 并返回 `{"error":"fail_safe", ...}`，确保 trace 中 `error_kind=fail_safe`，运行测试确认 GREEN。
- [ ] 在 `tests/test_runner.py` 增加 fail-safe 仍生成 report、保留已执行步骤的测试，先 RED 后 GREEN。
- [ ] 运行日志与 fail-safe 目标测试。

## Task 6：稳定化与人工验证

- [ ] 将三个单元级截图测试改为 mock `save_screenshot`，避免单元测试依赖交互桌面。
- [ ] 保留一项 `manual` 标记的真实截图集成验证，记录当前 BitBlt 环境限制。
- [ ] 运行受影响测试：`.\.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_safety.py tests/test_launcher.py tests/test_ui_automation.py tests/test_trace.py tests/test_runner.py tests/test_mcp_server.py tests/test_composite.py -v`
- [ ] 运行完整测试：`.\.venv\Scripts\python.exe -m pytest tests/ -v`
- [ ] 在无人操作输入设备的安全环境中人工验证：无坐标滚动正常；敏感顶层窗口截图被遮盖；鼠标移到角落触发 fail-safe 后任务仍返回结构化 trace/report。

## Task 7：缺陷文档与项目文档

- [ ] 按共同根因创建 5 篇缺陷文档：配置/白名单、路径边界、输入与截图安全、任务调度与 trace、日志脱敏与 fail-safe。
- [ ] 更新 `docs/deployment.md` 的配置路径与环境变量约定。
- [ ] 更新 `docs/api.md` 的路径边界、递归限制、timeout/fail-safe 和 trace 脱敏语义。
- [ ] 用 `python scripts/changelog.py add --title ... --body ...` 写入当天 CHANGELOG。

## Task 8：主屏输入边界

- [x] 审计全部 `validate_coordinate`、`to_physical` 和公开指针/输入路线，区分只读感知坐标与会产生真实输入的坐标。
- [x] 在 safety 层建立单一主屏输入坐标校验；禁止 MCP、CLI、composite、snapshot 或 UIA/`target_name` 派生路线自行传入全显示器范围放宽边界。
- [x] 先增加 RED 回归测试：至少覆盖 MCP 显式坐标动作、当前光标动作、composite/UIA 派生动作、snapshot `click_by_uid`、可测试的 CLI 输入路线和主屏正常路径。
- [x] 保留 screenshot 的 `monitor=0`、副屏选择和虚拟桌面能力，并保留 `get_monitors` 多显示器枚举测试。
- [x] 在 `core.py` 最终公共输入原语强制主屏坐标边界，覆盖直接调用和依赖当前光标位置的输入。
- [x] 拖拽在执行任何真实输入前同时检查起点和终点的坐标及实时目标。
- [x] snapshot UID 点击按最终坐标实时获取目标信息，不信任客户端 snapshot 安全元数据。
- [x] 不弱化敏感进程、类名、危险文本检查，不修改密码输入行为，不修改截图光标标记。
- [x] 更新 `docs/api.md` 与输入截图安全缺陷文档，只描述当前根因与最终边界。
- [x] 运行受影响测试和完整测试套件。

## 验收标准

- 绝对路径 allowlist 不再隐式允许同名程序。
- 所有 MCP 可写路径均无法通过用户参数逃逸配置目录。
- 所有滚动操作执行目标安全检查。
- 敏感截图检测覆盖截图范围，而非中心点采样。
- 任务递归被拒绝，步骤数有上限。
- timeout 与 fail-safe 在返回值、trace、report 和 review 中一致标记为失败。
- 一次 `run_task_plan` 只对应一个 trace。
- `COMPUTER_USE_CONFIG` 实际控制配置文件。
- trace 与日志不保存输入正文。
- 脱敏步骤明确不可重放，不会用占位符执行真实输入。
- 密码控件状态本身不阻断输入；安全密码控件可通过 MCP 和共用安全检查输入，敏感进程/类名与危险文本仍被拒绝，并有回归测试覆盖。
- 所有产生真实指针输入的公开路线只接受主屏内非负物理坐标，包括显式坐标、当前光标、CLI、composite、snapshot 和 UIA/`target_name` 派生坐标；副屏和负坐标均被拒绝。
- 截图、显示器枚举和只读检查继续支持虚拟桌面、`monitor=0` 与副屏，不因输入限制而退化。
- 完整自动化测试通过。
- GUI 安全人工验证完成。
