"""Application launching via Windows Shell.Application and WScript.Shell.

This module is optional at runtime; if ``win32com`` is not available the
launch_app tool returns a clear error without crashing the server.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from computer_use.safety import (
    SafetyError,
    check_target_window,
    is_allowed_command,
)

logger = logging.getLogger(__name__)

# Windows CSIDL constants for special folders. These are passed to
# Shell.Application.Namespace(...) to enumerate Start Menu and Desktop.
_CSIDL_STARTMENU = 11
_CSIDL_COMMON_STARTMENU = 22
_CSIDL_DESKTOPDIRECTORY = 16
_CSIDL_COMMON_DESKTOPDIRECTORY = 25

_SHELL_FOLDERS = [
    _CSIDL_STARTMENU,
    _CSIDL_COMMON_STARTMENU,
    _CSIDL_DESKTOPDIRECTORY,
    _CSIDL_COMMON_DESKTOPDIRECTORY,
]

_BLOCKED_ERROR = "Target is in sensitive process list or not in allowed_commands whitelist"


def _get_shell_dispatch() -> Any | None:
    """Return a Dispatch object or None when win32com is unavailable."""
    try:
        import win32com.client

        return win32com.client.Dispatch("Shell.Application")
    except Exception as exc:  # pragma: no cover
        logger.debug("Shell.Application unavailable: %s", exc)
        return None


def _get_wscript_shell() -> Any | None:
    """Return a WScript.Shell Dispatch object or None when unavailable."""
    try:
        import win32com.client

        return win32com.client.Dispatch("WScript.Shell")
    except Exception as exc:  # pragma: no cover
        logger.debug("WScript.Shell unavailable: %s", exc)
        return None


def _collect_lnk_items(shell: Any) -> list[tuple[Any, str]]:
    """Collect all ``.lnk`` items from configured special folders.

    Returns a list of ``(Item, lnk_path)`` tuples.
    """
    items: list[tuple[Any, str]] = []
    for folder_id in _SHELL_FOLDERS:
        try:
            namespace = shell.Namespace(folder_id)
            if namespace is None:
                continue
            for item in namespace.Items():
                try:
                    path = str(item.Path)
                    if path.lower().endswith(".lnk"):
                        items.append((item, path))
                except Exception as exc:  # pragma: no cover
                    logger.debug("failed to read item path: %s", exc)
        except Exception as exc:  # pragma: no cover
            logger.debug("failed to enumerate folder %s: %s", folder_id, exc)
    return items


def _resolve_lnk_target(lnk_path: str, wscript: Any) -> str | None:
    """Resolve the target path of a ``.lnk`` shortcut file."""
    try:
        shortcut = wscript.CreateShortcut(lnk_path)
        target = getattr(shortcut, "TargetPath", None)
        if target:
            return str(target)
    except Exception as exc:  # pragma: no cover
        logger.debug("failed to resolve shortcut %s: %s", lnk_path, exc)
    return None


def _is_name_match(item_name: str, query: str, exact: bool) -> bool:
    """Case-insensitive comparison for exact or contains matching."""
    if exact:
        return item_name.lower() == query.lower()
    return query.lower() in item_name.lower()


def _process_name_from_path(target_path: str) -> str | None:
    """Return the executable filename from a target path, or None."""
    name = Path(target_path).name
    return name if name else None


def launch_app(name: str) -> dict[str, Any]:
    """Launch an application by its Start Menu/Desktop shortcut name.

    Matching is exact-first, then contains fallback. If multiple shortcuts
    match, a list of candidates is returned so the caller can disambiguate.
    """
    shell = _get_shell_dispatch()
    if shell is None:
        return {"launched": False, "error": "Shell automation unavailable"}

    wscript = _get_wscript_shell()
    if wscript is None:
        return {"launched": False, "error": "Shell automation unavailable"}

    items = _collect_lnk_items(shell)
    if not items:
        return {"launched": False, "error": f"No application named '{name}' found"}

    # Exact matches first.
    exact_matches: list[tuple[Any, str, str]] = []
    for item, lnk_path in items:
        try:
            item_name = str(item.Name)
        except Exception as exc:  # pragma: no cover
            logger.debug("failed to read item name: %s", exc)
            continue
        if _is_name_match(item_name, name, exact=True):
            target_path = _resolve_lnk_target(lnk_path, wscript)
            if target_path:
                exact_matches.append((item, item_name, target_path))

    if exact_matches:
        candidates = exact_matches
    else:
        # Fallback to contains matching.
        contains_matches: list[tuple[Any, str, str]] = []
        for item, lnk_path in items:
            try:
                item_name = str(item.Name)
            except Exception as exc:  # pragma: no cover
                logger.debug("failed to read item name: %s", exc)
                continue
            if _is_name_match(item_name, name, exact=False):
                target_path = _resolve_lnk_target(lnk_path, wscript)
                if target_path:
                    contains_matches.append((item, item_name, target_path))
        candidates = contains_matches

    if not candidates:
        return {"launched": False, "error": f"No application named '{name}' found"}

    if len(candidates) > 1:
        return {
            "launched": False,
            "matches": [
                {"name": item_name, "target_path": target_path}
                for _, item_name, target_path in candidates
            ],
        }

    item, item_name, target_path = candidates[0]

    # Security checks.
    if not is_allowed_command(target_path):
        return {"launched": False, "error": _BLOCKED_ERROR}

    process_name = _process_name_from_path(target_path)
    if process_name:
        try:
            check_target_window(process_name, None, None)
        except SafetyError:
            return {"launched": False, "error": _BLOCKED_ERROR}

    try:
        item.InvokeVerb("Open")
    except Exception as exc:  # pragma: no cover
        logger.exception("InvokeVerb failed for %s", target_path)
        return {"launched": False, "error": str(exc)}

    return {"launched": True, "name": item_name, "target_path": target_path}
