# Computer Use for Kimi Code CLI

A local MCP Server that gives Kimi Code CLI the ability to see and control your Windows desktop through screenshots and mouse/keyboard actions.

## What it does

- Takes screenshots of your full virtual desktop (all monitors) and returns them as base64 PNG.
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

## Register with Kimi Code CLI

Add the following to your `~/.kimi-code/config.toml`:

```toml
[mcp.servers.computer-use]
command = "C:\\Users\\<user>\\.kimi-code\\mcp\\computer-use\\.venv\\Scripts\\python.exe"
args = ["-m", "computer_use.mcp_server"]
```

Replace `<user>` with your Windows username, or use the absolute path where you cloned this server.

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
| `screenshot` | Capture the virtual desktop (or a single monitor) as base64 PNG. |
| `get_screen_size` | Return virtual screen size (width, height). |
| `get_monitors` | Return all monitors with index, primary flag, and bounds. |
| `click` | Click at physical virtual screen coordinates. |
| `move_to` | Move cursor to physical virtual screen coordinates. |
| `scroll` | Scroll wheel by amount, optionally at coordinates. |
| `type` | Type text. |
| `key_combo` | Press key combination. |

## Local debug CLI

```powershell
# Screenshot to stdout (base64)
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
- All actions are logged to `~/.kimi-code/logs/computer-use.log` with rotation.

## Configuration

Edit `config.yaml` in this directory to customize logging directory and safety
lists. Set `display.default_monitor` to `0` (virtual desktop) or a 1-based
monitor index to change the default screenshot target.

The `~/.kimi-code/config.toml` file is used only to register the server
with Kimi Code CLI.

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
