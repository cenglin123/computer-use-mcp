"""Deterministic trace review and summary generation.

``review_task`` reads a trace file and produces a structured summary without
using any LLM. Future LLM-powered summarization is intentionally kept on the
client side.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from computer_use import trace as trace_module


def _parse_timestamp(value: str) -> datetime:
    """Best-effort parse an ISO timestamp."""
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.now(timezone.utc)


def review_task(trace_id: str, detail: bool = False) -> dict[str, Any]:
    """Generate a deterministic summary for the given trace.

    Returns a dict with goal, counts, error distribution, timing stats, and
    screenshot/snapshot indexes. Does not call any LLM.

    When ``detail=True``, adds a ``"steps"`` list with per-step records.
    Persisted traces are sanitized at write time, and review sanitizes again so
    older or manually written trace files do not leak sensitive values.
    """
    records = trace_module.read_trace(trace_id)
    if not records:
        return {"error": "trace_not_found", "trace_id": trace_id}

    meta = trace_module.read_trace_meta(trace_id)
    goal = meta.get("goal")

    total = len(records)
    errors = [r for r in records if r.get("error_kind")]
    successful = total - len(errors)

    error_distribution: dict[str, int] = {}
    for rec in errors:
        kind = rec.get("error_kind") or "unknown"
        error_distribution[kind] = error_distribution.get(kind, 0) + 1

    durations = [r.get("duration_ms", 0) for r in records if isinstance(r.get("duration_ms"), (int, float))]
    total_duration_ms = sum(durations)
    avg_duration_ms = int(total_duration_ms / len(durations)) if durations else 0

    screenshots = [r["screenshot_path"] for r in records if r.get("screenshot_path")]
    snapshots = [r["ui_snapshot_path"] for r in records if r.get("ui_snapshot_path")]

    retry_count = sum(
        1 for r in records
        if isinstance(r.get("step_index"), str) and ".retry." in r["step_index"]
    )

    start_time = ""
    end_time = ""
    if records:
        start_time = records[0].get("start_time", "")
        end_time = records[-1].get("start_time", "")

    result = {
        "trace_id": trace_id,
        "goal": goal,
        "summary": {
            "total_steps": total,
            "successful_steps": successful,
            "failed_steps": len(errors),
            "retry_steps": retry_count,
            "total_duration_ms": total_duration_ms,
            "average_duration_ms": avg_duration_ms,
        },
        "error_distribution": error_distribution,
        "step_index_range": {
            "first": records[0].get("step_index") if records else None,
            "last": records[-1].get("step_index") if records else None,
        },
        "timing": {
            "start_time": start_time,
            "end_time": end_time,
        },
        "screenshots": screenshots,
        "snapshots": snapshots,
        "improvement_suggestions_placeholder": "Future work: client-side LLM can summarize error patterns here.",
    }

    if detail:
        steps = []
        for rec in records:
            args, step_result, error_message = trace_module.sanitize_trace_payload(
                rec.get("args", {}),
                rec.get("result"),
                rec.get("error_message"),
            )
            steps.append(
                {
                    "step_index": rec.get("step_index"),
                    "tool": rec.get("tool", ""),
                    "args": args,
                    "result": step_result,
                    "duration_ms": rec.get("duration_ms", 0),
                    "screenshot_path": rec.get("screenshot_path"),
                    "ui_snapshot_path": rec.get("ui_snapshot_path"),
                    "error_kind": rec.get("error_kind"),
                    "error_message": error_message,
                }
            )
        result["steps"] = steps

    return result


def generate_deterministic_report(trace_id: str, goal: str | None = None) -> Path:
    """Generate ``report.md`` using the existing trace report generator."""
    return trace_module.generate_report(trace_id, goal=goal)


def review_task_session(task_id: str, detail: bool = False) -> dict[str, Any]:
    """Generate a deterministic summary for a business task session."""
    from computer_use import task_session

    task = task_session.get_task(task_id)
    reviewed_traces: list[dict[str, Any]] = []
    error_distribution: dict[str, int] = {}
    total_steps = 0
    trace_data_for_timing: list[dict[str, Any]] = []
    for link in task.get("traces", []):
        trace_id = link.get("trace_id")
        if not isinstance(trace_id, str):
            continue
        trace_review = review_task(trace_id, detail=detail)
        if trace_review.get("error"):
            reviewed_traces.append({**link, "review": trace_review})
            continue
        total_steps += trace_review["summary"]["total_steps"]
        for kind, count in trace_review.get("error_distribution", {}).items():
            error_distribution[kind] = error_distribution.get(kind, 0) + count
        reviewed_traces.append({**link, "review": trace_review})
        # Collect timing data for breakdown
        trace_data_for_timing.append({
            "trace_id": trace_id,
            "started_at": link.get("started_at"),
            "finished_at": link.get("finished_at"),
            "total_duration_ms": trace_review["summary"].get("total_duration_ms", 0),
        })

    result = {
        "task_id": task_id,
        "goal": task.get("goal"),
        "status": task.get("status"),
        "trace_count": task.get("trace_count", 0),
        "failed_trace_count": task.get("failed_trace_count", 0),
        "active_trace_count": task.get("active_trace_count", 0),
        "total_steps": total_steps,
        "error_distribution": error_distribution,
        "traces": reviewed_traces,
        "timing_breakdown": _summarize_timing(trace_data_for_timing),
    }
    return result


def _summarize_timing(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate wall-clock, tool duration, and agent gap time from a list of trace timing records.

    All durations are in milliseconds.
    """
    if not traces:
        return {
            "trace_count": 0,
            "tool_duration_ms": 0,
            "wall_clock_duration_ms": 0,
            "agent_gap_duration_ms": 0,
            "agent_gap_ratio": 0.0,
        }

    starts = [_parse_timestamp(t["started_at"]) for t in traces if t.get("started_at")]
    ends = [_parse_timestamp(t["finished_at"]) for t in traces if t.get("finished_at")]
    wall_clock_ms = int((max(ends) - min(starts)).total_seconds() * 1000) if starts and ends else 0
    tool_ms = sum(int(t.get("total_duration_ms", 0)) for t in traces)
    gap_ms = max(0, wall_clock_ms - tool_ms)

    return {
        "trace_count": len(traces),
        "tool_duration_ms": tool_ms,
        "wall_clock_duration_ms": wall_clock_ms,
        "agent_gap_duration_ms": gap_ms,
        "agent_gap_ratio": (gap_ms / wall_clock_ms) if wall_clock_ms else 0.0,
    }
