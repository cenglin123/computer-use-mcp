---
round: 1
reviewer_backend: opencode
reviewer_instance_id: ses_13392a5bfffegTtOGrXKcH4eo1
generated_at: 2026-06-16T10:12:00Z
---

# Round 1 · 20260616-mcp-contract-plan

## Reviewer 完整输出

Summary: Verdict **阻断需修复** — the core design (contract module + lazy dirs + manifest) is sound, but 5 blocking defects will mislead executors, mostly from the plan misstating the real test infrastructure and leaving key transformations/behavior-changes under-specified.

```yaml
round: 1
verdict: 阻断需修复
blocking_issues:
  - id: 1
    description: |
      Every test snippet in Tasks 2/3/5/6/7 calls `_configure_trace_dir(monkeypatch, tmp_path)`, and Task 6 additionally calls `_stub_uia(monkeypatch)`. Neither helper exists. The real test modules use different conventions: tests/test_mcp_server.py and tests/test_runner.py use an autouse fixture `_patch_trace_dir` (which already patches trace_dir to tmp_path, making `_configure_trace_dir` both undefined AND redundant); tests/test_trace.py uses a `tmp_trace_dir` fixture; tests/test_snapshot.py has no trace_dir patching and uses `_stub_process_name`/`_fake_tree`, not `_stub_uia`. An executor copy-pasting these snippets hits NameError immediately. This is a systematic factual error about the existing test infrastructure, not a one-off typo.
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 2 Step 1/2, Task 3 Step 1, Task 5 Step 1, Task 6 Step 1, Task 7 Step 1
    rubric_gap: false
  - id: 2
    description: |
      The `artifact_manifest` function (Task 5 Step 2) returns a FLAT shape: {trace_id, artifact_root, trace_path, report_path, screenshots, snapshots}. But the response envelope (Task 5 Step 3, and asserted by Task 7 Step 1) uses a NESTED `artifacts` object with different keys: {trace_id, trace_path, artifact_root, artifacts:{screenshots, snapshots, report}}. Note `report_path` (manifest) vs `report` (envelope). The plan says "实现时复用 artifact_manifest，不要在三个模块分别扫描目录" but never specifies the manifest→envelope transformation (which fields lift to top-level, which nest under `artifacts`, how `report_path` becomes `report`). Task 5 Step 1's manifest test asserts the flat shape; Task 7 Step 1's test asserts the nested shape. An executor cannot satisfy both without guessing the mapping.
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: Task 5 Step 2 vs Task 5 Step 3 vs Task 7 Step 1
    rubric_gap: false
  - id: 3
    description: |
      The 风险与取舍 section explicitly states a hard requirement: "Schema enum 与工具注册表可能漂移。实现时必须由同一常量生成 nested enum，并添加集合一致性测试。" No task implements this consistency test. Task 2 Step 1 only asserts `tool_schema["enum"] == list(BATCH_ACTION_TOOL_NAMES)` (Schema↔constant), which does NOT catch drift between the constant `ATOMIC_AND_COMPOSITE_TOOL_NAMES` and the actual `TOOLS` registry (the real source of truth). Adding a tool to `TOOLS` while forgetting the constant would silently drop it from the batch enum with no test failure — exactly the drift the risk describes. The plan mandates a mitigation it never schedules, leaving acceptance criterion "Schema、运行时规范化和响应 canonical name 一致" (Task 9 Step 5) only partially covered.
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: 风险与取舍 + Task 2 (missing step)
    rubric_gap: false
  - id: 4
    description: |
      Task 2 Step 5 instructs: "在 runner.py 执行每个 step 前使用 TASK_STEP_TOOL_NAMES 调用 normalize_nested_tool_name。run_task_plan 作为 step 必须返回 invalid_tool". This conflicts with the live code and existing tests. Currently `_validate_task_steps` (runner.py:28-51) raises ValueError for nested run_task_plan, and tests/test_runner.py:346 `test_run_task_plan_rejects_nested_run_task_plan` and :363 `test_run_task_plan_rejects_run_task_plan_inside_batch` assert `pytest.raises(ValueError)`. Switching to a structured `invalid_tool` return breaks those tests, but the plan neither flags them nor schedules updates. Additionally Step 5 introduces a runner behavior change with NO corresponding RED test in test_runner.py (Task 2's RED tests only cover batch schema/normalization), violating the task's own RED→impl→GREEN discipline and leaving the runner normalization untested.
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: Task 2 Step 5
    rubric_gap: false
  - id: 5
    description: |
      Naming consistency failure (pre-flight Q5). After Task 6, the per-trace `<trace_id>/snapshots/` directory holds TWO unrelated artifact types: UI-tree JSON dumps (from `_save_ui_snapshot` via batch `capture_snapshot`, mcp_server.py:1151-1159) AND screenshot PNGs (from `get_ui_snapshot(include_screenshot=True)` bound to trace). `artifact_manifest`'s `files("snapshots")` lists both file types in one flat list, so a consumer cannot distinguish a UI-tree snapshot from a screenshot. This directly contradicts the plan's own motivation (状态与问题证据: "`<trace_dir>/snapshots/` 是独立 UI snapshot 的截图目录") which criticizes snapshot-dir ambiguity. The term "snapshots" is used to mean two different things. Fix direction: either split directories (e.g. snapshot JSONs vs snapshot screenshots) or give the manifest separate keys per file type.
    attribution: plan_defect
    severity: conceptual
    plan_amendment_required: true
    location: Task 6 Step 4 + Task 5 Step 2 + 状态与问题证据
    rubric_gap: false
suggestion_issues:
  - description: |
      Task 6 Step 4 changes `_dispatch_tool` to call `snapshot.get_ui_snapshot(scope, include_screenshot, trace_id=trace_id)`. Existing test fakes in tests/test_mcp_server.py:1387 and :1417 have signature `(scope, include_screenshot)` and will raise TypeError on the new `trace_id=` kwarg. Task 6 lists test_mcp_server.py as modified but does not explicitly flag these two existing fakes for signature updates. The executor should update them, but the plan should call it out.
  - description: |
      review.py is listed as Modify in Task 3 and Task 5, but no step concretely describes what changes there. review.py's error_distribution already counts arbitrary error_kind values (no code change needed for "invalid_tool"), and manifest attachment is specified to happen in `_call_tool` via `_attach_trace_manifest`, not in review.py. Either drop review.py from the file lists or specify the actual edit.
  - description: |
      `retry_step` and `review_task` are included in ATOMIC_AND_COMPOSITE_TOOL_NAMES (Task 1 Step 3), making them valid batch actions. These are trace-inspection/diagnostic tools, not GUI actions; allowing them inside a batch action list is questionable and expands the batch contract unnecessarily. Consider excluding them from BATCH_ACTION_TOOL_NAMES.
  - description: |
      `_save_ui_snapshot` (mcp_server.py:1151-1159) manually does `trace_root(trace_id)/"snapshots".mkdir(...)`. After Task 4 introduces `artifact_dir`, this call site should migrate to `artifact_dir(trace_id, "snapshots")` for consistency, but Task 4 only generically says "call sites in mcp_server.py" without enumerating it.
antipattern_observations:
  - type: environment_lock-in
    evidence: |
      Plan uses `.\.venv\Scripts\python.exe -m pytest ...` in every Run block and cites absolute path `C:\Users\chenr\.computer-use\traces\20260615-173349-9lf66b\trace.jsonl` in 状态与问题证据.
    note: |
      Acceptable per AGENTS.md project conventions (Windows project; `.venv\Scripts\python.exe` is the documented venv entry point; the absolute trace path is problem-evidence pointing at a real failed trace, not a hardcoded runtime path). No remediation required — recorded only to show the scan ran.
contract_amendment_required: false
```

## Orchestrator 处理记录

- **[Orchestrator Detection]** verdict = 阻断需修复。5 个 blocking，全部 attribution=plan_defect，全部 plan_amendment_required=true。归因分布：4×plan_defect(structural/implementation)，1×plan_defect(conceptual)。4 个 suggestion（非阻断）。
- **[Orchestrator Detection]** Round 1 无历史 → Type O / Type R / Type F 检测均 N/A。
- **[Orchestrator Detection]** 信息源核对（M-6）：逐条 blocking 的事实前提均基于 reviewer 对实时代码的核对（tool_contract.py 不存在✓、_error_kind_for_result 现状✓、trace_root 预创建✓、_validate_task_steps 与 test_runner.py:346/363✓、_save_ui_snapshot mcp_server.py:1151-1159✓）。无与用户原话/计划矛盾的虚假前提。pass。
- **[Orchestrator Detection]** boundary_check: pass —— 本轮仅 Spawn reviewer + 记录，未直接修改 plan（硬约束 #7 守住）。
- **[Orchestrator Detection]** issue 归类复核：issue 5 标 severity=conceptual（命中前置自检 Q5 命名一致性 + Q4 职责边界——`snapshots/` 目录二义性）。按评议决策路径，conceptual 阻断倾向"升级完整收敛"；但 Orchestrator 语义判定：该 issue 的修复方向（拆分目录 / manifest 分键）reviewer 已明确给出，属可在 plan 修订中单轮解决的设计决策，不构成计划方向性缺陷。计划核心设计（contract module + lazy dirs + manifest）被 reviewer 判定为 sound。→ 见"Orchestrator 处置建议"，提交用户拍板。
