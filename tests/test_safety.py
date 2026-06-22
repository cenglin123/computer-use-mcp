"""Tests for safety enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from computer_use.config import load_config, reset_config_cache
from computer_use.safety import (
    SafetyError,
    check_target_window,
    contains_shell_metacharacters,
    is_allowed_command,
    is_dangerous_text,
    is_path_deletion,
    validate_coordinate,
    validate_monitor_index,
    validate_text_input,
)


@pytest.fixture(autouse=True)
def _reset_config():
    reset_config_cache()
    yield
    reset_config_cache()


@pytest.mark.parametrize(
    "text,expected",
    [
        ("rm -rf /", True),
        ("del /f /s /q file.txt", True),
        ("format C:", True),
        ("shutdown /s", True),
        ("hello world", False),
        ("echo hello", False),
    ],
)
def test_is_dangerous_text(text: str, expected: bool) -> None:
    assert is_dangerous_text(text) is expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("del file.txt", True),
        ("rm -f file.txt", True),
        ("rmdir dir", True),
        ("type hello", False),
    ],
)
def test_is_path_deletion(text: str, expected: bool) -> None:
    assert is_path_deletion(text) is expected


def test_validate_text_input_blocks_dangerous() -> None:
    with pytest.raises(SafetyError):
        validate_text_input("rm -rf /")


def test_validate_text_input_allows_normal() -> None:
    validate_text_input("hello world")


def test_check_target_window_allows_safe_password_control() -> None:
    check_target_window(
        process_name="app.exe",
        class_name="Edit",
        control_type="Edit",
        is_password=True,
    )


def test_validate_coordinate_inside() -> None:
    validate_coordinate(100, 200, 1920, 1080)


def test_validate_coordinate_outside() -> None:
    with pytest.raises(SafetyError):
        validate_coordinate(2000, 2000, 1920, 1080)


def test_validate_coordinate_off_by_one() -> None:
    # Coordinates equal to width/height are out of bounds for zero-indexed screens.
    with pytest.raises(SafetyError):
        validate_coordinate(1920, 1080, 1920, 1080)


def test_validate_coordinate_restricts_input_to_primary_screen() -> None:
    monitors = [
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": 1920, "top": 9, "width": 1920, "height": 1080},
    ]
    # Inside primary monitor.
    validate_coordinate(100, 200, 3840, 1089, monitors=monitors)
    # Input on a secondary monitor is outside the supported primary-screen boundary.
    with pytest.raises(SafetyError, match="primary"):
        validate_coordinate(2000, 500, 3840, 1089, monitors=monitors)
    with pytest.raises(SafetyError, match="primary"):
        validate_coordinate(2000, 5, 3840, 1089, monitors=monitors)
    with pytest.raises(SafetyError, match="primary"):
        validate_coordinate(4000, 0, 3840, 1089, monitors=monitors)


def test_validate_monitor_index() -> None:
    validate_monitor_index(0, 2)
    validate_monitor_index(1, 2)
    validate_monitor_index(2, 2)

    with pytest.raises(SafetyError):
        validate_monitor_index(-1, 2)
    with pytest.raises(SafetyError):
        validate_monitor_index(3, 2)
    with pytest.raises(SafetyError):
        validate_monitor_index("1", 2)


@pytest.mark.parametrize(
    "command,allowed,expected",
    [
        ("notepad.exe", ["notepad.exe"], True),
        ("NOTEPAD.EXE", ["notepad.exe"], True),
        ("calc.exe", ["notepad.exe"], False),
        ("notepad.exe", [], False),
        ("/usr/bin/git", ["/usr/bin/git"], True),
    ],
)
def test_is_allowed_command(command: str, allowed: list[str], expected: bool) -> None:
    reset_config_cache()
    config = load_config()
    config["safety"]["allowed_commands"] = allowed
    assert is_allowed_command(command) is expected


def test_is_allowed_command_path_object(monkeypatch) -> None:
    reset_config_cache()
    config = load_config()
    config["safety"]["allowed_commands"] = ["C:/Program Files/App/app.exe"]
    assert is_allowed_command(Path("C:/Program Files/App/app.exe")) is True
    assert is_allowed_command("D:/Other/app.exe") is False
    assert is_allowed_command("app.exe") is False
    assert is_allowed_command("other.exe") is False


@pytest.mark.parametrize(
    "text,expected",
    [
        ("cmd.exe /c echo hello", False),
        ("notepad.exe && calc.exe", True),
        ("cmd | more", True),
        ("cmd ; calc", True),
        ("echo > file.txt", True),
        ("echo < file.txt", True),
        ("echo >> file.txt", True),
        ("echo ^hello", True),
        ("echo %PATH%", True),
        ("echo $(date)", True),
        ("echo `date`", True),
        ("echo hello\nworld", True),
        ("echo hello\rworld", True),
        ("notepad.exe", False),
        ("C:/Program Files/App/app.exe", False),
    ],
)
def test_contains_shell_metacharacters(text: str, expected: bool) -> None:
    assert contains_shell_metacharacters(text) is expected


# --- New tests: runtime permission integration ---

def test_is_allowed_command_with_runtime_once_grant():
    from computer_use.runtime_permissions import (
        grant_command_permission,
        clear_runtime_permissions,
    )
    reset_config_cache()
    config = load_config()
    config["safety"]["allowed_commands"] = []  # nothing in permanent whitelist
    grant_command_permission("C:/app/special.exe", "once")
    assert is_allowed_command("C:/app/special.exe") is True
    clear_runtime_permissions()


def test_is_allowed_command_with_runtime_session_grant():
    from computer_use.runtime_permissions import (
        grant_command_permission,
        clear_runtime_permissions,
    )
    reset_config_cache()
    config = load_config()
    config["safety"]["allowed_commands"] = []
    grant_command_permission("custom-tool.exe", "session")
    assert is_allowed_command("custom-tool.exe") is True
    clear_runtime_permissions()


def test_check_target_window_with_runtime_exception():
    from computer_use.runtime_permissions import (
        grant_window_exception,
        clear_runtime_permissions,
    )
    grant_window_exception(process_name="saplogon.exe", class_name="#32770", level="once")
    # Should not raise
    check_target_window("saplogon.exe", "#32770", None)
    clear_runtime_permissions()


def test_check_target_window_still_blocks_without_exception():
    with pytest.raises(SafetyError):
        check_target_window("saplogon.exe", "#32770", None)


def test_check_target_window_still_blocks_hardcoded_sensitive_process():
    # keepass.exe is in the hardcoded sensitive list — runtime exception
    # should NOT override hardcoded sensitive processes.
    from computer_use.safety import SensitiveProcessError
    from computer_use.runtime_permissions import (
        grant_window_exception,
        clear_runtime_permissions,
    )
    grant_window_exception(process_name="keepass.exe", level="session")
    with pytest.raises(SensitiveProcessError):
        check_target_window("keepass.exe", None, None)
    clear_runtime_permissions()
