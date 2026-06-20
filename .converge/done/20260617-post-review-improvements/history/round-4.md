---
round: 4
reviewer_backend: opencode
reviewer_instance_id: ses_125bf48a1ffe3e6076T3cZ2txf
generated_at: 2026-06-18T18:20:00+08:00
---

# Round 4 · post-review-improvements plan

## Reviewer 完整输出

```yaml
round: 4
verdict: 阻断需修复
deterministic_check: skipped
deterministic_check_skip_reason: 审查对象为 plan 文档，非代码项目
blocking_issues:
  - id: 1
    description: |
      Task 1 的 integration_app fixture 仍同时调用 launcher.launch_app(name) 与 subprocess.Popen([exe])，在 allowed_commands 非空时会真实启动两个记事本进程，且 ManagedApp 只清理后者。Fixture 契约声称 launcher.launch_app 仅用于“验证”，但同一段又说明 launcher.launch_app 会通过 Shell.Application.InvokeVerb("Open") 真实启动应用，二者自相矛盾。R3 issue 3 未真正修复。
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: "Task 1 Step 3 fixture 代码与 Fixture 契约"
    rubric_gap: false
  - id: 2
    description: |
      Task 2 Step 1 测试 test_launch_app_empty_allowed_list_shows_config_hint 在本地 config.yaml 已将 notepad.exe 加入 allowed_commands 时会失败（launcher 返回 launched=True），但测试名称与断言均假设白名单为空。计划未说明如何固定 allowed_commands 状态（如 monkeypatch、测试配置隔离），导致测试不具备确定性。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: "Task 2 Step 1"
    rubric_gap: false
  - id: 3
    description: |
      Task 1 测试使用 json.loads(mcp_server._call_tool(...))，假设 _call_tool 返回 JSON 字符串；Task 3 仅说明 mcp_server.py 保留 _call_tool shim 并“委托给 dispatch.dispatch_tool()”，但未明确 dispatch_tool/_call_tool 的返回类型与序列化责任。若 dispatch_tool 返回 dict 而 shim 未 json.dumps，Task 1 测试将在 Task 3 完成后失败。
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: "Task 1 Step 1 与 Task 3 Step 4 兼容性 shim"
    rubric_gap: false
suggestion_issues:
  - description: |
      Task 5 使用 Move-Item 归档计划文件，未确保 docs/plans/completed/ 目录存在；在目录不存在时命令会失败。
    drift_detected: false
antipattern_observations:
  - round_referenced: 4
    type: over_compromise
    evidence: |
      "fixture 仍调用 launcher.launch_app(name) 做基本验证（确认 launcher 接受该名称），但不依赖它启动进程或获取 PID" 与 "launcher.launch_app 当前通过 Shell.Application.InvokeVerb('Open') 启动应用，无法返回可靠 PID" 同处 Fixture 契约，说明计划对双启副作用做了妥协式解释，未真正消除孤儿进程风险。
  - round_referenced: 4
    type: solution_anchoring
    evidence: |
      即使 R3 已指出 double-start 问题，fixture 仍保留 launcher.launch_app 调用，并以“验证”名义保留该设计，未改为纯 subprocess.Popen 启动。
contract_amendment_required: false
escalated_issues_review:
  - id: R3-1
    status: resolved
    reason: Task 1 fixture 与 Task 2 测试均已移除 json.loads，Fixture 契约明确声明 launcher.launch_app 返回 Python dict。
  - id: R3-2
    status: resolved
    reason: Task 2 测试已改为断言 result["launched"] is False 与 error 字段内容，不再使用不存在的 status 字段。
  - id: R3-3
    status: still_blocking
    reason: fixture 仍调用会真实启动应用的 launcher.launch_app(name)，随后再用 subprocess.Popen 启动一次，且仅清理后者，孤儿进程问题未解决。
  - id: R3-4
    status: resolved
    reason: 计划已删除所有 OCR 相关声明，pitfalls.md 与验收标准均明确项目不提供 OCR 工具。
  - id: R3-suggestion-hardcoded_name
    status: resolved
    reason: Task 2 错误消息已改用 f-string 引用 {name}，不再硬编码 notepad.exe。
  - id: R3-suggestion-pytest_timeout
    status: resolved
    reason: Task 1 已注明 pytest-timeout 依赖并要求安装或在 pytest.ini 注册 timeout marker。
  - id: R3-suggestion-create_modify
    status: resolved
    reason: 文件结构清单中 Create/Modify 标签与正文一致。
  - id: R3-suggestion-test_assertions
    status: resolved
    reason: Task 2 断言与测试描述“empty allowed list shows config hint”一致。
  - id: R3-suggestion-visual_fallback
    status: resolved
    reason: Task 4 pitfalls.md 已新增视觉 fallback 小节，明确由多模态模型读取截图。
```

## Orchestrator 处理记录

- **[Orchestrator Detection]** Type O 检测：无新的 overturn。
- **[Orchestrator Detection]** Type R 等价标注：R4 issue 1 与 R3 issue 3 同源（double-start fixture）。
- **[Orchestrator Detection]** boundary_check: pass。
- **[Orchestrator Detection]** 3 个 blocking issues，全部 attribution = plan_defect，需要 plan amendment。
- **[Orchestrator Detection]** antipatterns: over_compromise, solution_anchoring。
- **[Orchestrator Detection]** 注意：R3 issue 3 仍未 resolved，是本轮核心问题。
