---
name: computer-use
description: Guide for operating Windows desktop applications through the Computer Use MCP server. Use when an agent needs to control a Windows GUI with screenshots, UI Automation, mouse, keyboard, batch actions, task sessions, or trace review. Requires a multimodal model or client-side image reading for visual GUI tasks; text-only models should use only structured UIA, task, trace, and audit tools.
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

## Safety Rules

- Check monitor bounds with `get_monitors` when coordinates are uncertain.
- Use only main-screen input coordinates unless the tool explicitly supports otherwise.
- Re-observe before clicking if the window moved, focus changed, animation occurred, or a previous action failed.
- Stop and re-plan on `safety_block`, `fail_safe`, `timeout`, `ui_not_found`, or `invalid_tool`; do not repeat blind clicks.
- Use `wait_for_window` and `wait_for_control` before fixed `sleep`. Use `sleep` only for animations or apps that UIA cannot observe.
- Never infer trace or task state by scanning global directories. Use returned `trace_path`, `artifact_root`, `artifacts`, `task_id`, and review tools.

## Efficient Tool Use

- Use `launch_app` before desktop-icon clicking when the application can be found by shell shortcut.
- Use `get_ui_snapshot(scope="foreground")` for interactable controls in the active window; use `scope="desktop"` only when necessary.
- Use `capture_snapshot` inside `batch` for steps that need later audit evidence.
- Use `run_task_plan` for structured multi-step plans; use `batch` for compact mechanical sequences.
- Preserve `requested_tool` and `tool` distinctions in reports when a prefixed tool name was normalized.

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
