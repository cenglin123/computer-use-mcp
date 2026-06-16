"""Installation diagnostics for distributed Computer Use MCP setups."""

from __future__ import annotations

import importlib.util
import platform
from pathlib import Path
from typing import Any

from computer_use import guidance
from computer_use.config import load_config


def _check(name: str, ok: bool, detail: str, *, warning: bool = False) -> dict[str, str]:
    if ok:
        status = "ok"
    elif warning:
        status = "warning"
    else:
        status = "failed"
    return {"name": name, "status": status, "detail": detail}


def run_doctor() -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    checks.append(_check("platform", platform.system() == "Windows", platform.platform()))
    checks.append(_check("mss", importlib.util.find_spec("mss") is not None, "mss importable"))
    checks.append(_check("Pillow", importlib.util.find_spec("PIL") is not None, "Pillow importable"))
    checks.append(
        _check(
            "pyautogui",
            importlib.util.find_spec("pyautogui") is not None,
            "pyautogui importable",
        )
    )
    checks.append(
        _check(
            "uiautomation",
            importlib.util.find_spec("uiautomation") is not None,
            "uiautomation importable",
            warning=True,
        )
    )

    try:
        config = load_config()
    except Exception as exc:
        checks.append(_check("config_load", False, str(exc)))
        return {
            "status": "failed",
            "checks": checks,
            "next_steps": list(guidance.DOCTOR_NEXT_STEPS),
        }

    for key in ("log_dir", "screenshot_dir", "trace_dir", "task_dir"):
        path_value = getattr(config, key, None)
        if path_value is None and isinstance(config, dict):
            path_value = config.get(key)
        if path_value is None:
            checks.append(_check(key, False, f"config missing key: {key}"))
            continue
        path = Path(path_value)
        try:
            path.mkdir(parents=True, exist_ok=True)
            writable = path.is_dir()
        except Exception as exc:
            checks.append(_check(key, False, str(exc)))
        else:
            checks.append(_check(key, writable, str(path)))

    checks.append(
        {
            "name": "model_capability",
            "status": "warning",
            "detail": guidance.MODEL_CAPABILITY_WARNING,
        }
    )

    status = "failed" if any(item["status"] == "failed" for item in checks) else "ok"
    return {
        "status": status,
        "checks": checks,
        "next_steps": list(guidance.DOCTOR_NEXT_STEPS),
    }
