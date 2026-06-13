# 平滑光标移动实现

## 产物身份

为 `computer-use` MCP 服务器的 `click` 和 `move_to` 操作增加 `duration` 参数，使光标从当前位置平滑移动到目标位置，而不是瞬间跳跃。默认 `duration = 0.2` 秒。

## 改动范围

- `computer_use/core.py`：`click` 和 `move_to` 增加 `duration` 参数，透传给 `pyautogui.click` / `pyautogui.moveTo`。
- `computer_use/mcp_server.py`：MCP 工具 Schema 增加可选 `duration` 字段；调度时读取并透传；返回结果包含实际使用的 `duration`。
- `computer_use/cli.py`：`click` 和 `move` 子命令增加 `--duration` 选项。
- `tests/test_core.py`：新增 4 个测试，覆盖默认值和自定义值。
- `tests/test_mcp_server.py`：新增 4 个测试，覆盖自定义 `duration` 和默认 `duration` 的 MCP 层透传。
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
