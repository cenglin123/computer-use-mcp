# MCP Audit Remediation Implementation Plan

## 执行结果

- 状态：已完成，独立 reviewer 终审无阻断项。
- 自动化验证：`226 passed, 1 skipped`；跳过项为默认禁用的真实桌面截图测试。
- 人工/集成验证：设置 `COMPUTER_USE_RUN_MANUAL=1` 后真实桌面截图测试通过。
- 未主动注入真实滚轮和角落 fail-safe，避免改变用户前台应用或干扰远控；对应执行和报告路径已有自动化覆盖。
- MCP 端到端复测前已终止 8 个旧服务进程；当前会话 transport 随之关闭，需要客户端重新加载 MCP 后复测。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement each defect with a verified RED/GREEN cycle.

**Goal:** 修复深度审计中除“允许输入密码”和“仅限制主屏”之外的全部确认缺陷。

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

明确不修：

- 允许向密码框输入内容，这是用户确认的产品特性。
- 只支持主屏/非负坐标，这是用户确认的当前产品边界。

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

## Task 8：独立验收与归档

- [ ] 执行完成后 Spawn 全新 reviewer，对照本计划、用户排除项和 git diff 审计实现。
- [ ] Reviewer 必须核对：没有改变密码输入特性；没有新增负坐标/副屏输入支持；所有验收标准有测试证据。
- [ ] 若 reviewer 有阻断项，保留计划在 `active/` 并修复后重新验收。
- [ ] Reviewer 通过后，将本计划移至 `docs/plans/completed/`，更新 `docs/CURRENT.md`。

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
- 完整自动化测试通过。
- GUI 安全人工验证完成。
- 独立 reviewer 验收通过后才归档计划。
