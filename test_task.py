"""Simple end-to-end test task for Computer Use.

This script:
1. Lists all monitors.
2. Verifies safety boundary blocks dangerous text.
3. Opens Notepad and types text on the primary monitor.
4. Takes a virtual-desktop screenshot.
5. If a secondary monitor exists, clicks its center and takes a screenshot.

All screenshots are saved to ~/.computer-use/logs/ for manual verification.
"""

from __future__ import annotations

import base64
import subprocess
import sys
import time
from pathlib import Path

from computer_use.core import click, get_monitors, screenshot, type_text
from computer_use.safety import SafetyError, validate_text_input


def save_screenshot(b64_data: str, name: str) -> Path:
    out = Path.home() / ".computer-use" / "logs" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return out


def main() -> int:
    print("=== Computer Use Simple Task Test ===\n")

    # 1. List monitors
    monitors = get_monitors()
    print(f"Found {len(monitors)} monitor(s):")
    for m in monitors:
        print(
            f"  {m.index}: primary={m.primary}, "
            f"{m.width}x{m.height} @ ({m.left},{m.top})"
        )
    print()

    # 2. Safety boundary test
    print("Testing safety boundary...")
    try:
        validate_text_input("rm -rf /")
        print("  FAIL: dangerous text was not blocked")
        return 1
    except SafetyError as e:
        print(f"  PASS: {e}")
    print()

    # 3. Open Notepad and type text
    print("Opening Notepad...")
    subprocess.Popen(["notepad.exe"])
    time.sleep(1.5)

    primary = next(m for m in monitors if m.primary)
    center_x = primary.left + primary.width // 2
    center_y = primary.top + primary.height // 2
    print(f"Clicking primary monitor center: ({center_x}, {center_y})")
    click(center_x, center_y)
    time.sleep(0.2)

    text = "Hello from Computer Use MCP!"
    print(f"Typing: {text}")
    type_text(text)
    time.sleep(0.2)

    # 4. Screenshot virtual desktop
    print("Taking virtual-desktop screenshot...")
    img = screenshot()
    out = save_screenshot(img, "computer-use-test-virtual.png")
    print(f"  Saved to: {out}")

    # 5. If secondary monitor exists, click it and screenshot it
    secondary = [m for m in monitors if not m.primary]
    if secondary:
        sec = secondary[0]
        sec_center_x = sec.left + sec.width // 2
        sec_center_y = sec.top + sec.height // 2
        print(f"Clicking secondary monitor center: ({sec_center_x}, {sec_center_y})")
        click(sec_center_x, sec_center_y)
        time.sleep(0.2)
        img = screenshot(monitor=sec.index)
        out = save_screenshot(img, "computer-use-test-secondary.png")
        print(f"  Secondary screenshot saved to: {out}")
    else:
        print("No secondary monitor detected, skipping secondary test.")

    print("\n=== Test complete ===")
    print("Please check the saved PNG files to verify visually.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
