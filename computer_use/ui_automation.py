"""Windows UI Automation helpers for control inspection and fallback locating.

This module is optional at runtime; failures are logged and fall back to
coordinate-based operations.
"""

from __future__ import annotations

import logging
import time
from typing import Any, NamedTuple

from computer_use.core import get_coordinate_system

try:
    import uiautomation as uia
except ImportError:  # pragma: no cover
    uia = None  # type: ignore


logger = logging.getLogger(__name__)


class ControlInfo(NamedTuple):
    name: str | None
    control_type: str | None
    class_name: str | None
    process_name: str | None
    is_password: bool
    rect: tuple[int, int, int, int] | None
    center: tuple[int, int] | None


def _uia_available() -> bool:
    return uia is not None


def _get_foreground_control() -> object | None:
    if uia is None:
        return None
    try:
        return uia.GetForegroundControl()
    except Exception as exc:  # pragma: no cover
        logger.debug("uiautomation foreground control failed: %s", exc)
        return None


def _get_root_control() -> object | None:
    if uia is None:
        return None
    try:
        return uia.GetRootControl()
    except Exception as exc:  # pragma: no cover
        logger.debug("uiautomation root control failed: %s", exc)
        return None


def _control_matches(
    control: object,
    name: str | None,
    automation_id: str | None,
    control_type: str | None,
    class_name: str | None,
    match: str,
) -> bool:
    """Return True if a control matches all provided criteria."""
    if name is not None:
        control_name = getattr(control, "Name", "") or ""
        if match == "exact":
            if control_name.lower() != name.lower():
                return False
        elif match == "startswith":
            if not control_name.lower().startswith(name.lower()):
                return False
        else:  # contains
            if name.lower() not in control_name.lower():
                return False

    if automation_id is not None:
        if (getattr(control, "AutomationId", "") or "").lower() != automation_id.lower():
            return False

    if control_type is not None:
        if (getattr(control, "ControlTypeName", "") or "").lower() != control_type.lower():
            return False

    if class_name is not None:
        if (getattr(control, "ClassName", "") or "").lower() != class_name.lower():
            return False

    return True


def _collect_descendants(control: object) -> list[object]:
    """Return all descendants of ``control`` in depth-first pre-order.

    Prefer ``GetDescendantControls`` when available; otherwise recurse via
    ``GetFirstChildControl`` and ``GetNextSiblingControl``.
    """
    if control is None:
        return []

    if hasattr(control, "GetDescendantControls"):
        try:
            return list(control.GetDescendantControls())
        except Exception as exc:  # pragma: no cover
            logger.debug("GetDescendantControls failed, falling back: %s", exc)

    result: list[object] = []
    stack = [control]
    while stack:
        current = stack.pop()
        if current is not control:
            result.append(current)
        child = getattr(current, "GetFirstChildControl", lambda: None)()
        if child is not None:
            siblings = []
            sibling = child
            while sibling is not None:
                siblings.append(sibling)
                sibling = getattr(sibling, "GetNextSiblingControl", lambda: None)()
            # Pre-order: push siblings in reverse so the first child is popped first.
            stack.extend(reversed(siblings))
    return result


def _control_to_info(control: object) -> ControlInfo:
    rect = getattr(control, "BoundingRectangle", None)
    if rect is not None:
        rect_tuple = (rect.left, rect.top, rect.right, rect.bottom)
        center = ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    else:
        rect_tuple = None
        center = None
    return ControlInfo(
        name=getattr(control, "Name", None) or None,
        control_type=getattr(control, "ControlTypeName", None) or None,
        class_name=getattr(control, "ClassName", None) or None,
        process_name=_get_process_name(control),
        is_password=bool(getattr(control, "IsPassword", False)),
        rect=rect_tuple,
        center=center,
    )


def inspect_point(x: int, y: int) -> ControlInfo:
    """Inspect the control at the given physical virtual screen coordinates.

    The input is in physical virtual screen pixels (mss coordinates), which map
    1:1 with screenshot pixels. ``ControlFromPoint`` on Windows expects physical
    screen coordinates, so the value is validated and routed through the
    coordinate system but passed through unchanged.
    """
    if uia is None:
        return ControlInfo(
            name=None,
            control_type=None,
            class_name=None,
            process_name=None,
            is_password=False,
            rect=None,
            center=None,
        )

    try:
        cs = get_coordinate_system()
        phys_x, phys_y = cs.to_physical(x, y)
        control = uia.ControlFromPoint(phys_x, phys_y)
        if control is None:
            raise RuntimeError("No control at point")
        return _control_to_info(control)
    except Exception as exc:  # pragma: no cover
        logger.debug("inspect_point failed: %s", exc)
        return ControlInfo(
            name=None,
            control_type=None,
            class_name=None,
            process_name=None,
            is_password=False,
            rect=None,
            center=None,
        )


def _get_process_name(control: object) -> str | None:
    try:
        proc_id = getattr(control, "ProcessId", None)
        if proc_id is None:
            return None
        import psutil

        return psutil.Process(proc_id).name()
    except Exception:  # pragma: no cover
        return None


def find_control_by_name(name: str) -> ControlInfo | None:
    """Find a control by its automation name and return its center."""
    if uia is None:
        return None
    try:
        root = uia.GetRootControl()
        control = root.GetFirstChildControl(
            lambda ctrl, _target=name: ctrl.Name == _target
        )
        if control is None:
            return None
        return _control_to_info(control)
    except Exception as exc:  # pragma: no cover
        logger.debug("find_control_by_name failed: %s", exc)
        return None


def _find_window_by_name(name: str) -> object | None:
    """Return the first window whose title contains ``name`` (case-insensitive)."""
    root = _get_root_control()
    if root is None:
        return None
    for descendant in _collect_descendants(root):
        control_type = (getattr(descendant, "ControlTypeName", "") or "").lower()
        if control_type != "window":
            continue
        window_name = getattr(descendant, "Name", "") or ""
        if name.lower() in window_name.lower():
            return descendant
    return None


def _info_to_result(info: ControlInfo) -> dict[str, Any]:
    return {
        "found": True,
        "name": info.name,
        "control_type": info.control_type,
        "class_name": info.class_name,
        "rect": (
            {
                "left": info.rect[0],
                "top": info.rect[1],
                "right": info.rect[2],
                "bottom": info.rect[3],
            }
            if info.rect is not None
            else None
        ),
        "center": (
            {"x": info.center[0], "y": info.center[1]}
            if info.center is not None
            else None
        ),
        "process_name": info.process_name,
    }


def _find_control_object(
    name: str | None = None,
    automation_id: str | None = None,
    control_type: str | None = None,
    class_name: str | None = None,
    scope: str = "desktop",
    window_name: str | None = None,
    match: str = "contains",
) -> object | None:
    """Return the first matching UIA control object, or None."""
    if not _uia_available():
        return None

    if scope not in {"desktop", "foreground", "window"}:
        raise ValueError(f"Invalid scope: {scope}. Must be one of desktop, foreground, window.")

    if scope == "window" and not window_name:
        raise ValueError("window_name is required when scope='window'.")

    if scope == "desktop":
        root = _get_root_control()
    elif scope == "foreground":
        root = _get_foreground_control()
    else:  # scope == "window"
        root = _find_window_by_name(window_name)
        if root is None:
            return None

    if root is None:
        return None

    for descendant in _collect_descendants(root):
        if _control_matches(descendant, name, automation_id, control_type, class_name, match):
            return descendant
    return None


def _is_control_available(control: object) -> bool:
    """Return True if a control exists, is enabled, and is visible."""
    if control is None:
        return False
    exists = bool(getattr(control, "Exists", True))
    enabled = bool(getattr(control, "Enabled", True))
    visible = bool(getattr(control, "Visible", True))
    return exists and enabled and visible


def find_control(
    name: str | None = None,
    automation_id: str | None = None,
    control_type: str | None = None,
    class_name: str | None = None,
    scope: str = "desktop",
    window_name: str | None = None,
    match: str = "contains",
    sensitive_check: bool = True,
) -> dict[str, Any]:
    """Find a control by name/automation id/control type/class name.

    Returns a structured dict so callers can distinguish UIA availability,
    misses, parent-window misses, and safety blocks.
    """
    from computer_use.safety import SafetyError, check_target_window

    if not _uia_available():
        return {"found": False, "uia_available": False, "blocked": False, "reason": "uia_not_available"}

    if not any(param is not None for param in (name, automation_id, control_type, class_name)):
        raise ValueError("At least one of name, automation_id, control_type, or class_name is required.")

    try:
        control = _find_control_object(
            name=name,
            automation_id=automation_id,
            control_type=control_type,
            class_name=class_name,
            scope=scope,
            window_name=window_name,
            match=match,
        )
        if control is None:
            if scope == "window" and not _find_window_by_name(window_name):
                return {
                    "found": False,
                    "uia_available": True,
                    "blocked": False,
                    "reason": "parent_window_not_found",
                }
            return {"found": False, "uia_available": True, "blocked": False, "reason": "not_found"}

        info = _control_to_info(control)
        if sensitive_check:
            try:
                check_target_window(info.process_name, info.class_name, info.control_type)
            except SafetyError as exc:
                return {
                    "found": False,
                    "uia_available": True,
                    "blocked": True,
                    "reason": "sensitive_window_blocked",
                    "detail": str(exc),
                }
        return _info_to_result(info)
    except Exception as exc:  # pragma: no cover
        logger.debug("find_control failed: %s", exc)
        return {"found": False, "uia_available": True, "blocked": False, "reason": "not_found"}


def wait_for_window(
    name: str,
    exists: bool = True,
    timeout: float = 10,
    poll_interval: float = 0.2,
) -> dict[str, Any]:
    """Poll until a window with a matching title appears or disappears."""
    if not _uia_available():
        return {"present": False, "timeout": True, "uia_available": False}

    deadline = time.time() + timeout
    while time.time() < deadline:
        window = _find_window_by_name(name)
        if exists and window is not None:
            rect = getattr(window, "BoundingRectangle", None)
            return {
                "present": True,
                "name": getattr(window, "Name", None) or None,
                "rect": (
                    {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom}
                    if rect is not None
                    else None
                ),
            }
        if not exists and window is None:
            return {"present": False, "timeout": False}
        time.sleep(poll_interval)

    return {"present": not exists, "timeout": True}


def wait_for_control(
    name: str | None = None,
    automation_id: str | None = None,
    control_type: str | None = None,
    exists: bool = True,
    timeout: float = 10,
    poll_interval: float = 0.2,
) -> dict[str, Any]:
    """Poll until a control becomes available (Exists, Enabled, Visible).

    Searches the foreground window by default and matches controls using the
    same rules as ``find_control``.
    """
    if not _uia_available():
        return {"present": False, "timeout": True, "uia_available": False}

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            control = _find_control_object(
                name=name,
                automation_id=automation_id,
                control_type=control_type,
                scope="foreground",
                match="contains",
            )
        except Exception as exc:  # pragma: no cover
            logger.debug("wait_for_control poll failed: %s", exc)
            time.sleep(poll_interval)
            continue

        available = _is_control_available(control)
        info = _control_to_info(control) if control is not None else None

        if exists and available:
            return {
                "present": True,
                "name": info.name if info is not None else None,
                "control_type": info.control_type if info is not None else None,
                "enabled": True,
                "visible": True,
            }
        if not exists and not available:
            return {"present": False, "timeout": False}

        time.sleep(poll_interval)

    return {"present": not exists, "timeout": True}
