# CU Task Context And Output Budget Hardening

> 状态：active
> 创建：2026-06-21
> 收敛：待评议

## 背景

`ses_11ad0e3dbffeoB5OFzDx7g57r9` 中暴露了两类工具层未阻止的高风险行为：

1. **大输出快照**：`get_ui_snapshot(scope="desktop", include_screenshot=true)` 产生约 9.5MB 的截断输出。
2. **空 task 审计链**：`start_task` 后所有后续工具调用忘传 `task_id`，导致显式 task `trace_count: 0`、最终 `status: failed`，每个工具各自创建 standalone task。

前一轮计划（已完成，见 `docs/plans/completed/mcp-accuracy-performance-improvement.md`）把这两类问题留在文档纪律层。本计划把它们升级为 **MCP 工具层可验证约束**。

## 目标

让使用 `computer-use` 的 agent 即使读了 skill 后不自觉遵守，也会被 MCP 层阻止最危险的两类错误：大输出快照和空 task 审计链。保持向后兼容：未显式 `start_task` 时，旧的 standalone 行为继续可用。

## 架构

在 MCP 分发入口加两类 guard。第一类是 **task context guard**：显式 active task 存在时，顶层可执行工具必须带 `task_id`。第二类是 **snapshot output budget guard**：桌面级/超大 UIA snapshot 不再直接 inline 返回。文档和 skill 只做配套说明，不再作为唯一防线。

## 技术栈

Python 3.11, MCP stdio server, pytest, existing `computer_use.task_session`, `computer_use.trace`, `computer_use.snapshot`。

## Guard 执行顺序

三个 guard 按以下顺序串联执行，前者未通过时后者不会运行：

1. **Task 1 guard**（`_handle_tool_call` 层，pre-context、pre-dispatch）— 最先触发。
2. **Task 2 guard**（`_dispatch_tool` 层，在 `get_ui_snapshot` 分支内）— 仅在 Task 1 通过后才可能运行。
3. **Task 3 guard**（post-serialization，snapshot result 构建后）— 仅在 Task 2 通过后才可能运行。

**关键交互**：若 agent 在 active explicit task 存在时调用 `get_ui_snapshot(scope=desktop, include_screenshot=true)` 但未带 `task_id`，Task 1 先触发并返回 `missing_task_id`；Task 2 不会运行，直到 agent 带 `task_id` 重试。

---

## Task 1: Enforce `task_id` After `start_task`

### 问题

`ses_11ad0e3dbffeoB5OFzDx7g57r9` 中：

- 调用了 `computer-use_start_task`，得到 `task-20260620-144807-zemjs2`。
- 后续 `move_to/click/screenshot` 全部没带 `task_id`。
- 每个工具都创建了 standalone task。
- 原始显式 task 最终 `trace_count: 0`，`status: failed`。

### 期望行为

如果存在 active explicit task，**所有未排除工具**调用没有 `task_id` 时，MCP 返回结构化错误，不执行真实输入、不创建 standalone task。

**被守护的工具集合** = 所有不在 `_TASK_CONTEXT_EXCLUDED_TOOLS` 内的工具，即除 task 管理工具（`start_task`/`finish_task`/`get_task`/`list_tasks`/`review_task_session`）和 `review_task` 之外的全部工具。这包含：

- 输入工具：`click`、`type`、`move_to`、`scroll`、`drag`、`key_combo`、`press_key` 等
- 观察工具：`screenshot`、`get_ui_snapshot`、`find_control`、`inspect_point`、`get_monitors`
- 等待工具：`wait_for_window`、`wait_for_control`、`sleep`
- 复合工具：`batch`、`run_task_plan`

**注意**：这意味着即使 `screenshot`、`get_monitors`、`sleep` 这类只读工具，在 active explicit task 存在时，未带 `task_id` 也会被拒绝。理由：只读工具也会创建独立 trace，污染审计链；guard 的目的是确保**所有**工作都归因到显式 task，使 `review_task_session` 能完整还原工作过程。

### 文件

- Modify: `computer_use/mcp_server.py`
- Modify: `computer_use/task_session.py` (if no suitable active-task helper exists)
- Modify: `computer_use/tools/schemas.py`
- Test: `tests/test_mcp_server.py`
- Docs: `docs/api.md`
- Docs/Skill: `computer_use/guidance.py`, `skills/computer-use/SKILL.md`, `.agents/skills/computer-use/SKILL.md`

### 实现步骤

1. Add or reuse active explicit task lookup.

If `task_session.list_tasks(status="active")` already exists and returns enough metadata, reuse it. Otherwise add a helper:

```python
def list_active_explicit_tasks(limit: int = 10) -> list[dict[str, Any]]:
    return [
        task for task in list_tasks(status="active", limit=limit)
        if task.get("mode") == "explicit"
    ]
```

2. Insert the new guard at `mcp_server._handle_tool_call`.

**已存在的常量（不要重复创建）**：`_TASK_CONTEXT_EXCLUDED_TOOLS` 已定义于 `computer_use/tools/schemas.py:15`，其值为 `_TASK_MANAGEMENT_TOOLS | {"review_task"}`，当前成员为 `{start_task, finish_task, get_task, list_tasks, review_task_session, review_task}`。该常量在 `mcp_server.py:70` 已被导入，并在 `_handle_tool_call` 中已有的 early-exit 分支（`mcp_server.py:1284` 处 `if name in _TASK_CONTEXT_EXCLUDED_TOOLS:`，至 `mcp_server.py:1300` 结束）中使用。

**精确插入点**：在上述 early-exit 块之后（约 `mcp_server.py:1302`），在 `_establish_context(...)` 调用之前（`mcp_server.py:1304`）。新 guard 复用已导入的 `_TASK_CONTEXT_EXCLUDED_TOOLS`，**不要创建新的常量**。

**已存在的 task_id 参数（无需 schema 结构改动）**：`task_id` 已通过 `_attach_task_context_schemas()`（`schemas.py:606-617`）作为可选参数挂载到所有未排除工具上。本 Task 不需要新增 schema 结构，只需要更新描述（见 Task 4）。

Pseudo-behavior:

```python
if name not in _TASK_CONTEXT_EXCLUDED_TOOLS and not safe_arguments.get("task_id"):
    active_tasks = task_session.list_active_explicit_tasks(limit=5)
    if len(active_tasks) == 1:
        return json.dumps({
            "error": "missing_task_id",
            "active_task_id": active_tasks[0]["task_id"],
            "next_action": (
                "Retry the same tool call with task_id set to active_task_id. "
                "After start_task, every executable computer-use tool must pass task_id."
            ),
        })
    if len(active_tasks) > 1:
        return json.dumps({
            "error": "missing_task_id_ambiguous",
            "active_task_ids": [task["task_id"] for task in active_tasks],
            "next_action": "Choose the intended task_id or finish/cancel stale active tasks.",
        })
```

3. Keep old behavior if no active explicit task exists.

This preserves compatibility for one-off calls:

```python
computer-use_screenshot({"monitor": 1})
```

still creates standalone task only when no explicit active task exists.

4. Add tests.

Required tests in `tests/test_mcp_server.py`:

- `test_top_level_tool_without_task_id_is_rejected_when_active_explicit_task_exists`
- `test_top_level_tool_without_task_id_still_creates_standalone_when_no_active_task`
- `test_top_level_tool_with_task_id_registers_trace_to_explicit_task`
- `test_task_management_tools_do_not_require_task_id_guard`

5. Update existing test `test_standalone_context_register_conflict_does_not_leave_active_task` in `tests/test_mcp_server.py` (lines 357-389): **finish the `owner` task before the guarded call** by inserting `task_session.finish_task(owner)` after the `register_trace(...)` block (after line 373). The `_handle_tool_call("run_task_plan", ...)` call (lines 375-383) remains unchanged and still omits `task_id`. The test's assertion (`data["error"] == "trace_task_conflict"`) remains unchanged.

Without this fix the new Task 1 guard short-circuits the call to `missing_task_id` because `run_task_plan` is a guarded (non-excluded) tool, an active explicit task (`owner`) exists, and the call omits `task_id`.

**Why not just add `task_id=owner` instead?** That would NOT trigger the conflict. Per `computer_use/task_session.py:189`, `register_trace` only raises `TraceTaskConflictError` when `existing_owner is not None and existing_owner != task_id`. If the call passes `task_id=owner`, `_establish_context` reuses the `owner` task and `register_trace` sees `existing_owner == task_id` → no conflict → the `"trace_task_conflict"` assertion fails.

By finishing `owner` first, no active explicit task exists, so the Task 1 guard passes; `_establish_context` creates a standalone task; `register_trace(standalone, "shared-trace", ...)` then finds `_find_trace_owner` still returns `owner` (it scans ALL tasks regardless of status — see `task_session.py:131-142`), so `existing_owner(owner) != standalone_task` → conflict triggers → the standalone task is cleaned up. This preserves the test's original intent (standalone-conflict-cleanup) while remaining compatible with the new guard.

7. Update existing test `test_outer_tool_handler_redacts_exception_response_and_log` in `tests/test_mcp_server.py` (lines 2118-2138): **monkeypatch `task_session.task_dir` to `tmp_path / "tasks"`** for directory isolation.

   The test calls `server._handle_tool_call("type", {"text": "outer-secret"})` without `task_id` and without isolating the task directory. Under the Task 1 guard, `_handle_tool_call` calls `list_active_explicit_tasks()` which queries the real `~/.computer-use/tasks/` directory. If a stale active explicit task exists there (from prior test runs that didn't clean up, or from real agent usage), the guard short-circuits to `missing_task_id` and the test assertion `"<redacted>" in result` fails.

   **修改方式**：
   - Add `tmp_path` to the test signature: `def test_outer_tool_handler_redacts_exception_response_and_log(monkeypatch, caplog, tmp_path) -> None:`
   - Add `import computer_use.task_session as task_session` inside the test body
   - Add `monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")` alongside the existing `server` monkeypatch

   The test already monkeypatches `server._call_tool` to throw, so `_establish_context` / `_dispatch_tool` are never reached. The only new code path exercised is the Task 1 guard lookup, which will now correctly see an empty (isolated) task directory → guard passes → execution reaches the monkeypatched `_call_tool` → throws → redaction works as before.

6. Update descriptions.

In `tools/schemas.py`, update `start_task` description and executable `task_id` description:

```text
After start_task, pass the returned task_id to every subsequent executable tool. If an explicit task is active, executable tools without task_id are rejected.
```

### 验收标准

- A session like the observed one fails fast on the first missing `task_id`.
- No real click/move/screenshot happens before the missing task id is corrected.
- Explicit task no longer ends with `trace_count: 0` after real work.
- Existing standalone one-off tool tests still pass, except `test_standalone_context_register_conflict_does_not_leave_active_task` (`tests/test_mcp_server.py:357-389`) which must be updated to insert `task_session.finish_task(owner)` after the `register_trace(...)` block (after line 373), keeping the `_handle_tool_call("run_task_plan", ...)` call unchanged (no `task_id`). The test creates an active explicit task via `task_session.start_task("owner")` at line 367; under the new guard, the call at lines 375-383 without `task_id` would be short-circuited to `missing_task_id`. Finishing `owner` first removes the active explicit task so the guard passes, `_establish_context` creates a standalone task, and `register_trace` then conflicts: the trace is still owned by the finished `owner` per `_find_trace_owner` (`task_session.py:131-142`, scans ALL tasks regardless of status), and `existing_owner(owner) != standalone_task` per `task_session.py:189`. This preserves the standalone-conflict-cleanup scenario without an active explicit task; the test assertion (`"trace_task_conflict"`) holds unchanged.
- **Scan of other tests（覆盖 Task 1/2/3 全部三个 guard）**：逐一审查了 `tests/test_mcp_server.py` 中全部 9 个 `_handle_tool_call` 调用点、全部 `_call_tool` / `_dispatch_tool` get_ui_snapshot 相关调用点，以及 `tests/test_snapshot.py` 中的 snapshot 测试。结论：

  **Task 1（task_id guard，在 `_handle_tool_call` 层）**：除上文 `test_standalone_context_register_conflict_does_not_leave_active_task`（line 357）外，还发现一处需修改——`test_outer_tool_handler_redacts_exception_response_and_log`（line 2118）调用 `_handle_tool_call("type", ...)` 但**未 monkeypatch `task_session.task_dir`**。该测试在 Task 1 guard 落地后，若真实 `~/.computer-use/tasks/` 存在 active explicit task（例如前序测试残留或真实使用遗留），guard 会短路返回 `missing_task_id`，导致断言 `"<redacted>" in result` 失败。**修改方式**：在 monkeypatch 块中添加 `monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path / "tasks")` 以隔离 task 目录（同时添加 `tmp_path` 参数和 `import computer_use.task_session as task_session`）。其余 `_handle_tool_call` 站点均安全：`start_task`（line 299，excluded）、`sleep` + task_id（lines 331/332/427，显式传 task_id）、`sleep` 无 task_id（line 349，`test_missing_task_id_creates_closed_standalone_task`，已 monkeypatch task_dir 且无 active task）、`batch`（line 400，`test_batch_registers_only_top_level_trace_for_task`，已 monkeypatch task_dir 且无 active task）、`review_task`（line 2005，excluded）。

  **注意**：`_call_tool` 和 `_dispatch_tool` 的直接调用**不走** `_handle_tool_call`，因此 Task 1 guard 不触发。Task 1 guard 仅守护 MCP 顶层入口。

  **Task 2（desktop + include_screenshot=true guard，在 `_dispatch_tool` 层）**：`test_get_ui_snapshot_tool_dispatch`（line 1790）调用 `_call_tool("get_ui_snapshot", {"scope": "desktop", "include_screenshot": True})`。`_call_tool` → `_dispatch_tool`，Task 2 guard 在调用 `snapshot.get_ui_snapshot(...)` 之前短路，返回 `high_cost_snapshot_blocked`。测试断言 `data["screenshot_path"] == "C:/tmp/snap.png"`、`calls[0][0:2] == ("desktop", True)` 均失败（fake 从未被调用，`calls` 为空 → IndexError）。**修改方式**见 Task 2 步骤 4。其余安全：`test_batch_capture_snapshot_includes_snapshot`（line 1760）的 batch capture 路径直接调用 `snapshot.get_ui_snapshot(scope="foreground", include_screenshot=False)`（`mcp_server.py:954`），绕过 `_dispatch_tool`，guard 不触发。

  **Task 3（>200K chars inline budget，post-serialization）**：无额外受影响测试。`test_get_ui_snapshot_tool_dispatch`（line 1790）的 fake 返回极小 payload（<200 chars），远低于 200K 预算——但该测试已被 Task 2 guard 拦截，不会到达 Task 3 检查。`tests/test_snapshot.py` 全部测试直接调用 `snapshot_mod.get_ui_snapshot(...)`，绕过 `_dispatch_tool`，Task 3 guard 不触发。

  **完整受影响测试汇总见文末「受影响测试汇总」表。**

---

## Task 2: Block High-Cost Desktop Snapshot Combinations

### 问题

The first heavy mistake was:

```json
{"scope":"desktop","include_screenshot":true}
```

It produced:

```text
...9496259 bytes truncated...
```

### 期望行为

This combination should not inline a full desktop UIA tree. Return a small structured error with a safe next action.

### 文件

- Modify: `computer_use/mcp_server.py`
- Modify: `computer_use/tools/schemas.py`
- Test: `tests/test_mcp_server.py`
- Docs: `docs/api.md`, `docs/pitfalls.md`
- Guidance/Skill: `computer_use/guidance.py`, `skills/computer-use/SKILL.md`, `.agents/skills/computer-use/SKILL.md`

### 实现步骤

1. In the `get_ui_snapshot` dispatch branch, reject exact high-cost combination:

```python
if args.get("scope") == "desktop" and args.get("include_screenshot") is True:
    return json.dumps({
        "error": "high_cost_snapshot_blocked",
        "next_action": (
            "Use get_ui_snapshot(scope='foreground', include_screenshot=false). "
            "If cross-window context is needed, use get_ui_snapshot(scope='desktop', include_screenshot=false) "
            "or find_control with narrow criteria."
        ),
    })
```

2. Add a test:

`test_get_ui_snapshot_blocks_desktop_with_include_screenshot`

Expected:

- output has `error == "high_cost_snapshot_blocked"`
- no screenshot file is created
- no giant `controls` payload is returned

3. Update tool description for `get_ui_snapshot`.

Add explicit warning:

```text
Do not use scope=desktop with include_screenshot=true; this combination is blocked because it can create huge outputs.
```

4. Update existing test `test_get_ui_snapshot_tool_dispatch` in `tests/test_mcp_server.py` (lines 1790-1814): the success-case call `_call_tool("get_ui_snapshot", {"scope": "desktop", "include_screenshot": True})` is now blocked by the Task 2 guard.

   **修改方式**：将 success-case 的参数从 `{"scope": "desktop", "include_screenshot": True}` 改为 `{"scope": "foreground", "include_screenshot": True}`（或 `{"scope": "desktop", "include_screenshot": False}`）。同步更新断言：`data["scope"] == "foreground"`（或保持 `"desktop"`）、`calls[0][0:2] == ("foreground", True)`（或 `("desktop", False)`）。该测试的核心目的是验证 `_dispatch_tool` 正确将 `scope`/`include_screenshot` 透传给 `snapshot.get_ui_snapshot` 并返回路径，foreground 成功路径同样验证这一点。被拦截的 desktop+screenshot 组合由新增的 `test_get_ui_snapshot_blocks_desktop_with_include_screenshot`（步骤 2）覆盖。

**与 Task 3 的关系**：Task 2 是针对已观察到的最危险组合（`desktop + include_screenshot=true`）的 fast-path 显式 guard；Task 3 是通用 backstop，覆盖任何超过 inline 预算的 snapshot。二者互补，Task 3 落地后**不要**以"重复"为由删除 Task 2。

### 验收标准

- The exact bad call from the session returns a small JSON error.
- The agent gets a clear safe replacement.
- No 9MB tool-output can be produced by that combination.

---

## Task 3: Add Inline Snapshot Output Budget

### 问题

Even `scope="desktop", include_screenshot=false` can still be large. Blocking only one combination is not enough.

### 期望行为

Any `get_ui_snapshot` response that exceeds a fixed inline budget should be replaced with a compact response. The full snapshot may be saved locally, but not returned inline.

### 文件

- Modify: `computer_use/mcp_server.py`
- Possibly modify: `computer_use/snapshot.py`
- Test: `tests/test_mcp_server.py`

### 实现步骤

1. Add a constant near MCP dispatch code:

```python
MAX_INLINE_SNAPSHOT_CHARS = 200_000
```

**阈值理由**：200K chars ≈ 50K tokens（按 ~4 chars/token 估算），是单个工具响应开始显著影响上下文的合理上限。Foreground snapshot 通常为 5-30KB（远低于预算）；desktop snapshot 可能超过 200KB+。更原则性的替代是在序列化前对 `control_count` 做上限，但 post-serialization 测量更简单，且不需要改动 `snapshot.py` 内部逻辑。

2. After building the snapshot result, serialize it once and measure length.

If serialized length exceeds budget:

```python
return json.dumps({
    "error": "snapshot_output_too_large",
    "scope": args.get("scope", "foreground"),
    "control_count": len(result.get("controls", [])),
    "truncated": True,
    "next_action": (
        "Use scope='foreground', find_control, click_by_text, or narrower criteria. "
        "Do not read full desktop snapshot output."
    ),
})
```

Optional but useful: save full JSON to a trace snapshot artifact and include `snapshot_path`, but make the `next_action` say not to read it unless absolutely necessary.

3. Add tests:

- `test_get_ui_snapshot_large_output_returns_compact_error`
- `test_get_ui_snapshot_normal_output_still_returns_controls`

**与 `_SCOPE_LIMITS` 的交互（建议 S2 裁决）**：`snapshot.py:34-37` 中 `_SCOPE_LIMITS["desktop"] = 5000`、`["foreground"] = 2000`。5000 个控件序列化后几乎必然超过 200K chars 预算，意味着 **Task 3 落地后 `scope="desktop"` 实际上总是被拦截**（即使 `include_screenshot=false`）。这是预期行为：desktop 级 UIA 树本身就过于昂贵，agent 应改用 `find_control` 配合窄条件、或 `get_ui_snapshot(scope="foreground")`。`_SCOPE_LIMITS` 是 `snapshot.py` 内部的"采集前"硬上限，与本 Task 的"序列化后"预算互补，不应合并或移除任一者。

### 验收标准

- No `get_ui_snapshot` call can inline hundreds of KB or MB of JSON.
- Foreground normal snapshots remain unchanged.
- Desktop snapshots either return small enough data or a compact error.
- **现有测试影响**：无。`test_get_ui_snapshot_tool_dispatch`（line 1790）的 fake 返回极小 payload（<200 chars），远低于 200K 预算，但该测试已被 Task 2 guard 在 `_dispatch_tool` 层拦截，不会到达 Task 3 post-serialization 检查。`tests/test_snapshot.py` 全部测试直接调用 `snapshot_mod.get_ui_snapshot(...)`，绕过 `_dispatch_tool`，Task 3 guard 不触发。Task 3 落地后新增的 `test_get_ui_snapshot_large_output_returns_compact_error` 和 `test_get_ui_snapshot_normal_output_still_returns_controls` 覆盖其行为。

---

## Task 4: Strengthen Guidance Where Models Actually See It

### 问题

The skill was loaded and contained `Context Budget`, but the model still ignored it. Tool descriptions and returned errors are more likely to be followed at the moment of action.

### 文件

- Modify: `computer_use/tools/schemas.py`
- Modify: `computer_use/guidance.py`
- Modify: `skills/computer-use/SKILL.md`
- Modify: `.agents/skills/computer-use/SKILL.md`
- Test: `tests/test_mcp_server.py` or `tests/test_mcp_prompts.py`

### 要求措辞

Add these rules verbatim or near-verbatim:

```text
After start_task, every subsequent executable computer-use tool call must include the returned task_id.
```

```text
Do not use get_ui_snapshot(scope="desktop", include_screenshot=true). It is blocked because it can create huge tool output.
```

```text
Do not repeatedly read PNG screenshots into context. Read only the latest screenshot needed for visual reasoning; after 2-3 image reads or any tool response over 60s, stop and summarize.
```

### 测试

**主要断言（绑定 guard 实际错误契约）**：

- `start_task` 描述包含 `"rejected"` 或 `"must include"`（对应 Task 1 规则措辞）
- `get_ui_snapshot` 描述包含 `"blocked"`（对应 `high_cost_snapshot_blocked`）

**次要断言（词汇检查，较宽松）**：

- 描述中出现 `task_id`、`desktop`、`include_screenshot`、`60s`/`60 seconds`、`PNG` 等关键词

### 验收标准

- The model sees the rule in the tool schema, not only after manually reading skill.
- `.agents` and `skills` copies remain identical.

---

> Task 5（cursor marker detection）已拆分为独立计划，不在本硬化任务范围内。

## 验证

Run these after implementation:

```powershell
& ".venv\Scripts\python.exe" -m pytest tests/test_mcp_server.py tests/test_review.py tests/test_trace.py tests/test_mcp_prompts.py -v
```

Then full suite:

```powershell
& ".venv\Scripts\python.exe" -m pytest tests/ -v
```

Then doc/link checks:

```powershell
python scripts/agent_links.py check
git diff --check
```

Expected:

- full pytest passes, with manual GUI tests skipped unless explicitly enabled
- `agent_links.py check` prints `link group ok (mode=copy)`
- `git diff --check` has no whitespace errors; CRLF warnings are acceptable on Windows

---

## 成功标准（回放失败 session）

If we replay the same behavior pattern:

1. Agent loads `computer-use` skill.
2. Agent calls `start_task`.
3. Agent tries `get_ui_snapshot(scope="desktop", include_screenshot=true)`.

Expected result:

- MCP returns `high_cost_snapshot_blocked`.
- No 9MB tool output is produced.

Then if agent calls:

```json
computer-use_find_control({"name":"原神","scope":"desktop"})
```

without `task_id`, while the explicit task is active.

Expected result:

- MCP returns `missing_task_id`.
- It includes the active task id.
- It does not create a standalone trace.
- It does not execute the tool.

When agent retries with:

```json
{"name":"原神","scope":"desktop","task_id":"task-..."}
```

Expected result:

- Tool executes.
- Trace is registered under the explicit task.
- `review_task_session(task_id, detail=True)` contains the actual steps.

---

## 推荐执行顺序

1. **Task 1 + Task 2 + Task 4**：最小有效闭环。
2. 如果测试通过，再做 **Task 3**。

## 相关文件

**改动目标（相对仓库根）：**
- `computer_use/mcp_server.py`
- `computer_use/task_session.py`
- `computer_use/tools/schemas.py`
- `computer_use/guidance.py`
- `skills/computer-use/SKILL.md`
- `.agents/skills/computer-use/SKILL.md`
- `docs/api.md`
- `docs/pitfalls.md`
- `tests/test_mcp_server.py`

**接口依赖（不修改，仅调用）：**
- `computer_use/task_session.py`（`list_tasks` 等）
- `computer_use/snapshot.py`（`get_ui_snapshot` 等）

---

## 受影响测试汇总

对 `tests/test_mcp_server.py`（9 个 `_handle_tool_call` 站点 + 全部 get_ui_snapshot 相关 `_call_tool` / `_dispatch_tool` 站点）、`tests/test_snapshot.py`（全部直接调用 `snapshot_mod.get_ui_snapshot`，绕过 MCP 层）、`tests/test_runner.py`、`tests/test_core.py` 做了全面扫描后的结果：

| 测试 | 文件:行 | 受哪个 Task 影响 | 修改方式 |
|------|---------|-----------------|---------|
| `test_standalone_context_register_conflict_does_not_leave_active_task` | `test_mcp_server.py:357` | Task 1 | 在 `register_trace(...)` 之后插入 `task_session.finish_task(owner)`，保持 `_handle_tool_call("run_task_plan", ...)` 不带 task_id；详见 Task 1 步骤 5 |
| `test_outer_tool_handler_redacts_exception_response_and_log` | `test_mcp_server.py:2118` | Task 1 | monkeypatch `task_session.task_dir` 到 `tmp_path / "tasks"` 以隔离 task 目录；详见 Task 1 步骤 7 |
| `test_get_ui_snapshot_tool_dispatch` | `test_mcp_server.py:1790` | Task 2 | 将 success-case 参数从 `{scope:desktop, include_screenshot:True}` 改为 `{scope:foreground, include_screenshot:True}`（或 `{scope:desktop, include_screenshot:False}`），同步更新断言；被拦截组合由新增 `test_get_ui_snapshot_blocks_desktop_with_include_screenshot` 覆盖；详见 Task 2 步骤 4 |

**经扫描确认不受影响的测试（含理由）**：

| 测试 | 文件:行 | 原因 |
|------|---------|------|
| `test_missing_task_id_creates_closed_standalone_task` | `test_mcp_server.py:342` | Task 1：已 monkeypatch task_dir，无 active task，guard 通过 |
| `test_batch_registers_only_top_level_trace_for_task` | `test_mcp_server.py:392` | Task 1：已 monkeypatch task_dir，无 active task，guard 通过 |
| `test_task_id_is_not_written_to_trace_args` | `test_mcp_server.py:417` | Task 1：显式传 task_id，guard 通过 |
| `test_batch_capture_snapshot_includes_snapshot` | `test_mcp_server.py:1760` | Task 2/3：batch capture 路径直接调用 `snapshot.get_ui_snapshot(scope="foreground", include_screenshot=False)`（`mcp_server.py:954`），绕过 `_dispatch_tool` |
| `test_exception_logging_redacts_input_values` | `test_mcp_server.py:2098` | Task 1：调用 `_call_tool`（绕过 `_handle_tool_call`），guard 不触发 |
| `test_fail_safe_returns_structured_error_and_trace` | `test_mcp_server.py:2141` | Task 1：调用 `_call_tool`（绕过 `_handle_tool_call`），guard 不触发 |
| `test_handle_review_task_does_not_create_task_context` | `test_mcp_server.py:1986` | Task 1：`review_task` 是 excluded tool |
| `tests/test_snapshot.py` 全部 get_ui_snapshot 测试 | `test_snapshot.py:126-313` | Task 2/3：直接调用 `snapshot_mod.get_ui_snapshot(...)`，绕过 MCP dispatch 层 |
| `tests/test_runner.py` 全部 dispatch 相关测试 | `test_runner.py:24-451` | Task 2/3：monkeypatch `_dispatch_tool` 为 fake，不走真实 guard 逻辑 |
