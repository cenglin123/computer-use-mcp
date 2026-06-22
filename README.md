# Computer Use MCP

A local MCP server that gives AI agents the ability to see and control a Windows desktop through screenshots, UI Automation, and mouse/keyboard actions. 42 deterministic tools — no model calls, no OCR, no magic.

---

## Quick Start

### Install

```powershell
python -m venv .venv
.venv\Scripts\activate.ps1
pip install -e .
pip install -e ".[dev]"   # optional: pytest, pywin32
```

### Configure

Copy `config.example.yaml` to `~/.computer-use/config.yaml`. The config controls log/screenshot/trace directories, safety rules, and whitelist defaults. By default, common system apps (notepad, calc, explorer, etc.) are pre-approved (`use_builtin_defaults: true`). Set to `false` for strict whitelist mode.

### Register with an MCP Client

The server runs over stdio — no network ports. Point your MCP client at the venv Python:

**OpenCode** (`~/.config/opencode/opencode.json`):
```json
{
  "mcp": {
    "computer-use": {
      "command": ["D:\\path\\to\\.venv\\Scripts\\python.exe", "-m", "computer_use.mcp_server"],
      "env": { "PYTHONUTF8": "1" },
      "enabled": true,
      "type": "local"
    }
  }
}
```

**Generic MCP client:**
```json
{
  "mcpServers": {
    "computer-use": {
      "command": "C:\\path\\to\\.venv\\Scripts\\python.exe",
      "args": ["-m", "computer_use.mcp_server"]
    }
  }
}
```

Replace `C:\\path\\to\\.venv` with the absolute path to this checkout's virtual environment. `PYTHONUTF8=1` is recommended on Chinese Windows.

### Verify

```powershell
# Self-check (no mouse/keyboard input)
python -m computer_use doctor

# Read-only protocol smoke test
python tools\smoke_mcp_client.py --server .\.venv\Scripts\python.exe --args -m computer_use.mcp_server
```

Expected: `doctor` returns JSON with `status: ok`, smoke test returns `status: ok` with 42 tools listed.

---

## Capability Boundary

### What it does

- **Screenshot** the desktop or a single monitor, return a local PNG path (never base64 in responses).
- **Crop** with automatic red L-bracket region annotation — see both cursor position and crop bounds in one `annotated_source_path`.
- **Click, move, scroll, type, drag** at physical virtual screen coordinates with coordinate→safety→input chain.
- **Find controls** via UI Automation (`find_control`, `get_ui_snapshot`, `click_by_uid`).
- **Wait** for windows/controls to appear/disappear (`wait_for_window`, `wait_for_control`).
- **Launch apps** by Start Menu / Desktop shortcut (`launch_app`, `activate_window`) with runtime whitelist escalation.
- **Batch** multi-step sequences in a single MCP call (`batch`, `run_task_plan`).
- **Audit** execution with trace, task sessions, and retrospective reports (`start_task`, `review_task_session`, `save_review`).

### What it does NOT do

- Does NOT call any model API or perform OCR.
- Does NOT work on macOS or Linux (Windows only).
- Does NOT bypass UAC, UIAccess/UIPI, or game anti-cheat protections.
- Does NOT support mixed-DPI multi-monitor setups (fail-fast).
- Does NOT handle dynamic monitor hot-plugging (restart server to pick up new layouts).

---

## Tools Overview

42 tools organized by category:

| Category | Tools |
|----------|-------|
| **Observe** | `screenshot`, `get_ui_snapshot`, `get_monitors`, `find_control`, `inspect_point` |
| **Visual click** | `click_on_screenshot`, `crop_screenshot` (with red L-bracket annotation) |
| **Raw input** | `click`, `move_to`, `type`, `key_combo`, `press_key`, `scroll`, `drag`, `mouse_down/up` |
| **Composite** | `open_menu`, `fill_form`, `scroll_until` |
| **Batch** | `batch`, `run_task_plan` |
| **Task audit** | `start_task`, `finish_task`, `review_task`, `review_task_session`, `save_review` |
| **Wait** | `wait_for_window`, `wait_for_control`, `sleep` |
| **Launch** | `launch_app`, `activate_window` |
| **Security** | `add_command_whitelist`, `add_window_exception` |

For the full tool reference with every parameter and description, load the `computer_use_guidance` MCP prompt or read [skills/computer-use/SKILL.md](skills/computer-use/SKILL.md).

---

## Safety & Permissions

All mouse/keyboard input goes through a deterministic safety chain:

- **Coordinate validation**: input must fall within the primary monitor bounds. Secondary-monitor coordinates are rejected.
- **Target window check**: the control under the cursor is inspected. Sensitive processes (keepass, certmgr, 1password, lastpass, mmc) and window classes (`#32770`) are blocked. **Hardcoded sensitive processes are NEVER bypassable.**
- **Text validation**: dangerous shell commands and file deletions are rejected before typing.

### Runtime Whitelist Escalation

When `launch_app` or a window interaction is blocked, the agent asks the user to grant permission at one of three levels:

| Level | Scope | How to grant |
|-------|-------|-------------|
| `once` | This execution only | `add_command_whitelist(command, level="once")` |
| `session` | Until server restart | `add_command_whitelist(command, level="session")` |
| `permanent` | Writes to config.yaml | `add_command_whitelist(command, level="permanent")` |

For sensitive windows (e.g. `#32770`): `add_window_exception(class_name="#32770", level="once|session")`.

Built-in defaults (`use_builtin_defaults: true`) pre-approve common system apps. Set to `false` for whitelist-only strict mode.

---

## For AI Agents

### Model Requirement

This server is intended for **multimodal agents**. The `screenshot` tool returns a local PNG path — the agent must open and understand that image file. Use `include_image=true` to receive the screenshot inline when supported by the client.

A text-only agent can still use structured tools (`get_monitors`, `find_control`, `get_ui_snapshot`, `review_task`, `review_task_session`, `list_tasks`), but cannot perform visual tasks reliably.

### Coordinate System

All tool coordinates are **physical virtual screen pixels** (mss coordinates), 1:1 with screenshot pixels. Origin is top-left of the virtual desktop.

- `monitor=0`: entire virtual desktop (may span multiple monitors).
- `monitor=1`: primary monitor (default).
- `monitor=2,3,...`: secondary monitors (screenshot-only; input always restricted to primary).

Prefer `click_on_screenshot(screenshot_path, image_x, image_y)` over raw `click(x, y)` — it maps image pixels to screen coordinates using capture metadata and runs the full safety chain.

### Recommended Workflow

1. **Start a task**: `start_task(goal="...")` → keep the returned `task_id` for all subsequent tool calls. If an active task exists, tools without `task_id` are rejected.
2. **Observe**: `screenshot(monitor=1)` → read the returned file. For small targets, `crop_screenshot` to zoom in. The `annotated_source_path` shows both the cursor crosshair and the crop region in one image.
3. **Locate**: prefer UIA tools (`find_control`, `click_by_text`, `click_by_uid`). Fall back to screenshot-based coordinates only when UIA cannot see the target.
4. **Act**: use `batch` for multi-step deterministic sequences. Avoid Bash scripts wrapping MCP calls.
5. **Verify**: screenshot after every action. The red cursor marker in the screenshot confirms where input actually landed. `annotation_layers` provides structured cursor/crop coordinates for programmatic verification.
6. **Close out**: `review_task_session(task_id)` for audit evidence, then `finish_task(task_id, summary="...")`. Cancel abandoned tasks with `cancel=true`.

**Fast path**: for workflows validated on a stable desktop layout, condense step 2-4 into one `batch` with `wait_for_window` guards and a single `final_screenshot`. See local `docs/recipes/*.md` for machine-specific recipes.

### Load the Full Discipline

The authoritative agent discipline is in [skills/computer-use/SKILL.md](skills/computer-use/SKILL.md). If your client supports MCP prompts, load `computer_use_guidance` instead. Key rules the SKILL enforces:

- Never scan `~/.computer-use/traces/` to guess task state — use `review_task_session`.
- Never call `python -m computer_use screenshot` from Bash — it outputs base64 that bloats context.
- `screenshot` returns `saved_path`, not base64 (except `include_image=true` opt-in).
- Wait for windows with `wait_for_window`, not `sleep`.
- Crop after orienting — a 300×120 crop costs a fraction of a 1920×1080 full frame in context.

---

## Configuration Reference

Runtime config defaults to `~/.computer-use/config.yaml`. Key settings:

| Key | Default | Description |
|-----|---------|-------------|
| `log_dir` | `~/.computer-use/logs` | Rotating log (10 MB, 5 backups) |
| `screenshot_dir` | `~/.computer-use/screenshots` | Where PNGs are saved |
| `trace_dir` | `~/.computer-use/traces` | Execution traces (date-partitioned) |
| `task_dir` | `~/.computer-use/tasks` | Business task sessions |
| `safety.allowed_commands` | `[]` | Additional command whitelist entries |
| `safety.use_builtin_defaults` | `true` | Pre-approve common system apps |
| `safety.screenshot_sensitive_window_check` | `true` | Redact screenshots over sensitive windows |
| `display.default_monitor` | `1` | Default screenshot monitor |

Override with `COMPUTER_USE_CONFIG` env var. The legacy `~/.kimi-code/mcp/computer-use/config.yaml` path is still supported as fallback.

`config.yaml` and `docs/recipes/` are **excluded from git tracking** (`.gitignore`) — they contain machine-specific data and should never be pushed to GitHub.

---

## Development

### Local Debug CLI

```powershell
python -m computer_use doctor           # self-check
python -m computer_use screenshot       # capture to PNG (base64 stdout)
python -m computer_use size             # virtual screen size
python -m computer_use monitors         # list monitors
python -m computer_use click 100 200    # click at coordinates
python -m computer_use type "hello"     # type text
python -m computer_use key ctrl c       # key combo
```

### Running Tests

```powershell
# Automated suite (423 tests, no real GUI)
.venv\Scripts\python.exe -m pytest tests/ -v -m "not manual"

# Real-GUI integration tests (idle desktop only!)
$env:COMPUTER_USE_RUN_MANUAL = "1"
.venv\Scripts\python.exe -m pytest tests/manual -v
```

### Documentation

| Document | Topic |
|----------|-------|
| [AGENTS.md](AGENTS.md) | AI agent behavior rules + task workflow |
| [STRUCTURE.md](STRUCTURE.md) | Full document index |
| [docs/overview.md](docs/overview.md) | Architecture & design decisions |
| [docs/api.md](docs/api.md) | MCP tool contracts |
| [docs/deployment.md](docs/deployment.md) | Environment setup & env vars |
| [docs/pitfalls.md](docs/pitfalls.md) | Known traps (encoding, coordinates, UIA gaps) |
| [skills/computer-use/SKILL.md](skills/computer-use/SKILL.md) | Agent operating discipline |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## Troubleshooting

- **Server fails to start**: Activate venv, confirm `mcp` is installed.
- **Coordinates are wrong**: Mixed-DPI monitors cause fail-fast. Ensure uniform scaling.
- **Clicks don't land**: Some apps block synthetic input (UAC/UIPI/anti-cheat). Use UIA Invoke when available.
- **Chinese text garbled**: Set `PYTHONUTF8=1` in the MCP server environment.
- **`launch_app` blocked**: Use runtime whitelist escalation (`add_command_whitelist`) or add the path to `config.yaml`.
- **Screenshot appears empty/redacted**: The capture region contains a sensitive window. Move/resize the target app.
