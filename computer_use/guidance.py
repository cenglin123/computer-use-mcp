"""Shared agent guidance for distributed Computer Use MCP clients."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuidancePrompt:
    name: str
    title: str
    description: str
    text: str


_CORE_BOUNDARY = """Computer Use MCP controls the real Windows desktop.

Visual GUI tasks require a multimodal model or a client that can open local PNG screenshots returned by the screenshot tool. A text-only model must not attempt screenshot-based clicking; it may use structured UIA, task, trace, and audit tools.

Do not bypass MCP safety with ad-hoc pyautogui scripts or private implementation imports.
"""

_STANDARD_LOOP = """Operate with this loop:
1. Use start_task(goal=...) for auditable user tasks.
2. Observe before acting with screenshot, get_ui_snapshot, find_control, wait_for_window, or wait_for_control.
3. Prefer UIA/semantic targeting over raw coordinates.
4. Use coordinates only after confirming screenshot pixels and monitor bounds.
5. Use batch for short mechanical sequences.
6. Verify after each meaningful state change; when using coordinate-based input, take a fresh screenshot and check the red cursor marker to confirm the click landed where intended.
7. Use review_task_session(task_id) and finish_task(task_id, summary=...) when done.
"""

_SAFETY = """Safety rules:
- Treat mouse and keyboard tools as real user input.
- Stop and re-observe after safety_block, fail_safe, timeout, ui_not_found, or invalid_tool.
- Use returned trace_path, artifact_root, artifacts, task_id, and review tools as the source of truth.
- Do not infer task state by scanning ~/.computer-use/traces.
"""

PROMPTS: tuple[GuidancePrompt, ...] = (
    GuidancePrompt(
        name="computer_use_guidance",
        title="Computer Use MCP operating guidance",
        description=(
            "Full guidance for safely operating Windows GUI applications "
            "through Computer Use MCP."
        ),
        text=f"{_CORE_BOUNDARY}\n{_STANDARD_LOOP}\n{_SAFETY}",
    ),
    GuidancePrompt(
        name="computer_use_visual_task",
        title="Computer Use visual GUI task loop",
        description=(
            "Use for multimodal agents performing screenshot-based Windows "
            "GUI tasks."
        ),
        text=f"{_CORE_BOUNDARY}\n{_STANDARD_LOOP}",
    ),
    GuidancePrompt(
        name="computer_use_text_only_limits",
        title="Computer Use text-only model limits",
        description="Use when the current model cannot inspect screenshots.",
        text=(
            "If you are a text-only model, do not attempt screenshot-based "
            "clicking. Use get_monitors, get_ui_snapshot, find_control, "
            "wait_for_window, wait_for_control, start_task, finish_task, "
            "review_task, list_tasks, get_task, and review_task_session. "
            "Ask for a multimodal model when a task requires visual layout, "
            "icons, colors, or coordinate selection from a screenshot."
        ),
    ),
    GuidancePrompt(
        name="computer_use_safety_checklist",
        title="Computer Use safety checklist",
        description="Checklist before sending real mouse or keyboard input.",
        text=_SAFETY,
    ),
)

MODEL_CAPABILITY_WARNING: str = (
    "Visual GUI tasks require a multimodal model or a client that can read "
    "local PNG screenshots."
)

DOCTOR_NEXT_STEPS: tuple[str, ...] = (
    "Run: python -m computer_use monitors",
    "Register the MCP server in your client",
    "Load MCP prompt computer_use_guidance when supported",
    "Run a read-only smoke test before sending mouse or keyboard input",
)


def list_prompt_metadata() -> list[dict[str, str]]:
    return [
        {
            "name": prompt.name,
            "title": prompt.title,
            "description": prompt.description,
        }
        for prompt in PROMPTS
    ]


def prompt_text(name: str) -> str:
    for prompt in PROMPTS:
        if prompt.name == name:
            return prompt.text
    raise KeyError(name)
