---
id: bugfix-batch-tool-contract-and-artifact-reporting
type: bugfix
title: Batch 工具名与 Trace 产物报告不明确
status: fixed
severity: high
scope:
  - backend
  - api
  - observability
modules:
  - mcp-server
  - runner
  - trace
  - snapshot
tags:
  - batch
  - trace
  - artifacts
  - tool-name
  - diagnostics
symptoms:
  - 外部限定工具名在 batch 内返回 Unknown tool
  - 空产物目录被误报为存在截图或快照
  - 执行侧无法从响应直接定位 trace.jsonl
error_signatures:
  - "Unknown tool: computer-use_press_key"
  - error_kind=unknown
related_files:
  - computer_use/tool_contract.py
  - computer_use/mcp_server.py
  - computer_use/trace.py
  - computer_use/runner.py
  - computer_use/snapshot.py
  - tests/test_mcp_server.py
  - tests/test_trace.py
  - tests/test_runner.py
  - tests/test_snapshot.py
verification:
  level: automated
  kind: regression-test
  path: tests/test_mcp_server.py
  command: .\.venv\Scripts\python.exe -m pytest tests/test_trace.py tests/test_mcp_server.py tests/test_runner.py tests/test_snapshot.py -v
created_at: 2026-06-16
updated_at: 2026-06-16
---

# Batch 工具名与 Trace 产物报告不明确

## 现在的行为

历史实现中，`batch` 和 `run_task_plan` 的嵌套工具名只是普通字符串。执行侧 Agent 把 MCP 外部限定名 `computer-use_press_key` 放入 `batch.actions[].tool` 后，server 按原始字符串分发，返回 `Unknown tool`，trace 中记录为 `error_kind=unknown`。

同时，trace 目录会预创建 `screenshots/` 和 `snapshots/` 空目录，响应只返回 `trace_id`，没有权威的 `trace_path`、`artifact_root` 或实际产物清单。执行侧容易把“目录存在”误报为“本次任务含截图或快照”。

## 预期的行为

嵌套工具必须使用 canonical tool name；已知 MCP 前缀可以兼容规范化，但响应必须同时保留 `requested_tool` 和规范化后的 `tool`。无法识别的工具名返回结构化 `invalid_tool`，并在 trace 中记录为同名 `error_kind`。

执行结果必须直接暴露可验证路径和实际产物清单。产物清单只列真实存在的文件，不能把空目录解释为证据。

## 复现方式

复现输入：

```json
{
  "actions": [
    {"tool": "computer-use_press_key", "args": {"key": "Down"}}
  ]
}
```

旧行为会进入未知工具分支。拼写错误形式：

```json
{
  "actions": [
    {"tool": "computer-use_press_keey", "args": {"key": "Down"}}
  ]
}
```

旧行为会记录为 `unknown`，无法区分调用契约错误和真实执行错误。

## 原因是什么

根因有三点：

- nested 工具名缺少集中契约，Schema、运行时和测试没有共享同一个 canonical 集合。
- trace 产物目录被预创建，目录存在不等于产物存在。
- batch/task/review 响应没有从 trace 层派生权威 manifest，执行侧只能根据目录名和经验猜测。

## 怎么修复的

修复包含：

- 新增 `computer_use/tool_contract.py`，集中定义 batch/task 可嵌套工具集合、已知 MCP 前缀规范化和候选建议。
- `batch.actions[].tool` Schema 改为 canonical enum；运行时也使用同一集合校验。
- `run_task_plan` 使用同一规范化逻辑，嵌套 `run_task_plan` 或拼错工具名返回 `invalid_tool` 结果项，而不是抛出非结构化 `ValueError`。
- `_error_kind_for_result` 将 `invalid_tool` 映射为专用 trace 分类。
- `trace_root()` 不再预创建产物目录，新增 `artifact_dir()` 按需创建。
- 新增扁平 `artifact_manifest()`，只列真实存在的 `trace.jsonl`、`report.md`、截图和快照文件。
- `_call_tool` 在 batch/run_task_plan/review_task 返回边界由 manifest 派生 `trace_path`、`artifact_root` 和嵌套 `artifacts`。
- 自动截图绑定当前 trace：截图 PNG 进入 `screenshots/`，UI-tree JSON 进入 `snapshots/`。
- batch/run_task_plan 响应增加 `status`、`error_kind`、`executed_count`、`requested_count`，让执行侧可准确汇报。

## 验证结果

已通过以下自动化验证：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trace.py tests/test_mcp_server.py tests/test_runner.py tests/test_snapshot.py -v
```

覆盖范围包括工具名规范化、非法工具分类、惰性产物目录、manifest 响应信封、自动截图归属和执行摘要字段。

## 风险和后续

已知兼容边界：

- 只兼容明确列出的 MCP 前缀，不做任意模糊自动执行。
- 全局无 trace 上下文的 snapshot 截图仍写入 `<trace_dir>/snapshots`，历史文件不迁移。
- 用户显式调用 `screenshot` 的保存目录契约不变，只有 task 自动截图和 snapshot 截图绑定 trace。
- 后续业务任务会话计划会在此 manifest 基础上新增 `task_id` 归属，不重复维护产物清单。
