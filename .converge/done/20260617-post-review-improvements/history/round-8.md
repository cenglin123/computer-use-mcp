---
round: 8
reviewer_backend: opencode
reviewer_instance_id: ses_1259be7b5ffeNrK1eB4UDGCtSG
generated_at: 2026-06-18T19:00:00+08:00
---

# Round 8 · post-review-improvements plan

## Reviewer 完整输出

```yaml
round: 8
verdict: 阻断需修复
deterministic_check: skipped
deterministic_check_skip_reason: 审查对象为 plan 文档，非代码项目
blocking_issues:
  - id: 1
    description: |
      Task 3 计划将 `_batch_tool`、`_handle_tool_call` 迁出 `mcp_server.py`，但现有 `tests/test_mcp_server.py` 大量测试直接调用 `server._batch_tool` 与 `server._handle_tool_call`；plan 既未在 `mcp_server.py` 保留兼容 shim，也未要求更新这些测试，按字面执行会导致 pytest 失败。此外 `computer_use/tools/__init__.py` 导入 `handle_batch`，而 Step 3 只要求 batch.py 迁移 `_batch_tool`，存在命名不匹配。
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: Task 3 Step 3、Step 4 与 tests/test_mcp_server.py
    rubric_gap: false
  - id: 2
    description: |
      Task 3 计划新建 `computer_use/tools/composite.py` 并迁移 composite 工具，但项目中已存在 `computer_use/composite.py` 且由 `tests/test_composite.py` 直接依赖。plan 未说明新模块仅作 MCP 包装层调用既有 `computer_use.composite`，还是将原实现整体迁移，会导致重复实现或破坏现有测试。
    attribution: plan_defect
    severity: architectural
    plan_amendment_required: true
    location: Task 3 Step 3 与 computer_use/composite.py
    rubric_gap: false
  - id: 3
    description: |
      Task 2 Step 1 的测试直接调用 `launcher.launch_app("notepad.exe")` 且仅 monkeypatch `safety._allowed_commands`，未像 `tests/test_launcher.py` 现有测试那样 mock Shell/WScript；`launch_app` 按 shortcut 名称匹配，"notepad.exe" 不是典型快捷方式名，测试大概率因 "No application named 'notepad.exe' found" 失败，无法命中 allowed_commands 为空的分支。应补全 fixture/mock 并使用 shortcut 名称。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 2 Step 1
    rubric_gap: false
suggestion_issues:
  - description: |
      Task 5 Step 1 的 "全量回归" 使用 `pytest tests/ -v` 未排除 integration 测试，与 Task 1 Step 5 的 CI 跳过命令及验收标准 `pytest tests/ -m "not integration"` 不一致；建议在默认回归命令中加入 `-m "not integration"`，并单独说明在真实 Windows 桌面再跑 integration 测试。
    drift_detected: false
  - description: |
      Task 2 Step 3 只给出一个失败分支的 inline 错误消息，但 `launcher.py` 中两处返回都使用 `_BLOCKED_ERROR` 常量；建议统一修改 `_BLOCKED_ERROR` 或两个返回点，避免错误提示不一致。
    drift_detected: false
antipattern_observations: []
contract_amendment_required: false
escalated_issues_review:
  - id: R7-1
    status: resolved
    reason: 已改为 `assert snap["controls"]`，与 `get_ui_snapshot` 实际返回结构一致。
  - id: R7-2
    status: resolved
    reason: 已将 monkeypatch 目标改为 `safety._allowed_commands`，对应实际配置读取函数。
```

## Orchestrator 处理记录

- **[Orchestrator Detection]** Type O 检测：无新的 overturn。
- **[Orchestrator Detection]** Type R 等价标注：无新的同源 issue。
- **[Orchestrator Detection]** boundary_check: pass。
- **[Orchestrator Detection]** 3 个 blocking issues（structural, architectural, implementation），全部 plan_defect，需要 plan amendment。
- **[Orchestrator Detection]** 已远超默认 max_outer_loops=5。
