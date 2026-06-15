"""Tests for the local debug CLI input safety boundary."""

from __future__ import annotations

from types import SimpleNamespace

from computer_use import cli


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
