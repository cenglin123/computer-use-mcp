"""Composite GUI automation tools built from atomic primitives.

These tools wrap common multi-step patterns (open a menu, fill a form, scroll
until an item appears) into single MCP-callable functions. They are deterministic
and do not call any LLM. When a target cannot be located via UIA, they return a
structured ``ui_not_found`` error so the caller can fall back to screenshot-based
reasoning.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import pyautogui

from computer_use.core import click, get_coordinate_system, scroll, type_text
from computer_use.safety import check_target_window, validate_coordinate, validate_text_input
from computer_use.ui_automation import find_control, inspect_point

logger = logging.getLogger(__name__)


MAX_OPEN_MENU_DEPTH: int = 20
DEFAULT_MENU_INTERVAL: float = 0.3
DEFAULT_SCROLL_INTERVAL: float = 0.3


def _validate_current_scroll_target() -> None:
    x, y = pyautogui.position()
    cs = get_coordinate_system()
    size = cs.get_screen_size()
    validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
    info = inspect_point(x, y)
    check_target_window(info.process_name, info.class_name, info.control_type)


def _safe_click(
    x: int,
    y: int,
    duration: float,
    button: str,
    control: dict[str, Any],
) -> dict[str, Any] | None:
    """Validate and execute a click, returning an error dict on safety block."""
    try:
        cs = get_coordinate_system()
        size = cs.get_screen_size()
        validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
        check_target_window(
            control.get("process_name"),
            control.get("class_name"),
            control.get("control_type"),
        )
    except Exception as exc:
        return {"error": "safety_block", "detail": str(exc)}
    click(x, y, duration=duration, button=button)
    return None


def _candidates_for_text(text: str) -> list[dict[str, Any]]:
    """Return candidate controls matching ``text`` across the foreground window."""
    result = find_control(name=text, scope="foreground", match="contains", sensitive_check=False)
    if result.get("found"):
        return [result]
    return []


def click_by_uid(
    uid: str,
    snapshot: dict[str, Any],
    duration: float = 0.2,
    button: str = "left",
) -> dict[str, Any]:
    """Click the control with ``uid`` inside the provided snapshot.

    This is a thin wrapper kept next to the other composite helpers. The actual
    implementation lives in ``computer_use.snapshot``.
    """
    from computer_use.snapshot import click_by_uid as _snapshot_click_by_uid

    return _snapshot_click_by_uid(uid, snapshot, duration=duration, button=button)


def click_by_text(
    text: str,
    match: str = "contains",
    scope: str = "foreground",
    duration: float = 0.2,
    button: str = "left",
) -> dict[str, Any]:
    """Find a control by displayed text and click it.

    Returns ``{"error": "ui_not_found", "candidates": [...]}`` if no control
    matches ``text``.
    """
    result = find_control(name=text, scope=scope, match=match, sensitive_check=False)
    if not result.get("found"):
        return {
            "error": "ui_not_found",
            "text": text,
            "match": match,
            "scope": scope,
            "candidates": _candidates_for_text(text),
        }

    center = result.get("center")
    if center is None:
        return {
            "error": "ui_not_found",
            "text": text,
            "detail": "control has no center",
            "candidates": [result],
        }

    error = _safe_click(center["x"], center["y"], duration, button, result)
    if error is not None:
        return error

    return {
        "clicked": True,
        "text": text,
        "x": center["x"],
        "y": center["y"],
        "button": button,
        "duration": duration,
        "mode": "uia",
        "control": {
            "name": result.get("name"),
            "control_type": result.get("control_type"),
            "class_name": result.get("class_name"),
            "process_name": result.get("process_name"),
        },
    }


def open_menu(
    path: list[str],
    interval: float = DEFAULT_MENU_INTERVAL,
    duration: float = 0.2,
    button: str = "left",
) -> dict[str, Any]:
    """Click through a menu path using UIA names.

    Each item in ``path`` is located in the foreground window and clicked. If any
    item cannot be found, the function stops and returns ``ui_not_found`` together
    with the attempted item and candidate controls.
    """
    if not path:
        raise ValueError("path must contain at least one menu item")
    if len(path) > MAX_OPEN_MENU_DEPTH:
        raise ValueError(f"path exceeds maximum depth of {MAX_OPEN_MENU_DEPTH}")

    clicked: list[str] = []
    for item in path:
        result = find_control(name=item, scope="foreground", match="contains", sensitive_check=False)
        if not result.get("found"):
            return {
                "error": "ui_not_found",
                "attempted": item,
                "clicked": clicked,
                "candidates": _candidates_for_text(item),
            }

        center = result.get("center")
        if center is None:
            return {
                "error": "ui_not_found",
                "attempted": item,
                "detail": "control has no center",
                "clicked": clicked,
                "candidates": [result],
            }

        error = _safe_click(center["x"], center["y"], duration, button, result)
        if error is not None:
            return error

        clicked.append(item)
        if interval > 0:
            time.sleep(interval)

    return {
        "opened": True,
        "path": path,
        "clicked": clicked,
        "duration": duration,
        "button": button,
    }


def fill_form(
    fields: list[dict[str, Any]],
    duration: float = 0.2,
    type_interval: float = 0.01,
) -> dict[str, Any]:
    """Fill a form by locating each field by UIA name and typing its value.

    Each field dict has keys ``name`` (the UIA control name), ``value`` (text to
    type), and optionally ``match`` (default ``contains``). Dangerous text is
    rejected by ``validate_text_input`` before typing.
    """
    if not fields:
        raise ValueError("fields must contain at least one entry")

    filled: list[dict[str, Any]] = []
    for field in fields:
        name = field.get("name")
        value = field.get("value")
        match = field.get("match", "contains")
        if not name:
            raise ValueError("each field must have a 'name'")
        if value is None:
            raise ValueError("each field must have a 'value'")

        result = find_control(name=name, scope="foreground", match=match, sensitive_check=False)
        if not result.get("found"):
            return {
                "error": "ui_not_found",
                "field": field,
                "filled": filled,
                "candidates": _candidates_for_text(name),
            }

        center = result.get("center")
        if center is None:
            return {
                "error": "ui_not_found",
                "field": field,
                "detail": "control has no center",
                "filled": filled,
                "candidates": [result],
            }

        validate_text_input(str(value))
        error = _safe_click(center["x"], center["y"], duration, "left", result)
        if error is not None:
            return error
        type_text(str(value), interval=type_interval)
        filled.append({
            "name": name,
            "value": str(value),
            "x": center["x"],
            "y": center["y"],
        })

    return {"filled": True, "fields": filled}


def scroll_until(
    target_text: str,
    direction: str = "down",
    max_attempts: int = 10,
    clicks: int = 3,
    interval: float = DEFAULT_SCROLL_INTERVAL,
) -> dict[str, Any]:
    """Scroll until ``target_text`` appears in the foreground UIA tree.

    Returns ``{"found": True, ...}`` as soon as the text is found, or
    ``{"error": "ui_not_found", ...}`` after ``max_attempts`` unsuccessful
    scrolls.
    """
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    normalized_direction = direction.lower()
    if normalized_direction not in {"up", "down"}:
        raise ValueError(f"direction must be 'up' or 'down', got {direction!r}")

    for attempt in range(1, max_attempts + 1):
        result = find_control(
            name=target_text,
            scope="foreground",
            match="contains",
            sensitive_check=False,
        )
        if result.get("found"):
            return {
                "found": True,
                "attempts": attempt,
                "target_text": target_text,
                "control": {
                    "name": result.get("name"),
                    "control_type": result.get("control_type"),
                    "class_name": result.get("class_name"),
                    "process_name": result.get("process_name"),
                    "center": result.get("center"),
                },
            }

        _validate_current_scroll_target()
        scroll(direction=normalized_direction, clicks=clicks)
        if interval > 0:
            time.sleep(interval)

    return {
        "error": "ui_not_found",
        "target_text": target_text,
        "attempts": max_attempts,
        "direction": normalized_direction,
    }
