"""Tests for safety enforcement."""

from __future__ import annotations

import pytest

from computer_use.safety import (
    SafetyError,
    is_dangerous_text,
    is_path_deletion,
    validate_coordinate,
    validate_monitor_index,
    validate_text_input,
)


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


def test_validate_coordinate_inside() -> None:
    validate_coordinate(100, 200, 1920, 1080)


def test_validate_coordinate_outside() -> None:
    with pytest.raises(SafetyError):
        validate_coordinate(2000, 2000, 1920, 1080)


def test_validate_coordinate_off_by_one() -> None:
    # Coordinates equal to width/height are out of bounds for zero-indexed screens.
    with pytest.raises(SafetyError):
        validate_coordinate(1920, 1080, 1920, 1080)


def test_validate_coordinate_virtual_screen() -> None:
    monitors = [
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": 1920, "top": 9, "width": 1920, "height": 1080},
    ]
    # Inside primary monitor.
    validate_coordinate(100, 200, 3840, 1089, monitors=monitors)
    # Inside secondary monitor.
    validate_coordinate(2000, 500, 3840, 1089, monitors=monitors)
    # Inside virtual screen bounds but in the gap between monitors.
    with pytest.raises(SafetyError, match="gap"):
        validate_coordinate(2000, 5, 3840, 1089, monitors=monitors)
    # Outside virtual screen bounds.
    with pytest.raises(SafetyError, match="outside"):
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
