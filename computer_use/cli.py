"""Local command-line entry point for development and debugging."""

from __future__ import annotations

import argparse
import json
import sys

import pyautogui

from computer_use.config import load_config
from computer_use.core import (
    click,
    get_coordinate_system,
    get_monitors,
    key_combo,
    move_to,
    screenshot,
    scroll,
    type_text,
)
from computer_use.safety import (
    SafetyError,
    check_target_window,
    validate_coordinate,
    validate_monitor_index,
    validate_text_input,
)
from computer_use.ui_automation import inspect_point


def _current_logical_position() -> tuple[int, int]:
    """Return the current cursor position in physical virtual screen pixels."""
    x, y = pyautogui.position()
    return int(x), int(y)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Computer Use local debug CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_screenshot = sub.add_parser("screenshot", help="Output base64 PNG screenshot to stdout")
    p_screenshot.add_argument(
        "--monitor",
        type=int,
        default=None,
        help="Monitor index: 0 for virtual desktop (default), 1+ for a single monitor",
    )

    sub.add_parser("size", help="Output virtual screen size as JSON")
    sub.add_parser("monitors", help="Output monitor list as JSON")

    p_click = sub.add_parser("click", help="Click at physical virtual screen coordinates")
    p_click.add_argument("x", type=int)
    p_click.add_argument("y", type=int)
    p_click.add_argument(
        "--duration",
        type=float,
        default=0.2,
        help="Seconds to spend moving the cursor before clicking (default: 0.2)",
    )

    p_move = sub.add_parser("move", help="Move mouse to physical virtual screen coordinates")
    p_move.add_argument("x", type=int)
    p_move.add_argument("y", type=int)
    p_move.add_argument(
        "--duration",
        type=float,
        default=0.2,
        help="Seconds to spend moving the cursor (default: 0.2)",
    )

    p_scroll = sub.add_parser("scroll", help="Scroll at current or given position")
    p_scroll.add_argument("amount", type=int)
    p_scroll.add_argument("--x", type=int, default=None)
    p_scroll.add_argument("--y", type=int, default=None)

    p_type = sub.add_parser("type", help="Type text")
    p_type.add_argument("text")

    p_key = sub.add_parser("key", help="Press key combination")
    p_key.add_argument("keys", nargs="+")

    args = parser.parse_args(argv)
    cs = get_coordinate_system()

    try:
        if args.cmd == "screenshot":
            monitor = args.monitor
            if monitor is None:
                monitor = load_config().get("display", {}).get("default_monitor", 0)
            print(screenshot(monitor=monitor))
        elif args.cmd == "size":
            info = cs.get_screen_size()
            print(json.dumps({"width": info.width, "height": info.height}))
        elif args.cmd == "monitors":
            print(json.dumps([m._asdict() for m in get_monitors()]))
        elif args.cmd == "click":
            size = cs.get_screen_size()
            validate_coordinate(args.x, args.y, size.width, size.height, monitors=cs.monitors)
            info = inspect_point(args.x, args.y)
            check_target_window(info.process_name, info.class_name, info.control_type)
            click(args.x, args.y, duration=args.duration)
        elif args.cmd == "move":
            size = cs.get_screen_size()
            validate_coordinate(args.x, args.y, size.width, size.height, monitors=cs.monitors)
            info = inspect_point(args.x, args.y)
            check_target_window(info.process_name, info.class_name, info.control_type)
            move_to(args.x, args.y, duration=args.duration)
        elif args.cmd == "scroll":
            if args.x is not None and args.y is not None:
                size = cs.get_screen_size()
                validate_coordinate(args.x, args.y, size.width, size.height, monitors=cs.monitors)
                info = inspect_point(args.x, args.y)
                check_target_window(
                    info.process_name, info.class_name, info.control_type
                )
            scroll(args.amount, args.x, args.y)
        elif args.cmd == "type":
            validate_text_input(args.text)
            x, y = _current_logical_position()
            info = inspect_point(x, y)
            check_target_window(
                info.process_name,
                info.class_name,
                info.control_type,
                is_password=info.is_password,
            )
            type_text(args.text)
        elif args.cmd == "key":
            x, y = _current_logical_position()
            info = inspect_point(x, y)
            check_target_window(info.process_name, info.class_name, info.control_type)
            key_combo(*args.keys)
        else:
            parser.print_help()
            return 1
    except SafetyError as exc:
        print(f"SAFETY: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
