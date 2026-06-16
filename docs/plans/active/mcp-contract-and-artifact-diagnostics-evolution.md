# MCP Contract and Artifact Diagnostics Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 batch/task 调用难以构造错误工具名，并让执行结果直接、准确地报告 trace 和实际产物，避免 Agent 混淆工具命名空间、目录用途和证据存在性。

**Architecture:** 在 MCP 分发层建立显式工具名契约：Schema 只暴露 canonical tool name，运行时兼容已知 MCP 前缀并规范化，无法识别时返回结构化 `invalid_tool`。在 trace 层提供惰性产物目录与**扁平** `artifact_manifest`（只列真实存在的文件）；batch/run_task_plan/review_task 的响应信封由 manifest **派生**——顶层放 `trace_id/trace_path/artifact_root` 与执行摘要字段，嵌套 `artifacts` 放 `screenshots/snapshots/report`（`report = manifest.report_path or None`）。trace 上下文内按文件类型分流：`screenshots/` 只放截图 PNG，`snapshots/` 只放 UI-tree 结构化 JSON；无 trace 上下文的独立 snapshot 截图回退到全局 `<trace_dir>/snapshots`（`_resolve_snapshot_dir` 既有行为）。文档只描述响应中可验证的路径，不要求 Agent 根据目录名猜测。

**Tech Stack:** Python 3.11+、MCP SDK、pytest、JSONL trace、pathlib、现有 `computer_use.trace` / `computer_use.mcp_server` / `computer_use.snapshot`。

---

## 状态与问题证据

已复现失败 trace：

`C:\Users\chenr\.computer-use\traces\20260615-173349-9lf66b\trace.jsonl`

确认事实：

- batch 动作使用了外部限定名 `computer-use_press_key`，内部只接受 `press_key`，第 0 步返回 `Unknown tool`。
- 该错误被记录为 `error_kind=unknown`，无法区分调用契约错误和执行错误。
- 全局 `<trace_dir>/snapshots/` 是无 trace 上下文时独立 snapshot 截图的回退目录（`_resolve_snapshot_dir` 默认值）；它在历史上既装截图又可能混入其他产物，语义二义。本计划在 trace 上下文中按文件类型分流（截图→`screenshots/`，UI-tree JSON→`snapshots/`，见 Task 4/Task 6），全局回退目录语义保持不变。
- 失败 trace 的 `screenshots/`、`snapshots/` 目录为空，但执行侧 Agent 仍声称“含快照”。
- batch 只返回 `trace_id`，未直接返回 `trace_path` 和实际产物清单，给错误汇报留下空间。

## 范围

包含：

- batch/run_task_plan 内部工具名规范化和 Schema 约束。
- `invalid_tool` 结构化错误及 trace 分类。
- trace 目录惰性创建和实际产物 manifest。
- batch/run_task_plan/review_task 响应中的可验证路径。
- UI snapshot 截图在 trace 上下文中的归属。
- API、部署、陷阱和 bugfix 文档。

不包含：

- 改变 MCP 对外注册工具名称。
- 静默猜测任意拼写错误并继续执行。
- 自动删除历史 trace。
- 引入数据库、LLM 复盘或新的工作流引擎。
- 改变主屏输入、密码输入或截图光标标记等既有产品边界。

## 文件结构与职责

- Create: `computer_use/tool_contract.py`
  - canonical 工具名集合、允许嵌套执行的集合、已知前缀规范化、候选建议。
- Modify: `computer_use/mcp_server.py`
  - Schema 枚举、batch/task 预校验、`invalid_tool` 响应、响应 manifest。
- Modify: `computer_use/trace.py`
  - 惰性目录、trace/artifact 路径查询、实际文件 manifest。
- Modify: `computer_use/snapshot.py`
  - trace 上下文存在时将 snapshot 截图写入对应 trace。
- Modify: `computer_use/runner.py`
  - 自动步骤截图写入 trace 专属目录；任务响应附带 manifest。
- Modify: `tests/test_mcp_server.py`
  - 工具名、Schema、batch 响应和错误分类回归测试。
- Modify: `tests/test_trace.py`
  - 惰性目录与 manifest 测试。
- Modify: `tests/test_runner.py`
  - task 路径与产物归属测试。
- Modify: `tests/test_snapshot.py`
  - snapshot 截图 trace 归属测试。
- Create: `docs/problems/bugfix/batch-tool-contract-and-artifact-reporting.md`
- Modify: `docs/api.md`
- Modify: `docs/overview.md`
- Modify: `docs/deployment.md`
- Modify: `docs/pitfalls.md`
- Modify: `CHANGELOG.md`

---

### Task 1: 建立 canonical 工具名契约

**Files:**
- Create: `computer_use/tool_contract.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: 写工具名规范化 RED 测试**

在 `tests/test_mcp_server.py` 增加：

```python
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("press_key", "press_key"),
        ("computer-use_press_key", "press_key"),
        ("mcp__computer-use__press_key", "press_key"),
    ],
)
def test_normalize_nested_tool_name_accepts_known_names(raw, expected):
    from computer_use.tool_contract import (
        BATCH_ACTION_TOOL_NAMES,
        normalize_nested_tool_name,
    )

    assert normalize_nested_tool_name(
        raw,
        allowed_tools=BATCH_ACTION_TOOL_NAMES,
    ) == expected


def test_normalize_nested_tool_name_rejects_unknown_name():
    from computer_use.tool_contract import (
        BATCH_ACTION_TOOL_NAMES,
        InvalidToolName,
    )

    with pytest.raises(InvalidToolName) as exc:
        normalize_nested_tool_name(
            "computer-use_press_keey",
            allowed_tools=BATCH_ACTION_TOOL_NAMES,
        )

    assert exc.value.requested_tool == "computer-use_press_keey"
    assert "press_key" in exc.value.candidates
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -k "normalize_nested_tool_name" -v
```

Expected: FAIL，`computer_use.tool_contract` 尚不存在。

- [ ] **Step 3: 实现最小工具名契约**

创建 `computer_use/tool_contract.py`：

```python
from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches


ATOMIC_AND_COMPOSITE_TOOL_NAMES = (
    "get_ui_snapshot",
    "screenshot",
    "get_monitors",
    "click",
    "move_to",
    "scroll",
    "type",
    "key_combo",
    "mouse_down",
    "mouse_up",
    "drag",
    "key_down",
    "key_up",
    "press_key",
    "find_control",
    "inspect_point",
    "wait_for_window",
    "wait_for_control",
    "launch_app",
    "sleep",
    "click_by_uid",
    "click_by_text",
    "open_menu",
    "fill_form",
    "scroll_until",
    "retry_step",
    "review_task",
)

# Orchestration tools never valid as a nested action / step.
_ORCHESTRATION_TOOL_NAMES = frozenset({"batch", "run_task_plan"})
# Diagnostic/trace-inspection tools: valid as a task step (a task may review or
# retry), but NOT valid inside a batch action list (a batch is a GUI action
# sequence; mixing in trace-inspection tools expands the contract needlessly).
_DIAGNOSTIC_TOOL_NAMES = frozenset({"retry_step", "review_task"})

BATCH_ACTION_TOOL_NAMES = tuple(
    name
    for name in ATOMIC_AND_COMPOSITE_TOOL_NAMES
    if name not in _DIAGNOSTIC_TOOL_NAMES
)
TASK_STEP_TOOL_NAMES = ATOMIC_AND_COMPOSITE_TOOL_NAMES + ("batch",)
_KNOWN_PREFIXES = ("mcp__computer-use__", "computer-use_")


@dataclass
class InvalidToolName(ValueError):
    requested_tool: str
    candidates: list[str]


def normalize_nested_tool_name(
    raw_name: object,
    *,
    allowed_tools: tuple[str, ...],
) -> str:
    if not isinstance(raw_name, str) or not raw_name:
        raise InvalidToolName(str(raw_name), [])
    candidate = raw_name
    for prefix in _KNOWN_PREFIXES:
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):]
            break
    if candidate in allowed_tools:
        return candidate
    suggestions = get_close_matches(candidate, allowed_tools, n=3, cutoff=0.55)
    raise InvalidToolName(raw_name, suggestions)
```

`run_task_plan` 不进入任何 nested 集合，避免递归；`batch` 只进入 `TASK_STEP_TOOL_NAMES`，因此 task 可包含一层 batch，而 batch action 不可再次包含 batch。`retry_step`/`review_task` 是诊断工具，保留在 `ATOMIC_AND_COMPOSITE_TOOL_NAMES`（task step 仍可调用），但从 `BATCH_ACTION_TOOL_NAMES` 排除（batch 是 GUI 动作序列，不应混入 trace-inspection 工具）。

- [ ] **Step 4: 运行聚焦测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -k "normalize_nested_tool_name" -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add computer_use/tool_contract.py tests/test_mcp_server.py
git commit -m "feat: define nested tool name contract"
```

---

### Task 2: 让 Schema 和运行时共同约束 batch 工具名

**Files:**
- Modify: `computer_use/mcp_server.py`
- Modify: `computer_use/tool_contract.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: 写 Schema、别名执行与注册表一致性 RED 测试**

> 说明：`tests/test_mcp_server.py` 顶部已有 `@pytest.fixture(autouse=True) def _patch_trace_dir(...)`，自动把 `trace_dir` 重定向到 `tmp_path`，下列测试**无需**手动 patch trace 目录。模块顶部已 `from computer_use.mcp_server import TOOLS, _call_tool`；用到 `_batch_tool` 时在函数内 `import computer_use.mcp_server as server`（与现有测试一致）。

```python
def test_batch_schema_enumerates_canonical_tool_names():
    from computer_use.tool_contract import BATCH_ACTION_TOOL_NAMES

    batch = next(tool for tool in TOOLS if tool.name == "batch")
    tool_schema = batch.inputSchema["properties"]["actions"]["items"]["properties"]["tool"]

    assert tool_schema["enum"] == list(BATCH_ACTION_TOOL_NAMES)
    assert "computer-use_press_key" not in tool_schema["enum"]


def test_batch_action_tool_names_match_tools_registry():
    """Guard against drift between the constant and the real TOOLS registry."""
    from computer_use.tool_contract import (
        BATCH_ACTION_TOOL_NAMES,
        _DIAGNOSTIC_TOOL_NAMES,
        _ORCHESTRATION_TOOL_NAMES,
    )

    registered = {tool.name for tool in TOOLS}
    # 每个声明的 batch 工具名必须是真实注册工具。
    assert set(BATCH_ACTION_TOOL_NAMES) <= registered
    # 反向：除编排/诊断工具外，其余注册工具都必须可用于 batch。
    excluded = _ORCHESTRATION_TOOL_NAMES | _DIAGNOSTIC_TOOL_NAMES
    assert set(BATCH_ACTION_TOOL_NAMES) == registered - excluded


def test_batch_normalizes_known_mcp_prefix(monkeypatch):
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(
        server,
        "_call_tool",
        lambda name, args, trace_context=None: calls.append(name) or json.dumps({"pressed": True}),
    )

    result = json.loads(
        server._batch_tool(
            {"actions": [{"tool": "computer-use_press_key", "args": {"key": "Down"}}]},
            trace_id="alias-batch",
        )
    )

    assert calls == ["press_key"]
    assert result["results"][0]["requested_tool"] == "computer-use_press_key"
    assert result["results"][0]["tool"] == "press_key"
```

- [ ] **Step 2: 写非法工具结构化错误 RED 测试**

```python
def test_batch_returns_invalid_tool_with_candidates():
    import computer_use.mcp_server as server

    result = json.loads(
        server._batch_tool(
            {"actions": [{"tool": "computer-use_press_keey", "args": {"key": "Down"}}]},
            trace_id="invalid-tool-batch",
        )
    )

    failure = result["results"][0]["result"]
    assert failure["error"] == "invalid_tool"
    assert failure["requested_tool"] == "computer-use_press_keey"
    assert "press_key" in failure["candidates"]
    assert result["failed_index"] == 0
```

- [ ] **Step 3: 运行并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -k "batch_schema_enumerates or batch_action_tool_names_match or batch_normalizes or invalid_tool" -v
```

Expected: FAIL。真正的 RED 是 `batch_schema_enumerates`（当前 Schema 为普通字符串）、`batch_normalizes`/`invalid_tool`（batch 不规范化名称）。`batch_action_tool_names_match_tools_registry` 是**漂移守卫**——常量在 Task 1 Step 3 已正确定义，故它此时即 PASS（其作用是防未来新增/移除工具时静默漂移，不是当前 RED）。

- [ ] **Step 4: 修改 Schema 和 batch 预校验**

在 `mcp_server.py` 导入：

```python
from computer_use.tool_contract import (
    InvalidToolName,
    BATCH_ACTION_TOOL_NAMES,
    normalize_nested_tool_name,
)
```

将 `actions[].tool` 改为：

```python
"tool": {
    "type": "string",
    "enum": list(BATCH_ACTION_TOOL_NAMES),
    "description": "Canonical nested tool name. Do not use MCP namespace prefixes.",
}
```

在 `_batch_tool` 每步开始时规范化：

```python
requested_tool = action.get("tool")
try:
    tool_name = normalize_nested_tool_name(
        requested_tool,
        allowed_tools=BATCH_ACTION_TOOL_NAMES,
    )
except InvalidToolName as exc:
    result_data = {
        "error": "invalid_tool",
        "requested_tool": exc.requested_tool,
        "candidates": exc.candidates,
        "allowed_tools": list(BATCH_ACTION_TOOL_NAMES),
    }
    results.append({
        "index": i,
        "tool": None,
        "requested_tool": requested_tool,
        "result": result_data,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    })
    failed_index = i
    if stop_on_error:
        break
    continue
```

成功步骤同时返回 `requested_tool` 和 canonical `tool`，只在两者不同或为保持固定响应结构时保留该字段。

删除 `_batch_tool` 中旧的显式嵌套拒绝（mcp_server.py:1199 `if tool_name in {"batch", "run_task_plan"}`）——`batch`/`run_task_plan` 均不在 `BATCH_ACTION_TOOL_NAMES`，规范化阶段已统一转为 `invalid_tool`，旧分支冗余。

- [ ] **Step 5: 为 runner nested tool 规范化写 RED 测试（在 test_runner.py）**

> `tests/test_runner.py` 同样有 `@pytest.fixture(autouse=True) def _patch_trace_dir(...)`，无需手动 patch。

当前 `runner._validate_task_steps`（runner.py:28-51）对嵌套 `run_task_plan`/嵌套 batch 直接 `raise ValueError`，且 `test_run_task_plan_rejects_nested_run_task_plan`（test_runner.py:346）和 `test_run_task_plan_rejects_run_task_plan_inside_batch`（test_runner.py:363）都断言 `pytest.raises(ValueError, match="run_task_plan")`。本步改为：工具名契约错误（嵌套 run_task_plan、未知名、已知前缀）走与 batch 一致的结构化 `invalid_tool` 结果项，而**非**抛异常。

先新增 RED 测试（覆盖规范化在前）：

```python
def test_run_task_plan_normalizes_known_mcp_prefix_step(monkeypatch):
    import computer_use.mcp_server as server

    seen = []

    def fake_dispatch_tool(name, args, cs, trace_id=None, parent_step_index=None):
        seen.append(name)
        return json.dumps({"called": name})

    monkeypatch.setattr(server, "_dispatch_tool", fake_dispatch_tool)

    result = runner_mod.run_task_plan(
        steps=[{"tool": "computer-use_press_key", "args": {"key": "Down"}}],
        trace_id="runner-alias",
        goal="normalize",
        capture_screenshots=False,
    )

    assert seen == ["press_key"]
    assert result["results"][0]["requested_tool"] == "computer-use_press_key"
    assert result["results"][0]["tool"] == "press_key"


def test_run_task_plan_step_unknown_tool_returns_invalid_tool():
    result = runner_mod.run_task_plan(
        steps=[{"tool": "computer-use_press_keey", "args": {}}],
        trace_id="runner-invalid",
        capture_screenshots=False,
    )

    assert result["failed_index"] == 0
    failure = result["results"][0]["result"]
    assert failure["error"] == "invalid_tool"
    assert "press_key" in failure["candidates"]
```

> 注：`status`/`executed_count`/`requested_count` 摘要字段在 Task 7 才加入，此处只断言 Task 2 产出的 `failed_index` + `invalid_tool` 结果项形状。

同时把两个现有断言改为断言结构化 `invalid_tool` 返回（理由：嵌套 `run_task_plan` 不在 `TASK_STEP_TOOL_NAMES` 中，规范化会抛 `InvalidToolName`，与 batch 一样转为 `invalid_tool` 结果项；不再用前置 `ValueError` 提前中止）：

- `test_run_task_plan_rejects_nested_run_task_plan`（test_runner.py:346）：删除 `with pytest.raises(ValueError, match="run_task_plan"):`，改为调用 `run_task_plan(...)` 取 `result`，断言 `result["failed_index"] == 0`、`result["results"][0]["result"]["error"] == "invalid_tool"`、`"run_task_plan" in result["results"][0]["result"]["candidates"]`。
- `test_run_task_plan_rejects_run_task_plan_inside_batch`（test_runner.py:363）：同样删除 `raises(ValueError)`。此例 step 0 是 batch，batch 内 action `run_task_plan` 在 batch 规范化阶段被拒（不在 `BATCH_ACTION_TOOL_NAMES`）。断言 `result["failed_index"] == 0`，且嵌套的 batch 响应中失败 action 为 `invalid_tool`：`result["results"][0]["result"]["results"][0]["result"]["error"] == "invalid_tool"`。

- [ ] **Step 6: 对 run_task_plan 使用同一规范化函数（impl）**

修改 `runner.run_task_plan`：在每个 step 执行前调用 `normalize_nested_tool_name(tool_name, allowed_tools=TASK_STEP_TOOL_NAMES)`。

- 成功规范化后，step 结果项增加 `requested_tool`（原始名）与 `tool`（canonical 名）字段（与 batch 一致），后续用 canonical 名执行。
- 捕获 `InvalidToolName` 时，构造与 batch 相同形状的 `invalid_tool` 结果项（`result={"error":"invalid_tool","requested_tool":...,"candidates":...,"allowed_tools":list(TASK_STEP_TOOL_NAMES)}`），置 `failed_index` 并 `break`。

同时把 `runner._validate_task_steps` 中的嵌套拒绝**移除**，改由 per-step 规范化处理（保留其余职责）：

- 删除 `if tool_name == "run_task_plan": raise ValueError(...)`（runner.py:34-35）。
- 删除 batch action 循环里的 `if nested_tool in {"batch", "run_task_plan"}: raise ValueError(...)`（runner.py:42-45），但**保留** `expanded_steps += len(actions)` 的预算计数。
- 保留 missing `'tool'` 仍 `raise ValueError`（runner.py:32-33）、step budget 超限仍 `raise ValueError`（runner.py:48-51）——二者是结构性/资源约束，不是工具名契约错误，不映射为 `invalid_tool`。

- [ ] **Step 7: 运行聚焦测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py tests/test_runner.py -k "batch or task_plan or invalid_tool or normalizes" -v
```

Expected: PASS。

- [ ] **Step 8: 提交**

```powershell
git add computer_use/tool_contract.py computer_use/mcp_server.py computer_use/runner.py tests/test_mcp_server.py tests/test_runner.py
git commit -m "feat: validate nested tool names"
```

---

### Task 3: 增加 `invalid_tool` 失败分类

**Files:**
- Modify: `computer_use/mcp_server.py`
- Modify: `computer_use/trace.py`
- Test: `tests/test_mcp_server.py`
- Test: `tests/test_trace.py`

> `review.py` 无需改动：其 `error_distribution` 已对任意 `error_kind` 计数（review.py:42-45），`invalid_tool` 自动覆盖；响应 manifest 在 `_call_tool` 边界由 `_attach_trace_manifest` 附加，不经 review.py。

- [ ] **Step 1: 写错误分类 RED 测试**

> autouse `_patch_trace_dir` 已重定向 trace_dir，无需手动 patch。

```python
def test_invalid_tool_is_recorded_with_dedicated_error_kind():
    import computer_use.mcp_server as server
    import computer_use.trace as trace_module

    result = json.loads(
        server._call_tool(
            "batch",
            {"actions": [{"tool": "computer-use_press_keey", "args": {}}]},
        )
    )
    records = trace_module.read_trace(result["trace_id"])

    assert result["results"][0]["result"]["error"] == "invalid_tool"
    assert records[-1]["error_kind"] == "invalid_tool"
```

- [ ] **Step 2: 运行并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py tests/test_trace.py -k "invalid_tool" -v
```

Expected: FAIL，当前映射降级为 `unknown`。

- [ ] **Step 3: 扩展统一错误映射**

在 `_error_kind_for_result` 中加入：

```python
if error_value == "invalid_tool":
    return "invalid_tool"
```

更新 `TraceRecord.error_kind` 文档、report/review 允许值和 API 文档。禁止用异常文本 `"Unknown tool: ..."` 反推分类。

- [ ] **Step 4: 运行聚焦测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py tests/test_trace.py -k "invalid_tool or error_kind" -v
git add computer_use/mcp_server.py computer_use/trace.py tests/test_mcp_server.py tests/test_trace.py
git commit -m "fix: classify invalid nested tools"
```

---

### Task 4: 惰性创建 trace 产物目录

**Files:**
- Modify: `computer_use/trace.py`
- Modify: `computer_use/mcp_server.py`（调用点：`_save_ui_snapshot` mcp_server.py:1151-1159）
- Modify: `computer_use/runner.py`（调用点：`_step_screenshot` runner.py:54-77）
- Test: `tests/test_trace.py`

> 下列测试在 `tests/test_trace.py` 中，使用该模块真实 fixture `tmp_trace_dir`（显式参数，非 autouse）。

- [ ] **Step 1: 写空 trace 不创建假产物目录的 RED 测试**

```python
def test_trace_root_does_not_precreate_artifact_directories(tmp_trace_dir):
    root = trace.trace_root("empty-artifacts")

    assert root.is_dir()
    assert not (root / "screenshots").exists()
    assert not (root / "snapshots").exists()
```

- [ ] **Step 2: 写按需目录 helper 测试**

```python
def test_artifact_dir_creates_only_requested_kind(tmp_trace_dir):
    screenshots = trace.artifact_dir("lazy-artifacts", "screenshots")

    assert screenshots.is_dir()
    assert not (screenshots.parent / "snapshots").exists()
```

- [ ] **Step 3: 实现惰性目录**

将 `trace_root`（trace.py:67-74）改为只创建 root（删除其内部 `(root/"screenshots").mkdir(...)` 和 `(root/"snapshots").mkdir(...)`）：

```python
def trace_root(trace_id: str) -> Path:
    validate_trace_id(trace_id)
    root = trace_dir() / trace_id
    root.mkdir(parents=True, exist_ok=True)
    return root
```

新增：

```python
_ARTIFACT_KINDS = {"screenshots", "snapshots"}


def artifact_dir(trace_id: str, kind: str) -> Path:
    if kind not in _ARTIFACT_KINDS:
        raise ValueError(f"Invalid artifact kind: {kind}")
    path = trace_root(trace_id) / kind
    path.mkdir(parents=True, exist_ok=True)
    return path
```

迁移现有直接 `trace_root(trace_id)/<kind>` 的调用点（全部枚举，避免遗漏）：

- `_save_ui_snapshot`（mcp_server.py:1151-1159）：`snapshot_dir = root / "snapshots"; snapshot_dir.mkdir(...)` 改为 `snapshot_dir = trace_module.artifact_dir(trace_id, "snapshots")`。注意 `_save_ui_snapshot` 写的是 UI-tree **JSON**，归类 `snapshots/`（与 B5 一致）。
- `_step_screenshot`（runner.py:54-77）当前用配置的 `screenshot_dir`；本 Task 暂不迁移它（Task 6 Step 3 才把它改为 trace 内 `screenshots/`）。

- [ ] **Step 4: 运行测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trace.py tests/test_mcp_server.py tests/test_runner.py -v
git add computer_use/trace.py computer_use/mcp_server.py computer_use/runner.py tests/test_trace.py tests/test_mcp_server.py tests/test_runner.py
git commit -m "refactor: create trace artifacts lazily"
```

---

### Task 5: 提供权威 trace artifact manifest

**Files:**
- Modify: `computer_use/trace.py`
- Modify: `computer_use/mcp_server.py`
- Modify: `computer_use/runner.py`
- Test: `tests/test_trace.py`
- Test: `tests/test_mcp_server.py`
- Test: `tests/test_runner.py`

> `review.py` 不改：响应 manifest 在 `_call_tool` 边界由 `_attach_trace_manifest` 附加，review_task 的返回经同一边界自动获得 envelope。

- [ ] **Step 1: 写 manifest RED 测试（扁平结构）**

> 在 `tests/test_trace.py` 中，使用 `tmp_trace_dir` fixture。断言**扁平** manifest 形状——manifest 是 source of truth，响应信封由它派生（见 Step 3）。

```python
def test_artifact_manifest_lists_only_existing_files(tmp_trace_dir):
    root = trace.trace_root("manifest")
    trace.record_step("manifest", 0, "click", {})
    screenshot = trace.artifact_dir("manifest", "screenshots") / "step.png"
    screenshot.write_bytes(b"png")

    manifest = trace.artifact_manifest("manifest")

    assert manifest == {
        "trace_id": "manifest",
        "artifact_root": str(root),
        "trace_path": str(root / "trace.jsonl"),
        "report_path": None,
        "screenshots": [str(screenshot)],
        "snapshots": [],
    }
```

- [ ] **Step 2: 实现 manifest**

```python
def artifact_manifest(trace_id: str) -> dict[str, Any]:
    root = trace_dir() / validate_trace_id(trace_id)
    trace_path = root / "trace.jsonl"
    report_path = root / "report.md"

    def files(kind: str) -> list[str]:
        directory = root / kind
        if not directory.is_dir():
            return []
        return [str(path) for path in sorted(directory.iterdir()) if path.is_file()]

    return {
        "trace_id": trace_id,
        "artifact_root": str(root),
        "trace_path": str(trace_path) if trace_path.is_file() else None,
        "report_path": str(report_path) if report_path.is_file() else None,
        "screenshots": files("screenshots"),
        "snapshots": files("snapshots"),
    }
```

manifest 只报告真实存在的文件，不根据目录存在推断。**manifest 是扁平 dict，作为唯一 source of truth；响应信封（Step 3）由它派生，不另扫目录。**

- [ ] **Step 3: 响应信封由 manifest 派生（明确映射）**

manifest（扁平，键 `report_path`）与响应信封（嵌套 `artifacts`，键 `report`）的字段映射如下，避免 executor 猜测：

| manifest（扁平） | 响应信封位置 |
|---|---|
| `trace_id` | 顶层 `trace_id` |
| `trace_path` | 顶层 `trace_path` |
| `artifact_root` | 顶层 `artifact_root` |
| `screenshots` | `artifacts.screenshots` |
| `snapshots` | `artifacts.snapshots` |
| `report_path` | `artifacts.report`（值为 `report_path or None`） |

响应最终形状（batch/run_task_plan/review_task 一致）：

```json
{
  "trace_id": "...",
  "trace_path": "...\\trace.jsonl",
  "artifact_root": "...\\<trace_id>",
  "status": "failed",
  "failed_index": 0,
  "error_kind": "invalid_tool",
  "executed_count": 1,
  "requested_count": 1,
  "artifacts": {
    "screenshots": [],
    "snapshots": [],
    "report": null
  }
}
```

`status`/`failed_index`/`error_kind`/`executed_count`/`requested_count` 由 Task 7 补全；本 Step 只保证顶层路径字段 + 嵌套 `artifacts` 由 manifest 派生。

- [ ] **Step 4: 实现 `_attach_trace_manifest` 派生 helper（在 _call_tool 边界）**

batch 父记录由 `_call_tool` 在 `_batch_tool` 返回后写入，因此 `_batch_tool` 内首次生成的 manifest 可能尚无父记录。统一在 `_call_tool` 完成 `record_step` 之后、返回之前调用：

```python
_MANIFEST_TOOL_NAMES = {"batch", "run_task_plan", "review_task"}


def _attach_trace_manifest(data: dict[str, Any], trace_id: str) -> dict[str, Any]:
    """从扁平 manifest 派生响应信封（顶层路径 + 嵌套 artifacts）。"""
    if not isinstance(data, dict):
        return data
    manifest = trace_module.artifact_manifest(trace_id)
    data["trace_id"] = manifest["trace_id"]
    data["trace_path"] = manifest["trace_path"]
    data["artifact_root"] = manifest["artifact_root"]
    data["artifacts"] = {
        "screenshots": manifest["screenshots"],
        "snapshots": manifest["snapshots"],
        "report": manifest["report_path"],
    }
    return data
```

在 `_call_tool`（mcp_server.py，`record_step` 之后）接入：

```python
if name in _MANIFEST_TOOL_NAMES and isinstance(data, dict):
    data = _attach_trace_manifest(data, trace_id)
```

这样 batch/run_task_plan/review_task 三个工具共用同一份 manifest 派生逻辑，不在三处分别扫描目录。Task 5 Step 1 断言**扁平** manifest、Task 7 Step 1 断言**嵌套** envelope，二者通过此派生关系一致。

- [ ] **Step 5: 运行测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trace.py tests/test_mcp_server.py tests/test_runner.py -k "manifest or artifact or trace_path or batch or task_plan or review" -v
git add computer_use/trace.py computer_use/mcp_server.py computer_use/runner.py tests/test_trace.py tests/test_mcp_server.py tests/test_runner.py
git commit -m "feat: return trace artifact manifests"
```

---

### Task 6: 将自动截图和 UI snapshot 绑定 trace

**Files:**
- Modify: `computer_use/mcp_server.py`
- Modify: `computer_use/runner.py`
- Modify: `computer_use/snapshot.py`
- Test: `tests/test_snapshot.py`
- Test: `tests/test_runner.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: 写 snapshot trace 归属 RED 测试**

> 在 `tests/test_snapshot.py` 中。该模块**没有** trace_dir autouse fixture，故直接 `monkeypatch.setattr(trace_module, "trace_dir", ...)`；UIA 用该模块真实 helper `_fake_tree`（fixture）+ `_stub_process_name`（函数），**不存在** `_stub_uia`。`save_screenshot`/`get_monitors` 也需 stub（与既有 `test_get_ui_snapshot_includes_screenshot` 一致）。
>
> B5：截图 PNG 必须落到 `screenshots/`，**不是** `snapshots/`（`snapshots/` 留给 UI-tree JSON）。

```python
def test_get_ui_snapshot_screenshot_uses_trace_screenshots_dir(
    monkeypatch, tmp_path, _fake_tree
):
    import computer_use.trace as trace_module
    from computer_use import snapshot as snapshot_mod
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    _stub_process_name(monkeypatch)
    snapshot_mod.uia = MagicMock()
    snapshot_mod.uia.GetForegroundControl.return_value = _fake_tree
    monkeypatch.setattr(snapshot_mod.pyautogui, "position", lambda: (0, 0))
    monkeypatch.setattr(snapshot_mod, "save_screenshot", lambda path, monitor=0: path)
    monkeypatch.setattr(
        snapshot_mod,
        "get_monitors",
        lambda: [SimpleNamespace(index=1, primary=True, left=0, top=0, width=1920, height=1080)],
    )

    result = snapshot_mod.get_ui_snapshot(
        scope="foreground",
        include_screenshot=True,
        trace_id="snapshot-trace",
    )

    assert Path(result["screenshot_path"]).parent == (
        tmp_path / "snapshot-trace" / "screenshots"
    )
```

- [ ] **Step 2: 扩展 snapshot API 的内部 trace 参数（截图分流到 screenshots/）**

```python
def get_ui_snapshot(
    scope: str = "foreground",
    include_screenshot: bool = False,
    save_path: str | None = None,
    snapshot_dir: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
```

截图 PNG 目录优先级（仅 `include_screenshot=True` 时生效）：

1. 显式 `save_path`
2. 显式 `snapshot_dir`
3. `trace_id` 对应 `trace_module.artifact_dir(trace_id, "screenshots")`（**注意是 `screenshots`**）
4. 无 trace 上下文时回退全局 `<trace_dir>/snapshots`（`_resolve_snapshot_dir` 既有默认，保持不变）

> 区分两层语义：trace 内按文件类型分目录（截图→`screenshots/`）；无 trace 的全局回退目录仍叫 `snapshots/`（历史行为，不改）。

- [ ] **Step 3: 自动 task 截图写入 trace**

将 `runner._step_screenshot`（runner.py:54-77）从配置的全局 `screenshot_dir` 改为：

```python
screenshot_dir = trace_module.artifact_dir(trace_id, "screenshots")
```

用户显式调用 `screenshot` 工具仍遵循配置的 `screenshot_dir`，不改变现有保存契约；只有任务自动截图绑定 trace。

- [ ] **Step 4: 分发层传递 trace_id（+ 更新现有 snapshot fake 签名）**

`_dispatch_tool("get_ui_snapshot", ...)`（mcp_server.py:745-750）改为透传 `trace_id`：

```python
snapshot.get_ui_snapshot(
    scope,
    include_screenshot,
    trace_id=trace_id,
)
```

batch `capture_snapshot`（mcp_server.py:1188-1195）产生的 UI-tree **JSON** 经 `_save_ui_snapshot` 继续写入 `<trace_id>/snapshots`（JSON 归类 `snapshots/`，与 B5 一致）。

> **S1 必改**：Task 6 Step 4 给 `get_ui_snapshot` 增加了 `trace_id=` kwarg，`tests/test_mcp_server.py` 的两个 snapshot fake 签名（`test_batch_capture_snapshot_includes_snapshot` 中的 fake，约 :1387；`test_get_ui_snapshot_tool_dispatch` 中的 fake，约 :1417）当前为 `def fake_get_ui_snapshot(scope, include_screenshot):`，会因意外 kwarg 抛 `TypeError`。把二者签名改为 `def fake_get_ui_snapshot(scope, include_screenshot, trace_id=None):`（或加 `**kwargs`）。

- [ ] **Step 5: 运行测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_snapshot.py tests/test_runner.py tests/test_mcp_server.py -k "snapshot or screenshot or artifact" -v
git add computer_use/snapshot.py computer_use/runner.py computer_use/mcp_server.py tests/test_snapshot.py tests/test_runner.py tests/test_mcp_server.py
git commit -m "feat: bind automatic artifacts to traces"
```

---

### Task 7: 强化执行结果摘要，避免 Agent 误报

**Files:**
- Modify: `computer_use/mcp_server.py`
- Modify: `computer_use/runner.py`
- Test: `tests/test_mcp_server.py`
- Test: `tests/test_runner.py`

- [ ] **Step 1: 写失败摘要 RED 测试**

> 经 `_call_tool("batch", ...)` 调用，使 Task 5 的 `_attach_trace_manifest` 在 `_call_tool` 边界附加 envelope（`trace_path`/`artifact_root`/嵌套 `artifacts`）。autouse `_patch_trace_dir` 已重定向 trace_dir。`bad_tool` 不在 `BATCH_ACTION_TOOL_NAMES`，规范化即转为 `invalid_tool`。

```python
def test_batch_response_exposes_authoritative_failure_summary():
    import computer_use.mcp_server as server

    result = json.loads(
        server._call_tool(
            "batch",
            {"actions": [{"tool": "bad_tool", "args": {}}]},
        )
    )

    assert result["status"] == "failed"
    assert result["failed_index"] == 0
    assert result["error_kind"] == "invalid_tool"
    assert result["executed_count"] == 1
    assert result["requested_count"] == 1
    assert result["artifacts"]["screenshots"] == []
    assert result["artifacts"]["snapshots"] == []
    assert result["artifacts"]["report"] is None
    assert result["trace_path"] is not None
```

- [ ] **Step 2: 实现固定摘要字段**

`_batch_tool` / `run_task_plan` 最终响应增加这些**摘要**字段（在工具内部即可计算）：

```python
{
    "status": "failed" if failed_index is not None else "succeeded",
    "failed_index": failed_index,
    "error_kind": top_level_error_kind,
    "executed_count": len(results),
    "requested_count": len(actions),
}
```

`error_kind` 从失败步骤的结构化结果提取，不从文本猜测；成功时为 `None`。`trace_path`/`artifact_root`/嵌套 `artifacts` 仍由 Task 5 的 `_attach_trace_manifest`（在 `_call_tool` 边界）派生，不在此重复。

- [ ] **Step 3: 保持 stop_on_error 语义清晰**

当 `stop_on_error=true` 时，`executed_count` 是实际执行/拒绝的动作数，不是请求动作总数。另返回 `requested_count=len(actions)`，便于 Agent准确表述“第 0 步失败，后续 7 步未执行”。

- [ ] **Step 4: 运行测试并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py tests/test_runner.py -k "summary or failed_index or stop_on_error" -v
git add computer_use/mcp_server.py computer_use/runner.py tests/test_mcp_server.py tests/test_runner.py
git commit -m "feat: add authoritative execution summaries"
```

---

### Task 8: 文档、缺陷记录与迁移说明

**Files:**
- Create: `docs/problems/bugfix/batch-tool-contract-and-artifact-reporting.md`
- Modify: `docs/api.md`
- Modify: `docs/overview.md`
- Modify: `docs/deployment.md`
- Modify: `docs/pitfalls.md`
- Modify: `STRUCTURE.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 创建结构化 bugfix 文档**

front matter 至少包含：

```yaml
---
id: bugfix-batch-tool-contract-and-artifact-reporting
type: bugfix
title: Batch 工具名与 Trace 产物报告不明确
status: fixed
severity: high
scope: [backend, api, observability]
modules: [mcp-server, runner, trace, snapshot]
tags: [batch, trace, artifacts, tool-name, diagnostics]
symptoms:
  - 外部限定工具名在 batch 内返回 Unknown tool
  - 空产物目录被误报为存在截图或快照
  - 执行侧无法从响应直接定位 trace.jsonl
related_files:
  - computer_use/tool_contract.py
  - computer_use/mcp_server.py
  - computer_use/trace.py
  - computer_use/runner.py
  - computer_use/snapshot.py
verification:
  level: automated
  kind: regression-test
  path: tests/test_mcp_server.py
  command: .\.venv\Scripts\python.exe -m pytest tests/ -q
created_at: 2026-06-16
updated_at: 2026-06-16
---
```

正文按“现在的行为、预期的行为、复现方式、原因是什么、怎么修复的、验证结果、风险和后续”填写，只记录最终机制。

- [ ] **Step 2: 更新 API 契约**

明确：

- batch `tool` 使用 canonical name，Schema enum 是权威集合；`BATCH_ACTION_TOOL_NAMES` 排除诊断工具（`retry_step`/`review_task`）。
- 已知 MCP 前缀会规范化，但响应同时报告 `requested_tool` 和 canonical `tool`。
- 非法名称（含嵌套 `run_task_plan`）返回 `invalid_tool`、候选和 allowed tools。
- `trace_path` 是操作轨迹；`artifacts`（嵌套）由扁平 `artifact_manifest` 派生：`artifacts.screenshots`=截图 PNG 列表，`artifacts.snapshots`=UI-tree JSON 列表，`artifacts.report`=`report_path or None`。
- trace 上下文内：截图 PNG→`<trace_id>/screenshots/`，UI-tree JSON→`<trace_id>/snapshots/`；无 trace 上下文的独立 snapshot 截图回退到全局 `<trace_dir>/snapshots`（`_resolve_snapshot_dir` 默认），二者语义不同，不得混淆。
- 所有时间戳为 UTC ISO 8601；本地文件时间由操作系统显示。

- [ ] **Step 3: 更新设计与部署**

`overview.md` 记录“响应即证据”的设计决策：调用方不扫描目录推断状态。

`deployment.md` 记录 trace 生命周期和磁盘清理边界。

`pitfalls.md` 增加“外部 MCP 名称与 nested canonical name”和“空目录不是产物证据”。

- [ ] **Step 4: 更新索引和 CHANGELOG**

```powershell
python scripts/changelog.py add --title "fix: 强化 batch 契约与 trace 产物报告" --body "..."
```

- [ ] **Step 5: 文档审计**

```powershell
python scripts/audit.py check
python scripts/agent_links.py check
```

Expected: 无 `[DEAD]`、`[DRIFT]`、`[UNDOC]`、`[ORPHAN]`、`[BROKEN]`。

- [ ] **Step 6: 提交**

```powershell
git add docs STRUCTURE.md CHANGELOG.md
git commit -m "docs: define trace artifact reporting contract"
```

---

### Task 9: 完整验收与真实失败样例回归

**Files:**
- Modify if needed: tests listed above only
- Move after acceptance: `docs/plans/active/mcp-contract-and-artifact-diagnostics-evolution.md` to `docs/plans/completed/`
- Modify: `docs/CURRENT.md`

- [ ] **Step 1: 重放原始错误形式**

调用 batch：

```json
{
  "actions": [
    {"tool": "computer-use_press_key", "args": {"key": "Down"}}
  ]
}
```

Expected:

- 请求规范化为 `press_key`。
- 响应包含 `requested_tool=computer-use_press_key`、`tool=press_key`。
- 若当前输入安全允许，则执行成功；若安全阻断，则错误为安全错误，不再是 unknown tool。

- [ ] **Step 2: 验证真正非法名称**

```json
{
  "actions": [
    {"tool": "computer-use_press_keey", "args": {"key": "Down"}}
  ]
}
```

Expected:

- `status=failed`
- `failed_index=0`
- `error_kind=invalid_tool`
- `executed_count=1`
- `requested_count=1`
- candidates 含 `press_key`
- `trace_path` 指向真实存在的 `trace.jsonl`
- `artifacts.screenshots=[]`
- `artifacts.snapshots=[]`
- 不创建空的 screenshots/snapshots 目录

- [ ] **Step 3: 验证含快照 batch**

执行一个 `capture_snapshot=true` 的安全只读动作。

Expected:

- `artifacts.snapshots` 至少包含一个真实存在的 JSON 文件。
- 响应路径与 trace 记录一致。
- 不需要扫描 `<trace_dir>/snapshots` 猜测归属。

- [ ] **Step 4: 运行完整自动化测试**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
.\.venv\Scripts\python.exe -m compileall -q computer_use
git diff --check
```

Expected: 全部通过；真实桌面截图测试仅在既有环境变量未启用时跳过。

- [ ] **Step 5: 独立 reviewer 验收**

Reviewer 必须检查：

- 错误工具名不能再落为 `unknown`。
- Schema、运行时规范化和响应 canonical name 一致。
- artifacts 只列真实文件。
- trace/snapshot/screenshot 目录语义在代码与文档一致。
- 没有改变输入安全边界。

- [ ] **Step 6: 归档计划**

Reviewer 通过后：

```powershell
Move-Item docs/plans/active/mcp-contract-and-artifact-diagnostics-evolution.md docs/plans/completed/
```

更新 `docs/CURRENT.md` 为无进行中任务。

---

## 验收标准

- batch 与 run_task_plan 的 nested tool Schema 使用 canonical enum。
- `press_key`、`computer-use_press_key`、`mcp__computer-use__press_key` 规范化为同一工具。
- 未知或拼错名称返回 `invalid_tool`，包含 requested name、候选和 allowed tools。
- 嵌套 `run_task_plan`（作为 step 或 batch action）返回结构化 `invalid_tool`，而非抛 `ValueError`。
- `BATCH_ACTION_TOOL_NAMES` 与真实 `TOOLS` 注册表一致（双向：无 stale 常量、新增工具不被静默漏掉），有 `test_batch_action_tool_names_match_tools_registry` 守护。
- trace 中的 `error_kind` 不再将契约错误记为 `unknown`。
- trace root 不预建空产物目录。
- batch/run_task_plan/review_task 返回真实 `trace_path` 和由扁平 manifest 派生的嵌套 `artifacts` envelope。
- artifacts 只列出实际存在的文件；空目录不能被解释为已有证据。
- trace 上下文内按文件类型分流：截图 PNG→`screenshots/`，UI-tree JSON→`snapshots/`；task 自动截图、batch capture_snapshot JSON 和 snapshot 截图各自归位。
- 响应能准确说明成功/失败、失败步骤、实际执行数（`executed_count`）和请求数（`requested_count`）。
- 文档明确 trace、snapshot、screenshot 三类路径的语义及时区。
- 完整测试通过，且不改变主屏输入、密码输入、敏感目标检查和截图光标标记行为。

## 风险与取舍

- Schema enum 与工具注册表可能漂移。实现时必须由同一常量生成 nested enum，并添加集合一致性测试（Task 2 Step 1 的 `test_batch_action_tool_names_match_tools_registry`，双向断言）。
- 兼容已知前缀会隐藏部分调用侧错误，因此响应必须保留 `requested_tool`；只规范化精确定义的前缀，不做任意模糊自动执行。
- 将自动产物绑定 trace 会改变其磁盘位置，需要在文档中明确；用户显式 `screenshot` 的 `screenshot_dir` 契约保持不变。
- B5 改变了 snapshot 截图在 trace 上下文中的落点（从 `snapshots/` 改到 `screenshots/`）。`retry_step`/`review_task` 等历史代码若曾假设 snapshot 截图在 `snapshots/`，需在 Task 6 一并核对（目前无此类假设）。
- manifest 扫描会增加少量文件系统访问，但每个 trace 的产物规模受步骤预算限制，可接受。
- 全局回退目录 `<trace_dir>/snapshots`（无 trace 上下文时）历史文件不迁移、不删除；仅在 trace 上下文内停止向 `snapshots/` 写截图（改写 `screenshots/`）。两层语义（全局回退 vs trace 内按类型分目录）须在文档区分。
