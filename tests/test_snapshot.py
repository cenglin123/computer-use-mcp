"""Tests for the UI snapshot module."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from computer_use import snapshot as snapshot_mod


class _FakeRect:
    def __init__(self, left: int, top: int, right: int, bottom: int) -> None:
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom


class _FakeControl:
    def __init__(
        self,
        name: str = "",
        control_type_name: str = "",
        class_name: str = "",
        native_window_handle: int = 0,
        process_id: int = 1234,
        rect: _FakeRect | None = None,
        children: list[_FakeControl] | None = None,
        enabled: bool = True,
        visible: bool = True,
    ) -> None:
        self.Name = name
        self.ControlTypeName = control_type_name
        self.ClassName = class_name
        self.NativeWindowHandle = native_window_handle
        self.ProcessId = process_id
        self.BoundingRectangle = rect or _FakeRect(0, 0, 100, 20)
        self.Enabled = enabled
        self.Visible = visible
        self._children = children or []
        self._parent: _FakeControl | None = None
        for child in self._children:
            child._parent = self

    def GetFirstChildControl(self) -> _FakeControl | None:
        return self._children[0] if self._children else None

    def GetNextSiblingControl(self) -> _FakeControl | None:
        if self._parent is None:
            return None
        siblings = self._parent._children
        try:
            idx = siblings.index(self)
        except ValueError:
            return None
        return siblings[idx + 1] if idx + 1 < len(siblings) else None


@pytest.fixture(autouse=True)
def _reset_uia_module():
    """Restore uia module state after each test."""
    original_uia = snapshot_mod.uia
    yield
    snapshot_mod.uia = original_uia


@pytest.fixture(autouse=True)
def _patch_safety(monkeypatch):
    """Stub coordinate/window safety checks so tests stay deterministic."""
    monkeypatch.setattr(snapshot_mod, "get_coordinate_system", lambda: SimpleNamespace(
        get_screen_size=lambda: SimpleNamespace(width=1920, height=1080),
        monitors=[{"left": 0, "top": 0, "width": 1920, "height": 1080}],
    ))
    monkeypatch.setattr(snapshot_mod, "validate_coordinate", lambda *a, **k: None)
    monkeypatch.setattr(snapshot_mod, "check_target_window", lambda *a, **k: None)



@pytest.fixture
def _fake_tree():
    return _FakeControl(
        name="Test Window",
        control_type_name="Window",
        class_name="HwndWrapper",
        native_window_handle=42,
        rect=_FakeRect(10, 10, 210, 110),
        children=[
            _FakeControl(
                name="OK",
                control_type_name="Button",
                rect=_FakeRect(20, 20, 70, 40),
            ),
            _FakeControl(
                name="",
                control_type_name="Edit",
                rect=_FakeRect(80, 20, 180, 40),
            ),
        ],
    )


def _stub_process_name(monkeypatch) -> None:
    monkeypatch.setattr(snapshot_mod, "_get_process_name", lambda _control: "test.exe")


def test_build_uid_is_deterministic() -> None:
    uid1 = snapshot_mod._build_uid(42, '/Window[0]"Test"')
    uid2 = snapshot_mod._build_uid(42, '/Window[0]"Test"')
    assert uid1 == uid2
    assert isinstance(uid1, str)
    assert uid1


def test_build_uid_differs_for_different_inputs() -> None:
    uid1 = snapshot_mod._build_uid(42, '/Window[0]"A"')
    uid2 = snapshot_mod._build_uid(43, '/Window[0]"A"')
    uid3 = snapshot_mod._build_uid(42, '/Window[0]"B"')
    assert uid1 != uid2
    assert uid1 != uid3
    assert uid2 != uid3


def test_get_ui_snapshot_uia_not_available() -> None:
    snapshot_mod.uia = None
    result = snapshot_mod.get_ui_snapshot()
    assert result == {"error": "uiautomation_not_available"}


def test_get_ui_snapshot_structure(monkeypatch, _fake_tree) -> None:
    _stub_process_name(monkeypatch)
    snapshot_mod.uia = MagicMock()
    snapshot_mod.uia.GetForegroundControl.return_value = _fake_tree
    monkeypatch.setattr(snapshot_mod.pyautogui, "position", lambda: (50, 60))

    result = snapshot_mod.get_ui_snapshot()

    assert result["scope"] == "foreground"
    assert "timestamp" in result
    assert result["foreground_window"] == {"name": "Test Window", "process_name": "test.exe"}
    assert result["cursor"] == {"x": 50, "y": 60}
    assert result["truncated"] is False
    assert result["screenshot_path"] is None

    controls = result["controls"]
    assert len(controls) == 3

    root = controls[0]
    assert root["name"] == "Test Window"
    assert root["control_type"] == "Window"
    assert root["class_name"] == "HwndWrapper"
    assert root["bbox"] == {"left": 10, "top": 10, "right": 210, "bottom": 110}
    assert root["center"] == {"x": 110, "y": 60}
    assert root["process_name"] == "test.exe"
    assert root["enabled"] is True
    assert root["visible"] is True
    assert root["path"] == '/Window[0]"Test Window"'

    button = controls[1]
    assert button["name"] == "OK"
    assert button["control_type"] == "Button"
    assert button["center"] == {"x": 45, "y": 30}
    assert button["path"] == '/Window[0]"Test Window"/Button[0]"OK"'

    edit = controls[2]
    assert edit["name"] == ""
    assert edit["control_type"] == "Edit"
    assert edit["path"] == '/Window[0]"Test Window"/Edit[1]'

    # UIDs are deterministic and unique within the snapshot.
    uids = [c["uid"] for c in controls]
    assert len(set(uids)) == len(uids)


def test_get_ui_snapshot_skips_zero_area_controls(monkeypatch, _fake_tree) -> None:
    _stub_process_name(monkeypatch)
    _fake_tree._children.append(
        _FakeControl(
            name="Ghost",
            control_type_name="Button",
            rect=_FakeRect(0, 0, 0, 0),
        )
    )
    snapshot_mod.uia = MagicMock()
    snapshot_mod.uia.GetForegroundControl.return_value = _fake_tree
    monkeypatch.setattr(snapshot_mod.pyautogui, "position", lambda: (0, 0))

    result = snapshot_mod.get_ui_snapshot()
    assert len(result["controls"]) == 3
    assert all(c["name"] != "Ghost" for c in result["controls"])


def test_get_ui_snapshot_truncation(monkeypatch, _fake_tree) -> None:
    _stub_process_name(monkeypatch)
    monkeypatch.setattr(snapshot_mod, "_SCOPE_LIMITS", {"foreground": 2, "desktop": 2})
    snapshot_mod.uia = MagicMock()
    snapshot_mod.uia.GetForegroundControl.return_value = _fake_tree
    monkeypatch.setattr(snapshot_mod.pyautogui, "position", lambda: (0, 0))

    result = snapshot_mod.get_ui_snapshot()
    assert len(result["controls"]) == 2
    assert result["truncated"] is True


def test_get_ui_snapshot_invalid_scope() -> None:
    snapshot_mod.uia = MagicMock()
    with pytest.raises(ValueError, match="Invalid scope"):
        snapshot_mod.get_ui_snapshot(scope="window")


def test_get_ui_snapshot_desktop_scope(monkeypatch, _fake_tree) -> None:
    _stub_process_name(monkeypatch)
    snapshot_mod.uia = MagicMock()
    snapshot_mod.uia.GetRootControl.return_value = _fake_tree
    snapshot_mod.uia.GetForegroundControl.return_value = _fake_tree
    monkeypatch.setattr(snapshot_mod.pyautogui, "position", lambda: (0, 0))

    with pytest.warns(UserWarning, match="Desktop UI snapshots"):
        result = snapshot_mod.get_ui_snapshot(scope="desktop")

    assert result["scope"] == "desktop"
    assert len(result["controls"]) == 3


def test_get_ui_snapshot_includes_screenshot(monkeypatch, _fake_tree, tmp_path) -> None:
    _stub_process_name(monkeypatch)
    snapshot_mod.uia = MagicMock()
    snapshot_mod.uia.GetForegroundControl.return_value = _fake_tree
    monkeypatch.setattr(snapshot_mod.pyautogui, "position", lambda: (0, 0))

    saved_path = tmp_path / "shot.png"
    screenshot_calls = []

    def fake_save_screenshot(path: str, monitor: int = 0):
        screenshot_calls.append((path, monitor))
        return saved_path

    monkeypatch.setattr(snapshot_mod, "save_screenshot", fake_save_screenshot)
    monkeypatch.setattr(
        snapshot_mod,
        "get_monitors",
        lambda: [
            SimpleNamespace(index=1, primary=True, left=0, top=0, width=1920, height=1080)
        ],
    )

    result = snapshot_mod.get_ui_snapshot(include_screenshot=True, save_path=str(saved_path))
    assert result["screenshot_path"] == str(saved_path)
    assert screenshot_calls == [(str(saved_path), 1)]


def test_get_ui_snapshot_screenshot_defaults_to_trace_dir(monkeypatch, _fake_tree, tmp_path) -> None:
    _stub_process_name(monkeypatch)
    snapshot_mod.uia = MagicMock()
    snapshot_mod.uia.GetForegroundControl.return_value = _fake_tree
    monkeypatch.setattr(snapshot_mod.pyautogui, "position", lambda: (0, 0))

    monkeypatch.setattr(snapshot_mod, "save_screenshot", lambda path, monitor=0: path)
    monkeypatch.setattr(
        snapshot_mod,
        "get_monitors",
        lambda: [
            SimpleNamespace(index=1, primary=True, left=0, top=0, width=1920, height=1080)
        ],
    )

    result = snapshot_mod.get_ui_snapshot(include_screenshot=True, snapshot_dir=str(tmp_path))
    assert result["screenshot_path"].startswith(str(tmp_path))
    assert result["screenshot_path"].endswith(".png")


def test_get_ui_snapshot_screenshot_uses_trace_screenshots_dir(
    monkeypatch, tmp_path, _fake_tree
) -> None:
    import computer_use.trace as trace_module

    monkeypatch.setattr(trace_module, "trace_dir", lambda: tmp_path)
    _stub_process_name(monkeypatch)
    snapshot_mod.uia = MagicMock()
    snapshot_mod.uia.GetForegroundControl.return_value = _fake_tree
    monkeypatch.setattr(snapshot_mod.pyautogui, "position", lambda: (0, 0))
    monkeypatch.setattr(snapshot_mod, "save_screenshot", lambda path, monitor=0: path)
    monkeypatch.setattr(
        snapshot_mod,
        "get_monitors",
        lambda: [
            SimpleNamespace(index=1, primary=True, left=0, top=0, width=1920, height=1080)
        ],
    )

    result = snapshot_mod.get_ui_snapshot(
        scope="foreground",
        include_screenshot=True,
        trace_id="snapshot-trace",
    )

    assert Path(result["screenshot_path"]).parent == (
        tmp_path / "snapshot-trace" / "screenshots"
    )
    assert not (tmp_path / "snapshot-trace" / "snapshots").exists()


def test_click_by_uid_success(monkeypatch, _fake_tree) -> None:
    _stub_process_name(monkeypatch)
    snapshot_mod.uia = MagicMock()
    snapshot_mod.uia.GetForegroundControl.return_value = _fake_tree
    monkeypatch.setattr(snapshot_mod.pyautogui, "position", lambda: (0, 0))

    snapshot = snapshot_mod.get_ui_snapshot()
    target = next(c for c in snapshot["controls"] if c["name"] == "OK")

    click_calls = []
    monkeypatch.setattr(
        snapshot_mod,
        "click",
        lambda x, y, duration, button: click_calls.append((x, y, duration, button)),
    )

    result = snapshot_mod.click_by_uid(target["uid"], snapshot, duration=0.3, button="right")
    assert result == {
        "clicked": True,
        "uid": target["uid"],
        "x": 45,
        "y": 30,
        "button": "right",
        "duration": 0.3,
    }
    assert click_calls == [(45, 30, 0.3, "right")]


def test_click_by_uid_rejects_secondary_monitor_center(monkeypatch) -> None:
    from computer_use.safety import validate_coordinate

    click_calls = []
    snapshot = {
        "controls": [
            {
                "uid": "secondary",
                "center": {"x": 2000, "y": 500},
                "process_name": "safe.exe",
                "class_name": "Button",
                "control_type": "Button",
            }
        ]
    }
    monkeypatch.setattr(
        snapshot_mod,
        "get_coordinate_system",
        lambda: SimpleNamespace(
            get_screen_size=lambda: SimpleNamespace(width=3840, height=1080),
            monitors=[
                {"left": 0, "top": 0, "width": 1920, "height": 1080},
                {"left": 1920, "top": 0, "width": 1920, "height": 1080},
            ],
        ),
    )
    monkeypatch.setattr(snapshot_mod, "validate_coordinate", validate_coordinate)
    monkeypatch.setattr(
        snapshot_mod,
        "click",
        lambda *args, **kwargs: click_calls.append((args, kwargs)),
    )

    result = snapshot_mod.click_by_uid("secondary", snapshot)

    assert result["error"] == "safety_block"
    assert "primary" in result["detail"].lower()
    assert click_calls == []


def test_click_by_uid_uses_live_target_metadata(monkeypatch) -> None:
    from computer_use.safety import SafetyError
    from computer_use.ui_automation import ControlInfo

    click_calls = []
    snapshot = {
        "controls": [
            {
                "uid": "forged-safe-target",
                "center": {"x": 100, "y": 200},
                "process_name": "safe.exe",
                "class_name": "Button",
                "control_type": "Button",
            }
        ]
    }
    monkeypatch.setattr(
        snapshot_mod,
        "get_coordinate_system",
        lambda: SimpleNamespace(
            get_screen_size=lambda: SimpleNamespace(width=1920, height=1080),
            monitors=[{"left": 0, "top": 0, "width": 1920, "height": 1080}],
        ),
    )
    monkeypatch.setattr(
        snapshot_mod,
        "inspect_point",
        lambda x, y: ControlInfo(
            name="Password Manager",
            control_type="Pane",
            class_name="SensitivePane",
            process_name="keepass.exe",
            is_password=False,
            rect=None,
            center=None,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        snapshot_mod,
        "check_target_window",
        lambda process_name, class_name, control_type: (
            (_ for _ in ()).throw(SafetyError("live target is sensitive"))
            if process_name == "keepass.exe"
            else None
        ),
    )
    monkeypatch.setattr(
        snapshot_mod,
        "click",
        lambda *args, **kwargs: click_calls.append((args, kwargs)),
    )

    result = snapshot_mod.click_by_uid("forged-safe-target", snapshot)

    assert result["error"] == "safety_block"
    assert "live target is sensitive" in result["detail"]
    assert click_calls == []


def test_click_by_uid_stale() -> None:
    result = snapshot_mod.click_by_uid("no-such-uid", {"controls": []})
    assert result == {"error": "stale_uid"}


def test_click_by_uid_uses_defaults(monkeypatch, _fake_tree) -> None:
    _stub_process_name(monkeypatch)
    snapshot_mod.uia = MagicMock()
    snapshot_mod.uia.GetForegroundControl.return_value = _fake_tree
    monkeypatch.setattr(snapshot_mod.pyautogui, "position", lambda: (0, 0))

    snapshot = snapshot_mod.get_ui_snapshot()
    target = next(c for c in snapshot["controls"] if c["name"] == "OK")

    click_calls = []
    monkeypatch.setattr(
        snapshot_mod,
        "click",
        lambda x, y, duration, button: click_calls.append((x, y, duration, button)),
    )

    snapshot_mod.click_by_uid(target["uid"], snapshot)
    assert click_calls == [(45, 30, 0.2, "left")]
