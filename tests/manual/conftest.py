"""Fixtures for manual GUI integration tests.

Tests in this directory are skipped unless ``COMPUTER_USE_RUN_MANUAL=1`` is set.
They exercise real Windows UI and should only be run on an idle desktop.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

from computer_use.config import load_config, reset_config_cache
from computer_use.ui_automation import _uia_available


def pytest_runtest_setup(item: pytest.Item) -> None:
    markers = {m.name for m in item.iter_markers()}
    if "manual" in markers and os.environ.get("COMPUTER_USE_RUN_MANUAL") != "1":
        pytest.skip("set COMPUTER_USE_RUN_MANUAL=1 to run manual tests")


@pytest.fixture
def notepad_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Start Notepad, redirect config dirs to temp paths, and clean up."""
    reset_config_cache()

    config = load_config()
    config["log_dir"] = tmp_path / "logs"
    config["screenshot_dir"] = tmp_path / "screenshots"
    config["trace_dir"] = tmp_path / "traces"
    config["task_dir"] = tmp_path / "tasks"
    config["safety"]["screenshot_sensitive_window_check"] = False
    monkeypatch.setattr("computer_use.config._config_cache", config)

    if not _uia_available():
        pytest.skip("uiautomation not available")

    proc = subprocess.Popen(["notepad.exe"])
    # Give Notepad time to create its window before callers observe it.
    time.sleep(1.0)

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)

    reset_config_cache()
