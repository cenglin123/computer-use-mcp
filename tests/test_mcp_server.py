"""Tests for MCP server tool dispatch."""

from __future__ import annotations

import json

import pytest

from computer_use.mcp_server import TOOLS, _call_tool


def test_tools_listed() -> None:
    names = {t.name for t in TOOLS}
    assert names == {
        "screenshot",
        "get_screen_size",
        "get_monitors",
        "click",
        "move_to",
        "scroll",
        "type",
        "key_combo",
    }


def test_get_screen_size() -> None:
    result = _call_tool("get_screen_size", {})
    data = json.loads(result)
    assert data["width"] > 0
    assert data["height"] > 0


def test_get_monitors() -> None:
    result = _call_tool("get_monitors", {})
    data = json.loads(result)
    assert isinstance(data, list)
    assert len(data) >= 1
    for mon in data:
        assert "index" in mon
        assert "primary" in mon
        assert "left" in mon
        assert "top" in mon
        assert "width" in mon
        assert "height" in mon


def test_screenshot_returns_base64() -> None:
    result = _call_tool("screenshot", {})
    # Should be a base64 string.
    assert isinstance(result, str)
    assert len(result) > 100


def test_screenshot_with_monitor() -> None:
    result = _call_tool("screenshot", {"monitor": 1})
    assert isinstance(result, str)
    assert len(result) > 100


def test_screenshot_invalid_monitor() -> None:
    result = _call_tool("screenshot", {"monitor": 99})
    data = json.loads(result)
    assert "error" in data or "out of range" in result


def test_type_blocks_dangerous() -> None:
    result = _call_tool("type", {"text": "rm -rf /"})
    data = json.loads(result)
    assert "error" in data or "Refusing" in result


def test_click_out_of_bounds() -> None:
    result = _call_tool("click", {"x": 99999, "y": 99999})
    data = json.loads(result)
    assert "error" in data or "outside" in result


def test_click_gap_region() -> None:
    # Virtual screen width is required; the exact gap depends on the host layout.
    # We first query size, then pick a point that is outside any monitor but
    # inside the virtual screen bounding box. If only one monitor is present,
    # this test is skipped because there is no gap.
    size = json.loads(_call_tool("get_screen_size", {}))
    monitors = json.loads(_call_tool("get_monitors", {}))
    if len(monitors) <= 1:
        pytest.skip("Need at least two monitors to test gap rejection.")

    # Pick x beyond the right edge of the primary monitor but within virtual width,
    # and y=0 (assuming no monitor extends there).
    primary = next((m for m in monitors if m["primary"]), monitors[0])
    gap_x = primary["left"] + primary["width"]
    gap_y = 0
    result = _call_tool("click", {"x": gap_x, "y": gap_y})
    data = json.loads(result)
    assert "error" in data or "gap" in result


def test_click_accepts_duration(monkeypatch) -> None:
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(server, "click", lambda x, y, duration: calls.append((x, y, duration)))
    result = _call_tool("click", {"x": 100, "y": 200, "duration": 0.5})
    data = json.loads(result)
    assert data["duration"] == 0.5
    assert calls == [(100, 200, 0.5)]


def test_move_to_accepts_duration(monkeypatch) -> None:
    import computer_use.mcp_server as server

    calls = []
    monkeypatch.setattr(server, "move_to", lambda x, y, duration: calls.append((x, y, duration)))
    result = _call_tool("move_to", {"x": 100, "y": 200, "duration": 0.8})
    data = json.loads(result)
    assert data["duration"] == 0.8
    assert calls == [(100, 200, 0.8)]
