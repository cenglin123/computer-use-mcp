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
    result = core.screenshot()
    # Result is a non-empty base64 PNG string.
    assert isinstance(result, str)
    assert len(result) > 100


def test_screenshot_single_monitor(monkeypatch) -> None:
    fake = FakeMss()
    monkeypatch.setattr(core.mss, "MSS", lambda: fake)
    result = core.screenshot(monitor=2)
    assert isinstance(result, str)
    assert len(result) > 100


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
    return cs


def test_click_uses_default_duration(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "click", lambda x, y, duration: calls.append((x, y, duration)))
    core.click(100, 200)
    assert calls == [(100, 200, 0.2)]


def test_click_uses_custom_duration(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(core, "get_coordinate_system", _fake_coordinate_system)
    monkeypatch.setattr(core.pyautogui, "click", lambda x, y, duration: calls.append((x, y, duration)))
    core.click(100, 200, duration=0.5)
    assert calls == [(100, 200, 0.5)]


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
    monkeypatch.setattr(core.pyautogui, "click", lambda x, y, duration: calls.append((x, y, duration)))
    core.click(100, 200, duration=0.0)
    assert calls == [(100, 200, 0.0)]


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
