"""Tests for composite GUI automation helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from computer_use import composite as composite_mod
from computer_use.safety import SafetyError


@pytest.fixture(autouse=True)
def _reset_uia_module():
    original_uia = composite_mod.find_control.__module__
    yield


@pytest.fixture(autouse=True)
def _patch_safety(monkeypatch):
    """Stub coordinate/window safety checks so tests stay deterministic."""
    monkeypatch.setattr(composite_mod, "get_coordinate_system", lambda: SimpleNamespace(
        get_screen_size=lambda: SimpleNamespace(width=1920, height=1080),
        monitors=[{"left": 0, "top": 0, "width": 1920, "height": 1080}],
    ))
    monkeypatch.setattr(composite_mod, "validate_coordinate", lambda *a, **k: None)
    monkeypatch.setattr(composite_mod, "check_target_window", lambda *a, **k: None)


def _make_control_result(name: str = "OK", x: int = 100, y: int = 200) -> dict:
    return {
        "found": True,
        "name": name,
        "control_type": "Button",
        "class_name": "Btn",
        "process_name": "app.exe",
        "center": {"x": x, "y": y},
    }


def test_click_by_text_hits_and_clicks(monkeypatch) -> None:
    find_calls = []
    click_calls = []

    def fake_find_control(**kwargs):
        find_calls.append(kwargs)
        return _make_control_result("Submit", x=150, y=250)

    monkeypatch.setattr(composite_mod, "find_control", fake_find_control)
    monkeypatch.setattr(composite_mod, "click", lambda x, y, duration, button: click_calls.append((x, y, duration, button)))

    result = composite_mod.click_by_text("Submit", match="exact", scope="foreground", duration=0.3, button="right")

    assert result["clicked"] is True
    assert result["text"] == "Submit"
    assert result["x"] == 150
    assert result["y"] == 250
    assert result["button"] == "right"
    assert result["duration"] == 0.3
    assert result["mode"] == "uia"
    assert click_calls == [(150, 250, 0.3, "right")]
    assert find_calls == [
        {"name": "Submit", "scope": "foreground", "match": "exact", "sensitive_check": False}
    ]


def test_click_by_text_not_found_returns_candidates(monkeypatch) -> None:
    def fake_find_control(**kwargs):
        return {"found": False, "uia_available": True, "blocked": False, "reason": "not_found"}

    monkeypatch.setattr(composite_mod, "find_control", fake_find_control)

    result = composite_mod.click_by_text("Missing")

    assert result["error"] == "ui_not_found"
    assert result["text"] == "Missing"
    assert result["match"] == "contains"


def test_open_menu_clicks_path(monkeypatch) -> None:
    find_calls = []
    click_calls = []
    sleep_calls = []

    def fake_find_control(**kwargs):
        find_calls.append(kwargs)
        name = kwargs["name"]
        return _make_control_result(name, x=50 + len(find_calls) * 10, y=100)

    monkeypatch.setattr(composite_mod, "find_control", fake_find_control)
    monkeypatch.setattr(composite_mod, "click", lambda x, y, duration, button: click_calls.append((x, y, duration, button)))
    monkeypatch.setattr(composite_mod, "time", SimpleNamespace(sleep=lambda d: sleep_calls.append(d)))

    result = composite_mod.open_menu(["Tools", "Registry Cleaner"], interval=0.1)

    assert result["opened"] is True
    assert result["path"] == ["Tools", "Registry Cleaner"]
    assert len(click_calls) == 2
    assert len(sleep_calls) == 2
    assert sleep_calls == [0.1, 0.1]


def test_open_menu_stops_on_missing_item(monkeypatch) -> None:
    def fake_find_control(**kwargs):
        if kwargs["name"] == "Tools":
            return _make_control_result("Tools", x=50, y=100)
        return {"found": False, "uia_available": True, "blocked": False, "reason": "not_found"}

    click_calls = []
    monkeypatch.setattr(composite_mod, "find_control", fake_find_control)
    monkeypatch.setattr(composite_mod, "click", lambda x, y, duration, button: click_calls.append((x, y)))
    monkeypatch.setattr(composite_mod, "time", SimpleNamespace(sleep=lambda d: None))

    result = composite_mod.open_menu(["Tools", "Missing"])

    assert result["error"] == "ui_not_found"
    assert result["attempted"] == "Missing"
    assert result["clicked"] == ["Tools"]
    assert len(click_calls) == 1


def test_fill_form_fills_all_fields(monkeypatch) -> None:
    find_calls = []
    click_calls = []
    type_calls = []

    def fake_find_control(**kwargs):
        find_calls.append(kwargs)
        name = kwargs["name"]
        return _make_control_result(name, x=100, y=200)

    monkeypatch.setattr(composite_mod, "find_control", fake_find_control)
    monkeypatch.setattr(composite_mod, "click", lambda x, y, duration, button="left": click_calls.append((x, y)))
    monkeypatch.setattr(composite_mod, "type_text", lambda text, interval: type_calls.append((text, interval)))

    result = composite_mod.fill_form(
        [
            {"name": "Username", "value": "alice"},
            {"name": "Password", "value": "secret"},
        ],
        duration=0.3,
        type_interval=0.02,
    )

    assert result["filled"] is True
    assert len(result["fields"]) == 2
    assert type_calls == [("alice", 0.02), ("secret", 0.02)]


def test_fill_form_blocks_dangerous_text(monkeypatch) -> None:
    def fake_find_control(**kwargs):
        return _make_control_result(kwargs["name"])

    monkeypatch.setattr(composite_mod, "find_control", fake_find_control)

    with pytest.raises(SafetyError):
        composite_mod.fill_form([{"name": "Command", "value": "rm -rf /"}])


def test_scroll_until_finds_target(monkeypatch) -> None:
    find_calls = []
    scroll_calls = []

    def fake_find_control(**kwargs):
        find_calls.append(kwargs)
        if len(find_calls) >= 3:
            return _make_control_result("Target", x=100, y=500)
        return {"found": False, "uia_available": True, "blocked": False, "reason": "not_found"}

    monkeypatch.setattr(composite_mod, "find_control", fake_find_control)
    monkeypatch.setattr(composite_mod, "scroll", lambda direction, clicks: scroll_calls.append((direction, clicks)))
    monkeypatch.setattr(composite_mod, "time", SimpleNamespace(sleep=lambda d: None))

    result = composite_mod.scroll_until("Target", direction="down", max_attempts=5, clicks=2, interval=0)

    assert result["found"] is True
    assert result["attempts"] == 3
    assert result["target_text"] == "Target"
    assert len(scroll_calls) == 2


def test_scroll_until_reaches_max_attempts(monkeypatch) -> None:
    def fake_find_control(**kwargs):
        return {"found": False, "uia_available": True, "blocked": False, "reason": "not_found"}

    scroll_calls = []
    monkeypatch.setattr(composite_mod, "find_control", fake_find_control)
    monkeypatch.setattr(composite_mod, "scroll", lambda direction, clicks: scroll_calls.append((direction, clicks)))
    monkeypatch.setattr(composite_mod, "time", SimpleNamespace(sleep=lambda d: None))

    result = composite_mod.scroll_until("Target", max_attempts=3, clicks=1)

    assert result["error"] == "ui_not_found"
    assert result["attempts"] == 3
    assert len(scroll_calls) == 3


def test_click_by_uid_delegates_to_snapshot(monkeypatch) -> None:
    snapshot = {"controls": []}

    def fake_click_by_uid(uid, snap, duration=0.2, button="left"):
        return {"clicked": True, "uid": uid, "duration": duration, "button": button}

    import computer_use.snapshot as snapshot_module
    monkeypatch.setattr(snapshot_module, "click_by_uid", fake_click_by_uid)

    result = composite_mod.click_by_uid("abc", snapshot, duration=0.4, button="middle")

    assert result == {"clicked": True, "uid": "abc", "duration": 0.4, "button": "middle"}
