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
