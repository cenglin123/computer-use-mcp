"""Core Computer Use primitives: screenshot, coordinate conversion, mouse/keyboard."""

from __future__ import annotations

import base64
import ctypes
import io
import sys
from typing import NamedTuple

import mss
import pyautogui
from PIL import Image

from computer_use.safety import SafetyError

# Make this process DPI-aware so that pyautogui coordinates and mss screenshots
# use a consistent coordinate system. On Windows this affects how logical vs
# physical pixels are reported.
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:  # pragma: no cover
    pass

# Suppress pyautogui failsafe moving too fast warnings in headless tests.
pyautogui.FAILSAFE = True

#: Default duration (seconds) for smooth cursor movement in mouse tools.
DEFAULT_MOVE_DURATION: float = 0.2


class ScreenInfo(NamedTuple):
    width: int
    height: int


class MonitorInfo(NamedTuple):
    index: int
    primary: bool
    left: int
    top: int
    width: int
    height: int


class RECT(ctypes.Structure):  # noqa: N801
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class CoordinateSystem:
    """Coordinate system for multi-monitor virtual screen.

    All public tool-facing coordinates are **physical virtual screen pixels**
    (mss coordinates). The origin is the top-left of the virtual desktop and
    coordinates map 1:1 with screenshot pixels. This class validates that
    coordinates fall within an actual monitor and routes them to the containing
    monitor when needed.
    """

    _TOLERANCE = 0.05

    def __init__(self) -> None:
        with mss.MSS() as sct:
            # Virtual screen physical bounds (monitors[0] in mss).
            virtual = sct.monitors[0]
            self.virtual_left = virtual["left"]
            self.virtual_top = virtual["top"]
            self.virtual_width = virtual["width"]
            self.virtual_height = virtual["height"]

            # Per-monitor physical bounds. mss uses 1-based indexing where 1 is
            # the primary monitor.
            self.monitors: list[dict[str, int]] = list(sct.monitors[1:])

            # Primary monitor physical bounds.
            primary = sct.monitors[1]
            self.primary_left = primary["left"]
            self.primary_top = primary["top"]
            self.primary_width_phys = primary["width"]
            self.primary_height_phys = primary["height"]

        # Logical size from pyautogui (Windows scaled logical pixels of the
        # primary monitor). Used only for uniform scaling detection.
        self.logical_width, self.logical_height = pyautogui.size()

        # Detect mixed scaling: if any monitor has a different physical/logical
        # ratio than the primary, refuse to operate. This is an MVP limitation
        # documented in the README.
        self._validate_uniform_scaling()

    def _get_monitor_logical_sizes(self) -> list[dict[str, int]]:
        """Return logical (system-DPI) bounds for all monitors.

        Uses EnumDisplayMonitors which returns system-DPI-aware logical
        coordinates after SetProcessDPIAware has been called.
        """
        monitors: list[dict[str, int]] = []

        try:
            user32 = ctypes.windll.user32
        except Exception:  # pragma: no cover
            return monitors

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):  # noqa: N803, ARG001
            rect = ctypes.cast(lprcMonitor, ctypes.POINTER(RECT)).contents
            monitors.append(
                {
                    "left": rect.left,
                    "top": rect.top,
                    "width": rect.right - rect.left,
                    "height": rect.bottom - rect.top,
                }
            )
            return 1

        MONITORENUMPROC = ctypes.WINFUNCTYPE(  # noqa: N806
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(RECT),
            ctypes.c_long,
        )

        try:
            user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(callback), 0)
        except Exception:  # pragma: no cover
            return []

        return monitors

    def _validate_uniform_scaling(self) -> None:
        """Raise RuntimeError if monitors have mismatched physical/logical ratios."""
        if self.logical_width == 0 or self.logical_height == 0:
            return

        primary_ratio_w = self.primary_width_phys / self.logical_width
        primary_ratio_h = self.primary_height_phys / self.logical_height

        logical_sizes = self._get_monitor_logical_sizes()

        for i, mon in enumerate(self.monitors, start=1):
            if i - 1 >= len(logical_sizes):
                continue
            logical = logical_sizes[i - 1]
            if logical["width"] == 0 or logical["height"] == 0:
                continue

            ratio_w = mon["width"] / logical["width"]
            ratio_h = mon["height"] / logical["height"]

            if (
                abs(ratio_w - primary_ratio_w) > self._TOLERANCE
                or abs(ratio_h - primary_ratio_h) > self._TOLERANCE
            ):
                raise RuntimeError(
                    f"Mixed-DPI multi-monitor setup detected: monitor {i} "
                    f"scale {ratio_w:.3f}x{ratio_h:.3f} differs from primary "
                    f"{primary_ratio_w:.3f}x{primary_ratio_h:.3f}. "
                    "Computer Use MVP does not support mixed-DPI setups."
                )

    def to_physical(self, x: int, y: int) -> tuple[int, int]:
        """Validate coordinates and route them to the containing monitor.

        Coordinates are already in physical virtual screen pixels, so this
        method only verifies that they fall within an actual monitor (not a gap
        in the virtual screen) and returns them unchanged.
        """
        if x < self.virtual_left or y < self.virtual_top:
            raise SafetyError(
                f"Coordinate ({x}, {y}) is outside virtual screen bounds "
                f"({self.virtual_width}x{self.virtual_height})."
            )
        if (
            x >= self.virtual_left + self.virtual_width
            or y >= self.virtual_top + self.virtual_height
        ):
            raise SafetyError(
                f"Coordinate ({x}, {y}) is outside virtual screen bounds "
                f"({self.virtual_width}x{self.virtual_height})."
            )

        for mon in self.monitors:
            if (
                mon["left"] <= x < mon["left"] + mon["width"]
                and mon["top"] <= y < mon["top"] + mon["height"]
            ):
                return x, y

        raise SafetyError(
            f"Coordinate ({x}, {y}) falls in a virtual screen gap and is not on any monitor."
        )

    def get_screen_size(self) -> ScreenInfo:
        """Return the physical virtual screen size."""
        return ScreenInfo(width=self.virtual_width, height=self.virtual_height)

    def get_monitors(self) -> list[MonitorInfo]:
        """Return metadata for all connected monitors."""
        result: list[MonitorInfo] = []
        for i, mon in enumerate(self.monitors, start=1):
            result.append(
                MonitorInfo(
                    index=i,
                    primary=(mon["left"] == self.primary_left and mon["top"] == self.primary_top),
                    left=mon["left"],
                    top=mon["top"],
                    width=mon["width"],
                    height=mon["height"],
                )
            )
        return result


_coordinate_system_instance: CoordinateSystem | None = None


def get_coordinate_system() -> CoordinateSystem:
    """Return the cached CoordinateSystem singleton."""
    global _coordinate_system_instance
    if _coordinate_system_instance is None:
        _coordinate_system_instance = CoordinateSystem()
    return _coordinate_system_instance


def get_monitors() -> list[MonitorInfo]:
    """Return metadata for all connected monitors."""
    return get_coordinate_system().get_monitors()


def screenshot(monitor: int = 0) -> str:
    """Take a screenshot and return a base64 PNG.

    Args:
        monitor: 0 for the entire virtual desktop, or a 1-based mss monitor
            index (1 = primary, 2 = secondary, etc.).
    """
    with mss.MSS() as sct:
        if monitor < 0 or monitor >= len(sct.monitors):
            raise ValueError(f"Invalid monitor index: {monitor}")
        img = sct.grab(sct.monitors[monitor])
    pil_img = Image.frombytes("RGB", img.size, img.rgb)
    buffer = io.BytesIO()
    pil_img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def create_redacted_image(width: int, height: int) -> str:
    """Return a fully-redacted red image as a base64 PNG."""
    pil_img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buffer = io.BytesIO()
    pil_img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def validate_duration(duration: float) -> float:
    """Validate that *duration* is a non-negative finite number.

    Args:
        duration: Desired movement duration in seconds.

    Returns:
        The validated duration.

    Raises:
        ValueError: If *duration* is negative, NaN, or not finite.
    """
    if duration != duration:  # NaN is the only value that does not equal itself.
        raise ValueError(f"duration must be a real number, got NaN")
    if duration < 0:
        raise ValueError(f"duration must be non-negative, got {duration}")
    if duration == float("inf"):
        raise ValueError(f"duration must be finite, got {duration}")
    return duration


def click(x: int, y: int, duration: float = DEFAULT_MOVE_DURATION) -> None:
    """Click at physical virtual screen coordinates (x, y).

    Args:
        duration: Seconds to spend moving the cursor to the target before
            clicking. Defaults to ``DEFAULT_MOVE_DURATION``. A small positive
            value keeps hover-activated menus open.
    """
    validate_duration(duration)
    cs = get_coordinate_system()
    phys_x, phys_y = cs.to_physical(x, y)
    pyautogui.click(phys_x, phys_y, duration=duration)


def move_to(x: int, y: int, duration: float = DEFAULT_MOVE_DURATION) -> None:
    """Move the cursor to physical virtual screen coordinates (x, y).

    Args:
        duration: Seconds to spend moving the cursor. Defaults to
            ``DEFAULT_MOVE_DURATION``. A small positive value keeps
            hover-activated menus open.
    """
    validate_duration(duration)
    cs = get_coordinate_system()
    phys_x, phys_y = cs.to_physical(x, y)
    pyautogui.moveTo(phys_x, phys_y, duration=duration)


def scroll(amount: int, x: int | None = None, y: int | None = None) -> None:
    """Scroll the mouse wheel by amount, optionally at physical virtual screen coordinates."""
    if x is not None and y is not None:
        cs = get_coordinate_system()
        phys_x, phys_y = cs.to_physical(x, y)
        pyautogui.scroll(amount, phys_x, phys_y)
    else:
        pyautogui.scroll(amount)


def type_text(text: str, interval: float = 0.01) -> None:
    pyautogui.typewrite(text, interval=interval)


def key_combo(*keys: str) -> None:
    pyautogui.hotkey(*keys)


if __name__ == "__main__":  # pragma: no cover
    # Simple debug harness.
    cmd = sys.argv[1] if len(sys.argv) > 1 else "screenshot"
    if cmd == "screenshot":
        print(screenshot())
    elif cmd == "size":
        info = get_coordinate_system().get_screen_size()
        print(f"{info.width}x{info.height}")
    else:
        raise SystemExit(f"Unknown command: {cmd}")
