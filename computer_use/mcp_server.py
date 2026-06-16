"""MCP Server exposing Computer Use tools to Kimi Code CLI."""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyautogui
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from computer_use.config import load_config
from computer_use.core import (
    DEFAULT_MOVE_DURATION,
    VALID_MOUSE_BUTTONS,
    CoordinateSystem,
    click,
    double_click,
    drag,
    get_coordinate_system,
    get_monitors,
    key_combo,
    key_down,
    key_up,
    move_to,
    mouse_down,
    mouse_up,
    press_key,
    save_redacted_image,
    save_screenshot,
    scroll,
    type_text,
    validate_duration,
)
from computer_use.launcher import launch_app
from computer_use.safety import (
    SafetyError,
    check_target_window,
    validate_coordinate,
    validate_monitor_index,
    validate_text_input,
)
from computer_use.ui_automation import (
    find_control,
    get_top_level_windows_in_rect,
    inspect_point,
    wait_for_control,
    wait_for_window,
)
from computer_use import trace as trace_module
from computer_use.tool_contract import (
    BATCH_ACTION_TOOL_NAMES,
    InvalidToolName,
    normalize_nested_tool_name,
)


def _setup_logging(log_dir: Path | None = None) -> None:
    if log_dir is None:
        log_dir = load_config().get("log_dir", Path.home() / ".kimi-code" / "logs")
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "computer-use.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.handlers.RotatingFileHandler(
                log_path, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
            ),
            logging.StreamHandler(sys.stderr),
        ],
    )


#: Maximum allowed sleep duration in seconds for the ``sleep`` tool.
MAX_SLEEP_DURATION: float = 60.0
_MANIFEST_TOOL_NAMES = {"batch", "run_task_plan", "review_task"}

TOOLS: list[Tool] = [
    Tool(
        name="screenshot",
        description="Take a screenshot and save it as a PNG file. The image itself is never returned in the context; only a file path reference is returned. The file can then be read with multimodal tools such as ReadMediaFile. By default the primary monitor (monitor=1) is captured; pass monitor=0 for the entire virtual desktop, or pass save_path to override the save location.",
        inputSchema={
            "type": "object",
            "properties": {
                "monitor": {
                    "type": "integer",
                    "description": "0 for virtual desktop, or 1-based monitor index for a single monitor. Defaults to the configured primary monitor (usually 1).",
                },
                "save_path": {
                    "type": "string",
                    "description": "If provided, save the PNG to this file path and return the path. Otherwise the PNG is saved to the configured screenshot_dir with an auto-generated timestamped name.",
                },
            },
        },
    ),
    Tool(
        name="get_monitors",
        description="Return a list of monitors with index, primary flag, left, top, width, and height in physical virtual screen coordinates.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_ui_snapshot",
        description="Return a structured UI automation tree snapshot.",
        inputSchema={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["foreground", "desktop"],
                    "default": "foreground",
                    "description": "Snapshot scope.",
                },
                "include_screenshot": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, also save a screenshot and return its path.",
                },
            },
        },
    ),
    Tool(
        name="click",
        description="Click a UI Automation control by name or at the given non-negative primary-screen physical coordinates (x, y). The cursor moves smoothly over a short duration to avoid closing hover-activated menus. Provide either target_name or both x and y.",
        inputSchema={
            "type": "object",
            "properties": {
                "target_name": {
                    "type": "string",
                    "description": "UIA control name. When provided, the control is located first and its center is used as the click target.",
                },
                "match": {
                    "type": "string",
                    "enum": ["exact", "contains", "startswith"],
                    "default": "contains",
                    "description": "Matching mode for target_name.",
                },
                "x": {"type": "integer", "description": "Primary-screen physical x coordinate"},
                "y": {"type": "integer", "description": "Primary-screen physical y coordinate"},
                "duration": {
                    "type": "number",
                    "default": DEFAULT_MOVE_DURATION,
                    "description": f"Seconds to spend moving the cursor before clicking. Default {DEFAULT_MOVE_DURATION}. Increase if menus close prematurely.",
                },
                "button": {
                    "type": "string",
                    "enum": list(VALID_MOUSE_BUTTONS),
                    "default": "left",
                    "description": "Mouse button to click: left, right, or middle.",
                },
                "double_click": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, perform a double-click instead of a single click.",
                },
            },
        },
    ),
    Tool(
        name="move_to",
        description="Move the cursor to a UI Automation control by name or to the given non-negative primary-screen physical coordinates (x, y). The cursor moves smoothly over a short duration to avoid closing hover-activated menus. Provide either target_name or both x and y.",
        inputSchema={
            "type": "object",
            "properties": {
                "target_name": {
                    "type": "string",
                    "description": "UIA control name. When provided, the control is located first and its center is used as the move target.",
                },
                "match": {
                    "type": "string",
                    "enum": ["exact", "contains", "startswith"],
                    "default": "contains",
                    "description": "Matching mode for target_name.",
                },
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "duration": {
                    "type": "number",
                    "default": DEFAULT_MOVE_DURATION,
                    "description": f"Seconds to spend moving the cursor. Default {DEFAULT_MOVE_DURATION}. Increase if menus close prematurely.",
                },
            },
        },
    ),
    Tool(
        name="scroll",
        description="Scroll the mouse wheel by amount or direction, optionally at non-negative primary-screen physical coordinates.",
        inputSchema={
            "type": "object",
            "properties": {
                "amount": {
                    "type": "integer",
                    "description": "Number of scroll units. Positive scrolls up, negative down. Either this or direction is required.",
                },
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Scroll direction. When provided, clicks is used to compute amount.",
                },
                "clicks": {
                    "type": "integer",
                    "default": 3,
                    "description": "Number of clicks when direction is provided. Defaults to 3.",
                },
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
        },
    ),
    Tool(
        name="type",
        description="Type the given text.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="key_combo",
        description="Press a key combination, e.g. ['ctrl', 'c'].",
        inputSchema={
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["keys"],
        },
    ),
    Tool(
        name="mouse_down",
        description="Press and hold a mouse button at the given non-negative primary-screen physical coordinates.",
        inputSchema={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "button": {
                    "type": "string",
                    "enum": list(VALID_MOUSE_BUTTONS),
                    "default": "left",
                },
            },
            "required": ["x", "y"],
        },
    ),
    Tool(
        name="mouse_up",
        description="Release a mouse button. Optionally move to (x, y) before releasing.",
        inputSchema={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "button": {
                    "type": "string",
                    "enum": list(VALID_MOUSE_BUTTONS),
                    "default": "left",
                },
            },
        },
    ),
    Tool(
        name="drag",
        description="Drag the mouse from (start_x, start_y) to (end_x, end_y) while holding a mouse button.",
        inputSchema={
            "type": "object",
            "properties": {
                "start_x": {"type": "integer"},
                "start_y": {"type": "integer"},
                "end_x": {"type": "integer"},
                "end_y": {"type": "integer"},
                "duration": {
                    "type": "number",
                    "default": DEFAULT_MOVE_DURATION,
                },
                "button": {
                    "type": "string",
                    "enum": list(VALID_MOUSE_BUTTONS),
                    "default": "left",
                },
            },
            "required": ["start_x", "start_y", "end_x", "end_y"],
        },
    ),
    Tool(
        name="key_down",
        description="Hold a keyboard key down (press without releasing). Use key_up to release.",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {"type": "string"},
            },
            "required": ["key"],
        },
    ),
    Tool(
        name="key_up",
        description="Release a keyboard key previously held with key_down.",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {"type": "string"},
            },
            "required": ["key"],
        },
    ),
    Tool(
        name="press_key",
        description="Press and release a single keyboard key.",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {"type": "string"},
            },
            "required": ["key"],
        },
    ),
    Tool(
        name="find_control",
        description="Find a UI Automation control by name, automation id, control type, or class name and return its bounding rectangle and center point.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Control name substring or full name"},
                "automation_id": {"type": "string"},
                "control_type": {"type": "string", "description": "e.g. Button, MenuItem, Window"},
                "class_name": {"type": "string"},
                "scope": {"type": "string", "enum": ["desktop", "foreground", "window"], "default": "desktop"},
                "window_name": {"type": "string", "description": "Required when scope=window"},
                "match": {"type": "string", "enum": ["exact", "contains", "startswith"], "default": "contains"},
                "sensitive_check": {"type": "boolean", "default": True},
            },
        },
    ),
    Tool(
        name="inspect_point",
        description="Inspect the UI Automation control at the given physical virtual screen coordinates.",
        inputSchema={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        },
    ),
    Tool(
        name="wait_for_window",
        description="Wait for a window with a matching title to appear or disappear.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "exists": {"type": "boolean", "default": True},
                "timeout": {"type": "number", "default": 10},
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="wait_for_control",
        description="Wait for a control to become available inside the foreground window.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "automation_id": {"type": "string"},
                "control_type": {"type": "string"},
                "exists": {"type": "boolean", "default": True},
                "timeout": {"type": "number", "default": 10},
            },
        },
    ),
    Tool(
        name="sleep",
        description="Pause execution for a specified duration in seconds. Useful inside batch workflows to wait for animations, window transitions, or application startup before the next action. The maximum allowed duration is 60 seconds.",
        inputSchema={
            "type": "object",
            "properties": {
                "duration": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": MAX_SLEEP_DURATION,
                    "default": 1,
                    "description": "Number of seconds to sleep. Must be between 0 and 60.",
                },
            },
        },
    ),
    Tool(
        name="launch_app",
        description="Launch an application by its Start Menu or Desktop shortcut name.",
        inputSchema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    ),
    Tool(
        name="click_by_uid",
        description="Click a control identified by its UID from a get_ui_snapshot result. The snapshot must be provided because UIDs are scoped to a single snapshot.",
        inputSchema={
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "Snapshot-scoped UID of the control to click."},
                "snapshot": {"type": "object", "description": "The full snapshot dict returned by get_ui_snapshot."},
                "duration": {"type": "number", "default": DEFAULT_MOVE_DURATION},
                "button": {"type": "string", "enum": list(VALID_MOUSE_BUTTONS), "default": "left"},
            },
            "required": ["uid", "snapshot"],
        },
    ),
    Tool(
        name="click_by_text",
        description="Find a control by displayed text in the UIA tree and click it. Returns ui_not_found if no match is found.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "match": {"type": "string", "enum": ["exact", "contains", "startswith"], "default": "contains"},
                "scope": {"type": "string", "enum": ["desktop", "foreground"], "default": "foreground"},
                "duration": {"type": "number", "default": DEFAULT_MOVE_DURATION},
                "button": {"type": "string", "enum": list(VALID_MOUSE_BUTTONS), "default": "left"},
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="open_menu",
        description="Click through a menu path by UIA control names. Stops and returns ui_not_found if any item cannot be located.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered list of menu item names to click.",
                },
                "interval": {"type": "number", "default": 0.3, "description": "Seconds to wait between menu clicks."},
                "duration": {"type": "number", "default": DEFAULT_MOVE_DURATION},
                "button": {"type": "string", "enum": list(VALID_MOUSE_BUTTONS), "default": "left"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="fill_form",
        description="Fill multiple input fields by UIA control name. Each field is clicked then typed into. Dangerous text is rejected.",
        inputSchema={
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "string"},
                            "match": {"type": "string", "enum": ["exact", "contains", "startswith"], "default": "contains"},
                        },
                        "required": ["name", "value"],
                    },
                },
                "duration": {"type": "number", "default": DEFAULT_MOVE_DURATION},
                "type_interval": {"type": "number", "default": 0.01},
            },
            "required": ["fields"],
        },
    ),
    Tool(
        name="scroll_until",
        description="Scroll until a target text appears in the foreground UIA tree. Returns ui_not_found if max_attempts is reached.",
        inputSchema={
            "type": "object",
            "properties": {
                "target_text": {"type": "string"},
                "direction": {"type": "string", "enum": ["up", "down"], "default": "down"},
                "max_attempts": {"type": "integer", "default": 10, "minimum": 1},
                "clicks": {"type": "integer", "default": 3},
                "interval": {"type": "number", "default": 0.3},
            },
            "required": ["target_text"],
        },
    ),
    Tool(
        name="run_task_plan",
        description="Execute a structured task plan as a single task. Records all steps under one trace ID and generates a report.md.",
        inputSchema={
            "type": "object",
            "properties": {
                "trace_id": {"type": "string", "description": "Optional trace ID to reuse."},
                "goal": {"type": "string", "description": "Optional task goal, written into report.md."},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string"},
                            "args": {"type": "object"},
                        },
                        "required": ["tool"],
                    },
                },
                "final_state": {"type": "boolean", "default": False, "description": "Capture a final UI snapshot + screenshot."},
                "capture_screenshots": {"type": "boolean", "default": True, "description": "Capture a screenshot before each step."},
            },
            "required": ["steps"],
        },
    ),
    Tool(
        name="retry_step",
        description="Re-execute a step from an existing trace. mode=single replays only that step; mode=from_step replays it and all subsequent steps.",
        inputSchema={
            "type": "object",
            "properties": {
                "trace_id": {"type": "string"},
                "step_index": {"type": "integer"},
                "mode": {"type": "string", "enum": ["single", "from_step"], "default": "single"},
            },
            "required": ["trace_id", "step_index"],
        },
    ),
    Tool(
        name="review_task",
        description="Generate a deterministic summary of a trace without using an LLM.",
        inputSchema={
            "type": "object",
            "properties": {
                "trace_id": {"type": "string"},
            },
            "required": ["trace_id"],
        },
    ),
    Tool(
        name="batch",
        description=(
            "Execute a sequence of tools in a single call. This is the preferred way to run multi-step GUI workflows. "
            "Call this tool directly with only the `actions` array; do not wrap it in Python/Bash scripts or import `_call_tool`. "
            "Each action is an object with `tool` (the tool name) and `args` (its arguments). "
            "Errors are captured per action. The response contains per-step results with timestamps, plus an optional final screenshot reference."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool": {
                                "type": "string",
                                "enum": list(BATCH_ACTION_TOOL_NAMES),
                                "description": "Canonical nested tool name. Do not use MCP namespace prefixes.",
                            },
                            "args": {"type": "object", "description": "Arguments for the tool."},
                            "capture_snapshot": {
                                "type": "boolean",
                                "default": False,
                                "description": "If true, capture a UI snapshot before this action and include its path in the result.",
                            },
                        },
                        "required": ["tool"],
                    },
                    "description": "Ordered list of tool calls to execute.",
                },
                "stop_on_error": {
                    "type": "boolean",
                    "default": True,
                    "description": "If true, stop executing further actions after the first error.",
                },
                "final_screenshot": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, append a final screenshot after all actions. The screenshot is saved to disk and its file path reference is included in the response; no base64 image enters the context.",
                },
                "screenshot_monitor": {
                    "type": "integer",
                    "default": 1,
                    "description": "Monitor index for the final screenshot (1 = primary monitor, default). Pass 0 for the entire virtual desktop.",
                },
            },
            "required": ["actions"],
        },
    ),
]


def _error_kind_for_result(error_value: Any) -> str:
    """Map a structured result error value to a trace error_kind."""
    if error_value is None:
        return "unknown"
    text = str(error_value).lower()
    if text == "ui_not_found":
        return "ui_not_found"
    if text == "stale_uid":
        return "stale_uid"
    if text == "timeout":
        return "timeout"
    if text == "fail_safe":
        return "fail_safe"
    if text == "invalid_tool":
        return "invalid_tool"
    if text in {"uiautomation_not_available", "uiautomation_root_failed"}:
        return "uia_unavailable"
    if text == "sensitive_window_blocked":
        return "safety_block"
    return "unknown"


def _failure_for_result(result: Any) -> tuple[str, str] | None:
    """Return ``(error_kind, message)`` for a structured failed result."""
    if not isinstance(result, dict):
        return None
    if result.get("error"):
        message = str(result["error"])
        return _error_kind_for_result(result["error"]), message
    if result.get("timeout") is True:
        return "timeout", "timeout"
    if result.get("failed_index") is not None:
        failed_index = result["failed_index"]
        results = result.get("results")
        if (
            isinstance(failed_index, int)
            and isinstance(results, list)
            and 0 <= failed_index < len(results)
            and isinstance(results[failed_index], dict)
        ):
            failed_entry = results[failed_index]
            nested_result = failed_entry.get("result", failed_entry)
            nested_failure = _failure_for_result(nested_result)
            if nested_failure is not None:
                return nested_failure
        return "unknown", "nested task failed"
    return None


def _attach_trace_manifest(data: dict[str, Any], trace_id: str) -> dict[str, Any]:
    """Derive response trace paths and artifacts from the flat trace manifest."""
    target_trace_id = data.get("trace_id") if isinstance(data.get("trace_id"), str) else trace_id
    manifest = trace_module.artifact_manifest(target_trace_id)
    data["trace_id"] = manifest["trace_id"]
    data["trace_path"] = manifest["trace_path"]
    data["artifact_root"] = manifest["artifact_root"]
    data["artifacts"] = {
        "screenshots": manifest["screenshots"],
        "snapshots": manifest["snapshots"],
        "report": manifest["report_path"],
    }
    return data


def _call_tool(name: str, args: dict, trace_context: dict[str, Any] | None = None) -> str:
    logging.info(
        "tool=%s args=%s", name, trace_module.sanitize_for_logging(args)
    )
    if trace_context:
        trace_id = trace_context["trace_id"]
    elif name == "run_task_plan" and args.get("trace_id"):
        trace_id = args["trace_id"]
    else:
        trace_id = trace_module.generate_trace_id()
    step_index = trace_context["step_index"] if trace_context else 0
    screenshot_path = trace_context.get("screenshot_path") if trace_context else None
    start = time.perf_counter()
    payload: str | None = None
    error: Exception | None = None
    try:
        cs = get_coordinate_system()
        payload = _dispatch_tool(name, args, cs, trace_id=trace_id, parent_step_index=step_index)
    except SafetyError as exc:
        logging.warning("safety block: %s", exc)
        payload = json.dumps({"error": str(exc)})
        error = exc
    except ValueError as exc:
        logging.warning("validation block: %s", exc)
        payload = json.dumps({"error": str(exc)})
        error = exc
    except pyautogui.FailSafeException as exc:
        logging.warning("pyautogui fail-safe: %s", exc)
        payload = json.dumps(
            {"error": "fail_safe", "detail": "PyAutoGUI fail-safe triggered"}
        )
    except Exception as exc:
        logging.error(
            "tool error: %s",
            trace_module.sanitize_message(args, str(exc)),
        )
        error = exc
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        if payload is not None:
            try:
                result_data: Any = json.loads(payload)
            except json.JSONDecodeError:
                result_data = payload
        elif error is not None:
            result_data = {"error": str(error)}
        else:
            result_data = None

        if screenshot_path is None and name == "screenshot" and isinstance(result_data, dict):
            screenshot_path = result_data.get("saved_path")

        error_kind = None
        error_message = None
        if error is not None:
            error_kind = "safety_block" if isinstance(error, SafetyError) else "unknown"
            error_message = str(error)
        else:
            failure = _failure_for_result(result_data)
            if failure is not None:
                error_kind, error_message = failure

        task_runner_owns_trace = (
            name == "run_task_plan"
            and error is None
            and isinstance(result_data, dict)
            and result_data.get("trace_id") == trace_id
        )
        if not task_runner_owns_trace:
            try:
                trace_module.record_step(
                    trace_id=trace_id,
                    step_index=step_index,
                    tool=name,
                    args=args,
                    result=result_data,
                    duration_ms=duration_ms,
                    screenshot_path=screenshot_path,
                    error_kind=error_kind,
                    error_message=error_message,
                )
            except Exception as exc:
                logging.warning("trace record failed: %s", exc)

        if error is not None and not isinstance(error, (SafetyError, ValueError)):
            raise error

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return payload  # type: ignore[return-value]

    if isinstance(data, dict) and "timestamp" not in data:
        data["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    if name in _MANIFEST_TOOL_NAMES and isinstance(data, dict):
        data = _attach_trace_manifest(data, trace_id)

    return json.dumps(data)


def _dispatch_tool(
    name: str,
    args: dict,
    cs: CoordinateSystem,
    trace_id: str | None = None,
    parent_step_index: int | str | None = None,
) -> str:
    if name == "get_ui_snapshot":
        from computer_use import snapshot
        scope = args.get("scope", "foreground")
        include_screenshot = args.get("include_screenshot", False)
        result = snapshot.get_ui_snapshot(
            scope,
            include_screenshot,
            trace_id=trace_id,
        )
        return json.dumps(result)

    if name == "screenshot":
        config = load_config()
        screenshot_dir = Path(config["screenshot_dir"]).resolve()
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        monitor = args.get("monitor", config.get("display", {}).get("default_monitor", 0))
        monitors = cs.get_monitors()
        validate_monitor_index(monitor, len(monitors))

        if monitor == 0:
            width, height = cs.virtual_width, cs.virtual_height
            capture_left, capture_top = cs.virtual_left, cs.virtual_top
        else:
            mon = cs.monitors[monitor - 1]
            width, height = mon["width"], mon["height"]
            capture_left, capture_top = mon["left"], mon["top"]

        save_path = args.get("save_path")
        if save_path:
            requested_path = Path(save_path).resolve()
            if requested_path == screenshot_dir or screenshot_dir not in requested_path.parents:
                raise SafetyError(
                    "Screenshot save_path must be inside configured screenshot_dir"
                )
            if not requested_path.parent.is_dir():
                raise SafetyError("Screenshot save_path parent directory does not exist")
            save_path = str(requested_path)

        sensitive = False
        if config["safety"]["screenshot_sensitive_window_check"]:
            bounds = (
                capture_left,
                capture_top,
                capture_left + width,
                capture_top + height,
            )
            windows = get_top_level_windows_in_rect(bounds)
            if windows is None:
                windows = [
                    inspect_point(
                        capture_left + width // 2,
                        capture_top + height // 2,
                    )
                ]
            for info in windows:
                try:
                    check_target_window(
                        info.process_name, info.class_name, info.control_type
                    )
                except SafetyError as exc:
                    logging.warning("screenshot sensitive window: %s", exc)
                    sensitive = True
                    break

        if not save_path:
            timestamp = datetime.now(timezone.utc)
            filename = timestamp.strftime("%Y%m%dT%H%M%S_%f")[:-3]
            save_path = str(screenshot_dir / f"screenshot_{filename}_m{monitor}.png")

        result: dict[str, Any] = {
            "screenshot_taken": True,
            "monitor": monitor,
            "width": width,
            "height": height,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        }

        try:
            if sensitive:
                saved = save_redacted_image(save_path, width, height)
                result["redacted"] = True
            else:
                saved = save_screenshot(save_path, monitor=monitor)
            result["saved_path"] = str(saved)
        except Exception as exc:
            logging.warning("screenshot save failed: %s", exc)
            return json.dumps({"error": f"Failed to save screenshot: {exc}"})

        return json.dumps(result)

    if name == "get_monitors":
        monitors = cs.get_monitors()
        return json.dumps(
            [
                {
                    "index": m.index,
                    "primary": m.primary,
                    "left": m.left,
                    "top": m.top,
                    "width": m.width,
                    "height": m.height,
                }
                for m in monitors
            ]
        )

    if name == "click":
        return _dispatch_pointer_tool("click", args, click, cs)

    if name == "move_to":
        return _dispatch_pointer_tool("move_to", args, move_to, cs)

    if name == "scroll":
        amount = args.get("amount")
        direction = args.get("direction")
        clicks = args.get("clicks", 3)
        x = args.get("x")
        y = args.get("y")
        if x is not None and y is not None:
            size = cs.get_screen_size()
            validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
            info = inspect_point(x, y)
            check_target_window(
                info.process_name, info.class_name, info.control_type
            )
        else:
            current_x, current_y = _current_logical_position()
            size = cs.get_screen_size()
            validate_coordinate(
                current_x,
                current_y,
                size.width,
                size.height,
                monitors=cs.monitors,
            )
            info = inspect_point(current_x, current_y)
            check_target_window(
                info.process_name, info.class_name, info.control_type
            )
        scroll(amount=amount, x=x, y=y, direction=direction, clicks=clicks)
        return json.dumps({"scrolled": True, "amount": amount, "direction": direction, "clicks": clicks, "x": x, "y": y})

    if name == "type":
        text = args["text"]
        validate_text_input(text)
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
        type_text(text)
        return json.dumps({"typed": True, "length": len(text)})

    if name == "key_combo":
        keys = args["keys"]
        x, y = _current_logical_position()
        size = cs.get_screen_size()
        validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
        info = inspect_point(x, y)
        check_target_window(info.process_name, info.class_name, info.control_type)
        key_combo(*keys)
        return json.dumps({"pressed": keys})

    if name == "mouse_down":
        x = args["x"]
        y = args["y"]
        button = args.get("button", "left")
        size = cs.get_screen_size()
        validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
        info = inspect_point(x, y)
        check_target_window(info.process_name, info.class_name, info.control_type)
        mouse_down(x, y, button=button)
        return json.dumps({"mouse_down": True, "x": x, "y": y, "button": button})

    if name == "mouse_up":
        x = args.get("x")
        y = args.get("y")
        button = args.get("button", "left")
        if x is not None and y is not None:
            size = cs.get_screen_size()
            validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
            info = inspect_point(x, y)
            check_target_window(info.process_name, info.class_name, info.control_type)
        else:
            x, y = _current_logical_position()
            size = cs.get_screen_size()
            validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
            info = inspect_point(x, y)
            check_target_window(info.process_name, info.class_name, info.control_type)
        mouse_up(x, y, button=button)
        return json.dumps({"mouse_up": True, "x": x, "y": y, "button": button})

    if name == "drag":
        start_x = args["start_x"]
        start_y = args["start_y"]
        end_x = args["end_x"]
        end_y = args["end_y"]
        duration = args.get("duration", DEFAULT_MOVE_DURATION)
        button = args.get("button", "left")
        validate_duration(duration)
        size = cs.get_screen_size()
        validate_coordinate(start_x, start_y, size.width, size.height, monitors=cs.monitors)
        validate_coordinate(end_x, end_y, size.width, size.height, monitors=cs.monitors)
        start_info = inspect_point(start_x, start_y)
        check_target_window(
            start_info.process_name,
            start_info.class_name,
            start_info.control_type,
        )
        end_info = inspect_point(end_x, end_y)
        check_target_window(
            end_info.process_name,
            end_info.class_name,
            end_info.control_type,
        )
        drag(start_x, start_y, end_x, end_y, duration=duration, button=button)
        return json.dumps({
            "dragged": True,
            "start_x": start_x,
            "start_y": start_y,
            "end_x": end_x,
            "end_y": end_y,
            "duration": duration,
            "button": button,
        })

    if name == "key_down":
        key = args["key"]
        x, y = _current_logical_position()
        size = cs.get_screen_size()
        validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
        info = inspect_point(x, y)
        check_target_window(info.process_name, info.class_name, info.control_type)
        key_down(key)
        return json.dumps({"key_down": True, "key": key})

    if name == "key_up":
        key = args["key"]
        x, y = _current_logical_position()
        size = cs.get_screen_size()
        validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
        info = inspect_point(x, y)
        check_target_window(info.process_name, info.class_name, info.control_type)
        key_up(key)
        return json.dumps({"key_up": True, "key": key})

    if name == "press_key":
        key = args["key"]
        x, y = _current_logical_position()
        size = cs.get_screen_size()
        validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
        info = inspect_point(x, y)
        check_target_window(info.process_name, info.class_name, info.control_type)
        press_key(key)
        return json.dumps({"pressed": True, "key": key})

    if name == "find_control":
        result = find_control(
            name=args.get("name"),
            automation_id=args.get("automation_id"),
            control_type=args.get("control_type"),
            class_name=args.get("class_name"),
            scope=args.get("scope", "desktop"),
            window_name=args.get("window_name"),
            match=args.get("match", "contains"),
            sensitive_check=args.get("sensitive_check", True),
        )
        return json.dumps(result)

    if name == "inspect_point":
        info = inspect_point(args["x"], args["y"])
        return json.dumps({
            "name": info.name,
            "control_type": info.control_type,
            "class_name": info.class_name,
            "process_name": info.process_name,
            "is_password": info.is_password,
            "rect": (
                {"left": info.rect[0], "top": info.rect[1], "right": info.rect[2], "bottom": info.rect[3]}
                if info.rect is not None else None
            ),
            "center": (
                {"x": info.center[0], "y": info.center[1]}
                if info.center is not None else None
            ),
        })

    if name == "wait_for_window":
        result = wait_for_window(
            name=args["name"],
            exists=args.get("exists", True),
            timeout=args.get("timeout", 10),
        )
        return json.dumps(result)

    if name == "wait_for_control":
        result = wait_for_control(
            name=args.get("name"),
            automation_id=args.get("automation_id"),
            control_type=args.get("control_type"),
            exists=args.get("exists", True),
            timeout=args.get("timeout", 10),
        )
        return json.dumps(result)

    if name == "sleep":
        duration = args.get("duration", 1)
        if duration != duration:
            raise ValueError("duration must be a real number, got NaN")
        if duration < 0:
            raise ValueError(f"duration must be non-negative, got {duration}")
        if duration > MAX_SLEEP_DURATION:
            raise ValueError(f"duration must not exceed {MAX_SLEEP_DURATION} seconds, got {duration}")
        time.sleep(duration)
        return json.dumps({"slept": True, "duration": duration})

    if name == "launch_app":
        result = launch_app(name=args["name"])
        return json.dumps(result)

    if name == "batch":
        return _batch_tool(args, trace_id=trace_id, parent_step_index=parent_step_index)

    if name == "click_by_uid":
        from computer_use import snapshot
        uid = args["uid"]
        snapshot_arg = args.get("snapshot")
        if not snapshot_arg:
            return json.dumps({"error": "snapshot is required for click_by_uid"})
        duration = args.get("duration", DEFAULT_MOVE_DURATION)
        button = args.get("button", "left")
        result = snapshot.click_by_uid(uid, snapshot_arg, duration=duration, button=button)
        if result.get("error") == "stale_uid":
            return json.dumps({"error": "stale_uid", "uid": uid})
        return json.dumps(result)

    if name == "click_by_text":
        from computer_use import composite
        result = composite.click_by_text(
            text=args["text"],
            match=args.get("match", "contains"),
            scope=args.get("scope", "foreground"),
            duration=args.get("duration", DEFAULT_MOVE_DURATION),
            button=args.get("button", "left"),
        )
        return json.dumps(result)

    if name == "open_menu":
        from computer_use import composite
        result = composite.open_menu(
            path=args["path"],
            interval=args.get("interval", 0.3),
            duration=args.get("duration", DEFAULT_MOVE_DURATION),
            button=args.get("button", "left"),
        )
        return json.dumps(result)

    if name == "fill_form":
        from computer_use import composite
        result = composite.fill_form(
            fields=args["fields"],
            duration=args.get("duration", DEFAULT_MOVE_DURATION),
            type_interval=args.get("type_interval", 0.01),
        )
        return json.dumps(result)

    if name == "scroll_until":
        from computer_use import composite
        result = composite.scroll_until(
            target_text=args["target_text"],
            direction=args.get("direction", "down"),
            max_attempts=args.get("max_attempts", 10),
            clicks=args.get("clicks", 3),
            interval=args.get("interval", 0.3),
        )
        return json.dumps(result)

    if name == "run_task_plan":
        from computer_use import runner
        result = runner.run_task_plan(
            steps=args["steps"],
            trace_id=args.get("trace_id") or trace_id,
            goal=args.get("goal"),
            final_state=args.get("final_state", False),
            capture_screenshots=args.get("capture_screenshots", True),
        )
        return json.dumps(result)

    if name == "retry_step":
        from computer_use import runner
        result = runner.retry_step(
            trace_id=args["trace_id"],
            step_index=args["step_index"],
            mode=args.get("mode", "single"),
        )
        return json.dumps(result)

    if name == "review_task":
        from computer_use import review
        result = review.review_task(trace_id=args["trace_id"])
        return json.dumps(result)

    raise ValueError(f"Unknown tool: {name}")


def _save_ui_snapshot(snapshot: dict[str, Any], trace_id: str) -> str:
    """Persist a snapshot dict to disk and return its file path."""
    snapshot_dir = trace_module.artifact_dir(trace_id, "snapshots")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = snapshot_dir / f"snapshot_{timestamp}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _batch_tool(
    args: dict,
    trace_id: str | None = None,
    parent_step_index: int | str | None = None,
) -> str:
    """Execute a list of tool calls sequentially and return aggregated results."""
    actions = args["actions"]
    stop_on_error = args.get("stop_on_error", True)
    final_screenshot = args.get("final_screenshot", False)
    monitor = args.get("screenshot_monitor", 1)
    trace_id = trace_id or trace_module.generate_trace_id()
    from computer_use.runner import MAX_TASK_STEPS

    if len(actions) > MAX_TASK_STEPS:
        raise ValueError(
            f"batch exceeds step budget of {MAX_TASK_STEPS} actions"
        )

    results: list[dict[str, Any]] = []
    failed_index: int | None = None

    for i, action in enumerate(actions):
        requested_tool = action.get("tool")
        try:
            tool_name = normalize_nested_tool_name(
                requested_tool,
                allowed_tools=BATCH_ACTION_TOOL_NAMES,
            )
        except InvalidToolName as exc:
            results.append(
                {
                    "index": i,
                    "tool": None,
                    "requested_tool": requested_tool,
                    "result": {
                        "error": "invalid_tool",
                        "requested_tool": exc.requested_tool,
                        "candidates": exc.candidates,
                        "allowed_tools": list(BATCH_ACTION_TOOL_NAMES),
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                }
            )
            failed_index = i
            if stop_on_error:
                break
            continue

        tool_args = action.get("args") or {}
        capture_snapshot = action.get("capture_snapshot", False)
        snapshot_ref: Any = None
        if capture_snapshot:
            try:
                from computer_use import snapshot
                snapshot_result = snapshot.get_ui_snapshot(scope="foreground", include_screenshot=False)
                if isinstance(snapshot_result, dict) and "error" in snapshot_result:
                    snapshot_ref = snapshot_result
                else:
                    snapshot_ref = _save_ui_snapshot(snapshot_result, trace_id)
            except Exception as exc:
                snapshot_ref = {"error": str(exc)}

        if parent_step_index is not None and parent_step_index != 0:
            sub_step_index = f"{parent_step_index}.{i + 1}"
        else:
            sub_step_index = i + 1

        try:
            result_text = _call_tool(
                tool_name,
                tool_args,
                trace_context={"trace_id": trace_id, "step_index": sub_step_index},
            )
            try:
                result_data = json.loads(result_text)
            except json.JSONDecodeError:
                result_data = result_text
        except Exception as exc:
            result_data = {"error": str(exc)}

        if capture_snapshot and snapshot_ref is not None:
            if isinstance(result_data, dict):
                result_data["snapshot"] = snapshot_ref
            else:
                result_data = {"result": result_data, "snapshot": snapshot_ref}

        step_entry: dict[str, Any] = {
            "index": i,
            "tool": tool_name,
            "requested_tool": requested_tool,
            "result": result_data,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        }
        results.append(step_entry)
        if _failure_for_result(result_data) is not None:
            failed_index = i
            if stop_on_error:
                break

    top_level_error_kind = None
    if failed_index is not None and failed_index < len(results):
        failed_entry = results[failed_index]
        failure = _failure_for_result(failed_entry.get("result", failed_entry))
        if failure is not None:
            top_level_error_kind = failure[0]

    response: dict[str, Any] = {
        "results": results,
        "status": "failed" if failed_index is not None else "succeeded",
        "failed_index": failed_index,
        "error_kind": top_level_error_kind,
        "executed_count": len(results),
        "requested_count": len(actions),
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }

    if final_screenshot:
        try:
            cs = get_coordinate_system()
            validate_monitor_index(monitor, len(cs.get_monitors()))
            screenshot_text = _call_tool(
                "screenshot",
                {"monitor": monitor},
                trace_context={"trace_id": trace_id, "step_index": len(actions) + 1},
            )
            try:
                response["final_screenshot"] = json.loads(screenshot_text)
            except json.JSONDecodeError:
                response["final_screenshot"] = screenshot_text
        except Exception as exc:
            response["final_screenshot_error"] = str(exc)

    return json.dumps(response)


def _dispatch_pointer_tool(
    name: str,
    args: dict,
    action: Callable[..., Any],
    cs: CoordinateSystem,
) -> str:
    """Dispatch click/move_to by control name or by explicit coordinates."""
    result_key = "clicked" if name == "click" else "moved"
    duration = args.get("duration", DEFAULT_MOVE_DURATION)
    validate_duration(duration)

    target_name = args.get("target_name")
    match = args.get("match", "contains")
    button = args.get("button", "left") if name == "click" else None
    is_double = name == "click" and args.get("double_click", False)

    if target_name:
        result = find_control(
            name=target_name,
            match=match,
            scope="desktop",
            sensitive_check=False,
        )
        if result.get("found"):
            center = result.get("center")
            if center is None:
                raise ValueError("Control found but has no center")
            x, y = center["x"], center["y"]
            size = cs.get_screen_size()
            validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
            check_target_window(
                result.get("process_name"),
                result.get("class_name"),
                result.get("control_type"),
            )
            if name == "click":
                if is_double:
                    double_click(x, y, duration, button=button)
                elif button and button != "left":
                    click(x, y, duration, button=button)
                else:
                    action(x, y, duration)
            else:
                action(x, y, duration)
            response = {
                result_key: True,
                "x": x,
                "y": y,
                "duration": duration,
                "mode": "uia",
                "target_name": target_name,
                "match": match,
                "control": {
                    "name": result.get("name"),
                    "control_type": result.get("control_type"),
                    "class_name": result.get("class_name"),
                    "process_name": result.get("process_name"),
                },
            }
            if name == "click":
                response["button"] = button
                response["double_click"] = is_double
            return json.dumps(response)

        # Control not found: fall back to coordinates if they were also provided.
        if "x" in args and "y" in args:
            return _run_mouse_tool(
                name, args["x"], args["y"], duration, action, cs,
                button=button, is_double=is_double,
            )

        return json.dumps({
            "error": (
                f"Control '{target_name}' not found. "
                "Use screenshot or find_control to locate it."
            )
        })

    if "x" in args and "y" in args:
        return _run_mouse_tool(
            name, args["x"], args["y"], duration, action, cs,
            button=button, is_double=is_double,
        )

    raise ValueError(f"Either target_name or both x and y are required for {name}")


def _run_mouse_tool(
    name: str,
    x: int,
    y: int,
    duration: float,
    action: Callable[..., Any],
    cs: CoordinateSystem,
    button: str | None = None,
    is_double: bool = False,
) -> str:
    """Run a mouse tool with shared validation, checks, and JSON response."""
    validate_duration(duration)
    size = cs.get_screen_size()
    validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
    info = inspect_point(x, y)
    check_target_window(info.process_name, info.class_name, info.control_type)
    if name == "click":
        if is_double:
            double_click(x, y, duration, button=button or "left")
        elif button and button != "left":
            click(x, y, duration, button=button)
        else:
            action(x, y, duration)
    else:
        action(x, y, duration)
    result_key = "clicked" if name == "click" else "moved"
    response = {
        result_key: True,
        "x": x,
        "y": y,
        "duration": duration,
        "mode": "coordinate",
    }
    if name == "click":
        response["button"] = button or "left"
        response["double_click"] = is_double
    return json.dumps(response)


def _current_logical_position() -> tuple[int, int]:
    """Return the current cursor position in physical virtual screen pixels."""
    x, y = pyautogui.position()
    return int(x), int(y)


def _handle_tool_call(name: str, arguments: dict) -> str:
    """Execute one MCP call without exposing input values in outer errors."""
    safe_arguments = arguments or {}
    try:
        return _call_tool(name, safe_arguments)
    except Exception as exc:
        message = trace_module.sanitize_message(safe_arguments, str(exc))
        logging.error("tool error: %s", message)
        return json.dumps({"error": message})


async def serve() -> None:
    _setup_logging()
    server = Server("computer-use")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        result = _handle_tool_call(name, arguments)
        return [TextContent(type="text", text=result)]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    import asyncio

    asyncio.run(serve())


if __name__ == "__main__":
    main()
