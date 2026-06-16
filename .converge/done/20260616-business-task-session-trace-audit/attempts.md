# Attempt Log · 20260616-business-task-session-trace-audit

> 跨轮累加的修复记录。历史 entry 不改写，只追加 annotation。

---

## Round 1 · Reviewer 阻断清单（待修复）

### Issue 1 · ExecutionContext 集成路径未定义
- source: converge_loop
- reviewer_backend: opencode-general
- Issue: Plan defines ExecutionContext (Task 5 Step 3) but never describes how task_id threads through _dispatch_tool to reach _batch_tool and run_task_plan. Current call chain: _handle_tool_call → _call_tool(name, args, trace_context) → _dispatch_tool(name, args, cs, trace_id=, parent_step_index=) → _batch_tool(args, trace_id=, parent_step_index=) / runner.run_task_plan(steps, trace_id=, ...). Neither _dispatch_tool, _batch_tool, nor run_task_plan currently receive or propagate task_id. The plan's Task 5 lists mcp_server.py and runner.py as files to modify but provides zero specification for these signature changes. Without this threading, batch sub-steps and task_plan steps cannot inherit the parent task, directly violating core decision #3 and the Task 5 Step 1 test.
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 5 Step 3 新增「task_id 线程传播路径」子节，列出 _call_tool / _dispatch_tool / _batch_tool / run_task_plan 的签名变更和 6 条传播规则，以及 task_id 不下传 core/UIA 的安全边界。
- Diff: Task 5 Step 3 扩展为含签名伪代码 + 传播规则 + 安全边界 + trace 记录中 task_id 剥离说明的完整子节。
- R1 verdict: Accepted
- **[Orchestrator Detection at R2]** Status: Accepted, confirmed by R2 escalated review: resolved

### Issue 2 · standalone task 结束时机与 finally 路径未定义
- source: converge_loop
- reviewer_backend: opencode-general
- Issue: Plan says "顶层 finally 路径完成 trace 状态" and "若为 standalone，在 finally 后结束 task" (Task 5 Step 3 points 4-5), but _call_tool is the SAME function for both top-level MCP entry (via _handle_tool_call) and nested entry (from _batch_tool and runner.run_task_plan). _call_tool's existing finally block runs on EVERY call including nested ones. The plan's ExecutionContext.top_level field is supposed to distinguish, but the plan never specifies: (a) who sets top_level and how; (b) where the standalone task ending code physically lives. If batch or task_plan throws mid-execution, plan does not describe whether standalone task is guaranteed to be ended.
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 Task 5 Step 3 新增「top_level 判定与 standalone task 结束保证」子节，明确 top_level 仅由 _handle_tool_call 设置、standalone 结束代码放在 _handle_tool_call 包装层而非 _call_tool finally、异常安全保证 batch/task_plan 抛出时顶层 finally 确保 task 结束。Step 1 测试列表新增对应 fail-safe 测试条目。
- Diff: Task 5 Step 3 扩展行为列表 + 新增 top_level/finally 子节含 _handle_tool_call 伪代码 + 异常安全保证段；Step 1 新增 2 条测试（异常结束 + args 剥离）。
- R1 verdict: Accepted
- **[Orchestrator Detection at R2]** Status: Accepted, confirmed by R2 escalated review: resolved

### Issue 3 · trace 归属文件存储机器绝对路径
- source: converge_loop
- reviewer_backend: opencode-general
- Issue: The trace 归属文件 data model (plan lines 138-152) stores "trace_path": "C:\\Users\\chenr\\.computer-use\\traces\\2026\\06\\16\\20260616-021531-z9y8x7" — an absolute, machine-specific Windows path. This directly contradicts the locator design (Task 1 Step 3: "locator 只存相对于 root 的路径") which explicitly stores relative paths. Creates stale paths, dual-source-of-truth, and embeds user home directory in audit data.
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 从归属文件 JSON 示例中移除 trace_path 字段，新增约束说明「归属文件不存储机器绝对路径；trace 物理位置通过 locator 按 trace_id 解析」。
- Diff: 数据模型 JSON 移除 trace_path 键值，新增路径约束段落。
- R1 verdict: Accepted
- **[Orchestrator Detection at R2]** Status: Accepted, confirmed by R2 escalated review: resolved

### Issue 4 · CLI pyautogui 导入重构未 scope
- source: converge_loop
- reviewer_backend: opencode-general
- Issue: Plan Task 6 Step 4 says "CLI 管理命令不得导入或初始化 pyautogui" but current cli.py has `import pyautogui` at MODULE LEVEL (line 10) and `from computer_use.core import ...` at lines 13-24. This requires restructuring the module's import architecture, which is a non-trivial refactor that the plan does not scope. Task 6 Step 1's test list does not include a test asserting audit commands don't import pyautogui.
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 将 Task 6 Step 4 重命名为「实现 CLI（含导入架构重构）」，列出 5 步导入重构指令（pyautogui/core 从模块顶层移到子命令处理函数内、_current_logical_position 内联导入、audit 子命令只导入无输入设备依赖的模块）。Step 1 测试列表新增 sys.modules 断言测试。
- Diff: Step 4 扩展为含导入重构 5 条指令 + 保证声明；Step 1 新增 sys.modules 断言测试条目。
- R1 verdict: Accepted
- **[Orchestrator Detection at R2]** Status: Accepted, confirmed by R2 escalated review: resolved

---

## Round 2 · Reviewer 阻断清单（待修复）

### Issue R2-1 · ExecutionContext dataclass 缺少 is_standalone 字段
- source: converge_loop
- reviewer_backend: opencode-general
- Issue: ExecutionContext dataclass 定义只有 task_id/trace_id/step_index/top_level 四字段，但 _handle_tool_call 伪代码使用 `ctx.is_standalone` 作为 standalone task 结束条件，该字段未定义。执行者无法推断 is_standalone 如何设置。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 ExecutionContext dataclass 新增 `is_standalone: bool` 字段，补充字段语义说明（_establish_context 按是否显式传入 task_id 设置）、新增「is_standalone 的设置」子节（与 top_level 的设置并列）、更新传播规则 1/5/6/7 显式写出 is_standalone 取值、修正 _handle_tool_call 伪代码注释说明 is_standalone 决定 finally 是否触发 standalone task 关闭。
- Diff: dataclass 定义 +6 字段语义段；新增「is_standalone 的设置」3 条；传播规则 1/5/6 显式补 is_standalone 取值；伪代码注释扩展为说明 catch-and-return 与 is_standalone 判定；Step 1 新增 2 条 is_standalone 相关测试。
- R2 verdict: Accepted
- **[Orchestrator Detection at R3]** Status: Accepted, confirmed by R3 escalated review: resolved

### Issue R2-2 · ExecutionContext 丢失 screenshot_path 字段
- source: converge_loop
- reviewer_backend: opencode-general
- Issue: 当前 trace_context dict 携带 screenshot_path（由 runner.py run_task_plan 每步截图后写入，由 _call_tool 读取传给 record_step）。ExecutionContext dataclass 只定义四字段，缺少 screenshot_path。不保留会导致 run_task_plan 每步截图功能静默失效。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 ExecutionContext dataclass 新增 `screenshot_path: str | None = None` 字段，补充字段语义说明（引用 runner.py:119-121 写入、mcp_server.py:651 读取的真实行号）；更新传播规则 5/6/7 明确嵌套 context 如何继承或设置 screenshot_path；Step 1 新增 screenshot_path 传播测试。
- Diff: dataclass 定义 +1 字段 + 字段语义段；传播规则 5（batch 继承父值）/6（run_task_plan 每步设置）/7（retry 默认 None）补 screenshot_path 处理；行为列表第 3 条补「继承 screenshot_path」；Step 1 新增 1 条 screenshot_path 测试。
- R2 verdict: Accepted
- **[Orchestrator Detection at R3]** Status: Accepted, confirmed by R3 escalated review: resolved

---

## Round 3 · Reviewer 阻断清单（待修复）

### Issue R3-1 · retry_step 传播规则 7 与继承模式矛盾
- source: converge_loop
- reviewer_backend: opencode-general
- Issue: retry_step 的 task_id 传播机制（传播规则 7：从 meta.json 派生）与其余嵌套入口的参数传递 + 父 context 继承模式直接矛盾。(A) is_standalone 设置节和 (B) Step 1 测试都说嵌套继承父 context，但 (C) 规则 7 硬编码独立派生。根因：签名变更节遗漏 retry_step 的 task_id 参数。
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 统一 retry_step 到与 _batch_tool/run_task_plan 完全相同的模式——签名新增 task_id 参数、新增 _dispatch_tool → retry_step 传播规则、规则 7 重写为参数接收 + 继承父 context is_standalone、删除全部 meta.json 派生逻辑、新增一致性验证段；附补 _handle_tool_call 三个辅助函数的一句话职责定义（处理 reviewer 建议）。
- Diff:
  1. 签名变更代码块：新增 `retry_step(..., task_id: str | None = None)` 定义，注释「与 _batch_tool / run_task_plan 同模式」。
  2. 调用链描述：分发目标补 `runner.retry_step(...)`；「目前均不接收」列表补 retry_step，引用 mcp_server.py 第 1134-1141 行。
  3. Step 1 测试（line 502）：从「meta.json 派生 task_id」改为「参数接收 task_id，继承父 is_standalone，None 报错」。
  4. 传播规则：原规则 4 之后插入新规则 5（`_dispatch_tool → runner.retry_step` 透传 task_id）；原 5/6/7 重编号为 6/7/8。
  5. 规则 8（原 7）重写：task_id 仅来自参数，删除 meta.json 派生、回退、standalone 分支；补 (a) task_closed 风险、(b) 孤儿 trace 风险说明；is_standalone=parent_ctx.is_standalone 与规则 6/7 一致。
  6. 新增「一致性验证」段：四个嵌套入口同模式（参数 task_id / top_level=False / 继承父 is_standalone / 不创建新 task）。
  7. 伪代码后新增「辅助函数职责」段：_establish_context / _finalize_trace_status / _ensure_standalone_task_closed 各一句话定义（处理 reviewer 建议）。
- R3 verdict: Accepted
- **[Orchestrator Detection at R4]** Status: Accepted, confirmed by R4 escalated review: resolved

---

## Round 4 · Reviewer 结论

verdict = **可执行**，零阻断。R3-B1 resolved。

### Suggestion R4-S1（不阻断，记录供实施注意）
- is_standalone 线程传播存在 pre-existing 缺口：签名变更只加了 task_id，未加 is_standalone 参数。嵌套函数无法访问 parent_ctx。但因 is_standalone 仅在 top_level=True 的 finally 中使用，嵌套 context（top_level=False）中该字段无运行时行为影响。实施时建议向 _dispatch_tool 等签名追加 is_standalone 参数。

---

## Blind Recheck · 阻断清单（注入主循环修复）

### Issue BR-1 · is_standalone 传播机制架构性断裂
- source: blind_recheck
- reviewer_backend: opencode-general
- Issue: 传播规则 6/7/8 要求嵌套 context 构造 is_standalone=parent_ctx.is_standalone，但签名变更只追加 task_id，无父 context 引用。
- Issue 归因: plan_defect
- plan_amendment_required: true
- Approach: 向 `_dispatch_tool` / `_batch_tool` / `run_task_plan` / `retry_step` 四个签名追加 `is_standalone: bool = False` 参数；传播规则 2–8 全部改为显式参数透传（is_standalone=is_standalone），删除对 `parent_ctx.is_standalone` 的引用；一致性验证段更新为"通过参数同时接收 task_id 和 is_standalone，不引用不存在的 parent_ctx"。
- Diff: 签名代码块 4 处 +is_standalone 参数；规则 2–5 补 `is_standalone=context.is_standalone` / `is_standalone=is_standalone`；规则 6/7/8 将 `is_standalone=parent_ctx.is_standalone` 与 `task_id=parent_task_id`/`task_id_from_param` 统一改为取参数值；一致性验证段重写。
- R5 verdict: (pending fresh reviewer)

### Issue BR-2 · 伪代码缺少 task 管理工具分支
- source: blind_recheck
- reviewer_backend: opencode-general
- Issue: 伪代码无条件调用 _establish_context，task 管理工具必须绕过。
- Issue 归因: plan_defect
- plan_amendment_required: true
- Approach: 在 `_handle_tool_call` 伪代码顶部新增 `_TASK_MANAGEMENT_TOOLS` frozenset（{start_task, finish_task, get_task, list_tasks, review_task_session}，与 Step 4 排除集合一致；review_task 不在其中）和早返回分支 `if name in _TASK_MANAGEMENT_TOOLS: return _dispatch_task_management_tool(...)`；辅助函数职责新增 `_dispatch_task_management_tool` 一句话定义。
- Diff: 伪代码新增 `_TASK_MANAGEMENT_TOOLS` 定义 + 早返回分支；辅助函数职责列表新增 `_dispatch_task_management_tool` 条目。
- R5 verdict: (pending fresh reviewer)

### Issue BR-3 · _establish_context 在 try 块外
- source: blind_recheck
- reviewer_backend: opencode-general
- Issue: TaskNotFoundError/TaskClosedError 会逃出 catch-and-return。
- Issue 归因: plan_defect
- plan_amendment_required: true
- Approach: 将 `_establish_context` 移入 try 块；try 块前初始化 `ctx: ExecutionContext | None = None`；新增 `except TaskNotFoundError` / `except TaskClosedError` / `except TraceTaskConflictError` 三个结构化 JSON 返回分支（含 task_id/trace_id/timestamp）；通用 `except Exception` 内对 `ctx is not None` 才调 `_finalize_trace_status`；finally 改为 `if ctx is not None and ctx.top_level and ctx.is_standalone` 判空。
- Diff: 伪代码 ctx 初始化移到 try 外、_establish_context 移入 try、新增 3 个 task 专属 except 分支、finally 加 `ctx is not None` 判空。
- R5 verdict: (pending fresh reviewer)

### Issue BR-4 · 伪代码缺少 register_trace 调用
- source: blind_recheck
- reviewer_backend: opencode-general
- Issue: 行为列表要求"执行前登记 trace"，伪代码中无 register_trace。
- Issue 归因: plan_defect
- plan_amendment_required: true
- Approach: 将 register_trace 折入 `_establish_context`（单一职责辅助函数），在其描述中新增第 (2)(3) 步：生成 trace_id、调用 `task_session.register_trace` 在执行真实动作前登记；明确 register_trace 失败（task_closed / trace_task_conflict）抛出异常阻止后续 `_call_tool` 执行真实鼠标键盘动作（满足 Step 1 测试）。伪代码注释标注 _establish_context 内含 register_trace。
- Diff: `_establish_context` 职责描述扩展为 4 步含 register_trace + 失败阻断说明；伪代码 try 块注释标注 register_trace 位置；TaskNotFoundError except 注释说明登记失败不执行真实动作。
- R5 verdict: (pending fresh reviewer)

### Round 5 · 附加建议处理（blind review suggestions）

以下建议在修复 4 个 blocking issues 时一并处理：

1. **_establish_context trace_id 生成（suggestion）**：`_establish_context` 职责第 (2) 步新增"生成 trace_id（或复用 args 中显式传入的 trace_id）"。
2. **_call_tool Optional context 矛盾（suggestion）**：签名注释补充说明 context 保持 Optional 仅为防御，唯一 None 路径是 task 管理工具经 `_dispatch_task_management_tool` 直接分发。
3. **task.json 缺少 active_trace_count（suggestion）**：task.json 示例新增 `"active_trace_count": 0`，与 Task 3 Step 4 重计算字段列表一致。

---

## Round 2 · 附加建议处理记录

以下建议在修复 blocking issues 时一并处理：

1. **retry_step task_id 传播（Suggestion A / minimum_patch antipattern 修复）**：传播规则新增第 7 条，明确 retry_step 从被重放 trace 的 meta.json 派生 task_id（`read_trace_meta(trace_id)["task_id"]`），构造 `top_level=False, is_standalone=<父值>` 嵌套 context，不创建新 task，screenshot_path 默认 None。同时在 top_level 的设置、top_level 判定引言、is_standalone 的设置三处补 retry_step 覆盖。此修复打破 R1 reviewer 标注的 minimum_patch antipattern（B1 修复遗漏 retry_step 调用链）。
2. **_handle_tool_call 伪代码 raise → catch-and-return（Suggestion B）**：伪代码 except 块从 `raise` 改为 `return json.dumps({"error": message})`，保持现有 mcp_server.py:1408-1416 的 catch-and-return 语义不改变，仅新增 `_finalize_trace_status` 和 finally 中的 `_ensure_standalone_task_closed`。
3. **_call_tool 向后兼容声明移除（Suggestion C）**：签名注释从「向后兼容：仍接受旧 trace_context dict，内部转换为 context」改为「所有内部调用方同步更新为传 context，不保留旧 trace_context dict 入口」。

---

## Round 1 · 附加建议处理记录

以下高价值建议在修复 blocking issues 时一并处理：

1. **review_task vs review_task_session 关系说明**：在 Task 4 Step 3 新增段落，明确两者输入键（trace_id vs task_id）和输出粒度（单 trace vs 多 trace 聚合）不重叠。
2. **_attach_task_context 排除集合枚举**：在 Task 5 Step 4 枚举完整排除集合（start_task、finish_task、get_task、list_tasks、review_task_session、review_task）。
3. **task_id 从 trace 记录剥离**：在 Task 5 Step 3 新增「trace 记录中的 task_id 处理」子节，明确 record_step 前从 args 中移除 task_id 键。Step 1 新增对应测试。
4. **generate_report 写语义澄清**：在 Task 2 Step 3 新增段落，明确 generate_report 使用 resolve_trace_root 定位已存在目录，对不存在 trace 是错误而非创建。
5. **TOCTOU 竞争缓解**：在核心决策 #5 新增 TOCTOU 已知限制条目，缓解策略为归属文件使用 O_CREAT|O_EXCL（open "x" 模式）。
6. **Task 2 rebase 检查点**：在 Task 2 新增 Step 0，要求实施前 rebase 到前一计划的 trace.py 最终签名，合并 create/resolve 分离、日期分区和延迟 artifact 目录。
