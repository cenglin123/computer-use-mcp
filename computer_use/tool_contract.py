"""Tool-name contracts for nested Computer Use executions."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches


ATOMIC_AND_COMPOSITE_TOOL_NAMES = (
    "get_ui_snapshot",
    "screenshot",
    "get_monitors",
    "click",
    "click_on_screenshot",
    "crop_screenshot",
    "move_to",
    "scroll",
    "type",
    "key_combo",
    "mouse_down",
    "mouse_up",
    "drag",
    "key_down",
    "key_up",
    "press_key",
    "find_control",
    "inspect_point",
    "wait_for_window",
    "wait_for_control",
    "launch_app",
    "sleep",
    "click_by_uid",
    "click_by_text",
    "open_menu",
    "fill_form",
    "scroll_until",
    "retry_step",
    "review_task",
)

_ORCHESTRATION_TOOL_NAMES = frozenset(
    {
        "batch",
        "run_task_plan",
        "start_task",
        "finish_task",
        "get_task",
        "list_tasks",
        "review_task_session",
    }
)
_DIAGNOSTIC_TOOL_NAMES = frozenset({"retry_step", "review_task"})

BATCH_ACTION_TOOL_NAMES = tuple(
    name
    for name in ATOMIC_AND_COMPOSITE_TOOL_NAMES
    if name not in _DIAGNOSTIC_TOOL_NAMES
)
TASK_STEP_TOOL_NAMES = ATOMIC_AND_COMPOSITE_TOOL_NAMES + ("batch",)
_KNOWN_PREFIXES = ("mcp__computer-use__", "computer-use_")


@dataclass
class InvalidToolName(ValueError):
    requested_tool: str
    candidates: list[str]


def normalize_nested_tool_name(
    raw_name: object,
    *,
    allowed_tools: tuple[str, ...],
) -> str:
    """Normalize known MCP prefixes and reject names outside a nested allow-list."""
    if not isinstance(raw_name, str) or not raw_name:
        raise InvalidToolName(str(raw_name), [])

    candidate = raw_name
    for prefix in _KNOWN_PREFIXES:
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):]
            break

    if candidate in allowed_tools:
        return candidate

    suggestions = get_close_matches(candidate, allowed_tools, n=3, cutoff=0.55)
    raise InvalidToolName(raw_name, suggestions)
