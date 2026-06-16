# Attempts · 20260616-mcp-contract-plan

> Cross-round attempt log. Each entry records one blocking-issue fix applied to
> the PLAN artifact (`docs/plans/active/mcp-contract-and-artifact-diagnostics-evolution.md`).
> Source: converge_loop (Round 1 deliberate → executor amendment).

## Round 1 attempt · issue B1
- source: converge_loop
- reviewer_backend: opencode
- Issue: "Every test snippet in Tasks 2/3/5/6/7 calls `_configure_trace_dir(monkeypatch, tmp_path)`, and Task 6 additionally calls `_stub_uia(monkeypatch)`. Neither helper exists."
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 用真实 fixture/helper 名替换，移除冗余手动 patch。test_mcp_server.py / test_runner.py 已有 autouse `_patch_trace_dir`，相关测试不再手动 patch；test_trace.py 用真实 `tmp_trace_dir` 参数 fixture；test_snapshot.py 用真实 `_fake_tree`(fixture)+`_stub_process_name`(函数)+直接 monkeypatch trace_dir，并补 `save_screenshot`/`get_monitors` stub（与既有 snapshot 测试一致）。
- Diff: Task 2 Step 1/2 各测试加 `import computer_use.mcp_server as server`/`from computer_use.tool_contract import ...`；Task 3 Step 1 删 `_configure_trace_dir`，签名去 `tmp_path`；Task 4 Step 1/2 改用 `tmp_trace_dir` 参数；Task 5 Step 1 改用 `tmp_trace_dir`；Task 6 Step 1 重写为真实 helper + monkeypatch trace_dir，断言改 `screenshots/`；Task 7 Step 1 改经 `_call_tool` 并加 `server` import。
- R1 verdict: Accepted (R2 reviewer escalated 复查 = resolved，附真实代码行号证据)

## Round 1 attempt · issue B2
- source: converge_loop
- reviewer_backend: opencode
- Issue: "`artifact_manifest` returns a FLAT shape … But the response envelope uses a NESTED `artifacts` object … The plan never specifies the manifest→envelope transformation … Task 5 Step 1 asserts flat; Task 7 Step 1 asserts nested."
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: manifest 保持扁平作为唯一 source of truth；响应信封由 `_attach_trace_manifest(data, trace_id)` 在 `_call_tool` 边界从 manifest **派生**。明确字段映射表（`report_path`→`artifacts.report = report_path or None`），让 Task5 Step1（扁平）与 Task7 Step1（嵌套）通过派生关系一致。
- Diff: Task 5 Step 1 标注扁平 source of truth；新增 Step 3 映射表 + envelope 形状；新增 Step 4 写出 `_attach_trace_manifest` helper 实现 + `_call_tool` 接入点（`_MANIFEST_TOOL_NAMES = {batch, run_task_plan, review_task}`）；Task 7 Step 1 改经 `_call_tool` 使 envelope 存在，加 `artifacts.report is None` 与 `trace_path is not None` 断言。
- R1 verdict: Accepted (R2 reviewer escalated 复查 = resolved，附真实代码行号证据)

## Round 1 attempt · issue B3
- source: converge_loop
- reviewer_backend: opencode
- Issue: "The 风险 section mandates a consistency test … No task implements this. Task 2 Step 1 only asserts Schema↔constant, which does NOT catch drift between the constant and the actual `TOOLS` registry."
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 2 Step 1 新增 `test_batch_action_tool_names_match_tools_registry`，双向断言真实 `TOOLS` 注册表与 `BATCH_ACTION_TOOL_NAMES` 一致（`<=` 守 stale 常量，`== registered - excluded` 守新增工具不漏）；excluded = `_ORCHESTRATION_TOOL_NAMES | _DIAGNOSTIC_TOOL_NAMES`。
- Diff: Task 2 Step 1 加入新测试 + 导入 `_DIAGNOSTIC_TOOL_NAMES`/`_ORCHESTRATION_TOOL_NAMES`；Task 1 Step 3 定义这两个 frozenset 常量；Task 2 Step 3 RED 命令 -k 增加 `batch_action_tool_names_match`；风险节与验收标准引用该测试名。
- R1 verdict: Accepted (R2 reviewer escalated 复查 = resolved，附真实代码行号证据)

## Round 1 attempt · issue B4
- source: converge_loop
- reviewer_backend: opencode
- Issue: "Task 2 Step 5 instructs run_task_plan nested rejection to return invalid_tool. This conflicts with live code: `_validate_task_steps` raises ValueError, and test_runner.py:346/363 assert `raises(ValueError)`. Plan neither flags them nor schedules a runner RED test."
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 选定与 batch 一致的结构化 `invalid_tool` 方案（反折中）。runner per-step 规范化用 `TASK_STEP_TOOL_NAMES`，`InvalidToolName` 转 invalid_tool 结果项；保留 missing-tool/step-budget 的 ValueError。明确列出两个需更新的现有测试 + 新增 runner RED 测试，纳入 Task 2 的 RED→impl→GREEN。
- Diff: Task 2 拆出 Step 5（runner RED 测试，含 `test_run_task_plan_normalizes_known_mcp_prefix_step`/`test_run_task_plan_step_unknown_tool_returns_invalid_tool`，并说明 346/363 两测试从 `raises(ValueError)` 改为断言 `invalid_tool`）+ Step 6（impl：`_validate_task_steps` 仅删嵌套拒绝、保留预算计数与 missing-tool ValueError）+ Step 7/8。
- R1 verdict: Accepted (R2 reviewer escalated 复查 = resolved，附真实代码行号证据)

## Round 1 attempt · issue B5
- source: converge_loop
- reviewer_backend: opencode
- Issue: "After Task 6, the per-trace `<trace_id>/snapshots/` directory holds TWO unrelated artifact types: UI-tree JSON AND screenshot PNGs … contradicts the plan's own motivation."
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 按文件类型分流——trace 内 `screenshots/` 只放截图 PNG，`snapshots/` 只放 UI-tree JSON。`get_ui_snapshot(trace_id=...)` 截图落 `artifact_dir(trace_id,"screenshots")`；batch `capture_snapshot` JSON 经 `_save_ui_snapshot` 继续 `snapshots/`。区分"trace 内按类型分目录"与"无 trace 的全局回退 `snapshots/`"两层语义。
- Diff: Task 6 Step 1 断言改 `screenshots/`；Step 2 目录优先级 3 改 `screenshots`；Step 4 注明 capture_snapshot JSON 归 `snapshots/`；状态与问题证据、Architecture、Task 8 Step 2 API、验收标准、风险节统一 snapshots/screenshots 语义措辞。
- R1 verdict: Accepted (R2 reviewer escalated 复查 = resolved，附真实代码行号证据)
