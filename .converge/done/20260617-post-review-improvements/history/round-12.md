---
round: 12
reviewer_backend: opencode
reviewer_instance_id: ses_1256b611effeqb6yMVlu3HSC50
generated_at: 2026-06-18T19:50:00+08:00
---

# Round 12 · post-review-improvements plan

## Reviewer 完整输出

```yaml
round: 12
verdict: 需重新设计
deterministic_check: skipped
deterministic_check_skip_reason: 审查对象为 plan 文档，非代码项目
blocking_issues:
  - id: 1
    description: |
      Task 3 对 `_call_tool` 的“薄 shim”定位与实际代码职责严重不符。实际 `mcp_server.py:_call_tool` 负责 trace 生成、异常捕获与分类、timestamp 注入、manifest 附加、task context 注入、trace 记录等生命周期工作；plan 却要求它只调用 `dispatch_tool` 后 `json.dumps`。这些职责既未明确转交给 `_handle_tool_call`，也未说明由新模块承担，按 plan 执行将丢失现有功能或破坏既有测试。
    attribution: plan_defect
    severity: architectural
    plan_amendment_required: true
    location: Task 3 Step 3–Step 4
    rubric_gap: true
  - id: 2
    description: |
      `dispatch_tool(name: str, arguments: dict) -> dict` 的两参数签名无法替代现有 `_dispatch_tool`，后者需要 `cs`、 `trace_id`、 `parent_step_index`、 `task_id`、 `is_standalone` 才能正确调用 `get_ui_snapshot`、 `batch`、 `run_task_plan`、 `retry_step` 等工具。plan 未给出这些上下文参数的传递路径。
    attribution: plan_defect
    severity: architectural
    plan_amendment_required: true
    location: Task 3 Step 3
    rubric_gap: true
  - id: 3
    description: |
      将 `_dispatch_tool`、 `_dispatch_pointer_tool` 迁到 `computer_use/tools/dispatch.py` 时，plan 遗漏了它们依赖的模块级常量与辅助函数，例如 `_NEXT_ACTION_UI_NOT_FOUND`、 `_NEXT_ACTION_FAIL_SAFE`、 `_NEXT_ACTION_COORDINATE_OR_SAFETY`、 `_NEXT_ACTION_INVALID_TOOL`、 `MAX_SLEEP_DURATION`、 `_run_mouse_tool`、 `_current_logical_position`。未迁移清单将导致拆分后模块无法编译。
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: Task 3 Step 3
    rubric_gap: true
  - id: 4
    description: |
      Task 3 拆分后存在循环导入风险：`computer_use/tools/batch.py` 的 `handle_batch` 需要递归调用 `_call_tool` 执行子动作，而 plan 要求 `_call_tool` 留在 `mcp_server.py`。plan 未说明 `batch.py` 如何避免直接导入 `mcp_server`，也未提供依赖注入或注册表方案。
    attribution: plan_defect
    severity: architectural
    plan_amendment_required: true
    location: Task 3 Step 3–Step 4
    rubric_gap: true
  - id: 5
    description: |
      Task 1 集成测试 fixture 使用 `pyautogui.getWindowsWithTitle("Notepad")` 硬编码英文标题，在非英文版 Windows 上无法定位记事本窗口，导致测试不稳定或失败。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 1 Step 3
    rubric_gap: false
  - id: 6
    description: |
      Task 1 集成测试在真实桌面运行时会生成截图文件但不清理；`type` 工具发送真实按键，若窗口激活失败或用户正在操作会把按键发送到错误目标；fixture 清理失败时会遗留记事本进程。plan 未提供截图清理、键盘干扰规避和孤儿进程兜底方案。
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: Task 1 Step 1、Step 3
    rubric_gap: false
suggestion_issues:
  - description: |
      Task 1 集成测试可使用 fixture 级临时 `screenshot_dir`，避免污染用户配置的截图目录，并简化清理逻辑。
    drift_detected: false
  - description: |
      Task 3 建议放弃“`_call_tool` 薄 shim”假设，改为保留 `_call_tool` 的现有生命周期职责，仅把内部 `_dispatch_tool` 重命名为 `dispatch_tool` 并迁入 `tools/dispatch.py`，由 `_call_tool` 传入完整上下文参数。
    drift_detected: false
antipattern_observations:
  - round_referenced: 12
    type: solution_anchoring
    evidence: |
      Task 3 Step 4 兼容性 shim 段落仍要求 “`_call_tool` 作为薄 shim：调用 `computer_use.tools.dispatch.dispatch_tool(name, arguments)` 获得 Python dict/list 结果，使用 `json.dumps` 返回”，与实际 `_call_tool` 承担 trace、异常、timestamp、manifest、task context 注入等职责的事实相矛盾。
  - round_referenced: 12
    type: over_compromise
    evidence: |
      多轮 amended 后，plan 通过增加 adapter 层、wrapper 层、shim 层等局部补丁来回避核心矛盾，但始终未重新设计 `_call_tool` / `_handle_tool_call` / `dispatch_tool` 之间的真实职责边界。
contract_amendment_required: false
escalated_issues_review:
  - id: BR2-1
    status: still_blocking
    final_attribution: plan_defect
    reason: Plan 将 `_call_tool` 描述为薄 shim，但实际代码中它承担 trace、异常、timestamp、manifest、task context 等生命周期职责，plan 未重新分配这些职责。
  - id: BR2-2
    status: still_blocking
    final_attribution: plan_defect
    reason: `dispatch_tool` 两参数签名无法替代需要 `cs`、trace 上下文、task 上下文等参数的 `_dispatch_tool`。
  - id: BR2-3
    status: still_blocking
    final_attribution: plan_defect
    reason: Plan 未列出 `_dispatch_tool` / `_dispatch_pointer_tool` 依赖的常量与辅助函数迁移清单，拆分后模块将缺少必要依赖。
  - id: BR2-4
    status: still_blocking
    final_attribution: plan_defect
    reason: Fixture 硬编码英文标题 “Notepad”，在非英文 Windows 上无法匹配本地化窗口标题。
  - id: BR2-5
    status: still_blocking
    final_attribution: plan_defect
    reason: Plan 未规定截图清理、真实按键干扰规避及孤儿进程兜底，集成测试在真实桌面存在副作用风险。
```

## Orchestrator 处理记录

- **[Orchestrator Detection]** Round 12 verdict = 需重新设计（strongest signal）。
- **[Orchestrator Detection]** 所有 BR2 issues confirmed as still_blocking, attribution = plan_defect.
- **[Orchestrator Detection]** 关键决策：Task 3 必须大幅收缩 scope，从“拆分 dispatch/batch/composite”改为“仅提取静态 TOOLS schema 到独立模块”。
- **[Orchestrator Detection]** Task 1 需要增强 fixture 的跨语言匹配、截图清理、副作用提示。
