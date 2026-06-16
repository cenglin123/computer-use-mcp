---
round: 3
reviewer_backend: opencode
generated_at: 2026-06-16T23:42:00+08:00
---

# Round 3 · 20260616-mcp-distribution-out-of-box-usage

Fresh reviewer spawned to accept/reject the amended plan after Round 2.

## Reviewer Output

```yaml
reviewer_id: R3
round: 3
verdict: 阻断需修复
deterministic_check: skipped
deterministic_check_skip_reason: This is a plan document, not code; no test suite applies
blocking_issues:
  - id: 1
    description: |
      `guidance.py` 被定义为“Agent 使用纪律的单一事实源”，职责描述包含导出“doctor 提醒”，但实际实现的 `guidance.py` 仅包含 MCP prompt 定义；`doctor.py` 的 `next_steps`、`model_capability` 警告等提醒文本全部硬编码在 `doctor.py` 中。这破坏了计划宣称的单一事实源架构，导致 prompts、docs、doctor 三处指导可能漂移。
    attribution: plan_defect
    severity: conceptual
    plan_amendment_required: true
    location: 文件结构与职责 (guidance.py 描述) + Task 1 Step 3 + Task 4 Step 3
    design_dimension: pre-check-Q4
  - id: 2
    description: |
      Task 4 要求“保持导入 CLI 不加载 `pyautogui`”，测试也断言调用 `cli.main(["doctor"])` 后 `sys.modules` 中不存在 `pyautogui` 和 `computer_use.core`。但计划没有提供任何重构策略来处理 `cli.py` 可能存在的模块级 `import computer_use.core` / `import pyautogui`。若当前 `cli.py` 在模块顶层导入 `core`，该测试必然失败。
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: Task 4 Step 1、Step 4 与“文件结构与职责”中 cli.py 描述
    design_dimension: DR4
  - id: 3
    description: |
      `doctor.py` 直接对 `load_config()` 返回值做 dict 风格索引 `config[key]`，并硬编码 `("log_dir", "screenshot_dir", "trace_dir", "task_dir")`。计划未验证 `load_config()` 实际返回的是 dict 还是 dataclass/object，也未验证这些 key 是否存在。一旦 config schema 不符，`doctor` 会崩溃。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 4 Step 3 中 `run_doctor()` 实现
    design_dimension: DR2
  - id: 4
    description: |
      Task 3 和 Task 6 多处假设现有代码中的工具名（`get_monitors`、`click`、`batch`、`start_task`、`review_task_session`、`click_by_text` 等）和内部函数名（`_batch_tool`、`_dispatch_tool`、`_failure_for_result`、`_call_tool`）与计划一致，但没有任何前置步骤去核验当前代码库中的实际命名。若存在差异，多个 RED 测试和 `next_action` 注入点将全部失败。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 3 Step 4 + Step 5 + Task 6 Step 1
    design_dimension: DR2
  - id: 5
    description: |
      Task 2 使用 `server.list_prompts()` / `server.get_prompt()` 装饰器，但计划未指定 MCP Python SDK 的最低版本，也未说明旧版 SDK 不支持 prompts 时的回退策略。若当前 `.venv` 中的 SDK 版本过低，`mcp_server.py` 会在注册阶段直接报错。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 2 Step 3 + Step 4
    design_dimension: DR6
  - id: 6
    description: |
      Task 3 要求修改关键工具 `description`，但未要求先审计现有测试是否对这些 `description` 做精确字符串断言。若 `tests/test_mcp_server.py` 中已有断言描述全文的测试，新增 guidance 文本会直接导致既有测试失败。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 3 Step 3
    design_dimension: DR2
  - id: 7
    description: |
      Task 5/7 对 README 的改造假设存在“注册后流程”并被替换为“First run”，且 `test_distribution_readiness.py` 同时检查“First run”和“Generic MCP”。但计划未明确 README 中必须出现“Generic MCP client”字样，也未处理 README 为英文或混合语言时“注册后流程”不存在的情况，测试可能误失败。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 5 Step 2 + Task 7 Step 1（`test_examples_do_not_hardcode_kimi_as_only_client`）
    design_dimension: DR2
suggestion_issues:
  - description: |
      Smoke 脚本导入测试使用 `Path("tools/smoke_mcp_client.py")`，依赖 pytest 从仓库根目录运行。建议改为基于 `__file__` 或项目根标记解析路径，提高可移植性。
    design_dimension: DR6
  - description: |
      Task 5 对 `docs/agent-usage.md`、`docs/deployment.md`、`docs/api.md`、`docs/pitfalls.md`、`skills/computer-use/SKILL.md` 的更新仅给出高层 bullet，建议为每份文档补充必须包含的具体段落或句子清单，避免执行时遗漏关键指导。
    design_dimension: DR2
  - description: |
      可考虑让 `guidance.py` 统一导出 doctor 提醒文本和 `next_steps` 列表，`doctor.py` 仅负责环境探测和组装 JSON，从而真正落实“单一事实源”。
    design_dimension: DR5
antipattern_observations:
  - type: past_commitment_anchoring
    evidence: |
      Task 3 Step 4 直接映射错误注入点到 `_batch_tool`、`_dispatch_tool`、`_failure_for_result`、`_call_tool` 等内部函数，并假设工具名如 `click_by_text`、`open_menu`、`fill_form`、`scroll_until` 存在，但未提供任何验证当前代码库中这些名称是否一致的步骤。
  - type: environment_lock-in
    evidence: |
      `doctor.py` 硬编码 `("log_dir", "screenshot_dir", "trace_dir", "task_dir")` 和 `platform.system() == "Windows"`；`examples/clients/generic-mcp.json` 使用 `\.venv\Scripts\python.exe`。虽然项目目标平台是 Windows，但计划未将这些视为需要与当前代码库核实的环境假设。
  - type: minimum_patch
    evidence: |
      Task 3 Step 3 明确“只修改公开分发关键工具，不重写全量工具表”。这种最小补丁策略虽控制上下文长度，但会留下部分工具缺乏 guidance 的缺口，建议至少补充“哪些工具不修改”的明确边界。
```

## Orchestrator 处理记录

- **[Orchestrator Detection]** Verdict: `阻断需修复`; 7 new blocking issues remain.
- **[Orchestrator Detection]** Type R 等价标注：R3-B1 与 R1/R2 中 "single source of truth" 相关 suggestion 同源但不完全重复；R3-B3 与 R1/R2 中 `config[key]` suggestion 同源。
- **[Orchestrator Detection]** Type O 检测：无历史 accepted fix 被推翻。
- **[Orchestrator Detection]** blocking issue 数量轨迹：R1=8 → R2=4 → R3=7（非单调下降，出现新维度问题）。
- **[Orchestrator Detection]** boundary_check: pass（本轮仅循环管理 + 语义判定）。
- **[Orchestrator Detection]** 关键新维度：Reviewer 指出计划未验证当前代码库实际状态（cli.py imports, tool names, internal function names, SDK version, config return type）。
