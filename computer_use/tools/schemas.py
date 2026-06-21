from __future__ import annotations

from mcp.types import Tool

from computer_use.core import DEFAULT_MOVE_DURATION, VALID_MOUSE_BUTTONS
from computer_use.tool_contract import BATCH_ACTION_TOOL_NAMES, TASK_STEP_TOOL_NAMES


#: Maximum allowed sleep duration in seconds for the ``sleep`` tool.
MAX_SLEEP_DURATION: float = 60.0
_MANIFEST_TOOL_NAMES = {"batch", "run_task_plan", "review_task"}
_TASK_MANAGEMENT_TOOLS = frozenset(
    {"start_task", "finish_task", "get_task", "list_tasks", "review_task_session"}
)
_TASK_CONTEXT_EXCLUDED_TOOLS = _TASK_MANAGEMENT_TOOLS | {"review_task"}



TOOLS: list[Tool] = [
    Tool(
        name="screenshot",
        description="Take a screenshot and save it as a PNG file. By default only a file path reference is returned (read the returned saved_path file to see what is on screen). By default the primary monitor (monitor=1) is captured; pass monitor=0 for the entire virtual desktop, or pass save_path to override the save location. Use the returned saved_path and coordinate metadata for any screenshot-based click. Do not infer click coordinates from a scaled chat preview. Set include_image=true only on multimodal clients that render image tool results to also receive the screenshot inline (saving a separate file read); the inline image is full-resolution, so click_on_screenshot coordinates still map correctly.",
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
                "include_image": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, also return the saved PNG inline as a full-resolution ImageContent block (in addition to saved_path), so a multimodal client need not read the file separately. Only enable on clients that render image tool results; oversized captures (e.g. monitor=0) silently fall back to path-only. Default false to keep context lean.",
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
        description="Return a structured UI automation tree snapshot. Do not use scope=desktop with include_screenshot=true; this combination is blocked because it can create huge outputs.",
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
        description="Click a UI Automation control by name or at the given non-negative primary-screen physical coordinates (x, y). This sends real Windows input; observe and verify first. The cursor moves smoothly over a short duration to avoid closing hover-activated menus. Provide either target_name or both x and y. For visual targets from a screenshot, prefer click_on_screenshot(screenshot_path, image_x, image_y). Raw x/y input is for already-known primary-screen physical coordinates.",
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
        description="Move the cursor to a UI Automation control by name or to the given non-negative primary-screen physical coordinates (x, y). This sends real Windows input; observe and verify first. The cursor moves smoothly over a short duration to avoid closing hover-activated menus. Provide either target_name or both x and y. For visual targets from a screenshot, prefer click_on_screenshot(screenshot_path, image_x, image_y). Raw x/y input is for already-known primary-screen physical coordinates.",
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
        name="click_on_screenshot",
        description="Click at image pixel coordinates on a previously saved screenshot. The tool reads the screenshot's capture metadata (sidecar .json) to map image pixels to screen coordinates, then runs the full safety chain. Prefer this over raw click(x,y) for visual targets.",
        inputSchema={
            "type": "object",
            "properties": {
                "screenshot_path": {"type": "string", "description": "Path to a PNG saved by the MCP screenshot tool."},
                "image_x": {"type": "integer", "description": "X coordinate in image pixels (from left)."},
                "image_y": {"type": "integer", "description": "Y coordinate in image pixels (from top)."},
                "button": {"type": "string", "enum": list(VALID_MOUSE_BUTTONS), "default": "left"},
                "duration": {"type": "number", "default": DEFAULT_MOVE_DURATION, "minimum": 0},
                "double_click": {"type": "boolean", "default": False},
            },
            "required": ["screenshot_path", "image_x", "image_y"],
        },
    ),
    Tool(
        name="crop_screenshot",
        description="Crop a region from a saved screenshot, preserving coordinate metadata for click_on_screenshot. Use to zoom in on small targets.",
        inputSchema={
            "type": "object",
            "properties": {
                "screenshot_path": {"type": "string"},
                "x": {"type": "integer", "description": "Left edge in image pixels."},
                "y": {"type": "integer", "description": "Top edge in image pixels."},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
            },
            "required": ["screenshot_path", "x", "y", "width", "height"],
        },
    ),
    Tool(
        name="scroll",
        description="Scroll the mouse wheel by amount or direction, optionally at non-negative primary-screen physical coordinates. This sends real Windows input; observe and verify first.",
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
        description="Type the given text. This sends real Windows input; observe and verify first.",
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
        description="Press a key combination, e.g. ['ctrl', 'c']. This sends real Windows input; observe and verify first.",
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
        description="Press and hold a mouse button at the given non-negative primary-screen physical coordinates. This sends real Windows input; observe and verify first.",
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
        description="Release a mouse button. Optionally move to (x, y) before releasing. This sends real Windows input; observe and verify first.",
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
        description="Drag the mouse from (start_x, start_y) to (end_x, end_y) while holding a mouse button. This sends real Windows input; observe and verify first.",
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
        description="Hold a keyboard key down (press without releasing). Use key_up to release. This sends real Windows input; observe and verify first.",
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
        description="Release a keyboard key previously held with key_down. This sends real Windows input; observe and verify first.",
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
        description="Press and release a single keyboard key. This sends real Windows input; observe and verify first.",
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
        name="activate_window",
        description="Bring an existing window whose title contains the given name to the foreground. Use this to focus a target application that is running but backgrounded or minimized, instead of shell scripts or Win32 calls. One-shot lookup + activate (no polling); call wait_for_window first if the window may not exist yet. Refuses to activate the agent's own host window (self_activation_blocked) and sensitive processes (blocked). A window on another virtual desktop may report activation_unconfirmed. Returns activated plus name, process_name, rect, or a reason on failure.",
        inputSchema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
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
                            "tool": {"type": "string", "enum": list(TASK_STEP_TOOL_NAMES)},
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
                "detail": {
                    "type": "boolean",
                    "default": False,
                    "description": "When true, include a 'steps' array with per-step args, result, duration_ms, screenshot_path, etc.",
                },
            },
            "required": ["trace_id"],
        },
    ),
    Tool(
        name="start_task",
        description="Start an explicit business task session and return task_id for subsequent tool calls. Use the returned task_id on subsequent calls for auditability. After start_task, pass the returned task_id to every subsequent executable tool. If an explicit task is active, executable tools without task_id are rejected.",
        inputSchema={
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Business task goal."},
            },
            "required": ["goal"],
        },
    ),
    Tool(
        name="finish_task",
        description="Finish a business task session. Final status is derived from registered traces.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "summary": {"type": "string"},
                "cancel": {"type": "boolean", "default": False},
            },
            "required": ["task_id"],
        },
    ),
    Tool(
        name="get_task",
        description="Return business task metadata and trace ownership records.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
            },
            "required": ["task_id"],
        },
    ),
    Tool(
        name="list_tasks",
        description="List business task sessions for audit.",
        inputSchema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Optional YYYY-MM-DD filter."},
                "status": {
                    "type": "string",
                    "enum": ["active", "succeeded", "failed", "cancelled"],
                },
                "limit": {"type": "integer", "minimum": 1},
            },
        },
    ),
    Tool(
        name="review_task_session",
        description="Generate a deterministic multi-trace summary for a business task session. Use returned task evidence as the source of truth.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "detail": {
                    "type": "boolean",
                    "default": False,
                    "description": "When true, each trace's review includes a 'steps' array with per-step detail.",
                },
            },
            "required": ["task_id"],
        },
    ),
    Tool(
        name="batch",
        description=(
            "Execute a sequence of tools in a single call. This is the preferred way to run multi-step GUI workflows. "
            "Call this tool directly with only the `actions` array; do not wrap it in Python/Bash scripts or import `_call_tool`. "
            "Use after you observe the UI; do not use for blind clicking. "
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


def _attach_task_context_schemas() -> None:
    for tool in TOOLS:
        if tool.name in _TASK_CONTEXT_EXCLUDED_TOOLS:
            continue
        properties = tool.inputSchema.setdefault("properties", {})
        properties.setdefault(
            "task_id",
            {
                "type": "string",
                "description": "Optional business task session ID returned by start_task.",
            },
        )


_attach_task_context_schemas()
