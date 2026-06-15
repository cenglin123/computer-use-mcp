"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

from computer_use import config


def test_load_config_defaults(tmp_path: Path) -> None:
    config.reset_config_cache()
    cfg = config.load_config(tmp_path / "nonexistent.yaml")
    assert cfg["log_dir"] == Path.home() / ".kimi-code" / "logs"
    assert cfg["screenshot_dir"] == Path.home() / ".kimi-code" / "mcp" / "computer-use" / "screenshots"
    assert cfg["safety"]["sensitive_processes"] == []
    assert cfg["safety"]["sensitive_window_classes"] == []
    assert cfg["safety"]["screenshot_sensitive_window_check"] is True
    assert cfg["display"]["default_monitor"] == 1


def test_load_config_override(tmp_path: Path) -> None:
    config.reset_config_cache()
    path = tmp_path / "config.yaml"
    path.write_text(
        """
log_dir: ~/custom-logs
screenshot_dir: ~/custom-shots
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
    assert cfg["screenshot_dir"] == Path.home() / "custom-shots"
    assert cfg["safety"]["sensitive_processes"] == ["myapp"]
    assert cfg["safety"]["sensitive_window_classes"] == ["MyClass"]
    assert cfg["safety"]["screenshot_sensitive_window_check"] is False
    assert cfg["display"]["default_monitor"] == 2


def test_load_config_uses_environment_override(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "env-config.yaml"
    path.write_text(
        """
trace_dir: ~/env-traces
display:
  default_monitor: 2
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("COMPUTER_USE_CONFIG", str(path))
    config.reset_config_cache()

    cfg = config.load_config()

    assert cfg["trace_dir"] == Path.home() / "env-traces"
    assert cfg["display"]["default_monitor"] == 2


def test_explicit_config_path_wins_over_environment(
    tmp_path: Path, monkeypatch
) -> None:
    env_path = tmp_path / "env-config.yaml"
    explicit_path = tmp_path / "explicit-config.yaml"
    env_path.write_text("display:\n  default_monitor: 2\n", encoding="utf-8")
    explicit_path.write_text("display:\n  default_monitor: 1\n", encoding="utf-8")
    monkeypatch.setenv("COMPUTER_USE_CONFIG", str(env_path))
    config.reset_config_cache()

    cfg = config.load_config(explicit_path)

    assert cfg["display"]["default_monitor"] == 1
