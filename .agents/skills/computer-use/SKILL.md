---
name: computer-use
description: Use when an agent needs to control a Windows GUI through Computer Use MCP/CU with screenshots, UI Automation, mouse, keyboard, batch actions, task sessions, or trace review. Requires a multimodal model or client-side image reading for visual GUI tasks; text-only models should use only structured UIA, task, trace, and audit tools.
---

# Computer Use MCP

Use this skill to operate Windows desktop applications through the `computer-use` MCP server safely and efficiently.

If the MCP client supports prompts, also load `computer_use_guidance`; it is the protocol-level guidance entrypoint for clients that do not support Skills.

## Capability Boundary

- Use a multimodal model, or a client that can open local PNG files, for visual GUI tasks.
- Do not attempt screenshot-based positioning with a text-only model. Text-only models may use structured tools such as `get_monitors`, `find_control`, `get_ui_snapshot`, `review_task`, and task session review.
- Treat mouse and keyboard tools as real user input. They affect the active Windows desktop.
- Do not bypass the MCP tools with ad-hoc `pyautogui` scripts or direct calls into private implementation modules.

## Standard Loop

1. Establish task context with `start_task(goal=...)` when the user task may span multiple tool calls or needs auditability.
2. Observe first with `screenshot`, `get_ui_snapshot`, `find_control`, `wait_for_window`, or `wait_for_control`.
3. Prefer semantic/UIA targeting over coordinates: `target_name`, `click_by_uid`, `click_by_text`, `open_menu`, or `find_control` then click.
4. Fall back to coordinates only after visually confirming the screenshot and monitor bounds.
5. Execute short sequences with `batch` to reduce round trips; keep `final_screenshot=false` unless final visual evidence is needed.
6. Verify after action with a fresh screenshot, UI snapshot, control query, or task review.
7. Finish auditable tasks with `review_task_session(task_id)` and `finish_task(task_id, summary=...)`.

After `start_task`, every subsequent executable computer-use tool call must include the returned `task_id`. If an explicit task is active, tools without `task_id` are rejected with `missing_task_id`.

## Safety Rules

- Check monitor bounds with `get_monitors` when coordinates are uncertain.
- Use only main-screen input coordinates unless the tool explicitly supports otherwise.
- Re-observe before clicking if the window moved, focus changed, animation occurred, or a previous action failed.
- Stop and re-plan on `safety_block`, `fail_safe`, `timeout`, `ui_not_found`, or `invalid_tool`; do not repeat blind clicks.
- Use `wait_for_window` and `wait_for_control` before fixed `sleep`. Use `sleep` only for animations or apps that UIA cannot observe.
- Never infer trace or task state by scanning global directories. Use returned `trace_path`, `artifact_root`, `artifacts`, `task_id`, and review tools.

## Verify Clicks with the Screenshot Cursor Marker

- Every `screenshot` draws a red crosshair and center dot at the **current cursor position** before saving the PNG.
- After any coordinate-based `click`, `move_to`, `mouse_down`, `mouse_up`, `drag`, or `scroll`, immediately take a fresh `screenshot` and check where the red marker landed.
- If the marker is not on the intended target, the previous coordinates were wrong; re-measure from the new screenshot or use UIA tools instead of repeating the same click.
- Do not assume a click succeeded just because the tool returned without error. The red cursor marker is the authoritative evidence of where input actually occurred.

## Pre-Click Verification: Coordinate Three-Step Pattern

The post-click verification above confirms *where* input landed. Use this **pre-click** pattern before sending any coordinate-based click, so the click is aimed correctly in the first place:

1. `move_to(x, y)` to the estimated target position.
2. `screenshot(monitor=1)` and check that the red cursor marker lands on the target center (not just near it).
3. Only after confirming, execute `click(x, y)`.

**Failure stop-loss rule**: if a click at a coordinate does not change the GUI state, allow at most one re-measurement from a fresh screenshot. Do NOT micro-adjust within 3-5 pixels of the same wrong coordinate - re-observe and re-estimate the target from scratch.

**Custom-drawn interfaces**: when UIA can only locate the window (not the specific button), prefer a `foreground` snapshot or screenshot for positioning. Do not use `click_by_uid` to click the window center as if it were the business button.

## Screenshot-Based Click Flow (Preferred for Visual Targets)

For visual GUI targets, do not estimate raw `click(x, y)` from a scaled chat preview. Instead use the screenshot-based click flow, which binds image pixels to screen coordinates via metadata:

1. `screenshot(monitor=1)` - capture the primary monitor. The response includes `saved_path`, `coordinate_space`, `capture_left`, `capture_top`, and `metadata_path`.
2. If the target is small or unclear, call `crop_screenshot(screenshot_path, x, y, width, height)` to zoom in. The crop preserves coordinate metadata so clicks still map back to the original screen.
3. Determine the target's image pixel coordinates `(image_x, image_y)` from the screenshot or crop.
4. `click_on_screenshot(screenshot_path, image_x, image_y)` - the tool reads the capture metadata, maps image pixels to screen coordinates, and runs the full safety chain (`validate_coordinate`, `inspect_point`, `check_target_window`).
5. `screenshot(monitor=1)` to verify the state change.

**Why this matters**: chat clients scale screenshot previews to fit the conversation, so pixel coordinates estimated from the preview are often wrong. `click_on_screenshot` uses the saved PNG's capture metadata (sidecar `.json`) to map image pixels accurately to screen coordinates, then enforces the same primary-screen input safety boundary as raw `click(x, y)`.

## Efficient Tool Use

- Use `launch_app` before desktop-icon clicking when the application can be found by shell shortcut.
- Use `get_ui_snapshot(scope="foreground")` for interactable controls in the active window; use `scope="desktop"` only when necessary.
- Use `capture_snapshot` inside `batch` for steps that need later audit evidence.
- Use `run_task_plan` for structured multi-step plans; use `batch` for compact mechanical sequences.
- Preserve `requested_tool` and `tool` distinctions in reports when a prefixed tool name was normalized.

## Context Budget

Large screenshots, UIA JSON, and base64 image data accumulate in context and degrade response latency for context-sensitive models. Follow these rules to keep context lean:

- **Do not use** `get_ui_snapshot(scope="desktop", include_screenshot=true)`. It is blocked because it can create huge tool output. Use `scope="foreground"` instead, or `scope="desktop"` without `include_screenshot`. If a desktop snapshot still exceeds the inline budget, the server returns `snapshot_output_too_large`; switch to `find_control` with narrow criteria.
- **Never call the CLI** `python -m computer_use screenshot` for visual understanding. It outputs base64 PNG to stdout, which enters tool output and context as raw image data.
- **Use the MCP** `screenshot` **tool** instead; it returns only `saved_path`. Do not repeatedly read PNG screenshots into context. Read only the latest screenshot needed for visual reasoning; after 2-3 image reads or any tool response over 60s, stop and summarize.
- **Default** `get_ui_snapshot(scope="foreground", include_screenshot=false)`. Use `scope="desktop"` only when cross-window positioning is needed - desktop JSON can reach hundreds of KB.
- **Do not read complete tool-output JSON**; use precise filtering or small summaries.
- **Long-context budget rule**: when a single tool response takes more than 60 seconds, or when consecutive tool outputs are cumulatively large (multiple PNG reads, truncated desktop JSON), stop visual iteration, summarize current state, and start a new session or ask the user to confirm continuing.

## Failure Handling

- If the cursor is at `(0, 0)` or fail-safe triggers, move only after confirming the remote-control state and current screenshot.
- If UIA cannot see a custom-drawn control, use screenshot-based visual positioning and `inspect_point` before clicking.
- If multiple controls match, inspect candidates or ask for a disambiguating observation rather than guessing.
- If a step fails inside `batch` or `run_task_plan`, use the returned `failed_index`, `error_kind`, `trace_path`, and `artifacts` as the source of truth.
- Use `retry_step` only when the current UI state still matches the failed step's assumptions.

## Reporting

- Report what was done, the final observed state, and the trace/task evidence path when available.
- Mention any limitations that affected reliability, such as text-only model use, remote-control interference, mixed DPI, inaccessible UIA controls, or blocked target windows.
- Do not include screenshot base64 in responses; reference saved local paths returned by the MCP tools.
