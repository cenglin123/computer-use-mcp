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


def _allowed_commands() -> set[str]:
    """Return the configured allowed command whitelist as lowercase strings.

    Each entry contributes both its full normalized value and its basename so
    that absolute-path whitelists also allow invocation by executable name.
    """
    config = load_config()
    commands = config.get("safety", {}).get("allowed_commands", [])
    normalized: set[str] = set()
    for cmd in commands:
        value = str(cmd) if isinstance(cmd, Path) else cmd
        normalized.add(_normalize_path(value))
        normalized.add(_normalize_path(Path(value).name))
    return normalized


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

    lowered = _normalize_path(command_str)
    basename = _normalize_path(Path(command_str).name)
    if lowered in allowed or basename in allowed:
        return True

    try:
        resolved = _normalize_path(str(Path(command_str).resolve()))
        if resolved in allowed:
            return True
    except Exception:  # pragma: no cover
        pass

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
    """Raise SafetyError if coordinates are outside the screen or in a gap.

    Coordinates must be within the virtual screen bounds
    [0, width-1] and [0, height-1]. If ``monitors`` is provided, the point
    must also fall inside at least one monitor (rejects virtual screen gaps).
    """
    if x < 0 or y < 0 or x >= width or y >= height:
        raise SafetyError(
            f"Coordinate ({x}, {y}) is outside virtual screen bounds ({width}x{height})."
        )

    if monitors is not None:
        for mon in monitors:
            if (
                mon["left"] <= x < mon["left"] + mon["width"]
                and mon["top"] <= y < mon["top"] + mon["height"]
            ):
                return
        raise SafetyError(
            f"Coordinate ({x}, {y}) falls in a virtual screen gap and is not on any monitor."
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
    """Raise SafetyError if the target window/control is sensitive."""
    if process_name and is_sensitive_process(process_name):
        raise SafetyError(
            f"Refusing to interact with sensitive process: {process_name}"
        )
    if class_name and is_sensitive_window_class(class_name):
        raise SafetyError(
            f"Refusing to interact with sensitive window class: {class_name}"
        )
    if is_password:
        raise SafetyError("Refusing to input text into a password control.")


class SafetyError(Exception):
    """Raised when an action violates the safety policy."""

    pass
