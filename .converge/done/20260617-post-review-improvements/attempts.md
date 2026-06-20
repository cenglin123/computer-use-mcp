## Round 15 attempt · suggestion 1
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 3 Step 4 的删除清单未包含 `_TASK_CONTEXT_EXCLUDED_TOOLS`。Step 3 已将该常量迁移到 `computer_use/tools/schemas.py`，但按 Step 4 字面执行会在 `mcp_server.py` 中遗留无引用的同名常量，造成 schema 相关常量的所有权分散。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 3 Step 4 的删除清单中加入 `_TASK_CONTEXT_EXCLUDED_TOOLS`，与 Step 3 迁移列表保持一致。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md:502 — 删除清单追加 "、`_TASK_CONTEXT_EXCLUDED_TOOLS`"
- R15 verdict: 

## Round 15 attempt · suggestion 2
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 1 Step 4 的 `integration_app` fixture 返回类型标注为 `Generator[callable, None, None]`，但 `callable` 不是有效类型提示符（应使用 `typing.Callable`）。虽然 `from __future__ import annotations` 使其不会运行时失败，但类型检查会报错。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 将 fixture 返回类型改为 `Generator[Callable, None, None]`，并在 imports 中追加 `from collections.abc import Callable`。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md:178 — 新增 `from collections.abc import Callable`; :247 — `callable` -> `Callable`
- R15 verdict: 

## Round 16 attempt · BR3-1
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 1 与 Task 4 的跨项目文档职责冲突。文件结构部分和 Task 1 均要求修改 README.md（增加集成测试运行说明），但 Task 4 声明“Task 4 是跨项目文档的唯一负责人”。README.md 属于跨项目文档，导致两个 Task 对同一文件存在冲突的修改权限，执行时易产生职责不清、重复或遗漏。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 将 README.md 的修改职责从 Task 1 移除，统一归口到 Task 4，并在 Task 4 新增 README.md 集成测试运行说明步骤。
- Diff: 文件结构与 Task 1 中删除 README.md；Task 4 Files 新增 README.md 并新增 Step 2 写入集成测试运行说明；提交命令加入 README.md。
- R16 verdict: 

## Round 16 attempt · BR3-2
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 1 的集成测试名为 test_notepad_type_and_verify，但并未验证输入文本实际出现在 Notepad 中，仅断言 type 工具返回结果不含 error 且两次截图路径不同。作为 P0 级“真实 GUI 集成测试”，核心闭环（输入 → 界面状态变化 → 验证）未完成，测试强度不足以支撑“集成测试骨架”的验收目标。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 重命名测试为 `test_notepad_launch_and_screenshot`，移除 `type` 工具调用，改用文件存在与大小断言验证两次截图均为有效文件。
- Diff: 测试函数改名；删除 type 调用；截图断言改为验证文件存在且大小 > 0 并路径不同；Fixture 契约与安全提示同步移除 type 相关描述。
- R16 verdict: 

## Round 16 attempt · BR3-3
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 1 fixture teardown 兜底清理当前用户所有 notepad.exe 进程，范围过宽。该行为可能误杀用户正常使用的 Notepad 实例，与集成测试“副作用可控”的安全承诺相冲突。应改为仅清理 fixture 自身启动的进程（通过 PID 或进程组），而非按用户名全量终止。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 将 fixture teardown 的清理范围收窄为仅终止 `ManagedApp.proc` 记录 PID 的进程，移除 `taskkill /F /IM notepad.exe` 与按用户名遍历终止所有 notepad.exe 的兜底。
- Diff: ManagedApp.close 仅终止 self.proc 并记录 warning；teardown 删除 broad user notepad 清理；Fixture 契约与风险与取舍同步更新。
- R16 verdict: 

## Round 16 attempt · suggestion 1
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 3 测试断言 len(schemas.TOOLS) == 34 过于脆弱，新增或删除工具即导致测试失败。建议改用非精确数量断言（如 >0 且包含关键工具名），或明确说明该数字需同步维护并配套自动化检查。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 将精确数量断言改为 `len(schemas.TOOLS) > 0` 并断言包含 `screenshot` 工具名。
- Diff: Task 3 Step 1 测试代码移除 ==34 断言，替换为 >0 与 any(tool.name == "screenshot")；删除相关维护注释。
- R16 verdict: 

## Round 16 attempt · suggestion 2
- source: converge_loop
- reviewer_backend: opencode
- Issue: 集成测试中两次截图保存到显式不同的路径，随后断言 saved_path 不同，该断言恒真，未验证 screenshot 工具的可重复执行能力。建议改为验证两个文件均存在、文件大小非零或内容不同。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在两次截图断言中验证文件存在且大小 > 0，并保留路径不同的比较。
- Diff: Task 1 Step 1 测试代码中两次截图均断言 saved_path 对应文件存在且 st_size > 0，再断言路径不同。
- R16 verdict: 

## Round 16 attempt · suggestion 3
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 1 fixture 依赖 win32gui/pywin32，但计划仅说明其“通常随 uiautomation/pyautogui 安装”。pyautogui 并不保证安装 pywin32，存在依赖缺失风险。建议在 pyproject.toml 中显式声明 pywin32 或 uiautomation 依赖。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 1 Step 2 的 dev 依赖组中显式添加 `pywin32>=306` 并说明其用途。
- Diff: pyproject.toml dev 依赖追加 pywin32>=306；步骤说明增加 pywin32 为 win32gui 提供依赖。
- R16 verdict: 

## Round 16 attempt · suggestion 4
- source: converge_loop
- reviewer_backend: opencode
- Issue: 原始评审指出“异常吞没较多”和“危险命令正则可能绕过”两项工程/安全问题，本计划未纳入也不在不包含列表中说明取舍原因。建议在“不包含”或“风险与取舍”中显式说明未处理这两项的理由。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在“不包含”列表中显式说明未处理“异常吞没较多”和“危险命令正则可能绕过”的理由。
- Diff: 范围-不包含新增两项：异常吞较多需 trace/logging 改造；危险命令正则绕过迁移白名单需设计评审，均超出本 sprint。
- R16 verdict: 

## Round 16 attempt · suggestion 5
- source: converge_loop
- reviewer_backend: opencode
- Issue: 集成测试直接调用 mcp_server._call_tool 内部函数，而非通过 serve()/MCP 协议入口验证端到端行为。作为“真实 GUI 集成测试”，建议至少说明为何不采用公共接口，或补充一条基于公共接口的测试。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 1 Step 1 添加“测试接口说明”，解释集成测试使用 `mcp_server._call_tool` 作为内部测试钩子的原因。
- Diff: Task 1 Step 1 新增 note，说明 `_call_tool` 是内部测试钩子，重点验证工具行为而非协议传输层。
- R16 verdict: 

## Round 16 attempt · suggestion 6
- source: converge_loop
- reviewer_backend: opencode
- Issue: “本计划明确排除混合 DPI 多显示器支持...”在“验收标准”与“风险与取舍”两段几乎逐字重复。“OCR 已移除...”同样在“验收标准”与“风险与取舍”两段几乎逐字重复。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 删除“验收标准”与“风险与取舍”中关于混合 DPI 和 OCR 的重复整句，将详细说明保留在“风险与取舍”，验收标准只保留能力声明。
- Diff: 验收标准删除混合 DPI 与 OCR 重复句；风险与取舍删除相同重复句并更新 GUI 测试副作用描述以匹配收窄清理策略。
- R16 verdict: 

## Round 18 attempt · BR4-1
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 1 的 fixture 通过 monkeypatch 替换 computer_use.mcp_server.load_config，使 screenshot_dir 指向临时目录；但测试实际调用的是 mcp_server._call_tool("screenshot", ...)。计划未验证 _call_tool 是在调用时动态读取 load_config()，还是在模块导入/初始化时已将配置缓存或绑定到局部变量。若属于后两种情况，monkeypatch 不会生效，save_path 校验将因不在用户配置的 screenshot_dir 内而失败，导致集成测试无法通过。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 1 Step 4 Fixture 契约中补充 load_config 调用时机验证说明。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 在 Fixture 契约新增 bullet，说明 `_dispatch_tool` 在 screenshot 工具调用时动态调用 `load_config()`（`computer_use/mcp_server.py:1044`），monkeypatch 在测试运行时生效。
- R18 verdict: 

## Round 18 attempt · BR4-2
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 1 测试假设 screenshot 工具接受 save_path 参数，并且会将其与配置的 screenshot_dir 做校验。计划未引用当前 screenshot 工具的 schema 或校验逻辑，也未说明当 save_path 为绝对路径或位于临时目录时的行为。若现有工具不支持 save_path、或校验规则与假设不同，按 plan 写出的 RED 测试/实现无法通过。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 1 Step 1 测试代码截图调用前补充 save_path 契约说明。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 在测试代码 `# 1. 截图到 fixture 提供的临时目录` 前新增注释，说明 screenshot 工具 schema 包含 `save_path` 且 `_dispatch_tool` 会校验其必须位于配置的 `screenshot_dir` 之下（`computer_use/mcp_server.py:1059-1068`）。
- R18 verdict: 

## Round 18 attempt · BR4-3
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 2 的 RED 测试断言 launcher.launch_app("notepad") 返回 {"launched": False, "error": ...} 结构，但计划仅展示修改 _BLOCKED_ERROR 常量，未验证 launch_app 在被拦截时确实返回该字典结构而非抛出异常或返回不同字段。若现有返回契约与测试假设不符，RED 测试在修复前就会因结构错误而非错误消息缺失而失败，无法正确驱动实现。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 2 Step 1 测试代码前补充 launch_app 拦截返回结构说明。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 在测试函数定义前新增“结构契约”注释，说明 `launcher.launch_app` 在白名单拦截时返回 `{"launched": False, "error": <str>}`（`computer_use/launcher.py:171-172`）。
- R18 verdict: 

## Round 18 attempt · BR4-4
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 1 测试断言 snap["controls"]，假设 get_ui_snapshot 返回包含 controls 键的字典。计划未说明该工具的实际返回 schema，也未给出等价验证方式。若返回的是列表、或键名不同，集成测试会在第 2 步失败。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 1 Step 1 get_ui_snapshot 调用前补充 controls 键存在说明。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 在 `# 2. 验证 UIA 返回了控件列表` 前新增注释，说明 `computer_use.snapshot.get_ui_snapshot` 返回字典包含 `controls` 键（`computer_use/snapshot.py:238`）。
- R18 verdict: 

## Round 18 attempt · suggestion 1
- source: converge_loop
- reviewer_backend: opencode
- Issue: 原始评审将“混合 DPI 多显示器支持”列为 P0，但计划明确排除并建议单独立项。虽然边界诚实，但应在“风险与取舍”或“不包含”中补充为何接受不处理最高优先级项的决策依据。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在“风险与取舍”中补充混合 DPI 排除的决策依据。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 在“风险与取舍”末尾新增风险项，说明混合 DPI 支持需要重写坐标系与 monitor 检测逻辑，技术风险高、测试成本高，作为 P0 仍超出当前 sprint 容量，因此明确排除并计划后续单独立项。
- R18 verdict: 

## Round 18 attempt · suggestion 2
- source: converge_loop
- reviewer_backend: opencode
- Issue: 原始评审在测试策略不足中列出“安全规则的 fuzz 测试”，但计划既未纳入也未明确排除，存在覆盖遗漏。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在“不包含”列表中补充安全规则 fuzz 测试排除说明。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 在“不包含”末尾新增项：安全规则 fuzz 测试需要额外框架与 CI 支持，超出本 sprint 范围。
- R18 verdict: 

## Round 18 attempt · suggestion 3
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 2 创建/更新 config.example.yaml 前未说明如何检查文件是否已存在及其当前内容，直接覆盖可能丢失既有示例。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 2 Step 4 配置示例步骤前追加保留现有内容的提示。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 在“创建或更新 config.example.yaml”前新增注释：若文件已存在，保留现有内容并追加示例条目，不要直接覆盖。
- R18 verdict: 

## Round 18 attempt · suggestion 4
- source: converge_loop
- reviewer_backend: opencode
- Issue: 计划将 _error_kind_for_result 列为“不移动的其他常量”示例，但该名称更可能是函数而非常量，表述欠准。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 修正 Task 3 Step 3 中 _error_kind_for_result 的归类描述。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 将“保持 mcp_server.py 运行时所需的其他常量（如 _NEXT_ACTION_*、_error_kind_for_result 等）不移动”改为“保持 _NEXT_ACTION_* 等常量不移动；不移动的其他辅助函数（如 _error_kind_for_result）也不移动”。
- R18 verdict: 

## Round 19 attempt · issue 1
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 1 的 RED 测试调用 screenshot 工具时显式传入 save_path，但断言仅检查返回路径存在、非空且与第二次截图路径不同，未断言返回的 saved_path 等于请求的 shot_path。若实现忽略 save_path 而返回自动生成路径，测试仍会通过，导致 save_path 契约验证存在假阴性，集成测试无法确保 screenshot 工具尊重用户指定的保存路径。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: Update Task 1 RED test assertions to compare returned saved_path with requested shot_path for both screenshots.
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — Task 1 Step 1 screenshot assertions now assert `str(saved1) == str(shot_path)` and `str(saved2) == str(shot2_path)`; ManagedApp already exposes screenshot_dir.
- R19 verdict: 

## Round 19 attempt · suggestion 1
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 2 RED 测试通过 monkeypatch 替换 safety._allowed_commands，但未像 Task 1 那样验证 launcher 是在运行时动态调用该函数，还是在模块导入时已缓存。补充该验证可提升测试隔离说明的严谨性。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: Add a note in Task 2 Step 1 test isolation section explaining _allowed_commands is dynamically called when is_allowed_command runs, referencing computer_use/safety.py:71.
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — Task 2 Step 1 测试隔离说明追加动态调用验证注释（computer_use/safety.py:71）。
- R19 verdict: 

## Round 20 attempt · suggestion
- source: converge_loop
- reviewer_backend: opencode
- Issue: Plan body 保留多处具体代码行号引用（如 `computer_use/mcp_server.py:1059-1068`、`computer_use/snapshot.py:238`、`computer_use/mcp_server.py:1044` 等）。Task 3 迁移 schema 后 mcp_server.py 行号必然变化，这些引用将迅速过期，增加维护负担并可能误导后续读者。建议改为函数/模块级引用或删除行号。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 将具体行号引用改为函数/模块级引用。
- Diff: 替换 5 处行号引用为函数/模块名引用（`computer_use.mcp_server` screenshot handler、`computer_use.snapshot.get_ui_snapshot`、`computer_use.mcp_server._dispatch_tool`、`computer_use.launcher.launch_app`、`computer_use.safety.is_allowed_command`）。
- R20 verdict: 

## Blind recheck 6 · issue 1
- source: blind_recheck
- reviewer_backend: opencode
- Issue: Task 2 把通用 `_BLOCKED_ERROR` 改写为只针对空 `allowed_commands` 白名单的提示，并用于 `launch_app` 两处拦截返回点；若第二处是敏感进程/窗口拦截，新消息会误导用户去配置白名单，而敏感进程本就不允许通过白名单放行。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 拆分为 `_NOT_ALLOWED_ERROR`（白名单未命中/为空）和 `_SENSITIVE_PROCESS_ERROR`（敏感进程/窗口拦截），并更新 RED 测试断言以排除 sensitive 字样。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — Task 2 Step 1 新增 `assert "sensitive" not in result["error"].lower()`；Step 3 将单一 `_BLOCKED_ERROR` 改为 `_NOT_ALLOWED_ERROR` + `_SENSITIVE_PROCESS_ERROR` 并分别用于两个拦截分支
- BR6 verdict:

## Blind recheck 6 · issue 2
- source: blind_recheck
- reviewer_backend: opencode
- Issue: 原始评审 P2 建议「引入视觉 fallback 和 OCR」在「范围 > 不包含」中完全缺失，仅在 pitfalls.md 和验收标准中零散提到 OCR 未提供，边界不诚实。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 在「范围 > 不包含」中显式列出「独立 OCR 工具 / 视觉 fallback 引擎的实现」，并说明当前采用多模态模型读图 + UIA 不可用时回退到坐标操作。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 范围 > 不包含追加 OCR/visual-fallback engine 排除项
- BR6 verdict:

## Blind recheck 7 · issue 1
- source: blind_recheck
- reviewer_backend: opencode
- Issue: Task 1 集成测试调用 `get_ui_snapshot` 并断言 `snap["controls"]`，但该工具依赖可选的 `uiautomation`；项目设计允许 UIA 缺失时仅 warning 并回退到坐标操作。集成测试在 UIA 未安装环境会失败，与“UIA 可选”矛盾。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 在 `tests/integration/test_notepad_smoke.py` 模块顶部使用 `pytest.importorskip("uiautomation")`；同时在 Task 1 Step 5 增加检查 `.github/workflows/*.yml` 的说明，统一 CHANGELOG title 与 commit message。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — Task 1 Step 1 新增 `pytest.importorskip("uiautomation")`；Step 5 改为“标记集成测试并配置 CI 跳过”；Task 4 Step 5 CHANGELOG title改为英文以匹配 commit message
- BR7 verdict:

## Blind recheck 8 · issue 1
- source: blind_recheck
- reviewer_backend: opencode
- Issue: `tests/integration/conftest.py` 在模块顶层无条件导入 `win32gui`；pytest 在收集阶段即导入 conftest，即使通过 `-m "not integration"` 取消选择，缺少 `pywin32` 也会导致 collection 崩溃，与“集成测试可选”矛盾。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 对 `win32gui` 做可选导入保护（`try/except` 置为 None），在 `_find_window_by_process` 中缺失时 `pytest.skip`。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — Task 1 Step 4 conftest 代码移除顶层 `import win32gui`，改为 try/except 保护 + 函数内 `pytest.skip`
- BR8 verdict:

## Blind recheck 8 · issue 2
- source: blind_recheck
- reviewer_backend: opencode
- Issue: Task 2 RED 测试未 mock `_get_shell_dispatch` 和 `_get_wscript_shell`；在缺少 `win32com` 的环境，`launch_app` 会在命中白名单分支前返回 `"Shell automation unavailable"`，导致断言因错误原因失败。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 在 RED 测试开头用 monkeypatch 让这两个函数返回非 None 的占位对象。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — Task 2 Step 1 测试代码新增 mock `_get_shell_dispatch` 与 `_get_wscript_shell`
- BR8 verdict:

## Blind recheck 9 · issue 1
- source: blind_recheck
- reviewer_backend: opencode
- Issue: Task 1 fixture 在 `_launch` 中先启动 notepad，然后才创建 `ManagedApp`；若窗口激活超时失败，`ManagedApp` 尚未加入 `launched`，teardown 无法终止进程，导致 notepad 遗留。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 在调用 `subprocess.Popen` 后立即创建 `ManagedApp` 并加入 `launched`，再尝试激活窗口；激活失败时调用 `app.close()`。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — Task 1 Step 4 `_launch` 调整为先创建 ManagedApp 再加入 launched，然后 try/except 激活窗口
- BR9 verdict:

## Blind recheck 9 · issue 2
- source: blind_recheck
- reviewer_backend: opencode
- Issue: 验收标准要求混合 DPI P0 排除获得书面确认，但未说明确认机制、记录位置。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 在 Task 5 新增 Step 1「确认 P0 排除签收 Gate」，规定确认方式（frontmatter 或提交消息引用来源）。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — Task 5 新增 Step 1，原 Step 1/2/3 后移
- BR9 verdict:

## Blind recheck 9 · issue 3
- source: blind_recheck
- reviewer_backend: opencode
- Issue: Task 2 RED 测试将 `_get_shell_dispatch`/`_get_wscript_shell` mock 为裸 `object()`，假设它们只在白名单检查后被使用；若未来实现调整顺序，测试会提前失败。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 使用 `SimpleNamespace` 提供最小 fake shell/wscript 对象。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — Task 2 Step 1 测试代码用 SimpleNamespace 替换 object() mock
- BR9 verdict:

## Blind recheck 9 · issue 4
- source: blind_recheck
- reviewer_backend: opencode
- Issue: Task 1 测试直接对 `_call_tool` 结果调用 `json.loads()` 并断言字段；计划使用「已验证」声明，但 blind reviewer 无法独立核实。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 将「已验证/已确认」改为「当前实现中」，并在测试代码中增加返回类型假设注释。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 全文替换「已验证」「已确认」为「当前实现中」；Task 1 Step 1 增加 JSON 返回类型注释
- BR9 verdict:

## Blind recheck 10 · issue 1
- source: blind_recheck
- reviewer_backend: opencode
- Issue: 项目已存在 `manual` marker 表示需要真实 Windows 桌面环境，本 plan 又新增语义重叠的 `integration` marker，未做调和；CI 跳过命令 `-m "not integration"` 无法阻止现有的 `manual` 测试运行，造成约定混乱。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 复用现有 `manual` marker，将 plan 中所有 `@pytest.mark.integration` 与 `-m "not integration"` 替换为 `manual`；不再新增 marker。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 全文替换 integration marker 为 manual；Task 1 Step 5 改为确认并使用现有 manual marker
- BR10 verdict:

## Blind recheck 10 · suggestion 1
- source: blind_recheck
- reviewer_backend: opencode
- Issue: P0 混合 DPI 排除 gate 已在验收标准列出，但 artifact 尚无 frontmatter 占位。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 在 plan 顶部增加 frontmatter 字段 `mixed_dpi_exclusion_ack: pending`，并在 Task 5 Step 1 说明执行前替换为实际确认。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 顶部新增 YAML frontmatter；Task 5 Step 1 更新为引用 frontmatter 占位
- BR10 verdict:

## Blind recheck 5 · issue 1
- source: blind_recheck
- reviewer_backend: opencode
- Issue: Task 3 Step 4 的 `mcp_server.py` 导入示例遗漏 `_TASK_CONTEXT_EXCLUDED_TOOLS`，而 plan 已要求迁移该常量；未改动的 `_attach_task_context_schemas()` 在 `mcp_server.py` 中仍引用它，迁移后将导致 NameError。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 在 Task 3 Step 4 的导入示例中加入 `_TASK_CONTEXT_EXCLUDED_TOOLS`。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — Task 3 Step 4 导入示例新增 `_TASK_CONTEXT_EXCLUDED_TOOLS`
- BR5 verdict:

## Blind recheck 5 · issue 2
- source: blind_recheck
- reviewer_backend: opencode
- Issue: 原始评审将「混合 DPI 多显示器支持」列为 #1 P0 项，本 plan 明确排除但未提供用户/维护者签认或后续立项承诺，scope 缺口未闭环。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 在「风险与取舍」节追加 P0 项排除确认与 2 周内单独立项承诺。
- Diff: docs/plans/active/post-review-improvements-2026-06-17.md — 「风险与取舍」末尾新增 P0 排除确认项，要求用户/维护者签认并承诺 2 周内创建 multi-dpi-support 计划
- BR5 verdict:


