"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

from computer_use import config


def test_load_config_defaults(tmp_path: Path) -> None:
    config.reset_config_cache()
    cfg = config.load_config(tmp_path / "nonexistent.yaml")
    assert cfg["log_dir"] == Path.home() / ".kimi-code" / "logs"
    assert cfg["safety"]["sensitive_processes"] == []
    assert cfg["safety"]["sensitive_window_classes"] == []
    assert cfg["safety"]["screenshot_sensitive_window_check"] is True
    assert cfg["display"]["default_monitor"] == 0


def test_load_config_override(tmp_path: Path) -> None:
    config.reset_config_cache()
    path = tmp_path / "config.yaml"
    path.write_text(
        """
log_dir: ~/custom-logs
safety:
  sensitive_processes: ["myapp"]
  sensitive_window_classes: ["MyClass"]
  screenshot_sensitive_window_check: false
display:
  default_monitor: 2
""",
        encoding="utf-8",
    )
    cfg = config.load_config(path)
    assert cfg["log_dir"] == Path.home() / "custom-logs"
    assert cfg["safety"]["sensitive_processes"] == ["myapp"]
    assert cfg["safety"]["sensitive_window_classes"] == ["MyClass"]
    assert cfg["safety"]["screenshot_sensitive_window_check"] is False
    assert cfg["display"]["default_monitor"] == 2
