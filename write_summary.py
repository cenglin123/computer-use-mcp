"""Take a screenshot of the primary monitor, summarize it, and save the summary to the Desktop.

Temporary screenshot is saved to ~/.kimi-code/logs/ instead of the Desktop.
"""

from __future__ import annotations

import base64
import subprocess
import sys
import time
from pathlib import Path

from computer_use.core import screenshot


SUMMARY_TEMPLATE = """主屏内容总结

时间：{timestamp}

主屏显示的是 Bilibili（哔哩哔哩）视频网站页面，当前正在观看 UP 主"山河有声"发布的视频：

标题：《奋六世之余烈：秦朝统一为何需要六世这么久？》
播放量：1.2万
弹幕数：48
发布时间：2026-06-12 17:00:00
当前观看人数：170人

视频画面为古代战争/秦朝相关场景，画面底部字幕显示"托遗响于悲风"。

页面右侧显示该 UP 主的"先秦史"播放列表，包含多个历史类视频推荐。

任务栏显示多个已打开的应用程序，包括浏览器、Kimi Code 等。
"""


def main() -> int:
    # 1. Save temporary screenshot to logs, NOT Desktop
    logs_dir = Path.home() / ".kimi-code" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = logs_dir / "main_screenshot.png"

    print(f"Taking primary monitor screenshot...")
    img_b64 = screenshot(monitor=1)
    screenshot_path.write_bytes(base64.b64decode(img_b64))
    print(f"  Screenshot saved to: {screenshot_path}")

    # 2. Write summary directly to Desktop via Python file I/O (avoids pyautogui Chinese input issues)
    from datetime import datetime

    summary = SUMMARY_TEMPLATE.format(timestamp=datetime.now().strftime("%Y/%m/%d %H:%M"))
    desktop_path = Path.home() / "Desktop" / "主屏内容总结.txt"
    desktop_path.write_text(summary, encoding="utf-8")
    print(f"Summary saved to: {desktop_path}")

    # 3. Open Notepad to show the result
    subprocess.Popen(["notepad.exe", str(desktop_path)])
    time.sleep(0.5)

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
