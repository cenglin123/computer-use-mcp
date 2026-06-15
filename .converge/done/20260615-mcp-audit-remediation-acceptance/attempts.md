# Attempts · 20260615-mcp-audit-remediation-acceptance

## Round 1 attempt · issue 1
- source: converge_loop
- reviewer_backend: codex
- Issue: Timeout 报告语义自相矛盾：trace 已记录 error_kind=timeout，但报告结果列仍输出 ok。现有测试仅断言报告包含 timeout，未验证结果列不能标记成功，违反计划要求的返回值、trace、report、review 一致标记失败。
- Issue 归因（reviewer 判定）: executor_limit
- plan_amendment_required: false
- Approach: 让 report 优先依据 error_kind 将结果列标记为失败，并补充 timeout、fail-safe 与显式 trace_id 的回归断言。
- Diff: 修改 computer_use/trace.py、tests/test_trace.py、tests/test_runner.py、tests/test_mcp_server.py；独立复跑完整测试 227 passed, 1 skipped。
- R1 verdict: Accepted

## Round 2 attempt · issue R2-1
- source: converge_loop
- reviewer_backend: codex
- Issue: Password input is not allowed as required. The plan declares it an allowed product feature, but the type path passes is_password into check_target_window, which raises SafetyError for password controls. No password-control regression test exists. This also fails design preflight Q1 because the stated boundary and implementation contradict each other; Q2-Q5 revealed no additional blockers.
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 先修订计划，增加 safety 与 MCP 密码输入 RED 测试，移除密码状态阻断，同时保留敏感进程/类名与危险文本检查，并更新已有 bugfix 文档。
- Diff: 修改 docs/plans/completed/mcp-audit-remediation.md、computer_use/safety.py、tests/test_safety.py、tests/test_mcp_server.py、docs/problems/bugfix/input-screenshot-safety.md；独立复跑完整测试 231 passed, 1 skipped。
- R2 verdict: Accepted

## Blind recheck attempt · issue BR-1
- source: blind_recheck
- reviewer_backend: codex
- Issue: validate_coordinate 明确允许副屏坐标，违反“仅主屏/非负坐标”边界。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: false
- Approach: 等待 Round 3 主循环 Reviewer 独立验证并落定归因。
- Diff: 无
- R3 verdict: Accepted
- **[Orchestrator Detection at R3]** Pending attribution resolved to: plan_defect
  - R3 原话（引用）: "输入坐标路线允许副屏操作，违反用户确认的仅主屏、非负坐标边界。"
  - Orchestrator 判定理由: 用户边界与当前实现/测试直接矛盾，且计划遗漏纠正任务。

## Round 3 attempt · issue BR-1
- source: converge_loop
- reviewer_backend: codex
- Issue: 输入坐标路线允许副屏操作，违反用户确认的仅主屏、非负坐标边界。计划必须补充主屏专属校验及 MCP、CLI、composite、UIA 坐标路线的回归要求，同时明确截图多显示器支持不受影响。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 先修订计划，将感知与输入坐标边界分离；集中收紧 safety 输入校验，并覆盖 MCP、CLI、composite、snapshot、target_name/UIA 与当前光标路线。
- Diff: 修改 safety/MCP/CLI、相关测试及 API/bugfix/plan 文档；未修改 core.py；独立复跑完整测试 242 passed, 1 skipped。
- R3 verdict: Accepted

## Round 3 inner-loop attempt · issue BR-2
- source: converge_loop
- reviewer_backend: codex
- Issue: 验证段仍保留“实现前失败、实现后通过”的实施过程历史，不符合只陈述当前结果的文档要求。
- Issue 归因（reviewer 判定）: executor_limit
- plan_amendment_required: false
- Approach: 仅清理 bugfix 文档验证段，保留当前完整测试命令、最终结果和跳过项说明。
- Diff: 仅更新 docs/problems/bugfix/input-screenshot-safety.md；过程考古关键词检索无命中。
- R3 verdict: Accepted

## Blind recheck 2 candidates
- source: blind_recheck
- reviewer_backend: codex
- Issues: core 底层副屏坐标、drag 起点目标、click_by_uid 真实目标复核、截图十字标记范围、计划文档过程考古。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: pending
- Approach: 注入 Round 4，由新 Reviewer 独立复现、做范围裁决并落定归因。
- Diff: 无
- R4 verdict: Pending

## Round 4 confirmed blockers
- source: converge_loop
- reviewer_backend: codex
- Issues: R4-1 core 最终输入原语缺少不可绕过的主屏边界；R4-2 drag 起点未检查；R4-3 snapshot 点击未实时复核目标；R4-5 计划文档存在提前终审结论和 Round 考古。
- Issue 归因（reviewer 判定）: R4-1/R4-5 plan_defect；R4-2/R4-3 executor_limit。
- plan_amendment_required: R4-1/R4-5 true；R4-2/R4-3 false。
- Approach: Executor 必须先修订计划，随后按 TDD 修复；保留用户既有 core.py 截图十字标记。
- Diff: 修订计划；core 最终输入原语增加主屏边界；drag 检查起终点；snapshot 按坐标实时检查；更新相关测试和稳定文档。
- R4 verdict: Accepted

## Blind recheck 3 candidates
- source: blind_recheck
- reviewer_backend: codex
- Issues: core 正向测试依赖真实光标位置；CURRENT 保留当前 Converge 过程状态。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: pending
- Approach: 注入 Round 5，由新 Reviewer 独立复现并区分实现 blocker 与完工状态清理。
- Diff: 无
- R5 verdict: Pending

## Round 5 confirmed blocker
- source: converge_loop
- reviewer_backend: codex
- Issue: 4 个 core 正向测试未隔离真实光标位置，在副屏光标环境使完整测试失败。
- Issue 归因（reviewer 判定）: executor_limit
- plan_amendment_required: false
- Approach: 仅修改 tests/test_core.py，mock 主屏光标并隔离坐标系统，不绕过安全 helper。
- Diff: 仅修改 tests/test_core.py，mock 主屏拓扑和光标位置，不绕过待测安全 helper。
- R5 verdict: Accepted

## Blind recheck attempt · issue BR-2
- source: blind_recheck
- reviewer_backend: codex
- Issue: 包含“计划最初没有要求”等修复历史考古措辞。
- Issue 归因（reviewer 判定）: pending
- plan_amendment_required: false
- Approach: 等待 Round 3 主循环 Reviewer 独立验证并落定归因。
- Diff: 无
- R3 verdict: Pending
- **[Orchestrator Detection at R3]** Pending attribution resolved to: executor_limit
  - R3 原话（引用）: "缺陷文档残留计划演化考古措辞，应改为仅描述当前根因。"
  - Orchestrator 判定理由: 计划无需变更，仅需删除产物中的历史措辞。

## Round 3 attempt · issue BR-2
- source: converge_loop
- reviewer_backend: codex
- Issue: 缺陷文档残留计划演化考古措辞，应改为仅描述当前根因。
- Issue 归因（reviewer 判定）: executor_limit
- plan_amendment_required: false
- Approach: 删除计划演化措辞，将原因改写为当前代码边界与产品边界不一致。
- Diff: 更新 docs/problems/bugfix/input-screenshot-safety.md；完整测试 242 passed, 1 skipped。
- R3 verdict: Pending
