---
round: 3
reviewer_backend: opencode
reviewer_instance_id: ses_125d04016ffeaZzpiQ4Pp1FziS
generated_at: 2026-06-18T18:10:00+08:00
---

# Round 3 · post-review-improvements plan

## Reviewer 完整输出

```yaml
round: 3
verdict: 阻断需修复
deterministic_check: skipped
deterministic_check_skip_reason: 审查对象为 plan 文档，非代码项目
blocking_issues:
  - id: 1
    description: |
      Task 1 与 Task 2 均假设 `launcher.launch_app()` 返回 JSON 字符串并使用 `json.loads()` 解析，但当前 `computer_use/launcher.py:108` 的返回类型是 Python `dict`。这会导致 Task 1 fixture（Step 3）和 Task 2 新增测试（Step 1）直接失败。Plan 要么需要把 launcher 改为返回 JSON 字符串并同步更新 `tests/test_launcher.py` 中所有基于 dict 的断言，要么应移除 Task 1/2 中的 `json.loads`。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 1 Step 3 fixture; Task 2 Step 1 test
    rubric_gap: false
  - id: 2
    description: |
      Task 2 测试断言 `result["status"] == "blocked"`，但当前 launcher 返回的是 `{"launched": False, "error": ...}`，没有 `status` 字段。Plan 未明确说明要修改 `launch_app` 的返回结构（从 `launched` 改为 `status`），也未给出既有测试/调用方需同步修改的清单。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 2 Step 1 test; Task 2 Step 3 error message
    rubric_gap: false
  - id: 3
    description: |
      Task 1 fixture 先调用 `launcher.launch_app(name)`（通过 `Shell.Application.InvokeVerb("Open")` 启动应用），在返回结果不含 `pid` 时又通过 `subprocess.Popen([exe])` 再次启动同一应用，且只清理后者。这会造成真实 GUI 测试产生孤儿进程，与「Fixture 契约」中「回退到 subprocess.Popen」的语义相矛盾。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 1 Step 3 fixture code; Task 1 Step 3 Fixture 契约
    rubric_gap: false
  - id: 4
    description: |
      Task 4 在 `docs/deployment.md`、`docs/pitfalls.md`、CHANGELOG 和验收标准中均将 OCR 描述为「项目已集成的可选能力」，但 AGENTS.md/CLAUDE.md/GEMINI.md 明确写明「无 OCR」，docs/api.md 写明「不再提供 OCR 工具」，CHANGELOG 也记录了 OCR 工具的移除。按此 plan 执行会产生与项目事实相矛盾的虚假文档。
    attribution: plan_defect
    severity: conceptual
    plan_amendment_required: true
    location: Task 4 Step 1, Step 2, Step 4; 验收标准；风险与取舍
    rubric_gap: true
suggestion_issues:
  - description: |
      Task 2 Step 3 的错误信息把应用名硬编码为 `notepad.exe`，应使用函数参数 `name`。
    drift_detected: false
  - description: |
      Task 1 Step 1 使用 `@pytest.mark.timeout(60)`，但 `requirements.txt` / `pyproject.toml` 未声明 `pytest-timeout`，且 `pytest.ini` 未注册 `timeout` marker。
    drift_detected: false
  - description: |
      文件结构总览把 `tests/integration/test_notepad_smoke.py`、`tests/integration/conftest.py`、`config.example.yaml` 标为 Modify，实际应为 Create（当前不存在）。
    drift_detected: false
  - description: |
      文件结构描述集成测试「UIA 定位编辑区」「验证窗口标题/截图内容」，但 Step 1 代码仅断言 `snap["root"]` 与两次截图路径不同，未定位编辑区、未验证窗口标题、未验证文本是否出现。
    drift_detected: false
  - description: |
      原始评审 P2 建议为「引入视觉 fallback 和 OCR」，Plan 对 OCR 的处理已偏离事实，且完全未提及 visual fallback 是纳入、排除还是已由模型视觉覆盖。
    drift_detected: false
antipattern_observations:
  - round_referenced: 3
    type: solution_anchoring
    evidence: |
      Round 2 把 Task 1 fixture 改为与 Task 2 测试一致地使用 `json.loads(launcher.launch_app(...))`，却未验证 `launcher.launch_app` 实际返回类型是 dict；本轮 plan 仍延续该错误假设，并在 Fixture 契约中写明「当前返回 JSON 字符串」。
  - round_referenced: 3
    type: report_hallucination
    evidence: |
      Plan 多处写明「项目集成了可选的 PaddleOCR」「OCR 作为已存在的可选能力」，但项目治理文档与 CHANGELOG 均表明 OCR 工具已被移除。
  - round_referenced: 3
    type: false_generality
    evidence: |
      Fixture 契约将 `launcher.launch_app(name) 当前返回 JSON 字符串`作为全局事实陈述，实际与 `launcher.py:108` 返回 dict 矛盾。
contract_amendment_required: false
escalated_issues_review:
  - id: R2-1
    status: still_blocking
    reason: Task 1/2 虽被统一为都使用 json.loads，但 launcher 实际返回 dict，跨 Task 契约仍不一致且均会失败。
  - id: R2-python_interpreter
    status: resolved
    reason: Task 4 Step 4 已改为 `./.venv/Scripts/python.exe scripts/changelog.py`。
  - id: R2-pytest_ini_missing
    status: resolved
    reason: 文件结构总览与 Task 1 Files 列表均已补充 `Modify: pytest.ini`。
```

## Orchestrator 处理记录

- **[Orchestrator Detection]** Type O 检测：R2 issue 1 的修复方向（统一用 json.loads）被 R3 推翻，标记为 Type O overturn（第 1 次）。
- **[Orchestrator Detection]** Type R 等价标注：R3 issue 1 与 R2 issue 1 同源（launcher 返回值契约）。
- **[Orchestrator Detection]** 发现关键事实错误：plan 对 launcher 返回类型、OCR 现状的假设与代码/治理文档不符。
- **[Orchestrator Detection]** boundary_check: pass。
- **[Orchestrator Detection]** 4 个 blocking issues，全部 attribution = plan_defect，需要 plan amendment。
- **[Orchestrator Detection]** antipatterns: solution_anchoring, report_hallucination, false_generality。
