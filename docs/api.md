# MCP 工具约定

> 记录 MCP 工具的设计约定和非显而易见的行为。具体工具列表可从 `mcp_server.py` 获取，这里只记约定。

## 通用约定

- 感知类坐标是**物理虚拟屏幕像素**，与 `mss` 截图像素 1:1 对应；截图、`get_monitors`、`find_control`、`inspect_point` 和 UI 快照可描述整个虚拟桌面。
- `monitor` 参数：0 表示整个虚拟桌面，1 表示主显示器，2+ 表示扩展显示器。
- 输入类工具只允许主显示器内的非负物理坐标。`core.py` 的最终公共输入原语强制执行该边界，显式坐标和依赖当前光标的输入均不能通过直接调用绕过；MCP/CLI 在此基础上继续执行目标窗口检查。副屏、负坐标和主屏外坐标会被拒绝。
- **每个工具响应都包含 `timestamp`**（ISO 8601，UTC，毫秒精度），便于复盘时计算各步骤间隔。即使出错，返回的 `{"error": "..."}` 对象也带 `timestamp`。

## MCP prompts

MCP prompts 是分发层指导，用于让客户端安装 server 后直接发现正确使用方式；它不替代工具 schema、安全检查或运行时错误处理。

- `computer_use_guidance`：完整 Windows GUI 操作纪律，包含多模态要求、标准闭环、安全规则和 trace/task 证据规则。
- `computer_use_visual_task`：面向多模态模型的视觉 GUI 任务闭环。
- `computer_use_text_only_limits`：图像读取不可用时的回退指导，只使用结构化 UIA、task、trace 和审计工具。
- `computer_use_safety_checklist`：发送真实鼠标/键盘输入前的安全检查清单。

## 视觉理解工作流

screenshot 保存 PNG 到本地并返回路径。读取该文件即可观察界面布局、图标、颜色和空间位置——这是 GUI 任务的主要观察手段。如果读取截图后确实无法获得视觉内容，才回退到 UIA 结构化查询或任务审计工具。

推荐的 GUI 任务模式是**先看图、再定位、再执行**：

1. `screenshot()`：截图后保存为本地 PNG，返回文件路径引用。多模态模型通过 `ReadMediaFile` 等工具读取该文件，理解布局、图标、颜色和空间位置。
2. `find_control` / `wait_for_window` / `wait_for_control`：用 UIA 语义定位目标控件或等待窗口/控件就绪，避免人工估算坐标。
3. `click` / `move_to`：优先使用 `target_name` 按控件名称点击；若 UIA 不可用或未命中，再回退到 `(x, y)` 坐标。

多模态模型已经能直接读图，因此不再提供 OCR 工具；需要精确文字时让模型直接看图识别即可。

**上下文保护原则**：`screenshot` 始终将 PNG 保存到本地目录，上下文默认只保留文件路径引用，不返回 base64 图像；唯一例外是显式传 `include_image=true`，此时全分辨率图像以独立的 `ImageContent` 块返回（不在 JSON 文本内），供能渲染图像的多模态客户端省去单独读盘。默认保存到 `~/.computer-use/screenshots/`；显式 `save_path` 必须位于配置的 `screenshot_dir` 内，不能使用 `..`、UNC、盘符相对路径或目录本身逃逸。`batch` 的 `final_screenshot` 默认关闭。

## 工具分类

### 感知类

- `get_ui_snapshot`：返回当前 UI 自动化树的结构化快照，含每个可交互控件的 `uid`、`name`、`control_type`、`class_name`、`bbox`（相对虚拟屏幕坐标）和 `path`。默认 `scope=foreground`（仅前台窗口），可传 `scope=desktop` 遍历完整桌面；可传 `include_screenshot=true` 同时保存一张截图并返回路径。返回的 `uid` 是**快照级自包含句柄**，仅在本次快照返回结果中有效；窗口刷新或 UI 重排后复用会返回 `{"error": "stale_uid"}`。遍历完整桌面可能耗时数秒，且输出 JSON 可达数百 KB（高成本操作，易导致上下文膨胀），优先使用前台窗口范围。**不要使用 `scope=desktop` 配合 `include_screenshot=true`；该组合会被 MCP 分发层直接拦截并返回 `high_cost_snapshot_blocked`。** 即便只取 `scope=desktop`，序列化后的 JSON 一旦超过内联预算（默认 200K chars）会被替换为 `snapshot_output_too_large` 紧凑错误，避免数百 KB 甚至 MB 级工具输出进入上下文；此时应改用 `scope=foreground` 或 `find_control` 配合窄条件。
- `screenshot`：截图后保存为 PNG，返回 `screenshot_taken`、`monitor`、`width`、`height`、`saved_path`、`timestamp`、`coordinate_space`（`monitor` 或 `virtual_desktop`）、`capture_left`、`capture_top`、`metadata_path`。默认图像不以 base64 形式进入上下文，模型应使用返回的路径通过 `ReadMediaFile` 等工具读取；传 `include_image=true` 时，全分辨率 base64 在独立的 `ImageContent` 块中随结果返回（文本块加 `inline_image: true`），仅建议在会渲染图像工具结果的客户端开启，超大截图（如 `monitor=0`，base64 超 3MB）会静默退化为纯路径并加 `inline_image_skipped`。默认捕获主屏（`monitor=1`），传 `monitor=0` 可捕获整个虚拟桌面，传 `save_path` 可覆盖保存位置。保存目录可在 `config.yaml` 的 `screenshot_dir` 中配置。保存前会在当前光标位置叠加红色十字标记；捕获单个显示器时会按该显示器左上角换算图像内坐标，光标不在捕获范围内则不绘制。PNG 旁会写入 sidecar JSON（`<saved_path>.json`），包含 `schema_version`、`screenshot_path`、`monitor`、`coordinate_space`、`capture_left`、`capture_top`、`width`、`height`、`created_at`，供 `click_on_screenshot` 和 `crop_screenshot` 映射图像像素到屏幕坐标。
- `get_monitors`：返回所有显示器的物理边界和主副标识，帮助 Agent 理解坐标系。

### 输入类

- `click` / `move_to`：鼠标操作。坐标必须落在主显示器内且非负。光标会平滑移动到目标位置，默认耗时 0.2 秒（来自 `computer_use.core.DEFAULT_MOVE_DURATION`）；可通过 `duration` 参数调整，避免快速移动导致悬停菜单关闭。`duration` 必须是非负有限数（`>= 0` 且不能为 NaN），否则抛出 `ValueError`。
  - `click` 支持 `button` 参数：`left`（默认）/`right`/`middle`。
  - `click` 支持 `double_click=true`：执行原生双击，兼容 `target_name` 和坐标两种定位模式，也兼容 `button`。
  - 支持 `target_name` 参数：按 UIA 控件名称定位，命中后取控件中心点击/移动；未命中且同时提供了 `(x, y)` 时回退到坐标模式。
  - `match`：与 `target_name` 配合，取值 `exact` / `contains` / `startswith`，默认 `contains`。
  - **`clicked=true` 只表示输入事件已发出，不表示业务操作成功。** 点击后必须通过新截图、UIA 查询或观察到的状态变化来验证业务结果。
- `mouse_down` / `mouse_up`：在主屏坐标按下或释放鼠标按键，支持 `left`/`right`/`middle`。`mouse_up` 的坐标可选；省略时仍校验当前光标位于主屏后再释放。
- `drag`：从 `(start_x, start_y)` 拖拽到 `(end_x, end_y)`，支持指定 `button` 和 `duration`。
  - 在任何移动或按键输入发生前，起点和终点都会分别执行坐标与实时目标窗口检查；任一点不安全时不会开始拖拽。
- `scroll`：滚动鼠标滚轮。可用 `amount`（正数向上、负数向下），或改用 `direction`（`up`/`down`）+ `clicks`。省略坐标时仍会检查当前光标位于主屏且目标窗口安全。
- `type`：模拟键盘输入文本。当前光标位置决定输入目标，光标必须位于主屏；键盘组合、按键按下/释放和单键输入遵循同一边界。
- `key_combo`：模拟组合键（如 `ctrl`, `c`）。
- `key_down` / `key_up` / `press_key`：更细粒度的键盘事件，分别用于按住、释放、按压单个键，便于构造 `ctrl`/`shift`/`alt` 等组合或长按场景。
- `click_by_uid`：snapshot 仅提供 UID 对应的定位坐标；执行点击前会按最终坐标实时检查目标窗口，不信任客户端 snapshot 中的进程、窗口类名或控件类型元数据。
- `click_on_screenshot`：在已保存的截图上按图像像素坐标点击。读取截图的 sidecar metadata（`<saved_path>.json`）将 `(image_x, image_y)` 映射为屏幕坐标，再走完整安全链（`validate_coordinate` → `inspect_point` → `check_target_window`）。映射后坐标仍受主屏输入限制，落入副屏会被 `SafetyError` 拒绝。缺少 sidecar 时返回 `screenshot_metadata_not_found`；图像坐标越界返回 `image_coordinate_out_of_bounds`；PNG 缺失返回 `screenshot_file_not_found`。**视觉目标应优先使用此工具，而非从缩放聊天预览估算裸 `click(x, y)` 坐标。** 支持 `button`、`duration`、`double_click` 参数。成功返回包含 `screen_x`/`screen_y`/`coordinate_space`/`monitor`，便于 trace 复盘。
- `crop_screenshot`：从已保存的截图中裁剪一个区域，保留坐标 metadata 以供后续 `click_on_screenshot`。裁剪图的 `capture_left/capture_top` 继承源截图的偏移量（`source_capture_left + x`、`source_capture_top + y`），因此对裁剪图调用 `click_on_screenshot(image_x, image_y)` 仍能映射回原始屏幕坐标。用于放大观察小目标。裁剪区域越界时返回 `image_coordinate_out_of_bounds`。

### 控件类

- `find_control`：按 `name`、`automation_id`、`control_type`、`class_name` 在指定作用域内查找控件，返回矩形和中心坐标。支持 `scope=desktop/foreground/window`，支持 `match=exact/contains/startswith`。未命中时返回结构化结果，便于模型换查询重试。
- `inspect_point`：返回某坐标下的 UIA 控件信息（若可用），用于确认点击目标。已注册为 MCP 工具，可直接调用。
- `wait_for_window`：事件驱动等待窗口出现或消失，替代固定 `sleep`。默认每 200ms 轮询，超时返回 `{"timeout": true}`。
- `wait_for_control`：事件驱动等待前台窗口内的指定控件变为可用（存在、启用、可见），或等待其消失。

### 启动类

- `launch_app`：通过 `Shell.Application` 按桌面或开始菜单快捷方式名称启动应用。支持精确匹配和子串回退；多个匹配时返回列表供模型确认，不自动启动。命令行类任务应交给框架的 Bash 工具，不通过本 MCP 执行。
- `activate_window`：把标题包含 `name` 的**已存在**窗口（后台或最小化）置前台，替代 shell/Win32 切窗。一次性查找+激活，不轮询；窗口可能尚未出现时先 `wait_for_window`。内建自指污染防御（命中宿主进程返回 `self_activation_blocked`）、敏感进程拦截（`blocked`）、不可激活窗口区分（`not_activatable`）、COM/UIPI 异常捕获（`activate_failed`），并在 `SetActive` 后用前台窗口后验，跨虚拟桌面静默失败时返回 `activation_unconfirmed`。失败原因见 `reason` 字段，异常细节见可选 `detail`。

### 控制类

- `sleep`：按指定秒数暂停执行，用于 `batch` 工作流中等待动画、窗口过渡或应用启动。`duration` 为非负实数，最大 60 秒。优先使用 `wait_for_window`/`wait_for_control` 等事件驱动等待；只有目标无法通过 UIA 探测时才回退到固定等待。

### 批量执行类

- `batch`：在一次调用里顺序执行多个工具，适合把 GUI 工作流（如“启动 → 点击菜单 → 选择项 → 截图验证”）打包成一次请求，减少长上下文下的回合数。**直接调用此工具即可，不要在 Python/Bash 里写 `import sys/json/time` 来包装 `_call_tool`**。**注意：`batch` 减少往返次数，但不减少观察/验证。** 只在目标已确认后将机械序列打包成 batch；不要把“对多个坐标的盲点”打包进 batch，batch 中的每个坐标都应已通过预验证。参数：
  - `actions`：工具调用数组，每项包含 `tool`（canonical 工具名）、`args`（参数对象），以及可选的 `capture_snapshot`（在该动作执行前调用 `get_ui_snapshot` 并保存 UI-tree JSON 路径到该步骤结果的 `snapshot` 字段，便于复盘定位）。
  - `stop_on_error`（默认 `true`）：遇到错误时是否停止后续动作。
  - `final_screenshot`（默认 `false`）：执行完成后是否追加一张最终截图。截图会保存到磁盘并在 `final_screenshot` 中返回 `{saved_path, monitor, width, height, timestamp}`，不会返回 base64。
  - `screenshot_monitor`（默认 `1`）：最终截图的显示器索引，`0` 表示整个虚拟桌面。

`tool` 的 Schema enum 是权威集合。已知外部 MCP 前缀（如 `computer-use_press_key`、`mcp__computer-use__press_key`）会被规范化为 canonical 名称，但响应会同时返回 `requested_tool` 和 `tool`。未知、拼错或禁止嵌套的工具名返回结构化 `invalid_tool`、候选和 allowed tools；不会继续执行真实输入动作。

返回 JSON 包含 `results`（每步结果，含 `index`、`requested_tool`、`tool`、`result`、`timestamp`）、`status`、`failed_index`、`error_kind`、`executed_count`、`requested_count`、`trace_id`、`trace_path`、`artifact_root`、`artifacts` 和 `timestamp`；当 `final_screenshot=true` 时还会包含 `final_screenshot`（保存路径引用）。`timeout=true` 视为失败。`batch` 内禁止再次调用 `batch` 或 `run_task_plan`，单次最多展开 100 个动作。

`artifacts` 由 trace 层的扁平 manifest 派生，只列实际存在的文件：

- `artifacts.screenshots`：trace 上下文内的截图 PNG。
- `artifacts.snapshots`：trace 上下文内的 UI-tree JSON。
- `artifacts.report`：`report.md` 路径；不存在时为 `null`。

`batch` 典型调用示例（等待时间单位为秒）：

```json
{
  "actions": [
    {"tool": "click", "args": {"x": 1026, "y": 49, "double_click": true}},
    {"tool": "sleep", "args": {"duration": 3}},
    {"tool": "click", "args": {"x": 1354, "y": 155}},
    {"tool": "sleep", "args": {"duration": 1}},
    {"tool": "click", "args": {"x": 1180, "y": 415}}
  ],
  "final_screenshot": true
}
```

## 典型调用流程示例

### 启动应用并点击菜单项

```text
1. launch_app(name="HiBit Uninstaller")
   -> {"launched": true, "name": "HiBit Uninstaller", "target_path": "..."}
2. wait_for_window(name="HiBit Uninstaller")
   -> {"present": true, "name": "...", "rect": {...}}
3. screenshot()                              # 保存到默认目录，返回文件路径引用
4. click(target_name="工具")
5. wait_for_control(name="注册表清理程序")
6. click(target_name="注册表清理程序")
```

### 双击桌面图标启动应用

```text
1. click(target_name="HiBit Uninstaller", double_click=true)
   -> {"clicked": true, "double_click": true, "mode": "uia", ...}
2. wait_for_window(name="HiBit Uninstaller")
```

### 在已知窗口内查找并操作

```text
1. find_control(name="设置", control_type="Button", scope="window", window_name="HiBit Uninstaller")
2. click(target_name="设置")
3. screenshot()                         # 保存截图并通过路径读取，验证打开的页面
```

### 自绘 GUI 坐标点击安全示例

对自绘界面（游戏、Delphi/VCL 等无法用 UIA 精确定位按钮的程序），按以下完整安全流程操作。核心是 **move_to → screenshot 验证落点 → click → screenshot 验证状态变化**：

```text
1. start_task(goal="打开对话回顾面板")
2. screenshot(monitor=1)                    # 观察当前界面，确定目标位置
3. move_to(x=204, y=45)                    # 移到预估目标位置
4. screenshot(monitor=1)                    # 验证红色光标标记落在目标中心
5. click(x=204, y=45)                      # 确认落点后点击
6. screenshot(monitor=1)                    # 验证 GUI 状态已变化
7. review_task_session(task_id, detail=True)  # 复盘步骤和坐标
8. finish_task(task_id, summary="成功打开对话回顾面板")
```

要点：
- 步骤 3-4 是 **pre-click 落点预验证**，步骤 6 是 **post-click 状态验证**，两者缺一不可。
- 若步骤 6 显示 GUI 无变化，最多允许一次重新测量；禁止在原错误坐标附近 3-5 像素盲调。

### 复合执行类

- `click_by_uid`：根据 `get_ui_snapshot` 返回的 `uid` 点击对应控件。必须同时传入完整的 `snapshot` 对象（UID 仅在当前快照内有效）。句柄失效时返回 `{"error": "stale_uid"}`。
- `click_by_text`：按显示文本在 UIA 树中查找并点击最匹配控件。未命中返回 `{"error": "ui_not_found", "candidates": [...]}`。
- `open_menu(path=["工具", "文件和注册表查找器"])`：依次点击菜单路径中的每个 UIA 控件；未命中时停止并返回 `ui_not_found`。
- `fill_form(fields=[{"name": "用户名", "value": "xxx"}, ...])`：批量填表，每个 field 按 `name` 定位输入框，先点击聚焦再输入文本。危险文本会被 `validate_text_input` 拒绝。
- `scroll_until(target_text, direction, max_attempts)`：滚动直到目标文本出现在前台 UIA 树中；达到最大尝试次数仍未命中返回 `ui_not_found`。

### 任务级执行类

- `run_task_plan`：执行任务级结构化计划。参数：
  - `trace_id`（可选）：复用已有 ID；省略则 server 生成。
  - `goal`（可选）：任务目标，写入 `report.md`。
  - `steps`：步骤数组，每项 `{"tool": ..., "args": ...}`，支持普通工具、复合工具和一层 `batch`，禁止嵌套 `run_task_plan`。
  - `final_state`（默认 `false`）：任务结束时是否捕获 `get_ui_snapshot(include_screenshot=true)`。
  - `capture_screenshots`（默认 `true`）：是否为每个 step 自动截图并写入 trace。
  返回 `trace_id`、`trace_path`、`artifact_root`、`artifacts`、`results`、`report_path`、`status`、`failed_index`、`error_kind`、`executed_count`、`requested_count`，以及可选的 `final_state_path`。`error`、`timeout=true` 和 PyAutoGUI fail-safe 均按失败处理；单次最多展开 100 个步骤。
- `retry_step(trace_id, step_index, mode)`：重放 trace 中的某一步。
  - `mode="single"`（默认）：仅重执行该 step。
  - `mode="from_step"`：从该 step 起顺序重放后续所有 step。
  - 重放使用新的 `step_index` 字符串，如 `"3.retry.1"`，追加到原 `trace.jsonl`。
  - 重放时不直接复用旧结果，而是重新调用底层工具，由当前 UI 状态重新定位并重新执行安全检查。
  - 含已脱敏输入的步骤标记为 `replayable=false`，返回 `retry_not_supported_for_redacted_step`，不会执行脱敏占位符。
- `review_task(trace_id, detail=False)`：读取 trace 并生成确定性统计摘要（总步骤数、成功/失败/重试数、错误类型分布、平均耗时、截图/快照索引），不调用 LLM。`detail=True` 时在返回中追加 `steps` 数组，每项含 `step_index`、`tool`、`args`（已脱敏）、`result`（已脱敏）、`duration_ms`、`screenshot_path`、`ui_snapshot_path`、`error_kind`、`error_message`，支持精确坐标复盘和自动化断言。默认 `False` 保持紧凑输出。

## 业务任务会话

业务任务会话用于把多个顶层 MCP 调用归属到同一个可审计任务。标准 Agent 流程：

```text
1. start_task(goal) -> task_id
2. tool(..., task_id=task_id)
3. batch(..., task_id=task_id)
4. review_task_session(task_id)
5. finish_task(task_id, summary)
```

`task_id` 表示业务任务边界，不是模型对话 ID 或客户端会话 ID。一个业务任务可以跨多个 Agent 回合产生多个 trace；同一个 Agent 对话也可以顺序创建多个互不混淆的业务 task。

未传 `task_id` 的顶层调用会自动创建并结束 standalone task，这是兼容旧调用方的行为；需要跨调用复盘或向用户汇报证据时，应显式使用 `start_task` 返回的 `task_id`。

- `start_task(goal)`：创建显式业务 task，返回 `task_id`、`status` 和 `task_path`。
- `finish_task(task_id, summary?, cancel?)`：结束显式 task；最终成功或失败由已登记 trace 派生，调用方不能伪造成功状态。
- `get_task(task_id)`：读取 task 元数据和 trace 归属列表。
- `list_tasks(date?, status?, limit?)`：按创建时间倒序列出 task，可按本地业务日期和状态过滤。
- `review_task_session(task_id, detail=False)`：聚合该 task 下所有 trace 的确定性复盘，输出 task 时间线、失败 trace、错误类型和实际存在的产物路径。`detail=True` 时每个 trace 的 review 中包含 `steps` 数组（透传 `review_task(detail=True)`）。MCP 分发直接委托 `review.review_task_session`，与 Python API 路径等价；CLI 仍默认输出紧凑复盘。
- `save_review(report_markdown, outcome="unknown", task_id?, client?, model?)`：把 agent 整理的复盘报告**写**成规范化 `.md`(YAML frontmatter + 正文)存入 `review_dir`(默认 `~/.computer-use/reviews/`)，供分发后统一收集反馈。与 `review_task`/`review_task_session`(只**读** trace 摘要)不同。工具自动附带元数据(`created_at`、`mcp_version`、`outcome`、`client`/`model`)、`doctor` 环境快照(标注 `doctor.captured_at`，采集于报告生成时刻)，以及——当传 `task_id` 时——`review_task_session` 摘要与各 trace 的 `artifact_manifest` 路径。`outcome` 受控枚举 `succeeded/partial/failed/unknown`(非法值回退 `unknown`)；`report_markdown` 上限 500KB(超限拒绝、不落盘)；富集任一失败安全降级，主报告仍落盘。**有 `task_id` 时文件名确定(`review_<task_id>.md`)，二次调用覆盖**；无 `task_id` 时按时间戳命名。返回 `{saved, review_path, review_dir}` 或 `{saved: false, error}`。报告末尾带隐私提示注释(含用户名/路径/依赖，分享前应预览)；不写入密钥、环境变量或 `config.yaml` 内容。属元操作，**不受 `task_id` 守卫约束**，也不可作为 `batch`/`run_task_plan` 嵌套步骤。

所有可执行顶层工具都支持可选 `task_id`；task 管理工具、只读单 trace 复盘 `review_task` 和复盘报告 `save_review` 不使用归属上下文。`task_id` 只在 MCP/runner 层用于归属管理，不会传给 `core.py`、`safety.py` 或 UIA 底层函数。

**`task_id` 守卫**：`start_task` 之后，只要存在未结束的显式 task，所有可执行顶层工具调用必须显式传 `task_id`。缺失时 MCP 分发层直接返回 `missing_task_id`（含 `active_task_id`）或 `missing_task_id_ambiguous`（多个 active task），工具不会执行也不会创建新的 standalone trace；agent 应使用返回的 `active_task_id` 重试或先结束冲突的 task。

## Trace 与复盘

- 每个工具调用（包括 `batch` 子步骤和单独工具）都会写入结构化 trace，目录由 `config.yaml` 的 `trace_dir` 配置，默认 `~/.computer-use/traces/`。
- 新 trace 按本地业务日期写入 `traces/YYYY/MM/DD/<trace_id>/`；旧 `<trace_dir>/<trace_id>/` 扁平布局保持只读兼容，不会被只读查询隐式迁移。
- `tasks/YYYY/MM/DD/<task_id>/` 保存业务任务生命周期和 trace 归属文件；trace 的实际物理位置通过 locator 按 `trace_id` 解析。
- `batch`、`run_task_plan` 和 `review_task` 直接返回 `trace_path`、`artifact_root` 和 `artifacts`。执行侧应以响应字段为证据，不扫描目录名推断状态。
- 单条 trace 记录包含 `trace_id`、`step_index`、`tool`、`args`、`result`、`duration_ms`、`screenshot_path`、`ui_snapshot_path`、`error_kind`、`error_message`、`replayable`。
- 当前 `error_kind` 取值：`safety_block` / `ui_not_found` / `stale_uid` / `timeout` / `fail_safe` / `invalid_tool` / `unknown`，未出错时为 `null`。
- `trace_id` 只允许安全的单一 ASCII 路径组件，所有读写入口使用同一校验。
- Trace 和工具日志会递归移除 `text`、`value`、`password`、`secret` 字段正文，只保留脱敏标记和长度；关联结果或错误中的相同正文也会替换。
- Trace 不记录多模态模型推理时间，也不包含截图 base64；复盘时通过路径引用读取对应截图或快照。
- trace 上下文内按文件类型分流：截图 PNG 写入 `<trace_id>/screenshots/`，UI-tree JSON 写入 `<trace_id>/snapshots/`。无 trace 上下文的独立 snapshot 截图仍回退到全局 `<trace_dir>/snapshots/`，两者语义不同。

## 安全行为

- 输入类工具会检查目标坐标所在进程的 `process_name`、`class_name`、`control_type`。
- 如果目标进程在白名单之外，操作会被拒绝。白名单逻辑见 `safety.py`。
- 文本输入允许密码框，这是当前产品特性；输入正文不会写入日志或 trace。
- `find_control` 默认开启 `sensitive_check=True`；命中敏感窗口时返回 `{"found": false, "blocked": true}`，而不会触发真实点击。
- `launch_app` 使用 `safety.allowed_commands` 白名单校验目标可执行文件。
- `allowed_commands` 中带路径分隔符的条目只按完整路径匹配；只有显式配置的裸文件名才按 basename 匹配。
- 截图敏感检测覆盖捕获范围内的可见顶层窗口；UIA 枚举不可用时回退到中心点检查。
