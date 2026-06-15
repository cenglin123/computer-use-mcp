"""Safety enforcement for Computer Use actions.

All enforcement here is deterministic (hardcoded rules), not AI-based.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from computer_use.config import load_config

# Dangerous operations are never executed by this server.
_DANGEROUS_COMMAND_PATTERNS = [
    re.compile(r"\brm\s+(-rf?|/f\s+/s\s+/q)", re.IGNORECASE),
    re.compile(r"\bdel\s+(/f\s+/s\s+/q|/s\s+/q)", re.IGNORECASE),
    re.compile(r"\bformat\b", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breg\s+(add|delete|edit)\b", re.IGNORECASE),
    re.compile(r"\bcd\.\s*\\", re.IGNORECASE),
]

# Sensitive application process/window class names. Interactions with these
# are blocked unless explicitly allowed by the user (out of scope for MVP).
_SENSITIVE_PROCESSES = {
    "keepass",
    "1password",
    "lastpass",
    "certmgr",
    "certlm",
    "mmc",
}

_SENSITIVE_WINDOW_CLASSES = {
    "#32770",  # Windows dialog; used by many sensitive apps
}


def _sensitive_processes() -> set[str]:
    config = load_config()
    extra = config.get("safety", {}).get("sensitive_processes", [])
    return _SENSITIVE_PROCESSES | {p.lower() for p in extra}


def _sensitive_window_classes() -> set[str]:
    config = load_config()
    extra = config.get("safety", {}).get("sensitive_window_classes", [])
    return _SENSITIVE_WINDOW_CLASSES | {c.lower() for c in extra}


def _allowed_commands() -> list[str]:
    """Return configured allowed commands as normalized strings."""
    config = load_config()
    commands = config.get("safety", {}).get("allowed_commands", [])
    return [_normalize_path(str(command)) for command in commands]


def _normalize_path(value: str) -> str:
    """Normalize a path string for comparison (lowercase, forward slashes)."""
    return value.lower().replace("\\", "/")


def is_allowed_command(command: str | Path) -> bool:
    """Return True if ``command`` is in the allowed-commands whitelist.

    The whitelist contains exact command names and/or absolute paths. If the
    configuration key is missing, an empty list is used and everything is
    blocked.
    """
    allowed = _allowed_commands()
    if not allowed:
        return False

    if isinstance(command, Path):
        command_str = str(command)
    else:
        command_str = command

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
                except Exception:  # pragma: no cover
                    continue
                if resolved == allowed_command:
                    return True
        elif command_basename == allowed_command:
            return True

    return False


def contains_shell_metacharacters(text: str) -> bool:
    """Return True if ``text`` contains shell metacharacters used for injection.

    Metacharacters include command connectors, redirections, variable/expansion
    markers, escaping characters, and newline separators.
    """
    metachar_pattern = re.compile(
        r"[&|;<>^`]|"          # connectors, redirection, escape, backtick
        r"%[^%]*%|"            # Windows environment expansion %VAR%
        r"\$\([^)]*\)|"        # command substitution $()
        r"[\r\n]",             # newline characters
    )
    return bool(metachar_pattern.search(text))


def is_dangerous_text(text: str) -> bool:
    """Return True if the typed text looks like a dangerous shell command."""
    for pattern in _DANGEROUS_COMMAND_PATTERNS:
        if pattern.search(text):
            return True
    return False


def is_path_deletion(text: str) -> bool:
    """Block any text that attempts to delete a file system path."""
    lowered = text.lower().strip()
    if lowered.startswith(("del ", "rm ", "rmdir ", "rd ", "erase ")):
        return True
    return False


def validate_text_input(text: str) -> None:
    """Raise SafetyError if the text input is not allowed."""
    if is_dangerous_text(text):
        raise SafetyError(
            "Refusing to type text that matches dangerous command patterns."
        )
    if is_path_deletion(text):
        raise SafetyError("Refusing to type text that looks like a file deletion command.")


def validate_coordinate(
    x: int,
    y: int,
    width: int,
    height: int,
    monitors: list[dict[str, int]] | None = None,
) -> None:
    """Raise SafetyError unless input coordinates are on the primary screen.

    Input coordinates are intentionally restricted to non-negative physical
    pixels on the primary monitor. Screenshot and inspection APIs use separate
    monitor validation and may continue to cover the full virtual desktop.
    ``monitors`` follows mss ordering, where the first entry is primary.
    """
    if monitors:
        primary = monitors[0]
        primary_left = primary["left"]
        primary_top = primary["top"]
        primary_right = primary_left + primary["width"]
        primary_bottom = primary_top + primary["height"]
        if (
            x < 0
            or y < 0
            or x < primary_left
            or y < primary_top
            or x >= primary_right
            or y >= primary_bottom
        ):
            raise SafetyError(
                f"Coordinate ({x}, {y}) is outside the primary screen input bounds "
                f"({primary_left}, {primary_top})-({primary_right - 1}, {primary_bottom - 1})."
            )
        return

    if x < 0 or y < 0 or x >= width or y >= height:
        raise SafetyError(
            f"Coordinate ({x}, {y}) is outside the primary screen input bounds "
            f"({width}x{height})."
        )


def validate_monitor_index(index: int, monitor_count: int) -> None:
    """Raise SafetyError if the monitor index is invalid.

    Index 0 represents the entire virtual desktop. Indices 1..monitor_count
    represent individual monitors (mss 1-based convention).
    """
    if not isinstance(index, int):
        raise SafetyError(f"Monitor index must be an integer, got {type(index).__name__}.")
    if index < 0 or index > monitor_count:
        raise SafetyError(
            f"Monitor index {index} is out of range. "
            f"Valid indices are 0 (virtual desktop) or 1..{monitor_count}."
        )


def is_sensitive_process(proc_name: str) -> bool:
    return proc_name.lower().rsplit(".exe", 1)[0] in _sensitive_processes()


def is_sensitive_window_class(class_name: str | None) -> bool:
    if class_name is None:
        return False
    return class_name.lower() in _sensitive_window_classes()


def check_target_window(
    process_name: str | None,
    class_name: str | None,
    control_type: str | None,
    is_password: bool = False,
) -> None:
    """Raise SafetyError if the target process or window class is sensitive."""
    if process_name and is_sensitive_process(process_name):
        raise SafetyError(
            f"Refusing to interact with sensitive process: {process_name}"
        )
    if class_name and is_sensitive_window_class(class_name):
        raise SafetyError(
            f"Refusing to interact with sensitive window class: {class_name}"
        )


class SafetyError(Exception):
    """Raised when an action violates the safety policy."""

    pass
