# Attempt Log · 20260621-task-context-output-budget-hardening

## Round 1 attempt · issue 1+2+3
- source: converge_loop
- reviewer_backend: opencode
- Issue: (1) Plan 不知 `_TASK_CONTEXT_EXCLUDED_TOOLS` 已存在（schemas.py:15），不知 _handle_tool_call 已有 early-exit branch（mcp_server.py:1284-1300），未指定 guard 精确插入点。(2) "顶层可执行工具"未定义。(3) Task 1/2/3 guard 顺序未声明。
- Issue 归因: plan_defect
- plan_amendment_required: true
- Approach: 修订计划——引用已有 _TASK_CONTEXT_EXCLUDED_TOOLS（schemas.py:15）并指定插入点（L1302）；定义 guarded set = 所有非排除工具；新增 Guard 执行顺序节（Task1>_handle_tool_call > Task2>_dispatch_tool > Task3>post-serialize）；拆分 Task 5 为延期；justified 200K 阈值；test 断言绑定 error contracts
- Diff: Task 1 期望行为/step 2、新增 Guard 执行顺序节、Task 2/3/4 注释、Task 5→deferral note、推荐执行顺序
- R1 verdict: Accepted (R2 reviewer 确认 resolved)

## Blind Recheck 1 attempt · issue BR-1
- source: blind_recheck
- reviewer_backend: opencode
- Issue: Task 1 guard 会破坏现有测试 test_standalone_context_register_conflict_does_not_leave_active_task（test_mcp_server.py:357-389）。计划声称 existing tests pass + full pytest passes，但不准确。
- Issue 归因: pending
- plan_amendment_required: true
- Approach: 验收标准注明 test_standalone_context_register_conflict 需传 task_id=owner；新增 step 5 指导修测试；扫描确认无其他受影响测试；Task 3 注明 desktop+5000controls 几乎总超 200K（intended）；修正行号 608-620→606-617
- Diff: 验收标准、新增 step 5、Task 3 注释、行号修正
- Blind verdict: Accepted (pending R3 + attribution 落定)
