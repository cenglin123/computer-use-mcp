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

## Tool Quick Reference

| Category | Tool | Key params | Purpose |
|----------|------|-----------|---------|
| **Observe** | `screenshot` | `monitor=1`, `save_path?` | Save PNG, return path + coordinate metadata |
| | `get_ui_snapshot` | `scope=foreground`, `include_screenshot=false` | UIA tree of controls (avoid `desktop`+`screenshot`) |
| | `get_monitors` | — | Physical bounds of all displays |
| | `find_control` | `name`, `scope`, `control_type?` | Locate a UI element, return center coords |
| | `inspect_point` | `x`, `y` | What control is under this screen coordinate? |
| **Click (visual)** | `click_on_screenshot` | `screenshot_path`, `image_x`, `image_y` | Map image pixels → screen coords, full safety chain |
| | `crop_screenshot` | `screenshot_path`, `x`, `y`, `width`, `height` | Zoom into small target, preserves coordinate mapping |
| **Click (raw)** | `click` | `x`, `y`, `button?`, `double_click?` | Primary-screen physical coordinates only |
| | `move_to` | `x`, `y` | Move cursor without clicking |
| | `click_by_uid` | `uid`, `snapshot` | Click a snapshot-identified control |
| | `click_by_text` | `text` | Find and click by displayed text |
| **Input** | `type` | `text` | Type text at current cursor |
| | `key_combo` | `keys=["ctrl","c"]` | Press key combination |
| | `press_key` | `key` | Single key press |
| | `scroll` | `amount` or `direction`+`clicks` | Mouse wheel scroll |
| | `drag` | `start_x`, `start_y`, `end_x`, `end_y` | Drag operation |
| **Composite** | `open_menu` | `path=["菜单","项"]` | Click through menu items by name |
| | `fill_form` | `fields=[{name,value}]` | Batch fill input fields |
| | `scroll_until` | `target_text`, `direction` | Scroll until text appears in UIA |
| **Batch** | `batch` | `actions=[{tool,args}]`, `stop_on_error?` | Execute multiple tools in one call |
| | `run_task_plan` | `steps=[{tool,args}]`, `goal?` | Structured multi-step plan with report |
| **Task** | `start_task` | `goal` | Begin auditable task, returns `task_id` |
| | `finish_task` | `task_id`, `summary?`, `cancel?` | End task |
| | `review_task` | `trace_id`, `detail?` | Trace summary (+ step detail if `detail=true`) |
| | `review_task_session` | `task_id`, `detail?` | Aggregate task review |
| **Wait** | `wait_for_window` | `name` | Wait for window to appear/disappear |
| | `wait_for_control` | `name` | Wait for control to exist/enable/vanish |
| | `sleep` | `duration` (max 60s) | Fixed pause (prefer event-driven waits) |
| **Launch** | `launch_app` | `name` | Start app by Start Menu / Desktop shortcut |

> All executable tools accept optional `task_id`. After `start_task`, omitting `task_id` while an explicit task is active returns `missing_task_id`.

## Minimal Examples

### Full visual click flow (preferred)

```json
1. {"tool": "start_task", "args": {"goal": "Open settings panel"}}
2. {"tool": "screenshot", "args": {"monitor": 1}}
   → returns saved_path, coordinate_space, capture_left, capture_top, metadata_path
3. {"tool": "click_on_screenshot", "args": {"screenshot_path": "<saved_path>", "image_x": 213, "image_y": 48}}
   → maps image pixels to screen coordinates, runs safety chain, clicks
4. {"tool": "screenshot", "args": {"monitor": 1}}
   → verify state change via red cursor marker
5. {"tool": "review_task_session", "args": {"task_id": "<task_id>", "detail": true}}
6. {"tool": "finish_task", "args": {"task_id": "<task_id>", "summary": "Opened settings"}}
```

### Small target: crop then click

```json
1. {"tool": "screenshot", "args": {"monitor": 1}}
2. {"tool": "crop_screenshot", "args": {"screenshot_path": "<path>", "x": 180, "y": 30, "width": 120, "height": 50}}
3. {"tool": "click_on_screenshot", "args": {"screenshot_path": "<crop_path>", "image_x": 33, "image_y": 18}}
```

### Mechanical batch (after target confirmed)

```json
{
  "tool": "batch",
  "args": {
    "actions": [
      {"tool": "click", "args": {"target_name": "File"}},
      {"tool": "sleep", "args": {"duration": 0.5}},
      {"tool": "click", "args": {"target_name": "Save"}}
    ],
    "task_id": "<task_id>"
  }
}
```

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
