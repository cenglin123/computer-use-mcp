"""Tests for UI Automation helpers using mocked control trees."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from computer_use import ui_automation as uia_mod
from computer_use.safety import SafetyError


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
        automation_id: str = "",
        control_type_name: str = "",
        class_name: str = "",
        process_id: int = 1234,
        is_password: bool = False,
        rect: _FakeRect | None = None,
        children: list[_FakeControl] | None = None,
        exists: bool = True,
        enabled: bool = True,
        visible: bool = True,
    ) -> None:
        self.Name = name
        self.AutomationId = automation_id
        self.ControlTypeName = control_type_name
        self.ClassName = class_name
        self.ProcessId = process_id
        self.IsPassword = is_password
        self.BoundingRectangle = rect or _FakeRect(0, 0, 100, 20)
        self.Exists = exists
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
    original_uia = uia_mod.uia
    yield
    uia_mod.uia = original_uia


def _tree() -> _FakeControl:
    return _FakeControl(
        name="Desktop",
        control_type_name="Pane",
        children=[
            _FakeControl(
                name="HiBit Uninstaller",
                control_type_name="Window",
                class_name="HwndWrapper",
                rect=_FakeRect(10, 10, 310, 210),
                children=[
                    _FakeControl(
                        name="Tools",
                        control_type_name="Button",
                        automation_id="toolsBtn",
                        rect=_FakeRect(20, 40, 80, 60),
                    ),
                    _FakeControl(
                        name="Registry Cleaner",
                        control_type_name="MenuItem",
                        rect=_FakeRect(20, 60, 140, 80),
                    ),
                ],
            ),
            _FakeControl(
                name="Settings",
                control_type_name="Window",
                rect=_FakeRect(320, 10, 620, 210),
            ),
        ],
    )


def test_find_control_by_name_contains() -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.find_control(name="Registry", match="contains")
    assert result["found"] is True
    assert result["name"] == "Registry Cleaner"
    assert result["control_type"] == "MenuItem"
    assert result["center"] == {"x": 80, "y": 70}


def test_find_control_exact_match() -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.find_control(name="Tools", match="exact")
    assert result["found"] is True
    assert result["name"] == "Tools"


def test_find_control_startswith() -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.find_control(name="Reg", match="startswith")
    assert result["found"] is True
    assert result["name"] == "Registry Cleaner"


def test_find_control_by_automation_id() -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.find_control(automation_id="toolsBtn")
    assert result["found"] is True
    assert result["name"] == "Tools"


def test_find_control_by_control_type() -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.find_control(control_type="Button")
    assert result["found"] is True
    assert result["name"] == "Tools"


def test_find_control_by_class_name() -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.find_control(class_name="HwndWrapper")
    assert result["found"] is True
    assert result["control_type"] == "Window"
    assert result["class_name"] == "HwndWrapper"


def test_find_control_scope_window() -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.find_control(
        name="Registry Cleaner", scope="window", window_name="HiBit"
    )
    assert result["found"] is True
    assert result["name"] == "Registry Cleaner"


def test_find_control_scope_window_missing_parent() -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.find_control(
        name="Registry Cleaner", scope="window", window_name="MissingWindow"
    )
    assert result["found"] is False
    assert result["reason"] == "parent_window_not_found"


def test_find_control_not_found() -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.find_control(name="NotThere")
    assert result["found"] is False
    assert result["reason"] == "not_found"


def test_find_control_requires_at_least_one_criterion() -> None:
    uia_mod.uia = MagicMock()
    with pytest.raises(ValueError):
        uia_mod.find_control()


def test_find_control_uia_not_available() -> None:
    uia_mod.uia = None
    result = uia_mod.find_control(name="Anything")
    assert result["found"] is False
    assert result["uia_available"] is False
    assert result["reason"] == "uia_not_available"


def test_find_control_sensitive_window_blocked(monkeypatch) -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    def fake_check(process_name, class_name, control_type):
        raise SafetyError("blocked")

    monkeypatch.setattr("computer_use.safety.check_target_window", fake_check)
    result = uia_mod.find_control(name="Tools")
    assert result["found"] is False
    assert result["blocked"] is True
    assert result["reason"] == "sensitive_window_blocked"
    assert "blocked" in result["detail"].lower() or "Refusing" in result["detail"]


def test_find_control_sensitive_check_disabled(monkeypatch) -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    calls = []

    def fake_check(process_name, class_name, control_type):
        calls.append((process_name, class_name, control_type))
        raise SafetyError("blocked")

    monkeypatch.setattr("computer_use.safety.check_target_window", fake_check)
    result = uia_mod.find_control(name="Tools", sensitive_check=False)
    assert result["found"] is True
    assert calls == []


def test_wait_for_window_found(monkeypatch) -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.wait_for_window(name="HiBit")
    assert result["present"] is True
    assert result["name"] == "HiBit Uninstaller"
    assert result["rect"] == {"left": 10, "top": 10, "right": 310, "bottom": 210}


def test_wait_for_window_not_exists(monkeypatch) -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.wait_for_window(name="Missing", exists=False, timeout=0.1)
    assert result["present"] is False
    assert result["timeout"] is False


def test_wait_for_window_timeout(monkeypatch) -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    result = uia_mod.wait_for_window(name="Missing", timeout=0.1)
    assert result["present"] is False
    assert result["timeout"] is True


def test_wait_for_control_found(monkeypatch) -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root
    uia_mod.uia.GetForegroundControl.return_value = root.GetFirstChildControl()

    result = uia_mod.wait_for_control(name="Registry")
    assert result["present"] is True
    assert result["name"] == "Registry Cleaner"
    assert result["control_type"] == "MenuItem"
    assert result["enabled"] is True
    assert result["visible"] is True


def test_wait_for_control_timeout(monkeypatch) -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root
    uia_mod.uia.GetForegroundControl.return_value = root.GetFirstChildControl()

    result = uia_mod.wait_for_control(name="Missing", timeout=0.1)
    assert result["present"] is False
    assert result["timeout"] is True


def test_wait_for_control_disabled_times_out(monkeypatch) -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root
    uia_mod.uia.GetForegroundControl.return_value = root.GetFirstChildControl()

    # The control exists but is disabled; wait_for_control should time out.
    target = root.GetFirstChildControl().GetFirstChildControl()  # "Tools"
    target.Enabled = False

    result = uia_mod.wait_for_control(name="Tools", timeout=0.1)
    assert result["present"] is False
    assert result["timeout"] is True


def test_wait_for_control_invisible_times_out(monkeypatch) -> None:
    root = _tree()
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root
    uia_mod.uia.GetForegroundControl.return_value = root.GetFirstChildControl()

    target = root.GetFirstChildControl().GetFirstChildControl()  # "Tools"
    target.Visible = False

    result = uia_mod.wait_for_control(name="Tools", timeout=0.1)
    assert result["present"] is False
    assert result["timeout"] is True


def test_inspect_point() -> None:
    target = _FakeControl(
        name="Target",
        control_type_name="Button",
        class_name="ButtonClass",
        rect=_FakeRect(10, 20, 30, 40),
    )
    fake_uia = MagicMock()
    fake_uia.ControlFromPoint.return_value = target
    uia_mod.uia = fake_uia

    with patch.object(uia_mod, "get_coordinate_system") as mock_cs:
        mock_cs.return_value.to_physical.return_value = (20, 30)
        info = uia_mod.inspect_point(20, 30)

    assert info.name == "Target"
    assert info.control_type == "Button"
    assert info.class_name == "ButtonClass"
    assert info.rect == (10, 20, 30, 40)
    assert info.center == (20, 30)


def test_inspect_point_uia_unavailable() -> None:
    uia_mod.uia = None
    info = uia_mod.inspect_point(0, 0)
    assert info.name is None
    assert info.control_type is None


def test_get_top_level_windows_in_rect_filters_visibility_and_intersection() -> None:
    root = _FakeControl(
        name="Desktop",
        control_type_name="Pane",
        children=[
            _FakeControl(
                name="Inside",
                control_type_name="Window",
                rect=_FakeRect(10, 10, 100, 100),
            ),
            _FakeControl(
                name="Outside",
                control_type_name="Window",
                rect=_FakeRect(500, 500, 600, 600),
            ),
            _FakeControl(
                name="Hidden",
                control_type_name="Window",
                rect=_FakeRect(20, 20, 80, 80),
                visible=False,
            ),
            _FakeControl(
                name="ChildPane",
                control_type_name="Pane",
                class_name="#32770",
                rect=_FakeRect(20, 20, 80, 80),
            ),
        ],
    )
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    windows = uia_mod.get_top_level_windows_in_rect((0, 0, 200, 200))

    assert windows is not None
    assert [window.name for window in windows] == ["Inside"]


def test_get_top_level_windows_in_rect_returns_none_when_uia_unavailable() -> None:
    uia_mod.uia = None

    assert uia_mod.get_top_level_windows_in_rect((0, 0, 200, 200)) is None


def test_get_top_level_windows_in_rect_returns_none_on_enumeration_error() -> None:
    root = MagicMock()
    root.GetFirstChildControl.side_effect = RuntimeError("uia failure")
    uia_mod.uia = MagicMock()
    uia_mod.uia.GetRootControl.return_value = root

    assert uia_mod.get_top_level_windows_in_rect((0, 0, 200, 200)) is None
