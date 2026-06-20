# MCP CU 截图坐标绑定与多屏点击准确度改进计划

## 目标

让 Agent 在多屏、缩放预览、小目标和自绘 UI 场景中，不再靠目测把聊天预览坐标直接传给 `click(x, y)`。工具层应把“截图像素坐标”和“最终屏幕输入坐标”显式绑定，并在 trace 中记录坐标来源。

## 核心判断

坐标点偏的关键风险不是单一模型能力问题，而是当前工具契约没有明确区分以下坐标：

| 坐标来源 | 含义 | 风险 |
|---|---|---|
| 截图图像像素坐标 | PNG 原始像素中的 `(image_x, image_y)` | 模型应优先表达这种坐标，但当前没有对应点击接口 |
| 屏幕输入坐标 | 鼠标实际移动/点击使用的坐标 | 当前输入工具受安全策略限制，只允许主屏输入 |
| 虚拟桌面坐标 | `monitor=0` 全景截图的物理虚拟桌面坐标 | 多屏画布变大，小目标在预览中更小 |
| 聊天预览坐标 | 客户端缩放展示后的视觉坐标 | 不能直接用于真实点击 |

当前应保留的安全边界：真实输入仍限制在主屏。即使截图来自 `monitor=0`，映射后的点击坐标如果落在副屏，也必须被现有 `safety.py` 拒绝，除非后续有单独计划放开副屏输入安全策略。

## 范围

本计划只解决“截图坐标如何可靠映射到点击坐标”。不改变鼠标/键盘安全策略，不放开副屏输入，不尝试自动识别游戏 UI 语义。

## 非目标

- 不新增 OCR。
- 不依赖聊天客户端预览尺寸。
- 不让 Agent 手动换算缩放比例。
- 不放开非主屏输入限制。
- 不在 review 层猜测目标按钮中心；review 只消费 trace 中已有事实。
- 不把归一化坐标作为主路径。归一化坐标只适合作为截图引用坐标的补充。

## 设计原则

1. **截图先产出坐标元数据**：每张 MCP 截图都要能回答“图像像素 `(x, y)` 对应哪个屏幕输入坐标”。
2. **点击接口引用截图**：Agent 应调用 `click_on_screenshot(screenshot_path, image_x, image_y)`，而不是裸 `click(x, y)`。
3. **裁剪保留来源关系**：裁剪图必须继承源截图的坐标元数据和 crop offset。
4. **安全检查不绕过**：所有映射后的最终屏幕坐标仍走现有 `validate_coordinate`、`inspect_point` 和 `check_target_window`。
5. **trace 记录推理链**：记录来源截图、图像坐标、映射后的屏幕坐标和 coordinate_space。

## 当前代码事实

- `computer_use/core.py` 使用 `mss` 截图，截图像素与 mss 物理坐标一致。
- `computer_use/mcp_server.py` 的 MCP `screenshot` 默认读取 `display.default_monitor`，项目默认值为 `1`。
- `computer_use/safety.py` 将真实输入限制在主屏。
- `click` / `move_to` 的 schema 文案当前写的是 primary-screen physical coordinates，但底层 `CoordinateSystem` 文档又描述为 virtual screen physical pixels。需要在文档和工具描述中明确：工具参数可以表达物理屏幕坐标，但最终输入安全策略只允许主屏。

## P0：为 MCP screenshot 写入 capture metadata

### 目标

`screenshot` 返回并持久化截图坐标元数据，使后续工具可以通过 `screenshot_path` 稳定映射图像坐标。

### 修改文件

- `computer_use/mcp_server.py`
- `computer_use/core.py`（如需抽取 capture bounds helper）
- `tests/test_mcp_server.py`
- `docs/api.md`

### 返回字段

MCP `screenshot` 在现有返回字段（`screenshot_taken`、`monitor`、`width`、`height`、`saved_path`、`timestamp`，见 mcp_server.py:524-530）基础上，**仅新增**以下 4 个字段：

```json
{
  "coordinate_space": "monitor",
  "capture_left": 0,
  "capture_top": 0,
  "metadata_path": "C:\\...\\screenshot_...png.json"
}
```

> **字段决策**：
> - `image_width`/`image_height` 与现有 `width`/`height` 语义重复，**不新增**——全部 JSON 示例复用现有 `width`/`height`。
> - `click_coordinates` 是文档字符串而非数据字段，**移除**——其指导内容（图像像素坐标可映射为屏幕坐标）移至工具描述，见 P1 工具描述章节。

完整返回示例（现有字段 + 新增字段）：

`monitor=0` 时：

```json
{
  "screenshot_taken": true,
  "monitor": 0,
  "width": 3840,
  "height": 1089,
  "saved_path": "...",
  "timestamp": "...",
  "coordinate_space": "virtual_desktop",
  "capture_left": 0,
  "capture_top": 0,
  "metadata_path": "...png.json"
}
```

`monitor=1` 时（主屏位于虚拟桌面原点，故 `capture_left=0`、`capture_top=0`）：

```json
{
  "screenshot_taken": true,
  "monitor": 1,
  "width": 1920,
  "height": 1080,
  "saved_path": "...",
  "timestamp": "...",
  "coordinate_space": "monitor",
  "capture_left": 0,
  "capture_top": 0,
  "metadata_path": "...png.json"
}
```

### Sidecar 文件

在 PNG 旁边写入 sidecar JSON：

```text
<saved_path>.json
```

内容至少包含：

```json
{
  "schema_version": 1,
  "screenshot_path": "C:\\...\\screenshot.png",
  "monitor": 1,
  "coordinate_space": "monitor",
  "capture_left": 0,
  "capture_top": 0,
  "width": 1920,
  "height": 1080,
  "created_at": "2026-06-21T00:00:00.000+00:00"
}
```

> **Sidecar 路径约定**：始终为 `<saved_path>.json`（同目录、同名加 `.json` 后缀）。因此 `save_path` 目录校验自动覆盖 sidecar——无需对 sidecar 单独做路径白名单检查。

### 验收

- `screenshot(monitor=1)` 返回 metadata，并写入 `<saved_path>.json`。
- `screenshot(monitor=0)` 返回 `coordinate_space=virtual_desktop`。
- sidecar 中的 `screenshot_path` 必须与实际 PNG 路径一致。
- `save_path` 自定义路径也必须写 sidecar，且仍只能写入配置允许的截图目录。

## P0：新增 click_on_screenshot

### 目标

Agent 可以表达“点击这张截图上的 `(image_x, image_y)`”，工具负责映射成屏幕坐标并执行点击。

### 新工具

```json
{
  "tool": "click_on_screenshot",
  "screenshot_path": "C:\\...\\screenshot.png",
  "image_x": 213,
  "image_y": 48,
  "button": "left",
  "duration": 0.2,
  "double_click": false,
  "task_id": "task-..."
}
```

### 映射规则

```python
screen_x = metadata["capture_left"] + image_x
screen_y = metadata["capture_top"] + image_y
```

click_on_screenshot 的 dispatch 实现**必须镜像 `_run_mouse_tool`（mcp_server.py:1180-1195）的完整 pre-flight 模式**：

1. `validate_coordinate(screen_x, screen_y, ...)` — 坐标边界检查
2. `info = inspect_point(screen_x, screen_y)` — UIA 探测目标窗口
3. `check_target_window(info.process_name, info.class_name, info.control_type)` — 目标窗口安全检查
4. `core.click(screen_x, screen_y, ...)` 或 `core.double_click(...)` — 执行输入

**不得直接调用 `core.click()` 而省略步骤 2/3**——这会绕过 sensitive window 检查。注意 `core.click()` 本身只做 `validate_coordinate` + `pyautogui.click`，不含 `inspect_point`/`check_target_window`；后者位于 dispatch 层 `_run_mouse_tool`。

推荐抽取 `_run_mouse_tool` 的步骤 1-3 为共享 helper（如 `_preflight_input_coordinate(x, y)`），`click_on_screenshot` 和 `_run_mouse_tool` 共用，避免代码重复和后续维护漂移。

### 错误返回

缺少 sidecar：

```json
{
  "error": "screenshot_metadata_not_found",
  "next_action": "Call the MCP screenshot tool first and use its saved_path."
}
```

PNG 缺失但 sidecar 存在（或反之）：

```json
{
  "error": "screenshot_file_not_found",
  "next_action": "Re-run the MCP screenshot tool; the requested screenshot file is missing."
}
```

图像坐标越界（使用现有 `width`/`height` 字段告知有效范围）：

```json
{
  "error": "image_coordinate_out_of_bounds",
  "width": 1920,
  "height": 1080
}
```

映射到非主屏（SafetyError）：

`click_on_screenshot` 的 dispatch 实现**不得捕获并重格式化 SafetyError**。映射后坐标落入 `validate_coordinate` / `check_target_window` 触发的 `SafetyError`，应直接冒泡到 `_call_tool` 的现有错误处理路径（mcp_server.py:292-297），返回：

```json
{
  "error": "<str(SafetyError)>",
  "next_action": "<_NEXT_ACTION_COORDINATE_OR_SAFETY>"
}
```

- **不需要** `coordinate_safety_block` 枚举：现有 `SafetyError` 消息已描述拒绝原因。
- **不需要** 自定义 `screen_x`/`screen_y` 错误字段：错误返回保持与 `_run_mouse_tool` 等其它工具一致。
- **成功返回仍应包含 `screen_x`/`screen_y`**，供 trace 可追溯（见下方「成功返回」）。

### 成功返回

```json
{
  "clicked": true,
  "screenshot_path": "C:\\...\\screenshot.png",
  "image_x": 213,
  "image_y": 48,
  "screen_x": 213,
  "screen_y": 48,
  "coordinate_space": "monitor",
  "monitor": 1
}
```

### 修改文件

- `computer_use/mcp_server.py`
- `computer_use/tools/schemas.py`
- `computer_use/tool_contract.py`
- `tests/test_mcp_server.py`
- `docs/api.md`

### tool_contract.py 分类决策

- `click_on_screenshot`：加入 `ATOMIC_AND_COMPOSITE_TOOL_NAMES`（使其可在 batch/run_task_plan 内嵌套使用）
- `crop_screenshot`：加入 `ATOMIC_AND_COMPOSITE_TOOL_NAMES`
- 两者都**不加入** `_DIAGNOSTIC_TOOL_NAMES`（否则被踢出 `BATCH_ACTION_TOOL_NAMES`）
- 两者都**不加入** `_TASK_CONTEXT_EXCLUDED_TOOLS`（schemas.py:15），因此 task_id guard 会守护它们（正确行为：截图点击应归属到显式 task）
- `schemas.py:606-617` 的 `_attach_task_context_schemas()` 会自动为两者挂载可选 `task_id` 参数

### 验收

- `click_on_screenshot` 只能使用带 sidecar metadata 的截图。
- 图像坐标映射为屏幕坐标后仍受主屏输入限制。
- trace 中能看到 `screenshot_path`、`image_x`、`image_y`、`screen_x`、`screen_y`。
- 不引入硬编码游戏坐标。

## P1：新增 crop_screenshot 并保留坐标来源

### 目标

让小目标先裁剪放大观察，再通过裁剪图坐标点击原屏幕位置。

### 新工具

```json
{
  "tool": "crop_screenshot",
  "screenshot_path": "C:\\...\\screenshot.png",
  "x": 0,
  "y": 0,
  "width": 360,
  "height": 120
}
```

### 输出

```json
{
  "cropped": true,
  "saved_path": "C:\\...\\crop.png",
  "metadata_path": "C:\\...\\crop.png.json",
  "source_screenshot_path": "C:\\...\\screenshot.png",
  "capture_left": 0,
  "capture_top": 0,
  "width": 360,
  "height": 120
}
```

裁剪 metadata 的 `capture_left/capture_top` 必须为：

```python
crop_capture_left = source_capture_left + x
crop_capture_top = source_capture_top + y
```

因此对裁剪图调用：

```json
{
  "tool": "click_on_screenshot",
  "screenshot_path": "C:\\...\\crop.png",
  "image_x": 213,
  "image_y": 48
}
```

仍能映射回原始屏幕坐标。

### 修改文件

- `computer_use/mcp_server.py`
- `computer_use/tools/schemas.py`
- `computer_use/tool_contract.py`（见 P0 click_on_screenshot 的「tool_contract.py 分类决策」）
- `tests/test_mcp_server.py`
- `docs/api.md`
- `skills/computer-use/SKILL.md`
- `.agents/skills/computer-use/SKILL.md`

### 验收

- 裁剪坐标必须在源图范围内。
- 裁剪图写入 sidecar。
- `click_on_screenshot` 可接受裁剪图路径并正确映射坐标。
- 裁剪不会读取或返回 base64。

## P1：工具描述与 guidance 更新

### 目标

让模型在调用工具前就能看到正确坐标契约。

### 修改内容

`screenshot` 工具描述补充：

```text
Use the returned saved_path and coordinate metadata for any screenshot-based click. Do not infer click coordinates from a scaled chat preview.
```

`click` / `move_to` 工具描述补充：

```text
For visual targets from a screenshot, prefer click_on_screenshot(screenshot_path, image_x, image_y). Raw x/y input is for already-known primary-screen physical coordinates.
```

`computer_use/guidance.py` 和 skill 补充推荐流程：

```text
1. screenshot(monitor=1)
2. If the target is small, crop_screenshot(...)
3. click_on_screenshot(crop_or_original_path, image_x, image_y)
4. screenshot(monitor=1) to verify state change
```

### 修改文件

- `computer_use/tools/schemas.py`
- `computer_use/guidance.py`
- `skills/computer-use/SKILL.md`
- `.agents/skills/computer-use/SKILL.md`
- `tests/test_mcp_prompts.py`
- `tests/test_mcp_server.py`

### 验收

- tool descriptions 中出现 `click_on_screenshot`。
- guidance/skill 中明确禁止从缩放聊天预览直接取裸 `click(x, y)` 坐标。
- 两份 skill SHA256 一致。

## P2：Trace 与 review 支持坐标来源字段

### 目标

让复盘工具可以准确回答每次截图点击的坐标来源。

### 记录字段

`click_on_screenshot` 的 trace result 至少包含：

```json
{
  "screenshot_path": "...",
  "image_x": 213,
  "image_y": 48,
  "screen_x": 213,
  "screen_y": 48,
  "coordinate_space": "monitor",
  "monitor": 1
}
```

### review 输出

`review_task(detail=True)` 已能返回 args/result。无需新增复杂诊断，只需保证上述字段出现在 detail steps 中。

### 验收

- `review_task(trace_id, detail=True)` 可看到截图坐标和最终屏幕坐标。
- 不做“模型是否误用预览缩放”的自动猜测。

## 延后项

### 归一化坐标

`x_ratio/y_ratio` 可以在 `coordinate_ref=screenshot_path` 的前提下补充实现，但不作为主路径。没有截图引用的归一化坐标不解决预览缩放误用。

### preview_click

现有 `move_to -> screenshot -> click` 可覆盖大部分预验证需求。若要减少步骤，可后续新增 `preview_click`，但不应阻塞 P0。

### 前景窗口截图

游戏/DirectX 窗口截图可能受限制。先用 `crop_screenshot` 支持稳定裁剪，再评估是否新增 `screenshot_foreground_window`。

### review 自动诊断

只有在 trace 已稳定记录截图坐标和屏幕坐标后，才考虑增加启发式诊断。

## 推荐执行顺序

1. 实现 `screenshot` metadata 和 sidecar。
2. 实现 `click_on_screenshot`。
3. 更新 schema、guidance、skill 和 docs。
4. 实现 `crop_screenshot`。
5. 补充 trace/review 验收测试。

## 测试建议

### 单元测试

```powershell
& ".venv\Scripts\python.exe" -m pytest tests/test_mcp_server.py tests/test_mcp_prompts.py -v
```

必须覆盖：

- screenshot metadata 写入。
- `click_on_screenshot` 基于 metadata 映射坐标。
- 映射到副屏时被 `safety.py` 拒绝。
- 缺少 metadata 时返回 `screenshot_metadata_not_found`。
- crop metadata 正确继承 source offset。
- skill 双副本内容一致。

### 全量验证

```powershell
& ".venv\Scripts\python.exe" -m pytest tests/ -v
python scripts/agent_links.py check
git diff --check
```

预期：

- pytest 全量通过，manual GUI 测试默认 skipped。
- `agent_links.py check` 输出 `link group ok (mode=copy)`。
- `git diff --check` 无 whitespace error；Windows CRLF warning 可接受。

## 行为验收

双屏环境中，Agent 面对小按钮应走以下流程：

1. `screenshot(monitor=1)` 获取主屏截图和 metadata。
2. 小目标不清晰时调用 `crop_screenshot`。
3. 在原图或裁剪图上确定图像坐标。
4. 调用 `click_on_screenshot`，由工具映射并执行点击。
5. 点击后截图验证状态变化。

若 Agent 尝试直接用聊天预览估算裸 `click(x, y)`，工具描述和 guidance 应明确提示改用 `click_on_screenshot`。
