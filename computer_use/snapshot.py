"""UI Automation tree snapshot and UID-based interaction.

This module provides structured accessibility-tree snapshots of the Windows UI.
It is optional at runtime: if ``uiautomation`` is not installed, public
functions return a clear error dict instead of raising.
"""

from __future__ import annotations

import base64
import logging
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyautogui

from computer_use.core import click, get_coordinate_system, get_monitors, save_screenshot
from computer_use.safety import check_target_window, validate_coordinate
from computer_use.ui_automation import _get_process_name, inspect_point


try:
    import uiautomation as uia
except ImportError:  # pragma: no cover
    uia = None  # type: ignore


logger = logging.getLogger(__name__)


#: Maximum controls collected per scope to keep payloads bounded.
_SCOPE_LIMITS = {
    "foreground": 2000,
    "desktop": 5000,
}


def _control_handle(control: object) -> int:
    """Return the best available native handle for a control."""
    for attr in ("NativeWindowHandle", "Handle", "hwnd"):
        value = getattr(control, attr, None)
        if isinstance(value, int) and value:
            return value
    return 0


def _control_bbox(control: object) -> dict[str, int] | None:
    """Return the bounding box of a control as a dict, or None."""
    rect = getattr(control, "BoundingRectangle", None)
    if rect is None:
        return None
    try:
        left = int(rect.left)
        top = int(rect.top)
        right = int(rect.right)
        bottom = int(rect.bottom)
    except Exception:
        return None
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def _control_enabled(control: object) -> bool:
    return bool(getattr(control, "Enabled", True))


def _control_visible(control: object) -> bool:
    return bool(getattr(control, "Visible", True))


def _build_uid(handle: int, path: str) -> str:
    """Encode handle + path into a deterministic, self-contained string."""
    payload = f"{handle}::{path}".encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _build_path_segment(control: object, index: int) -> str:
    """Build a single human-readable path segment."""
    control_type = getattr(control, "ControlTypeName", "Control") or "Control"
    name = getattr(control, "Name", "") or ""
    segment = f"{control_type}[{index}]"
    if name:
        segment += f'"{name}"'
    return segment


def _traverse_controls(root: object, scope: str) -> tuple[list[dict[str, Any]], bool]:
    """Depth-first traversal of ``root``, returning controls and a truncated flag."""
    limit = _SCOPE_LIMITS.get(scope, 2000)
    controls: list[dict[str, Any]] = []
    truncated = False
    stack: list[tuple[object, str, int]] = [(root, "/", 0)]

    while stack:
        control, parent_path, index = stack.pop()
        bbox = _control_bbox(control)
        if bbox is None:
            continue
        if bbox["right"] <= bbox["left"] or bbox["bottom"] <= bbox["top"]:
            continue

        segment = _build_path_segment(control, index)
        path = f"{parent_path.rstrip('/')}/{segment}" if parent_path != "/" else f"/{segment}"
        handle = _control_handle(control)
        center_x = (bbox["left"] + bbox["right"]) // 2
        center_y = (bbox["top"] + bbox["bottom"]) // 2

        controls.append({
            "uid": _build_uid(handle, path),
            "name": getattr(control, "Name", "") or "",
            "control_type": getattr(control, "ControlTypeName", "") or "",
            "class_name": getattr(control, "ClassName", "") or "",
            "bbox": bbox,
            "center": {"x": center_x, "y": center_y},
            "process_name": _get_process_name(control),
            "enabled": _control_enabled(control),
            "visible": _control_visible(control),
            "path": path,
        })

        if len(controls) >= limit:
            truncated = True
            logger.warning("UI snapshot truncated at %d controls for scope=%s", limit, scope)
            break

        children: list[object] = []
        first_child = getattr(control, "GetFirstChildControl", lambda: None)()
        if first_child is not None:
            sibling = first_child
            sibling_index = 0
            while sibling is not None:
                children.append((sibling, path, sibling_index))
                sibling = getattr(sibling, "GetNextSiblingControl", lambda: None)()
                sibling_index += 1
        # Pre-order: push in reverse so first child is popped first.
        stack.extend(reversed(children))

    return controls, truncated


def _monitor_index_for_point(x: int, y: int) -> int:
    """Return the 1-based monitor index containing ``(x, y)``, or 0 if unknown."""
    for monitor in get_monitors():
        if (
            monitor.left <= x < monitor.left + monitor.width
            and monitor.top <= y < monitor.top + monitor.height
        ):
            return monitor.index
    return 0


def _resolve_snapshot_dir(snapshot_dir: str | None) -> Path:
    """Return the directory to store snapshot screenshots."""
    if snapshot_dir:
        path = Path(snapshot_dir).resolve()
    else:
        from computer_use.trace import trace_dir

        path = trace_dir() / "snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_ui_snapshot(
    scope: str = "foreground",
    include_screenshot: bool = False,
    save_path: str | None = None,
    snapshot_dir: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Capture a structured UI Automation tree snapshot.

    Args:
        scope: ``foreground`` (default) for the current foreground window, or
            ``desktop`` for the entire desktop.
        include_screenshot: If True, capture and save a screenshot of the
            relevant monitor and return its path.
        save_path: Explicit screenshot destination path. If omitted, a
            timestamped file is created under ``snapshot_dir``.
        snapshot_dir: Directory for the screenshot. Defaults to
            ``<trace_dir>/snapshots``.
        trace_id: Optional trace ID. When provided and no explicit screenshot
            destination is set, screenshots are stored under that trace's
            ``screenshots`` artifact directory.

    Returns:
        A dict describing the snapshot, or ``{"error": "uiautomation_not_available"}``.
    """
    if uia is None:
        return {"error": "uiautomation_not_available"}

    if scope not in {"foreground", "desktop"}:
        raise ValueError(f"Invalid scope: {scope!r}. Use 'foreground' or 'desktop'.")

    if scope == "desktop":
        warnings.warn(
            "Desktop UI snapshots can be large and slow. Prefer scope='foreground'.",
            stacklevel=2,
        )

    try:
        if scope == "foreground":
            root = uia.GetForegroundControl()
        else:
            root = uia.GetRootControl()
    except Exception as exc:  # pragma: no cover
        logger.debug("Failed to acquire UIA root control: %s", exc)
        return {"error": "uiautomation_root_failed", "detail": str(exc)}

    if root is None:
        return {"error": "uiautomation_root_failed"}

    controls, truncated = _traverse_controls(root, scope)

    root_bbox = _control_bbox(root)
    root_name = getattr(root, "Name", "") or ""
    root_process = _get_process_name(root)

    foreground_window = {"name": root_name, "process_name": root_process}
    if scope == "desktop":
        try:
            fg = uia.GetForegroundControl()
            foreground_window = {
                "name": getattr(fg, "Name", "") or "",
                "process_name": _get_process_name(fg),
            }
        except Exception as exc:  # pragma: no cover
            logger.debug("Failed to get foreground control: %s", exc)

    cursor_x, cursor_y = pyautogui.position()

    result: dict[str, Any] = {
        "scope": scope,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "foreground_window": foreground_window,
        "cursor": {"x": cursor_x, "y": cursor_y},
        "controls": controls,
        "truncated": truncated,
        "screenshot_path": None,
    }

    if include_screenshot:
        monitor = 0
        if scope == "foreground" and root_bbox:
            monitor = _monitor_index_for_point(
                (root_bbox["left"] + root_bbox["right"]) // 2,
                (root_bbox["top"] + root_bbox["bottom"]) // 2,
            )

        if save_path:
            screenshot_dest = Path(save_path)
            screenshot_dest.parent.mkdir(parents=True, exist_ok=True)
        else:
            if snapshot_dir:
                dest_dir = _resolve_snapshot_dir(snapshot_dir)
            elif trace_id:
                from computer_use.trace import artifact_dir

                dest_dir = artifact_dir(trace_id, "screenshots")
            else:
                dest_dir = _resolve_snapshot_dir(snapshot_dir)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            screenshot_dest = dest_dir / f"snapshot_{ts}.png"

        try:
            saved = save_screenshot(str(screenshot_dest), monitor=monitor)
            result["screenshot_path"] = str(saved)
        except Exception as exc:  # pragma: no cover
            logger.debug("Screenshot capture failed: %s", exc)
            result["screenshot_path"] = None

    return result


def click_by_uid(
    uid: str,
    snapshot: dict[str, Any],
    duration: float = 0.2,
    button: str = "left",
) -> dict[str, Any]:
    """Click the control identified by ``uid`` in ``snapshot``.

    Returns:
        A dict with click details, or ``{"error": "stale_uid"}`` if the UID
        is not present in the snapshot.
    """
    controls = snapshot.get("controls", [])
    for control in controls:
        if control.get("uid") == uid:
            center = control["center"]
            try:
                cs = get_coordinate_system()
                size = cs.get_screen_size()
                validate_coordinate(center["x"], center["y"], size.width, size.height, monitors=cs.monitors)
                info = inspect_point(center["x"], center["y"])
                check_target_window(
                    info.process_name,
                    info.class_name,
                    info.control_type,
                )
            except Exception as exc:
                return {"error": "safety_block", "detail": str(exc)}
            click(center["x"], center["y"], duration=duration, button=button)
            return {
                "clicked": True,
                "uid": uid,
                "x": center["x"],
                "y": center["y"],
                "button": button,
                "duration": duration,
            }
    return {"error": "stale_uid"}


# crop annotation — see plans/active/crop-region-annotation.md
DEFAULT_BRACKET_ARM_PX = 24
DEFAULT_BRACKET_WIDTH_PX = 3
ANNOTATION_COLOR = (255, 0, 0)
_annotation_font = None  # lazy-loaded


def _get_annotation_font():
    """Lazy-load PIL default font (cached)."""
    global _annotation_font
    if _annotation_font is None:
        from PIL import ImageFont
        _annotation_font = ImageFont.load_default()
    return _annotation_font


def annotate_region(
    source_path: str,
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    style: str = "corner_brackets",
    arm_length: int = DEFAULT_BRACKET_ARM_PX,
    line_width: int = DEFAULT_BRACKET_WIDTH_PX,
) -> str:
    """Draw a red region marker on a copy of the source image. Non-destructive.

    Args:
        source_path: Path to the source PNG. Not modified.
        x, y, width, height: Region in source image pixels.
        style: Marker style. Currently only "corner_brackets" is supported.
        arm_length: Length of each L-bracket arm in pixels.
        line_width: Stroke width in pixels.

    Returns:
        Path to the annotated PNG (a sibling file with ``_annotated`` suffix).
    """
    if style != "corner_brackets":
        raise ValueError(f"unsupported annotation style: {style!r}")

    from PIL import Image, ImageDraw

    src = Image.open(source_path)
    if src.mode != "RGB":
        src = src.convert("RGB")

    x2, y2 = x + width, y + height
    if x < 0 or y < 0 or x2 > src.width or y2 > src.height:
        raise ValueError(
            f"region ({x},{y},{width},{height}) out of source bounds "
            f"({src.width}x{src.height})"
        )

    annotated = src.copy()
    draw = ImageDraw.Draw(annotated)
    color = ANNOTATION_COLOR
    L = arm_length
    W = line_width

    # Top-left corner
    draw.line([(x, y), (x + L, y)], fill=color, width=W)
    draw.line([(x, y), (x, y + L)], fill=color, width=W)
    # Top-right
    draw.line([(x2, y), (x2 - L, y)], fill=color, width=W)
    draw.line([(x2, y), (x2, y + L)], fill=color, width=W)
    # Bottom-left
    draw.line([(x, y2), (x + L, y2)], fill=color, width=W)
    draw.line([(x, y2), (x, y2 - L)], fill=color, width=W)
    # Bottom-right
    draw.line([(x2, y2), (x2 - L, y2)], fill=color, width=W)
    draw.line([(x2, y2), (x2, y2 - L)], fill=color, width=W)

    # Coordinate label (top-left inside crop, white shadow for legibility)
    label = f"({x},{y},{width},{height})"
    font = _get_annotation_font()
    label_x = x + 6
    label_y = y + 6
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        draw.text((label_x + dx, label_y + dy), label, fill=(255, 255, 255), font=font)
    draw.text((label_x, label_y), label, fill=color, font=font)

    # Output path: <source>_annotated.png in same directory
    src_path = Path(source_path)
    annotated_path = src_path.with_name(f"{src_path.stem}_annotated.png")
    annotated.save(str(annotated_path))
    return str(annotated_path)
