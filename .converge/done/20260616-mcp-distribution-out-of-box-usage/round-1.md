---
round: 1
reviewer_backend: opencode
reviewer_count: 3
generated_at: 2026-06-16T23:05:00+08:00
---

# Round 1 · 20260616-mcp-distribution-out-of-box-usage

Ultraverge parallel review spawned 3 independent reviewers with identical self-contained prompts covering 5 pre-check questions and DR1-DR7 design dimensions.

---

## Reviewer 1 Output

```yaml
reviewer_id: 1
round: 1
verdict: 阻断需修复
blocking_issues:
  - id: 1
    description: |
      客户端示例配置文件写死了当前开发机的绝对路径 `C:\Project\computer-use-mcp\.venv\Scripts\python.exe`，分发后其他安装路径的用户无法直接使用，直接违背“开箱可用”目标。计划把环境锁定的数据写进了产物规格，Q3 数据纯度答案为“否”。
    attribution: plan_defect
    severity: conceptual
    plan_amendment_required: true
    location: Task 5 Step 1, lines 607-626 (`examples/clients/generic-mcp.json`, `examples/clients/kimi-code.toml`)
    design_dimension: pre-check-Q3, DR6
  - id: 2
    description: |
      Task 2 Step 3 给出的 `_get_prompt` 实现使用了 `TextContent`，但同一步的 import 行只写了 `from mcp.types import GetPromptResult, Prompt, PromptMessage`，未引入 `TextContent`。按该代码片段字面执行会得到 NameError。虽然当前 `mcp_server.py` 已导入 `TextContent`，但计划文本不完整，执行者可能遗漏。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 2 Step 3, lines 285-316 (`computer_use/mcp_server.py`)
    design_dimension: DR1, DR2
  - id: 3
    description: |
      Task 2 Step 3 文字要求“如果未知 prompt，捕获 KeyError 并抛 ValueError”，但紧接给出的 `_get_prompt` 函数和 `get_prompt` handler 代码里均未体现该处理；未知 prompt 会以 KeyError 泄漏为内部错误。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 2 Step 3, line 319
    design_dimension: DR2
  - id: 4
    description: |
      Task 6 的 smoke 脚本只给出“最小行为”和一条具体命令 `python tools\smoke_mcp_client.py --server ... --args -m computer_use.mcp_server`，但未给出与 `--server` / `--args` 对应的 argparse 实现或接口约定；命令与实现规格不匹配，执行时必然出现歧义。且 `--args` 后接多值参数在 argparse 中需特别处理，计划未说明。
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: Task 6, lines 709-750 (`tools/smoke_mcp_client.py`)
    design_dimension: DR2
suggestion_issues:
  - description: |
      建议在 `computer_use/doctor.py` 或 `tests/test_cli.py` 中显式断言：导入 `doctor` 模块本身不会加载 `pyautogui` / `computer_use.core`。当前配置安全，但计划未把“doctor 模块级不触碰输入设备”作为不变量文档化或测试化。
    design_dimension: DR2, DR4
  - description: |
      `examples/clients/agent-prompt.md` 与 `computer_use/guidance.py` 存在自然语言冗余；计划虽已用分发就绪测试守住关键词，仍可考虑在 `examples/clients/agent-prompt.md` 顶部注明“此内容应与 computer_use.guidance 保持一致”。
    design_dimension: DR5
  - description: |
      README 第一屏流程把 `review_task_session` 列为只读 smoke 工具，但未说明需先 `start_task` 获取 task_id；建议写成“start_task → review_task_session(task_id)”以避免用户困惑。
    design_dimension: DR3
  - description: |
      `doctor.py` 中 `config[key]` 假设四个目录键一定存在；建议改用 `config.get(key)` 并给出缺省 fallback，提升对未来配置变更的防御性。
    design_dimension: DR2
  - description: |
      计划未提及是否要在 `computer_use/__init__.py` 显式导出 `guidance`。当前为空文件，子模块导入可工作，但显式导出更利于 API 稳定性。
    design_dimension: DR1
antipattern_observations:
  - type: environment_lock-in
    evidence: |
      `"command": "C:\\\\Project\\\\computer-use-mcp\\\\.venv\\\\Scripts\\\\python.exe"` (Task 5 Step 1, `examples/clients/generic-mcp.json`)
      `command = "C:\\Project\\computer-use-mcp\\.venv\\Scripts\\python.exe"` (Task 5 Step 1, `examples/clients/kimi-code.toml`)
  - type: minimum_patch
    evidence: |
      `_get_prompt` 代码片段只给出最简实现，缺少 `TextContent` 导入和未知 prompt 的 KeyError 转 ValueError 处理（Task 2 Step 3）。
  - type: false_generality
    evidence: |
      文件名为 `generic-mcp.json`、定位是“通用 MCP 客户端配置示例”，但内容写死了单一机器的绝对路径，名实不符。
```

---

## Reviewer 2 Output

```yaml
reviewer_id: 2
round: 1
verdict: 阻断需修复
blocking_issues:
  - id: 1
    description: |
      分发示例文件 `examples/clients/generic-mcp.json` 与 `examples/clients/kimi-code.toml` 直接写死了本机绝对路径 `C:\Project\computer-use-mcp\.venv\Scripts\python.exe`，且计划未在示例文件或 Task 5 步骤中要求加入“替换为你自己的路径”的注释/说明。README 现有写法尚有 “Replace the path with the absolute path where you cloned this server” 提示，但新示例文件脱离该上下文后会被用户原样复制，导致开箱即用的配置在其它机器上直接失效，与计划标题“Out-of-Box Usage / Distribution”的可移植目标冲突。
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: "Task 5 Step 1 (examples/clients/generic-mcp.json, examples/clients/kimi-code.toml)"
    design_dimension: DR6
  - id: 2
    description: |
      Task 3 Step 4 要求给 `ui_not_found`、`invalid_tool`、`fail_safe`、coordinate/safety block 四类错误追加 `next_action`，并声明“在不改变 error_kind 的前提下”，但计划没有指明这些 next_action 应注入哪些具体代码位置（如 `_batch_tool` 的 invalid_tool 结果、`_dispatch_pointer_tool` 的控制未找到分支、`_call_tool` 的 SafetyError / FailSafeException / ValueError 处理路径等）。验收标准又要求“常见失败结果包含 next_action”。缺少代码位置映射会导致执行者遗漏注入点，测试通过但验收失败，或误改 error_kind 字段。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: "Task 3 Step 4, Task 8 Step 3"
    design_dimension: DR2
suggestion_issues:
  - description: |
      CLI `doctor` 分支必须置于 `from computer_use.ui_automation import inspect_point` 之前，而不仅仅是 `cs = get_coordinate_system()` 之前，因为 `ui_automation.py` 在模块级导入 `computer_use.core`，会间接加载 `pyautogui`。建议在 Task 4 Step 4 明确写出“在解析 args 后、任何 core/ui_automation 导入前即返回”，以保住只读承诺。
    design_dimension: DR3
  - description: |
      `computer_use/doctor.py` 直接通过 `config[key]` 读取四个目录键，虽当前 `_DEFAULTS` 保证存在，但建议改用 `.get()` 或 `_DEFAULTS` 兜底，避免未来配置 schema 变更时 `run_doctor` 抛出 KeyError。
    design_dimension: DR2
  - description: |
      `doctor` 声称验证“显示器、截图能力”，实际仅检查 `mss`/`PIL`/`uiautomation` 是否可导入以及目录是否可写，并未真正调用 `get_monitors` 或尝试截图。建议要么补充真实只读探测，要么把描述改为“验证依赖与目录可写性”，避免宣传能力与实现不符。
    design_dimension: DR2
  - description: |
      Task 6 的 smoke 脚本没有给出 MCP stdio 调用的具体实现，测试仅验证导入不加载 `pyautogui`。若 MCP SDK 客户端 API 不稳定，计划允许只做 manual 工具，但应明确说明自动化覆盖范围，否则验收标准“只读 smoke”难以判定是否完成。
    design_dimension: DR2
  - description: |
      `doctor` 未检查 `mcp`、`psutil` 等核心依赖是否可导入，而这些是 server 启动的必要条件。建议补充或明确排除理由。
    design_dimension: DR2
antipattern_observations:
  - type: environment_lock-in
    evidence: |
      `examples/clients/generic-mcp.json` 内容：
      `"command": "C:\\\\Project\\\\computer-use-mcp\\\\.venv\\\\Scripts\\\\python.exe"`
      `examples/clients/kimi-code.toml` 内容：
      `command = "C:\\Project\\computer-use-mcp\\.venv\\Scripts\\python.exe"`
  - type: false_generality
    evidence: |
      文件命名为 `generic-mcp.json`，暗示通用模板，但内容硬编码了特定开发者机器的项目路径；没有占位符或注释提示用户替换。
```

---

## Reviewer 3 Output

```yaml
reviewer_id: 3
round: 1
verdict: 阻断需修复
blocking_issues:
  - id: 1
    description: |
      计划声称 doctor 是“只读安装自检”，但 Task 4 Step 3 的 `run_doctor()` 实现会调用 `path.mkdir(parents=True, exist_ok=True)` 创建 `~/.computer-use` 下的日志/截图/trace/task 目录。创建目录属于写操作，与“只读”身份直接矛盾，也会让用户在安全审计场景下对 doctor 侧写行为产生误判。若 doctor 需要验证“可写目录”，应明确将其命名为 benign write probe 或拆分 read-only 检查与 write probe，而不是继续称为 read-only。
    attribution: plan_defect
    severity: conceptual
    plan_amendment_required: true
    location: "Task 4 Step 3, lines 490-555; 验收标准 line 907"
    design_dimension: "pre-check-Q2 / DR4"
  - id: 2
    description: |
      Task 3 Step 3 仅增强 click / move_to / type / key_combo / press_key 的 description 以提示“真实 Windows 输入”，却遗漏同样发送真实输入的 mouse_down / mouse_up / drag / key_down / key_up / scroll。这会在 tools/list 中形成安全描述断层：部分输入工具声明风险，部分不声明，导致 agent 对同一类危险操作产生不一致的认知。计划应统一覆盖所有能触发真实鼠标/键盘/滚轮事件的工具。
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: "Task 3 Step 3, lines 385-391"
    design_dimension: "DR4"
  - id: 3
    description: |
      Task 6 line 707 的测试文件位置写成 “Test: `tests/test_cli.py` or new `tests/test_smoke_script.py`”，存在二选一的结构歧义。实施计划不应在测试文件落点使用“或”，否则验收时无法确定哪份文件承担该职责，也影响 `pytest tests/` 的覆盖预期。计划应明确指定为 `tests/test_smoke_script.py` 或给出二选一决策规则。
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: "Task 6, line 707"
    design_dimension: "DR2"
  - id: 4
    description: |
      Task 3 Step 4 要求“在不改变 error_kind 的前提下给错误结果追加 next_action”，但只给出了错误种类与文案映射，没有指出这些错误在 `computer_use/mcp_server.py`、`computer_use/composite.py`、`computer_use/runner.py` 中的具体构造点。例如 `ui_not_found` 在 `composite.py` 多处、`invalid_tool` 在 `mcp_server.py` batch 与 `runner.py` 中、`fail_safe` 在 mcp_server 异常处理中。缺少落点说明会导致实现者遗漏部分路径，next_action 字段分布不均，违背 DR1 一致性。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: "Task 3 Step 4, lines 394-403"
    design_dimension: "DR2"
  - id: 5
    description: |
      Task 4 Step 1 的测试 `test_cli_doctor_outputs_read_only_json_without_input_device_import` 通过 monkeypatch 和 `sys.modules` 检查来验证 doctor 不加载 pyautogui，但缺少一个与现有 `test_cli_module_import_does_not_load_pyautogui` 等价的子进程导入测试。仅靠同进程 monkeypatch 无法 robust 地证明 `computer_use/doctor.py` 在模块级不导入 `computer_use.core` 或 `pyautogui`（例如当 `doctor.py` 未来被重构引入顶层 import 时，同进程测试可能因缓存而漏报）。计划应补一个 subprocess 导入测试。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: "Task 4 Step 1, lines 447-480"
    design_dimension: "DR2"
suggestion_issues:
  - description: |
      计划假设 `mcp>=1.0.0` 支持 `list_prompts` / `get_prompt` 与 `Prompt` / `GetPromptResult` / `PromptMessage` 类型，但未显式注明最低 SDK 版本或提供兼容性检查。建议在 Task 2 增加一行确认当前依赖 `mcp>=1.0.0` 已覆盖 prompts API，或在依赖中收紧版本。
    design_dimension: "DR6"
  - description: |
      `doctor.run_doctor()` 在 `load_config()` 失败时会直接抛出异常，没有返回结构化错误。建议在 doctor 中捕获配置加载异常并返回 `{"status": "failed", "checks": [...]}`，避免安装自检命令输出非 JSON。
    design_dimension: "DR2"
  - description: |
      计划将 `computer_use/guidance.py` 定义为“单一事实源”，但 doctor 的 `next_steps` 文案直接硬编码在 `doctor.py` 中。可考虑将 doctor 提醒文案也放到 guidance.py 导出，减少后续漂移。
    design_dimension: "DR1"
  - description: |
      `computer_use_text_only_limits` prompt 同时列出 `review_task` 与 `review_task_session`，二者是不同的工具，对纯文本模型来说容易混淆。建议在 guidance 中说明 `review_task`（工具）与 `review_task_session`（会话复盘工具）的区别。
    design_dimension: "DR1"
  - description: |
      可增加一条导入测试，确保 `computer_use/guidance.py` 模块级导入不触发 `pyautogui` 或 `computer_use.core`，以守护“轻量 guidance”的边界。
    design_dimension: "DR2 / DR6"
antipattern_observations:
  - type: minimum_patch
    evidence: |
      Task 3 Step 3: “只修改公开分发关键工具，不重写全量工具表”。该策略虽然可控制 tools/list 上下文长度，却把 mouse_down / mouse_up / drag / key_down / key_up / scroll 等同样发送真实输入的工具排除在安全提示之外，形成以“是否关键”为标准的描述断层，留下安全提示缺口。
```

---

## Orchestrator 处理记录

- **[Orchestrator Detection]** Verdict 一致性：3/3 reviewers returned `verdict: 阻断需修复`. Unanimous non-executable.
- **[Orchestrator Detection]** Type R 等价标注：
  - Reviewer 1 B1, Reviewer 2 B1, Reviewer 3 (no exact duplicate) all concern hard-coded absolute paths in example configs → marked as `examples_path_hardcoded`.
  - Reviewer 1 B2/B3 and Reviewer 3 (no duplicate) concern `_get_prompt` snippet completeness; R2 did not raise this but it is a valid defect.
  - Reviewer 2 B2 and Reviewer 3 B4 both concern missing concrete code injection points for `next_action` → marked as `next_action_location_undefined`.
- **[Orchestrator Detection]** 无 Type O（本轮无历史可推翻）。
- **[Orchestrator Detection]** 无盲审触发条件（尚未收敛）。
- **[Orchestrator Detection]** boundary_check: pass（本轮仅循环管理 + 语义判定，未直接修改产物）。
