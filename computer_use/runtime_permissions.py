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

    Uses Path.resolve() for exact full-path matching.
    """
    norm_cmd = _normalize_path(command)
    cmd_basename = _normalize_path(Path(command).name)
    grant_norm = _normalize_path(grant_key)

    # Exact path match (both normalized)
    if norm_cmd == grant_norm:
        return True

    # Resolve the command path and compare
    try:
        resolved_cmd = _normalize_path(str(Path(command).resolve()))
        if resolved_cmd == grant_norm:
            return True
    except Exception:
        pass

    # Basename match (only if grant_key is a bare name, not a path)
    grant_basename = _normalize_path(Path(grant_key).name)
    if cmd_basename == grant_basename and "/" not in grant_key and "\\" not in grant_key:
        return True

    return False


def grant_command_permission(command: str, level: str) -> None:
    """Grant runtime permission for a command.

    Args:
        command: The executable path or name.
        level: ``"once"``, ``"session"``, or ``"permanent"``.
    """
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
    """Grant runtime exception for a sensitive window.

    Args:
        process_name: Process name to except (e.g. ``"saplogon.exe"``).
        class_name: Window class to except (e.g. ``"#32770"``).
        level: ``"once"`` or ``"session"``.
    """
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
    """Append a value to a list in config.yaml, avoiding duplicates.

    NOTE: yaml.safe_dump will strip ALL comments from config.yaml.
    This is acceptable for MVP since permanent grants are rare.
    """
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
