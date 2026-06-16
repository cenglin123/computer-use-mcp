---
round: blind-recheck
reviewer_backend: opencode
generated_at: 2026-06-17T00:08:00+08:00
---

# Blind Recheck · 20260616-mcp-distribution-out-of-box-usage

Blind reviewer spawned without access to attempts.md / round logs.

## Blind Reviewer Output

```yaml
reviewer_id: blind
round: blind-recheck
verdict: 阻断需修复
blocking_issues:
  - id: 1
    description: |
      Q3 数据纯度/架构完整性：计划将多项目前代码状态结论（“当前代码已声明 mcp>=1.0.0”、“本轮审计结果：名称一致，可直接使用”）直接内嵌为事实，但未对 doctor 的懒加载链进行关键审计。`computer_use/doctor.py` 顶层导入 `from computer_use.config import load_config`，而计划只审计 `cli.py` 的顶层导入，完全未审计 `config.py` 和 `computer_use/__init__.py` 是否在模块级加载 `pyautogui` / `computer_use.core`。若这些文件任一顶层的副作用导入存在，`test_doctor_module_import_does_not_load_pyautogui_or_core` 会在 Step 2 直接失败，且 doctor 命令的“不触发真实输入设备”承诺被破坏。必须在 Task 4 Step 0 增加对 `config.py` 与 `__init__.py` 的 import-chain 审计。
    attribution: pending
    severity: architectural
    plan_amendment_required: true
    location: "Task 4 Step 0; computer_use/doctor.py 实现"
    design_dimension: pre-check-Q3
  - id: 2
    description: |
      DR2 完整性 / DR4 边界清晰：doctor 直接调用 `config = load_config()` 且未做 try/except。若配置文件缺失、格式损坏或 `load_config` 本身抛出任何异常，`python -m computer_use doctor` 会崩溃并返回 traceback，而非输出 JSON 诊断结果。这与验收标准中“`python -m computer_use doctor` 可运行，输出 JSON”直接冲突。应在 `run_doctor()` 开头将配置加载失败捕获为一条 failed check，再进入后续目录检查。
    attribution: pending
    severity: implementation
    plan_amendment_required: true
    location: "Task 4 Step 3: computer_use/doctor.py 实现"
    design_dimension: DR2
  - id: 3
    description: |
      DR1 一致性：Task 2 Step 0 要求“确认 mcp>=1.0.0，若低于则先升级”，但 Step 4 实现却用 `try/except AttributeError` 静默跳过 prompt 注册并仅打印 warning。两种策略未调和：要么在依赖中强制 `mcp>=1.0.0` 并移除降级 fallback，要么保留 fallback 但将“prompts 不可用”作为 doctor 的 failed/warning check 明确告知用户，而非仅写入服务端日志。当前做法会让旧 SDK 用户安装后无 prompts 且无清晰失败信号。
    attribution: pending
    severity: architectural
    plan_amendment_required: true
    location: "Task 2 Step 0 与 Step 4"
    design_dimension: DR1
  - id: 4
    description: |
      DR2 完整性：Task 3 Step 5 的 `test_coordinate_safety_block_error_includes_next_action` 使用 `assert data["error"] == "mocked safety block"` 做精确相等断言。计划仅说明“保持原有 error 字段不变”，但未审计当前 `_call_tool` 是否会在异常消息外加前缀或包装。一旦实现将异常包装为 `f"Safety error: {exc}"` 等格式，测试会通过 next_action 检查却在 error 字符串断言上失败，造成修复-测试循环中的假阴性。应改为子串断言（`in`）或先审计 `_call_tool` 的 error 字段构造方式。
    attribution: pending
    severity: implementation
    plan_amendment_required: true
    location: "Task 3 Step 5: test_coordinate_safety_block_error_includes_next_action"
    design_dimension: DR2
  - id: 5
    description: |
      DR2 / DR6：doctor 硬编码检查 config 键 "log_dir", "screenshot_dir", "trace_dir", "task_dir"，但计划未审计 `load_config()` 实际返回对象中这些键是否真实存在、是否叫这个名字。若实际配置使用 "log_directory"、"artifact_dir" 等名称，doctor 会全部报 failed，给出错误诊断。应在 Task 4 Step 0 增加对 config schema 的审计，或改为读取现有 `config.yaml` 示例/默认值推导可写目录。
    attribution: pending
    severity: structural
    plan_amendment_required: true
    location: "Task 4 Step 3: run_doctor 目录检查循环"
    design_dimension: DR2
suggestion_issues:
  - description: |
      DR5 残留冗余：Task 6 的 smoke test 与 Task 7 的 `test_distribution_readiness.py` 都依赖 JSON-RPC over stdio 和文档短语，但未提供对当前 `mcp_server.py` 实际传输层或 README 当前结构的审计步骤。建议把“确认 mcp_server 使用 stdio / 当前 README 已有 onboarding 节”加入对应 Task 的 Step 0。
    design_dimension: DR5
  - description: |
      DR3 可维护性：`test_distribution_readiness.py` 检查 README 中 “Kimi” 不能出现在 “First run” 之前，并把 “First run / 快速开始 / Get started” 作为可接受标题。这种对文档营销措辞的精确测试会在文档正常迭代中频繁误报，建议改为检查 onboarding 节存在性 + 关键短语存在性，而非相对位置与品牌词禁令。
    design_dimension: DR3
  - description: |
      DR4 边界清晰：`skills/computer-use/SKILL.md` 与 `docs/agent-usage.md`、`examples/clients/agent-prompt.md` 三者内容高度同源，但计划仅通过存在性测试和少量关键词守护。建议明确说明三者的职责分层（SKILL.md 给支持 Skill 的客户端；agent-usage.md 给阅读仓库的人；agent-prompt.md 给不支持 prompts/Skill 的客户端），并在验收标准中要求关键规则三者一致，而非仅依赖人工维护。
    design_dimension: DR4
antipattern_observations:
  - type: archaeology_leftover
    evidence: |
      "当前代码已声明 `mcp>=1.0.0`，因此无需修改依赖；若审计发现版本低于 `1.0.0`，先升级到 `mcp>=1.0.0` 再继续。"
      "本轮审计结果：名称一致，可直接使用。"
  - type: data_tool_coupling
    evidence: |
      `test_distribution_readiness.py` 断言 `before_first_run = readme.split(header, 1)[0]; assert "Kimi" not in before_first_run`，将测试与 README 中品牌词的出现位置强耦合。
  - type: solution_anchoring
    evidence: |
      计划大量测试直接访问 `by_name["screenshot"]`、`server._call_tool("batch", ...)` 等具体工具名，依赖 Task 3 Step 0 中“已确认”的工具表；但盲审视角无法验证这些确认是否仍有效，缺少运行时或代码级二次确认步骤。
```

## Orchestrator 处理记录

- **[Orchestrator Detection]** Blind verdict: `阻断需修复`; 5 blocking findings.
- **[Orchestrator Detection]** 盲审发现将作为 escalated_issues (BR- 前缀) 注入 Round 5 主循环 Reviewer。
- **[Orchestrator Detection]** archaeology_leftover 观察：计划中出现“本轮审计结果：名称一致，可直接使用”等修复痕迹，需要在 Round 5 修复中删除。
