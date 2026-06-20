"""Manual smoke tests against a real Windows desktop.

Set ``COMPUTER_USE_RUN_MANUAL=1`` to run these tests. They will launch Notepad,
so run them only when the desktop is idle and no sensitive windows are visible.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from computer_use.mcp_server import _call_tool


pytestmark = [pytest.mark.manual, pytest.mark.timeout(60)]


def test_notepad_screenshot_returns_valid_path(notepad_session) -> None:
    result = _call_tool("screenshot", {"monitor": 1})
    data = json.loads(result)

    assert data["screenshot_taken"] is True
    assert "saved_path" in data
    saved = Path(data["saved_path"])
    assert saved.exists()
    assert saved.stat().st_size > 0


def test_notepad_foreground_snapshot_returns_controls(notepad_session) -> None:
    result = _call_tool("get_ui_snapshot", {"scope": "foreground"})
    data = json.loads(result)

    assert "controls" in data
    assert isinstance(data["controls"], list)
    assert len(data["controls"]) > 0
    assert data.get("foreground_window", {}).get("name") is not None
