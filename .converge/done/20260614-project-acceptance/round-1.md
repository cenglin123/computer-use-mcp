# Round 1 · 20260614-project-acceptance

---
round: 1
reviewer_backend: opencode
generated_at: 2026-06-14T12:00:00+08:00
---

## Reviewer 1 完整输出

```yaml
reviewer: 1
verdict: 阻断需修复
deterministic_check: pass
blocking_issues:
  - id: 1
    description: |
      run_task_plan 默认开启 capture_screenshots，实现中每步先调用 _step_screenshot -> _call_tool("screenshot") 记录一条 trace，再调用 _call_tool(tool_name) 记录同一步骤的实际工具记录；两条记录使用相同的 step_index。这导致 retry_step(step_index=N) 会命中先写入的 screenshot 记录，从而“重试截图”而非重试用户预期的实际步骤；同时 review_task 的总步数、耗时统计也会把截图重复计数，破坏了 trace schema 的 step_index 语义。
    severity: architectural
    location: computer_use/runner.py:22-38,68-97; computer_use/mcp_server.py:592-650
suggestion_issues:
  - description: |
      Trace 记录未充分利用 screenshot_path / ui_snapshot_path 字段：get_ui_snapshot、batch 的 capture_snapshot、run_task_plan 的 final_state 产生的截图/快照路径只出现在响应或单独文件中，未写入对应 trace 记录的 screenshot_path / ui_snapshot_path，与 schema 定义不一致。
    location: computer_use/mcp_server.py:1026-1122; computer_use/runner.py:103-113; computer_use/snapshot.py:163-260
  - description: |
      runner.py 从 mcp_server.py 导入 _call_tool 与 _save_ui_snapshot，导致任务执行层反向依赖工具分发层；长期应将通用调用入口与快照持久化下沉到独立模块，避免循环引用风险并厘清边界。
    location: computer_use/runner.py:17-18
  - description: |
      composite.click_by_uid 是对 snapshot.click_by_uid 的薄包装，但 mcp_server.py 已直接调用 snapshot 版本，该 wrapper 当前未被使用；可移除或统一入口以减少冗余。
    location: computer_use/composite.py:36-49
  - description: |
      计划 Phase 3 要求更新部署文档与示例，但 docs/deployment.md 未按预期更新以反映 trace_dir、review_task、retry_step 等新增能力的配置与使用。
    location: docs/deployment.md
antipattern_observations: []
highlights:
  - finding: |
      默认参数下 run_task_plan + retry_step 会“重试截图”而非“重试原步骤”，是 acceptance 前必须修复的核心缺陷。
    why_it_it_matters: |
      破坏 trace 契约与复盘/重放能力，使默认参数产生的 task trace 不可信。
    suggested_direction: |
      将 _step_screenshot 改为不经过 _call_tool 的纯截图调用，把 screenshot_path 写入同一步骤的 trace 记录；避免为截图生成独立 trace 条目，确保 step_index 在单次 trace 内语义唯一。
```

## Reviewer 2 完整输出

```yaml
reviewer: 2
verdict: 阻断需修复
deterministic_check: pass
blocking_issues:
  - id: 1
    description: |
      Composite UID/text/menu/form tools bypass safety.py coordinate and target-window checks.
      snapshot.click_by_uid and composite.click_by_text/open_menu/fill_form call core.click directly
      without validate_coordinate or check_target_window, violating the invariant that every mouse
      action is guarded by safety.py. They also pass sensitive_check=False to find_control and then
      omit the explicit check_target_window that atomic click/move tools perform.
    severity: architectural
    location: computer_use/snapshot.py:279; computer_use/composite.py:83,139,197
  - id: 2
    description: |
      Structured composite errors (ui_not_found, stale_uid) do not set trace error_kind.
      _call_tool only derives error_kind from exceptions, so when click_by_uid/click_by_text/
      open_menu/fill_form/scroll_until return {"error": "..."} dicts, the trace record has
      error_kind=null. review_task counts failures exclusively by error_kind, so these errors
      disappear from review summaries and break the trace/review pipeline.
    severity: structural
    location: computer_use/mcp_server.py:629-633; computer_use/composite.py; computer_use/snapshot.py
  - id: 3
    description: |
      run_task_plan emits duplicate step_index values when capture_screenshots=True (default).
      _step_screenshot records a "screenshot" record with step_index N, then the actual tool call
      records another record with the same step_index N. retry_step picks original_records[0],
      which is the screenshot record, so retrying a run_task_plan step replays screenshot instead
      of the intended action.
    severity: structural
    location: computer_use/runner.py:73-83
suggestion_issues:
  - description: |
      batch final screenshot monitor default mismatch: TOOLS schema declares default 1, but
      _batch_tool uses args.get("screenshot_monitor", 0), so omitted value captures the entire
      virtual desktop instead of the primary monitor.
    location: computer_use/mcp_server.py:1031 vs mcp_server.py:581
  - description: |
      retry_step mode=from_step continues regardless of intermediate failures and filters out
      batch records, which may surprise users replaying plans that contained nested batches.
    location: computer_use/runner.py:192-220
  - description: |
      review_task always returns goal=None because the goal is not persisted in trace records;
      report.md has it, but the deterministic summary cannot report the original task goal.
    location: computer_use/review.py:64
  - description: |
      Circular import: runner.py imports _call_tool and _save_ui_snapshot from mcp_server.py,
      while mcp_server.py imports runner.py. Consider extracting shared dispatch/snapshot helpers
      to a lower-level module.
    location: computer_use/runner.py:18; computer_use/mcp_server.py:988
antipattern_observations:
  - description: |
      Tests for composite tools exercise functions in isolation and do not verify trace error_kind
      or safety-path integration, leaving the full MCP-call path uncovered.
    location: tests/test_composite.py, tests/test_runner.py
  - description: |
      Module-level import of core.click in composite.py is monkeypatched in tests; this works but
      is fragile and hides real dependency wiring.
    location: tests/test_composite.py
highlights:
  - finding: |
      Composite tools bypass safety.py checks entirely, creating a real risk of clicking outside
      allowed windows or screen bounds.
    why_it_matters: |
      The project hard-constraint states that any change to computer_use/core.py-controlled input
      must go through safety.py coordinate and target-window checks. Composite tools are shipped
      as MCP tools but do not call validate_coordinate or check_target_window, so they can click
      sensitive/disallowed windows or off-screen coordinates.
    suggested_direction: |
      Route composite clicks through the same _run_mouse_tool or a shared helper that calls
      find_control, validate_coordinate, and check_target_window before invoking core.click.
  - finding: |
      The trace schema's error_kind field is not populated for the structured errors the plan
      itself defines (ui_not_found, stale_uid), so review_task silently under-reports failures.
    why_it_matters: |
      The whole point of structured trace is to classify errors for post-hoc analysis. If composite
      tools return errors in result dicts but leave error_kind null, review_task, report.md, and
      future experience mining will miss them.
    suggested_direction: |
      Make _call_tool inspect result.get("error") and map known error strings to error_kind, or
      have composite tools raise typed exceptions that _call_tool maps consistently.
```

## Reviewer 3 完整输出

```yaml
reviewer: 3
verdict: 阻断需修复
deterministic_check: pass
blocking_issues:
  - id: 1
    description: |
      Composite tools (click_by_text, open_menu, fill_form, scroll_until) return structured
      {"error": "ui_not_found"} results, but _call_tool only sets error_kind when an exception
      is raised. Consequently ui_not_found / stale_uid / timeout errors are never written to
      trace.jsonl's error_kind field, even though the plan and api.md explicitly require these
      values. review_task relies on error_kind to count failures, so composite failures are
      under-reported and the trace schema contract is broken.
    severity: structural
    location: computer_use/mcp_server.py:629-648; computer_use/composite.py; docs/api.md:146
  - id: 2
    description: |
      Composite tools call computer_use.core.click directly after find_control(..., sensitive_check=False),
      bypassing check_target_window. The plan states "命中时执行 click(target_name=text)，因此 safety
      检查复用现有路径", but the implementation never invokes check_target_window, allowing clicks on
      sensitive processes/classes that the atomic click tool would block.
    severity: implementation
    location: computer_use/composite.py:83,139,197; computer_use/mcp_server.py:1125-1248
  - id: 3
    description: |
      Trace step_index collisions occur when run_task_plan executes a batch step: the batch parent
      record uses step_index N from run_task_plan, and batch sub-steps also use step_index 1,2,3...
      inside the batch. The plan says batch sub-steps should use their own index, but the resulting
      duplicate step_index values within the same trace_id break trace uniqueness and confuse
      retry_step, which filters records by step_index.
    severity: architectural
    location: computer_use/runner.py:79-83; computer_use/mcp_server.py:1026-1122
suggestion_issues:
  - description: |
      Tool schema for batch declares screenshot_monitor default=1, but _batch_tool uses
      args.get("screenshot_monitor", 0). Clients omitting the parameter receive the entire
      virtual desktop instead of the primary monitor.
    location: computer_use/mcp_server.py:580-584,1031
  - description: |
      review_task always returns goal=None because the goal is never persisted in trace.jsonl
      (only in report.md). The plan and api.md state that review_task output includes the task
      goal.
    location: computer_use/review.py:64; docs/api.md:139
  - description: |
      run_task_plan's capture_screenshots creates a separate "screenshot" trace record with the
      same step_index as the actual step, producing duplicate step_index entries and leaving the
      step record without a screenshot_path. Consider attaching screenshot_path directly to the
      step record.
    location: computer_use/runner.py:75-97
  - description: |
      final_state_path returned by run_task_plan is not included in report.md, although the plan
      says "结果路径写入 report.md".
    location: computer_use/trace.py:138-205; computer_use/runner.py:103-125
  - description: |
      click_by_uid and run_task_plan may serialize the full snapshot dict into trace args,
      inflating trace.jsonl size significantly.
    location: computer_use/mcp_server.py:640
antipattern_observations:
  - composite.py raises ValueError for empty path/fields, which _call_tool converts to a generic
    {"error_kind": "unknown"} trace record instead of a structured validation response.
highlights:
  - finding: |
      The trace system is wired end-to-end, but the error taxonomy is hollow: composite failures
      populate result.error while error_kind stays null, so review_task cannot accurately summarize
      task health.
    why_it_matters: |
      Error classification is a central goal of Phase 3 ("错误恢复与经验沉淀"). Without it, traces
      cannot drive retry decisions or error-pattern analysis, and the review_task tool returns
      misleading success counts.
    suggested_direction: |
      Have _call_tool inspect returned dicts for known error keys and map them to error_kind
      (ui_not_found, stale_uid, timeout, fail_safe), and route composite clicks through the same
      check_target_window path used by atomic click/move_to.
```

## Orchestrator 处理记录

- **[Orchestrator Detection]** 3 reviewers unanimous on 2 critical blocking themes: run_task_plan duplicate step_index (retry screenshots) and composite errors not setting error_kind.
- **[Orchestrator Detection]** 2 reviewers also flag safety bypass in composite tools (click_by_text/open_menu/fill_form).
- **[Orchestrator Detection]** Minor suggestions: batch final_screenshot monitor default mismatch, review.goal persistence, final_state_path in report.md.
- **[Orchestrator Detection]** boundary_check: pass.
