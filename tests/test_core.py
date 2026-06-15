"""Tests for core coordinate conversion."""

from __future__ import annotations

import pytest

from computer_use import core
from computer_use.safety import SafetyError


class FakeMss:
    """Standard multi-monitor mock fixture.

    Two 1920x1080 monitors side by side with a small vertical offset, matching
    the target environment:
      - monitor 1 (primary): left=0, top=0, 1920x1080
      - monitor 2: left=1920, top=9, 1920x1080
      - virtual screen: left=0, top=0, 3840x1089
    """

    monitors = [
        {"left": 0, "top": 0, "width": 3840, "height": 1089},  # virtual
        {"left": 0, "top": 0, "width": 1920, "height": 1080},  # primary
        {"left": 1920, "top": 9, "width": 1920, "height": 1080},  # secondary
    ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def grab(self, monitor: dict) -> object:
        class FakeImage:
            size = (monitor["width"], monitor["height"])
            rgb = b"\x00" * (monitor["width"] * monitor["height"] * 3)

        return FakeImage()


@pytest.fixture
def multi_monitor_cs(monkeypatch):
    """Return a CoordinateSystem backed by the standard two-monitor fake fixture."""
    monkeypatch.setattr(core.mss, "MSS", FakeMss)
    monkeypatch.setattr(core.pyautogui, "size", lambda: (1920, 1080))

    cs = core.CoordinateSystem.__new__(core.CoordinateSystem)
    # Populate directly to avoid __init__ side effects; then run validation.
    virtual = FakeMss.monitors[0]
    cs.virtual_left = virtual["left"]
    cs.virtual_top = virtual["top"]
    cs.virtual_width = virtual["width"]
    cs.virtual_height = virtual["height"]
    cs.monitors = list(FakeMss.monitors[1:])
    primary = FakeMss.monitors[1]
    cs.primary_left = primary["left"]
    cs.primary_top = primary["top"]
    cs.primary_width_phys = primary["width"]
    cs.primary_height_phys = primary["height"]
    cs.logical_width = 1920
    cs.logical_height = 1080
    cs._validate_uniform_scaling()
    return cs


def test_coordinate_system_conversion() -> None:
    # Integration smoke test on the developer machine.
    cs = core.get_coordinate_system()
    info = cs.get_screen_size()
    assert info.width > 0
    assert info.height > 0


def test_to_physical_monotonic(multi_monitor_cs) -> None:
    cs = multi_monitor_cs
    # Primary top-left maps to itself.
    assert cs.to_physical(0, 0) == (0, 0)
    # Secondary monitor coordinate is accepted as-is.
    assert cs.to_physical(2000, 500) == (2000, 500)


def test_virtual_screen_bounds(multi_monitor_cs) -> None:
    cs = multi_monitor_cs
    info = cs.get_screen_size()
    assert info.width == 3840
    assert info.height == 1089

    # Bottom-right corner of virtual screen is out of bounds (one past last pixel).
    with pytest.raises(SafetyError):
        cs.to_physical(info.width, info.height)

    # Negative coordinates are rejected.
    with pytest.raises(SafetyError):
        cs.to_physical(-1, 0)
    with pytest.raises(SafetyError):
        cs.to_physical(0, -1)


def test_gap_region_rejected(multi_monitor_cs) -> None:
    cs = multi_monitor_cs
    # Gap region between the two monitors: x in (1920, 3840) but y < 9.
    with pytest.raises(SafetyError, match="gap"):
        cs.to_physical(2000, 5)


def test_get_monitors(multi_monitor_cs) -> None:
    cs = multi_monitor_cs
    monitors = cs.get_monitors()
    assert len(monitors) == 2
    assert monitors[0] == core.MonitorInfo(
        index=1, primary=True, left=0, top=0, width=1920, height=1080
    )
    assert monitors[1] == core.MonitorInfo(
        index=2, primary=False, left=1920, top=9, width=1920, height=1080
    )


def test_screenshot_default_uses_virtual_desktop(monkeypatch) -> None:
    fake = FakeMss()
    monkeypatch.setattr(core.mss, "MSS", lambda: fake)
    monkeypatch.setattr(core.pyautogui, "position", lambda: (100, 100))
    result = core.screenshot()
    # Result is a non-empty base64 PNG string.
    assert isinstance(result, str)
    assert len(result) > 100


def test_screenshot_single_monitor(monkeypatch) -> None:
    fake = FakeMss()
    monkeypatch.setattr(core.mss, "MSS", lambda: fake)
    monkeypatch.setattr(core.pyautogui, "position", lambda: (2020, 109))
    result = core.screenshot(monitor=2)
    assert isinstance(result, str)
    assert len(result) > 100


def test_draw_cursor_marker_draws_red_crosshair() -> None:
    from PIL import Image

    image = Image.new("RGB", (50, 50), "black")
    core._draw_cursor_marker(image, 25, 25)

    assert image.getpixel((25, 25)) == (255, 0, 0)
    assert image.getpixel((5, 25)) == (255, 0, 0)
    assert image.getpixel((45, 25)) == (255, 0, 0)
    assert image.getpixel((25, 5)) == (255, 0, 0)
    assert image.getpixel((25, 45)) == (255, 0, 0)
    assert image.getpixel((4, 25)) == (0, 0, 0)


def test_draw_cursor_marker_ignores_cursor_outside_image() -> None:
    from PIL import Image

    image = Image.new("RGB", (20, 20), "black")
    core._draw_cursor_marker(image, 20, 10)

    assert image.getbbox() is None


def test_screenshot_translates_virtual_cursor_to_monitor_coordinates(monkeypatch) -> None:
    import base64
    import io

    from PIL import Image

    fake = FakeMss()
    monkeypatch.setattr(core.mss, "MSS", lambda: fake)
    monkeypatch.setattr(core.pyautogui, "position", lambda: (2020, 109))

    result = core.screenshot(monitor=2)
    image = Image.open(io.BytesIO(base64.b64decode(result)))

    assert image.getpixel((100, 100)) == (255, 0, 0)


def test_save_screenshot_marks_cursor_at_monitor_relative_position(
    monkeypatch, tmp_path
) -> None:
    from PIL import Image

    fake = FakeMss()
    monkeypatch.setattr(core.mss, "MSS", lambda: fake)
    monkeypatch.setattr(core.pyautogui, "position", lambda: (2020, 109))
    path = tmp_path / "marked.png"

    core.save_screenshot(path, monitor=2)
    image = Image.open(path)

    assert image.getpixel((100, 100)) == (255, 0, 0)


def test_screenshot_invalid_monitor(monkeypatch) -> None:
    fake = FakeMss()
    monkeypatch.setattr(core.mss, "MSS", lambda: fake)
    with pytest.raises(ValueError):
        core.screenshot(monitor=99)


def test_create_redacted_image() -> None:
    import base64
    import io

    from PIL import Image

    result = core.create_redacted_image(100, 200)
    img = Image.open(io.BytesIO(base64.b64decode(result)))
    assert img.size == (100, 200)


def _fake_coordinate_system() -> core.CoordinateSystem:
    cs = core.CoordinateSystem.__new__(core.CoordinateSystem)
    cs.to_physical = lambda x, y: (x, y)  # type: ignore[method-assign]
    cs.monitors = [
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    ]
    cs.get_screen_size = lambda: core.ScreenInfo(3840, 1080)  # type: ignore[method-assign]
    return cs


def test_click_uses_default_duration(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(
        core.pyautogui, "click", lambda x, y, duration, button: calls.append((x, y, duration, button))
    )
    core.click(100, 200)
    assert calls == [(100, 200, 0.2, "left")]


def test_click_uses_custom_duration_and_button(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(
        core.pyautogui, "click", lambda x, y, duration, button: calls.append((x, y, duration, button))
    )
    core.click(100, 200, duration=0.5, button="right")
    assert calls == [(100, 200, 0.5, "right")]


def test_move_to_uses_default_duration(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "moveTo", lambda x, y, duration: calls.append((x, y, duration)))
    core.move_to(100, 200)
    assert calls == [(100, 200, 0.2)]


def test_move_to_uses_custom_duration(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "moveTo", lambda x, y, duration: calls.append((x, y, duration)))
    core.move_to(100, 200, duration=0.5)
    assert calls == [(100, 200, 0.5)]


def test_click_negative_duration_raises() -> None:
    with pytest.raises(ValueError, match="duration"):
        core.click(100, 200, duration=-0.1)


def test_move_to_negative_duration_raises() -> None:
    with pytest.raises(ValueError, match="duration"):
        core.move_to(100, 200, duration=-0.1)


def test_click_nan_duration_raises() -> None:
    with pytest.raises(ValueError, match="NaN|duration"):
        core.click(100, 200, duration=float("nan"))


def test_move_to_nan_duration_raises() -> None:
    with pytest.raises(ValueError, match="NaN|duration"):
        core.move_to(100, 200, duration=float("nan"))


def test_click_zero_duration_accepted(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(
        core.pyautogui, "click", lambda x, y, duration, button: calls.append((x, y, duration, button))
    )
    core.click(100, 200, duration=0.0)
    assert calls == [(100, 200, 0.0, "left")]


def test_move_to_zero_duration_accepted(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "moveTo", lambda x, y, duration: calls.append((x, y, duration)))
    core.move_to(100, 200, duration=0.0)
    assert calls == [(100, 200, 0.0)]


def test_mixed_dpi_fail_fast(monkeypatch) -> None:
    """CoordinateSystem should raise when monitors have mismatched scale ratios."""
    cs = core.CoordinateSystem.__new__(core.CoordinateSystem)
    cs.primary_left = 0
    cs.primary_top = 0
    cs.primary_width_phys = 1920
    cs.primary_height_phys = 1080
    cs.logical_width = 1920
    cs.logical_height = 1080
    cs.monitors = list(FakeMss.monitors[1:])

    def mock_logical_sizes(self) -> list[dict[str, int]]:
        return [
            {"left": 0, "top": 0, "width": 1920, "height": 1080},  # primary
            {"left": 1920, "top": 0, "width": 1280, "height": 720},  # 150% scaled
        ]

    monkeypatch.setattr(
        core.CoordinateSystem, "_get_monitor_logical_sizes", mock_logical_sizes
    )
    monkeypatch.setattr(core.mss, "MSS", FakeMss)

    with pytest.raises(RuntimeError, match="Mixed-DPI"):
        cs._validate_uniform_scaling()


def test_uniform_scaling_passes(monkeypatch) -> None:
    """CoordinateSystem should not raise when all monitors share the same scale."""
    cs = core.CoordinateSystem.__new__(core.CoordinateSystem)
    cs.primary_left = 0
    cs.primary_top = 0
    cs.primary_width_phys = 1920
    cs.primary_height_phys = 1080
    cs.logical_width = 1920
    cs.logical_height = 1080
    cs.monitors = list(FakeMss.monitors[1:])

    def mock_logical_sizes(self) -> list[dict[str, int]]:
        return [
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": 1920, "top": 0, "width": 1920, "height": 1080},
        ]

    monkeypatch.setattr(
        core.CoordinateSystem, "_get_monitor_logical_sizes", mock_logical_sizes
    )
    monkeypatch.setattr(core.mss, "MSS", FakeMss)

    # Should complete without raising.
    cs._validate_uniform_scaling()


def test_click_invalid_button_raises() -> None:
    with pytest.raises(ValueError, match="Invalid mouse button"):
        core.click(100, 200, button="side")


def test_mouse_down_moves_and_presses(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "moveTo", lambda x, y: calls.append(("move", x, y)))
    monkeypatch.setattr(core.pyautogui, "mouseDown", lambda button: calls.append(("down", button)))
    core.mouse_down(100, 200, button="right")
    assert calls == [("move", 100, 200), ("down", "right")]


def test_mouse_up_without_coords_releases(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "position", lambda: (100, 100))
    monkeypatch.setattr(core.pyautogui, "mouseUp", lambda button: calls.append(("up", button)))
    core.mouse_up(button="left")
    assert calls == [("up", "left")]


def test_mouse_up_with_coords_moves_and_releases(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "moveTo", lambda x, y: calls.append(("move", x, y)))
    monkeypatch.setattr(core.pyautogui, "mouseUp", lambda button: calls.append(("up", button)))
    core.mouse_up(300, 400, button="right")
    assert calls == [("move", 300, 400), ("up", "right")]


def test_drag_moves_holds_and_releases(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "moveTo", lambda x, y, duration=0: calls.append(("move", x, y, duration)))
    monkeypatch.setattr(core.pyautogui, "mouseDown", lambda button: calls.append(("down", button)))
    monkeypatch.setattr(core.pyautogui, "mouseUp", lambda button: calls.append(("up", button)))
    core.drag(10, 20, 110, 120, duration=0.5, button="left")
    assert calls == [
        ("move", 10, 20, 0),
        ("down", "left"),
        ("move", 110, 120, 0.5),
        ("up", "left"),
    ]


def test_scroll_direction_up(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "position", lambda: (100, 100))
    monkeypatch.setattr(core.pyautogui, "scroll", lambda amount, x=None, y=None: calls.append((amount, x, y)))
    core.scroll(direction="up", clicks=5)
    assert calls == [(5, None, None)]


def test_scroll_direction_down(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "position", lambda: (100, 100))
    monkeypatch.setattr(core.pyautogui, "scroll", lambda amount, x=None, y=None: calls.append((amount, x, y)))
    core.scroll(direction="down", clicks=2)
    assert calls == [(-2, None, None)]


def test_scroll_amount_and_direction_conflict() -> None:
    with pytest.raises(ValueError, match="amount or direction"):
        core.scroll(amount=3, direction="up")


def test_key_down_up_and_press(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "position", lambda: (100, 100))
    monkeypatch.setattr(core.pyautogui, "keyDown", lambda key: calls.append(("down", key)))
    monkeypatch.setattr(core.pyautogui, "keyUp", lambda key: calls.append(("up", key)))
    monkeypatch.setattr(core.pyautogui, "press", lambda key: calls.append(("press", key)))
    core.key_down("ctrl")
    core.key_up("ctrl")
    core.press_key("enter")
    assert calls == [("down", "ctrl"), ("up", "ctrl"), ("press", "enter")]


@pytest.mark.parametrize(
    "invoke",
    [
        lambda: core.click(2000, 500),
        lambda: core.double_click(2000, 500),
        lambda: core.move_to(2000, 500),
        lambda: core.mouse_down(2000, 500),
        lambda: core.mouse_up(2000, 500),
        lambda: core.drag(100, 100, 2000, 500),
        lambda: core.drag(2000, 500, 100, 100),
        lambda: core.scroll(amount=1, x=2000, y=500),
    ],
)
def test_public_coordinate_input_primitives_reject_secondary_monitor(
    monkeypatch, invoke
) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "click", lambda *args, **kwargs: calls.append("click"))
    monkeypatch.setattr(
        core.pyautogui, "doubleClick", lambda *args, **kwargs: calls.append("doubleClick")
    )
    monkeypatch.setattr(core.pyautogui, "moveTo", lambda *args, **kwargs: calls.append("moveTo"))
    monkeypatch.setattr(
        core.pyautogui, "mouseDown", lambda *args, **kwargs: calls.append("mouseDown")
    )
    monkeypatch.setattr(core.pyautogui, "mouseUp", lambda *args, **kwargs: calls.append("mouseUp"))
    monkeypatch.setattr(core.pyautogui, "scroll", lambda *args, **kwargs: calls.append("scroll"))

    with pytest.raises(core.SafetyError, match="primary"):
        invoke()

    assert calls == []


@pytest.mark.parametrize(
    "invoke",
    [
        lambda: core.scroll(amount=1),
        lambda: core.type_text("safe"),
        lambda: core.key_combo("ctrl", "c"),
        lambda: core.mouse_up(),
        lambda: core.key_down("ctrl"),
        lambda: core.key_up("ctrl"),
        lambda: core.press_key("enter"),
    ],
)
def test_public_current_cursor_input_primitives_reject_secondary_monitor(
    monkeypatch, invoke
) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "position", lambda: (2000, 500))
    monkeypatch.setattr(core.pyautogui, "scroll", lambda *args, **kwargs: calls.append("scroll"))
    monkeypatch.setattr(core.pyautogui, "typewrite", lambda *args, **kwargs: calls.append("typewrite"))
    monkeypatch.setattr(core.pyautogui, "hotkey", lambda *args, **kwargs: calls.append("hotkey"))
    monkeypatch.setattr(core.pyautogui, "mouseUp", lambda *args, **kwargs: calls.append("mouseUp"))
    monkeypatch.setattr(core.pyautogui, "keyDown", lambda *args, **kwargs: calls.append("keyDown"))
    monkeypatch.setattr(core.pyautogui, "keyUp", lambda *args, **kwargs: calls.append("keyUp"))
    monkeypatch.setattr(core.pyautogui, "press", lambda *args, **kwargs: calls.append("press"))

    with pytest.raises(core.SafetyError, match="primary"):
        invoke()

    assert calls == []
