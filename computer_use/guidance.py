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

The screenshot tool saves a PNG to disk and returns saved_path. Read the saved file to see what is on the screen — this is your primary way to observe the GUI. If reading yields no visual content, fall back to structured UIA tools (get_ui_snapshot, find_control, click_by_text). Do not assume a visual task is impossible just because UIA cannot see the target.

Do not bypass MCP safety with ad-hoc pyautogui scripts or private implementation imports.
"""

_STANDARD_LOOP = """Operate with this loop:
1. Use start_task(goal=...) for auditable user tasks.
2. Observe: call screenshot(monitor=1), then read the returned saved_path file to see what is on screen. Use get_ui_snapshot or find_control for supplementary structured info.
3. Prefer UIA/semantic targeting over raw coordinates. If UIA cannot see the target (common for games and custom-drawn UIs), use the screenshot-based click flow.
4. Use coordinates only after confirming screenshot pixels and monitor bounds.
5. Use batch for short mechanical sequences.
6. Verify after each meaningful state change; when using coordinate-based input, take a fresh screenshot and check the red cursor marker to confirm the click landed where intended.
7. Use review_task_session(task_id) and finish_task(task_id, summary=...) when done.
"""

_COORDINATE_VERIFY = """Coordinate pre-click verification (complements the post-click verification in step 6):
- Before clicking an estimated (x, y), first move_to(x, y) to position the cursor, then screenshot(monitor=1) and check that the red cursor marker lands on the target center.
- Only after confirming the marker is on the target, execute click(x, y).
- If a click does not change GUI state, allow at most one re-measurement from a fresh screenshot; do NOT micro-adjust within 3-5 pixels of the same wrong coordinate.
- For custom-drawn interfaces where UIA can only locate the window (not the button), prefer a foreground snapshot or screenshot for positioning; do not use click_by_uid to click the window center as a business button.
"""

_COORDINATE_SAFETY = """Screenshot-based click flow (preferred for visual GUI targets):
- For visual GUI targets: 1) screenshot(monitor=1), 2) if target is small, crop_screenshot, 3) click_on_screenshot(path, image_x, image_y), 4) screenshot to verify. Do not estimate raw click(x,y) from a scaled chat preview.
- click_on_screenshot reads the screenshot's capture metadata to map image pixels to screen coordinates, then runs the full safety chain (validate_coordinate, inspect_point, check_target_window).
- crop_screenshot preserves coordinate metadata so click_on_screenshot still maps back to original screen coordinates.
- screenshot returns coordinate_space, capture_left, capture_top, and metadata_path alongside saved_path.
"""

_CONTEXT_BUDGET = """Context budget rules (model-agnostic):
- After start_task, every subsequent executable computer-use tool call must include the returned task_id. If an explicit task is active, tools without task_id are rejected with missing_task_id.
- Do not use get_ui_snapshot(scope="desktop", include_screenshot=true). It is blocked because it can create huge tool output.
- Never call the CLI `python -m computer_use screenshot` for visual understanding; it outputs base64 PNG to stdout, which enters tool output and context as raw image data.
- Use the MCP `screenshot` tool instead; it returns only saved_path. Do not repeatedly read PNG screenshots into context. Read only the latest screenshot needed for visual reasoning; after 2-3 image reads or any tool response over 60s, stop and summarize.
- Default to get_ui_snapshot(scope="foreground", include_screenshot=false). Use scope="desktop" only when cross-window positioning is needed; desktop JSON can reach hundreds of KB.
- Do not read complete tool-output JSON; use precise filtering or small summaries.
- When a single tool response takes more than 60 seconds, or when consecutive tool outputs are cumulatively large (multiple PNG reads, truncated desktop JSON), stop visual iteration, summarize current state, and start a new session or ask the user to confirm continuing.
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
        text=f"{_CORE_BOUNDARY}\n{_STANDARD_LOOP}\n{_COORDINATE_VERIFY}\n{_COORDINATE_SAFETY}\n{_CONTEXT_BUDGET}\n{_SAFETY}",
    ),
    GuidancePrompt(
        name="computer_use_visual_task",
        title="Computer Use visual GUI task loop",
        description=(
            "Screenshot-based Windows GUI task guidance. Use when "
            "performing visual GUI operations."
        ),
        text=f"{_CORE_BOUNDARY}\n{_STANDARD_LOOP}\n{_COORDINATE_VERIFY}\n{_COORDINATE_SAFETY}\n{_CONTEXT_BUDGET}",
    ),
    GuidancePrompt(
        name="computer_use_text_only_limits",
        title="Computer Use fallback without image reading",
        description="Use only when the agent confirmed it cannot read screenshot files.",
        text=(
            "If reading a saved screenshot file yields no visual content, "
            "do not attempt visual coordinate clicking. Use get_monitors, "
            "get_ui_snapshot, find_control, wait_for_window, "
            "wait_for_control, start_task, finish_task, review_task, "
            "list_tasks, get_task, and review_task_session. Ask the user "
            "to switch to a client/model with image reading capability "
            "when a task requires visual layout, icons, colors, or "
            "coordinate selection from a screenshot."
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
    "After screenshot saves a PNG, read the saved file to see the screen. "
    "If you cannot interpret image content, use structured UIA tools instead."
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
