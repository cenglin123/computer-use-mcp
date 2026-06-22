---
name: computer-use
description: Use when an agent needs to control a Windows GUI through Computer Use MCP with screenshots, UI Automation, mouse, keyboard, batch actions, task sessions, or trace review. The screenshot tool saves PNG files locally and returns the file path — read the saved file to visually identify UI elements and their pixel positions.
---

# Computer Use MCP

Use this skill to operate Windows desktop applications through the `computer-use` MCP server safely and efficiently.

If the MCP client supports prompts, also load `computer_use_guidance`; it is the protocol-level guidance entrypoint for clients that do not support Skills.

## How to See the Screen

The `screenshot` tool saves a PNG to disk and returns `saved_path`. **Read the saved file** to see what is on the desktop — this is how you observe the GUI. The screenshot also includes coordinate metadata for precise clicking (see Screenshot-Based Click Flow below).

If reading the screenshot file yields no visual content, fall back to structured tools: `get_ui_snapshot`, `find_control`, `click_by_text`. Do not give up on a visual task just because UIA cannot see the target — most game and custom-drawn UIs are invisible to UIA but clearly visible in screenshots.

## Capability Boundary

- Treat mouse and keyboard tools as real user input. They affect the active Windows desktop.
- Do not bypass the MCP tools with ad-hoc `pyautogui` scripts or direct calls into private implementation modules.
- Do not use shell/PowerShell or Win32 calls to probe or change desktop state. To check whether an app is running or in the foreground use `find_control` / `get_ui_snapshot(scope="foreground")` / `wait_for_window`; to foreground it use `activate_window`. Reaching for `Get-Process`, `SetForegroundWindow`, or `Add-Type` means the right MCP tool was not used.
- Reading the saved screenshot file **is** the vision step. This project has no OCR and needs none — do not install or call OCR (pytesseract, easyocr, etc.) and do not request a different model to "read the image" before trying to read the screenshot yourself.

## Tool Quick Reference

| Category | Tool | Key params | Purpose |
|----------|------|-----------|---------|
| **Observe** | `screenshot` | `monitor=1`, `save_path?` | Save PNG, return path + coordinate metadata |
| | `get_ui_snapshot` | `scope=foreground`, `include_screenshot=false` | UIA tree of controls (avoid `desktop`+`screenshot`) |
| | `get_monitors` | — | Physical bounds of all displays |
| | `find_control` | `name`, `scope`, `control_type?` | Locate a UI element, return center coords |
| | `inspect_point` | `x`, `y` | What control is under this screen coordinate? |
| **Click (visual)** | `click_on_screenshot` | `screenshot_path`, `image_x`, `image_y` | Map image pixels → screen coords, full safety chain |
| | `crop_screenshot` | `screenshot_path`, `x`, `y`, `width`, `height`, `annotate?`, `annotate_style?` | Zoom into small target, preserves coordinate mapping. By default also writes `<source>_annotated.png` with red L-bracket markers so the agent can visually verify the cropped region before reading the crop content. |
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
| | `save_review` | `report_markdown`, `outcome?`, `task_id?` | Persist a standardized retrospective report to `~/.computer-use/reviews/` |
| **Wait** | `wait_for_window` | `name` | Wait for window to appear/disappear |
| | `wait_for_control` | `name` | Wait for control to exist/enable/vanish |
| | `sleep` | `duration` (max 60s) | Fixed pause (prefer event-driven waits) |
| **Launch** | `launch_app` | `name` | Start app by Start Menu / Desktop shortcut |
| | `activate_window` | `name` | Bring an existing/backgrounded/minimized window to the foreground |

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

### Verifying crop region before relying on cropped content

When a crop returns unreadable content (uniform color, looks like desktop background, doesn't match expected UI element), do not blindly retry with a different region estimate. Instead:

1. Read the `annotated_source_path` returned by `crop_screenshot`.
2. Confirm the red L-brackets in that annotated image actually surround the intended control.
3. If brackets miss the target, re-measure from the source screenshot, then call `crop_screenshot` again with corrected coordinates.

The annotated image is non-destructive — the original source PNG is never overwritten, so the agent can repeatedly crop from the same source and inspect each annotation. Set `annotate: false` to skip the sidecar write when not needed (e.g. when cropping in tight performance-sensitive loops).

`annotated_source_path` is the canonical one-image verification artifact. When the source is an MCP screenshot, it contains both visual layers: the red cursor crosshair from the screenshot and the red crop-region marker from `crop_screenshot`. Use it to answer both questions at once: "where was the mouse?" and "what region did I crop?"

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
2. Observe: call `screenshot(monitor=1)`, then **read the returned `saved_path` file as your first action** — that read *is* the vision step. Do not jump to UIA, `find_control`, or shell probing before you have read the screenshot and confirmed the target is not visible. If the target app is running but backgrounded or minimized, use `activate_window(name=...)` to foreground it, then re-screenshot. **If the screenshot clearly shows the target app's UI, that is itself confirmation the target is in the foreground — proceed directly to visual positioning; do not use `get_ui_snapshot` / `wait_for_window` / `find_control` to re-verify the window.** Only when the screenshot does not clearly show the target (blurry, partial, ambiguous, or you cannot read images) use `get_ui_snapshot(scope="foreground")` or `find_control` for supplementary structured info.
3. Prefer semantic/UIA targeting over coordinates: `target_name`, `click_by_uid`, `click_by_text`, `open_menu`, or `find_control` then click. If UIA cannot see the target (common for games and custom-drawn UIs), use the screenshot-based click flow below.
4. Fall back to coordinates only after visually confirming the screenshot and monitor bounds.
5. Execute short sequences with `batch` to reduce round trips; keep `final_screenshot=false` unless final visual evidence is needed.
6. Verify after action with a fresh screenshot, UI snapshot, control query, or task review.
7. Finish auditable tasks with `review_task_session(task_id)` and `finish_task(task_id, summary=...)`.

After `start_task`, every subsequent executable computer-use tool call must include the returned `task_id`. If an explicit task is active, tools without `task_id` are rejected with `missing_task_id`.

## Fast Path After Validation

Once a workflow has been successfully validated on a stable desktop layout, do not repeat the full exploratory loop on every run. Use this faster pattern:

1. Take one orientation screenshot.
2. If known preconditions are still true, run deterministic actions in `batch`.
3. Use event waits (`wait_for_window`, `wait_for_control`) instead of fixed `sleep` where possible.
4. Take one final screenshot or crop for verification.
5. Fall back to the standard loop only if a wait times out, a final screenshot does not match expected state, or coordinates no longer hit the target.

For validated desktop workflows, see `docs/recipes/*.md` (local files — not in GitHub repo; created by the user during setup).

## Safety Rules

- Check monitor bounds with `get_monitors` when coordinates are uncertain.
- Use only main-screen input coordinates unless the tool explicitly supports otherwise.
- Re-observe before clicking if the window moved, focus changed, animation occurred, or a previous action failed.
- Stop and re-plan on `safety_block`, `fail_safe`, `timeout`, `ui_not_found`, or `invalid_tool`; do not repeat blind clicks.
- Use `wait_for_window` and `wait_for_control` before fixed `sleep`. Use `sleep` only for animations or apps that UIA cannot observe.
- Never infer trace or task state by scanning global directories. Use returned `trace_path`, `artifact_root`, `artifacts`, `task_id`, and review tools.
- **Verify window ownership before acting on a desktop-scope UIA match.** A `scope="desktop"` `find_control` / `click_by_text` search can latch onto your own host window — the terminal or IDE running this agent often has the task text in its title bar. Before clicking, check the match's `process_name`: if it belongs to the process hosting this session rather than the target app, it is a false match — re-scope to the target window or `launch_app`/`activate_window` the real app first. `activate_window` enforces this for you and returns `self_activation_blocked` if the match is your own host.
- **Close out tasks you abandon.** If a task is blocked or you stop early, call `finish_task(task_id, cancel=true)` with the reason instead of leaving the session dangling.

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

**Rows of similar adjacent controls (toolbars, icon strips)**: when the target is one of several similar controls packed along a single axis (e.g. a horizontal row of top-left icons), almost all aiming error concentrates on the axis that separates them — in a horizontal row the shared height makes `y` trivially right while `x` carries every chance of error (wrong icon *or* wrong horizontal center). Do not trust "the marker is in the row" as confirmation. Instead:

1. Identify the target by its **function**, not its position in the row, and crop **tight around the single candidate** — never estimate one icon's center from a wide crop that spans several icons.
2. Always run the `move_to` → `screenshot` pre-click check above and confirm the red marker sits on that specific icon along the discriminative axis. `click_on_screenshot` only maps your estimated pixel faithfully; a faithful map of a wrong estimate still misses.
3. If adjacent icons are low-contrast (e.g. white glyphs over a bright background), `crop_screenshot` to enlarge and disambiguate boundaries before estimating the center.

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
- **Use the MCP** `screenshot` **tool** instead; by default it returns only `saved_path`. Do not repeatedly read PNG screenshots into context. Read only the latest screenshot needed for visual reasoning; after 2-3 image reads or any tool response over 60s, stop and summarize.
- **`include_image=true` opt-in**: on a client that renders image tool results, you may pass `include_image=true` to receive the screenshot inline (a full-resolution `ImageContent` block, returned *in addition to* `saved_path`) and skip the separate file read. This is the one sanctioned exception to "screenshot returns only a path" — the base64 lives in a dedicated `ImageContent` block, never inside the JSON text. Reserve it for screenshots you actually need to reason about visually; keep it off for landing-verification / intermediate checks to save vision tokens and transport bytes. Oversized captures (e.g. `monitor=0`) silently fall back to path-only with `inline_image_skipped`.
- **Default** `get_ui_snapshot(scope="foreground", include_screenshot=false)`. Use `scope="desktop"` only when cross-window positioning is needed - desktop JSON can reach hundreds of KB.
- **Do not read complete tool-output JSON**; use precise filtering or small summaries.
- **Long-context budget rule**: when a single tool response takes more than 60 seconds, or when consecutive tool outputs are cumulatively large (multiple PNG reads, truncated desktop JSON), stop visual iteration, summarize current state, and start a new session or ask the user to confirm continuing.

### Long-Session Performance Discipline

Each full-screen screenshot (whether read via the file tool or returned with `include_image=true`) is ~2-4 MB of image data that **stays in the conversation for the rest of the session**. Per-turn latency scales with the accumulated image payload, so a long task gets progressively slower. Keep the running total small:

- **Crop after orienting.** Take at most one full-screen screenshot to locate the target; for every subsequent observation use `crop_screenshot` (or screenshot then crop) and reason about the small region. A 300x120 crop is a tiny fraction of a 1920x1080 frame in context — this is the single biggest lever you control.
- **Crop annotated source on disambiguation.** When a cropped image is ambiguous or appears empty, re-read the `annotated_source_path` to confirm the crop region was correct before trying alternative coordinates. This is far cheaper than re-screenshotting the whole screen.
- **One observation per state change.** Do not re-screenshot when nothing changed. Verify with the cursor marker on a crop, not a fresh full frame, when possible.
- **One task per session.** Old screenshots from a finished task keep costing tokens on every later turn. Start a fresh session for a new task instead of piling tasks into one long conversation.
- **Keep turns flowing.** Prompt caching expires after a few minutes idle; a long pause forces the next turn to reprocess the whole accumulated context (including every retained image) as fresh, expensive input. The slow turns in a long session are usually these cache misses, not any single tool call.
- **`include_image` only when needed now.** Do not inline a full frame when a crop suffices, and never both inline and separately read the same screenshot.

## Failure Handling

- If the cursor is at `(0, 0)` or fail-safe triggers, move only after confirming the remote-control state and current screenshot.
- If UIA cannot see a custom-drawn control, use screenshot-based visual positioning and `inspect_point` before clicking.
- **A `get_ui_snapshot(scope="foreground")` that returns your own host terminal/IDE is a self-reference signal, not a contradiction.** Games, cloud games, accessibility-less Electron apps, console UIs, and custom-drawn installers expose no UIA controls and often no standard window title, so UIA reports the foreground as your host window (whose title may even contain the task text). This is the same "false match" pattern as the desktop-scope `find_control` self-match in Safety Rules, via a different entry point. **Precondition: this only applies once the screenshot already clearly shows the target app** (i.e. the target is confirmed in front per Standard Loop step 2); if the screenshot does *not* show the target, a host-window foreground means the target genuinely is not in front — `activate_window` it. When the precondition holds: do not treat it as a puzzle to solve, do not retry `wait_for_window` with different app-name guesses (seeing the target on screen already proves the issue is not title matching), and proceed straight to screenshot visual positioning + `click_on_screenshot`, which does not depend on what UIA thinks is foreground.
- If multiple controls match, inspect candidates or ask for a disambiguating observation rather than guessing.
- If a step fails inside `batch` or `run_task_plan`, use the returned `failed_index`, `error_kind`, `trace_path`, and `artifacts` as the source of truth.
- Use `retry_step` only when the current UI state still matches the failed step's assumptions.

## Retrospective Reports

When the user asks to summarize or review the execution (e.g. "复盘", "总结一下复盘报告", "复盘一下执行经过", "write a retrospective"), produce a standardized report and persist it with `save_review` so it can be collected for maintainer feedback. Steps:

1. **Gather** from this session what actually happened. If the session has a `task_id`, call `review_task_session(task_id, detail=true)` first for structured evidence.
2. **Compose** `report_markdown` using this template (required sections always; optional sections write `N/A` when not applicable):
   - **Required**: Task goal · Timeline (key steps and tool calls — the decisive ones, not every call) · Outcome (`succeeded` / `partial` / `failed`) · Failures & symptoms (include `error_kind`; required when outcome is `partial`/`failed`) · Evidence paths.
   - **Optional**: What worked · Root-cause hypothesis · Suggestions · Client + model (pass as args if known; if unsure pass nothing and the tool records `unknown`) · Notes.
3. **Persist**: call `save_review(report_markdown=..., outcome=<succeeded|partial|failed|unknown>, task_id=<if any>, client=<if known>, model=<if known>)`.
4. **Report back** the returned `review_path` to the user, and note the file contains environment info (username/paths) so they should preview before sharing it as feedback.

`save_review` wraps your body with metadata + a doctor environment snapshot (and trace/task evidence when `task_id` is given), so do not paste raw environment dumps into `report_markdown`. Re-running with the same `task_id` overwrites the prior file.

## Reporting

- Report what was done, the final observed state, and the trace/task evidence path when available.
- Mention any limitations that affected reliability, such as inability to read screenshots, remote-control interference, mixed DPI, inaccessible UIA controls, or blocked target windows.
- Do not include screenshot base64 in your text responses; reference saved local paths returned by the MCP tools. (The `screenshot include_image=true` exception delivers base64 only inside a dedicated `ImageContent` tool-result block, not in text.)
