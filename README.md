# Computer Use MCP

A local MCP server that gives AI agents the ability to see and control a Windows desktop through screenshots, UI Automation, and mouse/keyboard actions.

## Model requirement

This server is intended for multimodal agents. The MCP `screenshot` tool returns a local PNG path, so the client/model must be able to open and understand image files to perform visual GUI tasks. A text-only model can still call structured tools such as `get_monitors`, `find_control`, task review, or audit commands, but it cannot reliably use screenshots to decide where to click.

## What it does

- Takes screenshots of your desktop and returns saved local file paths to MCP clients.
- Can also capture a single monitor via the `monitor` parameter.
- Clicks, moves, scrolls, and types at physical virtual screen coordinates.
- Presses key combinations like `ctrl+c`.
- Enforces deterministic safety rules: dangerous commands, file deletions, and password fields are blocked.

## What it does NOT do

- Does NOT call any model API itself.
- Does NOT work on macOS or Linux (Windows only).
- Does NOT bypass UAC, UIAccess/UIPI, or game anti-cheat protections.
- Does NOT support mixed-DPI multi-monitor setups in the MVP (fail-fast).
- Does NOT handle dynamic monitor hot-plugging; restart the server to pick up new layouts.

## Install

```powershell
# 1. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate.ps1

# 2. Install dependencies
pip install -e .

# 3. (Optional) install dev dependencies
pip install -e ".[dev]"
```

## First run

1. Run `python -m computer_use doctor`.
2. Register the MCP server in your client.
   - Generic MCP client: see `examples/clients/generic-mcp.json`.
   - Kimi Code: see `examples/clients/kimi-code.toml`.
3. If your client supports MCP prompts, load `computer_use_guidance`.
4. If your client supports Skills, load `skills/computer-use/SKILL.md`.
5. Run read-only smoke tools first: `get_monitors`, `get_ui_snapshot`, `review_task_session` on an explicit task.
6. Only then perform real mouse/keyboard tasks.

## Tests

Run the automated test suite (excludes real-GUI manual tests):

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v -m "not manual"
```

To run the real-GUI integration tests in `tests/manual/`:

```powershell
$env:COMPUTER_USE_RUN_MANUAL = "1"
.venv\Scripts\python.exe -m pytest tests/manual -v
```

Only run manual tests on an idle Windows desktop with no sensitive windows visible.

## Register with an MCP Client

Use the Python interpreter from this checkout's virtual environment and run the server module over stdio.

### cc-switch (recommended for multi-client management)

If you use [cc-switch](https://github.com/Cong-Cong-Man/ClaudeCodeSwitch) to manage MCP servers across clients:

1. Install this server locally (see [Install](#install)).
2. Copy `config.example.yaml` to `~/.computer-use/config.yaml` and edit `allowed_commands`.
3. Open cc-switch and go to the MCP management page.
4. Click **Add MCP** / **+** and fill in:
   - **Name**: `computer-use`
   - **Type**: `stdio`
   - **Command**: `C:\Project\computer-use-mcp\.venv\Scripts\python.exe`
   - **Args**: `-m computer_use.mcp_server`
5. Enable the clients you want (opencode, codex, gemini, etc.).
6. Reactivate the MCP entry or restart the target client to pick up the latest code after updates.

### Generic MCP client

```json
{
  "mcpServers": {
    "computer-use": {
      "command": "C:\\Project\\computer-use-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "computer_use.mcp_server"]
    }
  }
}
```

### Kimi Code

```toml
[mcp.servers.computer-use]
command = "C:\\Project\\computer-use-mcp\\.venv\\Scripts\\python.exe"
args = ["-m", "computer_use.mcp_server"]
```

Replace the path with the absolute path where you cloned this server. The server itself does not depend on a specific MCP client.

## Agent guidance

Prefer MCP prompt `computer_use_guidance` when your client supports prompts. Agents that support Skills can load [skills/computer-use/SKILL.md](skills/computer-use/SKILL.md) for safe operating discipline. Generic MCP clients can use [docs/agent-usage.md](docs/agent-usage.md) or [examples/clients/agent-prompt.md](examples/clients/agent-prompt.md) as a prompt snippet.

## 如何使用该 MCP 工具

这个 MCP 适合让多模态 AI Agent 操作 Windows 桌面应用。它本身不包含模型，也不替你规划任务；它只提供观察屏幕、读取 UIA 信息、控制鼠标键盘、记录 trace/task 的本地工具。

推荐流程：

1. 安装依赖后先运行自检：

   ```powershell
   python -m computer_use doctor
   ```

   确认输出为 JSON，且关键检查为 `ok`。如果只有 `model_capability` 是 `warning`，表示 MCP 环境可用，但执行视觉 GUI 任务仍需要多模态模型或客户端能读取本地 PNG 截图。

2. 在你的 MCP 客户端中注册服务器：

   ```json
   {
     "mcpServers": {
       "computer-use": {
         "command": "C:\\Project\\computer-use-mcp\\.venv\\Scripts\\python.exe",
         "args": ["-m", "computer_use.mcp_server"]
       }
     }
   }
   ```

   把 `command` 改成你本机仓库虚拟环境里的 Python 绝对路径。Kimi Code 可参考 [examples/clients/kimi-code.toml](examples/clients/kimi-code.toml)，通用客户端可参考 [examples/clients/generic-mcp.json](examples/clients/generic-mcp.json)。

3. 让 Agent 读取使用指南：

   - 如果客户端支持 MCP prompts，加载 `computer_use_guidance`。
   - 如果客户端支持 Skills，加载 [skills/computer-use/SKILL.md](skills/computer-use/SKILL.md)。
   - 如果都不支持，把 [examples/clients/agent-prompt.md](examples/clients/agent-prompt.md) 的内容放进 Agent 系统提示或任务提示。

4. 先做只读 smoke test，不要一上来点击或输入：

   ```powershell
   python tools\smoke_mcp_client.py --server .\.venv\Scripts\python.exe --args -m computer_use.mcp_server
   ```

   也可以让 Agent 先调用 `get_monitors`、`screenshot`、`get_ui_snapshot`、`start_task`、`review_task_session` 等只读或审计类工具，确认工具链能正常返回结果。

5. 执行真实 GUI 任务时，按这个闭环走：

   - `start_task(goal=...)` 创建业务任务会话，后续工具调用带上返回的 `task_id`。
   - 先观察：优先 `screenshot` 和 `get_ui_snapshot`，不要凭空猜坐标。
   - 再定位：能用 `find_control` / `click_control` 等 UIA 工具时优先用语义定位；UIA 不可用时再根据截图坐标操作。
   - 再动作：多步操作优先用原生 `batch`，不要在 Bash/PowerShell 里手写脚本绕过 MCP。
   - 再验证：每轮动作后截图或读取 snapshot，确认界面状态确实变化。
   - 最后复盘：用 `review_task_session(task_id)` 查看 trace、截图、artifact，再 `finish_task(task_id, summary=...)` 结束任务。

6. 给 Agent 的任务描述可以这样写：

   ```text
   使用 computer-use MCP 操作 Windows 桌面。请先 start_task 创建任务，
   通过 screenshot/get_ui_snapshot 观察界面，优先使用 UIA 语义定位，
   必要时再用坐标点击。每次真实输入后截图验证，最后 review_task_session
   并 finish_task。不要扫描 ~/.computer-use/traces 猜测任务状态。
   ```

注意事项：

- 视觉 GUI 任务必须使用多模态模型；纯文本模型不能可靠地根据截图决定点击位置。
- `screenshot` 返回的是本地 PNG 路径，不返回 base64；客户端或模型必须能读取该文件。
- 鼠标键盘是真实输入设备，运行前确认当前机器无人手动操作鼠标键盘。
- 不要绕过 `safety.py` 的坐标和窗口安全检查；遇到 `next_action` 时优先按返回建议修正。

## Coordinate system

All tool coordinates are **physical virtual screen pixels** (mss coordinates).
The origin is the top-left of the virtual desktop and coordinates map 1:1 with
screenshot pixels.

- The virtual desktop may span multiple monitors.
- Valid coordinates must fall within an actual monitor; coordinates in virtual
  screen gaps are rejected.
- Monitor indices follow the mss 1-based convention: `1` = primary, `2` =
  secondary, etc. Use `0` for the entire virtual desktop.

If your setup has multiple monitors with different scaling factors, the server
will fail fast in the MVP.

## Tools

| Tool | Description |
|------|-------------|
| `screenshot` | Capture the virtual desktop or one monitor and return a saved PNG path. |
| `get_monitors` | Return all monitors with index, primary flag, and bounds. |
| `click` | Click at physical virtual screen coordinates. |
| `move_to` | Move cursor to physical virtual screen coordinates. |
| `scroll` | Scroll wheel by amount, optionally at coordinates. |
| `type` | Type text. |
| `key_combo` | Press key combination. |

## Local debug CLI

```powershell
# Screenshot to stdout (base64, debug CLI only)
python -m computer_use screenshot

# Screenshot a single monitor
python -m computer_use screenshot --monitor 2

# Virtual screen size
python -m computer_use size

# List monitors
python -m computer_use monitors

# Click at (100, 200)
python -m computer_use click 100 200

# Type text
python -m computer_use type "hello world"

# Key combo
python -m computer_use key ctrl c
```

## Run tests

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

## Safety

- Dangerous shell commands and file deletions are blocked.
- Password controls are detected via UI Automation and refused.
- Sensitive application processes/window classes are blocked.
- All actions are logged to `~/.computer-use/logs/computer-use.log` with rotation by default.

## Configuration

Runtime configuration defaults to `~/.computer-use/config.yaml`. Set
`COMPUTER_USE_CONFIG` to point at another YAML file, or pass an explicit config
path in code. For compatibility, if the new default config does not exist but
the legacy `~/.kimi-code/mcp/computer-use/config.yaml` exists, it is still read.

Use `config.yaml` in this repository as a template to customize logging,
screenshot, trace, task, display, and safety settings. MCP client config files
are only for registering the server process with that client.

If `launch_app` returns a whitelist error, copy `config.example.yaml` to
`~/.computer-use/config.yaml` and add the target application to
`safety.allowed_commands`. Sensitive processes are blocked even if listed.

## 文档

| 文档 | 说明 |
|------|------|
| [docs/overview.md](docs/overview.md) | 系统架构与设计决策 |
| [docs/api.md](docs/api.md) | MCP 工具约定 |
| [docs/deployment.md](docs/deployment.md) | 部署与环境配置 |
| [docs/pitfalls.md](docs/pitfalls.md) | 已知环境陷阱 |
| [CHANGELOG.md](CHANGELOG.md) | 变更记录 |

## AI Agent 协作

本仓库配置了面向 AI Agent 的文档体系。如果你是 AI Agent，请加载 [AGENTS.md](AGENTS.md)（或 [CLAUDE.md](CLAUDE.md) / [GEMINI.md](GEMINI.md)）获取行为规则和信息导航。

## Troubleshooting

- **Server fails to start**: Check that your virtual environment is activated
  and that `mcp` is installed.
- **Coordinates are wrong**: Ensure you are using physical virtual screen
  pixels (mss coordinates) and that you do not have mixed-DPI monitors.
- **Clicks don't work in some apps**: Some apps block synthetic input
  (UAC/UIPI/anti-cheat). This is a documented limitation.
