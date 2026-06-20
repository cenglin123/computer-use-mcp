---
round: 10
reviewer_backend: opencode
reviewer_instance_id: ses_125813248ffezFSaTlwWizPooU
generated_at: 2026-06-18T19:25:00+08:00
---

# Round 10 · post-review-improvements plan

## Reviewer 完整输出

```yaml
round: 10
verdict: 阻断需修复
deterministic_check: skipped
deterministic_check_skip_reason: 审查对象为 plan 文档，非代码项目
blocking_issues:
  - id: 1
    description: |
      Task 1 的集成测试 fixture 仍使用 `time.sleep(1)` 等待窗口，并默认 `subprocess.Popen` 启动的 Notepad 会自动成为前台窗口；该假设在真实 Windows 桌面环境中不可靠，且测试在调用 `type` 前未显式激活目标窗口，容易导致按键发送到错误窗口或丢失。
    attribution: plan_defect
    severity: implementation
    plan_amendment_required: true
    location: Task 1 Step 1 与 Step 3
    rubric_gap: true
  - id: 2
    description: |
      Task 2 的测试数据硬编码 Windows 环境路径（`C:\ProgramData\...\Start Menu\...\Notepad.lnk`、`C:\Windows\System32\notepad.exe`）。虽然通过 monkeypatch 避免真实文件系统依赖，但仍违反数据纯度原则，且在不同环境或系统路径变化时会造成误导。
    attribution: plan_defect
    severity: structural
    plan_amendment_required: true
    location: Task 2 Step 1
    rubric_gap: false
suggestion_issues:
  - description: |
      Task 1 fixture 预先声明了 calc、mspaint 映射但测试仅使用 notepad，建议仅保留实际使用的映射或补充对应 smoke 测试，避免 false generality。
    drift_detected: false
  - description: |
      Task 2 测试通过 monkeypatch 私有函数 `_allowed_commands` 的形状来固定白名单，建议在测试隔离说明中显式记录已确认该函数为可调用对象，或改用更稳定的 `safety.is_allowed_command` monkeypatch。
    drift_detected: false
antipattern_observations:
  - round_referenced: 10
    type: environment_lock-in
    evidence: |
      Task 2 Step 1 测试代码中硬编码 `"C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Notepad.lnk"` 与 `r"C:\\Windows\\System32\\notepad.exe"` 作为 monkeypatch 返回值。
contract_amendment_required: false
escalated_issues_review:
  - id: BR-1
    status: resolved
    final_attribution: plan_defect
    reason: 计划已在范围、验收标准、风险与取舍及 pitfalls.md 中明确排除混合 DPI 支持，提供临时缓解措施（统一缩放比例）并声明需后续单独立项。
  - id: BR-2
    status: still_blocking
    final_attribution: plan_defect
    reason: Task 1 fixture 仍依赖 time.sleep(1) 与 Notepad 自动置前的不可靠假设，需改为显式等待/激活窗口的稳健设计。
  - id: BR-3
    status: still_blocking
    final_attribution: plan_defect
    reason: Task 2 测试数据硬编码真实 Windows 路径，违反数据纯度原则，应替换为与实现无关的占位路径。
  - id: BR-4
    status: resolved
    final_attribution: plan_defect
    reason: 实际代码中 `safety._allowed_commands` 确为返回 list 的可调用对象，monkeypatch 替换为 lambda: [] 可生效；但 plan 未显式记录该验证，建议在测试隔离说明中补一句确认。
```

## Orchestrator 处理记录

- **[Orchestrator Detection]** BR-1 resolved, BR-4 resolved. BR-2 and BR-3 still blocking.
- **[Orchestrator Detection]** 2 new blocking issues (same as BR-2/BR-3) + 2 suggestions.
- **[Orchestrator Detection]** boundary_check: pass.
