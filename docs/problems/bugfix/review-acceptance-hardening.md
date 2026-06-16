---
id: bugfix-review-acceptance-hardening
type: bugfix
title: 计划验收后收口 Schema、CLI 导入和 standalone 清理边界
status: fixed
severity: medium
scope:
  - mcp
  - cli
  - audit
modules:
  - computer_use.mcp_server
  - computer_use.cli
tags:
  - review
  - run-task-plan
  - pyautogui
  - standalone-task
symptoms:
  - run_task_plan 的 steps[].tool Schema 缺少 enum 静态提示
  - import computer_use.cli 会经 UIA 链条加载 pyautogui
  - standalone task 在 trace_id 归属冲突时可能停留 active
error_signatures:
  - run_task_plan.steps.items.properties.tool has no enum
  - pyautogui in sys.modules after importing computer_use.cli
  - trace_task_conflict leaves standalone task active
related_files:
  - computer_use/mcp_server.py
  - computer_use/cli.py
  - tests/test_mcp_server.py
  - tests/test_cli.py
verification:
  level: automated
  kind: regression-test
  path: tests/test_mcp_server.py
  command: .\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py tests/test_cli.py -v
created_at: 2026-06-16
updated_at: 2026-06-16
---

# 计划验收后收口 Schema、CLI 导入和 standalone 清理边界

## 现在的行为

独立验收发现三个边界：

- `batch.actions[].tool` 已有 canonical enum，但 `run_task_plan.steps[].tool` 仍只是字符串，Schema 层无法提示合法工具名。
- `computer_use.cli` 模块级导入 `inspect_point`，会经 `ui_automation` / `core` 链条提前加载 `pyautogui`，违背审计命令不初始化输入设备依赖的目标。
- 未传 `task_id` 且复用已归属其他 task 的 `trace_id` 时，standalone task 会先创建，再在 `register_trace` 冲突处失败；失败发生在 `ExecutionContext` 返回前，外层 finally 无法关闭该 standalone task。

## 预期的行为

- `run_task_plan` 的嵌套工具 Schema 与运行时 allow-list 一致。
- 只读 CLI 审计路径和模块导入本身不加载 `pyautogui` 或 `computer_use.core`。
- 上下文建立失败时，自动创建的 standalone task 不应长期保持 active。

## 复现方式

1. 检查 `run_task_plan` tool schema，可看到 `steps[].tool` 没有 `enum`。
2. 在干净 Python 子进程中执行 `from computer_use import cli`，再检查 `sys.modules`。
3. 先把 `shared-trace` 归属到显式 task，再不传 `task_id` 调用带同一 `trace_id` 的 `run_task_plan`，观察 standalone task 状态。

## 原因是什么

Schema 补全只覆盖了 `batch`，没有同步到 `run_task_plan`。CLI 之前虽然延迟了大部分输入设备函数，但遗漏了 `inspect_point` 的模块级导入。standalone cleanup 逻辑放在 `_handle_tool_call` 的 `finally`，但 `_establish_context` 在 register 阶段抛错时尚未返回 context。

## 怎么修复的

- `run_task_plan.steps[].tool` 复用 `TASK_STEP_TOOL_NAMES` 生成 enum，并新增漂移守卫测试。
- 将 `inspect_point` 延迟到 `main()` 中真实需要鼠标输入路径时导入，并新增干净子进程导入测试。
- `_establish_context` 记录刚创建的 standalone task；若上下文建立失败，调用 `finish_task(..., cancel=True)` 关闭该 task 后继续返回结构化错误。

## 验证结果

已执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py tests/test_cli.py -v
```

结果：`101 passed, 1 skipped`。

## 风险和后续

standalone 上下文建立失败时保留一个 `cancelled` task 审计记录，而不是删除 task 目录。这会多一条可解释的失败审计记录，但不会留下 active 任务，也不会执行真实输入动作。
