"""MCP Server exposing Computer Use tools to MCP clients."""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyautogui
from PIL import Image as PILImage
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import GetPromptResult, Prompt, PromptMessage, TextContent, Tool

from computer_use import guidance
from computer_use.config import load_config
from computer_use.core import (
    DEFAULT_MOVE_DURATION,
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
    TASK_STEP_TOOL_NAMES,
    normalize_nested_tool_name,
)

from computer_use.tools.schemas import (
    TOOLS,
    _MANIFEST_TOOL_NAMES,
    _TASK_CONTEXT_EXCLUDED_TOOLS,
    _TASK_MANAGEMENT_TOOLS,
    MAX_SLEEP_DURATION,
)


def _setup_logging(log_dir: Path | None = None) -> None:
    if log_dir is None:
        log_dir = load_config().get("log_dir", Path.home() / ".computer-use" / "logs")
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


_NEXT_ACTION_INVALID_TOOL = (
    "Use one of allowed_tools; do not include MCP namespace prefixes in nested "
    "batch/run_task_plan steps."
)
_NEXT_ACTION_UI_NOT_FOUND = (
    "Call get_ui_snapshot or screenshot, then retry with a better target."
)
_NEXT_ACTION_FAIL_SAFE = (
    "Confirm cursor/remote-control state, then re-observe before sending input."
)
_NEXT_ACTION_COORDINATE_OR_SAFETY = (
    "Call get_monitors and inspect_point before retrying."
)

#: Maximum JSON-encoded length a get_ui_snapshot response may inline before it is
#: replaced by a compact `snapshot_output_too_large` error. ~200K chars ≈ 50K
#: tokens. Foreground snapshots (5-30KB) stay well below this; desktop-level UIA
#: trees can exceed 200KB and would otherwise dominate the model context.
MAX_INLINE_SNAPSHOT_CHARS = 200_000


@dataclass(frozen=True)
class ExecutionContext:
    task_id: str
    trace_id: str
    step_index: int | str
    top_level: bool
    is_standalone: bool
    screenshot_path: str | None = None


PROMPTS: list[Prompt] = [
    Prompt(
        name=item["name"],
        description=item["description"],
        arguments=[],
    )
    for item in guidance.list_prompt_metadata()
]


def _get_prompt(name: str) -> GetPromptResult:
    try:
        text = guidance.prompt_text(name)
    except KeyError as exc:
        raise ValueError(f"Unknown prompt: {name}") from exc
    metadata = next(item for item in guidance.list_prompt_metadata() if item["name"] == name)
    return GetPromptResult(
        description=metadata["description"],
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=text),
            )
        ],
    )


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


def _is_fail_safe_exception(exc: BaseException) -> bool:
    """Detect PyAutoGUI fail-safe even if the module was re-imported."""
    return exc.__class__.__name__ == "FailSafeException"


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


def _with_next_action(result: dict[str, Any], next_action: str) -> dict[str, Any]:
    if result.get("error") and "next_action" not in result:
        result["next_action"] = next_action
    return result


def _with_ui_not_found_next_action(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("error") == "ui_not_found":
        return _with_next_action(result, _NEXT_ACTION_UI_NOT_FOUND)
    return result


def _is_coordinate_validation_error(exc: ValueError) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in ("coordinate", "coordinates", "monitor", "screen", "bounds", "point")
    )


def _attach_trace_manifest(data: dict[str, Any], trace_id: str) -> dict[str, Any]:
    """Derive response trace paths and artifacts from the flat trace manifest."""
    data_trace_id = data.get("trace_id")
    target_trace_id = data_trace_id if isinstance(data_trace_id, str) else trace_id
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


def _call_tool(
    name: str,
    args: dict,
    trace_context: dict[str, Any] | None = None,
    *,
    context: ExecutionContext | None = None,
) -> str:
    dispatch_args = dict(args)
    if name not in _TASK_MANAGEMENT_TOOLS:
        dispatch_args.pop("task_id", None)
    logging.info(
        "tool=%s args=%s", name, trace_module.sanitize_for_logging(dispatch_args)
    )
    if context is not None:
        trace_id = context.trace_id
        step_index = context.step_index
        screenshot_path = context.screenshot_path
        task_id = context.task_id
        is_standalone = context.is_standalone
    elif trace_context:
        trace_id = trace_context["trace_id"]
        step_index = trace_context["step_index"]
        screenshot_path = trace_context.get("screenshot_path")
        task_id = trace_context.get("task_id")
        is_standalone = bool(trace_context.get("is_standalone", False))
    elif name == "run_task_plan" and args.get("trace_id"):
        trace_id = args["trace_id"]
        step_index = 0
        screenshot_path = None
        task_id = None
        is_standalone = False
    else:
        trace_id = trace_module.generate_trace_id()
        step_index = 0
        screenshot_path = None
        task_id = None
        is_standalone = False
    start = time.perf_counter()
    payload: str | None = None
    error: Exception | None = None
    try:
        cs = get_coordinate_system()
        dispatch_kwargs: dict[str, Any] = {
            "trace_id": trace_id,
            "parent_step_index": step_index,
        }
        if task_id is not None:
            dispatch_kwargs["task_id"] = task_id
            dispatch_kwargs["is_standalone"] = is_standalone
        payload = _dispatch_tool(name, dispatch_args, cs, **dispatch_kwargs)
    except SafetyError as exc:
        logging.warning("safety block: %s", exc)
        payload = json.dumps(
            {"error": str(exc), "next_action": _NEXT_ACTION_COORDINATE_OR_SAFETY}
        )
        error = exc
    except ValueError as exc:
        logging.warning("validation block: %s", exc)
        result = {"error": str(exc)}
        if _is_coordinate_validation_error(exc):
            result["next_action"] = _NEXT_ACTION_COORDINATE_OR_SAFETY
        payload = json.dumps(result)
        error = exc
    except pyautogui.FailSafeException as exc:
        logging.warning("pyautogui fail-safe: %s", exc)
        payload = json.dumps(
            {
                "error": "fail_safe",
                "detail": "PyAutoGUI fail-safe triggered",
                "next_action": _NEXT_ACTION_FAIL_SAFE,
            }
        )
    except Exception as exc:
        if _is_fail_safe_exception(exc):
            logging.warning("pyautogui fail-safe: %s", exc)
            payload = json.dumps(
                {
                    "error": "fail_safe",
                    "detail": "PyAutoGUI fail-safe triggered",
                    "next_action": _NEXT_ACTION_FAIL_SAFE,
                }
            )
        else:
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
        if name not in _TASK_CONTEXT_EXCLUDED_TOOLS and not task_runner_owns_trace:
            try:
                trace_module.record_step(
                    trace_id=trace_id,
                    step_index=step_index,
                    tool=name,
                    args=dispatch_args,
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

    if context is not None and isinstance(data, dict):
        data.setdefault("task_id", context.task_id)
        data.setdefault("trace_id", context.trace_id)
        try:
            from computer_use import task_session

            data.setdefault("task_path", task_session.get_task(context.task_id)["task_path"])
        except Exception:
            pass

    return json.dumps(data)


def _task_error(exc: Exception) -> dict[str, Any]:
    from computer_use import task_session

    if isinstance(exc, task_session.TaskNotFoundError):
        return {"error": "task_not_found", "task_id": exc.task_id}
    if isinstance(exc, task_session.TaskClosedError):
        return {"error": "task_closed", "task_id": exc.task_id}
    if isinstance(exc, task_session.TraceTaskConflictError):
        return {
            "error": "trace_task_conflict",
            "task_id": exc.task_id,
            "trace_id": exc.trace_id,
            "existing_task_id": exc.existing_task_id,
        }
    raise exc


def _dispatch_tool(
    name: str,
    args: dict,
    cs: CoordinateSystem,
    trace_id: str | None = None,
    parent_step_index: int | str | None = None,
    task_id: str | None = None,
    is_standalone: bool = False,
) -> str:
    if name == "get_ui_snapshot":
        if args.get("scope") == "desktop" and args.get("include_screenshot") is True:
            return json.dumps(
                {
                    "error": "high_cost_snapshot_blocked",
                    "next_action": (
                        "Use get_ui_snapshot(scope='foreground', include_screenshot=false). "
                        "If cross-window context is needed, use get_ui_snapshot(scope='desktop', include_screenshot=false) "
                        "or find_control with narrow criteria."
                    ),
                }
            )
        from computer_use import snapshot
        scope = args.get("scope", "foreground")
        include_screenshot = args.get("include_screenshot", False)
        result = snapshot.get_ui_snapshot(
            scope,
            include_screenshot,
            trace_id=trace_id,
        )
        serialized = json.dumps(result)
        if len(serialized) > MAX_INLINE_SNAPSHOT_CHARS:
            return json.dumps(
                {
                    "error": "snapshot_output_too_large",
                    "scope": scope,
                    "control_count": len(result.get("controls", [])) if isinstance(result, dict) else None,
                    "truncated": True,
                    "next_action": (
                        "Use scope='foreground', find_control, click_by_text, or narrower criteria. "
                        "Do not read full desktop snapshot output."
                    ),
                }
            )
        return serialized

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

        coordinate_space = "virtual_desktop" if monitor == 0 else "monitor"
        result["coordinate_space"] = coordinate_space
        result["capture_left"] = capture_left
        result["capture_top"] = capture_top

        sidecar = {
            "schema_version": 1,
            "screenshot_path": str(saved),
            "monitor": monitor,
            "coordinate_space": coordinate_space,
            "capture_left": capture_left,
            "capture_top": capture_top,
            "width": width,
            "height": height,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        }
        metadata_path = str(saved) + ".json"
        Path(metadata_path).write_text(
            json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
        )
        result["metadata_path"] = metadata_path

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

    if name == "click_on_screenshot":
        return _handle_click_on_screenshot(args, cs, trace_id)

    if name == "crop_screenshot":
        return _handle_crop_screenshot(args, cs)

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
        return _batch_tool(
            args,
            trace_id=trace_id,
            parent_step_index=parent_step_index,
            task_id=task_id,
            is_standalone=is_standalone,
        )

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
        return json.dumps(_with_ui_not_found_next_action(result))

    if name == "open_menu":
        from computer_use import composite
        result = composite.open_menu(
            path=args["path"],
            interval=args.get("interval", 0.3),
            duration=args.get("duration", DEFAULT_MOVE_DURATION),
            button=args.get("button", "left"),
        )
        return json.dumps(_with_ui_not_found_next_action(result))

    if name == "fill_form":
        from computer_use import composite
        result = composite.fill_form(
            fields=args["fields"],
            duration=args.get("duration", DEFAULT_MOVE_DURATION),
            type_interval=args.get("type_interval", 0.01),
        )
        return json.dumps(_with_ui_not_found_next_action(result))

    if name == "scroll_until":
        from computer_use import composite
        result = composite.scroll_until(
            target_text=args["target_text"],
            direction=args.get("direction", "down"),
            max_attempts=args.get("max_attempts", 10),
            clicks=args.get("clicks", 3),
            interval=args.get("interval", 0.3),
        )
        return json.dumps(_with_ui_not_found_next_action(result))

    if name == "run_task_plan":
        from computer_use import runner
        result = runner.run_task_plan(
            steps=args["steps"],
            trace_id=args.get("trace_id") or trace_id,
            goal=args.get("goal"),
            final_state=args.get("final_state", False),
            capture_screenshots=args.get("capture_screenshots", True),
            task_id=task_id,
            is_standalone=is_standalone,
        )
        return json.dumps(result)

    if name == "retry_step":
        from computer_use import runner
        result = runner.retry_step(
            trace_id=args["trace_id"],
            step_index=args["step_index"],
            mode=args.get("mode", "single"),
            task_id=task_id,
            is_standalone=is_standalone,
        )
        return json.dumps(result)

    if name == "review_task":
        from computer_use import review
        result = review.review_task(trace_id=args["trace_id"], detail=args.get("detail", False))
        return json.dumps(result)

    if name == "review_task_session":
        from computer_use import review
        try:
            result = review.review_task_session(
                task_id=args["task_id"],
                detail=args.get("detail", False),
            )
        except Exception as exc:
            result = _task_error(exc)
        return json.dumps(result)

    if name in {
        "start_task",
        "finish_task",
        "get_task",
        "list_tasks",
    }:
        from computer_use import task_session

        try:
            if name == "start_task":
                result = task_session.start_task(args["goal"])
            elif name == "finish_task":
                result = task_session.finish_task(
                    args["task_id"],
                    summary=args.get("summary"),
                    cancel=args.get("cancel", False),
                )
            elif name == "get_task":
                result = task_session.get_task(args["task_id"])
            elif name == "list_tasks":
                result = {
                    "tasks": task_session.list_tasks(
                        date=args.get("date"),
                        status=args.get("status"),
                        limit=args.get("limit"),
                    )
                }
            else:
                raise ValueError(f"Unhandled task tool: {name}")
        except Exception as exc:
            result = _task_error(exc)
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
    task_id: str | None = None,
    is_standalone: bool = False,
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
                        "next_action": _NEXT_ACTION_INVALID_TOOL,
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
            if task_id:
                result_text = _call_tool(
                    tool_name,
                    tool_args,
                    context=ExecutionContext(
                        task_id=task_id,
                        trace_id=trace_id,
                        step_index=sub_step_index,
                        top_level=False,
                        is_standalone=is_standalone,
                    ),
                )
            else:
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
            if task_id:
                screenshot_text = _call_tool(
                    "screenshot",
                    {"monitor": monitor},
                    context=ExecutionContext(
                        task_id=task_id,
                        trace_id=trace_id,
                        step_index=len(actions) + 1,
                        top_level=False,
                        is_standalone=is_standalone,
                    ),
                )
            else:
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


def _read_screenshot_metadata(screenshot_path: str) -> dict[str, Any] | None:
    metadata_path = str(screenshot_path) + ".json"
    meta_file = Path(metadata_path)
    if not meta_file.exists():
        return None
    return json.loads(meta_file.read_text(encoding="utf-8"))


def _handle_click_on_screenshot(
    args: dict[str, Any],
    cs: CoordinateSystem,
    trace_id: str | None = None,
) -> str:
    screenshot_path = args["screenshot_path"]
    image_x = args["image_x"]
    image_y = args["image_y"]
    button = args.get("button", "left")
    duration = args.get("duration", DEFAULT_MOVE_DURATION)
    is_double = args.get("double_click", False)

    meta = _read_screenshot_metadata(screenshot_path)
    if meta is None:
        return json.dumps({
            "error": "screenshot_metadata_not_found",
            "next_action": "Call the MCP screenshot tool first and use its saved_path.",
        })

    if not Path(screenshot_path).exists():
        return json.dumps({
            "error": "screenshot_file_not_found",
            "next_action": "Re-run the MCP screenshot tool; the requested screenshot file is missing.",
        })

    img_w = meta.get("width", 0)
    img_h = meta.get("height", 0)
    if not (0 <= image_x < img_w and 0 <= image_y < img_h):
        return json.dumps({
            "error": "image_coordinate_out_of_bounds",
            "width": img_w,
            "height": img_h,
        })

    screen_x = meta["capture_left"] + image_x
    screen_y = meta["capture_top"] + image_y

    validate_duration(duration)
    size = cs.get_screen_size()
    validate_coordinate(screen_x, screen_y, size.width, size.height, monitors=cs.monitors)
    info = inspect_point(screen_x, screen_y)
    check_target_window(info.process_name, info.class_name, info.control_type)

    if is_double:
        double_click(screen_x, screen_y, duration, button=button)
    elif button and button != "left":
        click(screen_x, screen_y, duration, button=button)
    else:
        click(screen_x, screen_y, duration)

    return json.dumps({
        "clicked": True,
        "screenshot_path": str(screenshot_path),
        "image_x": image_x,
        "image_y": image_y,
        "screen_x": screen_x,
        "screen_y": screen_y,
        "coordinate_space": meta.get("coordinate_space", "monitor"),
        "monitor": meta.get("monitor"),
    })


def _handle_crop_screenshot(
    args: dict[str, Any],
    cs: CoordinateSystem,
) -> str:
    screenshot_path = args["screenshot_path"]
    x = args["x"]
    y = args["y"]
    crop_width = args["width"]
    crop_height = args["height"]

    meta = _read_screenshot_metadata(screenshot_path)
    if meta is None:
        return json.dumps({
            "error": "screenshot_metadata_not_found",
            "next_action": "Call the MCP screenshot tool first and use its saved_path.",
        })

    if not Path(screenshot_path).exists():
        return json.dumps({
            "error": "screenshot_file_not_found",
            "next_action": "Re-run the MCP screenshot tool; the requested screenshot file is missing.",
        })

    src_w = meta.get("width", 0)
    src_h = meta.get("height", 0)
    if x < 0 or y < 0 or x + crop_width > src_w or y + crop_height > src_h:
        return json.dumps({
            "error": "image_coordinate_out_of_bounds",
            "width": src_w,
            "height": src_h,
        })

    config = load_config()
    screenshot_dir = Path(config["screenshot_dir"]).resolve()
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")[:-3]
    crop_path = str(screenshot_dir / f"crop_{timestamp}.png")

    img = PILImage.open(screenshot_path)
    cropped = img.crop((x, y, x + crop_width, y + crop_height))
    cropped.save(crop_path)

    crop_capture_left = meta["capture_left"] + x
    crop_capture_top = meta["capture_top"] + y
    crop_meta = {
        "schema_version": 1,
        "screenshot_path": crop_path,
        "source_screenshot_path": str(screenshot_path),
        "monitor": meta.get("monitor"),
        "coordinate_space": meta.get("coordinate_space", "monitor"),
        "capture_left": crop_capture_left,
        "capture_top": crop_capture_top,
        "width": crop_width,
        "height": crop_height,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }
    crop_meta_path = crop_path + ".json"
    Path(crop_meta_path).write_text(
        json.dumps(crop_meta, ensure_ascii=False), encoding="utf-8"
    )

    return json.dumps({
        "cropped": True,
        "saved_path": crop_path,
        "metadata_path": crop_meta_path,
        "source_screenshot_path": str(screenshot_path),
        "capture_left": crop_capture_left,
        "capture_top": crop_capture_top,
        "width": crop_width,
        "height": crop_height,
    })


def _current_logical_position() -> tuple[int, int]:
    """Return the current cursor position in physical virtual screen pixels."""
    x, y = pyautogui.position()
    return int(x), int(y)


def _task_kind_for_tool(name: str) -> str:
    if name == "batch":
        return "batch"
    if name == "run_task_plan":
        return "task_plan"
    return "atomic"


def _establish_context(name: str, args: dict) -> ExecutionContext:
    from computer_use import task_session

    explicit_task_id = args.get("task_id")
    created_standalone_task_id: str | None = None
    try:
        if explicit_task_id:
            task_id = explicit_task_id
            is_standalone = False
            task_session.get_task(task_id)
        else:
            task = task_session.start_standalone_task(f"{name} call")
            task_id = task["task_id"]
            created_standalone_task_id = task_id
            is_standalone = True

        if name in {"run_task_plan", "retry_step"} and args.get("trace_id"):
            trace_id = args["trace_id"]
        else:
            trace_id = trace_module.generate_trace_id()

        task_session.register_trace(
            task_id,
            trace_id,
            kind=_task_kind_for_tool(name),
            tool=name,
        )
        trace_module.write_trace_meta(trace_id, task_id=task_id)
    except Exception:
        if created_standalone_task_id is not None:
            try:
                task_session.finish_task(
                    created_standalone_task_id,
                    summary="context establishment failed",
                    cancel=True,
                )
            except Exception as cleanup_exc:
                logging.warning("standalone task cleanup failed: %s", cleanup_exc)
        raise
    return ExecutionContext(
        task_id=task_id,
        trace_id=trace_id,
        step_index=0,
        top_level=True,
        is_standalone=is_standalone,
    )


def _complete_context_trace(
    context: ExecutionContext,
    result_text: str | None = None,
    error: Exception | None = None,
) -> None:
    from computer_use import task_session

    status = "failed"
    if error is None and result_text is not None:
        try:
            data: Any = json.loads(result_text)
        except json.JSONDecodeError:
            data = result_text
        status = "failed" if _failure_for_result(data) is not None else "succeeded"
    try:
        task_session.complete_trace(context.task_id, context.trace_id, status=status)
    except Exception as exc:
        logging.warning("task trace completion failed: %s", exc)


def _finish_standalone_context(context: ExecutionContext) -> None:
    if not context.is_standalone:
        return
    from computer_use import task_session

    try:
        task_session.finish_task(context.task_id)
    except Exception as exc:
        logging.warning("standalone task finish failed: %s", exc)


def _handle_tool_call(name: str, arguments: dict) -> str:
    """Execute one MCP call without exposing input values in outer errors."""
    safe_arguments = arguments or {}
    if name in _TASK_CONTEXT_EXCLUDED_TOOLS:
        try:
            data = json.loads(_dispatch_tool(name, safe_arguments, None))  # type: ignore[arg-type]
            if isinstance(data, dict) and "timestamp" not in data:
                data["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            if name in _MANIFEST_TOOL_NAMES and isinstance(data, dict):
                fallback_trace_id = safe_arguments.get("trace_id")
                if not isinstance(fallback_trace_id, str):
                    fallback_trace_id = data.get("trace_id")
                if not isinstance(fallback_trace_id, str):
                    fallback_trace_id = ""
                data = _attach_trace_manifest(data, fallback_trace_id)
            return json.dumps(data)
        except Exception as exc:
            message = trace_module.sanitize_message(safe_arguments, str(exc))
            logging.error("tool error: %s", message)
            return json.dumps({"error": message})

    if not safe_arguments.get("task_id"):
        from computer_use import task_session

        active_tasks = task_session.list_active_explicit_tasks(limit=5)
        if len(active_tasks) == 1:
            return json.dumps(
                {
                    "error": "missing_task_id",
                    "active_task_id": active_tasks[0]["task_id"],
                    "next_action": (
                        "Retry the same tool call with task_id set to active_task_id. "
                        "After start_task, every executable computer-use tool must pass task_id."
                    ),
                }
            )
        if len(active_tasks) > 1:
            return json.dumps(
                {
                    "error": "missing_task_id_ambiguous",
                    "active_task_ids": [task["task_id"] for task in active_tasks],
                    "next_action": "Choose the intended task_id or finish/cancel stale active tasks.",
                }
            )

    context: ExecutionContext | None = None
    try:
        context = _establish_context(name, safe_arguments)
        result = _call_tool(name, safe_arguments, context=context)
        _complete_context_trace(context, result_text=result)
        return result
    except Exception as exc:
        if context is not None:
            _complete_context_trace(context, error=exc)
        if hasattr(exc, "task_id"):
            try:
                data = _task_error(exc)
                data["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                return json.dumps(data)
            except Exception:
                pass
        message = trace_module.sanitize_message(safe_arguments, str(exc))
        logging.error("tool error: %s", message)
        return json.dumps({"error": message})
    finally:
        if context is not None:
            _finish_standalone_context(context)


async def serve() -> None:
    _setup_logging()
    server = Server("computer-use")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return PROMPTS

    @server.get_prompt()
    async def get_prompt(
        name: str,
        arguments: dict | None = None,
    ) -> GetPromptResult:
        del arguments
        return _get_prompt(name)

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
