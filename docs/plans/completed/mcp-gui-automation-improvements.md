# MCP GUI 自动化执行效率改进计划

## 背景

在近期实际任务（启动 HiBit Uninstaller 并打开注册表清理程序）中，当前 `computer-use-mcp` 暴露出几个明显瓶颈：

1. **每步延迟过长**：操作后需要固定 `sleep`，再截图、OCR（PaddleOCR 经 subprocess），然后人工估算坐标，完成简单三步点击耗时数分钟。
2. **坐标点击脆弱**：OCR 只返回文本不返回位置，菜单项估算坐标容易点错（例如“注册表清理程序”与“空文件夹清理程序”混淆）。
3. **OCR 依赖过重**：截图后先转文字再让模型读文字，丢失了空间、颜色、图标等视觉信息。
4. **启动应用依赖桌面图标坐标**：分辨率、图标排列变化后容易失效。

## 目标

将当前“像素 + OCR + 坐标硬点 + sleep”的执行模式，升级为“**控件语义 + 多模态视觉 + 事件驱动等待 + Shell 启动**”的混合模式，使 MCP 在执行 GUI 任务时更快、更稳、更自然。

## 改进项

### 1. 视觉理解：让模型直接看截图，OCR 降级为可选工具

**现状**：
- `screenshot` 虽然返回 base64 PNG，但当前执行流程习惯先调用 `ocr` 提取文字，再让模型基于文字做决策。
- `ocr` 调用会启动 PaddleOCR subprocess，耗时 2-10 秒。

**改进**：
- 明确 `screenshot` 的核心价值是“给多模态模型看”。
- `ocr` 保留为独立工具，仅在需要提取大量文字（日志、表格、代码块）时由模型主动调用。
- 在工具描述中提示模型：优先直接阅读图像，需要精确文字时再调用 `ocr`。
- 在 `docs/api.md` 中加入具体调用模式示例：先 `screenshot` → 描述画面 → 必要时 `ocr`。

**改动文件**：
- `computer_use/mcp_server.py`：调整 `screenshot` 和 `ocr` 的工具描述。
- `docs/api.md`：更新视觉工具的使用建议与示例。

### 2. 控件定位：新增 UIA/Accessible 工具族

**现状**：
- 只有 `click`/`move_to` 等坐标工具。
- 项目已有 `computer_use/ui_automation.py`，但只用于内部安全检查，未暴露为 MCP 工具。

> **不一致修复声明**：本计划修复一个已有不一致——`docs/api.md` 将 `inspect_point` 列为可用工具，但 `computer_use/mcp_server.py` 的 `TOOLS` 列表中并未注册它。本计划将 `inspect_point` 注册为 MCP 工具，并同步更新测试。

**改进**：
- 新增 `find_control` 工具：按名称/AutomationId/控件类型/类名在指定作用域内查找控件，返回矩形和中心坐标。
- 新增 `inspect_point` 工具（内部函数已存在，计划一并注册为 MCP 工具）：查询某坐标下的控件信息。
- 扩展 `click`/`move_to` 支持 `target_name` 参数：优先按 UIA 控件定位，fallback 到坐标。
- 新增 `wait_for_window` 工具：事件驱动等待窗口出现/消失，替代固定 `sleep`。
- 新增 `wait_for_control` 工具：等待指定控件出现/可用。

完整输入 schema、返回结构与字段语义见[附录 A](#appendix-a-new-tool-specifications)。

**`find_control` 语义**：
- 搜索遍历根控件的所有后代（descendants），而非仅直接子控件。
- 遍历顺序为**深度优先前序遍历**（depth-first pre-order）。
- 遍历 API 优先使用 `uiautomation` 库的 `GetDescendantControl` / `GetDescendantControls`；若当前安装的库版本缺少 descendants API，则降级为递归 `GetFirstChildControl` + `GetNextSiblingControl`。
- 查询参数（满足 `anyOf` 至少其一即可，多参数同时存在时按“名称 → automation_id → control_type → class_name”的顺序组合过滤）：
  - `name`：控件名称子串或完整名称（由 `match` 决定）。
  - `automation_id`：AutomationId，默认按精确匹配比较。
  - `control_type`：控件类型，如 `Button`、`MenuItem`、`Window`、`Edit`。
  - `class_name`：窗口类名或控件类名。
- `scope` 参数取值：
  - `"desktop"`：从桌面根开始搜索。
  - `"foreground"`：仅搜索当前前台窗口。
  - `"window"`：在指定窗口内搜索，需配合 `window_name`。
- `match` 参数取值（仅作用于 `name` 字段）：
  - `"exact"`：名称完全匹配（大小写不敏感）。
  - `"contains"`：名称包含子串（大小写不敏感）。
  - `"startswith"`：名称以给定字符串开头（大小写不敏感）。
- `scope=window` 时：
  - `window_name` 为必填参数。
  - 窗口名称匹配采用 `contains` 大小写不敏感规则。
  - 若未找到对应窗口，直接返回 `{"found": false, "uia_available": true, "blocked": false, "reason": "parent_window_not_found"}`，不再进入后代遍历。
- 命中多个时返回首个匹配；未命中时返回结构化结果，便于模型换查询重试。
- 可选参数 `sensitive_check=True`（默认 `True`）：返回前先经 `safety.py` 校验目标窗口是否敏感，敏感则拦截并返回结构化 blocked 结果。

**`find_control` 空结果区分**：
返回统一 JSON 结构，使模型能够区分未安装 UIA、未命中控件、父窗口未找到、被安全拦截四种情况：

| 场景 | 返回值 |
|------|--------|
| UIA 库未安装 | `{"found": false, "uia_available": false, "blocked": false, "reason": "uia_not_available"}` |
| 未命中任何控件 | `{"found": false, "uia_available": true, "blocked": false, "reason": "not_found"}` |
| `scope=window` 时父窗口未找到 | `{"found": false, "uia_available": true, "blocked": false, "reason": "parent_window_not_found"}` |
| 命中但被安全拦截 | `{"found": false, "uia_available": true, "blocked": true, "reason": "sensitive_window_blocked", "detail": "..."}` |
| 命中并返回 | `{"found": true, "name": "...", "control_type": "...", "rect": {"left": ..., "top": ..., "right": ..., "bottom": ...}, "center": {"x": ..., "y": ...}, "process_name": "..."}` |

**`click`/`move_to` 新接口**：
- JSON schema 使用 `oneOf` 表达“必须提供 `target_name` 或 `(x, y)` 之一”的条件必填语义。MCP-compatible 示例：
  ```json
  {
    "type": "object",
    "oneOf": [
      {"required": ["target_name"]},
      {"required": ["x", "y"]}
    ],
    "properties": {
      "target_name": {"type": "string", "description": "UIA 控件名称，提供时优先使用"},
      "match": {"type": "string", "enum": ["exact", "contains", "startswith"], "default": "contains", "description": "target_name 匹配模式"},
      "x": {"type": "integer", "description": "屏幕横坐标，target_name 未命中且未提供坐标时必填"},
      "y": {"type": "integer", "description": "屏幕纵坐标，target_name 未命中且未提供坐标时必填"},
      "duration": {"type": "number", "description": "移动持续时间（秒）"}
    }
  }
  ```
- 默认 `target_name` 匹配模式为 `"contains"`，与 `find_control` 保持一致。
- 备选方案：若 `oneOf` 对特定 MCP 客户端不兼容，可拆分为独立工具 `click_at(x, y)` 与 `click_control(target_name)`，并在 `docs/api.md` 中记录拆分决策。
- 校验：调用必须至少包含 `target_name` 或 `(x, y)` 中的一组。
- 执行顺序：
  1. 若提供 `target_name`，先进行 UIA 查找（scope 默认 `"desktop"`，match 默认 `"contains"`）；
  2. 命中控件后，取控件中心坐标，并将该控件的进程名、窗口类名、控件类型传入 `check_target_window` 进行安全检查；检查通过后才执行点击/移动；
  3. 若 UIA 未命中且提供了 `(x, y)`，则回退到坐标模式；
  4. 若两者都未命中，返回明确错误并建议模型用 `screenshot` 或 `find_control` 确认。

**改动文件**：
- `computer_use/ui_automation.py`：扩展查找/等待函数，支持后代遍历、scope/match 参数。
- `computer_use/mcp_server.py`：注册新工具，更新 `click`/`move_to` schema 与工具描述。
- `computer_use/safety.py`：`check_target_window` 支持接收控件元数据（进程名、类名、控件类型）。
- `docs/api.md`：补充控件工具约定。

### 3. 应用启动：新增 `launch_app` / `run` 工具

**现状**：
- 启动程序只能双击桌面图标，依赖坐标。

**改进**：
- 新增 `launch_app(name)` 工具：通过 `Shell.Application` 按桌面/开始菜单名称启动应用。
- 新增 `run(command, args=[], timeout=30)` 工具：执行命令或程序路径（在安全白名单内）。
- 在 `safety.py` 中增加命令/应用启动的安全检查（禁止危险命令）。

完整输入 schema、返回结构与字段语义见[附录 A](#appendix-a-new-tool-specifications)。

**`launch_app(name)` 精确机制**：
- 枚举范围：使用 `win32com.client.Dispatch("Shell.Application").Namespace(...)` 依次枚举 Windows 特殊文件夹 `CSIDL_STARTMENU`、`CSIDL_COMMON_STARTMENU`、`CSIDL_DESKTOPDIRECTORY`、`CSIDL_COMMON_DESKTOPDIRECTORY`（或对应 `Shell.Namespace` 常量），收集其中的快捷方式（`.lnk`）项。
- 名称匹配：
  1. 主匹配：快捷方式显示名称（`Item.Name`）与传入 `name` 进行大小写不敏感精确比较；
  2. 若精确匹配数量为 0，则进行大小写不敏感子串比较（contains）作为回退；
  3. 若精确匹配命中多个，直接视为“多个匹配”，不再使用子串回退。
- 解析 `.lnk` 目标路径：
  - 使用 `win32com.client.Dispatch("WScript.Shell").CreateShortcut(lnk_path)` 创建 Shortcut 对象，读取其 `.TargetPath` 属性。
  - 该目标路径用于白名单校验、返回字段 `target_path`、敏感进程检查。
- 歧义处理：
  - 单个匹配：调用 `Item.InvokeVerb("Open")` 启动，返回 `{"launched": true, "name": "...", "target_path": "..."}`。
  - 多个匹配：不启动任何应用，返回 `{"launched": false, "matches": [{"name": "...", "target_path": "..."}, ...]}` 供模型确认。
  - 无匹配：返回 `{"launched": false, "error": "No application named '...' found"}`。
- 安全校验：
  1. 解析快捷方式目标可执行文件，将目标绝对路径/可执行文件名与 `safety.allowed_commands` 白名单进行匹配；不在白名单内则返回 `{"launched": false, "error": "Target is in sensitive process list or not in allowed_commands whitelist"}`。
  2. 将目标进程名传入 `check_target_window` 敏感进程列表检查；命中敏感进程则同样返回上述 blocked 错误。

**`run` 工具白名单规则**：
- 白名单来源：`config.yaml` 中 `safety.allowed_commands`，值为精确命令名或可执行文件绝对路径列表。
- 输入语义：`run` 接收 `command` + `args` 两个独立字段，**不是**单个 shell 字符串。MCP 客户端/模型将可执行文件放入 `command`，将参数列表放入 `args`。
  - `command`：可执行文件名称或绝对路径。
  - `args`：字符串数组，作为参数列表依次传递给可执行文件。
  - `timeout`：默认 `30` 秒。
- 命令解析：
  1. 对 `command` 使用 `shutil.which` 在 PATH 中查找；
  2. 若 `command` 已是绝对路径或相对路径，再使用 `Path(command).resolve()` 解析为绝对路径；
  3. 检查 resolved path 或其 basename 是否在 `safety.allowed_commands` 白名单中；不在则拒绝。
- 参数透传：使用 `subprocess.run([executable, *args], ...)` 列表形式调用，避免 shell 解析。
- 默认拒绝：只要 `command` 无法解析到白名单内可执行文件，即拒绝执行。
- 元字符拦截：即使可执行文件在白名单内，若 `command` 字符串本身包含以下 shell 元字符/模式也一律拒绝，防止命令注入：
  - 连接符：`&`、`|`、`;`、`&&`、`||`
  - 重定向：`>`、`<`、`>>`
  - 转义/变量：`^`、`%...%`、`$()`、反引号（`` ` ``）
  - 换行符
- 实现上应在白名单检查之前先进行元字符拦截；一旦命中直接拒绝。
- 返回值：
  - 成功：`{"executed": true, "command": "...", "returncode": 0, "stdout": "...", "stderr": "..."}`
  - 被拦截：`{"executed": false, "error": "Command not in allowed_commands whitelist or contains shell metacharacters"}`

**改动文件**：
- 新增 `computer_use/launcher.py`。
- `computer_use/mcp_server.py`：注册工具。
- `computer_use/safety.py`：增加启动安全策略与元字符检查。
- `config.yaml`：补充 `safety.allowed_commands` 示例。

### 4. 事件驱动：用等待工具替代 `sleep`

**现状**：
- 外部调用脚本常用 `sleep(2~5)` 等待窗口响应。

**改进**：
- 新增 `wait_for_window(name, exists=True, timeout=10)`：等待窗口出现或消失。
- 新增 `wait_for_control(name, automation_id, control_type, exists=True, timeout=10)`：等待指定控件出现/可用。
- 移除或大幅精简 `wait_for_idle`；如需保留，定义为辅助能力而非主要等待手段：
  - 采样窗口 `sample_window=500ms`
  - CPU 阈值 `cpu_threshold=5%`
  - 连续采样次数 `consecutive_samples=3`
  - 进程匹配按精确进程名进行
- 在 `docs/api.md` 和工具描述中建议：优先使用 `wait_for_window` / `wait_for_control` 等事件驱动等待，避免固定 sleep。

完整输入 schema、返回结构与字段语义见[附录 A](#appendix-a-new-tool-specifications)。

**`wait_for_window(name, exists=True, timeout=10)` 语义**：
- 匹配规则：沿用 `find_control` 的 `"contains"` 规则对窗口标题/名称进行大小写不敏感子串匹配。
- 轮询策略：每 200ms 查询一次，直到条件满足或超时。
- 返回值：
  - 超时：`{"present": false, "timeout": true}`
  - 命中：`{"present": true, "name": "...", "rect": {"left": ..., "top": ..., "right": ..., "bottom": ...}}`
- 当 `exists=False` 时，行为反转：等待匹配窗口消失后返回 `{"present": false, "timeout": false}`；超时则返回 `{"present": true, "timeout": true}`。

**`wait_for_control(name, automation_id, control_type, exists=True, timeout=10)` 语义**：
- “可用”定义：控件同时满足 `Exists and Enabled and Visible`。
- 匹配规则：调用 `find_control(..., match="contains", scope="foreground")`，可选 `automation_id`/`control_type` 参数进一步过滤。
- 轮询策略：每 200ms 查询一次，直到条件满足或超时。
- 返回值：
  - 超时：`{"present": false, "timeout": true}`
  - 命中：`{"present": true, "name": "...", "control_type": "...", "enabled": true, "visible": true}`
- 当 `exists=False` 时，等待控件不再可用后返回 `{"present": false, "timeout": false}`；超时则返回 `{"present": true, "timeout": true}`。

**改动文件**：
- `computer_use/ui_automation.py`：实现等待逻辑。
- `computer_use/mcp_server.py`：注册工具。

### 5. OCR 调用路径优化

**现状**：
- OCR 已经支持 subprocess fallback 和结果临时文件，但首次调用仍需等待 PaddleOCR 初始化。

**改进**：
- 在 `ocr` 工具首次被调用前，后台线程预热 PaddleOCR（可选配置 `ocr.preheat`）。
- 预热不阻塞首次 `ocr` 调用；若首次调用时预热尚未完成，则降级为按需初始化。
- 预热失败不报错，仅记录日志，后续调用走正常 on-demand 初始化路径。
- 继续保留“结果写入临时文件”机制，避免 stdout 日志污染。
- 明确 OCR 是可选能力，未安装时返回清晰错误。

**`config.yaml` 示例**：
```yaml
ocr:
  preheat: true  # start PaddleOCR initialization in a background thread on server startup
```

**改动文件**：
- `computer_use/ocr.py`：增加预热逻辑。
- `config.yaml`：增加 `ocr.preheat` 配置示例。

### 6. 安全与回滚

- 所有新工具必须通过 `safety.py` 检查。
- `run` 工具默认白名单机制，仅允许启动已知安全应用。
- `launch_app` 与 `run` 共享 `safety.allowed_commands` 白名单，并对目标进程执行敏感窗口/进程检查。
- 控件操作仍需目标窗口/进程检查，避免误触敏感窗口；当 `click`/`move_to` 通过 `target_name` 解析到控件时，必须将控件所属进程名、窗口类名、控件类型传入 `check_target_window` 完成敏感窗口校验。
- `find_control` 默认开启 `sensitive_check=True`，命中敏感窗口时返回结构化拦截结果（`blocked: true`）。
- 统一安全响应格式：所有**阻断性动作**（sensitive window、whitelist denial、command injection）均通过 `mcp_server._call_tool` 中现有的 `SafetyError` → JSON 路径返回 `{"error": "..."}`。`find_control` 属于查询工具，其 `sensitive_check=True` 时返回结构化的 `found: false, blocked: true` 结果；若模型随后对同一控件执行 `click`/`move_to`，`click`/`move_to` 将抛出 `SafetyError` 并返回 `{"error": "..."}`。
- 每步改动后运行 `pytest tests/` 全量测试。

## 测试策略

新增 GUI/Shell 相关测试采用分层策略，避免对真实桌面环境过度依赖：

1. **单元测试（默认运行）**
   - 对 `find_control`、`wait_for_window`、`wait_for_control` 的解析与参数校验使用 mock 的 UIA 控件树。
   - 对 `run` 工具的命令拆分、白名单匹配、元字符拦截使用纯字符串/配置断言。
   - 对 `launch_app` 的名称匹配与歧义处理使用 mock 的 `Shell.Application` 命名空间。

2. **Shell 启动 mock 测试**
   - 使用 `unittest.mock` 替换 `Shell.Application`（`win32com.client.Dispatch`）或 `launcher.py` 中的调用入口，验证 `launch_app` 传入的动词与路径正确。

3. **手动/集成测试**
   - 涉及真实鼠标、键盘、窗口焦点的测试统一标记为 `manual`（pytest marker），默认不运行。
   - 在 `pytest.ini` 中注册 `manual` marker，避免未注册 marker 告警。
   - 当环境变量 `CI=1` 时，自动跳过所有 `manual` 与依赖真实 GUI 的测试。
   - 为 `manual` 集成测试维护最小清单（至少覆盖：HiBit 启动、控件查找、事件等待、安全拦截）。

4. **回归测试**
   - 每次改动后执行 `pytest tests/ -v`；
   - 受影响的模块额外执行 `pytest tests/test_<module>.py -v` 确保覆盖率不下降。

## 实施顺序

1. **Phase 1：控件工具基础**
   - 扩展 `ui_automation.py`：后代遍历、`scope`/`match` 参数、`sensitive_check`、空结果区分。
   - 暴露 `find_control`、`inspect_point`、`wait_for_window`、`wait_for_control`。
   - 更新 `safety.py`：`check_target_window` 支持控件元数据；`launch_app` 与 `run` 共享白名单。
   - 注册 MCP 工具并写测试。

2. **Phase 2：启动工具**
   - 新增 `launcher.py`（Shell.Application + WScript.Shell 解析 `.lnk`）。
   - 新增 `run` 工具并集成安全白名单与元字符拦截。
   - 注册工具并写测试。

3. **Phase 3：click/move_to 语义化**
   - 为 `click`/`move_to` 增加 `target_name` 与 `match` 参数，更新 JSON schema（`oneOf` 或拆分工具）。
   - 优先 UIA 定位并执行控件级安全检查，fallback 坐标。

4. **Phase 4：视觉理解引导**
   - 更新 `screenshot`/`ocr` 工具描述。
   - 更新 `docs/api.md` 使用建议与示例。

5. **Phase 5：OCR 预热与性能**
   - 增加 `ocr.preheat` 后台线程预热。
   - 基准测试：对“启动 HiBit → 工具 → 注册表清理程序”完整任务至少运行 3 次，分别记录冷启动（无缓存/预热的首次运行）与热启动（已有预热/缓存）的耗时，报告 mean/max。

## 验收标准

- [ ] `find_control("注册表清理程序")` 能返回正确中心坐标
- [ ] `wait_for_window("HiBit Uninstaller")` 在窗口出现后 1 秒内返回，不用固定 sleep
- [ ] `launch_app("HiBit Uninstaller")` 能启动应用
- [ ] `click(target_name="工具")` 优先通过 UIA 点击并通过安全检查
- [ ] 完整复现“启动 HiBit → 工具 → 注册表清理程序”任务，总耗时从数分钟降到 30 秒以内（基准：3 次冷启动/热启动，报告 mean/max；同时记录原 baseline 耗时作为参照）
- [ ] 所有现有测试通过，新增测试覆盖率 ≥80%

## 风险与回滚

| 风险 | 缓解措施 |
|------|---------|
| UIA 对某些非标准控件支持差 | fallback 到坐标点击 + 多模态视觉 |
| `launch_app` 名称匹配歧义 | 精确匹配优先；多个匹配时返回列表供确认，不自动启动 |
| 安全白名单误拦截 | 配置化白名单，用户可扩展 |
| 控件等待超时 | 返回明确错误（`timeout: true`），提示模型用 screenshot 确认 |
| UIA 库未安装 | 工具返回清晰错误（`uia_available: false`），保留坐标点击路径 |
| `wait_for_idle` CPU 采样抖动 | 降级为辅助能力，主等待改为事件驱动 |
| `run` 命令注入 | 元字符拦截 + 仅允许白名单内可执行文件 + `subprocess.run([...])` 列表参数 |
| `launch_app` 启动敏感应用 | 共享 `run` 白名单 + `check_target_window` 敏感进程检查 |
| `launch_app` `.lnk` 目标解析失败 | 使用 WScript.Shell 标准 Shortcut API；解析失败时返回错误并记录日志 |

## 不纳入本次范围

- 修改 PaddleOCR 本身的识别能力。
- 支持非 Windows 平台（项目当前定位就是 Windows GUI 自动化）。
- 引入 LLM 多模态模型能力本身（这是客户端/模型侧能力，MCP 只需提供截图）。

## 实施注意事项

- 执行期间涉及工具注册、文档变更、安全策略调整时，同步更新 `CHANGELOG.md` 与 `docs/CURRENT.md`。
- 若修改了 `AGENTS.md` 中提及的流程或约定，运行 `python scripts/agent_links.py check` 并修复同步不一致。

---

## Appendix A: New Tool Specifications

本附录为所有新增 MCP 工具提供可直接用于 `mcp_server.py` 注册的完整 `inputSchema` 与返回 JSON 结构。字段名、类型、必填规则、默认值均按以下规范实现，实现者不应自行猜测。

### `find_control`

**inputSchema**：
```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string", "description": "Control name substring or full name"},
    "automation_id": {"type": "string"},
    "control_type": {"type": "string", "description": "e.g. Button, MenuItem, Window"},
    "class_name": {"type": "string"},
    "scope": {"type": "string", "enum": ["desktop", "foreground", "window"], "default": "desktop"},
    "window_name": {"type": "string", "description": "Required when scope=window"},
    "match": {"type": "string", "enum": ["exact", "contains", "startswith"], "default": "contains"},
    "sensitive_check": {"type": "boolean", "default": true}
  },
  "anyOf": [
    {"required": ["name"]},
    {"required": ["automation_id"]},
    {"required": ["control_type"]},
    {"required": ["class_name"]}
  ]
}
```

**Returns on found**：
```json
{"found": true, "name": "...", "control_type": "...", "rect": {"left": 0, "top": 0, "right": 100, "bottom": 20}, "center": {"x": 50, "y": 10}, "process_name": "..."}
```

**Returns on miss**：
```json
{"found": false, "uia_available": true, "blocked": false, "reason": "not_found"}
```

**Returns UIA not installed**：
```json
{"found": false, "uia_available": false, "blocked": false, "reason": "uia_not_available"}
```

**Returns blocked**：
```json
{"found": false, "uia_available": true, "blocked": true, "reason": "sensitive_window_blocked", "detail": "..."}
```

**Returns parent window not found (scope=window)**：
```json
{"found": false, "uia_available": true, "blocked": false, "reason": "parent_window_not_found"}
```

---

### `inspect_point`

**inputSchema**：
```json
{"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}
```

**Returns existing ControlInfo as JSON**：
```json
{"name": "...", "control_type": "...", "class_name": "...", "process_name": "...", "is_password": false, "rect": {"left": 0, "top": 0, "right": 100, "bottom": 20}, "center": {"x": 50, "y": 10}}
```

---

### `wait_for_window`

**inputSchema**：
```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "exists": {"type": "boolean", "default": true},
    "timeout": {"type": "number", "default": 10}
  },
  "required": ["name"]
}
```

**Returns on success**：
```json
{"present": true, "name": "...", "rect": {"left": 0, "top": 0, "right": 100, "bottom": 20}}
```

**Returns on timeout**：
```json
{"present": false, "timeout": true}
```

**Note**：`exists=False` waits for window to disappear; success returns `{"present": false, "timeout": false}`.

---

### `wait_for_control`

**inputSchema**：
```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "automation_id": {"type": "string"},
    "control_type": {"type": "string"},
    "exists": {"type": "boolean", "default": true},
    "timeout": {"type": "number", "default": 10}
  },
  "anyOf": [
    {"required": ["name"]},
    {"required": ["automation_id"]},
    {"required": ["control_type"]}
  ]
}
```

**Returns on success**：
```json
{"present": true, "name": "...", "control_type": "...", "enabled": true, "visible": true}
```

**Returns on timeout**：
```json
{"present": false, "timeout": true}
```

**Note**：`exists=False` waits for control to become unavailable; success returns `{"present": false, "timeout": false}`.

---

### `launch_app`

**inputSchema**：
```json
{"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
```

**Returns single match**：
```json
{"launched": true, "name": "HiBit Uninstaller", "target_path": "C:\\Program Files\\HiBit\\HiBitUninstaller.exe"}
```

**Returns multiple matches**：
```json
{"launched": false, "matches": [{"name": "...", "target_path": "..."}, ...]}
```

**Returns no match**：
```json
{"launched": false, "error": "No application named '...' found"}
```

**Returns blocked**：
```json
{"launched": false, "error": "Target is in sensitive process list or not in allowed_commands whitelist"}
```

---

### `run`

**inputSchema**：
```json
{"type": "object", "properties": {"command": {"type": "string"}, "args": {"type": "array", "items": {"type": "string"}}, "timeout": {"type": "number", "default": 30}}, "required": ["command"]}
```

**说明**：`command` 是可执行文件名称或绝对路径；`args` 是参数列表，二者分开传递，不拼接成 shell 字符串。

**Returns**：
```json
{"executed": true, "command": "notepad.exe", "returncode": 0, "stdout": "...", "stderr": "..."}
```

**On blocked**：
```json
{"executed": false, "error": "Command not in allowed_commands whitelist or contains shell metacharacters"}
```
