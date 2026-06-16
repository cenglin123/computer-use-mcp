# Attempt Log · 20260616-mcp-distribution-out-of-box-usage

## Round 1 attempt · issue R1-B1 / R2-B1 (hard-coded example paths)
- source: converge_loop
- reviewer_backend: opencode
- Issue: 客户端示例配置文件写死了当前开发机的绝对路径 `C:\Project\computer-use-mcp\.venv\Scripts\python.exe`，分发后其他安装路径的用户无法直接使用；文件名为 `generic-mcp.json` 但内容不通用，名实不符。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在示例文件中加入占位符/注释说明替换路径，或在 Task 5 中显式说明用户必须替换路径。
- Diff: N/A
- R1 verdict: Fixed by executor
- **[Orchestrator Detection at R2]** Status changed to: Accepted

## Round 1 attempt · issue R1-B2 (missing TextContent import)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 2 Step 3 给出的 `_get_prompt` 实现使用了 `TextContent`，但同一步的 import 行只写了 `from mcp.types import GetPromptResult, Prompt, PromptMessage`，未引入 `TextContent`。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 import 行中加入 `TextContent`，或说明复用 `mcp_server.py` 已有的 `TextContent` 导入。
- Diff: N/A
- R1 verdict: Fixed by executor
- **[Orchestrator Detection at R2]** Status changed to: Accepted

## Round 1 attempt · issue R1-B3 (missing unknown prompt error handling)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 2 Step 3 文字要求“如果未知 prompt，捕获 KeyError 并抛 ValueError”，但给出的代码里未体现该处理。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 `_get_prompt` 或 `get_prompt` handler 中显式捕获 KeyError 并 raise ValueError。
- Diff: N/A
- R1 verdict: Fixed by executor
- **[Orchestrator Detection at R2]** Status changed to: Accepted

## Round 1 attempt · issue R1-B4 (smoke script CLI underspecified)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 6 的 smoke 脚本只给出命令示例，未给出与 `--server` / `--args` 对应的 argparse 实现或接口约定；命令与实现规格不匹配。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在计划中给出 `tools/smoke_mcp_client.py` 的 argparse 接口与参数解析实现。
- Diff: N/A
- R1 verdict: Fixed by executor
- **[Orchestrator Detection at R2]** Status changed to: Accepted

## Round 1 attempt · issue R2-B2 / R3-B4 (next_action injection points undefined)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 3 Step 4 要求给错误结果追加 `next_action`，但未指明这些 next_action 应注入哪些具体代码位置（如 `_batch_tool`、`_dispatch_pointer_tool`、`_call_tool` 等）。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 3 Step 4 补充每个 error_kind 对应的具体代码构造点和注入方式。
- Diff: N/A
- R1 verdict: Fixed by executor (location mapping added)
- **[Orchestrator Detection at R2]** Status changed to: Partial — R2 found `ui_not_found` mapping inaccurate

## Round 1 attempt · issue R3-B1 (doctor is not read-only due to mkdir)
- source: converge_loop
- reviewer_backend: opencode
- Issue: 计划声称 doctor 是“只读安装自检”，但 `run_doctor()` 实现会调用 `path.mkdir(...)` 创建目录，与“只读”身份矛盾。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 重命名 doctor 的检查项为“目录可写探测”或拆分为 read-only 检查与 benign write probe，并在文档/验收标准中诚实说明。
- Diff: N/A
- R1 verdict: Fixed by executor
- **[Orchestrator Detection at R2]** Status changed to: Accepted

## Round 1 attempt · issue R3-B2 (missing real-input warnings on additional input tools)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 3 Step 3 仅增强 click/move_to/type/key_combo/press_key 的 description，遗漏同样发送真实输入的 mouse_down/mouse_up/drag/key_down/key_up/scroll。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 3 Step 3 的安全提示工具列表中统一加入所有能触发真实输入的工具。
- Diff: N/A
- R1 verdict: Fixed by executor
- **[Orchestrator Detection at R2]** Status changed to: Accepted

## Round 1 attempt · issue R3-B3 (ambiguous smoke test file location)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 6 line 707 的测试文件位置写成 “Test: `tests/test_cli.py` or new `tests/test_smoke_script.py`”，存在二选一的结构歧义。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 明确指定测试文件为 `tests/test_smoke_script.py` 或给出二选一决策规则。
- Diff: N/A
- R1 verdict: Fixed by executor
- **[Orchestrator Detection at R2]** Status changed to: Accepted

## Round 1 attempt · issue R3-B5 (missing subprocess import test for doctor)
- source: converge_loop
- reviewer_backend: opencode
- Issue: `test_cli_doctor_outputs_read_only_json_without_input_device_import` 仅通过 monkeypatch 验证 doctor 不加载 pyautogui，缺少 subprocess 导入测试，无法 robust 证明模块级不导入输入设备模块。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 4 中补充一个 subprocess 导入测试，验证 `computer_use/doctor.py` 模块级不加载 `pyautogui` / `computer_use.core`。
- Diff: N/A
- R1 verdict: Fixed by executor
- **[Orchestrator Detection at R2]** Status changed to: Accepted

---

## Round 2 attempt · issue R2-B1 (README rewrite conflicts with readiness test)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 5 Step 2 要求把 README 注册后流程改成 "First run" section，但 Task 7 的分发就绪测试仍基于旧的 "Register with an MCP Client" header 做断言，导致两者不一致。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 同步 Task 7 测试断言与新的 README 结构；或保留/兼容旧 header。
- Diff: N/A
- R2 verdict: Fixed by executor
- **[Orchestrator Detection at R3]** Status changed to: Accepted

## Round 2 attempt · issue R2-B2 (ui_not_found injection point misidentified)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 3 Step 4 把 `ui_not_found` 注入点放在 `_dispatch_pointer_tool` 控制未找到分支，但实际该处被 `_failure_for_result` 映射为 `error_kind="unknown"`；真正返回 `{"error": "ui_not_found"}` 的是 composite tools（click_by_text, open_menu, fill_form, scroll_until）。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 修正 `ui_not_found` 的注入点映射到 composite tools 的错误构造处；如该 error_kind 实际不存在，则改为在 `_failure_for_result` 中统一注入 next_action。
- Diff: N/A
- R2 verdict: Fixed by executor
- **[Orchestrator Detection at R3]** Status changed to: Accepted

## Round 2 attempt · issue R2-B3 (missing automated tests for other next_action kinds)
- source: converge_loop
- reviewer_backend: opencode
- Issue: 验收标准要求常见失败结果都包含 `next_action`，但 Task 3 只给 `invalid_tool` 加了自动化测试，`fail_safe`、coordinate/safety-block、`ui_not_found` 均无自动化守卫。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 3 Step 5 补充针对 fail_safe、coordinate/safety-block、ui_not_found 的 next_action 自动化测试。
- Diff: N/A
- R2 verdict: Fixed by executor
- **[Orchestrator Detection at R3]** Status changed to: Accepted

## Round 2 attempt · issue R2-B4 (smoke MCP client runtime underspecified)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 6 的 smoke 脚本只描述了 argparse 与高层行为，未给出具体 MCP stdio client 代码、子进程生命周期、超时、错误输出格式或 SDK API 引用；测试仅验证导入不加载 pyautogui，运行行为无验证。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 6 补充 smoke 脚本的核心实现骨架（stdio subprocess、JSON-RPC initialize/tools/list/prompts/list/get_monitors、timeout、错误输出 schema），或明确说明为 manual-only 工具并下调验收标准。
- Diff: N/A
- R2 verdict: Fixed by executor
- **[Orchestrator Detection at R3]** Status changed to: Accepted

---

## Round 3 attempt · issue R3-B1 (guidance.py single-source claim inconsistent)
- source: converge_loop
- reviewer_backend: opencode
- Issue: guidance.py 被定义为“单一事实源”并声称导出 doctor 提醒，但实际只含 MCP prompts；doctor 的 next_steps/model_capability 警告硬编码在 doctor.py，破坏单一事实源架构。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 要么从 guidance.py 导出 doctor 提醒文案与 next_steps，要么修改 guidance.py 的职责描述，取消“导出 doctor 提醒”的声称。
- Diff: N/A
- R3 verdict: Fixed by executor
- **[Orchestrator Detection at R4]** Status changed to: Accepted

## Round 3 attempt · issue R3-B2 (cli.py top-level import risk)
- source: converge_loop
- reviewer_backend: opencode
- Issue: 计划要求 CLI 导入不加载 pyautogui/core 并断言测试通过，但未提供重构策略处理 cli.py 可能存在的模块级 import computer_use.core / pyautogui。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 4 增加前置审计步骤：先读取 cli.py 确认模块级导入，再决定是否需要将 core/ui_automation 导入延迟到具体命令分支内。
- Diff: N/A
- R3 verdict: Fixed by executor
- **[Orchestrator Detection at R4]** Status changed to: Accepted

## Round 3 attempt · issue R3-B3 (doctor config[key] hardcoding)
- source: converge_loop
- reviewer_backend: opencode
- Issue: doctor.py 直接 dict 索引 config[key] 并硬编码四个目录键，未验证 load_config() 返回类型与 key 存在性。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 修改 doctor.py 实现使用 getattr/config.get/默认值，或先读取 config.py 确认返回类型与可用键。
- Diff: N/A
- R3 verdict: Fixed by executor
- **[Orchestrator Detection at R4]** Status changed to: Accepted

## Round 3 attempt · issue R3-B4 (unverified code-base naming assumptions)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 3/6 假设工具名和内部函数名（get_monitors、click_by_text、_batch_tool、_dispatch_tool、_failure_for_result 等）与代码库一致，但未提供验证步骤。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 3 开头增加“前置审计”步骤，读取 mcp_server.py/composite.py/runner.py 确认工具名和内部函数名；根据实际命名调整测试和注入点。
- Diff: N/A
- R3 verdict: Fixed by executor
- **[Orchestrator Detection at R4]** Status changed to: Accepted

## Round 3 attempt · issue R3-B5 (MCP SDK version unspecified)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 2 使用 server.list_prompts()/get_prompt() 装饰器，但未指定 MCP Python SDK 最低版本，也未说明旧版不支持时的回退策略。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 2 增加检查 pyproject.toml/依赖中 mcp 版本，要求 >=1.0.0（或实际支持 prompts 的版本），并提供版本不足时的处理策略（升级依赖或跳过 prompts 注册）。
- Diff: N/A
- R3 verdict: Fixed by executor
- **[Orchestrator Detection at R4]** Status changed to: Accepted

## Round 3 attempt · issue R3-B6 (existing description tests not audited)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 3 要求修改工具 description，但未要求先审计现有测试是否对这些 description 做精确字符串断言。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 3 Step 3 之前增加审计步骤：检查 tests/test_mcp_server.py 是否已有精确 description 断言，必要时先更新既有测试为包含/关键词断言。
- Diff: N/A
- R3 verdict: Fixed by executor
- **[Orchestrator Detection at R4]** Status changed to: Accepted

## Round 3 attempt · issue R3-B7 (README transformation assumptions)
- source: converge_loop
- reviewer_backend: opencode
- Issue: Task 5/7 假设 README 存在“注册后流程”并被替换为“First run”，且测试检查“Generic MCP client”字样，但未明确 README 中必须包含这些文本，也未处理中英文混合情况。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 5 Step 2 明确列出 README 中必须出现的节标题和关键短语；在 Task 7 测试中使用更鲁棒的断言（如检查任意语言的首屏流程关键字）。
- Diff: N/A
- R3 verdict: Fixed by executor
- **[Orchestrator Detection at R4]** Status changed to: Accepted

---

## Blind recheck · issue BR-1 (doctor import-chain audit incomplete)
- source: blind_recheck
- reviewer_backend: opencode
- Issue: 计划只审计 cli.py 顶层导入，未审计 config.py 和 computer_use/__init__.py 是否在模块级加载 pyautogui / computer_use.core；若存在副作用导入，test_doctor_module_import_does_not_load_pyautogui_or_core 会失败。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 在 Task 4 Step 0 增加对 config.py 与 __init__.py 的 import-chain 审计，确保 doctor.py 导入链不触发 pyautogui / core。
- Diff: N/A
- Blind verdict: Open

## Blind recheck · issue BR-2 (doctor crashes if load_config fails)
- source: blind_recheck
- reviewer_backend: opencode
- Issue: doctor 直接调用 load_config() 且未 try/except；配置异常时 doctor 崩溃而非输出 JSON failed check。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 在 run_doctor() 开头捕获 load_config 异常，作为 failed check 返回，再进入后续目录检查。
- Diff: N/A
- Blind verdict: still_blocking (R5)
- R5 attribution: plan_defect
- R5 verdict: Fixed by executor
- **[Orchestrator Detection at R6]** Status changed to: Accepted

## Blind recheck · issue BR-3 (MCP SDK fallback strategy inconsistent)
- source: blind_recheck
- reviewer_backend: opencode
- Issue: Task 2 Step 0 要求确认并升级 mcp>=1.0.0，但 Step 4 又用 try/except AttributeError 静默跳过 prompt 注册；策略未调和。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 统一策略：要么强制 mcp>=1.0.0 并移除 fallback，要么保留 fallback 但将 prompts 不可用作为 doctor warning/failed check 明确告知用户。
- Diff: N/A
- Blind verdict: still_blocking (R5)
- R5 attribution: plan_defect
- R5 verdict: Fixed by executor
- **[Orchestrator Detection at R6]** Status changed to: Accepted

## Blind recheck · issue BR-4 (exact error string assertion in safety test)
- source: blind_recheck
- reviewer_backend: opencode
- Issue: test_coordinate_safety_block_error_includes_next_action 使用 assert data["error"] == "mocked safety block" 精确断言，未审计 _call_tool 是否包装异常消息。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 改为子串断言（"mocked safety block" in data["error"]）或先审计 _call_tool 的 error 字段构造方式。
- Diff: N/A
- Blind verdict: resolved (R5)
- R5 attribution: N/A

## Blind recheck · issue BR-5 (doctor hard-coded config keys unverified)
- source: blind_recheck
- reviewer_backend: opencode
- Issue: doctor 硬编码检查 log_dir/screenshot_dir/trace_dir/task_dir，但未审计 load_config() 实际返回的 schema；键名不符会导致 doctor 全部报 failed。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: true
- Approach: 在 Task 4 Step 0 审计 config schema，或读取 config.yaml 示例/默认值推导可写目录；在实现中使用 config.get 防御缺失键。
- Diff: N/A
- Blind verdict: resolved (R5)
- R5 attribution: N/A
