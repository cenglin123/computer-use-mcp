"""Local command-line entry point for development and debugging."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable

from computer_use.safety import (
    SafetyError,
    check_target_window,
    validate_coordinate,
    validate_monitor_index,
    validate_text_input,
)
from computer_use.ui_automation import inspect_point


DEFAULT_MOVE_DURATION = 0.2


def load_config() -> dict:
    from computer_use.config import load_config as _load_config

    return _load_config()


def get_coordinate_system():
    from computer_use.core import get_coordinate_system as _get_coordinate_system

    return _get_coordinate_system()


def get_monitors():
    from computer_use.core import get_monitors as _get_monitors

    return _get_monitors()


def screenshot(*args, **kwargs):
    from computer_use.core import screenshot as _screenshot

    return _screenshot(*args, **kwargs)


def click(*args, **kwargs):
    from computer_use.core import click as _click

    return _click(*args, **kwargs)


def move_to(*args, **kwargs):
    from computer_use.core import move_to as _move_to

    return _move_to(*args, **kwargs)


def scroll(*args, **kwargs):
    from computer_use.core import scroll as _scroll

    return _scroll(*args, **kwargs)


def type_text(*args, **kwargs):
    from computer_use.core import type_text as _type_text

    return _type_text(*args, **kwargs)


def key_combo(*args, **kwargs):
    from computer_use.core import key_combo as _key_combo

    return _key_combo(*args, **kwargs)


def validate_duration(*args, **kwargs):
    from computer_use.core import validate_duration as _validate_duration

    return _validate_duration(*args, **kwargs)


def _current_logical_position() -> tuple[int, int]:
    """Return the current cursor position in physical virtual screen pixels."""
    import pyautogui

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

    p_click = sub.add_parser("click", help="Click at primary-screen physical coordinates")
    p_click.add_argument("x", type=int)
    p_click.add_argument("y", type=int)
    p_click.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_MOVE_DURATION,
        help=f"Seconds to spend moving the cursor before clicking (default: {DEFAULT_MOVE_DURATION})",
    )

    p_move = sub.add_parser("move", help="Move mouse to primary-screen physical coordinates")
    p_move.add_argument("x", type=int)
    p_move.add_argument("y", type=int)
    p_move.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_MOVE_DURATION,
        help=f"Seconds to spend moving the cursor (default: {DEFAULT_MOVE_DURATION})",
    )

    p_scroll = sub.add_parser("scroll", help="Scroll at current or given position")
    p_scroll.add_argument("amount", type=int)
    p_scroll.add_argument("--x", type=int, default=None)
    p_scroll.add_argument("--y", type=int, default=None)

    p_type = sub.add_parser("type", help="Type text")
    p_type.add_argument("text")

    p_key = sub.add_parser("key", help="Press key combination")
    p_key.add_argument("keys", nargs="+")

    p_tasks = sub.add_parser("tasks", help="Audit business task sessions")
    tasks_sub = p_tasks.add_subparsers(dest="tasks_cmd", required=True)
    p_tasks_list = tasks_sub.add_parser("list", help="List task sessions as JSON")
    p_tasks_list.add_argument("--date", default=None)
    p_tasks_list.add_argument("--status", default=None)
    p_tasks_list.add_argument("--limit", type=int, default=None)
    p_tasks_show = tasks_sub.add_parser("show", help="Show one task session as JSON")
    p_tasks_show.add_argument("task_id")
    p_tasks_review = tasks_sub.add_parser("review", help="Review one task session as JSON")
    p_tasks_review.add_argument("task_id")

    p_audit = sub.add_parser("audit", help="Audit store maintenance")
    audit_sub = p_audit.add_subparsers(dest="audit_cmd", required=True)
    p_rebuild = audit_sub.add_parser("rebuild-index", help="Rebuild locator indexes")
    p_rebuild.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "tasks":
        from computer_use import review, task_session

        if args.tasks_cmd == "list":
            print(json.dumps({"tasks": task_session.list_tasks(date=args.date, status=args.status, limit=args.limit)}))
        elif args.tasks_cmd == "show":
            print(json.dumps(task_session.get_task(args.task_id)))
        elif args.tasks_cmd == "review":
            print(json.dumps(review.review_task_session(args.task_id)))
        return 0

    if args.cmd == "audit":
        if args.audit_cmd == "rebuild-index":
            if args.dry_run:
                print(json.dumps({"dry_run": True}))
                return 0
            from computer_use import audit_store, task_session, trace

            print(json.dumps({
                "traces": audit_store.rebuild_location_index(trace.trace_dir(), "trace_id"),
                "tasks": audit_store.rebuild_location_index(task_session.task_dir(), "task_id"),
            }))
        return 0

    cs = get_coordinate_system()

    def _dispatch_mouse_subcommand(
        args: argparse.Namespace,
        action: Callable[[int, int, float], None],
        result_key: str,
    ) -> None:
        validate_duration(args.duration)
        size = cs.get_screen_size()
        validate_coordinate(args.x, args.y, size.width, size.height, monitors=cs.monitors)
        info = inspect_point(args.x, args.y)
        check_target_window(info.process_name, info.class_name, info.control_type)
        action(args.x, args.y, args.duration)
        print(json.dumps({result_key: True, "x": args.x, "y": args.y, "duration": args.duration}))

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
            _dispatch_mouse_subcommand(args, click, "clicked")
        elif args.cmd == "move":
            _dispatch_mouse_subcommand(args, move_to, "moved")
        elif args.cmd == "scroll":
            if args.x is not None and args.y is not None:
                x, y = args.x, args.y
            else:
                x, y = _current_logical_position()
            size = cs.get_screen_size()
            validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
            info = inspect_point(x, y)
            check_target_window(
                info.process_name, info.class_name, info.control_type
            )
            scroll(args.amount, args.x, args.y)
        elif args.cmd == "type":
            validate_text_input(args.text)
            x, y = _current_logical_position()
            size = cs.get_screen_size()
            validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
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
            size = cs.get_screen_size()
            validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
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
