# Business Task Session Trace Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **完成记录（2026-06-16）**：已实施并归档。最终验证：专项测试 `155 passed, 1 skipped`；完整测试 `307 passed, 1 skipped`；`python -m compileall -q computer_use`、`git diff --check`、`python scripts/agent_links.py check`、`python scripts/audit.py check` 均通过。安全手工 MCP 验证使用临时 `trace_dir/task_dir` 和 `sleep` 观察调用完成，模拟重启后 A/B/standalone 三个 task 均可按 `task_id` 查询和复盘，trace 数量分别为 2/1/1，未串任务。执行中发现并修复 `task_dir` 配置未加载问题，见 `docs/problems/bugfix/task-dir-config-not-loaded.md`。

**Goal:** 为一天内连续执行的多个业务任务建立明确、可查询、可审计的任务会话边界，使每条 trace 都能回答“属于哪个业务任务、该任务执行了哪些调用、最终状态如何、证据在哪里”。

**Architecture:** 保留 trace 作为一次顶层工具调用的执行记录，在其上新增显式 `task_id` 业务任务会话。trace 按本地业务日期物理分区，task 目录保存生命周期元数据和 trace 归属文件；通过按 ID 哈希命名的可重建定位索引支持自定义 ID、跨日任务和旧扁平目录兼容。MCP 不维护进程全局“当前任务”，调用方通过显式 `task_id` 跨回合关联；未提供 `task_id` 时自动创建并完成 standalone task。

**Tech Stack:** Python 3.11+、MCP SDK、pytest、JSON/JSONL、pathlib、SHA-256 定位索引、现有 `computer_use.trace` / `computer_use.mcp_server` / `computer_use.runner`。

---

## 状态与实施门禁

本计划独立于正在审计的：

`docs/plans/active/mcp-contract-and-artifact-diagnostics-evolution.md`

两份计划都会修改 `computer_use/trace.py`、`computer_use/mcp_server.py`、`computer_use/runner.py` 和相关测试，因此：

- 本计划可以独立审计，但不得与前一计划并行实施。
- 推荐先完成 MCP 契约与产物诊断计划，再以其最终接口为基线实施本计划。
- 实施前重新读取前一计划的完成版本和实际代码，不机械套用本计划中的旧行号或旧函数形态。
- 前一计划提供的 artifact manifest 负责回答“本次调用产生了什么”；本计划负责回答“这些调用属于哪个业务任务”。两者组合，不重复维护产物清单。

## 问题定义

当前 trace 模型可以区分每次顶层调用：

- 原子工具调用各自生成 `trace_id`。
- `batch` 的子步骤共享一个 `trace_id`。
- `run_task_plan` 的步骤共享一个 `trace_id`。

但它不能表达更高层的业务任务边界：

- Agent 在同一天可能先执行“卸载软件”，再执行“审计 MCP”，两者的 trace 平铺在同一根目录。
- 同一业务任务可能跨多个 Agent 回合，产生多个原子调用、batch 和 task plan。
- 仅凭时间和目录名无法可靠判断哪些 trace 属于同一任务。
- trace 根目录长期累积后不利于浏览、归档和审计。
- 自定义 `trace_id` 不能安全地仅靠 ID 中日期推导物理路径。
- 进程全局“当前任务”在多客户端、并发调用和服务重启场景会产生串任务风险。

## 核心决策

### 1. 两级身份

- `task_id`：业务任务会话，可跨多个 Agent 回合和多个顶层 MCP 调用。
- `trace_id`：一次顶层 MCP 调用；batch/task plan 的内部步骤继续共享该 trace。

关系为：

`task 1 -> N traces -> N execution records/artifacts`

### 2. 显式上下文，不使用全局当前任务

- `start_task(goal)` 创建业务任务并返回 `task_id`。
- 后续顶层工具调用通过可选 `task_id` 归属该任务。
- `finish_task(task_id, summary?)` 结束任务，最终成功/失败由服务端根据已登记 trace 派生。
- `list_tasks(...)` 和 `review_task_session(task_id)` 提供审计入口。
- 不设置进程级、线程级或模块级 mutable current task。
- 不从自然语言、Agent 会话 ID、时间邻近度自动猜测任务归属。

### 3. 缺省调用形成 standalone task

兼容现有调用方：

- 未传 `task_id` 的每个顶层调用自动创建 standalone task。
- batch/task plan 的内部子步骤继承顶层 task，不各自创建 task。
- 调用完成后 standalone task 自动结束。
- 所有顶层响应都返回实际 `task_id`，保证 trace 不成为无主记录。

### 4. 日期分区与定位索引

默认布局：

```text
~/.computer-use/
  traces/
    2026/06/16/<trace_id>/
      meta.json
      trace.jsonl
      screenshots/
      snapshots/
    .index/<sha256(trace_id)>.json
  tasks/
    2026/06/16/<task_id>/
      task.json
      traces/<trace_id>.json
    .index/<sha256(task_id)>.json
```

规则：

- 分区日期使用创建时的本地系统日期，JSON 时间字段统一使用带时区的 ISO 8601。
- 定位索引文件名使用原始 ID 的 SHA-256，避免自定义 ID 参与路径拼接。
- 索引内容保存原始 ID、相对路径、创建时间和 schema version。
- 索引是可重建的派生数据，不是唯一事实源。
- 旧布局 `<trace_dir>/<trace_id>/` 继续可读，不在运行时自动搬迁。
- 新写入只进入日期分区，不继续扩大旧扁平目录。

### 5. 单一归属与并发安全

- 一个 `trace_id` 只能归属一个 `task_id`。
- 同一 task 重复登记同一 trace 必须幂等。
- 将同一 trace 登记到另一个 task 返回结构化 `trace_task_conflict`。
- `task.json` 和 locator 使用"同目录临时文件 + `Path.replace`"原子写入。
- task 下每条 trace 使用独立 JSON 文件，避免多个进程并发追加同一 `traces.jsonl`。
- trace 本身现有 JSONL 并发写约束不在本计划扩大；禁止多个顶层调用并发复用同一 `trace_id`。
- **TOCTOU 已知限制**：trace 归属的 check-then-register 序列（检查归属文件是否已存在 → 写入归属文件 → 更新 `task.json` 统计）存在 check-then-write 竞争窗口。`Path.replace` 保证单文件原子性，但不保证跨文件的 check-then-write 原子性。缓解策略：归属文件写入使用 `O_CREAT|O_EXCL`（`open(..., "x")`）——若文件已存在则检测冲突并返回幂等或 `trace_task_conflict`，而非先 check 后 write。此窗口在单进程串行 MCP 调用下不构成实际风险；多进程并发场景作为已知限制记录。

## 生命周期与数据模型

### `task.json`

```json
{
  "schema_version": 1,
  "task_id": "task-20260616-101530-a1b2c3",
  "goal": "启动 HiBit Uninstaller 并打开文件和注册表查找器",
  "mode": "explicit",
  "status": "active",
  "created_at": "2026-06-16T10:15:30.000+08:00",
  "updated_at": "2026-06-16T10:15:30.000+08:00",
  "finished_at": null,
  "summary": null,
  "trace_count": 0,
  "failed_trace_count": 0,
  "active_trace_count": 0
}
```

约束：

- `mode` 为 `explicit` 或 `standalone`。
- `status` 为 `active`、`succeeded`、`failed` 或 `cancelled`。
- `finish_task` 默认根据 trace 结果派生 `succeeded` / `failed`。
- 仅显式取消时允许调用方请求 `cancelled`。
- 已结束 task 不接受新 trace，返回 `task_closed`。

### `tasks/.../<task_id>/traces/<trace_id>.json`

```json
{
  "schema_version": 1,
  "task_id": "task-20260616-101530-a1b2c3",
  "trace_id": "20260616-021531-z9y8x7",
  "kind": "atomic",
  "tool": "click",
  "started_at": "2026-06-16T10:15:31.000+08:00",
  "finished_at": "2026-06-16T10:15:32.120+08:00",
  "status": "succeeded"
}
```

`kind` 为 `atomic`、`batch` 或 `task_plan`。task 统计值由这些归属记录重新计算后写回，避免把可漂移计数当成唯一事实。

**路径约束：归属文件不存储机器绝对路径。** `trace_path` 字段已移除——trace 物理位置通过 locator 按 `trace_id` 在读取时解析（`audit_store.resolve_location(root, trace_id)`）。这避免了：路径在 `trace_dir` 配置变更或数据迁移后失效；与 locator 重复维护 trace 路径造成双真相源；在结构化审计数据中嵌入特定用户主目录。归属文件只保留 `trace_id` 作为定位键。

## 范围

包含：

- 业务任务 ID、生命周期和状态模型。
- trace/task 日期分区、定位、旧布局兼容和索引重建。
- 所有顶层 MCP 工具的可选 `task_id` 上下文。
- standalone task 兼容策略。
- batch/task plan 子步骤继承父 task。
- task 列表、详情、复盘和 CLI 审计入口。
- trace/task 单一归属、关闭后拒绝写入和结构化错误。
- API、设计、部署、陷阱、迁移和测试文档。

不包含：

- 从自然语言自动推断 task 边界。
- 将 Codex/Kimi/Claude 的产品会话 ID 直接等同于业务任务 ID。
- 多机共享、网络数据库或云端审计。
- 自动删除、压缩或上传历史 trace。
- 修改截图、鼠标、键盘或密码输入安全边界。
- 把旧 trace 自动批量迁移到新目录。
- 在本计划中重复实现 artifact manifest。

## 文件结构与职责

- Create: `computer_use/audit_store.py`
  - 日期分区、原子 JSON、哈希 locator、路径边界验证和索引重建基础能力。
- Create: `computer_use/task_session.py`
  - task ID、生命周期、trace 归属、统计和审计查询。
- Modify: `computer_use/trace.py`
  - 新 trace 分区写入、locator 解析、旧扁平布局兼容、task_id 元数据。
- Modify: `computer_use/mcp_server.py`
  - task 工具、通用 `task_id` schema、顶层上下文建立和响应字段。
- Modify: `computer_use/runner.py`
  - task plan 继承 task_id，不创建嵌套 standalone task。
- Modify: `computer_use/review.py`
  - 复用 trace 读取解析器；新增 task 级聚合复盘。
- Modify: `computer_use/cli.py`
  - `tasks list/show/review` 与 `audit rebuild-index` 只读/维护命令。
- Create: `tests/test_audit_store.py`
- Create: `tests/test_task_session.py`
- Modify: `tests/test_trace.py`
- Modify: `tests/test_mcp_server.py`
- Modify: `tests/test_runner.py`
- Modify: `tests/test_review.py`
- Modify: `tests/test_cli.py`
- Modify: `docs/api.md`
- Modify: `docs/overview.md`
- Modify: `docs/deployment.md`
- Modify: `docs/pitfalls.md`
- Modify: `docs/audit-checklist.md`
- Modify: `tests/manual_test_checklist.md`
- Modify: `CHANGELOG.md`

---

### Task 1: 建立分区存储与可重建 locator

**Files:**
- Create: `computer_use/audit_store.py`
- Create: `tests/test_audit_store.py`

- [ ] **Step 1: 写失败测试**

覆盖：

- 本地日期转换为 `YYYY/MM/DD` 分区。
- locator 文件名只由 SHA-256 十六进制组成。
- locator 原子写入后可按原始 ID 解析。
- locator 中的相对路径不能通过 `..` 或绝对路径逃逸配置根目录。
- 同 ID 同路径重复注册幂等。
- 同 ID 不同路径返回明确冲突。
- 删除 `.index` 后可扫描分区目录重建。
- 扫描时忽略临时文件、非法目录和旧扁平目录。

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_audit_store.py -v`

Expected: FAIL，因为模块尚不存在。

- [ ] **Step 3: 实现最小通用存储能力**

提供：

```python
def partition_for(moment: datetime) -> Path: ...
def locator_name(identifier: str) -> str: ...
def write_json_atomic(path: Path, data: dict[str, Any]) -> None: ...
def register_location(root: Path, identifier: str, target: Path) -> Path: ...
def resolve_location(root: Path, identifier: str) -> Path | None: ...
def rebuild_location_index(root: Path, id_field: str) -> dict[str, int]: ...
```

实现要求：

- 临时文件与目标文件位于同一目录。
- `replace` 前 flush，并在可用时 `os.fsync`。
- locator 只存相对于 root 的路径。
- 解析后使用 `Path.resolve()` 做 containment check。
- rebuild 写入新索引后再替换，不删除仍有效的旧索引。

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_audit_store.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add computer_use/audit_store.py tests/test_audit_store.py
git commit -m "feat: add partitioned audit storage"
```

### Task 2: 将新 trace 写入日期分区并兼容旧布局

**Files:**
- Modify: `computer_use/trace.py`
- Modify: `tests/test_trace.py`

- [ ] **Step 0: Rebase 与前置计划对齐**

本计划与 `mcp-contract-and-artifact-diagnostics-evolution.md` 都修改 `trace.py`。实施前必须 rebase 到前一计划的最终代码：

1. 读取前一计划完成版本中的 `trace.py` 实际签名，特别是 `trace_root` 的变更（移除 screenshots/snapshots 预创建、新增 `artifact_dir()` 等）。
2. 本计划的 `trace_root` 变更（新增 `create` 参数、日期分区布局）必须与前一计划的变更合并为一个统一签名：`trace_root(trace_id, *, create: bool = True)` 同时支持 create/resolve 分离、日期分区和延迟 artifact 目录。
3. 确认 `create_trace_root` / `resolve_trace_root` 的分离与前一计划的 artifact 目录策略不冲突。
4. 不机械套用本计划中基于旧代码的行号或旧函数形态。

- [ ] **Step 1: 写失败测试**

覆盖：

- `trace_root(new_id)` 创建 `traces/YYYY/MM/DD/<trace_id>`。
- 新建 trace 同时产生 locator。
- `read_trace`、`read_trace_meta`、`generate_report` 通过 locator 读取新布局。
- 旧 `<trace_dir>/<trace_id>` 在无 locator 时仍可读取。
- 自定义 `trace_id` 不依赖 ID 中日期也可定位。
- locator 损坏时返回受控错误，不回退到全盘模糊搜索。
- `meta.json` 包含可选 `task_id`、`created_at` 和 schema version。
- 同一 trace 不能被不同 task 改写归属。
- 现有 trace ID 路径安全测试继续通过。

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_trace.py -v`

Expected: FAIL，新布局断言不成立。

- [ ] **Step 3: 实现 create/resolve 分离**

禁止让只读操作隐式创建目录：

```python
def create_trace_root(trace_id: str, *, created_at: datetime | None = None) -> Path: ...
def resolve_trace_root(trace_id: str) -> Path | None: ...
def trace_root(trace_id: str, *, create: bool = True) -> Path: ...
```

兼容顺序：

1. 有 locator 时解析新布局。
2. 无 locator 时检查旧扁平路径。
3. 只读找不到时返回 `None` 或空结果，不创建空 trace。
4. 写入找不到时创建日期分区并登记 locator。

`generate_report` 使用 `resolve_trace_root`（而非 `create_trace_root`）定位已存在的 trace 目录，再将 `report.md` 写入其中。对不存在的 trace 调用 `generate_report` 是错误（返回 `None` 或抛出受控异常），不隐式创建空 trace 目录。

- [ ] **Step 4: 扩展 trace 元数据**

```python
def write_trace_meta(
    trace_id: str,
    goal: str | None = None,
    *,
    task_id: str | None = None,
) -> Path: ...
```

保留旧调用兼容，不改变敏感信息脱敏规则。

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_trace.py -v`

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add computer_use/trace.py tests/test_trace.py
git commit -m "feat: partition trace storage by business date"
```

### Task 3: 实现业务 task 生命周期与 trace 单一归属

**Files:**
- Create: `computer_use/task_session.py`
- Create: `tests/test_task_session.py`

- [ ] **Step 1: 写失败测试**

覆盖：

- task ID 格式、Windows 路径安全和保留设备名拒绝。
- `start_task` 创建 explicit task。
- `start_standalone_task` 创建 standalone task。
- task 可跨多个调用登记 atomic/batch/task_plan trace。
- 重复登记同一 trace 幂等。
- 同一 trace 登记到第二个 task 返回 `trace_task_conflict`。
- 已结束 task 返回 `task_closed`。
- trace 成功/失败状态正确汇总。
- `finish_task` 从 trace 归属记录派生最终状态。
- 无 trace 的 explicit task 可被取消，不可伪装为成功。
- `list_tasks` 按创建时间倒序，并可按日期和状态过滤。
- 跨日期运行的 task 保持在创建日目录，后续 trace 可位于其他日期。
- task locator 删除后可重建。

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_task_session.py -v`

Expected: FAIL，因为模块尚不存在。

- [ ] **Step 3: 实现数据类型与错误**

至少定义：

```python
class TaskSessionError(Exception): ...
class TaskNotFoundError(TaskSessionError): ...
class TaskClosedError(TaskSessionError): ...
class TraceTaskConflictError(TaskSessionError): ...

def generate_task_id() -> str: ...
def start_task(goal: str, *, mode: str = "explicit") -> dict[str, Any]: ...
def register_trace(task_id: str, trace_id: str, *, kind: str, tool: str) -> dict[str, Any]: ...
def complete_trace(task_id: str, trace_id: str, *, status: str) -> dict[str, Any]: ...
def finish_task(task_id: str, *, summary: str | None = None, cancel: bool = False) -> dict[str, Any]: ...
def get_task(task_id: str) -> dict[str, Any]: ...
def list_tasks(...) -> list[dict[str, Any]]: ...
```

- [ ] **Step 4: 保证任务统计可修复**

每次读取详情时从 `traces/*.json` 重新计算：

- `trace_count`
- `failed_trace_count`
- `active_trace_count`

若 `task.json` 缓存计数漂移，维护命令可修复，但普通只读查询不静默改盘。

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_task_session.py -v`

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add computer_use/task_session.py tests/test_task_session.py
git commit -m "feat: add business task session lifecycle"
```

### Task 4: 暴露 task 生命周期 MCP 工具

**Files:**
- Modify: `computer_use/mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: 写失败测试**

新增工具：

- `start_task`
- `finish_task`
- `get_task`
- `list_tasks`
- `review_task_session`

覆盖：

- Schema 必填项和枚举正确。
- `start_task` 返回 `task_id`、`status`、`task_path`。
- `finish_task` 不接受调用方伪造 `succeeded`。
- 未知 task 返回 `task_not_found`。
- 已关闭 task 返回 `task_closed`。
- 所有错误响应保留 `timestamp`，不泄露内部堆栈。

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_mcp_server.py -k "task_session or start_task or finish_task" -v`

Expected: FAIL，新工具未注册。

- [ ] **Step 3: 实现工具注册和分发**

task 管理工具本身不自动创建 standalone task，也不写入被管理 task 的执行 trace，避免生命周期操作递归制造任务。

`review_task(trace_id)` 与 `review_task_session(task_id)` 的关系：前者是现有的单 trace 确定性摘要，以 `trace_id` 为输入；后者是新增的 task 级多 trace 聚合复盘，以 `task_id` 为输入，遍历该 task 下所有 trace 并汇总。两者不重叠——`review_task_session` 内部可复用 `review_task` 的 trace 读取解析器。API 文档（Task 7 Step 1）应明确区分两者的输入键和输出粒度。

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_mcp_server.py -k "task_session or start_task or finish_task" -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add computer_use/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: expose task session MCP tools"
```

### Task 5: 将 `task_id` 贯穿所有顶层执行并实现 standalone 兼容

**Files:**
- Modify: `computer_use/mcp_server.py`
- Modify: `computer_use/runner.py`
- Modify: `tests/test_mcp_server.py`
- Modify: `tests/test_runner.py`

- [ ] **Step 1: 写失败测试**

覆盖：

- 所有可执行工具 schema 都有可选 `task_id`，task 管理工具除外。
- 显式 task 下连续两个原子调用产生两个 trace，归属同一 task。
- 未传 task_id 的原子调用自动创建并结束 standalone task。
- batch 只登记一个顶层 trace，子步骤不创建额外 task。
- run_task_plan 只登记一个顶层 trace，内部 `_call_tool` 继承 task context。
- 嵌套调用不把 `task_id` 传给 core/UIA 函数。
- 响应统一包含 `task_id`、`trace_id`、`task_path` 和 trace/artifact manifest。
- 工具异常、SafetyError、fail-safe 和取消路径都完成 trace 归属状态。
- task 登记失败时不执行真实鼠标键盘动作。
- 显式 task 保持 active，直到调用 `finish_task`。
- standalone task 根据本次 trace 自动派生 succeeded/failed。
- batch 或 run_task_plan 中途抛出未预期异常时，顶层包装器的 `finally` 保证 standalone task 被结束（状态派生为 `failed`），不存在永久 active 的 standalone task。
- trace JSONL 记录中 `args` 不包含 `task_id` 键（已在 `record_step` 前剥离）。
- `run_task_plan` 每步捕获的 `screenshot_path` 通过 `ExecutionContext.screenshot_path` 传入 `_call_tool`，trace JSONL 中该步骤记录包含正确的 `screenshot_path`（验证 screenshot_path 字段未在 context 迁移中丢失）。
- 顶层 atomic 调用（未传 task_id）生成的 context `is_standalone=True`；显式 task 调用生成的 context `is_standalone=False`；嵌套 context（batch/run_task_plan/retry_step 子步骤）继承父 context 的 `is_standalone` 值。
- `retry_step` 通过参数从 `_dispatch_tool` 接收 `task_id`，构造 `top_level=False` 且继承父 context `is_standalone` 的嵌套 context，不创建新 task；`task_id=None` 时报错而非回退 `meta.json` 猜测。

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_mcp_server.py tests/test_runner.py -k "task_id or standalone or task_context" -v`

Expected: FAIL，当前分发没有业务 task 上下文。

- [ ] **Step 3: 建立显式调用上下文**

使用不可变数据对象代替散落 dict：

```python
@dataclass(frozen=True)
class ExecutionContext:
    task_id: str
    trace_id: str
    step_index: int | str
    top_level: bool
    is_standalone: bool
    screenshot_path: str | None = None
```

**字段语义：**

- `task_id` / `trace_id` / `step_index`：归属与步骤定位，沿用原 `trace_context` dict 的同名键。
- `top_level`：区分 `_call_tool` 是由 MCP 入口（`_handle_tool_call`）调用（`True`）还是由嵌套入口（`_batch_tool` / `run_task_plan` / `retry_step`）调用（`False`）。详见下方「top_level 判定与 standalone task 结束保证」。
- `is_standalone`：标识当前 context 绑定的 task 是否为 standalone task。`_establish_context` 设置该字段：当调用方**未**提供显式 `task_id`（即自动创建了一个 standalone task）时设为 `True`；当调用方**显式**提供了 `task_id`（即 task 由 `start_task` 预先创建）时设为 `False`。`is_standalone=True` 决定 `_handle_tool_call` 的 `finally` 块需要在调用结束后自动结束该 standalone task（见下方伪代码与异常安全保证）；嵌套 context 继承父 context 的 `is_standalone` 值。
- `screenshot_path`：保留现有 `trace_context` dict 携带的 `screenshot_path` 语义（见 `runner.py` `run_task_plan` 第 119-121 行：每步截图后写入；`mcp_server.py` `_call_tool` 第 651 行读取并传给 `record_step`）。`run_task_plan` 在捕获每步截图后设置该字段；`_call_tool` 在调用 `record_step` 时读取它，使 trace JSONL 记录包含该步骤的 `screenshot_path`。顶层 atomic 调用默认为 `None`（若工具本身是 `screenshot`，`_call_tool` 现有逻辑仍可从结果中派生，见 `mcp_server.py` 第 689-690 行，不受本字段影响）。

行为：

1. 顶层 `_handle_tool_call`（MCP 入口）解析或创建 task，构造 `top_level=True` 的 `ExecutionContext`，并根据是否显式传入 `task_id` 设置 `is_standalone`。
2. 在执行真实动作前登记 trace。
3. nested 调用复用同一 context，仅更新 step index（`top_level=False`），并继承父 context 的 `is_standalone` 和（如适用）`screenshot_path`。
4. `_call_tool` 的 `finally` 路径在**所有**调用（顶层和嵌套）中完成 trace 状态记录。
5. standalone task 的结束**不在** `_call_tool` 的 `finally` 中执行，而是在顶层包装器中执行（见下方「top_level 判定与 standalone task 结束保证」）。

#### task_id 线程传播路径

当前调用链为 `_handle_tool_call → _call_tool(name, args, trace_context) → _dispatch_tool(name, args, cs, trace_id=, parent_step_index=) → _batch_tool(...) / runner.run_task_plan(...) / runner.retry_step(...)`。`_dispatch_tool`、`_batch_tool`、`run_task_plan` 和 `retry_step` 目前均不接收或传播 `task_id`（`_dispatch_tool` 当前分发到 `retry_step` 时见 `mcp_server.py` 第 1134-1141 行，未传 `task_id`）。以下是必须实现的签名变更和传播规则：

**签名变更：**

```python
# _call_tool 接收 ExecutionContext（所有内部调用方同步更新为传 context，不保留旧 trace_context dict 入口）。
# context 保持 Optional 仅为防御：task 管理工具经 _dispatch_task_management_tool 直接分发，完全绕过
# _call_tool；正常可执行工具调用（含嵌套）始终携带非空 context，实践中 None 路径不触发。
def _call_tool(
    name: str,
    args: dict,
    *,
    context: ExecutionContext | None = None,
) -> str: ...

# _dispatch_tool 新增 task_id 和 is_standalone 参数，向下传递（嵌套入口无法访问父 ExecutionContext，
# 因此 is_standalone 必须作为参数显式传入，不能引用 parent_ctx）
def _dispatch_tool(
    name: str,
    args: dict,
    cs: CoordinateSystem,
    trace_id: str | None = None,
    parent_step_index: int | str | None = None,
    task_id: str | None = None,
    is_standalone: bool = False,
) -> str: ...

# _batch_tool 新增 task_id 和 is_standalone 参数，传递给内部 _call_tool 调用
def _batch_tool(
    args: dict,
    trace_id: str | None = None,
    parent_step_index: int | str | None = None,
    task_id: str | None = None,
    is_standalone: bool = False,
) -> str: ...

# runner.run_task_plan 新增 task_id 和 is_standalone 参数
def run_task_plan(
    steps: list[dict[str, Any]],
    trace_id: str | None = None,
    goal: str | None = None,
    final_state: bool = False,
    capture_screenshots: bool = True,
    task_id: str | None = None,
    is_standalone: bool = False,
) -> dict[str, Any]: ...

# runner.retry_step 新增 task_id 和 is_standalone 参数（与 _batch_tool / run_task_plan 同模式）
def retry_step(
    trace_id: str,
    step_index: int,
    mode: str = "single",
    retry_suffix: str | None = None,
    task_id: str | None = None,
    is_standalone: bool = False,
) -> dict[str, Any]: ...
```

**传播规则：**

1. **`_handle_tool_call` → `_call_tool`**：`_handle_tool_call`（经 `_establish_context`）解析 `args.get("task_id")`，创建或解析 task，构造 `ExecutionContext(task_id=..., trace_id=..., step_index=0, top_level=True, is_standalone=<调用方未传 task_id>)`，传入 `_call_tool(name, args, context=ctx)`。
2. **`_call_tool` → `_dispatch_tool`**：`_call_tool` 从 `context` 提取 `task_id`、`trace_id` 和 `is_standalone`，传给 `_dispatch_tool(..., task_id=context.task_id, is_standalone=context.is_standalone)`。
3. **`_dispatch_tool` → `_batch_tool`**：`_dispatch_tool` 将 `task_id` 和 `is_standalone` 透传给 `_batch_tool(args, trace_id=trace_id, parent_step_index=..., task_id=task_id, is_standalone=is_standalone)`。
4. **`_dispatch_tool` → `runner.run_task_plan`**：`_dispatch_tool` 将 `task_id` 和 `is_standalone` 透传给 `run_task_plan(steps, trace_id=..., task_id=task_id, is_standalone=is_standalone, ...)`。
5. **`_dispatch_tool` → `runner.retry_step`**：`_dispatch_tool` 将 `task_id` 和 `is_standalone` 透传给 `retry_step(args["trace_id"], args["step_index"], mode=..., task_id=task_id, is_standalone=is_standalone)`，与 `_batch_tool` 和 `run_task_plan` 的传播方式完全一致。`_dispatch_tool` 当前的 `retry_step` 分发（`mcp_server.py` 第 1134-1141 行）只传 `trace_id`/`step_index`/`mode`，迁移后补 `task_id` 和 `is_standalone`。
6. **`_batch_tool` 内部 `_call_tool` 调用**：构造嵌套 `ExecutionContext(task_id=task_id, trace_id=trace_id, step_index=sub_step_index, top_level=False, is_standalone=is_standalone)`（`task_id` 与 `is_standalone` 均取自 `_batch_tool` 收到的参数，即父 context 的对应值），传入 `_call_tool(tool_name, tool_args, context=nested_ctx)`。子步骤复用父 task 和父 trace，仅更新 `step_index`。`screenshot_path` 默认继承父 context 值（batch 子步骤不自行截图，除非未来扩展）。
7. **`run_task_plan` 内部 `_call_tool` 调用**：构造嵌套 `ExecutionContext(task_id=task_id, trace_id=trace_id, step_index=step_index, top_level=False, is_standalone=is_standalone)`（`task_id` 与 `is_standalone` 均取自 `run_task_plan` 收到的参数，即父 context 的对应值）。`run_task_plan` 在捕获每步截图后（`_step_screenshot`，见 `runner.py` 第 115-117 行）将该步的 `screenshot_path` 写入嵌套 context，使 `_call_tool` 的 `record_step` 调用能把它带入 trace JSONL；未捕获截图的步骤该字段为 `None`。
8. **`runner.retry_step` 内部 `_call_tool` 调用**：`retry_step` 当前以 `trace_context={"trace_id": trace_id, "step_index": ...}` 调用 `_call_tool`（见 `runner.py` 第 246-250、275-279 行）。迁移后使用 `_dispatch_tool` 通过参数传入的 `task_id` 和 `is_standalone`（见传播规则 5），构造嵌套 `ExecutionContext(task_id=task_id, trace_id=trace_id, step_index=retry_suffix, top_level=False, is_standalone=is_standalone)`（`task_id` 与 `is_standalone` 均取自 `retry_step` 收到的参数，即父 context 的对应值）。`task_id` 来源**仅限参数**，不从 `meta.json` 派生——这与 `_batch_tool`（规则 6）和 `run_task_plan`（规则 7）的传播模式完全一致，避免以下问题：(a) `meta.json` 指向的 task 可能已被 `finish_task` 关闭，导致 retry 命中 `task_closed`；(b) standalone retry 的嵌套 trace 可能被错配到 `meta.json` 指向的旧 task，产生孤儿记录。若 `task_id` 参数为 `None`（实践中不应发生，因 `_dispatch_tool` 始终从 `_call_tool` 的 context 接收），`retry_step` 报错而非猜测或回退 `meta.json`。retry 属于既有 trace 的重放，不创建新 task，`top_level=False`。retry 步骤不重新截图（重放原始 args），`screenshot_path` 默认 `None`。

**一致性验证：** 上述传播规则完成后，所有四个嵌套入口（`_dispatch_tool → _batch_tool`、`_dispatch_tool → run_task_plan`、`_dispatch_tool → retry_step`、以及各自内部的嵌套 `_call_tool`）使用**同一模式**：(1) 通过参数从 `_dispatch_tool` 同时接收 `task_id` **和** `is_standalone`，不读 `meta.json`，不引用其作用域内不存在的 `parent_ctx` 对象；(2) 构造嵌套 context 时 `top_level=False` 且 `is_standalone` 直接取参数值（该参数值即父 context 的 `is_standalone`，由 `_call_tool → _dispatch_tool` 一路透传）；(3) 不创建新 task。`retry_step` 不再有特殊路径。

**安全边界：**

`task_id` 只存在于 `mcp_server` / `runner` 层，用于 task/trace 归属管理。`task_id` **不传递给** `core.py`（鼠标/键盘）、`safety.py`（坐标校验）、`ui_automation.py`（UIA）或任何其他底层函数。这些函数的签名和职责不变。`_dispatch_tool` 内调用 core/UIA 函数时不带 `task_id`。

**trace 记录中的 task_id 处理：**

`task_id` 在传入 `_call_tool` 后，在调用 `record_step` 前从 `args` 中剥离（移除 `args` dict 中的 `"task_id"` 键），使 trace JSONL 记录不重复存储 `task_id`（trace 与 task 的归属关系已由 `task_session.register_trace` 和 `meta.json` 中的 `task_id` 字段维护）。剥离后的 `args` 才传给 `_dispatch_tool` 执行实际工具逻辑。

#### top_level 判定与 standalone task 结束保证

`_call_tool` 是**同一个函数**，既被顶层 MCP 入口（`_handle_tool_call`）调用，也被嵌套入口（`_batch_tool`、`run_task_plan`、`retry_step`）调用。其现有 `finally` 块在**每次**调用（含嵌套）时执行。因此必须区分两层关注点：

**trace 状态完成（每次调用都执行）：**

`_call_tool` 的 `finally` 块负责在**所有**调用（`top_level=True` 和 `top_level=False`）中记录 trace step（`record_step`）和派生 trace step 状态（succeeded/failed/error）。这是现有的行为，保持不变。

**standalone task 生命周期结束（仅顶层执行）：**

standalone task 的结束代码**不放在** `_call_tool` 的 `finally` 中（否则会在嵌套 `_call_tool` 调用时错误地结束 task）。它放在 `_handle_tool_call` 的作用域中，作为 `_call_tool` 返回或抛出后的薄包装层：

```python
# task 管理工具不走 ExecutionContext / standalone task 路径，直接分发，
# 避免生命周期操作递归制造 task。集合与 Task 5 Step 4 排除集合一致：
#   {start_task, finish_task, get_task, list_tasks, review_task_session}
# 注意：review_task（单 trace 摘要）不在该集合，仍走正常上下文建立。
_TASK_MANAGEMENT_TOOLS = frozenset({
    "start_task", "finish_task", "get_task",
    "list_tasks", "review_task_session",
})


def _handle_tool_call(name: str, arguments: dict) -> str:
    safe_arguments = arguments or {}

    # task 管理工具绕过 _establish_context，直接分发（不创建 standalone task、不登记执行 trace）。
    if name in _TASK_MANAGEMENT_TOOLS:
        return _dispatch_task_management_tool(name, safe_arguments)

    # ctx 必须在 try 块外初始化为 None，使 finally 能安全判空
    # （若 _establish_context 抛出，ctx 仍为 None）。
    ctx: ExecutionContext | None = None
    try:
        # _establish_context 位于 try 块内：解析/创建 task、生成 trace_id、
        # 调用 register_trace 登记trace。若 task 不存在 / 已关闭 / trace 冲突，
        # 在此抛出并被下方对应 except 捕获，返回结构化 JSON 而非逃逸到 MCP 传输层。
        ctx = _establish_context(name, safe_arguments)
        result = _call_tool(name, safe_arguments, context=ctx)
        _finalize_trace_status(ctx, result)
        return result
    except TaskNotFoundError as e:
        # register_trace 在 _establish_context 内先于 _call_tool 执行，
        # 因此 task 登记失败时不执行真实鼠标键盘动作（满足 Step 1 测试）。
        return json.dumps({
            "error": "task_not_found",
            "task_id": e.task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except TaskClosedError as e:
        return json.dumps({
            "error": "task_closed",
            "task_id": e.task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except TraceTaskConflictError as e:
        return json.dumps({
            "error": "trace_task_conflict",
            "task_id": getattr(e, "task_id", None),
            "trace_id": getattr(e, "trace_id", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        if ctx is not None:
            _finalize_trace_status(ctx, error=exc)
        # 保持现有 catch-and-return 语义（mcp_server.py 第 1408-1416 行）：
        # 错误以 {"error": ...} JSON 返回，不向上传播到 MCP 传输层。
        message = trace_module.sanitize_message(safe_arguments, str(exc))
        logging.error("tool error: %s", message)
        return json.dumps({"error": message})
    finally:
        # 仅当成功建立了 context（ctx is not None）、且为顶层 standalone task 时，
        # 才自动关闭。显式 task（is_standalone=False）等 finish_task；
        # 嵌套调用不会进入此 _handle_tool_call 路径。
        if ctx is not None and ctx.top_level and ctx.is_standalone:
            _ensure_standalone_task_closed(ctx)
```

**伪代码引用的辅助函数职责（各一句话）：**

- `_establish_context(name: str, args: dict) -> ExecutionContext`：(1) 解析 `args.get("task_id")`——若存在则复用该 explicit task、`is_standalone=False`，否则创建 standalone task、`is_standalone=True`；(2) 生成 `trace_id`（或复用 `args` 中显式传入的 `trace_id`）；**(3) 调用 `task_session.register_trace(task_id, trace_id, kind=..., tool=name)` 在执行真实动作前登记 trace**；(4) 构造 `top_level=True` 的顶层 `ExecutionContext`。若 `register_trace` 失败（task 不存在 → `TaskNotFoundError`；task 已关闭 → `TaskClosedError`；trace 已属其他 task → `TraceTaskConflictError`），`_establish_context` 抛出对应异常，**阻止后续 `_call_tool` 执行真实鼠标键盘动作**（满足 Step 1 测试「task 登记失败时不执行真实鼠标键盘动作」）。task 管理工具（`start_task` 等）不走此函数。
- `_finalize_trace_status(ctx: ExecutionContext, result: str | None = None, error: Exception | None = None) -> None`：调用 `task_session.complete_trace` 注册该 trace 的最终状态（成功由 `result` 派生、失败由 `error` 派生），幂等。
- `_ensure_standalone_task_closed(ctx: ExecutionContext) -> None`：仅对 `is_standalone=True` 的 task 调用 `finish_task`，关闭 standalone task，最终状态从该 task 已登记 trace 派生；explicit task 不在此关闭。
- `_dispatch_task_management_tool(name: str, args: dict) -> str`：将 `name` 直接映射到对应 task 管理函数（`start_task` / `finish_task` / `get_task` / `list_tasks` / `review_task_session`），返回 `json.dumps` 结果。不经 `_establish_context`、不创建 standalone task、不登记执行 trace——这些工具自身的输入参数已包含 `task_id`，其生命周期操作（如 `finish_task` 遇未知 task）不应递归制造任务。task_session 层的错误以结构化 dict 字段返回（如 `{"error": "task_not_found", ...}`），由本函数原样序列化。

**`top_level` 的设置：**

- `top_level=True`：**仅**当 `_call_tool` 由 `_handle_tool_call`（MCP 入口点）调用时。由 `_handle_tool_call` 在构造 `ExecutionContext` 时显式设置。
- `top_level=False`：当 `_call_tool` 由 `_batch_tool`、`run_task_plan` 或 `retry_step` 调用时。由这些调用者在构造嵌套 `ExecutionContext` 时显式设置。

**`is_standalone` 的设置：**

- `is_standalone=True`：当顶层调用未提供显式 `task_id`，`_establish_context` 自动创建 standalone task 时。嵌套 context（batch/run_task_plan/retry_step 子步骤）继承父 context 的 `is_standalone=True`。
- `is_standalone=False`：当顶层调用显式提供了 `task_id`（task 由 `start_task` 预先创建）时。嵌套 context 同样继承 `is_standalone=False`。
- `is_standalone` 仅在 `_handle_tool_call` 的 `finally` 中与 `top_level` 共同判断是否触发 `_ensure_standalone_task_closed`；嵌套调用（`top_level=False`）即使 `is_standalone=True` 也不触发关闭。

**异常安全保证：**

如果 `batch` 或 `run_task_plan` 在执行中途抛出未预期异常，异常会向上传播到 `_handle_tool_call`。`_handle_tool_call` 的 `finally` 块保证 standalone task 被结束（状态从已记录的 trace 结果派生，缺省为 `failed`）。这防止了永久 "active" 的 standalone task，满足验收标准「不存在进程全局 current task，不会因并发客户端串任务」。

- [ ] **Step 4: Schema 使用统一辅助函数**

避免手工给几十个工具重复添加字段：

```python
def _attach_task_context(tool: Tool) -> Tool: ...
```

排除集合（不附加 `task_id` 的工具）：

- **task 管理工具**：`start_task`、`finish_task`、`get_task`、`list_tasks`、`review_task_session`——这些工具本身操作 task 生命周期或执行 task 级聚合，其输入参数已包含显式 `task_id`，不应再叠加归属上下文。
- **只读单 trace 审计工具**：`review_task`——以 `trace_id` 为输入，不产生新执行记录，不需要 task 归属。

排除集合与 Step 1 测试中「task 管理工具除外」的断言必须一致。测试应显式枚举此集合，避免新增工具时遗漏。

- [ ] **Step 5: 禁止跨 task 复用 trace**

对显式 `trace_id`：

- 未有归属时绑定当前 task。
- 已属于当前 task 时允许既有 retry/resume 语义。
- 已属于其他 task 时在执行动作前返回 `trace_task_conflict`。

- [ ] **Step 6: 运行测试**

Run: `pytest tests/test_mcp_server.py tests/test_runner.py -v`

Expected: PASS。

- [ ] **Step 7: 提交**

```powershell
git add computer_use/mcp_server.py computer_use/runner.py tests/test_mcp_server.py tests/test_runner.py
git commit -m "feat: propagate business task context"
```

### Task 6: 提供 task 级复盘和本地审计 CLI

**Files:**
- Modify: `computer_use/review.py`
- Modify: `computer_use/cli.py`
- Modify: `tests/test_review.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: 写失败测试**

覆盖：

- task 复盘按时间列出所有 trace。
- 汇总工具数量、总步骤、失败 trace、错误类型和产物路径。
- 某条 trace 缺失时标记 `missing_trace`，不让整个复盘崩溃。
- 旧布局 trace 也能进入 task 复盘。
- `computer-use tasks list --date 2026-06-16 --status failed` 输出 JSON。
- `computer-use tasks show <task_id>` 输出 task 和 trace 列表。
- `computer-use tasks review <task_id>` 生成 task 级 Markdown 报告。
- `computer-use audit rebuild-index --dry-run` 不写文件。
- rebuild 输出 scanned/created/unchanged/conflicts/invalid 计数。
- 验证 audit 子命令的执行路径不导入 `pyautogui` 或 `computer_use.core`（可通过 import hook 或 `sys.modules` 状态检查测试：执行 `tasks list` / `audit rebuild-index` 后断言 `"pyautogui" not in sys.modules` 且 `"computer_use.core" not in sys.modules`）。

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_review.py tests/test_cli.py -k "task or audit" -v`

Expected: FAIL，task 审计入口不存在。

- [ ] **Step 3: 实现确定性 task 复盘**

复盘只读取结构化数据，不调用 LLM，不根据目录名称猜测证据。

输出至少包含：

- task 元数据和最终状态。
- trace 时间线。
- 每条 trace 的 kind/tool/status/path。
- 实际存在的截图、快照和报告 manifest。
- 缺失、损坏和归属冲突诊断。

- [ ] **Step 4: 实现 CLI（含导入架构重构）**

CLI 管理命令不得导入或初始化 `pyautogui` 后才执行，以保证无桌面环境也能审计。

当前 `cli.py` 在模块顶层（第 10 行 `import pyautogui`，第 13–24 行 `from computer_use.core import ...`）导入 pyautogui 和 core，这意味着任何子命令（包括只读审计命令）在启动时就会初始化输入设备库。必须重构导入架构：

**导入重构：**

1. 将 `import pyautogui` 从模块顶层移除，延迟到实际需要它的输入设备子命令处理函数内部（`click`、`move`、`scroll`、`type`、`key`）执行时导入。
2. 将 `from computer_use.core import (...)` 从模块顶层移除，延迟到输入设备子命令处理函数内部导入（core 的 `__init__` 会触发 pyautogui 导入）。
3. 将 `_current_logical_position()`（使用 `pyautogui.position()`）的 `pyautogui` 导入也移到函数内部。
4. `from computer_use.config import load_config`、`from computer_use.safety import ...`、`from computer_use.ui_automation import ...` 中，凡会传递导入 pyautogui 或 core 的依赖，也延迟到输入设备子命令处理函数内。只保留 `argparse`、`json`、`sys` 等标准库在模块顶层。
5. 新增的 audit/management 子命令处理函数（`tasks list/show/review`、`audit rebuild-index`）只导入 `computer_use.task_session`、`computer_use.audit_store`、`computer_use.review` 等不涉及输入设备的模块。

**保证：**

执行 `computer-use tasks list`、`computer-use tasks show <task_id>`、`computer-use tasks review <task_id>`、`computer-use audit rebuild-index` 时，`pyautogui` 和 `computer_use.core` 不出现在 `sys.modules` 中。Step 1 的测试断言此保证。

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_review.py tests/test_cli.py -v`

Expected: PASS。

- [ ] **Step 6: 提交**

```powershell
git add computer_use/review.py computer_use/cli.py tests/test_review.py tests/test_cli.py
git commit -m "feat: add task session audit commands"
```

### Task 7: 文档化使用协议、兼容边界与运维流程

**Files:**
- Modify: `docs/api.md`
- Modify: `docs/overview.md`
- Modify: `docs/deployment.md`
- Modify: `docs/pitfalls.md`
- Modify: `docs/audit-checklist.md`
- Modify: `tests/manual_test_checklist.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 更新 API 协议**

给出标准 Agent 流程：

```text
start_task(goal) -> task_id
tool(..., task_id=task_id)
batch(..., task_id=task_id)
review_task_session(task_id)
finish_task(task_id, summary)
```

明确：

- `task_id` 是业务任务，不是模型对话 ID。
- 一个业务任务可跨多个 Agent 回合。
- 一个 Agent 对话可以顺序创建多个业务 task。
- 未传 task_id 时只是兼容模式，不适合需要跨调用审计的任务。

- [ ] **Step 2: 更新设计与部署**

记录：

- 日期分区、task/trace 两级模型和 locator 可重建性质。
- `task_dir` 默认值及自定义配置。
- 本地系统时区决定目录分区，时间字段保留 offset。
- 旧扁平 trace 保持只读兼容，不自动迁移。
- 备份时必须同时包含 `traces/` 和 `tasks/`；`.index/` 可重建。

- [ ] **Step 3: 更新陷阱与审计清单**

增加：

- 禁止把 `~/.computer-use/traces/` 整体描述为“本次任务日志”。
- 汇报时必须给出 `task_id` 和关联 trace 数量。
- 不以时间相邻作为同任务证据。
- 检查 active task 是否长期未结束、trace 是否无主、locator 是否失效。

- [ ] **Step 4: 更新手工验证清单**

至少手工执行两个连续业务任务，验证：

1. 两个 task_id 不同。
2. 各自包含正确 trace。
3. 同日物理目录有明确日期分区。
4. review 不串任务。
5. MCP 重启后仍可按 task_id 查询。

- [ ] **Step 5: 使用 changelog 工具记录**

Run:

```powershell
python scripts/changelog.py add --title "feat: 增加业务任务会话审计" --body "新增 task_id 生命周期、日期分区 trace、任务级复盘与旧布局兼容，解决同日多任务 trace 难以归属和审计的问题。"
```

- [ ] **Step 6: 提交**

```powershell
git add docs tests/manual_test_checklist.md CHANGELOG.md
git commit -m "docs: document business task session auditing"
```

### Task 8: 全量验证、独立审计与计划归档

**Files:**
- Modify: `docs/CURRENT.md`
- Move: `docs/plans/active/business-task-session-trace-audit.md`
- To: `docs/plans/completed/business-task-session-trace-audit.md`

- [ ] **Step 1: 运行专项测试**

Run:

```powershell
pytest tests/test_audit_store.py tests/test_task_session.py tests/test_trace.py tests/test_mcp_server.py tests/test_runner.py tests/test_review.py tests/test_cli.py -v
```

Expected: PASS。

- [ ] **Step 2: 运行完整测试**

Run: `pytest tests/ -v`

Expected: PASS。

- [ ] **Step 3: 运行文档和链接审计**

Run:

```powershell
python scripts/agent_links.py check
python scripts/audit.py check
```

Expected: 两项均通过。

- [ ] **Step 4: 手工 MCP 验证**

在确保无人操作输入设备后：

1. 启动业务任务 A，执行两个无破坏性的观察调用并结束。
2. 启动业务任务 B，执行一个观察调用并结束。
3. 重启 MCP 服务。
4. 分别 `get_task` 和 `review_task_session`。
5. 确认 A/B 的 trace、路径、状态和 manifest 不交叉。
6. 执行一个不带 task_id 的观察调用，确认生成已结束 standalone task。

- [ ] **Step 5: 检查旧 trace 兼容**

使用测试夹具或备份副本验证旧 `<trace_dir>/<trace_id>/`：

- `read_trace`
- `review_task`
- task 手工关联后的 task review

均可读取，且不自动移动原目录。

- [ ] **Step 6: 独立 reviewer 验收**

重点审计：

- 并发客户端是否可能共享隐式 task 状态。
- 输入设备动作前是否完成 task/trace 归属校验。
- locator 路径是否可逃逸配置根目录。
- trace 是否可能跨 task 重复归属。
- 异常和 fail-safe 路径是否留下永久 active trace。
- 旧布局兼容是否会被只读调用意外创建新目录。
- task review 是否只报告实际存在的证据。

- [ ] **Step 7: 归档计划**

验收通过后将本文件移动到 `docs/plans/completed/`，更新 `docs/CURRENT.md`，记录最终测试数量、手工验证结果和 reviewer 结论。

- [ ] **Step 8: 最终提交**

```powershell
git add docs/CURRENT.md docs/plans
git commit -m "docs: archive task session trace plan"
```

---

## 验收标准

- 同一 Agent 会话内可创建多个互不混淆的业务 task。
- 同一业务 task 可跨多个 Agent 回合关联多个顶层 trace。
- 每条新 trace 都有且只有一个 task 归属。
- 未传 task_id 的旧调用仍工作，并产生可审计 standalone task。
- 新 trace 不再平铺到 trace 根目录，而按本地业务日期分区。
- 自定义 trace_id/task_id 可通过 locator 精确定位，不依赖 ID 日期。
- 旧扁平 trace 保持可读，不发生隐式迁移或删除。
- MCP 重启后 task 查询和复盘结果稳定。
- task 复盘只报告实际存在的 trace 和产物，不把目录用途当作证据。
- 不存在进程全局 current task，不会因并发客户端串任务。
- 所有专项测试、完整测试、文档审计和 Agent 链接检查通过。

## 风险与回滚

- **接口冲突**：前一计划也修改 trace/manifest。通过串行实施和实施前 rebase 解决，不并行编辑。
- **测试夹具大面积失效**：现有测试假设 `<trace_dir>/<trace_id>`。集中提供测试 helper 获取 resolved root，不在测试中复制路径规则。
- **索引损坏**：locator 可由分区目录重建；重建前支持 dry-run，冲突不自动覆盖。
- **跨日理解偏差**：task 保留在创建日，trace 按各自创建日分区；task manifest 是跨日关联真相源。
- **未结束 task**：不自动猜测完成状态；`list_tasks(status=active)` 和审计清单暴露陈旧 active task。
- **磁盘占用**：本计划只改组织和可审计性，不自动清理；后续 retention 计划基于 task 状态安全实施。
- **回滚**：停止写 task 上下文并恢复旧 trace 写入逻辑即可；新分区数据不删除，兼容读取器保留到完成迁移策略评审后。
