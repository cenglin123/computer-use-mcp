"""Windows UI Automation helpers for control inspection and fallback locating.

This module is optional at runtime; failures are logged and fall back to
coordinate-based operations.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

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


def _get_foreground_control() -> object | None:
    if uia is None:
        return None
    try:
        return uia.GetForegroundControl()
    except Exception as exc:  # pragma: no cover
        logger.debug("uiautomation foreground control failed: %s", exc)
        return None


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
        rect = control.BoundingRectangle
        center = ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
        return ControlInfo(
            name=control.Name or None,
            control_type=getattr(control, "ControlTypeName", None),
            class_name=getattr(control, "ClassName", None),
            process_name=_get_process_name(control),
            is_password=bool(getattr(control, "IsPassword", False)),
            rect=(rect.left, rect.top, rect.right, rect.bottom),
            center=center,
        )
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
        rect = control.BoundingRectangle
        center = ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
        return ControlInfo(
            name=control.Name or None,
            control_type=getattr(control, "ControlTypeName", None),
            class_name=getattr(control, "ClassName", None),
            process_name=_get_process_name(control),
            is_password=bool(getattr(control, "IsPassword", False)),
            rect=(rect.left, rect.top, rect.right, rect.bottom),
            center=center,
        )
    except Exception as exc:  # pragma: no cover
        logger.debug("find_control_by_name failed: %s", exc)
        return None
