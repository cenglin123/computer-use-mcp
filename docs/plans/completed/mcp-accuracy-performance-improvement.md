# MCP 调用准确度与性能改进计划

## 背景

2026-06-20，使用 Kimi 模型执行一次原神游戏内“对话回顾”查看任务时，出现三类严重问题：

1. **准确度失败**：目标是点击左上角第二个“对话回顾”按钮，但连续多次点到左侧“自动”按钮区域；错误坐标集中在 `x≈108`，最终正确坐标为 `x=204`，偏差约 96 像素。
2. **性能退化**：随着截图、UIA 快照和工具输出进入上下文，Kimi 单轮响应从数秒退化到 1-4 分钟。
3. **复盘困难**：底层 trace 已记录坐标和结果，但 `tasks review` 只暴露汇总信息，执行者需要人工回看会话才能还原“点偏了 100 像素”。

本计划的目标不是重新设计 MCP，而是补齐四条闭环并沉淀执行示例：**操作准确度门控**、**上下文预算门控**、**复盘 detail/export**、**执行纪律与示例**。

> **范围说明**：本计划改进的主要是 **Agent 使用模式**（skill/guidance 文档、MCP 工具的 review 层 API、CLI 帮助文案、示例沉淀），而非 MCP server 的输入设备底层（`core.py`、`safety.py` 不在改动范围）。主线 C 是唯一的代码层改动，限定在 **review 层及其 MCP 接线**（`review.py`、`mcp_server.py` 的 review 分发、`tools/schemas.py` 的 review schema；`trace.py` 仅读已有数据），不触碰输入设备路径。

## 实证记录

### 原神任务关键操作

| 时间 (UTC+8) | Task ID | Trace ID | 操作 | 关键坐标 | 结果 |
|-------------|---------|----------|------|---------|------|
| 06:30:21 | task-20260620-063020-5hn6tg | 20260620-063020-wxujpd | screenshot | - | 首次截到原神对话界面，对话框显示派蒙台词与两个选项 |
| 06:30:51 | task-20260620-063050-2m0886 | 20260620-063050-9c98xb | click | x=150, y=40 | 点中“自动”按钮右侧，画面无变化 |
| 06:33:24 | task-20260620-063323-pyp19v | 20260620-063323-x8vgs3 | click | x=108, y=45 | 仍偏左，落在“自动”区域，按钮显示禁用符号 |
| 06:36:31 | task-20260620-063630-2580jq | 20260620-063630-9f62qh | click | x=108, y=45 | 重复错误坐标 |
| 06:45:51 | task-20260620-064550-ukbe7n | 20260620-064550-ajuy1y | click | x=108, y=42 | 仍偏左 |
| 07:00:54 | task-20260620-070053-vtog8w | 20260620-070053-c48uuc | move_to | x=108, y=42 | 再次移动到错误位置 |
| 10:24:01 | task-20260620-102401-boi6kf | 20260620-102401-5vfmnj | click | x=204, y=45 | 正确位置，成功打开“对话回顾”面板 |
| 10:31:01 | task-20260620-103100-27otnc | 20260620-103100-tr6csk | click | x=1842, y=42 | 关闭对话回顾面板 |

关键截图文件均保存在 `C:\Users\chenr\.computer-use\screenshots\`：

- `screenshot_20260620T063021_612_m1.png`：初始状态。
- `screenshot_20260620T063155_724_m1.png`：错误点击 `x=150, y=40` 后。
- `screenshot_20260620T064222_347_m1.png`：多次错误点击后仍无变化。
- `screenshot_20260620T102432_354_m1.png`：正确点击后打开的“对话回顾”面板。

### Kimi 会话性能数据

会话 ID：`ses_11c4f9175ffeeAuisz0cTIZBTM`。

opencode SQLite 记录显示：

- `messages=114`
- `parts=392`
- `tokens_input=368,644`
- `tokens_cache_read=8,724,215`
- `tokens_output=21,828`

按上下文规模聚合的响应耗时：

| 上下文规模 | 轮数 | 平均耗时 | 最短 | 最长 |
|-----------|-----:|---------:|-----:|-----:|
| <50k | 16 | 7.7s | 3.0s | 23.2s |
| 50k-80k | 25 | 10.7s | 5.1s | 28.1s |
| 80k-100k | 9 | 28.4s | 5.9s | 60.2s |
| 100k-120k | 21 | 99.0s | 22.7s | 164.9s |
| 120k+ | 29 | 132.4s | 29.1s | 246.6s |

性能退化的直接证据：

- 06:21:24：`get_ui_snapshot(scope="desktop", include_screenshot=true)` 产生约 374KB 输出，被截断保存到 tool-output。
- 06:22:01：Agent 读取格式化后的 UIA JSON，输出约 55KB 进入上下文。
- 06:23:10：再次 `get_ui_snapshot(scope="desktop", include_screenshot=true)`，产生约 431KB 输出。
- 06:29:59：通过 CLI 执行 `python -m computer_use screenshot --monitor 1 > screenshot_path.txt; Get-Content screenshot_path.txt`，CLI `screenshot` 输出 base64 PNG 到 stdout，生成约 39KB 工具输出；下一轮上下文从约 65k token 跳到约 92k token。
- 后续每次 `Read` PNG 虽然文本输出只有约 23 字节，但会把图像作为多模态内容挂入上下文，每张约增加 2.8k-3k token。

结论：MCP `screenshot` 工具本身只返回路径，设计方向正确；上下文膨胀主要来自 **桌面级 UIA 大 JSON、CLI base64 截图、连续读取多张 PNG**。

## 问题清单

### P0：缺少上下文预算门控

- `get_ui_snapshot(scope="desktop")` 在桌面范围会产生数十万字符输出，尤其在 `include_screenshot=true` 时更容易诱导后续读取截图和完整 JSON。
- CLI `python -m computer_use screenshot` 默认输出 base64 PNG，Agent 误用后会把图像数据直接写入工具输出和上下文。
- Agent 反复读取历史截图和大 JSON，导致 Kimi 在 100k token 后进入分钟级响应。

### P0：坐标点击缺少落点预验证

- Agent 直接点击预估坐标，没有先 `move_to` 到目标附近并截图确认红色光标标记。
- 点击无效后，继续在原错误区域微调或重复点击，没有强制重新观察。
- “工具返回 clicked=true”被误当作“业务点击成功”，忽略了 GUI 状态没有变化。

### P1：Skill/Guidance 未成为任务启动门控

- `skills/computer-use/SKILL.md` 和 `computer_use.guidance` 已包含关键纪律，但会话中读取 skill 的时间太晚，且读取后没有转化为硬性步骤。
- 问题不是“文档不存在”，而是“客户端/Agent 未在使用 computer-use 前加载并执行”。

### P1：Task/Trace Review 只暴露汇总，不暴露 step detail

- 底层 `trace.jsonl` 已记录 `args`、`result`、`screenshot_path`、`ui_snapshot_path`。
- 例如 `20260620-063050-9c98xb/trace.jsonl` 已记录 `args: {"x": 150, "y": 40}`；`20260620-102401-5vfmnj/trace.jsonl` 已记录 `args: {"x": 204, "y": 45}`。
- 但 `computer_use tasks review <task_id>` 只输出总步数、耗时、错误分布、截图/快照索引，不输出逐步参数和结果，导致复盘者看不到关键坐标。

### P2：无效探索放大成本（本计划延期处理）

- 早期会话在 GUI 任务中尝试了 OCR 可用性、Chrome DevTools、Windows Runtime、PowerShell 自写窗口激活脚本等旁路探索。
- 这些探索没有直接服务于“点击当前原神页面对话回顾按钮”，增加了工具调用和上下文噪声。

> **延期理由**：P2 的根因是 Agent 在任务启动阶段缺乏明确的问题边界约束，倾向探索旁路工具。这属于客户端 Agent 调度策略层（何时收敛工具选择），不在本 MCP server + skill/guidance 计划范围内。本计划的主线 A/B/D 通过强化门控和示例间接缓解（让 Agent 更早进入正确工具链），但 P2 的彻底解决需要客户端侧的“任务边界声明”机制，留待后续计划。

## 根因分析

| 根因 | 判断 |
|------|-------------|
| 视觉空间估算错误 | 确认存在。错误坐标与正确坐标相差约 96 像素。 |
| 坐标系工具缺陷 | 暂无证据。MCP 坐标与截图像素 1:1 的设计仍成立。 |
| 未建立落点验证闭环 | 确认存在。未先 `move_to` + `screenshot` 验证红色光标。 |
| Skill 未成为前置门控 | 确认存在。已有 skill/guidance，但没有在任务开始时约束行为。 |
| 截图工具返回 base64 | 对 MCP 工具不成立；对 CLI `computer_use screenshot` 成立。 |
| UIA/截图上下文管理粗放 | 确认存在。桌面级 UIA JSON、CLI base64、多张 PNG 共同导致上下文膨胀。 |
| Trace 数据维度不足 | 底层不成立；review/export 暴露层成立。 |
| 缺乏失败止损 | 确认存在。连续失败后仍重复错误坐标。 |
| 任务启动阶段缺乏问题边界约束（P2） | 确认存在。Agent 倾向探索旁路工具（OCR、Chrome DevTools 等）。本计划延期处理，理由见 P2 段。 |

## 改进方案

### 主线 A：操作准确度门控

目标：坐标输入不再靠一次视觉估算直接点击。

> **与现有 guidance 的关系**：`guidance.py` 已有“点击后截图验证业务成功”的步骤（post-click 验证）。本主线的 `move_to → screenshot → click` 三段式是 **pre-click 落点预验证**，与现有 post-click 验证互补而非替换——两者结合形成“点前确认落点、点后确认状态”的完整闭环。

执行项：

1. 更新 `skills/computer-use/SKILL.md` 和 `computer_use/guidance.py`，加入“坐标点击三段式”：
   - `move_to(x, y)` 到预估点；
   - `screenshot(monitor=1)` 检查红色光标是否落在目标中心；
   - 确认后才 `click(x, y)`。
2. 增加失败止损规则：同一目标坐标点击后 GUI 状态无变化，最多允许一次重新测量；禁止在原坐标附近 3-5 像素盲调。
3. 对自绘界面明确推荐流程：优先 `foreground` 快照或截图；UIA 只能定位窗口时，不用 `click_by_uid` 点击窗口中心作为业务按钮。
4. 在 `docs/api.md` 补充“clicked=true 只表示输入事件发出，不表示业务状态成功”。目标文件明确为 `docs/api.md`，因为该规则属于工具语义说明，归 api 文档管辖，不写入 `docs/overview.md`。

验收：

- Skill/guidance 中能明确读到 `move_to -> screenshot -> click` 流程。
- 文档中明确“点击后需通过新截图、UIA 查询或状态变化验证业务成功”。
- 不引入会自动点击的硬编码游戏坐标规则。

### 主线 B：上下文预算门控

目标：防止 Agent 把大图、大 UIA JSON 或 base64 截图塞进上下文。

执行项：

1. 更新 `skills/computer-use/SKILL.md` 和 `computer_use/guidance.py`：
   - 禁止为了视觉理解调用 CLI `python -m computer_use screenshot`。
   - 使用 MCP `screenshot`，只保留 `saved_path`；按需读取最新一张图。
   - 默认 `get_ui_snapshot(scope="foreground", include_screenshot=false)`；只有需要跨窗口定位时才用 `scope="desktop"`。
   - 禁止读取完整 tool-output 大 JSON；必要时用精确过滤或新工具导出小摘要。
2. 修改 CLI 行为或帮助文案，降低误用概率：
   - 至少在 `python -m computer_use screenshot --help` 中明确“该 CLI 输出 base64，不适合 Agent 视觉任务”。
   - 更优方案是新增保存路径模式，例如 `python -m computer_use screenshot --save-path <path>`，并在文档中推荐该模式。
3. 限制 `get_ui_snapshot` 的输出风险：
   - 文档层明确 `scope=desktop` 是高成本操作。
   - 如改代码，优先考虑为 snapshot 返回添加裁剪/限制字段，而不是默认返回完整桌面树。
4. 增加长上下文 GUI 任务预算规则（模型无关，适用于对上下文规模敏感的模型）：
   - 触发条件使用 **Agent 可观测的代理信号**，不引用 token 计数（token 计数是客户端侧关注点，MCP server 与 Agent 自身无法程序化读取自身上下文 token 数）：
     - **主条件**：单次工具响应耗时超过 60s（可观测，已在本计划验证）。
     - **辅助条件**：连续 N 次工具调用的输出累积规模明显放大（例如连续读取多张 PNG、或一次 `get_ui_snapshot(scope="desktop")` 返回被截断保存的大 JSON）。
   - 触发后动作：停止继续视觉迭代，汇总当前状态后新开会话或让用户确认继续。
   - 历史数据中 80k token 是性能拐点的旁证，但不作为门控条件写入 guidance（Agent 无法自检 token 数）。

验收：

- 文档不再把“测截图 base64”当作唯一排查任务，而是明确三类膨胀源。
- CLI screenshot 的 base64 风险有用户可见提示或替代保存路径。
- Skill/guidance 中明确避免读取完整历史截图、完整 UIA JSON 和 CLI base64。

### 主线 C：复盘 detail/export

目标：审计 agent 不需要翻原始会话，也能从 task/trace 复盘出坐标、截图路径和结果。

#### API 设计决策

**复用与新增并存，分两层：**

1. **已有层（human-readable，不改动）**：`review.generate_deterministic_report(trace_id, goal)` (review.py:91-93) 包装 `trace.generate_report(trace_id, goal, final_state_path)` (trace.py:353-432)，生成 markdown `report.md` 文件，内含步骤表格（step_index/tool/duration_ms/result/error_kind）、错误与改进建议、截图与快照索引。这是**给人读的文件产物**，本计划不重写它。

2. **新增层（programmatic/MCP，本主线改动）**：在 `review_task(trace_id)` 增加**可选参数 `detail: bool = False`**。`detail=False`（默认）保持当前紧凑 summary 行为不变；`detail=True` 时在返回 dict 中追加 `steps` 数组，每项包含：
   - `step_index`、`tool`
   - 脱敏后的 `args`、脱敏后的 `result`
   - `duration_ms`、`screenshot_path`、`ui_snapshot_path`
   - `error_kind` / `error_message`

3. **会话聚合**：`review_task_session(task_id)` 同步增加可选 `detail: bool = False` 参数。`detail=True` 时把每个 trace 的 `review_task(trace_id, detail=True)` 结果透传聚合（即每个 `reviewed_traces[i].review` 已含 `steps`）。

**为什么 markdown 报告之外还需要 JSON detail：**
- markdown `report.md` 是**文件产物**，供人离线阅读，字段被渲染成表格文本，不便程序解析；且 `result_summary` 在表格中被截断到 40 字符（trace.py:391）。
- JSON `steps` 是**结构化数据**，供 MCP 客户端 / 审计 agent 程序化消费，保留完整 `args`（如 `{"x": 150, "y": 40}`）和完整 `result`，支持精确坐标复盘和自动化断言。

**为什么不默认开启、不新增 CLI 子命令：**
- `review_task` 的返回被 MCP 客户端直接消费，`review_task_session` 嵌套多个 `review_task` 输出。默认带 `steps` 会导致多 trace 会话 JSON 显著膨胀（本次案例单会话 114 条消息、8 个 trace）。`detail` 默认 False 保持向后兼容与紧凑输出，按需 opt-in。
- 不新增 `tasks export --detail` 子命令（Occam：避免扩大 CLI 命令面；MCP 工具参数已足够覆盖程序化消费场景）。

#### MCP 分发路径与统一（必读）

`detail` 参数必须在 **两条 MCP 分发路径** 上都能到达 `review.py`，否则"审计 agent 拿到 steps"这一 主线 C 目标只在 CLI 侧成立。当前两条路径状况不同：

- **trace 级（`review_task`）—— 无架构分歧，仅缺 detail 透传**：MCP 分发（`mcp_server.py:850-853`）已直接调用 `review.review_task(trace_id=...)`，正确委托 review.py。本主线只需在分发处补 `detail=args.get("detail", False)` 透传。
- **session 级（`review_task_session`）—— 存在平行实现，需统一**：MCP 分发（`mcp_server.py:884`）调用的是私有助手 `_review_task_session_result(task_id)`（`mcp_server.py:414-426`），该函数直接读 `task_session.get_task()` 返回**裸 task 元数据 + trace 链接**，**完全绕过 `review.review_task_session()` 的聚合逻辑**。因此仅给 `review.review_task_session` 加 `detail` 只让 CLI（`cli.py:168`）受益，MCP 客户端拿不到 `steps`。

**统一方案：删除平行实现，统一委托 review.py**：**删除 `_review_task_session_result`，把 `mcp_server.py:884` 的分发改为直接调用 `review.review_task_session(task_id, detail=...)`**，与 trace 级分发（`mcp_server.py:850-853` 直接调用 `review.review_task()`）保持一致的委托模式。

选删除而非"在 `_review_task_session_result` 内部补 detail 聚合"的理由：
- `_review_task_session_result` 仅被 `mcp_server.py:884` 一处调用，且其输出字段是 `review.review_task_session()` 返回字段的**真子集**（后者额外含 `total_steps`、`error_distribution`、每个 trace 的 `review`），保留它只是与 review.py 重复一段聚合逻辑，违背 Occam。
- 删除后 MCP 与 Python 两条路径通过同一函数返回结果，使下方验收标准的 MCP 路径等价性验证实质成立。
- 需确认：删除前核对 `_review_task_session_result` 是否被测试或其他模块引用（已确认仅定义处与单处调用）；若有旧测试断言其裸字段，改为对 `review.review_task_session(detail=False)` 断言。

> **tool_contract.py 分类提示**：`tool_contract.py` 将 `review_task` 归入 `_DIAGNOSTIC_TOOL_NAMES`（line 50），将 `review_task_session` 归入 `_ORCHESTRATION_TOOL_NAMES`（line 47），二者分属不同 frozenset。新增 `detail` 参数不改工具名，预期不影响分类；但执行时应验证分类规则不依赖参数签名（当前仅按名字归类，无签名依赖）。

执行项：

1. 不重写 trace 存储格式。保留现有 `trace.jsonl` 字段：`args`、`result`、`screenshot_path`、`ui_snapshot_path`、`duration_ms`、`error_kind`。
2. 修改 `review.review_task` 签名为 `review_task(trace_id: str, detail: bool = False)`；`detail=True` 时按上述字段组装 `steps` 数组并加入返回 dict。
3. 修改 `review.review_task_session` 签名为 `review_task_session(task_id: str, detail: bool = False)`；`detail=True` 时透传给内部 `review_task` 调用。
4. **统一 MCP session 级分发**：删除 `_review_task_session_result`（`mcp_server.py:414-426`），把 `review_task_session` 提到与 `review_task`（`mcp_server.py:850-853`）并列的独立 `if` 分支，分支内 `from computer_use import review` 后直接调用 `review.review_task_session(args["task_id"], detail=args.get("detail", False))`。新分支须保留当前 `name in {...}` 分支已有的 try/except 错误处理结构。
5. **MCP trace 级分发透传 detail**：把 `mcp_server.py:852` 改为 `review.review_task(trace_id=args["trace_id"], detail=args.get("detail", False))`。
6. **更新 MCP schema**：修改 `tools/schemas.py`（`review_task` 约 line 470、`review_task_session` 约 line 531 的 schema 定义），为二者新增可选 `detail: bool = False` 参数及描述。
7. 保持隐私边界：`steps` 中的 `args` / `result` 复用 trace 层现有脱敏逻辑，不记录或输出 `text`、`value`、`password`、`secret` 字段正文。
8. 文档（`docs/api.md`）补充 `detail` 参数说明与示例返回。

验收：

- 对 `task-20260620-063050-2m0886` 执行 Python `review.review_task_session(task_id, detail=True)`，返回 JSON 中能直接读到对应 trace 的 step `args: {"x": 150, "y": 40}`。
- 对 `task-20260620-102401-boi6kf` 同上，能读到 `args: {"x": 204, "y": 45}`。
- **MCP 路径等价性验证**：经 MCP `review_task_session(detail=True)` 调用同一 task_id，返回的 `steps` 结构与 Python 函数一致（MCP 分发直接委托 `review.review_task_session`，返回结构化 review 聚合结果）。
- `review_task(trace_id)` 与 `review_task_session(task_id)` 不传 `detail` 时，返回结构与现状一致（无 `steps` 字段），保持向后兼容。
- 现有敏感字段脱敏测试在 `detail=True` 路径下仍通过。

### 主线 D：执行纪律与示例

目标：给后续 Agent 一个可照抄的正确流程。

执行项：

1. 在 `docs/api.md` 增加一个“自绘 GUI 坐标点击安全示例”：
   - `start_task`
   - `screenshot`
   - `move_to`
   - `screenshot` 验证红色光标
   - `click`
   - `screenshot` 验证状态
   - `review_task_session` / `finish_task`
2. 给 `batch` 示例增加警告：只用于已确认目标后的机械序列，不能把“盲点多个坐标”打包成 batch。
3. 在 `docs/pitfalls.md` 增加长上下文 GUI 任务陷阱（模型无关）：大 UIA JSON、CLI base64、多图读取都会显著拖慢对上下文规模敏感的模型。

验收：

- 执行 agent 能从文档中直接找到正确流程。
- 文档明确“batch 减少往返”不等于“减少观察验证”。

## 推荐执行顺序

1. **先做主线 C**：改 `review_task` / `review_task_session` 暴露 detail，最快提升可复盘性，也能用已有 trace 写测试。
2. **再做主线 B**：修正 CLI screenshot 风险和上下文预算文档，防止再次把 Kimi 拖到 100k+ token。
3. **再做主线 A**：强化 skill/guidance 的坐标点击门控。
4. **最后做主线 D**：补充示例和 pitfalls，确保下个执行者按正确方式使用。

## 测试建议

至少新增或更新以下测试：

- `tests/test_review.py`：验证 `review_task(trace_id, detail=True)` 和 `review_task_session(task_id, detail=True)` 能返回 step `args` 和 `result`；验证 `detail=False`（默认）返回结构不含 `steps` 字段。
- `tests/test_mcp_server.py`（若不存在则新增）：验证 MCP 分发 `review_task_session(detail=True)` 与 `review_task(detail=True)` 委托到 review.py，返回含 `steps`（而非裸 task 元数据）；验证 `_review_task_session_result` 已删除、分发直接走 `review.review_task_session`。
- `tests/test_trace.py`：确认敏感字段在 detail 输出中仍脱敏。
- `tests/test_cli.py` 或相关 CLI 测试：覆盖 screenshot help/保存路径行为。
- `tests/test_guidance.py` 或现有 guidance 测试：确认核心 guidance 包含坐标预验证、CLI base64 禁用和上下文预算提示。

完整验证命令：

```powershell
pytest tests/ -v -m "not manual"
```

如果涉及真实鼠标/键盘行为，只做文档和 mock 验证；真实 GUI 验证需在无人操作输入设备时单独执行。

## 相关文件

**改动目标（相对仓库根）：**

- `skills/computer-use/SKILL.md`
- `computer_use/guidance.py`
- `computer_use/review.py`
- `computer_use/mcp_server.py`（主线 C：删除 `_review_task_session_result`、trace/session 两路 detail 透传）
- `computer_use/tools/schemas.py`（主线 C：`review_task` / `review_task_session` schema 加 `detail`）
- `computer_use/tool_contract.py`（主线 C：仅验证 `detail` 参数不破坏 `_DIAGNOSTIC_TOOL_NAMES` / `_ORCHESTRATION_TOOL_NAMES` 分类，预期无需改动）
- `computer_use/cli.py`
- `docs/api.md`
- `docs/pitfalls.md`
- `tests/test_review.py`
- `tests/test_trace.py`
- `tests/test_cli.py`
- `tests/test_mcp_server.py`（主线 C：验证 MCP `review_task_session(detail=True)` 与 Python 路径等价）

**接口依赖（不修改，仅调用）：**

- `computer_use/trace.py`（主线 C 仅读已有 trace 数据，不重写存储格式）
- `computer_use/task_session.py`（主线 C 仅调用 `task_session.get_task()` 读取 task 元数据）

**证据引用（仅本次任务实证，机器相关路径，非执行目标）：**

> 以下绝对路径为本机（`%COMPUTER_USE_HOME%` = `~/.computer-use/`）的证据快照，仅供复盘溯源，不是改动对象。换机复盘时按 `%COMPUTER_USE_HOME%` 环境变量定位等价目录。

- `%COMPUTER_USE_HOME%\screenshots\`（本次任务截图，对应 `C:\Users\chenr\.computer-use\screenshots\`）
- `%COMPUTER_USE_HOME%\tasks\2026\06\20\`（本次任务 task）
- `%COMPUTER_USE_HOME%\traces\2026\06\20\`（本次任务 trace）
- `%LOCALAPPDATA%\opencode\opencode.db`（Kimi 会话性能证据，对应 `C:\Users\chenr\.local\share\opencode\opencode.db`）
