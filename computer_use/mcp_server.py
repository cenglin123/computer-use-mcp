"""MCP Server exposing Computer Use tools to Kimi Code CLI."""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from pathlib import Path

import pyautogui
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolRequestParams, TextContent, Tool

from computer_use.config import load_config
from computer_use.core import (
    CoordinateSystem,
    click,
    create_redacted_image,
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


TOOLS: list[Tool] = [
    Tool(
        name="screenshot",
        description="Take a screenshot and return a base64 PNG. By default captures the entire virtual desktop. Pass monitor=1,2,... for a single monitor (1-based, primary is 1).",
        inputSchema={
            "type": "object",
            "properties": {
                "monitor": {
                    "type": "integer",
                    "description": "0 for virtual desktop (default), or 1-based monitor index for a single monitor.",
                },
            },
        },
    ),
    Tool(
        name="get_screen_size",
        description="Return the virtual screen size (width, height) in physical pixels.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_monitors",
        description="Return a list of monitors with index, primary flag, left, top, width, and height in physical virtual screen coordinates.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="click",
        description="Click at the given physical virtual screen coordinates (x, y).",
        inputSchema={
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "Physical virtual screen x coordinate"},
                "y": {"type": "integer", "description": "Physical virtual screen y coordinate"},
            },
            "required": ["x", "y"],
        },
    ),
    Tool(
        name="move_to",
        description="Move the mouse cursor to the given physical virtual screen coordinates.",
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
        name="scroll",
        description="Scroll the mouse wheel by the given amount, optionally at physical virtual screen coordinates.",
        inputSchema={
            "type": "object",
            "properties": {
                "amount": {"type": "integer"},
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["amount"],
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
]


def _call_tool(name: str, args: dict) -> str:
    logging.info("tool=%s args=%s", name, args)
    cs = get_coordinate_system()
    try:
        return _dispatch_tool(name, args, cs)
    except SafetyError as exc:
        logging.warning("safety block: %s", exc)
        return json.dumps({"error": str(exc)})


def _dispatch_tool(name: str, args: dict, cs: CoordinateSystem) -> str:
    if name == "screenshot":
        config = load_config()
        monitor = args.get("monitor", config.get("display", {}).get("default_monitor", 0))
        monitors = cs.get_monitors()
        validate_monitor_index(monitor, len(monitors))

        if config["safety"]["screenshot_sensitive_window_check"]:
            if monitor == 0:
                width, height = cs.virtual_width, cs.virtual_height
                cx, cy = width // 2, height // 2
            else:
                mon = cs.monitors[monitor - 1]
                width, height = mon["width"], mon["height"]
                cx = mon["left"] + width // 2
                cy = mon["top"] + height // 2
            info = inspect_point(cx, cy)
            try:
                check_target_window(
                    info.process_name, info.class_name, info.control_type
                )
            except SafetyError as exc:
                logging.warning("screenshot sensitive window: %s", exc)
                return create_redacted_image(width, height)
        return screenshot(monitor=monitor)

    if name == "get_screen_size":
        info = cs.get_screen_size()
        return json.dumps({"width": info.width, "height": info.height})

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
        x, y = args["x"], args["y"]
        size = cs.get_screen_size()
        validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
        info = inspect_point(x, y)
        check_target_window(info.process_name, info.class_name, info.control_type)
        click(x, y)
        return json.dumps({"clicked": True, "x": x, "y": y})

    if name == "move_to":
        x, y = args["x"], args["y"]
        size = cs.get_screen_size()
        validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
        info = inspect_point(x, y)
        check_target_window(info.process_name, info.class_name, info.control_type)
        move_to(x, y)
        return json.dumps({"moved": True, "x": x, "y": y})

    if name == "scroll":
        amount = args["amount"]
        x = args.get("x")
        y = args.get("y")
        if x is not None and y is not None:
            size = cs.get_screen_size()
            validate_coordinate(x, y, size.width, size.height, monitors=cs.monitors)
            info = inspect_point(x, y)
            check_target_window(
                info.process_name, info.class_name, info.control_type
            )
        scroll(amount, x, y)
        return json.dumps({"scrolled": True, "amount": amount, "x": x, "y": y})

    if name == "type":
        text = args["text"]
        validate_text_input(text)
        x, y = _current_logical_position()
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
        info = inspect_point(x, y)
        check_target_window(info.process_name, info.class_name, info.control_type)
        key_combo(*keys)
        return json.dumps({"pressed": keys})

    raise ValueError(f"Unknown tool: {name}")


def _current_logical_position() -> tuple[int, int]:
    """Return the current cursor position in physical virtual screen pixels."""
    x, y = pyautogui.position()
    return int(x), int(y)


async def serve() -> None:
    _setup_logging()
    server = Server("computer-use")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(params: CallToolRequestParams) -> list[TextContent]:
        try:
            result = _call_tool(params.name, params.arguments or {})
            return [TextContent(type="text", text=result)]
        except Exception as exc:
            logging.exception("tool error")
            return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]

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
