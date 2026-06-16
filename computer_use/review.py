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


def review_task(trace_id: str) -> dict[str, Any]:
    """Generate a deterministic summary for the given trace.

    Returns a dict with goal, counts, error distribution, timing stats, and
    screenshot/snapshot indexes. Does not call any LLM.
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

    return {
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


def generate_deterministic_report(trace_id: str, goal: str | None = None) -> Path:
    """Generate ``report.md`` using the existing trace report generator."""
    return trace_module.generate_report(trace_id, goal=goal)


def review_task_session(task_id: str) -> dict[str, Any]:
    """Generate a deterministic summary for a business task session."""
    from computer_use import task_session

    task = task_session.get_task(task_id)
    reviewed_traces: list[dict[str, Any]] = []
    error_distribution: dict[str, int] = {}
    total_steps = 0
    for link in task.get("traces", []):
        trace_id = link.get("trace_id")
        if not isinstance(trace_id, str):
            continue
        trace_review = review_task(trace_id)
        if trace_review.get("error"):
            reviewed_traces.append({**link, "review": trace_review})
            continue
        total_steps += trace_review["summary"]["total_steps"]
        for kind, count in trace_review.get("error_distribution", {}).items():
            error_distribution[kind] = error_distribution.get(kind, 0) + count
        reviewed_traces.append({**link, "review": trace_review})

    return {
        "task_id": task_id,
        "goal": task.get("goal"),
        "status": task.get("status"),
        "trace_count": task.get("trace_count", 0),
        "failed_trace_count": task.get("failed_trace_count", 0),
        "active_trace_count": task.get("active_trace_count", 0),
        "total_steps": total_steps,
        "error_distribution": error_distribution,
        "traces": reviewed_traces,
    }
