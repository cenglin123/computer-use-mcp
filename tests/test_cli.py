"""Tests for the local debug CLI input safety boundary."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from computer_use import cli
from computer_use import task_session


def test_cli_click_rejects_secondary_monitor_coordinate(monkeypatch, capsys) -> None:
    calls = []
    monkeypatch.setattr(
        cli,
        "get_coordinate_system",
        lambda: SimpleNamespace(
            get_screen_size=lambda: SimpleNamespace(width=3840, height=1080),
            monitors=[
                {"left": 0, "top": 0, "width": 1920, "height": 1080},
                {"left": 1920, "top": 0, "width": 1920, "height": 1080},
            ],
        ),
    )
    monkeypatch.setattr(
        cli,
        "click",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    exit_code = cli.main(["click", "2000", "500"])

    assert exit_code == 2
    assert "primary" in capsys.readouterr().err.lower()
    assert calls == []


def test_cli_tasks_list_outputs_json_without_input_device_import(
    tmp_path, monkeypatch, capsys
) -> None:
    # Other test modules in the same process may have already loaded pyautogui
    # (e.g. test_mcp_server imports mcp_server which imports pyautogui).
    # Pop them so we can verify the tasks-list execution path does NOT re-import.
    sys.modules.pop("pyautogui", None)
    sys.modules.pop("computer_use.core", None)
    monkeypatch.setattr(task_session, "task_dir", lambda: tmp_path)
    task_session.start_task("audit")

    exit_code = cli.main(["tasks", "list"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["tasks"][0]["goal"] == "audit"
    assert "pyautogui" not in sys.modules
    assert "computer_use.core" not in sys.modules


def test_cli_module_import_does_not_load_pyautogui() -> None:
    """Importing computer_use.cli in a clean subprocess must not load pyautogui."""
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "from computer_use import cli; "
                "print('pyautogui' not in sys.modules and "
                "'computer_use.core' not in sys.modules)"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True", (
        f"cli module import loaded input-device dependencies:\n{result.stderr}"
    )
