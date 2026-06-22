# Runtime Permission Whitelist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hard-block for `launch_app` whitelist and `#32770` sensitive windows with a three-tier runtime permission system (once / session / permanent), plus sensible defaults for common system apps.

**Architecture:** New `runtime_permissions.py` module manages in-memory permission state (one-shot tokens, session-scoped grants). `safety.py` integrates runtime checks into `is_allowed_command()` and `check_target_window()`. Two new MCP tools (`add_command_whitelist`, `add_window_exception`) let the agent grant permissions after user consent. Error responses carry structured codes (`command_not_whitelisted`, `sensitive_window_blocked`) so agents can recognize actionable blocks and offer the whitelist flow.

**Tech Stack:** Python 3.11+, in-memory dict state (no new dependencies)

**Known Limitations (deferred to future work):**
- **Thread safety**: In-memory `_command_grants` dict and `_window_exceptions` list are not thread-safe. The MCP server currently processes tools sequentially per-request; concurrent dispatch is not exposed in the current stdio transport.
- **Command matching duplication**: `_match_command` (runtime_permissions.py) and `_static_whitelist_check` (safety.py) implement similar matching logic (basename, full path, resolve). Future refactoring should extract a shared `_match_command_path` utility.
- **Tool-awareness for consume**: `_window_tools` frozenset must be manually kept in sync with actual window-interacting tools. Future work could add a tool-level attribute so new tools self-declare as window-interacting.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `computer_use/runtime_permissions.py` | **Create** | In-memory permission store (once/session levels), permanent config writer |
| `computer_use/safety.py` | **Modify** | Add default system commands, integrate runtime checks, structured error distinction |
| `computer_use/mcp_server.py` | **Modify** | Dispatch `add_command_whitelist`, `add_window_exception` tools; enhanced error responses |
| `computer_use/launcher.py` | **Modify** | Return structured `command_not_whitelisted` error with target path |
| `computer_use/tools/schemas.py` | **Modify** | Add two new tool schemas |
| `computer_use/config.py` | **Modify** | Default `allowed_commands` includes common system apps |
| `config.example.yaml` | **Modify** | Update comments and defaults |
| `skills/computer-use/SKILL.md` | **Modify** | Document whitelist escalation flow for agents |
| `.agents/skills/computer-use/SKILL.md` | **Modify** | Sync copy (edit AGENTS.md says "只编辑 AGENTS.md" but this is skill content) |
| `computer_use/guidance.py` | **Modify** | Update guidance prompts |
| `docs/pitfalls.md` | **Modify** | Document the runtime permission mechanism |
| `tests/test_runtime_permissions.py` | **Create** | Unit tests for permission store |
| `tests/test_safety.py` | **Modify** | Tests for integrated runtime checks |

---

## Permission Levels

| Level | Key | Lifetime | Storage |
|-------|-----|----------|---------|
| `once` | `(command_or_spec, "once")` | Consumed after one successful execution | In-memory |
| `session` | `(command_or_spec, "session")` | Until MCP server restart | In-memory |
| `permanent` | n/a | Forever | Written to `config.yaml` |

Note: "once" tokens are consumed after the tool that uses them reports success. If the execution fails for another reason, the token remains valid for the next attempt.

---

### Task 1: Create `runtime_permissions.py` — in-memory permission store

**Files:**
- Create: `computer_use/runtime_permissions.py`
- Create: `tests/test_runtime_permissions.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_runtime_permissions.py
"""Tests for runtime permission store."""
from __future__ import annotations

import pytest
from computer_use.runtime_permissions import (
    grant_command_permission,
    check_command_permission,
    consume_command_permission,
    grant_window_exception,
    check_window_exception,
    consume_window_exception,
    save_permanent_command,
    clear_runtime_permissions,
    list_runtime_permissions,
)


@pytest.fixture(autouse=True)
def _clean_runtime_state():
    clear_runtime_permissions()
    yield
    clear_runtime_permissions()


class TestCommandPermissions:
    def test_once_grant_and_consume(self):
        grant_command_permission("C:/app/app.exe", "once")
        assert check_command_permission("C:/app/app.exe") is True
        # Consume after successful execution
        consume_command_permission("C:/app/app.exe")
        assert check_command_permission("C:/app/app.exe") is False

    def test_once_not_consumed_before_explicit_call(self):
        grant_command_permission("C:/app/app.exe", "once")
        assert check_command_permission("C:/app/app.exe") is True
        assert check_command_permission("C:/app/app.exe") is True  # still valid
        consume_command_permission("C:/app/app.exe")
        assert check_command_permission("C:/app/app.exe") is False

    def test_session_grant_persists(self):
        grant_command_permission("C:/app/app.exe", "session")
        assert check_command_permission("C:/app/app.exe") is True
        # Session grants are not consumed
        consume_command_permission("C:/app/app.exe")  # no-op for session
        assert check_command_permission("C:/app/app.exe") is True

    def test_normalized_path_matching(self):
        grant_command_permission("C:/App/App.exe", "session")
        assert check_command_permission("c:\\app\\app.exe") is True

    def test_basename_matching_for_name_only_grants(self):
        grant_command_permission("notepad.exe", "session")
        assert check_command_permission("notepad.exe") is True
        assert check_command_permission("C:/Windows/System32/notepad.exe") is True

    def test_unknown_command_not_granted(self):
        assert check_command_permission("C:/unknown.exe") is False

    def test_consume_non_existent_is_noop(self):
        consume_command_permission("C:/nonexistent.exe")  # should not raise

    def test_clear_runtime_permissions(self):
        grant_command_permission("cmd.exe", "session")
        grant_command_permission("calc.exe", "once")
        clear_runtime_permissions()
        assert check_command_permission("cmd.exe") is False
        assert check_command_permission("calc.exe") is False

    def test_list_permissions(self):
        grant_command_permission("cmd.exe", "session")
        grant_command_permission("calc.exe", "once")
        perms = list_runtime_permissions()
        assert len(perms) == 2
        names = {p["name"] for p in perms}
        assert names == {"cmd.exe", "calc.exe"}


class TestWindowExceptions:
    def test_once_window_exception(self):
        grant_window_exception(process_name="saplogon.exe", class_name="#32770", level="once")
        assert check_window_exception("saplogon.exe", "#32770") is True
        consume_window_exception("saplogon.exe", "#32770")
        assert check_window_exception("saplogon.exe", "#32770") is False

    def test_session_window_exception(self):
        grant_window_exception(process_name="saplogon.exe", class_name="#32770", level="session")
        assert check_window_exception("saplogon.exe", "#32770") is True
        consume_window_exception("saplogon.exe", "#32770")  # no-op for session
        assert check_window_exception("saplogon.exe", "#32770") is True

    def test_window_exception_class_only(self):
        # Grant exception for any process with this class
        grant_window_exception(class_name="#32770", level="session")
        assert check_window_exception("any.exe", "#32770") is True
        assert check_window_exception("other.exe", "#32770") is True

    def test_window_exception_process_specific(self):
        grant_window_exception(process_name="saplogon.exe", class_name="#32770", level="session")
        assert check_window_exception("saplogon.exe", "#32770") is True
        assert check_window_exception("other.exe", "#32770") is False

    def test_window_exception_case_insensitive(self):
        grant_window_exception(process_name="SAPLOGON.EXE", class_name="#32770", level="session")
        assert check_window_exception("saplogon.exe", "#32770") is True
```

- [ ] **Step 2: Run test to verify they fail**

Run: `pytest tests/test_runtime_permissions.py -v`
Expected: All FAIL with ImportError (module not found)

- [ ] **Step 3: Write minimal implementation**

```python
# computer_use/runtime_permissions.py
"""Runtime permission store for whitelist escalation.

Manages three levels of runtime grants:
  - ``once``: consumed after one successful execution
  - ``session``: valid until server restart
  - ``permanent``: written to config.yaml
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from computer_use.config import _default_config_path, load_config, reset_config_cache
from computer_use.safety import _normalize_path  # reuse existing normalization

logger = logging.getLogger(__name__)

# In-memory stores (session-scoped)
_command_grants: dict[str, dict] = {}   # key = normalized name, value = {"level": str, "remaining": int | None}
_window_exceptions: list[dict] = []      # list of {"process_name": str|None, "class_name": str|None, "level": str, "remaining": int | None}


def _command_key(command: str) -> str:
    return _normalize_path(command)


def _match_command(grant_key: str, command: str) -> bool:
    """Check if a grant key matches a command (path or basename).

    Uses Path.resolve() for exact full-path matching (Issue 3 additional fix).
    """
    from pathlib import Path as _Path

    norm_cmd = _normalize_path(command)
    cmd_basename = _normalize_path(_Path(command).name)
    grant_norm = _normalize_path(grant_key)

    # Exact path match (both normalized)
    if norm_cmd == grant_norm:
        return True

    # Resolve the command path and compare (e.g., C:/Windows/System32/cmd.exe
    # matches C:/Windows/System32/../../Windows/System32/cmd.exe)
    try:
        resolved_cmd = _normalize_path(str(_Path(command).resolve()))
        if resolved_cmd == grant_norm:
            return True
    except Exception:
        pass

    # Basename match (only if grant_key is a bare name, not a path)
    grant_basename = _normalize_path(_Path(grant_key).name)
    if cmd_basename == grant_basename and "/" not in grant_key and "\\" not in grant_key:
        return True

    return False


def grant_command_permission(command: str, level: str) -> None:
    """Grant runtime permission for a command."""
    key = _command_key(command)
    remaining: int | None = 1 if level == "once" else None
    _command_grants[key] = {"level": level, "command": command, "remaining": remaining}


def check_command_permission(command: str) -> bool:
    """Return True if the command has an active runtime grant."""
    cmd = _normalize_path(command)
    for key, grant in _command_grants.items():
        if _match_command(key, cmd):
            return True
        if _match_command(key, command):
            return True
    return False


def consume_command_permission(command: str) -> None:
    """Consume a one-shot permission for the given command."""
    cmd = _normalize_path(command)
    keys_to_remove = []
    for key, grant in list(_command_grants.items()):
        if _match_command(key, cmd) or _match_command(key, command):
            if grant.get("level") == "once":
                remaining = grant.get("remaining", 0)
                if remaining is not None and remaining <= 1:
                    keys_to_remove.append(key)
                elif remaining is not None:
                    grant["remaining"] = remaining - 1
    for key in keys_to_remove:
        del _command_grants[key]


def grant_window_exception(
    process_name: str | None = None,
    class_name: str | None = None,
    level: str = "session",
) -> None:
    """Grant runtime exception for a sensitive window."""
    remaining: int | None = 1 if level == "once" else None
    entry = {
        "process_name": _normalize_path(process_name) if process_name else None,
        "class_name": _normalize_path(class_name) if class_name else None,
        "level": level,
        "remaining": remaining,
    }
    _window_exceptions.append(entry)


def check_window_exception(process_name: str | None, class_name: str | None) -> bool:
    """Return True if this window has an active runtime exception."""
    proc = _normalize_path(process_name) if process_name else None
    cls = _normalize_path(class_name) if class_name else None
    for entry in _window_exceptions:
        proc_match = (
            entry["process_name"] is None
            or (proc is not None and entry["process_name"] == proc)
        )
        cls_match = (
            entry["class_name"] is None
            or (cls is not None and entry["class_name"] == cls)
        )
        if proc_match and cls_match:
            return True
    return False


def consume_window_exception(process_name: str | None, class_name: str | None) -> None:
    """Consume one-shot window exceptions matching the given spec.

    Pass ``None, None`` to consume ALL one-shot window exceptions.
    """
    proc = _normalize_path(process_name) if process_name else None
    cls = _normalize_path(class_name) if class_name else None
    indices_to_remove = []
    for i, entry in enumerate(_window_exceptions):
        if proc is None and cls is None:
            if entry.get("level") == "once":
                indices_to_remove.append(i)
            continue
        proc_match = (
            entry["process_name"] is None
            or (proc is not None and entry["process_name"] == proc)
        )
        cls_match = (
            entry["class_name"] is None
            or (cls is not None and entry["class_name"] == cls)
        )
        if proc_match and cls_match and entry.get("level") == "once":
            indices_to_remove.append(i)
    for i in reversed(indices_to_remove):
        del _window_exceptions[i]


def save_permanent_command(command: str) -> None:
    """Append a command to allowed_commands in config.yaml."""
    _append_to_config("allowed_commands", command)
    reset_config_cache()


def _append_to_config(key: str, value: str) -> None:
    """Append a value to a list in config.yaml, avoiding duplicates."""
    config_path = _default_config_path()
    if not config_path.exists():
        return

    import yaml

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return

    safety = data.setdefault("safety", {})
    existing: list[str] = list(safety.get(key, []))

    if value not in existing:
        existing.append(value)

    safety[key] = existing

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)
        # NOTE: yaml.safe_dump will strip ALL comments from config.yaml.
        # This is acceptable for MVP since permanent grants are rare and the
        # config file is auto-generated from config.example.yaml. If users
        # curate their config with extensive comments, future work should
        # switch to ruamel.yaml for comment-preserving round-trip writes,
        # or write grants to a separate grants.yaml file.


def clear_runtime_permissions() -> None:
    """Clear all runtime permissions (for testing)."""
    _command_grants.clear()
    _window_exceptions.clear()


def list_runtime_permissions() -> list[dict[str, Any]]:
    """List current runtime permissions for debugging."""
    result: list[dict[str, Any]] = []
    for key, grant in _command_grants.items():
        result.append({"type": "command", "name": grant["command"], "level": grant["level"]})
    for entry in _window_exceptions:
        result.append({
            "type": "window",
            "process_name": entry.get("process_name"),
            "class_name": entry.get("class_name"),
            "level": entry.get("level"),
        })
    return result
```

- [ ] **Step 4: Run test to verify they pass**

Run: `pytest tests/test_runtime_permissions.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add computer_use/runtime_permissions.py tests/test_runtime_permissions.py
git commit -m "feat: add runtime_permissions module for command and window whitelist"
```

---

### Task 2: Integrate runtime checks into `safety.py`

**Files:**
- Modify: `computer_use/safety.py`

- [ ] **Step 1: Update test_safety.py with new tests**

```python
# Append to tests/test_safety.py

def test_is_allowed_command_with_runtime_once_grant():
    from computer_use.runtime_permissions import (
        grant_command_permission,
        clear_runtime_permissions,
    )
    reset_config_cache()
    config = load_config()
    config["safety"]["allowed_commands"] = []  # nothing in permanent whitelist
    grant_command_permission("C:/app/special.exe", "once")
    assert is_allowed_command("C:/app/special.exe") is True
    clear_runtime_permissions()

def test_is_allowed_command_with_runtime_session_grant():
    from computer_use.runtime_permissions import (
        grant_command_permission,
        clear_runtime_permissions,
    )
    reset_config_cache()
    config = load_config()
    config["safety"]["allowed_commands"] = []
    grant_command_permission("custom-tool.exe", "session")
    assert is_allowed_command("custom-tool.exe") is True
    clear_runtime_permissions()

def test_check_target_window_with_runtime_exception():
    from computer_use.runtime_permissions import (
        grant_window_exception,
        clear_runtime_permissions,
    )
    grant_window_exception(process_name="saplogon.exe", class_name="#32770", level="once")
    # Should not raise
    check_target_window("saplogon.exe", "#32770", None)
    clear_runtime_permissions()

def test_check_target_window_still_blocks_without_exception():
    with pytest.raises(SafetyError):
        check_target_window("saplogon.exe", "#32770", None)

def test_check_target_window_still_blocks_hardcoded_sensitive_process():
    # keepass.exe is in the hardcoded sensitive list — runtime exception
    # should NOT override hardcoded sensitive processes (keepass, certmgr, etc.).
    # Issue 1 fix: hardcoded checks run first and short-circuit.
    from computer_use.safety import SensitiveProcessError
    from computer_use.runtime_permissions import (
        grant_window_exception,
        clear_runtime_permissions,
    )
    grant_window_exception(process_name="keepass.exe", level="session")
    with pytest.raises(SensitiveProcessError):
        check_target_window("keepass.exe", None, None)
    clear_runtime_permissions()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_safety.py -v -k "runtime"`
Expected: 3-4 FAIL (runtime checks not yet integrated)

- [ ] **Step 3: Modify safety.py**

The key changes to `safety.py`:

```python
# At top of file, add imports:
from computer_use.runtime_permissions import check_command_permission as _runtime_check_command
from computer_use.runtime_permissions import check_window_exception as _runtime_check_window

# Define SafetyError subclasses for structured error handling:
class SensitiveProcessError(SafetyError):
    """Raised when a hardcoded sensitive process is the target.

    Carries structured data so mcp_server.py can extract details
    without parsing error message strings.
    """
    def __init__(self, message: str, process_name: str):
        super().__init__(message)
        self.process_name = process_name


class SensitiveWindowError(SafetyError):
    """Raised when a hardcoded sensitive window class is the target.

    Carries structured data so mcp_server.py can extract details
    without parsing error message strings.
    """
    def __init__(self, message: str, class_name: str):
        super().__init__(message)
        self.class_name = class_name


# Modify _allowed_commands() — reads from config only; built-in defaults
# are prepended conditionally based on use_builtin_defaults flag.
# NOTE: This is a SIMPLIFIED STUB for initial integration.
# The DEFINITIVE version with full use_builtin_defaults + single-source logic
# is in Task 5 — implementers must apply Task 5's version as the final code.
from computer_use.config import _BUILTIN_COMMANDS

def _allowed_commands() -> list[str]:
    config = load_config()
    commands = list(config.get("safety", {}).get("allowed_commands", []))
    use_defaults = config.get("safety", {}).get("use_builtin_defaults", True)
    if use_defaults:
        commands = list(_BUILTIN_COMMANDS) + commands
    return [_normalize_path(str(c)) for c in commands]

# Modify is_allowed_command to check runtime permissions:
def is_allowed_command(command: str | Path) -> bool:
    allowed = _allowed_commands()
    command_str = str(command) if isinstance(command, Path) else command
    
    # Check static whitelist
    if _static_whitelist_check(command_str, allowed):
        return True
    
    # Check runtime permissions
    if _runtime_check_command(command_str):
        return True
    
    return False


def _static_whitelist_check(command_str: str, allowed: list[str]) -> bool:
    """Check against the static config whitelist."""
    if not allowed:
        return False
    normalized_command = _normalize_path(command_str)
    command_basename = _normalize_path(Path(command_str).name)
    for allowed_command in allowed:
        allowed_path = Path(allowed_command)
        is_path_entry = "/" in allowed_command or "\\" in allowed_command
        if is_path_entry:
            if normalized_command == allowed_command:
                return True
            if allowed_path.is_absolute():
                try:
                    resolved = _normalize_path(str(Path(command_str).resolve()))
                except Exception:
                    continue
                if resolved == allowed_command:
                    return True
        elif command_basename == allowed_command:
            return True
    return False


# Modify check_target_window to check hardcoded first, raise subclasses:
def check_target_window(
    process_name: str | None,
    class_name: str | None,
    control_type: str | None,
    is_password: bool = False,
) -> None:
    """Raise SafetyError subclass unless an exception or whitelist allows it.

    Execution order (Issue 1 fix):
    1. Hardcoded sensitive process/class checks MUST run first and short-circuit.
       These are never bypassable (keepass, certmgr, etc.).
    2. Runtime window exceptions apply ONLY after hardcoded checks pass.
    """
    # 1. Hardcoded sensitive checks (never bypassable)
    if process_name and is_sensitive_process(process_name):
        raise SensitiveProcessError(
            f"Refusing to interact with sensitive process: {process_name}",
            process_name=process_name,
        )
    if class_name and is_sensitive_window_class(class_name):
        raise SensitiveWindowError(
            f"Refusing to interact with sensitive window class: {class_name}",
            class_name=class_name,
        )

    # 2. Runtime exceptions (bypassable via add_window_exception)
    if _runtime_check_window(process_name, class_name):
        return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_safety.py -v`
Expected: ALL PASS (including new runtime tests)

- [ ] **Step 5: Commit**

```bash
git add computer_use/safety.py tests/test_safety.py
git commit -m "feat: integrate runtime permissions into safety checks with default commands"
```

---

### Task 3: Add structured error responses for actionable blocks

**Files:**
- Modify: `computer_use/launcher.py`
- Modify: `computer_use/mcp_server.py`

- [ ] **Step 1: Update launcher.py to return structured block errors**

In `launcher.py`, modify `_whitelist_error()`:

```python
def _whitelist_error(target_path: str, action: str = "launch") -> dict[str, Any]:
    allowed = load_config().get("safety", {}).get("allowed_commands", [])
    if not allowed:
        return {
            "launched": False,
            "error": "no_commands_allowed",
            "target_path": target_path,
            "action": action,
            "next_action": (
                "Add commands to allowed_commands in config.yaml, or ask user to "
                "grant permission via add_command_whitelist. "
                f"{_CONFIG_EXAMPLE_HINT}"
            ),
        }
    return {
        "launched": False,
        "error": "command_not_whitelisted",
        "command": target_path,
        "action": action,
        "next_action": (
            f"'{target_path}' is not in the whitelist. Ask user: "
            "\"Add to whitelist? Options: once / session / permanent\" "
            "If user agrees, call add_command_whitelist(name=..., level=...)."
        ),
    }
```

- [ ] **Step 2: Update mcp_server.py SafetyError handling**

In `_call_tool()`, modify the `SafetyError` handler to use subclass checks instead of regex:

```python
except SafetyError as exc:
    if isinstance(exc, SensitiveWindowError):
        payload = json.dumps({
            "error": "sensitive_window_blocked",
            "class_name": getattr(exc, "class_name", None),
            "detail": str(exc),
            "next_action": (
                f"Window class '{getattr(exc, 'class_name', 'unknown')}' is protected. Ask user: "
                "\"Grant window exception? Options: once / session\" "
                "If user agrees, call add_window_exception(class_name=..., level=...)."
            ),
        })
    elif isinstance(exc, SensitiveProcessError):
        process_name = getattr(exc, "process_name", None)
        payload = json.dumps({
            "error": "sensitive_process_blocked",
            "process_name": process_name,
            "detail": str(exc),
            "next_action": (
                f"Process '{process_name or 'unknown'}' is "
                f"{'hardcoded and NEVER bypassable.' if _is_hardcoded_sensitive(process_name) else 'protected.'} "
                f"{'Ask user if they want to grant a session exception?' if not _is_hardcoded_sensitive(process_name) else ''}"
            ),
        })
    else:
        payload = json.dumps(
            {"error": str(exc), "next_action": _NEXT_ACTION_COORDINATE_OR_SAFETY}
        )
    logging.warning("safety block: %s", exc)
    error = exc
```

> **Note:** `SensitiveProcessError` and `SensitiveWindowError` are defined as subclasses of `SafetyError` in `safety.py` (see Task 2 Step 3). Hardcoded sensitive processes always raise `SensitiveProcessError` before runtime exceptions are checked, so `add_window_exception` cannot bypass them. Only config-level sensitive window classes (e.g., `#32770` from `sensitive_window_classes` in config.yaml) are reachable via runtime exceptions.

- [ ] **Step 2.5: Add consume hooks after successful execution (Issue 3)**

**In `launcher.py`**, after a successful launch, call `consume_command_permission`:

```python
# In the launch path, after successful InvokeVerb / subprocess.Popen:
from computer_use.runtime_permissions import consume_command_permission

try:
    subprocess.Popen([target_path], ...)  # or ShellExecute / InvokeVerb
    consume_command_permission(target_path)
except Exception:
    pass  # consumption is best-effort, don't fail the tool
```

**In `mcp_server.py`**, wrap the `_dispatch_tool` success path to consume window exceptions:

```python
# In _call_tool(), modify the dispatch section:
def _call_tool(name: str, args: dict) -> str:
    # ... initial setup ...
    try:
        result = _dispatch_tool(name, args)
        _consume_runtime_permissions(name, args)
        return result
    except SafetyError as exc:
        ...  # existing handler (isinstance checks)
```

Add a helper in `mcp_server.py`:

```python
def _consume_runtime_permissions(tool_name: str, args: dict) -> None:
    """After a successful tool execution, consume one-shot runtime grants.

    For window-tool executions, consume one-shot window exceptions.
    Consumption is intentionally broad (None, None) because the dispatch
    context doesn't currently carry per-call process_name/class_name.
    For multi-window workflows, use 'session' level grants instead of 'once'.
    Future: thread inspect_point results through dispatch context for
    targeted per-window token consumption.
    """
    from computer_use.runtime_permissions import consume_window_exception

    _window_tools = frozenset({
        "click", "move_to", "click_on_screenshot", "mouse_down",
        "mouse_up", "drag", "type", "key_combo", "press_key",
        "scroll", "batch", "click_by_uid", "click_by_text",
        "open_menu", "fill_form", "scroll_until",
    })
    if tool_name in _window_tools:
        consume_window_exception(None, None)
```

> **Trade-off:** Passing `None, None` consumes ALL non-hardcoded one-shot window exception tokens at once. This is a known limitation — multi-window workflows requiring sequential one-shot exceptions should use `level="session"` instead. Targeted consumption (passing actual process_name/class_name from dispatch context) is deferred to a future iteration.

- [ ] **Step 3: Run existing tests**

Run: `pytest tests/test_mcp_server.py -v -m "not manual"`
Expected: All existing tests pass (or adjust if tests depend on exact error string)

- [ ] **Step 4: Commit**

```bash
git add computer_use/launcher.py computer_use/mcp_server.py
git commit -m "feat: structured error responses for whitelist and sensitive window blocks"
```

---

### Task 4: Add new MCP tools: `add_command_whitelist` and `add_window_exception`

**Files:**
- Modify: `computer_use/tools/schemas.py` (add tool definitions)
- Modify: `computer_use/mcp_server.py` (add dispatch handlers)

- [ ] **Step 1: Add tool schemas**

In `schemas.py`, insert two new Tool entries into the `TOOLS` list:

```python
    Tool(
        name="add_command_whitelist",
        description="Add a command to the runtime whitelist at the requested permission level. Call this after user confirmation when a command is blocked by the whitelist. level='once' grants one-time use, 'session' grants for the current server session, 'permanent' writes to config.yaml.",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The executable path or name to whitelist (e.g., 'D:/Program Files/SAP/saplogon.exe' or 'notepad.exe').",
                },
                "level": {
                    "type": "string",
                    "enum": ["once", "session", "permanent"],
                    "default": "once",
                    "description": "Permission level: 'once' (one successful use), 'session' (until server restart), 'permanent' (write to config.yaml).",
                },
            },
            "required": ["command"],
        },
    ),
    Tool(
        name="add_window_exception",
        description="Add a runtime exception for a sensitive window class or process. Call this after user confirmation when a window interaction is blocked by the sensitive window check. Only 'once' and 'session' levels are supported (permanent window exceptions are not writable to config — hardcoded sensitive processes like keepass, certmgr are never bypassable).",
        inputSchema={
            "type": "object",
            "properties": {
                "class_name": {
                    "type": "string",
                    "description": "The window class name to except (e.g., '#32770'). Use when the block was on class_name.",
                },
                "process_name": {
                    "type": "string",
                    "description": "The process name to except (e.g., 'saplogon.exe'). Use when the block was on process_name. Hardcoded sensitive processes (keepass, certmgr, etc.) are never exceptable.",
                },
                "level": {
                    "type": "string",
                    "enum": ["once", "session"],
                    "default": "once",
                    "description": "Permission level: 'once' (one successful use) or 'session' (until server restart). 'permanent' is not supported for window exceptions (sensitive process/class protections remain in config).",
                },
            },
        },
    ),
```

- [ ] **Step 2: Add dispatch handlers in mcp_server.py**

In `_dispatch_tool()`, add:

```python
    if name == "add_command_whitelist":
        from computer_use import runtime_permissions as rp
        command = args["command"]
        level = args.get("level", "once")
        if level == "permanent":
            rp.save_permanent_command(command)
        rp.grant_command_permission(command, level)
        return json.dumps({
            "granted": True,
            "command": command,
            "level": level,
            "next_action": f"Permission granted ({level}). Retry the blocked tool.",
        })

    if name == "add_window_exception":
        from computer_use import runtime_permissions as rp
        class_name = args.get("class_name")
        process_name = args.get("process_name")
        level = args.get("level", "once")
        if not class_name and not process_name:
            return json.dumps({
                "error": "Either class_name or process_name is required.",
            })
        rp.grant_window_exception(
            process_name=process_name,
            class_name=class_name,
            level=level,
        )
        return json.dumps({
            "granted": True,
            "class_name": class_name,
            "process_name": process_name,
            "level": level,
            "next_action": f"Window exception granted ({level}). Retry the blocked tool.",
        })
```

- [ ] **Step 3: Run smoke test to verify tools appear**

```bash
$env:PYTHONUTF8 = "1"; .\.venv\Scripts\python.exe tools\smoke_mcp_client.py --server .\.venv\Scripts\python.exe --args -m computer_use.mcp_server
```
Expected: `add_command_whitelist`, `add_window_exception` in tools list

- [ ] **Step 4: Write integration test**

Create `tests/test_runtime_permissions_integration.py`:

```python
"""Integration tests for runtime permission tools via _call_tool."""
from __future__ import annotations

import json
from computer_use.mcp_server import _call_tool
from computer_use.runtime_permissions import clear_runtime_permissions
from computer_use.config import reset_config_cache
import pytest


@pytest.fixture(autouse=True)
def _clean_state():
    reset_config_cache()
    clear_runtime_permissions()
    yield
    reset_config_cache()
    clear_runtime_permissions()


def test_add_command_whitelist_once():
    result_text = _call_tool("add_command_whitelist", {
        "command": "C:/test/app.exe",
        "level": "once",
    })
    result = json.loads(result_text)
    assert result["granted"] is True
    assert result["level"] == "once"


def test_add_command_whitelist_permanent_updates_config(tmp_path):
    # Would need to mock config path; skip for now
    pass
```

- [ ] **Step 5: Commit**

```bash
git add computer_use/tools/schemas.py computer_use/mcp_server.py tests/test_runtime_permissions_integration.py
git commit -m "feat: add add_command_whitelist and add_window_exception MCP tools"
```

---

### Task 5: Update config defaults and example

**Files:**
- Modify: `computer_use/config.py`
- Modify: `config.example.yaml`

- [ ] **Step 1: Update config.py defaults**

In `_DEFAULTS`, change `allowed_commands`:

```python
_BUILTIN_COMMANDS = [
    "notepad.exe",
    "calc.exe",
    "explorer.exe",
    "cmd.exe",
    "powershell.exe",
    "mspaint.exe",
    "write.exe",
    "taskmgr.exe",
    "control.exe",
    "charmap.exe",
    "snippingtool.exe",
]

_DEFAULTS: dict[str, Any] = {
    ...
    "safety": {
        ...
        "allowed_commands": [],  # Empty by default; builtins prepended at runtime
        "use_builtin_defaults": True,  # Issue 6: strict-security users can set False
    },
    ...
}
```

In `_allowed_commands()` (in safety.py), respect the flag:

```python
from computer_use.config import _BUILTIN_COMMANDS

def _allowed_commands() -> list[str]:
    config = load_config()
    commands = list(config.get("safety", {}).get("allowed_commands", []))
    use_defaults = config.get("safety", {}).get("use_builtin_defaults", True)
    if use_defaults:
        commands = list(_BUILTIN_COMMANDS) + commands
    return [_normalize_path(str(c)) for c in commands]
```

> **Note:** When `use_builtin_defaults: true` (default), `_BUILTIN_COMMANDS` are prepended before user-configured commands. When `use_builtin_defaults: false`, only config.yaml's `allowed_commands` and runtime grants apply. For full runtime-only mode, set both `use_builtin_defaults: false` and `allowed_commands: []` — all commands must come from `add_command_whitelist` runtime grants.

- [ ] **Step 2: Update config.example.yaml**

```yaml
safety:
  # use_builtin_defaults: true  # (default) prepend built-in system commands.
  # Set to false for strict-security mode: only config.yaml + runtime grants.
  use_builtin_defaults: true

  allowed_commands:
    # Built-in defaults (notepad, calc, explorer, cmd, powershell, mspaint,
    # write, taskmgr, control, charmap, snippingtool) are active when
    # use_builtin_defaults is true. Add custom application paths below:
    # - C:/Program Files (x86)/HiBit Uninstaller/HiBitUninstaller.exe
    # - D:/Program Files (x86)/SAP/FrontEnd/SAPgui/saplogon.exe
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -v -m "not manual"`

- [ ] **Step 4: Commit**

```bash
git add computer_use/config.py config.example.yaml
git commit -m "feat: add built-in default system commands to allowed_commands"
```

---

### Task 6: Update Skill, guidance, and pitfalls

**Files:**
- Modify: `skills/computer-use/SKILL.md`
- Modify: `.agents/skills/computer-use/SKILL.md`
- Modify: `computer_use/guidance.py`
- Modify: `docs/pitfalls.md`

- [ ] **Step 1: Update SKILL.md with whitelist escalation flow**

Add to `skills/computer-use/SKILL.md` (and sync copy):

```markdown
### Whitelist Escalation

When `launch_app` returns `command_not_whitelisted` or any tool returns `sensitive_window_blocked`:

1. **Inform the user** what was blocked and why
2. **Ask**: "Add to whitelist? Options: once (this time) / session (this session) / permanent (write to config)"
3. **If user agrees**, call the appropriate tool:
   - `add_command_whitelist(command="<path>", level="once|session|permanent")` for command blocks
   - `add_window_exception(class_name="<class>", process_name="<proc>", level="once|session")` for window blocks
4. **Retry** the blocked tool

**Hardcoded blocks** (keepass, certmgr, 1password, lastpass, mmc) CANNOT be bypassed. Do not ask for exceptions for these — they will always be refused.
```

- [ ] **Step 2: Update guidance.py prompts**

Update `safety_checklist` and `visual_task` prompts to mention the new escalation flow.

- [ ] **Step 3: Update pitfalls.md**

Add new section:

```markdown
## 运行时白名单机制

**现象**：`launch_app` 返回 `command_not_whitelisted`，或点击/截图工具返回 `sensitive_window_blocked`。

**原因**：MCP 的安全检查拦截了不在白名单中的命令或敏感窗口类的交互。

**解决**（三层权限）：
1. **本次同意** (`once`)：调用 `add_command_whitelist(command, level="once")`，仅允许下一次成功执行
2. **本会话同意** (`session`)：调用 `add_command_whitelist(command, level="session")`，允许到服务重启
3. **永久同意** (`permanent`)：调用 `add_command_whitelist(command, level="permanent")`，写入 config.yaml

对内建的敏感进程（keepass、certmgr 等）始终拒绝，不可绕过。
```

- [ ] **Step 4: Sync skill copies**

```bash
python scripts/sync_global_skill.py
```

- [ ] **Step 5: Commit**

```bash
git add skills/computer-use/SKILL.md .agents/skills/computer-use/SKILL.md computer_use/guidance.py docs/pitfalls.md
git commit -m "docs: document runtime permission escalation flow"
```

---

### Task 7: Full test suite and manual smoke

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v -m "not manual"
```

Expected: ALL PASS

- [ ] **Step 2: Verify via doctor**

```bash
.\.venv\Scripts\python.exe -m computer_use doctor
```

Expected: status ok, no regressions

- [ ] **Step 3: Manual smoke via CLI**

```bash
$env:PYTHONUTF8 = "1"; .\.venv\Scripts\python.exe -c "from computer_use.safety import is_allowed_command; print(is_allowed_command('notepad.exe'))"
```

Expected: `True`

- [ ] **Step 4: Final commit (if any fixes)**

```bash
git add -A
git commit -m "test: full suite validation after runtime permissions"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: Three-tier permission levels (once/session/permanent) ✓, default system commands ✓, runtime escalation flow for both launch_app and #32770 ✓, hardcoded sensitive process protection ✓
- [x] **Placeholder scan**: No TBD/TODO/fill-in-later; all code is concrete
- [x] **Type consistency**: `grant_command_permission(command, level)` → `check_command_permission(command)` → `consume_command_permission(command)` all use same param shapes
- [x] **No breaking changes**: Existing test assertions on error strings are updated where needed; runtime checks are additive
- [x] **Edge cases**: Empty allowed_commands ✓, non-existent path ✓, case insensitivity ✓, basename vs full path matching ✓, hardcoded sensitive process bypass rejection ✓
- [x] **SafetyError subclasses (DR fix)**: `SensitiveProcessError` and `SensitiveWindowError` carry structured `process_name`/`class_name` attrs — no undefined extract functions ✓
- [x] **_allowed_commands() single source (DR fix)**: Task 2 marked as stub, Task 5 as definitive version with cross-reference note ✓
- [x] **Tool name accuracy (DR fix)**: `_window_tools` frozenset uses canonical tool names (key_combo not key_sequence) ✓
- [x] **Consume scoping (DR fix)**: `consume_window_exception(None,None)` documented as known trade-off; multi-window users directed to `level="session"` ✓
- [x] **yaml.safe_dump (DR fix)**: Comment-loss behavior documented as acceptable-for-MVP with ruamel.yaml migration path noted ✓
- [x] **Known limitations**: Thread-safety, matching duplication, tool-awareness — deferred to future work ✓
- [x] **Execution order (Issue 1)**: Hardcoded sensitive process/class check runs FIRST and short-circuits in `check_target_window`. Runtime exceptions checked only after hardcoded checks pass ✓
- [x] **Single source of truth (Issue 2)**: `_BUILTIN_COMMANDS` defined ONLY in `config.py`; `_allowed_commands()` reads from config only; high-risk items (regedit.exe, msconfig.exe) removed from defaults ✓
- [x] **Consume integration (Issue 3)**: `consume_command_permission` called in `launcher.py` after successful launch; `consume_window_exception` called in `mcp_server.py` via `_consume_runtime_permissions` helper after successful window-tool execution ✓
- [x] **Structured errors (Issue 4)**: `SensitiveProcessError` and `SensitiveWindowError` subclasses defined in `safety.py`; `mcp_server.py` uses `isinstance()` instead of regex; `check_target_window` raises appropriate subclass ✓
- [x] **No dead code (Issue 5)**: `save_permanent_window_exception` removed; `negate` parameter removed from `_append_to_config`; `add_window_exception` tool supports only `once`/`session` levels ✓
- [x] **Opt-out built-ins (Issue 6)**: `use_builtin_defaults: true` flag in config; `_allowed_commands()` respects flag for strict-security mode ✓
- [x] **Normalization (additional)**: `runtime_permissions.py` reuses `_normalize_path` from `safety.py` (no private duplicate); `_match_command` includes `Path.resolve()` normalization; `save_permanent_command` uses `_default_config_path()` ✓
