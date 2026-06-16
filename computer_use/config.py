"""Runtime configuration loader for the Computer Use MCP Server."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = (
    Path.home() / ".kimi-code" / "mcp" / "computer-use" / "config.yaml"
)


_DEFAULTS: dict[str, Any] = {
    "log_dir": Path.home() / ".kimi-code" / "logs",
    "screenshot_dir": Path.home() / ".kimi-code" / "mcp" / "computer-use" / "screenshots",
    "trace_dir": Path.home() / ".computer-use" / "traces",
    "task_dir": Path.home() / ".computer-use" / "tasks",
    "safety": {
        "sensitive_processes": [],
        "sensitive_window_classes": [],
        "screenshot_sensitive_window_check": True,
        "allowed_commands": [],
    },
    "display": {
        "default_monitor": 1,
    },
}


def _expand_user(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("~/"):
        return Path(os.path.expanduser(value))
    return value


def _load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_CONFIG_PATH
    config = {
        "log_dir": _expand_user(_DEFAULTS["log_dir"]),
        "screenshot_dir": _expand_user(_DEFAULTS["screenshot_dir"]),
        "trace_dir": _expand_user(_DEFAULTS["trace_dir"]),
        "task_dir": _expand_user(_DEFAULTS["task_dir"]),
        "safety": dict(_DEFAULTS["safety"]),
        "display": dict(_DEFAULTS["display"]),
    }

    if not path.exists():
        return config

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:  # pragma: no cover
        return config

    if "log_dir" in data:
        config["log_dir"] = Path(_expand_user(data["log_dir"]))

    if "screenshot_dir" in data:
        config["screenshot_dir"] = Path(_expand_user(data["screenshot_dir"]))

    if "trace_dir" in data:
        config["trace_dir"] = Path(_expand_user(data["trace_dir"]))

    if "task_dir" in data:
        config["task_dir"] = Path(_expand_user(data["task_dir"]))

    safety = data.get("safety", {})
    config["safety"]["sensitive_processes"] = list(
        safety.get("sensitive_processes", [])
    )
    config["safety"]["sensitive_window_classes"] = list(
        safety.get("sensitive_window_classes", [])
    )
    config["safety"]["screenshot_sensitive_window_check"] = bool(
        safety.get("screenshot_sensitive_window_check", True)
    )
    config["safety"]["allowed_commands"] = list(
        safety.get("allowed_commands", [])
    )

    display = data.get("display", {})
    config["display"]["default_monitor"] = int(
        display.get("default_monitor", _DEFAULTS["display"]["default_monitor"])
    )

    return config


_config_cache: dict[str, Any] | None = None


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load and cache the server configuration.

    An explicit path takes precedence over ``COMPUTER_USE_CONFIG``, followed by
    the default user configuration path. The result is cached for the lifetime
    of the process.
    """
    global _config_cache
    if _config_cache is None:
        selected_path = path
        if selected_path is None:
            selected_path = Path(
                os.environ.get("COMPUTER_USE_CONFIG", DEFAULT_CONFIG_PATH)
            )
        _config_cache = _load_config(selected_path)
    return _config_cache


def reset_config_cache() -> None:
    """Clear the cached configuration. Used primarily by tests."""
    global _config_cache
    _config_cache = None
