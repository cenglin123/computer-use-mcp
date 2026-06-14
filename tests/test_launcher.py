"""Tests for the launcher module using mocked Windows Shell objects."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from computer_use import launcher
from computer_use.config import load_config, reset_config_cache


@pytest.fixture(autouse=True)
def _reset_config() -> None:
    reset_config_cache()
    yield
    reset_config_cache()


_CSIDL_STARTMENU = launcher._CSIDL_STARTMENU
_CSIDL_COMMON_STARTMENU = launcher._CSIDL_COMMON_STARTMENU
_CSIDL_DESKTOPDIRECTORY = launcher._CSIDL_DESKTOPDIRECTORY
_CSIDL_COMMON_DESKTOPDIRECTORY = launcher._CSIDL_COMMON_DESKTOPDIRECTORY


def _make_item(name: str, path: str) -> SimpleNamespace:
    """Build a fake Shell.Application item."""
    item = SimpleNamespace()
    item.Name = name
    item.Path = path
    item.InvokeVerb = MagicMock()
    return item


def _make_namespace(items: list[Any]) -> SimpleNamespace:
    """Build a fake Shell.Application Namespace."""
    ns = SimpleNamespace()
    ns.Items = lambda: items
    return ns


def _make_shell(mappings: dict[int, list[Any]]) -> SimpleNamespace:
    """Build a fake Shell.Application dispatch."""
    shell = SimpleNamespace()

    def namespace(folder_id: int) -> Any:
        return _make_namespace(mappings.get(folder_id, []))

    shell.Namespace = namespace
    return shell


def _make_wscript(targets: dict[str, str]) -> SimpleNamespace:
    """Build a fake WScript.Shell dispatch."""
    wscript = SimpleNamespace()

    def create_shortcut(path: str) -> Any:
        shortcut = SimpleNamespace()
        shortcut.TargetPath = targets.get(path)
        return shortcut

    wscript.CreateShortcut = create_shortcut
    return wscript


def _allow(commands: list[str]) -> None:
    """Set the allowed_commands whitelist in the cached config."""
    config = load_config()
    config["safety"]["allowed_commands"] = commands


class TestLaunchAppNoWin32Com:
    def test_returns_unavailable_when_win32com_missing(self) -> None:
        with patch.object(launcher, "_get_shell_dispatch", return_value=None):
            result = launcher.launch_app("Notepad")
        assert result == {"launched": False, "error": "Shell automation unavailable"}


class TestLaunchAppMatching:
    def test_launch_allowed_app(self) -> None:
        _allow(["C:/Program Files/App/app.exe"])

        item = _make_item("App", "C:/Start/App.lnk")
        shell = _make_shell({_CSIDL_STARTMENU: [item]})
        wscript = _make_wscript({"C:/Start/App.lnk": "C:/Program Files/App/app.exe"})

        with patch.object(launcher, "_get_shell_dispatch", return_value=shell), \
             patch.object(launcher, "_get_wscript_shell", return_value=wscript):
            result = launcher.launch_app("App")

        assert result == {
            "launched": True,
            "name": "App",
            "target_path": "C:/Program Files/App/app.exe",
        }
        item.InvokeVerb.assert_called_once_with("Open")

    def test_exact_match_wins_over_contains(self) -> None:
        _allow(["C:/Apps/Exact.exe"])

        exact = _make_item("App", "C:/Start/App.lnk")
        contains = _make_item("My App", "C:/Start/MyApp.lnk")
        shell = _make_shell({_CSIDL_DESKTOPDIRECTORY: [exact, contains]})
        wscript = _make_wscript({
            "C:/Start/App.lnk": "C:/Apps/Exact.exe",
            "C:/Start/MyApp.lnk": "C:/Apps/MyApp.exe",
        })

        with patch.object(launcher, "_get_shell_dispatch", return_value=shell), \
             patch.object(launcher, "_get_wscript_shell", return_value=wscript):
            result = launcher.launch_app("App")

        assert result["launched"] is True
        assert result["target_path"] == "C:/Apps/Exact.exe"
        exact.InvokeVerb.assert_called_once_with("Open")
        contains.InvokeVerb.assert_not_called()

    def test_contains_fallback_when_no_exact(self) -> None:
        _allow(["C:/Apps/MyApp.exe"])

        item = _make_item("My App", "C:/Start/MyApp.lnk")
        shell = _make_shell({_CSIDL_COMMON_STARTMENU: [item]})
        wscript = _make_wscript({"C:/Start/MyApp.lnk": "C:/Apps/MyApp.exe"})

        with patch.object(launcher, "_get_shell_dispatch", return_value=shell), \
             patch.object(launcher, "_get_wscript_shell", return_value=wscript):
            result = launcher.launch_app("App")

        assert result == {
            "launched": True,
            "name": "My App",
            "target_path": "C:/Apps/MyApp.exe",
        }

    def test_multiple_matches_returns_list(self) -> None:
        _allow(["C:/Apps/A.exe", "C:/Apps/B.exe"])

        a = _make_item("App A", "C:/Start/A.lnk")
        b = _make_item("App B", "C:/Start/B.lnk")
        shell = _make_shell({_CSIDL_DESKTOPDIRECTORY: [a, b]})
        wscript = _make_wscript({
            "C:/Start/A.lnk": "C:/Apps/A.exe",
            "C:/Start/B.lnk": "C:/Apps/B.exe",
        })

        with patch.object(launcher, "_get_shell_dispatch", return_value=shell), \
             patch.object(launcher, "_get_wscript_shell", return_value=wscript):
            result = launcher.launch_app("App")

        assert result["launched"] is False
        assert "matches" in result
        assert len(result["matches"]) == 2

    def test_no_match(self) -> None:
        shell = _make_shell({_CSIDL_STARTMENU: []})
        wscript = _make_wscript({})

        with patch.object(launcher, "_get_shell_dispatch", return_value=shell), \
             patch.object(launcher, "_get_wscript_shell", return_value=wscript):
            result = launcher.launch_app("Missing")

        assert result == {"launched": False, "error": "No application named 'Missing' found"}

    def test_blocked_when_not_allowed(self) -> None:
        _allow(["C:/Allowed/allowed.exe"])

        item = _make_item("Bad", "C:/Start/Bad.lnk")
        shell = _make_shell({_CSIDL_STARTMENU: [item]})
        wscript = _make_wscript({"C:/Start/Bad.lnk": "C:/Bad/bad.exe"})

        with patch.object(launcher, "_get_shell_dispatch", return_value=shell), \
             patch.object(launcher, "_get_wscript_shell", return_value=wscript):
            result = launcher.launch_app("Bad")

        assert result["launched"] is False
        assert "error" in result
        assert "allowed_commands" in result["error"]
        item.InvokeVerb.assert_not_called()

    def test_blocked_when_sensitive_process(self) -> None:
        _allow(["C:/Windows/System32/certmgr.exe"])

        item = _make_item("Certs", "C:/Start/Certs.lnk")
        shell = _make_shell({_CSIDL_DESKTOPDIRECTORY: [item]})
        wscript = _make_wscript({"C:/Start/Certs.lnk": "C:/Windows/System32/certmgr.exe"})

        with patch.object(launcher, "_get_shell_dispatch", return_value=shell), \
             patch.object(launcher, "_get_wscript_shell", return_value=wscript):
            result = launcher.launch_app("Certs")

        assert result["launched"] is False
        assert "error" in result
        item.InvokeVerb.assert_not_called()
