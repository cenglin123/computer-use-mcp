---
round: blind-recheck-2
reviewer_backend: opencode
reviewer_instance_id: ses_12573a2d1ffegaA29O7J6rJ2h7
generated_at: 2026-06-18T19:40:00+08:00
---

# Blind Recheck 2 · post-review-improvements plan

## Reviewer 完整输出

```yaml
round: blind-recheck-2
verdict: 阻断需修复
deterministic_check: skipped
deterministic_check_skip_reason: 审查对象为 plan 文档，非代码项目
blocking_issues:
  - id: 1
    description: |
      Task 3 将 `_call_tool` 设计为仅接受 `(name, arguments)` 的“薄 shim”，但当前 `mcp_server._call_tool` 的实际签名为 `_call_tool(name, args, trace_context=None, *, context=None)`，且承担 trace 记录、异常分类处理、timestamp 注入、manifest 附加、task context 注入等职责。`_handle_tool_call` 当前以 `context=context` 调用 `_call_tool`，薄 shim 会破坏该调用；若将上述职责全部上移到 `_handle_tool_call`，则 Task 1 直接调用 `_call_tool` 的集成测试会失去 trace/异常处理等行为。计划声称“签名与返回类型保持不变”但所示签名仅两个参数，自相矛盾。
    attribution: pending
    severity: architectural
    plan_amendment_required: true
    location: Task 3 Step 4 “兼容性 shim”
  - id: 2
    description: |
      Task 3 暴露的公共 `dispatch_tool(name: str, arguments: dict) -> dict` 仅有两个参数，无法替代当前需要 `cs`（CoordinateSystem）、`trace_id`、`parent_step_index`、`task_id`、`is_standalone` 等上下文的 `_dispatch_tool`。若 `dispatch_tool` 内部自行创建 coordinate system 与 trace context，会与 `_handle_tool_call` 的 context 生命周期冲突；若不支持这些参数，则工具调用行为改变。计划未说明如何在不破坏行为的前提下完成替换。
    attribution: pending
    severity: architectural
    plan_amendment_required: true
    location: Task 3 Step 3 “创建 tools 子包”
  - id: 3
    description: |
      计划将 `_dispatch_tool` 迁移至 `computer_use/tools/dispatch.py`，但未说明同时迁移其内部依赖的 `_NEXT_ACTION_UI_NOT_FOUND`、`_NEXT_ACTION_INVALID_TOOL` 等常量。这些常量在 `_dispatch_tool` 内部被直接使用，迁移后会导致 `dispatch.py` 导入错误，重构无法通过编译。
    attribution: pending
    severity: structural
    plan_amendment_required: true
    location: Task 3 Step 3
  - id: 4
    description: |
      Task 1 集成测试 fixture 使用 `pyautogui.getWindowsWithTitle("Notepad")` 并匹配标题包含 "Notepad" 的窗口。在非英文 Windows（如中文系统窗口标题为“无标题 - 记事本”）中该匹配会失败，导致测试无法通过。计划声称测试在“真实 Windows 环境”通过，但未处理系统语言差异。
    attribution: pending
    severity: implementation
    plan_amendment_required: true
    location: Task 1 Step 4 `_wait_and_activate_window`
  - id: 5
    description: |
      Task 1 集成测试生成两张截图但不对 `saved_path` 返回的文件进行清理，可能遗留文件；测试向真实 notepad 输入文本，若用户正在操作键盘会造成干扰，但计划未提示应在无人操作时运行；`ManagedApp.close()` 通过 terminate/kill 关闭 notepad，若出现未保存提示框可能留下挂起窗口，影响后续测试稳定性。
    attribution: pending
    severity: implementation
    plan_amendment_required: true
    location: Task 1 Step 1、Step 4
suggestion_issues:
  - description: 计划中的命令大量使用 `./.venv/Scripts/python.exe` 等环境特定路径，作为 handoff 文档应改为更通用的 `python -m pytest` 形式或注明依赖已激活虚拟环境。
  - description: `_call_tool` 以下划线开头却被计划称为“公开 shim”，与 Python 私有约定冲突；建议明确其为内部测试钩子或重命名为公开名称。
  - description: 项目 `pytest.ini` 已存在 `manual` marker，计划新增 `integration` marker；建议说明不复用 `manual` 的原因，避免 marker 语义重复。
  - description: Task 2 测试通过 monkeypatch 替换私有函数 `safety._allowed_commands`，较脆弱；可考虑改为通过配置对象或公开 API 控制白名单状态。
  - description: `config.example.yaml` 示例仅列出基本名，未展示 `is_allowed_command` 支持的完整路径白名单形式，可补充说明。
  - description: 原评审“混合 DPI 多显示器支持”列为 P0，计划明确排除并标记为验收风险；建议在风险节补充更具体的升级路径/触发条件。
antipattern_observations:
  - type: over_compromise
    evidence: |
      Task 3 中 "_call_tool" 被描述为"薄 shim"，实际承担 trace 记录、异常处理、timestamp 注入、manifest 附加等关键职责，计划通过过度简化来保持"测试兼容"，但未说明这些职责由谁承接。
```

## Orchestrator 处理记录

- **[Orchestrator Detection]** 第二次盲审 verdict = 阻断需修复，5 个 blocking issues，全部 attribution = pending。
- **[Orchestrator Detection]** 核心问题：Task 3 对 `_call_tool` / `_dispatch_tool` 的描述与实际代码严重不符，需要大幅收缩 Task 3 scope。
- **[Orchestrator Detection]** Task 1 fixture 需要处理非英文 Windows 标题与清理/干扰问题。
