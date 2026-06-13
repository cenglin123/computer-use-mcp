# 平滑光标移动实现

## 产物身份

为 `computer-use` MCP 服务器的 `click` 和 `move_to` 操作增加 `duration` 参数，使光标从当前位置平滑移动到目标位置，而不是瞬间跳跃。默认 `duration = 0.2` 秒。

## 改动范围

- `computer_use/core.py`：`click` 和 `move_to` 增加 `duration` 参数，透传给 `pyautogui.click` / `pyautogui.moveTo`。
- `computer_use/mcp_server.py`：MCP 工具 Schema 增加可选 `duration` 字段；调度时读取并透传；返回结果包含实际使用的 `duration`。
- `computer_use/cli.py`：`click` 和 `move` 子命令增加 `--duration` 选项。
- `tests/test_core.py`：新增多个测试，覆盖默认值、自定义值、负值、NaN、零值等边界。
- `tests/test_mcp_server.py`：新增多个测试，覆盖自定义 `duration`、默认 `duration` 以及非法 `duration` 的 MCP 层错误响应。
- `docs/api.md`：文档说明 `duration` 行为。
- `CHANGELOG.md`：记录变更。

## 触发原因

用户反馈：光标瞬移会导致某些应用的悬停菜单/下拉框在点击前关闭。平滑移动可显著降低该问题发生率。

## 验收标准

1. `click` / `move_to` 默认使用 0.2 秒平滑移动。
2. MCP、CLI、core API 均支持自定义 `duration`。
3. 所有既有测试与新测试通过：`pytest tests/ -q`。
4. 文档与 CHANGELOG 同步更新。

## 已知限制

- 若应用对鼠标移动极为敏感，仍可能需要调大 `duration`。
- 此实现仍使用全局光标，无法完全避免与用户操作冲突（该问题在 `docs/pitfalls.md` 中另有记录）。

## 本次修订目标（来自 design-review highlights）

1. **单一权威源**：消除 `0.2` 在 `core.py` / `mcp_server.py` / `cli.py` 中的重复硬编码。默认值应来自 `core.py` 中的常量（如 `DEFAULT_MOVE_DURATION`），MCP 与 CLI 从该常量派生默认值。
2. **取值边界与文档**：为 `duration` 定义并校验可接受范围（如 `duration >= 0`），并在 `docs/api.md` 中明确说明；异常值应给出清晰的错误信息而非透传给 `pyautogui`。
3. **减少鼠标工具重复模式**：抽象 `mcp_server.py` 和 `cli.py` 中 `click`/`move_to` 的公共校验、检查、调用、响应构造流程，使新增鼠标工具时改动更集中。
