# 计划：Computer Use MCP 智能化执行与复盘系统

## 完成状态

- 状态：已完成。
- 实现提交：`ecb1f5d feat: smart executor, structured trace, composite tools and safety fixes`。
- 后续验收与修复：`8fa2168`、`3be3cb6`、`e96dcfc`。
- Converge 归档：`.converge/done/20260614-smart-executor-and-trace/`、`.converge/done/20260614-project-acceptance/`、`.converge/done/20260615-mcp-audit-remediation-acceptance/`。
- 说明：本文件此前因未移动而错误停留在 `active/`，本次仅纠正计划状态。

## 背景与问题

当前 `computer-use-mcp` 已提供 20 个原子工具（点击、移动、截图、键盘、查找控件、启动应用等），可作为 Kimi Code / opencode 的本地 GUI 自动化后端。但在真实任务中暴露出三个问题：

1. **往返开销高**：模型每做一次动作（点击、输入、截图）都要走一次 MCP 调用 → 模型推理 → 下一次 MCP 调用的完整回合。实测中相邻两次 MCP 请求间隔可达 40–1000 秒，而 MCP server 内部执行仅毫秒级。
2. **观察粒度粗**：模型只能通过 `screenshot` 看屏幕，再自己估算坐标；缺少 chrome-devtools 式的结构化 UI 快照（accessibility tree + 元素 ID）。
3. **无复盘能力**：虽然有日志，但没有按任务组织的结构化执行轨迹（trace），无法系统性地分析错误、沉淀经验、持续优化。

## 根因分析

- chrome-devtools MCP 快的关键：
  - 使用 Puppeteer/CDP，事件是浏览器内部合成，无需物理鼠标移动；
  - 提供 `take_snapshot` 返回带稳定 UID 的 accessibility tree，模型可凭 UID 操作，跳过截图→坐标的循环；
  - 工具层面就有复合能力（`fill_form`、`navigate_page`、`wait_for`）。
- computer-use MCP 慢的关键：
  - 每个动作依赖真实 `pyautogui` 输入，且需要模型先看图再决策；
  - 没有结构化 UI 快照，模型不得不频繁截图；
  - 复合/批处理能力弱，模型不会天然把多步打包成 `batch`。

> 注意：实测已证明延迟不在 MCP server 内部，而在“模型收到结果 → 生成下一步工具调用”这一段。因此优化方向不是让 server 变快，而是**减少模型需要决策的次数、每次给模型更丰富的信息、并把常见序列封装成高层工具**。

## 设计目标

1. **功能完整性**：保留并增强所有键鼠宏能力 + 截图能力。
2. **ReAct 友好**：让外部多模态模型能高效地完成“观察 → 推理 → 行动”循环。
3. **高效率**：通过结构化快照、复合工具和任务级批处理，把常见多步任务压缩到少数几次 MCP 往返。
4. **可复盘**：每一次任务都生成结构化 trace（步骤、截图、状态、错误、耗时），支持事后回放和总结。

## 架构原则

- **MCP server 仍是执行器**：复杂的 LLM 推理保留在 Kimi Code / opencode 侧，避免在 server 里再跑一个 LLM。
- **server 只提供确定性执行能力**：模型可以提交“计划”，由 server 内部以确定性方式执行，并返回完整 trace。循环、条件、重试由上层 Agent 负责，不由 server 实现。
- **向后兼容**：现有原子工具全部保留；新能力以新增工具和增强 `batch` 的形式提供。
- **不引入 OCR**：多模态模型可直接读图，MCP 不再提供 OCR 工具或视觉回退；复合工具只依赖 UIA / 控件名，找不到时返回结构化 `not_found`，由上层模型决定下一步。现有 `screenshot_dir` / `log_dir` 仍沿用项目原有默认值，与新引入的 `trace_dir` 中性默认路径独立，后续如需统一可单独评估。

## Trace 数据格式（先定义 schema，再实现记录）

所有任务级、批量级、单工具级调用都写入同一格式的 JSONL 记录。trace 目录通过 `config.yaml` 的 `trace_dir` 配置，默认 `~/.computer-use/traces/`。

### trace_id 生命周期

- `run_task_plan` 和 `batch`：
  - 若调用方提供 `trace_id`，则复用该值；
  - 否则由 server 生成：`{YYYYMMDD-HHMMSS}-{6 位随机 slug}`。
- 单个原子工具调用：
  - 每次调用生成一个独立 trace_id，格式同上；
  - 写入单条 trace 记录文件，便于事后审计。
- `trace_id` 在单次调用周期内保持不变；`batch` 内所有子步骤共享同一个 `trace_id`。

### 单条记录 schema

```json
{
  "trace_id": "20260614-123045-a1b2c3",
  "step_index": 0,
  "tool": "click",
  "args": {"target_name": "工具"},
  "result": {"clicked": true, "mode": "uia"},
  "start_time": "2026-06-14T12:30:45.123+08:00",
  "duration_ms": 45,
  "screenshot_path": "...",
  "ui_snapshot_path": "...",
  "error_kind": null,
  "error_message": null
}
```

字段说明：

- `trace_id`：本次任务/调用唯一标识。
- `step_index`：`batch` 或 `run_task_plan` 内的步骤序号；单工具调用为 `0`。retry 产生的记录使用字符串形式 `"{original}.retry.{n}"`（如 `"3.retry.1"`），因此 trace 消费者应将 `step_index` 视为 `int | str`。
- `tool` / `args` / `result`：工具名、参数、返回结果。
- `start_time`：ISO 8601，本地时区带偏移。
- `duration_ms`：server 内部执行耗时，不含 MCP 传输和模型推理时间。
- `screenshot_path`：该步骤关联的截图路径（若有）。
- `ui_snapshot_path`：该步骤关联的 UI 快照路径（若有）。
- `error_kind`：`null` / `safety_block` / `ui_not_found` / `stale_uid` / `timeout` / `fail_safe` / `unknown`。
- `error_message`：人类可读的错误描述。

### 文件组织

```
~/.computer-use/traces/
  <trace_id>/
    trace.jsonl
    report.md          # 仅 run_task_plan 生成
    screenshots/
    snapshots/
```

默认路径为中性命名，不携带客户端特定环境；可通过 `config.yaml` 覆盖。

## 具体方案

### 1. 新增 `get_ui_snapshot` 工具（结构化观察）

返回当前屏幕的 UI 自动化树摘要 + 当前焦点窗口 + 光标位置 + 可选截图路径。

- 使用 `uiautomation` 遍历前台窗口或桌面的控件树；
- 默认 `scope=foreground` 以控制耗时；支持 `scope=desktop` 但需接受更大开销；
- 为每个控件生成 **snapshot-scoped 自包含句柄**（编码运行时 UIA handle + 控件路径），并附带 `bbox`、`name`、`control_type`、`class_name`、`path` 等消歧元数据；
- 可附加 `screenshot=True` 同时保存一张截图并返回路径。

#### UID / 句柄语义

- **生成方式**：句柄由 `get_ui_snapshot` 调用时临时生成，基于控件运行时 UIA handle + 控件路径字符串，编码为单个自包含字符串；不跨 MCP 会话持久化，也不在 server 内存中维护映射表。
- **自包含快照**：每次 `get_ui_snapshot` 返回全新的句柄集合；句柄不缓存、不继承自上一次快照。
- **失效语义**：若窗口刷新或 UI 重排导致句柄失效，`click_by_uid` 返回 `{"error": "stale_uid"}`；调用方应重新调用 `get_ui_snapshot` 获取新句柄。
- **无持久映射**：server 不在内存或磁盘维护 UID 映射表；句柄仅在返回给调用方的当前快照对象内有效。

收益：模型一次调用即可知道“有哪些可点击元素、它们在哪”，不必反复截图估算坐标。

### 2. 新增 UID 操作与复合工具

- `click_by_uid(uid)`：根据 `get_ui_snapshot` 返回的 snapshot-scoped 自包含句柄点击；句柄失效时返回 `{"error": "stale_uid"}`。
- `click_by_text(text, ...)`：在 UIA 树中按显示文本做模糊搜索，返回候选列表或点击最匹配项；
  - 仅依赖 UIA 控件名 / 显示文本，不引入 OCR 或视觉回退；
  - 未命中时返回结构化 `{"error": "ui_not_found", "candidates": [...]}`，由上层多模态模型看图决策；
  - 与现有 `click(target_name=...)` 的区别：`target_name` 按 UIA 控件名精确/包含匹配；`click_by_text` 搜索控件上的显示文本，支持跨控件类型的模糊匹配。
  - 命中时执行 `click(target_name=text)`，因此 safety 检查复用现有路径；若 UIA 句柄失效导致点击失败，返回 `ui_not_found`。
- `open_menu(path=["工具", "文件和注册表查找器"])`：server 内部依次点击菜单路径；仅使用 UIA，不引入 OCR/视觉回退；对自定义绘制菜单无法定位时返回 `ui_not_found`。
  - 执行逻辑：对 `path` 中每个文本，调用 `find_control(name=text, scope="foreground")`；命中则点击其中心；未命中即停止并返回 `{"error": "ui_not_found", "attempted": text, "candidates": [...]}`。
  - 每步点击后等待 `interval` 秒（默认 0.3），让菜单展开。
- `fill_form(fields=[{"name": "用户名", "value": "xxx"}, ...])`：批量填表，仅依赖 UIA 控件定位。
  - 每个 field 通过 `name`（UIA 控件名，支持 `match`）找到输入框，先 `click` 聚焦再 `type_text` 输入。
  - 若某 field 未找到，停止并返回 `{"error": "ui_not_found", "field": field, "candidates": [...]}`。
  - 输入前调用 `validate_text_input` 检查危险文本。
- `scroll_until(target_text, direction, max_attempts)`：滚动直到目标文本在 UIA 树中出现；仅依赖 UIA。
  - 每次滚动后调用 `find_control(name=target_text, scope="foreground")`；命中即返回 `{"found": true, "attempts": n, "control": {...}}`。
  - 达到 `max_attempts` 仍未命中返回 `{"error": "ui_not_found", "attempts": max_attempts}`。

收益：把常见多步模式封装成一次 MCP 调用，减少模型回合数；同时保持“找不到就上报，不替模型做视觉判断”的边界。

### 3. 增强 `batch`：确定性顺序执行 + 每步快照

`batch` 只扩展以下字段，不引入条件、循环、变量或通用工作流能力：

- `capture_snapshot`：该步骤前后是否截图并记录状态；
- `stop_on_error`（已存在，默认 `true`）：遇到错误是否停止；
- `final_screenshot`（已存在，默认 `false`）：执行完成后是否追加最终截图。

> 设计边界说明：`batch` 是**确定性的执行快捷键**，用于把模型已经规划好的固定序列一次下发；复杂的分支决策、循环、重试策略、错误恢复由上层 Agent 负责。`batch` 不会变成工作流引擎或状态机，也不替代 Agent 的 ReAct 循环。

示例：

```json
{
  "actions": [
    {"tool": "launch_app", "args": {"name": "HiBit Uninstaller"}},
    {"tool": "wait_for_window", "args": {"name": "HiBit Uninstaller", "timeout": 10}},
    {"tool": "open_menu", "args": {"path": ["工具", "文件和注册表查找器"]}, "capture_snapshot": true},
    {"tool": "sleep", "args": {"duration": 0.5}}
  ],
  "stop_on_error": true,
  "final_screenshot": true,
  "trace_id": "hibit-demo-001"
}
```

收益：模型把一段连续工作流一次性交给 server，server 自己处理顺序、等待、截图、错误；同时保持 server 轻量、无 LLM、无工作流语义。

### 4. 新增 `run_task_plan` 工具（任务级执行）

允许模型提交一个高层计划数组，server 内部执行并返回：

- `trace_id`：本次任务唯一 ID；
- `results`：每步结果；
- `final_state_path`：最终 UI 快照路径（若启用）；
- `report_path`：复盘报告文件路径。

`run_task_plan` 与 `batch` 的区别：

- **输入层级不同**：`batch` 接收“低层工具序列”；`run_task_plan` 接收“目标导向的结构化步骤”，每个 step 是 `{"tool": <tool_name>, "args": <args_dict>}`，支持所有已注册 MCP 工具（含 `batch`、`open_menu` 等复合工具）。第一阶段不引入 `{"intent": ...}` 模板语法；所有步骤必须是可直接映射到具体 tool 的结构化调用。
- **trace 保证不同**：`run_task_plan` **必须**生成 `trace.jsonl` + `report.md` 并返回稳定 `trace_id`；`batch` 是通用执行原语，可记录 trace 但不强制生成报告。
- **职责定位不同**：`run_task_plan` 是任务级入口；`batch` 是 server 内部或被外部直接调用的执行原语。

**输入 schema**：

```json
{
  "trace_id": "hibit-demo-001",
  "goal": "打开 HiBit 的文件和注册表查找器",
  "steps": [
    {"tool": "launch_app", "args": {"name": "HiBit Uninstaller"}},
    {"tool": "wait_for_window", "args": {"name": "HiBit Uninstaller", "timeout": 10}},
    {"tool": "open_menu", "args": {"path": ["工具", "文件和注册表查找器"]}},
    {"tool": "sleep", "args": {"duration": 0.5}}
  ],
  "final_state": true
}
```

- `trace_id`（可选）：复用已有 ID；省略则 server 生成。
- `goal`（可选）：任务目标文本，写入 `report.md`；省略时留空。
- `steps`：步骤数组。每个 step 是 `{"tool": <tool_name>, "args": <args_dict>}`，支持所有已注册 MCP 工具（含 `batch`、`open_menu` 等复合工具）。
- `final_state`（默认 `false`）：任务结束时是否调用 `get_ui_snapshot(scope="foreground", include_screenshot=true)` 并保存，结果路径写入 `report.md`。
- `capture_screenshots`（默认 `true`）：是否在 `run_task_plan` 生命周期内为每个 step 自动追加截图（通过内部调用 `screenshot`），截图路径写入 trace。

**执行规则**：

1. 每个 step 直接调用 `_call_tool`，使用共享 `trace_id` 和递增 `step_index`。
2. step 索引从 1 开始；若 step 本身是 `batch`，batch 内部子步骤沿用 task 的 `trace_id`，step_index 使用 `"{parent_step_index}.{sub_index}"` 命名空间（如 `"1.1"`、`"1.2"`），避免与 task 其他步骤冲突。
3. 遇到 error 时停止后续 step（与 `batch.stop_on_error=true` 行为一致），但记录失败步骤的 error_kind。
4. 任务结束后生成 `report.md`：包含 goal、起止时间、步骤概览、总耗时、错误摘要、截图索引、`final_state` 路径、改进建议占位。

**第一阶段约束**：`run_task_plan` 只接受结构化描述（工具调用或预定义模板），不解析自由自然语言。server 内部把每个步骤确定性映射为 `batch` 或原子工具执行。server 内部**不调用 LLM**；任何自然语言意图解析都保留在客户端。

### 5. 结构化 Trace 与复盘

新增 `computer_use/trace.py`：

- 每个 `run_task_plan` / `batch` / 单独工具调用都会生成一条 trace 记录；
- trace 文件：`~/.computer-use/traces/<trace_id>/trace.jsonl`（可配置）；
- 每条记录字段见前文“Trace 数据格式”；
- 任务结束时生成 `report.md`：goal、起止时间、步骤概览、总耗时、错误、截图索引、`final_state` 路径、改进建议占位。goal 来自 `run_task_plan` 的 `goal` 参数；未提供时 goal 字段为空。

新增 `computer_use/review.py`：

- 提供 `review_task(trace_id)` 工具，读取 trace 并生成结构化复盘摘要；
- `review_task` 是 server 内的**确定性文本摘要工具**，不调用 LLM。输出包含：任务目标、总步骤数、成功/失败/重试统计、错误类型分布、平均耗时、截图路径列表、改进建议占位。
- 未来可接入 LLM 自动总结错误模式（由客户端模型调用，不在 server 内）。

### 6. 错误恢复与经验沉淀

- 在 `trace.jsonl` 中标记错误类型：`safety_block`、`ui_not_found`、`stale_uid`、`timeout`、`fail_safe`、`unknown`。
- 提供 `retry_step(trace_id, step_index, mode="single")` 工具，从某一步重新执行。
  - `mode="single"`（默认）：仅重执行指定 step 一次，使用原记录的 `tool` 和 `args`，复用原 `trace_id`，新 step_index 为原 `step_index` 加 `.retry.N`（字符串形式，如 `"3.retry.1"`）。结果追加到原 `trace.jsonl`，不覆盖旧记录。
  - `mode="from_step"`：从指定 step 开始顺序重放后续所有 step；每个重放步骤都作为新记录追加，step_index 使用原索引加 `.retry.N`。
  - 重放时**不直接复用旧的坐标或 UID 结果**；所有点击/输入操作重新走当前 UIA 查找或 safety 校验。即：`retry_step` 只是按原 `tool`/`args` 重新调用 `_call_tool`，由底层工具在当前 UI 状态下重新定位。
  - 若原 step 是 `click(x, y)` 坐标模式，重放时仍使用相同坐标，但 safety 校验（坐标边界、目标窗口白名单）会重新执行。
  - UI 状态已变化导致重放失败时，返回当前错误（如 `ui_not_found`、`safety_block`），并在 `error_message` 中注明是 retry 重放失败。
  - retry 不自动生成新的 `report.md`；需要更新报告时由客户端调用 `review_task` 后自行决定是否重新生成。
- **经验框架**：标记为 `(future work)`。本阶段不在 `~/.computer-use/experience/` 下实现持久化经验条目，仅在 `report.md` 中预留“改进建议”占位；后续由复盘流程填充。

## 推荐模块结构

```
computer_use/
  mcp_server.py      # MCP 传输 + 工具注册表（瘦身）
  core.py            # 底层键鼠/截图/坐标系
  ui_automation.py   # UIA 查找/等待
  safety.py          # 安全策略
  config.py          # 配置加载
  launcher.py        # 应用启动
  snapshot.py        # NEW: UI 快照、get_ui_snapshot
  composite.py       # NEW: click_by_uid, click_by_text, open_menu, fill_form, scroll_until
  runner.py          # NEW: 增强 batch + run_task_plan
  trace.py           # NEW: 结构化 trace 记录
  review.py          # NEW: 复盘报告生成
```

## 实施顺序

按优先级分 3 个阶段：

### Trace Schema 定义（前置）

1. 在 `config.yaml` 中加入 `trace_dir` 默认路径 `~/.computer-use/traces/`；
2. 在 `trace.py` 中定义 `TraceRecord` schema、`trace_id` 生成策略、目录创建与写入接口；
3. 改造 `_call_tool` 使其自动记录每条工具调用的结构化 trace（单工具调用生成独立 trace_id）。

### 阶段 1：观察增强 + Trace 落地（快速见效）

1. 实现 `snapshot.py` 和 `get_ui_snapshot` 工具；
2. 在 `batch` 中加入 `capture_snapshot` 支持，并记录子步骤 trace；
3. 更新 `docs/api.md`、`docs/overview.md`、`docs/pitfalls.md`（移除 OCR 建议）和 `docs/audit-checklist.md`（标注 OCR 审计项为历史项）。

### 阶段 2：复合工具与高效执行

1. 实现 `composite.py`（`click_by_uid`, `click_by_text`, `open_menu`, `fill_form`, `scroll_until`）；
2. 实现 `run_task_plan`（仅结构化描述，无 LLM，内部映射为 batch 或原子工具）。

### 阶段 3：复盘与持续优化

1. 实现 `review.py` 和 `review_task` 工具；
2. 添加 `retry_step`；
3. 经验框架保持 `(future work)`，本阶段不实现持久化存储；
4. 更新部署文档和示例。

## 验收标准

- `get_ui_snapshot` 能在 2 秒内返回当前前台窗口的控件树 + 截图路径；
- `open_menu(["工具", "文件和注册表查找器"])` 能在一次 MCP 调用内打开目标窗口；
- `batch` 执行一段 5 步工作流的总耗时 <= 各原子操作耗时之和 + 500ms；
- 每次 `batch` 或 `run_task_plan` 调用都会生成可在磁盘上找到的 `trace.jsonl`；
- 每次 `run_task_plan` 生成 `report.md`（goal 来自输入参数或为空）；
- 单独工具调用也记录 trace，生成独立 trace_id 和单条记录；
- `click_by_uid` 在句柄失效时返回 `{"error": "stale_uid"}`；
- 现有测试全部通过，新增测试覆盖 snapshot、composite、runner、trace 模块。

## 风险与取舍

- **UIA 覆盖不足 / 遍历耗时**：自定义绘制控件（如 HiBit 标题栏）可能无法通过 UIA 定位；`get_ui_snapshot` 默认只遍历前台窗口以控制耗时，避免完整桌面遍历超过 2 秒；`click_by_text` / `open_menu` 仅依赖 UIA，找不到时返回 `ui_not_found`，由上层多模态模型看图决策，不在 server 内做 OCR。
- **MCP server 变重**：新增模块会让启动时间略有增加；可通过延迟加载（如 `uiautomation`）缓解。
- **过度封装 / 最小 MCP 原则张力**：复合工具不应该隐藏太多细节，否则模型在异常情况下难以调试。每个复合工具都要返回足够详细的内部步骤信息。`batch` 增强是确定性执行快捷键，不替代上层 Agent 的 ReAct 循环。
- **不引入 LLM 到 server**：本计划坚持把 LLM 留在客户端，server 只执行确定性逻辑，避免架构错位。

## 下一步

等待用户确认本计划后，进入 Trace Schema 定义与阶段 1 实施。
