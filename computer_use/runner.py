"""Task-level execution and deterministic batching.

``run_task_plan`` executes a structured list of tool calls as a single task,
recording all steps under one trace ID and generating a ``report.md``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from computer_use import snapshot, trace as trace_module
from computer_use.core import get_coordinate_system, save_screenshot
from computer_use.mcp_server import (
    _call_tool,
    _failure_for_result,
    _save_ui_snapshot,
)
from computer_use.tool_contract import (
    InvalidToolName,
    TASK_STEP_TOOL_NAMES,
    normalize_nested_tool_name,
)

logger = logging.getLogger(__name__)
MAX_TASK_STEPS = 100


def _validate_task_steps(steps: list[dict[str, Any]]) -> None:
    expanded_steps = 0
    for index, step in enumerate(steps):
        tool_name = step.get("tool")
        if not tool_name:
            raise ValueError(f"step {index} is missing 'tool'")

        expanded_steps += 1
        if tool_name == "batch":
            actions = (step.get("args") or {}).get("actions") or []
            expanded_steps += len(actions)

    if expanded_steps > MAX_TASK_STEPS:
        raise ValueError(
            f"Task exceeds step budget of {MAX_TASK_STEPS} expanded steps"
        )


def _step_screenshot(trace_id: str, step_index: int | str, monitor: int = 1) -> str | None:
    """Capture a screenshot for a task step and return its path.

    This does not create a separate trace record; the caller attaches the
    returned path to the actual step record via ``trace_context``.
    """
    try:
        cs = get_coordinate_system()
        from computer_use.safety import validate_monitor_index

        validate_monitor_index(monitor, len(cs.get_monitors()))
        screenshot_dir = trace_module.artifact_dir(trace_id, "screenshots")
        timestamp = datetime.now(timezone.utc)
        filename = timestamp.strftime("%Y%m%dT%H%M%S_%f")[:-3]
        save_path = str(
            screenshot_dir / f"task_{trace_id}_step_{step_index}_m{monitor}_{filename}.png"
        )
        saved = save_screenshot(save_path, monitor=monitor)
        return str(saved)
    except Exception as exc:
        logger.warning("step screenshot failed: %s", exc)
        return None


def run_task_plan(
    steps: list[dict[str, Any]],
    trace_id: str | None = None,
    goal: str | None = None,
    final_state: bool = False,
    capture_screenshots: bool = True,
) -> dict[str, Any]:
    """Execute a structured task plan and produce a trace + report.

    Args:
        steps: List of ``{"tool": ..., "args": ...}`` dicts.
        trace_id: Optional trace ID to reuse; otherwise one is generated.
        goal: Optional task goal, written into ``report.md``.
        final_state: If True, capture a final UI snapshot + screenshot.
        capture_screenshots: If True, capture a screenshot before each step.

    Returns:
        Dict with ``trace_id``, ``results``, ``report_path``, and optionally
        ``final_state_path``.
    """
    if not steps:
        raise ValueError("steps must contain at least one entry")
    _validate_task_steps(steps)

    trace_id = trace_id or trace_module.generate_trace_id()
    trace_module.create_trace_root(trace_id)
    if goal is not None:
        trace_module.write_trace_meta(trace_id, goal=goal)
    results: list[dict[str, Any]] = []
    failed_index: int | None = None

    for i, step in enumerate(steps):
        requested_tool = step.get("tool")
        try:
            tool_name = normalize_nested_tool_name(
                requested_tool,
                allowed_tools=TASK_STEP_TOOL_NAMES,
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
                        "allowed_tools": list(TASK_STEP_TOOL_NAMES),
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                }
            )
            failed_index = i
            break

        tool_args = step.get("args") or {}
        step_index = i + 1

        screenshot_path = None
        if capture_screenshots:
            screenshot_path = _step_screenshot(trace_id, step_index)

        trace_context: dict[str, Any] = {"trace_id": trace_id, "step_index": step_index}
        if screenshot_path:
            trace_context["screenshot_path"] = screenshot_path

        result_text = _call_tool(
            tool_name,
            tool_args,
            trace_context=trace_context,
        )
        try:
            result_data = json.loads(result_text)
        except json.JSONDecodeError:
            result_data = result_text

        entry: dict[str, Any] = {
            "index": i,
            "tool": tool_name,
            "requested_tool": requested_tool,
            "result": result_data,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        }
        if screenshot_path:
            entry["screenshot_path"] = screenshot_path
        results.append(entry)

        if _failure_for_result(result_data) is not None:
            failed_index = i
            break

    final_state_path: str | None = None
    if final_state:
        try:
            snapshot_result = snapshot.get_ui_snapshot(
                scope="foreground",
                include_screenshot=True,
                trace_id=trace_id,
            )
            if isinstance(snapshot_result, dict) and "error" not in snapshot_result:
                final_state_path = _save_ui_snapshot(snapshot_result, trace_id)
            elif isinstance(snapshot_result, dict):
                final_state_path = None
                logger.warning("final state snapshot failed: %s", snapshot_result.get("error"))
        except Exception as exc:
            logger.warning("final state capture failed: %s", exc)

    report_path = trace_module.generate_report(trace_id, goal=goal, final_state_path=final_state_path)

    top_level_error_kind = None
    if failed_index is not None and failed_index < len(results):
        failed_entry = results[failed_index]
        failure = _failure_for_result(failed_entry.get("result", failed_entry))
        if failure is not None:
            top_level_error_kind = failure[0]

    response: dict[str, Any] = {
        "trace_id": trace_id,
        "results": results,
        "report_path": str(report_path),
        "status": "failed" if failed_index is not None else "succeeded",
        "failed_index": failed_index,
        "error_kind": top_level_error_kind,
        "executed_count": len(results),
        "requested_count": len(steps),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }
    if final_state:
        response["final_state_path"] = final_state_path
    return response


def retry_step(
    trace_id: str,
    step_index: int,
    mode: str = "single",
    retry_suffix: str | None = None,
) -> dict[str, Any]:
    """Re-execute a step from an existing trace.

    Args:
        trace_id: Trace ID of the original task.
        step_index: Original step index to retry.
        mode: ``single`` to replay only that step, ``from_step`` to replay the
            step and all subsequent steps.
        retry_suffix: Optional suffix for the new trace step index. If omitted,
            the next available retry number is computed.

    Returns:
        Dict with the replayed result(s).
    """
    records = trace_module.read_trace(trace_id)
    if not records:
        return {"error": "trace_not_found", "trace_id": trace_id}

    original_records = [r for r in records if r.get("step_index") == step_index and r.get("tool") != "batch"]
    if not original_records:
        return {
            "error": "step_not_found",
            "trace_id": trace_id,
            "step_index": step_index,
        }

    original = original_records[0]
    if original.get("replayable") is False:
        return {
            "error": "retry_not_supported_for_redacted_step",
            "trace_id": trace_id,
            "step_index": step_index,
        }
    subsequent: list[dict[str, Any]] = []
    if mode == "from_step":
        subsequent = [
            record
            for record in records
            if isinstance(record.get("step_index"), int)
            and record["step_index"] > step_index
            and record.get("tool") != "batch"
        ]
        non_replayable = next(
            (
                record
                for record in subsequent
                if record.get("replayable") is False
            ),
            None,
        )
        if non_replayable is not None:
            return {
                "error": "retry_not_supported_for_redacted_step",
                "trace_id": trace_id,
                "step_index": non_replayable["step_index"],
            }
    tool_name = original["tool"]
    tool_args = original.get("args", {})

    if retry_suffix is None:
        retry_count = sum(
            1
            for r in records
            if isinstance(r.get("step_index"), str)
            and str(r["step_index"]).startswith(f"{step_index}.retry.")
        )
        retry_suffix = f"{step_index}.retry.{retry_count + 1}"

    result_text = _call_tool(
        tool_name,
        tool_args,
        trace_context={"trace_id": trace_id, "step_index": retry_suffix},
    )
    try:
        result_data = json.loads(result_text)
    except json.JSONDecodeError:
        result_data = result_text

    response: dict[str, Any] = {
        "trace_id": trace_id,
        "original_step_index": step_index,
        "retry_step_index": retry_suffix,
        "mode": mode,
        "result": result_data,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }

    if mode == "from_step":
        subsequent_results: list[dict[str, Any]] = []
        for rec in subsequent:
            next_retry_count = sum(
                1
                for r in records
                if isinstance(r.get("step_index"), str)
                and str(r["step_index"]).startswith(f"{rec['step_index']}.retry.")
            )
            next_suffix = f"{rec['step_index']}.retry.{next_retry_count + 1}"
            sub_text = _call_tool(
                rec["tool"],
                rec.get("args", {}),
                trace_context={"trace_id": trace_id, "step_index": next_suffix},
            )
            try:
                sub_data = json.loads(sub_text)
            except json.JSONDecodeError:
                sub_data = sub_text
            subsequent_results.append({
                "original_step_index": rec["step_index"],
                "retry_step_index": next_suffix,
                "result": sub_data,
            })
        response["subsequent_results"] = subsequent_results

    return response
