"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

from computer_use import config


def test_load_config_defaults(tmp_path: Path) -> None:
    config.reset_config_cache()
    cfg = config.load_config(tmp_path / "nonexistent.yaml")
    assert cfg["log_dir"] == Path.home() / ".computer-use" / "logs"
    assert cfg["screenshot_dir"] == Path.home() / ".computer-use" / "screenshots"
    assert cfg["trace_dir"] == Path.home() / ".computer-use" / "traces"
    assert cfg["task_dir"] == Path.home() / ".computer-use" / "tasks"
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
trace_dir: ~/custom-traces
task_dir: ~/custom-tasks
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
    assert cfg["trace_dir"] == Path.home() / "custom-traces"
    assert cfg["task_dir"] == Path.home() / "custom-tasks"
    assert cfg["safety"]["sensitive_processes"] == ["myapp"]
    assert cfg["safety"]["sensitive_window_classes"] == ["MyClass"]
    assert cfg["safety"]["screenshot_sensitive_window_check"] is False
    assert cfg["display"]["default_monitor"] == 2


def test_load_config_uses_environment_override(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "env-config.yaml"
    path.write_text(
        """
trace_dir: ~/env-traces
task_dir: ~/env-tasks
display:
  default_monitor: 2
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("COMPUTER_USE_CONFIG", str(path))
    config.reset_config_cache()

    cfg = config.load_config()

    assert cfg["trace_dir"] == Path.home() / "env-traces"
    assert cfg["task_dir"] == Path.home() / "env-tasks"
    assert cfg["display"]["default_monitor"] == 2


def test_load_config_falls_back_to_legacy_default_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    new_path = tmp_path / "new" / "config.yaml"
    legacy_path = tmp_path / "legacy" / "config.yaml"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text("log_dir: ~/legacy-logs\n", encoding="utf-8")
    monkeypatch.setattr(config, "DEFAULT_CONFIG_PATH", new_path)
    monkeypatch.setattr(config, "LEGACY_CONFIG_PATH", legacy_path)
    monkeypatch.delenv("COMPUTER_USE_CONFIG", raising=False)
    config.reset_config_cache()

    cfg = config.load_config()

    assert cfg["log_dir"] == Path.home() / "legacy-logs"


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
