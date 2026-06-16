# Computer Use MCP

A local MCP server that gives AI agents the ability to see and control a Windows desktop through screenshots, UI Automation, and mouse/keyboard actions.

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

## Register with an MCP Client

Use the Python interpreter from this checkout's virtual environment and run the server module over stdio.

Generic MCP client shape:

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

Kimi Code TOML shape:

```toml
[mcp.servers.computer-use]
command = "C:\\Project\\computer-use-mcp\\.venv\\Scripts\\python.exe"
args = ["-m", "computer_use.mcp_server"]
```

Replace the path with the absolute path where you cloned this server. The server itself does not depend on a specific MCP client.

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
